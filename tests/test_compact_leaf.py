"""Compact-leaf equivalence tests (2026-06-09, leaf-rewrite branch).

A fast pytest counterpart to scripts/reconcile_compact_leaf.py: proves the
USE_COMPACT_LEAF path (flat union-find pre-populating the engine farm/city memo
dicts) produces the SAME leaf as the production object-BFS path, on random
positions sampled across game depth. The script is the exhaustive verdict; this
is the always-on CI guard.
"""
from __future__ import annotations

import copy
import random

import numpy as np
import pytest

from carcassonne_ai import compact_leaf
from carcassonne_ai import virtual_score as _vs
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score import virtual_score
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.farmer_connection_with_coordinate import (
    FarmerConnectionWithCoordinate,
)
from wingedsheep.carcassonne.utils.city_util import CityUtil
from wingedsheep.carcassonne.utils.farm_util import FarmUtil
from wingedsheep.carcassonne.utils.points_collector import PointsCollector


def _collect_states(seed: int, n_games: int = 6, snap_every: int = 5):
    game = Game()
    states = []
    for g in range(n_games):
        random.seed(seed + g)
        board = game.get_init_board()
        plies = 0
        while game.get_game_ended(board, 0) == 0.0 and plies < 400:
            legal = np.flatnonzero(game.get_valid_moves(board))
            if legal.size == 0:
                break
            board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
            plies += 1
            if plies % snap_every == 0 and game.get_game_ended(board, 0) == 0.0:
                states.append(board.state)
        states.append(board.state)
    return [s for s in states if s.players == 2]


@pytest.fixture
def states():
    return _collect_states(seed=4242)


@pytest.fixture(autouse=True)
def _restore_toggle():
    saved = _vs.USE_COMPACT_LEAF
    yield
    _vs.USE_COMPACT_LEAF = saved


def test_default_toggle_is_off():
    # Production must be unaffected unless explicitly opted in.
    import importlib

    mod = importlib.import_module("carcassonne_ai.virtual_score")
    # Reading the live attribute after our fixture-restore would be stale, so
    # check the source-of-truth: a freshly imported module defaults to False.
    assert mod.USE_COMPACT_LEAF in (True, False)  # attribute exists
    # The committed default:
    src = (
        __import__("pathlib").Path(mod.__file__).read_text()
    )
    assert "USE_COMPACT_LEAF = False" in src


def _farm_region(farm) -> frozenset:
    return frozenset(
        FarmUtil._farm_node_key(fcc) for fcc in farm.farmer_connections_with_coordinate
    )


def test_farm_partition_matches_find_farm(states):
    checked = 0
    for state in states:
        cache = compact_leaf.build_farm_cache(state)
        for row in range(len(state.board)):
            for col in range(len(state.board[row])):
                tile = state.board[row][col]
                if tile is None:
                    continue
                for fc in tile.farms:
                    fcc = FarmerConnectionWithCoordinate(fc, Coordinate(row, col))
                    key = FarmUtil._farm_node_key(fcc)
                    assert key in cache, f"farm node {key} missing from compact cache"
                    assert _farm_region(cache[key]) == _farm_region(
                        FarmUtil.find_farm(state, fcc)
                    )
                    checked += 1
    assert checked > 0, "no farm nodes exercised"


def test_city_partition_matches_compute_city(states):
    checked = 0
    for state in states:
        cache = compact_leaf.build_city_cache(state)
        seen = set()
        for row in range(len(state.board)):
            for col in range(len(state.board[row])):
                tile = state.board[row][col]
                if tile is None:
                    continue
                for city_group in tile.city:
                    for side in city_group:
                        cws = CoordinateWithSide(Coordinate(row, col), side)
                        if cws in seen:
                            continue
                        seen.add(cws)
                        assert cws in cache, f"city edge missing from compact cache"
                        c_pos, c_fin = cache[cws]
                        t_pos, t_fin = CityUtil._compute_city(state, cws)
                        assert frozenset(c_pos) == frozenset(t_pos)
                        assert c_fin == t_fin
                        checked += 1
    assert checked > 0, "no city edges exercised"


def _scores(state, compact: bool):
    snap = copy.deepcopy(state)
    if compact:
        snap._farm_cache = compact_leaf.build_farm_cache(snap)
        snap._city_cache = compact_leaf.build_city_cache(snap)
    else:
        snap._farm_cache = {}
        snap._city_cache = {}
    PointsCollector.count_final_scores(game_state=snap)
    return tuple(snap.scores)


def test_count_final_scores_identical(states):
    for state in states:
        assert _scores(state, compact=False) == _scores(state, compact=True)


def test_leaf_int_identical(states):
    n = 0
    for state in states:
        for p in range(state.players):
            _vs.USE_COMPACT_LEAF = False
            vs_off, v2_off = virtual_score(state, p), virtual_score_v2(state, p, DEFAULT_CONFIG)
            _vs.USE_COMPACT_LEAF = True
            vs_on, v2_on = virtual_score(state, p), virtual_score_v2(state, p, DEFAULT_CONFIG)
            assert vs_off == vs_on, f"virtual_score differs p={p}: {vs_off} vs {vs_on}"
            assert v2_off == v2_on, f"virtual_score_v2 differs p={p}: {v2_off} vs {v2_on}"
            n += 1
    assert n > 0
