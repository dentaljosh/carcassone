"""Contracts for the J13/J5 pre-gate instrument (`scripts/analyzer/j13_pregate.py`).

Five groups:
  A. union-find    — persistent feature identity survives component MERGES
  B. synthetic boards with KNOWN feature fates — component spans, values, closure,
     ownership, and (the strong one) agreement with `flat_leaf._final_scores`,
     which is the engine-faithful reference this instrument's terminal
     attribution must reproduce exactly
  C. touch classification — buildup / claim_now / own_growth / feed_claimed /
     contested, plus the cloister carve-out (a cloister is claimable ONLY on the
     turn its tile is placed, so an ownerless cloister is ownerless forever)
  D. the statistics — conversion, feed, shared credit and the claim race computed
     from hand-built touch/feature ledgers with arithmetic checked by hand
  E. integration — real archives replay bit-exact AND the per-feature attribution
     reconciles with the true final scores

⚠️ Group E needs `CARCASSONNE_FIX_R9=1` latched at `carcassonne_ai.base_deck`
import time, so it is exported at module import and the test SKIPS (never
silently grading the wrong farms) if another module already latched it off.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "analyzer"))
sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))

# R9 must be in the env BEFORE carcassonne_ai.base_deck imports (Rust OnceLock).
os.environ.setdefault("CARCASSONNE_FIX_R9", "1")

import env_preamble  # noqa: E402,F401  production leaf env, before carcassonne_ai
import j13_pregate as J  # noqa: E402

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_type import MeepleType  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles  # noqa: E402
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule  # noqa: E402
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet  # noqa: E402

E4_DIR = REPO / "measurement" / "e4_games"


# --------------------------------------------------------------------------- #
# synthetic-board helpers                                                       #
# --------------------------------------------------------------------------- #
def blank_state() -> CarcassonneGameState:
    """A 2-player Base+Farmers state with an EMPTY board (no start tile)."""
    st = CarcassonneGameState(tile_sets=(TileSet.BASE,),
                              supplementary_rules=(SupplementaryRule.FARMERS,),
                              players=2)
    for r in range(len(st.board)):
        for c in range(len(st.board[0])):
            st.board[r][c] = None
    st.placed_meeples = [[], []]
    st.scores = [0, 0]
    st.next_tile = None          # terminal
    st.placed_coords = set()
    st.open_positions = set()
    return st


def put(st, r: int, c: int, name: str, turns: int = 0):
    tile = base_tiles[name]
    if turns:
        tile = tile.turn(turns)
    st.board[r][c] = tile
    st.placed_coords.add(Coordinate(row=r, column=c))
    return tile


def meeple(st, player: int, r: int, c: int, side: Side,
           mtype: MeepleType = MeepleType.NORMAL):
    mp = MeeplePosition(mtype, CoordinateWithSide(Coordinate(r, c), side))
    st.placed_meeples[player].append(mp)
    return mp


def comps_of(view, terrain):
    return [k for k in view.comp_slots if k[0] == terrain]


def the_comp(view, terrain):
    got = comps_of(view, terrain)
    assert len(got) == 1, f"expected exactly one {terrain} component, got {len(got)}"
    return got[0]


# --------------------------------------------------------------------------- #
# A. persistent union-find                                                      #
# --------------------------------------------------------------------------- #
def test_dsu_find_is_identity_for_fresh_keys():
    d = J.DSU()
    assert d.find("a") == "a"
    assert d.find(("road", 1, 2, "top")) == ("road", 1, 2, "top")


def test_dsu_union_makes_one_class():
    d = J.DSU()
    d.union("a", "b")
    d.union("c", "d")
    assert d.find("a") == d.find("b")
    assert d.find("c") == d.find("d")
    assert d.find("a") != d.find("c")
    d.union("b", "c")                       # the MERGE
    assert len({d.find(x) for x in "abcd"}) == 1


def test_dsu_merge_is_order_independent():
    """The whole identity scheme rests on this: two roads that grow separately and
    later join must end as ONE feature no matter which order the unions arrive."""
    a, b = J.DSU(), J.DSU()
    a.union(1, 2); a.union(3, 4); a.union(2, 3)
    b.union(3, 4); b.union(1, 2); b.union(4, 1)
    assert len({a.find(x) for x in (1, 2, 3, 4)}) == 1
    assert len({b.find(x) for x in (1, 2, 3, 4)}) == 1


def test_persistent_identity_survives_a_merge_across_two_views():
    """Two ownerless roads, then a connector: the slots of BOTH must land in one
    persistent class even though each intermediate view saw them as separate."""
    early = blank_state()
    put(early, 9, 10, "straight_road")
    put(early, 12, 10, "straight_road")
    v0 = J.build_view(early)
    assert len(comps_of(v0, "road")) == 2

    late = blank_state()
    for r in (9, 10, 11, 12):
        put(late, r, 10, "straight_road")
    v1 = J.build_view(late)
    assert len(comps_of(v1, "road")) == 1

    puf = J.DSU()
    for view in (v0, v1):
        for slots in view.comp_slots.values():
            for s in slots[1:]:
                puf.union(slots[0], s)
    roots = {puf.find(("road", r, 10, Side.TOP)) for r in (9, 10, 11, 12)}
    assert len(roots) == 1


# --------------------------------------------------------------------------- #
# B. synthetic boards with known feature fates                                  #
# --------------------------------------------------------------------------- #
def test_road_component_spans_three_tiles_and_is_open():
    st = blank_state()
    for r in (9, 10, 11):
        put(st, r, 10, "straight_road")
    v = J.build_view(st)
    comp = the_comp(v, "road")
    assert len(v.comp_coords[comp]) == 3
    assert v.comp_finished[comp] is False
    assert v.comp_value[comp] == 3           # 1 point per tile, open or closed


def test_road_closes_when_capped_and_keeps_its_value():
    """chapel_with_road turn 0 = road on BOTTOM, turn 2 = road on TOP, so those
    two cap a vertical road. The caps are road tiles themselves => 4 tiles."""
    st = blank_state()
    put(st, 9, 10, "chapel_with_road", 0)    # road points DOWN into the run
    put(st, 10, 10, "straight_road")
    put(st, 11, 10, "straight_road")
    put(st, 12, 10, "chapel_with_road", 2)   # road points UP into the run
    v = J.build_view(st)
    comp = the_comp(v, "road")
    assert v.comp_coords[comp] == {(9, 10), (10, 10), (11, 10), (12, 10)}
    assert v.comp_finished[comp] is True
    assert v.comp_value[comp] == 4


def test_cloister_value_counts_its_neighbourhood_and_finishes_at_nine():
    st = blank_state()
    put(st, 10, 10, "chapel")
    v = J.build_view(st)
    comp = ("cloister", 10, 10)
    assert v.comp_value[comp] == 1 and v.comp_finished[comp] is False
    put(st, 10, 11, "straight_road", 1)
    assert J.build_view(st).comp_value[comp] == 2
    for (dr, dc) in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (1, -1), (1, 0), (1, 1)):
        put(st, 10 + dr, 10 + dc, "straight_road")
    v = J.build_view(st)
    assert v.comp_value[comp] == 9
    assert v.comp_finished[comp] is True


def test_owners_are_read_off_the_placed_meeples():
    st = blank_state()
    for r in (9, 10, 11):
        put(st, r, 10, "straight_road")
    meeple(st, 0, 10, 10, Side.TOP)
    v = J.build_view(st)
    comp = the_comp(v, "road")
    assert v.comp_owners[comp] == {0: 1}
    meeple(st, 1, 9, 10, Side.BOTTOM)          # same road, other seat
    v2 = J.build_view(st)
    comp2 = the_comp(v2, "road")
    assert v2.comp_owners[comp2] == {0: 1, 1: 1}
    assert J._winners_of(v2.comp_owners[comp2]) == [0, 1]


def test_winners_of_handles_majority_tie_and_empty():
    assert J._winners_of({}) == []
    assert J._winners_of({0: 0, 1: 0}) == []
    assert J._winners_of({0: 2, 1: 1}) == [0]
    assert J._winners_of({0: 1, 1: 1}) == [0, 1]       # a tie pays BOTH in full


def test_unowned_component_pays_nobody():
    """The fact the whole lever is about: an ownerless feature is worth ZERO to
    everyone, which is exactly what the production leaf already prices."""
    st = blank_state()
    put(st, 9, 10, "chapel_with_road", 0)
    put(st, 10, 10, "straight_road")
    put(st, 11, 10, "chapel_with_road", 2)
    v = J.build_view(st)
    comp = the_comp(v, "road")
    assert v.comp_finished[comp] is True and v.comp_value[comp] == 3
    assert J._winners_of(v.comp_owners.get(comp, {})) == []


@pytest.mark.parametrize("layout", ["road", "city", "cloister", "farm", "mixed"])
def test_terminal_attribution_equals_flat_final_scores(layout):
    """THE reference test. `flat_leaf._final_scores` is the engine-faithful
    terminal scorer; this instrument re-derives the same award PER COMPONENT so it
    can trace points back to a feature. The per-seat totals must agree exactly."""
    from carcassonne_ai.flat_leaf import _final_scores, decompose

    st = blank_state()
    if layout == "road":
        for r in (9, 10, 11):
            put(st, r, 10, "straight_road")
        meeple(st, 0, 10, 10, Side.TOP)
    elif layout == "city":
        put(st, 10, 10, "city_narrow")
        put(st, 10, 9, "city_top", 1)
        put(st, 10, 11, "city_top", 3)
        meeple(st, 1, 10, 10, Side.LEFT)
    elif layout == "cloister":
        put(st, 10, 10, "chapel")
        put(st, 10, 11, "straight_road", 1)
        meeple(st, 0, 10, 10, Side.CENTER)
    elif layout == "farm":
        put(st, 10, 10, "city_narrow")
        put(st, 10, 9, "city_top", 1)
        put(st, 10, 11, "city_top", 3)
        meeple(st, 0, 10, 10, Side.TOP_LEFT, MeepleType.FARMER)
    else:
        for r in (9, 10, 11):
            put(st, r, 10, "straight_road")
        put(st, 12, 10, "chapel")
        meeple(st, 0, 10, 10, Side.TOP)
        meeple(st, 1, 9, 10, Side.BOTTOM)          # same road => a TIE
        meeple(st, 0, 12, 10, Side.CENTER)

    reference = _final_scores(st, decompose(st))
    v = J.build_view(st)
    mine = [0, 0]
    for comp, counts in v.comp_owners.items():
        for w in J._winners_of(counts):
            mine[w] += int(v.comp_value.get(comp, 0))
    assert mine == list(reference[:2]), f"{layout}: {mine} != {reference}"


def test_meeple_comp_matches_the_component_the_meeple_sits_on():
    st = blank_state()
    for r in (9, 10, 11):
        put(st, r, 10, "straight_road")
    mp = meeple(st, 0, 10, 10, Side.TOP)
    from carcassonne_ai.flat_leaf import decompose
    d = decompose(st)
    v = J.build_view(st)
    assert J.meeple_comp(st, mp, d) == the_comp(v, "road")
    assert J.meeple_slot(st, mp) == ("road", 10, 10, Side.TOP)


# --------------------------------------------------------------------------- #
# C. touch classification                                                       #
# --------------------------------------------------------------------------- #
def _road_view(owner_seats=()):
    st = blank_state()
    for r in (9, 10, 11):
        put(st, r, 10, "straight_road")
    for seat, (rr, side) in owner_seats:
        meeple(st, seat, rr, 10, side)
    v = J.build_view(st)
    return v, the_comp(v, "road")


def _classify(view, comp, actor, claimed_comp=None, seen=frozenset(), prev=None):
    return J._classify_touch(comp, view.comp_slots[comp], view, prev, seen, actor,
                             claimed_comp, turn=5, k_rem=40, n_players=2)


def test_touch_ownerless_is_buildup():
    v, comp = _road_view()
    t = _classify(v, comp, actor=0)
    assert t["kind"] == "buildup" and t["terrain"] == "road" and t["actor"] == 0


def test_touch_ownerless_claimed_same_turn_is_claim_now_not_buildup():
    """A feature you claim on the same tile is already priced by the leaf; only an
    ownerless feature LEFT ownerless is the J13 quantity."""
    v, comp = _road_view()
    assert _classify(v, comp, actor=0, claimed_comp=comp)["kind"] == "claim_now"


def test_touch_own_growth_when_the_actor_already_owns_it():
    v, comp = _road_view(owner_seats=[(0, (10, Side.TOP))])
    assert _classify(v, comp, actor=0)["kind"] == "own_growth"


def test_touch_feed_claimed_when_only_the_opponent_owns_it():
    v, comp = _road_view(owner_seats=[(1, (10, Side.TOP))])
    assert _classify(v, comp, actor=0)["kind"] == "feed_claimed"


def test_touch_contested_when_both_seats_are_on_it():
    v, comp = _road_view(owner_seats=[(0, (10, Side.TOP)), (1, (9, Side.BOTTOM))])
    assert _classify(v, comp, actor=0)["kind"] == "contested"


def test_touch_creation_flag_and_value_delta():
    """`is_creation` is 'no slot of this component existed before'; `value_delta`
    is measured against the PREVIOUS view's components, so a MERGE of a 1-tile and
    a 2-tile road into a 4-tile road reads +1, not +4."""
    before = blank_state()
    put(before, 9, 10, "straight_road")
    put(before, 11, 10, "straight_road")
    put(before, 12, 10, "straight_road")
    prev = J.build_view(before)
    seen = frozenset(prev.slot_comp)

    after = blank_state()
    for r in (9, 10, 11, 12):
        put(after, r, 10, "straight_road")
    v = J.build_view(after)
    comp = the_comp(v, "road")
    t = _classify(v, comp, actor=1, seen=seen, prev=prev)
    assert t["is_creation"] is False
    assert t["value_before"] == 3 and t["value_after"] == 4 and t["value_delta"] == 1
    assert t["comp_tiles"] == 4

    fresh = _classify(v, comp, actor=1, seen=frozenset(), prev=prev)
    assert fresh["is_creation"] is True and fresh["value_before"] == 0


def test_ownerless_cloister_can_never_be_claimed_later():
    """RULES FACT the readout leans on: a meeple goes on the tile you JUST played,
    so a cloister nobody claimed on its own turn is ownerless forever. J13's
    OFFENSIVE side is inapplicable to cloisters by construction — the leaf's zero
    is the correct price there."""
    st = blank_state()
    put(st, 10, 10, "chapel")
    v = J.build_view(st)
    comp = ("cloister", 10, 10)
    assert J._classify_touch(comp, v.comp_slots[comp], v, None, frozenset(), 0,
                             None, 3, 50, 2)["kind"] == "buildup"
    # ...and it still pays nobody however full the neighbourhood gets.
    for (dr, dc) in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
        put(st, 10 + dr, 10 + dc, "straight_road")
    v2 = J.build_view(st)
    assert v2.comp_value[comp] == 9
    assert J._winners_of(v2.comp_owners.get(comp, {})) == []


# --------------------------------------------------------------------------- #
# D. the statistics                                                             #
# --------------------------------------------------------------------------- #
def _touch(actor, kind, terrain="road", turn=0, anchor=None, delta=0):
    return {"turn": turn, "actor": actor, "kind": kind, "terrain": terrain,
            "k_remaining": 40, "anchor": anchor, "is_creation": False,
            "value_before": 0, "value_after": delta, "value_delta": delta,
            "comp_tiles": 3, "owners": [], "feature": anchor}


def _feature(terrain="road", n_tiles=4, points=(0, 0), claimers=(), buildup=(0, 0)):
    return {"terrain": terrain, "n_tiles": n_tiles, "finished": True,
            "points_to": list(points), "claimers": set(claimers),
            "first_claim_turn": None, "first_claim_player": None,
            "buildup_by": list(buildup), "touches_by": list(buildup),
            "value_final": max(points)}


def test_fate_is_relative_to_the_seat():
    f = _feature(points=(6, 0), claimers=(0,))
    assert J._fate(f, 0, 2) == ("self", "self")
    assert J._fate(f, 1, 2) == ("opp", "opp")
    tie = _feature(points=(6, 6), claimers=(0, 1))
    assert J._fate(tie, 0, 2) == ("both", "both")
    void = _feature(points=(0, 0), claimers=())
    assert J._fate(void, 0, 2) == ("none", "none")


def test_conversion_and_feed_counts_are_the_fate_mix_of_buildup_touches():
    mine = _feature(points=(6, 0), claimers=(0,), buildup=(2, 0))
    theirs = _feature(points=(0, 4), claimers=(1,), buildup=(1, 0))
    dead = _feature(points=(0, 0), claimers=(), buildup=(1, 0))
    feats = {"F_mine": mine, "F_theirs": theirs, "F_dead": dead}
    touches = ([_touch(0, "buildup", anchor="F_mine")] * 2
               + [_touch(0, "buildup", anchor="F_theirs")]
               + [_touch(0, "buildup", anchor="F_dead")]
               + [_touch(0, "feed_claimed", anchor="F_theirs")])
    agg = J.aggregate_game(touches, feats, [5, 0], 2)
    seat = agg["per_seat"][0]
    assert seat["kind_counts"]["buildup"] == 4
    assert seat["kind_counts"]["feed_claimed"] == 1
    assert seat["buildup_fate_claim"] == {"self": 2, "opp": 1, "both": 0, "none": 1}
    assert J._m_conv(seat) == pytest.approx(2 / 4)
    assert J._m_feed(seat) == pytest.approx(1 / 4)
    assert J._m_none(seat) == pytest.approx(1 / 4)


def test_shared_credit_is_pro_rata_by_tiles_and_never_exceeds_the_payout():
    """credit_p(F) = points_to_p(F) * buildup_p(F) / n_tiles(F). Hand-checked:
    seat 0 laid 2 of a 4-tile feature that paid it 6 => 3.0, and 1 of a 4-tile
    feature that paid the OPPONENT 4 => 1.0 of feed credit."""
    feats = {"A": _feature(n_tiles=4, points=(6, 0), claimers=(0,), buildup=(2, 0)),
             "B": _feature(n_tiles=4, points=(0, 4), claimers=(1,), buildup=(1, 0))}
    touches = [_touch(0, "buildup", anchor="A"), _touch(0, "buildup", anchor="A"),
               _touch(0, "buildup", anchor="B")]
    seat = J.aggregate_game(touches, feats, [3, 0], 2)["per_seat"][0]
    assert seat["credit_self"] == pytest.approx(3.0)
    assert seat["credit_opp"] == pytest.approx(1.0)
    assert J._m_ppb_self(seat) == pytest.approx(3.0 / 3)
    assert J._m_ppb_net(seat) == pytest.approx((3.0 - 1.0) / 3)
    # conservation: nobody can be credited more than the feature ever paid.
    assert seat["credit_self"] <= sum(f["points_to"][0] for f in feats.values())


def test_credit_splits_between_both_builders():
    """Both seats build a 4-tile feature that pays seat 0 eight points; seat 0
    laid 3 tiles, seat 1 laid 1 => 6.0 of self-credit and 2.0 of feed-credit."""
    feats = {"A": _feature(n_tiles=4, points=(8, 0), claimers=(0,), buildup=(3, 1))}
    touches = [_touch(0, "buildup", anchor="A")] * 3 + [_touch(1, "buildup", anchor="A")]
    agg = J.aggregate_game(touches, feats, [3, 1], 2)
    assert agg["per_seat"][0]["credit_self"] == pytest.approx(6.0)
    assert agg["per_seat"][0]["credit_opp"] == pytest.approx(0.0)
    assert agg["per_seat"][1]["credit_self"] == pytest.approx(0.0)
    assert agg["per_seat"][1]["credit_opp"] == pytest.approx(2.0)


def test_structural_credit_excludes_farms():
    feats = {"R": _feature("road", 4, (4, 0), (0,), (2, 0)),
             "F": _feature("farm", 10, (9, 0), (0,), (5, 0))}
    touches = [_touch(0, "buildup", "road", anchor="R")] * 2 + \
              [_touch(0, "buildup", "farm", anchor="F")] * 5
    seat = J.aggregate_game(touches, feats, [7, 0], 2)["per_seat"][0]
    assert seat["credit_self"] == pytest.approx(4 * 2 / 4 + 9 * 5 / 10)
    assert seat["credit_self_structural"] == pytest.approx(2.0)
    assert seat["buildup_by_terrain"] == {"city": 0, "road": 2, "cloister": 0, "farm": 5}


def test_buildup_plies_count_turns_not_touches():
    """One tile can touch several ownerless features; the PLY share must not
    double-count it."""
    feats = {"A": _feature(buildup=(1, 0)), "B": _feature("farm", buildup=(1, 0))}
    touches = [_touch(0, "buildup", "road", turn=7, anchor="A"),
               _touch(0, "buildup", "farm", turn=7, anchor="B")]
    seat = J.aggregate_game(touches, feats, [1, 0], 2)["per_seat"][0]
    assert seat["kind_counts"]["buildup"] == 2
    assert seat["buildup_plies"] == 1
    assert seat["buildup_plies_structural"] == 1
    assert J._m_buildup_share(seat) == pytest.approx(1.0)


def test_claim_race_counts_who_out_built_the_single_claimer():
    feats = {
        "won": _feature(points=(6, 0), claimers=(0,), buildup=(3, 1)),
        "lost": _feature(points=(6, 0), claimers=(0,), buildup=(1, 3)),
        "tied": _feature(points=(0, 6), claimers=(1,), buildup=(2, 2)),
        "contested": _feature(points=(6, 6), claimers=(0, 1), buildup=(3, 0)),
        "void": _feature(points=(0, 0), claimers=(), buildup=(4, 0)),
    }
    race = J.aggregate_game([], feats, [0, 0], 2)["claim_race"]
    assert race["n"] == 3                    # only the single-claimer features
    assert race["builder_won"] == 1 and race["builder_lost"] == 1 and race["tie"] == 1


def test_feature_base_rates_bound_the_headroom():
    feats = {"a": _feature(points=(6, 0), claimers=(0,), n_tiles=4, buildup=(2, 0)),
             "b": _feature(points=(0, 0), claimers=(), n_tiles=3, buildup=(3, 0))}
    fr = J.aggregate_game([], feats, [0, 0], 2)["features"]
    assert fr["n"] == 2 and fr["ever_claimed"] == 1 and fr["never_claimed"] == 1
    assert fr["points_total"] == 6
    assert fr["points_through_unclaimed_buildup"] == pytest.approx(6 * 2 / 4)
    assert fr["tiles_before_first_claim"] == [2]


def test_rate_is_none_on_an_empty_denominator():
    assert J._rate(3, 0) is None
    assert J._rate(0, 4) == 0.0


def test_paired_difference_is_the_within_game_contrast():
    st = J._paired([0.5, 0.6, 0.7], [0.4, 0.5, 0.6])
    assert st["mean"] == pytest.approx(0.1)
    assert st["sd"] == pytest.approx(0.0, abs=1e-12)
    assert st["n"] == 3


# --------------------------------------------------------------------------- #
# E. integration on real archives                                               #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def fixed_v1_archives():
    if not E4_DIR.exists():
        pytest.skip(f"corpus missing: {E4_DIR}")
    from carcassonne_ai import rules_profile
    if not rules_profile.r9_env_on():
        pytest.skip("CARCASSONNE_FIX_R9 latched off by another module; run this file alone")
    rows = [r for r in J.resolve_corpus(E4_DIR) if r[1] == "fixed_v1"]
    if not rows:
        pytest.skip("no fixed_v1 archives")
    return rows


def test_profiles_are_resolved_from_the_archive_never_assumed():
    if not E4_DIR.exists():
        pytest.skip(f"corpus missing: {E4_DIR}")
    rows = J.resolve_corpus(E4_DIR)
    assert rows, "no archives"
    from carcassonne_ai import rules_profile
    for path, prof, arch in rows:
        assert prof in rules_profile.PROFILES
        stamped = arch["provenance"].get("rules_profile")
        # THE 2026-08-05 discriminator: an archive with no stamp is pre-fixed_v1
        # and must never resolve to fixed_v1, whatever its (start, grid) says.
        if stamped in (None, ""):
            assert prof != "fixed_v1", path


@pytest.mark.parametrize("idx", [0, 1])
def test_real_archive_replays_bit_exact_and_reconciles(fixed_v1_archives, idx):
    from carcassonne_ai import rules_profile
    prof = rules_profile.activate("fixed_v1")
    path, _p, arch = fixed_v1_archives[idx]
    rec = J.replay_j13(arch["deck_seed"], arch["actions"],
                       game_kwargs=prof.game_kwargs(),
                       recorded_scores=arch["recorded_scores"],
                       game_id=Path(path).stem)
    it = rec["integrity"]
    assert it["replay_scores_match"] is True, path
    assert it["attribution_reconciles"] is True, path
    assert it["reconstructed_scores"] == it["final_scores"]
    assert it["n_touches"] > 0 and it["n_features"] > 0


def test_every_touch_lands_in_a_traced_feature(fixed_v1_archives):
    """No touch may dangle: every one must resolve to a persistent feature, or the
    conversion denominators and the fate numerators count different things."""
    from carcassonne_ai import rules_profile
    prof = rules_profile.activate("fixed_v1")
    path, _p, arch = fixed_v1_archives[0]
    rec = J.replay_j13(arch["deck_seed"], arch["actions"],
                       game_kwargs=prof.game_kwargs(),
                       recorded_scores=arch["recorded_scores"],
                       game_id=Path(path).stem)
    feats = rec["features"]
    assert all(t.get("feature") in feats for t in rec["touches"])
    agg = rec["aggregate"]
    for seat in agg["per_seat"]:
        assert sum(seat["kind_counts"].values()) == seat["touches"]
        assert sum(seat["buildup_fate_claim"].values()) == seat["kind_counts"]["buildup"]


def test_shared_credit_never_exceeds_the_points_actually_paid(fixed_v1_archives):
    from carcassonne_ai import rules_profile
    prof = rules_profile.activate("fixed_v1")
    path, _p, arch = fixed_v1_archives[0]
    rec = J.replay_j13(arch["deck_seed"], arch["actions"],
                       game_kwargs=prof.game_kwargs(),
                       recorded_scores=arch["recorded_scores"],
                       game_id=Path(path).stem)
    agg = rec["aggregate"]
    paid = [sum(f["points_to"][p] for f in rec["features"].values()) for p in (0, 1)]
    for p in (0, 1):
        credited = agg["per_seat"][p]["credit_self"] + agg["per_seat"][1 - p]["credit_opp"]
        assert credited <= paid[p] + 1e-9, (p, credited, paid[p])


def test_verdict_json_is_present_and_self_consistent():
    """The shipped artefact must carry its own integrity flags, not just numbers."""
    import json
    vp = REPO / "measurement" / "j13_pregate_20260813" / "VERDICT.json"
    if not vp.exists():
        pytest.skip("VERDICT.json not generated yet")
    v = json.loads(vp.read_text())
    assert v["schema"] == J.SCHEMA
    assert v["integrity"]["replay_scores_match_all"] is True
    assert v["integrity"]["attribution_reconciles_all"] is True
    assert v["integrity"]["n_games"] == v["n_archives"] == 26
    assert set(v["profiles"]) == {"walled", "app_aug2", "fixed_v1"}
    assert v["caveats"], "the honesty caveats must ship with the numbers"
