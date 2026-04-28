"""Tests for the warm-start dataset module (warmstart.py)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from carcassonne_ai.action_space import action_size
from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.warmstart import (
    GameDataset,
    _heuristic_policy,
    _mcts_policy,
    generate_one_game_dataset,
    iter_game_dataset_files,
    normalized_value_target,
)
from carcassonne_ai.game_wrapper import Game


def test_normalized_value_target_in_tanh_range() -> None:
    """The value target is tanh(diff / 15), so it must be strictly in (-1, +1)."""
    g = Game()
    board = g.get_init_board()
    v = normalized_value_target(board.state, 0)
    assert -1.0 < v < 1.0


def test_mcts_policy_normalization() -> None:
    """Visit counts get normalized to a probability distribution."""
    visits = {0: 3, 5: 5, 12: 2}  # total 10
    A = action_size(25)
    p = _mcts_policy(visits, A)
    assert p.shape == (A,)
    assert abs(p.sum() - 1.0) < 1e-6
    assert p[0] == 0.3
    assert p[5] == 0.5
    assert p[12] == 0.2
    # All other entries are 0
    other = [i for i in range(A) if i not in {0, 5, 12}]
    assert (p[other] == 0).all()


def test_mcts_policy_empty_visits() -> None:
    """Empty visits → all-zero policy (callers should ignore but must not crash)."""
    p = _mcts_policy({}, action_size(25))
    assert p.shape == (action_size(25),)
    assert p.sum() == 0


def test_heuristic_policy_distribution_over_legal() -> None:
    """Heuristic policy must sum to 1 over legal moves and be 0 on illegal."""
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    # Step a few moves to reach a non-trivial state.
    import random

    random.seed(0)
    for _ in range(15):
        if g.get_game_ended(board, 0) != 0.0:
            break
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))

    mask = g.get_valid_moves(board)
    p = _heuristic_policy(g, board, mask)
    assert p.shape == (action_size(25),)
    assert abs(p.sum() - 1.0) < 1e-5
    # Illegal indices have zero probability.
    assert (p[~mask] == 0).all()
    # Legal indices have probability >= 0.
    assert (p[mask] >= 0).all()


def test_generate_one_game_dataset_heuristic_smoke() -> None:
    """Generate one game's worth of heuristic-labeled positions; verify shapes
    and that policy/value targets are sensible."""
    ds = generate_one_game_dataset(
        seed=0,
        label_strategy="heuristic",
        n_positions_per_game=5,
    )
    assert len(ds) <= 5
    assert ds.boards.shape[1:] == (N_CHANNELS, 25, 25)
    assert ds.scalars.shape[1] == N_SCALAR_FEATURES
    assert ds.policies.shape[1] == action_size(25)
    assert ds.values.ndim == 1
    assert ds.valid_masks.shape[1] == action_size(25)
    # Each row's policy sums to ~1 over its valid mask.
    for i in range(len(ds)):
        assert abs(ds.policies[i].sum() - 1.0) < 1e-4
        # Policy is nonzero only where mask is True.
        assert (ds.policies[i][~ds.valid_masks[i]] == 0).all()
    # Values are tanh-bounded.
    assert (ds.values > -1).all() and (ds.values < 1).all()


def test_dataset_save_load_roundtrip(tmp_path: Path) -> None:
    """Save then load a GameDataset; arrays must be byte-identical."""
    ds = generate_one_game_dataset(seed=1, label_strategy="heuristic", n_positions_per_game=3)
    path = tmp_path / "seed_00001.npz"
    ds.save(path)
    loaded = GameDataset.load(path)
    np.testing.assert_array_equal(ds.boards, loaded.boards)
    np.testing.assert_array_equal(ds.scalars, loaded.scalars)
    np.testing.assert_array_equal(ds.policies, loaded.policies)
    np.testing.assert_array_equal(ds.values, loaded.values)
    np.testing.assert_array_equal(ds.valid_masks, loaded.valid_masks)


def test_iter_game_dataset_files_sorted(tmp_path: Path) -> None:
    """Iterator yields .npz files in name-sorted order."""
    # Create dummy files in random order
    for name in ["seed_00010.npz", "seed_00002.npz", "seed_00007.npz"]:
        (tmp_path / name).write_bytes(b"")
    # And a non-matching file that should be skipped
    (tmp_path / "other.npz").write_bytes(b"")
    files = [p.name for p in iter_game_dataset_files(tmp_path)]
    assert files == ["seed_00002.npz", "seed_00007.npz", "seed_00010.npz"]


def test_invalid_strategy_raises() -> None:
    with pytest.raises(ValueError):
        generate_one_game_dataset(seed=0, label_strategy="invalid", n_positions_per_game=1)
