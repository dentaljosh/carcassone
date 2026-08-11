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
from carcassonne_ai.mcts import HeuristicMCTS, MCTS, virtual_score_estimate


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


def test_best_action_prefers_higher_q_when_visit_counts_tied() -> None:
    """At low s, many root children have N=1. best_action should pick by
    Q-value (mean rollout reward), not by N (where ties resolve arbitrarily).
    This test simulates that scenario by directly setting node stats."""
    from carcassonne_ai.mcts import MCTS, Node

    g = Game(enable_legal_moves_cache=True)
    mcts = MCTS(game=g, simulations=0, seed=0)
    board = g.get_init_board()

    # Build a fake root with three "visited" children, all N=1, different Q.
    root_key = g.string_representation(board)
    root = Node(state_key=root_key, player_to_move=0, untried_actions=[])
    root.N = 3
    for action_idx, q in [(100, 0.1), (200, 0.9), (300, 0.5)]:
        child = Node(state_key=f"fake-{action_idx}", player_to_move=1)
        child.N = 1
        # child.W is from child's perspective (player 1). We want root's
        # perspective Q to be the supplied q. Since child.player_to_move
        # differs from root, best_action negates child.Q. So set
        # child.W = -q so that -child.Q = -(-q/1) = q from root's view.
        child.W = -q
        root.children[action_idx] = child
    mcts._nodes[root_key] = root

    chosen = mcts.best_action(board)
    assert chosen == 200, f"expected action 200 (highest Q from root view), got {chosen}"


def test_virtual_score_estimate_works_at_init() -> None:
    """virtual_score_estimate is now implemented (Phase 3); should return 0
    at init (empty board, no realized or pending value)."""
    g = Game()
    board = g.get_init_board()
    assert virtual_score_estimate(board, 0) == 0


# ---------------------------------------------------------------------------
# HeuristicMCTS — vanilla MCTS with virtual_score leaf instead of random rollout.
# ---------------------------------------------------------------------------


def test_heuristic_mcts_search_returns_legal_visits() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = HeuristicMCTS(game=g, simulations=8, seed=0)
    board = g.get_init_board()
    visits = mcts.search(board)
    assert sum(visits.values()) == 8
    import numpy as np

    legal = set(np.flatnonzero(g.get_valid_moves(board)).tolist())
    assert set(visits.keys()).issubset(legal)


def test_heuristic_mcts_best_action_is_legal() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = HeuristicMCTS(game=g, simulations=5, seed=0)
    board = g.get_init_board()
    a = mcts.best_action(board)
    import numpy as np

    legal = np.flatnonzero(g.get_valid_moves(board))
    assert a in legal


def test_heuristic_mcts_rollout_returns_bounded_value() -> None:
    """The leaf evaluator must return values in [-1, +1] so UCT scaling
    stays comparable to the vanilla rollout regime. virtual_score is an
    unbounded integer; HeuristicMCTS normalizes via tanh."""
    g = Game(enable_legal_moves_cache=True)
    mcts = HeuristicMCTS(game=g, simulations=0, seed=0)
    board = g.get_init_board()
    v = mcts._rollout(board)
    assert -1.0 <= v <= 1.0


def test_heuristic_mcts_rollout_returns_terminal_value_on_terminal() -> None:
    """At a terminal state, _rollout returns the engine's terminal value
    (Game already normalizes the score differential into [-1, +1]) without
    routing through the heuristic tanh normalizer."""
    import numpy as np

    g = Game(enable_legal_moves_cache=True)
    mcts = HeuristicMCTS(game=g, simulations=0, seed=0)
    board = g.get_init_board()
    rng = random.Random(0)
    while g.get_game_ended(board, 0) == 0.0:
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(rng.choice(legal.tolist())))
    v = mcts._rollout(board)
    expected = g.get_game_ended(board, board.state.current_player)
    assert v == expected and v != 0.0


def test_heuristic_mcts_beats_random_at_sims_50() -> None:
    """Smoke check: HeuristicMCTS at sims=50 should beat random by a wide
    margin. This is the bare-minimum 'depth-search-on-virtual_score-leaf
    is at least as good as just-the-leaf' sanity check."""
    import numpy as np

    n_games = 4
    diffs = []
    for seed in range(n_games):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        mcts = HeuristicMCTS(game=g, simulations=50, seed=seed)
        rng = random.Random(seed)
        mcts_idx = seed % 2
        while g.get_game_ended(b, 0) == 0.0:
            mask = g.get_valid_moves(b)
            legal = np.flatnonzero(mask)
            cur = b.state.current_player
            if cur == mcts_idx:
                mcts.clear()
                a = mcts.best_action(b)
            else:
                a = int(rng.choice(legal.tolist()))
            b, _ = g.get_next_state(b, a)
        s0, s1 = b.state.scores
        diff = (s0 - s1) if mcts_idx == 0 else (s1 - s0)
        diffs.append(diff)
    mean_diff = sum(diffs) / len(diffs)
    assert mean_diff > 5.0, (
        f"HeuristicMCTS avg diff vs random was only {mean_diff:+.1f} across "
        f"{n_games} games — leaf evaluator may be miswired"
    )
