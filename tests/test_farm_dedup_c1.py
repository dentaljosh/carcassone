"""C1 regression guard: farm-scoring double-count fix (count_farm_points).

Ported from scripts/verify_farm_dedup_fix.py into pytest so a reintroduction of
the farm double-count bug (which shipped once, ~17% of farms over-scored) FAILS
CI instead of staying green. Plays random games to terminal (count_final_scores
stubbed so placed farmers survive), and for every farm asserts the engine's
count_farm_points equals an independent position-set-deduped reference.

Teeth check: also confirms the OLD buggy arithmetic (no cross-connection dedup)
WOULD have over-counted some farms — i.e. the test actually exercises the
dedup-prone path, so a green result is meaningful.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import Game
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.utils.city_util import CityUtil
from wingedsheep.carcassonne.utils.farm_util import FarmUtil
from wingedsheep.carcassonne.utils.points_collector import PointsCollector

N_GAMES = 40  # enough farms to reliably hit the bug-prone case; random games are fast


def _ref_farm_points(state, farm) -> int:
    """Independent CORRECT score: 3 per distinct finished adjacent city, deduped
    by position set here (not relying on engine code)."""
    seen, pts = set(), 0
    for fc in farm.farmer_connections_with_coordinate:
        for city in CityUtil.find_cities(
            game_state=state, coordinate=fc.coordinate,
            sides=fc.farmer_connection.city_sides,
        ):
            key = frozenset(city.city_positions)
            if key in seen:
                continue
            seen.add(key)
            if city.finished:
                pts += 3
    return pts


def _old_buggy_farm_points(state, farm) -> int:
    """Pre-fix behavior: 3 per finished city per connection, NO cross-dedup."""
    pts = 0
    for fc in farm.farmer_connections_with_coordinate:
        for city in CityUtil.find_cities(
            game_state=state, coordinate=fc.coordinate,
            sides=fc.farmer_connection.city_sides,
        ):
            if city.finished:
                pts += 3
    return pts


def _enumerate_farms(state):
    seen = set()
    for player_meeples in state.placed_meeples:
        for mp in player_meeples:
            if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                continue
            farm = FarmUtil.find_farm_by_coordinate(
                game_state=state, position=mp.coordinate_with_side
            )
            key = frozenset(farm.farmer_connections_with_coordinate)
            if key in seen:
                continue
            seen.add(key)
            yield farm


def _play_to_terminal(seed: int, monkeypatch):
    game = Game()
    random.seed(seed)
    board = game.get_init_board()
    monkeypatch.setattr(
        PointsCollector, "count_final_scores",
        classmethod(lambda cls, game_state: None),
    )
    while not board.state.is_terminated():
        legal = np.flatnonzero(game.get_valid_moves(board))
        if legal.size == 0:
            return None
        board, _ = game.get_next_state(board, int(random.choice(legal)))
    return board.state


def test_count_farm_points_matches_dedup_reference(monkeypatch):
    total_farms = 0
    old_over = 0
    for s in range(N_GAMES):
        state = _play_to_terminal(s, monkeypatch)
        if state is None:
            continue
        for farm in _enumerate_farms(state):
            total_farms += 1
            new = PointsCollector.count_farm_points(game_state=state, farm=farm)
            ref = _ref_farm_points(state, farm)
            old = _old_buggy_farm_points(state, farm)
            assert new == ref, (
                f"C1 REGRESSION: count_farm_points={new} != dedup-ref={ref} "
                f"(seed {s})"
            )
            if old > ref:
                old_over += 1

    assert total_farms > 0, "no farms exercised — test has no teeth"
    assert old_over > 0, (
        "the OLD buggy arithmetic never over-counted in this sample — the test "
        "isn't exercising the dedup-prone path, so a pass is meaningless"
    )
