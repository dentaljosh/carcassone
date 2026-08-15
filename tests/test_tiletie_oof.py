"""Contract tests for the OUT-OF-FAMILY re-pricing plan + read-out instruments
(scripts/tiletie/build_oof_plan.py, scripts/tiletie/analyze_oof.py;
measurement/tiletie_oof_20260814/).

Pure plan/stat surgery -- no engine import, no search, no share writes. All
plan-dir / records-tree fixtures live under tmp_path."""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import analyze_oof as AO  # noqa: E402
import build_oof_plan as BP  # noqa: E402


# =========================================================================== #
# A. build_oof_plan.py
# =========================================================================== #

# --------------------------------------------------------------------------- #
# A1. committed_order                                                          #
# --------------------------------------------------------------------------- #
def test_committed_order_deterministic_partition():
    rids = [f"r{i:03d}" for i in range(50)]
    main1, pilot1 = BP.committed_order(rids, pilot_n=10, seed=123)
    main2, pilot2 = BP.committed_order(rids, pilot_n=10, seed=123)
    assert main1 == main2 and pilot1 == pilot2
    assert len(pilot1) == 10
    assert set(main1) | set(pilot1) == set(rids)
    assert not (set(main1) & set(pilot1))
    assert len(main1) + len(pilot1) == len(rids)


def test_committed_order_zero_pilot_keeps_everything_in_main():
    rids = [f"r{i:03d}" for i in range(12)]
    main, pilot = BP.committed_order(rids, pilot_n=0, seed=7)
    assert pilot == []
    assert set(main) == set(rids)
    assert len(main) == len(rids)


# --------------------------------------------------------------------------- #
# A2. chunk_slices                                                             #
# --------------------------------------------------------------------------- #
def test_chunk_slices_partition_preserves_order_balanced():
    order = list(range(23))
    chunks = BP.chunk_slices(order, 4)
    assert sum(chunks, []) == order
    sizes = [len(c) for c in chunks]
    assert max(sizes) - min(sizes) <= 1
    assert sum(sizes) == len(order)


def test_chunk_slices_k1_returns_whole():
    order = list(range(7))
    chunks = BP.chunk_slices(order, 1)
    assert chunks == [order]


# --------------------------------------------------------------------------- #
# A3. dev_rids                                                                 #
# --------------------------------------------------------------------------- #
def test_dev_rids_excludes_holdout_roots():
    arms = {
        "a": {"root_id": "R1"}, "b": {"root_id": "R2"},
        "c": {"root_id": "R1"}, "d": {"root_id": "R3"},
    }
    holdout = {"R2"}
    assert BP.dev_rids(arms, holdout) == ["a", "c", "d"]


# --------------------------------------------------------------------------- #
# A4. write_plan_dir -- G-HOLDOUT / G-PILOT gates                              #
# --------------------------------------------------------------------------- #
def _mini_arms():
    return {
        "p1": {"root_id": "R1", "stratum": "selfplay", "arms": [10, 11]},
        "p2": {"root_id": "R2", "stratum": "selfplay", "arms": [10, 11]},
        "p3": {"root_id": "R3", "stratum": "e4", "arms": [10, 11]},
    }


def test_write_plan_dir_raises_on_holdout_violation(tmp_path):
    arms = _mini_arms()
    with pytest.raises(SystemExit):
        BP.write_plan_dir(
            tmp_path / "out", {"p2"}, source_plan={}, source_arms=arms,
            dropped={}, leg_rows={}, label="test", holdout={"R2"})


def test_write_plan_dir_raises_on_pilot_violation(tmp_path):
    arms = _mini_arms()
    with pytest.raises(SystemExit):
        BP.write_plan_dir(
            tmp_path / "out", {"p1"}, source_plan={}, source_arms=arms,
            dropped={}, leg_rows={}, label="test", holdout=set(),
            forbidden={"p1"})


# --------------------------------------------------------------------------- #
# A5. write_plan_dir -- round trip                                            #
# --------------------------------------------------------------------------- #
def _build_source_fixture(tmp_path):
    """A tiny 4-position, 2-leg-file source plan on disk (run_tiletie shape)."""
    src = tmp_path / "source"
    src.mkdir()
    arms = {
        "p1": {"root_id": "R1", "stratum": "selfplay", "rules_profile": "walled",
               "phase_bucket": "mid", "arms": [10, 11, 12], "capped": False},
        "p2": {"root_id": "R1", "stratum": "selfplay", "rules_profile": "walled",
               "phase_bucket": "mid", "arms": [10, 11], "capped": False},
        "p3": {"root_id": "R2", "stratum": "e4", "rules_profile": "open",
               "phase_bucket": "late", "arms": [10, 11, 12, 13], "capped": True},
        "p4": {"root_id": "R3", "stratum": "e4", "rules_profile": "open",
               "phase_bucket": "early", "arms": [10, 11], "capped": False},
    }
    leg1_lines = [json.dumps({"rid": r}) for r in ("p1", "p2", "p3", "p4")]
    leg2_lines = [json.dumps({"rid": r}) for r in ("p1", "p3")]
    (src / "positions_walled_leg1.jsonl").write_text(
        "".join(ln + "\n" for ln in leg1_lines))
    (src / "positions_walled_leg2.jsonl").write_text(
        "".join(ln + "\n" for ln in leg2_lines))
    plan = {
        "afterstate_dedupe": {"applied": True, "n_qualifying_before_drop": 4,
                               "n_dropped_all_transposition": 0},
        "cap_j": 4, "m_worlds": 8, "max_arms": 4, "out_dir": str(src),
        "files": {
            "walled/leg1": {"n": 4, "path": str(src / "positions_walled_leg1.jsonl")},
            "walled/leg2": {"n": 2, "path": str(src / "positions_walled_leg2.jsonl")},
        },
    }
    dropped = {"rows": []}
    return src, plan, arms, dropped


def test_write_plan_dir_round_trip(tmp_path):
    src, plan, arms, dropped = _build_source_fixture(tmp_path)
    leg_rows = BP.read_leg_files(src, plan)
    keep = {"p1", "p2", "p3"}
    out_dir = tmp_path / "out_main"
    BP.write_plan_dir(out_dir, keep, source_plan=plan, source_arms=arms,
                       dropped=dropped, leg_rows=leg_rows, label="main",
                       holdout=set())

    plan_out = json.loads((out_dir / "POSITIONS_PLAN.json").read_text())
    arms_out = json.loads((out_dir / "ARMS.json").read_text())

    assert plan_out["afterstate_dedupe"]["applied"] is True

    total_lines = 0
    assert plan_out["files"]     # non-empty
    for key, info in plan_out["files"].items():
        p = Path(info["path"])
        lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
        assert info["n"] == len(lines)
        total_lines += len(lines)
        for line in lines:
            rid = json.loads(line)["rid"]
            assert rid in arms_out

    assert plan_out["total_legs"] == total_lines
    assert plan_out["total_arm_playouts"] == (
        plan_out["total_legs"] * 2 * int(plan["m_worlds"]))


# --------------------------------------------------------------------------- #
# A6. stage_if_records                                                        #
# --------------------------------------------------------------------------- #
def test_stage_if_records_copies_only_keep(tmp_path):
    src_root = tmp_path / "if_records"
    for prof, leg, rid in (
            ("walled", 1, "p1"), ("walled", 1, "p2"), ("walled", 2, "p1"),
            ("open", 1, "p3"), ("open", 1, "p4")):
        d = src_root / prof / f"leg{leg}" / "records"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rid}.json").write_text(json.dumps({"rid": rid, "ok": True}))

    dst_root = tmp_path / "if_dev"
    keep = {"p1", "p3"}
    result = BP.stage_if_records(src_root, dst_root, keep)

    assert result["copied"] == 3                   # p1 leg1, p1 leg2, p3 leg1
    assert result["skipped_not_in_slice"] == 2      # p2, p4

    copied_stems = {p.stem for p in dst_root.glob("*/leg*/records/*.json")}
    assert copied_stems == {"p1", "p3"}
    assert not (copied_stems - keep)                # no out-of-slice file in dst


# =========================================================================== #
# B. analyze_oof.py
# =========================================================================== #

# --------------------------------------------------------------------------- #
# B7. binom_two_sided                                                          #
# --------------------------------------------------------------------------- #
def test_binom_two_sided_hand_values():
    assert AO.binom_two_sided(4, 4) == pytest.approx(0.125)
    assert AO.binom_two_sided(2, 4) == pytest.approx(1.0)
    assert math.isnan(AO.binom_two_sided(0, 0))


def test_binom_two_sided_full_agreement_formula():
    for n in (1, 2, 3, 4, 5, 8):
        assert AO.binom_two_sided(n, n) == pytest.approx(2.0 * (2.0 ** (-n)))


# --------------------------------------------------------------------------- #
# B8. paired_ratio_bootstrap                                                   #
# --------------------------------------------------------------------------- #
def test_paired_ratio_bootstrap_near_2x():
    n = 60
    den = [1.0 + 0.37 * i for i in range(n)]
    num = [2.0 * d for d in den]
    roots = [f"root{i}" for i in range(n)]
    med, lo, hi, n_fin, frac_den_le_0 = AO.paired_ratio_bootstrap(
        num, den, roots, n_boot=3000, seed=1)
    assert med == pytest.approx(2.0, abs=0.15)
    assert lo == pytest.approx(2.0, abs=0.15)
    assert hi == pytest.approx(2.0, abs=0.15)
    assert n_fin > 0
    assert frac_den_le_0 == pytest.approx(0.0)     # den is strictly positive here


def test_paired_ratio_bootstrap_single_root_nan():
    med, lo, hi, n_fin, frac_den_le_0 = AO.paired_ratio_bootstrap(
        [1.0, 2.0], [0.5, 1.0], ["only_root", "only_root"])
    assert math.isnan(med) and math.isnan(lo) and math.isnan(hi) and math.isnan(n_fin)
    assert math.isnan(frac_den_le_0)


# --------------------------------------------------------------------------- #
# B9. g_cal                                                                     #
# --------------------------------------------------------------------------- #
def _gcal_records(n_roots, oof_sign):
    """`n_roots` single-leg positions on an M=8 world layout.

    IF selection-half delta (parity_base=1 => sel=[1,3,5,7]) grows 1..n_roots
    (a clean ordering for the quantile threshold). OOF evaluation-half delta
    (eva=[0,2,4,6]) is `oof_sign`-signed with mild per-root variation so the
    cluster-robust se is nonzero and z is well-defined.
    """
    sel = [1, 3, 5, 7]
    eva = [0, 2, 4, 6]
    if_recs, oof_recs, arms = {}, {}, {}
    for i in range(n_roots):
        rid = f"p{i}"
        d_if = float(i + 1)
        d_oof = oof_sign * (4.0 + (i % 5) * 0.3)
        va = [0.0] * 8
        vb_if = [0.0] * 8
        for j in sel:
            vb_if[j] = d_if
        vb_oof = [0.0] * 8
        for j in eva:
            vb_oof[j] = d_oof
        if_recs[rid] = {1: {"ok": True, "values_a": list(va), "values_b": vb_if,
                             "pick_a": 100, "pick_b": 101}}
        oof_recs[rid] = {1: {"ok": True, "values_a": list(va), "values_b": vb_oof,
                              "pick_a": 100, "pick_b": 101}}
        arms[rid] = {"root_id": f"root{i}"}
    return if_recs, oof_recs, arms


def test_g_cal_aligned_sign_passes():
    if_recs, oof_recs, arms = _gcal_records(20, oof_sign=1.0)
    r = AO.g_cal(if_recs, oof_recs, arms, m=8)
    assert r["ok"] is True
    assert r["pass"] is True
    assert r["z"] > 2.0


def test_g_cal_flipped_sign_fails():
    if_recs, oof_recs, arms = _gcal_records(20, oof_sign=-1.0)
    r = AO.g_cal(if_recs, oof_recs, arms, m=8)
    assert r["ok"] is True
    assert r["pass"] is False


# --------------------------------------------------------------------------- #
# B10. crn_identity                                                            #
# --------------------------------------------------------------------------- #
def _crn_rec(world_seeds, pick_a=100, pick_b=101):
    return {"world_seeds": world_seeds, "playout_seeds": [1, 2, 3],
            "pick_a": pick_a, "pick_b": pick_b, "crn_verified": True,
            "checksum_ok": True}


def test_crn_identity_matching_seeds_ok():
    if_recs = {"p1": {1: _crn_rec([1, 2, 3])}, "p2": {1: _crn_rec([4, 5, 6])}}
    oof_recs = {"p1": {1: _crn_rec([1, 2, 3])}, "p2": {1: _crn_rec([4, 5, 6])}}
    out = AO.crn_identity(if_recs, oof_recs)
    assert out["ok"] is True
    for k in ("world_seed_mismatch", "playout_seed_mismatch", "crn_unverified",
              "checksum_failed", "arm_mismatch"):
        assert out[k] == 0
    assert out["compared_legs"] == 2


def test_crn_identity_mutated_world_seed_detected():
    if_recs = {"p1": {1: _crn_rec([1, 2, 3])}, "p2": {1: _crn_rec([4, 5, 6])}}
    oof_recs = {"p1": {1: _crn_rec([1, 2, 999])}, "p2": {1: _crn_rec([4, 5, 6])}}
    out = AO.crn_identity(if_recs, oof_recs)
    assert out["world_seed_mismatch"] == 1
    assert out["ok"] is False


# --------------------------------------------------------------------------- #
# B11. sign_check                                                              #
# --------------------------------------------------------------------------- #
def _sc_row(v, s=1.0):
    return {"headroom_champ": v, "scale_all": s}


def test_sign_check_corroborates():
    # all 6 shared positions agree in sign; both aggregate means positive.
    if_rows = {f"p{i}": _sc_row(1.0) for i in range(6)}
    oof_rows = {f"p{i}": _sc_row(1.0) for i in range(6)}
    r = AO.sign_check(if_rows, oof_rows, "headroom_champ", "scale_all")
    assert r["corroboration"].startswith("CORROBORATES")


def test_sign_check_partial_secondary_negative_aggregate():
    # 9/10 positions agree in sign (small, positive both), the 10th has a huge
    # OOF-only negative outlier that flips the OOF aggregate mean negative
    # while the IF aggregate stays positive -- per-position agreement stays
    # above chance and significant, but the secondary's own sign disagrees.
    if_rows = {f"p{i}": _sc_row(1.0) for i in range(10)}
    oof_rows = {f"p{i}": _sc_row(1.0) for i in range(9)}
    oof_rows["p9"] = _sc_row(-100.0)
    r = AO.sign_check(if_rows, oof_rows, "headroom_champ", "scale_all")
    assert r["agreement_rate"] > 0.5
    assert r["binomial_p_two_sided"] < 0.05
    assert r["primary_mean_sign_only"] != r["secondary_mean_sign_only"]
    assert r["corroboration"].startswith("PARTIAL")


def test_sign_check_no_corroboration_at_chance():
    if_rows = {"p1": _sc_row(1.0), "p2": _sc_row(1.0),
               "p3": _sc_row(1.0), "p4": _sc_row(-1.0)}
    oof_rows = {"p1": _sc_row(1.0), "p2": _sc_row(1.0),
                "p3": _sc_row(-1.0), "p4": _sc_row(1.0)}
    r = AO.sign_check(if_rows, oof_rows, "headroom_champ", "scale_all")
    assert r["corroboration"].startswith("NO CORROBORATION")


# --------------------------------------------------------------------------- #
# B12. adjudicate -- the read-rule table                                       #
# --------------------------------------------------------------------------- #
def _v(**kw):
    base = {
        "preconditions": {"G-N": True, "G-DENOM": True},
        "z_OOF": 0.0, "R": 0.0, "R_lo": 0.0, "R_hi": 0.0, "R_norm": 0.0,
        "z_swap_OOF": 0.0, "g_cal": {"pass": True},
    }
    base.update(kw)
    return base


def test_adjudicate_unreadable_on_any_failed_precondition():
    # a failed precondition short-circuits BEFORE any other key is even read.
    v = {"preconditions": {"G-N": False}}
    r = AO.adjudicate(v)
    assert r["branch"] == "U-UNREADABLE"


def test_adjudicate_c_confirm():
    v = _v(z_OOF=3.0, R=0.8, R_norm=0.8, z_swap_OOF=1.5, R_lo=0.4, R_hi=1.2,
           g_cal={"pass": True})
    assert AO.adjudicate(v)["branch"] == "C-CONFIRM"


def test_adjudicate_c_confirm_needs_positive_zswap():
    v = _v(z_OOF=3.0, R=0.8, R_norm=0.8, z_swap_OOF=-0.5, R_lo=0.4, R_hi=1.2,
           g_cal={"pass": True})
    assert AO.adjudicate(v)["branch"] == "B-PARTIAL"


def test_adjudicate_x_collapse():
    v = _v(z_OOF=0.5, R=0.05, R_norm=0.05, R_hi=0.3, R_lo=-0.2, g_cal={"pass": True})
    assert AO.adjudicate(v)["branch"] == "X-COLLAPSE"


def test_adjudicate_x_collapse_becomes_p_blind_when_gcal_fails():
    v = _v(z_OOF=0.5, R=0.05, R_norm=0.05, R_hi=0.3, R_lo=-0.2, g_cal={"pass": False})
    assert AO.adjudicate(v)["branch"] == "P-BLIND"


def test_adjudicate_p_blind():
    v = _v(z_OOF=1.0, R=0.6, R_norm=0.6, R_hi=1.4, R_lo=-0.3, z_swap_OOF=1.0,
           g_cal={"pass": True})
    assert AO.adjudicate(v)["branch"] == "P-BLIND"


def test_adjudicate_b_partial():
    v = _v(z_OOF=1.0, R=0.6, R_norm=0.6, R_hi=1.4, R_lo=0.2, z_swap_OOF=1.0,
           g_cal={"pass": True})
    assert AO.adjudicate(v)["branch"] == "B-PARTIAL"


def test_adjudicate_exhaustive_and_exclusive_over_grid():
    """Sweep the full branch grid: every combination lands in exactly one of
    the four readable branches, and adjudicate never raises."""
    valid_branches = {"C-CONFIRM", "X-COLLAPSE", "P-BLIND", "B-PARTIAL"}
    zs = (0.5, 1.0, 2.5)
    rs = (0.1, 0.6)
    r_norms = (0.1, 0.6)
    r_los = (-0.2, 0.2)
    r_his = (0.3, 1.4)
    zsws = (-1.0, 1.0)
    cals = (True, False)
    n_checked = 0
    for z, R, Rn, R_lo, R_hi, zsw, cal in itertools.product(
            zs, rs, r_norms, r_los, r_his, zsws, cals):
        if R_lo > R_hi:
            continue
        v = _v(z_OOF=z, R=R, R_norm=Rn, R_lo=R_lo, R_hi=R_hi,
               z_swap_OOF=zsw, g_cal={"pass": cal})
        result = AO.adjudicate(v)
        assert result["branch"] in valid_branches
        n_checked += 1
    assert n_checked > 0


# --------------------------------------------------------------------------- #
# B13. stat_block                                                              #
# --------------------------------------------------------------------------- #
def test_stat_block_returns_expected_keys(monkeypatch):
    # stat_block reads the MODULE constant BOOT_REPS at call time, so
    # monkeypatching it before the call takes effect (no default-arg binding).
    monkeypatch.setattr(AO, "BOOT_REPS", 200)

    roots = ["R1", "R2", "R3", "R4"]
    rows = {}
    for i in range(12):
        rid = f"p{i}"
        rows[rid] = {
            "rid": rid, "root_id": roots[i % 4], "stratum": "selfplay",
            "rules_profile": "walled", "phase_bucket": "mid", "capped": False,
            "sigma2_arm": 1.0 + 0.1 * i, "gap_G": 2.0 + 0.05 * i,
            "gap_G_parity_swap": 1.8 + 0.05 * i, "gap_naive": 2.5 + 0.05 * i,
            "headroom_champ": 0.5 + 0.02 * i,
            "headroom_champ_parity_swap": 0.4 + 0.02 * i,
            "headroom_champ_naive": 0.6 + 0.02 * i,
            "headroom_leaf": 0.3 + 0.02 * i,
            "scale_all": 1.0, "scale_strict": 0.9,
        }

    out = AO.stat_block(rows, "TEST")
    assert out["_label"] == "TEST"
    for key in ("S1a_sigma2_arm_all", "S2_headroom_all", "S2_headroom_parity_swap"):
        assert key in out
        blk = out[key]
        for sub in ("mean", "se_cluster", "z", "boot_lo", "boot_hi"):
            assert sub in blk
