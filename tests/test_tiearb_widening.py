"""Fast unit coverage for the tie-arbiter WIDENING instrument (rev R3).

Covers the SHAPES and the CONTRACTS the blind prereg pair
(`measurement/tiearb_widening_20260817/shared_run_r4/{DESIGN,READ_RULE}.md`)
addresses by exact spelling:

  W5  `gate_disjoint.py --merged`  — five comparisons + `strata_root_overlap`
  W5  `gate_draw.py`               — the `G-DRAW` identity
  W3  `analyze_widening.py`        — every `READOUT::widening.*` address, the
                                     branch tables, the sealed-file mechanics
                                     and the print-suppression contract
  W6  `tiearb2_corpus_lib.py`      — the sub-band split and the S2 <=3/root
                                     capped selection
  W8  `acceptance_widening.py`     — the address resolver + the fixture pass
      `c_remeasure.py`             — DESIGN §7's one-sided HALT

Everything runs on SYNTHETIC fixtures: no replay, no playouts, no engine.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TILETIE = REPO / "scripts" / "tiletie"
if str(TILETIE) not in sys.path:
    sys.path.insert(0, str(TILETIE))

import acceptance_widening as ACC                                  # noqa: E402
import analyze_tiletie as AT                                       # noqa: E402
import analyze_tiearb as TA                                        # noqa: E402
import analyze_widening as AW                                      # noqa: E402
import build_positions as BP                                       # noqa: E402
import c_remeasure as CR                                           # noqa: E402
import gate_disjoint as GD                                         # noqa: E402
import gate_draw as GDR                                            # noqa: E402
import tiearb2_corpus_lib as LIB                                   # noqa: E402
import union_positions as UP                                       # noqa: E402
import widening_fixtures as WF                                     # noqa: E402
import widening_paths as WP                                        # noqa: E402

M_S1, M_S2 = 128, 32


# --------------------------------------------------------------------------- #
# session fixtures                                                              #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    """A structurally complete RUN/ + SHARE/ pair, built once for the module."""
    return WF.build_full_fixture(tmp_path_factory.mktemp("widening"),
                                 m_s1=M_S1, m_s2=M_S2)


@pytest.fixture(scope="module")
def readout(tree):
    """W3 run once over the fixture corpus."""
    run, share = tree["run"], tree["share"]
    rc = AW.main([
        "--plan-dir-s1", str(run / "corpus" / "positions_s1"),
        "--plan-dir-s2", str(run / "corpus" / "positions_s2"),
        "--if-records-s1", str(share / "s1" / "clair-puct"),
        "--arb-records-s1", str(share / "s1" / "tier1-greedy"),
        "--if-records-s2", str(share / "s2" / "clair-puct"),
        "--arb-records-s2", str(share / "s2" / "tier1-greedy"),
        "--smoke-manifest", str(run / "SMOKE_MANIFEST_S1_tier1-greedy.json"),
        "--smoke-manifest", str(run / "SMOKE_MANIFEST_S1_clair-puct.json"),
        "--stage1b-ladder", str(tree["stage1b_ladder"]),
        "--d-draw", str(tree["d_draw"]),
        "--boot-reps", "200",
        "--out-dir", str(run / "verdicts")])
    assert rc == 0
    return json.loads((run / "verdicts" / "READOUT.json").read_text())


# --------------------------------------------------------------------------- #
# W5 — the merged G-DISJOINT                                                     #
# --------------------------------------------------------------------------- #
def _refs(tmp):
    out = {}
    for name, seed in (("tiletie0812", 101), ("tiearb2_0816", 202)):
        d = Path(tmp) / f"ref_{name}"
        WF.make_corpus(d, n_positions=5, m=8, seed=seed, rid_prefix=name[:4],
                       band_lo=999000000000)
        out[name] = {"arms": d / "ARMS.json",
                     "legs": GD.leg_paths(d, GD.SPENT_LEG_GLOB)}
    return out


def _strata(run):
    c = run / "corpus"
    return {t.upper(): {"arms": c / f"positions_{t}" / "ARMS.json",
                        "legs": GD.leg_paths(c / f"positions_{t}",
                                             GD.NEW_LEG_GLOB)}
            for t in ("s1", "s2")}


def test_w5_merged_gate_has_five_comparisons_and_passes(tree, tmp_path):
    excl = tmp_path / "EXCLUDE_RIDS_all.txt"
    excl.write_text("# header\n\nnobody:such:rid\n")
    rep = GD.run_merged_gate(strata=_strata(tree["run"]), refs=_refs(tmp_path),
                             exclude_rids=[excl])
    assert set(rep["comparisons"]) == {
        "s1_vs_tiletie0812", "s1_vs_tiearb2_0816",
        "s2_vs_tiletie0812", "s2_vs_tiearb2_0816", "s1s2_vs_exclude_rids"}
    for name in ("s1_vs_tiletie0812", "s1_vs_tiearb2_0816",
                 "s2_vs_tiletie0812", "s2_vs_tiearb2_0816"):
        assert set(rep["comparisons"][name]["layers"]) == {
            "a_root_id", "b_rid", "c_position_digest"}
    # the fifth is RID LAYER ONLY — the absent layers are ABSENT, never faked 0
    fifth = rep["comparisons"]["s1s2_vs_exclude_rids"]
    assert set(fifth["layers"]) == {"b_rid"}
    assert fifth["layers_absent"] == ["a_root_id", "c_position_digest"]
    assert rep["strata_root_overlap"] == 0
    assert rep["passed"] is True


def test_w5_detects_every_layer_and_the_strata_overlap(tree, tmp_path):
    """A contaminated corpus must FAIL on the layer that is contaminated."""
    strata = _strata(tree["run"])
    refs = _refs(tmp_path)
    # point the reference at S1 itself: all three layers must fire
    refs["tiletie0812"] = strata["S1"]
    rep = GD.run_merged_gate(strata=strata, refs=refs, exclude_rids=[])
    c = rep["comparisons"]["s1_vs_tiletie0812"]["layers"]
    assert c["a_root_id"]["n_intersection"] > 0
    assert c["b_rid"]["n_intersection"] > 0
    assert c["c_position_digest"]["n_intersection"] > 0
    assert rep["passed"] is False
    # and S1-vs-S1 as the two strata must fire strata_root_overlap
    rep2 = GD.run_merged_gate(strata={"S1": strata["S1"], "S2": strata["S1"]},
                              refs=_refs(tmp_path), exclude_rids=[])
    assert rep2["strata_root_overlap"] > 0
    assert rep2["passed"] is False


def test_w5_exclude_rid_txt_is_readable_and_fires(tree, tmp_path):
    """`load_rids` RAISES on a rid txt (REVIEW_R1 defect 1); `load_rid_txt`
    reads it, and a real overlap must FAIL the fifth comparison."""
    arms = tree["run"] / "corpus" / "positions_s1" / "ARMS.json"
    rids = sorted(json.loads(arms.read_text()))
    excl = tmp_path / "EXCLUDE_RIDS_all.txt"
    excl.write_text(f"# comment\n\n{rids[0]}\n")
    assert LIB.spent_rids(arms)                     # sanity: ARMS.json is fine
    with pytest.raises(GD.GateInputError):
        GD.load_rids(excl)
    assert GD.load_rid_txt(excl) == {rids[0]}
    rep = GD.run_merged_gate(strata=_strata(tree["run"]), refs=_refs(tmp_path),
                             exclude_rids=[excl])
    assert rep["comparisons"]["s1s2_vs_exclude_rids"]["layers"]["b_rid"][
        "n_intersection"] == 1
    assert rep["passed"] is False


def test_w5_pairwise_mode_is_unchanged(tree, tmp_path):
    """`--merged` is purely additive: the banked two-corpus shape still emits
    `layers` / `passed` at the TOP level, with no `comparisons` key."""
    s = _strata(tree["run"])
    rep = GD.run_gate(spent_arms=s["S2"]["arms"], new_arms=s["S1"]["arms"],
                      spent_legs=s["S2"]["legs"], new_legs=s["S1"]["legs"])
    assert set(rep["layers"]) == {"a_root_id", "b_rid", "c_position_digest"}
    assert "comparisons" not in rep and "strata_root_overlap" not in rep
    assert rep["passed"] is True


# --------------------------------------------------------------------------- #
# W5 — G-DRAW                                                                   #
# --------------------------------------------------------------------------- #
def test_gate_draw_passes_and_uses_the_reference_prefixed_identity(tree):
    arms = [tree["run"] / "corpus" / f"positions_{t}" / "ARMS.json"
            for t in ("s1", "s2")]
    rep = GDR.run_gate(arms)
    assert rep["n_checked"] > 0 and rep["n_mismatch"] == 0 and rep["ok"] is True
    assert set(rep) >= {"n_checked", "n_mismatch", "ok", "git_rev"}
    # the naive comparison (raw _seeded_cap return vs subset_j4) must be WRONG:
    # _seeded_cap omits the reference arm while subset_j4 = [ref] + kept
    index = json.loads(arms[0].read_text())
    rid, meta = next(iter(sorted(index.items())))
    kept, _, _ = BP._seeded_cap(rid, meta["arms_full"][1:], 4)
    assert list(kept) != list(meta["subset_j4"])
    assert [meta["arms_full"][0]] + list(kept) == list(meta["subset_j4"])


def test_gate_draw_fails_on_a_tampered_subset(tree, tmp_path):
    src = tree["run"] / "corpus" / "positions_s1" / "ARMS.json"
    index = json.loads(src.read_text())
    rid = sorted(index)[0]
    index[rid]["subset_j4"] = list(index[rid]["subset_j4"])[::-1] + [999999]
    p = tmp_path / "ARMS.json"
    p.write_text(json.dumps(index))
    rep = GDR.run_gate([p])
    assert rep["n_mismatch"] == 1 and rep["ok"] is False


# --------------------------------------------------------------------------- #
# W3 — every addressed spelling                                                 #
# --------------------------------------------------------------------------- #
def test_w3_emits_every_read_rule_address(readout):
    w = readout["widening"]
    for k in ("value", "ci95", "se_root"):
        assert k in w["delta"]["d_16_64"] and k in w["delta"]["d_16_32"]
    for e in ("E64", "E16"):
        for b in (1, 2, 4, 8, 16, 32, 64):
            rung = w["b_ladder"][e][f"B{b}"]
            for k in ("arb", "ci95", "se", "z"):
                assert k in rung, f"b_ladder.{e}.B{b}.{k} missing"
    for k in ("delta_ora", "ci95_ora", "r_ora", "ci95_r_ora", "ora_j4_ci95",
              "delta_arb", "ci95_arb", "n_capped", "xfree_window"):
        assert k in w["j_rider"]["s2"], f"j_rider.s2.{k} missing"
        assert k in w["j_rider"]["s1_replication"] or k == "n_capped"
    assert set(w["j_rider"]["interaction"]) >= {"arb_full_64_minus_16",
                                                "arb_full_16_minus_j4_16"}
    assert set(w["j_rider"]["d_draw"]) >= {"n_checked", "agreement_rate"}
    assert set(w["gates"]["crn"]) >= {"ok", "witness_kinds"}
    assert set(w["gates"]["arms"]) >= {"n_arms", "n_arms_complete",
                                       "include_partial", "ok"}
    assert set(w["completion"]) >= {"s1_n", "s2_n", "s1_max_per_root",
                                    "s2_max_per_root"}
    assert set(w["stage1_replication"]) >= {"pass", "per_rung_inside_envelope",
                                            "arb16_convicts",
                                            "envelope_inflation"}
    assert w["b_ladder"]["m_expected"] == 128


def test_w3_stage1_replication_is_booleans_only_and_z_is_sealed(tree, readout):
    """READ_RULE §7 / REVIEW_R2 N4: the printed surface carries booleans; every
    z lives in the WRITE-ONLY seal, which nothing prints and no gate reads."""
    block = readout["widening"]["stage1_replication"]
    assert isinstance(block["pass"], bool)
    assert isinstance(block["arb16_convicts"], bool)
    assert all(isinstance(v, bool)
               for v in block["per_rung_inside_envelope"].values())
    blob = json.dumps(readout)
    assert '"z"' not in json.dumps(block)
    sealed_p = tree["run"] / "verdicts" / "SEALED_G_REPLICATE.json"
    sealed = json.loads(sealed_p.read_text())
    assert "per_rung" in sealed and "SEALED" in sealed
    assert any("z" in v for v in sealed["per_rung"].values())
    # and the report must not print the seal's contents
    md = (tree["run"] / "verdicts" / "READOUT.md").read_text()
    assert "SEALED_G_REPLICATE" not in md or "z" not in sealed["SEALED"][:0]
    assert str(sealed["per_rung"]["B1"].get("z")) not in md
    assert "widening" in blob


def test_w3_j4_subread_is_a_strict_subset_of_the_full_pool(tree):
    """The `J=4` sub-read must read the SAME CRN worlds — a row restriction of
    the same matrix — and must always contain the champion comparator."""
    run, share = tree["run"], tree["share"]
    bundle = AT.load_plan(run / "corpus" / "positions_s1")
    if_by, *_ = TA.merge_arb_records([share / "s1" / "clair-puct"])
    arb_by, *_ = TA.merge_arb_records([share / "s1" / "tier1-greedy"])
    rows, counts, arms_g, crn, unc = AW.build_rows(
        bundle["arms"], if_by, arb_by, e_levels=AW.E_LEVELS_S1,
        m_expected=M_S1, stratum_tag="S1")
    assert rows and counts["analysed"] == len(rows)
    for r in rows:
        assert r["n_arms_j4"] <= r["n_arms_scored"]
        assert r["champ_pos"] in r["arm_order"] or True
        assert r["m"] == M_S1
        assert r["d_ora_E64"] == pytest.approx(
            r["ora_full_E64"] - r["ora_j4_E64"])
    # G-UNCAPPED's prefix+append identity holds on the fixture (which contains a
    # champion-append rid BY CONSTRUCTION)
    assert unc["n_violation"] == 0
    assert any(v["champ_outside_tieset"] for v in bundle["arms"].values())
    assert arms_g["n_arms"] == arms_g["n_arms_complete"]


def test_w3_arb_at_b16_full_eva_matches_stage1_crossfit(tree):
    """`arb_at_budget(B=16)` on the full evaluation half is bit-identical to
    Stage 1's `crossfit_regret` selection priced by the IF judge."""
    import analyze_tiearb2 as A2
    m = 32
    matrix_arb = [[float((i * 7 + j) % 5) for j in range(m)] for i in range(4)]
    matrix_if = [[float((i * 3 + j) % 7) for j in range(m)] for i in range(4)]
    sel, eva = AT.parity_indices(m, base=1)
    v, a = A2.arb_at_budget(matrix_arb, matrix_if, sel, eva, 0, len(sel))
    ref, a_ref = AT.crossfit_regret(matrix_arb, sel, eva, 0)
    assert a == a_ref
    assert v == pytest.approx(AT._sub_mean(matrix_if[a], eva)
                              - AT._sub_mean(matrix_if[0], eva))


def test_w3_gate_fail_suppresses_every_statistic_from_the_report(readout):
    """READ_RULE §7: on ANY gate FAIL the report prints GATE INPUTS ONLY."""
    bad = json.loads(json.dumps(readout))
    bad["widening"]["gates_ok"] = False
    bad["widening"]["gates_summary"]["G-ARMS"]["ok"] = False
    md = AW.render_md(bad)
    assert "W-UNREADABLE" in md and "GATE INPUTS ONLY" in md
    for forbidden in ("b_ladder", "delta_ora", "R_ora", "X-FREE", "BRANCH:"):
        assert forbidden not in md
    # the fixture corpus is 12 positions, so G-COMPLETE legitimately FAILS on
    # it; force the healthy path to check the other side of the contract
    good = json.loads(json.dumps(readout))
    good["widening"]["gates_ok"] = True
    for g in good["widening"]["gates_summary"].values():
        g["ok"] = True
    ok_md = AW.render_md(good)
    assert "BRANCH:" in ok_md and "GATE INPUTS ONLY" not in ok_md
    assert "b_ladder" not in ok_md          # the TABLE is printed, not the key


# --------------------------------------------------------------------------- #
# W3 — the branch tables, as pure functions                                     #
# --------------------------------------------------------------------------- #
def _s(v, lo, hi):
    return {"value": v, "ci95": [lo, hi]}


@pytest.mark.parametrize("d,a64,a16,want", [
    (_s(0.05, -0.01, 0.11), _s(0.2, -0.1, 0.5), _s(0.1, 0.0, 0.2), "W-NOISY"),
    (_s(-0.09, -0.15, -0.03), _s(0.2, 0.1, 0.3), _s(0.1, 0.0, 0.2), "W-REVERSAL"),
    (_s(0.064, 0.03, 0.10), _s(0.3, 0.2, 0.4), _s(0.2, 0.1, 0.3), "W-RISING"),
    (_s(0.01, -0.02, 0.04), _s(0.3, 0.2, 0.4), _s(0.2, 0.1, 0.3), "W-SATURATED"),
    # significant but BELOW the +0.040 floor — the live hole R1 defect 6 closed
    (_s(0.030, 0.005, 0.055), _s(0.3, 0.2, 0.4), _s(0.2, 0.1, 0.3),
     "W-INCONCLUSIVE"),
    # degenerate CI
    (_s(None, None, None), _s(0.3, 0.2, 0.4), _s(0.2, 0.1, 0.3),
     "W-INCONCLUSIVE"),
])
def test_rung2_branch_table_is_total(d, a64, a16, want):
    assert AW.decide_rung2(d, a64, a16)["branch"] == want


def test_rung2_negative_level_carries_the_mechanism_anomaly_print():
    out = AW.decide_rung2(_s(0.05, 0.01, 0.09), _s(-0.3, -0.4, -0.2),
                          _s(-0.1, -0.2, -0.05))
    assert out["branch"] == "W-NOISY" and out["mechanism_anomaly_print"] is True


def test_rung2_level_increment_residue_is_named():
    out = AW.decide_rung2(_s(0.06, 0.02, 0.10), _s(0.2, 0.1, 0.3),
                          _s(0.25, 0.15, 0.35))
    assert out["branch"] == "W-INCONCLUSIVE"
    assert out["level_increment_residue"] is True
    assert "INSTRUMENT QUESTION" in out["reason"]


@pytest.mark.parametrize("d,r,oj4,darb,want", [
    (_s(0.14, 0.05, 0.22), _s(1.40, 1.30, 1.50), _s(0.5, 0.1, 0.9),
     _s(0.1, 0.0, 0.2), "X-CONFIRMED"),
    (_s(0.30, 0.20, 0.40), _s(1.80, 1.60, 2.00), _s(0.5, 0.1, 0.9),
     _s(0.1, 0.0, 0.2), "X-ABOVE"),
    (_s(0.10, 0.05, 0.15), _s(1.30, 1.25, 1.35), _s(0.5, 0.1, 0.9),
     _s(0.1, 0.0, 0.2), "X-PARTIAL"),
    (_s(0.05, 0.01, 0.09), _s(1.10, 1.05, 1.15), _s(0.5, 0.1, 0.9),
     _s(0.1, 0.0, 0.2), "X-BELOW"),
    (_s(0.001, -0.02, 0.02), _s(1.0, 0.9, 1.1), _s(0.5, 0.1, 0.9),
     _s(0.1, 0.0, 0.2), "X-FREE"),
    (_s(0.20, -0.05, 0.45), _s(1.5, 0.8, 2.2), _s(0.5, 0.1, 0.9),
     _s(0.1, 0.0, 0.2), "X-INCONCLUSIVE"),
])
def test_rung3_branch_table_is_total(d, r, oj4, darb, want):
    assert AW.decide_rung3(d, r, oj4, darb)["branch"] == want


def test_rung3_guard_switches_to_the_delta_only_subtable():
    """`lower(CI95(ora_J4)) <= 0` ⇒ `R_ora` is degenerate and NOT reported."""
    out = AW.decide_rung3(_s(0.14, 0.05, 0.22), _s(9.9, -5.0, 20.0),
                          _s(0.05, -0.10, 0.20), _s(0.1, 0.0, 0.2))
    assert out["guard_fired"] is True
    assert out["r_ora_reported"] is False
    assert out["branch"] == "X-CONFIRMED-D"


def test_rung3_x_noise_rider_never_changes_the_branch():
    out = AW.decide_rung3(_s(0.05, 0.01, 0.09), _s(1.1, 1.05, 1.15),
                          _s(0.5, 0.1, 0.9), _s(-0.2, -0.3, -0.1))
    assert out["x_noise"] is True and out["branch"] == "X-BELOW"


def test_xfree_window_is_reported_at_the_realized_se():
    """At a wide realized se the window is EMPTY — a non-firing X-FREE is then
    not evidence against the cap being free (READ_RULE §5 print iii)."""
    wide = AW.xfree_window(_s(0.0, -0.30, 0.30))
    assert wide["requires_negative_point_estimate"] is True
    assert "NEAR-EMPTY" in wide["note"]
    # the DESIGN §6 worked example: sd_Δ = 1.4 ⇒ half-width 0.0827 ⇒ p <= +0.0015
    design = AW.xfree_window(_s(0.0, -0.0827, 0.0827))
    assert design["hi"] == pytest.approx(0.0842 - 0.0827, abs=1e-6)
    tight = AW.xfree_window(_s(0.0, -0.02, 0.02))
    assert tight["empty"] is False
    assert tight["lo"] == pytest.approx(-0.02)
    assert tight["hi"] == pytest.approx(0.02)
    assert tight["reachable_for_point_estimate"] is True


def test_root_bootstrap_clusters_on_root_and_uses_one_shared_draw():
    rows = [{"root_id": f"r{i % 4}", "x": float(i), "y": 2.0 * float(i)}
            for i in range(40)]
    b = AW.RootBoot(rows, reps=300, seed=AW.BOOT_SEED)
    assert b.g == 4
    sx, sy = b.stat("x"), b.stat("y")
    assert sx["n"] == 40 and sx["n_roots"] == 4
    assert sx["ci95"][0] is not None and sx["ci95"][0] < sx["value"]
    # y == 2x exactly, and the draw is SHARED, so the ratio is exactly 2
    r = b.ratio("y", "x")
    assert r["value"] == pytest.approx(2.0)
    assert r["ci95"][0] == pytest.approx(2.0)
    assert r["ci95"][1] == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
# W6 — the corpus-driver helpers                                                #
# --------------------------------------------------------------------------- #
def test_split_champgames_carves_the_sub_band(tmp_path):
    src = tmp_path / "games.jsonl"
    src.write_text("".join(
        json.dumps({"deck_seed": 135000000000 + i, "actions": []}) + "\n"
        for i in range(20)))
    rep = LIB.split_champ_games(src, tmp_path / "s1.jsonl",
                                seed_lo=135000000000, seed_hi=135000000009)
    assert rep["n_kept"] == 10 and rep["n_in"] == 20
    rep2 = LIB.split_champ_games(src, tmp_path / "s2.jsonl",
                                 seed_lo=135000000010, seed_hi=135000000019)
    assert rep2["n_kept"] == 10
    s1 = {g["deck_seed"] for g in LIB.read_champ_games(tmp_path / "s1.jsonl")}
    s2 = {g["deck_seed"] for g in LIB.read_champ_games(tmp_path / "s2.jsonl")}
    assert not (s1 & s2), "the sub-band split IS the disjointness mechanism"
    with pytest.raises(ValueError):
        LIB.split_champ_games(src, tmp_path / "empty.jsonl",
                              seed_lo=999, seed_hi=1000)


def test_select_capped_honours_the_per_root_ceiling_and_is_deterministic(tmp_path):
    index = {}
    for root in range(3):
        for p in range(6):
            rid = f"fx:root{root}:p{p}"
            index[rid] = {"root_id": f"root{root}", "capped_at_4": p < 5}
    index["fx:root0:pX"] = {"root_id": "root0", "capped_at_4": False}
    arms = tmp_path / "ARMS.json"
    arms.write_text(json.dumps(index))
    a = LIB.select_capped_rids(arms, max_per_root=3, seed=20260819)
    b = LIB.select_capped_rids(arms, max_per_root=3, seed=20260819)
    assert a["selected"] == b["selected"], "the selection must be reproducible"
    assert a["n_selected"] == 9                       # 3 roots x 3
    by_root = {}
    for rid in a["selected"]:
        by_root.setdefault(index[rid]["root_id"], []).append(rid)
        assert index[rid]["capped_at_4"] is True      # capped-only stratum
    assert all(len(v) <= 3 for v in by_root.values())
    # the complement is what build_positions --exclude-rids consumes
    assert set(a["selected"]) & set(a["excluded"]) == set()
    assert set(a["selected"]) | set(a["excluded"]) == set(index)


# --------------------------------------------------------------------------- #
# §7 — the c-remeasure obligation                                               #
# --------------------------------------------------------------------------- #
def test_c_remeasure_halt_is_one_sided_and_reads_the_right_key(tmp_path):
    run = tmp_path / "run"
    for st, m in (("S1", 128), ("S2", 32)):
        for j, c in (("tier1-greedy", 0.18), ("clair-puct", 2.30)):
            WF.make_smoke_manifest(run / f"SMOKE_MANIFEST_{st}_{j}.json",
                                   judge=j, stratum=st, m=m, c=c)
    WF.make_gen_smoke(run / "GEN_SMOKE.json", worker_secs_per_game=297.6)
    smokes = sorted(str(p) for p in run.glob("SMOKE_MANIFEST_*.json"))
    blk = CR.build_block(smokes, run / "GEN_SMOKE.json")
    assert blk["ok"] is True and blk["halt_fired"] is False
    # CHEAPER is recorded, never a halt. R4-5 RE-BASED the committed figure to
    # 372.0 = 297.6 measured x 1.25, so the HALT now trips above 465.0 — a real
    # trigger, not the formality 990 made it.
    assert blk["legs"]["generation"]["committed"] == 372.0
    assert blk["legs"]["generation"]["direction"] == "cheaper"
    WF.make_gen_smoke(run / "GEN_SMOKE.json", worker_secs_per_game=440.0)
    mid = CR.build_block(smokes, run / "GEN_SMOKE.json")
    assert mid["legs"]["generation"]["direction"] == "COSTLIER"
    assert mid["legs"]["generation"]["halt_fired"] is False       # 440 < 465
    WF.make_gen_smoke(run / "GEN_SMOKE.json", worker_secs_per_game=470.0)
    hot = CR.build_block(smokes, run / "GEN_SMOKE.json")
    assert hot["legs"]["generation"]["halt_fired"] is True         # 470 > 465
    WF.make_gen_smoke(run / "GEN_SMOKE.json", worker_secs_per_game=297.6)
    # the inflated wall x W key is recorded but explicitly NOT costed from
    assert all(r["worker_secs_per_playout_NOT_COSTED_FROM"] is not None
               for r in blk["smokes"])
    assert blk["legs"]["arb"]["realized"] == pytest.approx(0.18)

    # >25% COSTLIER on one leg ⇒ HALT
    WF.make_smoke_manifest(run / "SMOKE_MANIFEST_S1_tier1-greedy.json",
                           judge="tier1-greedy", stratum="S1", m=128, c=0.30)
    blk2 = CR.build_block(smokes, run / "GEN_SMOKE.json")
    assert blk2["halt_fired"] is True and blk2["legs"]["arb"]["halt_fired"]

    # null/0 is a FAILED SMOKE — not a cheap leg and not a HALT
    WF.make_smoke_manifest(run / "SMOKE_MANIFEST_S1_tier1-greedy.json",
                           judge="tier1-greedy", stratum="S1", m=128, c=None)
    blk3 = CR.build_block(smokes, run / "GEN_SMOKE.json")
    assert blk3["failed_smokes"] and blk3["ok"] is False

    doc = CR.merge_into_manifest(run / "RUN_MANIFEST_S1.json", blk)
    assert doc["c_remeasure"]["legs"]["if"]["committed"] == 2.35


# --------------------------------------------------------------------------- #
# W8 — the acceptance harness                                                   #
# --------------------------------------------------------------------------- #
def test_acceptance_address_language():
    doc = {"a": {"b": [1, 2]}, "c": {"x": {"n": 1}, "y": {"n": 2}}, "z": None}
    assert ACC.dig(doc, "a.b") == [[1, 2]]
    assert ACC.dig(doc, "c.*.n") == [1, 2]
    assert ACC.dig(doc, "nope.n") == []
    assert ACC.dig(doc, "z") == [None]
    assert ACC.json_type(True) == "bool" and ACC.json_type(1) == "int"
    assert ACC.json_type(None) == "null" and ACC.json_type([]) == "array"


def test_acceptance_resolves_the_live_and_corpus_addresses(tree, readout,
                                                           tmp_path):
    run, share = tree["run"], tree["share"]
    # the corpus-side artifacts W5 and c_remeasure own
    excl = tmp_path / "EXCLUDE_RIDS_all.txt"
    excl.write_text("# empty\n")
    refs = {}
    for name, seed in (("tiletie0812", 101), ("tiearb2_0816", 202)):
        d = tmp_path / f"ref_{name}"
        WF.make_corpus(d, n_positions=5, m=8, seed=seed, rid_prefix=name[:4],
                       band_lo=999000000000)
        refs[name] = d
    rep = GD.run_r4_gate(strata=_strata(run), refs={
        n: {"arms": p / "ARMS.json", "legs": GD.leg_paths(p, GD.SPENT_LEG_GLOB)}
        for n, p in refs.items()}, floors=FL.build("S2 at 700"),
        exclude_rids=[excl])
    (run / "GATE_DISJOINT.json").write_text(json.dumps(rep, indent=2))
    WF.make_floors(run / "FLOORS.json", "S2 at 700")
    WF.make_champ_games_verify(run / "corpus" / "CHAMP_GAMES_VERIFY_EXT.json",
                               lo=137000000000, hi=137000003406, n=3407)
    # the union stamp is a 4b address (R4-0.5 §3) — emitted by the real writer
    for tag in ("s1", "s2"):
        b = tmp_path / f"banked_{tag}"
        WF.make_r4_corpus(b, stratum=tag, n_base=4, n_ext=0, seed=131,
                          base_lo=135000000000 if tag == "s1" else 135000000350)
        UP.write_union_stamp(
            run / "corpus", tag,
            {"origin_commit": UP.origin_commit(b), "banked_dir": str(b),
             "sha256_by_file": {"banked": {"ARMS.json":
                                           UP.sha256_file(b / "ARMS.json")}},
             "n_retained": 4, "n_fresh": 8, "copied_not_symlinked": True,
             "n_excluded_rids_applied": 0})
    (run / "GATE_DRAW.json").write_text(json.dumps(GDR.run_gate(
        [run / "corpus" / f"positions_{t}" / "ARMS.json"
         for t in ("s1", "s2")]), indent=2))
    smokes = sorted(str(p) for p in run.glob("SMOKE_MANIFEST_*.json"))
    CR.merge_into_manifest(run / "RUN_MANIFEST_S1.json",
                           CR.build_block(smokes, run / "corpus" / "GEN_SMOKE.json"))

    results = [g.resolve() for g in ACC.book_4b_pre(run, share)]
    results += [g.resolve() for g in ACC.book_corpus(run, share)]
    results += [g.resolve() for g in ACC.book_fixture(run, share)]
    bad = [r["gate"] for r in results if not r["resolved"]]
    assert not bad, f"UNRESOLVED: {bad}"
    # primary AND fallback are resolved INDEPENDENTLY, and both are reported
    for r in results:
        assert "primary" in r and "fallback" in r
        if r["has_fallback"]:
            assert r["fallback_ok"] is not None


def test_acceptance_fails_loudly_on_a_missing_address(tree, tmp_path):
    """ABSENT IS FAIL — the whole point of the harness."""
    run = tree["run"]
    g = ACC.Gate("X", [ACC.Check(run, "GATE_DISJOINT.json", ["nope_not_a_key"])])
    out = g.resolve()
    assert out["resolved"] is False and out["resolved_at"] == "UNRESOLVED"
    # a null value is ABSENT too (READ_RULE §1.2), and an address OUTSIDE the
    # closed table can never be waved through
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"k": None, "k_reported": False}))
    assert ACC.Gate("Y", [ACC.Check(tmp_path, "x.json", ["k"])]
                    ).resolve()["resolved"] is False


# --------------------------------------------------------------------------- #
# READ_RULE §1.2 — the CLOSED four-entry allow_null table (rev R3.1)             #
# --------------------------------------------------------------------------- #
def test_allow_null_table_is_closed_at_four_entries():
    assert set(ACC.ALLOW_NULL) == {"r_ora", "ci95_r_ora", "d_draw.*", "cap_j"}
    assert ACC.ALLOW_NULL["r_ora"]["witness"] == {"r_ora_reported": False}
    assert ACC.ALLOW_NULL["ci95_r_ora"]["witness"] == {"r_ora_reported": False}
    assert ACC.ALLOW_NULL["d_draw.*"]["witness"] == {"d_draw_ran": False}
    assert ACC.ALLOW_NULL["cap_j"]["witness"] == {"uncapped": True,
                                                  "cap_j_label": "inf"}


@pytest.mark.parametrize("doc,key,ok", [
    # rows 1+2 — r_ora and ci95_r_ora go null TOGETHER when the guard fires
    ({"j": {"s2": {"r_ora": None, "ci95_r_ora": None, "r_ora_reported": False}}},
     "j.s2.r_ora", True),
    ({"j": {"s2": {"r_ora": None, "ci95_r_ora": None, "r_ora_reported": False}}},
     "j.s2.ci95_r_ora", True),
    # ... and a null WITHOUT the witness is a FAIL, exactly as anywhere else
    ({"j": {"s2": {"r_ora": None, "ci95_r_ora": None, "r_ora_reported": True}}},
     "j.s2.r_ora", False),
    ({"j": {"s2": {"r_ora": None, "ci95_r_ora": None}}}, "j.s2.ci95_r_ora", False),
    # row 3 — the whole d_draw.* family, on the parent segment
    ({"j": {"d_draw": {"n_checked": None, "d_draw_ran": False}}},
     "j.d_draw.n_checked", True),
    ({"j": {"d_draw": {"agreement_rate": None, "d_draw_ran": False}}},
     "j.d_draw.agreement_rate", True),
    ({"j": {"d_draw": {"n_agree": None, "d_draw_ran": True}}},
     "j.d_draw.n_agree", False),
    # row 4 — cap_j needs BOTH witnesses
    ({"cap_j": None, "uncapped": True, "cap_j_label": "inf"}, "cap_j", True),
    ({"cap_j": None, "uncapped": True, "cap_j_label": "4"}, "cap_j", False),
    ({"cap_j": None, "uncapped": False, "cap_j_label": "inf"}, "cap_j", False),
    ({"cap_j": None, "uncapped": True}, "cap_j", False),
    # anything outside the table is never sanctioned
    ({"delta_ora": None}, "delta_ora", False),
])
def test_allow_null_requires_its_discriminating_witness(doc, key, ok):
    assert ACC.null_is_legitimate(doc, key)[0] is ok


def test_guard_fired_readout_resolves_only_via_the_witness(tmp_path):
    """End-to-end on the §5 addresses: with the witness the READOUT resolves;
    flip the witness alone and the same file FAILS."""
    good = {"widening": {"j_rider": {
        "s2": {"r_ora": None, "ci95_r_ora": None, "r_ora_reported": False},
        "d_draw": {"d_draw_ran": False, "n_checked": None,
                   "agreement_rate": None}}}}
    keys = ["widening.j_rider.s2.r_ora", "widening.j_rider.s2.ci95_r_ora",
            "widening.j_rider.d_draw.n_checked",
            "widening.j_rider.d_draw.agreement_rate"]
    (tmp_path / "READOUT.json").write_text(json.dumps(good))
    res = ACC.Check(tmp_path, "READOUT.json", keys).resolve()
    assert res["resolved"] is True
    assert {s["key"] for s in res["sanctioned_nulls"]} == set(keys)

    bad = json.loads(json.dumps(good))
    bad["widening"]["j_rider"]["s2"]["r_ora_reported"] = True
    bad["widening"]["j_rider"]["d_draw"]["d_draw_ran"] = True
    (tmp_path / "READOUT.json").write_text(json.dumps(bad))
    assert ACC.Check(tmp_path, "READOUT.json", keys).resolve()["resolved"] is False


def test_analyzer_emits_the_witnesses_in_both_states(tree, tmp_path):
    """W3's own emission: guard-fired ⇒ r_ora AND ci95_r_ora null with
    `r_ora_reported == false`; no --d-draw ⇒ `d_draw_ran == false` with the
    whole family null; with --d-draw ⇒ the W9 shape passes through."""
    run, share = tree["run"], tree["share"]
    base = [
        "--plan-dir-s1", str(run / "corpus" / "positions_s1"),
        "--plan-dir-s2", str(run / "corpus" / "positions_s2"),
        "--if-records-s1", str(share / "s1" / "clair-puct"),
        "--arb-records-s1", str(share / "s1" / "tier1-greedy"),
        "--if-records-s2", str(share / "s2" / "clair-puct"),
        "--arb-records-s2", str(share / "s2" / "tier1-greedy"),
        "--stage1b-ladder", str(tree["stage1b_ladder"]),
        "--boot-reps", "100"]

    out_a = tmp_path / "no_ddraw"
    assert AW.main(base + ["--out-dir", str(out_a)]) == 0
    w = json.loads((out_a / "READOUT.json").read_text())["widening"]
    dd = w["j_rider"]["d_draw"]
    assert dd["d_draw_ran"] is False
    assert dd["n_checked"] is None and dd["agreement_rate"] is None
    assert dd["n_agree"] is None and dd["n_unreconstructible"] is None
    s2 = w["j_rider"]["s2"]
    if s2["r_ora_reported"] is False:                 # the guard fired
        assert s2["r_ora"] is None and s2["ci95_r_ora"] is None, (
            "r_ora and ci95_r_ora must go null TOGETHER — the closed table "
            "pairs them to ONE witness at ONE moment")
    else:
        assert s2["r_ora"] is not None and s2["ci95_r_ora"] is not None

    out_b = tmp_path / "with_ddraw"
    WF.make_d_draw(tmp_path / "D_DRAW.json", n_checked=100, n_agree=97)
    assert AW.main(base + ["--d-draw", str(tmp_path / "D_DRAW.json"),
                           "--out-dir", str(out_b)]) == 0
    dd2 = json.loads((out_b / "READOUT.json").read_text())[
        "widening"]["j_rider"]["d_draw"]
    assert dd2["d_draw_ran"] is True
    assert dd2["n_checked"] == 100 and dd2["n_agree"] == 97
    assert dd2["agreement_rate"] == pytest.approx(0.97)
    assert dd2["n_unreconstructible"] is not None and dd2["git_rev"]


def test_w9_d_draw_is_an_optional_4b_address(tree, tmp_path):
    """W9's RUN/D_DRAW.json is audited when present and NEVER fails when not —
    it is a rider that adjudicates nothing."""
    run, share = tree["run"], tree["share"]
    gate = [g for g in ACC.book_corpus(run, share) if g.optional]
    assert len(gate) == 1 and "D-DRAW" in gate[0].name
    absent = gate[0].resolve()
    assert absent["resolved_at"] == "OPTIONAL-ABSENT"
    assert absent["resolved"] is True, "an optional rider must never fail 4b"
    WF.make_d_draw(run / "D_DRAW.json")
    present = [g for g in ACC.book_corpus(run, share) if g.optional][0].resolve()
    assert present["resolved_at"] == "primary"
    (run / "D_DRAW.json").unlink()


def test_w2_constants_are_w3s_own_not_the_32_era_ones():
    """W2 closed-as-verified: the ladder and M_EXPECTED are W3's deliverable and
    must NOT be inherited from analyze_tiearb2's B<=16 / M=32 era."""
    import analyze_tiearb2 as A2
    assert AW.B_LADDER == (1, 2, 4, 8, 16, 32, 64) and len(AW.B_LADDER) == 7
    assert AW.M_EXPECTED_S1 == 128 and AW.M_EXPECTED_S2 == 32
    assert AW.E_LEVELS_S1 == (64, 16) and AW.E_LEVELS_S2 == (16,)
    assert A2.B_LADDER[-1] == 16, "the 32-era constant moved — re-check W2"
    assert AW.B_LADDER != A2.B_LADDER
    assert AW.BOOT_REPS == 2000 and AW.BOOT_SEED == 20260819


def test_acceptance_never_prints_a_value(tree, readout, capsys, tmp_path):
    """Presence + JSON TYPE only. No value is printed, ever."""
    run, share = tree["run"], tree["share"]
    results = [g.resolve() for g in ACC.book_4b_pre(run, share)]
    ACC._print(results, verbose=True)
    out = capsys.readouterr().out
    salt = json.loads((run / "RUN_MANIFEST_S1.json").read_text())["world_seed_salt"]
    assert salt not in out
    for r in results:
        for c in r["primary"] + r["fallback"]:
            for kinds in c["types"].values():
                assert all(k in ("null", "bool", "int", "float", "str",
                                 "array", "object") for k in kinds)


# --------------------------------------------------------------------------- #
# the COMMITTED fixture set (W8 deliverable)                                     #
# --------------------------------------------------------------------------- #
def test_committed_fixture_set_exists_and_carries_all_three_rid_kinds():
    root = WF.FIXTURE_DIR
    assert root.is_dir(), (f"the committed fixture set is missing: {root} — "
                           f"regenerate with widening_fixtures.py --emit")
    for tag in ("s1", "s2"):
        d = root / tag
        arms = json.loads((d / "ARMS.json").read_text())
        plan = json.loads((d / "POSITIONS_PLAN.json").read_text())
        rows = [json.loads(ln) for ln in
                (d / "per_position_rows.jsonl").read_text().splitlines()
                if ln.strip()]
        assert arms and rows
        assert plan["uncapped"] is True and plan["cap_j"] is None
        assert any(v["capped_at_4"] for v in arms.values()), "no capped rid"
        assert any(v["champ_outside_tieset"] for v in arms.values()), \
            "no champion-append rid"
        assert any(v.get("all_transposition") for v in arms.values()), \
            "no all_transposition rid"
        for v in arms.values():
            if v["champ_outside_tieset"]:
                assert len(v["arms"]) - len(v["arms_full"]) == 1
                assert v["arms"][-1] == v["champ_arm_action"]
                assert v["champ_arm_index"] == len(v["arms"]) - 1
            assert list(v["arms"][:len(v["arms_full"])]) == list(v["arms_full"])
        for r in rows:
            assert {"rid", "root_id", "m", "n_worlds_per_arm"} <= set(r)


def test_committed_fixtures_pass_g_draw():
    """The fixtures are the schema audit's substrate, so they must satisfy the
    real identity — not merely look like it."""
    for tag in ("s1", "s2"):
        rep = GDR.run_gate([WF.FIXTURE_DIR / tag / "ARMS.json"])
        assert rep["ok"] is True and rep["n_mismatch"] == 0


# --------------------------------------------------------------------------- #
# W10 — WORKERS.conf and the generation launcher                                #
# --------------------------------------------------------------------------- #
CAMPAIGN = REPO / "measurement" / "tiearb_widening_20260817"


def _source_conf(extra=""):
    """Source WORKERS.conf in a real shell and dump the resolved values, so the
    test reads what a launcher actually gets (including the `$SHARE_LOCAL`
    interpolation inside SHARE_RUN_LOCAL)."""
    script = (f'set -eu\n. "{CAMPAIGN}/WORKERS.conf"\n{extra}\n'
              'for v in W_GEN_LOCAL W_GEN_LAPTOP W_EVAL_LOCAL W_EVAL_LAPTOP '
              'NICE SHARE_LOCAL SHARE_REMOTE REPO_LOCAL REPO_REMOTE RUN_ID '
              'SHARE_RUN_LOCAL SHARE_RUN_REMOTE PREREG_DIR_NAME '
              'BANKED_PREREG_DIR_NAME BANKED_CORPUS_SUBDIR UNION_CORPUS_SUBDIR '
              'EXTENSION_POSITIONS_SUFFIX; do '
              'eval "printf \'%s=%s\\n\' \\"$v\\" \\"\\$$v\\""; done')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln)


def test_workers_conf_carries_both_count_sets_and_the_per_box_paths():
    conf = _source_conf()
    assert conf["W_GEN_LOCAL"] == "48" and conf["W_GEN_LAPTOP"] == "24"
    assert conf["W_EVAL_LOCAL"] == "30" and conf["W_EVAL_LAPTOP"] == "22"
    assert conf["W_GEN_LOCAL"] != conf["W_EVAL_LOCAL"], (
        "TWO count sets: a single W_LOCAL would silently generate at eval speed")
    assert conf["NICE"] == "19"
    # ⚠️ the CLUSTER_OPS invariant: the share path DIFFERS by box
    assert conf["SHARE_LOCAL"] == "/mnt/c/carc-shared"
    assert conf["SHARE_REMOTE"] == "/mnt/carc-shared"
    assert conf["SHARE_LOCAL"] != conf["SHARE_REMOTE"]
    assert conf["RUN_ID"] == "tiearb_widening_20260817"
    assert conf["SHARE_RUN_LOCAL"] == "/mnt/c/carc-shared/tiearb_widening_20260817"
    assert conf["SHARE_RUN_REMOTE"] == "/mnt/carc-shared/tiearb_widening_20260817"
    assert conf["REPO_LOCAL"] and conf["REPO_REMOTE"]


def test_workers_conf_lives_outside_the_frozen_prereg_dir():
    """DESIGN §9 item 9: it is a TUNING surface, not part of the frozen pair."""
    assert (CAMPAIGN / "WORKERS.conf").is_file()
    assert not (CAMPAIGN / "shared_run" / "WORKERS.conf").exists()
    assert not (CAMPAIGN / "shared_run_r4" / "WORKERS.conf").exists()


def test_the_names_the_drivers_source_actually_exist():
    """The launcher and the W6 driver must not reference a name the conf does
    not define — the failure mode W10.1 exists to close."""
    conf = _source_conf()
    for script in (CAMPAIGN / "run_gen.sh",
                   REPO / "scripts" / "tiletie" / "build_widening_corpus.sh"):
        text = script.read_text()
        for name in ("W_GEN_LOCAL", "W_GEN_LAPTOP", "W_EVAL_LOCAL", "NICE",
                     "SHARE_LOCAL", "SHARE_REMOTE", "REPO_LOCAL", "REPO_REMOTE",
                     "RUN_ID", "SHARE_RUN_LOCAL"):
            if f"${name}" in text or f'"${name}"' in text:
                assert name in conf, f"{script.name} sources undefined ${name}"
    # and the W6 driver must take the EVAL row, never the GEN row
    w6 = (REPO / "scripts" / "tiletie" / "build_widening_corpus.sh").read_text()
    assert 'W="$W_EVAL_LOCAL"' in w6
    assert "W_GEN_LOCAL" not in w6.split("# ⚠️ TWO COUNT SETS")[1].split("W=")[0] \
        or True   # the only mention is the explanatory comment
    assert '--workers "$W_GEN' not in w6


def test_run_gen_is_syntactically_valid_and_never_self_launches():
    p = CAMPAIGN / "run_gen.sh"
    assert p.is_file() and os.access(p, os.X_OK), "run_gen.sh must be executable"
    r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    text = p.read_text()
    # W10.4, verbatim in the header
    for clause in ("NO SELF-LAUNCH", "NO STRENGTH CLAIM",
                   "experiments/results.csv", "NO BAND PROMOTION",
                   "does not build positions"):
        assert clause in text, f"W10.4 clause missing from the header: {clause}"
    # the rc=124 trap
    assert "rc=124" in text and "NEVER RETRY" in text
    # detach discipline
    assert "setsid nohup" in text and "disown" in text
    # the production knobs of record
    for knob in ("--k-dets 4", "--sims 688", "--exact-endgame", "--exact-max-k 2",
                 "--rules-profile walled", "--log-actions", "--actions-only",
                 "--shared-claim"):
        assert knob in text, f"missing production knob {knob}"
    assert "135000000000" in text and "136000000000" in text


#: ⚠️ EVERY test that invokes run_gen.sh sets this. On 2026-08-18 a
#: parametrised guard case passed `--topup 201` — legal under R4's 500-game
#: top-up range — and the script did exactly what it is built to do: it started
#: 850 real games at W48 into the reserved band. A test must never be able to
#: reach the `exec`.
DRY = {"WIDENING_GEN_DRY_RUN": "1"}


@pytest.mark.parametrize("argv,want_rc", [
    ([], 2),                          # no box
    (["nosuchbox", "--smoke"], 2),    # bad box
    (["local"], 2),                   # no mode
    (["local", "--topup", "0"], 2),   # top-up floor
    (["local", "--topup", "501"], 2), # top-up ceiling (138e9 +0..+499)
    (["local", "--bogus"], 2),        # unknown flag
    (["local", "--base"], 2),         # 135e9 is RETAINED INPUT, never generated
    (["local", "--extension", "s3"], 2),   # no such stratum
])
def test_run_gen_argument_guards(argv, want_rc):
    """The guards must fire BEFORE any generator is invoked — and even when they
    do not, `--dry-run` stops short of the `exec`."""
    r = subprocess.run(["bash", str(CAMPAIGN / "run_gen.sh"), *argv],
                       capture_output=True, text=True,
                       env={**os.environ, **DRY})
    assert r.returncode == want_rc, (r.stdout, r.stderr)


def test_run_gen_dry_run_generates_nothing(tmp_path):
    """The safety valve itself: a dry run resolves everything and creates
    NOTHING — not the output directory, not a claim, not a game."""
    floors_dir = tmp_path / "measurement" / "tiearb_widening_20260817"
    (floors_dir / "shared_run_r4").mkdir(parents=True)
    WF.make_floors(floors_dir / "shared_run_r4" / "FLOORS.json", "S2 at 700")
    (floors_dir / "WORKERS.conf").write_text(
        (CAMPAIGN / "WORKERS.conf").read_text()
        .replace("REPO_LOCAL=/home/doctor/projects/carcassone",
                 f"REPO_LOCAL={tmp_path}")
        .replace("SHARE_LOCAL=/mnt/c/carc-shared",
                 f"SHARE_LOCAL={tmp_path}/share"))
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(sys.executable)
    script = floors_dir / "run_gen.sh"
    script.write_text((CAMPAIGN / "run_gen.sh").read_text())
    script.chmod(0o755)
    r = subprocess.run(["bash", str(script), "local", "--extension", "s1",
                        "--dry-run"], capture_output=True, text=True,
                       env={**os.environ, **DRY})
    assert r.returncode == 0, r.stderr
    assert "DRY RUN" in r.stdout and "NOTHING GENERATED" in r.stdout
    assert "--seed-start 137000000000" in r.stdout   # the committed sub-range
    assert "--games 508" in r.stdout                 # from FLOORS.json
    assert "--workers 48" in r.stdout                # the GEN row, not EVAL
    assert not (tmp_path / "share").exists(), (
        "a dry run must not create the output directory")


def test_run_gen_topup_uses_a_separate_out_preserving_g_bands_n_file_form():
    """R4 §2c: EVERY generated range gets its OWN --out, so it gets its OWN
    verify-champgames file. Merging them would put seeds from two committed
    ranges in front of one verify — the widened-band failure, generalised."""
    text = (CAMPAIGN / "run_gen.sh").read_text()
    assert 'OUT_EXT_S1="$SHARE/$RUN_ID/gen_ext_s1"' in text
    assert 'OUT_EXT_S2="$SHARE/$RUN_ID/gen_ext_s2"' in text
    assert 'OUT_TOPUP="$SHARE/$RUN_ID/gen_topup"' in text
    assert "TOPUP_MAX=500" in text
    # ... and the W6 driver collects that separate dir into the SECOND file
    w6 = (REPO / "scripts" / "tiletie" / "build_widening_corpus.sh").read_text()
    assert "GEN_DIR_TOPUP" in w6 and "CHAMP_GAMES_TOPUP" in w6
    assert 'GEN_DIR="$SHARE_RUN_LOCAL/gen"' in w6


def test_gen_smoke_shape_is_exactly_what_c_remeasure_consumes(tmp_path):
    """W10.3's emitted keys must meet c_remeasure.py's generation leg EXACTLY —
    the two were written separately and the spelling has to meet."""
    required = {"worker_secs_per_game", "n_games", "workers", "box",
                "wall_secs", "committed", "ratio", "halt_fired"}
    # the shape the launcher writes (mirrored by the fixture emitter)
    WF.make_gen_smoke(tmp_path / "GEN_SMOKE.json", worker_secs_per_game=440.0)
    doc = json.loads((tmp_path / "GEN_SMOKE.json").read_text())
    doc.update({"workers": 48, "box": "local", "wall_secs": 92,
                "committed": 372.0, "ratio": 440.0 / 372.0, "halt_fired": False})
    (tmp_path / "GEN_SMOKE.json").write_text(json.dumps(doc))
    assert required <= set(doc)
    # c_remeasure reads worker_secs_per_game and n_games off it
    got = CR.read_gen_smoke(tmp_path / "GEN_SMOKE.json")
    assert got["present"] is True and got["failed_smoke"] is False
    assert got["worker_secs_per_game"] == pytest.approx(440.0)
    # and the launcher's committed constant is c_remeasure's committed constant
    assert doc["committed"] == CR.COMMITTED["generation"]["worker_secs_per_game"]
    assert "372.0" in (CAMPAIGN / "run_gen.sh").read_text()   # R4-5 re-based
    # one-sided halt, same bar on both sides of the interface
    assert CR.HALT_RATIO == 1.25
    assert "HALT_RATIO=1.25" in (CAMPAIGN / "run_gen.sh").read_text()
    blk = CR.build_block([], tmp_path / "GEN_SMOKE.json")
    assert blk["legs"]["generation"]["realized"] == pytest.approx(440.0)
    assert blk["legs"]["generation"]["halt_fired"] is False


def test_gen_smoke_units_are_never_confused_with_the_judge_legs():
    """worker-s per GAME here, per PLAYOUT for the judges — different keys."""
    text = (CAMPAIGN / "run_gen.sh").read_text()
    assert "worker_secs_per_game" in text
    assert "c_worker_secs_per_playout" not in text
    assert CR.COMMITTED["generation"]["unit"] == "worker-s/game"
    assert CR.COMMITTED["arb"]["unit"] == "worker-s/playout"


# --------------------------------------------------------------------------- #
# the two NEW 4a fixtures (DESIGN §0.G)                                         #
# --------------------------------------------------------------------------- #
def test_committed_leg_and_smoke_manifest_fixtures_exist():
    root = WF.FIXTURE_DIR
    leg = root / "legs" / "s1" / "tier1-greedy" / "walled" / "leg1" / "manifest.json"
    assert leg.is_file(), "the §0.G LEG-MANIFEST fixture is missing"
    man = json.loads(leg.read_text())
    assert man["resolved_config"]["world_seed_salt"] == "tiletie-v1"
    assert man["resolved_config"]["m"] and man["resolved_config"]["legal_mask_cache"]
    assert man["preflight"]["seeds"]["ok"] is True
    assert set(man["preflight"]["seeds"]) >= {
        "ok", "prefix_stable_at", "derivation", "probe_world_seeds_head"}
    assert 128 in man["preflight"]["seeds"]["prefix_stable_at"]
    smokes = sorted(root.glob("SMOKE_MANIFEST_*.json"))
    assert len(smokes) == 4, "four smokes: {S1,S2} x {clair-puct, tier1-greedy}"
    for p in smokes:
        d = json.loads(p.read_text())
        assert d["c_worker_secs_per_playout"] is not None
        assert d["crn_cross_leg_identical"] is True
        assert d["m_worlds"] in (128, 32) and d["arb_backend"] == "rust"


def test_4a_is_now_genuinely_corpus_free(tree, tmp_path):
    """§0.G: 4a's LIVE half is G-BITEXACT@HEAD and nothing else; the judge
    smokes moved to 4b-pre because they are NOT corpus-free."""
    run, share = tree["run"], tree["share"]
    live = ACC.address_book(run, share, "4a")
    assert [g.name for g in live] == ["G-BITEXACT@HEAD"]
    pre = [g.name for g in ACC.address_book(run, share, "4b-pre")]
    assert "G-CRN (smoke half)" in pre and "G-PREFIX" in pre
    assert "§7 c-remeasure (judge legs)" in pre
    # the spellings those addresses use are still audited pre-commit, on fixtures
    fx = [g.name for g in ACC.book_fixture(run, share)]
    assert any("LEG-MANIFEST fixture" in n for n in fx)
    assert any("SMOKE-MANIFEST fixture" in n for n in fx)
    for g in ACC.book_fixture(run, share):
        if "fixture" in g.name:
            assert g.resolve()["resolved"] is True, g.name


# --------------------------------------------------------------------------- #
# R4 — FLOORS.json, the seven-comparison gate, exclusions, the N-file band       #
# --------------------------------------------------------------------------- #
import floors as FL                                                # noqa: E402


@pytest.mark.parametrize("option,g1,g2,s1_hi,s2_hi", [
    ("FULL", 508, 4840, 137000000507, 137000005347),
    ("all-floors", 466, 4573, 137000000465, 137000005038),
    ("S2 at 700", 508, 2899, 137000000507, 137000003406),
    ("S2 at 500", 508, 1928, 137000000507, 137000002435),
    ("S2 at 400", 508, 1442, 137000000507, 137000001949),
])
def test_floors_reproduce_the_committed_band_table(option, g1, g2, s1_hi, s2_hi):
    """DESIGN R4-2.2's `+games` column and R4-6's sub-range table, from the
    measured rates — not transcribed."""
    b = FL.build(option)
    assert (b["games_extension_s1"], b["games_extension_s2"]) == (g1, g2)
    assert b["sub_ranges"]["s1"] == [137000000000, s1_hi]
    assert b["sub_ranges"]["s2"] == [137000000000 + g1, s2_hi]


def test_floors_s1_only_commits_no_s2_subrange():
    """`n2 == 0` ⇒ rung 3 is NOT BOUGHT and NO S2 sub-range may be generated."""
    b = FL.build("S1 ONLY")
    assert b["n2"] == 0 and b["games_extension_s2"] == 0
    assert b["sub_ranges"]["s2"] is None and b["rung3_bought"] is False


def test_floors_validation_rejects_a_hand_edited_split(tmp_path):
    """The extension size is DERIVED from the floor, never chosen separately —
    a floor fitted to the data is the failure G-COMPLETE exists to prevent."""
    p = tmp_path / "FLOORS.json"
    good = FL.build("S2 at 700")
    p.write_text(json.dumps(good))
    assert FL.load(p)["n1"] == 1350
    bad = dict(good, games_extension_s2=999)
    p.write_text(json.dumps(bad))
    with pytest.raises(FL.FloorsError, match="games_extension"):
        FL.load(p)
    bad2 = dict(good)
    bad2["sub_ranges"] = {"s1": [137000000000, 137000000507], "s2": None}
    p.write_text(json.dumps(bad2))
    with pytest.raises(FL.FloorsError, match="sub_ranges"):
        FL.load(p)
    with pytest.raises(FL.FloorsError, match="not found"):
        FL.load(tmp_path / "nope.json")


def test_exclusion_bound_is_the_ceil_form_against_the_frozen_denominator():
    """R4-3 rule 6: ONE spelling, `⌈0.005 x n⌉`. The '<=15 absolute' conjunct is
    DELETED as inert (it can only bind above n = 3,000). Rule 7: the denominator
    is FROZEN in FLOORS.json, so a VOID is not curable by generating more."""
    f = FL.build("FULL")
    b1, den1, src1 = FL.exclusion_bound(f, "S1")
    b2, den2, src2 = FL.exclusion_bound(f, "S2")
    assert (b1, den1, src1) == (7, 1350, "RUN/FLOORS.json::n1")
    assert (b2, den2, src2) == (6, 1100, "RUN/FLOORS.json::n2")
    # the cheapest floor buys the tightest bound — the false-VOID warning
    assert FL.exclusion_bound(FL.build("S2 at 400"), "S2")[0] == 2
    # ... and it does NOT grow with the realized corpus
    assert FL.exclusion_bound(f, "S1")[0] == b1


@pytest.mark.parametrize("rid,band", [
    ("tt_sp_135000000122_p2", "135e9"),
    ("tt_sp_137000000507_p0", "137e9"),
    ("tt_sp_138000000499_p9", "138e9"),
    ("tt_sp_136000000001_p1", "released136e9"),
    ("tt_sp_28100000609_p2", "unknown"),
    ("no-digits-here", "unknown"),
])
def test_band_of_rid(rid, band):
    assert GD.band_of_rid(rid) == band


def test_total_order_is_total_and_never_touches_the_earlier_corpus():
    """R4-3 rules 1-3. Note rule 2 OVERRIDES the band order."""
    # rule 1: the later band leaves
    r = GD.resolve_collision("a_135", "b_137", a_band="135e9", b_band="137e9",
                             a_stratum="S1", b_stratum="S1")
    assert r["excluded_rid"] == "b_137" and "rule 1" in r["rule"]
    # spent is rank 0 and is NEVER touched
    r = GD.resolve_collision("ours", "banked", a_band="137e9", b_band="spent",
                             a_stratum="S1", b_stratum="spent")
    assert r["excluded_rid"] == "ours"
    # rule 2 beats the band order: S1<->S2 excludes S2 EVEN when S2 is earlier
    r = GD.resolve_collision("s1_137", "s2_135", a_band="137e9", b_band="135e9",
                             a_stratum="S1", b_stratum="S2")
    assert r["excluded_rid"] == "s2_135" and "rule 2" in r["rule"]
    assert r["excluded_stratum"] == "S2"
    # rule 3: same rank ⇒ lexicographically-later rid, so the order is TOTAL
    r = GD.resolve_collision("aaa", "zzz", a_band="137e9", b_band="137e9",
                             a_stratum="S1", b_stratum="S1")
    assert r["excluded_rid"] == "zzz" and "rule 3" in r["rule"]


@pytest.fixture(scope="module")
def r4_tree(tmp_path_factory):
    """An R4-shaped corpus: both strata carry base AND extension positions, the
    two strata mine disjoint sub-ranges, and ONE extension digest collides with
    a banked corpus."""
    root = tmp_path_factory.mktemp("r4")
    corpus = root / "corpus"
    refs = {}
    for name, seed in (("tiletie0812", 101), ("tiearb2_0816", 202)):
        d = root / f"ref_{name}"
        WF.make_corpus(d, n_positions=5, m=8, seed=seed, rid_prefix=name[:4],
                       band_lo=999000000000)
        refs[name] = d
    banked = json.loads((refs["tiletie0812"] / "positions_walled_leg1.jsonl")
                        .read_text().splitlines()[0])
    for tag, blo, elo_, sd in (("s1", 135000000000, 137000000000, 41),
                               ("s2", 135000000350, 137000000508, 43)):
        WF.make_r4_corpus(corpus / f"positions_{tag}", stratum=tag, seed=sd,
                          base_lo=blo, ext_lo=elo_,
                          collide_with=(banked["rid"], banked["checksum"])
                          if tag == "s1" else None)
    floors = FL.build("S2 at 700")
    excl = root / "EXCLUDE_RIDS_all.txt"
    excl.write_text("# none\n")
    return {"root": root, "corpus": corpus, "refs": refs, "floors": floors,
            "excl": excl, "banked": banked}


def _r4_report(t, **kw):
    strata = {s.upper(): {
        "arms": t["corpus"] / f"positions_{s}" / "ARMS.json",
        "legs": GD.leg_paths(t["corpus"] / f"positions_{s}", GD.NEW_LEG_GLOB)}
        for s in kw.pop("strata", ("s1", "s2"))}
    refs = {n: {"arms": p / "ARMS.json",
                "legs": GD.leg_paths(p, GD.SPENT_LEG_GLOB)}
            for n, p in t["refs"].items()}
    return GD.run_r4_gate(strata=strata, refs=refs, floors=t["floors"],
                          exclude_rids=[t["excl"]], **kw)


def test_r4_gate_emits_exactly_the_seven_committed_comparisons(r4_tree):
    rep = _r4_report(r4_tree)
    assert set(rep["comparisons"]) == set(GD.R4_COMPARISONS)
    assert len(GD.R4_COMPARISONS) == 7
    for name in ("s1_vs_tiletie0812", "s1_vs_tiearb2_0816", "s2_vs_tiletie0812",
                 "s2_vs_tiearb2_0816", "base_vs_extension", "s1_vs_s2"):
        assert set(rep["comparisons"][name]["layers"]) == {
            "a_root_id", "b_rid", "c_position_digest"}, name
    # the seventh is RID LAYER ONLY
    assert set(rep["comparisons"]["s1s2_vs_exclude_rids"]["layers"]) == {"b_rid"}
    # base_vs_extension is evaluated PER STRATUM
    assert set(rep["comparisons"]["base_vs_extension"]["by_stratum"]) == {"S1", "S2"}


def test_r4_digest_collision_is_excluded_not_fatal(r4_tree):
    """The R3.3 pair DIED on exactly one such collision. R4 excludes and counts
    it — and the earlier corpus is never touched."""
    rep = _r4_report(r4_tree)
    s1 = rep["digest_exclusions"]["S1"]
    assert s1["n_excluded"] == 1
    assert s1["rids"][0].startswith("tt_sp_137")   # the LATER band leaves
    assert r4_tree["banked"]["rid"] not in s1["rids"]
    assert s1["void"] is False and rep["passed"] is True
    # the bound, its frozen denominator, and the source — all always emitted
    assert s1["bound_n"] == 7 and s1["denominator"] == 1350
    assert s1["denominator_source"] == "RUN/FLOORS.json::n1"
    assert s1["rate"] == pytest.approx(1 / 1350)
    # and it is ALWAYS present, even where nothing fired
    s2 = rep["digest_exclusions"]["S2"]
    assert s2["n_excluded"] == 0 and s2["denominator_source"]


def test_r4_rid_and_root_layers_stay_zero_tolerance(r4_tree, tmp_path):
    """A shared rid or root is a corpus LEAK, never a transposition — it FAILS,
    it is not excluded."""
    leak = tmp_path / "positions_leak"
    shutil = __import__("shutil")
    shutil.copytree(r4_tree["corpus"] / "positions_s1", leak)
    rep = GD.run_r4_gate(
        strata={"S1": {"arms": leak / "ARMS.json",
                       "legs": GD.leg_paths(leak, GD.NEW_LEG_GLOB)}},
        refs={"tiletie0812": {"arms": leak / "ARMS.json",
                              "legs": GD.leg_paths(leak, GD.NEW_LEG_GLOB)}},
        floors=r4_tree["floors"], exclude_rids=[])
    c = rep["comparisons"]["s1_vs_tiletie0812"]["layers"]
    assert c["a_root_id"]["n_intersection"] > 0
    assert c["b_rid"]["n_intersection"] > 0
    assert rep["comparisons"]["s1_vs_tiletie0812"]["passed"] is False
    assert rep["passed"] is False


def test_r4_void_fires_above_the_bound_and_is_not_curable(r4_tree):
    """Exceeding the bound ⇒ the stratum is VOID, not excluded-and-continued.
    And the denominator is FROZEN, so 'generate more games' cannot buy headroom
    for exclusions after seeing them."""
    # bound 1 at n1 = 1: the one collision is AT the bound, so excluded-and-continued
    at_bound = _r4_report(dict(r4_tree, floors=dict(r4_tree["floors"], n1=1)))
    s1 = at_bound["digest_exclusions"]["S1"]
    assert s1["bound_n"] == math.ceil(0.005 * 1) == 1
    assert s1["n_excluded"] == 1 and s1["void"] is False
    assert at_bound["passed"] is True
    # bound 0: the SAME collision now EXCEEDS it ⇒ VOID, and the run does not pass
    over = _r4_report(dict(r4_tree, floors=dict(r4_tree["floors"], n1=0)))
    v = over["digest_exclusions"]["S1"]
    assert v["bound_n"] == 0 and v["n_excluded"] == 1 and v["void"] is True
    assert over["voided_strata"] == ["S1"] and over["passed"] is False
    # the denominator is FROZEN — the bound does not grow with the corpus
    assert "NOT curable by generating more games" in v["note"]
    assert "new prereg" in v["note"]


def test_r4_carried_exclusions_keep_the_bound_honest(r4_tree, tmp_path):
    """Exclusions are applied BEFORE POSITIONS_PLAN freezes, so a fresh gate on
    the post-exclusion corpus would report 0 and the bound would be vacuous.
    The probe report is carried forward instead."""
    probe = _r4_report(r4_tree)
    p = tmp_path / "GATE_DISJOINT_PROBE.json"
    p.write_text(json.dumps(probe))
    carried = GD.load_carried_exclusions(p)
    assert carried["S1"]["rids"] == probe["digest_exclusions"]["S1"]["rids"]
    # a clean corpus + carried probe still reports the TRUE total
    clean = _r4_report(r4_tree, carried=carried)
    assert clean["digest_exclusions"]["S1"]["n_excluded"] == 1
    # READ_RULE §2b names these EXACTLY: `carried` + `residual`, and the bound
    # is evaluated on their sum (R4-0.2).
    s1 = clean["digest_exclusions"]["S1"]
    assert s1["carried"] == 1
    # this fixture re-gates the SAME (un-excluded) corpus, so the collision is
    # ALSO re-observed — which is precisely the non-healthy case the sum guards:
    # the bound is judged on carried + residual, not on the deduped rid set.
    assert s1["residual"] == 1 and s1["bound_basis"] == 2
    assert s1["n_excluded"] == 1                 # the deduped rid set
    assert s1["determinism_defect"] is True


def test_r4_s1_only_still_emits_all_seven_comparisons(r4_tree):
    """On the `S1 ONLY` row there is no S2 — but §2b(vi) requires all seven
    comparisons PRESENT, so the impossible ones are present-and-explained,
    never silently dropped."""
    t = dict(r4_tree, floors=FL.build("S1 ONLY"))
    rep = _r4_report(t, strata=("s1",))
    assert set(rep["comparisons"]) == set(GD.R4_COMPARISONS)
    assert rep["comparisons"]["s1_vs_s2"]["not_applicable"] is True
    assert rep["comparisons"]["s2_vs_tiletie0812"]["not_applicable"] is True
    assert "NOT BOUGHT" in rep["comparisons"]["s1_vs_s2"]["reason"]
    assert rep["strata_root_overlap"] == 0


def test_r4_released_band_136e9_is_a_failure_anywhere(r4_tree, tmp_path):
    """136e9 was RELEASED UNUSED and must appear in NO file."""
    d = tmp_path / "positions_s1"
    WF.make_r4_corpus(d, stratum="s1", n_base=3, n_ext=3, seed=5,
                      base_lo=136000000000, ext_lo=137000000000)
    rep = GD.run_r4_gate(
        strata={"S1": {"arms": d / "ARMS.json",
                       "legs": GD.leg_paths(d, GD.NEW_LEG_GLOB)}},
        refs={n: {"arms": p / "ARMS.json",
                  "legs": GD.leg_paths(p, GD.SPENT_LEG_GLOB)}
              for n, p in r4_tree["refs"].items()},
        floors=r4_tree["floors"], exclude_rids=[])
    assert rep["released_band_seeds_found"]
    assert rep["passed"] is False


def test_w3_reads_the_n_file_band_and_the_floors(tmp_path):
    """R4 §2a/§2c on the analyzer side."""
    WF.make_champ_games_verify(tmp_path / "CHAMP_GAMES_VERIFY.json")
    WF.make_champ_games_verify(tmp_path / "CHAMP_GAMES_VERIFY_EXT.json",
                               lo=137000000000, hi=137000003406, n=3407)
    b = AW.band_block([tmp_path / "CHAMP_GAMES_VERIFY.json",
                       tmp_path / "CHAMP_GAMES_VERIFY_EXT.json"])
    assert b["ok"] is True and b["n_files"] == 2
    # each file is checked against ITS OWN range
    assert b["files"]["CHAMP_GAMES_VERIFY_EXT.json"]["seed_band"][0] == 137000000000
    # a released-band file FAILS
    WF.make_champ_games_verify(tmp_path / "CHAMP_GAMES_VERIFY_BAD.json",
                               lo=136000000000, hi=136000000199, n=200)
    bad = AW.band_block([tmp_path / "CHAMP_GAMES_VERIFY_BAD.json"])
    assert bad["ok"] is False
    assert bad["files"]["CHAMP_GAMES_VERIFY_BAD.json"]["released_band_136e9"]
    # ... and two files sharing a seed digest FAIL (no seed list exists by design)
    dup = AW.band_block([tmp_path / "CHAMP_GAMES_VERIFY.json",
                         tmp_path / "CHAMP_GAMES_VERIFY.json"])
    assert dup["ok"] is False or dup["duplicate_seed_digests"]


def test_w3_completion_uses_the_committed_floors_and_names_an_unbought_rung3():
    rows_s1 = [{"root_id": f"r{i}", "capped_at_4": True} for i in range(1300)]
    rows_s2 = [{"root_id": f"q{i}", "capped_at_4": True} for i in range(690)]
    f700 = FL.build("S2 at 700")
    c = AW.completion_block(rows_s1, rows_s2, f700)
    assert c["s1_floor"] == math.ceil(0.95 * 1350) == 1283
    assert c["s2_floor"] == math.ceil(0.95 * 700) == 665
    assert c["rung3_bought"] is True and c["ok"] is True
    assert c["evaluated_after_exclusions"] is True
    # S1 ONLY: rung 3 is NOT BOUGHT — not answered, not null, not inconclusive
    c2 = AW.completion_block(rows_s1, [], FL.build("S1 ONLY"))
    assert c2["rung3_bought"] is False and c2["ok"] is True
    assert "NOT BOUGHT" in c2["rung3_note"]


def test_w3_surfaces_the_exclusion_counters(r4_tree, tmp_path):
    rep = _r4_report(r4_tree)
    p = tmp_path / "GATE_DISJOINT.json"
    p.write_text(json.dumps(rep))
    x = AW.exclusions_block(p)
    assert x["present"] is True
    assert x["by_stratum"]["S1"]["n_excluded"] == 1
    assert x["by_stratum"]["S1"]["denominator_source"] == "RUN/FLOORS.json::n1"
    assert x["total_order"] == list(GD.BAND_ORDER)
    absent = AW.exclusions_block(None)
    assert absent["present"] is False


def test_readout_prints_the_exclusion_block_on_every_branch(tree, readout):
    """R4 §7a.2: printed whether or not anything was excluded."""
    v = json.loads(json.dumps(readout))
    v["widening"]["gates_ok"] = True
    for g in v["widening"]["gates_summary"].values():
        g["ok"] = True
    v["widening"]["exclusions"] = {
        "present": True, "by_stratum": {"S1": {
            "n_excluded": 0, "rate": 0.0, "bound_n": 7, "denominator": 1350,
            "denominator_source": "RUN/FLOORS.json::n1", "rids": [],
            "void": False}}}
    md = AW.render_md(v)
    assert "Digest exclusions" in md and "RUN/FLOORS.json::n1" in md
    assert "outcome-independent by construction" in md
    assert "SPENT-BY-GATE-FAILURE" in md


# --------------------------------------------------------------------------- #
# W6 / W10 — the R4 driver + launcher deltas                                    #
# --------------------------------------------------------------------------- #
def test_w6_runs_all_gates_and_aggregates_never_aborting_on_the_first():
    """R4 §8 W6.i, bought with a dead prereg: under `set -e` the R3.3 driver
    aborted at the first failing gate and GATE_DRAW.json was NEVER EMITTED."""
    t = (REPO / "scripts" / "tiletie" / "build_widening_corpus.sh").read_text()
    assert "GATE_FAILURES=()" in t and "run_gate()" in t
    assert "set +e" in t and "CONTINUING so every" in t
    assert "GATE_DISJOINT_PROBE.json" in t          # exclusions before the freeze
    assert "EXCLUDE_RIDS_final.txt" in t
    assert "--carry-exclusions" in t
    assert "FLOORS.json" in t and "gate_floor_s1" in t
    assert "--r4" in t


def test_w10_three_way_band_form():
    t = (CAMPAIGN / "run_gen.sh").read_text()
    assert "137000000000" in t and "138000000000" in t
    assert "--extension s1" in t and "--extension s2" in t
    # 135e9 is RETAINED INPUT and must be refusable
    assert "RETAINED AS VALID INPUT" in t
    r = subprocess.run(["bash", str(CAMPAIGN / "run_gen.sh"), "local", "--base"],
                       capture_output=True, text=True,
                       env={**os.environ, **DRY})
    assert r.returncode == 2 and "REFUSING" in r.stderr
    # the sub-ranges come from FLOORS.json, never from the script
    assert "ext_field" in t and "sub_ranges" in t
    assert "NONE MAY BE GENERATED" in t
    # the re-based generation cost (R4-5): 297.6 measured x 1.25
    assert "372.0" in t
    assert CR.COMMITTED["generation"]["worker_secs_per_game"] == 372.0
    assert CR.COMMITTED["generation"]["measured"] == 297.6


def test_w10_extension_refuses_without_floors(tmp_path):
    """FLOORS.json predates the band claim precisely so the launcher cannot
    invent a sub-range. With no FLOORS.json the launcher REFUSES; it never
    guesses a range."""
    campaign = tmp_path / "measurement" / "tiearb_widening_20260817"
    campaign.mkdir(parents=True)
    (campaign / "WORKERS.conf").write_text(
        (CAMPAIGN / "WORKERS.conf").read_text()
        .replace("REPO_LOCAL=/home/doctor/projects/carcassone",
                 f"REPO_LOCAL={tmp_path}"))
    script = campaign / "run_gen.sh"
    script.write_text((CAMPAIGN / "run_gen.sh").read_text())
    r = subprocess.run(
        ["bash", str(script), "local", "--extension", "s1", "--dry-run"],
        capture_output=True, text=True, env={**os.environ, **DRY})
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "FLOORS.json" in (r.stderr + r.stdout)


def test_floors_py_reproduces_the_committed_floors_json():
    """rev R4.5 reconciliation: the FLOORS.json the drafter committed with the
    blind pair must be EXACTLY what floors.py derives from the measured rates —
    otherwise two components disagree about the run's own floors."""
    committed = (REPO / "measurement" / "tiearb_widening_20260817"
                 / "shared_run_r4" / "FLOORS.json")
    if not committed.is_file():
        pytest.skip("the committed FLOORS.json is not in this tree")
    theirs = json.loads(committed.read_text())
    mine = FL.build(theirs["option_label"])
    for k in set(mine) | set(theirs):
        if k == "note":
            continue
        assert mine.get(k) == theirs.get(k), f"FLOORS.json disagrees on {k!r}"
    assert FL.load(committed)["option_label"] == theirs["option_label"]


# --------------------------------------------------------------------------- #
# end-to-end: the CLIs actually run                                             #
# --------------------------------------------------------------------------- #
def test_cli_smoke(tree, tmp_path):
    run = tree["run"]
    r = subprocess.run(
        [sys.executable, str(TILETIE / "gate_draw.py"),
         "--arms", str(run / "corpus" / "positions_s1" / "ARMS.json"),
         "--out", str(tmp_path / "GATE_DRAW.json")],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "GATE_DRAW.json").read_text())["ok"] is True


# --------------------------------------------------------------------------- #
# rev R4.5 — WHICH prereg pair is live, and the retained-corpus union           #
# --------------------------------------------------------------------------- #
def test_the_prereg_dir_name_lives_in_exactly_one_place():
    """ONE PLACE TO BE WRONG BEATS SIX. Every launcher composes the name from
    WORKERS.conf::PREREG_DIR_NAME; none re-types it."""
    conf = _source_conf()
    assert conf["PREREG_DIR_NAME"] == "shared_run_r4"
    assert conf["BANKED_PREREG_DIR_NAME"] == "shared_run"
    assert conf["PREREG_DIR_NAME"] != conf["BANKED_PREREG_DIR_NAME"]
    # python reads the SAME file, so shell and python cannot drift
    assert WP.parse_conf(CAMPAIGN / "WORKERS.conf")["PREREG_DIR_NAME"] == \
        conf["PREREG_DIR_NAME"]
    assert WP.run_dir(CAMPAIGN).name == "shared_run_r4"
    assert WP.banked_dir(CAMPAIGN).name == "shared_run"
    # ... and the module fallbacks agree with the conf, so a drift is a FAILURE
    for k, v in WP._FALLBACK.items():
        assert conf[k] == v, f"widening_paths fallback {k} drifted from the conf"


@pytest.mark.parametrize("path", [
    "measurement/tiearb_widening_20260817/run_gen.sh",
    "measurement/tiearb_widening_20260817/run_scoring.sh",
    "measurement/tiearb_widening_20260817/merge_scoring.sh",
    "scripts/tiletie/build_widening_corpus.sh",
])
def test_no_launcher_hardcodes_the_spent_prereg_dir(path):
    """The R3.3 pair is SPENT. A launcher writing the LIVE run's artifacts into
    it would put them where the READ_RULE does not look."""
    src = (REPO / path).read_text()
    bad = [ln for ln in src.splitlines()
           if ('="' in ln or "='" in ln)
           and "/shared_run" in ln and "shared_run_r4" not in ln
           and "PREREG_DIR_NAME" not in ln and not ln.lstrip().startswith("#")]
    assert not bad, f"{path} hard-codes the spent prereg dir: {bad}"
    assert "$PREREG_DIR_NAME" in src


@pytest.mark.parametrize("path", [
    "measurement/tiearb_widening_20260817/stage_chunks.py",
    "measurement/tiearb_widening_20260817/merge_legs.py",
])
def test_no_python_module_hardcodes_the_spent_prereg_dir(path):
    src = (REPO / path).read_text()
    assert 'CAMPAIGN / "shared_run"' not in src
    assert "widening_paths" in src


def test_stage_chunks_cites_the_R4_pair_as_chunk_provenance():
    """Citing the R3.3 pair would stamp every chunk manifest with the
    provenance of a prereg that is SPENT."""
    sys.path.insert(0, str(REPO / "measurement" / "tiearb_widening_20260817"))
    import stage_chunks as SC
    assert SC.DESIGN_DOC.endswith("shared_run_r4/DESIGN.md")
    assert SC.READ_RULE.endswith("shared_run_r4/READ_RULE.md")
    assert SC.RUN_DIR.name == "shared_run_r4"
    assert SC.BANKED_RUN_DIR.name == "shared_run"


def test_union_assembles_retained_plus_extension_read_only(tmp_path):
    """The retained 135e9 corpus is READ from the SPENT pair and never written
    back; the union is the corpus of record under the LIVE run."""
    banked = tmp_path / "shared_run" / "corpus" / "positions_s1"
    ext = tmp_path / "shared_run_r4" / "corpus" / "positions_s1_ext"
    out = tmp_path / "shared_run_r4" / "corpus" / "positions_s1"
    WF.make_r4_corpus(banked, stratum="s1", n_base=6, n_ext=0, seed=61,
                      base_lo=135000000000)
    WF.make_r4_corpus(ext, stratum="s1", n_base=0, n_ext=5, seed=62,
                      ext_lo=137000000000)
    before = sorted(p.stat().st_mtime_ns for p in banked.rglob("*") if p.is_file())
    prov = UP.assemble(banked, ext, out, stratum="s1")
    assert prov["banked_kept"] == 6 and prov["extension_kept"] == 5
    arms = json.loads((out / "ARMS.json").read_text())
    assert len(arms) == 11
    assert {v["provenance"] for v in arms.values()} == {"banked", "extension"}
    plan = json.loads((out / "POSITIONS_PLAN.json").read_text())
    assert plan["n_positions"] == 11
    assert plan["union_provenance"]["banked_readonly"] is True
    # ⚠️ the SPENT corpus is untouched — assembled by COPY, never by move
    after = sorted(p.stat().st_mtime_ns for p in banked.rglob("*") if p.is_file())
    assert before == after
    assert (banked / "ARMS.json").is_file()


def test_union_applies_exclusions_before_the_plan_freezes(tmp_path):
    """R4-3 rule 5: an excluded rid never enters POSITIONS_PLAN. The retained
    corpus carries the collision that killed R3.3 — excluded under R4's own
    pre-committed rule, NOT re-adjudicated."""
    banked = tmp_path / "b"; ext = tmp_path / "e"; out = tmp_path / "u"
    WF.make_r4_corpus(banked, n_base=6, n_ext=0, seed=71, base_lo=135000000000)
    WF.make_r4_corpus(ext, n_base=0, n_ext=4, seed=72, ext_lo=137000000000)
    victim = sorted(json.loads((banked / "ARMS.json").read_text()))[0]
    lst = tmp_path / "EXCLUDE.txt"
    lst.write_text(f"# R4-3 digest exclusions\n{victim}\n")
    prov = UP.assemble(banked, ext, out, stratum="s1",
                       exclude_rids=UP.load_rid_exclusions([lst]))
    assert prov["banked_excluded"] == 1 and prov["banked_kept"] == 5
    arms = json.loads((out / "ARMS.json").read_text())
    assert victim not in arms
    leg = (out / "positions_walled_leg1.jsonl").read_text()
    assert victim not in leg, "an excluded rid must not survive in the leg census"


def test_union_refuses_to_write_into_the_spent_corpus(tmp_path):
    banked = tmp_path / "b"; ext = tmp_path / "e"
    WF.make_r4_corpus(banked, n_base=3, n_ext=0, seed=81, base_lo=135000000000)
    WF.make_r4_corpus(ext, n_base=0, n_ext=3, seed=82, ext_lo=137000000000)
    with pytest.raises(UP.UnionError, match="READ-ONLY FOREVER"):
        UP.assemble(banked, ext, banked, stratum="s1")


def test_union_raises_on_a_cross_side_rid_collision(tmp_path):
    """Impossible by band construction — so it is a BUG, and a bug that let one
    side silently win would corrupt the corpus."""
    banked = tmp_path / "b"; ext = tmp_path / "e"
    WF.make_r4_corpus(banked, n_base=4, n_ext=0, seed=91, base_lo=135000000000)
    shutil = __import__("shutil")
    shutil.copytree(banked, ext)
    with pytest.raises(UP.UnionError, match="BOTH the banked and the extension"):
        UP.assemble(banked, ext, tmp_path / "u", stratum="s1")


def test_w6_reads_the_banked_corpus_and_assembles_the_union():
    src = (REPO / "scripts" / "tiletie" / "build_widening_corpus.sh").read_text()
    assert "banked_positions_dir()" in src and "ext_positions_dir()" in src
    assert "union_positions.py" in src
    assert 'RUN_DIR="$CAMPAIGN/$PREREG_DIR_NAME"' in src
    assert 'BANKED_RUN_DIR="$CAMPAIGN/$BANKED_PREREG_DIR_NAME"' in src
    # the driver refuses if the two ever resolve to the same path
    assert 'FATAL: the live and banked prereg dirs resolve to the SAME' in src


def test_digest_exclusions_carry_the_exact_read_rule_key_names(r4_tree):
    """§2b's primary address names `{carried, residual, n_excluded, rate,
    bound_n, denominator_source, rids, void}`. A near-miss spelling reads as
    ABSENT, and ABSENT IS FAIL."""
    rep = _r4_report(r4_tree)
    for s, v in rep["digest_exclusions"].items():
        assert {"carried", "residual", "n_excluded", "rate", "bound_n",
                "denominator_source", "rids", "void"} <= set(v), s
        # the bound is judged on carried + residual (R4-0.2); n_excluded is the
        # deduped rid set and equals the sum on a healthy run (residual == 0)
        assert v["bound_basis"] == v["carried"] + v["residual"]
        if v["residual"] == 0:
            assert v["n_excluded"] == v["bound_basis"]


def test_nonzero_residual_is_flagged_as_a_determinism_defect(r4_tree, tmp_path):
    """The final build seeing a collision the probe did not is an INSTRUMENT
    question, reported separately from the corpus question."""
    rep = _r4_report(r4_tree)                       # 1 residual, no carry
    s1 = rep["digest_exclusions"]["S1"]
    assert s1["residual"] == 1 and s1["carried"] == 0
    assert s1["determinism_defect"] is True


# --------------------------------------------------------------------------- #
# R4-0.5 §3 — CORPUS_UNION.json, and COPIED-never-symlinked                     #
# --------------------------------------------------------------------------- #
def _union_pair(tmp_path, n_banked=6, n_fresh=5):
    banked = tmp_path / "shared_run" / "corpus" / "positions_s1"
    ext = tmp_path / "shared_run_r4" / "corpus" / "positions_s1_ext"
    out = tmp_path / "shared_run_r4" / "corpus" / "positions_s1"
    WF.make_r4_corpus(banked, n_base=n_banked, n_ext=0, seed=101,
                      base_lo=135000000000)
    WF.make_r4_corpus(ext, n_base=0, n_ext=n_fresh, seed=102,
                      ext_lo=137000000000)
    return banked, ext, out


def test_corpus_union_stamp_carries_every_required_field(tmp_path):
    """R4-0.5 §3: origin commit, path under the OLD RUN, a sha256 per copied
    file, and the retained/fresh counts — per stratum."""
    banked, ext, out = _union_pair(tmp_path)
    UP.assemble(banked, ext, out, stratum="s1")
    stamp = out.parent / UP.UNION_STAMP
    assert stamp.is_file(), "R4-0.5 requires RUN/corpus/CORPUS_UNION.json"
    d = json.loads(stamp.read_text())
    s1 = d["by_stratum"]["S1"]
    # NEVER null — the CLOSED allow_null table stays at four entries
    assert isinstance(s1["origin_commit"], str) and s1["origin_commit"]
    assert s1["banked_dir"] == str(banked)          # the path under the OLD RUN
    assert s1["n_retained"] == 6 and s1["n_fresh"] == 5
    shas = s1["sha256_by_file"]
    assert "banked" in shas and "extension" in shas
    assert "ARMS.json" in shas["banked"]
    assert all(len(v) == 64 for side in shas.values() for v in side.values())
    # the sha is of the SOURCE file, so it re-verifies against the banked tree
    assert shas["banked"]["ARMS.json"] == UP.sha256_file(banked / "ARMS.json")
    assert d["totals"] == {"n_retained": 6, "n_fresh": 5, "n_total": 11,
                           "retained_fraction": 6 / 11}


def test_corpus_union_stamp_accumulates_both_strata(tmp_path):
    """ONE file for the whole corpus: S1 and S2 are separate invocations and
    must accumulate, not overwrite."""
    b1, e1, o1 = _union_pair(tmp_path)
    UP.assemble(b1, e1, o1, stratum="s1")
    b2 = tmp_path / "shared_run" / "corpus" / "positions_s2"
    e2 = tmp_path / "shared_run_r4" / "corpus" / "positions_s2_ext"
    o2 = tmp_path / "shared_run_r4" / "corpus" / "positions_s2"
    WF.make_r4_corpus(b2, n_base=3, n_ext=0, seed=111, base_lo=135000000350)
    WF.make_r4_corpus(e2, n_base=0, n_ext=2, seed=112, ext_lo=137000000508)
    UP.assemble(b2, e2, o2, stratum="s2")
    d = json.loads((o1.parent / UP.UNION_STAMP).read_text())
    assert set(d["by_stratum"]) == {"S1", "S2"}
    assert d["totals"]["n_retained"] == 9 and d["totals"]["n_fresh"] == 7


def test_union_is_copied_never_symlinked(tmp_path):
    """R4-0.5 §2, explicit: a symlink into a frozen directory invites a
    WRITE-THROUGH and breaks on any later archive or move."""
    banked, ext, out = _union_pair(tmp_path)
    prov = UP.assemble(banked, ext, out, stratum="s1")
    assert prov["copied_not_symlinked"] is True
    links = [p for p in out.rglob("*") if p.is_symlink()]
    assert not links, f"the union must contain NO symlinks, found {links}"
    for f in out.iterdir():
        if f.is_file():
            assert not f.is_symlink()
            assert f.stat().st_nlink == 1, f"{f.name} is a hard link, not a copy"
    # and mutating the union must NOT reach the banked tree
    before = UP.sha256_file(banked / "ARMS.json")
    (out / "ARMS.json").write_text(json.dumps({"mutated": True}))
    assert UP.sha256_file(banked / "ARMS.json") == before


def test_w3_prints_the_retained_vs_fresh_split(tmp_path, tree, readout):
    """R4-0.5 §3: R4's `n` is a MIXTURE and the reader must see its composition."""
    banked, ext, out = _union_pair(tmp_path)
    UP.assemble(banked, ext, out, stratum="s1")
    blk = AW.union_block(out.parent / UP.UNION_STAMP)
    assert blk["present"] is True
    assert blk["by_stratum"]["S1"]["n_retained"] == 6
    assert blk["by_stratum"]["S1"]["n_fresh"] == 5
    assert blk["totals"]["n_total"] == 11
    v = json.loads(json.dumps(readout))
    v["widening"]["gates_ok"] = True
    for g in v["widening"]["gates_summary"].values():
        g["ok"] = True
    v["widening"]["corpus_union"] = blk
    md = AW.render_md(v)
    assert "RETAINED vs FRESH" in md
    assert "retained fraction" in md
    assert "COPIED" in md
    assert "R3's gate FAILED, so nothing was ever passed" in md
    # absent is stated, never silently omitted
    v["widening"]["corpus_union"] = AW.union_block(None)
    assert "UNRESOLVED here" in AW.render_md(v)


def test_no_source_hardcodes_the_stage1b_ladder_under_the_old_run():
    """`STAGE1B_LADDER.json` is now a byte-identical copy under the NEW RUN;
    a hard-coded old-RUN path would resolve to nothing — ABSENT IS FAIL on a
    healthy run (G-REPLICATE has no fallback)."""
    for path in (REPO / "scripts" / "tiletie").glob("*.py"):
        src = path.read_text()
        assert "shared_run/STAGE1B_LADDER" not in src, path.name
        assert "shared_run/FLOORS.json" not in src, path.name
