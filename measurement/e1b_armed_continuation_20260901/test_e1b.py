#!/usr/bin/env python3
"""Contract tests for the E-1b ARMED-CONTINUATION instrument.

§1 pins the pairing arithmetic and the mover-sign convention on hand fixtures;
§2 the CRN world-seeding property (no arm term, no POLICY term); §3 the SCOPE
WITNESS; §4 the frozen constants against PREREG.md and the inherited target set;
§5 the estimator and the family-paired secondary; §6 ⭐ the REAL-EMITTER
fixtures.

⚠️⚠️ **FIXTURE DISCIPLINE (three realized incidents in this program).** §6's
fixtures in `selftest_fixture/` are the **actual output of the real emitter** —
four `unit_*.json` files and the `manifest.json` that `continue_armed.py` wrote
during the pre-freeze smoke, copied byte-for-byte. Nothing in §6 is a
hand-encoded expectation of what the emitter "should" produce, and the tests
address the real NESTED shapes (`arms.<arm>.witness`, `arms.<arm>.jr_expansions`,
`arms.<arm>.scope_witness`, `arms.<arm>.arming_resolved`, `pair.crn_witness`,
`baseline_e1a`) rather than a flattened idealisation of them. The synthetic
fixtures in §1/§5 are deliberately kept for ARITHMETIC only, where the emitter
has no say.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

D = Path(__file__).resolve().parent
FIX = D / "selftest_fixture"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, D / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CA = _load("continue_armed")
AD = _load("adjudicate_e1b")


def arm(margin, **w):
    base = {"root_repr_sha": "R", "world_deck_sha": "W", "world_deck_len": 30,
            "n_drawn_prefix": 40, "n_legal_root": 12,
            "det_seed_base_at_root": 999, "move_idx_at_root": 40}
    base.update(w)
    return {"status": "OK", "margin_p0_minus_p1": margin, "witness": base,
            "jr_expansions": {"total": 100, "own_mover": 60, "boosted": 40}}


def BL(**w):
    base = {"root_repr_sha": "R", "world_deck_sha": "W", "world_deck_len": 30,
            "n_drawn_prefix": 40, "n_legal_root": 12,
            "det_seed_base_at_root": 999, "move_idx_at_root": 40}
    base.update(w)
    return base


# --------------------------------------------------------------------------- #
# §1 the pairing arithmetic — hand fixtures                                     #
# --------------------------------------------------------------------------- #
def test_seat0_mover_sign_positive_when_owner_arm_scores_more():
    r = CA.pair_price(arm(7), arm(2), actor=0, baseline=BL())
    assert r["status"] == "OK"
    assert r["delta_pts_mover"] == 5


def test_seat1_mover_sign_is_negated():
    r = CA.pair_price(arm(7), arm(2), actor=1, baseline=BL())
    assert r["delta_pts_mover"] == -5


def test_identical_arms_price_to_exactly_zero_at_both_seats():
    for actor in (0, 1):
        assert CA.pair_price(arm(4), arm(4), actor=actor,
                             baseline=BL())["delta_pts_mover"] == 0


def test_antisymmetry_of_the_mover_sign():
    a = CA.pair_price(arm(9), arm(-3), actor=0, baseline=BL())
    b = CA.pair_price(arm(9), arm(-3), actor=1, baseline=BL())
    assert a["delta_pts_mover"] == -b["delta_pts_mover"]


@pytest.mark.parametrize("field", CA.CRN_WITNESS_KEYS)
def test_any_crn_witness_mismatch_voids_the_pair(field):
    bad = {field: "DIFFERENT" if isinstance(arm(0)["witness"][field], str) else 12345}
    r = CA.pair_price(arm(7), arm(2, **bad), actor=0, baseline=BL())
    assert r["status"] == "VOID" and r["reason"] == "crn_witness_mismatch"
    assert field in r["fields"]


@pytest.mark.parametrize("bad", ["TIME_SKIPPED", "OOM_SKIPPED", "ERROR"])
def test_a_skipped_arm_voids_the_pair_on_either_side(bad):
    assert CA.pair_price({"status": bad}, arm(2), 0, baseline=BL())["status"] == "VOID"
    assert CA.pair_price(arm(2), {"status": bad}, 0, baseline=BL())["status"] == "VOID"


# ⭐ the E-1b-specific voids
def test_a_root_that_is_not_e1a_s_root_voids_the_pair():
    r = CA.pair_price(arm(7), arm(2), actor=0,
                      baseline=BL(root_repr_sha="SOMETHING_ELSE"))
    assert r["status"] == "VOID" and r["reason"] == "root_identity_mismatch"
    assert r["fields"] == ["root_repr_sha"]


def test_an_absent_baseline_voids_the_pair_rather_than_passing():
    """ABSENT is FAIL: without an E-1a sibling there is no single-variable proof."""
    r = CA.pair_price(arm(7), arm(2), actor=0, baseline=None)
    assert r["status"] == "VOID" and r["reason"] == "baseline_absent"


def test_an_unexpressed_arming_voids_the_pair():
    dead = arm(7)
    dead["jr_expansions"] = {"total": 100, "own_mover": 60, "boosted": 0}
    r = CA.pair_price(dead, arm(2), actor=0, baseline=BL())
    assert r["status"] == "VOID" and r["reason"] == "arm_witness_failed"


# --------------------------------------------------------------------------- #
# §2 the world seeding — no arm term AND no policy term                         #
# --------------------------------------------------------------------------- #
def test_world_rng_has_no_arm_term_so_both_arms_get_one_permutation():
    a = [CA.world_rng(1234, 40, 3).random() for _ in range(5)]
    b = [CA.world_rng(1234, 40, 3).random() for _ in range(5)]
    assert a == b


def test_world_seed_is_e1a_s_or_the_crn_across_families_is_broken():
    """⛔ WORLD_SEED is INHERITED. A different value silently re-worlds every
    unit and G-ROOT would fail on all 728 — which is the point of freezing it
    here as a test rather than as a comment."""
    e1a = _load("../e4_continuation_20260828/continue_plies".replace("/", "_")) \
        if False else None
    src = (D.parent / "e4_continuation_20260828" / "continue_plies.py").read_text()
    m = re.search(r"^WORLD_SEED\s*=\s*(\d+)", src, re.M)
    assert m and int(m.group(1)) == CA.WORLD_SEED
    for const in ("CONTINUATION_SEED", "M_WORLDS"):
        m = re.search(rf"^{const}\s*=\s*(\d+)", src, re.M)
        assert m and int(m.group(1)) == getattr(CA, const)


def test_distinct_worlds_give_distinct_permutations():
    outs = {tuple(sorted([CA.world_rng(99, 10, w).random() for _ in range(3)]))
            for w in range(8)}
    assert len(outs) == 8


# --------------------------------------------------------------------------- #
# §3 THE SCOPE WITNESS                                                          #
# --------------------------------------------------------------------------- #
def test_scope_denominator_partitions_the_census():
    c = {"total": 100, "own_mover": 60}
    assert CA.scope_denominator(c, "own") == 60
    assert CA.scope_denominator(c, "opp") == 40
    assert CA.scope_denominator(c, "all") == 100


def test_a_live_opp_census_passes():
    w = CA.scope_witness({"total": 100, "own_mover": 60, "boosted": 40}, "opp")
    assert w["ok"] and w["coverage"] == 1.0 and w["exact_partition"]


def test_an_absent_census_is_a_hard_failure_not_zeros():
    """A stale (pre-R7) wheel must never read as 'the arm did not boost'."""
    w = CA.scope_witness(None, "opp")
    assert not w["ok"] and "census_absent_stale_wheel" in w["failures"]
    w = CA.scope_witness({"total": 1, "own_mover": 0}, "opp")
    assert not w["ok"] and any("missing_keys" in f for f in w["failures"])


def test_boosted_zero_fails_the_witness():
    w = CA.scope_witness({"total": 100, "own_mover": 60, "boosted": 0}, "opp")
    assert not w["ok"]
    assert any("never_expressed" in f for f in w["failures"])


def test_boost_outside_the_scope_fails_the_witness():
    w = CA.scope_witness({"total": 100, "own_mover": 60, "boosted": 41}, "opp")
    assert not w["ok"] and any("outside_scope" in f for f in w["failures"])


def test_partial_coverage_is_advisory_not_a_failure():
    """⛔ PG-A1: terminal / no-legal-child expansions legitimately boost nothing,
    so a HARD equality here would void healthy cells."""
    w = CA.scope_witness({"total": 100, "own_mover": 60, "boosted": 5}, "opp")
    assert w["ok"] and w["coverage"] == 0.125 and not w["exact_partition"]


def test_an_unarmed_side_would_fail_the_armed_witness():
    """The champion's all-zero census is the HEALTHY shape for an UNARMED side
    and a FAILURE for an armed one — the two must not wear the same shape."""
    assert not CA.scope_witness({"total": 0, "own_mover": 0, "boosted": 0},
                                "opp")["ok"]


# --------------------------------------------------------------------------- #
# §4 the frozen constants and the inherited target set                          #
# --------------------------------------------------------------------------- #
def test_prereg_constants_match_the_code():
    p = (D / "PREREG.md").read_text()
    for const, val in (("WORLD_SEED", CA.WORLD_SEED),
                       ("CONTINUATION_SEED", CA.CONTINUATION_SEED),
                       ("M_WORLDS", CA.M_WORLDS),
                       ("ARM_WALL_CAP_S", CA.ARM_WALL_CAP_S),
                       ("ARM_DOSE", CA.ARM_DOSE),
                       ("ARM_MASK", CA.ARM_MASK),
                       ("PINNED_K_DETS", CA.PINNED_K_DETS),
                       ("PINNED_SIMS_PER_DET", CA.PINNED_SIMS_PER_DET),
                       ("PINNED_EXACT_K", CA.PINNED_EXACT_K)):
        assert re.search(rf"^{const}\s*=\s*{val}\b", p, re.M), const
    assert re.search(r'^ARM_SCOPE\s*=\s*"opp"', p, re.M)
    assert CA.LEAF_HASH_OF_RECORD in p


def test_the_adjudicator_and_the_runner_agree_on_the_frozen_arming():
    assert (AD.ARM_DOSE, AD.ARM_MASK, AD.ARM_SCOPE) == \
           (CA.ARM_DOSE, CA.ARM_MASK, CA.ARM_SCOPE)
    assert (AD.PINNED_K_DETS, AD.PINNED_SIMS_PER_DET, AD.PINNED_EXACT_K) == \
           (CA.PINNED_K_DETS, CA.PINNED_SIMS_PER_DET, CA.PINNED_EXACT_K)
    assert AD.M_WORLDS == CA.M_WORLDS
    assert AD.LEAF_HASH_OF_RECORD == CA.LEAF_HASH_OF_RECORD


def test_the_bar_is_stated_in_the_prereg_and_is_not_two_sigma_of_the_instrument():
    p = (D / "PREREG.md").read_text()
    assert f"BAR_REOPEN = +{AD.BAR_REOPEN}" in p
    # the bar must NOT equal 2 * E-1a's realized se (that is the defect the
    # 2026-08-30 owner ruling names)
    assert abs(AD.BAR_REOPEN - 2 * AD.E1A["primary_se"]) > 0.2


def test_targets_are_byte_identical_to_the_frozen_e1a_set():
    mine = (D / "targets_continuation.jsonl").read_bytes()
    theirs = (D.parent / "e4_continuation_20260828"
              / "targets_continuation.jsonl").read_bytes()
    assert mine == theirs


def test_the_target_set_is_the_91_divergent_plies_in_38_games():
    rows = [json.loads(l) for l in (D / "targets_continuation.jsonl").open()]
    assert len(rows) == AD.N_TARGET_PLIES == 91
    assert len({r["game"] for r in rows}) == 38
    assert all(r["played_action"] != r["counterfactual_action"] for r in rows)
    from collections import Counter
    assert Counter(r["stratum"] for r in rows) == {
        "control": 30, "defense": 28, "invasion": 21, "farm_capture": 12}


def test_the_baseline_covers_every_target_ply_at_every_world():
    b = json.loads((D / "CRN_BASELINE.json").read_text())
    assert b["n_units"] == AD.N_TARGET_UNITS == 728
    assert b["n_plies"] == 91
    rows = [json.loads(l) for l in (D / "targets_continuation.jsonl").open()]
    for r in rows:
        for w in range(CA.M_WORLDS):
            k = f"{r['game']}|{r['ply']}|{w}"
            assert k in b["units"], k
            assert set(CA.CRN_WITNESS_KEYS) <= set(b["units"][k]["witness"])


def test_the_baseline_quotes_e1a_s_adjudicated_primary():
    b = json.loads((D / "CRN_BASELINE.json").read_text())
    p = b["banked_verdict"]["PRIMARY_invasion_minus_control"]
    assert math.isclose(p["diff"], AD.E1A["primary_diff"], rel_tol=1e-12)
    assert math.isclose(p["se"], AD.E1A["primary_se"], rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# §5 the estimator + the family-paired secondary                                #
# --------------------------------------------------------------------------- #
def _ply(game, stratum, price, price_e1a=None):
    return {"game": game, "ply": 1, "stratum": stratum, "price": price,
            "price_e1a": price_e1a,
            "price_delta_family": (None if price_e1a is None
                                   else price - price_e1a)}


def test_cluster_robust_se_uses_games_not_plies():
    """Two plies in ONE game that agree perfectly contribute ZERO variance;
    treating them as independent draws would not."""
    same = [_ply("g1", "x", 4.0), _ply("g1", "x", 4.0)]
    s = AD.cluster_stats(same)
    assert s["n"] == 2 and s["n_clusters"] == 1 and s["mean"] == 4.0
    assert s["se"] == 0.0


def test_cluster_se_is_positive_across_games():
    s = AD.cluster_stats([_ply("g1", "x", 0.0), _ply("g2", "x", 8.0)])
    assert s["n_clusters"] == 2 and s["se"] > 0


def test_contrast_is_a_difference_of_means():
    a = [_ply("g1", "i", 5.0), _ply("g2", "i", 3.0)]
    b = [_ply("g3", "c", 1.0), _ply("g4", "c", 1.0)]
    c = AD.contrast(a, b)
    assert math.isclose(c["diff"], 3.0)
    assert c["n_clusters"] == 4 and c["n_shared_clusters"] == 0


def test_a_shared_game_cluster_is_paired_not_independent():
    a = [_ply("g1", "i", 5.0), _ply("g2", "i", 3.0)]
    b = [_ply("g1", "c", 5.0), _ply("g2", "c", 3.0)]
    c = AD.contrast(a, b)
    assert c["n_shared_clusters"] == 2
    assert math.isclose(c["diff"], 0.0, abs_tol=1e-12) and c["se"] == 0.0


def test_the_family_delta_is_computed_on_the_declared_field():
    a = [_ply("g1", "i", 2.0, -6.0), _ply("g2", "i", 0.0, -8.0)]
    b = [_ply("g3", "c", 1.0, 1.0), _ply("g4", "c", -1.0, -1.0)]
    c = AD.contrast(a, b, field="price_delta_family")
    assert math.isclose(c["diff"], 8.0)


def test_collapse_worlds_pairs_the_family_delta_on_the_SAME_world_set():
    """⛔ A world E-1b voided must not enter one side of the paired difference
    and not the other, so `price_e1a` is None unless every landed world has an
    E-1a sibling."""
    def row(w, ok, delta, e1a):
        return {"game": "g", "ply": 3, "stratum": "invasion", "actor": 0,
                "world": w,
                "pair": ({"status": "OK", "delta_pts_mover": delta} if ok
                         else {"status": "VOID", "reason": "arm_not_ok"}),
                "baseline_e1a": (None if e1a is None
                                 else {"delta_pts_mover": e1a})}
    good = AD.collapse_worlds([row(0, True, 4, 1), row(1, True, 6, 3)])[0]
    assert good["price"] == 5.0 and good["price_e1a"] == 2.0
    assert good["price_delta_family"] == 3.0
    # a landed world with no sibling -> the paired delta is withheld entirely
    part = AD.collapse_worlds([row(0, True, 4, 1), row(1, True, 6, None)])[0]
    assert part["price"] == 5.0 and part["price_e1a"] is None
    assert part["price_delta_family"] is None
    # a VOID world drops out of BOTH sides
    vd = AD.collapse_worlds([row(0, True, 4, 1), row(1, False, 6, 3)])[0]
    assert vd["price"] == 4.0 and vd["price_e1a"] == 1.0
    assert vd["m_worlds_void"] == 1


def test_holm_tests_the_larger_z_first_and_gates_the_smaller():
    h = AD.holm([("PRIMARY", {"z": 3.0}), ("SECONDARY_A", {"z": 2.0})])
    assert h["PRIMARY"]["threshold"] == AD.HOLM_STEP1 and h["PRIMARY"]["clears"]
    assert h["SECONDARY_A"]["threshold"] == AD.HOLM_STEP2
    assert h["SECONDARY_A"]["clears"]
    h = AD.holm([("PRIMARY", {"z": 1.0}), ("SECONDARY_A", {"z": 2.1})])
    assert not h["SECONDARY_A"]["clears"]   # 2.1 < 2.2414 at step 1
    assert not h["PRIMARY"]["clears"]       # step 2 never opens


def test_a_null_z_never_clears():
    h = AD.holm([("PRIMARY", {"z": None}), ("SECONDARY_A", {"z": None})])
    assert not any(v["clears"] for v in h.values())


# --------------------------------------------------------------------------- #
# §6 ⭐ THE REAL-EMITTER FIXTURES                                                #
# --------------------------------------------------------------------------- #
FIXTURE_UNITS = sorted(FIX.glob("unit_*.json"))


def test_the_fixture_exists_and_is_the_real_emitter_s_output():
    assert FIXTURE_UNITS, "selftest_fixture/ is empty — regenerate with MODE=smoke"
    man = json.loads((FIX / "manifest.json").read_text())
    assert man["schema"] == AD.SCHEMA
    assert man["arming"]["dose"] == CA.ARM_DOSE
    assert man["arming"]["scope"] == CA.ARM_SCOPE
    assert man["budget_pin"]["k_dets"] == CA.PINNED_K_DETS
    assert man["budget_pin"]["sims_per_det"] == CA.PINNED_SIMS_PER_DET


@pytest.mark.parametrize("f", FIXTURE_UNITS, ids=lambda f: f.name)
def test_every_emitted_unit_carries_the_full_nested_shape(f):
    r = json.loads(f.read_text())
    for k in ("game", "ply", "world", "stratum", "profile", "actor", "phase",
              "r9_env", "continuation_family", "arms", "pair", "baseline_e1a",
              "followup_agrees_with_archive"):
        assert k in r, k
    assert set(r["arms"]) == set(CA.ARMS)
    for a in r["arms"].values():
        assert a["status"] == "OK"
        assert set(CA.CRN_WITNESS_KEYS) <= set(a["witness"])
        assert set(CA.JR_KEYS) == set(a["jr_expansions"])
        assert set(a["arming_resolved"]) >= {"dose", "mask", "scope", "k_dets",
                                             "sims_per_det", "exact_max_k"}
        assert a["scope_witness"]["ok"] is True
    assert r["pair"]["status"] == "OK"
    assert r["pair"]["root_identity_ok"] is True
    assert set(CA.CRN_WITNESS_KEYS) == set(r["pair"]["crn_witness"])


@pytest.mark.parametrize("f", FIXTURE_UNITS, ids=lambda f: f.name)
def test_the_emitted_arming_and_budget_are_the_frozen_ones(f):
    r = json.loads(f.read_text())
    for a in r["arms"].values():
        g = a["arming_resolved"]
        assert (g["dose"], g["mask"], g["scope"]) == (CA.ARM_DOSE, CA.ARM_MASK,
                                                      CA.ARM_SCOPE)
        assert (g["k_dets"], g["sims_per_det"], g["exact_max_k"]) == (
            CA.PINNED_K_DETS, CA.PINNED_SIMS_PER_DET, CA.PINNED_EXACT_K)


@pytest.mark.parametrize("f", FIXTURE_UNITS, ids=lambda f: f.name)
def test_the_emitted_census_is_live_and_inside_its_scope(f):
    r = json.loads(f.read_text())
    for a in r["arms"].values():
        c = a["jr_expansions"]
        assert c["boosted"] > 0
        assert 0 <= c["own_mover"] <= c["total"]
        assert c["boosted"] <= c["total"] - c["own_mover"]
        assert CA.scope_witness(c, CA.ARM_SCOPE)["ok"]


@pytest.mark.parametrize("f", FIXTURE_UNITS, ids=lambda f: f.name)
def test_the_emitted_witness_reproduces_the_e1a_baseline_exactly(f):
    """⭐ G-ROOT on real data: E-1b landed on E-1a's exact roots and worlds."""
    r = json.loads(f.read_text())
    b = json.loads((D / "CRN_BASELINE.json").read_text())["units"]
    key = f"{r['game']}|{r['ply']}|{r['world']}"
    assert key in b
    assert r["pair"]["crn_witness"] == b[key]["witness"]
    assert r["baseline_e1a"]["delta_pts_mover"] == b[key]["delta_pts_mover"]


def test_the_adjudicator_passes_its_smoke_gates_on_the_real_fixture():
    rows = [json.loads(f.read_text()) for f in FIXTURE_UNITS]
    man = json.loads((FIX / "manifest.json").read_text())
    plies = AD.collapse_worlds(rows)
    gates = [AD.gate_manifest(man, "fix"), AD.gate_leaf(man, "fix"),
             AD.gate_negctrl(man, "fix"), AD.gate_witness(rows),
             AD.gate_arming(rows), AD.gate_budget(rows), AD.gate_root(rows),
             AD.gate_rules(rows, [{"game": r["game"], "ply": r["ply"],
                                   "profile": r["profile"]} for r in rows]),
             AD.gate_void(plies, rows)]
    bad = [g for g in gates if g["status"] != "PASS"]
    assert not bad, bad


def test_a_stale_wheel_shape_on_the_real_fixture_fails_g_witness():
    """Mutate the REAL emitter output rather than hand-building the defect."""
    rows = [json.loads(f.read_text()) for f in FIXTURE_UNITS]
    rows[0]["arms"]["arm_owner"]["jr_expansions"] = None
    rows[0]["arms"]["arm_owner"]["scope_witness"] = CA.scope_witness(None, "opp")
    assert AD.gate_witness(rows)["status"] == "FAIL"


def test_a_yaml_budget_drift_on_the_real_fixture_fails_g_budget():
    rows = [json.loads(f.read_text()) for f in FIXTURE_UNITS]
    rows[0]["arms"]["arm_cf"]["arming_resolved"]["k_dets"] = 16
    assert AD.gate_budget(rows)["status"] == "FAIL"
    assert AD.gate_arming(rows)["status"] == "PASS"   # ⭐ a DIFFERENT gate owns it


def test_the_manifest_records_the_production_yaml_drift_rather_than_hiding_it():
    man = json.loads((FIX / "manifest.json").read_text())
    obs = man["production_yaml_observed"]
    assert obs["k_dets"] is not None and obs["sims_per_det"] is not None
    assert isinstance(obs["drift_vs_pin"], bool)
    assert man["negative_control"]["ok"] is True
    z = man["negative_control"]["unarmed_dose0"]["census"]
    assert all(z[k] == 0 for k in CA.JR_KEYS)
    assert man["negative_control"]["armed_dose_dstar"]["census"]["boosted"] > 0


def test_the_smoke_validation_artifact_is_a_pass_with_no_failures():
    v = json.loads((FIX / "SMOKE_VALIDATION.json").read_text())
    assert v["PASS"] is True and v["failures"] == []
    assert v["n_priced"] == v["n_units"] == len(FIXTURE_UNITS)
    assert set(v["strata"]) == {"invasion", "control", "defense", "farm_capture"}


def test_the_smoke_adjudicator_refuses_an_EMPTY_cell():
    """⛔ THE LAUNCH-BLOCKING DEFECT CLASS: a smoke that 'passes' because it
    measured nothing. `--smoke` must exit NONZERO."""
    man = json.loads((FIX / "manifest.json").read_text())
    with pytest.raises(SystemExit) as e:
        AD.smoke_adjudicate([], man, "fix")
    assert e.value.code == 3


def test_the_smoke_adjudicator_refuses_a_cell_with_no_priced_pair():
    rows = [json.loads(f.read_text()) for f in FIXTURE_UNITS]
    for r in rows:
        r["pair"] = {"status": "VOID", "reason": "arm_not_ok"}
    man = json.loads((FIX / "manifest.json").read_text())
    with pytest.raises(SystemExit) as e:
        AD.smoke_adjudicate(rows, man, "fix")
    assert e.value.code == 3


def test_the_smoke_adjudicator_refuses_an_ABSENT_manifest():
    rows = [json.loads(f.read_text()) for f in FIXTURE_UNITS]
    with pytest.raises(SystemExit):
        AD.smoke_adjudicate(rows, None, "fix")


# --------------------------------------------------------------------------- #
# §7 the adjudicator's own selftest is a test                                   #
# --------------------------------------------------------------------------- #
def test_adjudicator_selftest_passes():
    assert AD.selftest() == 0
