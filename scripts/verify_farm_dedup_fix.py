#!/usr/bin/env python3
"""C1 verification: farm-scoring double-count fix (count_farm_points).

Plays random games to termination with count_final_scores stubbed (so placed
farmers survive), enumerates every farm touched by a farmer, and for each farm
compares three quantities:

  NEW  = PointsCollector.count_farm_points (the FIXED engine code)
  REF  = independent correct score = 3 * (# distinct finished cities adjacent),
         deduped by frozenset(city_positions) here in the script
  OLD  = the pre-fix buggy behavior = 3 per finished city per farmer connection,
         with NO cross-connection dedup (faithful repro of identity-set union)

Pass criteria:
  - NEW == REF for ALL farms              (the fix is correct)
  - OLD  > REF for some farms             (the bug really existed; ~17% expected)
  - NEW  < OLD on exactly the buggy farms (the fix removed the inflation)

Usage: python scripts/verify_farm_dedup_fix.py --n 150
"""
import argparse
import copy
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np

from carcassonne_ai.game_wrapper import Game
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.utils.city_util import CityUtil
from wingedsheep.carcassonne.utils.farm_util import FarmUtil
from wingedsheep.carcassonne.utils.points_collector import PointsCollector


def _ref_farm_points(state, farm) -> int:
    """Independent CORRECT farm score: 3 per distinct finished adjacent city,
    deduped by position set right here (not relying on engine code)."""
    seen = set()
    pts = 0
    for fc in farm.farmer_connections_with_coordinate:
        for city in CityUtil.find_cities(
            game_state=state,
            coordinate=fc.coordinate,
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
    """Faithful repro of the PRE-FIX behavior: count 3 per finished city per
    farmer connection with NO cross-connection dedup (the old identity-set
    union never merged fresh City objects across find_cities calls)."""
    pts = 0
    for fc in farm.farmer_connections_with_coordinate:
        for city in CityUtil.find_cities(
            game_state=state,
            coordinate=fc.coordinate,
            sides=fc.farmer_connection.city_sides,
        ):
            if city.finished:
                pts += 3
    return pts


def _enumerate_farms(state):
    """Yield each distinct farm (by farmer-connection set) that has a farmer."""
    seen_farms = set()
    for player_meeples in state.placed_meeples:
        for mp in player_meeples:
            if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                continue
            farm = FarmUtil.find_farm_by_coordinate(
                game_state=state, position=mp.coordinate_with_side
            )
            key = frozenset(farm.farmer_connections_with_coordinate)
            if key in seen_farms:
                continue
            seen_farms.add(key)
            yield farm


def play_to_terminal(seed: int):
    """Random game to terminal; returns the terminal state with meeples intact
    (count_final_scores stubbed so farmers aren't consumed)."""
    game = Game()
    random.seed(seed)
    board = game.get_init_board()
    orig = PointsCollector.count_final_scores
    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
    try:
        while not board.state.is_terminated():
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                return None
            idx = int(random.choice(legal))
            board, _ = game.get_next_state(board, idx)
    finally:
        PointsCollector.count_final_scores = orig
    return board.state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed-start", type=int, default=0)
    args = ap.parse_args()

    total_farms = 0
    new_ne_ref = 0          # FIX BROKEN if > 0
    old_ne_ref = 0          # bug-present farms
    old_gt_ref = 0          # over-counted (the actual bug direction)
    spurious_pts = 0
    worst = 0
    games = 0

    for s in range(args.seed_start, args.seed_start + args.n):
        try:
            state = play_to_terminal(s)
        except Exception as exc:
            print(f"seed {s}: {type(exc).__name__}: {exc}")
            continue
        if state is None:
            continue
        games += 1
        for farm in _enumerate_farms(state):
            # score only farms with a winner-eligible farmer (matches engine),
            # but for a pure scoring-arithmetic check we compare on every farm.
            new = PointsCollector.count_farm_points(game_state=state, farm=farm)
            ref = _ref_farm_points(state, farm)
            old = _old_buggy_farm_points(state, farm)
            total_farms += 1
            if new != ref:
                new_ne_ref += 1
            if old != ref:
                old_ne_ref += 1
            if old > ref:
                old_gt_ref += 1
                spurious_pts += (old - ref)
                worst = max(worst, old - ref)

    print(f"\n=== C1 farm-dedup verification ({games} games, {total_farms} farms) ===")
    print(f"NEW != REF (fix broken if >0):  {new_ne_ref}")
    print(f"OLD != REF (bug present):       {old_ne_ref} "
          f"({100*old_ne_ref/max(1,total_farms):.1f}% of farms)")
    print(f"OLD  > REF (over-counted):      {old_gt_ref}")
    print(f"spurious points removed by fix: {spurious_pts}  (worst single farm: +{worst})")
    verdict = "PASS" if new_ne_ref == 0 and old_gt_ref > 0 else "FAIL"
    print(f"VERDICT: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
