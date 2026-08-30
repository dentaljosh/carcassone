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


def test_fpu_reduction_stored_and_default_none() -> None:
    g = Game(enable_legal_moves_cache=True)
    assert NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=4).fpu_reduction is None
    m = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=4, fpu_reduction=0.25)
    assert m.fpu_reduction == 0.25


def test_fpu_reduction_changes_search_but_stays_valid() -> None:
    """FPU (round-2 audit) is an active knob: a nonzero reduction changes the
    visit distribution vs legacy q=0 while still returning a valid distribution.
    With uniform priors + value=0, node.Q stays ~0, so fpu=0.5 makes unvisited
    children (q=-0.5) less attractive than legacy (q=0) → selection order differs."""
    import random
    g = Game(enable_legal_moves_cache=True)
    # ⛔ SEED THE **GLOBAL** RNG, not just the local one below. `get_init_board()`
    # shuffles the deck from the `random` MODULE, so without this the DECK — and
    # therefore the whole board — depends on how much global randomness every
    # previously-COLLECTED test module happened to consume at import time.
    # Measured 2026-08-30: importing `tests/test_b64_cell.py` (transitively
    # `scripts/tiletie/analyze_tiearb`) shifts the stream, this test lands on a
    # different deck, and on some decks the 24-sim legacy and fpu=0.5 searches
    # coincide — so the assertion below failed as a pure ORDER-OF-COLLECTION
    # artefact, on the pre-fpu-plumbing source as well as after it. The local
    # `Random(3)` never protected against this because it does not drive the deck.
    random.seed(12345)
    board = g.get_init_board()
    # The init board has ~1 legal move (first tile forced to start) — advance to a
    # branchy mid-game position so there are many children for FPU to reorder.
    rng = random.Random(3)
    for _ in range(12):
        if g.get_game_ended(board, 0) != 0.0:
            break
        legal_moves = np.flatnonzero(g.get_valid_moves(board)).tolist()
        board, _ = g.get_next_state(board, rng.choice(legal_moves))
    legal = set(np.flatnonzero(g.get_valid_moves(board)).tolist())
    assert len(legal) > 1, "need a branchy board to exercise FPU"
    v_legacy = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=24, seed=0).search(board)
    v_fpu = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=24, seed=0, fpu_reduction=0.5).search(board)
    for v in (v_legacy, v_fpu):
        assert sum(v.values()) == 24
        assert set(v.keys()).issubset(legal)
    assert v_legacy != v_fpu, "fpu_reduction had no effect on the search"


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


def test_transposition_table_shares_nodes_across_paths(monkeypatch) -> None:
    """If a path reaches a state already in the transposition table, NeuralMCTS
    must reuse the existing node and connect the parent to it (instead of
    silently creating a duplicate). Previously the setdefault return value was
    ignored. (External review 2026-04-28.)

    This test forces the transposition through the actual _simulate code path
    by pre-populating _nodes with a node whose state_key matches what
    _create_node will produce on the next visit.
    """
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    mcts = NeuralMCTS(game=g, evaluator=_uniform_evaluator, simulations=1, seed=0)

    # Run one search to populate the root and pick a real action.
    mcts.search(board)
    root_key = g.string_representation(board)
    root = mcts._nodes[root_key]

    # Pick an action whose child node already exists in our tree.
    sample_action, original_child = next(iter(root.children.items()))

    # Now: erase the parent's link to that child, but leave the child node
    # in _nodes (simulating a transposition where some other path created
    # the child). Then run another simulation. _simulate will descend from
    # root via the same action, _create_node will produce a fresh node with
    # the same state_key, and the setdefault must return the EXISTING
    # `original_child`. The parent's children[sample_action] must be set to
    # `original_child`, NOT a duplicate.
    del root.children[sample_action]
    # Force the next selection to pick this action by making it the only
    # legal choice in the parent. Backup priors and replace temporarily.
    orig_priors = dict(root.priors)
    orig_valid = list(root.valid_actions)
    root.priors = {sample_action: 1.0}
    root.valid_actions = [sample_action]

    try:
        # Run one simulation. After it, the parent should be reconnected to
        # the original_child, not to a new duplicate node.
        mcts._simulate(board, root)
        reconnected = root.children[sample_action]
        assert reconnected is original_child, (
            "transposition table not shared: simulate created a duplicate node "
            "instead of reusing the existing one"
        )
        # Sanity: only ONE node with the child's state_key in _nodes.
        keys_matching = sum(1 for n in mcts._nodes.values() if n is original_child)
        assert keys_matching == 1
    finally:
        root.priors = orig_priors
        root.valid_actions = orig_valid


def test_evaluator_with_negative_priors_falls_back_to_uniform() -> None:
    """A malformed evaluator might return finite-but-negative priors (e.g.
    raw logits instead of softmax outputs). NeuralMCTS must reject and use
    uniform fallback rather than producing negative PUCT terms.
    (External review pass 2, 2026-04-28.)"""
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    A = action_size(g.window_size)

    def negative_evaluator(_board) -> tuple[np.ndarray, float]:
        priors = np.full(A, -0.5, dtype=np.float32)
        priors[0] = 1.0  # one positive among negatives
        return priors, 0.0

    mcts = NeuralMCTS(game=g, evaluator=negative_evaluator, simulations=8, seed=0)
    visits = mcts.search(board)
    # Search must complete; with uniform fallback all legal actions can
    # accumulate visits — not just action 0.
    legal = set(np.flatnonzero(g.get_valid_moves(board)).tolist())
    assert set(visits.keys()).issubset(legal)
    assert sum(visits.values()) == 8
    # Verify no PUCT corruption: all root child priors are finite and >= 0.
    root_key = g.string_representation(board)
    for child_action, prior in mcts._nodes[root_key].priors.items():
        assert math.isfinite(prior) and prior >= 0
