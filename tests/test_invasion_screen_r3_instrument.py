"""INSTRUMENT TESTS — invasion-risk term family, ROUND-3 fine ladders + joint at 2752.

Pair under test: `measurement/invasion_screen_r3_prep/` (`DESIGN.md` + `READ_RULE.md`),
its bar library `screen_lib.py`, its adjudicator `analyze_screen.py`, and its
launcher `run_cells.sh`.

Adapted from `tests/test_invasion_screen_r2_instrument.py`. The three load-bearing
properties rounds 1 and 2 established are carried verbatim:

1. **BARS LIVE IN ONE IMPLEMENTATION POINT.** Every threshold, weight and cost
   figure is `screen_lib`'s, and the launcher pins only the BAND as a numeric
   literal.
2. **NO SELF-INVALIDATING TESTS.** A test that re-asserts a constant against
   itself proves nothing. So the tests below check RELATIONSHIPS and BEHAVIOUR.
3. **THE ADJUDICATOR IS VALIDATED AGAINST A REAL EMITTED MANIFEST**, never a
   synthesized one — `analyze_screen.py --selftest` must exit 0.

⭐ AND ROUND 3 ADDS THREE MORE, because round 3 added the machinery that needs them:

4. ⭐⭐ **THE JOINT CELLS ARE TESTED AS THE ADOPTION-CHAIN-ELIGIBLE ONES, AND THE
   ATTRIBUTION BAN IS TESTED AS A CONTRACT.** The J cells are the only ones whose
   PROMOTE reaches the four-link chain, so the tests drive `PROMOTE-JOINT`
   end-to-end AND assert that every J branch — including the nulls — carries the
   ban, that the ban names the forbidden inferences explicitly, and that no J
   cell can be silently given a non-champion opponent.

5. ⭐⭐ **THE IS-A1 FOLD IS DRIVEN IN BOTH DIRECTIONS.** Round 2's frozen
   adjudicator falsely voided a healthy round by comparing the two boxes' emitted
   SHORT REVS for string equality. The canonicalized gate must PASS on
   same-commit-different-short-length (round 2's exact case, replayed) and FAIL on
   genuinely different commits — plus fail on disagreeing pins, on an absent pin,
   and on a rev below the 7-hex floor.

6. ⭐ **THE WEIGHT DERIVATION IS TESTED AS ARITHMETIC, NOT AS A TABLE.** Round 3
   is the first round that PICKS weights, so the tests check that the chosen
   ladders actually BRACKET what the derivation says they bracket, that every
   weight sits inside the owner-licensed interval, and that no round-3 weight
   repeats a round-1 or round-2 point.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "invasion_screen_r3_prep"
R2_PREP = REPO / "measurement" / "invasion_screen_r2_prep"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ⚠️ THE LIBRARY IS LOADED UNDER THE **SAME DIRECTORY-QUALIFIED NAME** the
# adjudicator uses, so the test and the adjudicator share ONE module object —
# and so neither collides with a sibling round's `screen_lib.py`. See the banner
# at the top of `analyze_screen.py`: rounds 1, 2 and 3 each ship a file with that
# name, and a bare `import screen_lib` off `sys.path` let whichever loaded first
# win, silently adjudicating one round against another round's bars.
L = _load(f"screen_lib__{PREP.name}", PREP / "screen_lib.py")
A = _load("analyze_screen_r3_under_test", PREP / "analyze_screen.py")
assert A.L is L, "the adjudicator must resolve THIS round's bar library"

_FIXTURE_DIR = PREP / "selftest_fixture"
LAUNCHER = (PREP / "run_cells.sh").read_text()
WORKERS = (PREP / "WORKERS.conf").read_text()


def _conf(key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.*)$", WORKERS, re.M)
    assert m, f"WORKERS.conf has no {key}"
    return m.group(1).split("#")[0].strip()


# ═══════════════════════════════════════════════════════════════════════════ #
# 1. THE SPEC IS INTERNALLY CONSISTENT                                        #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_sanity_check_is_clean():
    problems = L.sanity_check()
    assert problems == [], "\n".join(problems)


def test_cell_ranges_are_disjoint_and_contiguous():
    spans = sorted((c.seed_start, c.seed_end) for c in L.CELLS)
    for (s0, e0), (s1, e1) in zip(spans, spans[1:]):
        assert s1 == e0 + 1, f"gap/overlap: {e0} -> {s1}"
    assert spans[0][0] == L.BAND
    assert spans[-1][1] == L.BAND + 3199, "8 cells x 400 decks = 3200 decks"


def test_eight_cells_three_shapes_and_every_one_is_an_arm():
    assert len(L.CELLS) == 8
    assert L.SHAPES == ("A", "J", "C")
    assert {c.shape for c in L.CELLS} == set(L.SHAPES)
    assert L.ARM_CELLS == L.CELLS, "there is no precondition cell in round 3"
    assert sum(c.n_games for c in L.CELLS) == 6400


def test_shape_b_is_not_a_round_3_shape_but_is_the_c_cells_opponent():
    """⭐ THE DEMOTION, AND THE INSTRUMENT USE, ARE DIFFERENT FACTS."""
    assert "B" not in L.SHAPES
    assert not any(c.knobs == ("invasion_alpha",) for c in L.CELLS), \
        "no round-3 cell is a shape-B CANDIDATE"
    # but every C cell's OPPONENT is exactly the shape-B agent
    for c in L.cells_of_shape("C"):
        assert c.opp_leaf_hash == L.SHAPE_B_LEAF_HASH
        assert c.opp_invasion == {"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0}
    note = L.SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE
    assert "INSTRUMENT" in note and "NOT A CANDIDATE" in note
    assert "noise" in note.lower(), "the demotion's REASON must be stated"


def test_the_shape_b_instrument_is_bit_for_bit_round_1s_and_round_2s():
    """⛔ The C ladders of rounds 2 and 3 must differ in gamma and BAND only."""
    assert L.SHAPE_B_LEAF_HASH == L.R1_MIDS["B"]["cand_leaf_hash"]
    for n in ("C_LOW", "C_MID", "C_HIGH"):
        assert L.R2_CELLS[n]["opponent"] == "shape_b"
    assert L.SHAPE_B_ENV == {"CARCASSONNE_INVASION_ALPHA": "0.09",
                             "CARCASSONNE_INVASION_ALPHA_CAP": "11.0"}


def test_a_and_c_have_three_rungs_and_j_has_two():
    assert [c.rung for c in L.cells_of_shape("A")] == ["low", "mid", "high"]
    assert [c.rung for c in L.cells_of_shape("C")] == ["low", "mid", "high"]
    assert [c.rung for c in L.cells_of_shape("J")] == ["low", "high"]
    assert L.cells_of_rung("J", "mid") is None, "the joint ladder has NO interior"


def test_only_the_joint_cells_are_joint():
    for c in L.CELLS:
        assert c.is_joint == (c.shape == "J")
        assert c.is_joint == (len(c.knobs) == 2)
    assert [c.name for c in L.CELLS if c.is_joint] == ["J_LOW", "J_HIGH"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 2. ⭐⭐ THE JOINT CELLS AND THE ADOPTION CHAIN                                #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_chain_eligibility_is_exactly_having_the_champion_as_opponent():
    """⛔ Chain eligibility is a property of the OPPONENT, never of the reading."""
    for c in L.CELLS:
        assert c.chain_eligible == (c.opp_leaf_hash == L.PROD_LEAF_HASH)
        assert c.chain_eligible == (c.opponent == "champion")
    assert {c.name for c in L.CELLS if c.chain_eligible} == {
        "A_LOW", "A_MID", "A_HIGH", "J_LOW", "J_HIGH"}
    assert {c.name for c in L.CELLS if not c.chain_eligible} == {
        "C_LOW", "C_MID", "C_HIGH"}
    assert set(L.CHAIN_ELIGIBLE_SHAPES) == {"A", "J"}


def test_both_joint_cells_face_the_champion_of_record():
    """⛔ THE SINGLE MOST DAMAGING SILENT ERROR THIS ROUND COULD MAKE would be a J
    cell handed the shape-B opponent: it would license nothing while LOOKING like
    the round's headline result."""
    for c in L.cells_of_shape("J"):
        assert c.opponent == "champion"
        assert c.opp_leaf_hash == L.PROD_LEAF_HASH
        assert c.shape_b_env is False
        assert c.opp_invasion == {}


def test_a_joint_cells_leaf_diff_is_exactly_two_knobs():
    for c in L.cells_of_shape("J"):
        assert set(c.leaf_diff_keys) == {"invasion_beta", "invasion_gamma"}
    for c in L.cells_of_shape("A"):
        assert set(c.leaf_diff_keys) == {"invasion_beta"}
    for c in L.cells_of_shape("C"):
        assert set(c.leaf_diff_keys) == {
            "invasion_alpha", "invasion_alpha_cap", "invasion_gamma"}


def test_round_branch_promote_joint_fires_on_a_joint_cell():
    br = {c.name: "NULL" for c in L.CELLS}
    br["J_HIGH"] = "PROMOTE"
    assert L.round_branch(br) == "PROMOTE-JOINT"


def test_round_branch_lists_both_chain_shapes_in_cell_order_without_duplicates():
    br = {c.name: "NULL" for c in L.CELLS}
    br["A_MID"] = "PROMOTE"
    br["A_HIGH"] = "PROMOTE"
    br["J_LOW"] = "PROMOTE"
    assert L.round_branch(br) == "PROMOTE-A,JOINT", \
        "cell order is A before J, and a shape is listed once"


def test_a_C_promote_never_outranks_a_chain_eligible_promote():
    br = {c.name: "NULL" for c in L.CELLS}
    br["C_MID"] = "PROMOTE"
    assert L.round_branch(br) == "DEFENDS-C"
    br["J_LOW"] = "PROMOTE"
    assert L.round_branch(br) == "PROMOTE-JOINT", \
        "a chain-eligible promote outranks DEFENDS-C"


def test_a_C_cell_can_never_produce_a_promote_label_naming_the_chain():
    """⛔ No arrangement of C readings may yield a PROMOTE-<shape> label."""
    for combo in range(1, 8):
        br = {c.name: "NULL" for c in L.CELLS}
        for i, c in enumerate(L.cells_of_shape("C")):
            if combo >> i & 1:
                br[c.name] = "PROMOTE"
        assert not L.round_branch(br).startswith("PROMOTE-")


def test_every_joint_branch_carries_the_attribution_ban():
    """⭐ INCLUDING THE NULLS — the tempting over-read of a null joint ('so
    neither term works') is the same error in the other direction."""
    for branch in ("PROMOTE", "BRACKET", "REVERSED", "NULL", "U-UNREADABLE"):
        text = L.joint_reading(branch, 0.0)
        assert L.JOINT_ATTRIBUTION_BAN in text, branch


def test_the_attribution_ban_names_the_forbidden_inferences_explicitly():
    ban = L.JOINT_ATTRIBUTION_BAN
    for needle in ("separately", "subtracting", "NULL joint", "SUM",
                   "ABLATION", "FRESH band"):
        assert needle in ban, f"the ban must name {needle!r}"


def test_the_joint_licence_is_one_h2h_of_one_leaf_and_nothing_else():
    lic = L.JOINT_LICENSES
    assert "PROMOTE-JOINT" in lic
    assert "AS ONE LEAF" in lic
    for forbidden in ("Not a PRODUCTION.yaml edit", "not an H2H of either knob alone"):
        assert forbidden in lic
    assert "fresh pair" in lic and "fresh funding decision" in lic


def test_joint_is_not_a_sum_is_stated_and_the_sizing_row_is_labelled_as_such():
    assert "JOINT != SUM OF PARTS" in L.JOINT_IS_NOT_A_SUM
    assert "NOT PREDICTING" in L.JOINT_IS_NOT_A_SUM
    row = next(r for r in L.POWER_TABLE if abs(r["true_effect_pts"] - 1.94) < 1e-9)
    assert "SIZING TARGET, NOT A PREDICTION" in row["note"]
    # and it really is the arithmetic sum of round 2's two BRACKET readings
    s = L.R2_CELLS["A_LOW"]["D"] + L.R2_CELLS["C_LOW"]["D"]
    assert abs(row["true_effect_pts"] - s) < 0.01


def test_the_joint_ladder_endpoint_rule_is_stated_before_any_number():
    r = L.JOINT_ENDPOINT_RULE
    assert "TWO POINTS AND THEREFORE NO INTERIOR" in r
    assert "NOT BRACKETED" in r
    assert "cannot say which knob's dose mattered" in r


# ═══════════════════════════════════════════════════════════════════════════ #
# 3. ⭐ THE WEIGHT DERIVATION, AS ARITHMETIC                                   #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_every_weight_is_inside_the_owner_licensed_interval():
    for c in L.CELLS:
        for k, w in zip(c.knobs, c.weights):
            lo, hi = L.LICENSED_INTERVALS[k]
            assert lo <= w <= hi, f"{c.name}: {k}={w} outside [{lo}, {hi}]"


def test_no_round_3_weight_repeats_a_round_1_or_round_2_point():
    """⛔ Structurally unpoolable with any predecessor."""
    prior_beta = {0.04, 0.12, 0.36}
    prior_gamma = {0.08, 0.23, 0.69}
    for c in L.CELLS:
        for k, w in zip(c.knobs, c.weights):
            prior = prior_beta if k == "invasion_beta" else prior_gamma
            assert w not in prior, f"{c.name}: {k}={w} repeats a prior round's point"


def test_the_A_ladder_brackets_both_the_empirical_best_and_the_fit_peak():
    lo, mid, hi = L.WEIGHT_DERIVATION["A"]["chosen"]
    assert lo < 0.04 < mid, "must bracket round 2's best beta on BOTH sides"
    assert mid < L.A_FIT[3] < hi, "must bracket the local fit's peak on BOTH sides"
    assert L.A_FIT[4], "the A local quadratic must be concave (its vertex a MAXIMUM)"


def test_the_A_fit_passes_through_the_structural_origin_anchor():
    """⭐ D(beta = 0) == 0 EXACTLY, by construction — at weight zero the candidate
    IS the champion, and round 1's IDENT cell measured that identity."""
    c, a, b, _peak, _ = L.A_FIT
    assert abs(c) < 1e-12, "the fit must pass through the origin"
    for beta, d in ((0.04, 0.93625), (0.12, 0.52375)):
        assert abs(a * beta + b * beta * beta - d) < 1e-9


def test_the_C_derivation_reports_TWO_readings_that_disagree():
    """⛔ The honest case: the r2-only interpolation puts the peak AT OR BELOW
    0.08 and the anchored one ABOVE it. The ladder must bracket both."""
    assert not L.C_FIT_R2_ONLY[4], "the r2-only interpolation is CONVEX (vertex a MIN)"
    assert L.C_FIT_R2_ONLY[3] > 0.69, "its vertex lies OUTSIDE the measured range"
    assert L.C_FIT_ANCHORED[4], "the anchored interpolation is CONCAVE (a real peak)"
    assert L.C_FIT_ANCHORED[3] > 0.08, "the anchored peak sits ABOVE round 2's best"
    lo, mid, hi = L.WEIGHT_DERIVATION["C"]["chosen"]
    assert lo < 0.08 < hi
    assert mid < L.C_FIT_ANCHORED[3] < hi


def test_the_C_derivations_weakest_input_is_disclosed_as_such():
    ins = L.WEIGHT_DERIVATION["C"]["inputs"]
    zero = next(i for i in ins if i["gamma"] == 0.0)
    src = zero["source"]
    assert "WEAKEST" in src
    assert "sign" in src.lower() and "flip" in src.lower()
    assert "cross-band" in src.lower() or "Cross-band" in src


def test_both_ladders_are_log_uniform_with_comparable_ratios():
    ra = L.WEIGHT_DERIVATION["A"]["log_ratios"]
    rc = L.WEIGHT_DERIVATION["C"]["log_ratios"]
    for r in ra + rc:
        assert 1.7 < r < 2.7, f"ratio {r} is not in the design's 2.2±0.5 band"


def test_both_ladders_leave_headroom_inside_the_licensed_interval():
    """⭐ So an ENDPOINT peak has somewhere to be extended INTO without re-opening
    the licence."""
    for sh in ("A", "C"):
        d = L.WEIGHT_DERIVATION[sh]
        lo_i, hi_i = d["licensed"]
        chosen = d["chosen"]
        assert lo_i < chosen[0], f"{sh}: no headroom below"
        assert chosen[-1] < hi_i, f"{sh}: no headroom above"
        assert d["headroom_left_for_round_4"] == [(lo_i, chosen[0]),
                                                  (chosen[-1], hi_i)]


def test_the_joint_points_are_rung_matched_to_the_two_fine_ladders():
    for jname, arung, crung in (("J_LOW", "low", "low"), ("J_HIGH", "mid", "mid")):
        j = L.cell_by_name(jname)
        assert j.dose["invasion_beta"] == L.cells_of_rung("A", arung).weights[0]
        assert j.dose["invasion_gamma"] == L.cells_of_rung("C", crung).weights[0]


def test_the_derivation_admits_it_is_a_re_pick_and_says_why():
    why = L.WEIGHT_DERIVATION["why_a_re_pick_at_all"]
    assert "NOT BRACKETED" in why
    assert "endpoint" in why.lower()
    assert "0.36" in why and "REVERSED" in why


def test_the_joint_expectation_about_gamma_is_stated_before_any_number():
    """⭐ Honest pre-registration: gamma was measured against a TUNED invader, and
    its contribution against a champion that merely invades in the ordinary
    course of play should be SMALLER — possibly null, possibly negative."""
    e = L.WEIGHT_DERIVATION["J"]["expectation_stated_before_any_number"]
    assert "SMALLER" in e
    assert "possibly null" in e and "possibly negative" in e
    assert "SIZING TARGET, not a prediction" in e


# ═══════════════════════════════════════════════════════════════════════════ #
# 4. ⭐⭐ THE IS-A1 FOLD — DRIVEN IN BOTH DIRECTIONS                            #
#                                                                             #
# Round 2's FROZEN adjudicator compared the two boxes' EMITTED SHORT REVS for  #
# string equality and falsely voided a healthy single-rev round. These tests   #
# replay round 2's EXACT case and require it to PASS, and require a genuinely  #
# different commit to FAIL.                                                    #
# ═══════════════════════════════════════════════════════════════════════════ #
R2_PIN = "240626a31feeab01e22e73b42230a80a9889ec6f"
BOTH = {"local": R2_PIN, "laptop": R2_PIN}


def test_IS_A1_same_commit_different_short_lengths_PASSES():
    """⭐ ROUND 2's EXACT FALSE VOID, REPLAYED. `git rev-parse --short` picks its
    length PER CLONE, so the two boxes at the IDENTICAL commit emitted
    '240626a3-dirty' and '240626a31f-dirty'. This MUST pass."""
    r = L.cross_box_rev_gate(
        {"C_LOW": "240626a3-dirty", "A_LOW": "240626a31f-dirty"}, BOTH)
    assert r["ok"], r["why"]
    assert r["pin"] == R2_PIN
    assert "IS-A1" in r["why"], "the passing message must name the amendment"


@pytest.mark.parametrize("lens", [(7, 8), (8, 10), (10, 40), (7, 40), (12, 9)])
def test_IS_A1_any_pair_of_valid_short_lengths_passes(lens):
    """The defect was LENGTH-dependent, so the fix is driven across lengths."""
    a, b = lens
    r = L.cross_box_rev_gate(
        {"C_LOW": R2_PIN[:a] + "-dirty", "A_LOW": R2_PIN[:b]}, BOTH)
    assert r["ok"], r["why"]


def test_genuinely_different_commits_FAIL():
    """⛔ THE FIX MUST NOT DEGENERATE INTO 'ANY PREFIX PASSES'."""
    r = L.cross_box_rev_gate(
        {"C_LOW": "240626a3-dirty", "A_LOW": "deadbee1-dirty"}, BOTH)
    assert not r["ok"]
    assert "does NOT name the shared pin" in r["why"]
    assert "A_LOW" in r["why"], "the failing cell must be named"


def test_disagreeing_pins_FAIL_and_the_message_distinguishes_the_two_cases():
    """⭐ THE CONJUNCT THE AMENDMENT SCRIPT DID NOT HAVE: the pins themselves must
    agree. A laptop that was never bundle-synced publishes a different pin."""
    r = L.cross_box_rev_gate({"C_LOW": R2_PIN[:8]},
                             {"local": R2_PIN, "laptop": "de" + R2_PIN[2:]})
    assert not r["ok"]
    assert "DIFFERENT COMMITS" in r["why"]
    assert "NOT THE SHORT REVS" in r["why"], \
        "the message must say what this is NOT, or the next reader repeats IS-A1"


def test_an_absent_pin_is_FAIL_never_a_fallback_to_rev_vs_rev():
    r = L.cross_box_rev_gate({"C_LOW": "240626a3", "A_LOW": "240626a3"}, {})
    assert not r["ok"], "identical revs must NOT rescue an absent pin"
    assert "ABSENT is FAIL" in r["why"]
    assert "forbids falling back to comparing the emitted revs" in r["why"]


def test_a_malformed_pin_is_FAIL():
    r = L.cross_box_rev_gate({"C_LOW": R2_PIN[:8]},
                             {"local": R2_PIN, "laptop": "not-a-sha"})
    assert not r["ok"]


@pytest.mark.parametrize("rev", ["2406", "240626", "", None, "zzzzzzzz", "240626aZ"])
def test_a_rev_below_the_hex_floor_or_not_hex_FAILS(rev):
    r = L.cross_box_rev_gate({"C_LOW": rev}, BOTH)
    assert not r["ok"], f"{rev!r} must not pass"


def test_a_single_box_round_passes_conjunct_one_trivially():
    """The §9 smoke and any single-box run must keep working unchanged."""
    r = L.cross_box_rev_gate({"C_LOW": R2_PIN[:10]}, {"local": R2_PIN})
    assert r["ok"], r["why"]


def test_the_gate_never_compares_two_emitted_revs_to_each_other():
    """⛔ THE STRUCTURAL PROPERTY, not just the behaviour: with a valid shared pin,
    the verdict is a function of each rev SEPARATELY. So a set of revs that all
    canonicalize passes REGARDLESS of how many distinct spellings it contains."""
    many = {f"C{i}": R2_PIN[: 7 + i] for i in range(8)}
    assert len({v for v in many.values()}) == 8, "eight DIFFERENT spellings"
    assert L.cross_box_rev_gate(many, BOTH)["ok"]


def test_rev_matches_is_a_prefix_rule_and_dirt_is_informational():
    ok, why = L.rev_matches(R2_PIN[:8] + "-dirty", R2_PIN)
    assert ok and "INFORMATIONAL" in why
    ok, _ = L.rev_matches("deadbeef", R2_PIN)
    assert not ok


# ═══════════════════════════════════════════════════════════════════════════ #
# 5. ⭐ THE TWO BOXES, W_LOCAL=14, AND THE SPLIT                               #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_w_local_is_fourteen_and_frozen_for_the_whole_round():
    assert L.BOXES["local"]["W"] == 14
    assert L.BOXES["laptop"]["W"] == 22
    assert int(_conf("W_LOCAL")) == 14
    assert int(_conf("W_LAPTOP")) == 22
    note = L.W_LOCAL_NOTE
    assert "limit local to w14 starting at 11am" in note, "the owner's words, verbatim"
    assert "NOT 22-then-14" in note
    assert "MOVES NO BAR" in note


def test_the_launcher_never_changes_W_mid_round():
    """⛔ `--workers` is emitted from ONE place — `build_argv`'s resolved per-box W —
    so a cell's passes cannot run at two different worker counts."""
    argv_lines = [ln for ln in LAUNCHER.splitlines()
                  if "--workers" in ln and not ln.strip().startswith("#")
                  and "log " not in ln and "print(" not in ln]
    assert len(argv_lines) == 1, argv_lines
    assert re.search(r'--workers "\$w"', argv_lines[0]), \
        "the launcher must pass the resolved per-box W, never a literal"
    # and W is resolved exactly once, from --host, before any cell table exists
    assert LAUNCHER.count('W="$W_LOCAL"') == 1
    assert LAUNCHER.count('W="$W_LAPTOP"') == 1
    # ⛔ no time-of-day logic anywhere: the constraint is FROZEN, not scheduled
    for needle in ("11:00", "11am", "date +%H", "TZ=", "at 11"):
        bad = [ln for ln in LAUNCHER.splitlines()
               if needle in ln and not ln.strip().startswith("#")
               and "log " not in ln]
        assert not bad, f"the launcher must not SCHEDULE on {needle!r}: {bad}"


def test_the_smoke_runs_at_the_boxs_own_frozen_W():
    """⭐ UNIFORMITY BEATS SPEED: round 2 smoked at a separate W=8; round 3 does
    not, so a smoke cannot pass at a W the real cells never use."""
    assert 'SMOKE_WORKERS="$W"' in LAUNCHER
    assert not re.search(r"^SMOKE_WORKERS=\d", WORKERS, re.M), \
        "WORKERS.conf must NOT carry an independent smoke W"


def test_every_shape_sits_wholly_on_one_box():
    """⛔ THE LOAD-BEARING PROPERTY: else §4.5's contrast and §4.5b's lift become
    CROSS-BOX statistics, and this program has been bitten by cross-box float
    drift (the Xeon's AVX-512 G0 failure)."""
    for sh in L.SHAPES:
        assert len({c.box for c in L.cells_of_shape(sh)}) == 1, sh


def test_the_assignment_is_the_opposite_of_round_2s_and_that_is_deliberate():
    assert {c.name for c in L.cells_of_box("local")} == {"C_LOW", "C_MID", "C_HIGH"}
    assert {c.name for c in L.cells_of_box("laptop")} == {
        "A_LOW", "A_MID", "A_HIGH", "J_LOW", "J_HIGH"}
    # round 2 put C on the laptop; round 3 puts it on local
    for n in ("C_LOW", "C_MID", "C_HIGH"):
        assert L.R2_CELLS[n]["box"] == "laptop"
        assert L.cell_by_name(n).box == "local"
    assert "OPPOSITE OF ROUND 2" in L.BOX_ASSIGNMENT_RULE


def test_the_chosen_split_is_the_wall_clock_optimum_at_this_rounds_W():
    rows = L.split_table()
    assert len(rows) == 6, "three shapes -> six non-degenerate whole-shape splits"
    assert rows[0]["chosen"], (
        "the frozen assignment is not the fastest split: "
        f"{[(r['local'], round(r['round_wall_hours'], 3)) for r in rows]}")
    # and it is genuinely better than the runner-up
    assert rows[0]["round_wall_hours"] < rows[1]["round_wall_hours"]


def test_the_split_would_be_different_at_round_2s_W():
    """⭐ THE POINT OF THE RECOMPUTE: at W_LOCAL=22 the fastest split is round 2's
    (the expensive shape to the laptop); at 14 it flips. If this test ever fails,
    the W_LOCAL constraint has stopped mattering and the prose is stale."""
    le = {}
    for sh in L.SHAPES:
        c = L.cells_of_shape(sh)[0]
        cand, opp = L._cell_ms(c)
        s = L.MOVES_PER_SIDE * (cand + opp) / 1000.0 * L.OVERHEAD
        le[sh] = s * c.n_games / 3600.0 * len(L.cells_of_shape(sh))

    def best(w_local):
        out = []
        for mask in range(1, 7):
            loc = [s for i, s in enumerate(L.SHAPES) if mask >> i & 1]
            lap = [s for s in L.SHAPES if s not in loc]
            lw = sum(le[s] for s in loc) / w_local
            pw = sum(le[s] * L.LAPTOP_RATIO_MEASURED for s in lap) / 22.0
            out.append((max(lw, pw), tuple(sorted(loc))))
        return min(out)[1]

    assert best(14) == ("C",), "at W=14 the C ladder belongs on local"
    assert best(22) != ("C",), "at W=22 the balance point is elsewhere — the flip is real"


def test_the_laptop_ratio_is_MEASURED_this_round_and_says_how():
    assert L.BOXES["laptop"]["ratio_is_measured"] is True
    assert abs(L.LAPTOP_RATIO_MEASURED - 692.66 / 633.42) < 0.001, \
        "the ratio must be the SAME leaf's ms/move on the two boxes"
    lo, hi = L.LAPTOP_RATIO_ENVELOPE
    assert lo < L.LAPTOP_RATIO_MEASURED < hi
    note = L.LAPTOP_RATIO_NOTE
    assert "MEASURED, not assumed" in note
    assert "633.42" in note and "692.66" in note, "the two readings must be shown"
    assert "does NOT transfer" in note, "the scope limit must be stated"


def test_the_share_mount_spelling_differs_by_box():
    assert L.BOXES["local"]["share_mount"] == "/mnt/c/carc-shared"
    assert L.BOXES["laptop"]["share_mount"] == "/mnt/carc-shared"
    assert _conf("SHARE_LOCAL") == L.BOXES["local"]["share_mount"]
    assert _conf("SHARE_LAPTOP").split()[0] == L.BOXES["laptop"]["share_mount"]


def test_each_box_smokes_a_config_it_will_actually_run():
    for role, sm in L.SMOKE_BY_BOX.items():
        assert L.cell_by_name(sm["cell"]).box == role


def test_the_load_bearing_smoke_is_the_JOINT_one():
    """⭐ The reason CHANGED from round 2 (where the laptop was new to the C
    regime): here the JOINT LEAF is new to the PROGRAM."""
    assert L.SMOKE_BY_BOX["laptop"]["cell"] == "J_HIGH"
    assert L.cell_by_name("J_HIGH").is_joint
    why = L.SMOKE_BY_BOX["laptop"]["why"]
    assert "LOAD-BEARING" in why
    assert "NEVER emitted a manifest" in why


def test_the_two_smoke_ranges_are_disjoint_from_each_other_and_every_cell():
    seen = set()
    for c in L.CELLS:
        seen |= set(c.seeds)
    smoke = set()
    for sm in L.SMOKE_BY_BOX.values():
        rng = set(range(sm["seed_start"], sm["seed_start"] + L.SMOKE_DECKS))
        assert not (rng & seen), "a smoke range reaches a real cell"
        assert not (rng & smoke), "the two smoke ranges overlap"
        smoke |= rng


def test_G_HOST_accepts_every_laptop_spelling_and_rejects_the_wrong_box():
    for h in ("laptop", "laptop-wsl", "LAPTOP-POP", "pop-os"):
        assert L.host_matches_box(h, "laptop")[0], h
        assert not L.host_matches_box(h, "local")[0], h
    for h in ("Doctor", "DESKTOP-5800X"):
        assert L.host_matches_box(h, "local")[0], h
        assert not L.host_matches_box(h, "laptop")[0], h
    for bad in (None, "", 0, [], {}):
        assert not L.host_matches_box(bad, "local")[0], "ABSENT is FAIL"
        assert not L.host_matches_box(bad, "laptop")[0], "ABSENT is FAIL"


# ═══════════════════════════════════════════════════════════════════════════ #
# 6. THE BARS, THE BRANCHES AND THE CONTRASTS                                 #
# ═══════════════════════════════════════════════════════════════════════════ #
@pytest.mark.parametrize("z,expected", [
    (2.0, "PROMOTE"), (2.0001, "PROMOTE"), (1.9999, "BRACKET"),
    (1.0, "BRACKET"), (0.9999, "NULL"), (-1.9999, "NULL"),
    (-2.0, "REVERSED"), (-2.5, "REVERSED"), (None, "U-UNREADABLE"),
    (float("nan"), "U-UNREADABLE"),
])
def test_branch_endpoints(z, expected):
    assert L.branch_for_cell(z, True) == expected


def test_the_bars_did_not_move_in_three_rounds():
    assert (L.PROMOTE_Z, L.BRACKET_Z, L.REVERSED_Z) == (2.0, 1.0, -2.0)
    assert L.CONTRAST_Z == 2.0
    assert L.SAT_WR == (0.35, 0.65)
    assert L.N_COMMON_FRAC == 0.80
    assert L.SIGMA_D_MODEL == 14.67
    assert L.SE_ANOMALY_BAND == (0.70, 1.43)
    assert L.ELO_PER_PT_BRACKET == (16.74, 19.35)
    assert L.NOISE_SIGNATURE_SIGMA == 1.0


def test_a_failed_gate_beats_every_branch():
    for z in (5.0, 2.0, 1.0, 0.0, -5.0):
        assert L.branch_for_cell(z, False) == "U-UNREADABLE"


def test_one_unreadable_or_missing_cell_voids_the_round_branch():
    br = {c.name: "PROMOTE" for c in L.CELLS}
    br["C_HIGH"] = "U-UNREADABLE"
    assert L.round_branch(br) == "U-UNREADABLE"
    del br["C_HIGH"]
    assert L.round_branch(br) == "U-UNREADABLE"


def test_bracket_continue_outranks_reversed_and_family_parks():
    br = {c.name: "NULL" for c in L.CELLS}
    br["A_LOW"] = "REVERSED"
    br["J_HIGH"] = "BRACKET"
    assert L.round_branch(br) == "BRACKET-CONTINUE"


def test_reversed_fires_only_when_nothing_reached_one_sigma():
    br = {c.name: "NULL" for c in L.CELLS}
    br["A_HIGH"] = "REVERSED"
    assert L.round_branch(br) == "REVERSED-A"
    br["J_LOW"] = "REVERSED"
    assert L.round_branch(br) == "REVERSED-A,JOINT"


def test_family_parks_requires_every_cell_null():
    assert L.round_branch({c.name: "NULL" for c in L.CELLS}) == "FAMILY-PARKS"


def test_family_parks_parks_formulas_never_the_mechanism():
    m = L.FAMILY_PARKS_MEANS
    assert "PARKS THE FORMULAS, NEVER THE MECHANISM" in m
    assert "E4 record stands" in m
    assert "DIFFERENT SHAPE" in m


def test_contrast_is_the_unmatched_difference_with_a_root_sum_square_se():
    lo = {"D": 1.0, "se": 0.6}
    hi = {"D": 3.0, "se": 0.8}
    ct = L.shape_contrast(lo, hi)
    assert abs(ct["delta"] - 2.0) < 1e-12
    assert abs(ct["se"] - math.hypot(0.6, 0.8)) < 1e-12
    assert abs(ct["z"] - 2.0 / math.hypot(0.6, 0.8)) < 1e-12


@pytest.mark.parametrize("lo,mid,hi", [
    (None, {"D": 1, "se": 1}, {"D": 1, "se": 1}),
    ({"D": 1, "se": 1}, {"D": 1, "se": 1}, None),
    ({"D": 1, "se": None}, {"D": 1, "se": 1}, {"D": 1, "se": 1}),
])
def test_interior_lift_absent_is_unreadable_never_zero(lo, mid, hi):
    lf = L.interior_lift(lo, mid, hi)
    assert not lf["readable"]
    assert lf["lift"] is None


def test_interior_lift_is_the_mid_minus_the_mean_of_its_neighbours():
    lo = {"D": 1.0, "se": 0.6}
    mid = {"D": 3.0, "se": 0.6}
    hi = {"D": 1.0, "se": 0.6}
    lf = L.interior_lift(lo, mid, hi)
    assert abs(lf["lift"] - 2.0) < 1e-12
    assert abs(lf["se"] - 0.6 * math.sqrt(1.5)) < 1e-12
    assert lf["verdict"] == "INTERIOR PEAK RESOLVED"
    assert "bracket holds" in lf["reading"]


def test_interior_lift_reports_a_resolved_trough_distinctly():
    lo = {"D": 3.0, "se": 0.6}
    mid = {"D": 0.0, "se": 0.6}
    hi = {"D": 3.0, "se": 0.6}
    lf = L.interior_lift(lo, mid, hi)
    assert lf["verdict"] == "INTERIOR TROUGH RESOLVED"
    assert "not single-peaked" in lf["reading"]


def test_an_unresolved_lift_keeps_the_endpoint_rule_in_force():
    lf = L.interior_lift({"D": 0.0, "se": 5.0}, {"D": 0.1, "se": 5.0},
                         {"D": 0.0, "se": 5.0})
    assert lf["verdict"] == "INTERIOR LIFT UNRESOLVED"
    assert "ENDPOINT RULE STAYS IN FORCE" in lf["reading"]


def test_the_joint_shape_has_no_interior_lift_and_says_so():
    lf = L.interior_lift({"D": 1, "se": 1}, None, {"D": 1, "se": 1})
    assert lf["verdict"] == "NOT APPLICABLE"
    assert lf["applicable"] is False
    assert "no interior" in lf["why"]


def test_neither_contrast_is_ever_described_as_a_promotion_input():
    ct = L.shape_contrast({"D": 1.0, "se": 0.6}, {"D": 2.0, "se": 0.6})
    lf = L.interior_lift({"D": 1, "se": 1}, {"D": 1, "se": 1}, {"D": 1, "se": 1})
    for d in (ct, lf):
        assert "NEVER a promotion input" in d["why"]
        assert "per-cell against zero" in d["why"]


def test_the_lift_is_tighter_than_the_scaling_contrast_at_the_same_dispersion():
    """⭐ Averaging the two neighbours halves their variance contribution, so the
    three-point statistic buys real resolution over the two-point one."""
    for a, b in zip(L.CONTRAST_POWER, L.LIFT_POWER):
        assert a["se_cell"] == b["se_cell"]
        assert b["se_stat"] < a["se_stat"]
        assert abs(b["se_stat"] - a["se_cell"] * math.sqrt(1.5)) < 1e-9
        assert abs(a["se_stat"] - a["se_cell"] * math.sqrt(2.0)) < 1e-9


def test_noise_signature_fires_only_when_the_mid_beats_BOTH_neighbours_by_over_1sigma():
    assert L.noise_signature({"z": 2.5}, {"z": 1.0}, {"z": 1.0})["fired"]
    assert not L.noise_signature({"z": 2.5}, {"z": 1.6}, {"z": 1.0})["fired"]
    assert not L.noise_signature({"z": 2.5}, {"z": 1.0}, {"z": 1.6})["fired"]
    # exactly 1.0 does NOT fire (the rule says "beats by >1σ")
    assert not L.noise_signature({"z": 2.0}, {"z": 1.0}, {"z": 1.0})["fired"]


def test_the_noise_signature_message_names_shape_Bs_demotion():
    fired = L.noise_signature({"z": 3.0}, {"z": 0.0}, {"z": 0.0})
    assert "DEMOTED SHAPE B" in fired["why"], \
        "the check must point at the case it actually caught"


def test_noise_signatures_runs_on_every_interior_rung_and_skips_the_two_point_one():
    stats = {c.name: {"z": 1.0} for c in L.CELLS}
    out = L.noise_signatures(stats)
    assert set(out) == set(L.SHAPES)
    assert out["A"]["applicable"] and out["C"]["applicable"]
    assert not out["J"]["applicable"]
    assert "no INTERIOR rung" in out["J"]["why"]


def test_a_and_c_are_bracketed_is_stated_without_repealing_the_endpoint_rule():
    r = L.A_AND_C_ARE_BRACKETED
    assert "GENUINELY BRACKETED" in r
    assert "NOT BEEN REPEALED" in r
    for w in ("0.02", "0.10", "0.03", "0.15"):
        assert w in r, "the endpoint weights must be named"


# ═══════════════════════════════════════════════════════════════════════════ #
# 7. THE COST MODEL                                                           #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_cost_model_reproduces_round_2s_realized_arms_without_under_predicting():
    """⛔ DIRECTIONAL: a model that decides funding must err DEAR."""
    k = L.MOVES_PER_SIDE * L.OVERHEAD / 1000.0
    for label, modelled, realized in (
        ("A", k * (L.MS_SHAPE_A_SIDE + L.MS_CHAMPION_SIDE), 84.75),
        ("B", k * (L.MS_SHAPE_B_SIDE + L.MS_CHAMPION_SIDE), 79.25),
        ("C", k * (L.MS_SHAPE_C_SIDE + L.MS_SHAPE_B_SIDE) * L.LAPTOP_RATIO_MEASURED,
         100.67),
    ):
        err = (modelled - realized) / realized
        assert 0.0 <= err <= 0.05, f"{label}: {modelled:.2f} vs {realized:.2f} ({err:+.2%})"


def test_the_joint_leaf_cost_is_the_only_unmeasured_input_and_is_additive():
    d_beta = L.MS_SHAPE_A_SIDE - L.MS_CHAMPION_SIDE
    d_gamma = L.MS_SHAPE_C_SIDE - L.MS_CHAMPION_SIDE
    assert abs(L.MS_SHAPE_J_SIDE - (L.MS_CHAMPION_SIDE + d_beta + d_gamma)) < 0.05
    lo, hi = L.MS_SHAPE_J_ENVELOPE
    assert lo < L.MS_SHAPE_J_SIDE < hi
    # the point estimate sits ABOVE the envelope midpoint — the DEAR direction
    assert L.MS_SHAPE_J_SIDE > (lo + hi) / 2.0
    assert L.project_cell_cost(L.cell_by_name("J_LOW"))["j_side_is_assumed"]
    assert not L.project_cell_cost(L.cell_by_name("A_LOW"))["j_side_is_assumed"]
    assert "ONE unmeasured input" in L.round_cost_envelope()["why"]


def test_the_joint_cells_are_the_dearest_and_the_A_cells_the_cheapest():
    per = L.project_round_cost()["per_cell"]
    a = per["A_LOW"]["core_hours_local_equiv"]
    c = per["C_LOW"]["core_hours_local_equiv"]
    j = per["J_LOW"]["core_hours_local_equiv"]
    assert a < c < j, f"A {a:.2f} < C {c:.2f} < J {j:.2f}"


def test_the_round_wall_is_the_MAX_over_boxes_not_the_sum():
    p = L.project_round_cost()
    walls = [b["wall_hours"] for b in p["per_box"].values()]
    assert abs(p["wall_hours"] - max(walls)) < 1e-12
    assert p["wall_hours"] < sum(walls)


def test_the_local_wall_uses_W14_and_the_laptop_W22():
    p = L.project_round_cost()
    assert p["per_box"]["local"]["W"] == 14
    assert p["per_box"]["laptop"]["W"] == 22
    assert abs(p["per_box"]["local"]["wall_hours"]
               - p["per_box"]["local"]["core_hours"] / 14.0) < 1e-12


def test_the_split_buys_real_wall_clock_over_a_single_box_run():
    p = L.project_round_cost()
    assert p["wall_hours_single_box_local"] > 2 * p["wall_hours"]


def test_the_cost_envelope_brackets_the_point_estimate():
    e = L.round_cost_envelope()
    assert e["low"]["core_hours"] < e["point"]["core_hours"] < e["high"]["core_hours"]


def test_cost_scales_linearly_with_games():
    c = L.cell_by_name("A_LOW")
    p = L.project_cell_cost(c)
    assert abs(p["core_hours"] - p["s_per_game"] * c.n_games / 3600.0) < 1e-12


def test_W_moves_wall_clock_and_nothing_else():
    c = L.cell_by_name("C_LOW")
    a = L.project_cell_cost(c, w=14)
    b = L.project_cell_cost(c, w=22)
    assert a["core_hours"] == b["core_hours"]
    assert a["s_per_game"] == b["s_per_game"]
    assert a["wall_hours"] > b["wall_hours"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 8. POWER — COMPUTED, NOT TYPED                                              #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_power_table_is_computed_from_the_two_frozen_dispersions():
    for row in L.POWER_TABLE:
        d = row["true_effect_pts"]
        assert abs(row["z_at_model_se"] - d / L.SE_MODEL_400) < 1e-12
        assert abs(row["z_at_realized_se"] - d / L.SE_REALIZED_400) < 1e-12
        assert abs(row["power_model"] - L.power_at(d, L.SE_MODEL_400)) < 1e-12
        assert 0.0 < row["power_model"] < row["power_realized"] < 1.0


def test_the_80_percent_MDE_rows_really_are_80_percent():
    for row in L.POWER_TABLE:
        if "80%-power MDE at round 2's REALIZED" in row["note"]:
            assert abs(row["power_realized"] - 0.80) < 0.01
        if "80%-power MDE at the FROZEN" in row["note"]:
            assert abs(row["power_model"] - 0.80) < 0.01


def test_the_realized_dispersion_is_round_2s_own_and_is_tighter_than_the_model():
    assert abs(L.SE_REALIZED_400 - L.R2_MEAN_SIGMA_D / 20.0) < 1e-12
    assert L.SE_REALIZED_400 < L.SE_MODEL_400, "the model must stay CONSERVATIVE"
    for n, s in L.R2_REALIZED_SIGMA_D.items():
        assert abs(s - L.R2_CELLS[n]["se"] * 20.0) < 1e-3


def test_round_2s_realized_ratios_all_sit_inside_the_dispersion_band():
    lo, hi = L.SE_ANOMALY_BAND
    for n, sigma in L.R2_REALIZED_SIGMA_D.items():
        assert lo <= sigma / L.SIGMA_D_MODEL <= hi, n


def test_the_power_headline_states_the_gap_between_what_is_chased_and_resolvable():
    h = L.POWER_HEADLINE
    assert "POWERED TO RESOLVE" in h
    assert "+0.94" in h and "+1.00" in h
    assert "JOINT CELLS EXIST" in h
    assert "FAMILY-PARKS" in h and "failed to replicate" in h


def test_each_single_cell_is_underpowered_for_the_effects_it_is_chasing():
    """⛔ THE HONEST NUMBER, asserted rather than merely written: a +1.0 effect is
    caught well under half the time."""
    for d in (L.R2_CELLS["A_LOW"]["D"], L.R2_CELLS["C_LOW"]["D"]):
        assert L.power_at(d, L.SE_REALIZED_400) < 0.40
        assert L.power_at(d, L.SE_MODEL_400) < 0.30


def test_the_joint_sizing_target_is_the_one_effect_this_round_can_resolve():
    d = 1.94
    assert L.power_at(d, L.SE_REALIZED_400) > 0.85
    assert L.power_at(d, L.SE_MODEL_400) > 0.70


def test_se_anomaly_is_reported_never_a_branch_input():
    a = L.se_anomaly(0.30, 400)
    assert a["flagged"] and "never a branch input" in a["note"]
    assert "TIGHTER" in a["direction"]
    b = L.se_anomaly(2.0, 400)
    assert b["flagged"] and "CONCERNING" in b["direction"]
    assert L.se_anomaly(None, 400)["flagged"], "ABSENT is FLAGGED"


# ═══════════════════════════════════════════════════════════════════════════ #
# 9. THE LEAF JSONS, THE PINS AND G-LEAF                                      #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_leaf_json_files_on_disk_match_the_frozen_bodies():
    for name, body in L.LEAF_JSON_BODIES.items():
        assert json.loads((PREP / name).read_text()) == body, name


def test_every_cell_has_its_own_leaf_json_and_they_are_all_used():
    used = {c.leaf_json for c in L.CELLS}
    assert used == set(L.LEAF_JSON_BODIES)
    assert len(used) == len(L.CELLS), "no two cells share a leaf JSON"


def test_every_candidate_json_carries_curve125_explicitly():
    for name, body in L.LEAF_JSON_BODIES.items():
        assert tuple(body["v29_meeple_curve"]) == L.CURVE125, name


def test_only_the_C_candidates_carry_the_explicit_alpha_zeros():
    """⭐ AND THE J CELLS' ABSENCE OF THEM IS CORRECT, not an omission: the J cells
    run in the PLAIN env regime, so there is nothing to neutralise."""
    for c in L.CELLS:
        body = L.LEAF_JSON_BODIES[c.leaf_json]
        has_zeros = body.get("invasion_alpha") == 0.0 and \
            body.get("invasion_alpha_cap") == 0.0
        assert has_zeros == (c.shape == "C"), c.name
        assert c.shape_b_env == (c.shape == "C"), c.name


def test_every_candidate_hash_is_distinct_and_off_the_champion_pin():
    hs = [c.cand_leaf_hash for c in L.CELLS]
    assert len(set(hs)) == len(hs)
    for c in L.CELLS:
        assert c.cand_leaf_hash != L.PROD_LEAF_HASH
        assert c.cand_leaf_hash != c.opp_leaf_hash
        assert c.cand_leaf_hash != L.SHAPE_B_LEAF_HASH


def test_no_round_3_pin_collides_with_a_round_1_or_2_pin():
    prior = {L.PROD_LEAF_HASH, L.SHAPE_B_LEAF_HASH,
             L.R1_MIDS["A"]["cand_leaf_hash"], L.R1_MIDS["D"]["cand_leaf_hash"],
             "f8c0f04092734f9e", "f6ce81145cbd5102", "f5b7a26216794290",
             "1a42effad7066c0b", "a6ab04dbb69ad29e", "897c21aca11b6fbd",
             "df34cb874fea6273"}
    for c in L.CELLS:
        assert c.cand_leaf_hash not in prior, c.name


@pytest.mark.parametrize("cell", [c.name for c in L.CELLS])
def test_leaf_gate_passes_on_the_frozen_pins(cell):
    c = L.cell_by_name(cell)
    assert L.leaf_gate(c, c.cand_leaf_hash, c.opp_leaf_hash, L.CURVE125)["ok"]


@pytest.mark.parametrize("cell", [c.name for c in L.CELLS])
def test_leaf_gate_fails_on_a_wrong_hash_on_either_side(cell):
    c = L.cell_by_name(cell)
    assert not L.leaf_gate(c, "0" * 16, c.opp_leaf_hash, L.CURVE125)["ok"]
    assert not L.leaf_gate(c, c.cand_leaf_hash, "0" * 16, L.CURVE125)["ok"]
    assert not L.leaf_gate(c, c.cand_leaf_hash, c.opp_leaf_hash, None)["ok"]


def test_leaf_gate_catches_a_JOINT_cell_handed_the_SHAPE_B_OPPONENT():
    """⛔ THE ROUND'S WORST SILENT ERROR: a J cell whose opponent is the invader
    licenses NOTHING while looking like the headline result."""
    for name in ("J_LOW", "J_HIGH"):
        c = L.cell_by_name(name)
        g = L.leaf_gate(c, c.cand_leaf_hash, L.SHAPE_B_LEAF_HASH, L.CURVE125)
        assert not g["ok"]
        assert not g["conjuncts"]["opp_hash_is_pinned"]


def test_leaf_gate_catches_a_C_cell_that_played_the_PLAIN_CHAMPION():
    for c in L.cells_of_shape("C"):
        g = L.leaf_gate(c, c.cand_leaf_hash, L.PROD_LEAF_HASH, L.CURVE125)
        assert not g["ok"]
        assert not g["conjuncts"]["opp_hash_is_pinned"]


@pytest.mark.parametrize("bad", [None, "", 0, [], {}])
def test_leaf_gate_absent_is_fail_not_a_vacuous_pass(bad):
    c = L.cell_by_name("J_HIGH")
    assert not L.leaf_gate(c, bad, bad, bad)["ok"], "ABSENT must not pass vacuously"


def test_the_wheel_probe_contract_gained_the_joint_key_and_fails_closed():
    assert "joint_two_knob_forward_ok" in L.WHEEL_PROBE_REQUIRED_TRUE
    good = {k: True for k in L.WHEEL_PROBE_REQUIRED_TRUE}
    good["carc_rs_build"] = "carc_rs-0.1.0+deadbeefcafe+rustcunpinned"
    assert L.wheel_probe_ok(good)[0]
    for drop in L.WHEEL_PROBE_REQUIRED_TRUE:
        bad = dict(good)
        bad[drop] = False
        assert not L.wheel_probe_ok(bad)[0], drop
    assert not L.wheel_probe_ok(None)[0]
    assert not L.wheel_probe_ok({})[0]


def test_the_launcher_computes_the_joint_conjunct_and_fails_closed_without_a_J_cell():
    """⭐ NOT VACUOUSLY TRUE: a probe that never saw a J cell must read FALSE."""
    assert "joint_two_knob_forward_ok" in LAUNCHER
    assert 'bool(_j) and all(' in LAUNCHER, \
        "the merged key must require at least one probed JOINT cell"
    assert "n_nonzero == 2" in LAUNCHER


def test_wheel_is_r1s_keys_on_the_binary_sha_alone():
    ok, why = L.wheel_is_r1s(L.R1_WHEEL_BINARY_SHA, "anything at all")
    assert ok
    assert "INFORMATIONAL" in why
    # a DIFFERENT build string with the RIGHT sha still passes
    assert L.wheel_is_r1s(L.R1_WHEEL_BINARY_SHA, L.R2_WHEEL_BUILD_INFORMATIONAL)[0]
    assert L.wheel_is_r1s(L.R1_WHEEL_BINARY_SHA, L.R1_WHEEL_BUILD_INFORMATIONAL)[0]
    for bad in (None, "", "deadbeef", 0, []):
        assert not L.wheel_is_r1s(bad)[0]
    assert "RE-OWES AN IDENT CELL" in L.wheel_is_r1s("deadbeef")[1]


def test_the_inherited_ident_is_round_1s_actual_reading_and_names_round_2():
    i = L.R1_IDENT
    assert i["band"] == 151000000000
    assert abs(i["z"]) <= i["bar"], "the inherited IDENT must actually have PASSED"
    assert i["cand_leaf_hash"] == i["opp_leaf_hash"] == L.PROD_LEAF_HASH
    assert "round 2" in i["inherited_by"] and "round 3" in i["inherited_by"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 10. THE LAUNCHER                                                            #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_workers_conf_band_matches_screen_lib():
    assert int(_conf("BAND")) == L.BAND == 153000000000


def test_the_launcher_pins_no_bar_of_its_own():
    for bar in ("2.0", "1.0", "-2.0", "14.67", "0.35", "0.65", "16.74", "19.35"):
        assert f"={bar}" not in LAUNCHER.replace("PROMOTE_Z", ""), \
            f"the launcher must not hard-code the bar {bar}"


def test_workers_conf_carries_both_pinned_hashes_for_every_cell():
    for c in L.CELLS:
        assert _conf(f"CAND_LEAF_HASH_{c.name}") == c.cand_leaf_hash, c.name
        assert _conf(f"OPP_LEAF_HASH_{c.name}") == c.opp_leaf_hash, c.name
    assert _conf("PROD_LEAF_HASH") == L.PROD_LEAF_HASH
    assert _conf("SHAPE_B_LEAF_HASH") == L.SHAPE_B_LEAF_HASH
    assert _conf("R1_WHEEL_BINARY_SHA") == L.R1_WHEEL_BINARY_SHA


def test_launcher_never_arms_the_tie_arbiter():
    """⛔ It may only ever be MENTIONED in a comment, never emitted into an argv."""
    live = [ln for ln in LAUNCHER.splitlines()
            if ("--cand-tiearb" in ln or "--opp-tiearb" in ln)
            and not ln.strip().startswith("#") and "log " not in ln]
    assert not live, live
    assert _conf("TIEARB") == "off"


def test_launcher_argv_is_symmetric_in_the_budget():
    for flag in ("--k-dets", "--opp-k-dets"):
        assert re.search(rf'{flag} +"\$K_DETS"', LAUNCHER), flag
    for flag in ("--sims", "--opp-sims"):
        assert re.search(rf'{flag} +"\$SIMS_PER_DET"', LAUNCHER), flag
    assert int(_conf("K_DETS")) * int(_conf("SIMS_PER_DET")) == int(_conf("TOTAL_SIMS"))


def test_the_invasion_env_is_emitted_into_the_argv_never_exported():
    """⛔ A process-wide export would give the A and J cells a shape-B opponent —
    and on a J cell that is the round's most damaging possible error."""
    assert "export CARCASSONNE_INVASION" not in LAUNCHER
    assert 'env "CARCASSONNE_INVASION_ALPHA=$a" "CARCASSONNE_INVASION_ALPHA_CAP=$cap"' \
        in LAUNCHER
    # and it is PINNED OFF explicitly rather than merely absent
    assert 'local a="0.0" cap="0.0"' in LAUNCHER


def test_the_launcher_marks_the_J_cells_env_regime_as_load_bearing_zero():
    m = re.search(r"declare -A CELL_BENV=\((.*?)\)", LAUNCHER, re.S)
    assert m
    body = m.group(1)
    for c in L.CELLS:
        assert f"[{c.name}]={1 if c.shape_b_env else 0}" in body, c.name


def test_launcher_cell_table_agrees_with_screen_lib():
    for field, attr in (("CELL_SEED", "seed_start"), ("CELL_DECKS", "n_decks"),
                        ("CELL_GAMES", "n_games"), ("CELL_SUB", "out_subdir"),
                        ("CELL_LEAF", "leaf_json"), ("CELL_BOX", "box")):
        m = re.search(rf"declare -A {field}=\((.*?)\n(?=[a-z#])", LAUNCHER, re.S)
        assert m, field
        body = m.group(1)
        for c in L.CELLS:
            assert f"[{c.name}]={getattr(c, attr)}" in body, f"{field}[{c.name}]"


def test_launcher_refuses_to_run_without_a_host_or_with_an_unknown_one():
    """⛔ There is NO default: a launcher that guessed would run the wrong cells at
    the wrong share mount and be voided by G-HOST after the compute was spent."""
    env = dict(os.environ, CARC_PY=sys.executable)
    for args in ([], ["--host", "xeon"]):
        r = subprocess.run(["bash", str(PREP / "run_cells.sh"), "--dry-run", *args],
                           capture_output=True, text=True, env=env)
        assert r.returncode == 2, r.stdout + r.stderr
        assert "--host" in (r.stdout + r.stderr)


@pytest.mark.parametrize("role", ["local", "laptop"])
def test_launcher_dry_run_emits_only_its_own_cells(role):
    env = dict(os.environ, CARC_PY=sys.executable)
    r = subprocess.run(["bash", str(PREP / "run_cells.sh"), "--host", role,
                        "--dry-run"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    for c in L.CELLS:
        if c.box == role:
            assert f"[dry-run] CELL {c.name}" in out.replace(f"CELL {c.name} :",
                                                             f"CELL {c.name}"), c.name
            assert c.cand_leaf_hash in out
        else:
            assert f"CELL {c.name}: ⛔ NOT THIS BOX'S" in out, c.name


@pytest.mark.parametrize("role,w,share", [("local", "22", "/mnt/c/carc-shared"),
                                          ("laptop", "22", "/mnt/carc-shared")])
def test_launcher_dry_run_uses_each_boxs_own_W_and_share(role, w, share):
    env = dict(os.environ, CARC_PY=sys.executable)
    r = subprocess.run(["bash", str(PREP / "run_cells.sh"), "--host", role,
                        "--dry-run"], capture_output=True, text=True, env=env)
    assert r.returncode == 0
    want_w = str(L.BOXES[role]["W"])
    assert f"--workers {want_w}" in r.stdout
    assert share in r.stdout
    if role == "local":
        assert "--workers 22" not in r.stdout, "local must never emit W=22"


def test_launcher_dry_run_prints_the_split_table_and_the_owner_constraint():
    env = dict(os.environ, CARC_PY=sys.executable)
    r = subprocess.run(["bash", str(PREP / "run_cells.sh"), "--host", "local",
                        "--dry-run"], capture_output=True, text=True, env=env)
    assert r.returncode == 0
    assert "THE SPLIT ARITHMETIC -- ALL SIX WHOLE-SHAPE PARTITIONS" in r.stdout
    assert "<== FROZEN" in r.stdout
    assert "limit local to w14 starting at 11am" in r.stdout
    assert "ROUND WALL" in r.stdout


def test_launcher_dry_run_prints_the_derivation_and_the_attribution_ban():
    env = dict(os.environ, CARC_PY=sys.executable)
    r = subprocess.run(["bash", str(PREP / "run_cells.sh"), "--host", "laptop",
                        "--dry-run"], capture_output=True, text=True, env=env)
    assert r.returncode == 0
    assert "THE WEIGHTS, AND WHERE THEY CAME FROM" in r.stdout
    assert "THE JOINT READ DOES NOT ATTRIBUTE" in r.stdout
    assert "ADOPTION-CHAIN-ELIGIBLE" in r.stdout
    assert "never the chain" in r.stdout


def test_launcher_refuses_an_only_cell_belonging_to_the_other_box():
    env = dict(os.environ, CARC_PY=sys.executable)
    r = subprocess.run(["bash", str(PREP / "run_cells.sh"), "--host", "local",
                        "--dry-run", "--only", "J_HIGH"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0
    assert "NOT THIS BOX'S" in r.stdout


def test_launcher_is_not_executable():
    """⛔ `chmod +x` is the ORCHESTRATOR's launch act, never this build's."""
    assert not os.access(PREP / "run_cells.sh", os.X_OK)


@pytest.mark.parametrize("role", ["local", "laptop"])
def test_launcher_table_preflight_actually_runs(role):
    """The heredoc that cross-checks the shell table against screen_lib must
    EXECUTE, not merely exist."""
    env = dict(os.environ, CARC_PY=sys.executable)
    src = LAUNCHER.replace("main \"$@\"", "require_table_agrees")
    p = PREP / f"_tmp_table_{role}.sh"
    p.write_text(src)
    try:
        r = subprocess.run(["bash", str(p), "--host", role],
                           capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "cell table agrees with screen_lib.py" in r.stdout
        assert "screen_lib.sanity_check(): 0 problem(s)" in r.stdout
    finally:
        p.unlink(missing_ok=True)


@pytest.mark.parametrize("field,label", [
    ("CELL_SEED", "seed_start"), ("CELL_BOX", "box"), ("CELL_BENV", "shape_b_env"),
])
def test_launcher_table_preflight_rejects_a_drifted_table(field, label):
    env = dict(os.environ, CARC_PY=sys.executable)
    src = LAUNCHER.replace("main \"$@\"", "require_table_agrees")
    m = re.search(rf"(declare -A {field}=\(.*?\[J_HIGH\]=)([^ \n)]+)", src, re.S)
    assert m, field
    bad = "local" if field == "CELL_BOX" else ("1" if field == "CELL_BENV"
                                               else "999000000000")
    src = src[:m.start(2)] + bad + src[m.end(2):]
    p = PREP / f"_tmp_drift_{field}.sh"
    p.write_text(src)
    try:
        r = subprocess.run(["bash", str(p), "--host", "laptop"],
                           capture_output=True, text=True, env=env)
        assert r.returncode != 0, "a drifted table must be REFUSED"
        assert label in (r.stdout + r.stderr) or "disagrees" in (r.stdout + r.stderr)
    finally:
        p.unlink(missing_ok=True)


def test_launcher_table_preflight_rejects_a_drifted_band():
    env = dict(os.environ, CARC_PY=sys.executable)
    src = LAUNCHER.replace("main \"$@\"", "require_table_agrees")
    p = PREP / "_tmp_band.sh"
    p.write_text(src)
    try:
        r = subprocess.run(["bash", str(p), "--host", "local", "--band", "999"],
                           capture_output=True, text=True, env=env)
        assert r.returncode != 0
        assert "disagrees with the pair's BAND" in (r.stdout + r.stderr)
    finally:
        p.unlink(missing_ok=True)


def test_the_pass_timeout_is_sized_for_the_dearest_cell_at_the_slowest_W():
    """⛔ RAISED FROM ROUND 2's 1800 s BECAUSE W_LOCAL=14. 100 games of the local
    box's dearest cell must fit with >= 3x margin."""
    t = int(_conf("PASS_TIMEOUT_SECS"))
    chunk = int(_conf("CHUNK_GAMES"))
    dearest_local = max(L.project_cell_cost(c)["s_per_game"]
                        for c in L.cells_of_box("local"))
    expected = chunk * dearest_local / L.BOXES["local"]["W"]
    assert t >= 3 * expected, f"{t}s is under 3x the expected {expected:.0f}s"
    assert t > 1800, "round 2's timeout would be too tight at W=14"


def test_the_launcher_code_paths_exclude_measurement():
    m = re.search(r"CODE_PATHS=\((.*?)\)", LAUNCHER)
    assert m
    paths = m.group(1).split()
    assert "measurement" not in paths, \
        "PINNED_SRC_REV / RUN_LIVE.json / WHEEL_PROBE.json necessarily dirty it"
    assert {"src", "engine", "scripts", "rust", "tests"} <= set(paths)


# ═══════════════════════════════════════════════════════════════════════════ #
# 11. THE GATES, DRIVEN ON RE-BADGED REAL ARCHIVES                            #
#                                                                             #
# The archives below are re-badges of `selftest_fixture/manifest.json` — a     #
# REAL emitted manifest — onto each cell's frozen band, with per-deck margins  #
# constructed to hit an EXACT z. Nothing here plays a game or spends a deck.   #
# ═══════════════════════════════════════════════════════════════════════════ #
def _exact_z_margins(n: int, z_target: float, seed: int = 20260827) -> list[float]:
    rng = random.Random(seed)
    xs = [rng.gauss(0.0, 12.0) for _ in range(n)]
    mx = sum(xs) / n
    var = sum((x - mx) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return [x - mx + z_target * se for x in xs]


def _build_full_cell(root: Path, spec, *, z_target: float = 0.0,
                     blind: str = "b" * 40, pinned: str = "b" * 40,
                     n_decks: int | None = None, rev: str | None = None,
                     host: str | None = None) -> Path:
    man = json.loads((_FIXTURE_DIR / "manifest.json").read_text())
    cfg = man["config"]
    champ_leaf = copy.deepcopy(cfg["cand_leaf_cfg"])
    for k in L.INVASION_FIELDS:
        champ_leaf.pop(k, None)
    n_decks = spec.n_decks if n_decks is None else n_decks

    cfg["band_seed_start"] = spec.seed_start
    cfg["seed_start"] = spec.seed_start
    cfg["n_decks"] = n_decks
    cfg["n"] = 2 * n_decks
    cfg["seatings_per_deck"] = 2
    cfg["cand_leaf_cfg"] = dict(champ_leaf, **dict(spec.cand_invasion))
    cfg["cand_leaf_hash"] = spec.cand_leaf_hash
    cfg["opp_leaf_cfg"] = dict(champ_leaf, **dict(spec.opp_invasion))
    cfg["opp_leaf_hash"] = spec.opp_leaf_hash
    cfg["champion"]["leaf_cfg"].update(L.INVASION_DEFAULTS)
    cfg["champion"]["leaf_cfg"].update(dict(spec.cand_invasion))
    cfg["stamps"] = {"BLIND_COMMIT": blind}
    man["BLIND_COMMIT"] = blind
    man["SCREEN_CELL"] = spec.name
    rev = pinned[:8] if rev is None else rev
    cfg["code_rev"] = rev
    man["code_rev"] = rev
    man["carc_rs_binary_sha"] = L.R1_WHEEL_BINARY_SHA
    man["host"] = host or ("laptop-wsl" if spec.box == "laptop" else "Doctor")

    d = root / spec.out_subdir
    d.mkdir(parents=True, exist_ok=True)
    recs = []
    for i, m in enumerate(_exact_z_margins(n_decks, z_target)):
        s = spec.seed_start + i
        for a in (0, 1):
            recs.append({"seed": s, "a_seat": a,
                         "diff": (2.0 * m) if a == 0 else 0.0,
                         "won_by_champ": ((i + a) % 2 == 0), "drew": False,
                         "deck_hash": f"{s:016x}"})
    for r in recs:
        (d / f"seed{r['seed']:012d}_a{r['a_seat']}.json").write_text(json.dumps(r))

    mean, z, n_paired, _se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    (d / "summary.json").write_text(json.dumps({
        "n": 2 * n_decks, "n_failed": 0, "failure_rate": 0.0,
        "winrate": we["winrate"], "elo": we["elo"],
        "elo_sig_1sigma": we["elo_sig_1sigma"],
        "paired_mean_margin": mean, "paired_z": z, "n_paired": n_paired,
        "avg_diff": we["avg_diff"],
        "champ_prefix_ms_per_move": 690.0, "rung_ms_per_move": 470.0,
    }, indent=1))
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    return d


def _healthy_probe() -> dict:
    p = {k: True for k in L.WHEEL_PROBE_REQUIRED_TRUE}
    p["carc_rs_build"] = "carc_rs-0.1.0+deadbeefcafe+rustcunpinned"
    return p


def _gates_on_disk(cell_dir: Path, spec, *, blind="b" * 40, pinned="b" * 40, **over):
    kw = dict(
        pinned_src_rev=pinned, blind_commit=blind, wheel_probe=_healthy_probe(),
        wheel_ancestry={"ok": True, "rev": "deadbeefcafe",
                        "invasion_source_present": True, "is_ancestor": True,
                        "why": ""},
        blind_proof={"ok": True, "blind_commit": blind, "is_ancestor_of_head": True,
                     "introduced_frozen_banner": True, "proof_ok": True, "why": ""},
        src_clean={"ok": True, "boundaries": ["pre-flight"], "dirty_boundaries": [],
                   "has_preflight": True, "missing_after": [], "why": ""})
    kw.update(over)
    return A.run_gates(A.Cell(spec, cell_dir), **kw)


@pytest.mark.parametrize("cell", [c.name for c in L.CELLS])
def test_a_healthy_full_size_archive_passes_every_gate(tmp_path, cell):
    """⭐ THE SATISFIABILITY CONTROL, driven on EVERY cell — including the two
    JOINT ones and the three whose opponent is not the champion."""
    spec = L.cell_by_name(cell)
    d = _build_full_cell(tmp_path, spec, z_target=0.5)
    g, _ = _gates_on_disk(d, spec)
    assert g.failed() == [], f"{cell}: {[(k, g.results[k]['note']) for k in g.failed()]}"


def test_G_SINGLEVAR_catches_a_JOINT_candidate_that_LOST_a_knob(tmp_path):
    """⛔ THE JOINT-SPECIFIC FAILURE: a leaf that reached rust with only beta."""
    spec = L.cell_by_name("J_HIGH")
    d = _build_full_cell(tmp_path, spec)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["cand_leaf_cfg"].pop("invasion_gamma")
    (d / "manifest.json").write_text(json.dumps(man))
    g, _ = _gates_on_disk(d, spec)
    assert "G-SINGLEVAR" in g.failed()
    assert "G-INVASION" in g.failed()


def test_G_LEAF_catches_a_JOINT_cell_handed_the_invader_end_to_end(tmp_path):
    spec = L.cell_by_name("J_LOW")
    d = _build_full_cell(tmp_path, spec)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["opp_leaf_hash"] = L.SHAPE_B_LEAF_HASH
    (d / "manifest.json").write_text(json.dumps(man))
    g, _ = _gates_on_disk(d, spec)
    assert "G-LEAF" in g.failed()


def test_G_INVASION_catches_a_C_cell_whose_OPPONENT_BLOCK_IS_EMPTY(tmp_path):
    spec = L.cell_by_name("C_MID")
    d = _build_full_cell(tmp_path, spec)
    man = json.loads((d / "manifest.json").read_text())
    for k in ("invasion_alpha", "invasion_alpha_cap"):
        man["config"]["opp_leaf_cfg"].pop(k, None)
    (d / "manifest.json").write_text(json.dumps(man))
    g, _ = _gates_on_disk(d, spec)
    assert "G-INVASION" in g.failed()


def test_G_HOST_catches_a_cell_run_on_the_wrong_box(tmp_path):
    spec = L.cell_by_name("C_LOW")           # frozen to LOCAL this round
    d = _build_full_cell(tmp_path, spec, host="laptop-wsl")
    g, _ = _gates_on_disk(d, spec)
    assert "G-HOST" in g.failed()


def test_G_WHEEL_SAME_fails_on_a_rebuilt_wheel(tmp_path):
    spec = L.cell_by_name("A_MID")
    d = _build_full_cell(tmp_path, spec)
    man = json.loads((d / "manifest.json").read_text())
    man["carc_rs_binary_sha"] = "0" * 16
    (d / "manifest.json").write_text(json.dumps(man))
    g, _ = _gates_on_disk(d, spec)
    assert "G-WHEEL-SAME" in g.failed()


def test_a_failed_subdirectory_record_is_never_counted_as_a_completion(tmp_path):
    spec = L.cell_by_name("A_LOW")
    d = _build_full_cell(tmp_path, spec, n_decks=10)
    (d / "failed").mkdir()
    (d / "failed" / "seed153000000099_a0.json").write_text(
        json.dumps({"seed": 153000000099, "a_seat": 0, "diff": 0.0}))
    cell = A.Cell(spec, d)
    assert len(cell.records) == 20, "the failure record must NOT be counted"


def test_absent_is_fail_for_every_gate_on_an_empty_archive():
    spec = L.cell_by_name("J_HIGH")
    g, _ = A.run_gates(A.Cell(spec, PREP / "__nonexistent__"),
                       pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    assert set(g.failed()) == set(L.GATE_IDS), \
        f"these passed with NO data: {[x for x in L.GATE_IDS if x not in g.failed()]}"


# ═══════════════════════════════════════════════════════════════════════════ #
# 12. THE ADJUDICATOR, END TO END                                             #
# ═══════════════════════════════════════════════════════════════════════════ #
def _full_run(tmp_path, monkeypatch, targets=None, *, revs=None, pins=None,
              blind="b" * 40, pinned="b" * 40):
    """A complete eight-cell run directory with per-box provenance, adjudicated."""
    targets = targets or {}
    revs = revs or {}
    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=targets.get(spec.name, 0.0),
                         blind=blind, pinned=pinned,
                         rev=revs.get(spec.name))
    pins = pins or {r: pinned for r in L.BOX_ROLES}
    for role, pin in pins.items():
        p = tmp_path / L.provenance_subdir(role)
        p.mkdir(parents=True, exist_ok=True)
        (p / "PINNED_SRC_REV").write_text(pin)
        (p / "BLIND_COMMIT").write_text(blind)
        (p / L.WHEEL_PROBE_FILENAME).write_text(json.dumps(_healthy_probe()))
    monkeypatch.setattr(A, "blind_facts", lambda *a, **k: {
        "ok": True, "blind_commit": blind, "is_ancestor_of_head": True,
        "introduced_frozen_banner": True, "proof_ok": True, "why": ""})
    monkeypatch.setattr(A, "src_clean_facts", lambda *a, **k: {
        "ok": True, "boundaries": ["pre-flight"], "dirty_boundaries": [],
        "has_preflight": True, "missing_after": [], "why": ""})
    monkeypatch.setattr(A, "wheel_ancestry_facts", lambda *a, **k: {
        "ok": True, "rev": "deadbeefcafe", "invasion_source_present": True,
        "is_ancestor": True, "why": ""})
    return A.adjudicate(tmp_path)


def test_a_clean_eight_cell_round_reads_FAMILY_PARKS(tmp_path, monkeypatch):
    rep = _full_run(tmp_path, monkeypatch)
    assert rep["round_branch"] == "FAMILY-PARKS", \
        {n: c["branch"] for n, c in rep["cells"].items()}
    assert rep["cross_box_rev_ok"]


def test_a_firing_joint_cell_reads_PROMOTE_JOINT_end_to_end(tmp_path, monkeypatch):
    """⭐⭐ THE ADOPTION-CHAIN BRANCH, driven all the way through the adjudicator."""
    rep = _full_run(tmp_path, monkeypatch, {"J_HIGH": 3.0})
    assert rep["round_branch"] == "PROMOTE-JOINT"
    assert rep["cells"]["J_HIGH"]["branch"] == "PROMOTE"
    jr = rep["cells"]["J_HIGH"]["joint_reading"]
    assert "PROMOTE-JOINT" in jr
    assert L.JOINT_ATTRIBUTION_BAN in jr, "a FIRING joint must still carry the ban"


def test_a_null_joint_cell_still_carries_the_attribution_ban(tmp_path, monkeypatch):
    rep = _full_run(tmp_path, monkeypatch)
    for n in ("J_LOW", "J_HIGH"):
        assert rep["cells"][n]["branch"] == "NULL"
        assert L.JOINT_ATTRIBUTION_BAN in rep["cells"][n]["joint_reading"]
        assert "BOUND ON THE PACKAGE, NOT ON EITHER TERM" in \
            rep["cells"][n]["joint_reading"]


def test_a_firing_C_cell_alone_never_reaches_the_chain(tmp_path, monkeypatch):
    rep = _full_run(tmp_path, monkeypatch, {"C_MID": 3.0})
    assert rep["round_branch"] == "DEFENDS-C"
    assert L.C_NEVER_PROMOTES_ALONE in rep["cells"]["C_MID"]["c_reading"]


def test_the_adjudicator_computes_both_contrast_families(tmp_path, monkeypatch):
    rep = _full_run(tmp_path, monkeypatch,
                    {"A_LOW": 0.0, "A_MID": 3.0, "A_HIGH": 0.0})
    assert set(rep["contrasts"]) == set(L.SHAPES)
    assert set(rep["interior_lifts"]) == set(L.SHAPES)
    assert rep["interior_lifts"]["A"]["verdict"] == "INTERIOR PEAK RESOLVED"
    assert rep["interior_lifts"]["J"]["verdict"] == "NOT APPLICABLE"
    assert rep["noise_signature"]["A"]["fired"], \
        "a mid at z=3 between two z=0 neighbours is a noise signature"
    assert not rep["noise_signature"]["J"]["applicable"]


def test_a_cross_box_short_sha_difference_does_NOT_void_the_round(tmp_path,
                                                                 monkeypatch):
    """⭐⭐ IS-A1, END TO END: round 2's exact false void must not recur."""
    pin = "b" * 40
    revs = {c.name: (pin[:8] if c.box == "local" else pin[:10]) + "-dirty"
            for c in L.CELLS}
    rep = _full_run(tmp_path, monkeypatch, revs=revs, pinned=pin)
    assert rep["cross_box_rev_ok"], rep["cross_box_rev_gate"]["why"]
    assert rep["round_branch"] != "U-UNREADABLE"
    for c in rep["cells"].values():
        assert c["gates"]["G-REV"]["ok"]


def test_a_genuine_cross_box_rev_disagreement_voids_G_REV_everywhere(tmp_path,
                                                                     monkeypatch):
    pin = "b" * 40
    revs = {c.name: (pin[:8] if c.box == "local" else "deadbee1") for c in L.CELLS}
    rep = _full_run(tmp_path, monkeypatch, revs=revs, pinned=pin)
    assert not rep["cross_box_rev_ok"]
    assert rep["round_branch"] == "U-UNREADABLE"
    for c in rep["cells"].values():
        assert not c["gates"]["G-REV"]["ok"]
        assert "EXPECTED, harmless and PASSES (IS-A1)" in c["gates"]["G-REV"]["note"]


def test_disagreeing_box_pins_void_the_round(tmp_path, monkeypatch):
    pin = "b" * 40
    rep = _full_run(tmp_path, monkeypatch, pinned=pin,
                    pins={"local": pin, "laptop": "c" * 40})
    assert not rep["cross_box_rev_ok"]
    assert "DIFFERENT COMMITS" in rep["cross_box_rev_gate"]["why"]


def test_a_failed_G_WHEEL_SAME_voids_ALL_EIGHT_cells(tmp_path, monkeypatch):
    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec)
    d = tmp_path / L.cell_by_name("A_LOW").out_subdir
    man = json.loads((d / "manifest.json").read_text())
    man["carc_rs_binary_sha"] = "0" * 16
    (d / "manifest.json").write_text(json.dumps(man))
    for role in L.BOX_ROLES:
        p = tmp_path / L.provenance_subdir(role)
        p.mkdir(parents=True, exist_ok=True)
        (p / "PINNED_SRC_REV").write_text("b" * 40)
        (p / "BLIND_COMMIT").write_text("b" * 40)
        (p / L.WHEEL_PROBE_FILENAME).write_text(json.dumps(_healthy_probe()))
    monkeypatch.setattr(A, "blind_facts", lambda *a, **k: {"ok": True, "why": ""})
    monkeypatch.setattr(A, "src_clean_facts", lambda *a, **k: {"ok": True, "why": ""})
    monkeypatch.setattr(A, "wheel_ancestry_facts", lambda *a, **k: {"ok": True, "why": ""})
    rep = A.adjudicate(tmp_path)
    assert rep["round_branch"] == "U-UNREADABLE"
    assert not rep["wheel_same"]["ok"]
    for n, c in rep["cells"].items():
        assert not c["gates"]["G-WHEEL-SAME"]["ok"], n


def test_the_adjudicator_reads_each_cell_against_its_OWN_BOXS_provenance(
        tmp_path, monkeypatch):
    """⭐ Each box publishes its own pin; the local box's laptop cells must be
    read against the LAPTOP's copy."""
    rep = _full_run(tmp_path, monkeypatch)
    for role in L.BOX_ROLES:
        assert rep["provenance"][role]["is_per_box"], role
        assert str(tmp_path) in rep["provenance"][role]["dir"]


def test_the_render_prints_every_mandatory_section(tmp_path, monkeypatch):
    rep = _full_run(tmp_path, monkeypatch, {"J_HIGH": 2.5})
    out = A.render(rep)
    for section in ("§3.4 THE INHERITED IDENT", "§6.5 THE TWO-BOX SPLIT",
                    "§4.3(1) PER CELL",
                    "§4.5 THE PRE-REGISTERED WITHIN-ROUND LOW-vs-HIGH CONTRAST",
                    "§4.5b THE INTERIOR LIFT",
                    "§4.5c ROUNDS 1 AND 2",
                    "§4.7 THE LADDER RULES", "§4.3(5) GATES (all 19",
                    "§4.3(4) POWER", "§4.3(6) INVASION-ARITHMETIC COST MULTIPLIER",
                    "§4.3(7) THE FROZEN INPUTS AND THE WEIGHT DERIVATION",
                    "§4.3(8) THE LADDER AS RUN", "§4.6 SHAPE C'S OPPONENT",
                    "§4.6b THE JOINT CELLS", "§4.8 WHAT `FAMILY-PARKS` WOULD PARK",
                    "§5 WHAT NO BRANCH DOES", "§6 THE STATED PRIOR"):
        assert section in out, section


def test_the_render_prints_the_joint_reading_on_every_J_cell(tmp_path, monkeypatch):
    out = A.render(_full_run(tmp_path, monkeypatch))
    assert out.count("§4.6b JOINT READING:") == 2
    assert out.count("§4.6 DEFENCE READING:") == 3


def test_the_render_labels_the_joint_cost_as_the_unmeasured_input(tmp_path,
                                                                  monkeypatch):
    out = A.render(_full_run(tmp_path, monkeypatch))
    assert "the CANDIDATE pays it TWICE on a J cell" in out
    assert "gamma-vs-alpha, NOT term-vs-plain" in out


def test_the_render_prints_all_three_rounds_on_one_axis_and_fences_them(
        tmp_path, monkeypatch):
    out = A.render(_full_run(tmp_path, monkeypatch))
    assert "r3:" in out and "r2:" in out and "r1:" in out
    assert "NEVER pooled, NEVER z-combined" in out
    assert "NO PRIOR ROUND HAS A JOINT POINT" in out


def test_the_render_prints_the_power_headline_and_the_derivation(tmp_path,
                                                                 monkeypatch):
    out = A.render(_full_run(tmp_path, monkeypatch))
    assert "POWERED TO RESOLVE" in out
    assert "FIRST ROUND THAT **PICKS** WEIGHTS" in out
    assert "WEAKEST input" in out


# ═══════════════════════════════════════════════════════════════════════════ #
# 13. §5's NO-OVER-READ LIST, AND THE STATED PRIOR                            #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_no_over_read_list_carries_round_2s_items_and_extends_them():
    joined = " ".join(L.NO_BRANCH_DOES)
    # carried
    for needle in ("2752 is the SCREENING budget", "DISJOINT",
                   "C's opponent is a shape-B invader", "four-link adoption chain",
                   "shape D", "ms/move ratio", "G-WHEEL-SAME",
                   "compares a LOCAL cell to a LAPTOP cell"):
        assert needle in joined, needle
    # extended for round 3
    for needle in ("JOINT cell as evidence about invasion_beta OR invasion_gamma",
                   "SUM of an A margin and a C margin",
                   "THREE BANDS NOW",
                   "the round-2 cell of the SAME NAME",
                   "shape B AS A CANDIDATE",
                   "W_LOCAL=14"):
        assert needle in joined, needle


def test_the_no_over_read_list_forbids_pooling_with_BOTH_prior_rounds():
    joined = " ".join(L.NO_BRANCH_DOES)
    assert "round-1 or a round-2 reading" in joined or \
        "round-1 or round-2 reading" in joined
    assert "CL-068" in joined


def test_the_stated_prior_is_a_distribution_and_names_the_modal_outcome():
    p = L.STATED_PRIOR
    pcts = [int(x) for x in re.findall(r"~(\d+)%", p)]
    assert 95 <= sum(pcts) <= 105, f"the prior sums to {sum(pcts)}%"
    assert "FAMILY-PARKS" in p and "PROMOTE-JOINT" in p
    assert "J_HIGH is the single most likely firing cell" in p
    assert "0.36" in p, "the reversal mechanism must be priced as out-of-range"


def test_the_overlay_rule_permits_the_derivation_and_forbids_everything_else():
    r = L.OVERLAY_RULE
    assert "DESCRIPTIVE OVERLAY ONLY" in r
    assert "NEVER pooled" in r and "NEVER a branch input" in r
    assert "Choosing where to look is not combining readings" in r


# ═══════════════════════════════════════════════════════════════════════════ #
# 14. THE PAIR AS SHIPPED                                                     #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_pair_files_all_exist():
    for f in ("DESIGN.md", "READ_RULE.md", "AMENDMENTS.md", "DEVIATIONS.md",
              "WORKERS.conf", "run_cells.sh", "screen_lib.py", "analyze_screen.py",
              "BAND_CLAIM.json", "BLIND_COMMIT"):
        assert (PREP / f).is_file(), f
    for name in L.LEAF_JSON_BODIES:
        assert (PREP / name).is_file(), name
    assert (PREP / "selftest_fixture" / "manifest.json").is_file()


def test_band_claimed_sentinel_is_NOT_present_at_freeze():
    """⛔ The executor interlock. This build never claims a band and never funds
    itself."""
    assert not (PREP / "BAND_CLAIMED").exists()


def test_the_executor_owed_artifacts_are_NOT_present_at_freeze():
    for f in ("PINNED_SRC_REV", "SRC_CLEAN.jsonl", "BLIND_PROOF.json",
              "WHEEL_PROBE.json", "RUN_LIVE.json"):
        assert not (PREP / f).exists(), f


def test_the_design_and_read_rule_carry_the_frozen_banner():
    for f in ("DESIGN.md", "READ_RULE.md"):
        assert "STATUS: FROZEN" in (PREP / f).read_text(), f


def test_the_design_and_read_rule_carry_the_frozen_numbers():
    design = (PREP / "DESIGN.md").read_text()
    rule = (PREP / "READ_RULE.md").read_text()
    assert str(L.BAND) in design and str(L.BAND) in rule
    for c in L.CELLS:
        assert c.cand_leaf_hash in design, c.name
        assert str(c.seed_start) in design, c.name
    for f in (design, rule):
        assert "limit local to w14 starting at 11am" in f, \
            "the owner constraint must be quoted in BOTH halves of the pair"


def test_read_rule_names_every_gate_and_every_round_branch():
    rule = (PREP / "READ_RULE.md").read_text()
    for gid in L.GATE_IDS:
        assert gid in rule, gid
    for br in ("PROMOTE-JOINT", "PROMOTE-A", "DEFENDS-C", "BRACKET-CONTINUE",
               "REVERSED-", "FAMILY-PARKS", "U-UNREADABLE"):
        assert br in rule, br


def test_the_pair_states_the_attribution_ban_in_both_halves():
    design = (PREP / "DESIGN.md").read_text()
    rule = (PREP / "READ_RULE.md").read_text()
    for f, label in ((design, "DESIGN.md"), (rule, "READ_RULE.md")):
        assert "ATTRIBUT" in f.upper(), label
        assert "ABLATION" in f.upper(), label


def test_the_amendments_file_carries_IS_A1_forward_as_inherited_and_folded():
    a = (PREP / "AMENDMENTS.md").read_text()
    assert "IS-A1" in a
    assert "cross_box_rev_gate" in a
    assert "NONE YET" in a.upper(), "round 3 has no amendments of its OWN yet"


def test_band_claim_row_names_this_band_and_parses_as_eight_csv_fields():
    import csv
    claim = json.loads((PREP / "BAND_CLAIM.json").read_text())
    row = next(csv.reader([claim["_csv_row"]]))
    assert len(row) == 8, f"got {len(row)} fields"
    assert int(row[0]) == L.BAND


def test_the_band_claim_allocation_matches_the_library():
    claim = json.loads((PREP / "BAND_CLAIM.json").read_text())
    cells = {c["cell"]: c for c in claim["cells"]}
    assert set(cells) == set(L.CELL_NAMES)
    for c in L.CELLS:
        assert cells[c.name]["seed_start"] == c.seed_start
        assert cells[c.name]["seed_end"] == c.seed_end
        assert cells[c.name]["cand_leaf"] == c.cand_leaf_hash
        assert cells[c.name]["opp_leaf"] == c.opp_leaf_hash
        assert cells[c.name]["box"] == c.box


def test_blind_commit_is_pending_or_a_real_sha():
    v = (PREP / "BLIND_COMMIT").read_text().strip()
    assert v == "PENDING" or re.fullmatch(r"[0-9a-f]{40}", v), v


def test_selftest_exits_zero():
    r = subprocess.run([sys.executable, str(PREP / "analyze_screen.py"), "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELFTEST GREEN" in r.stdout


def test_selftest_fixture_is_a_real_emitted_archive_not_a_synthesis():
    man = json.loads((_FIXTURE_DIR / "manifest.json").read_text())
    assert man.get("code_rev") and man.get("config") and man.get("carc_rs_build")
    assert len(list(_FIXTURE_DIR.glob("seed*_a*.json"))) == L.FIXTURE_SPEC.n_games


def test_the_fixture_spec_is_not_a_round_3_cell():
    assert L.FIXTURE_SPEC.name not in L.CELL_NAMES
    assert L.FIXTURE_SPEC.shape not in L.SHAPES
    assert L.FIXTURE_SPEC.seed_start < L.BAND


def test_adjudicator_never_writes_results_csv():
    src = (PREP / "analyze_screen.py").read_text()
    assert "results.csv" in src, "the prohibition must be STATED"
    assert "NEVER writes experiments/results.csv" in src
    assert "to_csv" not in src and "results_csv" not in src.replace(
        "no-results-csv", "")
