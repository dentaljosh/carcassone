"""Tests for the E4 autopsy ANALYSIS stage (scripts/analyzer/analyze_autopsy.py).

The extraction/stratification stage is pinned by `tests/test_e4_autopsy.py`; this module
pins the stage that turns banked scoring records into the readout, because that is where a
plausible-but-wrong verdict would be manufactured. Everything here is pure stdlib + numpy
on SYNTHETIC records built in `tmp_path` — no engine, no search, no share mount.

What's pinned, matching the pre-registration's own risk list
(`measurement/e4_autopsy_20260812/DESIGN.md` §8, binding):

  1. THE SIGN CONTRACT — Δ = V(played) − V(best) is the record's `delta` verbatim, and a
     positive Δ means HIS move earned more. A silent flip would invert the whole readout.
  2. THE ARITHMETIC, HAND-COMPUTED — mean, naive SE, CR1 cluster-robust SE on `game_label`,
     two-sided z and the 95% CI, on a tiny corpus whose numbers are worked out in the test
     rather than taken from the code. `cluster_se` is additionally checked to agree with
     the farm-war implementation it is a copy of.
  3. READ RULE 2 — |z| < 2 is NO CONVICTION and it always ships an explicit numeric BOUND
     in pts/ply. A ZERO-EFFECT corpus is run end to end to prove the null path never emits
     "no effect".
  4. THE §8 BRANCH MAP — every branch (localized defect, the DEG search-defect special
     case, champion-picks-better, no-conviction) fires on a corpus constructed to fire it,
     and the run-level self-preference / everything-null branches fire on theirs.
  5. MULTIPLICITY (read rule 10) — the nine mechanism contrasts are enumerated and counted,
     nothing below |z| = 3 is marked quotable, and the convergent-sign escape hatch needs
     all four F9/F2 tags to agree in sign AND reach |z| = 2.
  6. COMPLETION ACCOUNTING — a failed record is reported (never silently dropped), an
     out-of-sample record in the out-root is excluded from every statistic, and a missing
     record is named.
  7. F7 IS NULL BY DESIGN — emitted as null with its status string, never as a zero.
  8. THE TIER-1 LEG IS SIGN ONLY — agreement counting is exact, and no Tier-1 magnitude
     ever reaches a Δ field.
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO / "scripts/analyzer"))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


AN = _load("analyze_autopsy", "scripts/analyzer/analyze_autopsy.py")
FW = _load("farmwar_analyze", "scripts/analyzer/farmwar_analyze.py")

BOOT = {"boot_reps": 200, "boot_seed": 7}


# --------------------------------------------------------------------------- #
# synthetic corpus builders                                                     #
# --------------------------------------------------------------------------- #
def _pos(rid, *, stratum="FARM", game="gA", decision="tile", phase="opening",
         commit="n/a", sdb="level", f9b=False, f9p=False, f2b=False, f2p=False,
         own=3, opp=3, bucket="within_noise", contested=None):
    return {
        "rid": rid, "root_id": rid, "game_label": game, "rules_profile": "fixed_v1",
        "stratum": stratum, "decision_type": decision, "phase_third": phase,
        "commit_direction": commit, "score_diff_bucket": sdb,
        "reinforce_losing_contest_best": f9b, "reinforce_losing_contest_played": f9p,
        "tie_force_join_best": f2b, "tie_force_join_played": f2p,
        "own_reserve": own, "opp_reserve": opp, "bucket": bucket,
        "contested_played": contested or [], "abs_delta_q": 0.1,
        "action_best": 1, "action_played": 2, "pick_a": 1, "pick_b": 2,
    }


def _rec(rid, delta, *, stratum="FARM", game="gA", ok=True, error=None, policy="clair-puct"):
    r = {"rid": rid, "root_id": rid, "game_label": game, "stratum": stratum,
         "rules_profile": "fixed_v1", "ok": ok, "delta": delta, "mean_a": 0.0,
         "mean_b": delta, "within_var": 1.0, "crn_verified": True,
         "distinct_afterstates": 32, "m": 32, "oracle_policy": policy,
         "elapsed_secs": 1.0}
    if not ok:
        r["error"] = error or "boom"
        r.pop("delta")
    return r


def _corpus(spec, **poskw):
    """spec = [(rid, delta, game, stratum), ...] -> (positions dict, records list)."""
    positions, records = {}, []
    for rid, delta, game, stratum in spec:
        positions[rid] = _pos(rid, stratum=stratum, game=game, **poskw)
        records.append(_rec(rid, delta, stratum=stratum, game=game))
    return positions, records


def _centred_noise(n, seed, sd=1.0):
    """Deterministic noise whose mean is EXACTLY zero, so a planted effect survives the
    arithmetic unchanged while the SEs stay positive."""
    rng = random.Random(seed)
    xs = [rng.gauss(0.0, sd) for _ in range(n)]
    m = sum(xs) / n
    return [x - m for x in xs]


def _flat(n, delta, *, stratum, games=6, seed=11, sd=1.0):
    """n positions in `games` games with mean Δ EXACTLY `delta`."""
    noise = _centred_noise(n, seed, sd)
    return [(f"{stratum}_{i}", delta + noise[i], f"g{i % games}", stratum)
            for i in range(n)]


# --------------------------------------------------------------------------- #
# 1. the sign contract                                                          #
# --------------------------------------------------------------------------- #
class TestSignContract:
    def test_delta_is_taken_verbatim_and_positive_means_he_earned_more(self):
        positions, records = _corpus([("r1", +2.5, "gA", "FARM"),
                                      ("r2", -1.5, "gB", "FARM")])
        v = AN.analyse(records, [], positions, **BOOT)
        farm = v["primary_strata"]["FARM"]
        assert farm["n"] == 2
        assert farm["mean_delta_pts"] == pytest.approx(0.5)
        assert farm["n_positive"] == 1 and farm["n_negative"] == 1
        assert "V(played) - V(best)" in v["statistic"]
        assert "POSITIVE => his move earned more" in v["statistic"]

    def test_a_positive_stratum_is_a_defect_in_the_champions_evaluation(self):
        """Positive Δ ⇒ his move earned more ⇒ the branch is about the CHAMPION's
        evaluation, never a claim that his play is worse."""
        positions, records = _corpus(_flat(40, +3.0, stratum="FARM"))
        v = AN.analyse(records, [], positions, **BOOT)
        assert v["stratum_branches"]["FARM"]["branch"] == "LOCALIZED_DEFECT"
        assert "champion's evaluation" in v["stratum_branches"]["FARM"]["text"]


# --------------------------------------------------------------------------- #
# 2. the arithmetic, hand-computed                                              #
# --------------------------------------------------------------------------- #
class TestArithmetic:
    def test_mean_naive_se_cluster_se_z_and_ci_by_hand(self):
        """Four positions, two games. Values 1, 3 (gA) and -1, 1 (gB).

        mean = 1.0; sd = sqrt(((0)^2+(2)^2+(-2)^2+(0)^2)/3) = sqrt(8/3);
        naive se = sd/2 = 0.816496580927726.
        CR1: residuals 0,2,-2,0 -> per-game sums gA=+2, gB=-2;
             meat = (4+4)*2/(2-1) = 16; se = sqrt(16)/4 = 1.0; z = 1.0.
        """
        positions, records = _corpus([("r1", 1.0, "gA", "FARM"), ("r2", 3.0, "gA", "FARM"),
                                      ("r3", -1.0, "gB", "FARM"), ("r4", 1.0, "gB", "FARM")])
        v = AN.analyse(records, [], positions, **BOOT)
        f = v["primary_strata"]["FARM"]
        assert f["mean_delta_pts"] == pytest.approx(1.0)
        assert f["sd_pts"] == pytest.approx(math.sqrt(8.0 / 3.0))
        assert f["se_naive"] == pytest.approx(math.sqrt(8.0 / 3.0) / 2.0)
        assert f["se_cluster_game"] == pytest.approx(1.0)
        assert f["n_game_clusters"] == 2
        assert f["z_two_sided"] == pytest.approx(1.0)
        assert f["z_naive_two_sided"] == pytest.approx(1.0 / (math.sqrt(8.0 / 3.0) / 2.0))
        assert f["ci95_lo"] == pytest.approx(1.0 - AN.Z_95)
        assert f["ci95_hi"] == pytest.approx(1.0 + AN.Z_95)
        assert f["design_effect"] == pytest.approx(1.0 / (8.0 / 3.0 / 4.0))
        assert f["mde_2sigma_realized_cluster_pts"] == pytest.approx(2.0)

    def test_cluster_se_matches_the_farmwar_implementation_it_copies(self):
        vals = [1.0, 3.0, -1.0, 1.0, 2.5, -4.0, 0.25]
        cls = ["a", "a", "b", "b", "c", "c", "c"]
        mine, theirs = AN.cluster_se(vals, cls), FW.cluster_se(vals, cls)
        assert mine["se"] == pytest.approx(theirs["se"])
        assert mine["n_clusters"] == theirs["n_clusters"]
        assert mine["design_effect"] == pytest.approx(theirs["design_effect"])

    def test_cluster_se_collapses_to_naive_when_every_cluster_is_a_singleton(self):
        vals = [1.0, 3.0, -1.0, 1.0]
        se = AN.cluster_se(vals, ["a", "b", "c", "d"])["se"]
        naive = AN._sd(vals) / math.sqrt(4)
        assert se == pytest.approx(naive * math.sqrt((4 / 3.0) * (3 / 4.0)))

    def test_bootstrap_is_deterministic_and_cell_name_seeded(self):
        vals = [1.0, 3.0, -1.0, 1.0, 2.0, 0.0]
        cls = ["a", "a", "b", "b", "c", "c"]
        one = AN.cluster_bootstrap_ci(vals, cls, reps=500, seed=1, name="X")
        two = AN.cluster_bootstrap_ci(vals, cls, reps=500, seed=1, name="X")
        other = AN.cluster_bootstrap_ci(vals, cls, reps=500, seed=1, name="Y")
        assert one == two
        assert (one["lo"], one["hi"]) != (other["lo"], other["hi"])
        assert one["n_clusters"] == 3

    def test_bootstrap_resamples_GAMES_not_positions(self):
        """With every position in ONE game the cluster bootstrap has nothing to resample,
        so the interval collapses to the point estimate. That is the design effect read
        rule 3 is about, made visible."""
        vals = [1.0, 5.0, -3.0, 2.0]
        ci = AN.cluster_bootstrap_ci(vals, ["g", "g", "g", "g"], reps=200, seed=3, name="Z")
        assert ci["lo"] == pytest.approx(1.25) and ci["hi"] == pytest.approx(1.25)


# --------------------------------------------------------------------------- #
# 3. read rule 2 — the null path always emits a BOUND                           #
# --------------------------------------------------------------------------- #
class TestNullPathEmitsABound:
    def test_zero_effect_corpus_bounds_every_stratum_and_never_says_no_effect(self, tmp_path):
        spec = []
        for i, st in enumerate(AN.STRATA):
            spec += _flat(20, 0.0, stratum=st, games=5, seed=100 + i)
        positions, records = _corpus(spec)
        v = AN.analyse(records, [], positions, **BOOT)

        for st in AN.STRATA:
            s = v["primary_strata"][st]
            assert s["mean_delta_pts"] == pytest.approx(0.0)
            assert s["convicts_at_z2"] is False
            assert v["stratum_branches"][st]["branch"] == "NO_CONVICTION"
            # THE deliverable of a null: a numeric bound in pts/ply, not a shrug.
            assert s["bound_pts_per_ply"] is not None
            assert s["bound_pts_per_ply"] > 0
            assert "pts/ply" in s["read"]
            assert "NOT a refutation" in s["read"]

        rl = v["run_level_branch"]
        assert rl["branch"] == "NO_CONVICTION_ANYWHERE"
        assert rl["tightest_bound_pts_per_ply"] > 0
        assert set(rl["bounds_pts_per_ply"]) == set(AN.STRATA)

        # Nothing the null path SAYS about a cell may read as "no effect" or "refuted".
        said = json.dumps({"strata": v["primary_strata"],
                           "branches": v["stratum_branches"],
                           "run_level": v["run_level_branch"],
                           "deg": v["deg_answer"]}).lower()
        assert "no effect" not in said
        assert "refuted" not in said.replace("not a refutation", "")
        assert "no conviction" in said
        # and the bound survives into the rendered readout
        md = AN.to_markdown(v)
        assert "pts/ply" in md and "NO_CONVICTION" in md

        out = tmp_path / "VERDICT.json"
        out.write_text(json.dumps(v, indent=2))
        assert json.loads(out.read_text())["run_level_branch"]["branch"] == \
            "NO_CONVICTION_ANYWHERE"

    def test_bound_is_the_larger_absolute_ci_endpoint(self):
        txt = AN._bound_text(-0.4, 1.9)
        assert "1.900 pts/ply" in txt and "NOT a refutation" in txt

    def test_underpowered_cells_are_flagged_by_construction(self):
        positions, records = _corpus(_flat(10, 0.0, stratum="CLOISTER", games=3, seed=5))
        v = AN.analyse(records, [], positions, **BOOT)
        assert v["primary_strata"]["CLOISTER"]["underpowered_by_construction"] is True
        assert v["primary_strata"]["CLOISTER"]["n"] < AN.MIN_N_POWERED


# --------------------------------------------------------------------------- #
# 4. the §8 branch map                                                          #
# --------------------------------------------------------------------------- #
class TestBranchMap:
    def test_positive_and_significant_is_a_localized_defect(self):
        positions, records = _corpus(_flat(40, +3.0, stratum="CITY"))
        v = AN.analyse(records, [], positions, **BOOT)
        b = v["stratum_branches"]["CITY"]
        assert b["branch"] == "LOCALIZED_DEFECT"
        assert b["mints_claim_id"] is False       # owner's call, never this script's
        assert "CONSERVATIVE" in b["text"]

    def test_positive_and_significant_in_DEG_is_a_SEARCH_defect(self):
        positions, records = _corpus(_flat(40, +3.0, stratum="DEG"))
        v = AN.analyse(records, [], positions, **BOOT)
        b = v["stratum_branches"]["DEG"]
        assert b["branch"] == "DEG_SEARCH_DEFECT"
        assert "SEARCH, not the leaf" in b["text"]
        assert v["deg_answer"]["branch"] == "DEG_SEARCH_DEFECT"
        assert "SEARCH defect" in v["deg_answer"]["implication_if_positive"]

    def test_negative_and_significant_means_the_champions_picks_are_better(self):
        positions, records = _corpus(_flat(40, -3.0, stratum="ROAD"))
        v = AN.analyse(records, [], positions, **BOOT)
        b = v["stratum_branches"]["ROAD"]
        assert b["branch"] == "CHAMPION_PICKS_BETTER"
        assert "SHARPENS the puzzle" in b["text"]

    def test_all_strata_positive_and_significant_is_judge_self_preference(self):
        spec = []
        for i, st in enumerate(AN.STRATA):
            spec += _flat(40, +3.0, stratum=st, seed=20 + i)
        positions, records = _corpus(spec)
        v = AN.analyse(records, [], positions, **BOOT)
        rl = v["run_level_branch"]
        assert rl["branch"] == "GENERAL_SAME_FAMILY_SELF_PREFERENCE"
        assert "INSTRUMENT" in rl["text"]
        assert set(rl["strata"]) == set(AN.STRATA)

    def test_a_mixed_map_is_reported_as_a_map_not_a_verdict(self):
        spec = (_flat(40, +3.0, stratum="FARM", seed=4)
                + _flat(40, 0.0, stratum="CITY", seed=5))
        positions, records = _corpus(spec)
        v = AN.analyse(records, [], positions, **BOOT)
        assert v["run_level_branch"]["branch"] == "MIXED_MAP"
        assert v["run_level_branch"]["convicting"] == ["FARM"]

    def test_z_gate_is_exactly_two_and_two_sided(self):
        assert AN.Z_GATE == 2.0
        st = {"n": 30, "mean_delta_pts": 1.0, "z_two_sided": -1.999,
              "ci95_lo": -2.0, "ci95_hi": 4.0}
        assert AN.stratum_branch(st, is_deg=False)["branch"] == "NO_CONVICTION"
        st["z_two_sided"] = -2.0
        st["mean_delta_pts"] = -1.0
        assert AN.stratum_branch(st, is_deg=False)["branch"] == "CHAMPION_PICKS_BETTER"

    def test_map_ranking_orders_by_absolute_effect_and_absolute_z(self):
        spec = (_flat(40, +3.0, stratum="FARM", seed=1)
                + _flat(40, +0.2, stratum="CITY", seed=2)
                + _flat(40, -1.0, stratum="ROAD", seed=3))
        positions, records = _corpus(spec)
        v = AN.analyse(records, [], positions, **BOOT)
        order = [r["stratum"] for r in v["map_ranking"]["by_abs_mean_delta"]]
        assert order[:3] == ["FARM", "ROAD", "CITY"]
        assert [r["stratum"] for r in v["map_ranking"]["by_abs_z"]][0] == "FARM"


# --------------------------------------------------------------------------- #
# 5. multiplicity, read rule 10                                                 #
# --------------------------------------------------------------------------- #
class TestMultiplicity:
    def _mech_corpus(self, *, f9_delta=0.0, base=0.0, n=40):
        spec, positions, records = [], {}, []
        for i in range(n):
            rid, game = f"m{i}", f"g{i % 5}"
            f9 = i % 2 == 0
            positions[rid] = _pos(rid, stratum="FARM", game=game, f9b=f9, f9p=f9,
                                  f2b=f9, f2p=f9,
                                  sdb=("behind", "level", "ahead")[i % 3],
                                  own=1 + i % 4, opp=1 + (i + 1) % 4)
            records.append(_rec(rid, base + (f9_delta if f9 else 0.0)
                                + (0.5 if i % 4 < 2 else -0.5),
                                stratum="FARM", game=game))
        return positions, records

    def test_nine_mechanism_contrasts_are_enumerated(self):
        positions, records = self._mech_corpus()
        v = AN.analyse(records, [], positions, **BOOT)
        inv = v["mechanism_tags"]["_contrast_inventory"]
        assert inv["n_contrasts_preregistered"] == AN.N_SECONDARY_CONTRASTS == 9
        assert inv["n_contrasts"] == 9
        labels = [i["contrast"] for i in inv["contrasts"]]
        assert sum(1 for x in labels if x.startswith("F6")) == 3
        assert sum(1 for x in labels if "True-minus-False" in x) == 4
        assert sum(1 for x in labels if x.startswith("F3")) == 2

    def test_nothing_below_z3_is_quotable_alone(self):
        positions, records = self._mech_corpus(f9_delta=1.0)
        v = AN.analyse(records, [], positions, **BOOT)
        inv = v["mechanism_tags"]["_contrast_inventory"]
        for i in inv["contrasts"]:
            if i.get("z") is not None and i["z"] == i["z"] and abs(i["z"]) < 3.0:
                assert i["contrast"] not in inv["quotable_at_z3"]
        assert AN.Z_GATE_SECONDARY == 3.0

    def test_convergent_sign_needs_all_four_tags_and_z2(self):
        mech = {
            "F9_reinforce_losing_contest_best": {"True": {"n": 5, "mean_delta_pts": 1.0,
                                                          "z_two_sided": 2.5}},
            "F9_reinforce_losing_contest_played": {"True": {"n": 5, "mean_delta_pts": 1.0,
                                                            "z_two_sided": 2.5}},
            "F2_tie_force_join_best": {"True": {"n": 5, "mean_delta_pts": 1.0,
                                                "z_two_sided": 2.5}},
            "F2_tie_force_join_played": {"True": {"n": 5, "mean_delta_pts": 1.0,
                                                  "z_two_sided": 2.5}},
        }
        assert AN.convergent_sign_check(mech)["convergent_and_quotable"] is True
        mech["F2_tie_force_join_played"]["True"]["z_two_sided"] = 1.2
        c = AN.convergent_sign_check(mech)
        assert c["all_four_same_sign"] is True
        assert c["all_four_abs_z_ge_2"] is False
        assert c["convergent_and_quotable"] is False
        mech["F2_tie_force_join_played"]["True"].update({"mean_delta_pts": -1.0,
                                                         "z_two_sided": 2.5})
        assert AN.convergent_sign_check(mech)["all_four_same_sign"] is False

    def test_f9_f2_counts_are_not_reported_as_effects(self):
        positions, records = self._mech_corpus()
        v = AN.analyse(records, [], positions, **BOOT)
        rules = " ".join(v["mechanism_tags"]["_read_rules"])
        assert "MOVE CLASS, not effects" in rules

    def test_multiplicity_ledger_covers_the_exploratory_axes_too(self):
        positions, records = self._mech_corpus(f9_delta=4.0)
        v = AN.analyse(records, [], positions, **BOOT)
        ml = v["multiplicity_ledger"]
        assert ml["n_contrasts_total"] > 9          # axes + tile/meeple join the ledger
        assert ml["gate_for_quotability"] == 3.0
        assert ml["expected_hits_at_abs_z_ge_2_if_all_null"] > 0
        for hit in ml["observed_abs_z_ge_3_QUOTABLE"]:
            assert abs(hit["z"]) >= 3.0
        for hit in ml["observed_abs_z_ge_2"]:
            assert abs(hit["z"]) >= 2.0

    def test_f3_is_a_regression_not_a_cell(self):
        positions, records = self._mech_corpus()
        v = AN.analyse(records, [], positions, **BOOT)
        f3 = v["mechanism_tags"]["F3_reserve_regression"]
        assert set(f3["terms"]) == {"intercept", "own_reserve", "opp_reserve"}
        assert f3["n"] == 40 and f3["n_game_clusters"] == 5

    def test_f3_recovers_a_planted_slope(self):
        """Δ = 2 * own_reserve exactly ⇒ β_own = 2, β_opp = 0, intercept 0."""
        positions, records = {}, []
        for i in range(40):
            rid, game = f"s{i}", f"g{i % 4}"
            own, opp = 1 + i % 5, 1 + (i * 3) % 5
            positions[rid] = _pos(rid, stratum="FARM", game=game, own=own, opp=opp)
            records.append(_rec(rid, 2.0 * own, stratum="FARM", game=game))
        v = AN.analyse(records, [], positions, **BOOT)
        t = v["mechanism_tags"]["F3_reserve_regression"]["terms"]
        assert t["own_reserve"]["beta_pts_per_meeple"] == pytest.approx(2.0, abs=1e-6)
        assert t["opp_reserve"]["beta_pts_per_meeple"] == pytest.approx(0.0, abs=1e-6)
        assert t["intercept"]["beta_pts_per_meeple"] == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# 6. completion accounting                                                      #
# --------------------------------------------------------------------------- #
class TestCompletionAccounting:
    def test_failed_out_of_sample_and_missing_are_all_reported(self):
        positions, records = _corpus([("r1", 1.0, "gA", "FARM"), ("r2", 2.0, "gB", "FARM"),
                                      ("r3", 3.0, "gB", "FARM")])
        positions["r4"] = _pos("r4", stratum="FARM", game="gC")     # never scored
        records[2] = _rec("r3", None, stratum="FARM", game="gB", ok=False,
                          error="WindowOverflowError: nope")
        records.append(_rec("smoke_extra", 99.0, stratum="FARM", game="gZ"))  # out of sample

        v = AN.analyse(records, [], positions, **BOOT)
        ca = v["completion_accounting"]["primary"]
        assert ca["n_records_written"] == 4
        assert ca["n_in_sample_ok"] == 2
        assert ca["n_failed"] == 1
        assert ca["failures"][0]["rid"] == "r3"
        assert "WindowOverflow" in ca["failures"][0]["error"]
        assert ca["out_of_sample_rids"] == ["smoke_extra"]
        assert ca["missing_rids"] == ["r4"]
        # the out-of-sample 99.0 must not have contaminated the estimate
        assert v["primary_strata"]["FARM"]["n"] == 2
        assert v["primary_strata"]["FARM"]["mean_delta_pts"] == pytest.approx(1.5)
        assert v["completion_accounting"]["planned_positions_this_epoch"] == 4
        assert v["completion_accounting"]["planned_records_both_judges"] == 8
        assert set(v["completion_accounting"]["symmetric_drop"]) >= {"r3", "r4"}

    def test_scope_is_stamped_as_fixed_v1_only_and_pooling_is_moot(self):
        positions, records = _corpus([("r1", 1.0, "gA", "FARM")])
        v = AN.analyse(records, [], positions, **BOOT)
        assert v["scope"]["epochs_scored"] == ["fixed_v1"]
        assert v["scope"]["epochs_not_scored"] == ["walled", "app_aug2"]
        assert v["scope"]["pooling_across_epochs"] == "moot_single_epoch_scored"
        assert "SCOPE RESTRICTION is not" in v["scope"]["limit"]

    def test_a_record_disagreeing_with_the_sample_on_stratum_raises(self):
        positions, records = _corpus([("r1", 1.0, "gA", "FARM")])
        records[0]["stratum"] = "CITY"
        with pytest.raises(ValueError, match="stratum disagreement"):
            AN.analyse(records, [], positions, **BOOT)

    def test_no_claim_is_minted_on_any_branch(self):
        for st, d in (("FARM", +3.0), ("DEG", +3.0), ("ROAD", -3.0), ("CITY", 0.0)):
            positions, records = _corpus(_flat(40, d, stratum=st))
            v = AN.analyse(records, [], positions, **BOOT)
            assert v["governance"]["mints_claim_id"] is False
            assert all(b["mints_claim_id"] is False
                       for b in v["stratum_branches"].values())


# --------------------------------------------------------------------------- #
# 7. F7 is null by design                                                       #
# --------------------------------------------------------------------------- #
class TestF7:
    def test_f7_is_null_with_a_status_never_zero(self):
        positions, records = _corpus([("r1", 1.0, "gA", "FARM")])
        v = AN.analyse(records, [], positions, **BOOT)
        assert v["mechanism_tags"]["F7_cross_world_spread"] is None
        assert "unavailable_pooled_only" in v["mechanism_tags"]["F7_status"]
        assert "NULL BY DESIGN" in v["mechanism_tags"]["F7_status"]


# --------------------------------------------------------------------------- #
# 8. the Tier-1 leg is SIGN ONLY                                                #
# --------------------------------------------------------------------------- #
class TestTier1SignOnly:
    def test_agreement_counting_is_exact_and_zeroes_are_excluded(self):
        primary = [{"rid": "a", "delta": 1.0}, {"rid": "b", "delta": -1.0},
                   {"rid": "c", "delta": 2.0}, {"rid": "d", "delta": 0.0}]
        secondary = [{"rid": "a", "delta": 5.0}, {"rid": "b", "delta": -0.5},
                     {"rid": "c", "delta": -9.0}, {"rid": "d", "delta": 3.0}]
        s = AN.sign_agreement(primary, secondary, "T")
        assert s["n_shared"] == 4
        assert s["n_both_nonzero"] == 3          # 'd' has a zero primary
        assert s["n_agree"] == 2                 # a and b agree, c does not
        assert s["agreement_rate"] == pytest.approx(2 / 3)
        assert s["n_primary_zero"] == 1
        assert 0.0 < s["binomial_p_two_sided"] <= 1.0

    def test_perfect_agreement_is_significant_and_perfect_disagreement_too(self):
        p = [{"rid": str(i), "delta": 1.0} for i in range(12)]
        s_same = [{"rid": str(i), "delta": 3.0} for i in range(12)]
        s_opp = [{"rid": str(i), "delta": -3.0} for i in range(12)]
        assert AN.sign_agreement(p, s_same, "T")["binomial_p_two_sided"] < 0.001
        assert AN.sign_agreement(p, s_opp, "T")["n_agree"] == 0
        assert AN.sign_agreement(p, s_opp, "T")["binomial_p_two_sided"] < 0.001

    def test_tier1_magnitude_never_enters_a_delta_estimate(self):
        positions, records = _corpus([("r1", 1.0, "gA", "FARM"), ("r2", 1.0, "gB", "FARM")])
        secondary = [_rec("r1", 100.0, stratum="FARM", game="gA", policy="tier1-greedy"),
                     _rec("r2", 100.0, stratum="FARM", game="gB", policy="tier1-greedy")]
        v = AN.analyse(records, secondary, positions, **BOOT)
        assert v["primary_strata"]["FARM"]["mean_delta_pts"] == pytest.approx(1.0)
        assert v["overall_pooled_all_strata"]["mean_delta_pts"] == pytest.approx(1.0)
        assert v["tier1_sign_check"]["ALL"]["agreement_rate"] == pytest.approx(1.0)
        assert v["tier1_sign_check"]["secondary_own_mean_SIGN_ONLY"]["ALL"] == 1
        assert "SIGN ONLY" in v["tier1_sign_check"]["note"]
        # no Tier-1 magnitude anywhere in the primary map
        assert "100.0" not in json.dumps(v["primary_strata"])

    def test_only_positions_scored_by_both_judges_are_paired(self):
        positions, records = _corpus([("r1", 1.0, "gA", "FARM"), ("r2", 1.0, "gB", "FARM")])
        secondary = [_rec("r1", 2.0, stratum="FARM", game="gA", policy="tier1-greedy")]
        v = AN.analyse(records, secondary, positions, **BOOT)
        assert v["tier1_sign_check"]["n_paired"] == 1
        assert v["tier1_sign_check"]["ALL"]["n_shared"] == 1


# --------------------------------------------------------------------------- #
# 9. the rendered readout                                                       #
# --------------------------------------------------------------------------- #
class TestMarkdown:
    def test_readout_carries_the_binding_caveats(self):
        spec = []
        for i, st in enumerate(AN.STRATA):
            spec += _flat(20, 0.0, stratum=st, games=5, seed=200 + i)
        positions, records = _corpus(spec)
        secondary = [_rec(r["rid"], -r["delta"], stratum=r["stratum"],
                          game=r["game_label"], policy="tier1-greedy") for r in records]
        md = AN.to_markdown(AN.analyse(records, secondary, positions, **BOOT))
        for needle in ("Scope limit", "not a strength claim", "SIGN ONLY",
                       "NULL BY DESIGN", "multiplicity", "Completion accounting",
                       "cluster-robust", "bootstrap", "NO CONVICTION"):
            assert needle.lower() in md.lower(), needle

    def test_cli_end_to_end(self, tmp_path):
        pos_p = tmp_path / "positions.jsonl"
        prec = tmp_path / "primary"
        srec = tmp_path / "secondary"
        prec.mkdir(), srec.mkdir()
        spec = []
        for i, st in enumerate(AN.STRATA):
            spec += _flat(20, 0.0, stratum=st, games=5, seed=200 + i)
        positions, records = _corpus(spec)
        pos_p.write_text("\n".join(json.dumps(p) for p in positions.values()))
        for r in records:
            (prec / f"{r['rid']}.json").write_text(json.dumps(r))
            (srec / f"{r['rid']}.json").write_text(
                json.dumps(dict(r, delta=-r["delta"], oracle_policy="tier1-greedy")))
        out, md = tmp_path / "V.json", tmp_path / "R.md"
        rc = AN.main(["--positions", str(pos_p), "--primary-records", str(prec),
                      "--secondary-records", str(srec), "--out", str(out),
                      "--md", str(md), "--bootstrap", "100"])
        assert rc == 0
        v = json.loads(out.read_text())
        assert v["schema"] == AN.SCHEMA
        assert v["run_level_branch"]["branch"] == "NO_CONVICTION_ANYWHERE"
        assert md.read_text().startswith("# E4 autopsy")
