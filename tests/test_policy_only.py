"""Tests for the `forward_policy_only` path and `*_policy_only` evaluator
factories added on 2026-05-15 as a hygiene cleanup.

Coverage:
1. `forward_policy_only` matches the full forward's `policy_logits` to within
   float32 noise (no semantic change in priors, just skip the value head).
2. `make_single_evaluator_policy_only` matches `make_single_evaluator`'s
   `priors` element-wise. The returned value is the sentinel 0.0.
3. `make_batch_evaluator_policy_only` matches the batched variant on priors;
   values are zeros.
4. eval_server with `policy_only=True` returns priors matching the
   policy_only-False server's priors; remote values are zeros.

Skips cleanly if the canonical checkpoint isn't present.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from carcassonne_ai.eval_server import (
    ServerHandles,
    shutdown_server,
    start_server,
)
from carcassonne_ai.evaluators import (
    make_batch_evaluator,
    make_batch_evaluator_policy_only,
    make_single_evaluator,
    make_single_evaluator_policy_only,
)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator


REPO_ROOT = Path(__file__).resolve().parent.parent
CKPT = REPO_ROOT / "checkpoints" / "warmstart_canonical.pt"


@pytest.fixture(scope="module")
def checkpoint_path() -> str:
    if not CKPT.exists():
        pytest.skip(f"canonical checkpoint missing at {CKPT}")
    return str(CKPT)


def _load_net(path: str) -> tuple[CarcassonneNet, torch.device]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(path, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net, device


def _mid_game_boards(n: int, seed: int) -> list:
    """Walk n random games to a mid-game state and return the boards."""
    import random
    g = Game(enable_legal_moves_cache=True)
    rng = random.Random(seed)
    boards = []
    for i in range(n):
        b = g.get_init_board()
        for _ in range(40):
            if g.get_game_ended(b, 0) != 0.0:
                break
            mask = g.get_valid_moves(b)
            legal = np.flatnonzero(mask)
            a = int(rng.choice(legal.tolist()))
            b, _ = g.get_next_state(b, a)
        boards.append(b)
    return boards


def test_forward_policy_only_matches_full(checkpoint_path: str) -> None:
    """forward_policy_only should produce the same policy_logits as the full
    forward — value head is independent so policy logits don't see it."""
    net, device = _load_net(checkpoint_path)
    g = Game(enable_legal_moves_cache=True)
    boards = _mid_game_boards(5, seed=0)
    for b in boards:
        obs, scalars = g.get_canonical_form(b, b.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
        with torch.no_grad():
            logits_full, _ = net(obs_t, scalars_t)
            logits_po = net.forward_policy_only(obs_t, scalars_t)
        diff = (logits_full - logits_po).abs().max().item()
        assert diff < 1e-6, f"logits diverge by {diff} (should be bitwise-equal)"


def test_single_evaluator_policy_only_matches_priors(checkpoint_path: str) -> None:
    """The policy_only single evaluator's priors must match the full single
    evaluator's priors. The value should be the 0.0 sentinel."""
    net, device = _load_net(checkpoint_path)
    g = Game(enable_legal_moves_cache=True)
    full = make_single_evaluator(net, device, g)
    po = make_single_evaluator_policy_only(net, device, g)
    boards = _mid_game_boards(5, seed=1)
    for b in boards:
        p_full, v_full = full(b)
        p_po, v_po = po(b)
        max_diff = float(np.abs(p_full - p_po).max())
        assert max_diff < 1e-6, f"priors diverge by {max_diff}"
        assert v_po == 0.0, f"policy_only value should be 0.0 sentinel, got {v_po}"


def test_batch_evaluator_policy_only_matches_priors(checkpoint_path: str) -> None:
    """Same for batched evaluator."""
    net, device = _load_net(checkpoint_path)
    g = Game(enable_legal_moves_cache=True)
    full = make_batch_evaluator(net, device, g)
    po = make_batch_evaluator_policy_only(net, device, g)
    boards = _mid_game_boards(8, seed=2)
    p_full, v_full = full(boards)
    p_po, v_po = po(boards)
    max_diff = float(np.abs(p_full - p_po).max())
    assert max_diff < 1e-6, f"priors diverge by {max_diff}"
    assert np.all(v_po == 0.0), "policy_only batch values should be all zeros"
    assert v_po.shape == (len(boards),)


def test_eval_server_policy_only_priors_match(checkpoint_path: str) -> None:
    """Server started with policy_only=True must return priors matching the
    normal server. Remote values are zero stubs."""
    proc_a, rq_a, resps_a = start_server(checkpoint_path, n_workers=1)
    proc_b, rq_b, resps_b = start_server(
        checkpoint_path, n_workers=1, policy_only=True
    )
    try:
        g = Game(enable_legal_moves_cache=True)
        ha = ServerHandles(request_q=rq_a, response_q=resps_a[0], worker_id=0)
        hb = ServerHandles(request_q=rq_b, response_q=resps_b[0], worker_id=0)
        eval_a = make_remote_single_evaluator(ha, g, timeout_s=30.0)
        eval_b = make_remote_single_evaluator(hb, g, timeout_s=30.0)
        boards = _mid_game_boards(3, seed=3)
        for b in boards:
            p_a, v_a = eval_a(b)
            p_b, v_b = eval_b(b)
            max_diff = float(np.abs(p_a - p_b).max())
            assert max_diff < 1e-5, f"priors diverge by {max_diff} (float32 noise)"
            assert v_b == 0.0, f"policy_only server value should be 0.0, got {v_b}"
    finally:
        shutdown_server(proc_a, rq_a)
        shutdown_server(proc_b, rq_b)
