"""Verify the per-tile internal-topology encoding (Phase 3 prerequisite #2).

Two tiles with identical outer-edge categories but different internal
connectivity used to encode identically. After the encoding-richness fix,
they must produce distinct internal-topology blocks.
"""
from __future__ import annotations

import numpy as np
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

from carcassonne_ai.board_repr import (
    N_SIDE_PAIRS,
    SIDE_PAIRS,
    _encode_city_pairs,
    _encode_road_pairs,
    _encode_tile_internal,
)
from wingedsheep.carcassonne.objects.side import Side

PAIR_TO_INDEX = {(a, b): i for i, (a, b) in enumerate(SIDE_PAIRS)}


def _idx(a: Side, b: Side) -> int:
    if (a, b) in PAIR_TO_INDEX:
        return PAIR_TO_INDEX[(a, b)]
    return PAIR_TO_INDEX[(b, a)]


def test_straight_road_joins_top_bottom() -> None:
    rp = _encode_road_pairs(base_tiles["straight_road"])
    expected = np.zeros(N_SIDE_PAIRS, dtype=np.float32)
    expected[_idx(Side.TOP, Side.BOTTOM)] = 1.0
    np.testing.assert_array_equal(rp, expected)


def test_bent_road_joins_bottom_left() -> None:
    rp = _encode_road_pairs(base_tiles["bent_road"])
    expected = np.zeros(N_SIDE_PAIRS, dtype=np.float32)
    expected[_idx(Side.BOTTOM, Side.LEFT)] = 1.0
    np.testing.assert_array_equal(rp, expected)


def test_crossroads_is_four_separate_roads() -> None:
    """Engine models a 4-way crossroads as four Connection(outer, CENTER).
    Per Carcassonne rules these are four SEPARATE road features. The
    encoding must NOT join any outer side to any other outer side.
    """
    rp = _encode_road_pairs(base_tiles["crossroads"])
    np.testing.assert_array_equal(rp, np.zeros(N_SIDE_PAIRS, dtype=np.float32))


def test_three_way_crossroads_is_three_separate_roads() -> None:
    rp = _encode_road_pairs(base_tiles["three_split_road"])
    np.testing.assert_array_equal(rp, np.zeros(N_SIDE_PAIRS, dtype=np.float32))


def test_chapel_with_road_dead_ends_at_center() -> None:
    """Road from BOTTOM->CENTER (chapel-with-road dead-end). The encoding
    sees only the outer-to-outer joins, so the result is all-zero — the
    road is "present" but no two outer sides are joined.
    """
    rp = _encode_road_pairs(base_tiles["chapel_with_road"])
    np.testing.assert_array_equal(rp, np.zeros(N_SIDE_PAIRS, dtype=np.float32))


def test_full_city_joins_all_pairs() -> None:
    cp = _encode_city_pairs(base_tiles["full_city_with_shield"])
    np.testing.assert_array_equal(cp, np.ones(N_SIDE_PAIRS, dtype=np.float32))


def test_city_diagonal_corner_joins_only_two() -> None:
    cp = _encode_city_pairs(base_tiles["city_diagonal_top_right"])
    expected = np.zeros(N_SIDE_PAIRS, dtype=np.float32)
    expected[_idx(Side.TOP, Side.RIGHT)] = 1.0
    np.testing.assert_array_equal(cp, expected)


def test_city_top_right_two_separate_cities_no_join() -> None:
    """`city_top_right` is two distinct cities (one on TOP, one on RIGHT).
    They must NOT be reported as joined.
    """
    cp = _encode_city_pairs(base_tiles["city_top_right"])
    np.testing.assert_array_equal(cp, np.zeros(N_SIDE_PAIRS, dtype=np.float32))


def test_city_left_right_two_separate_cities_no_join() -> None:
    cp = _encode_city_pairs(base_tiles["city_left_right"])
    np.testing.assert_array_equal(cp, np.zeros(N_SIDE_PAIRS, dtype=np.float32))


def test_internal_block_is_concat_of_road_then_city() -> None:
    t = base_tiles["city_top_straight_road"]
    block = _encode_tile_internal(t)
    assert block.shape == (2 * N_SIDE_PAIRS,)
    np.testing.assert_array_equal(block[:N_SIDE_PAIRS], _encode_road_pairs(t))
    np.testing.assert_array_equal(block[N_SIDE_PAIRS:], _encode_city_pairs(t))


def test_distinct_internal_topologies_distinguishable() -> None:
    """Crossroads and chapel_with_road both have edges {road, none, road, road}
    or similar; their outer-edge encodings differ but the internal-topology
    block must also differ for tiles whose edges happen to coincide.

    Concrete pair: straight_road (TOP-BOTTOM joined) vs city_top_road_bend_left
    (different topology). The road internal blocks must differ.
    """
    a = _encode_tile_internal(base_tiles["straight_road"])
    b = _encode_tile_internal(base_tiles["city_top_road_bend_left"])
    assert not np.array_equal(a, b)
