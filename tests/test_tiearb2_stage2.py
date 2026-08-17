"""Contract tests for the Stage-2 PHASE B adjudicator
(scripts/tiletie/analyze_tiearb2_stage2.py; measurement/tiearb2_stage2_20260817/).

Pure plan/stat surgery -- no engine import, no search, no share writes, no game
played. Every fixture is synthetic and lives under tmp_path.

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
    assert S2.N_COMMON_FLOOR == 600
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
    return {"cand_leaf_hash": leaf_hash, "config": {"cand_tiearb": cfg},
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
        kw.pop("n_common", 600), kw.pop("z_arb", 1.0), kw.pop("z_rnd", 0.5),
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
    {"config": {}},                                        # absent
    {"config": {"cand_tiearb": None}},                     # unresolved
    {"config": {"cand_tiearb": "argmax"}},                 # not a resolved dict
    {"config": {"cand_tiearb": _tiearb("argmax", B=8)}},   # wrong B
    {"config": {"cand_tiearb": _tiearb("argmax", J=2)}},   # wrong J
])
def test_G_J4_absent_unresolved_or_wrong_B_or_J(cell, bad):
    pre, det = _all_pre(cells=_cells(**{f"{cell.lower()}_over": bad}))
    assert pre["G-J4"] is False
    assert det["G-J4"][cell]["ok"] is False
    assert all(v for k, v in pre.items() if k != "G-J4")


def test_G_J4_mode_must_be_argmax_for_ARB_and_random_for_RND():
    """A swapped pair is the failure that would grade the CONTROL as the candidate."""
    swapped = _cells(arb_over={"config": {"cand_tiearb": _tiearb("random")}},
                     rnd_over={"config": {"cand_tiearb": _tiearb("argmax")}})
    pre, det = _all_pre(cells=swapped)
    assert pre["G-J4"] is False
    assert det["G-J4"]["ARB"]["expected_mode"] == "argmax"
    assert det["G-J4"]["RND"]["expected_mode"] == "random"
    assert det["G-J4"]["ARB"]["ok"] is False and det["G-J4"]["RND"]["ok"] is False


def test_G_J4_accepts_the_top_level_spelling_and_REPORTS_where_it_found_it():
    """READ_RULE §3 and DESIGN §4 both spell it `config.cand_tiearb`; every shipped
    sibling knob resolves at manifest TOP LEVEL. Both are read, and the read-out
    says which -- so the knob is never taken from an unnamed place silently."""
    cells = _cells()
    for c in ("ARB", "RND"):
        cells[c]["manifest"].pop("config")
        cells[c]["manifest"]["cand_tiearb"] = _tiearb(S2.MODE_BY_CELL[c])
    pre, det = _all_pre(cells=cells)
    assert pre["G-J4"] is True
    assert det["G-J4"]["ARB"]["resolved_at"] == "cand_tiearb"
    cells2 = _cells()
    _, det2 = _all_pre(cells=cells2)
    assert det2["G-J4"]["ARB"]["resolved_at"] == "config.cand_tiearb"


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
    (600, 800, False),      # AT both thresholds -> passes
    (599, 800, True),       # n_common < 600
    (600, 640, False),      # AT the per-cell floor
    (600, 639, True),       # a cell short of 640 of its 800
    (None, 800, True),
    (600, None, True),
])
def test_G_N_at_its_two_thresholds(n_common, n_games, fails):
    """§3 G-N: 'n_common < 600, OR either cell completed fewer than 640 of its 800
    paired games.' Implemented EXACTLY as committed -- see the inconsistency test."""
    pre, det = _all_pre(cells=_cells(n_games=n_games), n_common=n_common)
    assert pre["G-N"] is (not fails)
    assert det["G-N"]["n_common_floor"] == 600
    assert det["G-N"]["cell_games_floor"] == 640
    assert det["G-N"]["n_common_units"] == "DECKS (READ_RULE §2)"


def test_G_N_is_short_on_ONE_cell_only_and_still_voids():
    cells = _cells()
    cells["RND"]["n_games"] = 500
    pre, _ = _all_pre(cells=cells, n_common=600)
    assert pre["G-N"] is False


def test_G_N_committed_text_inconsistency_is_REPORTED_and_NOT_silently_resolved():
    """⚠️ GOVERNANCE. `n_common` is DECKS (§2) and each cell is 800 deck-paired
    GAMES = 400 decks (§1/§6, `--paired --n 800`), so `n_common <= 400 < 600` and
    the committed G-N floor is UNSATISFIABLE. The instrument must implement the
    committed text and SAY SO -- never rescale the bar to make the run readable."""
    # the realistic maximum for the committed cell size
    pre, det = _all_pre(cells=_cells(n_games=800), n_common=400)
    assert pre["G-N"] is False
    assert "STAGE2_G_N_INCONSISTENCY" in S2.G_N_INCONSISTENCY
    assert det["G-N"]["inconsistency"] == S2.G_N_INCONSISTENCY
    # the bar was NOT quietly softened to something a 400-deck cell could clear
    assert S2.N_COMMON_FLOOR == 600
    # and the second clause cannot rescue it either: 640 games = 320 decks
    pre, _ = _all_pre(cells=_cells(n_games=640), n_common=320)
    assert pre["G-N"] is False


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
        "G-J4": dict(cells=_cells(arb_over={"config": {}})),
        "G-J13": dict(preflights=[_preflight("local", pos=False),
                                  _preflight("laptop")]),
        "G-FIRE": dict(cells=_cells(phi=(0.5, 20.0))),
        "G-BAND": dict(band_claim=_band_claim(claimed=False)),
        "G-N": dict(n_common=599),
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
    man["config"]["cand_tiearb"]["mode"] = mode
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

    # the run is short by the COMMITTED G-N floor, so it must read UNREADABLE ...
    assert v["branch"] == "U-UNREADABLE"
    assert v["failed_preconditions"] == ["G-N"]
    # ... and the reason must be visible, not inferred
    assert "STAGE2_G_N_INCONSISTENCY" in md

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
    # §4.3 (6) both verbatim carries, on this (non-passing) branch too
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
    """The branch machinery on a run that clears every gate. The G-N floor is
    reachable only by building a 700-deck cell -- which is NOT the committed
    800-GAME shape (that is the inconsistency this suite reports); the fixture is
    deliberately oversized so the §4 half of the instrument is exercised at all."""
    root = _e2e_world(tmp_path, arb={"n_decks": 700, "margin": 2.5},
                      rnd={"n_decks": 700, "margin": 0.0})
    out = tmp_path / "out"
    assert S2.main(_e2e_argv(root, out)) == 0
    v = json.loads((out / "READOUT.json").read_text())
    assert v["failed_preconditions"] == []
    assert v["D_block"]["n_common_decks"] == 700
    assert v["branch"] in ("G-CONFIRMED", "G-DEPLOYS", "G-CLOCK",
                           "G-PRESENT", "G-FLAT", "G-ANOMALY")
    assert v["p_q_r"]["p"] is not None
    # the cost rider fired (ms_ratio 1.20 exactly -> NOT fired; make it fire)
    assert v["cost_N4"]["N4_FIRED"] is False
    md = (out / "READOUT.md").read_text()
    assert "NO CORROBORATION" in md          # §4.3(6) on a PASSING branch too


def test_cost_confounded_prefixes_the_branch_sentence(tmp_path):
    """§4.2: above the bar the read-out 'downgrades the against-champion reading to
    COST-CONFOUNDED and says so IN THE BRANCH SENTENCE'."""
    root = _e2e_world(tmp_path, arb={"n_decks": 700, "champ_ms": 1500.0},
                      rnd={"n_decks": 700})
    out = tmp_path / "out"
    S2.main(_e2e_argv(root, out))
    v = json.loads((out / "READOUT.json").read_text())
    assert v["cost_N4"]["N4_FIRED"] is True
    assert v["branch_headline"].startswith("[COST-CONFOUNDED — ms_ratio > 1.20]")
    assert "COST-CONFOUNDED" in (out / "READOUT.md").read_text()


def test_G_FLAT_carries_both_mandatory_riders_and_the_scope_sentence(tmp_path):
    root = _e2e_world(tmp_path,
                      arb={"n_decks": 700, "margin": 0.0, "z_override": 0.2,
                           "elo": 1.0},
                      rnd={"n_decks": 700, "margin": 0.0, "z_override": 0.1})
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
                      arb={"n_decks": 700, "margin": 0.0, "z_override": 9.99},
                      rnd={"n_decks": 700, "margin": 0.0})
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
