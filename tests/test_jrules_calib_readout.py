"""Unit tests for the MECHANICAL application of the J-rules CALIB_READ_RULE.

`measurement/jrules_on_search_20260813/make_calib_readout.py` turns the calibration's
`SUMMARY.json` into a branch by CODE, so the branch cannot be chosen by a reader who has
already seen the ladder. These tests walk §3.4's exhaustive outcome→branch table with
synthetic ladders — no searches, no archives, no engine.

Written alongside the rule-applier and BEFORE the calibration's SUMMARY.json was read.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_MOD_PATH = REPO / "measurement" / "jrules_on_search_20260813" / "make_calib_readout.py"


def _load():
    spec = importlib.util.spec_from_file_location("jrules_make_calib_readout", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mk = _load()

N = 1556


def _cells(rates: dict) -> dict:
    """{dose: flip_rate} -> the `cells` dict `decide()` consumes."""
    out = {}
    for i, (dose, f) in enumerate(sorted(rates.items())):
        k = round(f * N)
        # A Wilson interval that is honest about the bar: computed the same way the
        # instrument does, so the `marginal` label is exercised for real.
        import math
        z = 1.959963984540054
        z2 = z * z
        denom = N + z2
        centre = (k + z2 / 2.0) / denom
        half = (z / denom) * math.sqrt(k * (N - k) / N + z2 / 4.0)
        out[mk.cell_name(dose)] = {
            "dose": dose, "mask": 31, "rules": ["J1", "J2", "J5", "J6", "J8"],
            "leaf_hash": f"cafe00000000000{i}", "flips": k, "n": N, "flip_rate": f,
            "wilson95": [max(0.0, centre - half), min(1.0, centre + half)],
            "wilson95_half_width": half,
            "phase_split": {"tiles": k, "meeples": 0, "other": {}, "tile_share": 1.0},
        }
    return out


def _summary(rates: dict, *, match=True, mask=31, champ_hash=False) -> dict:
    cells = _cells(rates)
    if mask != 31:
        for c in cells.values():
            c["mask"] = mask
    if champ_hash:
        list(cells.values())[0]["leaf_hash"] = mk.CHAMP_LEAF_HASH
    return {
        "arms": {n: {"flips_total": c["flips"], "n_graded": c["n"],
                     "flip_rate": c["flip_rate"], "wilson95": c["wilson95"],
                     "wilson95_half_width": c["wilson95_half_width"],
                     "phase_split": c["phase_split"]} for n, c in cells.items()},
        "arm_knobs": {n: {"dose": c["dose"], "mask": c["mask"], "rules": c["rules"],
                          "leaf_hash": c["leaf_hash"]} for n, c in cells.items()},
        "all_replay_scores_match": match,
        "replay_scores_mismatch_archives": ([] if match else ["g9.json"]),
        "n_games": 26, "n_graded_plies": N,
        "rules_profile_histogram": {"fixed_v1": 23, "walled": 2, "app_aug2": 1},
        "champ_agrees_archive_rate": 0.62,
    }


# --------------------------------------------------------------------------- #
# cell naming — must match the instrument's DEFAULT_ARM_SPECS exactly          #
# --------------------------------------------------------------------------- #
def test_cell_names_match_the_instrument():
    jr_path = REPO / "scripts" / "classical_search" / "jrules_e4_replay.py"
    spec = importlib.util.spec_from_file_location("jrules_e4_replay_for_readout", jr_path)
    jr = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = jr
    spec.loader.exec_module(jr)
    arms = jr.parse_arms(jr.DEFAULT_ARM_SPECS)
    assert [mk.cell_name(a.dose) for a in arms] == [a.name for a in arms]
    finer = jr.parse_arm(jr.FINER_RUNG_ARM_SPEC)
    assert mk.cell_name(finer.dose) == finer.name == "d0p25"
    assert mk.MASK == jr.DEFAULT_MASK == 31
    assert tuple(mk.DOSES) == tuple(a.dose for a in arms)


# --------------------------------------------------------------------------- #
# §3.4 — the exhaustive outcome -> branch table                                #
# --------------------------------------------------------------------------- #
def test_finer_rung_fires_when_dose_one_exceeds_twenty_percent():
    v = mk.decide(_cells({0.5: 0.09, 1.0: 0.2001, 2.0: 0.31}))
    assert v["branch"] == "FINER-RUNG"
    assert v["fundable"] is False and v["funded_cells"] == []
    assert "0.25" in v["next_action"]


def test_finer_rung_beats_funding_even_when_a_rung_clears():
    """§3.1 is evaluated BEFORE §3.2 — nothing is funded until 0.25 is measured."""
    v = mk.decide(_cells({0.5: 0.15, 1.0: 0.28, 2.0: 0.40}))
    assert v["branch"] == "FINER-RUNG"


def test_finer_rung_does_not_fire_at_exactly_twenty_percent():
    """The rule says STRICTLY greater than 0.20."""
    v = mk.decide(_cells({0.5: 0.11, 1.0: 0.20, 2.0: 0.30}))
    assert v["branch"] == "FUND-SMALLEST"
    assert v["chosen_dose"] == 0.5


def test_finer_rung_fires_once_then_the_extended_ladder_is_read():
    cells = _cells({0.25: 0.12, 0.5: 0.19, 1.0: 0.26, 2.0: 0.38})
    v = mk.decide(cells)
    assert v["branch"] == "FUND-SMALLEST"
    assert v["chosen_cell"] == "d0p25" and v["chosen_dose"] == 0.25


def test_finer_rung_present_but_below_bar_falls_through_to_the_next_clearing_dose():
    v = mk.decide(_cells({0.25: 0.04, 0.5: 0.13, 1.0: 0.25, 2.0: 0.40}))
    assert v["branch"] == "FUND-SMALLEST"
    assert v["chosen_dose"] == 0.5


@pytest.mark.parametrize("rates,dose", [
    ({0.5: 0.11, 1.0: 0.14, 2.0: 0.18}, 0.5),
    ({0.5: 0.07, 1.0: 0.12, 2.0: 0.19}, 1.0),
    ({0.5: 0.03, 1.0: 0.06, 2.0: 0.11}, 2.0),
])
def test_fund_smallest_names_the_smallest_clearing_dose(rates, dose):
    v = mk.decide(_cells(rates))
    assert v["branch"] == "FUND-SMALLEST"
    assert v["chosen_dose"] == dose
    assert v["funded_cells"] == [mk.cell_name(dose)]


def test_fund_smallest_funds_exactly_one_cell():
    v = mk.decide(_cells({0.5: 0.12, 1.0: 0.16, 2.0: 0.19}))
    assert len(v["funded_cells"]) == 1
    assert "RESOLVABILITY, NOT SAFETY" in v["why"]


def test_fund_smallest_is_not_the_largest_f():
    """The rule picks the smallest DOSE, never the biggest expression."""
    v = mk.decide(_cells({0.5: 0.101, 1.0: 0.19, 2.0: 0.199}))
    assert v["chosen_dose"] == 0.5


def test_non_monotone_ladder_is_read_as_measured():
    """0.25 clears, 0.5 does not — the smallest clearing dose still wins."""
    v = mk.decide(_cells({0.25: 0.11, 0.5: 0.08, 1.0: 0.13, 2.0: 0.19}))
    assert v["chosen_dose"] == 0.25


def test_exactly_at_the_bar_clears():
    v = mk.decide(_cells({0.5: 0.10, 1.0: 0.12, 2.0: 0.15}))
    assert v["branch"] == "FUND-SMALLEST"
    assert v["chosen_dose"] == 0.5


def test_marginal_label_when_wilson_lower_bound_is_below_the_bar():
    v = mk.decide(_cells({0.5: 0.1009, 1.0: 0.15, 2.0: 0.19}))
    assert v["branch"] == "FUND-SMALLEST"
    assert v["marginal"] is True          # exactly CL-080's A_d0p5 situation


def test_not_marginal_when_the_lower_bound_clears_too():
    v = mk.decide(_cells({0.5: 0.14, 1.0: 0.17, 2.0: 0.19}))
    assert v["marginal"] is False


def test_no_expression_when_nothing_clears():
    v = mk.decide(_cells({0.5: 0.02, 1.0: 0.05, 2.0: 0.09}))
    assert v["branch"] == "NO-EXPRESSION"
    assert v["fundable"] is False and v["funded_cells"] == []
    assert "above 2.0" in v["why"]


def test_no_marginal_tier_the_open_city_branch_is_not_inherited():
    """0.05 <= f < 0.10 is NO-EXPRESSION here, not FUND-MARGINAL."""
    v = mk.decide(_cells({0.5: 0.06, 1.0: 0.08, 2.0: 0.099}))
    assert v["branch"] == "NO-EXPRESSION"


def test_all_zero_ladder_is_reported_as_inert():
    v = mk.decide(_cells({0.5: 0.0, 1.0: 0.0, 2.0: 0.0}))
    assert v["branch"] == "NO-EXPRESSION"
    assert v["all_zero"] is True


# --------------------------------------------------------------------------- #
# §3.0 — the validity gate                                                     #
# --------------------------------------------------------------------------- #
def test_replay_mismatch_voids_even_a_funding_ladder():
    r = mk.build(_summary({0.5: 0.15, 1.0: 0.18, 2.0: 0.19}, match=False))
    assert r["verdict"]["branch"] == "VOID"
    assert r["verdict"]["fundable"] is False and r["verdict"]["funded_cells"] == []


def test_candidate_hashing_to_the_champion_voids():
    r = mk.build(_summary({0.5: 0.15, 1.0: 0.18, 2.0: 0.19}, champ_hash=True))
    assert r["verdict"]["branch"] == "VOID"
    assert any("silent null" in x for x in r["verdict"]["void_reasons"])


def test_wrong_mask_voids():
    r = mk.build(_summary({0.5: 0.15, 1.0: 0.18, 2.0: 0.19}, mask=8))
    assert r["verdict"]["branch"] == "VOID"


def test_a_ladder_that_is_not_the_preregistered_one_refuses_to_read():
    s = _summary({0.5: 0.15, 1.0: 0.18})          # missing the 2.0 rung
    with pytest.raises(SystemExit, match="REFUSING TO READ"):
        mk.build(s)


def test_an_extra_unauthorised_rung_refuses_to_read():
    s = _summary({0.5: 0.15, 1.0: 0.18, 2.0: 0.19, 4.0: 0.44})
    with pytest.raises(SystemExit, match="REFUSING TO READ"):
        mk.build(s)


def test_the_one_authorised_extra_rung_is_accepted():
    r = mk.build(_summary({0.25: 0.11, 0.5: 0.15, 1.0: 0.28, 2.0: 0.40}))
    assert r["verdict"]["branch"] == "FUND-SMALLEST"
    assert r["integrity"]["ladder_is_preregistered"] is True


# --------------------------------------------------------------------------- #
# the rendered markdown                                                        #
# --------------------------------------------------------------------------- #
def test_markdown_states_the_branch_the_dose_and_the_anchor():
    s = _summary({0.5: 0.13, 1.0: 0.18, 2.0: 0.19})
    r = mk.build(s)
    md = mk.to_md(r, s)
    assert "FUND-SMALLEST" in md
    assert "jrules_dose = 0.5" in md
    assert "10.09%" in md and "18.89%" in md          # the CL-080 anchor, always shown
    assert "0 games played" in md
    assert mk.READ_RULE_COMMIT in md


def test_markdown_of_a_no_expression_ladder_forbids_inflating_the_dose():
    s = _summary({0.5: 0.01, 1.0: 0.03, 2.0: 0.06})
    md = mk.to_md(mk.build(s), s)
    assert "NO-EXPRESSION" in md
    assert "Dose > 2.0 is forbidden" in md
    assert "No dose is named" in md


def test_markdown_documents_the_finer_rung_history_and_the_crn_proof():
    """When the 0.25 rung is present, the readout must say WHY it exists and HOW."""
    s = _summary({0.25: 0.11, 0.5: 0.15, 1.0: 0.28, 2.0: 0.40})
    s["merged_from"] = ["calib", "calib_d0p25"]
    s["crn_proof"] = {"archives": 26, "plies_compared": 1556,
                      "champ_picks_compared": 1556}
    md = mk.to_md(mk.build(s), s)
    assert "1b." in md and "FINER-RUNG" in md
    assert "1,556 champion picks identical" in md
    assert "no rule text was edited" in md.lower()


def test_markdown_rules_column_does_not_break_the_table():
    """`J1|J2|...` inside a markdown cell would split it into extra columns."""
    s = _summary({0.5: 0.13, 1.0: 0.18, 2.0: 0.19})
    md = mk.to_md(mk.build(s), s)
    row = [ln for ln in md.splitlines() if ln.startswith("| `d0p5` |") and "J1" in ln][0]
    assert row.count("|") == 6          # 5 columns + the trailing pipe
    assert "J1 + J2" in row
