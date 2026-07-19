"""P1-L5 adjudication: does the v2.9 leaf under-credit a completed city that is
adjacent to TWO topologically-distinct fields both controlled by one player?

External-review claim (P1-L5), verbatim intent
-----------------------------------------------
The leaf shares a ``counted_growth_cities`` set across ALL of a player's farms
(comment: the same city adjacent to two farms "shouldn't be paid for twice").
Under canonical Carcassonne farm scoring each separately-controlled field scores
each adjacent COMPLETED city independently, so the SAME completed city touching
TWO DISTINCT fields of one player legitimately scores 3 + 3 = 6. If the leaf
deduplicates one city across DIFFERENT fields it systematically undervalues
multi-field city geometry. (Deduplicating repeated farmers on the SAME field is
correct — that is the C1 fix in tests/test_farm_dedup_c1.py.)

Verdict established by this fixture (all measured, not argued)
-------------------------------------------------------------
RULE-LEVEL / TERMINAL farm scoring — the P1-L5 claim as framed — is CORRECT in
every implementation:

  * ENGINE ``count_final_scores``            -> player gets 6  (ground truth)
  * FLAT leaf base (production path)          -> +6 differential
  * OBJECT leaf base (engine count_final)     -> +6 differential

The completed-city credit does NOT flow through ``counted_growth_cities`` at all.
That set lives only in the closure-ANTICIPATION bonus, whose farm branch skips any
city that is already ``finished`` (object: virtual_score_v2.py:569
``if city.finished: continue``; flat: flat_leaf.py:768 ``if
decomp.city_root_finished[croot]: continue``). Completed-city farm points are
awarded once PER FIELD by:

  * FLAT : flat_leaf.py:565-571  ``pts = 3 * decomp.farm_root_finished_cities[root]``
           accumulated per farm ``root`` (no cross-field dedup), and
           farm_root_finished_cities is built per-root (flat_leaf.py:397-408).
  * OBJECT: PointsCollector.count_final_scores calls count_farm_points once per
           farm (points_collector.py:255-266); the dedup inside count_farm_points
           (points_collector.py:292-303) is WITHIN a single field only.

So P1-L5 is NOT a rule bug. The ``counted_growth_cities`` /
``growth_roots``-union dedup that the review points at is real, but it only
touches the INCOMPLETE-city closure-anticipation HEURISTIC (a capped, tunable
term), where it under-anticipates a multi-field incomplete city by 3xP per extra
field. That behaviour is characterised (and asserted green) in
``test_growth_anticipation_dedups_incomplete_city_across_fields`` below, kept as
documentation of exactly what the flagged code does — it is a heuristic
imperfection, not a terminal-scoring rule violation.

Board geometry (engine ``city_narrow`` tile: city bar [[LEFT, RIGHT]])
----------------------------------------------------------------------
        (10, 9)        (10, 10)          (10, 11)
      city_top.t1     city_narrow       city_top.t3
      [city→RIGHT]  [==== CITY ====]   [city→LEFT ]
                     top field (TL)         caps complete the 3-tile city
                     bot field (BL)         (city.finished == True)

city_narrow has NO farmer half-side on its LEFT/RIGHT edges, so the TOP field
(exits only up) and the BOTTOM field (exits only down) are topologically
DISTINCT and never merge. Both are adjacent to the single completed city.

Runnable as pytest OR standalone:
  CARCASSONNE_USE_FLAT_LEAF=1 .venv/bin/python -m pytest tests/test_farm_multifield_city_p1l5.py
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

# Frozen v2.9 (curve125) production leaf shape — mirrors test_measurement_infra /
# test_probe_a_feature_emit so DEFAULT_CONFIG carries the production closure_p.
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
# Production runs the FLAT leaf; make the flat redirect live for the end-to-end check.
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import pytest  # noqa: E402

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_type import MeepleType  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles  # noqa: E402
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule  # noqa: E402
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet  # noqa: E402
from wingedsheep.carcassonne.utils.city_util import CityUtil  # noqa: E402
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402
from wingedsheep.carcassonne.utils.points_collector import PointsCollector  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.flat_leaf import (  # noqa: E402
    decompose,
    flat_base_score,
    flat_closure_bonus,
    flat_virtual_score_v2,
)
from carcassonne_ai.virtual_score import virtual_score  # noqa: E402
from carcassonne_ai.virtual_score_v2 import (  # noqa: E402
    DEFAULT_CONFIG,
    _closure_anticipation_bonus,
)

R, C = 10, 10  # city_narrow tile coordinate
TOP = CoordinateWithSide(Coordinate(R, C), Side.TOP_LEFT)     # top field, farmer_positions[0]
BOT = CoordinateWithSide(Coordinate(R, C), Side.BOTTOM_LEFT)  # bottom field, farmer_positions[0]


def _blank_state() -> CarcassonneGameState:
    st = CarcassonneGameState(
        tile_sets=(TileSet.BASE,),
        supplementary_rules=(SupplementaryRule.FARMERS,),
        players=2,
    )
    for r in range(len(st.board)):
        for c in range(len(st.board[0])):
            st.board[r][c] = None
    st.placed_meeples = [[], []]
    st.scores = [0, 0]
    st.next_tile = None  # terminal
    return st


def _build(bottom_player: int = 0, complete_city: bool = True) -> CarcassonneGameState:
    """city_narrow at (10,10); optionally capped L/R to COMPLETE its city.
    A farmer (player 0) in the TOP field and a farmer (``bottom_player``) in the
    BOTTOM field — two topologically distinct fields on the one tile."""
    st = _blank_state()
    st.board[R][C] = base_tiles["city_narrow"]
    if complete_city:
        st.board[R][C - 1] = base_tiles["city_top"].turn(1)  # city on RIGHT -> caps narrow LEFT
        st.board[R][C + 1] = base_tiles["city_top"].turn(3)  # city on LEFT  -> caps narrow RIGHT
    st.placed_meeples[0].append(MeeplePosition(MeepleType.FARMER, TOP))
    st.placed_meeples[bottom_player].append(MeeplePosition(MeepleType.FARMER, BOT))
    return st


# --------------------------------------------------------------------------- #
# 0. Fixture teeth: the board really has the P1-L5 geometry.
# --------------------------------------------------------------------------- #
def test_fixture_has_two_distinct_fields_and_one_completed_city() -> None:
    st = _build(bottom_player=0, complete_city=True)
    top = FarmUtil.find_farm_by_coordinate(st, TOP)
    bot = FarmUtil.find_farm_by_coordinate(st, BOT)
    top_key = frozenset(top.farmer_connections_with_coordinate)
    bot_key = frozenset(bot.farmer_connections_with_coordinate)
    assert top_key != bot_key, "TOP and BOTTOM fields must be topologically distinct"

    city = CityUtil.find_city(st, CoordinateWithSide(Coordinate(R, C), Side.LEFT))
    assert city.finished, "the shared city must be COMPLETE for the deterministic P1-L5 case"
    n_tiles = len({p.coordinate for p in city.city_positions})
    assert n_tiles == 3, f"expected a 3-tile completed city, got {n_tiles}"


# --------------------------------------------------------------------------- #
# 1. ENGINE ground truth (must pass — this is the canonical rule).
# --------------------------------------------------------------------------- #
def test_engine_pays_six_same_player_two_fields() -> None:
    """Canonical rule: one player controlling two distinct fields, each adjacent
    to the same completed city, scores 3 + 3 = 6."""
    st = _build(bottom_player=0, complete_city=True)
    PointsCollector.count_final_scores(st)
    assert st.scores == [6, 0], (
        f"ENGINE terminal scoring wrong: {st.scores} (expected [6, 0]). "
        "If the engine only paid 3 the bug would be UPSTREAM of the leaf."
    )


def test_engine_pays_three_each_different_players() -> None:
    """Mirror: the two distinct fields controlled by DIFFERENT players -> 3 each."""
    st = _build(bottom_player=1, complete_city=True)
    PointsCollector.count_final_scores(st)
    assert st.scores == [3, 3], f"ENGINE: {st.scores} (expected [3, 3])"


# --------------------------------------------------------------------------- #
# 2. LEAF terminal / base component (the farm component P1-L5 is about).
#    These PASS -> the alleged rule bug is NOT present. No xfail warranted.
# --------------------------------------------------------------------------- #
def test_flat_leaf_base_credits_city_twice_same_player() -> None:
    st = _build(bottom_player=0, complete_city=True)
    diff = flat_base_score(st, 0, decompose(st))  # scores[0] - scores[1]
    assert diff == 6, (
        f"FLAT leaf base (production path) differential {diff}, expected +6. "
        "A cross-field dedup bug would show +3 here."
    )


def test_flat_leaf_base_splits_between_players() -> None:
    st = _build(bottom_player=1, complete_city=True)
    assert flat_base_score(st, 0, decompose(st)) == 0  # 3 - 3


def test_object_leaf_base_credits_city_twice_same_player() -> None:
    # OBJECT path base == engine count_final_scores on a snapshot.
    st = _build(bottom_player=0, complete_city=True)
    assert virtual_score(copy.deepcopy(st), 0) == 6
    st2 = _build(bottom_player=1, complete_city=True)
    assert virtual_score(copy.deepcopy(st2), 0) == 0


def test_full_production_leaf_reflects_six() -> None:
    """End-to-end production entry point (flat_virtual_score_v2). meeples held
    equal so the meeple-curve term is 0 and the +6 farm credit is exposed
    directly (completed city -> zero closure-anticipation bonus)."""
    st = _build(bottom_player=0, complete_city=True)
    st.meeples = [7, 7]  # isolate the farm term (curve(7)-curve(7)=0)
    assert flat_virtual_score_v2(st, 0, DEFAULT_CONFIG) == 6


# --------------------------------------------------------------------------- #
# 3. What counted_growth_cities ACTUALLY does: the INCOMPLETE-city closure-
#    anticipation heuristic dedups a city across distinct fields. This is the
#    literal code the review flagged. It is a heuristic under-anticipation, NOT
#    a terminal-scoring rule error — asserted green as documentation.
# --------------------------------------------------------------------------- #
def test_growth_anticipation_dedups_incomplete_city_across_fields() -> None:
    """INCOMPLETE shared city adjacent to two distinct same-player fields.

    The growth branch credits ``3 * P(closes)`` but ``counted_growth_cities``
    (object, virtual_score_v2.py:566-568) / the ``growth_roots`` union (flat,
    flat_leaf.py:764-766) collapse it to ONE field's worth. A faithful
    anticipation of terminal scoring would credit each distinct field (the
    completed-city terminal path DOES — tests above). So the two-field bonus
    equals the one-field bonus instead of doubling it.

    Kept green (asserts the observed dedup) because it documents a bounded
    HEURISTIC choice, not the rule bug P1-L5 alleges.
    """
    cfg = DEFAULT_CONFIG
    two = _build(bottom_player=0, complete_city=False)  # city open -> anticipation fires
    one = _blank_state()
    one.board[R][C] = base_tiles["city_narrow"]
    one.placed_meeples[0].append(MeeplePosition(MeepleType.FARMER, TOP))  # only TOP field

    flat_two = flat_closure_bonus(two, 0, decompose(two), cfg)
    flat_one = flat_closure_bonus(one, 0, decompose(one), cfg)
    obj_two = _closure_anticipation_bonus(two, 0, cfg)
    obj_one = _closure_anticipation_bonus(one, 0, cfg)

    # teeth: the single-field anticipation is a real, positive credit.
    assert flat_one > 0.0 and obj_one > 0.0

    # the flagged dedup: adding a SECOND distinct same-player field does NOT
    # increase the credit (flat and object agree), whereas a faithful
    # anticipation would give ~2x flat_one.
    assert flat_two == pytest.approx(flat_one)
    assert obj_two == pytest.approx(obj_one)
    assert flat_two == pytest.approx(obj_two)  # flat/object parity preserved


if __name__ == "__main__":  # standalone smoke
    test_fixture_has_two_distinct_fields_and_one_completed_city()
    test_engine_pays_six_same_player_two_fields()
    test_engine_pays_three_each_different_players()
    test_flat_leaf_base_credits_city_twice_same_player()
    test_flat_leaf_base_splits_between_players()
    test_object_leaf_base_credits_city_twice_same_player()
    test_full_production_leaf_reflects_six()
    test_growth_anticipation_dedups_incomplete_city_across_fields()
    print("P1-L5 fixture: all assertions pass (engine=6, leaf base=6; growth-bonus dedup documented)")
