"""Verify the centered-window encoding contracts."""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai import board_repr as B
from carcassonne_ai.action_space import DEFAULT_WINDOW_SIZE, WindowOffset
from carcassonne_ai.game_wrapper import Game


def test_shape_matches_get_board_shape() -> None:
    g = Game()
    board = g.get_init_board()
    arr = B.encode_board(board.state, 0, board.offset)
    assert arr.shape == g.get_board_shape()
    assert arr.dtype == np.float32


@pytest.mark.parametrize("window_size", [21, 25, 31])
def test_shape_at_alternate_window_sizes(window_size: int) -> None:
    g = Game(window_size=window_size)
    board = g.get_init_board()
    arr = B.encode_board(board.state, 0, board.offset)
    assert arr.shape == (B.N_CHANNELS, window_size, window_size)


def test_canonical_swap_is_involutive() -> None:
    """canonical_swap applied twice returns the original tensor."""
    g = Game()
    board = g.get_init_board()
    # Step a few times to populate meeple channels with something interesting.
    random.seed(7)
    for _ in range(20):
        if g.get_game_ended(board, 0) != 0.0:
            break
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    arr = B.encode_board(board.state, 0, board.offset)
    swapped_twice = B.canonical_swap(B.canonical_swap(arr))
    np.testing.assert_array_equal(arr, swapped_twice)


def test_canonical_swap_actually_swaps_meeple_channels() -> None:
    """A nonzero mine channel becomes the opp channel after one swap."""
    arr = np.zeros((B.N_CHANNELS, 5, 5), dtype=np.float32)
    arr[B.CH_MEEPLE_MINE, 2, 2] = 1.0
    arr[B.CH_FARMER_OPP, 1, 4] = 1.0
    swapped = B.canonical_swap(arr)
    assert swapped[B.CH_MEEPLE_OPP, 2, 2] == 1.0
    assert swapped[B.CH_MEEPLE_MINE, 2, 2] == 0.0
    assert swapped[B.CH_FARMER_MINE, 1, 4] == 1.0
    assert swapped[B.CH_FARMER_OPP, 1, 4] == 0.0


def test_init_board_has_no_tiles_yet_but_after_first_move_has_one() -> None:
    """At init the board is empty (river_start is in next_tile, not placed).
    After the first action it should have one tile placed."""
    g = Game()
    board = g.get_init_board()
    arr0 = B.encode_board(board.state, 0, board.offset)
    assert arr0[B.CH_TILE_PRESENT].sum() == 0
    mask = g.get_valid_moves(board)
    legal = np.flatnonzero(mask)
    assert legal.size >= 1
    board, _ = g.get_next_state(board, int(legal[0]))
    arr1 = B.encode_board(board.state, 0, board.offset)
    assert arr1[B.CH_TILE_PRESENT].sum() >= 1


def test_no_overflow_on_first_few_random_moves() -> None:
    """The window must comfortably hold the early game."""
    g = Game()
    board = g.get_init_board()
    random.seed(42)
    for _ in range(50):
        if g.get_game_ended(board, 0) != 0.0:
            break
        assert not B.board_overflows_window(board.state, board.offset)
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))
