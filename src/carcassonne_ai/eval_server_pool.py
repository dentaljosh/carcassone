"""Multi-process eval-server pool — cracks the GIL bottleneck of the
single-server orchestrator.

The single-server design (eval_server.start_server) loads one net on the
GPU and runs a Python dispatch loop that batches requests from N workers.
That dispatch loop is GIL-bound to one CPU core; on workloads where the
GPU can chew through batches faster than the dispatcher can hand them
out, the GPU sits idle and total throughput is gated by the single
Python process.

This pool spawns M independent servers, each owning its own net copy
(~2 GB VRAM each) and a dedicated request_q. Workers are sharded by
`worker_id % M` to one server permanently for the lifetime of the run —
no cross-server coordination, no shared mutable state, no runtime
adaptation. Each server's GIL bottleneck is now independent, so total
dispatch capacity is M × (one Python loop).

Why static sharding and not dynamic load-balancing: workloads here are
homogeneous (every self-play game runs the same sims/move, same batch
shape, same wallclock distribution). Adaptive routing buys nothing on
homogeneous traffic, costs cross-server measurement and routing-decision
overhead. Static `worker_id % M` is the right answer at our regime.

Lifecycle:

    pool = start_server_pool(checkpoint_path, n_workers=80, n_shards=4)
    # pool.handles_by_worker[w] gives the ServerHandles for global worker w.
    # Distribute pool.handles_by_worker[w] to worker w via its init cfg.
    ...
    shutdown_server_pool(pool)

VRAM budget: each shard loads its own net. For our 96×6 net (~30 MB) the
allocator pool is ~2 GB per server. M=4 = 8 GB, well under the 32 GB
budget. If we ever go to a 70M-param net + M=8, this needs reconsidering.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from .eval_server import ServerHandles, shutdown_server, start_server


@dataclasses.dataclass
class ServerPool:
    """Bundle of all per-shard process+queue handles plus the worker→shard map.

    Attributes:
        procs: M server processes, in shard order.
        request_qs: M request queues, in shard order.
        handles_by_worker: list of length n_workers; entry w is the
            ServerHandles to give to global worker w.
    """
    procs: list[Any]
    request_qs: list[Any]
    handles_by_worker: list[ServerHandles]


def start_server_pool(
    checkpoint_path: str | Path,
    n_workers: int,
    n_shards: int = 1,
    max_batch: int = 256,
    batch_timeout_ms: float = 2.0,
    use_fp16: bool = False,
    ready_timeout_s: float = 60.0,
    policy_only: bool = False,
) -> ServerPool:
    """Spawn n_shards server processes and return a routing pool.

    n_shards == 1 is identical to the old start_server (single server,
    same VRAM). n_shards > 1 spawns multiple servers; each holds its own
    net copy.

    Worker sharding: global worker w → shard (w % n_shards). Within each
    shard, the global worker w's local index is (w // n_shards), which
    indexes into that shard's response_qs list.
    """
    if n_shards < 1:
        raise ValueError(f"n_shards must be >= 1; got {n_shards}")
    if n_workers < 1:
        raise ValueError(f"n_workers must be >= 1; got {n_workers}")

    procs: list[Any] = []
    request_qs: list[Any] = []
    response_qs_by_shard: list[list[Any]] = []

    # Compute per-shard worker assignments first so each server is told
    # exactly how many response_qs to allocate.
    worker_ids_per_shard: list[list[int]] = [[] for _ in range(n_shards)]
    for w in range(n_workers):
        worker_ids_per_shard[w % n_shards].append(w)

    for shard_id in range(n_shards):
        shard_worker_count = len(worker_ids_per_shard[shard_id])
        if shard_worker_count == 0:
            # Possible if n_shards > n_workers. Skip empty shards.
            procs.append(None)
            request_qs.append(None)
            response_qs_by_shard.append([])
            continue
        proc, request_q, response_qs = start_server(
            checkpoint_path=checkpoint_path,
            n_workers=shard_worker_count,
            max_batch=max_batch,
            batch_timeout_ms=batch_timeout_ms,
            use_fp16=use_fp16,
            ready_timeout_s=ready_timeout_s,
            policy_only=policy_only,
        )
        procs.append(proc)
        request_qs.append(request_q)
        response_qs_by_shard.append(response_qs)

    # Build the global-worker → ServerHandles map. Each worker's local index
    # within its shard is its position in worker_ids_per_shard[shard_id].
    handles_by_worker: list[ServerHandles] = [None] * n_workers  # type: ignore
    for shard_id, worker_ids in enumerate(worker_ids_per_shard):
        for local_idx, global_w in enumerate(worker_ids):
            handles_by_worker[global_w] = ServerHandles(
                request_q=request_qs[shard_id],
                response_q=response_qs_by_shard[shard_id][local_idx],
                worker_id=local_idx,
            )

    return ServerPool(
        procs=procs,
        request_qs=request_qs,
        handles_by_worker=handles_by_worker,
    )


def shutdown_server_pool(pool: ServerPool, timeout_s: float = 10.0) -> None:
    """Shut down every server in the pool. Idempotent on already-dead shards."""
    for proc, request_q in zip(pool.procs, pool.request_qs):
        if proc is None or request_q is None:
            continue
        shutdown_server(proc, request_q, timeout_s=timeout_s)
