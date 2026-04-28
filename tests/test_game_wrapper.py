"""End-to-end wrapper integrity: 200-game fuzz with no rule/mask violations."""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import Game, _self_play_random


@pytest.mark.parametrize("seed_offset", [0, 100])
def test_random_self_play_100_games_clean(seed_offset: int) -> None:
    """100 games per parametrization, 200 total. No violations, no uncompleted games."""
    summary = _self_play_random(n_games=100, seed=seed_offset)
    assert summary["rule_violations"] == 0, summary
    assert summary["mask_violations"] == 0, summary
    assert summary["completed"] == 100, summary
    assert summary["mean_score_sum"] > 10.0, summary
    # Random play with our 25x25 window should rarely overflow.
    assert summary["overflow_rate"] < 0.05, summary


def test_get_game_ended_zero_during_play_nonzero_at_end() -> None:
    g = Game()
    board = g.get_init_board()
    assert g.get_game_ended(board, 0) == 0.0
    random.seed(0)
    while g.get_game_ended(board, 0) == 0.0:
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    v = g.get_game_ended(board, 0)
    assert -1.0 <= v <= 1.0
    assert v != 0.0


def test_canonical_form_returns_correct_shapes() -> None:
    g = Game()
    board = g.get_init_board()
    arr, scalars = g.get_canonical_form(board, 0)
    assert arr.shape == g.get_board_shape()
    assert scalars.shape == (g.get_scalar_feature_size(),)


def test_chosen_action_must_be_in_mask() -> None:
    """If we play the wrapper, every action we pick is in the mask we asked for."""
    g = Game()
    board = g.get_init_board()
    random.seed(99)
    steps = 0
    while g.get_game_ended(board, 0) == 0.0 and steps < 100:
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        idx = int(random.choice(legal))
        assert mask[idx], f"chose idx {idx} which is not in mask"
        board, _ = g.get_next_state(board, idx)
        steps += 1
