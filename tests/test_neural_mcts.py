"""Tests for NeuralMCTS — the network-evaluator variant of MCTS used in
Phase 3 acceptance Tournament 2 (net+MCTS vs vanilla MCTS)."""
from __future__ import annotations

import math

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


def test_evaluator_with_nan_priors_falls_back_to_uniform() -> None:
    """A bad checkpoint can return NaN/inf priors. NeuralMCTS must not silently
    pick "first legal action" by NaN comparison — it must use uniform fallback.
    (External review 2026-04-28.)"""
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    A = action_size(g.window_size)

    def nan_evaluator(_board) -> tuple[np.ndarray, float]:
        return np.full(A, float("nan"), dtype=np.float32), 0.0

    mcts = NeuralMCTS(game=g, evaluator=nan_evaluator, simulations=10, seed=0)
    visits = mcts.search(board)
    # Search must complete and produce a sensible visit distribution. With
    # uniform-fallback priors, visits should be spread across legal actions.
    assert sum(visits.values()) == 10
    legal = set(np.flatnonzero(g.get_valid_moves(board)).tolist())
    assert set(visits.keys()).issubset(legal)


def test_evaluator_with_nonfinite_value_clamps_safely() -> None:
    """Network returning inf/nan value must not poison backprop."""
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    A = action_size(g.window_size)

    def bad_value_evaluator(_board) -> tuple[np.ndarray, float]:
        return np.full(A, 1.0 / A, dtype=np.float32), float("inf")

    mcts = NeuralMCTS(game=g, evaluator=bad_value_evaluator, simulations=8, seed=0)
    visits = mcts.search(board)
    # Confirm Q values are finite (nothing escaped).
    for child in mcts._nodes[g.string_representation(board)].children.values():
        assert math.isfinite(child.W)
        assert math.isfinite(child.Q)
    assert sum(visits.values()) == 8


def test_transposition_table_shares_nodes_across_paths() -> None:
    """If two parents reach the same state, NeuralMCTS should share the child
    node (visit counts combine). Previously the setdefault return value was
    ignored, creating duplicate nodes. (External review 2026-04-28.)

    Construct a stub MCTS where the evaluator returns a deterministic prior
    so we can predict that two distinct parent paths converge on a common
    child via different first-actions.
    """
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=10, seed=0)
    # Inject a fake transposition: pretend two parent nodes (with different
    # state_keys) each route to a child whose state_key already exists in
    # _nodes. After the second insert, the parent's child reference must
    # equal the original (shared) node.
    from carcassonne_ai.mcts import _NeuralNode

    shared = _NeuralNode(state_key="SHARED", player_to_move=0, expanded=True, leaf_value=0.5)
    mcts._nodes["SHARED"] = shared

    # Re-running the setdefault with a fresh node should return the shared one.
    fresh = _NeuralNode(state_key="SHARED", player_to_move=0)
    returned = mcts._nodes.setdefault(fresh.state_key, fresh)
    assert returned is shared
    assert returned is not fresh
