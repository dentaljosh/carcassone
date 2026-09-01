#!/usr/bin/env python3
"""`b32v64_cell` — the branch TRUTH-TABLE SWEEP and the gate machinery tests.

⭐ DESIGN §12.1 names this file a LAUNCH PRECONDITION, and READ_RULE §4.4 spells
out what it must do:

> ⛔ TO BE VERIFIED BY A MACHINE SWEEP over the branch-condition truth table, in
> `tests/test_tiearb_b32v64.py`, which must **re-transcribe this section
> independently of the implementation** and assert exactly one branch fires on
> every cell — `NaN`, infinity, the `se_D <= 0.2551` overlap region, and the exact
> boundary values `z_D ∈ {−2, +2}` and `|D| + 1.645·se_D = 0.93` included.

⭐ "INDEPENDENTLY OF THE IMPLEMENTATION" is taken literally: `_oracle_branch`
below is a fresh transcription of READ_RULE §4's five rows from the pair's TEXT,
written without reference to `decide_branch`'s code, and the sweep asserts the
two agree on every cell. If they ever disagree, ONE of them is wrong and the test
says which cell separates them — which is the whole point. (Stage 2's equivalent
§4.1 sweep is the template, and it is what found Stage 2's unreachable `G-N`
before any number existed.)

⚠️ The `EQUIV` bar is NOT a constant of the adjudicator: `TOLERANCE_PTS` and
`EQUIV_SHAPE` are READ from `b32v64_cell/WORKERS.conf`. BOTH supported shapes are
swept, and the SHIPPED committed value is asserted separately so a silent edit to
the conf is visible as a test failure rather than as a changed verdict.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TILETIE = REPO / "scripts" / "tiletie"
CELL_DIR = REPO / "measurement" / "tiearb_widening_20260817" / "b32v64_cell"
if str(TILETIE) not in sys.path:
    sys.path.insert(0, str(TILETIE))

A = pytest.importorskip("analyze_b32v64_cell")

HI, LO = A.CELL_HI, A.CELL_LO
NAN = float("nan")
INF = float("inf")

#: The sibling cell's REAL spent artifacts — the known-good corpus. Tests that
#: need them skip cleanly when the share is not mounted.
_B64_SHARE = Path(A.DEFAULT_KNOWNGOOD_SHARE)
_B64_SMOKE_PRESENT = (_B64_SHARE / "smoke" /
                      "smoke_b64_WIDE_B64J4_deploy11008" /
                      "manifest.json").is_file()
needs_b64_smoke = pytest.mark.skipif(
    not _B64_SMOKE_PRESENT,
    reason=f"the b64 cell's spent smoke artifacts are not mounted at {_B64_SHARE}")


# --------------------------------------------------------------------------- #
# the ORACLE — READ_RULE §4 re-transcribed from the PAIR'S TEXT                #
# --------------------------------------------------------------------------- #
def _oracle_equiv(D, se_D, tolerance, shape):
    """READ_RULE §4's definitions block, transcribed:

        MARGIN  == 0.93 pts/game                      (here: `tolerance`)
        EQUIV   == ( |D| + 1.645*se_D <= MARGIN )     two_sided
        EQUIV   == (  D  + 1.645*se_D <= MARGIN )     one_sided (non-inferiority)
    """
    if D is None or se_D is None:
        return False
    if isinstance(D, float) and (math.isnan(D) or math.isinf(D)):
        return False
    if isinstance(se_D, float) and (math.isnan(se_D) or math.isinf(se_D)):
        return False
    lhs = (abs(D) if shape == "two_sided" else D) + 1.645 * se_D
    return lhs <= tolerance


def _oracle_branch(z_D, D, se_D, any_gate_failed, tolerance, shape):
    """READ_RULE §4.1's FIVE rows, in the committed order, FIRST MATCH WINS.

    1 `U-UNREADABLE`  any §3 precondition fails
    2 `L-REVERSED`    z_D <= -2.0
    3 `L-RISING`      z_D >= +2.0
    4 `L-SATURATED`   EQUIV
    5 `L-AMBIGUOUS`   everything else
    """
    if any_gate_failed:
        return "U-UNREADABLE"
    if z_D is None or (isinstance(z_D, float)
                       and (math.isnan(z_D) or math.isinf(z_D))):
        # §4.4: G-STAT catches this in §3 BEFORE any branch comparison, so it can
        # only be reached as a DEFECT — and a defect is not adjudicated.
        return "U-UNREADABLE"
    if z_D <= -2.0:
        return "L-REVERSED"
    if z_D >= 2.0:
        return "L-RISING"
    if _oracle_equiv(D, se_D, tolerance, shape):
        return "L-SATURATED"
    return "L-AMBIGUOUS"


def _cfg(shape="two_sided", tolerance=0.93):
    return {"tolerance_pts": tolerance, "equiv_shape": shape, "ci_z": A.CI_Z,
            "predicate": A.EQUIV_SHAPE_TEXT[shape], "source": "<synthetic>"}


def _decide(z_D, D, se_D, cfg, failed=False):
    pre = {"G-STAT": not failed}
    return A.decide_branch(z_D, D, se_D, pre, cfg)["branch"]


# --------------------------------------------------------------------------- #
# A FULLY SYNTHETIC, GATE-CLEAN RUN — so the END-TO-END read-out can be tested #
# --------------------------------------------------------------------------- #
#: ⚠️ Built at the pair's REAL floors (1,200 common decks / 2,400 games per cell)
#: rather than at a convenient small n, because `G-N`'s floors are production
#: constants and a test that shrank them would stop testing the shipped gate.
#: 4,800 tiny records write and re-read in well under a second.
_SYNTH_N_DECKS = 1200


def _synth_records(cell_dir: Path, values: dict):
    """One record per (deck, seat). Both seats carry the same `diff`, so the
    seat-balanced per-deck margin IS that value — `_paired_z`'s own construction
    with the seat noise removed."""
    for seed, v in values.items():
        for seat in (0, 1):
            (cell_dir / f"seed{seed}_a{seat}.json").write_text(json.dumps({
                "seed": seed, "a_seat": seat, "diff": v, "elapsed_s": 600.0,
                "ok": True, "cand_tiearb": {"fires": 17.5}}))


def _synth_summary(b, n_games, M, z):
    return {
        "paired_mean_margin": M, "paired_z": z, "n_paired": n_games // 2,
        "elo": 40.0, "elo_sig_1sigma": 9.0, "winrate": 0.55, "winrate_z": 3.1,
        "W": 700, "D": 100, "L": 400, "n": n_games, "n_attempted": n_games,
        "n_failed": 0, "failure_rate": 0.0, "failed_cells": [],
        "resolved_failed_cells": [], "failure_rate_trigger": 0.05,
        "validity_trigger_fired": False,
        "tiearb_B": [b], "tiearb_J": [4], "tiearb_modes": ["argmax"],
        "tiearb_phi": 17.5, "tiearb_error_rate_on_fired": 0.0,
        "tiearb_errors_total": 0, "tiearb_first_error": None,
        "tiearb_partial_argmax_total": 0,
        "champ_prefix_ms_per_move": 11651.0, "rung_ms_per_move": 1763.0,
    }


def _synth_manifest(b):
    return {
        "cand_tiearb": {"enabled": True, "B": b, "J": 4, "mode": "argmax",
                        "salt": "tiearb2-deploy-v1", "eps": 0.0},
        "carc_rs_build": "carc_rs-0.1.0+deadbeefcafe+rustcunpinned",
        "rules_profile": {"name": "fixed_v1"},
        "utc": "2026-08-21T00:00:00Z", "utc_end": "2026-08-21T01:00:00Z",
        "config": {"cand_leaf_hash": A.CHAMP_LEAF_HASH,
                   "band_seed_start": A.BAND_EXPECTED, "paired": True,
                   "info": "fair", "n": 2 * _SYNTH_N_DECKS,
                   "champion": {"k_dets": 8, "sims_per_det": 1376,
                                "total_sims": 11008, "c_puct": 1.5, "tau_p": 5.0,
                                "leaf_quantize": "float",
                                "final_select": "visits"},
                   "endgame": {"exact_k": 2},
                   "backend": {"name": "rust"},
                   "opponent": {"mode": "fair-champion"}},
    }


def _synthetic_run(tmp: Path, D=-0.35, se_D=0.49, shape="one_sided",
                   halt=False, smoke_utc="2020-01-01T00:00:00Z"):
    """A complete, GATE-CLEAN synthetic run on disk, at the pair's real floors."""
    n = _SYNTH_N_DECKS
    # a ±1 pattern scaled to land EXACTLY on the requested (D, se_D)
    z = [1.0 if i % 2 == 0 else -1.0 for i in range(n)]
    mean_z = sum(z) / n
    sd_z = math.sqrt(sum((x - mean_z) ** 2 for x in z) / (n - 1))
    scale = se_D * math.sqrt(n) / sd_z
    seeds = [A.BAND_EXPECTED + i for i in range(n)]
    d_vals = {s: D + scale * (z[i] - mean_z) for i, s in enumerate(seeds)}

    hi = tmp / "cell_hi"; lo = tmp / "cell_lo"
    verdicts = tmp / "verdicts"
    for p in (hi, lo, verdicts):
        p.mkdir(parents=True, exist_ok=True)
    _synth_records(hi, d_vals)                      # CELL_B64 carries D_i
    _synth_records(lo, {s: 0.0 for s in seeds})     # CELL_B32 is the zero arm
    (hi / "summary.json").write_text(json.dumps(_synth_summary(64, 2 * n, D, 1.0)))
    (lo / "summary.json").write_text(json.dumps(_synth_summary(32, 2 * n, 0.0, 0.1)))
    (hi / "manifest.json").write_text(json.dumps(_synth_manifest(64)))
    (lo / "manifest.json").write_text(json.dumps(_synth_manifest(32)))

    for host in A.EXPECT_HOSTS:
        for b in (64, 32):
            (verdicts / f"PREFLIGHT_{host}_FIRST_B{b}.json").write_text(
                json.dumps(_pf(host, b)))

    (tmp / "GATE_NEST.json").write_text(json.dumps({"witness": True}))
    (tmp / "BAND_CLAIM.json").write_text(
        f"{A.BAND_EXPECTED}\nsynthetic\nclaimed 2026-08-20\n")
    conf = tmp / "WORKERS.conf"
    conf.write_text(
        f"TOLERANCE_PTS=0.93\nEQUIV_SHAPE={shape}\nK_DETS=8\nSIMS=1376\n"
        f"EXACT_K=2\nRULES_PROFILE=fixed_v1\n"
        f"CHAMP_LEAF_HASH={A.CHAMP_LEAF_HASH}\nTIEARB_B_LO=32\nTIEARB_B_HI=64\n")

    realized = A.SMOKE_HALT_BAR * (1.2 if halt else 0.5)
    (tmp / "SMOKE.json").write_text(json.dumps({
        "worker_secs_per_game": realized,
        "production_knobs": A.expected_production_knobs(conf),
        "smoke_utc": smoke_utc}))
    (tmp / A.SMOKE_HALT_RECORD).write_text(json.dumps(
        A.halt_record({"worker_secs_per_game": realized})))
    return {"hi": hi, "lo": lo, "verdicts": verdicts, "conf": conf, "tmp": tmp}


def _synthetic_readout(D=-0.35, se_D=0.49, shape="one_sided", halt=False,
                       tmp=None, **kw):
    import argparse
    import tempfile
    tmp = Path(tmp or tempfile.mkdtemp())
    r = _synthetic_run(tmp, D=D, se_D=se_D, shape=shape, halt=halt, **kw)
    args = argparse.Namespace(
        b64_summary=str(r["hi"] / "summary.json"),
        b64_manifest=str(r["hi"] / "manifest.json"), b64_records=str(r["hi"]),
        b32_summary=str(r["lo"] / "summary.json"),
        b32_manifest=str(r["lo"] / "manifest.json"), b32_records=str(r["lo"]),
        preflight=None, verdicts_dir=str(r["verdicts"]),
        gate_nest=str(tmp / "GATE_NEST.json"),
        band_claim=str(tmp / "BAND_CLAIM.json"),
        smoke=str(tmp / "SMOKE.json"),
        smoke_halt=str(tmp / A.SMOKE_HALT_RECORD),
        workers_conf=str(r["conf"]), blind_commit="0123456789abcdef",
        failures_confirmed_by=None, failures_confirmed_note=None)
    return A.build_readout(args)


# --------------------------------------------------------------------------- #
# 1. THE BRANCH TRUTH-TABLE SWEEP                                              #
# --------------------------------------------------------------------------- #
#: The synthetic (D, se_D) grid. It is built to STRADDLE every boundary the pair
#: names, not to be a pretty lattice: the committed se_D (0.5044), the realized
#: projection (0.4570), the `two_sided` overlap threshold 0.93/3.645 = 0.2551,
#: values either side of it, and se_D small enough that a modest D reaches 2σ.
SE_GRID = (0.02, 0.10, 0.2551, 0.26, 0.4570, 0.5044, 0.80, 1.50)
D_GRID = (-4.0, -2.0, -1.0088, -0.93, -0.5, -0.3, -0.1003, -0.01, 0.0,
          0.01, 0.1003, 0.3, 0.5, 0.93, 1.0088, 2.0, 4.0)


@pytest.mark.parametrize("shape", ["two_sided", "one_sided"])
def test_branch_truth_table_sweep_matches_the_oracle(shape):
    """⭐ THE SWEEP. Every (D, se_D) cell, both shapes, oracle vs implementation."""
    cfg = _cfg(shape)
    seen = set()
    for se in SE_GRID:
        for D in D_GRID:
            z = D / se
            want = _oracle_branch(z, D, se, False, 0.93, shape)
            got = _decide(z, D, se, cfg)
            assert got == want, (
                f"shape={shape} D={D} se_D={se} z_D={z:+.4f}: oracle says {want}, "
                f"decide_branch says {got}")
            seen.add(got)
    # ⚠️ a sweep that never reaches a branch has not tested it
    assert {"L-REVERSED", "L-RISING", "L-SATURATED", "L-AMBIGUOUS"} <= seen, (
        f"shape={shape}: the grid did not reach every branch — reached {seen}")


@pytest.mark.parametrize("shape", ["two_sided", "one_sided"])
def test_every_branch_is_reachable_and_exactly_one_fires(shape):
    """§4.4 TOTALITY + DISJOINTNESS: exactly one branch matches every read."""
    cfg = _cfg(shape)
    fired = {}
    for se in SE_GRID:
        for D in D_GRID:
            b = _decide(D / se, D, se, cfg)
            assert b in A.BRANCH_ORDER
            fired.setdefault(b, []).append((D, se))
    for b in ("L-REVERSED", "L-RISING", "L-SATURATED", "L-AMBIGUOUS"):
        assert fired.get(b), f"{b} never fired under shape={shape}"


@pytest.mark.parametrize("shape", ["two_sided", "one_sided"])
def test_all_five_named_branches_have_text_and_are_declared_reachable(shape):
    """§4.0 — an unreachable headline branch must be visible BEFORE the run."""
    assert A.BRANCH_ORDER == ("U-UNREADABLE", "L-REVERSED", "L-RISING",
                              "L-SATURATED", "L-AMBIGUOUS")
    for b in A.BRANCH_ORDER:
        head, body = A.branch_text(b, _cfg(shape))
        assert head and body
    rs = A.reachable_branches(_cfg(shape))
    assert rs["unreachable"] == []
    assert set(rs["reachable"]) == set(A.BRANCH_ORDER)


# --------------------------------------------------------------------------- #
# 1b. ⭐ THE BRANCH-TEXT CONFORMANCE CLASS (REVIEW R1 finding R10)              #
#                                                                             #
# The sweep above tests the branch LABEL and nothing else — which is exactly   #
# how B1–B5 shipped under 130 green tests: the adjudicator carried the         #
# pre-RULING-1 two-sided WORDS while choosing the right branch. These          #
# assertions are the missing class.                                           #
# --------------------------------------------------------------------------- #
#: ⛔ READ_RULE §2.1 line 98 and §4: *"The read-out must say 'one-sided 95%
#: upper bound', NEVER '90% CI'."*
FORBIDDEN_UNDER_ONE_SIDED = ("90% CI", "AT 90% CONFIDENCE", "90% confidence",
                             "UPPER 90% bound")
REQUIRED_UNDER_ONE_SIDED = {
    "L-SATURATED": ("UB95(D)", "ONE-SIDED 95% UPPER BOUND ON THE COST",
                    "ONE-SIDED NON-INFERIORITY", "0.556",
                    "THIRD MANDATORY RIDER", "L-REVERSED did NOT fire",
                    "NOT THE PLACE TO CLAIM"),
    "L-AMBIGUOUS": ("UB95(D)", "REACHABLE ONLY FROM THE HIGH SIDE",
                    "0.556", "0.629", "NO n resolves it",
                    "NEITHER A CONVICTED COST NOR A CONVICTED NON-INFERIORITY"),
}


@pytest.mark.parametrize("branch,phrases", sorted(REQUIRED_UNDER_ONE_SIDED.items()))
def test_one_sided_branch_text_carries_the_ruled_phrases(branch, phrases):
    head, body = A.branch_text(branch, _cfg("one_sided"))
    blob = head + " " + body
    for p in phrases:
        assert p in blob, f"{branch} (one_sided) is missing required phrase {p!r}"


@pytest.mark.parametrize("branch", sorted(REQUIRED_UNDER_ONE_SIDED))
def test_one_sided_branch_text_never_says_90_percent_CI(branch):
    """⛔ THE PROHIBITION, ASSERTED. This is the assertion that would have caught
    B1 and B2 before they shipped."""
    head, body = A.branch_text(branch, _cfg("one_sided"))
    blob = head + " " + body
    for p in FORBIDDEN_UNDER_ONE_SIDED:
        assert p not in blob, (
            f"{branch} (one_sided) contains the FORBIDDEN phrase {p!r} — "
            f"READ_RULE §4 forbids it under RULING 1")


#: The converse set. A `two_sided` committed block must render text matching ITS
#: OWN predicate — the failure mode is text and shape disagreeing, in EITHER
#: direction, and a test that only policed one direction would let the mirror
#: image of B1 through.
REQUIRED_UNDER_TWO_SIDED = {
    "L-SATURATED": ("AT 90% CONFIDENCE", "90% CI", "EQUIVALENCE result", "0.158"),
    "L-AMBIGUOUS": ("NEITHER A DIFFERENCE NOR AN EQUIVALENCE", "CI90(D)",
                    "equivalence test", "0.158"),
}
FORBIDDEN_UNDER_TWO_SIDED = ("UB95(D)", "ONE-SIDED NON-INFERIORITY",
                             "ONE-SIDED 95% UPPER BOUND", "0.556")


@pytest.mark.parametrize("branch,phrases", sorted(REQUIRED_UNDER_TWO_SIDED.items()))
def test_two_sided_branch_text_is_the_converse(branch, phrases):
    head, body = A.branch_text(branch, _cfg("two_sided"))
    blob = head + " " + body
    for p in phrases:
        assert p in blob, f"{branch} (two_sided) is missing required phrase {p!r}"
    for p in FORBIDDEN_UNDER_TWO_SIDED:
        assert p not in blob, (
            f"{branch} (two_sided) contains {p!r} — that is the RULED shape's "
            f"language on the DRAFTED shape's predicate, the mirror image of B1")
    # ⚠️ and the drafted text must SAY it is superseded, so nobody reads a
    # two_sided render as current practice
    assert "SUPERSEDED BY RULING 1" in blob


def test_shape_invariant_branches_are_shared_not_duplicated():
    """Rows 1–3 do not depend on the predicate, so they must be ONE text."""
    for b in ("U-UNREADABLE", "L-REVERSED", "L-RISING"):
        assert (A.branch_text(b, _cfg("one_sided"))
                == A.branch_text(b, _cfg("two_sided")))
        assert b in A.BRANCH_TEXT_COMMON


def test_branch_text_refuses_an_unknown_shape():
    """⛔ A verdict rendered in the wrong shape's words is a MIS-ADJUDICATION."""
    with pytest.raises(SystemExit) as e:
        A.branch_text("L-SATURATED", {"equiv_shape": "three_sided"})
    assert "MIS-ADJUDICATION" in str(e.value)


def test_the_rendered_readout_carries_the_ruled_phrases_not_the_drafted_ones():
    """⭐ END-TO-END: the phrases must survive into the MARKDOWN a human reads,
    not merely exist in a constant."""
    v = _synthetic_readout(D=-0.35, se_D=0.49, shape="one_sided")
    md = A.render(v)
    assert v["branch"] == "L-SATURATED"
    for p in ("UB95(D)", "ONE-SIDED 95% UPPER BOUND ON THE COST"):
        assert p in md
    # ⚠️ SCOPED DELIBERATELY. A line that says *NEVER "90% CI"* is the RULE being
    # quoted, not a violation of it — the read-out is required to carry the
    # prohibition. What is forbidden is PRESENTING the statistic that way, so the
    # assertion runs over every line that is not itself stating the prohibition.
    offenders = [ln for ln in md.splitlines()
                 if "NEVER" not in ln
                 and any(p in ln for p in FORBIDDEN_UNDER_ONE_SIDED)]
    assert not offenders, f"the rendered read-out presents: {offenders}"
    # …and the prohibition itself MUST be present somewhere
    assert any("NEVER" in ln and "90% CI" in ln for ln in md.splitlines())
    # CI90 survives ONLY as demoted context, never as the headline statistic
    assert "REPORTED FOR CONTEXT, adjudicates nothing" in md
    # ⭐ B1's exact failure scenario: D̂ = −0.35, se_D = 0.49 ⇒ the third rider
    # must be DISCHARGED against the realized sign, not left as static prose.
    assert "THIRD MANDATORY RIDER, DISCHARGED" in md
    assert "NOT THE PLACE TO CLAIM" in md


# --------------------------------------------------------------------------- #
# 2. FIRST-MATCH-WINS — the ordering edge, both directions                     #
# --------------------------------------------------------------------------- #
def test_first_match_wins_l_rising_preempts_l_saturated():
    """⭐ A value satisfying BOTH `L-RISING` and `L-SATURATED` arithmetic must fire
    `L-RISING`. §4.4: *"FIRST-MATCH-WINS still governs … a 2σ difference is not an
    equivalence whatever a wide-margin CI says."*"""
    D, se = 0.25, 0.10          # z_D = +2.5 AND |D| + 1.645*se = 0.4145 <= 0.93
    for shape in ("two_sided", "one_sided"):
        cfg = _cfg(shape)
        assert A.equiv_predicate(D, se, cfg)["EQUIV"] is True, shape
        assert (D / se) >= A.Z_BAR
        assert _decide(D / se, D, se, cfg) == "L-RISING", shape


def test_first_match_wins_l_reversed_preempts_l_saturated_under_one_sided():
    """⭐ THE ORDERING EDGE THE 2026-08-21 ONE-SIDED RULING MAKES LOAD-BEARING.

    Under `one_sided`, a LARGE-NEGATIVE `D` satisfies non-inferiority by
    construction. `L-REVERSED` is branch #2 and must pre-empt it."""
    D, se = -0.25, 0.10         # z_D = -2.5 AND D + 1.645*se = -0.0855 <= 0.93
    cfg = _cfg("one_sided")
    assert A.equiv_predicate(D, se, cfg)["EQUIV"] is True
    assert (D / se) <= -A.Z_BAR
    assert _decide(D / se, D, se, cfg) == "L-REVERSED"
    # and the read-out is told to print BOTH facts, never to hide the overlap
    det = A.decide_branch(D / se, D, se, {"G-STAT": True}, cfg)
    assert det["equiv"]["EQUIV"] is True
    assert det.get("first_match_note")


def test_one_sided_ruling_mild_negative_D_fires_l_saturated():
    """⭐ THE RULING'S OTHER LOAD-BEARING CELL: a MILDLY negative `D` with
    `|z_D| < 2` CLEARS non-inferiority and must fire `L-SATURATED`."""
    D, se = -0.3, 0.5           # z_D = -0.6 ; D + 1.645*se = +0.5225 <= 0.93
    one, two = _cfg("one_sided"), _cfg("two_sided")
    assert abs(D / se) < A.Z_BAR
    assert _decide(D / se, D, se, one) == "L-SATURATED"
    # ⚠️ and the SHAPE is what decides it: two_sided reads the same numbers
    # AMBIGUOUS (|D| + 1.645*se = 1.1225 > 0.93). One committed line, two verdicts.
    assert A.equiv_predicate(D, se, two)["EQUIV"] is False
    assert _decide(D / se, D, se, two) == "L-AMBIGUOUS"


@pytest.mark.parametrize("z", [-2.0, 2.0])
def test_exact_z_boundaries_are_inclusive(z):
    """§4.1: `z_D <= -2.0` and `z_D >= +2.0` — the boundary VALUES fire."""
    se = 0.5
    D = z * se
    want = "L-REVERSED" if z < 0 else "L-RISING"
    for shape in ("two_sided", "one_sided"):
        assert _decide(z, D, se, _cfg(shape)) == want, shape


def test_exact_equivalence_boundary_is_inclusive():
    """`EQUIV` is `<=`, so `|D| + 1.645*se_D == 0.93` FIRES `L-SATURATED`."""
    se = 0.4
    D = 0.93 - 1.645 * se       # exactly on the bar
    cfg = _cfg("two_sided")
    eq = A.equiv_predicate(D, se, cfg)
    assert eq["EQUIV"] is True
    assert abs(eq["statistic"] - 0.93) < 1e-12
    assert _decide(D / se, D, se, cfg) == "L-SATURATED"
    # and a hair over the bar does NOT fire it
    assert A.equiv_predicate(D + 1e-6, se, cfg)["EQUIV"] is False


def test_two_sided_overlap_region_is_empty_above_the_documented_threshold():
    """§4.4's arithmetic: under `two_sided` the `L-RISING`/`L-SATURATED` overlap is
    empty for every `se_D > 0.93/3.645 = 0.2551`."""
    cfg = _cfg("two_sided")
    thresh = 0.93 / 3.645
    for se in (0.26, 0.4570, 0.5044, 0.80):
        assert se > thresh
        D = 2.0 * se            # exactly z_D = +2
        assert A.equiv_predicate(D, se, cfg)["EQUIV"] is False
    # BELOW the threshold the overlap is real — and first-match-wins resolves it
    se = 0.10
    D = 2.0 * se
    assert A.equiv_predicate(D, se, cfg)["EQUIV"] is True
    assert _decide(D / se, D, se, cfg) == "L-RISING"


# --------------------------------------------------------------------------- #
# 3. `U-UNREADABLE` — every gate failure suppresses the verdict                #
# --------------------------------------------------------------------------- #
ALL_GATES = ("G-J1", "G-J4", "G-J13", "G-NEST", "G-FIRE", "G-DIVERGE", "G-BAND",
             "G-N", "G-FAILED", "G-TOOL", "G-PLY", "G-STAT", "G-SMOKE")


def test_thirteen_gates_are_named_with_scope_and_marker():
    """READ_RULE §3: **13 gates**, and *"an unmarked gate is a DRAFTING DEFECT."*"""
    assert len(ALL_GATES) == 13
    assert set(A.GATE_SCOPE) == set(ALL_GATES)
    assert set(A.GATE_MARKER) == set(ALL_GATES)
    for g in ALL_GATES:
        assert A.GATE_SCOPE[g].startswith("["), g
        assert A.GATE_MARKER[g].startswith("["), g


@pytest.mark.parametrize("gate", ALL_GATES)
@pytest.mark.parametrize("shape", ["two_sided", "one_sided"])
def test_any_single_gate_failure_fires_u_unreadable(gate, shape):
    """§4.1 row 1 — a failing gate SUPPRESSES the verdict, whatever `z_D` says."""
    cfg = _cfg(shape)
    pre = {g: True for g in ALL_GATES}
    pre[gate] = False
    for z, D, se in ((0.0, 0.0, 0.5), (3.0, 1.5, 0.5), (-3.0, -1.5, 0.5),
                     (0.1, 0.05, 0.5)):
        v = A.decide_branch(z, D, se, pre, cfg)
        assert v["branch"] == "U-UNREADABLE", (gate, z)
        assert v["failed_preconditions"] == [gate]
        assert v["adjudicated"] is False
        assert "SUPPRESSES" in v["suppressed"]


def test_all_gates_pass_lets_a_verdict_through():
    """The control: with all 13 passing, the branch table actually fires."""
    pre = {g: True for g in ALL_GATES}
    v = A.decide_branch(3.0, 1.5, 0.5, pre, _cfg("one_sided"))
    assert v["branch"] == "L-RISING"
    assert v["adjudicated"] is True


def test_multiple_gate_failures_are_all_reported_never_short_circuited():
    """§3: *"whichever gate(s) failed — ALL of them, never short-circuited at the
    first."*"""
    pre = {g: True for g in ALL_GATES}
    pre["G-N"] = pre["G-PLY"] = pre["G-TOOL"] = False
    v = A.decide_branch(0.5, 0.25, 0.5, pre, _cfg("one_sided"))
    assert v["failed_preconditions"] == ["G-N", "G-PLY", "G-TOOL"]


# --------------------------------------------------------------------------- #
# 4. `G-STAT` — NaN / infinity / absent / se_D <= 0                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [NAN, INF, -INF, None])
@pytest.mark.parametrize("slot", ["z_D", "D", "se_D", "z_hi", "z_lo"])
def test_gate_stat_fails_on_nan_inf_or_absent_in_any_slot(bad, slot):
    args = {"z_D": 1.0, "D": 0.5, "se_D": 0.5, "ci90": [-0.3, 1.3],
            "z_hi": 1.1, "z_lo": 0.9}
    args[slot] = bad
    ok, d = A.gate_stat(**args)
    assert ok is False
    assert d["nan_inf_or_absent"] or d["se_D_positive"] is False


@pytest.mark.parametrize("bad_ci", [[NAN, 1.0], [0.0, INF], [None, 1.0], None,
                                    [1.0]])
def test_gate_stat_fails_on_a_bad_ci90(bad_ci):
    """READ_RULE §3 names `CI90(D)` in `G-STAT` explicitly — a half-formed or
    non-finite interval FAILS."""
    ok, _d = A.gate_stat(1.0, 0.5, 0.5, bad_ci, 1.1, 0.9)
    assert ok is False


@pytest.mark.parametrize("se", [0.0, -0.1])
def test_gate_stat_fails_on_non_positive_se(se):
    ok, d = A.gate_stat(1.0, 0.5, se, [0.0, 1.0], 1.1, 0.9)
    assert ok is False
    assert d["se_D_positive"] is False


def test_gate_stat_passes_a_healthy_read():
    ok, d = A.gate_stat(1.2345, 0.6, 0.486, [-0.2, 1.4], 1.1, 0.9)
    assert ok is True
    assert d["nan_inf_or_absent"] == []


def test_gate_stat_rejects_booleans_in_statistic_slots():
    """⚠️ `True` is an `int` in Python. A boolean reaching a statistic slot is a
    plumbing bug and must not be silently read as 1.0."""
    ok, _d = A.gate_stat(True, 0.5, 0.5, [0.0, 1.0], 1.1, 0.9)
    assert ok is False


def test_nan_z_without_a_gate_failure_is_reported_as_a_defect():
    """§4.4 guarantees `G-STAT` fires first; if it somehow did not, the branch
    table must NOT enter a comparison on NaN — it names the defect."""
    pre = {g: True for g in ALL_GATES}
    for z in (NAN, INF, -INF, None):
        v = A.decide_branch(z, 0.5, 0.5, pre, _cfg("one_sided"))
        assert v["branch"] == "U-UNREADABLE"
        assert v["failed_preconditions"] == ["G-STAT"]
        assert "DEFECT" in v["reason"]


def test_equiv_is_false_on_non_finite_inputs():
    cfg = _cfg("one_sided")
    for D, se in ((NAN, 0.5), (0.5, NAN), (INF, 0.5), (0.5, INF), (None, 0.5),
                  (0.5, None)):
        eq = A.equiv_predicate(D, se, cfg)
        assert eq["EQUIV"] is False
        assert eq["statistic"] is None


# --------------------------------------------------------------------------- #
# 5. `G-J13` — STRICTLY PINNED, no `two_sided.*` fallback                      #
# --------------------------------------------------------------------------- #
def _pf(host, B, changed=True, unchanged=True, expected_B=None,
        with_witness_B=True, two_sided_only=False, path=None):
    """A synthetic preflight record at the PINNED addresses."""
    w = {"pick_changed": changed, "root_leaf_value_bits_unchanged": unchanged}
    if with_witness_B:
        w["B"] = B
    if two_sided_only:
        w = {"B": B} if with_witness_B else {}
    d = {"host": host, "j13_witness": w,
         "expected": {"B": B if expected_B is None else expected_B},
         "carc_rs_build": "carc_rs-0.1.0+deadbeefcafe+rustcunpinned",
         "_path": path or f"/verdicts/PREFLIGHT_{host}_FIRST_B{B}.json"}
    if two_sided_only:
        d["two_sided"] = {"pick_changed": changed,
                          "root_leaf_value_bits_unchanged": unchanged}
    return d


def _healthy_preflights():
    return [_pf(h, b) for h in A.EXPECT_HOSTS for b in (64, 32)]


def test_gate_j13_passes_a_healthy_four_file_set():
    ok, d = A.gate_j13(_healthy_preflights())
    assert ok is True
    assert d["n_files_consumed"] == 4
    for host in A.EXPECT_HOSTS:
        for b in ("64", "32"):
            assert d["by_host"][host][b]["two_sided_ok"] is True


def test_gate_j13_absent_witness_B_fails_never_coerced():
    """⚠️ RULING 2: *"ABSENT `B` ⇒ FAIL, never coerced."* A file with no
    `j13_witness.B` cannot evidence "at both B values"."""
    pres = _healthy_preflights()
    pres[0] = _pf(A.EXPECT_HOSTS[0], 64, with_witness_B=False)
    ok, d = A.gate_j13(pres)
    assert ok is False
    assert "ABSENT" in d["by_host"][A.EXPECT_HOSTS[0]]["64"]["why"]


def test_gate_j13_expected_B_mismatch_fails():
    pres = _healthy_preflights()
    pres[0] = _pf(A.EXPECT_HOSTS[0], 64, expected_B=32)
    ok, _d = A.gate_j13(pres)
    assert ok is False


@pytest.mark.parametrize("changed,unchanged", [(False, True), (True, False),
                                               (False, False), (None, True),
                                               (True, None)])
def test_gate_j13_requires_both_booleans_exactly_true(changed, unchanged):
    pres = _healthy_preflights()
    pres[0] = _pf(A.EXPECT_HOSTS[0], 64, changed=changed, unchanged=unchanged)
    ok, _d = A.gate_j13(pres)
    assert ok is False


def test_gate_j13_does_NOT_fall_back_to_two_sided():
    """⛔ THE STRICTNESS THIS CELL ADDS. `b32v64_cell/preflight.sh` ASSERTS the
    pinned booleans, so a record carrying them only under `two_sided.*` is an
    EMITTER defect and must FAIL LOUDLY rather than be papered over."""
    pres = _healthy_preflights()
    pres[0] = _pf(A.EXPECT_HOSTS[0], 64, two_sided_only=True)
    ok, d = A.gate_j13(pres)
    assert ok is False, "the two_sided.* fallback must be GONE"
    assert "two_sided" in d["strictness"]


def test_gate_j13_missing_host_or_missing_B_reads_as_zero_not_a_pass():
    """⭐ RULING 4: a zero-match glob reads as ZERO, never as a silent pass — and
    the filenames consumed per host are printed."""
    ok, d = A.gate_j13([])
    assert ok is False
    assert d["n_files_consumed"] == 0
    for host in A.EXPECT_HOSTS:
        assert d["files_consumed_per_host"][host] == []
        assert d["by_host"][host]["64"]["two_sided_ok"] is False
    # one host complete, the other absent entirely
    ok, _d = A.gate_j13([_pf(A.EXPECT_HOSTS[0], b) for b in (64, 32)])
    assert ok is False
    # both hosts, but only ONE B value each
    ok, _d = A.gate_j13([_pf(h, 64) for h in A.EXPECT_HOSTS])
    assert ok is False


def test_gate_j13_this_cell_expects_B_64_and_32():
    ok, d = A.gate_j13(_healthy_preflights())
    assert d["expected_B"] == [64, 32]
    assert ok is True


# --------------------------------------------------------------------------- #
# 6. `G-TOOL` — cross-box equality, and `+rustcunpinned` is NORMAL             #
# --------------------------------------------------------------------------- #
def test_gate_tool_passes_when_both_boxes_emit_the_same_unpinned_build():
    """⛔ THE THIRD UNSATISFIABLE-GATE CATCH, carried: `unpinned` PASSES."""
    ok, d = A.gate_tool(_healthy_preflights())
    assert ok is True
    assert d["distinct_builds"] == ["carc_rs-0.1.0+deadbeefcafe+rustcunpinned"]


def test_gate_tool_fails_only_on_a_cross_box_difference():
    pres = _healthy_preflights()
    for p in pres:
        if p["host"] == A.EXPECT_HOSTS[1]:
            p["carc_rs_build"] = "carc_rs-0.1.0+0123456789ab+rustcunpinned"
    ok, d = A.gate_tool(pres)
    assert ok is False
    assert len(d["distinct_builds"]) == 2


def test_gate_tool_ignores_binary_sha_entirely():
    """`carc_rs_binary_sha` is BOX-LOCAL and must NEVER be compared across boxes."""
    pres = _healthy_preflights()
    for i, p in enumerate(pres):
        p["carc_rs_binary_sha"] = f"sha-{i}"
    ok, _d = A.gate_tool(pres)
    assert ok is True


def test_gate_tool_fails_on_an_absent_build_string():
    pres = _healthy_preflights()
    pres[0].pop("carc_rs_build")
    ok, _d = A.gate_tool(pres)
    assert ok is False


# --------------------------------------------------------------------------- #
# 7. the remaining gates — floors, reachability, fail-closed absences          #
# --------------------------------------------------------------------------- #
def test_gate_n_floors_are_reachable_and_bind_in_both_units():
    """⭐ Stage 2's `G-N` was UNREACHABLE BY CONSTRUCTION. This asserts it here."""
    ok, d = A.gate_n(1500, {HI: 3000, LO: 3000})
    assert ok is True
    assert d["deck_clause_reachable"] is True
    assert d["game_clause_reachable"] is True
    assert d["n_common_floor"] == 1200 and d["cell_games_floor"] == 2400
    # the deck clause is INDEPENDENTLY binding
    ok, _d = A.gate_n(1199, {HI: 3000, LO: 3000})
    assert ok is False
    ok, _d = A.gate_n(1500, {HI: 3000, LO: 2399})
    assert ok is False
    ok, _d = A.gate_n(None, {HI: 3000, LO: 3000})
    assert ok is False


def test_gate_fire_floor_and_absence():
    cells = {c: {"phi": 17.5, "summary": {"tiearb_error_rate_on_fired": 0.0}}
             for c in (HI, LO)}
    assert A.gate_fire(cells)[0] is True
    cells[LO]["phi"] = 0.5
    assert A.gate_fire(cells)[0] is False
    cells[LO]["phi"] = None
    assert A.gate_fire(cells)[0] is False, "an unmeasured surface is not a live one"


def test_gate_ply_absent_is_unknown_not_zero_and_fails():
    cells = {c: {"summary": {"tiearb_partial_argmax_total": 0}} for c in (HI, LO)}
    assert A.gate_ply(cells)[0] is True
    cells[HI]["summary"]["tiearb_partial_argmax_total"] = 1
    assert A.gate_ply(cells)[0] is False
    cells[HI]["summary"] = {}
    assert A.gate_ply(cells)[0] is False


def test_gate_diverge_floor_and_the_anomaly_that_still_passes():
    hi = {i: 1.0 for i in range(100)}
    lo = {i: (1.0 if i < 3 else 0.0) for i in range(100)}   # 1 - f0 = 0.97
    fb = A.f0_block(hi, lo)
    ok, d = A.gate_diverge(fb)
    assert ok is True and d["anomaly"] is False
    # 1 - f0 = 0.90 PASSES the 0.10 floor but is BELOW the 0.95 anomaly bar
    lo = {i: (1.0 if i < 10 else 0.0) for i in range(100)}
    fb = A.f0_block(hi, lo)
    assert abs(fb["one_minus_f0"] - 0.90) < 1e-9
    ok, d = A.gate_diverge(fb)
    assert ok is True, "an anomaly PASSES the gate"
    assert d["anomaly"] is True, "…and must be REPORTED as an anomaly"
    # a genuinely inert surface FAILS
    lo = {i: (1.0 if i < 95 else 0.0) for i in range(100)}
    ok, _d = A.gate_diverge(A.f0_block(hi, lo))
    assert ok is False


def test_gate_nest_absent_fails_and_a_false_witness_fails():
    assert A.gate_nest(None)[0] is False
    assert A.gate_nest({})[0] is False
    assert A.gate_nest({"witness": False})[0] is False
    assert A.gate_nest({"witness": "true"})[0] is False, "exactly True, not truthy"
    assert A.gate_nest({"witness": True})[0] is True


def test_gate_band_requires_all_four_conjuncts():
    decks = list(range(A.BAND_EXPECTED, A.BAND_EXPECTED + 5))
    cells = {c: {"manifest": {"config": {"band_seed_start": A.BAND_EXPECTED}},
                 "deck_seeds": decks} for c in (HI, LO)}
    claim = {"claimed_before_game_1": True, "band": A.BAND_EXPECTED}
    assert A.gate_band(cells, claim)[0] is True
    # a wrong band on one cell
    bad = json.loads(json.dumps(cells))
    bad[LO]["manifest"]["config"]["band_seed_start"] = 139000000000
    assert A.gate_band(bad, claim)[0] is False
    # the right band, but NOT the pinned one
    other = {c: {"manifest": {"config": {"band_seed_start": 139000000000}},
                 "deck_seeds": decks} for c in (HI, LO)}
    assert A.gate_band(other, {"claimed_before_game_1": True,
                               "band": 139000000000})[0] is False
    # different deck sets
    bad2 = json.loads(json.dumps(cells))
    bad2[LO]["deck_seeds"] = decks[:-1]
    assert A.gate_band(bad2, claim)[0] is False
    # no claim / a sentinel naming another band
    assert A.gate_band(cells, {"claimed_before_game_1": False,
                               "band": A.BAND_EXPECTED})[0] is False
    assert A.gate_band(cells, {"claimed_before_game_1": True,
                               "band": 139000000000})[0] is False


def test_gate_j1_is_inverted_and_absent_fails():
    cells = {c: {"manifest": {"config": {"cand_leaf_hash": A.CHAMP_LEAF_HASH}}}
             for c in (HI, LO)}
    assert A.gate_j1(cells)[0] is True
    cells[LO]["manifest"]["config"]["cand_leaf_hash"] = "0000000000000000"
    assert A.gate_j1(cells)[0] is False
    cells[LO]["manifest"] = {}
    assert A.gate_j1(cells)[0] is False


def _j4_cells(b_hi=64, b_lo=32):
    def one(b):
        return {"manifest": {"cand_tiearb": {
                    "enabled": True, "B": b, "J": 4, "mode": "argmax",
                    "salt": "tiearb2-deploy-v1", "eps": 0.0}},
                "summary": {"tiearb_B": [b], "tiearb_J": [4],
                            "tiearb_modes": ["argmax"]}}
    return {HI: one(b_hi), LO: one(b_lo)}


def test_gate_j4_pins_the_deployed_shape_and_voids_a_mixed_B_cell():
    assert A.gate_j4(_j4_cells())[0] is True
    bad = _j4_cells()
    bad[LO]["summary"]["tiearb_B"] = [32, 64]     # a MIXED-B cell is a VOID
    assert A.gate_j4(bad)[0] is False
    bad = _j4_cells()
    bad[HI]["manifest"]["cand_tiearb"]["salt"] = "other-salt"
    assert A.gate_j4(bad)[0] is False
    bad = _j4_cells()
    bad[HI]["manifest"]["cand_tiearb"]["J"] = 8
    assert A.gate_j4(bad)[0] is False
    assert A.gate_j4(_j4_cells(b_lo=16))[0] is False, "this cell's low B is 32"


def _failed_cells(f_hi, f_lo, attempted=3000):
    return {c: {"summary": {"n_failed": f, "n_attempted": attempted,
                            "failed_cells": [], "resolved_failed_cells": []},
                "n_games": attempted, "records": []}
            for c, f in ((HI, f_hi), (LO, f_lo))}


def test_gate_failed_three_clauses():
    # healthy: 0/0 — clause 3 vacuous
    ok, d = A.gate_failed(_failed_cells(0, 0))
    assert ok is True and d["clause3_vacuous_at_zero"] is True
    # clause 1: rate above 2%
    ok, _d = A.gate_failed(_failed_cells(61, 0), confirmation={
        "all_failures_confirmed": True})
    assert ok is False
    # clause 2: candidate-correlated, and the >= 5 floor protects a 1-vs-0 split
    ok, d = A.gate_failed(_failed_cells(1, 0), confirmation={
        "all_failures_confirmed": True})
    assert ok is True and d["clause2_candidate_correlated"] is False
    ok, d = A.gate_failed(_failed_cells(6, 1), confirmation={
        "all_failures_confirmed": True})
    assert ok is False and d["clause2_candidate_correlated"] is True
    # clause 3: ANY failure HALTS until a HUMAN confirmation is recorded
    ok, d = A.gate_failed(_failed_cells(1, 0))
    assert ok is False and d["clause3_halt"] is True
    ok, d = A.gate_failed(_failed_cells(1, 0),
                          confirmation={"all_failures_confirmed": True})
    assert ok is True and d["clause3_halt"] is False


def test_failure_surface_is_printed_and_wired_into_no_conjunct():
    """DESIGN §13.2 item 2 — `failed_cells[]` is a REPORT, never a conjunct."""
    cells = _failed_cells(0, 0)
    for c in (HI, LO):
        cells[c]["summary"]["failed_cells"] = [
            {"seed": 1, "a_seat": 0, "attempts": 2, "permanent": True,
             "exc_type": "WindowTruncationError", "window_truncation": True,
             "window_diag": {"extent": 41}}]
        cells[c]["summary"]["validity_trigger_fired"] = False
    surf = A.failure_surface(cells)
    assert surf["wired_into_conjuncts"] == []
    for c in (HI, LO):
        assert surf["per_cell"][c]["failed_cells"][0]["window_truncation"] is True
        assert surf["per_cell"][c]["validity_trigger_fired"] is False
    # ⭐ and it does NOT move the gate: the same cells with n_failed 0 still pass
    ok, d = A.gate_failed(cells, surface=surf)
    assert ok is True
    assert d["failure_surface_REPORT_ONLY"] is surf


# --------------------------------------------------------------------------- #
# 8. `G-SMOKE` — the TWO surfaces (RULING 1)                                   #
# --------------------------------------------------------------------------- #
def test_smoke_gate_fires_only_on_outcome_keys_not_on_structural_ones():
    """⭐ RULING 1: *"a reading that applies the emitter whitelist to the row
    fails a known-good smoke."*"""
    doc = {"worker_secs_per_game": 500.0, "headline": "a structural key",
           "kind": "smoke", "cells": {"CELL_B64": {"n": 24}},
           "throwaway_band": True}
    ok, d = A.gate_smoke(doc)
    assert ok is True, "structural keys must NEVER fire the row"
    assert d["forbidden_outcome_keys"] == []
    # the EMITTER surface DOES object to them — and is reported, not graded
    assert d["whitelist_REPORTED_not_a_gate_input"]["ok"] is False


@pytest.mark.parametrize("leak", [
    {"paired_mean_margin": 1.0}, {"elo": 12.0}, {"z_D": 2.0}, {"f0": 0.01},
    {"nested": {"deep": {"winrate": 0.55}}}, {"rows": [{"paired_z": 1.0}]},
])
def test_smoke_gate_fires_on_a_forbidden_outcome_key_at_any_depth(leak):
    doc = dict({"worker_secs_per_game": 500.0}, **leak)
    ok, d = A.gate_smoke(doc)
    assert ok is False
    assert d["forbidden_outcome_keys"]


def test_smoke_gate_absent_artifact_fails():
    ok, d = A.gate_smoke({})
    assert ok is False and d["present"] is False


def test_smoke_halt_bar_is_derived_from_the_measured_cell_and_is_one_sided():
    assert A.SMOKE_HALT_BAR == pytest.approx(1.50 * 928.025)
    over = {"worker_secs_per_game": A.SMOKE_HALT_BAR + 1}
    under = {"worker_secs_per_game": A.SMOKE_HALT_BAR - 1}
    # an overrun HALTS
    _ok, d = A.gate_smoke(over, cells_ran=False)
    assert d["halted"] is True
    # …and a HALT alone does not void the run: it is the LAUNCH that does
    ok, _d = A.gate_smoke(over, cells_ran=False)
    assert ok is True
    ok, _d = A.gate_smoke(over, cells_ran=True)
    assert ok is False, "halt AND the cells ran ⇒ launched anyway ⇒ FIRES"
    # an UNDERRUN proceeds, and running the cells after it is correct
    _ok, d = A.gate_smoke(under, cells_ran=True)
    assert d["halted"] is False
    assert _ok is True


def test_launched_anyway_is_derived_not_supplied():
    """⛔ B6: the old `--launched-after-halt` store_true flag defaulted to the
    PASSING value, so the gate could only fire if the person it policed chose to
    accuse themselves. It is DELETED, and no CLI surface can set it."""
    import inspect
    assert "launched_anyway" not in inspect.signature(A.gate_smoke).parameters
    src = (TILETIE / "analyze_b32v64_cell.py").read_text()
    # ⚠️ asserted on the CALL and the ATTRIBUTE, not on the bare name: the name
    # still appears in the prose that RECORDS why the flag was removed, and
    # deleting that history to satisfy a substring match would be worse.
    assert 'add_argument("--launched-after-halt"' not in src
    assert "launched_after_halt" not in src.replace(
        "--launched-after-halt", "")
    parser_src = src.split("def build_arg_parser")[1].split("\ndef main")[0]
    assert "store_true" not in parser_src, \
        "no operator store_true flag may gate a §3 conjunct"
    # and the CLI genuinely rejects it
    with pytest.raises(SystemExit):
        A.build_arg_parser().parse_args(
            ["adjudicate", "--launched-after-halt", "--b64-summary", "x",
             "--b64-manifest", "x", "--b32-summary", "x", "--b32-manifest", "x",
             "--out-dir", "x"])


def test_halt_record_shape_and_fail_closed_on_an_unevaluable_cost():
    """DESIGN §9.3.1 fixes the SHAPE: {halt, realized, bar}."""
    hd = A.halt_record({"worker_secs_per_game": 500.0})
    assert set(("halt", "realized", "bar")) <= set(hd)
    assert hd["halt"] is False and hd["realized"] == 500.0
    assert hd["bar"] == pytest.approx(A.SMOKE_HALT_BAR)
    assert A.halt_record({"worker_secs_per_game": 5000.0})["halt"] is True
    # ⛔ an absent / non-finite cost HALTS: an unevaluable cost check must not
    # wave a 6,000-game run through
    for bad in ({}, {"worker_secs_per_game": None},
                {"worker_secs_per_game": NAN}):
        hd = A.halt_record(bad)
        assert hd["halt"] is True and hd["evaluable"] is False


def test_gate_smoke_production_knobs_conjunct(tmp_path):
    """R6 — `G-SMOKE`'s FIRST conjunct, implementable at last."""
    conf = tmp_path / "WORKERS.conf"
    conf.write_text("TOLERANCE_PTS=0.93\nEQUIV_SHAPE=one_sided\nK_DETS=8\n"
                    "SIMS=1376\nEXACT_K=2\nRULES_PROFILE=fixed_v1\n"
                    f"CHAMP_LEAF_HASH={A.CHAMP_LEAF_HASH}\n"
                    "TIEARB_B_LO=32\nTIEARB_B_HI=64\n")
    want = A.expected_production_knobs(conf)
    assert set(want) == set(A.PRODUCTION_KNOB_FIELDS)
    good = {"worker_secs_per_game": 500.0, "production_knobs": want,
            "smoke_utc": "2020-01-01T00:00:00Z"}
    ok, d = A.gate_smoke(good, cells_ran=True, expected_knobs=want)
    assert ok is True
    assert d["conjunct1_production_knobs_before_game_1"]["ok"] is True
    # ⛔ ANY mismatch fires
    bad = json.loads(json.dumps(good))
    bad["production_knobs"]["sims"] = 800
    ok, d = A.gate_smoke(bad, cells_ran=True, expected_knobs=want)
    assert ok is False
    assert "sims" in d["conjunct1_production_knobs_before_game_1"]["mismatched"]
    # ⛔ ABSENCE fires — a conjunct reading an address nothing writes must not pass
    for missing in ("production_knobs", "smoke_utc"):
        bad2 = json.loads(json.dumps(good))
        bad2.pop(missing)
        ok, _d = A.gate_smoke(bad2, cells_ran=True, expected_knobs=want)
        assert ok is False, f"absent {missing} must FIRE"
    # ⛔ an observed None mismatches
    bad3 = json.loads(json.dumps(good))
    bad3["production_knobs"]["exact_k"] = None
    ok, _d = A.gate_smoke(bad3, cells_ran=True, expected_knobs=want)
    assert ok is False


#: ⭐ REVIEW R2 finding N3. The two sides of the ordering clause are written by
#: DIFFERENT emitters in DIFFERENT ISO spellings: `smoke_utc` comes from
#: `manifest::utc_end` in OFFSET form, `_earliest_record_utc` emits the `Z` form.
#: Every case below therefore uses MISMATCHED spellings on the two sides — the
#: previous test used `Z` on both and could not see this class at all.
@pytest.mark.parametrize("smoke_utc,earliest,want_ok,why", [
    # smoke strictly BEFORE game 1 — passes, across the spelling boundary
    ("2026-08-20T04:43:46+00:00", "2026-08-21T00:00:00Z", True, "before"),
    ("2026-08-20T23:59:59+00:00", "2026-08-21T00:00:00Z", True, "one second before"),
    # smoke strictly AFTER — fires
    ("2026-08-22T00:00:00+00:00", "2026-08-21T00:00:00Z", False, "after"),
    ("2026-08-21T00:00:01+00:00", "2026-08-21T00:00:00Z", False, "one second after"),
    # ⭐ THE EXACT TIE — DESIGN §9.2 says ">= FIRES". Lexicographically '+'
    # (0x2B) sorts BEFORE 'Z' (0x5A), so the string compare read PASS here.
    ("2026-08-21T00:00:00+00:00", "2026-08-21T00:00:00Z", False, "EXACT TIE fires"),
    # …and the tie in the other spelling order, so neither is special-cased
    ("2026-08-21T00:00:00Z", "2026-08-21T00:00:00+00:00", False, "tie, swapped"),
    # a NON-UTC offset must be normalised, not compared as text: 23:00-01:00 is
    # 2026-08-21T00:00:00Z ⇒ an exact tie ⇒ FIRES, though '2026-08-20…' < '2026-08-21…'
    ("2026-08-20T23:00:00-01:00", "2026-08-21T00:00:00Z", False,
     "offset normalised to a tie"),
])
def test_gate_smoke_ordering_clause_across_iso_spellings(smoke_utc, earliest,
                                                         want_ok, why):
    """DESIGN §9.2: *"`smoke_utc` >= the earliest real-cell record ⇒ FIRES."*"""
    want = A.expected_production_knobs()
    base = {"worker_secs_per_game": 500.0, "production_knobs": want}
    ok, d = A.gate_smoke(dict(base, smoke_utc=smoke_utc), cells_ran=True,
                         expected_knobs=want, earliest_cell_record_utc=earliest)
    c1 = d["conjunct1_production_knobs_before_game_1"]
    assert c1["ordering_ok"] is want_ok, f"{why}: {c1['ordering_why']}"
    assert ok is want_ok
    assert c1["smoke_utc_parsed"] is not None


#: The b64 cell's two real smoke cell dirs, as `aggregate_smoke` takes them.
_B64_SMOKE_DIRS = {
    LO: str(_B64_SHARE / "smoke" / "smoke_b64_NARROW_B16J4_deploy11008"),
    HI: str(_B64_SHARE / "smoke" / "smoke_b64_WIDE_B64J4_deploy11008"),
}


@needs_b64_smoke
def test_g_smoke_conjunct1_emitter_to_gate_round_trip_on_real_artifacts():
    """⭐ REVIEW R2 finding N4 — THE ROUND TRIP, on real manifests.

    The previous positive case fed `expected_production_knobs()` back in as the
    OBSERVED dict, which proves the comparator and nothing else. This drives the
    gate with what `_production_knobs_from_manifest` + `aggregate_smoke` ACTUALLY
    emit, so a drift in one manifest address or one type is caught here instead
    of firing `G-SMOKE` on a healthy 6,000-game run.
    """
    doc = A.aggregate_smoke(_B64_SMOKE_DIRS, band=A.SMOKE_BAND, out_path=None)
    obs = doc["production_knobs"]
    want = A.expected_production_knobs()
    # every field the pair names is actually emitted
    assert set(obs) == set(A.PRODUCTION_KNOB_FIELDS)
    # ⭐ the 11 SHAPE/BUDGET fields must agree exactly — that is the drift class
    shape_fields = [f for f in A.PRODUCTION_KNOB_FIELDS
                    if f != "cand_tiearb_per_cell"]
    mismatched = {f: (want[f], obs[f]) for f in shape_fields if obs[f] != want[f]}
    assert not mismatched, f"emitter/expectation drift: {mismatched}"
    # …and none of them is a silent None
    assert all(obs[f] is not None for f in shape_fields)


@needs_b64_smoke
def test_g_smoke_conjunct1_fires_on_a_foreign_cells_arbiter_width():
    """⚠️ The b64 cell ran `B` ∈ {64, 16}; THIS cell commits {64, 32}. The round
    trip must therefore FIRE on `cand_tiearb_per_cell` — and on nothing else.

    ⛔ REPORTED: REVIEW R2's N4 states it ran this round trip and saw
    `MISMATCHED = NONE`. That does not reproduce — the low cell's `B` is 16
    against a committed 32, which is a REAL and CORRECT mismatch. The conjunct
    doing its job on a foreign cell's knobs is the finding, and it is pinned here
    rather than smoothed over."""
    doc = A.aggregate_smoke(_B64_SMOKE_DIRS, band=A.SMOKE_BAND, out_path=None)
    want = A.expected_production_knobs()
    ok, d = A.gate_smoke(doc, cells_ran=False, expected_knobs=want)
    c1 = d["conjunct1_production_knobs_before_game_1"]
    assert ok is False
    assert set(c1["mismatched"]) == {"cand_tiearb_per_cell"}
    assert c1["mismatched"]["cand_tiearb_per_cell"]["observed"][LO]["B"] == 16
    assert c1["mismatched"]["cand_tiearb_per_cell"]["expected"][LO]["B"] == 32


@needs_b64_smoke
def test_g_smoke_conjunct1_round_trip_PASSES_on_this_cells_own_widths(tmp_path):
    """The completing half: the same REAL manifests with only the low cell's
    arbiter width moved to this cell's committed 32 ⇒ the conjunct passes
    end-to-end, emitter output to gate verdict, with nothing echoed back."""
    dirs = {}
    for cell, src in _B64_SMOKE_DIRS.items():
        dst = tmp_path / cell
        dst.mkdir()
        for p in Path(src).glob("seed*.json"):
            (dst / p.name).write_text(p.read_text())
        man = json.loads((Path(src) / "manifest.json").read_text())
        if cell == LO:                      # 16 → this cell's committed 32
            man["cand_tiearb"]["B"] = 32
            man["config"]["cand_tiearb"]["B"] = 32
        (dst / "manifest.json").write_text(json.dumps(man))
        (dst / "summary.json").write_text(
            (Path(src) / "summary.json").read_text())
        dirs[cell] = str(dst)
    doc = A.aggregate_smoke(dirs, band=A.SMOKE_BAND, out_path=None)
    want = A.expected_production_knobs()
    ok, d = A.gate_smoke(doc, cells_ran=False, expected_knobs=want,
                         earliest_cell_record_utc="2027-01-01T00:00:00Z")
    c1 = d["conjunct1_production_knobs_before_game_1"]
    assert c1["mismatched"] == {}, c1["mismatched"]
    assert c1["ordering_ok"] is True
    assert c1["ok"] is True and ok is True
    # the emitted smoke_utc came off the REAL manifest, in its own spelling
    assert doc["smoke_utc"].endswith("+00:00")


def test_ordering_clause_fails_closed_on_an_unparseable_timestamp():
    """⛔ A timestamp nobody can read is not a pass."""
    want = A.expected_production_knobs()
    base = {"worker_secs_per_game": 500.0, "production_knobs": want}
    for bad in ("not-a-date", "", None, 20260821):
        ok, d = A.gate_smoke(dict(base, smoke_utc=bad), cells_ran=True,
                             expected_knobs=want,
                             earliest_cell_record_utc="2026-08-21T00:00:00Z")
        assert ok is False
        c1 = d["conjunct1_production_knobs_before_game_1"]
        # an absent smoke_utc trips the presence check; a junk one trips ordering
        assert c1.get("ordering_ok") is False or c1["ok"] is False


@pytest.mark.parametrize("s,expect", [
    ("2026-08-20T04:43:46+00:00", "2026-08-20T04:43:46+00:00"),
    ("2026-08-20T04:43:46Z", "2026-08-20T04:43:46+00:00"),
    ("2026-08-20T04:43:46", "2026-08-20T04:43:46+00:00"),      # naive ⇒ UTC
    ("2026-08-20T05:43:46+01:00", "2026-08-20T04:43:46+00:00"),
])
def test_parse_utc_normalises_every_spelling_the_emitters_use(s, expect):
    assert A._parse_utc(s).isoformat() == expect


@pytest.mark.parametrize("bad", ["", "   ", None, 17, "yesterday", "2026-13-01"])
def test_parse_utc_returns_none_rather_than_guessing(bad):
    assert A._parse_utc(bad) is None


def test_the_two_emitters_really_do_disagree_on_spelling(tmp_path):
    """⭐ The PREMISE of N3, asserted so the normalisation cannot be dropped as
    'unnecessary' later: a REAL manifest's `utc_end` is offset-form while
    `_earliest_record_utc` emits `Z`-form."""
    man = json.loads((_B64_SHARE / "smoke" /
                      "smoke_b64_WIDE_B64J4_deploy11008" /
                      "manifest.json").read_text()) if _B64_SMOKE_PRESENT else None
    if man is not None:
        assert man["utc_end"].endswith("+00:00"), "the harness writes offset form"
    (tmp_path / "seed1_a0.json").write_text("{}")
    assert A._earliest_record_utc([tmp_path]).endswith("Z")


def test_smoke_cost_definition_is_the_pairs_own_equation_not_wall_times_W():
    assert "SUM(seed*.json::elapsed_s) / n" in A.WORKER_SECS_DEFINITION
    assert "NEVER wall x W / n" in A.WORKER_SECS_DEFINITION


def test_aggregate_smoke_refuses_a_cell_with_no_records(tmp_path):
    """⚠️ FAIL-LOUD: `elapsed_s` over the records IS the cost basis; a cell with
    none must never be reported as zero."""
    lo, hi = tmp_path / "lo", tmp_path / "hi"
    lo.mkdir(), hi.mkdir()
    (lo / "seed1_a0.json").write_text(json.dumps({"elapsed_s": 10.0}))
    with pytest.raises(SystemExit) as e:
        A.aggregate_smoke({LO: str(lo), HI: str(hi)}, out_path=None)
    assert "NO per-game records" in str(e.value)


def test_aggregate_smoke_computes_sum_elapsed_over_n_and_declares_throwaway(tmp_path):
    lo, hi = tmp_path / "lo", tmp_path / "hi"
    lo.mkdir(), hi.mkdir()
    for d, vals in ((lo, (10.0, 20.0)), (hi, (30.0, 50.0))):
        for i, v in enumerate(vals):
            (d / f"seed{i}_a0.json").write_text(
                json.dumps({"elapsed_s": v, "diff": 3.0, "seed": i, "a_seat": 0}))
    doc = A.aggregate_smoke({LO: str(lo), HI: str(hi)}, band=A.SMOKE_BAND,
                            out_path=str(tmp_path / "SMOKE.json"))
    assert doc["_cells"][LO]["worker_secs_per_game"] == pytest.approx(15.0)
    assert doc["_cells"][HI]["worker_secs_per_game"] == pytest.approx(40.0)
    # §9.3 grades CELL_B64 — the top level carries the GRADED cell
    assert doc["worker_secs_per_game"] == pytest.approx(40.0)
    # §9.1's condition of acceptance
    assert doc["band_tier"] == "throwaway"
    assert doc["band_registry_claimed"] is False
    assert doc["band_seed_start"] == A.SMOKE_BAND
    # ⛔ no outcome key survived the per-game records into the artifact
    assert A.smoke_outcome_scan(doc) == []
    assert A.smoke_whitelist_check(doc)["ok"] is True


# --------------------------------------------------------------------------- #
# 9. the committed constants block — parameterization AND the shipped value    #
# --------------------------------------------------------------------------- #
def test_the_shipped_committed_block_is_one_sided_at_0_93():
    """⭐ OWNER RULING 2026-08-21 — "One-sided ±15". A silent edit to the conf must
    show up HERE as a test failure, not as a changed verdict."""
    cfg = A.load_equiv_config()
    assert cfg["tolerance_pts"] == 0.93
    assert cfg["equiv_shape"] == "one_sided"
    assert cfg["source"].endswith("b32v64_cell/WORKERS.conf")


def test_changing_the_two_committed_lines_changes_the_verdict_with_no_code_edit(
        tmp_path):
    """⭐ THE PARAMETERIZATION REQUIREMENT, tested end-to-end through the FILE."""
    D, se = -0.3, 0.5           # z_D = -0.6: one_sided EQUIV, two_sided not
    for shape, want in (("one_sided", "L-SATURATED"),
                        ("two_sided", "L-AMBIGUOUS")):
        p = tmp_path / f"WORKERS_{shape}.conf"
        p.write_text(f"# a committed constants block\nTOLERANCE_PTS=0.93\n"
                     f"EQUIV_SHAPE={shape}\nW_LOCAL=30\n")
        cfg = A.load_equiv_config(p)
        assert cfg["equiv_shape"] == shape
        assert _decide(D / se, D, se, cfg) == want
    # and the TOLERANCE alone flips it too, with the shape held fixed
    p = tmp_path / "WORKERS_tight.conf"
    p.write_text("TOLERANCE_PTS=0.10\nEQUIV_SHAPE=one_sided\n")
    cfg = A.load_equiv_config(p)
    assert cfg["tolerance_pts"] == 0.10
    assert _decide(D / se, D, se, cfg) == "L-AMBIGUOUS"


@pytest.mark.parametrize("body,why", [
    ("EQUIV_SHAPE=one_sided\n", "TOLERANCE_PTS"),
    ("TOLERANCE_PTS=0.93\n", "EQUIV_SHAPE"),
    ("TOLERANCE_PTS=abc\nEQUIV_SHAPE=one_sided\n", "not a number"),
    ("TOLERANCE_PTS=0\nEQUIV_SHAPE=one_sided\n", "finite positive"),
    ("TOLERANCE_PTS=-1\nEQUIV_SHAPE=one_sided\n", "finite positive"),
    ("TOLERANCE_PTS=0.93\nEQUIV_SHAPE=three_sided\n", "supported vocabulary"),
    ("TOLERANCE_PTS=0.93\nEQUIV_SHAPE=TWO_SIDED\n", "supported vocabulary"),
])
def test_equiv_config_is_fail_closed_with_no_coerced_default(tmp_path, body, why):
    """⛔ An absent, unparseable or out-of-vocabulary value is a REFUSAL. Silently
    substituting 0.93/two_sided would make the committed block decorative."""
    p = tmp_path / "WORKERS.conf"
    p.write_text(body)
    with pytest.raises(SystemExit) as e:
        A.load_equiv_config(p)
    assert why in str(e.value)


def test_equiv_config_refuses_an_absent_file(tmp_path):
    with pytest.raises(SystemExit) as e:
        A.load_equiv_config(tmp_path / "nope.conf")
    assert "absent" in str(e.value)


def test_workers_conf_parser_ignores_comments_and_does_not_execute_shell(tmp_path):
    p = tmp_path / "WORKERS.conf"
    p.write_text("# comment\n\nexport TOLERANCE_PTS=0.93   # trailing note\n"
                 "EQUIV_SHAPE=\"one_sided\"\nRUST_TOOLCHAIN=\n"
                 "EVIL=$(touch /tmp/should_not_exist)\n")
    conf = A.parse_workers_conf(p)
    assert conf["TOLERANCE_PTS"] == "0.93"
    assert conf["EQUIV_SHAPE"] == "one_sided"
    assert conf["RUST_TOOLCHAIN"] == ""
    assert not Path("/tmp/should_not_exist").exists()


def test_cost_is_a_branch_input_nowhere():
    """⛔ READ_RULE §4.2 — there is NO affordability predicate in this pair."""
    src = (TILETIE / "analyze_b32v64_cell.py").read_text()
    assert "def affordability" not in src
    assert "OWNER_WAIVER" not in src.replace("OWNER_WAIVER.md machinery", "")
    # the branch decision takes NO cost argument
    import inspect
    params = list(inspect.signature(A.decide_branch).parameters)
    assert params == ["z_D", "D", "se_D", "preconditions", "equiv_cfg"]


# --------------------------------------------------------------------------- #
# 10. the `D` block, the power arithmetic and the supply conversions           #
# --------------------------------------------------------------------------- #
def test_d_block_is_M64_minus_M32_with_ci90():
    hi = {i: 2.0 for i in range(10)}
    lo = {i: 1.0 for i in range(10)}
    db = A.d_block(hi, lo, _cfg("one_sided"))
    assert db["D"] == pytest.approx(1.0)
    assert db["n_common"] == 10
    assert db["se_D"] == pytest.approx(0.0)      # a constant difference
    assert db["CI90"] == [pytest.approx(1.0), pytest.approx(1.0)]


def test_ci90_uses_1_645_and_refuses_a_half_formed_interval():
    assert A.ci90(1.0, 0.5) == (pytest.approx(1.0 - 1.645 * 0.5),
                                pytest.approx(1.0 + 1.645 * 0.5))
    assert A.ci90(None, 0.5) == (None, None)
    assert A.ci90(1.0, NAN) == (None, None)


def test_n_for_equivalence_returns_none_when_no_n_can_resolve_it():
    """⛔ A finite promise where the point estimate already exceeds the tolerance
    would be a lie."""
    cfg = _cfg("one_sided")
    out = A.n_for_equivalence(1500, 1.5, 0.5, cfg)
    assert out["decks_per_cell"] is None
    assert out["no_n_resolves_it"] is True
    assert "NO n RESOLVES IT" in out["why"]
    assert "SHRINKING se_D CANNOT HELP" in out["why"]
    # a reachable case returns decks, games AND two-box wall-hours
    out = A.n_for_equivalence(1500, 0.20, 0.50, cfg)
    assert out["decks_per_cell"] > 0
    assert out["games_per_cell"] == 2 * out["decks_per_cell"]
    assert out["games_total"] == 4 * out["decks_per_cell"]
    assert out["two_box_wall_hours"] > 0
    assert out["effective_pool_workers"] == A.EFFECTIVE_POOL_WORKERS


def test_supply_conversion_reproduces_the_committed_wall():
    """§7.5: 1,500 decks/cell ⇒ ≈1,256 worker-h ⇒ ≈35.3 h of two-box wall."""
    s = A._supply_from_decks(1500)
    assert s["games_per_cell"] == 3000
    assert s["games_total"] == 6000
    assert s["worker_hours"] == pytest.approx(A.WORKER_H_COMMITTED, abs=0.5)
    assert s["two_box_wall_hours"] == pytest.approx(A.WALL_COMMITTED_H, abs=0.1)


#: ⭐ REVIEW R1 finding B4. This assertion used to read `== 0.158` FLAT — the
#: SUPERSEDED two-sided figure — so the suite ENFORCED the drafted constant and
#: fixing the adjudicator would have turned a green test red. It is now keyed to
#: the shape, exactly like the constants it checks, and it carries the pair's
#: ONE-SIDED figures for the ruled shape.
POWER_EXPECTED = {
    "one_sided": {"raw": 0.5788, "l_rev": 0.0228, "eff": 0.5560,
                  "eff_proj": 0.6290, "bracket_top": 0.4459,
                  "n80": 2728, "n80_proj": 2240, "modal": "L-SATURATED"},
    "two_sided": {"raw": 0.158, "l_rev": 0.0, "eff": 0.158,
                  "eff_proj": 0.304, "bracket_top": 0.150,
                  "n80": 3779, "n80_proj": 3102, "modal": "L-AMBIGUOUS"},
}


@pytest.mark.parametrize("shape", ["two_sided", "one_sided"])
def test_power_block_carries_the_pre_run_figures_FOR_ITS_SHAPE(shape):
    e = POWER_EXPECTED[shape]
    pb = A.power_block(_cfg(shape), se_D_realized=0.45)["pre_run"]
    assert pb["P_L_SATURATED_at_true_D_zero_RAW"] == e["raw"]
    assert pb["P_L_REVERSED_mass"] == e["l_rev"]
    assert pb["P_L_SATURATED_at_true_D_zero_EFFECTIVE"] == e["eff"]
    assert pb["P_L_SATURATED_at_true_D_zero_EFFECTIVE_realized_projection"] \
        == e["eff_proj"]
    assert pb["P_at_bracket_top_EFFECTIVE"] == e["bracket_top"]
    assert pb["n_for_80pct_power_committed_law"] == e["n80"]
    assert pb["n_for_80pct_power_realized_law"] == e["n80_proj"]
    assert pb["modal_pre_run_expectation"] == e["modal"]
    assert pb["se_D_committed"] == 0.5044
    assert A.power_block(_cfg(shape), se_D_realized=0.45)["realized"][
        "saturated_window_at_realized_se"] == pytest.approx(0.93 - 1.645 * 0.45)


@pytest.mark.parametrize("shape", ["two_sided", "one_sided"])
def test_reachable_set_power_matches_the_power_block(shape):
    """⛔ B3 — the pre-run power STATEMENT is printed on EVERY branch from two
    places (`reachable_branches` and `power_block`). They must not diverge."""
    rs = A.reachable_branches(_cfg(shape))
    pb = A.power_block(_cfg(shape))
    assert rs["power_statement"] == pb["statement"]
    assert (rs["power_at_true_D_zero_committed"]
            == pb["pre_run"]["P_L_SATURATED_at_true_D_zero_EFFECTIVE"])
    assert rs["modal_pre_run_expectation"] == POWER_EXPECTED[shape]["modal"]


def test_one_sided_power_statement_states_the_RULED_figures_not_the_drafted():
    """⛔ B3's exact defect: a surface stating the two-sided form AS CURRENT."""
    s = A.reachable_branches(_cfg("one_sided"))["power_statement"]
    assert "~56%" in s and "~63%" in s
    assert "~44%" in s
    # the drafted figures may appear ONLY as the WAS side of the ruling diff
    assert "up from ~16% (~30%)" in s
    assert "~70–84%" not in s


def test_power_constants_refuse_an_unknown_shape():
    with pytest.raises(SystemExit) as e:
        A.power_constants({"equiv_shape": "three_sided"})
    assert "power constants" in str(e.value)


# --------------------------------------------------------------------------- #
# 11. the structural nest witness now LIVES HERE, and gate_nest is repointed   #
# --------------------------------------------------------------------------- #
def test_nest_witness_lives_in_this_cells_adjudicator_and_reads_the_source():
    w = A.nest_witness()
    assert set(w["sites"]) == {"world_seed", "playout_seed", "build_arms_cap",
                               "select_stream"}
    assert w["witness"] is True
    for s in w["sites"].values():
        assert s["found"] and s["b_free"]


def test_gate_nest_py_imports_from_this_module_not_the_spent_b64_tool():
    """DESIGN §13.2 item 7's own stated resolution, discharged."""
    src = (CELL_DIR / "gate_nest.py").read_text()
    assert "import analyze_b32v64_cell" in src
    assert "import analyze_b64_cell" not in src


def test_analyze_b64_cell_is_untouched_and_still_owns_its_own_witness():
    """⛔ The spent run's tool is NOT modified: the function was COPIED."""
    b64 = pytest.importorskip("analyze_b64_cell")
    assert callable(b64.nest_witness)
    assert b64.nest_witness is not A.nest_witness


# --------------------------------------------------------------------------- #
# 12. the known-good partition — the launch precondition itself                #
# --------------------------------------------------------------------------- #
def test_resolve_preflights_defaults_to_the_four_named_addresses(tmp_path):
    """⛔ B7 / READ_RULE §2.2 — the adjudicator resolves the four NAMED addresses
    itself rather than accepting a caller-supplied glob."""
    v = tmp_path / "verdicts"
    v.mkdir()
    for host in A.EXPECT_HOSTS:
        for b in (64, 32):
            (v / f"PREFLIGHT_{host}_FIRST_B{b}.json").write_text(
                json.dumps(_pf(host, b)))
            # a SUPERSEDED rotation from an earlier wheel epoch, beside it
            rot = _pf(host, b)
            rot["carc_rs_build"] = "carc_rs-0.1.0+0000pre0build+rustcunpinned"
            (v / f"PREFLIGHT_{host}_FIRST_B{b}_1787174832.json").write_text(
                json.dumps(rot))
    named, superseded, res = A.resolve_preflights(None, v)
    assert len(named) == 4 and len(superseded) == 4
    assert res["mode"].startswith("RESOLVED")
    # ⭐ THE FAILURE THE REVIEW DEMONSTRATED: the glob would fail a healthy run
    pre_named = S2_load(named)
    assert A.gate_tool(pre_named)[0] is True
    pre_glob = S2_load(sorted(v.glob("PREFLIGHT_*_FIRST_B*.json")))
    assert A.gate_tool(pre_glob)[0] is False, (
        "the glob must be the thing that fails — otherwise this test is not "
        "demonstrating what named_preflights protects against")
    # and the supersession is RECORDED, never silently dropped
    assert all(r["status"].startswith("SUPERSEDED") for r in superseded)


def S2_load(paths):
    import analyze_tiearb2_stage2 as S2
    return S2.load_preflights([str(p) for p in paths])


def test_resolve_preflights_refuses_a_supplied_rotation(tmp_path):
    """⛔ A supplied path is never SILENTLY dropped — the operator is told."""
    v = tmp_path / "verdicts"
    v.mkdir()
    rot = v / "PREFLIGHT_Doctor_FIRST_B64_1787174832.json"
    rot.write_text(json.dumps(_pf("Doctor", 64)))
    with pytest.raises(SystemExit) as e:
        A.resolve_preflights([str(rot)], v)
    msg = str(e.value)
    assert "SUPERSEDED ROTATION" in msg
    assert "PREFLIGHT_Doctor_FIRST_B64.json" in msg, "name the address to use"
    assert "will not silently drop" in msg


def test_resolve_preflights_accepts_supplied_named_addresses(tmp_path):
    v = tmp_path / "verdicts"
    v.mkdir()
    paths = []
    for host in A.EXPECT_HOSTS:
        for b in (64, 32):
            p = v / f"PREFLIGHT_{host}_FIRST_B{b}.json"
            p.write_text(json.dumps(_pf(host, b)))
            paths.append(str(p))
    named, _sup, res = A.resolve_preflights(paths, v)
    assert len(named) == 4
    assert res["mode"].startswith("SUPPLIED")


# --------------------------------------------------------------------------- #
# 12b. END-TO-END on a fully synthetic, GATE-CLEAN run                          #
# --------------------------------------------------------------------------- #
def test_synthetic_run_passes_all_thirteen_gates(tmp_path):
    """The control for every render assertion below: if the synthetic run did not
    clear §3, the read-out under test would be a `U-UNREADABLE` stub."""
    v = _synthetic_readout(tmp=tmp_path)
    assert v["gates_failed"] == [], v["gates_failed"]
    assert v["gates_all_pass"] is True
    assert v["n_gates"] == 13


def test_ub95_is_the_rendered_PRIMARY_and_ci90_is_demoted(tmp_path):
    """⛔ B5 — `UB95(D)` was emitted NOWHERE and `CI90(D)` was printed, bolded, in
    its place. `grep UB95` returned zero hits in 2,468 lines."""
    v = _synthetic_readout(D=-0.35, se_D=0.49, tmp=tmp_path)
    assert v["D_block"]["UB95"] == pytest.approx(-0.35 + 1.645 * 0.49, abs=1e-6)
    assert v["D_block"]["UB95_label"] == A.UB95_LABEL
    md = A.render(v)
    # the PRIMARY is bolded and named
    assert f"**`UB95(D)` = " in md
    assert A.UB95_LABEL in md
    # CI90 survives ONLY as context — never bolded as the headline interval
    assert "**`CI90(D)` = [" not in md
    assert "`CI90(D)` = [" in md


def test_render_emits_every_mandatory_4_3_item(tmp_path):
    """⛔ R5 — item 1, item 4, item 6's REALIZED values, item 7 and item 13 were
    all JSON-only. The markdown read-out is what a human reads."""
    v = _synthetic_readout(tmp=tmp_path)
    md = A.render(v)
    # item 1 — both cells, in full
    assert "§4.3 item 1 — both cells" in md
    for probe in ("`paired_z`", "W / D / L", "seat balance", "elo ±1σ", "`wr_z`"):
        assert probe in md, f"item 1 is missing {probe}"
    # item 2 — the D block with UB95 leading
    assert "§4.3 item 2" in md and "UB95(D)" in md
    # item 3 — divergence
    assert "§4.3 item 3" in md
    # item 4 — phi
    assert "§4.3 item 4 — the `phi` block" in md
    assert "phi_effective" in md and "cross-cell `phi` difference" in md
    # item 6 — every gate WITH ITS REALIZED VALUE
    assert "with their REALIZED" in md
    assert "| gate | scope | marker | ok | realized |" in md
    for g in ALL_GATES:
        assert f"| `{g}` |" in md
    # RULING 4's filenames-consumed condition
    assert "the exact filenames consumed, per host" in md
    assert "j13_witness.B" in md
    # item 7 — the failed-record accounting in full
    assert "§4.3 item 7" in md
    for probe in ("`failed_cells[]`", "`resolved_failed_cells[]`",
                  "`validity_trigger_fired`", "`tiearb_partial_argmax_total`"):
        assert probe in md, f"item 7 is missing {probe}"
    assert "REPORT ONLY" in md
    # items 12-13 — the band and the blind-commit ordering
    assert "§4.3 items 12–13" in md
    assert "blind commit: `0123456789abcdef`" in md
    assert "SAME commit before game 1" in md


def test_render_prints_the_gate_realized_values_not_just_pass_fail(tmp_path):
    v = _synthetic_readout(tmp=tmp_path)
    md = A.render(v)
    # a spot-check that the realized column carries actual numbers
    assert "1−f0=" in md
    assert "n_common=1200 decks" in md
    assert f"F_{HI}=0" in md


def test_end_to_end_halt_makes_G_SMOKE_fire_when_the_cells_ran(tmp_path):
    """⛔ B6's failure scenario, end to end: a 1.2x overrun, the cells launched
    anyway, and NOBODY passes a flag. The gate must still fire."""
    v = _synthetic_readout(halt=True, tmp=tmp_path)
    gs = v["gates"]["G-SMOKE"]
    assert gs["detail"]["halted"] is True
    assert gs["detail"]["cells_ran"] is True
    assert gs["detail"]["launched_anyway"] is True
    assert gs["ok"] is False
    assert v["branch"] == "U-UNREADABLE"
    assert "G-SMOKE" in v["gates_failed"]


def test_end_to_end_underrun_does_not_fire_G_SMOKE(tmp_path):
    v = _synthetic_readout(halt=False, tmp=tmp_path)
    assert v["gates"]["G-SMOKE"]["ok"] is True
    assert v["gates"]["G-SMOKE"]["detail"]["halted"] is False


def test_smoke_check_writes_the_halt_record_and_exits_nonzero_on_halt(tmp_path):
    """⛔ DESIGN §9.3.1's WRITER row: `halt` is IN THE EXIT CONDITION."""
    want = A.expected_production_knobs()
    for realized, expect_halt, expect_rc in (
            (A.SMOKE_HALT_BAR * 0.5, False, 0),
            (A.SMOKE_HALT_BAR * 1.2, True, 1)):
        sp = tmp_path / f"SMOKE_{expect_halt}.json"
        sp.write_text(json.dumps({"worker_secs_per_game": realized,
                                  "production_knobs": want,
                                  "smoke_utc": "2020-01-01T00:00:00Z"}))
        hp = tmp_path / f"HALT_{expect_halt}.json"
        rc = A.main(["smoke-check", "--smoke", str(sp), "--halt-out", str(hp)])
        assert rc == expect_rc
        rec = json.loads(hp.read_text())
        assert rec["halt"] is expect_halt
        assert rec["realized"] == pytest.approx(realized)
        assert rec["bar"] == pytest.approx(A.SMOKE_HALT_BAR)


def test_run_cells_sh_reads_the_halt_record_and_has_no_override_flag():
    """⛔ DESIGN §9.3.1's ENFORCER row."""
    src = (CELL_DIR / "run_cells.sh").read_text()
    assert "require_no_halt" in src
    assert "SMOKE_HALT_RECORD" in src
    assert "NO override flag" in src or "NO OVERRIDE FLAG" in src
    # the enforcer is called on the real-cell path, in STRICT mode (N5)
    assert "|| require_no_halt strict" in src
    # and the conf carries the record's name in ONE place
    conf = A.parse_workers_conf()
    assert conf["SMOKE_HALT_RECORD"] == A.SMOKE_HALT_RECORD


def _run_cells(*args, blind_commit=None, halt_record=None):
    """Run the launcher with a temporarily-patched `BLIND_COMMIT` / halt record,
    always restoring both. Returns `(rc, output)`.

    ⚠️ The launcher resolves `$DIR` from the REPO path, not from `$0`, so it
    cannot be exercised from a copy — the conf and the record are patched in
    place and restored in a `finally`."""
    import subprocess
    conf = CELL_DIR / "WORKERS.conf"
    rec = CELL_DIR / A.SMOKE_HALT_RECORD
    conf_bak, rec_bak = conf.read_text(), (rec.read_text() if rec.is_file()
                                           else None)
    try:
        if blind_commit:
            conf.write_text(conf_bak.replace("BLIND_COMMIT=PENDING",
                                             f"BLIND_COMMIT={blind_commit}"))
        if halt_record is None:
            rec.unlink(missing_ok=True)
        else:
            rec.write_text(json.dumps(halt_record))
        p = subprocess.run([str(CELL_DIR / "run_cells.sh"), *args],
                           capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout + p.stderr
    finally:
        conf.write_text(conf_bak)
        if rec_bak is None:
            rec.unlink(missing_ok=True)
        else:
            rec.write_text(rec_bak)


def test_absent_halt_record_REFUSES_a_real_cell_launch():
    """⛔ REVIEW R2 finding N5 — `[ -f "$rec" ] || return 0` treated "no smoke has
    ever run" as a pass. The adjudicator is fail-closed behind it, so nothing
    could be MIS-adjudicated — but the loss was ~35 two-box wall-hours and 6,000
    games discovered at READ time. KILL QUALITY: refuse the launch."""
    rc, out = _run_cells("local", "--band", "140000000000",
                         blind_commit="deadbeefcafe01", halt_record=None)
    assert rc == 9, out
    assert "NO §9.3 HALT RECORD" in out
    assert "MISSING ADDRESS" in out
    assert A.SMOKE_HALT_RECORD in out, "the missing address must be NAMED"
    assert "NO SMOKE HAS RUN" in out
    assert "--smoke" in out, "tell the executor what to do instead"
    assert not (CELL_DIR / "RUN_LIVE.json").exists()


def test_halt_true_refuses_and_halt_false_falls_through_to_the_next_precondition():
    rc, out = _run_cells("local", "--band", "140000000000",
                         blind_commit="deadbeefcafe01",
                         halt_record={"halt": True, "realized": 2100.0,
                                      "bar": A.SMOKE_HALT_BAR})
    assert rc == 9 and "HALT IS IN FORCE" in out
    rc, out = _run_cells("local", "--band", "140000000000",
                         blind_commit="deadbeefcafe01",
                         halt_record={"halt": False, "realized": 800.0,
                                      "bar": A.SMOKE_HALT_BAR})
    # the halt gate lets it through; the NEXT precondition (G-J13) stops it
    assert "HALT IS IN FORCE" not in out and "NO §9.3 HALT RECORD" not in out
    assert "G-J13" in out and rc == 13
    assert not (CELL_DIR / "RUN_LIVE.json").exists()


def test_an_unreadable_halt_record_fails_closed(tmp_path):
    """A corrupt record is not a pass either.

    ⚠️ FIXED (chores queue): this test used to `rec.write_text(...)` straight
    over the TRACKED `SMOKE_HALT.json` fixture with no backup, then
    `rec.unlink()` it in `finally` — losing the real committed halt record
    (CELL_B64's actual §9.3 grading evidence) instead of restoring it, which
    leaves the tree dirty and breaks any `run_cells.sh` invocation between
    test runs that expects the record to exist (`test_absent_halt_record_
    REFUSES_a_real_cell_launch` next to it in this file exists for exactly
    that failure mode). `run_cells.sh` resolves its own `$DIR` from
    `WORKERS.conf`'s hard-coded `REPO_LOCAL`/`REPO_REMOTE` (not from `$0`), so
    the corrupted record still has to land at the REAL path for the
    subprocess to read it — it cannot be redirected to a tmpdir wholesale —
    but the ORIGINAL bytes are now copied to `tmp_path` FIRST and restored
    from there byte-for-byte, so the mutation the real path sees is transient
    and the fixture is never actually lost."""
    conf = CELL_DIR / "WORKERS.conf"
    rec = CELL_DIR / A.SMOKE_HALT_RECORD
    conf_bak = conf.read_text()
    rec_existed = rec.is_file()
    rec_backup = tmp_path / "SMOKE_HALT.json.orig"
    if rec_existed:
        rec_backup.write_bytes(rec.read_bytes())
    import subprocess
    try:
        conf.write_text(conf_bak.replace("BLIND_COMMIT=PENDING",
                                         "BLIND_COMMIT=deadbeefcafe01"))
        rec.write_text("{ not json at all")
        p = subprocess.run([str(CELL_DIR / "run_cells.sh"), "local", "--band",
                            "140000000000"], capture_output=True, text=True,
                           timeout=120)
        assert p.returncode == 9
        assert "HALT IS IN FORCE" in (p.stdout + p.stderr)
    finally:
        conf.write_text(conf_bak)
        if rec_existed:
            rec.write_bytes(rec_backup.read_bytes())
        else:
            rec.unlink(missing_ok=True)


def test_dry_run_is_exempt_from_the_halt_preconditions():
    """A dry run starts no games, so neither the record's absence nor a HALT may
    stop it — and it must still write nothing."""
    rc, out = _run_cells("local", "--dry-run", "--band", "140000000000",
                         halt_record=None)
    assert rc == 0, out
    assert "NO §9.3 HALT RECORD" not in out
    assert not (CELL_DIR / "RUN_LIVE.json").exists()
    assert not (CELL_DIR / A.SMOKE_HALT_RECORD).exists()
    # …but it must SAY that a real cell would be refused, so the dry run is a
    # preview of the launch and not a rosier version of it
    assert "A REAL-CELL LAUNCH WOULD BE REFUSED" in out


def test_workers_conf_prose_is_current():
    """C4 — the conf claimed the adjudicator was NOT YET BUILT."""
    src = (CELL_DIR / "WORKERS.conf").read_text()
    assert "NOT YET BUILT" not in src
    assert "UPPER 90% bound" not in src, "R1 — the drafted wording"


def test_run_cells_sh_prose_is_current():
    """C5 — the launcher claimed the adjudicator was NOT BUILT YET."""
    src = (CELL_DIR / "run_cells.sh").read_text()
    assert "NOT BUILT YET" not in src


KNOWNGOOD = CELL_DIR / "KNOWNGOOD_EVAL.json"


@pytest.mark.skipif(not KNOWNGOOD.is_file(),
                    reason="KNOWNGOOD_EVAL.json not emitted yet")
def test_knowngood_eval_has_no_failing_row_on_a_healthy_run():
    """⭐ *"A gate that fails a healthy run is a drafting defect."*"""
    doc = json.loads(KNOWNGOOD.read_text())
    assert doc["n_rows"] == 13
    assert doc["failed_rows"] == [], doc["failed_rows"]
    assert doc["all_evaluable_rows_pass"] is True
    # every N-A row must be NAMED with a reason, never silently counted
    for g in doc["na_rows"]:
        assert doc["rows"][g]["detail"].get("why")
    # the branch label emitted there is explicitly NOT a re-adjudication
    assert "NOT A VERDICT" in doc["branch_on_known_good_disclaimer"]
    assert "B-COSTKILL" in doc["known_good_verdict_of_record"]


@pytest.mark.skipif(not KNOWNGOOD.is_file(),
                    reason="KNOWNGOOD_EVAL.json not emitted yet")
def test_knowngood_names_partial_conjunct_coverage_so_the_headline_cannot_lie():
    """⛔ REVIEW R2 finding N4, second half. The file promises that machinery
    which cannot be exercised is NAMED and never silently counted as covered —
    a promise kept at ROW granularity while `G-SMOKE`'s scaled conjunct hid
    inside a row-level PASS."""
    doc = json.loads(KNOWNGOOD.read_text())
    partial = doc["rows_with_partial_conjunct_coverage"]
    assert "G-SMOKE" in partial, "the scaled conjunct must be NAMED"
    assert (partial["G-SMOKE"]["conjunct1_production_knobs_before_game_1"]
            == "NOT EVALUATED (scaled)")
    assert "over-state" in doc["coverage_caveat"]
    # every conjunct listed as covered really is EVALUATED, not merely absent
    cov = doc["rows"]["G-SMOKE"]["conjunct_coverage"]
    assert cov["conjunct2_halted_and_launched_anyway"] == "EVALUATED"
    assert cov["conjunct3_forbidden_outcome_keys"] == "EVALUATED"
    # and the row still PASSES — partial coverage is a disclosure, not a failure
    assert doc["rows"]["G-SMOKE"]["status"] == "PASS"


def test_gate_realized_column_reports_conjunct_1(tmp_path):
    """X3 — the newest and most complex conjunct was the one missing from the
    gate table's realized column."""
    v = _synthetic_readout(tmp=tmp_path)
    md = A.render(v)
    assert "knobs/before-game-1=ok" in md


def test_two_sided_power_table_has_no_bare_nulls():
    """X2 — a bare `None` reads as a missing computation; the pair simply never
    quoted that figure for the drafted shape."""
    pb = A.power_block(_cfg("two_sided"))["pre_run"]
    for k, val in pb.items():
        assert val is not None, f"{k} is a bare None"
    assert "not quoted by the pair" in str(pb["P_at_bracket_floor_EFFECTIVE"])
