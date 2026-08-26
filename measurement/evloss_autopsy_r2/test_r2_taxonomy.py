#!/usr/bin/env python3
"""Tests for the R2 classifier's mechanical feature extraction and its estimator copy.

Run:  pytest -q measurement/evloss_autopsy_r2/test_r2_taxonomy.py

Fixtures are small hand-built `taxonomy` blocks in the exact shape
`03_build_positions.py` writes into `positions_meta.jsonl`. No corpus, no judge records,
no network — these tests pin the PREDICATES, which is what the blind stamp is protecting.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from r2_estimator import cluster_sandwich, contrast_cluster, hajek, holm, two_sided_p  # noqa: E402
from r2_taxonomy import (  # noqa: E402
    CONTEST_FLAGS, DECISIVE_FARM_SHARE, EXPLOIT_BUCKETS, MOVE_KIND_BUCKETS,
    PHASE_BUCKETS, STRATUM_BUCKETS, axis_of, classify, exploit_labels, farm_engaged,
)


def tax(**kw):
    """A neutral covariate block; override only what a test is about."""
    base = {
        "structure": "road", "degenerate": False, "stratum": "ROAD",
        "decision_type": "tile", "phase_third": "middle",
        "move_kind_best": "tile", "move_kind_played": "tile",
        "commit_direction": "n/a", "meeple_axis": None,
        "contested_best": [], "contested_played": [],
        "reinforce_losing_contest_best": False, "reinforce_losing_contest_played": False,
        "tie_force_join_best": False, "tie_force_join_played": False,
        "score_diff": 0, "score_diff_bucket": "level",
        "own_reserve": 5, "opp_reserve": 5,
        "farm_share": None, "total_leaf_diff": 1.0, "farm_leaf_diff": 0.0,
        "alias_group_size": 1, "n_alias_groups": 10, "n_eligible": 10,
        "cross_world_spread": 0.25, "cross_world_spread_status": "ok_per_world_routeb",
        "cross_world_n_distinct": 2, "cross_world_q_spread": 0.05,
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# farm_engaged — the H4 mechanical predicate                                   #
# --------------------------------------------------------------------------- #
def test_farm_engaged_false_on_a_pure_road_ply():
    assert farm_engaged(tax()) is False


@pytest.mark.parametrize("override", [
    {"stratum": "FARM"},
    {"structure": "farm"},
    {"move_kind_best": "farm"},
    {"move_kind_played": "farm"},
    {"contested_best": ["farm"]},
    {"contested_played": ["city", "farm"]},
])
def test_farm_engaged_fires_on_every_declared_route(override):
    assert farm_engaged(tax(**override)) is True


def test_farm_engaged_ignores_non_farm_contested_kinds():
    assert farm_engaged(tax(contested_best=["city", "road", "cloister"])) is False


# --------------------------------------------------------------------------- #
# H2 — the steal                                                               #
# --------------------------------------------------------------------------- #
def test_h2_steal_available_taken_and_foregone_are_consistent():
    # steal on the table, champion declined  -> AVAILABLE + FOREGONE, not TAKEN
    lab = exploit_labels(tax(tie_force_join_best=True, tie_force_join_played=False))
    assert lab["H2_STEAL_AVAILABLE"] is True
    assert lab["H2_STEAL_FOREGONE"] is True
    assert lab["H2_STEAL_TAKEN"] is False

    # steal on the table and taken -> AVAILABLE + TAKEN, not FOREGONE
    lab = exploit_labels(tax(tie_force_join_best=True, tie_force_join_played=True))
    assert lab["H2_STEAL_AVAILABLE"] is True
    assert lab["H2_STEAL_TAKEN"] is True
    assert lab["H2_STEAL_FOREGONE"] is False

    # champion stole where the runner-up did not -> TAKEN only
    lab = exploit_labels(tax(tie_force_join_best=False, tie_force_join_played=True))
    assert lab["H2_STEAL_AVAILABLE"] is False
    assert lab["H2_STEAL_TAKEN"] is True
    assert lab["H2_STEAL_FOREGONE"] is False


def test_h2_reinforce_losing_reads_the_PLAYED_arm_only():
    assert exploit_labels(
        tax(reinforce_losing_contest_played=True))["H2_REINFORCE_LOSING"] is True
    assert exploit_labels(
        tax(reinforce_losing_contest_best=True))["H2_REINFORCE_LOSING"] is False


def test_h2xh4_farm_steal_needs_both_halves():
    assert exploit_labels(tax(tie_force_join_best=True,
                              contested_best=["farm"]))["H2xH4_FARM_STEAL"] is True
    assert exploit_labels(tax(tie_force_join_best=True,
                              contested_best=["city"]))["H2xH4_FARM_STEAL"] is False
    assert exploit_labels(tax(tie_force_join_best=False,
                              contested_best=["farm"]))["H2xH4_FARM_STEAL"] is False


# --------------------------------------------------------------------------- #
# H4 — late / decisive farm                                                    #
# --------------------------------------------------------------------------- #
def test_h4_late_farm_requires_endgame_AND_farm_engagement():
    assert exploit_labels(tax(phase_third="endgame",
                              stratum="FARM"))["H4_LATE_FARM"] is True
    assert exploit_labels(tax(phase_third="middle",
                              stratum="FARM"))["H4_LATE_FARM"] is False
    assert exploit_labels(tax(phase_third="endgame"))["H4_LATE_FARM"] is False


def test_h4_decisive_farm_cut_is_at_the_pre_registered_share():
    assert DECISIVE_FARM_SHARE == 0.5
    hi = exploit_labels(tax(phase_third="endgame", stratum="FARM", farm_share=0.5))
    lo = exploit_labels(tax(phase_third="endgame", stratum="FARM", farm_share=0.49))
    assert hi["H4_DECISIVE_FARM"] is True     # the cut is INCLUSIVE at 0.5
    assert lo["H4_DECISIVE_FARM"] is False


def test_h4_decisive_farm_is_false_when_farm_share_is_none():
    """`farm_share` is None on degenerate plies — must not crash, must not fire."""
    lab = exploit_labels(tax(phase_third="endgame", stratum="DEG", structure="farm",
                             degenerate=True, farm_share=None))
    assert lab["H4_LATE_FARM"] is True
    assert lab["H4_DECISIVE_FARM"] is False


def test_h4_decisive_implies_late_farm():
    for share in (0.0, 0.3, 0.5, 0.9, 1.0):
        lab = exploit_labels(tax(phase_third="endgame", stratum="FARM", farm_share=share))
        assert not lab["H4_DECISIVE_FARM"] or lab["H4_LATE_FARM"]


# --------------------------------------------------------------------------- #
# classify() — the full pre-registered family                                  #
# --------------------------------------------------------------------------- #
def test_partition_axes_are_partitions_of_one_position():
    lab = classify(tax(stratum="CITY", decision_type="tile", phase_third="opening"), 0.30)
    assert sum(lab[f"structure={b}"] for b in STRATUM_BUCKETS) == 1
    assert sum(lab[f"phase_third={b}"] for b in PHASE_BUCKETS) == 1
    assert lab["decision_type=tile"] and not lab["decision_type=meeple"]
    assert lab["f7_cross_world_spread=low"] ^ lab["f7_cross_world_spread=high"]


def test_move_kind_axis_is_empty_on_a_tile_ply_and_singular_on_a_meeple_ply():
    tile = classify(tax(decision_type="tile", move_kind_played="tile"), 0.3)
    assert sum(tile[f"move_kind={b}"] for b in MOVE_KIND_BUCKETS) == 0
    meep = classify(tax(decision_type="meeple", move_kind_played="farm"), 0.3)
    assert sum(meep[f"move_kind={b}"] for b in MOVE_KIND_BUCKETS) == 1
    assert meep["move_kind=farm"]


def test_f7_median_split_is_inclusive_low_and_handles_unavailable():
    at_median = classify(tax(cross_world_spread=0.30), 0.30)
    assert at_median["f7_cross_world_spread=low"] is True
    above = classify(tax(cross_world_spread=0.31), 0.30)
    assert above["f7_cross_world_spread=high"] is True
    missing = classify(tax(cross_world_spread=None,
                           cross_world_spread_status="unavailable_pooled_only"), 0.30)
    assert missing["f7_cross_world_spread=low"] is False
    assert missing["f7_cross_world_spread=high"] is False


def test_contest_flags_treat_a_nonempty_LIST_as_true():
    lab = classify(tax(contested_best=["city"], contested_played=[]), 0.3)
    assert lab["contest=contested_best"] is True
    assert lab["contest=contested_played"] is False


def test_family_shape_is_the_pre_registered_one():
    lab = classify(tax(), 0.3)
    assert len(lab) == 26 + len(EXPLOIT_BUCKETS)
    assert len([k for k in lab if k.startswith("contest=")]) == len(CONTEST_FLAGS)
    assert axis_of("structure=DEG") == "structure"
    assert axis_of("H4_LATE_FARM") == "exploit"


def test_classifier_cannot_see_an_outcome():
    """The blind guarantee, mechanically: classify() takes ONLY the covariate block."""
    import inspect
    src = inspect.getsource(classify) + inspect.getsource(exploit_labels) \
        + inspect.getsource(farm_engaged)
    # NB "ok_per_world_routeb" is F7's COVARIATE status string (per-world root stats from
    # the subject pass), not a judged value — hence "per_world_delta", not "per_world".
    for forbidden in ("R_champ", "delta", "values_a", "values_b", "G_search",
                      "per_world_delta", "judge", "oracle"):
        assert forbidden not in src


# --------------------------------------------------------------------------- #
# estimator copy — arithmetic pins                                             #
# --------------------------------------------------------------------------- #
def test_hajek_is_a_weighted_mean():
    assert hajek([1.0, 3.0], [1.0, 3.0]) == pytest.approx(2.5)


def test_cluster_sandwich_matches_a_hand_computed_two_cluster_case():
    vals, wts, grp = [0.0, 2.0, 4.0, 6.0], [1.0, 1.0, 1.0, 1.0], ["a", "a", "b", "b"]
    se, deff, G = cluster_sandwich(vals, wts, grp)
    assert G == 2
    mu = 3.0
    e = [v - mu for v in vals]
    s = [e[0] + e[1], e[2] + e[3]]
    expect = math.sqrt((2 / 1) * (s[0] ** 2 + s[1] ** 2) / 16.0)
    assert se == pytest.approx(expect)


def test_cluster_sandwich_is_nan_below_two_clusters():
    se, _, G = cluster_sandwich([1.0, 2.0], [1.0, 1.0], ["a", "a"])
    assert G == 1 and math.isnan(se)


def test_contrast_is_the_difference_of_the_two_hajek_means():
    vals = [1.0, 2.0, 10.0, 11.0]
    wts = [1.0, 2.0, 1.0, 3.0]
    grp = ["a", "a", "b", "b"]
    member = [True, True, False, False]
    theta, se, z = contrast_cluster(vals, wts, grp, member)
    assert theta == pytest.approx(hajek(vals[:2], wts[:2]) - hajek(vals[2:], wts[2:]))
    assert se > 0 and z == pytest.approx(theta / se)


def test_contrast_is_nan_when_a_side_is_empty():
    theta, se, z = contrast_cluster([1.0, 2.0], [1.0, 1.0], ["a", "b"], [True, True])
    assert math.isnan(theta) and math.isnan(z)


def test_holm_is_monotone_and_bonferroni_at_the_smallest_p():
    p = {"a": 0.001, "b": 0.02, "c": 0.5}
    r = holm(p)
    assert r["a"]["p_holm"] == pytest.approx(0.003)
    assert r["b"]["p_holm"] >= r["a"]["p_holm"]
    assert r["c"]["p_holm"] >= r["b"]["p_holm"]
    assert r["a"]["reject"] and not r["c"]["reject"]


def test_two_sided_p_of_1_96_is_about_five_percent():
    assert two_sided_p(1.959964) == pytest.approx(0.05, abs=1e-6)


# --------------------------------------------------------------------------- #
# G_search identity                                                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ds,expected_R,expected_G", [
    ({"leaf": -1.0, "sib2": 2.0, "sib3": 0.5}, 2.0, 1.0),
    ({"leaf": 3.0, "sib2": 1.0}, 3.0, -3.0),
    ({"sib2": -2.0, "sib3": -1.0}, 0.0, 0.0),      # leaf leg absent (A6) => D_leaf = 0
    ({"leaf": -5.0, "sib2": -4.0}, 0.0, 5.0),
])
def test_G_search_equals_minus_D_leaf_and_R_champ_is_the_clamped_argmax(
        ds, expected_R, expected_G):
    d_leaf = ds.get("leaf", 0.0)
    R = max(0.0, max(ds.values()))
    G = -d_leaf
    assert R == pytest.approx(expected_R)
    assert G == pytest.approx(expected_G)
    # the identity R_leaf = R_champ + G_search must hold arm-for-arm
    R_leaf = max(0.0, max(ds.values())) - d_leaf
    assert R_leaf == pytest.approx(R + G)
