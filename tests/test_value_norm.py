"""Tests for the per-instance HeuristicMCTS value_norm (v2.9.1 retune Wave D).

Contract: value_norm is a per-INSTANCE tanh denominator; None preserves the module
default (15.0) bit-identically, so every existing caller is unchanged. A different norm
rescales the leaf squash (same sign, different magnitude) — which is the whole point of
the Wave-D sweep, and why it must be per-instance (paired A/B: candidate swept, baseline
fixed at 15.0).
"""
from __future__ import annotations

import math

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HEURISTIC_VALUE_NORM, HeuristicMCTS


def _mcts(value_norm=None):
    return HeuristicMCTS(game=Game(enable_legal_moves_cache=True), simulations=4,
                         seed=0, heur_leaf="v2_7", value_norm=value_norm)


def test_default_is_module_norm():
    assert _mcts()._value_norm == HEURISTIC_VALUE_NORM == 15.0
    assert _mcts(value_norm=None)._value_norm == 15.0


def test_explicit_norm_stored():
    for n in (12.0, 18.0, 24.0):
        assert _mcts(value_norm=n)._value_norm == n


def test_norm_rescales_rollout_same_sign():
    """Same board, two norms -> same-sign leaf values, smaller norm = larger |tanh|."""
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    # advance a few plies so the leaf differential is non-zero
    m12, m24 = _mcts(value_norm=12.0), _mcts(value_norm=24.0)
    for _ in range(8):
        if g.get_game_ended(board, 0) != 0.0:
            break
        m12.clear()
        a = m12.best_action(board)
        board, _ = g.get_next_state(board, a)
    v12 = m12._rollout(board)
    v24 = m24._rollout(board)
    assert math.copysign(1, v12) == math.copysign(1, v24)        # same sign
    if abs(v12) > 1e-9:
        assert abs(v12) >= abs(v24) - 1e-9                       # smaller norm compresses less
