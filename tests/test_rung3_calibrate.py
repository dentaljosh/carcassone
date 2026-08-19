#!/usr/bin/env python3
"""Tests for the RUNG 3 (`J > 4`) successor prereg's R5-1 counts-only
calibration sweep (`scripts/tiletie/rung3_calibrate.py`).

`measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md` §R5-1.1 requires a
counts-only density sweep at >= 4 nested corpus scales, BEFORE the mechanical
READ_RULE is drafted; §R5-2 adds a mining ply-floor knob. This suite covers:

  * digest REUSE — the sweep never hashes a checksum itself, it goes through
    `gate_disjoint.load_digest_map` exactly like `G-DISJOINT` does
  * nested-scale MONOTONICITY of the raw counts
  * a synthetic fixture with collisions PLANTED at known plies, and exact
    recovery via the ply histogram + the ply-floor knob's arithmetic
  * the >= 4-scales precondition, enforced loudly
  * the CLI end to end (argparse, JSON emission, exit codes)

Fast, hermetic, no engine, no replay, no leaf.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TILETIE = REPO / "scripts" / "tiletie"
if str(TILETIE) not in sys.path:
    sys.path.insert(0, str(TILETIE))

import gate_disjoint as GD                                          # noqa: E402
import rung3_calibrate as RC                                        # noqa: E402

SCRIPT = TILETIE / "rung3_calibrate.py"


# --------------------------------------------------------------------------- #
# fixture builder — plain leg1 jsonl, the SAME shape gate_disjoint.py reads    #
# --------------------------------------------------------------------------- #
def _leg_line(*, ds, ply, checksum, rid_suffix=""):
    rid = f"tt_sp_{ds}_p{ply}{rid_suffix}"
    return {"rid": rid, "root_id": f"sp_{ds}", "deck_seed": ds, "ply": ply,
            "checksum": checksum}


def write_leg_file(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def make_planted_corpus(tmp_path, *, n_games=10):
    """`n_games` games, each with candidate positions at ply 2 / 5 / 8.

    Collisions PLANTED at exactly two known plies:
      * ply 2  -- deck_seed 1 and 2 share a checksum (both enter at scale=2)
      * ply 5  -- deck_seed 6 and 7 share a checksum (only enters at scale=7)
    Every other position gets a checksum unique to (deck_seed, ply). This is
    the ground truth every collision-count / ply-histogram / ply-floor
    assertion below is checked against.
    """
    records = []
    for ds in range(1, n_games + 1):
        for ply in (2, 5, 8):
            if (ds, ply) == (1, 2) or (ds, ply) == (2, 2):
                checksum = "COLLIDE_PLY2"
            elif (ds, ply) == (6, 5) or (ds, ply) == (7, 5):
                checksum = "COLLIDE_PLY5"
            else:
                checksum = f"UNIQUE_{ds}_{ply}"
            records.append(_leg_line(ds=ds, ply=ply, checksum=checksum))
    leg = tmp_path / "positions_walled_leg1.jsonl"
    write_leg_file(leg, records)
    return leg


# --------------------------------------------------------------------------- #
# digest reuse                                                                  #
# --------------------------------------------------------------------------- #
def test_digest_reuse_calls_gate_disjoint_load_digest_map(tmp_path, monkeypatch):
    """The sweep must compute its digests through
    `gate_disjoint.load_digest_map` — never a second `hashlib.sha256` of its
    own. Proven by spying on the gate's own loader: it must be called, and the
    module under test must not import `hashlib` at all."""
    leg = make_planted_corpus(tmp_path)
    calls = []
    real = GD.load_digest_map

    def spy(paths):
        calls.append(list(paths))
        return real(paths)

    monkeypatch.setattr(RC.GD, "load_digest_map", spy)
    RC.run_calibration(legs=[leg], scales=[2, 4, 7, 10])
    assert len(calls) == 1, "run_calibration must call gate_disjoint.load_digest_map exactly once"
    assert "hashlib" not in dir(RC), "rung3_calibrate must not import hashlib itself"


def test_digests_match_gate_disjoint_directly(tmp_path):
    """The digest MAP the sweep uses is byte-identical to calling
    `gate_disjoint.load_digest_map` directly on the same files."""
    leg = make_planted_corpus(tmp_path)
    direct_map, direct_lines = GD.load_digest_map([leg])
    report = RC.run_calibration(legs=[leg], scales=[2, 4, 7, 10])
    assert report["config"]["n_leg_lines_total"] == direct_lines
    # every rid that appears in the digest map must appear in the sweep's own
    # metadata load with the same rid spelling (same source of truth)
    meta = RC.load_meta([leg])
    all_rids_in_digest_map = {r for rids in direct_map.values() for r in rids}
    assert all_rids_in_digest_map == set(meta)


# --------------------------------------------------------------------------- #
# >= 4 scales precondition                                                      #
# --------------------------------------------------------------------------- #
def test_fewer_than_four_scales_raises(tmp_path):
    leg = make_planted_corpus(tmp_path)
    with pytest.raises(RC.CalibrationError, match="R5-1.1 requires"):
        RC.run_calibration(legs=[leg], scales=[2, 4, 7])


def test_four_distinct_scales_after_dedup_raises(tmp_path):
    """Duplicate scale values collapse before the >= 4 check -- so [2, 2, 4,
    7, 10] (4 distinct values) must PASS, not raise on 'too few'."""
    leg = make_planted_corpus(tmp_path)
    report = RC.run_calibration(legs=[leg], scales=[2, 2, 4, 7, 10])
    assert report["config"]["scales"] == [2, 4, 7, 10]


def test_scale_exceeding_corpus_size_raises(tmp_path):
    leg = make_planted_corpus(tmp_path, n_games=10)
    with pytest.raises(RC.CalibrationError, match="exceeds"):
        RC.run_calibration(legs=[leg], scales=[2, 4, 7, 11])


def test_missing_required_field_raises(tmp_path):
    leg = tmp_path / "positions_walled_leg1.jsonl"
    write_leg_file(leg, [{"rid": "tt_sp_1_p2", "checksum": "X", "ply": 2}])  # no deck_seed
    with pytest.raises(RC.CalibrationError, match="deck_seed"):
        RC.run_calibration(legs=[leg], scales=[1, 2, 3, 4])


# --------------------------------------------------------------------------- #
# nested-scale monotonicity                                                     #
# --------------------------------------------------------------------------- #
def test_nested_scale_monotonicity(tmp_path):
    """Positions, exclusions and pairwise collisions must be non-decreasing as
    G grows, at every ply floor -- a G-prefix is a strict superset of any
    smaller prefix, so nothing counted at a smaller scale can vanish."""
    leg = make_planted_corpus(tmp_path, n_games=20)
    scales = [2, 5, 10, 15, 20]
    report = RC.run_calibration(legs=[leg], scales=scales,
                                ply_floors=[0, 3, 6])
    for k_block in report["by_ply_floor"].values():
        per_scale = k_block["per_scale"]
        prev = None
        for g in scales:
            cur = per_scale[str(g)]
            if prev is not None:
                assert cur["n_positions"] >= prev["n_positions"]
                assert cur["n_exclusions"] >= prev["n_exclusions"]
                assert cur["n_pairwise_collisions"] >= prev["n_pairwise_collisions"]
            prev = cur


def test_scale_prefix_is_a_true_prefix_of_games(tmp_path):
    """The default (unseeded) game order is sorted ascending deck_seed, so a
    scale-G prefix is exactly deck_seed 1..G."""
    leg = make_planted_corpus(tmp_path, n_games=10)
    meta = RC.load_meta([leg])
    order = RC.committed_game_order(meta)
    assert order == list(range(1, 11))


def test_order_seed_is_deterministic_and_differs_from_default(tmp_path):
    leg = make_planted_corpus(tmp_path, n_games=10)
    meta = RC.load_meta([leg])
    default_order = RC.committed_game_order(meta)
    seeded_a = RC.committed_game_order(meta, order_seed=20260817)
    seeded_b = RC.committed_game_order(meta, order_seed=20260817)
    assert seeded_a == seeded_b, "same seed must reproduce the same order"
    assert set(seeded_a) == set(default_order)
    assert seeded_a != default_order, "a real shuffle should not equal sorted order"


# --------------------------------------------------------------------------- #
# planted-collision recovery: ply histogram + ply-floor arithmetic EXACT        #
# --------------------------------------------------------------------------- #
def test_planted_collisions_recovered_at_full_scale_no_floor(tmp_path):
    leg = make_planted_corpus(tmp_path, n_games=10)
    report = RC.run_calibration(legs=[leg], scales=[2, 4, 7, 10],
                                ply_floors=[0])
    blk = report["by_ply_floor"]["0"]["per_scale"]["10"]
    assert blk["n_digest_groups_collided"] == 2
    assert blk["n_pairwise_collisions"] == 2
    assert blk["n_exclusions"] == 2
    assert blk["collision_ply_histogram_touched"] == {2: 2, 5: 2}
    assert blk["collision_ply_histogram_excluded"] == {2: 1, 5: 1}


def test_ply_floor_removes_exactly_the_collision_below_it(tmp_path):
    """k=3 must remove the ply-2 collision entirely (both members excluded
    from the candidate set, not merely from the excluded-count) while leaving
    the ply-5 collision untouched. k=6 must remove both."""
    leg = make_planted_corpus(tmp_path, n_games=10)
    report = RC.run_calibration(legs=[leg], scales=[2, 4, 7, 10],
                                ply_floors=[0, 3, 6])

    k0 = report["by_ply_floor"]["0"]["per_scale"]["10"]
    k3 = report["by_ply_floor"]["3"]["per_scale"]["10"]
    k6 = report["by_ply_floor"]["6"]["per_scale"]["10"]

    assert k0["n_exclusions"] == 2
    # k=3: only the ply-5 collision remains -- exactly 1 exclusion, and the
    # ply-2 entry must be ABSENT from the histogram (not zero -- absent)
    assert k3["n_exclusions"] == 1
    assert 2 not in k3["collision_ply_histogram_excluded"]
    assert k3["collision_ply_histogram_excluded"] == {5: 1}
    # k=3 must also have dropped exactly 2 candidate positions per game with a
    # ply-2 row (10 games x 1 ply-2 position each = 10 fewer than k=0)
    assert k0["n_positions"] - k3["n_positions"] == 10

    # k=6: both planted collisions are below the floor -- zero exclusions
    assert k6["n_exclusions"] == 0
    assert k6["collision_ply_histogram_excluded"] == {}
    assert k6["n_positions"] == 10  # only the ply-8 row per game survives


def test_ply_floor_knob_is_monotonically_less_or_equal_collisions(tmp_path):
    """Raising k can only ever REMOVE collision mass, never add it (every
    position dropped by a higher floor is also dropped by every floor above
    it, and a group can only lose members as k rises)."""
    leg = make_planted_corpus(tmp_path, n_games=10)
    report = RC.run_calibration(legs=[leg], scales=[2, 4, 7, 10],
                                ply_floors=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    prev = None
    for k in range(10):
        cur = report["by_ply_floor"][str(k)]["per_scale"]["10"]["n_exclusions"]
        if prev is not None:
            assert cur <= prev
        prev = cur


# --------------------------------------------------------------------------- #
# density / d_model / saturation guard sanity                                  #
# --------------------------------------------------------------------------- #
def test_density_matches_exclusions_over_positions(tmp_path):
    leg = make_planted_corpus(tmp_path, n_games=10)
    report = RC.run_calibration(legs=[leg], scales=[2, 4, 7, 10])
    blk = report["by_ply_floor"]["0"]["per_scale"]["10"]
    assert blk["density"] == pytest.approx(blk["n_exclusions"] / blk["n_positions"])


def test_fit_power_law_exact_on_synthetic_power_law_points():
    """A synthetic (G, d) set drawn EXACTLY from `d = 2 * G**1.5` must recover
    a=2, b=1.5 (up to floating-point tolerance) and r_squared == 1."""
    a_true, b_true = 2.0, 1.5
    points = [(g, a_true * g ** b_true) for g in (100, 500, 1000, 5000)]
    fit = RC.fit_power_law(points)
    assert fit["a"] == pytest.approx(a_true, rel=1e-6)
    assert fit["b"] == pytest.approx(b_true, rel=1e-6)
    assert fit["r_squared"] == pytest.approx(1.0, abs=1e-9)


def test_fit_power_law_needs_two_usable_points():
    with pytest.raises(RC.CalibrationError):
        RC.fit_power_law([(100, 0.01)])
    with pytest.raises(RC.CalibrationError):
        RC.fit_power_law([(100, None), (200, 0.0)])


def test_saturation_guard_flags_high_density(tmp_path):
    """A corpus with a saturating (large, roughly-constant) collision rate
    must trip the 5% guard at every ply floor that cannot clear it."""
    records = []
    # 40 games, EVERY ply-2 position collides pairwise in groups of 2 -- a
    # deliberately dense corpus so d_model(G) stays >> 5%.
    for ds in range(1, 41):
        checksum = f"COLLIDE_{(ds - 1) // 2}"
        records.append(_leg_line(ds=ds, ply=2, checksum=checksum))
        records.append(_leg_line(ds=ds, ply=8, checksum=f"UNIQUE_{ds}"))
    leg = write_leg_file(tmp_path / "positions_walled_leg1.jsonl", records)
    report = RC.run_calibration(legs=[leg], scales=[10, 20, 30, 40],
                                ply_floors=[0, 3])
    assert report["by_ply_floor"]["0"]["saturation_void"] is True
    # k=3 drops every ply-2 collision, so it must clear the guard
    assert report["by_ply_floor"]["3"]["saturation_void"] is False
    assert report["recommended_ply_floor_k"] == 3


def test_recommended_k_none_when_nothing_clears_guard(tmp_path):
    """If every candidate floor still saturates, `recommended_ply_floor_k`
    must be None -- never silently pick an unsafe floor."""
    records = []
    for ds in range(1, 41):
        checksum = f"COLLIDE_{(ds - 1) // 2}"
        # the SAME collision at every candidate ply floor, so raising k never
        # clears the guard
        records.append(_leg_line(ds=ds, ply=2, checksum=checksum))
        records.append(_leg_line(ds=ds, ply=3, checksum=checksum + "b"))
    leg = write_leg_file(tmp_path / "positions_walled_leg1.jsonl", records)
    # every position collides regardless of floor 0..1 (ply 2 and 3 both >=
    # any floor <= 1); use floors that cannot remove the ply-3 collision
    report = RC.run_calibration(legs=[leg], scales=[10, 20, 30, 40],
                                ply_floors=[0, 1])
    assert report["recommended_ply_floor_k"] is None


# --------------------------------------------------------------------------- #
# CLI end-to-end                                                                #
# --------------------------------------------------------------------------- #
def test_cli_writes_calibration_json(tmp_path):
    leg = make_planted_corpus(tmp_path, n_games=10)
    out = tmp_path / "CALIBRATION.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--legs", str(leg),
         "--scales", "2", "4", "7", "10",
         "--ply-floors", "0", "3", "6",
         "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    assert out.is_file()
    body = json.loads(out.read_text())
    assert body["schema"] == "carcassonne-rung3-r5-calibration/v1"
    assert body["config"]["scales"] == [2, 4, 7, 10]
    assert "0" in body["by_ply_floor"] and "3" in body["by_ply_floor"]


def test_cli_legs_dir_expands_glob(tmp_path):
    leg_dir = tmp_path / "positions_s2"
    make_planted_corpus(leg_dir, n_games=10)
    out = tmp_path / "CALIBRATION.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--legs-dir", str(leg_dir),
         "--scales", "2", "4", "7", "10", "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    assert out.is_file()


def test_cli_fewer_than_four_scales_exits_2(tmp_path):
    leg = make_planted_corpus(tmp_path, n_games=10)
    out = tmp_path / "CALIBRATION.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--legs", str(leg),
         "--scales", "2", "4", "7", "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "R5-1.1 requires" in r.stderr
    assert not out.exists()


def test_cli_missing_legs_source_exits_2(tmp_path):
    out = tmp_path / "CALIBRATION.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--scales", "2", "4", "7", "10", "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "--legs-dir" in r.stderr


def test_cli_no_clearing_floor_exits_1_but_still_writes(tmp_path):
    records = []
    for ds in range(1, 41):
        checksum = f"COLLIDE_{(ds - 1) // 2}"
        records.append(_leg_line(ds=ds, ply=2, checksum=checksum))
        records.append(_leg_line(ds=ds, ply=3, checksum=checksum + "b"))
    leg = write_leg_file(tmp_path / "positions_walled_leg1.jsonl", records)
    out = tmp_path / "CALIBRATION.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--legs", str(leg),
         "--scales", "10", "20", "30", "40",
         "--ply-floors", "0", "1", "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 1
    assert out.is_file()
    assert "NO PLY FLOOR CLEARS" in r.stderr
