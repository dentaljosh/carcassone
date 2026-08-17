"""tiearb2 STAGE 2 PHASE B — the instrument's tests.

TWO instruments are pinned here, in one file because READ_RULE §4.1 names this
path:

  * sections A-G — the ADJUDICATOR (`scripts/tiletie/analyze_tiearb2_stage2.py`).
    Pure plan/stat surgery: no engine import, no search, no share writes, no game
    played. Every fixture is synthetic and lives under tmp_path.
  * section H — the RUST ARBITER KNOB (`carc_core::tiearb`, the `carc_rs` wheel):
    predicate parity with the corpus definition of record, and the byte-identical
    default path. Skipped, never failed, when the wheel is absent.

⚠️ NOTHING HERE PLAYS A CELL, READS A STRENGTH NUMBER, OR ADJUDICATES ANYTHING.

⚠️ This suite tracks the AMENDED read-rule: `READ_RULE.md` §0 (PRE-RUN AMENDMENT,
commit `6c281f9e`), applied before the band claim and before game 1, with no band
claimed and no `summary.json` / `manifest.json` in existence. It set `G-N`'s deck
floor to **320** — the exact 80% analogue of the committed 640/800 games clause,
because the original 600 was unreachable (a paired n = 800 cell yields at most 400
decks) and so fired on a PERFECTLY COMPLETE run — named the `+1.0` PRESENTATION
split in §2, and corrected the knob to top-level `cand_tiearb`. **No adjudicating
bar moved**: `+2.0`, `+1.0` and `1.20` are unchanged and every §4 branch condition
is unchanged, which
`test_the_amendment_moved_no_adjudicating_bar_and_no_branch_condition` pins against
the pre-amendment text at `b2faa238`.

⭐ The centrepiece is section D, and it is the artefact READ_RULE §4.1 promises by
name: "This is verified by a machine sweep over the branch-condition truth table in
`tests/test_tiearb2_stage2.py`, which re-transcribes this section independently of
the implementation and asserts exactly one branch fires on every cell, `NaN`
included."  `_reference_branch` below is that independent re-transcription: it is
written from the READ_RULE TEXT, as five (six with G-ANOMALY) INDEPENDENT boolean
conditions with no if/elif chain, so "exactly one fires" is a real assertion and not
a restatement of the implementation's own control flow. The implementation must
agree with this file; this file is the spec.
"""
from __future__ import annotations

import itertools
import json
import math
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import analyze_tiearb2_stage2 as S2      # noqa: E402

NAN = float("nan")
CHAMP_HASH = "a36d2e15a3b3d71d"
BAND = 132000000000


# =========================================================================== #
# A. The committed constants -- pinned so a silent bar move fails LOUDLY
# =========================================================================== #
def test_bars_are_the_committed_constants():
    """READ_RULE §2: 'The bars are +2.0 (z) and 1.20 (the N4 cost trigger).
    Neither is a new constant.'  Plus §4's +1.0 PRESENT split and §3's floors."""
    assert S2.Z_BAR == 2.0
    assert S2.Z_PRESENT_BAR == 1.0
    assert S2.MS_RATIO_BAR == 1.20
    assert S2.MS_RATIO_NEUTRAL == 1.05
    assert S2.CHAMP_LEAF_HASH == CHAMP_HASH
    assert S2.B_EXPECTED == 16 and S2.J_EXPECTED == 4
    assert S2.SALT_EXPECTED == "tiearb2-deploy-v1"
    assert S2.MODE_BY_CELL == {"ARB": "argmax", "RND": "random"}
    assert S2.PHI_FLOOR == 1.0
    assert S2.BAND_EXPECTED == BAND
    assert S2.N_COMMON_FLOOR == 320          # AMENDED §0.B (was an unreachable 600)
    assert S2.CELL_GAMES_PLANNED == 800 and S2.CELL_GAMES_FLOOR == 640
    assert S2.ALL_GATES == ("G-J1", "G-J4", "G-J13", "G-FIRE", "G-BAND", "G-N",
                            "G-TOOL", "G-STAT")


def test_phase_a_cost_facts_match_COST_REMEASURE_on_disk():
    """§4.3 item 7 -- the numbers are CARRIED, so they must equal the artefact."""
    doc = json.loads((REPO / "measurement/tiearb2_stage2_20260817/"
                      "COST_REMEASURE.json").read_text())
    r16 = doc["ladder_primary_w30"]["rungs"]["16"]
    assert doc["c_tier1_rust_w30"] == pytest.approx(S2.C_TIER1_RUST, abs=5e-7)
    assert doc["speedup_vs_python"]["w30_vs_pilot_2.7274"] == pytest.approx(
        S2.C_TIER1_SPEEDUP_VS_PILOT, abs=5e-3)
    assert r16["rho_wall"] == pytest.approx(S2.RHO_WALL_16, abs=5e-5)
    assert r16["rho_amortized"] == pytest.approx(S2.RHO_AMORTIZED_16, abs=5e-5)
    # ⚠️ the one that is NOT solved
    assert r16["rho_phone"] == pytest.approx(S2.RHO_PHONE_16, abs=5e-4)
    assert doc["ladder_primary_w30"]["B_affordable"] == 16
    # Stage 1b's carried capture, verbatim
    assert r16["carried_capture"]["arb"] == S2.STAGE1B_ARB_H
    assert r16["carried_capture"]["z"] == S2.STAGE1B_ARB_H_Z


def test_verbatim_carries_are_byte_identical_to_the_committed_DESIGN():
    """§4.3 item 6: conditions (b) and (c) are carried VERBATIM. A paraphrase is a
    governance failure, so the strings are diffed against DESIGN.md itself."""
    design = (REPO / "measurement/tiearb2_stage2_20260817/DESIGN.md").read_text()
    for blob in (S2.CONDITION_B_VERBATIM, S2.CONDITION_C_VERBATIM,
                 S2.MISMATCH_I_VERBATIM, S2.MISMATCH_II_VERBATIM,
                 S2.MISMATCH_CONCLUSION_VERBATIM):
        # DESIGN.md carries them as blockquotes / bullets; strip the markers.
        stripped = "\n".join(ln.lstrip("> ").lstrip("- ") for ln in design.splitlines())
        want = "\n".join(ln.lstrip("> ").lstrip("- ") for ln in blob.splitlines())
        assert want in stripped, blob[:80]
    # ... and the check is not vacuous: a PARAPHRASE must not pass it
    stripped = "\n".join(ln.lstrip("> ").lstrip("- ") for ln in design.splitlines())
    assert S2.CONDITION_C_VERBATIM.replace("NO CORROBORATION",
                                           "no corroboration") not in stripped


# =========================================================================== #
# B. READ_RULE §2 -- ONE paired convention, mirrored from `_paired_z`
# =========================================================================== #
def _reference_paired(ds):
    """`eval_fair_puct._paired_z`'s arithmetic, transcribed from its source."""
    ds = list(ds)
    if len(ds) < 2:
        return None, None, None, len(ds)
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    z = mean / se if se > 0 else float("nan")
    return mean, se, z, len(ds)


def test_paired_stats_matches_the_eval_fair_puct_convention():
    rng = random.Random(20260817)
    for n in (2, 3, 17, 400):
        ds = [rng.gauss(0.3, 4.0) for _ in range(n)]
        assert S2.paired_stats(ds) == _reference_paired(ds)


def test_paired_stats_degenerate_cases_match_paired_z_exactly():
    # below two decks -> `_paired_z` returns (None, None, 0); ours mirrors it
    assert S2.paired_stats([]) == (None, None, None, 0)
    assert S2.paired_stats([1.0]) == (None, None, None, 1)
    # se == 0 -> `_paired_z` returns NaN, NOT an infinite z
    m, se, z, n = S2.paired_stats([2.0, 2.0, 2.0])
    assert (m, se, n) == (2.0, 0.0, 3) and z != z


def test_the_paired_z_source_still_carries_this_convention():
    """Guard against upstream drift: if `_paired_z` changes, `z_D` silently stops
    being comparable to `z_arb`/`z_rnd` and this file must fail."""
    src = (REPO / "scripts/classical_search/eval_fair_puct.py").read_text()
    body = src.split("def _paired_z(results):", 1)[1].split("\ndef ", 1)[0]
    assert "(v[0] + v[1]) / 2.0" in body            # seat-balanced per deck
    assert "/ (len(ds) - 1)" in body                # ddof = 1
    assert "math.sqrt(var / len(ds))" in body       # se
    assert 'z = mean / se if se > 0 else float("nan")' in body
    assert "return None, None, 0" in body           # below two decks


def test_per_deck_balanced_drops_a_half_played_deck():
    recs = [{"seed": 1, "a_seat": 0, "diff": 4}, {"seed": 1, "a_seat": 1, "diff": -2},
            {"seed": 2, "a_seat": 0, "diff": 9}]           # deck 2 is half-played
    assert S2.per_deck_balanced(recs) == {1: 1.0}


def test_D_is_deck_paired_not_a_difference_of_means():
    """READ_RULE §2: `D` = M_arb − M_rnd DECK-PAIRED over n_common. The per-deck
    difference is taken FIRST -- that is the whole point of sharing the decks."""
    arb = {1: 5.0, 2: -3.0, 3: 1.0, 9: 100.0}     # deck 9 is ARB-only
    rnd = {1: 4.0, 2: -5.0, 3: 0.0, 8: -100.0}    # deck 8 is RND-only
    d = S2.deck_paired_D(arb, rnd)
    assert d["n_common"] == 3 and d["n_common_decks"] == 3
    assert d["deck_seed_min"] == 1 and d["deck_seed_max"] == 3
    exp = _reference_paired([1.0, 2.0, 1.0])
    assert (d["D"], d["se_D"], d["z_D"]) == (exp[0], exp[1], exp[2])
    # the uncommon decks are excluded from BOTH restricted means
    assert d["M_arb_on_common"] == pytest.approx(1.0)
    assert d["M_rnd_on_common"] == pytest.approx(-1.0 / 3.0)


def test_D_below_two_common_decks_is_absent_and_therefore_G_STAT():
    d = S2.deck_paired_D({1: 1.0}, {1: 0.0})
    assert d["D"] is None and d["z_D"] is None and d["n_common"] == 1
    ok, det = S2.gate_stat(3.0, 0.1, d["z_D"])
    assert ok is False and det["nan_or_absent"] == ["z_D"]


def test_n_to_reach_is_the_realized_dispersion_rule_and_never_promises_on_a_null():
    assert S2.n_to_reach(400, 1.0) == 1600          # z scales as sqrt(n)
    assert S2.n_to_reach(400, 2.0) == 400
    assert S2.n_to_reach(400, 1.5) == 712           # ceil(400 * (2/1.5)^2)
    for bad in (None, NAN, 0.0, -1.7):
        assert S2.n_to_reach(400, bad) is None
    assert S2.n_to_reach(None, 1.0) is None and S2.n_to_reach(0, 1.0) is None


# =========================================================================== #
# D. THE MACHINE SWEEP -- READ_RULE §4, re-transcribed INDEPENDENTLY
# =========================================================================== #
def _pre(**over):
    d = {g: True for g in S2.ALL_GATES}
    d.update(over)
    return d


def _reference_branch(z_arb, z_rnd, z_D, D):
    """READ_RULE §4 transcribed from the TEXT, independently of the implementation.

        U-UNREADABLE  ≡  any §3 precondition fails      (pre-empts EVERYTHING)
        G-ANOMALY     ≡  z_rnd ≥ +2.0                   (pre-empts the rest)
        p ≡ C_arb ≡ z_arb ≥ +2.0
        q ≡ C_ctl ≡ D     ≥ 0
        r ≡ C_res ≡ z_D   ≥ +2.0

        G-CONFIRMED ≡ ¬A ∧ p ∧ q ∧ r
        G-DEPLOYS   ≡ ¬A ∧ p ∧ q ∧ ¬r
        G-CLOCK     ≡ ¬A ∧ p ∧ ¬q                (TOTAL in r, by §4's own note)
        G-PRESENT   ≡ ¬A ∧ ¬p ∧ ( z_arb ≥ +1.0 ∨ z_D ≥ +1.0 )
        G-FLAT      ≡ ¬A ∧ ¬p ∧ ¬( z_arb ≥ +1.0 ∨ z_D ≥ +1.0 )

    Every condition is written OUT IN FULL (no if/elif chain), so a caller can
    assert that EXACTLY ONE fires -- the exclusivity+exhaustiveness §4.1 claims.
    Returns `(fired_names, A, p, q, r, present)`.
    """
    def ge(x, bar):
        """NaN never satisfies a comparison -- §4.1's 'no branch is entered on a
        NaN comparison', re-transcribed rather than imported."""
        try:
            return bool(x == x and x >= bar)
        except TypeError:
            return False

    A = ge(z_rnd, 2.0)
    p = ge(z_arb, 2.0)
    q = ge(D, 0.0)
    r = ge(z_D, 2.0)
    present = ge(z_arb, 1.0) or ge(z_D, 1.0)
    fired = [nm for nm, cond in (
        ("G-ANOMALY", A),
        ("G-CONFIRMED", (not A) and p and q and r),
        ("G-DEPLOYS", (not A) and p and q and (not r)),
        ("G-CLOCK", (not A) and p and (not q)),
        ("G-PRESENT", (not A) and (not p) and present),
        ("G-FLAT", (not A) and (not p) and (not present)),
    ) if cond]
    return fired, A, p, q, r, present


#: every bar straddled from BELOW / AT / ABOVE, both signs, and NaN.
_ZS = (-3.0, 0.0, 0.9999, 1.0, 1.5, 1.9999, 2.0, 3.5, NAN)
#: D negative / just-negative / ZERO (the bar is inclusive) / just-positive /
#: positive / NaN.
_DS = (-2.0, -1e-9, 0.0, 1e-9, 2.0, NAN)


def test_branch_sweep_is_exclusive_exhaustive_and_matches_the_reference():
    """⭐ THE machine sweep READ_RULE §4.1 names by file. Dense grid over
    (z_arb, z_rnd, z_D, D) straddling every bar, NaN in EVERY position, and
    EXACTLY ONE branch fires on every cell."""
    n = 0
    seen = set()
    for z_arb, z_rnd, z_D, D in itertools.product(_ZS, _ZS, _ZS, _DS):
        got = S2.decide_branch(z_arb, z_rnd, z_D, D, _pre())
        fired, A, p, q, r, present = _reference_branch(z_arb, z_rnd, z_D, D)
        cell = (z_arb, z_rnd, z_D, D)
        # ⭐ EXACTLY ONE branch condition fires, on every cell, NaN included
        assert len(fired) == 1, (cell, fired)
        assert got["branch"] == fired[0], (cell, got["branch"], fired)
        assert got["p"] is p and got["q"] is q and got["r"] is r
        assert got["G_ANOMALY"] is A and got["PRESENT"] is present
        assert got["failed_preconditions"] == []
        assert got["branch"] in S2.BRANCH_TEXT
        assert got["branch_headline"] == S2.BRANCH_TEXT[got["branch"]][0]
        assert got["read"] == S2.BRANCH_TEXT[got["branch"]][1]
        seen.add(got["branch"])
        n += 1
    # pin the cell count so a shrunk grid fails LOUDLY
    assert len(_ZS) == 9 and len(_DS) == 6
    assert n == 9 * 9 * 9 * 6 == 4374
    # every non-U branch was actually exercised by the grid
    assert seen == {"G-ANOMALY", "G-CONFIRMED", "G-DEPLOYS", "G-CLOCK",
                    "G-PRESENT", "G-FLAT"}


def test_G_ANOMALY_preempts_every_other_reading():
    """§4: 'G-ANOMALY is evaluated second and pre-empts the rest, so the remaining
    five are evaluated only where z_rnd < +2.0.'"""
    n = 0
    for z_arb, z_D, D in itertools.product(_ZS, _ZS, _DS):
        for z_rnd in (2.0, 3.5, 99.0):
            got = S2.decide_branch(z_arb, z_rnd, z_D, D, _pre())
            assert got["branch"] == "G-ANOMALY", (z_arb, z_rnd, z_D, D)
            assert got["G_ANOMALY"] is True
            n += 1
        # ... and 1.9999 is BELOW the bar, so the rest of the table is live
        assert S2.decide_branch(z_arb, 1.9999, z_D, D, _pre())["branch"] != "G-ANOMALY"
    assert n == 9 * 9 * 6 * 3


def test_the_p_q_r_cube_is_exactly_partitioned_and_p_and_not_q_and_r_is_vacuous():
    """§4.1's own table, cell by cell -- plus the structural claim that
    `r ⇒ q`, so `p ∧ ¬q ∧ r` is VACUOUS, while `G-CLOCK` stays TOTAL in `r` so the
    table remains total even if that impossible cell were ever presented."""
    table = {(True, True, True): "G-CONFIRMED",
             (True, True, False): "G-DEPLOYS",
             (True, False, True): "G-CLOCK",     # the vacuous cell -- still TOTAL
             (True, False, False): "G-CLOCK"}
    seen = {}
    for p in (True, False):
        for q in (True, False):
            for r in (True, False):
                z_arb = 3.5 if p else 0.5
                D = 1.0 if q else -1.0
                z_D = 3.5 if r else 0.5
                got = S2.decide_branch(z_arb, 1.0, z_D, D, _pre())
                if p:
                    assert got["branch"] == table[(p, q, r)], (p, q, r)
                else:
                    assert got["branch"] in ("G-PRESENT", "G-FLAT")
                seen[(got["p"], got["q"], got["r"])] = got["branch"]
    assert len(seen) == 8      # every (p, q, r) cell was actually exercised


def test_r_implies_q_on_statistics_the_analyser_actually_computes():
    """READ_RULE §4: 'r ⇒ q (a z_D ≥ +2.0 requires D > 0)'. On RAW independent
    inputs the cell is representable (and the table handles it); on the statistics
    this instrument computes it cannot occur, because z_D = D / se(D) with se ≥ 0
    and `paired_stats` returns NaN -- never a finite z -- when se == 0."""
    rng = random.Random(4242)
    n_r = 0
    for _ in range(3000):
        k = rng.randint(2, 40)
        arb = {i: rng.gauss(rng.uniform(-1, 1), 3.0) for i in range(k)}
        rnd = {i: rng.gauss(0.0, 3.0) for i in range(k)}
        d = S2.deck_paired_D(arb, rnd)
        r = S2._ge(d["z_D"], 2.0)
        q = S2._ge(d["D"], 0.0)
        assert (not r) or q, d          # r => q
        if r:
            assert d["D"] > 0
            n_r += 1
    assert n_r > 50, "the random sweep never produced a resolved D -- widen it"


def test_G_PRESENT_and_G_FLAT_are_exact_negations_within_not_p():
    """§4.1: '¬p splits into G-PRESENT and its EXACT NEGATION G-FLAT.'"""
    n = 0
    for z_arb, z_D, D in itertools.product(_ZS, _ZS, _DS):
        if S2._ge(z_arb, 2.0):
            continue                      # p holds -- not this partition
        got = S2.decide_branch(z_arb, 0.0, z_D, D, _pre())
        present = S2._ge(z_arb, 1.0) or S2._ge(z_D, 1.0)
        assert got["branch"] == ("G-PRESENT" if present else "G-FLAT")
        assert got["PRESENT"] is present
        n += 1
    assert n > 0
    # and they are complementary, never both, never neither
    assert ({"G-PRESENT", "G-FLAT"} ==
            {S2.decide_branch(z, 0.0, zd, 0.0, _pre())["branch"]
             for z, zd in ((1.0, 0.0), (0.0, 0.0))})


def test_bars_are_INCLUSIVE_at_every_boundary():
    """+2.0, +1.0 and D = 0 are all `>=` -- an AT-the-bar read fires."""
    assert S2.decide_branch(2.0, 0.0, 2.0, 0.0, _pre())["branch"] == "G-CONFIRMED"
    assert S2.decide_branch(1.9999, 0.0, 2.0, 0.0, _pre())["branch"] == "G-PRESENT"
    assert S2.decide_branch(2.0, 0.0, 1.9999, 0.0, _pre())["branch"] == "G-DEPLOYS"
    assert S2.decide_branch(2.0, 0.0, 2.0, -1e-9, _pre())["branch"] == "G-CLOCK"
    assert S2.decide_branch(1.0, 0.0, 0.0, 0.0, _pre())["branch"] == "G-PRESENT"
    assert S2.decide_branch(0.9999, 0.0, 0.9999, 0.0, _pre())["branch"] == "G-FLAT"
    assert S2.decide_branch(0.0, 2.0, 0.0, 0.0, _pre())["branch"] == "G-ANOMALY"
    assert S2.decide_branch(0.0, 1.9999, 0.0, 0.0, _pre())["branch"] == "G-FLAT"


def test_nan_never_fires_a_conjunct():
    got = S2.decide_branch(NAN, NAN, NAN, NAN, _pre())
    assert got["branch"] == "G-FLAT"
    assert (got["p"], got["q"], got["r"], got["G_ANOMALY"], got["PRESENT"]) == (
        False, False, False, False, False)


def test_any_nan_z_routes_to_U_UNREADABLE_via_G_STAT_before_any_comparison():
    """§4.1: 'Any NaN in z_arb/z_rnd/z_D is caught by G-STAT in §3 BEFORE a
    comparison is taken, so no branch is entered on a NaN comparison.' Swept over
    the full grid: every NaN-bearing cell fails G-STAT and adjudicates UNREADABLE."""
    n_nan = 0
    for z_arb, z_rnd, z_D in itertools.product(_ZS + (None,), _ZS + (None,),
                                               _ZS + (None,)):
        ok, det = S2.gate_stat(z_arb, z_rnd, z_D)
        bad = [nm for nm, v in (("z_arb", z_arb), ("z_rnd", z_rnd), ("z_D", z_D))
               if v is None or (isinstance(v, float) and v != v)]
        assert ok is (not bad)
        assert det["nan_or_absent"] == bad
        if bad:
            n_nan += 1
            pre = _pre(**{"G-STAT": False})
            for D in (-1.0, 0.0, 1.0, NAN):
                got = S2.decide_branch(z_arb, z_rnd, z_D, D, pre)
                assert got["branch"] == "U-UNREADABLE"
                assert got["failed_preconditions"] == ["G-STAT"]
                assert got["p"] is None and got["q"] is None and got["r"] is None
    assert n_nan == 10 ** 3 - 8 ** 3      # 1000 cells, 512 fully finite


def test_u_unreadable_preempts_every_gate_and_every_reading():
    """§3/§4: 'U-UNREADABLE (§3) pre-empts everything' -- including G-ANOMALY and
    including a would-be G-CONFIRMED."""
    n = 0
    for gate in S2.ALL_GATES:
        for z_arb, z_rnd, z_D, D in ((3.5, 0.1, 3.5, 1.0),     # would be CONFIRMED
                                     (0.1, 9.0, 0.1, -1.0),    # would be ANOMALY
                                     (0.0, 0.0, 0.0, 0.0)):    # would be FLAT
            got = S2.decide_branch(z_arb, z_rnd, z_D, D, _pre(**{gate: False}))
            assert got["branch"] == "U-UNREADABLE"
            assert got["failed_preconditions"] == [gate]
            assert got["p"] is None and got["q"] is None and got["r"] is None
            assert got["G_ANOMALY"] is None and got["PRESENT"] is None
            assert got["read"] == S2.BRANCH_TEXT["U-UNREADABLE"][1]
            n += 1
    assert n == len(S2.ALL_GATES) * 3


def test_u_unreadable_lists_every_failed_gate():
    got = S2.decide_branch(9.0, 0.0, 9.0, 9.0,
                           _pre(**{"G-N": False, "G-FIRE": False, "G-J1": False}))
    assert got["branch"] == "U-UNREADABLE"
    assert got["failed_preconditions"] == ["G-FIRE", "G-J1", "G-N"]


def test_failed_conjuncts_names_exactly_which_one():
    got = S2.decide_branch(1.0, 0.0, 3.0, 1.0, _pre())
    assert got["failed_conjuncts"] == ["p = C_arb (z_arb >= +2.0)"]
    got = S2.decide_branch(3.0, 0.0, 1.0, -1.0, _pre())
    assert got["failed_conjuncts"] == ["q = C_ctl (D >= 0)",
                                       "r = C_res (z_D >= +2.0)"]
    assert S2.decide_branch(3.0, 0.0, 3.0, 1.0, _pre())["failed_conjuncts"] == []


# =========================================================================== #
# E. READ_RULE §3 -- each precondition, one at a time
# =========================================================================== #
def _tiearb(mode, B=16, J=4):
    return {"enabled": True, "B": B, "J": J, "mode": mode,
            "salt": "tiearb2-deploy-v1", "eps": 0.0}


def _manifest(cell, *, leaf_hash=CHAMP_HASH, tiearb=None, band=BAND, n=800,
              toolchain="1.96.0", build="carc_rs-0.1.0+abc123"):
    cfg = _tiearb(S2.MODE_BY_CELL[cell]) if tiearb is None else tiearb
    # §0.C.2: the knob resolves at manifest TOP LEVEL, like every shipped sibling.
    return {"cand_leaf_hash": leaf_hash, "cand_tiearb": cfg,
            "band_seed_start": band, "seed_start": band, "n": n, "paired": True,
            "rust_toolchain": toolchain, "carc_rs_build": build,
            "mixed_builds": False}


def _cells(*, arb_over=None, rnd_over=None, n_games=800, phi=(20.0, 20.0),
           decks=None):
    decks = decks if decks is not None else list(range(BAND, BAND + 400))
    out = {}
    for i, c in enumerate(("ARB", "RND")):
        m = _manifest(c)
        m.update((arb_over if c == "ARB" else rnd_over) or {})
        out[c] = {"cell": c, "manifest": m, "n_games": n_games, "phi": phi[i],
                  "deck_seeds": list(decks)}
    return out


def _preflight(host, *, pos=True, neg=True, allpass=True,
               toolchain="1.96.0", build="carc_rs-0.1.0+abc123"):
    return {"kind": "tiearb2_stage2_preflight", "host": host,
            "all_preflight_pass": allpass, "first_on_host": True,
            "two_sided": {"pick_changed": pos,
                          "root_leaf_value_bits_unchanged": neg},
            "rust_toolchain": toolchain, "carc_rs_build": build,
            "_path": f"PREFLIGHT_tiearb2_{host}_FIRST.json"}


def _band_claim(band=BAND, claimed=True):
    return {"band": band, "claimed_before_game_1": claimed,
            "decision_influenced": "pending"}


def _all_pre(**kw):
    """The all-green world -- every §3 gate passes."""
    cells = kw.pop("cells", None) or _cells()
    pf = kw.pop("preflights", None)
    pf = pf if pf is not None else [_preflight("local"), _preflight("laptop")]
    return S2.evaluate_preconditions(
        cells, pf, kw.pop("band_claim", None) or _band_claim(),
        kw.pop("expect_hosts", ("local", "laptop")),
        kw.pop("n_common", 400), kw.pop("z_arb", 1.0), kw.pop("z_rnd", 0.5),
        kw.pop("z_D", 0.7))


def test_the_all_green_world_passes_every_gate():
    pre, _ = _all_pre()
    assert pre == {g: True for g in S2.ALL_GATES}
    assert S2.decide_branch(1.0, 0.5, 0.7, 0.1, pre)["branch"] == "G-PRESENT"


@pytest.mark.parametrize("cell", ["ARB", "RND"])
def test_G_J1_is_an_INVERTED_gate_a_DIFFERENT_hash_aborts(cell):
    """§3 G-J1: 'a difference is an ABORT, not a finding.'"""
    over = {"cand_leaf_hash": "deadbeefdeadbeef"}
    pre, det = _all_pre(cells=_cells(**{f"{cell.lower()}_over": over}))
    assert pre["G-J1"] is False
    assert det["G-J1"]["expected_equal"] == CHAMP_HASH
    assert det["G-J1"]["observed"][cell] == "deadbeefdeadbeef"
    assert all(v for k, v in pre.items() if k != "G-J1")
    got = S2.decide_branch(9.0, 0.0, 9.0, 9.0, pre)
    assert got["branch"] == "U-UNREADABLE" and got["failed_preconditions"] == ["G-J1"]


@pytest.mark.parametrize("cell", ["ARB", "RND"])
@pytest.mark.parametrize("bad", [
    {"cand_tiearb": None},                     # absent / unresolved
    {"cand_tiearb": "argmax"},                 # not a resolved dict
    {"cand_tiearb": _tiearb("argmax", B=8)},   # wrong B
    {"cand_tiearb": _tiearb("argmax", J=2)},   # wrong J
])
def test_G_J4_absent_unresolved_or_wrong_B_or_J(cell, bad):
    pre, det = _all_pre(cells=_cells(**{f"{cell.lower()}_over": bad}))
    assert pre["G-J4"] is False
    assert det["G-J4"][cell]["ok"] is False
    assert all(v for k, v in pre.items() if k != "G-J4")


def test_G_J4_a_manifest_carrying_the_knob_NOWHERE_aborts():
    cells = _cells()
    cells["ARB"]["manifest"].pop("cand_tiearb")
    pre, det = _all_pre(cells=cells)
    assert pre["G-J4"] is False
    assert det["G-J4"]["ARB"]["resolved_at"] is None
    assert det["G-J4"]["ARB"]["cand_tiearb"] is None


def test_G_J4_mode_must_be_argmax_for_ARB_and_random_for_RND():
    """A swapped pair is the failure that would grade the CONTROL as the candidate."""
    swapped = _cells(arb_over={"cand_tiearb": _tiearb("random")},
                     rnd_over={"cand_tiearb": _tiearb("argmax")})
    pre, det = _all_pre(cells=swapped)
    assert pre["G-J4"] is False
    assert det["G-J4"]["ARB"]["expected_mode"] == "argmax"
    assert det["G-J4"]["RND"]["expected_mode"] == "random"
    assert det["G-J4"]["ARB"]["ok"] is False and det["G-J4"]["RND"]["ok"] is False


def test_G_J4_reads_TOP_LEVEL_by_default_and_REPORTS_where_it_found_it():
    """§0.C.2: the knob is top-level `cand_tiearb`, matching every shipped sibling
    (`eval_fair_puct.py:3945`). The pre-amendment `config.cand_tiearb` spelling is
    still ACCEPTED and the read-out says which it found -- so the knob is never
    taken from an unnamed place silently."""
    _, det = _all_pre(cells=_cells())
    assert det["G-J4"]["ARB"]["resolved_at"] == "cand_tiearb"      # the amended name
    legacy = _cells()
    for c in ("ARB", "RND"):
        legacy[c]["manifest"].pop("cand_tiearb")
        legacy[c]["manifest"]["config"] = {"cand_tiearb": _tiearb(S2.MODE_BY_CELL[c])}
    pre, det2 = _all_pre(cells=legacy)
    assert pre["G-J4"] is True
    assert det2["G-J4"]["ARB"]["resolved_at"] == "config.cand_tiearb"
    # ... and the legacy spelling is still GATED, not merely tolerated
    legacy["RND"]["manifest"]["config"] = {"cand_tiearb": _tiearb("argmax")}
    pre, _ = _all_pre(cells=legacy)
    assert pre["G-J4"] is False


@pytest.mark.parametrize("side", ["pos", "neg"])
def test_G_J13_either_side_of_the_two_sided_control_failing_voids(side):
    """§3 G-J13: the arbiter must CHANGE THE PICK **and** leave
    `root_leaf_value_bits` UNCHANGED -- on EACH host, before that host's game 1."""
    pf = [_preflight("local", **{side: False}), _preflight("laptop")]
    pre, det = _all_pre(preflights=pf)
    assert pre["G-J13"] is False
    assert det["G-J13"]["hosts"]["local"]["ok"] is False
    assert det["G-J13"]["hosts"]["laptop"]["ok"] is True
    assert all(v for k, v in pre.items() if k != "G-J13")


def test_G_J13_fails_closed_on_a_missing_host_a_missing_file_or_an_absent_witness():
    # a host that played but has no pre-flight
    pre, det = _all_pre(preflights=[_preflight("local")])
    assert pre["G-J13"] is False and det["G-J13"]["missing_hosts"] == ["laptop"]
    # no pre-flight at all
    pre, _ = _all_pre(preflights=[])
    assert pre["G-J13"] is False
    # a file that carries neither witness -> ABSENT, never coerced to True
    doc = _preflight("local")
    doc.pop("two_sided")
    pre, det = _all_pre(preflights=[doc, _preflight("laptop")])
    assert pre["G-J13"] is False
    assert det["G-J13"]["hosts"]["local"]["pick_changed"] is None
    # all_preflight_pass False alone is enough
    pre, _ = _all_pre(preflights=[_preflight("local", allpass=False),
                                  _preflight("laptop")])
    assert pre["G-J13"] is False


def test_G_J13_reads_the_witness_off_the_checks_list_too():
    doc = _preflight("local")
    doc.pop("two_sided")
    doc["checks"] = [{"check": "P1_arbiter_pick_change", "ok": True},
                     {"check": "P2_root_leaf_value_bits_unchanged", "ok": True}]
    pre, det = _all_pre(preflights=[doc, _preflight("laptop")])
    assert pre["G-J13"] is True
    assert det["G-J13"]["hosts"]["local"]["pick_changed"] is True


@pytest.mark.parametrize("phi", [(0.9999, 20.0), (20.0, 0.9999), (0.0, 0.0),
                                 (None, 20.0), (20.0, None), (NAN, 20.0)])
def test_G_FIRE_floor_is_1_0_in_EITHER_cell_and_an_absent_phi_fails_closed(phi):
    """§3 G-FIRE / DESIGN §3: 'a cell that never fires grades a
    champion-vs-champion null wearing the shape of a real cell.'"""
    pre, det = _all_pre(cells=_cells(phi=phi))
    assert pre["G-FIRE"] is False
    assert det["G-FIRE"]["floor"] == 1.0 and det["G-FIRE"]["prior"] == 22.96
    assert all(v for k, v in pre.items() if k != "G-FIRE")


def test_G_FIRE_passes_AT_the_floor_and_phi_is_otherwise_never_a_branch_input():
    pre, _ = _all_pre(cells=_cells(phi=(1.0, 1.0)))
    assert pre["G-FIRE"] is True
    # a phi far below the prior is REPORTED, not a gate
    pre, _ = _all_pre(cells=_cells(phi=(1.5, 2.0)))
    assert pre == {g: True for g in S2.ALL_GATES}


def test_G_BAND_unclaimed_wrong_band_or_a_different_deck_range():
    pre, det = _all_pre(band_claim=_band_claim(claimed=False))
    assert pre["G-BAND"] is False and det["G-BAND"]["claimed_before_game_1"] is False
    pre, _ = _all_pre(band_claim=_band_claim(band=88000000000))
    assert pre["G-BAND"] is False
    pre, det = _all_pre(cells=_cells(rnd_over={"band_seed_start": 88000000000,
                                               "seed_start": 88000000000}))
    assert pre["G-BAND"] is False
    assert det["G-BAND"]["same_launch_deck_range"] is False
    # same band, DIFFERENT n -> not the same decks
    pre, _ = _all_pre(cells=_cells(rnd_over={"n": 400}))
    assert pre["G-BAND"] is False


@pytest.mark.parametrize("n_common,n_games,fails", [
    (320, 800, False),      # AT the amended deck floor -> passes
    (319, 800, True),       # n_common < 320
    (320, 640, False),      # AT both floors -> passes (640 games IS 320 decks)
    (320, 639, True),       # a cell short of 640 of its 800
    (None, 800, True),
    (320, None, True),
])
def test_G_N_at_its_two_thresholds(n_common, n_games, fails):
    """§3 G-N AS AMENDED (§0.B): 'n_common < 320 decks, OR either cell completed
    fewer than 640 of its 800 paired games.' Both clauses are the same 80% bar."""
    pre, det = _all_pre(cells=_cells(n_games=n_games), n_common=n_common)
    assert pre["G-N"] is (not fails)
    assert det["G-N"]["n_common_floor"] == 320
    assert det["G-N"]["cell_games_floor"] == 640
    assert det["G-N"]["n_common_units"] == "DECKS (READ_RULE §2)"
    assert det["G-N"]["read_rule_amendment"] == S2.READ_RULE_AMENDMENT


def test_G_N_is_short_on_ONE_cell_only_and_still_voids():
    cells = _cells()
    cells["RND"]["n_games"] = 500
    pre, _ = _all_pre(cells=cells, n_common=320)
    assert pre["G-N"] is False


def test_G_N_PASSES_on_a_COMPLETE_run_which_is_what_the_pre_amendment_text_broke():
    """⭐ THE case the committed text at `b2faa238` could not express. A perfectly
    complete cell -- 800/800 games and all 400/400 decks common -- must PASS G-N.
    Under the old 600-DECK floor it FAILED, so the read-rule could only ever return
    U-UNREADABLE. This is the regression test for the amendment."""
    pre, _ = _all_pre(cells=_cells(n_games=800), n_common=400)
    assert pre["G-N"] is True
    assert pre == {g: True for g in S2.ALL_GATES}       # nothing else broke either
    # 400 decks is the CEILING for a paired n=800 cell (eval_fair_puct.py:3924),
    # so the pre-amendment 600 was unreachable by construction.
    assert 400 == 800 // 2
    assert S2.N_COMMON_FLOOR <= 400


def test_G_N_deck_clause_stays_INDEPENDENTLY_BINDING():
    """§0.B: 'two cells could each complete >= 640 games while overlapping on fewer
    than 320 COMMON decks, which would silently weaken D.' That must still void."""
    pre, det = _all_pre(cells=_cells(n_games=800), n_common=319)
    assert pre["G-N"] is False
    assert det["G-N"]["n_games"] == {"ARB": 800, "RND": 800}   # both cells COMPLETE
    assert det["G-N"]["n_common"] == 319                       # yet the overlap is short
    assert "independently_binding" in " ".join(det["G-N"])


def test_the_amendment_moved_no_adjudicating_bar_and_no_branch_condition():
    """⚠️ GOVERNANCE, and it now covers TWO amendments. §0.A-C amended a
    PRECONDITION and two report-only spellings; §0.D waived a rider that was never
    a branch input. Both were written to leave §4 BYTE-IDENTICAL -- the overrides
    live in §0 -- so this proof runs against the ORIGINAL text at `b2faa238` and
    must still pass."""
    import subprocess
    old = subprocess.run(
        ["git", "show", "b2faa238:measurement/tiearb2_stage2_20260817/READ_RULE.md"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout
    new = (REPO / "measurement/tiearb2_stage2_20260817/READ_RULE.md").read_text()

    # §4 -- byte-identical across BOTH amendments, on either natural boundary.
    def _conds(doc):        # the branch CONDITIONS alone
        return doc.split("## 4. Branches", 1)[1].split("### 4.1", 1)[0]

    def _whole(doc):        # §4 entire, incl. 4.1 exclusivity / 4.2 N4 / 4.3 companion
        return doc.split("## 4. Branches", 1)[1].split("## 5.", 1)[0]

    assert _conds(old) == _conds(new), "§4's branch conditions MOVED -- not an amendment"
    assert _whole(old) == _whole(new), "§4 MOVED somewhere below the table"
    # lengths pinned so a byte drift is loud rather than silently re-equal
    assert len(_conds(new).encode()) == 4965
    assert len(_whole(new).encode()) == 8206
    # §0.D is present, and it is an OVERRIDE rather than an edit
    assert "0.D" in new and "a81b8c72" in S2.READ_RULE_AMENDMENT
    # ⭐ the structural reason the waiver cannot move a branch: `ms_ratio` appears
    # in no CONDITION -- not in the p/q/r definitions, and not in the condition
    # COLUMN of the branch table. It appears only in READ text (what to REPORT) and
    # in §4.2 below the table. That is what "never a branch input" means textually.
    # both fenced blocks: G-ANOMALY, then the p / q / r definitions
    defs = "\n".join(_conds(new).split("```")[1::2])
    assert "ms_ratio" not in defs
    assert "z_arb" in defs and "z_rnd" in defs and "z_D" in defs and "D ≥ 0" in defs
    conditions = [ln.split("|")[2] for ln in _conds(new).splitlines()
                  if ln.startswith("|") and len(ln.split("|")) > 3]
    assert len(conditions) >= 7                        # header, separator, 6 branches
    for col in conditions:
        assert "ms_ratio" not in col, col
    # ... while it IS present in the read text and in §4.2, which is where §0.D bites
    assert "ms_ratio" in _conds(new)                   # in READ text only
    assert "ms_ratio" in _whole(new)
    # the adjudicating bars are unchanged in the instrument
    assert (S2.Z_BAR, S2.Z_PRESENT_BAR, S2.MS_RATIO_BAR) == (2.0, 1.0, 1.20)
    # ... and the amendment is STAMPED, so a reader knows which text was adjudicated
    assert "6c281f9e" in S2.READ_RULE_AMENDMENT
    assert "NO ADJUDICATING BAR MOVED" in S2.AMENDMENT_NOTE.upper()
    # §0.C.1: +1.0 selects a LABEL, never a permission
    assert "NOT an adjudicating bar" in S2.Z_PRESENT_BAR_NOTE
    # the two branches +1.0 separates are ALIKE NON-LICENSING -- neither text
    # licenses anything, while the two that +2.0 gates both do.
    for br in ("G-PRESENT", "G-FLAT"):
        assert "LICENSES" not in " ".join(S2.BRANCH_TEXT[br]).upper(), br
    for br in ("G-CONFIRMED", "G-DEPLOYS"):
        assert "LICENSES" in " ".join(S2.BRANCH_TEXT[br]).upper(), br


def test_G_TOOL_mixed_or_absent_builds():
    pre, det = _all_pre(cells=_cells(rnd_over={"carc_rs_build": "carc_rs-0.1.0+OTHER"}))
    assert pre["G-TOOL"] is False and det["G-TOOL"]["distinct_builds"] == 2
    pre, _ = _all_pre(cells=_cells(rnd_over={"rust_toolchain": "1.95.0"}))
    assert pre["G-TOOL"] is False
    pre, _ = _all_pre(cells=_cells(arb_over={"mixed_builds": True}))
    assert pre["G-TOOL"] is False
    pre, _ = _all_pre(cells=_cells(arb_over={"rust_toolchain": None}))
    assert pre["G-TOOL"] is False
    # a host that ran a different wheel is a mixed build too
    pre, _ = _all_pre(preflights=[_preflight("local"),
                                  _preflight("laptop", build="carc_rs-0.1.0+OTHER")])
    assert pre["G-TOOL"] is False


def test_G_TOOL_refuses_the_harness_provenance_FAILURE_SENTINEL():
    """⚠️ `eval_fair_puct` writes `carc_rs_build = "<unavailable: ...>"` and
    `mixed_builds = None` when its provenance block RAISES (~line 4498). A pure
    equality gate PASSES that: both cells carry the SAME sentinel, so it reads as
    one distinct build. Unknown provenance is not agreement -- it must FAIL."""
    for over in ({"carc_rs_build": "<unavailable: ImportError>"},
                 {"rust_toolchain": ""},
                 {"mixed_builds": None}):          # provenance RAISED, not clean
        pre, _ = _all_pre(cells=_cells(arb_over=over, rnd_over=dict(over)))
        assert pre["G-TOOL"] is False, over
    # the same sentinel on a PREFLIGHT is refused too
    pre, _ = _all_pre(preflights=[_preflight("local", build="<unavailable: OSError>"),
                                  _preflight("laptop", build="<unavailable: OSError>")])
    assert pre["G-TOOL"] is False


def test_G_TOOL_names_the_WEAK_build_witness_when_only_the_cargo_version_exists():
    """`carc_rs_version` is the CARGO version and does not move between builds --
    it cannot tell a fresh wheel from a stale one. It is accepted as a fallback and
    REPORTED as weak, never silently treated as the content hash."""
    cells = _cells()
    for c in ("ARB", "RND"):
        cells[c]["manifest"].pop("carc_rs_build")
        cells[c]["manifest"]["carc_rs_version"] = "0.1.0"
    pf = []
    for h in ("local", "laptop"):
        d = _preflight(h)
        d.pop("carc_rs_build")
        d["carc_rs_version"] = "0.1.0"
        pf.append(d)
    pre, det = _all_pre(cells=cells, preflights=pf)
    assert pre["G-TOOL"] is True
    assert "WEAK" in det["G-TOOL"]["stamps"]["ARB"]["build_witness"]
    # ... whereas the content hash is named as the witness of record
    _, det2 = _all_pre(cells=_cells())
    assert "content hash" in det2["G-TOOL"]["stamps"]["ARB"]["build_witness"]


@pytest.mark.parametrize("zs", [(NAN, 0.5, 0.7), (1.0, NAN, 0.7), (1.0, 0.5, NAN),
                                (None, 0.5, 0.7), (1.0, None, 0.7), (1.0, 0.5, None)])
def test_G_STAT_fires_on_a_NaN_or_absent_z_in_any_position(zs):
    pre, det = _all_pre(z_arb=zs[0], z_rnd=zs[1], z_D=zs[2])
    assert pre["G-STAT"] is False
    assert len(det["G-STAT"]["nan_or_absent"]) == 1
    assert all(v for k, v in pre.items() if k != "G-STAT")


def test_every_gate_is_individually_sufficient_to_void_the_run():
    """Each §3 precondition, alone, pre-empts every other branch."""
    breakers = {
        "G-J1": dict(cells=_cells(arb_over={"cand_leaf_hash": "0" * 16})),
        "G-J4": dict(cells=_cells(arb_over={"cand_tiearb": None})),
        "G-J13": dict(preflights=[_preflight("local", pos=False),
                                  _preflight("laptop")]),
        "G-FIRE": dict(cells=_cells(phi=(0.5, 20.0))),
        "G-BAND": dict(band_claim=_band_claim(claimed=False)),
        "G-N": dict(n_common=319),
        "G-TOOL": dict(cells=_cells(rnd_over={"rust_toolchain": "1.0.0"})),
        "G-STAT": dict(z_D=NAN),
    }
    assert set(breakers) == set(S2.ALL_GATES)
    for gate, kw in breakers.items():
        pre, _ = _all_pre(**kw)
        assert pre[gate] is False, gate
        assert [k for k, v in pre.items() if not v] == [gate], gate
        # a would-be G-CONFIRMED read is pre-empted anyway
        got = S2.decide_branch(9.0, 0.0, 9.0, 9.0, pre)
        assert got["branch"] == "U-UNREADABLE" and got["failed_preconditions"] == [gate]


# =========================================================================== #
# F. §4.2 -- the N4 cost rider: a DOWNGRADE trigger, NEVER a branch input
# =========================================================================== #
def test_N4_fires_strictly_ABOVE_1_20_and_names_the_field_name_trap():
    """⚠️ `N4_FIRED` is the MEASUREMENT and §0.D did not waive it — it is still
    computed and reported exactly as before. Only the CONSEQUENCE is waived."""
    assert S2.cost_rider(1.20, 1.20)["N4_FIRED"] is False        # AT the bar: no
    assert S2.cost_rider(1.2000001, 1.0)["N4_FIRED"] is True
    assert S2.cost_rider(1.0, 1.21)["N4_FIRED"] is True
    assert S2.cost_rider(NAN, NAN)["N4_FIRED"] is False
    assert S2.cost_rider(None, None)["N4_FIRED"] is False
    assert S2.cost_rider(1.05, 1.0)["cost_neutral"] is True
    assert S2.cost_rider(1.06, 1.0)["cost_neutral"] is False
    trap = S2.cost_rider(1.0, 1.0)["field_name_trap"]
    assert "champ_prefix_ms_per_move` IS THE CANDIDATE SIDE" in trap
    assert "2361/2371/2389" in trap
    assert S2.cost_rider(1.0, 1.0)["expected_from_design_5"] == 1.1985


def _same(x, y):
    """Equality with NaN == NaN, so a NaN `ms_ratio` does not read as a difference."""
    if isinstance(x, float) and isinstance(y, float) and x != x and y != y:
        return True
    if isinstance(x, dict) and isinstance(y, dict):
        return set(x) == set(y) and all(_same(x[k], y[k]) for k in x)
    return x == y


def test_the_0_D_waiver_suppresses_the_CONSEQUENCE_and_nothing_else():
    """READ_RULE §0.D (OWNER RULING, commit a81b8c72): the §4.2 downgrade is waived
    for this cell. The measurement, the trap, the prediction-vs-realized comparison
    and the cost-neutral annotation all survive."""
    on = S2.cost_rider(5.0, 5.0, waived=True)        # the ruling (the default)
    off = S2.cost_rider(5.0, 5.0, waived=False)
    assert S2.cost_rider(5.0, 5.0)["downgrade_waived"] is True      # DEFAULTS to it
    assert on["N4_FIRED"] is off["N4_FIRED"] is True               # still measured
    assert on["cost_confounded"] is False and off["cost_confounded"] is True
    assert on["n4_downgrade_waived_by"] == S2.N4_WAIVER_BY
    assert "a81b8c72" in on["n4_downgrade_waived_by"]
    assert off["n4_downgrade_waived_by"] is None
    assert on["owner_ruling_verbatim"] == S2.N4_WAIVER_OWNER_VERBATIM
    # the measurement-side payload is IDENTICAL under the waiver
    for k in ("ms_ratio_arb", "ms_ratio_rnd", "bar", "neutral_bar",
              "expected_from_design_5", "prediction_vs_realized", "N4_FIRED",
              "cost_neutral", "field_name_trap", "rider", "ms_ratio_missing"):
        assert _same(on[k], off[k]), k


def test_the_owner_ruling_is_carried_verbatim_from_the_READ_RULE():
    doc = (REPO / "measurement/tiearb2_stage2_20260817/READ_RULE.md").read_text()
    assert S2.N4_WAIVER_OWNER_VERBATIM.split(". ")[0] in doc.replace("\n", " ")
    # the anti-gaming clause is binding and must travel with the waiver
    note = S2.N4_WAIVER_NOTE
    assert "ANTI-GAMING" in note
    assert "B stays 16" in note and "not narrowed" in note and "truncation" in note
    assert "rho_phone is NOT reopened" in note
    # WAIVED the consequence, NOT the measurement -- said in so many words
    assert "WAIVED: the consequence" in note and "NOT WAIVED: the measurement" in note


def test_prediction_vs_realized_is_a_first_class_field_not_a_footnote():
    c = S2.cost_rider(1.30, 1.10)
    pvr = c["prediction_vs_realized"]
    assert pvr["predicted"] == 1.1985
    assert pvr["realized"] == {"ARB": 1.30, "RND": 1.10}
    assert pvr["delta"]["ARB"] == pytest.approx(1.30 - 1.1985)
    assert pvr["delta"]["RND"] == pytest.approx(1.10 - 1.1985)
    assert "cost model" in pvr["why"]
    # ... and it survives an absent reading rather than crashing
    assert S2.cost_rider(None, NAN)["prediction_vs_realized"]["delta"] == {
        "ARB": None, "RND": None}


def test_an_ABSENT_ms_ratio_is_still_a_DEFECT_because_only_the_consequence_was_waived():
    """§4.3(4) makes the measurement mandatory on EVERY branch; §0.D waived the
    consequence. So a cell that reports no cost is a defect in the read-out."""
    assert S2.cost_rider(1.0, 1.0)["MEASUREMENT_DEFECT"] is False
    for bad in ((None, 1.0), (1.0, NAN), (None, None)):
        c = S2.cost_rider(*bad)
        assert c["MEASUREMENT_DEFECT"] is True
        assert c["ms_ratio_missing"]
    assert S2.cost_rider(None, 1.0)["ms_ratio_missing"] == ["ARB"]
    assert S2.cost_rider(1.0, NAN)["ms_ratio_missing"] == ["RND"]


def test_the_waiver_changes_NO_branch_on_a_grid_straddling_both_cost_bars():
    """⭐ THE MECHANICAL STATEMENT OF §0.D's structural claim: 'waiving a rider that
    was never a branch input cannot change which branch fires on any read.'

    For every (branch-input, ms_ratio) pair the branch is IDENTICAL with the waiver
    on and off -- only the annotation differs. `decide_branch` is not even handed
    `ms_ratio`, so this is belt-and-braces on top of
    `test_N4_is_never_a_branch_input`, which pins that structurally."""
    ratios = (0.5, 1.0, 1.05, 1.0500001, 1.1985, 1.20, 1.2000001, 1.5, 5.0, NAN, None)
    n = 0
    differed_on_annotation = 0
    for z_arb, z_rnd, z_D, D in itertools.product(_ZS, _ZS, _ZS, _DS):
        branch = S2.decide_branch(z_arb, z_rnd, z_D, D, _pre())["branch"]
        for m_arb in ratios:
            for m_rnd in (1.0, 5.0):
                on = S2.cost_rider(m_arb, m_rnd, waived=True)
                off = S2.cost_rider(m_arb, m_rnd, waived=False)
                # the branch does not move -- not with the waiver, not without it,
                # not for any ms_ratio
                assert S2.decide_branch(z_arb, z_rnd, z_D, D,
                                        _pre())["branch"] == branch
                # ... and the ONLY field that differs is the consequence
                # (NaN-aware: a NaN ms_ratio is EQUAL to itself for this purpose)
                diffs = {k for k in on if not _same(on[k], off[k])}
                assert diffs <= {"cost_confounded", "downgrade_waived",
                                 "n4_downgrade_waived_by", "owner_ruling_verbatim",
                                 "waiver_note"}, diffs
                if "cost_confounded" in diffs:
                    differed_on_annotation += 1
                n += 1
    assert n == 4374 * len(ratios) * 2
    assert differed_on_annotation > 0, "the grid never straddled the bar"


def test_N4_is_never_a_branch_input():
    """§4.2: 'ms_ratio is a downgrade trigger, not a conjunct', and 'it does not
    touch the mechanism contrast D / z_D'. `decide_branch` cannot even see it."""
    import inspect
    src = inspect.getsource(S2.decide_branch)
    for forbidden in ("ms_ratio", "cost", "N4", "rho"):
        assert forbidden not in src, forbidden
    sig = inspect.signature(S2.decide_branch)
    assert list(sig.parameters) == ["z_arb", "z_rnd", "z_D", "D", "preconditions"]


# =========================================================================== #
# G. End to end -- synthetic cells on disk, thin IO, every §4.3 item rendered
# =========================================================================== #
def _write_cell(root, name, mode, *, n_decks=400, margin=0.0, phi=20.0,
                z_override=None, champ_ms=1200.0, rung_ms=1000.0, elo=12.0,
                seed=1, drop_last_seat=0, **man_over):
    """A synthetic cell dir: per-game records + summary.json + manifest.json."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "failed").mkdir(exist_ok=True)
    # a failure record in the SUBDIR -- it must never reach the statistics
    (d / "failed" / "seed000000000999_a0.json").write_text(json.dumps(
        {"failed": True, "seed": 999, "a_seat": 0, "exc": "boom"}))
    rng = random.Random(seed)
    recs = []
    for i in range(n_decks):
        s = BAND + i
        for a_seat in (0, 1):
            if i == n_decks - 1 and a_seat == 1 and drop_last_seat:
                continue                       # a half-played deck (partial run)
            diff = margin + rng.gauss(0.0, 6.0)
            recs.append({"seed": s, "a_seat": a_seat, "diff": diff,
                         "cand_tiearb": {"fires": phi}})
    for r in recs:
        (d / f"seed{r['seed']:012d}_a{r['a_seat']}.json").write_text(json.dumps(r))
    by_deck = S2.per_deck_balanced(recs)
    m, se, z, npair = S2.paired_stats(by_deck.values())
    summary = {"n": len(recs), "W": len(recs) // 2, "D": 0, "L": len(recs) // 2,
               "winrate": 0.51, "winrate_z": 0.8, "elo": elo, "elo_sig_1sigma": 8.5,
               "avg_diff": m, "paired_mean_margin": m,
               "paired_z": (z if z_override is None else z_override),
               "n_paired": npair, "n_failed": 1, "failure_rate": 1.0 / (len(recs) + 1),
               "champ_prefix_ms_per_move": champ_ms, "rung_ms_per_move": rung_ms,
               "opponent": "fair-champion"}
    (d / "summary.json").write_text(json.dumps(summary))
    man = _manifest(name.split("_")[0].upper() if name.upper() in ("ARB", "RND")
                    else ("ARB" if mode == "argmax" else "RND"))
    man["cand_tiearb"]["mode"] = mode
    man.update(man_over)
    (d / "manifest.json").write_text(json.dumps(man))
    return d


def _e2e_argv(root, out, *, hosts=("local", "laptop")):
    argv = ["--arb-summary", str(root / "ARB/summary.json"),
            "--arb-manifest", str(root / "ARB/manifest.json"),
            "--rnd-summary", str(root / "RND/summary.json"),
            "--rnd-manifest", str(root / "RND/manifest.json"),
            "--band-claim", str(root / "BAND_CLAIMED.json"),
            "--out-dir", str(out)]
    for h in hosts:
        argv += ["--expect-host", h]
    for h in hosts:
        argv += ["--preflight", str(root / f"PREFLIGHT_tiearb2_{h}_FIRST.json")]
    return argv


def _e2e_world(tmp_path, **kw):
    root = tmp_path / "run"
    root.mkdir(exist_ok=True)
    _write_cell(root, "ARB", "argmax", seed=1, **kw.pop("arb", {}))
    _write_cell(root, "RND", "random", seed=2, **kw.pop("rnd", {}))
    for h in kw.pop("hosts", ("local", "laptop")):
        doc = _preflight(h, **kw.pop(f"pf_{h}", {}))
        doc.pop("_path")
        (root / f"PREFLIGHT_tiearb2_{h}_FIRST.json").write_text(json.dumps(doc))
    (root / "BAND_CLAIMED.json").write_text(json.dumps(_band_claim()))
    return root


def test_end_to_end_writes_both_artefacts_and_every_4_3_item(tmp_path, capsys):
    root = _e2e_world(tmp_path)
    out = tmp_path / "out"
    assert S2.main(_e2e_argv(root, out)) == 0
    v = json.loads((out / "READOUT.json").read_text())
    md = (out / "READOUT.md").read_text()

    # ⭐ the COMMITTED shape -- 800/800 games, 400/400 common decks -- is READABLE
    # under the amended G-N. (Under the pre-amendment 600-deck floor this exact
    # fixture read U-UNREADABLE, which is the defect §0 fixed.)
    assert v["failed_preconditions"] == []
    assert v["branch"] in ("G-ANOMALY", "G-CONFIRMED", "G-DEPLOYS", "G-CLOCK",
                           "G-PRESENT", "G-FLAT")
    # the text adjudicated is stamped, and stated up top
    assert v["read_rule_amendment"] == S2.READ_RULE_AMENDMENT
    assert "6c281f9e" in md and "No adjudicating bar moved." in md

    # §4.3 (1) both cells
    for c in ("ARB", "RND"):
        b = v["cells"][c]
        assert b["n_games"] == 800 and b["n_decks_seat_balanced"] == 400
        assert b["seat_balance"]["balanced"] is True
        assert b["z"] is not None and b["M"] is not None
        assert b["elo"] is not None and b["wr"] is not None
    assert "seat balance" in md and "paired_z ⭐ PRIMARY" in md
    # §4.3 (2) D, se, z_D, and BOTH resolving-n figures
    assert v["D_block"]["n_common_decks"] == 400
    assert v["D_block"]["se_D"] is not None and v["D_block"]["z_D"] is not None
    assert "n_to_resolve_D_2sigma" in v["D_block"]
    assert "n_to_convict_z_arb_2sigma" in v
    assert "the `n` that would resolve `D` to 2σ" in md
    assert "the `n` that would convict `z_arb` at 2σ" in md
    # §4.3 (3) phi + the offline prior + BOTH §2.1 mismatches verbatim
    assert v["phi_block"]["phi_arb"] == 20.0 and v["phi_block"]["offline_prior"] == 22.96
    assert "65.98" in md and "40.4" in md
    assert S2.MISMATCH_I_VERBATIM.splitlines()[0].lstrip("*") in md.replace("> ", "")
    assert "reseeding alone flips picks" in md
    # §4.3 (4) ms_ratio both cells + the field-name trap NAMED
    assert v["cost_N4"]["ms_ratio_arb"] == pytest.approx(1.2)
    assert "IS THE CANDIDATE SIDE" in md and "2361/2371/2389" in md
    assert "1.1985" in md
    # §4.3 (5) every gate with its realized value + the J13 witness per host
    for g in S2.ALL_GATES:
        assert f"`{g}`" in md
    assert "pick_changed=True" in md and "root_leaf_value_bits_unchanged=True" in md
    assert "local" in md and "laptop" in md
    # §4.3 (6) both verbatim carries, on EVERY branch
    assert "NO CORROBORATION" in md and "511/1033" in md
    assert "both terminal-grounded" in md
    # §4.3 (7) Phase-A cost, including rho_phone NOT SOLVED
    assert "0.178232" in md and "15.3" in md and "0.6224" in md
    assert "5.52" in md and "NOT SOLVED" in md
    # §4.3 (8) band, deck range, registry
    assert str(BAND) in md and "BAND_REGISTRY.csv" in md
    assert v["band_registry"]["deck_range_common"] == [BAND, BAND + 399]
    # READ_RULE §5 -- what no branch does
    assert "PRODUCTION.yaml" in md and "read-rule is SPENT" in md
    assert capsys.readouterr().out.count("BRANCH:") >= 1


def test_end_to_end_partial_run_reports_the_realized_n_and_still_voids(tmp_path):
    """⚠️ A partial run is READ at its realized n -- and G-N still voids it."""
    root = _e2e_world(tmp_path, arb={"n_decks": 300, "drop_last_seat": 1},
                      rnd={"n_decks": 260})
    out = tmp_path / "out"
    assert S2.main(_e2e_argv(root, out)) == 0
    v = json.loads((out / "READOUT.json").read_text())
    assert v["cells"]["ARB"]["n_games"] == 599        # 300 decks, one seat dropped
    assert v["cells"]["ARB"]["n_decks_seat_balanced"] == 299
    assert v["cells"]["RND"]["n_decks_seat_balanced"] == 260
    assert v["D_block"]["n_common_decks"] == 260      # the overlap, not either cell
    assert v["D_block"]["D"] is not None              # statistics still computed
    assert v["branch"] == "U-UNREADABLE"
    assert v["failed_preconditions"] == ["G-N"]
    assert v["partial_run"]["realized_games"] == {"ARB": 599, "RND": 520}
    assert v["partial_run"]["planned_games_per_cell"] == 800
    md = (out / "READOUT.md").read_text()
    assert "Partial-run status" in md and "Nothing is extrapolated" in md


def test_end_to_end_ignores_the_failed_subdirectory(tmp_path):
    root = _e2e_world(tmp_path, arb={"n_decks": 50}, rnd={"n_decks": 50})
    recs = S2.load_records(root / "ARB")
    assert len(recs) == 100 and all(not r.get("failed") for r in recs)
    assert (root / "ARB/failed/seed000000000999_a0.json").exists()


def test_readable_branch_when_the_committed_G_N_floor_is_met(tmp_path, monkeypatch):
    """The branch machinery on a run that clears every gate, at the COMMITTED
    shape: 400 decks x 2 seats = 800 paired games per cell, all 400 common."""
    root = _e2e_world(tmp_path, arb={"n_decks": 400, "margin": 2.5},
                      rnd={"n_decks": 400, "margin": 0.0})
    out = tmp_path / "out"
    assert S2.main(_e2e_argv(root, out)) == 0
    v = json.loads((out / "READOUT.json").read_text())
    assert v["failed_preconditions"] == []
    assert v["D_block"]["n_common_decks"] == 400
    assert v["branch"] in ("G-CONFIRMED", "G-DEPLOYS", "G-CLOCK",
                           "G-PRESENT", "G-FLAT", "G-ANOMALY")
    assert v["p_q_r"]["p"] is not None
    # the cost rider fired (ms_ratio 1.20 exactly -> NOT fired; make it fire)
    assert v["cost_N4"]["N4_FIRED"] is False
    md = (out / "READOUT.md").read_text()
    assert "NO CORROBORATION" in md          # §4.3(6) on a PASSING branch too


def test_end_to_end_a_ratio_over_the_bar_is_reported_but_NOT_downgraded(tmp_path):
    """§0.D end to end: `ms_ratio` 1.50 > 1.20 is MEASURED, REPORTED, and read AT
    FACE VALUE -- the branch sentence carries no COST-CONFOUNDED prefix."""
    root = _e2e_world(tmp_path, arb={"n_decks": 400, "champ_ms": 1500.0},
                      rnd={"n_decks": 400})
    out = tmp_path / "out"
    S2.main(_e2e_argv(root, out))
    v = json.loads((out / "READOUT.json").read_text())
    md = (out / "READOUT.md").read_text()
    assert v["cost_N4"]["ms_ratio_arb"] == pytest.approx(1.5)
    assert v["cost_N4"]["N4_FIRED"] is True                  # still MEASURED
    assert v["cost_N4"]["cost_confounded"] is False          # consequence WAIVED
    assert not v["branch_headline"].startswith("[COST-CONFOUNDED")
    assert v["cost_N4"]["n4_downgrade_waived_by"] == S2.N4_WAIVER_BY
    assert "a81b8c72" in md
    assert "WAIVED" in md and "AT FACE VALUE" in md
    # the owner's words, and the binding anti-gaming clause, travel with it
    assert "dont let that be the constraint right now" in md
    assert "ANTI-GAMING" in md and "B stays 16" in md
    # ⭐ prediction vs realized is a first-class line
    assert "PREDICTION vs REALIZED" in md and "1.1985" in md
    assert "Δ +0.3015" in md                                  # 1.50 - 1.1985


def test_end_to_end_a_cost_neutral_run_says_so(tmp_path):
    """§0.D retains the <= 1.05 annotation."""
    root = _e2e_world(tmp_path, arb={"n_decks": 400, "champ_ms": 1000.0},
                      rnd={"n_decks": 400, "champ_ms": 1020.0})
    out = tmp_path / "out"
    S2.main(_e2e_argv(root, out))
    v = json.loads((out / "READOUT.json").read_text())
    assert v["cost_N4"]["cost_neutral"] is True
    assert "COST-NEUTRAL" in (out / "READOUT.md").read_text()


def test_end_to_end_an_absent_ms_ratio_is_shouted_about(tmp_path):
    """The measurement was NOT waived -- a cell with no cost number is a defect."""
    root = _e2e_world(tmp_path, arb={"n_decks": 400, "rung_ms": 0.0},
                      rnd={"n_decks": 400})
    out = tmp_path / "out"
    S2.main(_e2e_argv(root, out))
    v = json.loads((out / "READOUT.json").read_text())
    assert v["cost_N4"]["MEASUREMENT_DEFECT"] is True
    assert v["cost_N4"]["ms_ratio_missing"] == ["ARB"]
    md = (out / "READOUT.md").read_text()
    assert "DEFECT" in md and "waived the CONSEQUENCE, not the MEASUREMENT" in md


def test_G_FLAT_carries_both_mandatory_riders_and_the_scope_sentence(tmp_path):
    root = _e2e_world(tmp_path,
                      arb={"n_decks": 400, "margin": 0.0, "z_override": 0.2,
                           "elo": 1.0},
                      rnd={"n_decks": 400, "margin": 0.0, "z_override": 0.1})
    out = tmp_path / "out"
    S2.main(_e2e_argv(root, out))
    v = json.loads((out / "READOUT.json").read_text())
    md = (out / "READOUT.md").read_text()
    if v["branch"] != "G-FLAT":
        pytest.skip(f"fixture drew {v['branch']}; the rider contract is asserted below")
    g = v["g_flat_riders"]
    assert g["scope_sentence"] == S2.G_FLAT_SCOPE_SENTENCE
    assert "BOUNDED null, not an exclusion" in md
    assert "+18.09" in md or "18.09" in md
    assert g["tension_rider"] == S2.G_FLAT_TENSION_RIDER
    assert "TENSION WITH A PUBLISHED RESULT" in md
    assert "not presented as resolved" in md.replace("NOT ", "not ")
    # the rider is CONDITIONAL and must state which way it went
    assert isinstance(g["offline_ci_excluded_at_95"], bool)
    assert ("EXCLUDED at 95%" in g["offline_ci_exclusion_rider"]
            or "NOT APPLICABLE" in g["offline_ci_exclusion_rider"])


def test_G_FLAT_offline_CI_exclusion_rider_fires_only_below_6_32_elo():
    """§4's G-FLAT rider: 'if the 95% upper bound on E_arb is below +6.32 elo'."""
    assert S2._elo_95_upper({"elo": 1.0, "elo_sig_1sigma": 2.0}) == pytest.approx(4.92)
    assert S2._elo_95_upper({"elo": 1.0, "elo_sig_1sigma": 2.0}) < S2.OFFLINE_ELO_LO
    assert S2._elo_95_upper({"elo": 3.0, "elo_sig_1sigma": 2.0}) > S2.OFFLINE_ELO_LO
    assert S2._elo_95_upper({"elo": None, "elo_sig_1sigma": 2.0}) is None
    assert S2._elo_95_upper({"elo": 800.0, "elo_sig_1sigma": NAN}) is None


def test_z_arb_and_z_rnd_are_READ_off_summary_never_recomputed(tmp_path):
    """READ_RULE §2 names `summary.json::paired_z` as THE primary statistic. A
    doctored summary must drive the branch, with our recomputation kept beside it
    as a WITNESS only."""
    root = _e2e_world(tmp_path,
                      arb={"n_decks": 400, "margin": 0.0, "z_override": 9.99},
                      rnd={"n_decks": 400, "margin": 0.0})
    out = tmp_path / "out"
    S2.main(_e2e_argv(root, out))
    v = json.loads((out / "READOUT.json").read_text())
    assert v["cells"]["ARB"]["z"] == 9.99
    assert v["p_q_r"]["p"] is True
    assert v["cells"]["ARB"]["recomputed"]["z"] != 9.99      # the witness disagrees
    assert v["branch"] in ("G-CONFIRMED", "G-DEPLOYS", "G-CLOCK")


def test_ms_ratio_is_candidate_over_opponent_not_the_other_way_round(tmp_path):
    """⚠️ THE FIELD-NAME TRAP, asserted numerically: `champ_prefix_ms_per_move` is
    the CANDIDATE. A swapped ratio would read 0.833 here instead of 1.20."""
    root = _e2e_world(tmp_path, arb={"n_decks": 20, "champ_ms": 1200.0,
                                     "rung_ms": 1000.0})
    cell = S2.load_cell("ARB", root / "ARB/summary.json", root / "ARB/manifest.json")
    assert cell["ms_ratio"] == pytest.approx(1.2)
    assert cell["champ_prefix_ms_per_move"] == 1200.0     # the CANDIDATE
    assert cell["rung_ms_per_move"] == 1000.0             # the OPPONENT


def test_load_band_claim_reads_the_plain_text_house_shape_and_never_invents_one():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "BAND_CLAIMED.json"
        p.write_text(f"{BAND}\nSTAGE 2 PHASE B ...\nclaimed 2026-08-17\n")
        doc = S2.load_band_claim(p)
        assert doc["band"] == BAND and doc["claimed_before_game_1"] is True
        p.write_text(f"{BAND}\nno claim line\n")
        assert S2.load_band_claim(p)["claimed_before_game_1"] is False
        assert S2.load_band_claim(Path(td) / "nope.json")["claimed_before_game_1"] is False
        assert S2.load_band_claim(None)["band"] is None


def test_expect_host_is_required_so_the_J13_roster_is_never_inferred():
    with pytest.raises(SystemExit):
        S2.parse_args(["--arb-summary", "a", "--arb-manifest", "b",
                       "--rnd-summary", "c", "--rnd-manifest", "d"])
    a = S2.parse_args(["--arb-summary", "a", "--arb-manifest", "b",
                       "--rnd-summary", "c", "--rnd-manifest", "d",
                       "--expect-host", "local"])
    assert a.expect_host == ["local"]


# =========================================================================== #
# H. THE RUST ARBITER KNOB -- `carc_core::tiearb`, via the `carc_rs` wheel.
#
# Authored by the instrument-build session; merged here (with its own section
# numbering flattened into this file's) after the two sessions collided on this
# path. Two things are pinned, both named in the pre-registration:
#
#   1. **The predicate is the CORPUS predicate.** `carc_core::tiearb::chain_values`
#      / `detect_tie` must agree BIT-FOR-BIT with `scripts/tiletie/chain_census.py`
#      (`chain_values` at line 168, `tie_report` at line 216), which is the
#      definition of record. A drifted predicate would fire on a different
#      population than the one the offline 22.96/game funnel describes.
#   2. **The default path is byte-identical** (DESIGN §4, the surface-C
#      `root_allow` precedent). With `tiearb_enabled=False` the candidate must be
#      the champion, bit for bit, whatever the other five knobs carry.
#
# ⚠️ The wheel guard is per-test, NOT module-level: sections A-G are the artefact
# READ_RULE §4.1 names by file and must never be skipped by a missing/stale wheel.
# =========================================================================== #
SALT = "tiearb2-deploy-v1"

try:                                                        # noqa: SIM105
    import carc_rs
except Exception:                                           # pragma: no cover
    carc_rs = None

requires_rs = pytest.mark.skipif(
    carc_rs is None or not hasattr(getattr(carc_rs, "MirrorState", None),
                                   "tiearb_probe"),
    reason="carc_rs wheel absent or predates the tiearb knob")

# --------------------------------------------------------------------------- #
# 1. predicate parity with the corpus definition of record                     #
# --------------------------------------------------------------------------- #
def _py_chain_values(game, board, seat, leaf):
    """`chain_census.chain_values`, inlined (that module needs a rules-profile
    env export at import time, which a test process must not latch)."""
    import numpy as np

    out = []
    for a in (int(x) for x in np.flatnonzero(game.get_valid_moves(board))):
        s1, _ = game.get_next_state(board, a)
        if int(s1.state.current_player) == int(seat):
            legal2 = [int(x) for x in np.flatnonzero(game.get_valid_moves(s1))]
            if legal2:
                best_v, best_m = None, None
                for m in legal2:                # ascending -> lowest index wins ties
                    s2, _ = game.get_next_state(s1, m)
                    v = leaf(s2.state)
                    if best_v is None or v > best_v:
                        best_v, best_m = v, m
                out.append((a, best_v, best_m))
                continue
        out.append((a, leaf(s1.state), None))
    return out


def _py_tie_actions(values):
    """`chain_census.tie_report`'s `tie_actions_exact` (eps = 0)."""
    top1 = max(v for _a, v, _m in values)
    return sorted(int(a) for a, v, _m in values if v == top1)


@pytest.fixture(scope="module")
def _env():
    from carcassonne_ai import flat_leaf
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import leaf_config_rs
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    return Game, flat_leaf, DEFAULT_CONFIG, leaf_config_rs(DEFAULT_CONFIG)


@requires_rs
def test_chain_values_are_bit_identical_to_the_corpus_definition(_env):
    """`carc_core::tiearb::chain_values` == `chain_census.chain_values`, on the
    RAW f64 bits, at every TILE ply of a pinned game."""
    import random
    import struct

    Game, flat_leaf, cfg, rcfg = _env

    def _f(bits):
        return struct.unpack("<d", struct.pack("<Q", bits))[0]

    # `MirrorState.from_seed(s)` IS `random.seed(s); Game().get_init_board()` —
    # the deck comes off the GLOBAL rng, so the seed must be set here or the two
    # legs walk different games (and the first divergence looks like a predicate
    # bug rather than a fixture bug).
    random.seed(28000000000)
    game = Game(enable_legal_moves_cache=False)
    board = game.get_init_board()
    ms = carc_rs.MirrorState.from_seed("28000000000")
    compared = 0
    tile_plies = 0
    for ply in range(120):
        if game.get_game_ended(board, 0) != 0:
            break
        probe = ms.tiearb_probe(rcfg, -1, 4, 0.0, SALT, ply)
        if probe["phase_tiles"] and probe["n_legal"] >= 2:
            tile_plies += 1
            seat = int(board.state.current_player)
            assert probe["seat"] == seat
            bag = bool(getattr(cfg, "bag_close", False))

            def leaf(st, _s=seat, _c=cfg, _b=bag):
                return float(flat_leaf.flat_virtual_score_v2_float(st, _s, _c, _b))

            py = _py_chain_values(game, board, seat, leaf)
            rs = probe["chain_values"]
            assert [a for a, _v, _m in py] == [a for a, _v, _m in rs], f"ply {ply}"
            for (pa, pv, pm), (ra, rvbits, rm) in zip(py, rs):
                assert pa == ra
                assert float(pv).hex() == float(_f(rvbits)).hex(), (
                    f"ply {ply} action {pa}: chain value differs")
                assert pm == rm, f"ply {ply} action {pa}: meeple continuation differs"
                compared += 1
            # ...and the exact-tie predicate itself
            py_tie = _py_tie_actions(py)
            if len(py_tie) >= 2:
                assert probe.get("tie_actions") == py_tie, f"ply {ply}"
            else:
                assert not probe.get("fired"), f"ply {ply}: fired without a python tie"
        a = int(ms.legal_actions()[len(ms.legal_actions()) // 2])
        board, _ = game.get_next_state(board, a)
        ms.advance(a)
    assert tile_plies >= 20, f"only {tile_plies} tile plies compared"
    assert compared >= 200, f"only {compared} chain values compared"


@requires_rs
def test_the_trigger_fires_often_enough_to_be_worth_deploying(_env):
    """A sanity floor, NOT a measurement: the offline prior is 22.96 tied tile
    plies/game (65.98% of tile plies), so a pinned line must fire on a large
    fraction of its tile plies. This catches a predicate that silently never
    fires — the `G-FIRE` failure mode, caught in CI instead of after 800 games."""
    _Game, _fl, _cfg, rcfg = _env
    ms = carc_rs.MirrorState.from_seed("28000000000")
    tile, fired = 0, 0
    for ply in range(120):
        if ms.is_terminal():
            break
        p = ms.tiearb_probe(rcfg, -1, 4, 0.0, SALT, ply)
        if p["phase_tiles"] and p["n_legal"] >= 2:
            tile += 1
            fired += bool(p.get("fired"))
        ms.advance(ms.legal_actions()[len(ms.legal_actions()) // 2])
    assert tile >= 20
    assert fired >= 5, f"the trigger fired on {fired}/{tile} tile plies"


@requires_rs
def test_eps_zero_is_exact_equality_not_a_tolerance(_env):
    """DESIGN §2: `eps = 0`, f64 EQUALITY. A positive eps must admit strictly
    more members — proof the knob is wired and that 0 is not a stand-in."""
    _Game, _fl, _cfg, rcfg = _env
    ms = carc_rs.MirrorState.from_seed("28000000000")
    widened = 0
    for ply in range(80):
        if ms.is_terminal():
            break
        exact = ms.tiearb_probe(rcfg, -1, 4, 0.0, SALT, ply)
        loose = ms.tiearb_probe(rcfg, -1, 4, 1.0, SALT, ply)
        if exact["phase_tiles"] and exact["n_legal"] >= 2:
            e = set(exact.get("tie_actions") or [])
            l_ = set(loose.get("tie_actions") or [])
            assert e <= l_, f"ply {ply}: eps=1.0 lost a member eps=0 had"
            widened += len(l_) > len(e)
        ms.advance(ms.legal_actions()[len(ms.legal_actions()) // 2])
    assert widened > 0, "eps never widened the set — the parameter is not wired"


# --------------------------------------------------------------------------- #
# 2. the default path is byte-identical                                        #
# --------------------------------------------------------------------------- #
def _search_cfg(**kw):
    from carcassonne_ai.rust_agent import leaf_config_rs
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    return carc_rs.SearchConfigRs(leaf_config_rs(DEFAULT_CONFIG), 48, 1.5, 5.0, 15.0, **kw)


@requires_rs
def test_disabled_knob_leaves_the_repr_and_the_resolved_dict_at_the_champion():
    base = _search_cfg()
    moved = _search_cfg(tiearb_enabled=False, tiearb_b=3, tiearb_j=9,
                        tiearb_mode="random", tiearb_salt="not-the-salt", tiearb_eps=2.5)
    assert repr(base) == repr(moved), "a disabled knob leaked into the repr"
    assert "tiearb" not in repr(base)
    assert base.tiearb == {"enabled": False, "B": 16, "J": 4, "mode": "argmax",
                           "salt": SALT, "eps": 0.0}
    on = _search_cfg(tiearb_enabled=True, tiearb_b=16, tiearb_j=4, tiearb_mode="random")
    assert on.tiearb == {"enabled": True, "B": 16, "J": 4, "mode": "random",
                         "salt": SALT, "eps": 0.0}
    assert "tiearb_enabled=true" in repr(on)


@requires_rs
def test_disabled_knob_is_bit_identical_at_the_agent():
    """The dose-0 analogue: same action, same pooled floats, zero counters."""
    def agent(**kw):
        return carc_rs.FairAgentRs(_search_cfg(**kw), 4, 101, threads=1,
                                   exact_endgame=False)

    a = agent()
    b = agent(tiearb_enabled=False, tiearb_b=2, tiearb_j=8, tiearb_mode="random",
              tiearb_salt="x", tiearb_eps=7.0)
    for ag in (a, b):
        ag.start_game_from_seed("28000000000")
        for _ in range(30):
            ag.advance(ag.legal_actions()[len(ag.legal_actions()) // 2])
    x = a.choose_action()
    y = b.choose_action()
    assert x == y
    sa, sb = a.stats(), b.stats()
    assert sa["last_move"]["pooled"] == sb["last_move"]["pooled"]
    assert sb["tiearb_fired_plies"] == 0
    assert sb["tiearb_tile_plies"] == 0
    assert sb["tiearb_playouts_total"] == 0
    assert sb["tiearb_secs"] == 0.0


@requires_rs
def test_the_resolved_knob_keys_are_always_present_in_stats():
    """`G-J4` reads a RESOLVED dict; the stats keys must be present on BOTH
    cells so an ARB/RND diff is a value diff, never a shape diff."""
    ag = carc_rs.FairAgentRs(_search_cfg(), 2, 7, threads=1)
    s = ag.stats()
    for k in ("tiearb_enabled", "tiearb_b", "tiearb_j", "tiearb_mode", "tiearb_salt",
              "tiearb_eps", "tiearb_tile_plies", "tiearb_fired_plies",
              "tiearb_pickchanges", "tiearb_arms_total", "tiearb_playouts_total",
              "tiearb_secs"):
        assert k in s, k
    for k in ("tiearb_fired", "tiearb_arms", "tiearb_champ_pick", "tiearb_pickchange",
              "tiearb_playouts", "tiearb_secs"):
        assert k in s["last_move"], k


@requires_rs
def test_a_bad_mode_or_a_zero_B_is_refused_even_when_disabled():
    with pytest.raises(ValueError):
        _search_cfg(tiearb_mode="Argmax")
    with pytest.raises(ValueError):
        _search_cfg(tiearb_b=0)
    with pytest.raises(ValueError):
        _search_cfg(tiearb_j=0)
    with pytest.raises(ValueError):
        _search_cfg(tiearb_eps=-1.0)
    with pytest.raises(ValueError):
        _search_cfg(tiearb_enabled=True, tiearb_salt="")


@requires_rs
def test_the_python_search_path_refuses_an_enabled_arbiter():
    """Fail-closed: a python-backend candidate must RAISE rather than silently
    play champion-vs-champion (the J13 failure mode)."""
    import dataclasses as dc

    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.heuristic_prior_mcts import (HeuristicPriorConfig,
                                                     make_heuristic_prior_evaluator)
    cfg = dc.replace(HeuristicPriorConfig(), tiearb_enabled=True)
    assert cfg.as_manifest()["tiearb_enabled"] is True
    assert cfg.as_manifest()["tiearb_b"] == 16
    with pytest.raises(NotImplementedError):
        make_heuristic_prior_evaluator(Game(enable_legal_moves_cache=False), cfg)


@requires_rs
def test_the_config_validates_its_knobs_even_when_disabled():
    import dataclasses as dc

    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig

    for bad in (dict(tiearb_mode="ARGMAX"), dict(tiearb_b=0), dict(tiearb_j=0),
                dict(tiearb_eps=-0.5), dict(tiearb_enabled=True, tiearb_salt="")):
        with pytest.raises(ValueError):
            dc.replace(HeuristicPriorConfig(), **bad)


@requires_rs
def test_the_arms_are_deduped_by_successor_board_and_capped_at_J(_env):
    """The corpus arm construction, in order: dedupe by SUCCESSOR BOARD first,
    then cap at `J` by a seeded draw. So an all-transposition tie can never
    present 8 "different" arms that are one board — the `tiletie_pricing`
    threat-3 finding, where 2 of 5 scored E4 positions had
    `distinct_afterstates == 0` and a zero delta meant the harness did nothing
    rather than that the leaf was blind."""
    _Game, _fl, _cfg, rcfg = _env
    ms = carc_rs.MirrorState.from_seed("28000000000")
    saw_dedupe, saw_cap = False, False
    for ply in range(120):
        if ms.is_terminal():
            break
        p = ms.tiearb_probe(rcfg, -1, 4, 0.0, SALT, ply)
        if p.get("fired"):
            tie, arms = p["tie_actions"], p["arms"]
            assert len(arms) <= 4, "J = 4 with no champion pick to append"
            assert arms[0] == min(tie), "arm[0] is the leaf tie-break of record"
            assert set(arms) <= set(tie)
            assert p["n_distinct_afterstates"] <= len(tie)
            saw_dedupe |= p["n_distinct_afterstates"] < len(tie)
            saw_cap |= bool(p["capped"])
        ms.advance(ms.legal_actions()[len(ms.legal_actions()) // 2])
    assert saw_dedupe, "no transposing tie set was seen — the dedupe is untested"
    assert saw_cap, "the J cap never bit — the seeded draw is untested"


@requires_rs
def test_the_two_sided_liveness_assert_passes_on_this_box():
    """`G-J13` in CI. A cheap `B` so the suite stays fast; the per-box pre-flight
    (`measurement/tiearb2_stage2_20260817/preflight_tiearb.py`) runs the SAME
    assert at the funded `B = 16` before game 1, and the driver refuses to play
    if it fails."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts", "classical_search"))
    from tiearb_live import _assert_surface_tiearb_live

    w = _assert_surface_tiearb_live(b=4, j=4, sims=48, k_dets=2, max_fired=8)
    assert w["positive_side"]["arbiter_pick"] != w["positive_side"]["champ_pick"]
    assert w["negative_side"]["root_leaf_value_bits"] > 0
    assert w["resolved_on"]["enabled"] is True and w["resolved_off"]["enabled"] is False


# =========================================================================== #
# I. A THIRD, INDEPENDENT TRANSCRIPTION of READ_RULE §3-§4 -- authored by the
# instrument-build session, kept because two independent transcriptions that
# AGREE are stronger evidence than either alone. It is written from the document
# and imports NOTHING from the harness; it must never be used to grade a cell.
#
# ⚠️ AMENDED with the file: §0.B's deck floor (600 -> 320) is applied here too,
# and `_peer_clean`'s n_common is set to a REACHABLE 400 (a paired n = 800 cell
# tops out at 400 decks). Nothing else in it was touched.
#
# `test_the_three_transcriptions_agree_on_the_whole_grid` is the payoff.
# =========================================================================== #
#
# ⚠️ This is a transcription of `measurement/tiearb2_stage2_20260817/READ_RULE.md`
# §3-§4, written from the document and importing NOTHING from the harness. Its
# job is to prove the table is TOTAL and EXCLUSIVE, per §4.1. It must never be
# used to grade a cell.
_PEER_Z = 2.0
_PEER_PRESENT = 1.0
_PEER_N4 = 1.20


def _peer_gates(g: dict) -> str | None:
    """§3, in the document's order. Returns the failing gate id or None."""
    champ = "a36d2e15a3b3d71d"
    if g["cand_leaf_hash_arb"] != champ or g["cand_leaf_hash_rnd"] != champ:
        return "G-J1"
    for cell, mode in (("arb", "argmax"), ("rnd", "random")):
        t = g.get(f"cand_tiearb_{cell}")
        if not t or t.get("mode") != mode or t.get("B") != 16 or t.get("J") != 4:
            return "G-J4"
    if not g["j13_two_sided_per_host"]:
        return "G-J13"
    if g["phi_arb"] < 1.0 or g["phi_rnd"] < 1.0:
        return "G-FIRE"
    if not g["band_claimed_before_game1"] or not g["same_band_same_decks"]:
        return "G-BAND"
    if g["n_common"] < 320 or g["n_arb"] < 640 or g["n_rnd"] < 640:
        return "G-N"
    if not g["same_toolchain_same_build"]:
        return "G-TOOL"
    for k in ("z_arb", "z_rnd", "z_D"):
        v = g.get(k)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "G-STAT"
    return None


def _peer_branch(g: dict) -> str:
    """§3 first, then `G-ANOMALY`, then the five."""
    if _peer_gates(g) is not None:
        return "U-UNREADABLE"
    if g["z_rnd"] >= _PEER_Z:
        return "G-ANOMALY"
    p = g["z_arb"] >= _PEER_Z
    q = g["D"] >= 0
    r = g["z_D"] >= _PEER_Z
    if p and q and r:
        return "G-CONFIRMED"
    if p and q and not r:
        return "G-DEPLOYS"
    if p and not q:
        return "G-CLOCK"
    if g["z_arb"] >= _PEER_PRESENT or g["z_D"] >= _PEER_PRESENT:
        return "G-PRESENT"
    return "G-FLAT"


def _peer_clean(**over) -> dict:
    g = {
        "cand_leaf_hash_arb": "a36d2e15a3b3d71d",
        "cand_leaf_hash_rnd": "a36d2e15a3b3d71d",
        "cand_tiearb_arb": {"enabled": True, "B": 16, "J": 4, "mode": "argmax",
                            "salt": SALT, "eps": 0.0},
        "cand_tiearb_rnd": {"enabled": True, "B": 16, "J": 4, "mode": "random",
                            "salt": SALT, "eps": 0.0},
        "j13_two_sided_per_host": True,
        "phi_arb": 20.0, "phi_rnd": 20.0,
        "band_claimed_before_game1": True, "same_band_same_decks": True,
        "n_common": 400, "n_arb": 800, "n_rnd": 800,
        "same_toolchain_same_build": True,
        "z_arb": 0.0, "z_rnd": 0.0, "z_D": 0.0, "D": 0.0,
        "ms_ratio_arb": 1.1985, "ms_ratio_rnd": 1.1985,
    }
    g.update(over)
    return g


def test_every_precondition_voids_the_run():
    assert _peer_branch(_peer_clean()) != "U-UNREADABLE"
    cases = {
        "G-J1": dict(cand_leaf_hash_arb="deadbeefdeadbeef"),
        "G-J4": dict(cand_tiearb_rnd={"enabled": True, "B": 16, "J": 4,
                                      "mode": "argmax", "salt": SALT, "eps": 0.0}),
        "G-J13": dict(j13_two_sided_per_host=False),
        "G-FIRE": dict(phi_arb=0.9),
        "G-BAND": dict(same_band_same_decks=False),
        "G-N": dict(n_common=319),
        "G-TOOL": dict(same_toolchain_same_build=False),
        "G-STAT": dict(z_D=float("nan")),
    }
    for gate, over in cases.items():
        g = _peer_clean(**over)
        assert _peer_gates(g) == gate, gate
        assert _peer_branch(g) == "U-UNREADABLE", gate
    # B != 16 and J != 4 are G-J4 too, and a MISSING dict is the worst case.
    for bad in ({"enabled": True, "B": 8, "J": 4, "mode": "argmax"},
                {"enabled": True, "B": 16, "J": 2, "mode": "argmax"},
                None):
        assert _peer_gates(_peer_clean(cand_tiearb_arb=bad)) == "G-J4"
    # phi below the floor voids EITHER cell.
    assert _peer_branch(_peer_clean(phi_rnd=0.0)) == "U-UNREADABLE"


def test_the_branch_table_is_total_and_exclusive():
    """§4.1's machine sweep. Exactly one branch on every combination of the
    quantities the table reads, NaN included."""
    zs = [-3.0, -1.0, 0.0, 0.5, 1.0, 1.5, 1.99, 2.0, 3.0, float("nan")]
    ds = [-1.0, -0.001, 0.0, 0.001, 1.0]
    known = {"U-UNREADABLE", "G-ANOMALY", "G-CONFIRMED", "G-DEPLOYS", "G-CLOCK",
             "G-PRESENT", "G-FLAT"}
    seen = set()
    n = 0
    for za in zs:
        for zr in zs:
            for zd in zs:
                for d in ds:
                    b = _peer_branch(_peer_clean(z_arb=za, z_rnd=zr, z_D=zd, D=d))
                    assert b in known
                    seen.add(b)
                    n += 1
                    # a NaN anywhere in the three z's is caught by G-STAT BEFORE
                    # any comparison is taken (§4.1)
                    if any(isinstance(v, float) and math.isnan(v)
                           for v in (za, zr, zd)):
                        assert b == "U-UNREADABLE", (za, zr, zd, d)
    assert n == len(zs) ** 3 * len(ds)
    assert seen == known, sorted(known - seen)


def test_r_implies_q_so_the_p_and_not_q_and_r_cell_is_vacuous():
    """§4.1: `z_D >= +2` requires `D > 0`, so `p ∧ ¬q ∧ r` cannot occur in a
    real read; `G-CLOCK` is defined total in `r` so the table stays total."""
    # The construction is only reachable by feeding an INCONSISTENT (D, z_D):
    # the table still returns exactly one branch, and it is G-CLOCK.
    assert _peer_branch(_peer_clean(z_arb=3.0, z_rnd=0.0, D=-1.0, z_D=3.0)) == "G-CLOCK"
    assert _peer_branch(_peer_clean(z_arb=3.0, z_rnd=0.0, D=-1.0, z_D=0.0)) == "G-CLOCK"


def test_the_named_branches_read_the_way_the_document_says():
    assert _peer_branch(_peer_clean(z_arb=3.0, z_rnd=2.5, D=1.0, z_D=3.0)) == "G-ANOMALY"
    assert _peer_branch(_peer_clean(z_arb=3.0, z_rnd=0.0, D=1.0, z_D=3.0)) == "G-CONFIRMED"
    assert _peer_branch(_peer_clean(z_arb=3.0, z_rnd=0.0, D=1.0, z_D=1.5)) == "G-DEPLOYS"
    assert _peer_branch(_peer_clean(z_arb=3.0, z_rnd=0.0, D=-0.1, z_D=1.0)) == "G-CLOCK"
    assert _peer_branch(_peer_clean(z_arb=1.5, z_rnd=0.0, D=1.0, z_D=0.0)) == "G-PRESENT"
    assert _peer_branch(_peer_clean(z_arb=0.0, z_rnd=0.0, D=1.0, z_D=1.2)) == "G-PRESENT"
    assert _peer_branch(_peer_clean(z_arb=0.5, z_rnd=0.0, D=1.0, z_D=0.5)) == "G-FLAT"
    # the bars are INCLUSIVE, exactly at +2.0 / +1.0
    assert _peer_branch(_peer_clean(z_arb=2.0, z_rnd=0.0, D=0.0, z_D=2.0)) == "G-CONFIRMED"
    assert _peer_branch(_peer_clean(z_arb=1.0, z_rnd=0.0, D=1.0, z_D=0.0)) == "G-PRESENT"
    assert _peer_branch(_peer_clean(z_arb=0.999, z_rnd=0.0, D=1.0, z_D=0.999)) == "G-FLAT"


def test_the_PEER_N4_cost_rider_is_never_a_branch_input():
    """§4.2: `ms_ratio` DOWNGRADES the reading; it must move no branch."""
    for r in (0.5, 1.05, 1.1985, 1.20, 5.0):
        assert _peer_branch(_peer_clean(z_arb=3.0, z_rnd=0.0, D=1.0, z_D=3.0,
                              ms_ratio_arb=r, ms_ratio_rnd=r)) == "G-CONFIRMED"


def test_the_three_transcriptions_agree_on_the_whole_grid():
    """⭐ THE PAYOFF for keeping both transcriptions. Three independently written
    readings of READ_RULE §4 -- section D's `_reference_branch` (independent
    booleans, proving EXACTLY ONE fires), section I's `_peer_branch` (an if/elif
    chain written by the instrument-build session), and the shipped
    `S2.decide_branch` -- must return the SAME branch on every cell of the dense
    grid, NaN included. Two transcriptions agreeing is evidence; three is a
    contract.

    ⚠️ The two transcriptions differ in where they place `G-STAT`: section I runs
    §3 itself and returns `U-UNREADABLE` on a NaN z, while section D sweeps §4 with
    the gates already green. That is the READ_RULE's own routing (§4.1: a NaN is
    caught by `G-STAT` in §3 BEFORE a comparison), so the NaN cells are compared
    against `U-UNREADABLE` and the finite cells against the branch.
    """
    n_finite = n_nan = 0
    for z_arb, z_rnd, z_D, D in itertools.product(_ZS, _ZS, _ZS, _DS):
        peer = _peer_branch(_peer_clean(z_arb=z_arb, z_rnd=z_rnd, z_D=z_D, D=D))
        nan_z = [v for v in (z_arb, z_rnd, z_D) if v != v]
        if nan_z:
            # §3 routes it; section D's grid runs with the gates forced green
            assert peer == "U-UNREADABLE", (z_arb, z_rnd, z_D, D)
            gate_ok, _ = S2.gate_stat(z_arb, z_rnd, z_D)
            assert gate_ok is False
            assert S2.decide_branch(z_arb, z_rnd, z_D, D,
                                    _pre(**{"G-STAT": False}))["branch"] == (
                "U-UNREADABLE")
            n_nan += 1
            continue
        fired, *_ = _reference_branch(z_arb, z_rnd, z_D, D)
        mine = S2.decide_branch(z_arb, z_rnd, z_D, D, _pre())["branch"]
        assert len(fired) == 1
        assert fired[0] == mine == peer, (z_arb, z_rnd, z_D, D, fired, mine, peer)
        n_finite += 1
    assert n_finite == 8 ** 3 * len(_DS) == 3072
    assert n_nan == (9 ** 3 - 8 ** 3) * len(_DS) == 1302
    assert n_finite + n_nan == 4374
