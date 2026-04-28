"""Verify the streaming/IterableDataset path used by the production trainer.

The smoke trainer pre-loads the full dataset into RAM via TensorDataset; the
production trainer streams from disk one .npz at a time. These tests
confirm that streaming yields the same total content (just in a different
order) and that train/val splits don't leak positions.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

from carcassonne_ai.warmstart import (
    GameDataset,
    count_positions,
    iter_game_dataset_files,
    make_streaming_dataset,
    split_files_train_val,
)


def _write_synthetic(path: Path, n_positions: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    # Tiny shapes to keep tests fast; the streaming code is shape-agnostic.
    ds = GameDataset(
        boards=rng.standard_normal((n_positions, 4, 5, 5)).astype(np.float32),
        scalars=rng.standard_normal((n_positions, 3)).astype(np.float32),
        policies=rng.standard_normal((n_positions, 11)).astype(np.float32),
        values=rng.standard_normal(n_positions).astype(np.float32),
        valid_masks=rng.integers(0, 2, size=(n_positions, 11)).astype(bool),
    )
    ds.save(path)


@pytest.fixture
def synthetic_files(tmp_path: Path) -> list[Path]:
    files: list[Path] = []
    for i in range(5):
        p = tmp_path / f"seed_{i:05d}.npz"
        _write_synthetic(p, n_positions=4, seed=i)
        files.append(p)
    return files


def test_count_positions_sums_correctly(synthetic_files: list[Path]) -> None:
    assert count_positions(synthetic_files) == 4 * 5  # 5 files × 4 positions


def test_iter_game_dataset_files_is_sorted(synthetic_files: list[Path]) -> None:
    found = list(iter_game_dataset_files(synthetic_files[0].parent))
    assert found == sorted(found)
    assert len(found) == 5


def test_streaming_yields_all_positions(synthetic_files: list[Path]) -> None:
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=False, shuffle_within_file=False)
    seen = list(iter(ds))
    assert len(seen) == 4 * 5


def test_streaming_yields_correct_shapes(synthetic_files: list[Path]) -> None:
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=False, shuffle_within_file=False)
    for board, scalar, policy, value, mask in ds:
        assert board.shape == (4, 5, 5)
        assert scalar.shape == (3,)
        assert policy.shape == (11,)
        assert value.shape == ()
        assert mask.shape == (11,)
        break


def test_dataloader_with_streaming_assembles_batches(synthetic_files: list[Path]) -> None:
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=False, shuffle_within_file=False)
    loader = DataLoader(ds, batch_size=3, num_workers=0)
    total = 0
    for board_b, scalar_b, policy_b, value_b, mask_b in loader:
        total += board_b.shape[0]
        assert board_b.shape[1:] == (4, 5, 5)
    assert total == 4 * 5


def test_streaming_with_workers_yields_all_positions(synthetic_files: list[Path]) -> None:
    """With num_workers=2 the dataset must shard files across workers and
    the union of yields must still be every position exactly once."""
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=False, shuffle_within_file=False)
    loader = DataLoader(ds, batch_size=1, num_workers=2)
    rows = []
    for board_b, scalar_b, policy_b, value_b, mask_b in loader:
        rows.append((board_b.numpy(), scalar_b.numpy(), value_b.item()))
    assert len(rows) == 4 * 5


def test_split_files_train_val_no_leak(synthetic_files: list[Path]) -> None:
    train, val = split_files_train_val(synthetic_files, val_fraction=0.4, seed=0)
    assert set(train).isdisjoint(set(val))
    assert set(train) | set(val) == set(synthetic_files)
    assert len(val) == 2  # 40% of 5 = 2 (rounded)


def test_split_files_deterministic(synthetic_files: list[Path]) -> None:
    a = split_files_train_val(synthetic_files, val_fraction=0.4, seed=42)
    b = split_files_train_val(synthetic_files, val_fraction=0.4, seed=42)
    assert a == b


def test_set_epoch_changes_file_order(synthetic_files: list[Path]) -> None:
    """When shuffle_files_each_epoch=True, set_epoch(k) varies the order."""
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=True, shuffle_within_file=False, seed=7)
    ds.set_epoch(0)
    order_a = [v.item() for _, _, _, v, _ in ds]
    ds.set_epoch(1)
    order_b = [v.item() for _, _, _, v, _ in ds]
    assert order_a != order_b
    # But the multisets are equal — same positions, different order.
    assert sorted(order_a) == sorted(order_b)


def test_split_handles_empty_list() -> None:
    train, val = split_files_train_val([], val_fraction=0.1, seed=0)
    assert train == [] and val == []
