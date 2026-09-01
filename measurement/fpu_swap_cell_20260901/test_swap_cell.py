#!/usr/bin/env python3
"""pytest contract tests for the FPU-SWAP CELL instrument.

Run from the repo (or this worktree) root:
    pytest measurement/fpu_swap_cell_20260901/test_swap_cell.py -q

⛔ These duplicate a subset of `adjudicate_swap_cell.py --selftest` under
pytest so CI/collection picks them up automatically; `--selftest` remains the
launcher's own precondition-ladder check (it must run standalone, without
pytest, because `launch_swap_cell.sh` shells out to it directly).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import screen_lib as L                        # noqa: E402
import adjudicate_swap_cell as A               # noqa: E402


# =========================================================================== #
# screen_lib arithmetic                                                       #
# =========================================================================== #

def test_sanity_check_clean():
    problems = L.sanity_check()
    assert problems == [], problems


def test_se_400_matches_model():
    assert abs(L.se_model(400) - L.SE_400) < 1e-9


def test_deployed_tiearb_matches_module():
    import tiearb_gates as TA
    assert L.DEPLOYED_TIEARB == TA.DEPLOYED_TIEARB_B64


@pytest.mark.parametrize("m,se,expect", [
    (-10.0, 0.3, "SWAP-KILLED"),
    (10.0, 0.3, "SWAP-SURPRISE"),
    (0.0, 0.69, "SWAP-UNRESOLVED"),
    (-1.0 - 2 * L.SE_400 - 1e-6, L.SE_400, "SWAP-KILLED"),   # just past the bar
    (-1.0 - 2 * L.SE_400 + 1e-6, L.SE_400, "SWAP-UNRESOLVED"),  # just short
])
def test_branch_sign_convention_pinned(m, se, expect):
    """⛔ THE SIGN CONVENTION IS PINNED HERE. `M` is candidate(fpu,arb-off)
    minus opponent(arb-on) — a NEGATIVE `M` means the arb-on opponent won,
    which is the branch this whole round expects to fire (SWAP-KILLED)."""
    assert L.branch_for_cell(m, se, gates_ok=True) == expect


def test_branch_mutually_exclusive_on_a_grid():
    for m10 in range(-800, 801, 4):
        m = m10 / 100.0
        for se10 in (10, 30, 50, 69, 90, 140, 200):
            se = se10 / 100.0
            b = L.branch_for_cell(m, se, gates_ok=True)
            assert b in L.BRANCHES
            ub95, lb95 = m + 2 * se, m - 2 * se
            if b == "SWAP-KILLED":
                assert ub95 <= -L.BAR_SWAP
                assert not (lb95 > 0)
            elif b == "SWAP-SURPRISE":
                assert lb95 > 0
                assert not (ub95 <= -L.BAR_SWAP)


def test_gates_not_ok_forces_void_regardless_of_m():
    assert L.branch_for_cell(-100.0, 0.1, gates_ok=False) == "U-VOID-INSTRUMENT"
    assert L.branch_for_cell(100.0, 0.1, gates_ok=False) == "U-VOID-INSTRUMENT"


def test_missing_stats_force_void():
    assert L.branch_for_cell(None, 0.5, gates_ok=True) == "U-VOID-INSTRUMENT"
    assert L.branch_for_cell(1.0, None, gates_ok=True) == "U-VOID-INSTRUMENT"


def test_power_table_sums_to_one_and_is_monotone():
    prev_killed = -1.0
    for delta in (0.0, L.BAR_SWAP, L.FUNDING_BRIEF_ARB_ADVANTAGE_PRIOR, 2.0,
                 L.ARITHMETIC_RECONSTRUCTION_ARB_ADVANTAGE, 3.0, 5.0):
        pw = L.power_at(delta, L.SE_400)
        total = pw["p_killed"] + pw["p_surprise"] + pw["p_unresolved"]
        assert abs(total - 1.0) < 1e-6
        assert pw["p_killed"] >= prev_killed - 1e-9
        prev_killed = pw["p_killed"]
        assert 0.0 <= pw["p_killed"] <= 1.0
        assert 0.0 <= pw["p_surprise"] <= 1.0


def test_power_table_surprise_negligible_under_positive_prior():
    """The prior in every PRIOR_ART row points the same (arb-favoring)
    direction — SWAP-SURPRISE should be many orders of magnitude below
    SWAP-KILLED under any of the priors this doc actually carries."""
    for delta in (L.FUNDING_BRIEF_ARB_ADVANTAGE_PRIOR,
                 L.ARITHMETIC_RECONSTRUCTION_ARB_ADVANTAGE):
        pw = L.power_at(delta, L.SE_400)
        assert pw["p_surprise"] < 1e-3
        assert pw["p_killed"] > pw["p_surprise"] * 10


# =========================================================================== #
# per_deck_margins / paired_margin / winrate_elo                              #
# =========================================================================== #

def test_per_deck_margins_drops_half_played():
    recs = [
        {"seed": 1, "a_seat": 0, "diff": 2.0},
        {"seed": 1, "a_seat": 1, "diff": -1.0},
        {"seed": 2, "a_seat": 0, "diff": 5.0},   # no seat 1 -> dropped
    ]
    dm = L.per_deck_margins(recs)
    assert dm == {1: 0.5}


def test_paired_margin_sign_matches_candidate_minus_opponent():
    # candidate crushed opponent on every deck -> positive M
    recs = [{"seed": s, "a_seat": a, "diff": 4.0} for s in range(5) for a in (0, 1)]
    mean, z, n, se, _ = L.paired_margin(recs)
    assert mean == pytest.approx(4.0)
    assert n == 5


def test_winrate_elo_candidate_referenced():
    recs = [{"seed": s, "a_seat": a, "diff": 1.0, "won_by_champ": True,
            "drew": False} for s in range(10) for a in (0, 1)]
    we = L.winrate_elo(recs)
    assert we["W"] == 20 and we["L"] == 0
    assert we["elo"] > 0


# =========================================================================== #
# gates on a hand-built (non-fixture) manifest — the ABSENT-is-FAIL contract  #
# =========================================================================== #

def _bare_manifest(**overrides) -> dict:
    m = {
        "host": "laptop-wsl",
        "code_rev": "a" * 40,
        "BLIND_COMMIT": "b" * 40,
        "carc_rs_build": "carc_rs-0.1.0+deadbeef",
        "carc_rs_binary_sha": "deadbeef" * 5,
        "mixed_builds": False,
        "config": {
            "cand_search": {"fpu_reduction": 0.2},
            "champion": {"fpu_reduction": 0.2, "k_dets": 16, "sims_per_det": 1376,
                        "total_sims": 22016},
            "opponent": {"champ_cfg": {"fpu_reduction": None, "k_dets": 16,
                                       "sims_per_det": 1376, "total_sims": 22016}},
            "endgame": {"exact_k": 2, "mode": "marginalized"},
            "backend": {"name": "rust", "requested": "rust", "mixed_builds": False},
            "cand_leaf_hash": L.LEAF_HASH, "opp_leaf_hash": L.LEAF_HASH,
            "band_seed_start": 170_000_000_000, "n_decks": 400,
            "seatings_per_deck": 2,
        },
        "rules_profile": {"name": "fixed_v1", "r9_env_ok": True,
                          "r9_env_observed": True},
        "opp_tiearb": dict(L.DEPLOYED_TIEARB),
    }
    m.update(overrides)
    return m


def test_gate_fpu_absent_is_fail():
    g = L.fpu_knob_gate({})
    assert g["ok"] is False
    assert "ABSENT" in g["why"]


def test_gate_fpu_null_is_positive_statement_not_missing():
    """`fpu_reduction: null` on the REQUEST side means "not requested", and
    must fail — MISSING (the key absent) and None (the key present, null) are
    different claims and both are handled, but neither passes this cell."""
    m = _bare_manifest()
    m["config"]["cand_search"]["fpu_reduction"] = None
    g = L.fpu_knob_gate(m)
    assert g["ok"] is False


def test_gate_arb_asym_healthy():
    m = _bare_manifest()
    g = L.arb_asymmetry_gate(m)
    assert g["ok"] is True, g["why"]


def test_gate_arb_asym_fails_if_candidate_also_armed():
    m = _bare_manifest()
    m["cand_tiearb"] = dict(L.DEPLOYED_TIEARB)
    g = L.arb_asymmetry_gate(m)
    assert g["ok"] is False


def test_gate_arb_asym_fails_if_opponent_unarmed():
    m = _bare_manifest()
    del m["opp_tiearb"]
    g = L.arb_asymmetry_gate(m)
    assert g["ok"] is False


def test_gate_arb_fired_requires_nonzero_opp_fires():
    summ = {"opp_tiearb_games": 8, "opp_tiearb_fired_plies_total": 0}
    g = L.arb_fired_gate(summ)
    assert g["ok"] is False


def test_gate_arb_fired_fails_if_candidate_fired_too():
    summ = {"opp_tiearb_games": 8, "opp_tiearb_fired_plies_total": 3,
           "tiearb_games": 8, "tiearb_fired_plies_total": 1}
    g = L.arb_fired_gate(summ)
    assert g["ok"] is False


def test_gate_arb_fired_healthy():
    summ = {"opp_tiearb_games": 8, "opp_tiearb_fired_plies_total": 5}
    g = L.arb_fired_gate(summ)
    assert g["ok"] is True, g["why"]


# =========================================================================== #
# empty-archive contract at the adjudicator level                             #
# =========================================================================== #

def test_empty_archive_never_passes_gates():
    empty = {"root": "<empty>", "manifest": None, "summary": None, "records": []}
    r = A.adjudicate_cell(empty, claimed_band=None, pinned_src_rev=None)
    assert r["gates_ok"] is False
    assert r["branch"] == "U-VOID-INSTRUMENT"
    for g in r["gates"]:
        assert g["ok"] is False, f"{g['gate']} passed on an empty archive"


def test_smoke_problems_nonempty_on_missing_manifest():
    cell = {"root": "<empty>", "manifest": None, "summary": None, "records": []}
    probs = A.smoke_problems(cell)
    assert probs, "an empty smoke cell must report problems, never pass silently"


# =========================================================================== #
# the full selftest, run once here too so `pytest` alone catches a regression #
# =========================================================================== #

def test_full_selftest_passes():
    assert A.selftest() == 0


# =========================================================================== #
# ⭐⭐ THE REAL-EMITTER FIXTURE — the FIXTURE-TRAP guard                        #
# =========================================================================== #

FIXTURE = HERE / "selftest_fixture"


def test_fixture_exists_and_is_from_a_real_emitter():
    """Guards the FIXTURE-TRAP named in this round's own brief: a hand-authored
    JSON fixture proves nothing about the harness. `manifest.json` must carry
    the keys ONLY the real `eval_fair_puct.py` emits (a build/version stamp
    that would be tedious to fabricate by hand, and normally is not)."""
    assert FIXTURE.is_dir(), "selftest_fixture/ is missing"
    man_path = FIXTURE / "manifest.json"
    assert man_path.is_file(), (
        "selftest_fixture/manifest.json is missing — run "
        "`launch_swap_cell.sh --smoke` (or the tiny-budget verification smoke "
        "in the build report) once and copy its output here")
    man = json.loads(man_path.read_text())
    for key in ("carc_rs_build", "carc_rs_binary_sha", "host", "code_rev"):
        assert key in man, (
            f"selftest_fixture/manifest.json has no {key!r} — this does not "
            "look like real eval_fair_puct.py output; the FIXTURE-TRAP says "
            "fixtures must come from the real emitter only")


def test_fixture_reads_as_the_intended_asymmetric_shape():
    man_path = FIXTURE / "manifest.json"
    if not man_path.is_file():
        pytest.skip("fixture not built yet")
    man = json.loads(man_path.read_text())
    g_fpu = L.fpu_knob_gate(man)
    g_asym = L.arb_asymmetry_gate(man)
    assert g_fpu["ok"], g_fpu["why"]
    assert g_asym["ok"], g_asym["why"]


def test_fixture_positive_control_fired_in_play():
    summ_path = FIXTURE / "summary.json"
    if not summ_path.is_file():
        pytest.skip("fixture not built yet")
    summ = json.loads(summ_path.read_text())
    g = L.arb_fired_gate(summ)
    assert g["ok"], (
        f"{g['why']} — the fixture's arbiter never fired in play; either "
        "re-smoke with more games/a position more likely to tie, or accept "
        "this as the disclosed 'inconclusive, not proof of failure' case "
        "PREREG.md §6 names for a tiny smoke, and note it in the build report")


def test_fixture_defects_each_fail_their_named_gate():
    """Re-run of `adjudicate_swap_cell.FIXTURE_DEFECTS` as individual pytest
    cases, so a broken single defect shows up as ITS OWN failing test rather
    than one line in a combined selftest dump."""
    man_path = FIXTURE / "manifest.json"
    if not man_path.is_file():
        pytest.skip("fixture not built yet")
    healthy = A.load_cell(FIXTURE)
    for name, mutate, expect_gate in A.FIXTURE_DEFECTS:
        broken = A._deep_copy_cell(healthy)
        try:
            mutate(broken)
        except Exception:                                        # noqa: BLE001
            continue   # some defects don't apply to every fixture shape
        bv = A.adjudicate_cell(broken, claimed_band=None, pinned_src_rev=None)
        by_id = {g["gate"]: g["ok"] for g in bv["gates"]}
        assert by_id.get(expect_gate) is False, (
            f"defect {name!r} did not fail {expect_gate!r} "
            f"(failed gates: {bv['failed_gates']})")
