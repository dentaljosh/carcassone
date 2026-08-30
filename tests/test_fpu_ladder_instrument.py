"""The FPU DOSE-LADDER instrument's own invariants
(`measurement/fpu_ladder_prep/`).

⛔ These test the INSTRUMENT, not a round: 0 games exist. They exist because the
launcher-side checks run once per round and are therefore never exercised by the
smoke, and because a gate nobody has seen FAIL is a gate nobody has tested.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "fpu_ladder_prep"

pytestmark = pytest.mark.skipif(not PREP.is_dir(), reason="prep dir absent")


# --------------------------------------------------------------------------- #
# ⛔⛔ R2 — THE IMPORT COLLISION (carried from the fpu_resurrection review)     #
# --------------------------------------------------------------------------- #
# `measurement/phasegate_prep/`, `measurement/fpu_resurrection_prep/` and now
# `measurement/fpu_ladder_prep/` ALL ship a module named `screen_lib` (each a
# deliberate FORK of the last). The original test file did
# `sys.path.insert(0, PREP)` + a bare `import screen_lib` inside a fixture;
# `tests/test_phasegate_instrument.py` does the same insert-and-import at MODULE
# scope — so in any run that collects both, phasegate's module was imported
# FIRST and cached in `sys.modules['screen_lib']`, and the deferred bare import
# then bound THE WRONG LIBRARY: 21 failures, of which the DANGEROUS ones were
# the ~2 that PASSED against the wrong constants.
#
# ⭐ THE FIX, AND IT MUST STAY: load by EXPLICIT PATH under a UNIQUE module name.
# ⛔ No bare `import screen_lib`, no `sys.path` insert, no reliance on collection
# order — a name that cannot collide cannot be shadowed.
def _load_by_path(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_LADDER_L = _load_by_path("fpu_ladder_screen_lib", PREP / "screen_lib.py")


@pytest.fixture(scope="module")
def L():
    return _LADDER_L


def test_the_ladder_screen_lib_is_not_a_siblings(L):
    """⛔⛔ R2's own regression pin. If this fails, the suite is testing another
    round's fork under this file's name and some assertions pass VACUOUSLY."""
    assert Path(L.__file__).parent == PREP
    assert L.__name__ == "fpu_ladder_screen_lib"
    # the discriminators: phasegate is ONE band / FOUR cells and has no BANDS;
    # fpu_resurrection is THREE bands and owns BAR_M + TAU_PAIR_SPEC; this round
    # is FOUR bands, owns BAR_EFFECT, and has no tau anything.
    assert hasattr(L, "BANDS") and len(L.BANDS) == 4
    assert not hasattr(L, "BAND"), "this is phasegate's screen_lib"
    assert not hasattr(L, "TAU_PAIR_SPEC"), "this is fpu_resurrection's fork"
    assert not hasattr(L, "BAR_M"), "this is fpu_resurrection's fork"
    assert hasattr(L, "BAR_EFFECT")
    assert {c.name for c in L.CELLS} == {"CELL_FPU005", "CELL_FPU010",
                                         "CELL_FPU015", "CELL_FPU030"}


# --------------------------------------------------------------------------- #
# THE LIBRARY IS THE LAW                                                       #
# --------------------------------------------------------------------------- #

def test_sanity_check_is_clean(L):
    assert L.sanity_check() == []


def test_selftest_passes():
    """⭐ Includes the named DEFECT variants, the round-verdict table, and BOTH
    directions of the FPU-A1 failure bar at the frozen 400-deck scale."""
    r = subprocess.run([sys.executable, str(PREP / "analyze_ladder.py"),
                        "--selftest"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-8000:]
    v = json.loads(r.stdout.split("\nSELFTEST")[0])
    assert v["problems"] == []
    # every named defect must have voided at least one rung AND the round
    for label, d in v["fixture"].items():
        if label in ("healthy", "synthetic_clean_round",
                     "fpu_a1_sub_bar_failure_is_REPORTED_not_void",
                     "fpu_a1_at_or_above_bar_VOIDS"):
            continue
        assert d["voided"], f"defect {label} voided no rung"
        assert d["round_verdict"] == "LADDER-VOID", label


def test_workers_conf_agrees_with_the_law(L):
    """⛔ WORKERS.conf RESTATES screen_lib; a restatement that drifts is a
    launcher defect. `run_cells.sh` asserts this at launch and so does this."""
    txt = (PREP / "WORKERS.conf").read_text()

    def val(k):
        m = re.search(rf"^{k}=(\S+)$", txt, re.M)
        assert m, f"{k} missing from WORKERS.conf"
        return m.group(1)

    assert int(val("K_DETS")) == L.K_DETS
    assert int(val("SIMS_PER_DET")) == L.SIMS_PER_DET
    assert int(val("TOTAL_SIMS")) == L.TOTAL_SIMS
    assert int(val("THROWAWAY_BASE")) == L.THROWAWAY_BASE
    assert int(val("BAND_FPU005")) == L.BANDS["CELL_FPU005"]
    assert int(val("BAND_FPU010")) == L.BANDS["CELL_FPU010"]
    assert int(val("BAND_FPU015")) == L.BANDS["CELL_FPU015"]
    assert int(val("BAND_FPU030")) == L.BANDS["CELL_FPU030"]
    assert val("RULES_PROFILE") == L.RULES_PROFILE
    assert val("BACKEND") == L.BACKEND
    # ⭐ the owner's W ruling of 2026-08-30, pinned so a future edit is deliberate
    assert int(val("W_LOCAL")) == 14
    assert int(val("W_LAPTOP")) == 22
    # ⭐ each box smokes a dose the round actually runs
    doses = {c.value for c in L.CELLS}
    assert float(val("SMOKE_DOSE_LOCAL")) in doses
    assert float(val("SMOKE_DOSE_LAPTOP")) in doses


def test_blind_commit_is_pending_at_the_freeze_commit():
    """⛔ A commit cannot name its own hash. It stays PENDING until a follow-up
    commit stamps the freeze sha, and `run_cells.sh` refuses a real rung while
    it is PENDING."""
    txt = (PREP / "WORKERS.conf").read_text()
    m = re.search(r"^BLIND_COMMIT=(\S+)$", txt, re.M)
    assert m
    assert m.group(1) == "PENDING" or re.fullmatch(r"[0-9a-f]{40}", m.group(1))


def test_budget_is_the_promoted_champion(L):
    assert (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS) == (16, 1376, 22016)
    assert L.K_DETS * L.SIMS_PER_DET == L.TOTAL_SIMS


def test_bands_are_disjoint_off_the_throwaway_and_off_the_reservations(L):
    rng = sorted((c.seed_start, c.seed_end, c.name) for c in L.CELLS)
    for a, b in zip(rng, rng[1:]):
        assert b[0] > a[1], f"{a} and {b} intersect"
    t_lo, t_hi = L.THROWAWAY_BASE, L.THROWAWAY_BASE + L.THROWAWAY_SPAN - 1
    for c in L.CELLS:
        assert c.seed_end < t_lo or c.seed_start > t_hi
    # ⛔ 155/156/157e9 are SPENT by the parent round; 161e9 is claimed and
    # 162/163e9 are RESERVED by S1 G3.
    spent = {155_000_000_000, 156_000_000_000, 157_000_000_000,
             161_000_000_000, 162_000_000_000, 163_000_000_000}
    assert not ({c.seed_start for c in L.CELLS} & spent)


def test_every_rung_owns_fpu_reduction_and_no_c_puct(L):
    for c in L.CELLS:
        assert c.knob == "fpu_reduction"
        assert c.cand_fpu is not None
        assert c.cand_c_puct is None


def test_the_four_doses_are_the_funded_ladder(L):
    assert sorted(c.value for c in L.CELLS) == [0.05, 0.10, 0.15, 0.30]


def test_box_split_is_two_and_two(L):
    """⭐ DESIGN §6's arithmetic: at the realized local-W14 / laptop-W22 rates a
    2+2 whole-rung split is the shortest wall a whole-cell assignment admits."""
    from collections import Counter
    assert Counter(c.role for c in L.CELLS) == {"local": 2, "laptop": 2}


# --------------------------------------------------------------------------- #
# ⭐⭐ THE BAR IS AN EFFECT SIZE (owner ruling 2026-08-30)                      #
# --------------------------------------------------------------------------- #

def test_the_bar_is_NOT_two_sigma_hat_of_the_instrument(L):
    """⛔⛔ THE HOUSE RULE, PINNED. The parent round's `BAR_M` was EXACTLY
    `2*se_model(400)` and its READ_RULE §8 had to disclose that a true null was
    then very nearly a coin flip between its kill and its unresolved branch.
    This round's bar comes from the DECISION and must not collapse onto the
    instrument's resolution."""
    two_sigma = 2 * L.se_model(400)
    assert abs(two_sigma - 1.381) < 2e-3, "se_model moved"
    assert abs(L.BAR_EFFECT - two_sigma) >= 0.05
    assert L.BAR_EFFECT == 1.5


def test_the_bar_is_read_on_LB95_and_UB95_not_the_point_estimate(L):
    """⭐ The whole difference from a point-estimate bar."""
    se = 0.69
    # a point estimate ABOVE the bar whose LB95 is below it -> NOT an adoption
    assert L.branch_for_cell(2.0, se, 2.0 / se,
                             gates_ok=True) == "R-UNRESOLVED"
    # LB95 exactly at the bar -> adoption
    m = L.BAR_EFFECT + 2 * se
    assert L.branch_for_cell(m, se, m / se,
                             gates_ok=True) == "R-ADOPT-CANDIDATE"
    # a POSITIVE point estimate whose UB95 is below the bar -> BOUNDED
    assert L.branch_for_cell(0.1, 0.2, 0.5, gates_ok=True) == "R-BOUNDED"


def test_the_incumbent_0p2_cell_would_just_clear_the_bar(L):
    """⭐ The bar was chosen so the realized `fpu=0.2` cell (M +2.951, se 0.683,
    LB95 +1.586) JUST clears it — a new rung must be at least as good as what we
    already hold. ⛔ This is a property of the BAR, not a comparison of rounds:
    no arithmetic here pools the 0.2 band with any rung of this one."""
    inc = L.CONTEXT_ROWS["fpu_reduction=0.2 (fpu_resurrection CELL_FPU02, "
                         "band 155e9)"]
    assert L.branch_for_cell(inc["M"], inc["se"], inc["z"],
                             gates_ok=True) == "R-ADOPT-CANDIDATE"
    assert inc["LB95"] > L.BAR_EFFECT           # by +0.086 pts/deck — narrowly


@pytest.mark.parametrize("delta,key,lo,hi", [
    # ⛔ THE NULL READ DISTRIBUTION, PRE-REGISTERED IN READ_RULE §8 AND PINNED
    # HERE so no future edit can quietly improve the round's advertised odds.
    (0.0, "R-BOUNDED", 0.53, 0.56),
    (0.0, "R-UNRESOLVED", 0.42, 0.45),
    (0.0, "R-ADOPT-CANDIDATE", 0.0, 0.001),
    (0.0, "P(LADDER-DEAD | all four rungs at this delta)", 0.09, 0.12),
    (1.5, "R-UNRESOLVED", 0.94, 0.97),
    (2.95125, "R-ADOPT-CANDIDATE", 0.50, 0.58),
])
def test_read_distribution_is_what_the_read_rule_advertises(L, delta, key, lo, hi):
    d = L.read_distribution(delta, L.se_model(400))
    assert lo <= d[key] <= hi, f"delta={delta} {key}={d[key]}"


def test_the_n_the_bar_would_actually_need(L):
    """⛔⛔ THE HONEST NUMBER. LADDER-DEAD at 80% under a true global null needs
    ~1,100 decks per rung — nearly 3x the funded 400 — and adopting a REPEAT of
    the incumbent's +2.951 at 80% needs ~730. READ_RULE §8 states both."""
    assert 1000 <= L.n_decks_for_ladder_dead(0.80) <= 1250
    assert 650 <= L.n_decks_for_adopt_power(2.95125, 0.80) <= 820


def test_elo_is_a_resolution_not_a_bar(L):
    """⛔ There is no exchange rate from +1.5 pts/deck into elo that this round
    measures, so the elo constant is the instrument's 2-sigma RESOLUTION and no
    branch may read it."""
    assert not hasattr(L, "BAR_ELO")
    assert "elo" not in L.branch_for_cell.__code__.co_varnames
    before = [L.branch_for_cell(m, se, m / se, gates_ok=True)
              for m in (-3.0, -0.5, 0.0, 1.0, 1.5, 3.0) for se in (0.4, 0.69, 1.4)]
    old = L.ELO_RESOLUTION_2SIGMA
    try:
        L.ELO_RESOLUTION_2SIGMA = 9999.0
        after = [L.branch_for_cell(m, se, m / se, gates_ok=True)
                 for m in (-3.0, -0.5, 0.0, 1.0, 1.5, 3.0)
                 for se in (0.4, 0.69, 1.4)]
    finally:
        L.ELO_RESOLUTION_2SIGMA = old
    assert before == after


def test_R4_elo_footing_is_deck_paired(L):
    """⭐ R4, carried: 800 games are 400 decks x 2 seatings, so the emitted sigma
    carries `1/sqrt(2)` and every field NAMES its footing."""
    assert abs(L.PAIRING_FACTOR - 0.7071067811865476) < 1e-12
    paired = 2 * L.elo_sigma_paired(0.5, 800)
    unpaired = 2 * L.elo_sigma_unpaired(0.5, 800)
    assert abs(L.ELO_RESOLUTION_2SIGMA - paired) < 0.05
    assert abs(unpaired - 24.57) < 0.05
    assert abs(paired - unpaired * L.PAIRING_FACTOR) < 1e-9
    recs = [{"diff": 1.0, "won_by_champ": True}] * 420 + \
           [{"diff": -1.0, "won_by_champ": False}] * 380
    we = L.winrate_elo(recs)
    assert we["elo_footing"] == "deck-paired"
    assert we["elo_sig_1sigma_paired"] < we["elo_sig_1sigma_unpaired"]
    assert "elo_sig_1sigma" not in we          # the unlabelled key is gone


# --------------------------------------------------------------------------- #
# ⭐⭐ THE FPU-A1 FIX — G-N AND G-DECKS ARE THE PROSE                           #
# --------------------------------------------------------------------------- #

def test_the_failure_bar_and_the_common_floor_are_the_prose(L):
    assert L.FAILURE_RATE_VOID == 0.02
    assert L.N_COMMON_FLOOR_FRACTION == 0.80


@pytest.mark.parametrize("n_failed,should_void", [
    (0, False),
    (1, False),          # 0.125% — the FPU04 case the parent round VOIDED
    (15, False),         # 1.875% — strictly below the bar
    (16, True),          # 2.000% — AT the bar
    (40, True),
])
def test_G_N_absorbs_below_the_bar_and_voids_at_it(L, n_failed, should_void):
    """⛔⛔ THE FPU-A1 REGRESSION, DIRECT ON THE GATE. The parent's condition
    column demanded `n_failed == 0` while its own notes column said a sub-2%
    rate is REPORTED — and the strict column won, voiding a healthy cell over
    ONE game in 800. Here the prose IS the condition."""
    spec = L.CELLS[0]
    g = L.n_gate(spec, spec.n_games - n_failed, n_failed,
                 spec.n_decks - n_failed, "summary:n", "summary:n_failed")
    assert g["ok"] is (not should_void), g["why"]
    if 0 < n_failed and not should_void:
        assert "REPORTED" in g["why"]


def test_G_N_refuses_games_that_vanished_without_a_failure_record(L):
    """⛔ The accounting identity. A denominator nobody knows is a strictly worse
    defect than a recorded failure, and the 2% bar does NOT absorb it."""
    spec = L.CELLS[0]
    g = L.n_gate(spec, 790, 0, 395, "summary:n", "summary:n_failed")
    assert not g["ok"]
    assert "ACCOUNTING" in g["why"]


def test_G_N_and_G_DECKS_share_one_denominator(L):
    """⭐ A one-seat-only deck IS one failed GAME. If the two gates used
    different denominators they would disagree by 2x on the same archive — the
    build caught exactly that in the first draft."""
    spec = L.CELLS[0]
    recs = []
    n_half = 15
    for i in range(spec.n_decks):
        seed = spec.seed_start + i
        seats = (0,) if i < n_half else (0, 1)
        for a in seats:
            recs.append({"seed": seed, "a_seat": a, "diff": 1.0 if a == 0 else -1.0,
                         "won_by_champ": a == 0, "drew": False})
    gd = L.decks_gate(spec, recs)
    gn = L.n_gate(spec, len(recs), n_half, spec.n_decks - n_half,
                  "summary:n", "summary:n_failed")
    assert gd["ok"] and gn["ok"]
    assert gd["detail"]["half_played_rate_of_games"] == pytest.approx(
        n_half / spec.n_games)
    assert gd["detail"]["half_played_rate_denominator"] == spec.n_games
    assert gn["detail"]["failure_rate"] == pytest.approx(n_half / spec.n_games)


def test_G_DECKS_still_hard_fails_out_of_range_and_overlap(L):
    spec = L.CELLS[0]
    recs = [{"seed": 999_999_999_999, "a_seat": a, "diff": 1.0,
             "won_by_champ": True, "drew": False} for a in (0, 1)]
    g = L.decks_gate(spec, recs)
    assert not g["ok"] and "outside" in g["why"]


# --------------------------------------------------------------------------- #
# THE LADDER AND THE ROUND VERDICT                                             #
# --------------------------------------------------------------------------- #

def test_ladder_is_exclusive_exhaustive_and_all_reachable(L):
    g = L.branch_grid(step=0.01)
    assert g["all_reachable"], g["reachable"]
    assert sum(g["histogram"].values()) == g["points"]


@pytest.mark.parametrize("M,se,want", [
    (5.0, 0.7, "R-ADOPT-CANDIDATE"),
    (-3.0, 0.7, "R-NEGATIVE"),
    (0.0, 0.4, "R-BOUNDED"),
    (0.0, 1.5, "R-UNRESOLVED"),
    (1.40, 0.69, "R-UNRESOLVED"),
    (2.90, 0.69, "R-ADOPT-CANDIDATE"),
])
def test_named_ladder_points(L, M, se, want):
    assert L.branch_for_cell(M, se, M / se, gates_ok=True) == want


def test_a_failed_gate_voids_first(L):
    assert L.branch_for_cell(9.9, 0.1, 99.0, gates_ok=False) == "U-VOID-INSTRUMENT"


def test_round_verdict_table(L):
    names = [c.name for c in L.CELLS]
    allb = {n: "R-BOUNDED" for n in names}
    assert L.round_verdict(allb, round_gates_ok=True)["verdict"] == "LADDER-DEAD"
    # R-NEGATIVE implies UB95 <= 0 < the bar, so it counts toward DEAD
    neg = dict(allb, **{names[0]: "R-NEGATIVE"})
    assert L.round_verdict(neg, round_gates_ok=True)["verdict"] == "LADDER-DEAD"
    live = dict(allb, **{names[1]: "R-ADOPT-CANDIDATE"})
    assert L.round_verdict(live, round_gates_ok=True)["verdict"] == "LADDER-LIVE"
    unres = dict(allb, **{names[2]: "R-UNRESOLVED"})
    assert L.round_verdict(unres, round_gates_ok=True)["verdict"] == "LADDER-UNRESOLVED"
    void = dict(allb, **{names[3]: "U-VOID-INSTRUMENT"})
    assert L.round_verdict(void, round_gates_ok=True)["verdict"] == "LADDER-VOID"
    assert L.round_verdict(allb, round_gates_ok=False)["verdict"] == "LADDER-VOID"
    # ⛔ ABSENT is FAIL: a frozen rung with no archive blocks the round verdict
    assert L.round_verdict({names[0]: "R-BOUNDED"},
                           round_gates_ok=True)["verdict"] == "LADDER-VOID"


def test_LADDER_DEAD_names_the_incumbents_confirmation_leg(L):
    names = [c.name for c in L.CELLS]
    v = L.round_verdict({n: "R-BOUNDED" for n in names}, round_gates_ok=True)
    assert "0.2" in v["why"] and "CONFIRMATION LEG" in v["why"].upper()
    assert "propose" in L.LADDER_DEAD_CONSEQUENCE.lower()
    assert "not 'funded'" in L.LADDER_DEAD_CONSEQUENCE.replace("’", "'")


def test_adoption_chain_is_frozen_and_has_three_legs_after_this_one(L):
    chain = L.ADOPTION_CHAIN
    joined = " ".join(chain).lower()
    assert "arbiter armed" in joined or "arbiter\narmed" in joined
    assert "carcasum" in joined and "e4" in joined
    assert "own prereg" in joined


# --------------------------------------------------------------------------- #
# THE CONTEXT ROWS ARE CONTEXT                                                 #
# --------------------------------------------------------------------------- #

def test_context_rows_carry_the_realized_numbers_and_the_cl068_caveat(L):
    r2 = L.CONTEXT_ROWS["fpu_reduction=0.2 (fpu_resurrection CELL_FPU02, "
                        "band 155e9)"]
    r4 = L.CONTEXT_ROWS["fpu_reduction=0.4 (fpu_resurrection CELL_FPU04, "
                        "band 156e9)"]
    assert r2["M"] == pytest.approx(2.95125)
    assert r2["z"] == pytest.approx(4.3236634230592745)
    assert r2["n_paired"] == 400 and r2["branch"] == "F-RESURRECT"
    assert r4["M"] == pytest.approx(0.7543859649122807)
    assert r4["n_paired"] == 399          # ⚠️ the FPU-A1 cell, one deck short
    assert "AMENDED" in r4["branch"]
    assert "CL-068" in L.CONTEXT_WARNING
    assert "NEVER A BRANCH INPUT" in L.CONTEXT_WARNING


def test_every_rider_set_forbids_pooling_and_production_change(L):
    joined = " ".join(L.RIDERS_ALWAYS)
    assert "CL-068" in joined
    assert "NEVER POOLED" in joined.upper()
    assert "PRODUCTION.yaml is UNTOUCHED" in joined
    assert "arbiter" in joined.lower()


# --------------------------------------------------------------------------- #
# THE LAUNCHER                                                                 #
# --------------------------------------------------------------------------- #

def test_launcher_parses_and_refuses_without_a_role():
    assert subprocess.run(["bash", "-n", str(PREP / "run_cells.sh")]).returncode == 0
    r = subprocess.run(["bash", str(PREP / "run_cells.sh")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode != 0


def test_golden_gate_scripts_parse():
    gg = PREP / "golden_gate"
    assert subprocess.run(["bash", "-n", str(gg / "run_golden_gate.sh")]).returncode == 0
    for f in ("identity_leg.py", "ladder_diff.py"):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(gg / f)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def _launcher_code() -> str:
    """`run_cells.sh` with FULL-LINE COMMENTS STRIPPED.

    ⚠️ Load-bearing: the launcher's comments deliberately NAME the flags it must
    never use ("`--c-puct` and `--tau-p` are the SHARED flags"). A prohibition
    test that scanned the raw text would fail on the very comment that documents
    the prohibition — and, worse, would pass if someone deleted the comment and
    added the flag."""
    return "\n".join(ln for ln in (PREP / "run_cells.sh").read_text().splitlines()
                     if not ln.lstrip().startswith("#"))


def test_launcher_never_arms_the_tie_arbiter():
    assert "--cand-tiearb" not in _launcher_code()


def test_launcher_uses_only_cand_fpu_reduction():
    """⭐ `--c-puct` and `--tau-p` build champ_cfg_dict, which `_make_opponent`
    feeds through the SAME `_cfg_from_dict` — they move BOTH SIDES. And no rung
    of this round varies c_puct at all, so even `--cand-c-puct` is forbidden."""
    code = _launcher_code()
    assert "--cand-fpu-reduction" in code
    assert "--cand-c-puct" not in code
    assert not re.search(r"(?<!-)--c-puct\b", code)
    assert not re.search(r"(?<!-)--tau-p\b", code)


def test_launcher_passes_paired_and_a_rules_profile():
    """The PG-D8/PG-D9 defects, pinned: without `--paired` n_paired is 0 on
    every rung; without `--rules-profile` the round silently runs `walled`."""
    code = _launcher_code()
    assert "--paired" in code
    assert "--rules-profile" in code


def test_launcher_probes_the_knob_at_EVERY_rung_dose():
    """⭐ A plumbing bug that clamped or rounded small values would pass a 0.2
    probe and silently flatten the bottom of the ladder."""
    code = _launcher_code()
    assert "for dose in (0.05, 0.1, 0.15, 0.3)" in code


def test_launcher_asserts_the_rev_pin_before_AND_after_every_rung():
    code = _launcher_code()
    assert code.count("assert_rev") >= 3           # def + before + after
    assert 'assert_rev "before"' in code
    assert 'assert_rev "after:$name"' in code
    assert "status --porcelain -- src engine scripts rust tests" in code


def test_launcher_refuses_a_real_rung_without_the_blind_commit_and_the_band():
    code = _launcher_code()
    assert 'BLIND_COMMIT" != "PENDING"' in code
    assert "BAND_CLAIMED" in code


def test_launcher_refuses_without_a_wheel_matched_golden_gate():
    """⛔⛔ The inheritance question, enforced. The parent's FPU_BITEXACT.json is
    NOT accepted: this round's gate must exist, PASS, and carry THIS BOX's own
    installed `carc_rs_binary_sha`."""
    code = _launcher_code()
    assert "FPU_BITEXACT_LADDER.json" in code
    assert "carc_rs_binary_sha" in code
    # ⛔ and the parent's artefact must never be READ as a substitute. It IS
    # named — inside the DIE message, which is where the executor needs to be
    # told why it does not count — so the test looks for a READ, not a mention.
    for ln in code.splitlines():
        if "fpu_resurrection_prep/FPU_BITEXACT.json" in ln:
            assert not re.search(r"(-f |grep|cat |open\(|json\.load)", ln), \
                f"the launcher READS the parent's artefact: {ln.strip()}"


def test_launcher_passes_a_smoke_cell_spec_to_the_adjudicator():
    """⭐⭐ R1(b), carried — the launcher must PASS the smoke's own spec.
    `--root` is the PARENT dir and the round's rung table names only the four
    ROUND rungs, so without this flag a smoke read has nothing to adjudicate the
    archive against and vacuously exits 0."""
    code = _launcher_code()
    assert "--smoke-cell" in code
    assert "--smoke-mode" in code
    assert re.search(r'--smoke-cell "\$\{SMOKE_NAME\}=fpu_reduction:'
                     r'\$\{SMOKE_DOSE\}:\$\{SMOKE_SEED\}:\$\{SMOKE_GAMES\}:'
                     r'\$\{ROLE\}"', code), \
        "the launcher does not pass the smoke's dose/seed/n/role"


# --------------------------------------------------------------------------- #
# ⭐⭐ R1 — `--smoke-mode` MUST ADJUDICATE THE SMOKE                            #
# --------------------------------------------------------------------------- #
# ⛔⛔ THE DEFECT, REPRODUCED. In the parent round the cell scan dropped every
# `SMOKE_*` dir AND `adjudicate()` iterated only `screen_lib.CELLS`, so a smoke
# read produced `"cells": {}` / `"resolved_knobs": {}` and STILL EXITED 0 — which
# made `run_cells.sh`'s `|| DIE "the smoke adjudication FAILED"` unreachable and
# the smoke's whole job silently did nothing.

FIXTURE = PREP / "selftest_fixture"


def _smoke_root(tmp_path, dirs: dict) -> Path:
    root = tmp_path / "fpu_ladder"
    root.mkdir()
    for dest, src in dirs.items():
        shutil.copytree(FIXTURE / src, root / dest)
    return root


def _run_smoke(root: Path, *smoke_cells: str, extra=()):
    return subprocess.run(
        [sys.executable, str(PREP / "analyze_ladder.py"), "--root", str(root),
         "--smoke-mode",
         *[a for s in smoke_cells for a in ("--smoke-cell", s)], *extra],
        capture_output=True, text=True, timeout=300)


#: the shipped fixture's 0.05 rung replayed under a SMOKE name: 12 decks = 24
#: games on the throwaway block, local box.
SMOKE_005_SPEC = "SMOKE_005=fpu_reduction:0.05:167999999000:24:local"
#: and the 0.30 rung: 10 decks = 20 games, laptop.
SMOKE_030_SPEC = "SMOKE_030=fpu_reduction:0.3:167999999300:20:laptop"


def test_smoke_mode_adjudicates_a_SMOKE_dir_and_returns_the_resolved_dose(tmp_path):
    """⭐⭐ R1(a)+(c) — THE REGRESSION PIN. On the parent's OLD code this archive
    produced `"cells": {}`, `"resolved_knobs": {}` and exit 0."""
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005"})
    r = _run_smoke(root, SMOKE_005_SPEC)
    v = json.loads(r.stdout)

    assert v["cells"], "⛔ R1: the smoke adjudicated ZERO cells"
    assert "SMOKE_005" in v["cells"]
    # ⭐ the dose comes back FROM THE EMITTED manifest.json, not from the CLI
    k = v["resolved_knobs"]["SMOKE_005"]
    assert k["requested_fpu_reduction"] == 0.05
    assert k["frozen"]["fpu_reduction"] == 0.05
    # ⭐ and it landed on the CANDIDATE SIDE ONLY
    assert k["resolved_two_sided"]["fpu_reduction"] == {"candidate": 0.05,
                                                        "opponent": None}
    by = {g["gate"]: g["ok"] for g in v["cells"]["SMOKE_005"]["gates"]}
    assert by["G-FPU"] and by["G-TWOSIDED"]
    assert v["smoke_ok"] is True and v["smoke_problems"] == []
    assert r.returncode == 0


def test_smoke_mode_exits_NONZERO_when_it_adjudicates_nothing(tmp_path):
    """⛔⛔ R1(c) — THE HEART OF IT. Zero adjudicated cells must be a FAILURE, so
    that `run_cells.sh`'s `|| DIE` is REACHABLE."""
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005"})
    r = _run_smoke(root, "SMOKE_ABSENT=fpu_reduction:0.05:167999999000:24:local")
    assert r.returncode != 0, "⛔ R1: a zero-cell smoke still exited 0"
    v = json.loads(r.stdout)
    assert v["cells"] == {} and v["resolved_knobs"] == {}
    assert v["smoke_ok"] is False
    assert any("ZERO CELLS" in p for p in v["smoke_problems"])


def test_smoke_mode_NEVER_adjudicates_a_real_round_rung(tmp_path):
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005",
                                  "CELL_FPU010": "CELL_FPU010",
                                  "CELL_FPU030": "CELL_FPU030"})
    r = _run_smoke(root, SMOKE_005_SPEC)
    v = json.loads(r.stdout)
    assert set(v["cells"]) == {"SMOKE_005"}
    assert set(v["resolved_knobs"]) == {"SMOKE_005"}
    assert r.returncode == 0


def test_smoke_mode_catches_a_dose_that_bound_on_the_opponent_too(tmp_path):
    """⛔⛔ The mirror of the parent's `--c-puct` both-sides trap: a build that
    moved the OPPONENT too is champion-vs-champion and EVERY other gate passes."""
    root = _smoke_root(tmp_path, {"SMOKE_030": "CELL_FPU030"})
    man = root / "SMOKE_030" / "manifest.json"
    m = json.loads(man.read_text())
    m["config"]["opponent"]["champ_cfg"]["fpu_reduction"] = 0.3
    man.write_text(json.dumps(m))

    r = _run_smoke(root, SMOKE_030_SPEC)
    assert r.returncode != 0
    v = json.loads(r.stdout)
    assert v["smoke_ok"] is False
    assert any("G-TWOSIDED" in p for p in v["smoke_problems"])


def test_smoke_mode_catches_a_dose_that_never_reached_the_wire(tmp_path):
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005"})
    man = root / "SMOKE_005" / "manifest.json"
    m = json.loads(man.read_text())
    del m["config"]["cand_search"]
    man.write_text(json.dumps(m))

    r = _run_smoke(root, SMOKE_005_SPEC)
    assert r.returncode != 0
    v = json.loads(r.stdout)
    assert any("G-FPU" in p or "did not put the dose on the wire" in p
               for p in v["smoke_problems"])


def test_smoke_mode_refuses_to_run_without_a_smoke_cell(tmp_path):
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005"})
    r = _run_smoke(root)
    assert r.returncode != 0
    assert "--smoke-cell" in r.stderr


def test_smoke_cell_is_rejected_outside_smoke_mode(tmp_path):
    root = _smoke_root(tmp_path, {"CELL_FPU005": "CELL_FPU005"})
    r = subprocess.run(
        [sys.executable, str(PREP / "analyze_ladder.py"), "--root", str(root),
         "--smoke-cell", SMOKE_005_SPEC],
        capture_output=True, text=True, timeout=300)
    assert r.returncode != 0
    assert "only legal with --smoke-mode" in r.stderr


def test_a_smoke_cell_may_never_name_a_round_rung(tmp_path):
    root = _smoke_root(tmp_path, {"CELL_FPU005": "CELL_FPU005"})
    r = _run_smoke(root, "CELL_FPU005=fpu_reduction:0.05:167999999000:24:local")
    assert r.returncode != 0
    assert "SMOKE_" in r.stderr


def test_a_smoke_cell_may_not_name_a_knob_this_round_does_not_own(tmp_path):
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005"})
    r = _run_smoke(root, "SMOKE_005=c_puct:1.0:167999999000:24:local")
    assert r.returncode != 0
    assert "unknown knob" in r.stderr


def test_smoke_mode_still_emits_NO_OUTCOME_KEY(tmp_path):
    """⛔⛔ The Stage-2 `G-SMOKE` ruling: no outcome key at ANY depth."""
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005"})
    v = json.loads(_run_smoke(root, SMOKE_005_SPEC).stdout)
    forbidden = {"paired_mean_margin", "paired_z", "n_paired", "winrate", "elo",
                 "M", "z", "se", "UB95", "LB95", "diff", "avg_diff", "branch",
                 "branches", "W", "D", "L", "stats", "secondary_elo",
                 "_per_deck", "se_anomaly", "round_verdict"}

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, val in node.items():
                assert k not in forbidden, f"outcome key {k!r} at {path}"
                walk(val, f"{path}.{k}")
        elif isinstance(node, list):
            for i, val in enumerate(node):
                walk(val, f"{path}[{i}]")

    walk(v)


def test_real_mode_still_skips_smoke_and_void_dirs(tmp_path):
    """⭐ R1(d) — REAL-MODE BEHAVIOUR IS UNCHANGED."""
    root = _smoke_root(tmp_path, {"SMOKE_005": "CELL_FPU005",
                                  "_VOID_OLD": "CELL_FPU010",
                                  "CELL_FPU005": "CELL_FPU005"})
    r = subprocess.run(
        [sys.executable, str(PREP / "analyze_ladder.py"), "--root", str(root)],
        capture_output=True, text=True, timeout=300)
    assert r.returncode == 0
    v = json.loads(r.stdout)
    assert set(v["cells"]) == {"CELL_FPU005"}
    assert v["smoke_mode"] is False
    assert "smoke_problems" not in v and "smoke_ok" not in v
    # ⛔ three frozen rungs produced no archive -> ABSENT is FAIL -> LADDER-VOID
    assert v["round_verdict"]["verdict"] == "LADDER-VOID"


# --------------------------------------------------------------------------- #
# THE GOLDEN GATE IS OWED, NOT INHERITED                                       #
# --------------------------------------------------------------------------- #

def test_the_parents_golden_gate_is_NOT_inherited():
    """⛔⛔ DESIGN §9. The parent's artefact is PASS but its `ONE-WHEEL` check
    binds it to carc_rs binary `f6316d42838574de`, and the S1 R7/R6 merge has
    since changed `carc_core::search` and `fair::search_worlds`. This round's own
    artefact is git-ignored (it is BOX-LOCAL) and must be produced per box."""
    assert not (PREP / "FPU_BITEXACT.json").exists(), \
        "the parent's artefact must not be copied in"
    gi = (PREP / ".gitignore").read_text()
    assert "/FPU_BITEXACT_LADDER.json" in gi
    parent = PREP.parent / "fpu_resurrection_prep" / "FPU_BITEXACT.json"
    if parent.is_file():
        v = json.loads(parent.read_text())
        wheels = {c["detail"][k] for c in v["checks"]
                  if c["check"] == "ONE-WHEEL" for k in c["detail"]}
        assert wheels == {"f6316d42838574de"}, \
            "the parent's gate no longer names the wheel this test reasons about"


def test_the_golden_gate_runner_covers_every_rung_dose(L):
    sh = (PREP / "golden_gate" / "run_golden_gate.sh").read_text()
    for dose in ("0.05", "0.1", "0.15", "0.3"):
        assert f" {dose} " in sh, f"no CTRL leg at dose {dose}"
    diff = (PREP / "golden_gate" / "ladder_diff.py").read_text()
    assert "DOSE-DISTINCT" in diff
    assert "RUNG-SET" in diff
    # ⛔ and the runner must PROVE its OLD tree is pre-plumbing rather than
    # trusting a log walk
    assert "ALREADY carries fpu_reduction" in sh


def test_adjudicator_reports_the_golden_gate_as_ABSENT_before_it_is_run():
    """⭐ At build time the artefact does not exist, and the read-out must SAY
    SO — with the reason the parent's is not a substitute — rather than
    defaulting to OK."""
    r = subprocess.run([sys.executable, str(PREP / "analyze_ladder.py"),
                        "--selftest"], capture_output=True, text=True,
                       timeout=600)
    v = json.loads(r.stdout.split("\nSELFTEST")[0])
    gg = v["golden_gate"]
    if gg["verdict"] == "ABSENT":
        assert gg["ok"] is False
        assert "f6316d42838574de" in gg["why"]
        assert "run_golden_gate.sh" in gg["why"]
