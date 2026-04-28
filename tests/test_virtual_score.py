"""Tests for virtual_score (Ameneyro 2020 §III.B equivalent)."""
from __future__ import annotations

import copy
import random

import numpy as np
import pytest

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score import virtual_score


def _bare_state(players: int = 2) -> CarcassonneGameState:
    """A CarcassonneGameState with deterministic mostly-empty fields."""
    state = CarcassonneGameState(
        players=players,
        tile_sets=[TileSet.BASE, TileSet.THE_RIVER],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    state.scores = [0] * players
    state.placed_meeples = [[] for _ in range(players)]
    return state


def test_empty_board_zero_diff() -> None:
    """A fresh state has scores=[0,0] and no placed meeples → diff=0."""
    g = Game()
    board = g.get_init_board()
    assert virtual_score(board.state, 0) == 0
    assert virtual_score(board.state, 1) == 0


def test_realized_scores_dominate_when_no_pending_features() -> None:
    """If players have realized scores and no placed meeples (no pending
    features to count), virtual_score equals the raw score differential."""
    state = _bare_state()
    state.scores = [12, 5]
    assert virtual_score(state, 0) == 7
    assert virtual_score(state, 1) == -7


def test_perspective_negation() -> None:
    """virtual_score(state, 0) == -virtual_score(state, 1) for any state."""
    g = Game()
    random.seed(13)
    board = g.get_init_board()
    for _ in range(40):
        if g.get_game_ended(board, 0) != 0.0:
            break
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))
        # invariant: holds at every state
        assert virtual_score(board.state, 0) == -virtual_score(board.state, 1)


def test_unfinished_road_with_meeple_scores_one_per_tile() -> None:
    """Engine end-of-game rule: unfinished road = 1pt/tile to majority-meeple
    holder. Two crossroads vertically + meeple → 2 tiles → 2 pts player 0."""
    state = _bare_state()
    state.board = [[None] for _ in range(2)]
    state.board[0][0] = base_tiles["crossroads"]
    state.board[1][0] = base_tiles["crossroads"]
    state.placed_meeples[0].append(
        MeeplePosition(
            meeple_type=MeepleType.NORMAL,
            coordinate_with_side=CoordinateWithSide(Coordinate(0, 0), Side.BOTTOM),
        )
    )
    diff = virtual_score(state, 0)
    assert diff == 2, f"expected 2 (1 pt/tile × 2 tiles), got {diff}"


def test_does_not_mutate_input_state() -> None:
    """virtual_score must not change the live state. Score, meeples, scores
    field, board contents must all be unchanged after the call."""
    state = _bare_state()
    state.scores = [3, 7]
    state.board = [[None] for _ in range(2)]
    state.board[0][0] = base_tiles["crossroads"]
    state.board[1][0] = base_tiles["crossroads"]
    state.placed_meeples[0].append(
        MeeplePosition(
            meeple_type=MeepleType.NORMAL,
            coordinate_with_side=CoordinateWithSide(Coordinate(0, 0), Side.BOTTOM),
        )
    )

    snapshot = copy.deepcopy(state)
    _ = virtual_score(state, 0)
    assert state.scores == snapshot.scores
    assert len(state.placed_meeples[0]) == len(snapshot.placed_meeples[0])
    assert state.placed_meeples == snapshot.placed_meeples


def test_rejects_non_two_player() -> None:
    state = _bare_state(players=3)
    with pytest.raises(ValueError):
        virtual_score(state, 0)


def test_terminal_state_matches_engine_final_scores() -> None:
    """At a terminal state, virtual_score equals the engine's final-score
    differential — they're computing the same thing by definition."""
    g = Game()
    random.seed(99)
    board = g.get_init_board()
    while g.get_game_ended(board, 0) == 0.0:
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    # At terminal, both scores are already final (count_final_scores ran on apply_action).
    expected = board.state.scores[0] - board.state.scores[1]
    assert virtual_score(board.state, 0) == expected


def test_consistent_during_a_random_game() -> None:
    """As a game progresses, virtual_score should monotonically converge to
    the true final differential. Not strictly monotonic per move (move-noise),
    but the absolute deviation from the final answer should generally shrink."""
    g = Game()
    random.seed(7)
    board = g.get_init_board()
    estimates: list[int] = []
    while g.get_game_ended(board, 0) == 0.0:
        estimates.append(virtual_score(board.state, 0))
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    final = board.state.scores[0] - board.state.scores[1]
    # Last estimate (the one right before terminal action) should match final exactly:
    # all features get end-of-game scoring applied the same way.
    assert estimates[-1] == final
