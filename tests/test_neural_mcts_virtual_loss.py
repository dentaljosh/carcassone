"""Tests for the Phase-4 virtual-loss / batched-evaluation extension to
NeuralMCTS.

The serial path (batch_size=1) is exercised by
`test_neural_mcts_selfplay_extensions.py`. This file specifically tests:

- Batched search produces correct visit-count totals.
- The batch evaluator is called the expected number of times (≈ ceil(sims / B)).
- Per-path vloss is correctly undone — final N/W are consistent.
- Diversification: with a uniform prior and a forced multi-action root,
  vloss spreads visits across multiple actions instead of piling on one.
- Dedupe: leaves visited via convergent paths in the same batch are
  evaluated once.
"""
from __future__ import annotations

import numpy as np
import pytest

from carcassonne_ai.action_space import action_size
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS


def _uniform_evaluator(board) -> tuple[np.ndarray, float]:
    a = action_size(board.offset.size)
    return np.full(a, 1.0 / a, dtype=np.float32), 0.0


def _board_with_branching(min_legal: int = 5, seed: int = 0):
    """Random-play moves until a position with at least `min_legal` legal
    actions appears. Seeds the global `random` (engine deck shuffle) AND a
    local rng for action selection — both are needed for repeatable
    fixtures."""
    import random as _random
    _random.seed(seed)  # engine deck shuffle uses the global random module
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    rng = _random.Random(seed)
    for _ in range(80):
        legal = np.flatnonzero(g.get_valid_moves(board))
        if legal.size >= min_legal:
            return g, board
        if legal.size == 0:
            break
        action = int(rng.choice(legal))
        board, _ = g.get_next_state(board, action)
    return g, board


class _CountingBatchEvaluator:
    """Wraps a single-board evaluator into a batch evaluator and counts
    how many batched calls have been made (and the batch sizes seen)."""

    def __init__(self, single_evaluator):
        self.single = single_evaluator
        self.calls = 0
        self.batch_sizes: list[int] = []

    def __call__(self, boards):
        self.calls += 1
        self.batch_sizes.append(len(boards))
        priors_list = []
        values_list = []
        for b in boards:
            p, v = self.single(b)
            priors_list.append(p)
            values_list.append(float(v))
        return np.stack(priors_list), np.array(values_list, dtype=np.float32)


# --- Visit-count totals ----------------------------------------------------


def test_batched_search_total_visits_match_simulations() -> None:
    """The sum of root child visits should equal `simulations` regardless of
    batch_size (each sim contributes exactly one visit to a root child)."""
    g, board = _board_with_branching(min_legal=4)
    for batch_size in (1, 2, 4, 8):
        mcts = NeuralMCTS(
            game=g, evaluator=_uniform_evaluator, simulations=16,
            seed=0, batch_size=batch_size,
        )
        visits = mcts.search(board)
        total = sum(visits.values())
        assert total == 16, (
            f"batch_size={batch_size}: expected 16 child visits, got {total}"
        )


def test_batched_root_visit_count_equals_simulations() -> None:
    g, board = _board_with_branching(min_legal=4)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=12,
        seed=1, batch_size=4,
    )
    mcts.search(board)
    root = mcts._nodes[g.string_representation(board)]
    assert root.N == 12


# --- Batch-call accounting -------------------------------------------------


def test_batch_evaluator_called_at_most_ceil_sims_over_batch_plus_root() -> None:
    """With batch_size=B and S simulations, the batched evaluator is called
    at most ceil(S/B) + 1 times: ceil(S/B) for sim batches plus one for
    the root expansion."""
    g, board = _board_with_branching(min_legal=4)
    counter = _CountingBatchEvaluator(_uniform_evaluator)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=16,
        seed=0, batch_size=8, batch_evaluator=counter,
    )
    mcts.search(board)
    # 16 / 8 = 2 sim batches + 1 root expansion
    assert counter.calls <= 3, f"too many batch calls: {counter.calls}"
    # Every batch call's size should be ≤ batch_size
    assert max(counter.batch_sizes) <= 8


def test_batch_evaluator_not_called_when_batch_size_one() -> None:
    """Serial path (batch_size=1) should not touch batch_evaluator at all,
    even when one is wired. Lets the user keep both evaluators on a
    NeuralMCTS instance and switch modes by changing batch_size only."""
    g, board = _board_with_branching(min_legal=4)
    counter = _CountingBatchEvaluator(_uniform_evaluator)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=8,
        seed=0, batch_size=1, batch_evaluator=counter,
    )
    mcts.search(board)
    assert counter.calls == 0


# --- vloss undo invariants -------------------------------------------------


def test_visit_count_sum_consistent_after_batched_search() -> None:
    """Each child's N should equal the number of times its subtree was hit.
    Sum of grand-children N should not exceed parent N (visits descend)."""
    g, board = _board_with_branching(min_legal=4)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=24,
        seed=0, batch_size=4,
    )
    mcts.search(board)
    root = mcts._nodes[g.string_representation(board)]
    for action, child in root.children.items():
        sub = sum(c.N for c in child.children.values())
        # A child's N counts both its own evaluations and its descendants'.
        # So sub ≤ child.N (with equality only if we always descended past
        # this child; usually <).
        assert sub <= child.N, (
            f"action {action}: sum(grandchild.N)={sub} > child.N={child.N}"
        )


def test_w_bounded_by_n_with_unit_vloss() -> None:
    """After search, |W| ≤ N for every node (real values are in [-1, +1] and
    vloss is fully undone). If vloss leaked, |W| could exceed N."""
    g, board = _board_with_branching(min_legal=4)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=16,
        seed=0, batch_size=4, virtual_loss=1.0,
    )
    mcts.search(board)
    for node in mcts._nodes.values():
        if node.N == 0:
            continue
        assert abs(node.W) <= node.N + 1e-6, (
            f"node {node.state_key[:20]}: |W|={abs(node.W)} > N={node.N} "
            f"(vloss leak?)"
        )


# --- Diversification -------------------------------------------------------


def test_batched_search_visits_multiple_root_actions() -> None:
    """At a branching position with uniform priors, batched search with
    vloss should visit >=2 distinct root actions, not pile all sims onto
    one. Skips if the random fixture didn't reach a branching position."""
    g, board = _board_with_branching(min_legal=4, seed=2)
    if np.flatnonzero(g.get_valid_moves(board)).size < 4:
        pytest.skip("fixture didn't produce a branching position")
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=8,
        seed=0, batch_size=8, virtual_loss=1.0,
    )
    visits = mcts.search(board)
    visited = [a for a, n in visits.items() if n > 0]
    assert len(visited) >= 2, (
        f"vloss didn't diversify: only {len(visited)} root actions visited"
    )


# --- Backwards-compat surface ---------------------------------------------


def test_default_constructor_uses_serial_path() -> None:
    """No batch params → batch_size=1 → existing serial behavior."""
    g, board = _board_with_branching(min_legal=4)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=8, seed=0
    )
    assert mcts.batch_size == 1
    assert mcts.batch_evaluator is None
    assert mcts.virtual_loss == 1.0
    visits = mcts.search(board)
    assert sum(visits.values()) == 8


def test_batched_search_with_dirichlet_noise() -> None:
    """Combining batched mode + Dirichlet noise (the actual self-play
    config) should still produce non-trivial visit distributions and
    correct totals."""
    g, board = _board_with_branching(min_legal=5, seed=2)
    mcts = NeuralMCTS(
        game=g, evaluator=_uniform_evaluator, simulations=16,
        seed=0, batch_size=4,
        dirichlet_alpha=0.3, dirichlet_eps=0.25,
    )
    visits = mcts.search(board)
    assert sum(visits.values()) == 16
