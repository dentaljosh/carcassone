"""Tests for the find_all_farms batch decomposition + index-aware leaf path
(2026-05-29 find_farm speedup; docs/PATH_B.md Step 2, DECISIONS 2026-05-29).

Contracts:
  1. find_all_farms partitions the board into exactly the components find_farm
     returns from each node (start-independent equivalence).
  2. virtual_score_v2 is bit-identical with the index path active vs disabled —
     the speedup changes the leaf VALUE by zero.
  3. An attached _farm_index never survives a state deepcopy (so it cannot leak
     across get_next_state), and virtual_score_v2 detaches it after the call.
  4. find_farm_by_coordinate with an attached index returns the same region as
     the flood-fill it replaces.
"""
from __future__ import annotations

import copy
import random

import numpy as np
import pytest

from carcassonne_ai import virtual_score as _vs
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_farmer_side import (
    CoordinateWithFarmerSide,  # noqa: F401  (kept for parity with engine imports)
)
from wingedsheep.carcassonne.objects.farmer_connection_with_coordinate import (
    FarmerConnectionWithCoordinate,
)
from wingedsheep.carcassonne.utils.farm_util import FarmUtil


def _play(game: Game, seed: int, plies: int, max_plies: int = 400):
    """Random-legal play up to `plies` (or terminal); return the live Board."""
    random.seed(seed)
    board = game.get_init_board()
    n = 0
    while game.get_game_ended(board, 0) == 0.0 and n < min(plies, max_plies):
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        n += 1
    return board


def _region(farm) -> frozenset:
    return frozenset(
        FarmUtil._farm_node_key(fcc) for fcc in farm.farmer_connections_with_coordinate
    )


def _all_nodes(state):
    out = []
    for row in range(len(state.board)):
        for col in range(len(state.board[row])):
            tile = state.board[row][col]
            if tile is None:
                continue
            for fc in tile.farms:
                fcc = FarmerConnectionWithCoordinate(fc, Coordinate(row, col))
                out.append((FarmUtil._farm_node_key(fcc), fcc))
    return out


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 7, 11])
def test_find_all_farms_matches_find_farm(seed):
    game = Game()
    state = _play(game, seed, plies=120).state
    index = FarmUtil.find_all_farms(state)
    nodes = _all_nodes(state)
    assert nodes, f"seed {seed} produced no farmer connections"
    saw_farm = False
    for key, fcc in nodes:
        saw_farm = True
        assert key in index, f"node {key} missing from find_all_farms index"
        assert _region(index[key]) == _region(FarmUtil.find_farm(state, fcc)), (
            f"index region != find_farm region at node {key} (seed {seed})"
        )
    assert saw_farm


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 7, 11, 13, 21])
def test_virtual_score_v2_value_invariant_to_cache(seed):
    """Combined farm + city leaf memo must not change the leaf value."""
    game = Game()
    state = _play(game, seed, plies=140).state
    for p in range(state.players):
        _vs.USE_FARM_CACHE = _vs.USE_CITY_CACHE = True
        with_cache = virtual_score_v2(state, p, DEFAULT_CONFIG)
        _vs.USE_FARM_CACHE = _vs.USE_CITY_CACHE = False
        try:
            without_cache = virtual_score_v2(state, p, DEFAULT_CONFIG)
        finally:
            _vs.USE_FARM_CACHE = _vs.USE_CITY_CACHE = True
        assert with_cache == without_cache, (
            f"seed {seed} player {p}: cache-on {with_cache} != cache-off {without_cache}"
        )


@pytest.mark.parametrize("seed", [0, 2, 3, 7])
def test_find_city_memo_returns_equivalent_fresh_objects(seed):
    """find_city with a _city_cache: same positions/finished as the no-cache
    flood-fill, but a DISTINCT City object each call (so count_farm_points'
    identity-based set dedup is unchanged)."""
    from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    from wingedsheep.carcassonne.utils.city_util import CityUtil

    game = Game()
    state = _play(game, seed, plies=150).state
    target = None
    for row in range(len(state.board)):
        for col in range(len(state.board[row])):
            tile = state.board[row][col]
            if tile is None:
                continue
            for side in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT):
                if tile.get_type(side) == TerrainType.CITY:
                    target = CoordinateWithSide(Coordinate(row, col), side)
                    break
            if target:
                break
        if target:
            break
    if target is None:
        pytest.skip("seed produced no city edge")

    no_cache = CityUtil.find_city(state, target)
    state._city_cache = {}
    try:
        first = CityUtil.find_city(state, target)
        second = CityUtil.find_city(state, target)
    finally:
        del state._city_cache
    assert set(first.city_positions) == set(no_cache.city_positions)
    assert first.finished == no_cache.finished
    assert set(second.city_positions) == set(no_cache.city_positions)
    assert first is not second  # fresh object each call (identity-dedup preserved)


def test_farm_cache_stripped_by_deepcopy_and_not_left_attached():
    game = Game()
    state = _play(game, 5, plies=130).state
    # deepcopy must not carry _farm_cache (CarcassonneGameState.__deepcopy__ only
    # copies its explicit fields) — guarantees no leak across get_next_state.
    state._farm_cache = {}
    clone = copy.deepcopy(state)
    assert not hasattr(clone, "_farm_cache")
    del state._farm_cache
    # virtual_score_v2 attaches transiently and must detach in its finally.
    virtual_score_v2(state, 0, DEFAULT_CONFIG)
    assert not hasattr(state, "_farm_cache")


def test_find_farm_by_coordinate_cache_returns_same_region():
    game = Game()
    state = _play(game, 2, plies=150).state
    # find a placed farmer meeple to exercise find_farm_by_coordinate
    target = None
    for player in range(state.players):
        for mp in state.placed_meeples[player]:
            cs = mp.coordinate_with_side
            tile = state.board[cs.coordinate.row][cs.coordinate.column]
            if tile is None:
                continue
            if any(cs.side in fc.farmer_positions for fc in tile.farms):
                target = cs
                break
        if target:
            break
    if target is None:
        pytest.skip("seed produced no placed farmer meeple")
    no_cache = FarmUtil.find_farm_by_coordinate(state, target)
    state._farm_cache = {}
    try:
        # first call populates, second hits the memo — both must equal no_cache
        first = FarmUtil.find_farm_by_coordinate(state, target)
        second = FarmUtil.find_farm_by_coordinate(state, target)
    finally:
        del state._farm_cache
    assert _region(first) == _region(no_cache)
    assert _region(second) == _region(no_cache)
    assert first is second  # memo returns the same object on the repeat query
