"""F-B1 regression guard: the learned VALUE must be able to steer the search.

The central project failure (F-B1) was that the net's value head was never in the
MCTS search loop — production self-play used the v2_5 leaf with value_blend=0, so
the net value was computed and discarded. Stage B's whole thesis (G-S1) is to put
it back via a blend λ. This test pins the contract: with the v2_5 leaf, a non-zero
value_blend (NN value mixed in) produces a DIFFERENT search than blend=0 (pure
v2.7), i.e. the learned value actually influences moves. If this regresses, the
blend has silently stopped reaching the leaf and Stage B is a no-op.

(Note: it does NOT assert anything about blend=0 production — there, by design,
the net value is discarded; that IS F-B1, fixed only by enabling the blend.)
"""
from __future__ import annotations

import dataclasses
import random
import zlib

import numpy as np

from carcassonne_ai.evaluators import make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG


def _stub_base(game):
    """Uniform priors + a deterministic, board-dependent value uncorrelated with
    the v2.7 heuristic, so blending it in measurably changes the leaf value."""
    def _ev(board):
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        p = np.zeros_like(mask, dtype=np.float32)
        if legal.size:
            p[legal] = 1.0 / legal.size
        key = game.string_representation(board).encode()
        v = (zlib.crc32(key) % 2000) / 1000.0 - 1.0  # deterministic in [-1, 1)
        return p, float(np.clip(v, -0.95, 0.95))
    return _ev


def _branchy_board(game, plies=12, seed=3):
    rng = random.Random(seed)
    board = game.get_init_board()
    for _ in range(plies):
        if game.get_game_ended(board, 0) != 0.0:
            break
        legal = np.flatnonzero(game.get_valid_moves(board)).tolist()
        board, _ = game.get_next_state(board, rng.choice(legal))
    return board


def test_value_blend_changes_the_search():
    game = Game(enable_legal_moves_cache=True)
    board = _branchy_board(game)
    legal = set(np.flatnonzero(game.get_valid_moves(board)).tolist())
    assert len(legal) > 1, "need a branchy board to exercise value influence"

    base = _stub_base(game)
    ev_pure = make_v25_value_wrapper(
        base, cfg=dataclasses.replace(DEFAULT_CONFIG, value_blend=0.0)
    )
    ev_blend = make_v25_value_wrapper(
        base, cfg=dataclasses.replace(DEFAULT_CONFIG, value_blend=0.9)
    )

    v_pure = NeuralMCTS(game=game, evaluator=ev_pure, simulations=48, seed=0).search(board)
    v_blend = NeuralMCTS(game=game, evaluator=ev_blend, simulations=48, seed=0).search(board)

    for v in (v_pure, v_blend):
        assert sum(v.values()) == 48
        assert set(v.keys()).issubset(legal)
    # priors + seed identical; ONLY the leaf value differs → the search must differ,
    # proving the NN value is in the loop (F-B1 contract).
    assert v_pure != v_blend, (
        "F-B1 REGRESSION: value_blend did not change the search — the NN value "
        "is not reaching the leaf / not influencing moves"
    )
