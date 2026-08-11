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
        ownership=rng.integers(-1, 2, size=(n_positions, 3, 5, 5)).astype(np.float32),
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
    for board, scalar, policy, value, mask, ownership, aux, group in ds:
        assert board.shape == (4, 5, 5)
        assert scalar.shape == (3,)
        assert policy.shape == (11,)
        assert value.shape == ()
        assert mask.shape == (11,)
        assert ownership.shape == (3, 5, 5)
        assert aux.shape == () and aux.dtype == torch.bool
        assert group.shape == () and group.dtype == torch.int64
        break


def test_dataloader_with_streaming_assembles_batches(synthetic_files: list[Path]) -> None:
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=False, shuffle_within_file=False)
    loader = DataLoader(ds, batch_size=3, num_workers=0)
    total = 0
    for board_b, scalar_b, policy_b, value_b, mask_b, own_b, aux_b, group_b in loader:
        total += board_b.shape[0]
        assert board_b.shape[1:] == (4, 5, 5)
        assert own_b.shape[1:] == (3, 5, 5)
        assert aux_b.shape == (board_b.shape[0],) and aux_b.dtype == torch.bool
    assert total == 4 * 5


def test_streaming_with_workers_yields_all_positions(synthetic_files: list[Path]) -> None:
    """With num_workers=2 the dataset must shard files across workers and
    the union of yields must still be every position exactly once."""
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=False, shuffle_within_file=False)
    loader = DataLoader(ds, batch_size=1, num_workers=2)
    rows = []
    for board_b, scalar_b, policy_b, value_b, mask_b, own_b, aux_b, group_b in loader:
        rows.append((board_b.numpy(), scalar_b.numpy(), value_b.item()))
    assert len(rows) == 4 * 5


def test_split_files_train_val_no_leak(synthetic_files: list[Path]) -> None:
    train, val = split_files_train_val(synthetic_files, val_fraction=0.4, seed=0)
    assert set(train).isdisjoint(set(val))
    assert set(train) | set(val) == set(synthetic_files)
    assert len(val) == 2  # 40% of 5 = 2 (rounded)


def test_split_files_train_val_no_leak_with_duplicates() -> None:
    """D-R4-1 regression: warmstart oversampling passes the same .npz MANY times
    (with replacement), so the file list has duplicate paths. The split must route
    EVERY occurrence of a game to one side — a duplicated path must never straddle
    train/val and leak positions across the boundary. val holds one occurrence of
    each held-out game; all duplicates inflate only the TRAIN side."""
    files = [
        Path("a.npz"), Path("a.npz"), Path("a.npz"),  # oversampled x3
        Path("b.npz"),
        Path("c.npz"), Path("c.npz"),                 # oversampled x2
        Path("d.npz"), Path("e.npz"),
    ]
    # sweep several seeds so the assertion holds regardless of which games are held out
    for seed in range(8):
        train, val = split_files_train_val(files, val_fraction=0.4, seed=seed)
        assert set(train).isdisjoint(set(val)), f"leak @ seed {seed}: {set(train) & set(val)}"
        assert len(val) == len(set(val)), f"val has duplicate occurrences @ seed {seed}"
        assert set(train) | set(val) == set(files), f"a game vanished @ seed {seed}"
        for p in set(val):
            assert p not in set(train), f"val game {p} also in train @ seed {seed}"
        for p in set(train):
            # every occurrence of a train-side game is preserved (oversampling intact)
            assert train.count(p) == files.count(p), f"dropped a {p} dup @ seed {seed}"


def test_split_files_deterministic(synthetic_files: list[Path]) -> None:
    a = split_files_train_val(synthetic_files, val_fraction=0.4, seed=42)
    b = split_files_train_val(synthetic_files, val_fraction=0.4, seed=42)
    assert a == b


def test_set_epoch_changes_file_order(synthetic_files: list[Path]) -> None:
    """When shuffle_files_each_epoch=True, set_epoch(k) varies the order."""
    ds = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=True, shuffle_within_file=False, seed=7)
    ds.set_epoch(0)
    order_a = [v.item() for _, _, _, v, _, _, _, _ in ds]
    ds.set_epoch(1)
    order_b = [v.item() for _, _, _, v, _, _, _, _ in ds]
    assert order_a != order_b
    # But the multisets are equal — same positions, different order.
    assert sorted(order_a) == sorted(order_b)


def test_split_handles_empty_list() -> None:
    train, val = split_files_train_val([], val_fraction=0.1, seed=0)
    assert train == [] and val == []


def test_split_zero_val_fraction(synthetic_files: list[Path]) -> None:
    """val_fraction=0.0 must produce an empty val and not silently force
    one val file (reviewer flagged the previous max(1, ...) behavior)."""
    train, val = split_files_train_val(synthetic_files, val_fraction=0.0, seed=0)
    assert val == []
    assert set(train) == set(synthetic_files)


def test_split_rejects_one(synthetic_files: list[Path]) -> None:
    """val_fraction=1.0 would empty the train split; reject it loudly."""
    with pytest.raises(ValueError):
        split_files_train_val(synthetic_files, val_fraction=1.0, seed=0)


def test_split_rejects_out_of_range(synthetic_files: list[Path]) -> None:
    with pytest.raises(ValueError):
        split_files_train_val(synthetic_files, val_fraction=-0.1, seed=0)
    with pytest.raises(ValueError):
        split_files_train_val(synthetic_files, val_fraction=1.5, seed=0)


def test_split_never_empties_train(tmp_path: Path) -> None:
    """With n=2 and val_fraction=0.5, n_val rounds to 1, leaving 1 train.
    With n=2 and val_fraction=0.99, n_val should still be capped to n-1=1."""
    files: list[Path] = []
    for i in range(2):
        p = tmp_path / f"seed_{i:05d}.npz"
        _write_synthetic(p, n_positions=4, seed=i)
        files.append(p)
    train, val = split_files_train_val(files, val_fraction=0.99, seed=0)
    assert len(train) >= 1, "split must never empty the train set"
    assert len(val) >= 1


def test_streaming_shuffle_reproducible_across_runs(synthetic_files: list[Path]) -> None:
    """The within-file shuffle must be reproducible: same seed/epoch/path
    must yield the same order even across processes (zlib.crc32 not Python's
    salted hash). Reviewer flagged the original hash() usage.
    """
    ds_a = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=True, shuffle_within_file=True, seed=42)
    ds_a.set_epoch(0)
    order_a = [v.item() for _, _, _, v, _, _, _, _ in ds_a]
    ds_b = make_streaming_dataset(synthetic_files, shuffle_files_each_epoch=True, shuffle_within_file=True, seed=42)
    ds_b.set_epoch(0)
    order_b = [v.item() for _, _, _, v, _, _, _, _ in ds_b]
    assert order_a == order_b
