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
) -> None:
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        ckpt = torch.load(
            checkpoint_path, map_location=device, weights_only=False
        )
        net = CarcassonneNet(
            n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
        ).to(device)
        net.load_state_dict(ckpt["model_state"])
        net.train(False)

        # Force CUDA init + cuDNN kernel selection BEFORE signaling ready,
        # so the first real request doesn't pay the ~1-2s warmup cost.
        if device.type == "cuda":
            with torch.no_grad():
                _ = net(
                    torch.zeros(1, N_CHANNELS, 25, 25, device=device),
                    torch.zeros(1, N_SCALAR_FEATURES, device=device),
                )
                torch.cuda.synchronize()
        ready_event.set()
    except Exception as e:
        sys.stderr.write(
            f"[eval_server] init FAILED: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}\n"
        )
        sys.stderr.flush()
        return

    timeout_s = batch_timeout_ms / 1000.0
    while True:
        try:
            first = request_q.get()
        except (KeyboardInterrupt, SystemExit):
            return
        if first == _SHUTDOWN:
            return

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

        try:
            _process_batch(batch, net, device, response_qs, use_fp16)
        except Exception as e:
            sys.stderr.write(
                f"[eval_server] forward FAILED: {type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}\n"
            )
            sys.stderr.flush()
            # Best-effort: tell each waiting worker we failed so they don't hang.
            for r in batch:
                try:
                    response_qs[r.worker_id].put(
                        EvalResponse(
                            request_id=r.request_id,
                            priors=np.zeros((r.obs.shape[0], 1), dtype=np.float32),
                            values=np.zeros((r.obs.shape[0],), dtype=np.float32),
                        )
                    )
                except Exception:
                    pass
            return

        if saw_shutdown:
            return


def _process_batch(
    batch: list[EvalRequest],
    net: CarcassonneNet,
    device: torch.device,
    response_qs: list[Any],
    use_fp16: bool,
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
        logits, values = net(obs_t, scalars_t)
        priors = net.policy_softmax_with_mask(logits, mask_t)
    priors_np = priors.float().cpu().numpy()
    values_np = values.float().cpu().numpy()

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


def start_server(
    checkpoint_path: str | Path,
    n_workers: int,
    max_batch: int = 256,
    batch_timeout_ms: float = 2.0,
    use_fp16: bool = False,
    ready_timeout_s: float = 60.0,
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
        ),
        daemon=False,
    )
    proc.start()
    if not ready_event.wait(timeout=ready_timeout_s):
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=2.0)
        raise RuntimeError(
            f"eval_server({checkpoint_path}) failed to become ready "
            f"within {ready_timeout_s}s"
        )
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
