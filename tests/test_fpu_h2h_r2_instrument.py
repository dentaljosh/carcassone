"""The FPU PRODUCTION-H2H **ROUND 2** instrument's own invariants
(`measurement/fpu_h2h_r2_prep/`).

⛔ These test the INSTRUMENT, not a round: 0 games exist. They exist because the
launcher-side checks run once per round and are therefore never exercised by the
smoke, and because a gate nobody has seen FAIL is a gate nobody has tested.

⚠️ SECONDS-SCALE BY CONSTRUCTION. Nothing here plays a game, imports
`carcassonne_ai`, or touches the share. The one subprocess is
`analyze_h2h.py --selftest` (~0.1 s).
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "fpu_h2h_r2_prep"

pytestmark = pytest.mark.skipif(not PREP.is_dir(), reason="prep dir absent")


# --------------------------------------------------------------------------- #
# ⛔⛔ R2 — THE IMPORT COLLISION (carried from the fpu_resurrection review)     #
# --------------------------------------------------------------------------- #
# `measurement/phasegate_prep/`, `measurement/fpu_resurrection_prep/`,
# `measurement/fpu_ladder_prep/` and now `measurement/fpu_h2h_r2_prep/` ALL ship a
# module named `screen_lib` (each a deliberate FORK of the last). A bare
# `import screen_lib` after a `sys.path` insert binds whichever fork was cached
# FIRST — 21 failures in the ladder's build, of which the DANGEROUS ones were the
# ~2 that PASSED against another round's constants.
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


_H2H2_L = _load_by_path("fpu_h2h_r2_screen_lib", PREP / "screen_lib.py")


@pytest.fixture(scope="module")
def L():
    return _H2H2_L


def test_the_r2_screen_lib_is_not_a_siblings(L):
    """⛔⛔ R2's own regression pin. If this fails, the suite is testing another
    round's fork under this file's name and some assertions pass VACUOUSLY."""
    assert Path(L.__file__).parent == PREP
    assert L.__name__ == "fpu_h2h_r2_screen_lib"
    assert L.ROUND_ID == "fpu_h2h_r2"
    # the discriminators: phasegate is FOUR cells on ONE band and has no BANDS;
    # fpu_resurrection owns BAR_M + TAU_PAIR_SPEC; the ladder is FOUR bands with
    # BAR_EFFECT 1.5 and an arb-OFF gate; this round is ONE band, ONE cell,
    # BAR_EFFECT 1.0, and owns the two-sided arbiter vocabulary.
    assert hasattr(L, "BANDS") and len(L.BANDS) == 1
    assert not hasattr(L, "BAND_") and not hasattr(L, "TAU_PAIR_SPEC")
    assert not hasattr(L, "BAR_M"), "this is fpu_resurrection's fork"
    assert L.BAR_EFFECT == 1.0
    assert {c.name for c in L.CELLS} == {"CELL_H2H2_FPU02"}
    assert hasattr(L, "DEPLOYED_TIEARB") and hasattr(L, "tiearb_sides_gate")
    # ⭐⭐ AND THE ROUND-2 DISCRIMINATORS — round 1's fork has NONE of these.
    # Without them this file could load round 1's screen_lib and pass most of
    # its assertions VACUOUSLY, which is precisely the R2 defect.
    assert L.CELLS[0].n_decks == 800 and L.CELLS[0].n_games == 1600
    assert L.BAND == 169_000_000_000
    for sym in ("N_CHUNKS", "DECKS_PER_CHUNK", "ROLES", "chunk_plan",
                "nodup_gate", "chunks_gate", "shard_ident_gate",
                "host_provenance_gate", "host_role_strict",
                "BAR_COINCIDENCE_AT_FUNDED_N", "ROUND1_VERDICT",
                "ARB_ON_SIBLING"):
        assert hasattr(L, sym), f"round 2 owns {sym} and this fork lacks it"


def test_the_arb_off_gate_is_gone_and_the_two_sided_one_replaced_it(L):
    """⛔⛔ THE INVERSION. The ladder's `G-ARB-OFF` FAILED on any armed arbiter.
    Carrying it here would void this round's healthy cell on its own premise."""
    assert not hasattr(L, "arb_off_gate"), (
        "the ladder's arb_off_gate survived the fork — it FAILS on an armed "
        "arbiter, which is exactly what this round arms on BOTH seats")
    assert hasattr(L, "tiearb_sides_gate") and hasattr(L, "tiearb_fire_gate")


def test_the_vocabulary_is_the_new_one_loaded_by_explicit_path(L):
    """⭐ `tiearb_gates` is the module merged 2026-08-31 with the opponent-side
    plumbing, and `screen_lib` loads it BY PATH under a round-unique name for the
    same R2 reason this test file does."""
    assert L.TG.__name__ == "fpu_h2h_r2_tiearb_gates"
    assert (Path(L.TG.__file__)
            == REPO / "scripts" / "classical_search" / "tiearb_gates.py")
    assert hasattr(L.TG, "assert_tiearb_sides")
    assert hasattr(L.TG, "tiearb_sides_summary")
    # the spec is CITED, never retyped
    assert L.DEPLOYED_TIEARB == L.TG.DEPLOYED_TIEARB_B64
    assert set(L.DEPLOYED_TIEARB) == set(L.TG.TIEARB_SPEC_KEYS)
    assert "phase_gate" in L.DEPLOYED_TIEARB, (
        "a spec that omits phase_gate is UNDER-SPECIFIED — a silently-defaulted "
        "'all' on a gated cell makes it BE the ungated cell")


# --------------------------------------------------------------------------- #
# THE LIBRARY IS THE LAW                                                       #
# --------------------------------------------------------------------------- #

def test_sanity_check_is_clean(L):
    assert L.sanity_check() == []


def test_selftest_passes():
    """⭐ Includes the named DEFECT variants (24 of them, five of which only
    exist because the opponent seat can now be armed), BOTH directions of the
    FPU-A1 failure bar at the frozen 400-deck scale, and the IDENT
    propositions."""
    r = subprocess.run([sys.executable, str(PREP / "analyze_h2h.py"),
                        "--selftest"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-8000:]
    v = json.loads(r.stdout.split("\nSELFTEST")[0])
    assert v["problems"] == []
    skip = {"healthy", "synthetic_clean_round",
            "fpu_a1_sub_bar_failure_is_REPORTED_not_void",
            "fpu_a1_at_or_above_bar_VOIDS", "ident_healthy",
            "ident_nonreproducing_detected", "ident_dose_did_not_bind_detected"}
    for label, d in v["fixture"].items():
        if label in skip:
            continue
        assert d["voided"], f"defect {label} voided no cell"
        assert d["verdict"] == "H-VOID-INSTRUMENT", label
    # ⭐ the five that could not have been written before 2026-08-31
    for label in ("opponent_seat_never_armed_the_confounded_cell",
                  "opponent_seat_present_but_disabled",
                  "the_two_seats_ran_different_B",
                  "phase_gate_key_missing_stale_wheel",
                  "opponent_seat_armed_but_never_arbitrated"):
        assert label in v["fixture"], f"{label} is not in the defect table"
    assert v["fixture"]["ident_nonreproducing_detected"] is True
    assert v["fixture"]["ident_dose_did_not_bind_detected"] is True


# --------------------------------------------------------------------------- #
# ⭐⭐ THE BAR — AN EFFECT SIZE, AND THE **CONFIRMATION** ONE                   #
# --------------------------------------------------------------------------- #

def test_the_bar_collided_with_two_sigma_hat_AND_IS_DISCLOSED(L):
    """⛔⛔⛔ ROUND 2 INVERTS ROUND 1's TEST, AND THE REASON IS ON THE RECORD.

    Round 1 asserted `|BAR - 2*se_model| > 0.05` — the house rule (owner
    2026-08-30) forbids a bar set at `2 sigma-hat` of the instrument. At round
    2's `n` that numeric test FIRES: `2*se_model(800) = 0.9652` against the
    frozen `+1.0`.

    ⭐ The bar still does not move, because the ruling is about PROVENANCE — a
    bar *defined as* `2*se_model`, read off the instrument instead of off the
    decision. This one was derived in ROUND 1 from two realized production folds
    and is carried VERBATIM; at round 1's `n` it sat at `0.73 * 2 sigma-hat`.
    Moving it after seeing round 1's `M = +1.019` would be choosing a bar from
    the data — strictly the worse sin.

    ⛔⛔ So what is tested is that the collision is DISCLOSED with correct
    arithmetic, that the pathology it implies is stated, and that the bar is
    still round 1's."""
    two_sig = 2 * L.se_model(L.CELLS[0].n_decks)
    assert abs(L.BAR_EFFECT - two_sig) < 0.05, (
        "the collision has gone away — good, but this test and DESIGN 3.3 "
        "must then be rewritten rather than left claiming it")
    d = L.BAR_COINCIDENCE_AT_FUNDED_N
    assert d["bar"] == L.BAR_EFFECT == 1.0, "the bar is round 1's, unmoved"
    assert abs(d["two_sigma_hat_at_funded_n"] - two_sig) < 5e-4
    assert abs(d["ratio_bar_over_2sigmahat"] - L.BAR_EFFECT / two_sig) < 5e-3
    assert "consequence" in d and "NON-POSITIVE" in d["consequence"].upper()
    # ⛔ and the consequence must be TRUE, not merely written down
    assert 0.0 < L.BAR_EFFECT - two_sig < 0.10
    for name in ("DESIGN.md", "READ_RULE.md"):
        txt = (PREP / name).read_text()
        assert "0.9652" in txt, f"{name} does not print the collision"


def test_the_bar_is_round_ones_unmoved(L):
    """⛔⛔ A successor round that softened its bar after seeing its
    predecessor's `M = +1.019` would be choosing a bar from the data."""
    assert L.BAR_EFFECT == 1.0
    r1 = L.CONTEXT_ROWS["⭐⭐ fpu=0.2 — fpu_h2h ROUND 1 CELL_H2H_FPU02, "
                        "band 168e9, ARB ON BOTH SEATS"]
    assert L.branch_for_cell(r1["M"], r1["se"], r1["z"],
                             gates_ok=True) == "H-UNRESOLVED", (
        "round 1's own numbers must still read H-UNRESOLVED under this round's "
        "frozen ladder — the two rounds share a bar and a branch table")


def test_the_bar_is_the_confirmation_bar_not_the_ladders_screen_bar(L):
    assert L.BAR_EFFECT < L.LADDER_SCREEN_BAR == 1.5
    k16 = L.PRODUCTION_FOLD_PRECEDENTS[
        "k16x1376 budget promotion (2026-08-30, h2h_22016_20260824, b148e9)"]
    assert L.BAR_EFFECT <= k16["D_pts_per_deck"], (
        "the bar must be no harder than an effect this program has actually "
        "accepted as a production fold")


def test_the_incumbent_clears_the_bar_and_the_ladder_peak_does_not(L):
    """⭐ Both halves matter. The first says a repeat of the effect being
    confirmed is adoptable; the second says the lower bar is NOT quietly a bar
    the ladder already cleared."""
    inc = L.CONTEXT_ROWS[
        "fpu=0.2 — fpu_resurrection CELL_FPU02, band 155e9, ARB OFF"]
    assert L.branch_for_cell(inc["M"], inc["se"], inc["z"],
                             gates_ok=True) == "H-ADOPT"
    pk = L.CONTEXT_ROWS[
        "fpu=0.15 — fpu_ladder CELL_FPU015, band 166e9, ARB OFF"]
    assert L.branch_for_cell(pk["M"], pk["se"], pk["z"],
                             gates_ok=True) != "H-ADOPT"


def test_the_bar_is_on_the_interval_not_the_point_estimate(L):
    """M=+1.5 is a point estimate half again the bar whose LB95 is below it —
    at BOTH rounds' se. Doubling n narrowed the interval; it did not move the
    bar onto the point estimate."""
    assert L.branch_for_cell(1.5, 0.69, 1.5 / 0.69,
                             gates_ok=True) == "H-UNRESOLVED"
    se0 = L.se_model(L.CELLS[0].n_decks)
    assert L.branch_for_cell(1.5, se0, 1.5 / se0,
                             gates_ok=True) == "H-UNRESOLVED"


def test_elo_is_never_a_branch_input(L):
    assert "elo" not in L.branch_for_cell.__code__.co_varnames


def test_the_read_distribution_matches_the_read_rule_table(L):
    """⛔ DOC vs CODE. READ_RULE §8 prints these percentages; if the arithmetic
    moves and the prose does not, the round is advertising odds it does not have.
    """
    se0 = L.se_model(L.CELLS[0].n_decks)
    txt = (PREP / "READ_RULE.md").read_text()
    for delta, key, printed in ((0.0, "H-BOUNDED", "50.6 %"),
                                (0.0, "H-UNRESOLVED", "47.1 %"),
                                (1.01875, "H-UNRESOLVED", "95.4 %"),
                                (1.835, "H-ADOPT", "39.4 %"),
                                (2.0, "H-ADOPT", "52.9 %"),
                                (2.95125, "H-ADOPT", "97.9 %")):
        got = L.read_distribution(delta, se0)[key] * 100.0
        assert printed in txt, f"READ_RULE §8 no longer prints {printed}"
        assert abs(got - float(printed.split()[0])) < 0.1, (
            f"read_distribution({delta})[{key}] = {got:.2f}% but READ_RULE §8 "
            f"prints {printed}")
    assert L.n_decks_for_adopt_power(2.95125, 0.80) == 396
    assert 1400 <= L.n_decks_for_bounded_power(0.80) <= 1650


def test_the_round_is_BLIND_to_round_ones_own_point_estimate_and_says_so(L):
    """⛔⛔ THE ROUND'S CENTRAL LIMITATION, PINNED AS A TEST BECAUSE IT IS THE
    ONE CLAIM A SUCCESSOR ROUND WOULD BE TEMPTED TO SOFTEN.

    If the true effect is what round 1 measured (+1.019), this round reads
    H-UNRESOLVED ~95% of the time and 80% adopt power would need over four
    MILLION decks. A pair that stopped saying so would be advertising a
    resolving power it does not have."""
    se0 = L.se_model(L.CELLS[0].n_decks)
    rd = L.read_distribution(1.01875, se0)
    assert rd["H-UNRESOLVED"] > 0.90
    assert rd["H-ADOPT"] < 0.05
    assert L.n_decks_for_adopt_power(1.01875, 0.80) > 1_000_000
    for name in ("DESIGN.md", "READ_RULE.md"):
        txt = (PREP / name).read_text()
        assert "4,279,208" in txt, f"{name} no longer prints the n it would need"
        assert "BLIND" in txt.upper()
    # ⭐ and the honest one-number summary: the 50%-power effect size
    assert abs((L.BAR_EFFECT + 2 * se0) - 1.965) < 0.01
    assert "+1.97" in (PREP / "DESIGN.md").read_text()


def test_the_sizing_constant_is_round_ones_own_arb_on_realization(L):
    """⭐ Round 1 is the ONLY arbiter-on-both-seats cell in existence, so its
    realized dispersion — not the arb-off 13.81 stand-in — is what sizes this
    round. ⛔ Its MEAN enters nothing."""
    r1 = L.ARB_ON_SIBLING[
        "fpu_h2h ROUND 1 / CELL_H2H_FPU02 (b168e9, n=400 decks, ⭐ ARB ON BOTH SEATS)"]
    assert abs(L.SIGMA_D_MODEL - r1["implied_sigma_D"]) < 5e-4
    assert abs(L.se_model(400) - r1["realized_se"]) < 5e-4
    assert abs(L.se_model(800) - 0.4826) < 5e-4


# --------------------------------------------------------------------------- #
# WORKERS.conf RESTATES THE LAW — A RESTATEMENT THAT DRIFTS IS A DEFECT        #
# --------------------------------------------------------------------------- #

def _conf(key: str) -> str:
    txt = (PREP / "WORKERS.conf").read_text()
    m = re.search(rf"^{key}=(\S+)$", txt, re.M)
    assert m, f"{key} missing from WORKERS.conf"
    return m.group(1)


def test_workers_conf_agrees_with_the_law(L):
    assert int(_conf("K_DETS")) == L.K_DETS
    assert int(_conf("SIMS_PER_DET")) == L.SIMS_PER_DET
    assert int(_conf("TOTAL_SIMS")) == L.TOTAL_SIMS
    assert int(_conf("EXACT_K")) == L.EXACT_K
    assert _conf("EXACT_MODE") == L.EXACT_MODE
    assert _conf("BACKEND") == L.BACKEND
    assert _conf("RULES_PROFILE") == L.RULES_PROFILE
    assert int(_conf("BAND_H2H")) == L.BAND == L.CELLS[0].seed_start
    assert int(_conf("THROWAWAY_BASE")) == L.THROWAWAY_BASE
    assert float(_conf("FPU_DOSE")) == L.CELLS[0].value == 0.2
    assert int(_conf("N_CHUNKS")) == L.N_CHUNKS == L.CELLS[0].n_chunks
    assert int(_conf("DECKS_PER_CHUNK")) == L.DECKS_PER_CHUNK \
        == L.CELLS[0].decks_per_chunk


def test_workers_conf_restates_the_deployed_arbiter(L):
    assert int(_conf("TIEARB_B")) == L.DEPLOYED_TIEARB["B"]
    assert int(_conf("TIEARB_J")) == L.DEPLOYED_TIEARB["J"]
    assert _conf("TIEARB_MODE") == L.DEPLOYED_TIEARB["mode"]
    assert _conf("TIEARB_SALT") == L.DEPLOYED_TIEARB["salt"]
    assert float(_conf("TIEARB_EPS")) == L.DEPLOYED_TIEARB["eps"]
    assert _conf("TIEARB_PHASE_GATE") == L.DEPLOYED_TIEARB["phase_gate"]


def test_the_provenance_stamps_are_coherent():
    """The freeze-time all-unstamped assertion retired 2026-08-31 at launch:
    W was stamped from the sweep (26). What stays law: BLIND_COMMIT is either
    the literal PENDING or a 40-hex sha (never garbage), and W_LAPTOP is either
    the sweep value or the TBD sentinel — the launcher refuses everything else."""
    bc = _conf("BLIND_COMMIT")
    assert bc == "PENDING" or (len(bc) == 40 and all(c in "0123456789abcdef" for c in bc))
    for key in ("W_LAPTOP", "W_LOCAL"):
        w = _conf(key)
        assert w == "TBD_FROM_SWEEP" or w.isdigit(), key


def test_both_share_paths_are_defined_and_are_the_right_way_round():
    """⚠️⚠️ THE SHARE MOUNT PATH DIFFERS BY BOX, and ROUND 2 MAY RUN ON BOTH —
    so unlike round 1 (laptop-only) BOTH must be defined, and getting them the
    wrong way round is the exact class of mistake the PreToolUse lint hook
    blocks. They are the SAME storage, which is what lets the two boxes' chunk
    dirs sit under ONE out-root and be pooled by ONE read."""
    txt = (PREP / "WORKERS.conf").read_text()
    assert re.search(r"^SHARE_LAPTOP=" + re.escape('/mnt/carc-shared') + "$",
                     txt, re.M)
    assert re.search(r"^SHARE_LOCAL=" + re.escape('/mnt/c/carc-shared') + "$",
                     txt, re.M)


# --------------------------------------------------------------------------- #
# THE LAUNCHER                                                                 #
# --------------------------------------------------------------------------- #

def test_run_cells_is_syntactically_valid():
    r = subprocess.run(["bash", "-n", str(PREP / "run_cells.sh")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def test_run_cells_refuses_local_while_W_LOCAL_IS_UNSTAMPED(L):
    """⛔⛔ ROUND 1's W REFUSAL, CARRIED ONTO THE BOX THAT NOW NEEDS IT.

    `W_LAPTOP` is BANKED (26) so the laptop launches; `W_LOCAL` is UNSET because
    no arb-on local sweep existed at the freeze commit. ⛔ NOTHING is exempt —
    not `--dry-run`, not `--smoke`: a smoke at a W the box will not run is a
    smoke of a different tenancy."""
    r = subprocess.run([str(PREP / "run_cells.sh"), "--role", "local",
                        "--dry-run"], capture_output=True, text=True,
                       timeout=120)
    out = r.stdout + r.stderr
    if _conf("W_LOCAL") == "TBD_FROM_SWEEP":
        assert r.returncode != 0
        assert "W_LOCAL" in out and "TBD_FROM_SWEEP" in out
    # the refusal text is pinned as SOURCE regardless, the house anti-drift style
    src = (PREP / "run_cells.sh").read_text()
    assert "TBD_FROM_SWEEP" in src and "REFUS" in src.upper()


def test_run_cells_does_NOT_refuse_the_local_box_as_such(L):
    """⭐⭐ THE DELIBERATE REVERSAL OF ROUND 1. Round 1 refused `--role local`
    outright (the owner held the box, and its `G-HOST` would have voided the
    archive). ⛔ ROUND 2's flexible-box clause (DESIGN §6.4) pre-registers box
    assignment as THROUGHPUT-ONLY and permits it to change mid-round, so a
    blanket refusal would make the owner's own funded flexibility unusable.

    ⚠️ The ONLY thing standing between local and a launch is the unstamped
    `W_LOCAL` — which is a tenancy question, not a validity one."""
    # ⚠️ READ THE CODE, NOT THE PROSE: the launcher's comments NAME round 1's
    # "LAPTOP ONLY" rule in order to explain why it is gone, and a substring
    # test on the whole file fires on its own documentation.
    code = _launcher_code()
    assert "LAPTOP ONLY" not in code, (
        "round 1's laptop-only refusal survived the fork — it would refuse the "
        "very box the flexible-box clause exists to add")
    assert "--role must be laptop or local" in code
    for c in L.ROLES:
        assert c in ("laptop", "local")
    assert set(L.ROLES) == {"laptop", "local"}


# --------------------------------------------------------------------------- #
# ⭐⭐⭐ THE FLEXIBLE-BOX CLAUSE — ITS MECHANICS, AS IMPLEMENTED               #
# --------------------------------------------------------------------------- #

def test_the_harness_still_has_no_seed_range_flag_so_the_launcher_owns_it():
    """⛔⛔ THE PREMISE OF THE WHOLE RANGE-RESTRICTION DESIGN, CHECKED RATHER
    THAN ASSUMED. `eval_fair_puct` exposes only `--n` and `--seed-start`. If it
    ever grew a real `--seed-lo`/`--seed-hi`, the launcher's per-chunk
    arithmetic would be redundant and DESIGN §6.4 would be describing a
    workaround that no longer exists."""
    txt = (REPO / "scripts" / "classical_search" / "eval_fair_puct.py").read_text()
    declared = set(re.findall(r'add_argument\(\s*[\s\S]{0,80}?"(--[a-z0-9-]+)"',
                              txt))
    assert "--seed-start" in declared and "--n" in declared
    for absent in ("--seed-lo", "--seed-hi", "--seed-end", "--band"):
        assert absent not in declared, (
            f"eval_fair_puct now declares {absent} — DESIGN §6.4 describes a "
            "launcher-side workaround that may no longer be needed")


def test_the_launcher_slices_chunks_by_seed_start_and_n():
    """⭐ The range restriction IS `--seed-start <chunk lo> --n <2*decks> --paired`,
    which is exact because `_build_work(seed_start, n, paired=True)` yields
    `seed_start .. seed_start+n/2-1` at both seats."""
    code = _launcher_code()
    m = re.search(r"local args=\(([\s\S]*?)\n  \)", code)
    assert m
    args_block = m.group(1)
    assert '--n "$n_games" --paired --seed-start "$seed_start"' in args_block
    # ⛔ and the launcher PROBES that contract at launch, so a change in the
    # harness's work-builder cannot silently move every chunk's seeds
    src = (PREP / "run_cells.sh").read_text()
    assert "_build_work(1000, 6, True)" in src


def test_the_launcher_accepts_both_range_spellings_and_refuses_a_partial_chunk(L):
    """⛔⛔ A `--seed-lo/--seed-hi` that is not CHUNK-ALIGNED must be REFUSED:
    a partial chunk would put two boxes' records in ONE out-dir, which emits ONE
    manifest with ONE `host`, so the provenance map would become a silent lie
    that no gate could see."""
    src = (PREP / "run_cells.sh").read_text()
    for flag in ("--chunks", "--seed-lo", "--seed-hi", "--plan", "--reclaim"):
        assert flag in src, f"{flag} is missing from the launcher"
    c = L.CELLS[0]
    # the library owns the arithmetic, and it round-trips
    assert c.chunks_for_seed_range(*c.chunk_range(0)) == [0]
    assert c.chunks_for_seed_range(c.seed_start, c.seed_end) \
        == list(range(c.n_chunks))
    with pytest.raises(ValueError):
        c.chunks_for_seed_range(c.seed_start, c.seed_start + 1)
    with pytest.raises(ValueError):
        c.chunks_for_seed_range(c.seed_start + 50, c.seed_end)


def test_the_chunks_tile_the_band_exactly(L):
    """⛔ If they did not, `G-N`'s accounting identity could never hold — and
    that identity IS the flexible-box tiling check."""
    c = L.CELLS[0]
    covered = set()
    for row in L.chunk_plan(c):
        rng = set(range(row["seed_lo"], row["seed_hi"] + 1))
        assert not (covered & rng), f"{row['name']} overlaps an earlier chunk"
        covered |= rng
    assert covered == set(range(c.seed_start, c.seed_end + 1))
    assert L.N_CHUNKS * L.DECKS_PER_CHUNK == c.n_decks == 800


def test_the_sharding_gates_exist_and_fail_on_their_own_defects(L):
    """⛔⛔ THE PRICE OF §6.4, TESTED RATHER THAN DOCUMENTED. Round 1 was one
    archive on one box, so 'is this one cell?' was answered by the filesystem."""
    c = L.CELLS[0]

    def shard(seeds, host="laptop-wsl", summary=True, dose=0.2):
        rows = [{"seed": x, "a_seat": a, "diff": 1.0} for x in seeds
                for a in (0, 1)]
        man = {"host": host}
        for addr, v in (("config.cand_search.fpu_reduction", dose),
                        ("config.cand_search.c_puct", None),
                        ("config.champion.fpu_reduction", dose),
                        ("config.champion.c_puct", 1.5),
                        ("config.champion.tau_p", 5.0),
                        ("config.champion.k_dets", L.K_DETS),
                        ("config.champion.sims_per_det", L.SIMS_PER_DET),
                        ("config.champion.total_sims", L.TOTAL_SIMS),
                        ("config.opponent.champ_cfg.fpu_reduction", None),
                        ("config.opponent.champ_cfg.c_puct", 1.5),
                        ("config.opponent.champ_cfg.tau_p", 5.0),
                        ("config.cand_leaf_hash", L.LEAF_HASH),
                        ("config.opp_leaf_hash", L.LEAF_HASH),
                        ("config.endgame.exact_k", L.EXACT_K),
                        ("config.endgame.mode", L.EXACT_MODE),
                        ("config.backend.name", L.BACKEND),
                        ("rules_profile.name", L.RULES_PROFILE)):
            cur = man
            parts = addr.split(".")
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
            cur[parts[-1]] = v
        man["cand_tiearb"] = dict(L.DEPLOYED_TIEARB)
        man["opp_tiearb"] = dict(L.DEPLOYED_TIEARB)
        return {"manifest": man,
                "summary": {"n": len(rows), "n_failed": 0} if summary else None,
                "records": rows}

    healthy = {}
    for row in L.chunk_plan(c):
        healthy[row["name"]] = shard(
            range(row["seed_lo"], row["seed_hi"] + 1),
            host="laptop-wsl" if row["chunk"] < 4 else "5800x-box")
    assert L.chunks_gate(c, healthy)["ok"]
    assert L.nodup_gate(c, healthy)["ok"]
    assert L.shard_ident_gate(healthy)["ok"]
    assert L.host_provenance_gate(c, healthy)["ok"]

    # ⛔ a chunk KILLED mid-flight (manifest, no summary) — §6.4's own mode
    killed = dict(healthy)
    r1 = L.chunk_plan(c)[1]
    killed[r1["name"]] = shard(range(r1["seed_lo"], r1["seed_hi"] + 1),
                               summary=False)
    assert not L.chunks_gate(c, killed)["ok"]

    # ⛔ OVERLAPPING ranges — the two-box mis-split
    dup = dict(healthy)
    r4 = L.chunk_plan(c)[4]
    dup[r4["name"]] = shard(range(r4["seed_lo"] - 10, r4["seed_hi"] + 1),
                            host="5800x-box")
    assert not L.nodup_gate(c, dup)["ok"]

    # ⛔ a chunk that resolved a DIFFERENT dose — a stale bundle on box 2
    drift = dict(healthy)
    r6 = L.chunk_plan(c)[6]
    drift[r6["name"]] = shard(range(r6["seed_lo"], r6["seed_hi"] + 1),
                              host="5800x-box", dose=0.15)
    assert not L.shard_ident_gate(drift)["ok"]

    # ⛔ ANTI-VACUITY: an empty pool must NOT pass
    assert not L.nodup_gate(c, {})["ok"]
    assert not L.shard_ident_gate({})["ok"]
    assert not L.host_provenance_gate(c, {})["ok"]


def test_G_HOST_is_provenance_only_and_any_tiling_is_legal(L):
    """⭐⭐ Box assignment is THROUGHPUT-ONLY. G-HOST voids on NOTHING about
    which funded box played what; it refuses only a DESTROYED provenance map."""
    c = L.CELLS[0]

    def shard(seeds, host):
        return {"manifest": {"host": host},
                "summary": {"n": 2 * len(list(seeds)), "n_failed": 0},
                "records": [{"seed": x, "a_seat": a, "diff": 1.0}
                            for x in seeds for a in (0, 1)]}

    # an INTERLEAVED assignment is legal
    inter = {row["name"]: shard(range(row["seed_lo"], row["seed_hi"] + 1),
                                "5800x-box" if row["chunk"] % 2 else "laptop-wsl")
             for row in L.chunk_plan(c)}
    g = L.host_provenance_gate(c, inter)
    assert g["ok"], g["why"]
    assert sorted(g["detail"]["chunks_by_role"]) == ["laptop", "local"]
    # so is all-one-box
    allo = {row["name"]: shard(range(row["seed_lo"], row["seed_hi"] + 1),
                               "laptop-wsl") for row in L.chunk_plan(c)}
    assert L.host_provenance_gate(c, allo)["ok"]
    # ⛔ but an ABSENT host, or an UNFUNDED box, is a FAIL
    bad = dict(inter)
    first = L.chunk_plan(c)[0]["name"]
    bad[first] = {"manifest": {}, "summary": inter[first]["summary"],
                  "records": inter[first]["records"]}
    assert not L.host_provenance_gate(c, bad)["ok"]
    bad2 = dict(inter)
    bad2[first] = {"manifest": {"host": "vast-ai-node-7"},
                   "summary": inter[first]["summary"],
                   "records": inter[first]["records"]}
    assert not L.host_provenance_gate(c, bad2)["ok"]


def test_host_role_strict_has_no_catch_all(L):
    """⛔⛔ THE DEFECT ROUND 2's OWN SELFTEST FOUND. `host_matches_box(h,
    "local")` carries a 'not the laptop => local' catch-all. Harmless in round 1
    (laptop-only, and the gate voided anything else) — but with BOTH boxes legal
    it would launder ANY unrecognised host into a clean provenance line."""
    assert L.host_role_strict("laptop-wsl") == "laptop"
    assert L.host_role_strict("laptop-pop") == "laptop"
    assert L.host_role_strict("5800x-box") == "local"
    assert L.host_role_strict("Doctor") == "local"
    for unfunded in ("vast-ai-node-7", "", None, "runpod-a100"):
        assert L.host_role_strict(unfunded) is None, unfunded
    # ⚠️ and the round-1 function is UNCHANGED — the catch-all is still there,
    # which is exactly why the strict resolver had to be a NEW symbol.
    ok, _ = L.host_matches_box("vast-ai-node-7", "local")
    assert ok, ("host_matches_box was edited; it is round 1's frozen carry and "
                "the fix belongs in host_role_strict")


def test_the_plan_mode_spends_nothing_and_is_gitignored(L):
    """⭐ `--plan` reads the share and proposes a split so the owner's 'add local
    now' decision is made against DISK. ⛔ It is a SCHEDULING artefact and must
    never be mistaken for a verdict."""
    src = (PREP / "run_cells.sh").read_text()
    assert "NO COMPUTE SPENT" in src
    assert "/PLAN_*.json" in (PREP / ".gitignore").read_text()
    r = subprocess.run([str(PREP / "run_cells.sh"), "--role", "laptop",
                        "--plan"], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    plan = json.loads(r.stdout[r.stdout.index("{"):r.stdout.rindex("}") + 1])
    assert len(plan["chunks"]) == L.N_CHUNKS
    assert plan["remaining_games"] == L.CELLS[0].n_games
    assert plan["eta_h_laptop_only"] > plan["eta_h_both_boxes"]
    assert set(plan["suggested_split"]) == {"laptop", "local"}
    # ⭐ both rates are MEASURED arb-on at this round's cell shape — no
    # cross-box extrapolation survives in the ETA
    assert set(plan["rates_g_per_h"]) == {"laptop_MEASURED_W26_arb_on",
                                          "local_MEASURED_W30_arb_on"}


def test_the_claim_interlock_only_frees_an_EMPTY_chunk():
    """⛔⛔ An out-dir emits ONE manifest with ONE `host`. If a PARTIALLY PLAYED
    chunk changed hands, G-HOST would publish a FALSE provenance map with every
    other gate passing. So --reclaim frees a chunk ONLY when it holds ZERO
    records, and an interrupted chunk is resumed on the box that started it."""
    src = (PREP / "run_cells.sh").read_text()
    assert "CLAIM.json" in src and "--reclaim" in src
    assert 'n_recs" -eq 0' in src, (
        "the zero-records condition on --reclaim is the whole interlock")
    for name in ("DESIGN.md", "READ_RULE.md"):
        assert "PROVENANCE" in (PREP / name).read_text().upper()


def test_no_cross_box_statistic_is_claimed_and_the_pair_says_why():
    """⭐⭐ The obvious objection to a two-box round, answered in the pair: both
    seatings of every deck are played inside ONE chunk on ONE box, so the box is
    COMMON TO BOTH ARMS of every contrast and cannot bias
    candidate-minus-opponent. Cross-box SOURCE identity is still required and is
    G-REV's."""
    for name in ("DESIGN.md", "READ_RULE.md"):
        txt = (PREP / name).read_text()
        assert "cross-box float identity is not relied on" in txt.lower() \
            or "CROSS-BOX FLOAT IDENTITY IS NOT RELIED ON" in txt
        assert "common to both arms" in txt.lower()
        assert "cross_box_rev_gate" in txt or "G-REV" in txt


def test_the_smoke_is_per_box_on_its_own_throwaway_offset(L):
    """⛔ A box may JOIN MID-ROUND and is the one LEAST likely to have been on
    the launch checklist — so its smoke is the only thing proving it can express
    the cell. Shared offsets would let one box's smoke stand in for the other's.
    """
    assert set(L.SMOKE_OFFSETS) == set(L.IDENT_OFFSETS) == set(L.ROLES)
    assert len(set(L.SMOKE_OFFSETS.values())) == len(L.ROLES)
    assert len(set(L.IDENT_OFFSETS.values())) == len(L.ROLES)
    src = (PREP / "run_cells.sh").read_text()
    assert "SMOKE_OFFSETS" in src and "IDENT_OFFSETS" in src
    assert "SMOKE_H2H2_${ROLE}" in src


def _launcher_code() -> str:
    """`run_cells.sh` with COMMENTS STRIPPED.

    ⚠️ Every flag-shaped invariant below must read the CODE, not the prose: the
    launcher's own comments NAME the forbidden flags (`--cand-c-puct`,
    `--c-puct`, `--tau-p`) in order to explain why they are absent, and a naive
    substring test on the whole file fires on its own documentation."""
    out = []
    for line in (PREP / "run_cells.sh").read_text().splitlines():
        out.append(re.sub(r"(^|\s)#.*$", "", line))
    return "\n".join(out)


def test_the_launcher_arms_BOTH_seats_and_carries_no_shared_knob_flag():
    """⛔⛔ THE SINGLE-VARIABLE INVARIANT, READ OFF THE LAUNCHER'S OWN CODE.

    Without `--opp-tiearb-*` the cell is candidate=champ+arb+fpu vs
    opponent=plain champ — a CONFOUNDED arb+fpu cell claiming one variable, and
    the shape this leg was INEXPRESSIBLE as before 2026-08-31.
    `--c-puct` / `--tau-p` are the SHARED flags and move BOTH sides."""
    code = _launcher_code()
    for flag in ("--cand-tiearb-enabled", "--opp-tiearb-enabled",
                 "--cand-fpu-reduction", "--paired", "--rules-profile",
                 "--out-root", "--out-subdir"):
        assert flag in code, f"{flag} is missing from the launcher"
    for forbidden in ("--cand-c-puct", "--tau-p"):
        assert forbidden not in code, (
            f"{forbidden} appears in the launcher — it would make the cell "
            "two-variable or move BOTH sides")
    # `--c-puct` must not appear as its own flag (the `--cand-...` and
    # `--opp-...` spellings are different flags and are absent anyway).
    assert not re.search(r"(?<![-\w])--c-puct(?![\w-])", code)
    # ⚠️ `--out` IS a legal flag — of `analyze_h2h.py`. What PG-D7 forbids is
    # passing it to `eval_fair_puct`, whose out dir is `--out-root`/`--out-subdir`
    # and whose argparse REFUSES the ambiguous prefix. So the check is scoped to
    # the harness invocation's own argument array, not to the whole file.
    m = re.search(r"local args=\(([\s\S]*?)\n  \)", code)
    assert m, "could not find the harness argument array in run_cells.sh"
    args_block = m.group(1)
    assert "eval_fair_puct.py" in args_block
    assert not re.search(r"(?<![-\w])--out(?![\w-])", args_block), (
        "`--out` is AMBIGUOUS in eval_fair_puct (PG-D7) — use "
        "--out-root/--out-subdir")
    for flag in ("--cand-tiearb-enabled", "--opp-tiearb-enabled", "--paired"):
        assert flag in args_block, f"{flag} is not on the harness invocation"


#: Flags the launcher passes to tools that are NOT the harness (`git`, `ps`).
_NON_HARNESS_FLAGS = {"--porcelain", "--sort"}
#: The launcher's own flags, and the adjudicator's.
_OUR_FLAGS = {"--role", "--dry-run", "--smoke", "--selftest", "--root",
              "--smoke-mode", "--smoke-cell", "--ident-mode", "--ident-a",
              "--ident-a2", "--ident-b", "--out", "--pin-laptop", "--pin-local",
              # ⭐ round 2's flexible-box flags — the launcher's own
              "--chunks", "--seed-lo", "--seed-hi", "--plan", "--reclaim"}


def test_every_flag_the_launcher_emits_exists_in_the_harness():
    """⭐⭐ THE WIRING TEST, WITHOUT IMPORTING THE HARNESS. A flag that
    `eval_fair_puct` does not define kills the run at argparse — after the
    precondition ladder has passed, and for the real cell that is after the
    census, the probes and the rev pin. The check is a TEXT scan of the harness's
    own `add_argument` calls, so it costs milliseconds and needs no
    `carcassonne_ai` import.

    ⚠️ `--rules-profile` is NOT declared in `eval_fair_puct.py`: it is added by
    `rules_profile.add_argument(ap)` (`src/carcassonne_ai/rules_profile.py`), so
    that file is scanned too. A scan of the harness alone would report a false
    missing flag — and the indirection is exactly the kind of thing a
    from-the-design test gets wrong."""
    known = set()
    for p in (REPO / "scripts" / "classical_search" / "eval_fair_puct.py",
              REPO / "src" / "carcassonne_ai" / "rules_profile.py"):
        known |= set(re.findall(r'add_argument\(\s*[\s\S]{0,80}?"(--[a-z0-9-]+)"',
                                p.read_text()))
    assert "--opp-tiearb-enabled" in known, (
        "this tree predates the 2026-08-31 opponent-side plumbing — the round "
        "is not expressible on it")
    assert "--rules-profile" in known
    emitted = set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*[a-z0-9])(?![\w-])",
                             _launcher_code()))
    missing = sorted(f for f in emitted - _OUR_FLAGS - _NON_HARNESS_FLAGS
                     if f not in known)
    assert not missing, (
        f"the launcher emits flags eval_fair_puct does not define: {missing}")


def test_the_launcher_probes_both_python_only_plumbings():
    """⛔⛔ THE PRIMARY PROVENANCE RISK HAS TWO HEADS. Both the fpu plumbing
    (2026-08-29) and the opponent-side arbiter plumbing (2026-08-31) are
    PYTHON-ONLY, so a stale box produces a healthy wheel, a healthy leaf hash and
    a silently wrong cell."""
    txt = (PREP / "run_cells.sh").read_text()
    assert "search_config_rs" in txt and "fpu=Some(" in txt
    assert "_make_opponent" in txt and "_opp_tiearb_telemetry" in txt
    assert "assert_tiearb_sides" in txt


def test_the_ident_legs_share_one_seed_and_drop_the_dose_on_exactly_one():
    """⭐ A / A2 identical; B same seeds, dose dropped. If the three legs did not
    share a seed the IDENT propositions would be about different games."""
    txt = (PREP / "run_cells.sh").read_text()
    assert txt.count("IDENT_SEED") >= 4          # one assignment + three uses
    assert 'run_cell "SMOKE_IDENT_A_${ROLE}"' in txt
    assert 'run_cell "SMOKE_IDENT_A2_${ROLE}"' in txt
    assert 'run_cell "SMOKE_IDENT_B_${ROLE}"' in txt
    # leg B passes the EMPTY dose — the positive control
    assert re.search(r'run_cell "SMOKE_IDENT_B_\$\{ROLE\}"\s+"\$IDENT_SEED"'
                     r'\s+"\$IDENT_GAMES"\s+""', txt)


def test_the_smoke_requires_the_two_new_gates(L):
    """⛔ A smoke that did not read the arbiter on BOTH seats would pass a
    launcher that armed only the candidate — and ship the confounded cell."""
    A = _load_by_path("fpu_h2h_r2_analyze", PREP / "analyze_h2h.py")
    assert set(A.SMOKE_REQUIRED_GATES) >= {"G-FPU", "G-TWOSIDED",
                                           "G-TIEARB-SIDES", "G-TIEARB-FIRE"}


# --------------------------------------------------------------------------- #
# THE GOLDEN GATE IS INHERITED — AND THE INHERITANCE IS CHECKED, NOT ASSUMED   #
# --------------------------------------------------------------------------- #

def test_no_golden_gate_is_shipped_here_and_the_ladders_is_named():
    """⭐ This round does NOT rebuild the gate. It inherits the ladder's and
    re-asserts the wheel at launch; DESIGN §9 states the argument and names the
    two gaps the IDENT legs pay."""
    assert not (PREP / "golden_gate").exists()
    txt = (PREP / "run_cells.sh").read_text()
    assert "fpu_ladder_prep/FPU_BITEXACT_LADDER.json" in txt
    assert "carc_rs_binary_sha" in txt
    design = (PREP / "DESIGN.md").read_text()
    assert "a9bb2311ab9a635d" in design
    assert "GATE_NEST.json" in design
    for gap in ("TOGETHER", "0.2` is not one of"):
        assert gap in design, "DESIGN §9.2 no longer names both gaps"
    # ⭐⭐ ROUND 2 ADDS A THIRD SOURCE, and its STATUS is the load-bearing part:
    # round 1's banked pass is an INSTRUMENT certificate, not a statistical one.
    assert "INSTRUMENT* CERTIFICATE" in design or \
        "INSTRUMENT CERTIFICATE" in design.upper()
    assert "PER BOX" in design.upper(), (
        "round 1's pass was banked on the LAPTOP; local has never run a "
        "gate-passing cell of this family and the pair must say so")


# --------------------------------------------------------------------------- #
# THE BAND CLAIM                                                               #
# --------------------------------------------------------------------------- #

def test_band_claim_row_matches_the_registry_schema(L):
    d = json.loads((PREP / "BAND_CLAIM.json").read_text())
    assert d["_order_of_operations"], "the claim order is the 146e9 trap's fix"
    rows = d["_csv_rows"]
    assert len(rows) == 1
    parsed = next(csv.reader(io.StringIO(rows[0])))
    header = next(csv.reader(io.StringIO(
        (REPO / "governance" / "BAND_REGISTRY.csv").read_text()
        .splitlines()[0])))
    assert len(parsed) == len(header), (
        f"the CSV row has {len(parsed)} fields, the registry has {len(header)}")
    assert int(parsed[0]) == L.BAND
    assert parsed[header.index("tier")] == "claim"
    assert parsed[header.index("decision_influenced")] == "yes"
    assert parsed[header.index("evidence_or_claim")] \
        == "measurement/fpu_h2h_r2_prep/READ_RULE.md"
    assert "169000000000..169000000799" in rows[0]
    assert "THROUGHPUT-ONLY" in rows[0], (
        "the registry row must carry the flexible-box clause — the row is what "
        "a future reader finds first")


def test_the_bands_status_is_claimed_or_spent(L):
    """⚠️ Was `test_the_band_is_not_already_in_the_registry`: written and frozen
    at CLAIM TIME (before the round played), when the band was correctly not
    yet in the registry. The round has since run to completion and the band
    moved claimed -> spent (governance/BAND_REGISTRY.csv), so the original
    `str(L.BAND) not in ids` assertion fails permanently in any full-suite run
    from here on. Relaxed to accept either live-claim state while STILL
    asserting band identity (band number + label), so a truly wrong/missing
    row is still caught."""
    with open(REPO / "governance" / "BAND_REGISTRY.csv", newline="") as f:
        by_band = {row["band_seed_start"]: row for row in csv.DictReader(f)}
    row = by_band.get(str(L.BAND))
    assert row is not None, f"band {L.BAND} is not registered at all"
    assert row["status"] in ("claimed", "spent"), (
        f"band {L.BAND} status is {row['status']!r}, expected claimed or spent")
    assert "CELL_H2H2_FPU02" in row["label"], \
        "the registry row at this band number is not this round's claim"
    for spent in ("164000000000", "165000000000", "166000000000",
                  "167000000000", "168000000000"):
        assert spent in by_band, (
            "the ladder's bands AND round 1's should be registered — 168e9 in "
            "particular, because re-playing it would put round 2's records in "
            "round 1's seed space")


def test_the_throwaway_range_never_touches_the_cells_decks(L):
    c = L.CELLS[0]
    lo, hi = L.THROWAWAY_BASE, L.THROWAWAY_BASE + L.THROWAWAY_SPAN - 1
    assert c.seed_end < lo or c.seed_start > hi
    # and it lives inside this band's own 1e9 space, the house convention
    assert L.BAND <= lo <= L.BAND + 999_999_999


# --------------------------------------------------------------------------- #
# THE FIXTURE AND THE GITIGNORE                                                #
# --------------------------------------------------------------------------- #

def test_the_fixture_differs_from_the_round_in_scale_only(L):
    specs = json.loads((PREP / "selftest_fixture" / "SPECS.json").read_text())
    assert len(specs) == 1
    s, f = specs[0], L.CELLS[0]
    assert (s["name"], s["role"], s["knob"], s["value"]) == (
        f.name, f.role, f.knob, f.value)
    assert s["n_decks"] != f.n_decks and s["seed_start"] != f.seed_start
    # ⭐⭐ AND IT IS SHARDED — a one-chunk fixture would leave the flexible-box
    # clause's three gates DOCUMENTED rather than TESTED.
    assert s["n_chunks"] >= 2


def test_the_fixture_is_a_TWO_BOX_round(L):
    """⛔⛔ A one-box fixture cannot distinguish a healthy two-box round from a
    G-WHEEL-SAME violation: `carc_rs_binary_sha` is BOX-LOCAL by construction,
    so the healthy shape has TWO shas and ONE code_rev."""
    fx = PREP / "selftest_fixture"
    spec = L.CellSpec(**json.loads((fx / "SPECS.json").read_text())[0])
    hosts, shas, revs = set(), set(), set()
    for row in L.chunk_plan(spec):
        man = json.loads((fx / row["name"] / "manifest.json").read_text())
        hosts.add(man["host"])
        shas.add(man["carc_rs_binary_sha"])
        revs.add(man["code_rev"])
    assert len(hosts) == 2, f"the fixture ran on {hosts}"
    assert len(shas) == 2, "box-local shas must differ between the two boxes"
    assert len(revs) == 1, "ONE source rev across boxes — that is G-REV's demand"
    assert {L.host_role_strict(h) for h in hosts} == {"laptop", "local"}


def test_the_fixture_manifest_carries_the_opponent_seat_arbiter(L):
    """⭐⭐ PG-A1: the fixture's shape is copied from a REAL emitted archive, and
    the opponent-seat addresses are the ones the gate resolves. A fixture missing
    them would teach the gate a shape no healthy cell has."""
    man = json.loads((PREP / "selftest_fixture" / L.CELLS[0].chunk_name(0)
                      / "manifest.json").read_text())
    for addr in (("opp_tiearb",), ("config", "opp_tiearb"),
                 ("config", "opponent", "tiearb")):
        cur = man
        for part in addr:
            assert part in cur, f"the fixture has no {'.'.join(addr)}"
            cur = cur[part]
        assert cur["enabled"] is True and cur["B"] == 64
    # and the realized close-out counts, so the gate is proven to read the SPEC
    # keys only (a manifest gates identically before and after close-out)
    assert "fired_plies" in man["opp_tiearb"]
    assert "fired_plies" not in man["config"]["opp_tiearb"]
    ok, findings = L.TG.check_tiearb_sides(man, L.DEPLOYED_TIEARB,
                                           L.DEPLOYED_TIEARB)
    assert ok, findings


def test_gitignore_patterns_are_all_anchored():
    """⚠️⚠️ An unanchored `PINNED_SRC_REV` matches at ANY DEPTH and swallows
    `selftest_fixture/PINNED_SRC_REV`, which is a COMMITTED FIXTURE FILE. Without
    it the selftest raises on a fresh clone."""
    for line in (PREP / ".gitignore").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert line.startswith("/"), f"unanchored .gitignore pattern: {line!r}"
    assert (PREP / "selftest_fixture" / "PINNED_SRC_REV").is_file()


def test_the_read_out_is_not_gitignored():
    """⛔ The verdict is the round's deliverable and is COMMITTED, exactly as
    fpu_ladder_prep/LADDER_VERDICT.json is."""
    assert "/H2H_VERDICT.json" not in (PREP / ".gitignore").read_text()


# --------------------------------------------------------------------------- #
# THE PAIR                                                                     #
# --------------------------------------------------------------------------- #

def test_the_pair_is_frozen_and_says_zero_games_exist():
    for name in ("DESIGN.md", "READ_RULE.md"):
        txt = (PREP / name).read_text()
        assert "STATUS: FROZEN" in txt
        assert "0 games have been played at this commit" in txt


def test_the_pair_states_the_adopt_consequence_is_a_proposal(L):
    """⛔ H-ADOPT licenses PROPOSING the PRODUCTION.yaml flip and step 3 — never
    an automatic adoption. If that word softens, the round has changed."""
    assert "PROPOSING" in L.ADOPT_CONSEQUENCE
    assert "NOT AN ADOPTION" in L.ADOPT_CONSEQUENCE
    for name in ("DESIGN.md", "READ_RULE.md"):
        txt = (PREP / name).read_text()
        assert "governance/PRODUCTION.yaml" in txt
        assert ("UNTOUCHED" in txt or "does not touch" in txt), (
            f"{name} no longer says PRODUCTION.yaml is untouched on every branch")
        assert "PROPOS" in txt.upper()


def test_the_pair_names_the_owner_funding_rather_than_a_fired_trigger():
    """⚠️ The ladder read LADDER-UNRESOLVED, whose own READ_RULE §8.3 says it
    does NOT discharge the confirmation leg. This round must not claim a trigger
    fired."""
    design = (PREP / "DESIGN.md").read_text()
    assert "LADDER-UNRESOLVED" in design
    assert "OWNER-FUNDED" in design or "owner-funded" in design
    assert "feedback_execute_prereg_triggers" in design
