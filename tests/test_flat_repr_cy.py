"""Regression guard: the Cython board-encoder port is bit-exact to the Python
reference (board_repr.encode_board).

Skipped automatically where the compiled `.so` isn't built (per-box artifact).
The exhaustive gate is scripts/reconcile_repr_cy.py (28k+ encodes); this is the
fast CI-resident contract: a few seeded games, every ply, both perspectives,
plus the runtime-flag wiring.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai import board_repr
from carcassonne_ai.game_wrapper import Game

flat_repr_cy = pytest.importorskip(
    "carcassonne_ai.flat_repr_cy",
    reason="flat_repr_cy not built on this box (python setup_flat_repr_cy.py build_ext --inplace)",
)


def _boards(game: Game, seed: int, snap_every: int = 1, max_plies: int = 200):
    random.seed(seed)
    board = game.get_init_board()
    out = [board]
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        plies += 1
        if plies % snap_every == 0:
            out.append(board)
    return out


@pytest.fixture(autouse=True)
def _force_python_reference():
    """The `py` side must not itself route through the cython port."""
    saved = board_repr.USE_CY_REPR
    board_repr.USE_CY_REPR = False
    yield
    board_repr.USE_CY_REPR = saved


@pytest.mark.parametrize("seed", [1, 7, 42, 101, 999])
def test_encode_board_cy_bit_exact(seed):
    game = Game()
    n = 0
    for board in _boards(game, seed):
        for player in (0, 1):
            py = board_repr.encode_board(board.state, player, board.offset)
            cy = flat_repr_cy.encode_board_cy(board.state, player, board.offset)
            assert py.shape == cy.shape
            assert np.array_equal(py, cy), (
                f"mismatch seed={seed} player={player} phase={board.state.phase}"
            )
            n += 1
    assert n > 0


def test_encode_board_cy_dtype_and_shape():
    game = Game()
    board = _boards(game, seed=3)[-1]
    cy = flat_repr_cy.encode_board_cy(board.state, 0, board.offset)
    assert cy.dtype == np.float32
    assert cy.shape == (board_repr.N_CHANNELS, board.offset.size, board.offset.size)
    assert cy.flags["C_CONTIGUOUS"]


def test_use_cy_repr_flag_routes_and_matches():
    """Flipping board_repr.USE_CY_REPR routes encode_board through the port and
    returns an identical array (lazy bind fires)."""
    game = Game()
    board = _boards(game, seed=55)[len(_boards(game, seed=55)) // 2]
    board_repr._CY_ENCODE = None
    board_repr.USE_CY_REPR = False
    py = board_repr.encode_board(board.state, 0, board.offset)
    board_repr.USE_CY_REPR = True
    try:
        routed = board_repr.encode_board(board.state, 0, board.offset)
        assert board_repr._CY_ENCODE not in (None, False)
        assert np.array_equal(py, routed)
    finally:
        board_repr.USE_CY_REPR = False
