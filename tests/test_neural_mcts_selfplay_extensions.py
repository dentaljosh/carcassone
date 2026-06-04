"""Tests for the Phase-4 self-play extensions to NeuralMCTS:

- Dirichlet noise mixed into root priors (root-only, once per fresh root).
- `select_for_training(temperature)` for sampling-from-visit-distribution
  policy targets.
- `root_visit_distribution` for building the policy training tensor.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from carcassonne_ai.action_space import action_size
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS


def _uniform_evaluator(board) -> tuple[np.ndarray, float]:
    a = action_size(board.offset.size)
    return np.full(a, 1.0 / a, dtype=np.float32), 0.0


def _board_with_branching(min_legal: int = 5):
    """Random-play a few moves until there's a position with at least
    `min_legal` legal actions — useful when we need branching to test
    distribution shapes. The opening river-tile-only positions have just
    one legal move."""
    import random as _random
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    rng = _random.Random(0)
    for _ in range(40):
        legal = np.flatnonzero(g.get_valid_moves(board))
        if legal.size >= min_legal:
            return g, board
        if legal.size == 0:
            break
        action = int(rng.choice(legal))
        board, _ = g.get_next_state(board, action)
    return g, board


# --- Dirichlet noise -------------------------------------------------------


def test_dirichlet_noise_disabled_by_default() -> None:
    """No noise unless both alpha and eps are positive — keeps existing
    tournament/eval call sites unchanged."""
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=4, seed=0)
    assert mcts.dirichlet_alpha == 0.0
    assert mcts.dirichlet_eps == 0.0
    board = g.get_init_board()
    mcts.search(board)
    assert mcts._noisy_roots == set()


def test_dirichlet_noise_changes_root_priors_only() -> None:
    """With noise enabled, root priors should differ from the evaluator's
    uniform output. Children of the root (after expansion) keep their
    original uniform priors — noise is root-only."""
    g, board = _board_with_branching(min_legal=5)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=8, seed=0,
        dirichlet_alpha=0.3, dirichlet_eps=0.5,
    )
    mcts.search(board)
    root_key = g.string_representation(board)
    root = mcts._nodes[root_key]
    assert root_key in mcts._noisy_roots
    spread = max(root.priors.values()) - min(root.priors.values())
    assert spread > 1e-3, f"noise produced no detectable spread: {spread}"

    # A child node that got expanded during simulation should still have
    # uniform priors (no noise leak).
    child_with_priors = None
    for c in root.children.values():
        if c.expanded and not c.is_terminal and len(c.valid_actions) >= 2:
            child_with_priors = c
            break
    if child_with_priors is not None:
        cspread = max(child_with_priors.priors.values()) - min(
            child_with_priors.priors.values()
        )
        assert cspread < 1e-5, (
            f"child priors not uniform — noise leaked? spread={cspread}"
        )


def test_dirichlet_applied_once_per_root() -> None:
    """Calling search() twice on the same root must not re-mix noise.
    Mutate the noise mix once and check the second call leaves it alone."""
    g, board = _board_with_branching(min_legal=5)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=4, seed=0,
        dirichlet_alpha=0.3, dirichlet_eps=0.5,
    )
    mcts.search(board)
    root_key = g.string_representation(board)
    root = mcts._nodes[root_key]
    snapshot = dict(root.priors)
    mcts.search(board)
    assert root.priors == snapshot, "Dirichlet noise was reapplied on 2nd search"


def test_clear_lets_noise_apply_to_next_root() -> None:
    g, board = _board_with_branching(min_legal=5)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=4, seed=0,
        dirichlet_alpha=0.3, dirichlet_eps=0.5,
    )
    mcts.search(board)
    assert len(mcts._noisy_roots) == 1
    mcts.clear()
    assert mcts._noisy_roots == set()
    mcts.search(board)
    assert len(mcts._noisy_roots) == 1


# --- select_for_training ---------------------------------------------------


def test_select_for_training_tau_zero_returns_argmax_visits() -> None:
    """At τ=0, return the most-visited child (not best-Q like best_action)."""
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=20, seed=0
    )
    board = g.get_init_board()
    visits = mcts.search(board)
    # Argmax visits manually:
    expected = max(visits.items(), key=lambda kv: kv[1])[0]
    chosen = mcts.select_for_training(board, temperature=0.0)
    assert chosen == expected


def test_select_for_training_tau_one_samples_proportional() -> None:
    """With τ=1, action frequencies over many samples should track visit
    counts roughly proportionally."""
    g, board = _board_with_branching(min_legal=4)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=30, seed=42
    )
    visits = mcts.search(board)
    if len(visits) < 2:
        pytest.skip("not enough children to measure proportionality")
    samples = Counter()
    for _ in range(2000):
        a = mcts.select_for_training(board, temperature=1.0)
        samples[a] += 1
    total_visits = sum(visits.values())
    total_samples = sum(samples.values())
    # Compare empirical fractions vs visit fractions for the top-2 children.
    top2 = sorted(visits.items(), key=lambda kv: -kv[1])[:2]
    for a, n in top2:
        empirical = samples[a] / total_samples
        expected = n / total_visits
        # Allow 10pp slack — 2000 samples on ~5 categories has SE ~1pp.
        assert abs(empirical - expected) < 0.10, (
            f"action {a}: empirical={empirical:.3f} expected={expected:.3f}"
        )


def test_select_for_training_only_returns_legal_actions() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=10, seed=0
    )
    board = g.get_init_board()
    legal = set(np.flatnonzero(g.get_valid_moves(board)).tolist())
    for tau in (0.0, 0.5, 1.0, 2.0):
        for _ in range(20):
            a = mcts.select_for_training(board, temperature=tau)
            assert a in legal


# --- root_visit_distribution ----------------------------------------------


def test_root_visit_distribution_matches_search_output() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=8, seed=0
    )
    board = g.get_init_board()
    visits = mcts.search(board)
    counts, actions = mcts.root_visit_distribution(board)
    assert len(counts) == len(actions) == len(visits)
    for a, c in zip(actions, counts):
        assert int(c) == visits[a]


def test_root_visit_distribution_runs_search_if_not_already_run() -> None:
    g = Game(enable_legal_moves_cache=True)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=8, seed=0
    )
    board = g.get_init_board()
    counts, actions = mcts.root_visit_distribution(board)
    assert int(counts.sum()) == 8


# --- root_value (search-value target source) -------------------------------


def _signed_evaluator(board) -> tuple[np.ndarray, float]:
    """Uniform priors, constant non-zero leaf value (+0.5 from the leaf's
    current-player POV) so root.Q is a definite non-zero number to read back."""
    a = action_size(board.offset.size)
    return np.full(a, 1.0 / a, dtype=np.float32), 0.5


def test_root_value_matches_root_q_after_search() -> None:
    """root_value reuses the most recent search's root: returns root.W / root.N
    (current-player POV) and runs no extra simulations."""
    g, board = _board_with_branching()
    mcts = NeuralMCTS(game=g, evaluator=_signed_evaluator, simulations=16, seed=0)
    mcts.search(board)
    root = mcts._nodes[g.string_representation(board)]
    expected = root.W / root.N
    assert mcts.root_value(board) == pytest.approx(expected)
    # Did not run extra sims (N unchanged by the read).
    assert root.N == 16
    assert -1.0 <= mcts.root_value(board) <= 1.0


def test_root_value_runs_search_if_not_already_run() -> None:
    g, board = _board_with_branching()
    mcts = NeuralMCTS(game=g, evaluator=_signed_evaluator, simulations=8, seed=0)
    v = mcts.root_value(board)  # no prior search
    assert np.isfinite(v) and -1.0 <= v <= 1.0
    assert mcts._nodes[g.string_representation(board)].N == 8
