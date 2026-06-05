"""Test train_iter._stage_files_local (keeps the train read-path off 9p/CIFS)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from train_iter import _stage_files_local  # noqa: E402


def test_stage_copies_and_preserves_order_and_content(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    files = []
    for i in range(3):
        f = src / f"seed_{i:06d}.npz"
        f.write_bytes(bytes([i]) * 16)
        files.append(f)
    staged = _stage_files_local(files, tmp_path / "stage")
    assert len(staged) == 3
    for orig, st in zip(files, staged):
        assert st.exists() and st.read_bytes() == orig.read_bytes()
    # all under the stage dir, none still on the source
    assert all((tmp_path / "stage") in s.parents for s in staged)


def test_stage_dedupes_duplicate_sources(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    a = src / "seed_000001.npz"
    a.write_bytes(b"A" * 8)
    b = src / "seed_000002.npz"
    b.write_bytes(b"B" * 8)
    # warmstart-mix samples with replacement → duplicate entries in the list
    files = [a, b, a, a, b]
    staged = _stage_files_local(files, tmp_path / "stage")
    assert len(staged) == 5                      # order/length preserved
    assert staged[0] == staged[2] == staged[3]   # same source → same staged path
    assert staged[1] == staged[4]
    # only 2 distinct files actually copied to disk
    assert len(set(staged)) == 2
    assert len(list((tmp_path / "stage").iterdir())) == 2
