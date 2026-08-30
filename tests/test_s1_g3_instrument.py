"""S1 GATE G3's instrument invariants (`measurement/s1_asymmetry_prep/`).

⛔ These test the INSTRUMENT, not a cell: 0 games exist. They exist because the
launcher-side checks run once per round and are therefore never exercised by the
smoke, and because a gate nobody has seen FAIL is a gate nobody has tested.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "s1_asymmetry_prep"
FIXTURE = PREP / "selftest_fixture_g3"

pytestmark = pytest.mark.skipif(not PREP.is_dir(), reason="prep dir absent")


# --------------------------------------------------------------------------- #
# ⛔⛔ IMPORT ISOLATION — the 2026-08-30 R2 fix pattern, carried.                #
# --------------------------------------------------------------------------- #
# `measurement/phasegate_prep/` and `measurement/fpu_resurrection_prep/` BOTH
# ship a module named `screen_lib`; a `sys.path.insert` + bare import in one test
# file bound the WRONG library in any run that collected both (21 failures, of
# which the dangerous ones were the ~2 that PASSED against the other round's
# constants). This round's library is `screen_lib_g3.py` — a name that cannot
# collide — but it is STILL loaded by EXPLICIT PATH under a UNIQUE module name,
# because relying on a filename to be unique is how the collision happened.
def _load_by_path(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_G3_L = _load_by_path("s1_g3_screen_lib_under_test", PREP / "screen_lib_g3.py")
_G3_A = _load_by_path("s1_g3_analyze_under_test", PREP / "analyze_g3.py")


@pytest.fixture(scope="module")
def L():
    return _G3_L


@pytest.fixture(scope="module")
def A():
    return _G3_A


def test_the_g3_library_is_not_a_siblings_screen_lib(L):
    """⛔⛔ R2's regression pin. If this fails, the suite is testing another
    round's fork under this file's name and its assertions pass VACUOUSLY."""
    assert Path(L.__file__).parent == PREP
    assert L.__name__ == "s1_g3_screen_lib_under_test"
    # the discriminators: the FPU fork is THREE bands / a knob table; phasegate
    # is ONE band and four cells; this round is ONE band, THREE SCOPES, and owns
    # a witness contract neither sibling has.
    assert not hasattr(L, "BANDS"), "this is the FPU screen_lib, not G3's"
    assert L.BAND == 161_000_000_000
    assert {c.scope for c in L.CELLS} == {"opp", "own", "all"}
    assert hasattr(L, "WITNESS_ADDRESSES") and hasattr(L, "witness_gate")


# --------------------------------------------------------------------------- #
# THE LIBRARY'S OWN INVARIANTS                                                  #
# --------------------------------------------------------------------------- #

def test_sanity_check_is_clean(L):
    assert L.sanity_check() == []


def test_every_branch_is_reachable(L):
    grid = L.branch_grid(step=0.05)
    assert grid["all_reachable"], grid["unreachable"]


def test_one_shared_deck_set_not_three_bands(L):
    """⭐ DESIGN §6.4 / SIZING §6: P2 is a PER-DECK cross-arm contrast, so the
    two gated arms MUST walk the same seeds and ALL must be a prefix subset."""
    opp, own, alla = (L.cell_by_name(n) for n in
                      ("CELL_G3_OPP", "CELL_G3_OWN", "CELL_G3_ALL"))
    assert opp.seed_start == own.seed_start == alla.seed_start == L.BAND
    assert opp.n_decks == own.n_decks == 600
    assert alla.n_decks == 400 and alla.seed_end <= opp.seed_end


def test_scope_is_the_only_variable_across_arms(L):
    assert len({c.dose for c in L.CELLS}) == 1
    assert len({c.mask for c in L.CELLS}) == 1
    assert len({c.scope for c in L.CELLS}) == 3
    assert all(c.dose == 0.25 and c.mask == 31 for c in L.CELLS)


def test_the_frozen_power_arithmetic_matches_SIZING(L):
    """The bars in READ_RULE_G3 §4 are arithmetic, not vibes."""
    assert L.se_model(600) == pytest.approx(0.5144, abs=5e-4)
    assert L.se_model(400) == pytest.approx(0.6300, abs=5e-4)
    assert L.se_model_contrast(600) == pytest.approx(0.7275, abs=1e-3)
    # SIZING §4.1: D=+2 reads z ~= 2.75 at n=1,200/arm
    assert 2.0 / L.se_model_contrast(600) == pytest.approx(2.75, abs=0.02)
    # ...and the design's own predicted +1 on P1 is INCONCLUSIVE, which is the
    # uncomfortable line the read rule states pre-outcome.
    assert 1.0 / L.se_model(600) < L.HOLM_Z[1]


def test_the_house_thumbrule_is_recorded_as_context_not_used(L):
    """⚠️ n=400 paired ~= +-12 elo extrapolates to ~8.7 at n=800; the REALIZED
    figure is 12.285. The library must carry the realized one."""
    assert L.SIGMA_ELO_800 == pytest.approx(12.285)
    thumb_at_800 = L.HOUSE_THUMB_ELO_400_PAIRED / math.sqrt(2.0)
    assert L.sigma_elo(800) > thumb_at_800 * 1.3


def test_holm_is_step_down_two_sided(L):
    assert L.HOLM_Z[0] > L.NOMINAL_Z > L.HOLM_Z[1]
    assert L.holm(3.0, 1.0)["P1_clears"] and not L.holm(3.0, 1.0)["P2_clears"]
    # 2.1 is above the nominal 2.0 but BELOW step 1 -> the ladder stops
    h = L.holm(2.1, 2.1)
    assert not h["P1_clears"] and not h["P2_clears"]
    assert all(leg["clears_nominal_2sigma"] for leg in h["legs"])
    h = L.holm(2.3, 2.0)
    assert h["P1_clears"] and h["P2_clears"]


def test_p2_is_a_per_deck_contrast_not_a_difference_of_means(L):
    """⭐ The CRN must actually buy variance. Two arms with a large SHARED deck
    effect must give a P2 se far below the naive rho=0 model."""
    a = [{"seed": 1000 + i, "a_seat": s,
          "diff": 40.0 * math.sin(i) + (2.0 if s == 0 else 2.0)}
         for i in range(60) for s in (0, 1)]
    b = [{"seed": 1000 + i, "a_seat": s,
          "diff": 40.0 * math.sin(i) + (0.0 if s == 0 else 0.0)}
         for i in range(60) for s in (0, 1)]
    r = L.paired_contrast(a, b)
    assert r["n_common"] == 60
    assert r["D"] == pytest.approx(2.0, abs=1e-9)
    assert r["se"] == pytest.approx(0.0, abs=1e-9)   # the deck effect cancels
    assert r["rho_realized"] == pytest.approx(1.0, abs=1e-9)


def test_a_deck_missing_a_seating_is_dropped_never_zero_filled(L):
    recs = [{"seed": 1, "a_seat": 0, "diff": 5.0},
            {"seed": 1, "a_seat": 1, "diff": 5.0},
            {"seed": 2, "a_seat": 0, "diff": 5.0}]
    assert list(L.per_deck_margins(recs)) == [1]


# --------------------------------------------------------------------------- #
# G-WITNESS — the gate this round exists for                                    #
# --------------------------------------------------------------------------- #

ARMED = {"total": 1000, "own_mover": 500, "boosted": 460}
UNARMED = {"total": 0, "own_mover": 0, "boosted": 0}


def _spec(L, scope="opp"):
    return L.cell_by_name({"opp": "CELL_G3_OPP", "own": "CELL_G3_OWN",
                           "all": "CELL_G3_ALL"}[scope])


def test_witness_passes_on_the_emitters_real_shape(L):
    """⚠️⚠️ THE UNARMED SIDE READS ALL ZEROS — the R7 counters live inside the
    `dose != 0` branch. A gate asserting `opponent.total > 0` would fail EVERY
    healthy cell (the PG-A1 shape), so this test pins the opposite."""
    g = L.witness_gate(_spec(L, "opp"), dict(ARMED), "summary:jr_expansions.candidate",
                       dict(UNARMED), "summary:jr_expansions.opponent")
    assert g["ok"], g["why"]
    assert g["detail"]["opponent"] == UNARMED


def test_witness_voids_when_absent_at_both_addresses(L):
    g = L.witness_gate(_spec(L), L.MISSING, None, L.MISSING, None)
    assert not g["ok"]
    assert "ABSENT is VOID" in g["why"]


@pytest.mark.parametrize("mut,why", [
    ({"boosted": 0}, "the knob never bound in play"),
    ({"total": 0, "own_mover": 0, "boosted": 0}, "the armed census never ran"),
    ({"boosted": 501}, "the boost escaped the opp scope (total-own_mover=500)"),
    ({"own_mover": 2000}, "own_mover exceeds total"),
])
def test_witness_hard_checks_fire(L, mut, why):
    cand = {**ARMED, **mut}
    g = L.witness_gate(_spec(L, "opp"), cand, "a", dict(UNARMED), "b")
    assert not g["ok"], why


def test_witness_fires_when_the_knob_bound_on_BOTH_sides(L):
    g = L.witness_gate(_spec(L, "own"), dict(ARMED), "a",
                       {**UNARMED, "boosted": 7}, "b")
    assert not g["ok"]
    assert "BOTH SIDES" in g["why"]


@pytest.mark.parametrize("scope,boosted,ok", [
    ("own", 500, True), ("own", 501, False),
    ("opp", 500, True), ("opp", 501, False),
    ("all", 1000, True), ("all", 1001, False),
])
def test_witness_scope_denominator_is_the_disjointness_check(L, scope, boosted, ok):
    """⭐ The machine-checkable half of DESIGN §9.2(c): own and opp boost
    disjoint sets whose union is all's."""
    g = L.witness_gate(_spec(L, scope), {**ARMED, "boosted": boosted}, "a",
                       dict(UNARMED), "b")
    assert g["ok"] is ok


def test_low_coverage_is_ADVISORY_not_a_void(L):
    """⛔ A hard equality here would be the PG-A1 shape — terminal and
    no-legal-child expansions legitimately boost nothing."""
    g = L.witness_gate(_spec(L, "opp"), {**ARMED, "boosted": 10}, "a",
                       dict(UNARMED), "b")
    assert g["ok"]
    assert g["detail"]["advisories"], "a below-floor coverage must be FLAGGED"
    assert g["detail"]["coverage"] == pytest.approx(0.02)


def test_the_witness_contract_names_both_emitted_addresses(L):
    """⭐ The R7 build writes the block twice; a cell must not void on a
    spelling (the cand_tiearb.fires precedent)."""
    for side, expect in (("candidate", "cand_jr_expansions"),
                         ("opponent", "opp_jr_expansions")):
        addrs = L.WITNESS_ADDRESSES[side]
        assert f"summary:jr_expansions.{side}" in addrs
        assert f"summary:{expect}" in addrs


# --------------------------------------------------------------------------- #
# G-SINGLEVAR — the asymmetric-emission trap                                    #
# --------------------------------------------------------------------------- #

def test_singlevar_tolerates_the_emitters_ASYMMETRIC_fpu_reduction(L):
    """⚠️ `as_manifest()` does NOT emit `fpu_reduction` for the candidate, but
    `champ_cfg_dict` states it POSITIVELY for the opponent. A bare
    present-on-one-side-only rule would void every healthy cell (PG-A1)."""
    rows = {a: {"champion": 1.5, "opponent": 1.5, "champion_absent": False,
                "opponent_absent": False, "addresses": ["m", "o"]}
            for a in L.SINGLEVAR_ALIASES}
    rows["fpu_reduction"] = {"champion": None, "opponent": None,
                             "champion_absent": True, "opponent_absent": False,
                             "addresses": [None, "o"]}
    g = L.singlevar_gate(_spec(L), rows)
    assert g["ok"], g["why"]
    # ...but a NON-default value on the one emitted side is still a defect
    rows["fpu_reduction"]["opponent"] = 0.2
    assert not L.singlevar_gate(_spec(L), rows)["ok"]


def test_singlevar_is_not_a_vacuous_pass_on_an_empty_manifest(L):
    rows = {a: {"champion": None, "opponent": None, "champion_absent": True,
                "opponent_absent": True, "addresses": [None, None]}
            for a in tuple(L.SINGLEVAR_ALIASES) + tuple(L.SINGLEVAR_ONESIDED_DEFAULTS)}
    assert not L.singlevar_gate(_spec(L), rows)["ok"]


# --------------------------------------------------------------------------- #
# THE INVERTED HASH GATE                                                        #
# --------------------------------------------------------------------------- #

def test_leaf_gate_is_INVERTED(L):
    """Surface B moves NO leaf hash, so EQUALITY is required and a MOVED hash is
    the defect — the opposite sense of an ordinary cell."""
    assert L.leaf_gate(L.LEAF_HASH, L.LEAF_HASH)["ok"]
    assert not L.leaf_gate("deadbeef", L.LEAF_HASH)["ok"]
    assert not L.leaf_gate(None, L.LEAF_HASH)["ok"]


# --------------------------------------------------------------------------- #
# THE ADJUDICATOR AND THE LAUNCHER                                              #
# --------------------------------------------------------------------------- #

def test_selftest_passes(A):
    assert A.selftest() == 0


def test_the_shipped_fixture_is_shaped_like_the_EMITTER(A, L):
    """⛔⛔ PG-A1: a fixture written to the GATE's expectation tests nothing.
    These keys are the ones a real `eval_fair_puct` archive carries, at the
    addresses it carries them."""
    man = json.loads((FIXTURE / "CELL_G3_OPP" / "manifest.json").read_text())
    summ = json.loads((FIXTURE / "CELL_G3_OPP" / "summary.json").read_text())
    # the opponent's budget is one level UP from champ_cfg; champ_cfg is the
    # FIVE-key dict plus the positively-stated fpu_reduction
    assert "k_dets" not in man["config"]["opponent"]["champ_cfg"]
    assert man["config"]["opponent"]["k_dets"] == 16
    assert man["config"]["opponent"]["champ_cfg"]["fpu_reduction"] is None
    # the candidate block does NOT carry fpu_reduction
    assert "fpu_reduction" not in man["config"]["champion"]
    # the resolved surface-B dict, and the leaf that must NOT move
    assert man["config"]["cand_jrules_prior"] == {"dose": 0.25, "mask": 31,
                                                  "scope": "opp"}
    assert man["config"]["cand_leaf_hash"] == L.LEAF_HASH
    # summary statistics under the emitter's real names, including the field
    # trap: the CANDIDATE is champ_prefix_ms_per_move
    for k in ("paired_mean_margin", "paired_z", "n_paired", "winrate",
              "avg_diff", "n_failed", "champ_prefix_ms_per_move",
              "rung_ms_per_move"):
        assert k in summ, k
    # ...and the R7 witness at BOTH addresses, with an all-zero unarmed side
    assert summ["jr_expansions"]["opponent"] == {"total": 0, "own_mover": 0,
                                                 "boosted": 0}
    assert summ["cand_jr_expansions"]["boosted"] > 0
    rec = json.loads((FIXTURE / "CELL_G3_OPP" /
                      "seed161000000000_a0.json").read_text())
    for k in ("seed", "a_seat", "diff", "won_by_champ", "drew",
              "cand_jr_expansions", "opp_jr_expansions"):
        assert k in rec, k


def test_n4_reads_the_candidate_side_from_the_right_field(A, L):
    """⚠️ `champ_prefix_ms_per_move` is the CANDIDATE, `rung_ms_per_move` the
    OPPONENT (feedback_verify_numbers_before_reporting)."""
    r = L.n4_cost_rider({"champ_prefix_ms_per_move": 3828.0,
                         "rung_ms_per_move": 3547.0})
    assert r["ms_ratio_cand_over_opp"] == pytest.approx(3828.0 / 3547.0)
    assert r["fired"] is False
    assert L.n4_cost_rider({"champ_prefix_ms_per_move": 5000.0,
                            "rung_ms_per_move": 3547.0})["fired"] is True
    # ABSENT must say so rather than reading as "did not fire"
    assert L.n4_cost_rider({})["fired"] is None


def test_an_absent_g2_census_can_never_reach_S1_FIRES(A, L):
    """DESIGN §10.4 — a margin result with a flat (or missing) signature
    licenses the number, not the mechanism story."""
    for sig in (False, None):
        b, _ = L.branch_for_round(gates_ok=True, z_p1=9.0, z_p2=9.0,
                                  signature_bar_met=sig)
        assert b == "S1-MARGIN-ONLY"
    b, _ = L.branch_for_round(gates_ok=True, z_p1=9.0, z_p2=9.0,
                              signature_bar_met=True)
    assert b == "S1-FIRES"


def test_any_failed_gate_voids_the_round(L):
    b, _ = L.branch_for_round(gates_ok=False, z_p1=9.0, z_p2=9.0,
                              signature_bar_met=True)
    assert b == "S1-VOID-INSTRUMENT"


@pytest.mark.parametrize("spec", [
    "SMOKE_OPP=opp:161999999500:8:local",
    "SMOKE_ALL=all:161999999520:8:local",
    "SMOKE_OWN=own:161999999540:8:laptop",
])
def test_smoke_specs_parse(A, spec):
    c = A.parse_smoke_cell(spec)
    assert c.name.startswith("SMOKE_") and c.n_games == 8


@pytest.mark.parametrize("bad", [
    "CELL_G3_OPP=opp:161999999500:8:local",     # a ROUND arm is never smokeable
    "SMOKE_OPP=sideways:161999999500:8:local",  # unknown scope
    "SMOKE_OPP=opp:161999999500:7:local",       # odd game count -> not paired
    "SMOKE_OPP=opp:161999999500:8:cloud",       # unknown role
    "SMOKE_OPP=opp:161999999500:8",             # short
    "SMOKE_OPP",                                # no '='
])
def test_smoke_specs_that_must_be_refused(A, bad):
    with pytest.raises(ValueError):
        A.parse_smoke_cell(bad)


def test_smoke_with_zero_cells_is_a_FAILURE_not_a_vacuous_pass(A):
    """⛔⛔ The FPU R1 defect: a smoke that adjudicated nothing exited 0 and the
    launcher's `|| DIE` was unreachable."""
    probs = A.smoke_problems({"cells": {}, "resolved_scopes": {}})
    assert probs and any("ZERO CELLS" in p for p in probs)
    assert A.SMOKE_REQUIRED_GATES == ("G-SCOPE", "G-WITNESS", "G-SINGLEVAR")


def test_smoke_mode_exit_code_is_reachable(A):
    """End-to-end: the CLI must exit non-zero when the smoke proves nothing."""
    r = subprocess.run(
        [sys.executable, str(PREP / "analyze_g3.py"), "--root", str(FIXTURE),
         "--smoke-mode", "--smoke-cell", "SMOKE_OPP=opp:161999999500:8:local"],
        capture_output=True, text=True)
    assert r.returncode == 1, r.stdout[-500:]
    assert "SMOKE ADJUDICATION FAILED" in r.stderr


def test_smoke_mode_emits_no_outcome_key(A):
    r = subprocess.run(
        [sys.executable, str(PREP / "analyze_g3.py"), "--root", str(FIXTURE),
         "--smoke-mode", "--smoke-cell", "SMOKE_OPP=opp:161999999500:8:local"],
        capture_output=True, text=True)
    blob = r.stdout
    for forbidden in ("paired_mean_margin", "paired_z", "winrate", "elo",
                      "avg_diff", "branch"):
        assert forbidden not in blob, forbidden


def test_launcher_is_executable_and_parses(A):
    sh = PREP / "run_g3.sh"
    assert sh.stat().st_mode & 0o111, "run_g3.sh is not executable"
    assert subprocess.run(["bash", "-n", str(sh)]).returncode == 0


def test_launcher_and_conf_agree_with_the_law(L):
    """⛔ THE PAIR IS LAW and the launcher only RESTATES it; a restatement that
    drifts is a launcher defect."""
    conf = (PREP / "WORKERS_G3.conf").read_text()

    def val(k):
        m = re.search(rf"^{k}=(\S+)$", conf, re.M)
        assert m, f"{k} missing from WORKERS_G3.conf"
        return m.group(1)

    assert int(val("K_DETS")) == L.K_DETS
    assert int(val("SIMS_PER_DET")) == L.SIMS_PER_DET
    assert int(val("TOTAL_SIMS")) == L.TOTAL_SIMS
    assert int(val("BAND_G3")) == L.BAND
    assert int(val("THROWAWAY_BASE")) == L.THROWAWAY_BASE
    assert float(val("JR_DOSE")) == L.JR_DOSE
    assert int(val("JR_MASK")) == L.JR_MASK
    assert val("RULES_PROFILE") == L.RULES_PROFILE
    assert val("BACKEND") == L.BACKEND
    assert int(val("EXACT_K")) == L.EXACT_K
    assert int(val("W_LOCAL")) == 30 and int(val("W_LAPTOP")) == 22


def test_the_launcher_puts_the_scope_on_the_CANDIDATE_side_only(L):
    """⛔ There must be no SHARED jrules flag anywhere — the `--c-puct`
    both-sides trap in its jrules disguise."""
    sh = (PREP / "run_g3.sh").read_text()
    assert "--cand-jrules-prior-scope" in sh
    assert "--cand-jrules-prior-dose" in sh
    assert "--cand-jrules-prior-mask" in sh
    # ⛔ no SHARED spelling on any argv line (comments may name it to warn)
    argv_lines = [ln for ln in sh.splitlines()
                  if ln.lstrip().startswith(("--", "args+=("))]
    assert not any(re.search(r"(?<!cand-)--jrules-prior-", ln)
                   for ln in argv_lines)
    # ...and no tie-arbiter flag on any argv line, by construction
    assert not any("--cand-tiearb" in ln for ln in argv_lines)
    # the three defects a smoke-adjudicated launcher exists to prevent
    assert "--paired" in sh and "--rules-profile" in sh
    assert "--out-root" in sh and "--out-subdir" in sh


def test_the_eval_harness_really_exposes_the_candidate_side_seam():
    """⭐ The seam this whole cell rests on, verified in the SOURCE rather than
    assumed: `--cand-jrules-prior-scope` exists, accepts 'opp', and the resolved
    dict is threaded into the CANDIDATE alone."""
    src = (REPO / "scripts" / "classical_search" / "eval_fair_puct.py").read_text()
    assert '"--cand-jrules-prior-scope", choices=("all", "own", "opp")' in src
    assert '"cand_jrules_prior": _cand_jrules_prior' in src
    # `champ_cfg_dict` builds the OPPONENT (via `_make_opponent` ->
    # `_cfg_from_dict`) and carries NO jrules key, which is WHY the scope knob
    # cannot leak to the opponent the way `--c-puct` does.
    i = src.index("champ_cfg_dict = {")
    block = src[i:src.index('"fpu_reduction": None}', i)]
    assert "jrules" not in block, block


def test_band_claim_is_proposed_not_claimed(L):
    claim = json.loads((PREP / "BAND_CLAIM_G3.json").read_text())
    assert "PROPOSED, NOT CLAIMED" in claim["_status"]
    assert not (PREP / "BAND_CLAIMED_G3").exists()
    assert list(claim["bands"]) == [str(L.BAND)]
    assert len(claim["_csv_rows"]) == 1
    assert claim["_csv_rows"][0].startswith(f"{L.BAND},")
    # the traps must stay named and unclaimed
    dropped = claim["sweep_2026_08_30"]["dropped_from_consideration"]
    for trap in ("146000000000", "158000000000", "160000000000"):
        assert trap in dropped
    for held in ("155000000000", "156000000000", "157000000000"):
        assert held in dropped
    assert set(claim["_reserved_not_claimed"]) >= {"162000000000",
                                                   "163000000000"}
    # ⛔ a reserve must never be appended by this round
    assert "162000000000," not in claim["_csv_rows"][0]


def test_read_rule_is_committed_pre_outcome():
    rr = (PREP / "READ_RULE_G3.md").read_text()
    assert "COMMITTED BEFORE ANY G3 STATISTIC EXISTS" in rr
    assert "CL-079" in rr and "CL-084" in rr
    assert "0 games" in rr
    for branch in _G3_L.BRANCHES:
        assert branch in rr, branch
    # the forbidden readings that keep costing the program money
    assert "A flip is not an improvement" in rr
    assert "is never \"refuted.\"" in rr or "never \"refuted\"" in rr


def test_no_run_live_sentinel_is_left_behind():
    """⛔ The freeze latch blocks main-tree commits while a run is live; a stale
    sentinel in a prep dir would block them for nothing."""
    assert not list(PREP.glob("**/RUN_LIVE.json"))
