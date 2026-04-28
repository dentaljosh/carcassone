"""Vanilla MCTS correctness tests.

These don't validate playing strength (that's the play_mcts_vs_random.py
tournament). They check structural invariants: the search returns a sensible
visit distribution, UCT selection is deterministic with a fixed seed, and
clear() resets state.
"""
from __future__ import annotations

import random

import pytest

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import MCTS, virtual_score_estimate


def _fresh_setup(sims: int = 10, seed: int = 0) -> tuple[Game, MCTS]:
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    mcts = MCTS(game=game, simulations=sims, seed=seed)
    return game, mcts


def test_search_returns_visit_distribution_summing_to_simulations() -> None:
    g, mcts = _fresh_setup(sims=8)
    board = g.get_init_board()
    visits = mcts.search(board)
    # Total visits at the root's children sum to s (each sim picks one
    # root-child path on the very first selection step).
    assert sum(visits.values()) == 8
    # All visited indices must have been legal at the root.
    import numpy as np

    legal = set(np.flatnonzero(g.get_valid_moves(board)).tolist())
    assert set(visits.keys()).issubset(legal)


def test_search_is_deterministic_with_fixed_seed() -> None:
    """Same seed → same search result. Important for reproducibility."""
    g1, m1 = _fresh_setup(sims=12, seed=99)
    g2, m2 = _fresh_setup(sims=12, seed=99)
    b1 = g1.get_init_board()
    b2 = g2.get_init_board()
    # Re-seed global random so the engine's deck is identical.
    random.seed(99); b1 = g1.get_init_board()
    random.seed(99); b2 = g2.get_init_board()
    v1 = m1.search(b1)
    v2 = m2.search(b2)
    assert v1 == v2


def test_best_action_is_in_legal_set() -> None:
    g, mcts = _fresh_setup(sims=5)
    board = g.get_init_board()
    a = mcts.best_action(board)
    import numpy as np

    legal = np.flatnonzero(g.get_valid_moves(board))
    assert a in legal


def test_clear_resets_tree_and_caches() -> None:
    g, mcts = _fresh_setup(sims=5)
    board = g.get_init_board()
    mcts.search(board)
    assert len(mcts._nodes) > 0
    assert g.cache_stats()["size"] > 0
    mcts.clear()
    assert mcts._nodes == {}
    assert g.cache_stats()["size"] == 0


def test_virtual_score_not_implemented_yet() -> None:
    """Phase 2 uses random rollouts. virtual_score_estimate is a Phase 3 stub
    that raises until implemented."""
    g = Game()
    board = g.get_init_board()
    with pytest.raises(NotImplementedError):
        virtual_score_estimate(board, 0)
