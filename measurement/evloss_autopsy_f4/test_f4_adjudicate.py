#!/usr/bin/env python3
"""Contract tests for the NEW F4 arithmetic (`F4_PREREG.md` §4–§6).

Nothing here tests the R1/R2 estimator — that is imported verbatim and is already covered by
`measurement/evloss_autopsy_r2/test_r2_taxonomy.py`. What is tested is what F4 adds:
the same-arm cross-judge witness, the half-split (selection-unbiased) witness, the
agreement statistics, the two verdict enums and every instrument gate.

Run:  python -m pytest measurement/evloss_autopsy_f4/test_f4_adjudicate.py -q
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f4_adjudicate as F4                                          # noqa: E402

M = 8                                   # small world count for the fixtures
SALT = "evloss-autopsy-20260824-v1"


# --------------------------------------------------------------------------- #
# fixtures — a two-judge corpus on disk                                        #
# --------------------------------------------------------------------------- #
def _rec(rid, arm, delta, per_world, *, ok=True, crn=True, salt=SALT,
         seeds=None, profile="walled", deck_a=None, deck_b=None):
    return {
        "rid": rid, "delta": float(delta), "per_world_delta": list(per_world),
        "m": len(per_world), "ok": ok, "crn_verified": crn,
        "rules_profile": profile, "world_seed_salt": salt,
        "world_seeds": seeds if seeds is not None else [hash((rid, j)) % 10**9
                                                        for j in range(len(per_world))],
        "afterstate_deck_hash_a": deck_a or [f"{rid}-a"] * len(per_world),
        "afterstate_deck_hash_b": deck_b or [f"{rid}-{arm}-b"] * len(per_world),
        "pick_a": 1, "pick_b": 100 + F4.ARMS.index(arm),
    }


def _write_leg(root: Path, leg, recs, *, manifest=True, policy="clair-puct",
               backend="rust"):
    d = root / leg / "records"
    d.mkdir(parents=True, exist_ok=True)
    for r in recs:
        (d / f"{r['rid']}.json").write_text(json.dumps(r))
    if manifest:
        # the REAL shape oracle_score_pilot.build_manifest writes (D-F4-10): the policy
        # lives at `oracle.policy`, the engine at `execution.backend`.
        (root / leg / "manifest.json").write_text(json.dumps(
            {"oracle": {"policy": policy,
                        "policy_family": ("OUT-OF-FAMILY: no search"
                                          if policy == "tier1-greedy"
                                          else "IN-FAMILY with the agents under test")},
             "execution": {"backend": backend}}))


def _tax():
    return {"stratum": "FARM", "structure": "farm", "degenerate": False,
            "decision_type": "meeple", "phase_third": "endgame",
            "move_kind_best": "farm", "move_kind_played": "farm",
            "commit_direction": "spend", "meeple_axis": None,
            "contested_best": ["farm"], "contested_played": [],
            "reinforce_losing_contest_best": False,
            "reinforce_losing_contest_played": False,
            "tie_force_join_best": True, "tie_force_join_played": False,
            "farm_share": 0.9, "cross_world_spread": 0.1,
            "cross_world_spread_status": "ok_per_world_routeb"}


@pytest.fixture
def corpus(tmp_path):
    """4 positions x 2 arms x 2 judges. Position i's clair argmax is `sib2` for all;
    the tier1 judge agrees on 3 of 4."""
    pos = tmp_path / "positions"
    pos.mkdir()
    meta = []
    for i in range(4):
        meta.append({"rid": f"r{i}", "game_id": 900 + i, "ply": 10 + i,
                     "ht_weight": 2.0, "pi_s": 0.5,
                     "arms": {"leaf": 1, "sib2": 2}, "n_arms_available": 2,
                     "in_rnd_subset": False, "taxonomy": _tax()})
    (pos / "positions_meta.jsonl").write_text(
        "\n".join(json.dumps(m) for m in meta) + "\n")

    C, T = tmp_path / "judge", tmp_path / "judge_t1"
    # clair: sib2 always the argmax (delta +2), leaf negative (-1)
    _write_leg(C, "leaf", [_rec(f"r{i}", "leaf", -1.0, [-1.0] * M) for i in range(4)])
    _write_leg(C, "sib2", [_rec(f"r{i}", "sib2", 2.0, [2.0] * M) for i in range(4)])
    # tier1: agrees (+1) on r0,r1,r2 and disagrees (-3) on r3
    t1_sib2 = [1.0, 1.0, 1.0, -3.0]
    _write_leg(T, "leaf", [_rec(f"r{i}", "leaf", -0.5, [-0.5] * M) for i in range(4)],
               policy="tier1-greedy", backend="python")
    _write_leg(T, "sib2", [_rec(f"r{i}", "sib2", t1_sib2[i], [t1_sib2[i]] * M)
                           for i in range(4)],
               policy="tier1-greedy", backend="python")
    return {"tmp": tmp_path, "positions": pos, "clair": C, "t1": T}


# --------------------------------------------------------------------------- #
# 1. the witness (§4.1)                                                        #
# --------------------------------------------------------------------------- #
def test_witness_is_the_tier1_delta_at_the_clair_argmax_arm(corpus):
    rows, _, _ = F4.build_f4_rows(corpus["positions"], corpus["clair"], corpus["t1"])
    assert len(rows) == 4
    by = {r["rid"]: r for r in rows}
    for rid in ("r0", "r1", "r2"):
        assert by[rid]["a_star_clair"] == "sib2"
        assert by[rid]["witness"] == pytest.approx(1.0)
    assert by["r3"]["witness"] == pytest.approx(-3.0)


def test_witness_is_not_clipped_at_zero(corpus):
    """The whole point: R_champ is max(0,.) and so cannot carry a sign; the witness can."""
    rows, _, _ = F4.build_f4_rows(corpus["positions"], corpus["clair"], corpus["t1"])
    by = {r["rid"]: r for r in rows}
    assert by["r3"]["R_champ"] == pytest.approx(2.0)        # clair, clipped, positive
    assert by["r3"]["R_champ_t1"] == pytest.approx(0.0)     # tier1, clipped -> 0
    assert by["r3"]["witness"] < 0                          # unclipped -> negative


def test_r_champ_side_reproduces_r2_construction(corpus):
    """The clair-puct half of a row must be `r2_taxonomy.build_rows`, field for field —
    that is what gate g5 leans on."""
    rows, _, _ = F4.build_f4_rows(corpus["positions"], corpus["clair"], corpus["t1"])
    for r in rows:
        assert r["R_champ"] == pytest.approx(2.0)
        assert r["G_search"] == pytest.approx(1.0)          # -d_leaf = -(-1.0)
        assert r["argmax_arm"] == "sib2"


def test_missing_leaf_leg_is_zero_not_missing(tmp_path):
    """PLAN.md A6: an absent `leaf` row means the depth-0 argmax equalled the played
    action, so D_leaf == 0 and G_search == 0."""
    pos = tmp_path / "positions"; pos.mkdir()
    (pos / "positions_meta.jsonl").write_text(json.dumps(
        {"rid": "x", "game_id": 1, "ply": 2, "ht_weight": 1.0,
         "arms": {"sib2": 2}, "in_rnd_subset": False, "taxonomy": _tax()}) + "\n")
    C, T = tmp_path / "judge", tmp_path / "judge_t1"
    _write_leg(C, "sib2", [_rec("x", "sib2", 3.0, [3.0] * M)])
    _write_leg(T, "sib2", [_rec("x", "sib2", 1.0, [1.0] * M)],
               policy="tier1-greedy", backend="python")
    rows, _, _ = F4.build_f4_rows(pos, C, T)
    assert rows[0]["G_search"] == 0.0
    assert rows[0]["leaf_leg_present"] is False


# --------------------------------------------------------------------------- #
# 2. the half-split witness (§4.3)                                             #
# --------------------------------------------------------------------------- #
def test_half_split_selects_on_first_half_and_evaluates_on_second(tmp_path):
    pos = tmp_path / "positions"; pos.mkdir()
    (pos / "positions_meta.jsonl").write_text(json.dumps(
        {"rid": "x", "game_id": 1, "ply": 2, "ht_weight": 1.0,
         "arms": {"leaf": 1, "sib2": 2}, "in_rnd_subset": False,
         "taxonomy": _tax()}) + "\n")
    C, T = tmp_path / "judge", tmp_path / "judge_t1"
    # over ALL 8 worlds sib2 wins (mean 1.0 vs 0.5); over worlds 0..3 LEAF wins (4 vs 0)
    leaf_pw = [8.0, 8.0, 8.0, 8.0, -7.0, -7.0, -7.0, -7.0]     # mean 0.5, first half 8.0
    sib2_pw = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]         # mean 1.0, first half 1.0
    _write_leg(C, "leaf", [_rec("x", "leaf", sum(leaf_pw) / 8, leaf_pw)])
    _write_leg(C, "sib2", [_rec("x", "sib2", 1.0, sib2_pw)])
    # tier1 values: distinguishable per arm and per half
    _write_leg(T, "leaf", [_rec("x", "leaf", 0.0, [0.0] * 4 + [-2.0] * 4)],
               policy="tier1-greedy", backend="python")
    _write_leg(T, "sib2", [_rec("x", "sib2", 5.0, [5.0] * 8)],
               policy="tier1-greedy", backend="python")
    rows, _, _ = F4.build_f4_rows(pos, C, T)
    r = rows[0]
    assert r["a_star_clair"] == "sib2"          # full-32 (here full-8) argmax
    assert r["a_dag"] == "leaf"                 # first-half argmax differs
    assert r["witness"] == pytest.approx(5.0)               # tier1 @ sib2, all worlds
    assert r["witness_split"] == pytest.approx(-2.0)        # tier1 @ leaf, worlds 4..7


def test_half_split_absent_when_per_world_arrays_are_ragged(tmp_path):
    pos = tmp_path / "positions"; pos.mkdir()
    (pos / "positions_meta.jsonl").write_text(json.dumps(
        {"rid": "x", "game_id": 1, "ply": 2, "ht_weight": 1.0,
         "arms": {"sib2": 2}, "in_rnd_subset": False, "taxonomy": _tax()}) + "\n")
    C, T = tmp_path / "judge", tmp_path / "judge_t1"
    _write_leg(C, "sib2", [_rec("x", "sib2", 1.0, [1.0] * M)])
    _write_leg(T, "sib2", [_rec("x", "sib2", 1.0, [1.0] * (M - 1))],
               policy="tier1-greedy", backend="python")
    rows, _, _ = F4.build_f4_rows(pos, C, T)
    assert rows[0]["witness_split"] is None
    assert rows[0]["witness"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# 3. category statistics (§4.2, §4.4, §4.5)                                    #
# --------------------------------------------------------------------------- #
def test_sign_agreement_rate_and_binomial(corpus):
    rows, _, _ = F4.build_f4_rows(corpus["positions"], corpus["clair"], corpus["t1"])
    st = F4.f4_category_stats(rows, [True] * len(rows))
    assert st["sign_agreement_n"] == 4                 # all have R_champ > 0
    assert st["sign_agreement_k"] == 3
    assert st["sign_agreement_rate"] == pytest.approx(0.75)
    assert st["sign_agreement_binom_p"] == pytest.approx(F4._binom_p_one_sided(3, 4))


def test_binomial_one_sided_matches_hand_arithmetic():
    assert F4._binom_p_one_sided(4, 4) == pytest.approx(1 / 16)
    assert F4._binom_p_one_sided(3, 4) == pytest.approx(5 / 16)
    assert F4._binom_p_one_sided(0, 4) == pytest.approx(1.0)


def test_argmax_concordance_and_arm_level_agreement(corpus):
    rows, _, _ = F4.build_f4_rows(corpus["positions"], corpus["clair"], corpus["t1"])
    st = F4.f4_category_stats(rows, [True] * len(rows))
    # tier1 argmax is sib2 on r0-r2 (1.0 > -0.5) but LEAF on r3 (-0.5 > -3.0)
    assert st["argmax_concordance"] == pytest.approx(0.75)
    # 8 arm pairs; leaf agrees 4/4 (both negative), sib2 agrees 3/4
    assert st["arm_pairs_n"] == 8
    assert st["arm_sign_agreement"] == pytest.approx(7 / 8)


def test_r_champ_t1_is_a_map_not_a_sign_test(corpus):
    """R^T1 is non-negative by construction: its z-vs-0 carries NO sign information.
    This test pins that property so nobody later reads it as one."""
    rows, _, _ = F4.build_f4_rows(corpus["positions"], corpus["clair"], corpus["t1"])
    for r in rows:
        assert r["R_champ_t1"] >= 0.0
    st = F4.f4_category_stats(rows, [True] * len(rows))
    assert st["R_champ_t1"] >= 0.0


def test_empty_category_is_unestimable():
    st = F4.f4_category_stats([], [])
    assert st["verdict"] == "F4-UNESTIMABLE"
    assert st["witness"] is None


# --------------------------------------------------------------------------- #
# 4. the per-category verdict enum (§4.6)                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("st,want", [
    ({"witness": -0.1, "witness_z": 5.0, "witness_split": 1.0}, "F4-REFUTED"),
    ({"witness": 0.0, "witness_z": 5.0, "witness_split": 1.0}, "F4-REFUTED"),
    ({"witness": 0.4, "witness_z": 2.0, "witness_split": 0.3}, "F4-CONFIRMED"),
    ({"witness": 0.4, "witness_z": 1.6448, "witness_split": 0.3}, "F4-DIRECTIONAL"),
    ({"witness": 0.4, "witness_z": 1.0, "witness_split": 0.3}, "F4-DIRECTIONAL"),
    ({"witness": 0.4, "witness_z": 5.0, "witness_split": -0.2}, "F4-DIRECTIONAL"),
    ({"witness": 0.4, "witness_z": 5.0, "witness_split": None}, "F4-DIRECTIONAL"),
    ({"witness": None}, "F4-UNESTIMABLE"),
])
def test_category_verdict_enum(st, want):
    assert F4.category_verdict(st) == want


def test_one_sided_threshold_is_exactly_alpha_05():
    assert F4.Z_ONE_SIDED == pytest.approx(1.6448536269514722)
    assert F4.norm_sf(F4.Z_ONE_SIDED) == pytest.approx(0.05, abs=1e-9)


# --------------------------------------------------------------------------- #
# 5. the funnel verdict enum (§5) — ORDER MATTERS, first match wins            #
# --------------------------------------------------------------------------- #
def test_funnel_broken_beats_everything():
    v, _ = F4.funnel_verdict(False, 5.0, 20.0, {"a": "F4-CONFIRMED"}, "L1")
    assert v == "F4-BROKEN"


@pytest.mark.parametrize("mu,z", [(-0.1, 5.0), (0.0, 5.0), (0.4, 1.9),
                                  (0.4, float("nan"))])
def test_funnel_closed_when_pooled_sign_fails(mu, z):
    v, _ = F4.funnel_verdict(True, mu, z, {"a": "F4-CONFIRMED"}, "L1")
    assert v == "FUNNEL-CLOSED-BY-F4"


def test_funnel_open_confirmed_even_beside_a_refutation():
    v, c = F4.funnel_verdict(True, 0.4, 3.0,
                             {"a": "F4-CONFIRMED", "b": "F4-REFUTED"}, "L1")
    assert v == "FUNNEL-OPEN-F4-CONFIRMED"
    assert "CONFIRMED set only" in c


def test_funnel_directional_requires_zero_refutations():
    assert F4.funnel_verdict(True, 0.4, 3.0, {"a": "F4-DIRECTIONAL"}, "L1")[0] \
        == "FUNNEL-OPEN-F4-DIRECTIONAL"
    assert F4.funnel_verdict(True, 0.4, 3.0,
                             {"a": "F4-DIRECTIONAL", "b": "F4-REFUTED"}, "L1")[0] \
        == "FUNNEL-F4-INCONCLUSIVE"


def test_funnel_closed_by_refutation_needs_all_refuted():
    assert F4.funnel_verdict(True, 0.4, 3.0,
                             {"a": "F4-REFUTED", "b": "F4-REFUTED"}, "L1")[0] \
        == "FUNNEL-CLOSED-BY-F4-REFUTED"


def test_rung_l3_prefixes_partial_and_cannot_confirm():
    v, c = F4.funnel_verdict(True, 0.4, 3.0, {"a": "F4-DIRECTIONAL"}, "L3")
    assert v == "F4-PARTIAL/FUNNEL-OPEN-F4-DIRECTIONAL"
    assert "UNAVAILABLE" in c


# --------------------------------------------------------------------------- #
# 6. instrument gates (§6)                                                     #
# --------------------------------------------------------------------------- #
def test_cross_judge_crn_witness_passes_on_matched_worlds(corpus):
    w = F4.crn_cross_judge_witness(corpus["clair"], corpus["t1"])
    assert w["cross_judge_comparisons"] == 8
    assert w["ok"] is True


def test_cross_judge_crn_witness_catches_a_reseeded_world(corpus):
    p = corpus["t1"] / "sib2" / "records" / "r1.json"
    d = json.loads(p.read_text())
    d["world_seeds"] = [x + 1 for x in d["world_seeds"]]
    p.write_text(json.dumps(d))
    w = F4.crn_cross_judge_witness(corpus["clair"], corpus["t1"])
    assert w["ok"] is False
    assert w["examples"][0]["field"] == "world_seeds"


def test_cross_judge_crn_witness_catches_a_different_afterstate(corpus):
    p = corpus["t1"] / "sib2" / "records" / "r2.json"
    d = json.loads(p.read_text())
    d["afterstate_deck_hash_b"] = ["different"] * M
    p.write_text(json.dumps(d))
    assert F4.crn_cross_judge_witness(corpus["clair"], corpus["t1"])["ok"] is False


def test_manifest_gate_rejects_the_wrong_judge(corpus):
    assert F4.manifest_gates(corpus["t1"], ("leaf", "sib2"))["all_ok"] is True
    # the R1 tree is clair-puct/rust — it must FAIL the F4 manifest gate
    assert F4.manifest_gates(corpus["clair"], ("leaf", "sib2"))["all_ok"] is False


def test_manifest_gate_rejects_a_manifest_with_no_policy_key_at_all(corpus, tmp_path):
    """D-F4-10 regression: the gate read `oracle_policy` at top level, which the harness
    never writes (that name exists only in the per-position RECORD), so a correct
    tier1-greedy manifest FAILED g2. Both spellings are accepted now; neither present
    must still fail."""
    bad = tmp_path / "badtree"
    (bad / "sib2").mkdir(parents=True)
    (bad / "sib2" / "manifest.json").write_text(json.dumps(
        {"execution": {"backend": "python"}}))
    assert F4.manifest_gates(bad, ("sib2",))["all_ok"] is False
    # promoted-to-top-level spelling must also pass
    (bad / "sib2" / "manifest.json").write_text(json.dumps(
        {"oracle_policy": "tier1-greedy",
         "oracle": {"policy_family": "OUT-OF-FAMILY: no search"},
         "execution": {"backend": "python"}}))
    assert F4.manifest_gates(bad, ("sib2",))["all_ok"] is True


def test_manifest_gate_rejects_an_in_family_policy_family(corpus, tmp_path):
    bad = tmp_path / "infam"
    (bad / "sib2").mkdir(parents=True)
    (bad / "sib2" / "manifest.json").write_text(json.dumps(
        {"oracle": {"policy": "tier1-greedy", "policy_family": "IN-FAMILY oops"},
         "execution": {"backend": "python"}}))
    assert F4.manifest_gates(bad, ("sib2",))["all_ok"] is False


def test_record_gate_rejects_a_wall_capped_or_uncrn_record(corpus):
    assert F4.record_gates(corpus["t1"], ("leaf", "sib2"))["all_ok"] is True
    p = corpus["t1"] / "sib2" / "records" / "r0.json"
    d = json.loads(p.read_text())
    d["crn_verified"] = False
    p.write_text(json.dumps(d))
    g = F4.record_gates(corpus["t1"], ("leaf", "sib2"))
    assert g["all_ok"] is False and g["sib2"]["ok"] is False


def test_record_gate_rejects_the_wrong_salt(corpus):
    p = corpus["t1"] / "leaf" / "records" / "r0.json"
    d = json.loads(p.read_text())
    d["world_seed_salt"] = "some-other-salt"
    p.write_text(json.dumps(d))
    assert F4.record_gates(corpus["t1"], ("leaf", "sib2"))["all_ok"] is False


def test_record_gate_rejects_the_wrong_rules_profile(corpus):
    p = corpus["t1"] / "leaf" / "records" / "r0.json"
    d = json.loads(p.read_text())
    d["rules_profile"] = "unwalled"
    p.write_text(json.dumps(d))
    assert F4.record_gates(corpus["t1"], ("leaf", "sib2"))["all_ok"] is False


def test_reconciliation_passes_on_matching_map_and_fails_on_a_drift(corpus):
    rows, _, _ = F4.build_f4_rows(corpus["positions"], corpus["clair"], corpus["t1"])
    members = {"all": [True] * len(rows)}
    ref = {"pooled": {"R_champ": 2.0},
           "categories": {"all": {"R_champ": 2.0}}}
    assert F4.reconcile(rows, members, ref)["ok"] is True
    ref_bad = {"pooled": {"R_champ": 2.0},
               "categories": {"all": {"R_champ": 2.0 + 1e-6}}}
    out = F4.reconcile(rows, members, ref_bad)
    assert out["ok"] is False and out["worst_category"] == "all"
    ref_pool = {"pooled": {"R_champ": 2.5}, "categories": {"all": {"R_champ": 2.0}}}
    assert F4.reconcile(rows, members, ref_pool)["pooled_ok"] is False


def test_arms_match_flag_detects_a_one_sided_arm(tmp_path):
    pos = tmp_path / "positions"; pos.mkdir()
    (pos / "positions_meta.jsonl").write_text(json.dumps(
        {"rid": "x", "game_id": 1, "ply": 2, "ht_weight": 1.0,
         "arms": {"leaf": 1, "sib2": 2}, "in_rnd_subset": False,
         "taxonomy": _tax()}) + "\n")
    C, T = tmp_path / "judge", tmp_path / "judge_t1"
    _write_leg(C, "leaf", [_rec("x", "leaf", -1.0, [-1.0] * M)])
    _write_leg(C, "sib2", [_rec("x", "sib2", 2.0, [2.0] * M)])
    _write_leg(T, "sib2", [_rec("x", "sib2", 1.0, [1.0] * M)],
               policy="tier1-greedy", backend="python")
    rows, _, _ = F4.build_f4_rows(pos, C, T)
    assert rows[0]["arms_match"] is False
    assert rows[0]["arms_both"] == ["sib2"]


# --------------------------------------------------------------------------- #
# 7. the leaf-computable-predicate table (§4.7)                                #
# --------------------------------------------------------------------------- #
def test_every_r2_family_bucket_has_a_predicate_ruling():
    import r2_taxonomy as RT
    names = set(RT.classify(_tax(), 0.25).keys())
    missing = names - set(F4.LEAF_COMPUTABLE)
    assert not missing, f"no leaf-computable ruling for {sorted(missing)}"


def test_f7_is_the_one_non_leaf_computable_axis():
    """F7 is a property of the champion's own SEARCH (cross-world argmax spread), so a
    static leaf term cannot compute it. Pinned so the ruling cannot drift silently."""
    assert F4.LEAF_COMPUTABLE["f7_cross_world_spread=low"] is False
    assert F4.LEAF_COMPUTABLE["f7_cross_world_spread=high"] is False
    assert all(v for k, v in F4.LEAF_COMPUTABLE.items()
               if not k.startswith("f7_"))


def test_estimator_is_imported_not_reimplemented():
    """R2 §2 is binding: F4 must not carry its own copy of the estimator."""
    import r2_estimator as RE
    assert F4.hajek is RE.hajek
    assert F4.cluster_sandwich is RE.cluster_sandwich
    assert F4.contrast_cluster is RE.contrast_cluster
    assert F4.holm is RE.holm
    src = Path(F4.__file__).read_text()
    assert "def hajek(" not in src and "def cluster_sandwich(" not in src


def test_bar_and_arms_come_from_the_r2_module():
    import r2_taxonomy as RT
    assert F4.BAR == RT.BAR == 0.5
    assert F4.ARMS == RT.ARMS == ("leaf", "sib2", "sib3", "sib4")
