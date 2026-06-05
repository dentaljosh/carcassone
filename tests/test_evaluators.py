"""Smoke tests for evaluators.make_single_evaluator / make_batch_evaluator.

The actual fp16 numerics need GPU to verify; on CPU, autocast is a no-op,
so these tests just confirm the API works (correct shapes, finite values,
no crashes) with both `use_fp16=False` and `use_fp16=True` selectors. A
real fp16-vs-fp32 ELO comparison is a separate offline bench and lives
out of CI.
"""
from __future__ import annotations

import numpy as np
import torch

from carcassonne_ai.action_space import action_size
from carcassonne_ai.evaluators import (
    make_batch_evaluator,
    make_single_evaluator,
    make_v25_batch_value_wrapper,
    make_v25_value_wrapper,
)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet


def _build_net(device: torch.device) -> CarcassonneNet:
    """Tiny CarcassonneNet for fast CPU tests (1 block, 8 filters)."""
    net = CarcassonneNet(n_filters=8, n_blocks=1).to(device)
    net.train(False)
    return net


def _board_with_branching(min_legal: int = 4):
    import random as _random
    _random.seed(0)
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    rng = _random.Random(0)
    for _ in range(40):
        legal = np.flatnonzero(g.get_valid_moves(board))
        if legal.size >= min_legal:
            return g, board
        if legal.size == 0:
            break
        action = int(rng.choice(legal))
        board, _ = g.get_next_state(board, action)
    return g, board


def test_single_evaluator_shapes_and_finiteness() -> None:
    device = torch.device("cpu")
    net = _build_net(device)
    g, board = _board_with_branching()
    evaluator = make_single_evaluator(net, device, g)
    priors, value = evaluator(board)
    assert priors.shape == (action_size(board.offset.size),)
    assert priors.dtype == np.float32
    assert np.isfinite(priors).all()
    assert isinstance(value, float)
    assert -1.0 <= value <= 1.0


def test_batch_evaluator_shapes_and_finiteness() -> None:
    device = torch.device("cpu")
    net = _build_net(device)
    g, board = _board_with_branching()
    batch_evaluator = make_batch_evaluator(net, device, g)
    boards = [board, board, board]  # 3 copies — same board, batched
    priors, values = batch_evaluator(boards)
    A = action_size(board.offset.size)
    assert priors.shape == (3, A)
    assert values.shape == (3,)
    assert np.isfinite(priors).all()
    assert np.isfinite(values).all()
    # Same input → same output (no batch-state pollution).
    assert np.allclose(priors[0], priors[1], atol=1e-5)
    assert np.allclose(priors[1], priors[2], atol=1e-5)
    assert abs(values[0] - values[1]) < 1e-5


def test_batch_evaluator_empty_returns_empty() -> None:
    device = torch.device("cpu")
    net = _build_net(device)
    g, _ = _board_with_branching()
    batch_evaluator = make_batch_evaluator(net, device, g)
    priors, values = batch_evaluator([])
    assert priors.shape == (0,)
    assert values.shape == (0,)


def test_use_fp16_does_not_crash_on_cpu() -> None:
    """fp16 autocast is a no-op on CPU; verify the codepath doesn't crash
    so deployments can pass `use_fp16=True` blindly without device-specific
    branches."""
    device = torch.device("cpu")
    net = _build_net(device)
    g, board = _board_with_branching()
    single = make_single_evaluator(net, device, g, use_fp16=True)
    batch = make_batch_evaluator(net, device, g, use_fp16=True)
    p1, v1 = single(board)
    pB, vB = batch([board, board])
    assert p1.shape == (action_size(board.offset.size),)
    assert pB.shape == (2, action_size(board.offset.size))
    assert np.isfinite(p1).all() and np.isfinite(pB).all()


def test_single_and_batch_agree_on_same_board() -> None:
    """A single-call evaluator and a batch=1 call to the batch evaluator
    should return numerically equivalent priors+value (within fp32 noise)."""
    device = torch.device("cpu")
    net = _build_net(device)
    g, board = _board_with_branching()
    single = make_single_evaluator(net, device, g)
    batch = make_batch_evaluator(net, device, g)
    p_s, v_s = single(board)
    p_b, v_b = batch([board])
    assert np.allclose(p_s, p_b[0], atol=1e-5)
    assert abs(v_s - float(v_b[0])) < 1e-5


# ---------------------------------------------------------------------------
# v2.5 leaf wrapper — value-head blend (2026-05-17 Option 2)
# ---------------------------------------------------------------------------


def test_v25_value_wrapper_blend_endpoints_and_midpoint() -> None:
    """make_v25_value_wrapper blends the NN value head into the leaf:
    leaf = (1-λ)·h + λ·v_nn. λ=0 → pure heuristic; λ=1 → pure v_nn;
    λ=0.5 → exact midpoint. λ=0 must also match the no-config default
    (back-compat guard — production runs at λ=0)."""
    from dataclasses import replace

    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    g, board = _board_with_branching()
    A = action_size(board.offset.size)
    V_NN = 0.6
    base = lambda b: (np.zeros(A, dtype=np.float32), V_NN)  # noqa: E731

    h = make_v25_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=0.0))(board)[1]
    assert abs(h - V_NN) > 0.01, "test not discriminating — pick a different V_NN"
    # default cfg (None) ≡ λ=0 — production behavior unchanged.
    assert make_v25_value_wrapper(base)(board)[1] == h
    # λ=1 — pure NN value.
    v1 = make_v25_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=1.0))(board)[1]
    assert abs(v1 - V_NN) < 1e-6
    # λ=0.5 — exact midpoint of heuristic and NN value.
    v_mid = make_v25_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=0.5))(board)[1]
    assert abs(v_mid - (0.5 * h + 0.5 * V_NN)) < 1e-6


def test_v25_batch_value_wrapper_blend() -> None:
    """The batched v2.5 wrapper blends per-board identically to the single
    wrapper: λ=0 → heuristic, λ=1 → v_nn, λ=0.5 → midpoint."""
    from dataclasses import replace

    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    g, board = _board_with_branching()
    A = action_size(board.offset.size)
    V_NN = 0.6
    boards = [board, board]
    base = lambda bs: (  # noqa: E731
        np.zeros((len(bs), A), dtype=np.float32),
        np.full(len(bs), V_NN, dtype=np.float32),
    )

    h = make_v25_batch_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=0.0))(boards)[1]
    assert np.allclose(make_v25_batch_value_wrapper(base)(boards)[1], h)
    v1 = make_v25_batch_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=1.0))(boards)[1]
    assert np.allclose(v1, V_NN, atol=1e-6)
    v_mid = make_v25_batch_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=0.5))(boards)[1]
    assert np.allclose(v_mid, 0.5 * h + 0.5 * V_NN, atol=1e-6)


# ---------------------------------------------------------------------------
# v2.5 leaf wrapper — RESIDUAL mode (Lever 1, 2026-06-05)
# ---------------------------------------------------------------------------


def test_v25_value_wrapper_residual_mode_and_clip() -> None:
    """residual_scale>0 → leaf = clip(h + scale·v_nn, ±1). It takes precedence
    over value_blend, and a large residual is clipped to the tanh range."""
    from dataclasses import replace

    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    g, board = _board_with_branching()
    A = action_size(board.offset.size)
    base = lambda b: (np.zeros(A, dtype=np.float32), 0.4)  # noqa: E731

    h = make_v25_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=0.0))(board)[1]
    # scale=0.5, small residual stays in range → exact h + 0.5·0.4.
    r = make_v25_value_wrapper(base, replace(DEFAULT_CONFIG, residual_scale=0.5))(board)[1]
    assert abs(r - max(-1.0, min(1.0, h + 0.5 * 0.4))) < 1e-6
    # residual takes precedence over a set value_blend.
    rb = make_v25_value_wrapper(
        base, replace(DEFAULT_CONFIG, residual_scale=0.5, value_blend=0.9)
    )(board)[1]
    assert abs(rb - r) < 1e-6
    # huge residual → clipped to ±1.
    base_hi = lambda b: (np.zeros(A, dtype=np.float32), 5.0)  # noqa: E731
    assert make_v25_value_wrapper(base_hi, replace(DEFAULT_CONFIG, residual_scale=1.0))(board)[1] == 1.0
    base_lo = lambda b: (np.zeros(A, dtype=np.float32), -5.0)  # noqa: E731
    assert make_v25_value_wrapper(base_lo, replace(DEFAULT_CONFIG, residual_scale=1.0))(board)[1] == -1.0


def test_v25_batch_value_wrapper_residual_mode_and_clip() -> None:
    """Batched residual wrapper matches the single wrapper + clips per-board."""
    from dataclasses import replace

    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    g, board = _board_with_branching()
    A = action_size(board.offset.size)
    boards = [board, board]
    base = lambda bs: (  # noqa: E731
        np.zeros((len(bs), A), dtype=np.float32),
        np.array([0.4, 5.0], dtype=np.float32),
    )
    h = make_v25_batch_value_wrapper(base, replace(DEFAULT_CONFIG, value_blend=0.0))(boards)[1]
    r = make_v25_batch_value_wrapper(base, replace(DEFAULT_CONFIG, residual_scale=0.5))(boards)[1]
    assert abs(r[0] - max(-1.0, min(1.0, float(h[0]) + 0.5 * 0.4))) < 1e-6
    assert r[1] == 1.0  # h + 0.5·5.0 > 1 → clipped to +1
