"""Tests for the farm-war discriminator (measurement/analyzer_evloss_20260805/).

Three things are pinned, matching the three things that could silently produce a
plausible-but-wrong verdict:

  1. THE STRATIFIER'S BOUNDARY BEHAVIOUR — the >=50% share rule at, above and below the
     threshold, the sign-insensitivity of the share, and the degenerate 0/0 case that must
     land in NEITHER stratum.
  2. THE ADAPTER'S TRIPLE EXTRACTION, against a REAL artifact on disk — a candidate ply
     really is a human inaccuracy/blunder with two distinct legal actions, and the
     positions file really carries the champion's pick as arm A and the human's as arm B
     (the sign of the entire deliverable turns on that order).
  3. THE DEFAULT PATH IS UNCHANGED — structurally here (a no-flag run builds exactly the
     `Game(...)` call it always did, and `_process` replays through the same code), and
     numerically by `scripts/measurement_infra/gate_positions_jsonl.py`, whose banked
     field-by-field diff is asserted from disk when it has been run.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MEAS = REPO / "measurement/analyzer_evloss_20260805"
FW = MEAS / "farmwar"

sys.path.insert(0, str(REPO / "scripts/analyzer"))
sys.path.insert(0, str(REPO / "scripts/human_anchor"))
sys.path.insert(0, str(REPO / "scripts/measurement_infra"))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ST = _load("farmwar_stratify", "scripts/analyzer/farmwar_stratify.py")
AN = _load("farmwar_analyze", "scripts/analyzer/farmwar_analyze.py")


# --------------------------------------------------------------------------- #
# 1. stratifier boundary behaviour                                              #
# --------------------------------------------------------------------------- #
class TestStratifierBoundary:
    def test_exactly_half_is_farm_driven(self):
        """">= 50%" includes 50%. total_diff = 2.0, farm_diff = 1.0."""
        ev = ST.classify_primary(l_full_played=2.0, l_full_best=0.0,
                                 l_nofarm_played=1.0, l_nofarm_best=0.0)
        assert ev["total_leaf_diff"] == pytest.approx(2.0)
        assert ev["farm_leaf_diff"] == pytest.approx(1.0)
        assert ev["farm_share"] == pytest.approx(0.5)
        assert ev["farm_driven"] is True

    def test_just_under_half_is_not(self):
        ev = ST.classify_primary(l_full_played=2.0, l_full_best=0.0,
                                 l_nofarm_played=1.0 + 1e-6, l_nofarm_best=0.0)
        assert ev["farm_share"] < 0.5
        assert ev["farm_driven"] is False

    def test_share_uses_magnitudes_not_signs(self):
        """A farm term pulling the OTHER way still 'accounts for' the difference — the
        rule is about attribution, not about agreeing with the champion."""
        ev = ST.classify_primary(l_full_played=1.0, l_full_best=0.0,
                                 l_nofarm_played=3.0, l_nofarm_best=0.0)
        assert ev["farm_leaf_diff"] == pytest.approx(-2.0)
        assert ev["farm_share"] == pytest.approx(2.0)
        assert ev["farm_driven"] is True

    def test_all_farm_and_no_farm_extremes(self):
        allfarm = ST.classify_primary(5.0, 0.0, 0.0, 0.0)
        assert allfarm["farm_share"] == pytest.approx(1.0) and allfarm["farm_driven"]
        nofarm = ST.classify_primary(5.0, 0.0, 5.0, 0.0)
        assert nofarm["farm_share"] == pytest.approx(0.0)
        assert nofarm["farm_driven"] is False

    def test_degenerate_total_lands_in_neither_stratum(self):
        ev = ST.classify_primary(3.0, 3.0, 1.0, 2.0)
        assert ev["degenerate_total_diff"] is True
        assert ev["farm_share"] is None
        assert ev["farm_driven"] is False

    def test_candidate_filter_rejects_the_undefined_plies(self):
        art = {"plies": [
            {"ply": 0, "actor": 0, "bucket": "blunder", "forced": False,
             "action_played": 1, "action_best": 2, "delta_q": 0.3},          # keep
            {"ply": 1, "actor": 1, "bucket": "blunder", "forced": False,
             "action_played": 1, "action_best": 2, "delta_q": 0.3},          # champion
            {"ply": 2, "actor": 0, "bucket": "agree", "forced": False,
             "action_played": 1, "action_best": 2, "delta_q": 0.3},          # bucket
            {"ply": 3, "actor": 0, "bucket": "blunder", "forced": True,
             "action_played": 1, "action_best": 2, "delta_q": 0.3},          # forced
            {"ply": 4, "actor": 0, "bucket": "blunder", "forced": False,
             "action_played": 7, "action_best": 7, "delta_q": 0.3},          # same arm
            {"ply": 5, "actor": 0, "bucket": "inaccuracy", "forced": False,
             "action_played": 1, "action_best": 2, "delta_q": None},         # no dQ
        ]}
        assert [p["ply"] for p in ST.candidate_plies(art)] == [0]


class TestControlMatching:
    def test_nearest_neighbour_without_replacement(self):
        def r(rid, dq, g="g", ply=0):
            return {"rid": rid, "abs_delta_q": dq, "game_label": g, "ply": ply}
        farm = [r("f1", 0.50, "g", 1), r("f2", 0.10, "g", 2)]
        pool = [r("c1", 0.49, "g", 3), r("c2", 0.48, "g", 4), r("c3", 0.11, "g", 5)]
        got = ST.match_control(farm, pool)
        # f1 (larger |dQ|) is consumed first and takes 0.49; f2 then takes 0.11.
        assert [c["rid"] for c in got] == ["c1", "c3"]
        assert got[0]["matched_to"] == "f1" and got[1]["matched_to"] == "f2"
        assert {c["rid"] for c in got}.isdisjoint({"c2"}) or len(got) == 2

    def test_short_pool_truncates_rather_than_reusing(self):
        def r(rid, dq, ply):
            return {"rid": rid, "abs_delta_q": dq, "game_label": "g", "ply": ply}
        got = ST.match_control([r("f1", 0.5, 1), r("f2", 0.4, 2)], [r("c1", 0.45, 3)])
        assert len(got) == 1 and got[0]["rid"] == "c1"


# --------------------------------------------------------------------------- #
# 2. the adapter's triple extraction, against real artifacts                     #
# --------------------------------------------------------------------------- #
ARTIFACTS = sorted(MEAS.glob("EV_LOSS_*.json"))


@pytest.mark.skipif(not ARTIFACTS, reason="no EV-loss artifacts on disk")
class TestTripleExtractionAgainstRealArtifacts:
    def test_every_candidate_has_a_well_formed_triple(self):
        seen = 0
        for p in ARTIFACTS:
            art = json.loads(p.read_text())
            for ply in ST.candidate_plies(art):
                seen += 1
                assert ply["actor"] == 0
                assert ply["bucket"] in ST.CANDIDATE_BUCKETS
                assert ply["action_played"] != ply["action_best"]
                assert ply["delta_q"] is not None
                assert not ply["forced"]
                assert ply["kind"] == "pimc"      # ΔQ only exists on the search plies
        assert seen >= 40, f"only {seen} candidate plies across six games"

    @pytest.mark.skipif(not (FW / "positions.jsonl").exists(),
                        reason="stratifier has not been run")
    def test_positions_file_puts_the_champion_in_arm_a(self):
        """The sign of the whole deliverable: `position_delta` returns B - A, so arm A
        MUST be the champion's pick for `delta` to be V(played) - V(best)."""
        rows = [json.loads(l) for l in (FW / "positions.jsonl").read_text().splitlines()
                if l.strip()]
        assert rows
        for r in rows:
            assert r["pick_a"] == r["action_best"]
            assert r["pick_b"] == r["action_played"]
            assert r["pick_a"] != r["pick_b"]
            assert r["root_player"] == 0
            assert r["stratum"] in ("FARM", "CONTROL")
            assert r["stratifier_rule"] == "primary"

    @pytest.mark.skipif(not (FW / "positions.jsonl").exists(),
                        reason="stratifier has not been run")
    def test_positions_round_trip_through_the_scorer_loader(self):
        OSP = _load("oracle_score_pilot", "scripts/measurement_infra/oracle_score_pilot.py")
        rows = OSP.load_positions_jsonl(FW / "positions.jsonl")
        assert rows and len({r["rid"] for r in rows}) == len(rows)
        for r in rows:
            assert r["actions"] and r["ply"] < len(r["actions"])
            assert isinstance(r["root_id"], str)

    @pytest.mark.skipif(not (FW / "STRATA.json").exists(),
                        reason="stratifier has not been run")
    def test_strata_are_disjoint_and_gate_is_recorded(self):
        s = json.loads((FW / "STRATA.json").read_text())
        f = {r["rid"] for r in s["farm"]}
        c = {r["rid"] for r in s["control"]}
        assert f and c and not (f & c)
        assert s["n_farm"] == len(f) and s["n_control"] == len(c)
        assert s["min_n_gate"] == 10
        assert s["gate_ok"] is (len(f) >= 10 and len(c) >= 10)
        assert all(r["stratifier_evidence"]["farm_driven"] for r in s["farm"])
        assert not any(r["stratifier_evidence"]["farm_driven"] for r in s["control"])


# --------------------------------------------------------------------------- #
# 3. the default path is unchanged                                              #
# --------------------------------------------------------------------------- #
class TestDefaultPathUnchanged:
    def test_replay_actions_signature_default_is_the_old_call(self):
        """`game_kwargs=None` must build the SAME board as the pre-change call. Compared
        on `string_representation`, which is the harness's own board identity."""
        import root_replay as RR
        from carcassonne_ai import rules_profile
        assert rules_profile.PROFILES["walled"].game_kwargs() == {}
        seed, actions = 28000000001, []
        g0, b0 = RR.replay_actions(seed, actions, 0)
        g1, b1 = RR.replay_actions(seed, actions, 0, game_kwargs=None)
        g2, b2 = RR.replay_actions(seed, actions, 0,
                                   game_kwargs=rules_profile.PROFILES["walled"].game_kwargs())
        assert g0.string_representation(b0) == g1.string_representation(b1)
        assert g0.string_representation(b0) == g2.string_representation(b2)

    def test_the_adapter_is_inert_when_its_flags_are_absent(self):
        """`_process` reads `_G["game_kwargs"]`, which the worker `_init` only receives
        when `--rules-profile` was given. With the flag absent the replay call degrades to
        `game_kwargs=None` — literally the pre-change call — so no banked record can move.
        """
        OSP = _load("oracle_score_pilot", "scripts/measurement_infra/oracle_score_pilot.py")
        OSP._G.clear()
        OSP._init({"backend": "python"})
        assert (OSP._G.get("game_kwargs") or None) is None
        src = (REPO / "scripts/measurement_infra/oracle_score_pilot.py").read_text()
        assert '"--positions-jsonl", default=None' in src
        assert '"--rules-profile", default=None' in src
        assert 'game_kwargs=(_G.get("game_kwargs") or None)' in src

    @pytest.mark.skipif(not (FW / "GATE_POSITIONS_JSONL.json").exists(),
                        reason="the numeric default-path gate has not been run")
    def test_banked_rescore_matches_field_by_field(self):
        g = json.loads((FW / "GATE_POSITIONS_JSONL.json").read_text())
        assert g["leg1_default_path"]["mismatches"] == []
        assert g["leg2_positions_jsonl"]["mismatches"] == []
        assert g["verdict"] == "PASS"


# --------------------------------------------------------------------------- #
# the decision map                                                              #
# --------------------------------------------------------------------------- #
class TestDecisionMap:
    def _s(self, mean, se, n=21):
        return {"n": n, "mean_delta_pts": mean, "se_cluster_root": se,
                "z_two_sided": mean / se,
                "ci95_lo": mean - AN.Z_95 * se, "ci95_hi": mean + AN.Z_95 * se,
                "ci95_covers_zero": (mean - AN.Z_95 * se) <= 0 <= (mean + AN.Z_95 * se)}

    def test_branch1_farm_positive_control_null(self):
        d = AN.decide(self._s(2.0, 0.5), self._s(0.1, 0.5))
        assert d["branch"] == 1 and d["mints_claim_id"] is True

    def test_branch2_farm_negative(self):
        d = AN.decide(self._s(-2.0, 0.5), self._s(0.1, 0.5))
        assert d["branch"] == 2 and d["mints_claim_id"] is False

    def test_branch3_needs_branch1_to_miss_first(self):
        """Precedence is real: both strata strongly positive and CONTROL >= half FARM
        fails branch 1's second clause, so branch 3 is reachable."""
        d = AN.decide(self._s(2.0, 0.3), self._s(1.8, 0.3))
        assert d["branch"] == 3 and d["mints_claim_id"] is True

    def test_branch1_wins_over_branch3_when_control_is_small(self):
        d = AN.decide(self._s(4.0, 0.3), self._s(1.0, 0.3))
        assert d["branch"] == 1

    def test_branch4_when_underpowered(self):
        d = AN.decide(self._s(1.0, 2.0), self._s(0.5, 2.0))
        assert d["branch"] == 4 and d["mints_claim_id"] is False

    def test_two_sided_is_two_sided(self):
        assert AN.decide(self._s(-2.0, 0.5), self._s(0.0, 0.5))["branch"] == 2
        assert AN.decide(self._s(-0.5, 0.5), self._s(0.0, 0.5))["branch"] == 4


class TestClusterRobustSe:
    def test_singleton_clusters_reduce_exactly_to_naive(self):
        """With one observation per cluster the CR1 correction G/(G-1) cancels the (n-1)
        in the residual sum, so the sandwich se is EXACTLY sd/sqrt(n) — which is why the
        root-clustered number here (each E4 ply is its own root) is a fact about the
        design, not a choice that could flatter the verdict."""
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        got = AN.cluster_se(vals, ["a", "b", "c", "d", "e"])
        naive = AN._sd(vals) / (len(vals) ** 0.5)
        assert got["n_clusters"] == 5
        assert got["se"] == pytest.approx(naive, rel=1e-12)
        assert got["design_effect"] == pytest.approx(1.0, rel=1e-12)

    def test_perfectly_correlated_clusters_inflate_the_se(self):
        vals = [1.0, 1.0, 1.0, -1.0, -1.0, -1.0]
        got = AN.cluster_se(vals, ["a"] * 3 + ["b"] * 3)
        naive = AN._sd(vals) / (len(vals) ** 0.5)
        assert got["se"] > naive
        assert got["design_effect"] > 1.0

    def test_epoch_sign_agreement_flag(self):
        rows = [{"rules_profile": "walled", "delta": 1.0},
                {"rules_profile": "fixed_v1", "delta": 2.0}]
        assert AN.per_epoch(rows)["_epochs_agree_in_sign"] is True
        rows[1]["delta"] = -2.0
        assert AN.per_epoch(rows)["_epochs_agree_in_sign"] is False
