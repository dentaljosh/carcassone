"""Small contract tests for Game wrapper that don't fit elsewhere."""
from __future__ import annotations

import math
import random

import numpy as np

from carcassonne_ai.game_wrapper import SCORE_NORM_SCALE, Game


def test_game_ended_value_bounded_in_minus_one_to_one() -> None:
    """`get_game_ended` returns a value in [-1, +1]."""
    g = Game()
    random.seed(123)
    board = g.get_init_board()
    while g.get_game_ended(board, 0) == 0.0:
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    v = g.get_game_ended(board, 0)
    assert -1.0 <= v <= 1.0


def test_game_ended_is_player_perspective() -> None:
    """`get_game_ended(board, 0) == -get_game_ended(board, 1)` (within float
    tolerance) for any terminal state."""
    g = Game()
    random.seed(321)
    board = g.get_init_board()
    while g.get_game_ended(board, 0) == 0.0:
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    v0 = g.get_game_ended(board, 0)
    v1 = g.get_game_ended(board, 1)
    assert abs(v0 + v1) < 1e-9


def test_score_norm_scale_is_15() -> None:
    """Sanity-check the normalization constant matches DECISIONS.md."""
    assert SCORE_NORM_SCALE == 15.0


def test_get_valid_moves_is_idempotent() -> None:
    """Calling get_valid_moves twice on the same board returns identical masks
    (no internal mutation of the cached state)."""
    g = Game()
    random.seed(42)
    board = g.get_init_board()
    for _ in range(20):
        if g.get_game_ended(board, 0) != 0.0:
            break
        m1 = g.get_valid_moves(board)
        m2 = g.get_valid_moves(board)
        np.testing.assert_array_equal(m1, m2)
        legal = np.flatnonzero(m1)
        board, _ = g.get_next_state(board, int(random.choice(legal)))


def test_canonical_form_is_idempotent() -> None:
    g = Game()
    random.seed(7)
    board = g.get_init_board()
    for _ in range(15):
        if g.get_game_ended(board, 0) != 0.0:
            break
        a1, s1 = g.get_canonical_form(board, 0)
        a2, s2 = g.get_canonical_form(board, 0)
        np.testing.assert_array_equal(a1, a2)
        np.testing.assert_array_equal(s1, s2)
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))


def test_get_next_state_does_not_mutate_input_board() -> None:
    """get_next_state must return a fresh board; the input remains valid for
    repeated re-use (essential for MCTS)."""
    g = Game()
    random.seed(0)
    board = g.get_init_board()
    # Step a few times to a non-trivial state.
    for _ in range(10):
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))

    repr_before = g.string_representation(board)
    mask_before = g.get_valid_moves(board)

    legal = np.flatnonzero(mask_before)
    _new_board, _ = g.get_next_state(board, int(random.choice(legal)))

    repr_after = g.string_representation(board)
    mask_after = g.get_valid_moves(board)
    assert repr_before == repr_after
    np.testing.assert_array_equal(mask_before, mask_after)


def test_unsupported_player_count_raises() -> None:
    """Phase 1 wrapper is 2-player only."""
    import pytest
    with pytest.raises(NotImplementedError):
        Game(players=4)


def test_canonical_form_for_opponent_actually_flips_perspective() -> None:
    """Regression: get_canonical_form(board, player=opponent) must return the
    opponent's perspective — meeples in CH_MEEPLE_OPP for the player whose
    turn it is. Previously double-swapped, silently returning current-player
    perspective. (External review 2026-04-28.)"""
    from carcassonne_ai.board_repr import CH_MEEPLE_MINE, CH_MEEPLE_OPP

    g = Game()
    random.seed(31)
    board = g.get_init_board()
    # Step a few times to populate meeples on the board.
    for _ in range(40):
        if g.get_game_ended(board, 0) != 0.0:
            break
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))

    # Skip if no meeples placed yet (rare with seed 31).
    cur_player = board.state.current_player
    opp = 1 - cur_player

    arr_cur, _ = g.get_canonical_form(board, cur_player)
    arr_opp, _ = g.get_canonical_form(board, opp)

    # The two perspectives must have mine/opp meeple channels swapped.
    np.testing.assert_array_equal(arr_cur[CH_MEEPLE_MINE], arr_opp[CH_MEEPLE_OPP])
    np.testing.assert_array_equal(arr_cur[CH_MEEPLE_OPP], arr_opp[CH_MEEPLE_MINE])
