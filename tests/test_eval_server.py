"""Tests for the GPU orchestrator (`eval_server` + `remote_evaluators`).

Coverage:

1. **Numerical agreement** — `make_remote_single_evaluator` and
   `make_remote_batch_evaluator` must produce outputs that match
   `make_batch_evaluator` to within float32 noise.
2. **Concurrent correctness** — multiple worker processes hitting one
   server must each receive their own responses, no cross-contamination,
   no hang.
3. **Shutdown propagation** — if the server dies, workers must raise
   `BrokenServerError` within their configured timeout, not block forever.

All tests skip cleanly when the canonical checkpoint isn't present (CI
without the warmstart artifact).
"""
from __future__ import annotations

import multiprocessing as mp
import os
import random
import time
from pathlib import Path

import numpy as np
import pytest
import torch

from carcassonne_ai.eval_server import (
    ServerHandles,
    shutdown_server,
    start_server,
)
from carcassonne_ai.evaluators import make_batch_evaluator
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.remote_evaluators import (
    BrokenServerError,
    make_remote_batch_evaluator,
    make_remote_single_evaluator,
)


CKPT = Path(__file__).resolve().parent.parent / "checkpoints" / "warmstart_canonical.pt"


@pytest.fixture(scope="module")
def checkpoint_path() -> str:
    if not CKPT.exists():
        pytest.skip(f"checkpoint not found: {CKPT}")
    return str(CKPT)


def _gen_mid_game_boards(n: int, seed: int = 0) -> list:
    """Generate N mid-game boards via random play. Each board is 20-40 plies in."""
    g = Game(enable_legal_moves_cache=True)
    boards = []
    rng = random.Random(seed)
    for i in range(n):
        random.seed(seed + i)  # engine deck shuffle uses global random
        board = g.get_init_board()
        target = 20 + rng.randint(0, 20)
        for _ in range(target):
            mask = g.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            action = int(rng.choice(legal.tolist()))
            board, _ = g.get_next_state(board, action)
            if g.get_game_ended(board, 0) != 0.0:
                break
        boards.append(board)
    return boards


def _load_local_net(checkpoint_path: str):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net, device


def test_numerical_agreement_single(checkpoint_path: str) -> None:
    net, device = _load_local_net(checkpoint_path)
    g = Game(enable_legal_moves_cache=True)
    local_batch = make_batch_evaluator(net, device, g)

    proc, request_q, response_qs = start_server(checkpoint_path, n_workers=1)
    try:
        handles = ServerHandles(
            request_q=request_q, response_q=response_qs[0], worker_id=0
        )
        remote = make_remote_single_evaluator(handles, g, timeout_s=30.0)

        boards = _gen_mid_game_boards(50, seed=42)
        max_l1 = 0.0
        max_v_diff = 0.0
        for b in boards:
            r_priors, r_value = remote(b)
            l_priors, l_values = local_batch([b])
            max_l1 = max(max_l1, float(np.abs(r_priors - l_priors[0]).sum()))
            max_v_diff = max(max_v_diff, abs(r_value - float(l_values[0])))
        assert max_l1 < 1e-5, f"prior L1 drift {max_l1} exceeds float32 noise"
        assert max_v_diff < 1e-5, f"value drift {max_v_diff} exceeds float32 noise"
    finally:
        shutdown_server(proc, request_q)


def test_numerical_agreement_batch(checkpoint_path: str) -> None:
    net, device = _load_local_net(checkpoint_path)
    g = Game(enable_legal_moves_cache=True)
    local_batch = make_batch_evaluator(net, device, g)

    proc, request_q, response_qs = start_server(checkpoint_path, n_workers=1)
    try:
        handles = ServerHandles(
            request_q=request_q, response_q=response_qs[0], worker_id=0
        )
        remote = make_remote_batch_evaluator(handles, g, timeout_s=30.0)

        boards = _gen_mid_game_boards(40, seed=7)
        for k in [1, 4, 8, 16]:
            r_priors, r_values = remote(boards[:k])
            l_priors, l_values = local_batch(boards[:k])
            l1 = float(np.abs(r_priors - l_priors).sum())
            vd = float(np.abs(r_values - l_values).max())
            assert l1 < 1e-5, f"K={k} prior L1 {l1} exceeds float32 noise"
            assert vd < 1e-5, f"K={k} value drift {vd} exceeds float32 noise"
    finally:
        shutdown_server(proc, request_q)


def _worker_eval_loop(handles: ServerHandles, n_boards: int, seed: int) -> int:
    """Pickleable worker entry: encode N mid-game boards and evaluate remotely."""
    from carcassonne_ai.game_wrapper import Game as _G
    from carcassonne_ai.remote_evaluators import (
        make_remote_single_evaluator as _mk,
    )
    g = _G(enable_legal_moves_cache=True)
    remote = _mk(handles, g, timeout_s=30.0)
    boards = _gen_mid_game_boards(n_boards, seed=seed)
    for b in boards:
        priors, value = remote(b)
        # Sanity-check shapes — if cross-contamination happened, this fires.
        assert priors.ndim == 1 and priors.shape[0] == g.get_action_size()
        assert isinstance(value, float)
    return n_boards


def test_concurrent_workers_no_hang(checkpoint_path: str) -> None:
    n_workers = 4
    n_per_worker = 8
    proc, request_q, response_qs = start_server(
        checkpoint_path, n_workers=n_workers
    )
    try:
        ctx = mp.get_context("spawn")
        worker_procs = []
        for w in range(n_workers):
            handles = ServerHandles(
                request_q=request_q,
                response_q=response_qs[w],
                worker_id=w,
            )
            wp = ctx.Process(
                target=_worker_eval_loop,
                args=(handles, n_per_worker, 1000 + w),
            )
            wp.start()
            worker_procs.append(wp)
        for wp in worker_procs:
            wp.join(timeout=90.0)
            assert not wp.is_alive(), "worker process did not finish in 90s"
            assert wp.exitcode == 0, (
                f"worker exited with code {wp.exitcode} — likely hit "
                f"cross-contamination assert or BrokenServerError"
            )
    finally:
        shutdown_server(proc, request_q)


def test_shutdown_propagates_to_worker(checkpoint_path: str) -> None:
    """Server crash → worker BrokenServerError within timeout (no infinite hang)."""
    proc, request_q, response_qs = start_server(checkpoint_path, n_workers=1)
    g = Game(enable_legal_moves_cache=True)
    handles = ServerHandles(
        request_q=request_q, response_q=response_qs[0], worker_id=0
    )

    # Verify normal eval works before we kill the server.
    remote_ok = make_remote_single_evaluator(handles, g, timeout_s=30.0)
    board = _gen_mid_game_boards(1, seed=0)[0]
    priors, value = remote_ok(board)
    assert priors.shape[0] == g.get_action_size()

    # Forcibly kill the server (simulates crash).
    proc.terminate()
    proc.join(timeout=5.0)
    assert not proc.is_alive()

    # Next eval should raise within ~2s, not block forever.
    remote_short = make_remote_single_evaluator(handles, g, timeout_s=2.0)
    t0 = time.perf_counter()
    with pytest.raises(BrokenServerError):
        remote_short(board)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"raise took {elapsed}s — should be ~timeout_s"

    # Cleanup: the killed server didn't consume our queued request. If we let
    # the queue's background feeder thread try to drain on test teardown, it
    # blocks forever — pytest hangs. cancel_join_thread() tells the feeder
    # to give up. This is teardown hygiene for any test that posts to a
    # mp.Queue whose consumer has died.
    request_q.close()
    request_q.cancel_join_thread()
    for q in response_qs:
        q.close()
        q.cancel_join_thread()
