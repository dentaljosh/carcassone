"""Tests for NeuralMCTS — the network-evaluator variant of MCTS used in
Phase 3 acceptance Tournament 2 (net+MCTS vs vanilla MCTS)."""
from __future__ import annotations

import numpy as np
import pytest

from carcassonne_ai.action_space import action_size
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS


def _uniform_evaluator(board) -> tuple[np.ndarray, float]:
    """Stub evaluator: uniform priors, value=0. Useful for testing the
    NeuralMCTS structure without a real network."""
    a = action_size(board.offset.size)
    return np.full(a, 1.0 / a, dtype=np.float32), 0.0


def test_search_returns_visit_distribution_summing_to_simulations() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=8, seed=0)
    board = g.get_init_board()
    visits = mcts.search(board)
    assert sum(visits.values()) == 8
    legal = set(np.flatnonzero(g.get_valid_moves(board)).tolist())
    assert set(visits.keys()).issubset(legal)


def test_best_action_in_legal_set() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=5, seed=0)
    board = g.get_init_board()
    a = mcts.best_action(board)
    legal = np.flatnonzero(g.get_valid_moves(board))
    assert a in legal


def test_clear_resets_tree_and_caches() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=5, seed=0)
    board = g.get_init_board()
    mcts.search(board)
    assert len(mcts._nodes) > 0
    assert g.cache_stats()["size"] > 0
    mcts.clear()
    assert mcts._nodes == {}
    assert g.cache_stats()["size"] == 0


def test_evaluator_priors_influence_visits() -> None:
    """If the evaluator strongly biases toward action X, X should be visited
    more than under uniform priors."""
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    legal = np.flatnonzero(g.get_valid_moves(board))
    target = int(legal[0])
    A = action_size(g.window_size)

    def biased_evaluator(_board) -> tuple[np.ndarray, float]:
        priors = np.full(A, 0.001 / A, dtype=np.float32)
        priors[target] = 1.0
        priors /= priors.sum()
        return priors, 0.0

    mcts = NeuralMCTS(game=g, evaluator=biased_evaluator, simulations=20, seed=0)
    visits = mcts.search(board)
    # The biased target action should get the most visits.
    top = max(visits.items(), key=lambda kv: kv[1])
    assert top[0] == target, f"biased target {target} did not win, top was {top}"


def test_evaluator_runs_end_to_end_through_a_short_game() -> None:
    """Play 5 moves with NeuralMCTS using a uniform-prior evaluator. No errors;
    actions are always legal."""
    import random

    rng = random.Random(0)
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    mcts = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=8, seed=0)
    for _ in range(5):
        if g.get_game_ended(board, 0) != 0.0:
            break
        mcts.clear()
        a = mcts.best_action(board)
        legal = np.flatnonzero(g.get_valid_moves(board))
        assert a in legal
        board, _ = g.get_next_state(board, a)
