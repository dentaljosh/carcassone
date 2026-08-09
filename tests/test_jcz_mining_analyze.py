"""Tests for the JCZ disagreement-mining analyzer + launcher
(measurement/jcz_mining_20260809/MINING_PREREG.md).

Each test class pins a distinct silent-failure mode:

  1. TestDecisionMapBranches — a wrong branch fires quietly and mis-directs a
     native term build (or fails to fund one that is real).
  2. TestSignConvention — pick_a/pick_b confusion anywhere flips
     CONVICT<->EXONERATE without any visible error.
  3. TestClusterSE — a bug in the CR1 sandwich either UNDER-reports SE (false
     positive convictions) or `cluster_consistency_ok` never fires False (a
     design-effect bug in the root/game clustering goes unnoticed).
  4. TestConvictedUncorroborated — a raw CONVICT ships as a plain CONVICT even
     though the out-of-family judge disagrees at chance, silently skipping the
     build-sequencing demotion PREREG §6 requires.
  5. TestWorkerClamp — a --workers value above the hard safety cap silently
     reaches the multiprocessing pool on Joshua's interactive machine.
  6. TestLauncherGate — the launcher starts compute beside a higher-priority
     tenant (memory: feedback_no_agent_compute_beside_eval) or refuses to run
     at all when nothing conflicts.
"""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
JCZ = REPO / "scripts/jcz_mining"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


AN = _load("analyze_mining", "scripts/jcz_mining/analyze_mining.py")
RM = _load("run_mining", "scripts/jcz_mining/run_mining.py")


def _s(mean: float, se: float, n: int, stratum: str = "X") -> dict:
    """Build a synthetic stratum_stats()-shaped dict directly from (mean, se, n).
    decide() only ever reads n / mean_delta_pts / z_two_sided / ci95_covers_zero
    from a stratum dict, so this is a faithful stand-in without needing real
    per-position rows."""
    z = mean / se if se else float("nan")
    lo, hi = mean - AN.Z_95 * se, mean + AN.Z_95 * se
    return {"stratum": stratum, "n": n, "mean_delta_pts": mean, "z_two_sided": z,
            "ci95_lo": lo, "ci95_hi": hi, "ci95_covers_zero": bool(lo <= 0.0 <= hi)}


# --------------------------------------------------------------------------- #
# 1. decision map, all branches                                                #
# --------------------------------------------------------------------------- #
class TestDecisionMapBranches:
    def test_g0_gate_fail_both_a_and_b(self):
        A, B, C = _s(1.0, 5.0, 5, "A"), _s(1.0, 5.0, 5, "B"), _s(1.0, 5.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] == "G0"
        assert dec["mints_claim_id"] is False
        assert dec["per_stratum"]["A"] == "INCONCLUSIVE_BY_CONSTRUCTION"
        assert dec["per_stratum"]["B"] == "INCONCLUSIVE_BY_CONSTRUCTION"

    def test_g0_requires_both_a_and_b_not_just_one(self):
        """A alone under the gate must NOT trigger G0 -- only BOTH A and B."""
        A = _s(1.0, 5.0, 5, "A")      # under gate (n=5 < 25)
        B = _s(0.1, 0.5, 40, "B")     # over gate, wash
        C = _s(0.1, 0.5, 80, "C")     # over gate, wash
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] != "G0"
        # A is still individually gate-failed regardless of the global branch.
        assert dec["per_stratum"]["A"] == "INCONCLUSIVE_BY_CONSTRUCTION"

    def test_g1_all_wash(self):
        A, B, C = _s(0.3, 1.0, 40, "A"), _s(0.3, 1.0, 40, "B"), _s(0.3, 1.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] == "G1"
        assert dec["mints_claim_id"] is False
        assert dec["per_stratum"]["S3"] == "NOT TESTED BY THIS DESIGN"

    def test_g2_not_localised(self):
        A = _s(3.0, 1.0, 40, "A")      # z=3
        B = _s(2.5, 1.0, 40, "B")      # z=2.5
        C = _s(1.5, 0.5, 80, "C")      # z=3, mean_C=1.5 >= 0.5*min(3.0,2.5)=1.25
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] == "G2"
        assert dec["mints_claim_id"] is True
        assert dec["per_stratum"]["A"] != "CONVICT"

    def test_g2_does_not_fire_when_control_mean_too_small(self):
        A = _s(3.0, 1.0, 40, "A")
        B = _s(2.5, 1.0, 40, "B")
        C = _s(0.5, 0.2, 80, "C")      # z=2.5 (sig) but mean_C=0.5 < 0.5*2.5=1.25
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] != "G2"
        assert dec["global_branch"] == "G3"

    def test_g3_a_convict_via_control_ci_covers_zero(self):
        A = _s(3.0, 1.0, 40, "A")      # z=3, mean>0
        B = _s(0.2, 1.0, 40, "B")      # wash
        C = _s(0.1, 2.0, 80, "C")      # ci covers zero
        assert C["ci95_covers_zero"] is True
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] == "G3"
        assert dec["per_stratum"]["A"].startswith("CONVICT")
        assert dec["mints_claim_id"] is True
        assert "S1" in dec["candidate_mapping"]["A"] and "S4" in dec["candidate_mapping"]["A"]

    def test_g3_a_convict_via_control_mean_less_than_half(self):
        A = _s(3.0, 1.0, 40, "A")
        B = _s(0.2, 1.0, 40, "B")
        C = _s(1.0, 0.1, 80, "C")      # huge z, ci does NOT cover 0, mean_C(1.0)<1.5
        assert C["ci95_covers_zero"] is False
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["per_stratum"]["A"].startswith("CONVICT")

    def test_g3_a_exonerate(self):
        A = _s(-3.0, 1.0, 40, "A")     # negative, |z|>=2
        B = _s(0.2, 1.0, 40, "B")
        C = _s(0.1, 2.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] == "G3"
        assert dec["per_stratum"]["A"] == "EXONERATE"
        assert "A" not in dec["candidate_mapping"]

    def test_g3_b_convict(self):
        A = _s(0.2, 1.0, 40, "A")
        B = _s(3.0, 1.0, 40, "B")
        C = _s(0.1, 2.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["per_stratum"]["B"].startswith("CONVICT")
        assert dec["candidate_mapping"]["B"] == "S2 deck-graded closure probability"

    def test_s3_never_gets_a_verdict(self):
        A, B, C = _s(3.0, 1.0, 40, "A"), _s(3.0, 1.0, 40, "B"), _s(3.0, 1.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["per_stratum"]["S3"] == "NOT TESTED BY THIS DESIGN"

    def test_precedence_g1_before_g2_before_g3(self):
        """All-wash beats every other reading even if some strata individually
        look 'significant enough' to a careless reader -- G1 fires first."""
        A, B, C = _s(0.1, 1.0, 40, "A"), _s(0.1, 1.0, 40, "B"), _s(0.1, 1.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["global_branch"] == "G1"

    def test_two_sidedness_large_negative_z_is_exonerate_never_convict(self):
        A = _s(-10.0, 1.0, 40, "A")
        B = _s(0.1, 1.0, 40, "B")
        C = _s(0.1, 2.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["per_stratum"]["A"] == "EXONERATE"
        assert "CONVICT" not in dec["per_stratum"]["A"]


# --------------------------------------------------------------------------- #
# 2. sign convention                                                            #
# --------------------------------------------------------------------------- #
class TestSignConvention:
    def test_jcz_pick_better_produces_positive_mean_and_convict_direction(self):
        """delta = mean(V_B - V_A) with pick_a=ours, pick_b=JCZ's -- a record set
        where JCZ's pick truly wins must land POSITIVE and CONVICT-direction,
        never silently flipped to EXONERATE."""
        rows = [{"rid": f"r{i}", "root_id": f"root{i}", "game_label": f"g{i}",
                "delta": 3.0 + 0.01 * i} for i in range(40)]
        A = AN.stratum_stats(rows, "A")
        assert A["mean_delta_pts"] > 0
        B = _s(0.1, 1.0, 40, "B")
        C = _s(0.1, 2.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["per_stratum"]["A"].startswith("CONVICT")

    def test_our_pick_better_produces_negative_mean_and_exonerate(self):
        """The mirror case -- OUR pick winning must land NEGATIVE and EXONERATE,
        proving the sign isn't just hardcoded positive somewhere."""
        rows = [{"rid": f"r{i}", "root_id": f"root{i}", "game_label": f"g{i}",
                "delta": -3.0 - 0.01 * i} for i in range(40)]
        A = AN.stratum_stats(rows, "A")
        assert A["mean_delta_pts"] < 0
        B = _s(0.1, 1.0, 40, "B")
        C = _s(0.1, 2.0, 80, "C")
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25)
        assert dec["per_stratum"]["A"] == "EXONERATE"


# --------------------------------------------------------------------------- #
# 3. cluster SE                                                                #
# --------------------------------------------------------------------------- #
class TestClusterSE:
    def test_singleton_clusters_reduce_exactly_to_naive(self):
        vals = [1.0, 2.0, 3.0, 10.0]
        clusters = ["r1", "r2", "r3", "r4"]
        got = AN.cluster_se(vals, clusters)
        naive = AN._sd(vals) / math.sqrt(len(vals))
        assert got["se"] == pytest.approx(naive, rel=1e-9)

    def test_perfectly_correlated_clusters_inflate_se(self):
        vals = [1.0, 1.0, 5.0, 5.0]
        clusters = ["a", "a", "b", "b"]
        got = AN.cluster_se(vals, clusters)
        naive = AN._sd(vals) / math.sqrt(len(vals))
        assert got["se"] > naive * 1.5

    def test_cluster_consistency_flags_divergence_as_bug_signal(self):
        rows = [
            {"root_id": "r1", "game_label": "g1", "delta": 1.0},
            {"root_id": "r2", "game_label": "g1", "delta": 1.0},
            {"root_id": "r3", "game_label": "g2", "delta": 5.0},
            {"root_id": "r4", "game_label": "g2", "delta": 5.0},
        ]
        s = AN.stratum_stats(rows, "X")
        assert s["se_cluster_root"] != pytest.approx(s["se_cluster_game"])
        assert s["cluster_consistency_ok"] is False

    def test_cluster_consistency_ok_under_one_position_per_game(self):
        """The pre-registered design (PREREG §4): one scored position per game
        -> every cluster is a singleton on BOTH root and game -> the two SEs
        must coincide."""
        rows = [{"root_id": f"r{i}", "game_label": f"g{i}", "delta": float(i)}
                for i in range(10)]
        s = AN.stratum_stats(rows, "X")
        assert s["cluster_consistency_ok"] is True
        assert s["se_cluster_root"] == pytest.approx(s["se_cluster_game"], rel=1e-9)


# --------------------------------------------------------------------------- #
# 4. CONVICTED_UNCORROBORATED labelling                                        #
# --------------------------------------------------------------------------- #
class TestConvictedUncorroborated:
    def test_convict_at_chance_tier1_sign_is_labelled_uncorroborated(self):
        A = _s(3.0, 1.0, 40, "A")      # raw CONVICT
        B = _s(0.1, 1.0, 40, "B")
        C = _s(0.1, 2.0, 80, "C")
        at_chance = {"n_scored": 20, "n_agree": 10, "agreement_rate": 0.5,
                     "binomial_p_two_sided": 1.0}
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25,
                        sign_checks={"A": at_chance, "B": None})
        assert dec["per_stratum"]["A"] == "CONVICTED_UNCORROBORATED"
        # still funds a build, per PREREG §6 -- just sequenced behind a
        # corroborated one, so mints_claim_id stays True.
        assert dec["mints_claim_id"] is True
        assert "A" in dec["candidate_mapping"]

    def test_convict_corroborated_stays_plain_convict(self):
        A = _s(3.0, 1.0, 40, "A")
        B = _s(0.1, 1.0, 40, "B")
        C = _s(0.1, 2.0, 80, "C")
        corroborated = {"n_scored": 30, "n_agree": 24, "agreement_rate": 0.8,
                        "binomial_p_two_sided": 0.0012}
        dec = AN.decide({"A": A, "B": B, "C": C}, min_n_gate=25,
                        sign_checks={"A": corroborated, "B": None})
        assert dec["per_stratum"]["A"] == "CONVICT"

    def test_sign_corroborates_helper_directly(self):
        assert AN.sign_corroborates(
            {"n_scored": 30, "agreement_rate": 0.8, "binomial_p_two_sided": 0.0012}) is True
        assert AN.sign_corroborates(
            {"n_scored": 30, "agreement_rate": 0.619, "binomial_p_two_sided": 0.38}) is False
        assert AN.sign_corroborates(None) is False
        assert AN.sign_corroborates({"n_scored": 0}) is False


# --------------------------------------------------------------------------- #
# 5. worker clamp                                                              #
# --------------------------------------------------------------------------- #
class TestWorkerClamp:
    @pytest.mark.parametrize("requested,expected", [(14, 14), (16, 14), (32, 14), (8, 8)])
    def test_clamp(self, requested, expected):
        assert RM.clamp_workers(requested) == expected

    def test_help_works_without_heavy_imports(self):
        """--help must exit 0 fast -- proves argparse setup doesn't accidentally
        import carcassonne_ai (and its env-latching side effects) at module
        scope."""
        r = subprocess.run([sys.executable, str(JCZ / "run_mining.py"), "--help"],
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 0
        assert "--workers" in r.stdout


# --------------------------------------------------------------------------- #
# 6. launcher gate                                                              #
# --------------------------------------------------------------------------- #
LAUNCHER = JCZ / "launch_mining.sh"


def _any_blocked_pattern_running() -> bool:
    """True if a REAL process on this box already matches one of the launcher's
    blocked patterns (e.g. the phase-arm ladder's own night_chain/pull_and_chain.sh
    is legitimately running). In that case the launcher's refusal on the "clean"
    tests below is CORRECT behaviour, not a bug -- skip rather than fight it."""
    for pat in ("eval_fair_puct.py", "curvephase_ladder_launcher.sh", "phase_seam_gate",
               "night_chain", "pull_and_chain.sh", "oracle_score_pilot.py"):
        if subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode == 0:
            return True
    return False


_BLOCKED_ALREADY_RUNNING = _any_blocked_pattern_running()


class TestLauncherGate:
    def test_bash_syntax_ok(self):
        subprocess.run(["bash", "-n", str(LAUNCHER)], check=True)

    def test_refuses_when_blocked_pattern_running(self, tmp_path):
        """A decoy process whose command line matches one of the blocked patterns
        must make the launcher refuse -- the phase-arm ladder has first claim on
        the box and this is the ONLY thing standing between it and a
        DRAM-latency-bound eval running alongside it (memory:
        feedback_no_agent_compute_beside_eval)."""
        decoy = tmp_path / "phase_seam_gate_decoy.sh"
        decoy.write_text("#!/bin/bash\nsleep 30\n")
        decoy.chmod(0o755)
        proc = subprocess.Popen(["bash", str(decoy)])
        try:
            for _ in range(20):
                if subprocess.run(["pgrep", "-f", "phase_seam_gate_decoy.sh"],
                                  capture_output=True).returncode == 0:
                    break
                time.sleep(0.1)
            r = subprocess.run(["bash", str(LAUNCHER), "--dry-run"],
                               capture_output=True, text=True)
            assert r.returncode != 0
            assert "phase_seam_gate" in (r.stdout + r.stderr)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            subprocess.run(["pkill", "-f", "phase_seam_gate_decoy.sh"], check=False)

    @pytest.mark.skipif(_BLOCKED_ALREADY_RUNNING,
                        reason="a real blocked-pattern process is already running on "
                               "this box -- the launcher's refusal is correct, not a "
                               "bug; the process-gate itself is covered by "
                               "test_refuses_when_blocked_pattern_running")
    def test_clean_dry_run_with_fixture_strata(self, tmp_path):
        """With nothing conflicting and a valid gate_ok STRATA.json, --dry-run
        must exit 0 and print the exact command it would run -- never launch
        anything. Uses --strata to point at a throwaway fixture so this does
        not depend on the extractor having produced real strata yet."""
        strata = tmp_path / "STRATA.json"
        strata.write_text(json.dumps({
            "schema": "carcassonne-jcz-mining-strata/v1",
            "gate_ok": True, "min_n_gate": 25, "k_late": 14, "rows": [],
        }))
        r = subprocess.run(["bash", str(LAUNCHER), "--dry-run", "--strata", str(strata)],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
        assert "run_mining.py" in r.stdout
        assert "Would run" in r.stdout

    @pytest.mark.skipif(_BLOCKED_ALREADY_RUNNING,
                        reason="a real blocked-pattern process is already running on "
                               "this box -- would refuse on the process gate before "
                               "ever reaching the gate_ok check")
    def test_refuses_cleanly_when_gate_ok_is_false(self, tmp_path):
        strata = tmp_path / "STRATA.json"
        strata.write_text(json.dumps({
            "schema": "carcassonne-jcz-mining-strata/v1",
            "gate_ok": False, "min_n_gate": 25, "k_late": 14, "rows": [],
        }))
        r = subprocess.run(["bash", str(LAUNCHER), "--dry-run", "--strata", str(strata)],
                           capture_output=True, text=True)
        assert r.returncode != 0
        assert "gate_ok" in (r.stdout + r.stderr)

    @pytest.mark.skipif(_BLOCKED_ALREADY_RUNNING,
                        reason="a real blocked-pattern process is already running on "
                               "this box -- would refuse on the process gate before "
                               "ever reaching the strata-existence check")
    def test_missing_strata_is_a_clean_explanatory_refusal(self):
        """If the real extractor output does not exist yet (fresh checkout, or
        the sibling extractor hasn't landed), the launcher must refuse cleanly
        rather than crash uninformatively."""
        r = subprocess.run(["bash", str(LAUNCHER), "--dry-run",
                            "--strata", "/nonexistent/STRATA.json"],
                           capture_output=True, text=True)
        assert r.returncode != 0
        assert "does not exist" in (r.stdout + r.stderr)
