"""The open-city calibration's BRANCH RULE, tested against ladders it has never seen.

`measurement/opencity_term_20260812/make_calib_readout.py` turns the calibration's
SUMMARY.json into a funding branch by applying CALIB_READ_RULE.md §3 mechanically. That
decision is the one that spends — or refuses to spend — a deck band, so the logic is
pinned here rather than trusted to a reading.

The failure this guards is specific and has a name in this project: choosing the dose
AFTER seeing which arm looks best (the forking path behind four winner's-curse instances
in the 2026-08-10 campaign). Code that decides the branch cannot forking-path; code that
decides it WRONGLY can, silently. Hence: synthetic ladders, expected branches, no real
numbers anywhere in this file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "measurement" / "opencity_term_20260812"))

import make_calib_readout as rd                  # noqa: E402

ARMS, DOSES = rd.ARMS, rd.DOSES


def mk(rates):
    """{(arm, dose): flip_rate} -> the `cells` dict `decide()` consumes."""
    return {rd.cell_name(a, d): {"arm": a, "dose": d,
                                 "size_min": ARMS[a][0], "edge_min": ARMS[a][1],
                                 "flip_rate": rates[(a, d)]}
            for a in ARMS for d in DOSES}


def flat_rates(v):
    return {(a, d): v for a in ARMS for d in DOSES}


# --------------------------------------------------------------------------- #
# Cell naming — a silent lookup miss would drop every dose-2.0 cell            #
# --------------------------------------------------------------------------- #
def test_cell_names_match_the_instrument_exactly():
    """`opencity_e4_replay.DEFAULT_ARM_SPECS` names them `A_d0p5` / `A_d2p0`. A `%g`
    format would produce `A_d2` and quietly miss all three dose-2.0 cells."""
    sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
    import opencity_e4_replay as inst
    instrument_names = {s.split(":")[0] for s in inst.DEFAULT_ARM_SPECS}
    ours = {rd.cell_name(a, d) for a in ARMS for d in DOSES}
    assert ours == instrument_names


# --------------------------------------------------------------------------- #
# Branch 1 — FUND-SMALLEST                                                     #
# --------------------------------------------------------------------------- #
def test_fund_smallest_minimises_dose_then_takes_tightest_predicate():
    """Both A and B clear at the low dose. Dose is minimised FIRST (T is a product of two
    excesses, so dose is the dangerous axis), then the TIGHTEST predicate clearing the bar
    at that dose wins — A (4 tiles) over B (3 tiles), even though B flips more."""
    v = rd.decide(mk({("A", 0.5): .14, ("A", 2.0): .25,
                      ("B", 0.5): .19, ("B", 2.0): .31,
                      ("C", 0.5): .0, ("C", 2.0): .0}))
    assert v["branch"] == "FUND-SMALLEST"
    assert v["chosen_cell"] == "A_d0p5"
    assert v["funded_cells"] == ["A_d0p5", "A_d2p0"]


def test_fund_smallest_prefers_widening_the_predicate_over_raising_the_dose():
    """Only B clears at dose 0.5; A needs dose 2.0. The rule says prefer widening the
    predicate over raising the dose — so B at the LOW dose wins."""
    v = rd.decide(mk({("A", 0.5): .07, ("A", 2.0): .12,
                      ("B", 0.5): .11, ("B", 2.0): .22,
                      ("C", 0.5): .0, ("C", 2.0): .0}))
    assert v["chosen_cell"] == "B_d0p5"
    assert v["funded_cells"] == ["B_d0p5", "B_d2p0"]


def test_fund_smallest_adds_the_dose_below_only_when_it_clears_the_floor():
    """"plus one dose above and (if it also clears 0.05) one below"."""
    clears = rd.decide(mk({("A", 0.5): .06, ("A", 2.0): .13,
                           ("B", 0.5): .04, ("B", 2.0): .09,
                           ("C", 0.5): .0, ("C", 2.0): .0}))
    assert clears["chosen_cell"] == "A_d2p0"
    assert clears["funded_cells"] == ["A_d2p0", "A_d0p5"]        # 0.06 >= floor

    below_floor = rd.decide(mk({("A", 0.5): .01, ("A", 2.0): .13,
                                ("B", 0.5): .01, ("B", 2.0): .09,
                                ("C", 0.5): .0, ("C", 2.0): .0}))
    assert below_floor["funded_cells"] == ["A_d2p0"]              # 0.01 < floor, dropped


def test_fund_smallest_never_funds_more_than_three_cells():
    v = rd.decide(mk({("A", 0.5): .5, ("A", 2.0): .6,
                      ("B", 0.5): .5, ("B", 2.0): .6,
                      ("C", 0.5): .5, ("C", 2.0): .6}))
    assert len(v["funded_cells"]) <= 3


def test_the_bar_is_inclusive_at_exactly_ten_percent():
    v = rd.decide(mk({("A", 0.5): .10, ("A", 2.0): .10,
                      ("B", 0.5): .0, ("B", 2.0): .0,
                      ("C", 0.5): .0, ("C", 2.0): .0}))
    assert v["branch"] == "FUND-SMALLEST"


# --------------------------------------------------------------------------- #
# Branch 2 — FUND-MARGINAL                                                     #
# --------------------------------------------------------------------------- #
def test_fund_marginal_takes_at_most_two_highest_f_cells_and_flags_underpower():
    v = rd.decide(mk({("A", 0.5): .055, ("A", 2.0): .09,
                      ("B", 0.5): .06, ("B", 2.0): .095,
                      ("C", 0.5): .0, ("C", 2.0): .0}))
    assert v["branch"] == "FUND-MARGINAL"
    assert v["funded_cells"] == ["B_d2p0", "A_d2p0"]
    assert v["underpowered_by_construction"] is True
    assert "never as a kill" in v["why"]


# --------------------------------------------------------------------------- #
# Branches 3 / 4 — the resolvable-floor guard. NOTHING is fundable.            #
# --------------------------------------------------------------------------- #
def test_structural_no_fund_when_everything_is_below_floor_and_flat():
    v = rd.decide(mk({("A", 0.5): .01, ("A", 2.0): .02,
                      ("B", 0.5): .02, ("B", 2.0): .03,
                      ("C", 0.5): .01, ("C", 2.0): .02}))
    assert v["branch"] == "STRUCTURAL-NO-FUND"
    assert v["fundable"] is False and v["funded_cells"] == []
    assert v["ladder_flat"] is True


def test_unresolved_when_below_floor_but_the_ladder_is_rising():
    v = rd.decide(mk({("A", 0.5): .005, ("A", 2.0): .01,
                      ("B", 0.5): .02, ("B", 2.0): .04,
                      ("C", 0.5): .001, ("C", 2.0): .002}))
    assert v["branch"] == "UNRESOLVED"
    assert v["fundable"] is False and v["funded_cells"] == []
    assert v["ladder_flat"] is False


def test_arm_C_reading_exactly_zero_is_handled_and_the_ambiguity_is_reported():
    """§3.3's flatness test divides by arm C's best f, and TERM_SPEC §6 predicts arm C
    reads ~0. At B>0, C==0 the ratio is undefined; the rule's own description of branch 4
    ("the ladder is clearly rising as the predicate loosens") is what applies."""
    v = rd.decide(mk({("A", 0.5): .01, ("A", 2.0): .03,
                      ("B", 0.5): .02, ("B", 2.0): .04,
                      ("C", 0.5): .0, ("C", 2.0): .0}))
    assert v["branch"] == "UNRESOLVED"
    assert v["ladder_ambiguity"] and "undefined" in v["ladder_ambiguity"]


def test_a_completely_dead_ladder_is_structural_not_unresolved():
    """0/0 is undefined too, but "nothing expresses anywhere" is the structural finding
    branch 3 exists to record — not a claim that the predicate was too tight."""
    v = rd.decide(mk(flat_rates(0.0)))
    assert v["branch"] == "STRUCTURAL-NO-FUND"
    assert v["ladder_ambiguity"] and "both read EXACTLY 0" in v["ladder_ambiguity"]


@pytest.mark.parametrize("f", [0.0, 0.001, 0.02, 0.0499])
def test_no_dose_is_ever_named_below_the_floor(f):
    """The guard the whole rule exists for: below 5% a cell cannot produce a resolvable
    result at either instrument at affordable n EVEN IF THE TERM IS GENUINELY GOOD. The
    readout must refuse to name a dose rather than pick the best of a bad ladder."""
    v = rd.decide(mk(flat_rates(f)))
    assert v["fundable"] is False
    assert v["funded_cells"] == []
    assert "chosen_cell" not in v


def test_the_floor_is_inclusive_at_exactly_five_percent():
    v = rd.decide(mk(flat_rates(0.05)))
    assert v["branch"] == "FUND-MARGINAL"
    assert v["fundable"] is True


# --------------------------------------------------------------------------- #
# Integrity — a broken replay VOIDS the calibration                            #
# --------------------------------------------------------------------------- #
def _summary(rates, *, replay_ok=True):
    arms = {}
    knobs = {}
    for a in ARMS:
        for d in DOSES:
            n = rd.cell_name(a, d)
            arms[n] = {"flips_total": int(rates[(a, d)] * 1000), "n_graded": 1000,
                       "flip_rate": rates[(a, d)], "wilson95": [0.0, 1.0],
                       "wilson95_half_width": 0.5,
                       "phase_split": {"tiles": 0, "meeples": 0, "other": {},
                                       "tile_share": None}}
            knobs[n] = {"size_min": ARMS[a][0], "edge_min": ARMS[a][1], "dose": d,
                        "symmetric": True, "leaf_hash": f"hash{a}{d}"}
    return {"arms": arms, "arm_knobs": knobs, "n_games": 26, "n_graded_plies": 1000,
            "all_replay_scores_match": replay_ok,
            "replay_scores_mismatch_archives": ([] if replay_ok else ["bad.json"]),
            "rules_profile_histogram": {"fixed_v1": 26},
            "champ_agrees_archive_rate": 0.5}


def test_a_failed_replay_checksum_voids_the_calibration_even_on_a_funding_ladder():
    """CALIB_READ_RULE §1: any archive that fails its replay checksum VOIDS the whole
    calibration. That must override a ladder that would otherwise fund."""
    r = rd.build(_summary(flat_rates(0.30), replay_ok=False))
    assert r["verdict"]["branch"] == "VOID"
    assert r["verdict"]["fundable"] is False
    assert r["verdict"]["funded_cells"] == []


def test_build_refuses_a_ladder_that_is_not_the_preregistered_one():
    s = _summary(flat_rates(0.2))
    s["arms"].pop("C_d2p0")
    s["arm_knobs"].pop("C_d2p0")
    with pytest.raises(SystemExit, match="pre-registered ladder"):
        rd.build(s)
