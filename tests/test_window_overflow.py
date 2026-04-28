"""Window-overflow detection contracts."""
from __future__ import annotations

import numpy as np

from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

from carcassonne_ai import board_repr as B
from carcassonne_ai.action_space import WindowOffset
from carcassonne_ai.game_wrapper import Game


def test_no_overflow_at_init() -> None:
    g = Game()
    board = g.get_init_board()
    assert not B.board_overflows_window(board.state, board.offset)


def test_overflow_detected_for_far_placement() -> None:
    """A handcrafted state with a tile placed deliberately outside the window
    must trigger board_overflows_window=True."""
    g = Game(window_size=11)
    board = g.get_init_board()
    state = board.state
    # Place a stray tile far from the centroid.
    # The engine board is 35x35; planting a tile at (0, 0) will be outside an
    # 11x11 window centered on the engine starting position (6, 15).
    state.board[0][0] = base_tiles["chapel"]
    overflow = B.board_overflows_window(
        state, WindowOffset(origin_row=6 - 5, origin_col=15 - 5, size=11)
    )
    assert overflow is True


def test_overflow_rate_under_one_percent_in_random_play() -> None:
    """Confirm Phase 0's empirical claim: <1% of 200 random games overflow 25x25."""
    from carcassonne_ai.game_wrapper import _self_play_random

    summary = _self_play_random(n_games=200, seed=0)
    assert summary["overflow_rate"] < 0.01, summary


def test_get_valid_moves_raises_when_all_actions_overflow() -> None:
    """When every legal placement falls outside the window, get_valid_moves
    should raise WindowOverflowError so callers can drop the game from
    training. Pre-fix it returned an empty mask, which callers couldn't
    distinguish from a real no-legal-moves terminal. (External review
    pass 4, 2026-04-28.)"""
    import pytest

    from carcassonne_ai.action_space import WindowOverflowError, WindowOffset
    from carcassonne_ai.game_wrapper import Game

    g = Game()
    board = g.get_init_board()

    # Force a degenerate window offset that puts the engine's starting_position
    # (where the next legal placement must go) outside the 25x25 window.
    sp = board.state.starting_position
    board.offset = WindowOffset(
        origin_row=sp.row + 100,  # window starts 100 rows below the action
        origin_col=sp.column + 100,
        size=25,
    )

    with pytest.raises(WindowOverflowError):
        g.get_valid_moves(board)
