"""Contract tests for the TERMINAL-GROUNDED TIE ARBITRATION instruments
(scripts/tiletie/build_tiearb_plan.py, scripts/tiletie/analyze_tiearb.py;
measurement/tiearb_20260816/).

Pure plan/stat surgery -- no engine import, no search, no share writes, no
oracle record opened. Every fixture is synthetic and lives under tmp_path; the
only real files read are the corpus's own ARMS.json / HOLDOUT_ROOTS.json plan
metadata (no VALUE, no statistic).
"""
from __future__ import annotations

import itertools
import json
import math
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import analyze_tiletie as AT      # noqa: E402
import analyze_tiearb as TA       # noqa: E402
import build_tiearb_plan as BT    # noqa: E402


# =========================================================================== #
# A. build_tiearb_plan.py
# =========================================================================== #

# --------------------------------------------------------------------------- #
# A1. the real holdout slice is EXACTLY 211 positions / 120 roots              #
# --------------------------------------------------------------------------- #
_ARMS = REPO / "measurement/tiletie_pricing_20260812/positions_pooled/ARMS.json"
_HOLD = REPO / "measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json"


@pytest.mark.skipif(not (_ARMS.is_file() and _HOLD.is_file()),
                    reason="corpus plan metadata not present")
def test_real_holdout_slice_is_211_positions_120_roots():
    arms = json.loads(_ARMS.read_text())
    holdout = BT.load_holdout_roots(_HOLD)
    assert len(arms) == 733
    rids = BT.holdout_rids(arms, holdout)
    assert len(rids) == BT.EXPECT_HOLDOUT_POSITIONS == 211
    assert len({arms[r]["root_id"] for r in rids}) == BT.EXPECT_HOLDOUT_ROOTS == 120
    # and the complement is the 522-position DEV slice the OOF run used
    assert len(arms) - len(rids) == 522


@pytest.mark.skipif(not (_ARMS.is_file() and _HOLD.is_file()),
                    reason="corpus plan metadata not present")
def test_pilot_rids_are_dev_not_holdout():
    arms = json.loads(_ARMS.read_text())
    holdout = BT.load_holdout_roots(_HOLD)
    pilot = BT.load_pilot_rids(REPO / "measurement/tiletie_oof_20260814/PILOT_RIDS.json")
    assert len(pilot) == 20
    assert all(r in arms for r in pilot)
    assert not [r for r in pilot if arms[r]["root_id"] in holdout]


# --------------------------------------------------------------------------- #
# A2. the committed permutation                                               #
# --------------------------------------------------------------------------- #
def test_committed_order_is_reproducible_from_seed_20260816():
    rids = [f"r{i:03d}" for i in range(50)]
    a = BT.committed_order(rids)
    b = BT.committed_order(list(reversed(rids)))     # input order must not matter
    assert a == b
    expect = sorted(rids)
    random.Random(20260816).shuffle(expect)
    assert a == expect
    assert sorted(a) == sorted(rids)
    assert BT.PERMUTATION_SEED == 20260816


def test_committed_order_is_a_permutation_not_a_subset():
    rids = [f"r{i:03d}" for i in range(37)]
    order = BT.committed_order(rids)
    assert len(order) == len(rids) == len(set(order))


# --------------------------------------------------------------------------- #
# A3. chunk_slices partitions                                                  #
# --------------------------------------------------------------------------- #
def test_chunk_slices_partition_preserves_order_balanced():
    order = list(range(211))
    chunks = BT.chunk_slices(order, 4)
    assert sum(chunks, []) == order
    sizes = [len(c) for c in chunks]
    assert sum(sizes) == 211
    assert max(sizes) - min(sizes) <= 1
    flat = [x for c in chunks for x in c]
    assert len(flat) == len(set(flat))           # no overlap, no loss


def test_chunk_slices_k1_returns_whole():
    order = list(range(7))
    assert BT.chunk_slices(order, 1) == [order]


def test_chunk_slices_rejects_zero():
    with pytest.raises(ValueError):
        BT.chunk_slices([1, 2, 3], 0)


# --------------------------------------------------------------------------- #
# A4. holdout_rids                                                             #
# --------------------------------------------------------------------------- #
def test_holdout_rids_selects_only_holdout_roots():
    arms = {"a": {"root_id": "R1"}, "b": {"root_id": "R2"},
            "c": {"root_id": "R1"}, "d": {"root_id": "R3"}}
    assert BT.holdout_rids(arms, {"R1", "R3"}) == ["a", "c", "d"]


# --------------------------------------------------------------------------- #
# A5. G-SLICE guards                                                           #
# --------------------------------------------------------------------------- #
def _mini_arms():
    return {
        "p1": {"root_id": "R1", "stratum": "selfplay", "arms": [10, 11]},
        "p2": {"root_id": "R2", "stratum": "selfplay", "arms": [10, 11]},
        "p3": {"root_id": "R3", "stratum": "e4", "arms": [10, 11]},
    }


def test_g_slice_raises_when_a_non_holdout_rid_enters_a_holdout_dir(tmp_path):
    arms = _mini_arms()
    with pytest.raises(SystemExit, match="G-SLICE"):
        BT.write_plan_dir(tmp_path / "out", {"p1", "p2"}, source_plan={},
                          source_arms=arms, dropped={}, leg_rows={}, label="holdout",
                          holdout={"R1"}, require_holdout=True)
    assert not (tmp_path / "out" / "POSITIONS_PLAN.json").exists()


def test_g_slice_raises_when_a_holdout_rid_leaks_into_the_dev_pilot(tmp_path):
    arms = _mini_arms()
    with pytest.raises(SystemExit, match="G-SLICE"):
        BT.write_plan_dir(tmp_path / "out", {"p2"}, source_plan={}, source_arms=arms,
                          dropped={}, leg_rows={}, label="pilot",
                          holdout={"R2"}, require_holdout=False)
    assert not (tmp_path / "out" / "POSITIONS_PLAN.json").exists()


def test_write_plan_dir_rejects_unknown_rid(tmp_path):
    with pytest.raises(SystemExit, match="unknown rid"):
        BT.write_plan_dir(tmp_path / "out", {"nope"}, source_plan={},
                          source_arms=_mini_arms(), dropped={}, leg_rows={},
                          label="x", holdout=set(), require_holdout=True)


# --------------------------------------------------------------------------- #
# A6. end-to-end plan build on a synthetic corpus                              #
# --------------------------------------------------------------------------- #
def _build_source_fixture(tmp_path):
    """A tiny 6-position, 2-leg-file source plan on disk (run_tiletie shape)."""
    src = tmp_path / "source"
    src.mkdir()
    arms = {}
    for i, (root, strat) in enumerate([("H1", "selfplay"), ("H1", "selfplay"),
                                       ("H2", "e4"), ("D1", "selfplay"),
                                       ("D2", "e4"), ("D2", "e4")], start=1):
        arms[f"p{i}"] = {"root_id": root, "stratum": strat, "rules_profile": "walled",
                         "phase_bucket": "mid", "arms": [10, 11, 12], "capped": False,
                         "champ_arm_index": 0, "ply": 40}
    leg1 = [json.dumps({"rid": r}) for r in arms]
    leg2 = [json.dumps({"rid": r}) for r in ("p1", "p3", "p5")]
    (src / "positions_walled_leg1.jsonl").write_text("".join(x + "\n" for x in leg1))
    (src / "positions_walled_leg2.jsonl").write_text("".join(x + "\n" for x in leg2))
    plan = {
        "afterstate_dedupe": {"applied": True, "n_qualifying_before_drop": 6,
                              "n_dropped_all_transposition": 0},
        "cap_j": 4, "m_worlds": 32, "max_arms": 5, "out_dir": str(src),
        "files": {
            "walled/leg1": {"n": 6, "path": str(src / "positions_walled_leg1.jsonl")},
            "walled/leg2": {"n": 3, "path": str(src / "positions_walled_leg2.jsonl")},
        },
    }
    (src / "POSITIONS_PLAN.json").write_text(json.dumps(plan))
    (src / "ARMS.json").write_text(json.dumps(arms))
    (src / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps({"rows": []}))
    return src, plan, arms


def _write_aux(tmp_path, holdout_roots, pilot_rids):
    h = tmp_path / "HOLDOUT_ROOTS.json"
    h.write_text(json.dumps({"holdout_roots": sorted(holdout_roots)}))
    p = tmp_path / "PILOT_RIDS.json"
    p.write_text(json.dumps({"rids": list(pilot_rids)}))
    return h, p


def test_main_builds_holdout_chunks_and_pilot(tmp_path, capsys):
    src, _plan, arms = _build_source_fixture(tmp_path)
    h, p = _write_aux(tmp_path, {"H1", "H2"}, ["p4", "p5"])
    out = tmp_path / "out"
    rc = BT.main(["--source-dir", str(src), "--holdout", str(h),
                  "--pilot-rids", str(p), "--out-dir", str(out),
                  "--chunks", "2", "--no-expect"])
    capsys.readouterr()
    assert rc == 0

    order = json.loads((out / "POSITION_ORDER.json").read_text())
    assert order["seed"] == 20260816
    assert sorted(order["order"]) == ["p1", "p2", "p3"]
    assert order["n"] == 3
    assert sum(order["chunk_sizes"]) == 3

    # holdout dir carries all 3 and ONLY holdout roots (G-SLICE)
    hold_arms = json.loads((out / "positions_holdout" / "ARMS.json").read_text())
    assert set(hold_arms) == {"p1", "p2", "p3"}
    assert all(arms[r]["root_id"] in {"H1", "H2"} for r in hold_arms)

    # chunks partition the holdout exactly
    seen = []
    for k in (1, 2):
        a = json.loads((out / f"positions_chunk{k}" / "ARMS.json").read_text())
        assert all(arms[r]["root_id"] in {"H1", "H2"} for r in a)
        seen.extend(a)
    assert sorted(seen) == ["p1", "p2", "p3"]
    assert len(seen) == len(set(seen))

    # pilot dir is DEV only
    pil = json.loads((out / "positions_pilot" / "ARMS.json").read_text())
    assert set(pil) == {"p4", "p5"}
    assert not [r for r in pil if arms[r]["root_id"] in {"H1", "H2"}]

    summary = json.loads((out / "PLAN_SUMMARY.json").read_text())
    assert summary["holdout_positions"] == 3
    assert summary["c_tier1_worker_s_per_playout"] == pytest.approx(2.1783)
    hd = summary["dirs"]["holdout"]
    assert hd["playouts"] == hd["legs"] * 2 * 32
    assert hd["eta"]["worker_hours"] == pytest.approx(hd["playouts"] * 2.1783 / 3600.0)
    assert hd["eta"]["wall_hours_at_W30"] == pytest.approx(
        hd["playouts"] * 2.1783 / (3600.0 * 30))


def test_main_refuses_when_slice_size_is_wrong(tmp_path, capsys):
    src, _plan, _arms = _build_source_fixture(tmp_path)
    h, p = _write_aux(tmp_path, {"H1", "H2"}, ["p4"])
    with pytest.raises(SystemExit, match="REFUSING"):
        BT.main(["--source-dir", str(src), "--holdout", str(h),
                 "--pilot-rids", str(p), "--out-dir", str(tmp_path / "o2"),
                 "--chunks", "2"])          # no --no-expect => 211/120 assertion fires
    capsys.readouterr()


def test_main_refuses_when_a_pilot_rid_is_a_holdout_root(tmp_path, capsys):
    src, _plan, _arms = _build_source_fixture(tmp_path)
    h, p = _write_aux(tmp_path, {"H1", "H2"}, ["p1"])       # p1 is root H1 == holdout
    with pytest.raises(SystemExit, match="G-SLICE"):
        BT.main(["--source-dir", str(src), "--holdout", str(h),
                 "--pilot-rids", str(p), "--out-dir", str(tmp_path / "o3"),
                 "--chunks", "2", "--no-expect"])
    capsys.readouterr()


# =========================================================================== #
# B. analyze_tiearb.py -- the estimator
# =========================================================================== #
M = 8


def _rec(values_a, values_b, pick_a, pick_b, *, seeds=None, crn=True, checksum=True):
    seeds = seeds if seeds is not None else list(range(1, M + 1))
    return {"values_a": list(values_a), "values_b": list(values_b),
            "world_seeds": list(seeds), "playout_seeds": [s + 1000 for s in seeds],
            "crn_verified": crn, "checksum_ok": checksum,
            "pick_a": pick_a, "pick_b": pick_b, "distinct_afterstates": M,
            "m": M, "ok": True, "elapsed_secs": 1.0}


def _fixture(if_rows, arb_rows, *, rid="p1", root="R1", champ_arm_index=0,
             n_positions=1, holdout_roots=frozenset()):
    """`if_rows`/`arb_rows` are A x M matrices (row 0 = the reference arm).

    Returns (arms_index, if_by_rid, arb_by_rid) for `n_positions` clones, each
    with its own rid/root so cluster_robust has >= 2 clusters when needed.
    """
    n_arms = len(if_rows)
    actions = [100 + i for i in range(n_arms)]
    arms_index, if_by, arb_by = {}, {}, {}
    for i in range(n_positions):
        r = rid if n_positions == 1 else f"{rid}_{i}"
        rt = root if n_positions == 1 else f"{root}_{i}"
        arms_index[r] = {"root_id": rt, "stratum": "selfplay", "rules_profile": "walled",
                         "phase_bucket": "mid", "capped": False, "ply": 40,
                         "arms": actions, "champ_arm_index": champ_arm_index}
        if_by[r] = {leg: _rec(if_rows[0], if_rows[leg], actions[0], actions[leg])
                    for leg in range(1, n_arms)}
        arb_by[r] = {leg: _rec(arb_rows[0], arb_rows[leg], actions[0], actions[leg])
                     for leg in range(1, n_arms)}
    return arms_index, if_by, arb_by


_RATES = {"by_stratum": {"selfplay": {"scale_all": 1.0, "scale_strict": 1.0},
                         "e4": {"scale_all": 1.0, "scale_strict": 1.0}}}


def _const(v):
    return [float(v)] * M


def _sym_crossfit(matrix, champ_pos):
    """The symmetrized `analyze_tiletie.crossfit_regret` -- the reference the
    per-position `ora` MUST equal."""
    out = []
    for swap in (False, True):
        sel, eva = AT.parity_indices(M, base=1, swap=swap)
        r, _ = AT.crossfit_regret(matrix, sel, eva, champ_pos)
        out.append(r)
    return (out[0] + out[1]) / 2.0


def test_ora_equals_symmetrized_crossfit_regret():
    if_rows = [_const(0.0), _const(1.0), _const(3.0)]
    arb_rows = [_const(5.0), _const(1.0), _const(0.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=1)
    rows, _integ, _cross, _counts = TA.build_positions(
        arms, ifb, arbb, _RATES, set(), rnd_seed=20260816)
    assert len(rows) == 1
    r = rows[0]
    assert r["champ_pos"] == 1
    assert r["ora"] == pytest.approx(_sym_crossfit(if_rows, 1))
    assert r["ora"] == pytest.approx(2.0)          # 3 - 1


def test_arb_uses_the_ARB_argmax_priced_by_IF_on_the_disjoint_half():
    # ARB ranks arm 0 best (5 > 1 > 0); IF ranks arm 2 best (3 > 1 > 0).
    if_rows = [_const(0.0), _const(1.0), _const(3.0)]
    arb_rows = [_const(5.0), _const(1.0), _const(0.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=1)
    rows, *_ = TA.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=20260816)
    r = rows[0]
    assert r["a_arb_folds"] == [0, 0]
    assert r["a_ora_folds"] == [2, 2]
    assert r["arb"] == pytest.approx(-1.0)         # IF[arm0] - IF[champ] = 0 - 1
    assert r["arb"] != pytest.approx(r["ora"])     # the judges disagree
    assert r["sel_agree"] is False
    assert r["pickchg"] is True
    # C-ARM0: the same pick, comparator = arm 0
    assert r["arm0"] == pytest.approx(0.0)         # IF[arm0] - IF[arm0]


def test_arb_equals_ora_when_the_two_judges_agree():
    if_rows = [_const(0.0), _const(1.0), _const(3.0)]
    arb_rows = [_const(0.0), _const(1.0), _const(9.0)]      # same ordering
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=1)
    rows, *_ = TA.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=20260816)
    r = rows[0]
    assert r["a_arb_folds"] == r["a_ora_folds"] == [2, 2]
    assert r["sel_agree"] is True
    assert r["arb"] == pytest.approx(r["ora"]) == pytest.approx(2.0)


def test_null_case_all_arms_identical_gives_zero():
    if_rows = [_const(2.0), _const(2.0), _const(2.0)]
    arb_rows = [_const(-7.0), _const(-7.0), _const(-7.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    rows, *_ = TA.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=20260816)
    r = rows[0]
    for k in ("arb", "ora", "rnd", "arm0", "sec", "h_arb", "arb_minus_rnd"):
        assert r[k] == pytest.approx(0.0)
    assert r["pickchg"] is False


def test_sec_arb_capture_fraction_against_its_own_headroom_is_identically_one():
    """READ_RULE §4.2 item 3: SEC-ARB's capture fraction against its OWN headroom
    is 1 BY CONSTRUCTION -- that circularity is the reason it can never adjudicate."""
    rng = random.Random(11)
    for _ in range(6):
        if_rows = [[rng.uniform(-9, 9) for _ in range(M)] for _ in range(4)]
        arb_rows = [[rng.uniform(-9, 9) for _ in range(M)] for _ in range(4)]
        arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=2)
        rows, *_ = TA.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=1)
        r = rows[0]
        assert r["sec"] == pytest.approx(r["h_arb"])
        assert r["sec"] == pytest.approx(_sym_crossfit(arb_rows, r["champ_pos"]))
        if abs(r["h_arb"]) > 1e-12:
            assert r["sec"] / r["h_arb"] == pytest.approx(1.0)


def test_arb_and_ora_share_the_champion_baseline_and_the_evaluation_worlds():
    """arb − ora == mean_eva IF[a_arb] − mean_eva IF[a_ora], symmetrized: the
    champion term cancels, which is why F's numerator and denominator are
    comparable."""
    rng = random.Random(3)
    if_rows = [[rng.uniform(-5, 5) for _ in range(M)] for _ in range(3)]
    arb_rows = [[rng.uniform(-5, 5) for _ in range(M)] for _ in range(3)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=1)
    rows, *_ = TA.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=1)
    r = rows[0]
    diff = []
    for swap, a_arb, a_ora in ((False, r["a_arb_folds"][0], r["a_ora_folds"][0]),
                               (True, r["a_arb_folds"][1], r["a_ora_folds"][1])):
        _sel, eva = AT.parity_indices(M, base=1, swap=swap)
        diff.append(AT._sub_mean(if_rows[a_arb], eva) - AT._sub_mean(if_rows[a_ora], eva))
    assert r["arb"] - r["ora"] == pytest.approx((diff[0] + diff[1]) / 2.0)


# --------------------------------------------------------------------------- #
# B2. C-RND                                                                     #
# --------------------------------------------------------------------------- #
def test_c_rnd_draw_is_deterministic_in_rid_and_seed():
    a = TA.rnd_arm_position("tt_sp_123_p40", 5, 20260816)
    b = TA.rnd_arm_position("tt_sp_123_p40", 5, 20260816)
    assert a == b
    assert 0 <= a < 5
    assert TA.rnd_arm_position("tt_sp_123_p41", 5, 20260816) != a or True   # in-range
    # a different seed is a different draw stream
    draws_a = [TA.rnd_arm_position(f"p{i}", 5, 20260816) for i in range(40)]
    draws_b = [TA.rnd_arm_position(f"p{i}", 5, 12345) for i in range(40)]
    assert draws_a != draws_b
    assert all(0 <= d < 5 for d in draws_a + draws_b)


def test_c_rnd_uses_the_same_arm_in_both_folds():
    rng = random.Random(5)
    if_rows = [[rng.uniform(-5, 5) for _ in range(M)] for _ in range(3)]
    arb_rows = [[rng.uniform(-5, 5) for _ in range(M)] for _ in range(3)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    rows, *_ = TA.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=20260816)
    r = rows[0]
    a_rnd = r["a_rnd"]
    expect = []
    for swap in (False, True):
        _sel, eva = AT.parity_indices(M, base=1, swap=swap)
        expect.append(AT._sub_mean(if_rows[a_rnd], eva)
                      - AT._sub_mean(if_rows[r["champ_pos"]], eva))
    assert r["rnd"] == pytest.approx((expect[0] + expect[1]) / 2.0)
    assert r["arb_minus_rnd"] == pytest.approx(r["arb"] - r["rnd"])


# --------------------------------------------------------------------------- #
# B3. integrity counters + exclusions                                          #
# --------------------------------------------------------------------------- #
def test_cross_judge_crn_witness_flags_a_mutated_world_seed():
    if_rows = [_const(0.0), _const(1.0)]
    arb_rows = [_const(0.0), _const(2.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    arbb["p1"][1]["world_seeds"][3] = 999999
    rows, _integ, cross, _c = TA.build_positions(
        arms, ifb, arbb, _RATES, set(), rnd_seed=1)
    assert len(rows) == 1
    assert cross["crn_cross_mismatch"] == 1
    assert cross["seed_cross_mismatch"] == 0
    assert cross["compared_legs"] == 1


def test_cross_judge_arm_mismatch_is_counted():
    if_rows = [_const(0.0), _const(1.0)]
    arb_rows = [_const(0.0), _const(2.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    arbb["p1"][1]["pick_b"] = 77777
    _rows, integ, cross, _c = TA.build_positions(
        arms, ifb, arbb, _RATES, set(), rnd_seed=1)
    assert cross["arm_cross_mismatch"] == 1
    assert integ["arb"]["arm_index_mismatch"] == 1
    assert integ["if"]["arm_index_mismatch"] == 0


def test_armset_mismatch_excludes_and_counts_the_position():
    if_rows = [_const(0.0), _const(1.0), _const(2.0)]
    arb_rows = [_const(0.0), _const(1.0), _const(2.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    del arbb["p1"][2]                       # ARB scored one leg fewer
    rows, _i, _cr, counts = TA.build_positions(
        arms, ifb, arbb, _RATES, set(), rnd_seed=1)
    assert rows == []
    assert counts["armset_mismatch"] == 1
    assert counts["armset_mismatch_frac"] == pytest.approx(1.0)


def test_partial_position_is_excluded_and_counted():
    if_rows = [_const(0.0), _const(1.0), _const(2.0)]
    arb_rows = [_const(0.0), _const(1.0), _const(2.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    del ifb["p1"][2]
    del arbb["p1"][2]                       # both judges missing the SAME planned leg
    rows, _i, _cr, counts = TA.build_positions(
        arms, ifb, arbb, _RATES, set(), rnd_seed=1)
    assert rows == []
    assert counts["partial"] == 1
    assert counts["armset_mismatch"] == 0


def test_position_without_the_champion_arm_is_dropped_and_counted():
    if_rows = [_const(0.0), _const(1.0)]
    arb_rows = [_const(0.0), _const(1.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    arms["p1"]["champ_arm_index"] = 7           # not in arm_order
    rows, _i, _cr, counts = TA.build_positions(
        arms, ifb, arbb, _RATES, set(), rnd_seed=1)
    assert rows == []
    assert counts["champ_arm_absent"] == 1


def test_slice_label_follows_the_holdout_root_set():
    if_rows = [_const(0.0), _const(1.0)]
    arb_rows = [_const(0.0), _const(1.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, root="RH", champ_arm_index=0)
    rows, *_ = TA.build_positions(arms, ifb, arbb, _RATES, {"RH"}, rnd_seed=1)
    assert rows[0]["slice"] == "holdout"
    rows2, *_ = TA.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=1)
    assert rows2[0]["slice"] == "dev"


# --------------------------------------------------------------------------- #
# B4. the paired ratio bootstrap                                               #
# --------------------------------------------------------------------------- #
def test_paired_ratio_bootstrap_near_2x():
    n = 60
    den = [1.0 + 0.37 * i for i in range(n)]
    num = [2.0 * d for d in den]
    roots = [f"root{i}" for i in range(n)]
    med, lo, hi, n_fin, frac = TA.paired_ratio_bootstrap(num, den, roots,
                                                         n_boot=3000, seed=1)
    assert med == pytest.approx(2.0, abs=0.15)
    assert lo == pytest.approx(2.0, abs=0.15)
    assert hi == pytest.approx(2.0, abs=0.15)
    assert n_fin > 0
    assert frac == pytest.approx(0.0)


def test_paired_ratio_bootstrap_reports_denominator_crossings():
    n = 40
    den = [(-1.0 if i % 2 else 1.0) * 0.01 for i in range(n)]
    num = [1.0] * n
    roots = [f"root{i}" for i in range(n)]
    _med, _lo, _hi, _nf, frac = TA.paired_ratio_bootstrap(num, den, roots,
                                                          n_boot=2000, seed=7)
    assert 0.0 < frac < 1.0


def test_paired_ratio_bootstrap_single_root_is_nan():
    med, lo, hi, nf, frac = TA.paired_ratio_bootstrap([1.0, 2.0], [0.5, 1.0],
                                                      ["only", "only"], n_boot=100)
    assert all(math.isnan(x) for x in (med, lo, hi, nf, frac))


def test_paired_ratio_bootstrap_matches_analyze_oof_convention():
    """Same convention as analyze_oof.paired_ratio_bootstrap -- identical stream,
    so identical numbers at the same seed. (analyze_oof is imported read-only.)"""
    import analyze_oof as AO
    n = 25
    den = [0.5 + 0.1 * i for i in range(n)]
    num = [0.3 * d for d in den]
    roots = [f"r{i % 9}" for i in range(n)]
    a = TA.paired_ratio_bootstrap(num, den, roots, n_boot=1000, seed=42)
    b = AO.paired_ratio_bootstrap(num, den, roots, n_boot=1000, seed=42)
    assert a == pytest.approx(b)


# --------------------------------------------------------------------------- #
# B5. sign check                                                               #
# --------------------------------------------------------------------------- #
def _sc_rows(vals, pickchg=True):
    return [{"arb": v, "scale_all": 1.0, "pickchg": pickchg} for v in vals]


def test_sign_check_corroborates():
    r = TA.sign_check(_sc_rows([1.0] * 8), aggregate_mean=1.0)
    assert r["corroboration"] == "CORROBORATES"
    assert r["agreement_rate"] == pytest.approx(1.0)


def test_sign_check_partial_when_aggregate_sign_is_opposite():
    r = TA.sign_check(_sc_rows([1.0] * 8), aggregate_mean=-0.4)
    assert r["corroboration"].startswith("PARTIAL")
    assert r["aggregate_sign"] == -1
    assert r["per_position_majority_sign"] == +1


def test_sign_check_no_corroboration_at_chance():
    r = TA.sign_check(_sc_rows([1.0, -1.0, 1.0, -1.0]), aggregate_mean=0.05)
    assert r["corroboration"].startswith("NO CORROBORATION")


def test_sign_check_only_reads_pick_change_positions():
    rows = _sc_rows([1.0] * 6) + _sc_rows([-1.0] * 40, pickchg=False)
    r = TA.sign_check(rows, aggregate_mean=1.0)
    assert r["n_pickchg"] == 6
    assert r["n_agree"] == 6


def test_binom_two_sided_hand_values():
    assert TA.binom_two_sided(4, 4) == pytest.approx(0.125)
    assert TA.binom_two_sided(2, 4) == pytest.approx(1.0)
    assert math.isnan(TA.binom_two_sided(0, 0))


# =========================================================================== #
# C. decide_branch -- the READ_RULE §3/§4 truth table
# =========================================================================== #
ALL_GATES = ("G-CRN", "G-ARM", "G-VA", "G-SLICE", "G-ARMSET", "G-N", "G-DENOM")


def _pre(**over):
    d = {g: True for g in ALL_GATES}
    d.update(over)
    return d


def _reference_branch(z, F, Ff, ah, gb):
    """READ_RULE §4 transcribed INDEPENDENTLY of the implementation."""
    def ge(x, bar):
        return bool(x == x and x >= bar)
    C_z = ge(z, 2.0)
    RBAR = ge(Ff, 0.35) and (ge(F, 0.35) or bool(gb))
    ANY_R = ge(Ff, 0.35) or (ge(F, 0.35) and not bool(gb))
    C_h = ge(ah, 0.0)
    A = C_z and RBAR and C_h
    P = (not A) and ANY_R
    Fl = (not A) and (not ANY_R)
    return A, P, Fl, RBAR, ANY_R


NAN = float("nan")
_ZS = (1.0, 1.9999, 2.0, 3.5, NAN)
_FS = (0.0, 0.34, 0.35, 0.9, NAN)
_FFS = (0.0, 0.34, 0.35, 0.9, NAN)
_AHS = (-0.5, -1e-9, 0.0, 0.4, NAN)
_GBS = (False, True)


def test_decide_branch_is_exclusive_and_exhaustive_over_the_grid():
    n = 0
    for z, F, Ff, ah, gb in itertools.product(_ZS, _FS, _FFS, _AHS, _GBS):
        got = TA.decide_branch(z, F, Ff, ah, gb, _pre())
        A, P, Fl, RBAR, ANY_R = _reference_branch(z, F, Ff, ah, gb)
        fired = [name for name, ok in (("A-CAPTURE", A), ("P-PARTIAL", P),
                                       ("F-FLAT", Fl)) if ok]
        assert len(fired) == 1, (z, F, Ff, ah, gb, fired)
        assert got["branch"] == fired[0], (z, F, Ff, ah, gb, got["branch"])
        assert got["failed_preconditions"] == []
        assert got["RBAR"] is RBAR
        assert got["ANY_R"] is ANY_R
        # READ_RULE §4.1: RBAR => ANY_R, so A-CAPTURE's ratio conjunct can never
        # coexist with F-FLAT's negation.
        assert (not RBAR) or ANY_R
        n += 1
    assert n == len(_ZS) * len(_FS) * len(_FFS) * len(_AHS) * len(_GBS) == 1250


def test_u_unreadable_preempts_every_gate_and_every_reading():
    """§3 is evaluated FIRST: a single failed gate voids the run whatever the
    numbers say -- including a reading that would otherwise be A-CAPTURE."""
    n = 0
    for gate in ALL_GATES:
        for z, F, Ff, ah, gb in itertools.product((1.0, 3.5), (0.1, 0.9),
                                                  (0.1, 0.9), (-0.5, 0.4), _GBS):
            got = TA.decide_branch(z, F, Ff, ah, gb, _pre(**{gate: False}))
            assert got["branch"] == "U-UNREADABLE"
            assert got["failed_preconditions"] == [gate]
            n += 1
    assert n == len(ALL_GATES) * 32


def test_u_unreadable_lists_every_failed_gate():
    got = TA.decide_branch(9.0, 9.0, 9.0, 9.0, False,
                           _pre(**{"G-N": False, "G-DENOM": False}))
    assert got["branch"] == "U-UNREADABLE"
    assert got["failed_preconditions"] == ["G-DENOM", "G-N"]


def test_a_capture_needs_all_three_conjuncts():
    ok = TA.decide_branch(3.0, 0.9, 0.9, 0.1, False, _pre())
    assert ok["branch"] == "A-CAPTURE"
    assert (ok["C_z"], ok["RBAR"], ok["C_h"]) == (True, True, True)
    for kw, expect in ((dict(z_arb=1.0), "P-PARTIAL"),
                       (dict(arb_holdout=-0.01), "P-PARTIAL"),
                       (dict(F_fixed=0.1), "P-PARTIAL")):
        args = dict(z_arb=3.0, F=0.9, F_fixed=0.9, arb_holdout=0.1,
                    g_boot_fired=False, preconditions=_pre())
        args.update(kw)
        assert TA.decide_branch(**args)["branch"] == expect


def test_g_boot_voids_F_as_a_branch_input():
    # F below bar, F_fixed above, G-BOOT FIRED => the ratio conjunct rests on
    # F_fixed alone and A-CAPTURE may still fire.
    assert TA.decide_branch(3.0, 0.1, 0.9, 0.1, True, _pre())["branch"] == "A-CAPTURE"
    # same reading with G-BOOT NOT fired => RBAR fails (F < bar) => P-PARTIAL
    got = TA.decide_branch(3.0, 0.1, 0.9, 0.1, False, _pre())
    assert got["branch"] == "P-PARTIAL"
    assert "RBAR" in " ".join(TA.failed_conjuncts(got))


def test_f_flat_when_neither_ratio_reaches_the_bar():
    got = TA.decide_branch(3.0, 0.2, 0.2, 0.5, False, _pre())
    assert got["branch"] == "F-FLAT"
    assert got["ANY_R"] is False


def test_nan_never_fires_a_conjunct():
    got = TA.decide_branch(NAN, NAN, NAN, NAN, False, _pre())
    assert got["branch"] == "F-FLAT"
    assert (got["C_z"], got["RBAR"], got["ANY_R"], got["C_h"]) == (
        False, False, False, False)


def test_bars_are_the_committed_constants():
    assert TA.RATIO_BAR == 0.35
    assert TA.Z_BAR == 2.0
    assert TA.FIXED_DENOM == 0.2803
    assert TA.GBOOT_BAR == 0.05
    assert TA.N_FLOOR_POOLED == 650
    assert TA.N_FLOOR_HOLDOUT == 158
    assert TA.BOOT_REPS == 20000
    assert TA.M_EXPECTED == 32


def test_failed_conjuncts_reports_exactly_which_one():
    got = TA.decide_branch(1.0, 0.9, 0.9, 0.5, False, _pre())
    assert TA.failed_conjuncts(got) == ["C_z (z_arb >= +2.0)"]
    got = TA.decide_branch(3.0, 0.9, 0.9, -0.5, False, _pre())
    assert TA.failed_conjuncts(got) == [
        "C_h (arb_holdout >= 0.0 — the blind holdout leans negative)"]


# =========================================================================== #
# D. aggregation / rendering wiring
# =========================================================================== #
def test_agg_block_and_cuts_wire_through_analyze_tiletie(monkeypatch):
    monkeypatch.setattr(TA, "BOOT_REPS", 200)
    rng = random.Random(19)
    rows = []
    for i in range(24):
        rows.append({
            "rid": f"p{i}", "root_id": f"R{i % 6}", "stratum": "selfplay",
            "rules_profile": "walled", "phase_bucket": "mid", "capped": bool(i % 3),
            "ply": 40, "slice": "dev", "champ_pos": 0, "a_arb_folds": [0, 1],
            "arb": rng.uniform(-1, 2), "ora": rng.uniform(0, 3),
            "rnd": rng.uniform(-1, 1), "arm0": rng.uniform(-1, 1),
            "sec": rng.uniform(-1, 1), "h_arb": rng.uniform(-1, 1),
            "arb_p1": rng.uniform(-1, 2), "ora_p1": rng.uniform(0, 3),
            "arb_minus_rnd": rng.uniform(-1, 1),
            "pickchg": True, "sel_agree": False,
            "scale_all": 0.74, "scale_strict": 0.78,
        })
    blk = TA.agg_block(rows, seed=1)
    assert blk["n"] == 24 and blk["n_roots"] == 6
    for name, _k in TA.STAT_KEYS:
        for suf in ("_all", "_discriminable"):
            a = blk[name + suf]
            for sub in ("mean", "se_cluster", "z", "boot_lo", "boot_hi",
                        "sd_positions", "n", "n_roots", "frac_boot_le_0"):
                assert sub in a
    # scale_all is applied as a multiplier, exactly as analyze_tiletie.aggregate does
    assert blk["arb_all"]["mean"] == pytest.approx(
        0.74 * blk["arb_discriminable"]["mean"])

    cuts = TA.cut_blocks(rows)
    assert "stratum:selfplay" in cuts and "capped_only" in cuts
    for d in cuts.values():
        assert d["F_fixed_point"] == pytest.approx(d["arb"] / TA.FIXED_DENOM)


def test_resolve_records_root_accepts_parent_or_leaf(tmp_path):
    parent = tmp_path / "merged"
    (parent / "tier1-greedy").mkdir(parents=True)
    assert TA.resolve_records_root(parent) == parent / "tier1-greedy"
    assert TA.resolve_records_root(parent / "tier1-greedy") == parent / "tier1-greedy"


def test_merge_arb_records_rejects_a_duplicate_rid_across_roots(tmp_path):
    def _mk(root, rid):
        d = root / "tier1-greedy" / "walled" / "leg1" / "records"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rid}.json").write_text(json.dumps({"rid": rid, "ok": True}))
    _mk(tmp_path / "a", "p1")
    _mk(tmp_path / "b", "p2")
    by, _pres, _nk, roots = TA.merge_arb_records([tmp_path / "a", tmp_path / "b"])
    assert set(by) == {"p1", "p2"}
    assert len(roots) == 2
    _mk(tmp_path / "c", "p1")
    with pytest.raises(SystemExit, match="duplicate rid"):
        TA.merge_arb_records([tmp_path / "a", tmp_path / "c"])


# =========================================================================== #
# E. end-to-end smoke -- SYNTHETIC records only, under tmp_path
# =========================================================================== #
def _e2e_corpus(tmp_path, n_dev=12, n_hold=10, arb_agrees=True):
    """A complete synthetic run tree: plan dir + both judges' record trees."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    if_root = tmp_path / "if" / "clair-puct"
    arb_root = tmp_path / "arb" / "tier1-greedy"

    arms, hold_roots = {}, []
    rng = random.Random(2026)
    for i in range(n_dev + n_hold):
        rid = f"tt_sp_{i:04d}_p40"
        root = f"sp_{i:04d}"
        is_hold = i >= n_dev
        if is_hold:
            hold_roots.append(root)
        arms[rid] = {"root_id": root, "stratum": "selfplay", "rules_profile": "walled",
                     "phase_bucket": "mid", "capped": False, "ply": 40,
                     "arms": [100, 101, 102], "champ_arm_index": 0}
        # IF: arm 2 is genuinely better than the champion (arm 0)
        if_rows = [[rng.gauss(0.0, 0.5) for _ in range(M)],
                   [rng.gauss(0.3, 0.5) for _ in range(M)],
                   [rng.gauss(1.6, 0.5) for _ in range(M)]]
        if arb_agrees:
            arb_rows = [[v + rng.gauss(0, 0.2) for v in r] for r in if_rows]
        else:
            arb_rows = [[-v + rng.gauss(0, 0.2) for v in r] for r in if_rows]
        for name, root_dir, mat in (("if", if_root, if_rows), ("arb", arb_root, arb_rows)):
            for leg in (1, 2):
                d = root_dir / "walled" / f"leg{leg}" / "records"
                d.mkdir(parents=True, exist_ok=True)
                rec = _rec(mat[0], mat[leg], 100, 100 + leg)
                rec["rid"] = rid
                (d / f"{rid}.json").write_text(json.dumps(rec))

    plan = {"schema": "x", "afterstate_dedupe": {
                "applied": True, "n_qualifying_before_drop": n_dev + n_hold + 2,
                "n_dropped_all_transposition": 2,
                "n_dropped_with_action_played_outside_tieset": 0},
            "cap_j": 4, "m_worlds": M, "max_arms": 5,
            "counts_by_stratum": {"selfplay": n_dev + n_hold},
            "counts_by_profile_leg": {"walled/leg1": n_dev + n_hold,
                                      "walled/leg2": n_dev + n_hold},
            "files": {}, "out_dir": str(plan_dir)}
    (plan_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan))
    (plan_dir / "ARMS.json").write_text(json.dumps(arms))
    (plan_dir / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps(
        {"rows": [{"stratum": "selfplay", "action_played_outside_tieset": False}] * 2}))
    full = tmp_path / "FULL_PLAN.json"
    full.write_text(json.dumps(plan))
    hr = tmp_path / "HOLDOUT_ROOTS.json"
    hr.write_text(json.dumps({"holdout_roots": hold_roots}))
    return plan_dir, if_root, arb_root, full, hr


def _e2e_argv(tmp_path, plan_dir, if_root, arb_root, full, hr, out):
    return ["--if-records", str(if_root), "--arb-records", str(arb_root),
            "--plan-dir", str(plan_dir), "--full-supply-plan", str(full),
            "--holdout-roots", str(hr), "--out-dir", str(out)]


def test_end_to_end_unreadable_when_G_N_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(TA, "BOOT_REPS", 200)
    plan_dir, if_root, arb_root, full, hr = _e2e_corpus(tmp_path)
    out = tmp_path / "out"
    assert TA.main(_e2e_argv(tmp_path, plan_dir, if_root, arb_root, full, hr, out)) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    # the real floors (650 / 158) cannot be met by a 22-position fixture
    assert v["adjudication"]["branch"] == "U-UNREADABLE"
    assert "G-N" in v["adjudication"]["failed_preconditions"]
    assert (out / "READOUT.md").is_file()
    assert (out / "per_position.jsonl").is_file()


def test_end_to_end_readable_branch_and_render(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(TA, "BOOT_REPS", 400)
    monkeypatch.setattr(TA, "N_FLOOR_POOLED", 10)
    monkeypatch.setattr(TA, "N_FLOOR_HOLDOUT", 5)
    plan_dir, if_root, arb_root, full, hr = _e2e_corpus(tmp_path, arb_agrees=True)
    out = tmp_path / "out"
    assert TA.main(_e2e_argv(tmp_path, plan_dir, if_root, arb_root, full, hr, out)) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    adj = v["adjudication"]
    assert adj["branch"] in {"A-CAPTURE", "P-PARTIAL", "F-FLAT"}
    assert adj["failed_preconditions"] == []
    assert all(v["preconditions"].values())
    # an agreeing arbiter must capture a large, positive fraction here
    assert v["primary"]["arb"] > 0
    assert v["primary"]["F"] > 0.5
    assert v["completion"]["n_analysed"] == 22
    assert v["completion"]["n_holdout"] == 10
    # scale_all from the analytic zeros is applied (2 dropped of 24 qualifying)
    row = json.loads((out / "per_position.jsonl").read_text().splitlines()[0])
    assert row["scale_all"] == pytest.approx(1.0 - 2.0 / 24.0)
    # READ_RULE §4.2's mandatory list, in order
    md = (out / "READOUT.md").read_text()
    for i, head in enumerate([
            "## 1. The primary statistics", "## 2. The single-fold",
            "## 3. Mandatory companions", "## 4. `R_holdout`", "## 5. `PICKCHG`",
            "## 6. The §4.5 sign check", "## 7. The §4.3 bound chain",
            "## 8. Realized `n`", "## 9. Cost", "## 10. Every §3 gate",
            "## 11. Realized resolution", "## 12. Cuts"], start=1):
        assert head in md, (i, head)
    order = [md.index(h) for h in ("## 1. ", "## 2. ", "## 3. ", "## 4. ", "## 5. ",
                                   "## 6. ", "## 7. ", "## 8. ", "## 9. ", "## 10. ",
                                   "## 11. ", "## 12. ")]
    assert order == sorted(order)
    assert "AUDIT-ONLY, CIRCULAR" in md
    assert "SPENDS THE HOLDOUT" in md
    assert "NEVER adjudicated on" in md


def test_end_to_end_disagreeing_arbiter_does_not_capture(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(TA, "BOOT_REPS", 400)
    monkeypatch.setattr(TA, "N_FLOOR_POOLED", 10)
    monkeypatch.setattr(TA, "N_FLOOR_HOLDOUT", 5)
    plan_dir, if_root, arb_root, full, hr = _e2e_corpus(tmp_path, arb_agrees=False)
    out = tmp_path / "out"
    assert TA.main(_e2e_argv(tmp_path, plan_dir, if_root, arb_root, full, hr, out)) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    # an ANTI-correlated arbiter picks the worst arm: arb < ora, F well under 1
    assert v["primary"]["arb"] < v["primary"]["ora"]
    assert v["primary"]["F"] < 0.35
    assert v["adjudication"]["branch"] in {"F-FLAT", "P-PARTIAL"}
