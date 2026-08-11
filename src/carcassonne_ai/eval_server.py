"""GPU inference-server for orchestrator mode.

Replaces the per-worker network-load pattern: one server process owns the
net and CUDA context; N CPU-only workers send (obs, scalars, mask) over IPC
and receive (priors, values). The server batches across workers for GPU
efficiency, which lifts utilization on workloads where each worker's batch
(e.g. virtual-loss batch_size=8) is too small to saturate the GPU.

Numerically identical to `make_batch_evaluator` on the same inputs, modulo
batch-stacking order (which can shift fp32 reduction order). Same float
precision (fp32 default; fp16 autocast on CUDA).

Lifecycle:

    proc, request_q, response_qs = start_server(checkpoint_path, n_workers=N)
    # Distribute response_qs[w] to worker w.
    # Workers call make_remote_batch_evaluator(ServerHandles(request_q, response_qs[w], w), game).
    ...
    shutdown_server(proc, request_q)
"""
from __future__ import annotations

import dataclasses
import multiprocessing as mp
import queue as _stdlib_queue
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .board_repr import N_CHANNELS
from .features import N_SCALAR_FEATURES
from .network import CarcassonneNet


_SHUTDOWN = "_SHUTDOWN_SENTINEL"


@dataclasses.dataclass
class EvalRequest:
    """One sub-batch from a single worker.

    `obs`/`scalars`/`mask` are NumPy arrays with leading dim k_i (≥1).
    The server concatenates many requests into one big forward pass.
    """
    worker_id: int
    request_id: int
    obs: np.ndarray         # (k, C, H, W) float32
    scalars: np.ndarray     # (k, S) float32
    mask: np.ndarray        # (k, A) bool


@dataclasses.dataclass
class EvalResponse:
    request_id: int
    priors: np.ndarray      # (k, A) float32
    values: np.ndarray      # (k,) float32


@dataclasses.dataclass
class ServerHandles:
    """Bundle of IPC handles needed by one worker to talk to the server."""
    request_q: Any           # shared mp.Queue, server consumes
    response_q: Any          # this worker's mp.Queue, only this worker reads
    worker_id: int           # index into the server's response_qs list


def _server_loop(
    checkpoint_path: str,
    request_q: Any,
    response_qs: list[Any],
    ready_event: Any,
    max_batch: int,
    batch_timeout_ms: float,
    use_fp16: bool,
    policy_only: bool = False,
) -> None:
    try:
        if torch.cuda.is_available():
            device = torch.device("cuda")
        elif torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")
        ckpt = torch.load(
            checkpoint_path, map_location=device, weights_only=False
        )
        # Scalar width follows the checkpoint (Path B Step E: 12 with farm
        # scalars, else 10). The worker building inputs MUST use a Game with the
        # matching include_farm_scalars so the tensor it sends is this wide.
        n_scalar = int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES))
        # n_input_channels + value_global_pool ride in the checkpoint (defaults 78
        # / False for pre-M2 checkpoints). Reading them fixes two latent gaps: a
        # global-pool checkpoint previously mismatched value_fc1 here (built
        # pool-off), and a sighted (81ch) net mismatched the stem conv.
        n_input_channels = int(ckpt.get("n_input_channels", N_CHANNELS))
        net = CarcassonneNet(
            n_filters=ckpt["n_filters"],
            n_blocks=ckpt["n_blocks"],
            n_input_channels=n_input_channels,
            n_scalar_features=n_scalar,
            value_global_pool=bool(ckpt.get("value_global_pool", False)),
        ).to(device)
        net.load_state_dict(ckpt["model_state"])
        net.train(False)

        # Force accelerator init + kernel selection BEFORE signaling ready,
        # so the first real request doesn't pay the ~1-2s warmup cost.
        if device.type in ("cuda", "mps"):
            with torch.no_grad():
                _ = net(
                    torch.zeros(1, n_input_channels, 25, 25, device=device),
                    torch.zeros(1, n_scalar, device=device),
                )
                if device.type == "cuda":
                    torch.cuda.synchronize()
                else:
                    torch.mps.synchronize()
        ready_event.set()
    except Exception as e:
        sys.stderr.write(
            f"[eval_server] init FAILED: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}\n"
        )
        sys.stderr.flush()
        return

    timeout_s = batch_timeout_ms / 1000.0
    # Stage timers (server-internal only — logged at shutdown). Per-stage
    # cumulative wallclock; the ratio of forward / batching / dispatch tells
    # us where the GIL-bottlenecked Python loop is actually spending its
    # time, which informs whether multi-process sharding is the right fix.
    stage_t = {"wait_first": 0.0, "accumulate": 0.0, "forward": 0.0, "dispatch": 0.0}
    n_batches = 0
    total_requests = 0
    total_examples = 0

    while True:
        t_wf0 = time.perf_counter()
        try:
            # Poll with a timeout rather than block forever. A bare get()
            # parks in a C-level semaphore where Python signal handlers
            # cannot run, so an unclean parent exit (no _SHUTDOWN sent)
            # would leave this process — and its CUDA context / VRAM —
            # hung indefinitely. The 1s wakeup lets a signal land.
            # wait_first = time blocked here = server STARVED (no work in queue);
            # accumulate = time pulling more to fill the batch = queue/contention.
            while True:
                try:
                    first = request_q.get(timeout=1.0)
                    break
                except _stdlib_queue.Empty:
                    pass
        except (KeyboardInterrupt, SystemExit):
            return
        stage_t["wait_first"] += time.perf_counter() - t_wf0
        if first == _SHUTDOWN:
            break

        t_acc0 = time.perf_counter()
        batch: list[EvalRequest] = [first]
        total_k = first.obs.shape[0]
        deadline = time.perf_counter() + timeout_s
        saw_shutdown = False
        while total_k < max_batch:
            wait = max(0.0, deadline - time.perf_counter())
            try:
                r = request_q.get(timeout=wait)
            except _stdlib_queue.Empty:
                break
            if r == _SHUTDOWN:
                saw_shutdown = True
                break
            batch.append(r)
            total_k += r.obs.shape[0]
        stage_t["accumulate"] += time.perf_counter() - t_acc0

        try:
            t_fw0 = time.perf_counter()
            _process_batch(batch, net, device, response_qs, use_fp16, stage_t, policy_only)
            stage_t["forward"] += time.perf_counter() - t_fw0
            n_batches += 1
            total_requests += len(batch)
            total_examples += total_k
        except Exception as e:
            sys.stderr.write(
                f"[eval_server] forward FAILED: {type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}\n"
            )
            sys.stderr.flush()
            # Best-effort: tell each waiting worker in this batch we failed so
            # it doesn't block on a response that will never arrive. The stub
            # priors must match the request's mask shape (k, A) — a (k, 1)
            # stub silently corrupts the caller's policy vector.
            for r in batch:
                try:
                    response_qs[r.worker_id].put(
                        EvalResponse(
                            request_id=r.request_id,
                            priors=np.zeros(r.mask.shape, dtype=np.float32),
                            values=np.zeros((r.obs.shape[0],), dtype=np.float32),
                        )
                    )
                except Exception:
                    pass
            # Re-raise rather than return: a forward failure is not
            # recoverable in place (a corrupt CUDA context would just spew
            # stub batches). Crash the server loudly — workers past this batch
            # get a clean BrokenServerError instead of an unexplained hang.
            raise

        if saw_shutdown:
            break

    # Log stage timings on graceful shutdown. Helps assess whether the
    # dispatcher Python loop is the bottleneck (forward << dequeue+dispatch
    # → yes; otherwise the GPU forward dominates and multi-process won't
    # help much).
    if n_batches > 0:
        avg_batch = total_examples / n_batches
        total = sum(stage_t.values())
        pct = {k: 100 * v / total if total > 0 else 0 for k, v in stage_t.items()}
        sys.stderr.write(
            f"[eval_server] timing: {n_batches} batches, "
            f"{total_requests} requests, {total_examples} examples, "
            f"avg_batch={avg_batch:.1f}\n"
            f"[eval_server] stages: "
            f"wait_first={stage_t['wait_first']:.1f}s ({pct['wait_first']:.0f}%, =STARVED), "
            f"accumulate={stage_t['accumulate']:.1f}s ({pct['accumulate']:.0f}%), "
            f"forward={stage_t['forward']:.1f}s ({pct['forward']:.0f}%), "
            f"dispatch={stage_t['dispatch']:.1f}s ({pct['dispatch']:.0f}%)\n"
        )
        sys.stderr.flush()


def _process_batch(
    batch: list[EvalRequest],
    net: CarcassonneNet,
    device: torch.device,
    response_qs: list[Any],
    use_fp16: bool,
    stage_t: dict | None = None,
    policy_only: bool = False,
) -> None:
    if not batch:
        return
    obs = np.concatenate([r.obs for r in batch], axis=0)
    scalars = np.concatenate([r.scalars for r in batch], axis=0)
    mask = np.concatenate([r.mask for r in batch], axis=0)

    obs_t = torch.from_numpy(obs).float().to(device)
    scalars_t = torch.from_numpy(scalars).float().to(device)
    mask_t = torch.from_numpy(mask.copy()).bool().to(device)

    if use_fp16 and device.type == "cuda":
        autocast_ctx = torch.amp.autocast(device_type="cuda", dtype=torch.float16)
    else:
        autocast_ctx = torch.amp.autocast(device_type="cpu", enabled=False)

    with torch.no_grad(), autocast_ctx:
        if policy_only:
            logits = net.forward_policy_only(obs_t, scalars_t)
            priors = net.policy_softmax_with_mask(logits, mask_t)
            # Stub values; caller must override (e.g. v2.5 leaf wrapper).
            values_np = np.zeros((obs_t.shape[0],), dtype=np.float32)
        else:
            logits, values = net(obs_t, scalars_t)
            priors = net.policy_softmax_with_mask(logits, mask_t)
            values_np = values.float().cpu().numpy()
    priors_np = priors.float().cpu().numpy()

    t_dp0 = time.perf_counter() if stage_t is not None else 0.0
    offset = 0
    for r in batch:
        k = r.obs.shape[0]
        response_qs[r.worker_id].put(
            EvalResponse(
                request_id=r.request_id,
                priors=priors_np[offset:offset + k],
                values=values_np[offset:offset + k],
            )
        )
        offset += k
    if stage_t is not None:
        dispatch_t = time.perf_counter() - t_dp0
        stage_t["dispatch"] += dispatch_t
        # Subtract dispatch from the "forward" bucket we started outside this
        # function; counted twice otherwise.
        stage_t["forward"] -= dispatch_t


def start_server(
    checkpoint_path: str | Path,
    n_workers: int,
    max_batch: int = 256,
    batch_timeout_ms: float = 2.0,
    use_fp16: bool = False,
    ready_timeout_s: float = 60.0,
    policy_only: bool = False,
) -> tuple[Any, Any, list[Any]]:
    """Spawn the server process and return (proc, request_q, response_qs).

    Blocks until the server signals readiness (after CUDA warmup). Raises
    RuntimeError on timeout.

    Caller is responsible for:
    - Passing response_qs[worker_id] to each worker via its `_worker_init` cfg
    - Eventually calling `shutdown_server(proc, request_q)`
    """
    ctx = mp.get_context("spawn")
    request_q = ctx.Queue()
    response_qs = [ctx.Queue() for _ in range(n_workers)]
    ready_event = ctx.Event()
    proc = ctx.Process(
        target=_server_loop,
        args=(
            str(checkpoint_path),
            request_q,
            response_qs,
            ready_event,
            max_batch,
            batch_timeout_ms,
            use_fp16,
            policy_only,
        ),
        daemon=False,
    )
    proc.start()
    # Wait for readiness, polling process liveness too. If init fails the
    # server logs to stderr and exits without ever setting ready_event; a
    # plain wait(timeout) would then block the full ready_timeout_s before
    # we notice. Polling catches a dead server in <1s.
    deadline = time.monotonic() + ready_timeout_s
    while not ready_event.is_set():
        if not proc.is_alive():
            proc.join()
            raise RuntimeError(
                f"eval_server({checkpoint_path}) exited during init "
                f"(exitcode={proc.exitcode}) — see stderr above"
            )
        if time.monotonic() >= deadline:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=2.0)
            raise RuntimeError(
                f"eval_server({checkpoint_path}) failed to become ready "
                f"within {ready_timeout_s}s"
            )
        ready_event.wait(timeout=0.25)
    return proc, request_q, response_qs


def shutdown_server(
    proc: Any, request_q: Any, timeout_s: float = 10.0
) -> None:
    """Send SHUTDOWN, then join the server process. Force-terminate on timeout."""
    try:
        request_q.put(_SHUTDOWN)
    except Exception:
        pass
    proc.join(timeout=timeout_s)
    if proc.is_alive():
        sys.stderr.write(
            f"[eval_server] WARNING: server did not exit in {timeout_s}s; "
            f"terminating\n"
        )
        sys.stderr.flush()
        proc.terminate()
        proc.join(timeout=2.0)
    # Release the queue's feeder thread. If the server died without draining
    # request_q, the parent's background feeder thread would otherwise block
    # at interpreter exit trying to flush buffered items — hanging the parent.
    try:
        request_q.close()
        request_q.cancel_join_thread()
    except Exception:
        pass
