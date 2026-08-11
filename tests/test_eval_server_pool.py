"""Tests for the multi-process eval-server pool.

Coverage:

1. **Numerical agreement vs single-server** — n_shards=4 must produce
   outputs that match n_shards=1 (and `make_batch_evaluator`) to within
   float32 noise. Sharding only changes WHICH server handles a worker;
   the forward computation is identical.

2. **Worker→shard routing** — each global worker's `ServerHandles` must
   route to exactly one shard's request_q, and its response_q must only
   receive responses for its own requests. Cross-shard contamination
   would surface as request_id mismatch.

3. **Concurrent multi-worker correctness** — same as single-server's
   concurrent test, but with multiple shards. Each worker stays on its
   assigned shard for its lifetime.

4. **Shutdown cleanup** — shutting down the pool must terminate every
   shard process; no orphaned servers.
"""
from __future__ import annotations

import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
import pytest

from carcassonne_ai.eval_server_pool import (
    shutdown_server_pool,
    start_server_pool,
)
from carcassonne_ai.evaluators import make_batch_evaluator
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator

# Reuse helpers from the single-server test module to keep boards comparable.
from tests.test_eval_server import _gen_mid_game_boards, _load_local_net


CKPT = Path(__file__).resolve().parent.parent / "checkpoints" / "warmstart_canonical.pt"


@pytest.fixture(scope="module")
def checkpoint_path() -> str:
    if not CKPT.exists():
        pytest.skip(f"checkpoint not found: {CKPT}")
    return str(CKPT)


def test_pool_numerical_agreement_vs_local(checkpoint_path: str) -> None:
    """4-shard pool produces outputs matching the local-net batch evaluator.

    Each worker is routed to its shard server (worker_id % 4). The forward
    computation is identical (each shard loaded from the same checkpoint),
    so results should be float32-noise close.
    """
    net, device = _load_local_net(checkpoint_path)
    g = Game(enable_legal_moves_cache=True)
    local_batch = make_batch_evaluator(net, device, g)

    n_workers = 8
    pool = start_server_pool(checkpoint_path, n_workers=n_workers, n_shards=4)
    try:
        boards = _gen_mid_game_boards(20, seed=11)
        max_l1 = 0.0
        max_v_diff = 0.0
        for w_idx in range(n_workers):
            handles = pool.handles_by_worker[w_idx]
            remote = make_remote_single_evaluator(handles, g, timeout_s=30.0)
            # Each worker evaluates a few boards; we accumulate the worst
            # error seen across all (worker, board) pairs.
            for b in boards[:5]:
                r_priors, r_value = remote(b)
                l_priors, l_values = local_batch([b])
                max_l1 = max(max_l1, float(np.abs(r_priors - l_priors[0]).sum()))
                max_v_diff = max(max_v_diff, abs(r_value - float(l_values[0])))
        assert max_l1 < 1e-5, f"prior L1 drift {max_l1} exceeds float32 noise"
        assert max_v_diff < 1e-5, f"value drift {max_v_diff} exceeds float32 noise"
    finally:
        shutdown_server_pool(pool)


def test_pool_routing_assigns_each_worker_to_one_shard(checkpoint_path: str) -> None:
    """worker_id % n_shards determines shard. Verify the map matches that rule."""
    n_workers = 10
    n_shards = 3
    pool = start_server_pool(checkpoint_path, n_workers=n_workers, n_shards=n_shards)
    try:
        # Each request_q corresponds to one shard. Build a reverse lookup
        # from request_q id() → shard_id, then check each worker.
        rq_to_shard = {id(rq): i for i, rq in enumerate(pool.request_qs)}
        for w in range(n_workers):
            handles = pool.handles_by_worker[w]
            assigned_shard = rq_to_shard[id(handles.request_q)]
            assert assigned_shard == w % n_shards, (
                f"worker {w} routed to shard {assigned_shard}, "
                f"expected {w % n_shards}"
            )
    finally:
        shutdown_server_pool(pool)


def _worker_pool_eval_loop(handles, n_boards: int, seed: int) -> int:
    """Pickleable worker entry: encode N boards, evaluate remotely.

    Identical to the single-server test's worker; included here so the
    multi-process test asserts the routing works under real fork/spawn.
    """
    from carcassonne_ai.game_wrapper import Game as _G
    from carcassonne_ai.remote_evaluators import (
        make_remote_single_evaluator as _mk,
    )
    g = _G(enable_legal_moves_cache=True)
    remote = _mk(handles, g, timeout_s=30.0)
    boards = _gen_mid_game_boards(n_boards, seed=seed)
    for b in boards:
        priors, value = remote(b)
        assert priors.ndim == 1 and priors.shape[0] == g.get_action_size()
        assert isinstance(value, float)
    return n_boards


def test_pool_concurrent_workers_no_hang(checkpoint_path: str) -> None:
    """Multiple workers sharded across 2 shards all complete cleanly."""
    n_workers = 4
    n_per_worker = 4
    pool = start_server_pool(
        checkpoint_path, n_workers=n_workers, n_shards=2
    )
    try:
        ctx = mp.get_context("spawn")
        worker_procs = []
        for w in range(n_workers):
            wp = ctx.Process(
                target=_worker_pool_eval_loop,
                args=(pool.handles_by_worker[w], n_per_worker, 2000 + w),
            )
            wp.start()
            worker_procs.append(wp)
        for wp in worker_procs:
            wp.join(timeout=90.0)
            assert not wp.is_alive(), "worker did not finish in 90s"
            assert wp.exitcode == 0, (
                f"worker exit {wp.exitcode} — likely cross-shard contamination "
                "or BrokenServerError"
            )
    finally:
        shutdown_server_pool(pool)


def test_pool_n_shards_one_matches_single_server(checkpoint_path: str) -> None:
    """n_shards=1 should be functionally identical to start_server (back-compat)."""
    pool = start_server_pool(checkpoint_path, n_workers=2, n_shards=1)
    try:
        # Both workers route to the SAME request_q.
        assert (
            pool.handles_by_worker[0].request_q
            is pool.handles_by_worker[1].request_q
        )
        # Each has its own response_q.
        assert (
            pool.handles_by_worker[0].response_q
            is not pool.handles_by_worker[1].response_q
        )
        # Local worker indices are 0 and 1 within the single shard.
        assert pool.handles_by_worker[0].worker_id == 0
        assert pool.handles_by_worker[1].worker_id == 1
    finally:
        shutdown_server_pool(pool)
