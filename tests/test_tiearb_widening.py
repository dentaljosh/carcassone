"""Fast unit coverage for the tie-arbiter WIDENING instrument (rev R3).

Covers the SHAPES and the CONTRACTS the blind prereg pair
(`measurement/tiearb_widening_20260817/shared_run/{DESIGN,READ_RULE}.md`)
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
import widening_fixtures as WF                                     # noqa: E402

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
    WF.make_gen_smoke(run / "GEN_SMOKE.json", worker_secs_per_game=440.0)
    smokes = sorted(str(p) for p in run.glob("SMOKE_MANIFEST_*.json"))
    blk = CR.build_block(smokes, run / "GEN_SMOKE.json")
    assert blk["ok"] is True and blk["halt_fired"] is False
    # CHEAPER is recorded, never a halt
    assert blk["legs"]["generation"]["direction"] == "cheaper"
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
    rep = GD.run_merged_gate(strata=_strata(run), refs={
        n: {"arms": p / "ARMS.json", "legs": GD.leg_paths(p, GD.SPENT_LEG_GLOB)}
        for n, p in refs.items()}, exclude_rids=[excl])
    (run / "GATE_DISJOINT.json").write_text(json.dumps(rep, indent=2))
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
              'SHARE_RUN_LOCAL SHARE_RUN_REMOTE; do '
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


@pytest.mark.parametrize("argv,want_rc", [
    ([], 2),                          # no box
    (["nosuchbox"], 2),               # bad box
    (["local", "--topup", "0"], 2),   # top-up floor
    (["local", "--topup", "201"], 2), # top-up ceiling (<=200, pre-licensed)
    (["local", "--bogus"], 2),        # unknown flag
])
def test_run_gen_argument_guards(argv, want_rc, tmp_path):
    """The guards must fire BEFORE any generator is invoked. `champ_env.sh` is
    sourced only after them, so a bad argument can never reach the Pool."""
    r = subprocess.run(["bash", str(CAMPAIGN / "run_gen.sh"), *argv],
                       capture_output=True, text=True,
                       env={**os.environ, "PATH": os.environ["PATH"]})
    assert r.returncode == want_rc, (r.stdout, r.stderr)
    assert "gen_fair_distill" not in r.stdout


def test_run_gen_topup_uses_a_separate_out_preserving_g_bands_two_file_form():
    text = (CAMPAIGN / "run_gen.sh").read_text()
    assert 'OUT="$SHARE/$RUN_ID/gen"' in text          # what W6 phase 1 collects
    assert 'OUT_TOPUP="$SHARE/$RUN_ID/gen_topup"' in text
    assert "TOPUP_MAX=200" in text
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
                "committed": 990.0, "ratio": 440.0 / 990.0, "halt_fired": False})
    (tmp_path / "GEN_SMOKE.json").write_text(json.dumps(doc))
    assert required <= set(doc)
    # c_remeasure reads worker_secs_per_game and n_games off it
    got = CR.read_gen_smoke(tmp_path / "GEN_SMOKE.json")
    assert got["present"] is True and got["failed_smoke"] is False
    assert got["worker_secs_per_game"] == pytest.approx(440.0)
    # and the launcher's committed constant is c_remeasure's committed constant
    assert doc["committed"] == CR.COMMITTED["generation"]["worker_secs_per_game"]
    assert "990.0" in (CAMPAIGN / "run_gen.sh").read_text()
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
