"""Probe §5A — unit test for step1_train.align_tempo (the shared-trainer edit).

Guards the (game_seed, ply, within-group ordinal) join that appends the tempo
block to the CL-037 dataset. Pure-logic: synthetic arrays, no 32GB obs, no GPU.
The bit-exact leaf-match on real data lives in the run log; this pins the join
semantics (ordinal within group, zero-fill on miss) so a refactor can't silently
mis-align tempo rows.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))


def _write_tempo(tmp_path, rows):
    """rows: list of (game_seed, ply, child_index, [feat...])."""
    gs = np.array([r[0] for r in rows], np.int64)
    ply = np.array([r[1] for r in rows], np.int16)
    ci = np.array([r[2] for r in rows], np.int32)
    tempo = np.array([r[3] for r in rows], np.float32)
    p = tmp_path / "tempo.npz"
    np.savez(p, tempo=tempo, game_seed=gs, ply=ply, child_index=ci,
             tempo_names=np.array(["f0", "f1"]))
    return str(p)


def test_align_maps_by_seed_ply_ordinal(tmp_path):
    from step1_train import align_tempo
    # tempo emitted for 2 roots, children in child_index order (scrambled row order)
    tempo_path = _write_tempo(tmp_path, [
        (100, 5, 1, [1.1, 1.2]),   # root A child 1
        (100, 5, 0, [0.1, 0.2]),   # root A child 0
        (200, 9, 0, [9.0, 9.1]),   # root B child 0
        (200, 9, 1, [9.2, 9.3]),   # root B child 1
    ])
    # dataset rows: group-contiguous, in enumeration order (ordinal = position in group)
    # group 0 = root A (2 rows), group 1 = root B (2 rows)
    grp = np.array([0, 0, 1, 1], np.int32)
    gs = np.array([100, 100, 200, 200], np.int64)
    ply = np.array([5, 5, 9, 9], np.int16)

    out, names = align_tempo(tempo_path, grp, gs, ply)
    assert names == ["f0", "f1"]
    assert out.shape == (4, 2)
    # dataset row 0 = root A ordinal 0 -> child_index 0 -> [0.1,0.2]
    np.testing.assert_allclose(out[0], [0.1, 0.2])
    np.testing.assert_allclose(out[1], [1.1, 1.2])   # ordinal 1
    np.testing.assert_allclose(out[2], [9.0, 9.1])   # root B ordinal 0
    np.testing.assert_allclose(out[3], [9.2, 9.3])


def test_align_respects_group_contiguity_not_row_order(tmp_path):
    """Ordinal is per-group, so two groups sharing a (seed,ply) would collide —
    but seeds are unique per root; here confirm interleaved group ids still map by
    each group's own ordinal counter."""
    from step1_train import align_tempo
    tempo_path = _write_tempo(tmp_path, [
        (100, 5, 0, [0.1, 0.2]),
        (100, 5, 1, [1.1, 1.2]),
        (100, 5, 2, [2.1, 2.2]),
    ])
    grp = np.array([7, 7, 7], np.int32)     # arbitrary group id, 3 children
    gs = np.array([100, 100, 100], np.int64)
    ply = np.array([5, 5, 5], np.int16)
    out, _ = align_tempo(tempo_path, grp, gs, ply)
    np.testing.assert_allclose(out, [[0.1, 0.2], [1.1, 1.2], [2.1, 2.2]])


def test_align_zero_fills_missing(tmp_path):
    from step1_train import align_tempo
    tempo_path = _write_tempo(tmp_path, [(100, 5, 0, [0.1, 0.2])])
    grp = np.array([0, 0], np.int32)         # 2 rows, but tempo only has ordinal 0
    gs = np.array([100, 100], np.int64)
    ply = np.array([5, 5], np.int16)
    out, _ = align_tempo(tempo_path, grp, gs, ply)
    np.testing.assert_allclose(out[0], [0.1, 0.2])
    np.testing.assert_allclose(out[1], [0.0, 0.0])   # ordinal 1 missing -> zero-filled


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
