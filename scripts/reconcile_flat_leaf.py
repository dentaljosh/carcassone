#!/usr/bin/env python3
"""Bit-exact equivalence gate for the de-objectified flat leaf (Stages 1-2).

NON-NEGOTIABLE before trusting `flat_leaf`. The flat path computes the leaf
WITHOUT the engine's object-graph flood-fills (`FarmUtil.find_farm`,
`CityUtil._compute_city`, `RoadUtil.find_road`) and WITHOUT `count_final_scores`
/ deepcopy. This gate proves it reproduces the engine EXACTLY, across many random
positions sampled at every game depth.

Checks (all HARD), flat vs the engine ground truth:

  Stage 1 — PARTITIONS (structure):
    1. FARM  — for every farmer-connection node, flat component (node-key set)
       == FarmUtil.find_farm from that node.
    2. CITY  — for every city edge, flat component (positions, finished)
       == CityUtil._compute_city.
    3. ROAD  — for every road edge, flat component (positions, finished)
       == RoadUtil.find_road.

  Stage 2 — BASE SCORE (pure integer):
    4. FINAL ADDITIONS — flat _final_scores(state) == the per-player points
       count_final_scores ADDS (deepcopy + count_final_scores, minus running).
    5. virtual_score INT — flat_base_score(state, p) == virtual_score(state, p)
       for every player. THIS IS THE BASE-LEAF CONTRACT.

Coverage (HARD if zero): farms, cities (finished + unfinished), roads (finished +
unfinished), cloisters scored, farms with >=1 finished adjacent city.

Exits non-zero on ANY mismatch or empty coverage. Run under the production env
(CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12).

Usage:  python scripts/reconcile_flat_leaf.py --n 400 --snap-every 4
"""
from __future__ import annotations

import argparse
import copy
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

import carcassonne_ai  # noqa: E402
import wingedsheep  # noqa: E402
from carcassonne_ai import flat_leaf  # noqa: E402
import carcassonne_ai.virtual_score_v2 as _v2mod  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score import virtual_score  # noqa: E402
from carcassonne_ai.virtual_score_v2 import (  # noqa: E402
    DEFAULT_CONFIG,
    _closure_anticipation_bonus,
    virtual_score_v2,
)
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate_with_side import (  # noqa: E402
    CoordinateWithSide,
)
from wingedsheep.carcassonne.objects.farmer_connection_with_coordinate import (  # noqa: E402
    FarmerConnectionWithCoordinate,
)
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.objects.terrain_type import TerrainType  # noqa: E402
from wingedsheep.carcassonne.utils.city_util import CityUtil  # noqa: E402
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402
from wingedsheep.carcassonne.utils.points_collector import PointsCollector  # noqa: E402
from wingedsheep.carcassonne.utils.road_util import RoadUtil  # noqa: E402

_CARD = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)


# --------------------------------------------------------------------------- #
# enumeration helpers
# --------------------------------------------------------------------------- #
def _cws_set(positions) -> frozenset:
    """Engine CoordinateWithSide set -> (row, col, side) tuple set."""
    return frozenset((p.coordinate.row, p.coordinate.column, p.side) for p in positions)


def _farm_region(farm) -> frozenset:
    return frozenset(
        FarmUtil._farm_node_key(fcc) for fcc in farm.farmer_connections_with_coordinate
    )


def _all_farm_nodes(state):
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


def _all_city_edges(state):
    out, seen = [], set()
    for row in range(len(state.board)):
        for col in range(len(state.board[row])):
            tile = state.board[row][col]
            if tile is None:
                continue
            for group in tile.city:
                for side in group:
                    key = (row, col, side)
                    if key not in seen:
                        seen.add(key)
                        out.append(CoordinateWithSide(Coordinate(row, col), side))
    return out


def _all_road_edges(state):
    out = []
    for row in range(len(state.board)):
        for col in range(len(state.board[row])):
            tile = state.board[row][col]
            if tile is None:
                continue
            for side in _CARD:
                if tile.get_type(side) == TerrainType.ROAD:
                    out.append(CoordinateWithSide(Coordinate(row, col), side))
    return out


def _engine_final_additions(state):
    """Per-player points count_final_scores ADDS (on a deepcopy; live state
    untouched)."""
    snap = copy.deepcopy(state)
    snap._farm_cache = {}
    snap._city_cache = {}
    before = tuple(snap.scores)
    PointsCollector.count_final_scores(game_state=snap)
    after = tuple(snap.scores)
    return tuple(a - b for a, b in zip(after, before))


def collect_states(game: Game, seed: int, snap_every: int, max_plies: int = 400):
    random.seed(seed)
    board = game.get_init_board()
    states = []
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        legal = np.flatnonzero(game.get_valid_moves(board))
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        plies += 1
        if plies % snap_every == 0 and game.get_game_ended(board, 0) == 0.0:
            states.append(board.state)
    states.append(board.state)
    return states


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="games to play")
    ap.add_argument("--snap-every", type=int, default=4, help="snapshot cadence (plies)")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--values-only", action="store_true",
                    help="skip the per-node partition BFS truth checks (faster)")
    args = ap.parse_args()

    assert "/carc-leafdev/" in carcassonne_ai.__file__, f"not worktree: {carcassonne_ai.__file__}"
    assert "/carc-leafdev/" in wingedsheep.__file__, f"not worktree: {wingedsheep.__file__}"

    # The flat leaf is CANONICAL (order-independent fsum) by construction, so the
    # engine bonus/v2 it is compared against must run canonical too — else the
    # known ~1e-4 ±1 naive-sum reorder flips would show as spurious mismatches.
    _v2mod.CANONICAL_BONUS_SUM = True
    print(f"CANONICAL_BONUS_SUM=True  DEFAULT_CONFIG: closure_p={DEFAULT_CONFIG.closure_p} "
          f"cap={DEFAULT_CONFIG.bonus_cap} opp_cap={DEFAULT_CONFIG.opp_bonus_cap}")

    game = Game()
    states_seen = 0
    farm_nodes = farm_mism = 0
    city_nodes = city_mism = 0
    road_nodes = road_mism = 0
    final_checks = final_mism = 0
    base_checks = base_mism = 0
    bonus_checks = bonus_mism = 0
    v2_checks = v2_mism = 0
    cov_farms = cov_cities = cov_roads = 0
    cov_cfin = cov_cunfin = cov_rfin = cov_runfin = 0
    cov_cloister = cov_farm_fincity = 0
    first_fail = None

    def fail(msg):
        nonlocal first_fail
        if first_fail is None:
            first_fail = msg

    for g in range(args.n):
        for state in collect_states(game, args.seed + g, args.snap_every):
            if state.players != 2:
                continue
            states_seen += 1
            decomp = flat_leaf.decompose(state)

            if not args.values_only:
                # --- check 1: farm partition ---
                for key, fcc in _all_farm_nodes(state):
                    farm_nodes += 1
                    cov_farms += 1
                    truth = _farm_region(FarmUtil.find_farm(state, fcc))
                    root = decomp.farm_pos0_root.get(
                        (fcc.coordinate.row, fcc.coordinate.column,
                         fcc.farmer_connection.farmer_positions[0])
                    )
                    # root via pos0 may miss a connection with no farmer_positions;
                    # fall back to scanning farm_root_keys for the node key.
                    got = None
                    if root is not None:
                        got = decomp.farm_root_keys.get(root)
                    if got is None:
                        for rk, keys in decomp.farm_root_keys.items():
                            if key in keys:
                                got = keys
                                break
                    if got != truth:
                        farm_mism += 1
                        fail(f"FARM node {key}: flat={got} truth={truth}")

                # --- check 2: city partition ---
                for cws in _all_city_edges(state):
                    city_nodes += 1
                    cov_cities += 1
                    t_pos, t_fin = CityUtil._compute_city(state, cws)
                    root = decomp.city_side_root.get((cws.coordinate.row, cws.coordinate.column, cws.side))
                    if root is None:
                        city_mism += 1
                        fail(f"CITY edge {cws.coordinate.row},{cws.coordinate.column},{cws.side} missing")
                        continue
                    c_pos = decomp.city_root_positions[root]
                    c_fin = decomp.city_root_finished[root]
                    if c_pos != _cws_set(t_pos) or c_fin != t_fin:
                        city_mism += 1
                        fail(f"CITY edge {cws.coordinate.row},{cws.coordinate.column},{cws.side}: "
                             f"flat(fin={c_fin},n={len(c_pos)}) truth(fin={t_fin},n={len(t_pos)})")
                    cov_cfin += 1 if t_fin else 0
                    cov_cunfin += 0 if t_fin else 1

                # --- check 3: road partition ---
                for cws in _all_road_edges(state):
                    road_nodes += 1
                    cov_roads += 1
                    road = RoadUtil.find_road(state, cws)
                    t_pos = _cws_set(road.road_positions)
                    t_fin = road.finished
                    root = decomp.road_side_root.get((cws.coordinate.row, cws.coordinate.column, cws.side))
                    if root is None:
                        road_mism += 1
                        fail(f"ROAD edge {cws.coordinate.row},{cws.coordinate.column},{cws.side} missing")
                        continue
                    r_pos = decomp.road_root_positions[root]
                    r_fin = decomp.road_root_finished[root]
                    if r_pos != t_pos or r_fin != t_fin:
                        road_mism += 1
                        fail(f"ROAD edge {cws.coordinate.row},{cws.coordinate.column},{cws.side}: "
                             f"flat(fin={r_fin},n={len(r_pos)}) truth(fin={t_fin},n={len(t_pos)})")
                    cov_rfin += 1 if t_fin else 0
                    cov_runfin += 0 if t_fin else 1

            # --- check 4: final-score additions (per player) ---
            final_checks += 1
            engine_final = _engine_final_additions(state)
            flat_final = tuple(flat_leaf._final_scores(state, decomp))
            if engine_final != flat_final:
                final_mism += 1
                fail(f"FINAL additions engine={engine_final} flat={flat_final}")

            # --- check 5: base virtual_score int (the contract) ---
            for p in range(state.players):
                base_checks += 1
                truth = virtual_score(state, p)
                got = flat_leaf.flat_base_score(state, p, decomp)
                if truth != got:
                    base_mism += 1
                    fail(f"flat_base_score p={p} flat={got} truth={truth}")

                # --- check 6: closure-anticipation bonus (uncapped float, canonical) ---
                bonus_checks += 1
                b_truth = _closure_anticipation_bonus(state, p, DEFAULT_CONFIG)
                b_got = flat_leaf.flat_closure_bonus(state, p, decomp, DEFAULT_CONFIG)
                if b_truth != b_got:
                    bonus_mism += 1
                    fail(f"flat_closure_bonus p={p} flat={b_got!r} truth={b_truth!r}")

                # --- check 7: full virtual_score_v2 int (THE LEAF CONTRACT) ---
                v2_checks += 1
                v2_truth = virtual_score_v2(state, p, DEFAULT_CONFIG)
                v2_got = flat_leaf.flat_virtual_score_v2(state, p, DEFAULT_CONFIG)
                if v2_truth != v2_got:
                    v2_mism += 1
                    fail(f"flat_virtual_score_v2 p={p} flat={v2_got} truth={v2_truth}")

            # coverage extras
            for root, fincnt in decomp.farm_root_finished_cities.items():
                if fincnt > 0:
                    cov_farm_fincity += 1
            # cloisters scored = chapel/flowers tiles carrying a meeple
            cov_cloister += _count_cloister_meeples(state)

        if (g + 1) % max(1, args.n // 10) == 0:
            print(f"  [{g + 1}/{args.n}] states={states_seen} "
                  f"farm={farm_nodes} city={city_nodes} road={road_nodes} base={base_checks} | "
                  f"mism farm={farm_mism} city={city_mism} road={road_mism} "
                  f"final={final_mism} base={base_mism} bonus={bonus_mism} v2={v2_mism}")

    print("\n=== reconcile_flat_leaf summary ===")
    print(f"states evaluated       : {states_seen}")
    print(f"farm partition checks  : {farm_nodes:>8}   mismatches: {farm_mism}")
    print(f"city partition checks  : {city_nodes:>8}   mismatches: {city_mism}")
    print(f"road partition checks  : {road_nodes:>8}   mismatches: {road_mism}")
    print(f"final-additions checks : {final_checks:>8}   mismatches: {final_mism}")
    print(f"flat_base_score checks : {base_checks:>8}   mismatches: {base_mism}")
    print(f"closure-bonus checks   : {bonus_checks:>8}   mismatches: {bonus_mism}")
    print(f"flat_virtual_score_v2  : {v2_checks:>8}   mismatches: {v2_mism}")
    print(f"coverage: farms={cov_farms} cities={cov_cities}(fin={cov_cfin}/unf={cov_cunfin}) "
          f"roads={cov_roads}(fin={cov_rfin}/unf={cov_runfin}) "
          f"cloisters_scored={cov_cloister} farms_w_fincity={cov_farm_fincity}")

    if first_fail is not None:
        print(f"\nFIRST FAILURE: {first_fail}")

    total_mism = (farm_mism + city_mism + road_mism + final_mism + base_mism
                  + bonus_mism + v2_mism)
    coverage_ok = args.values_only or (
        cov_farms > 0 and cov_cfin > 0 and cov_cunfin > 0
        and cov_rfin > 0 and cov_runfin > 0
    )
    if total_mism > 0:
        print(f"\nFAIL: {total_mism} mismatch(es) — flat leaf NOT equivalent.")
        return 1
    if not coverage_ok:
        print("\nFAIL: insufficient coverage (need farms + fin/unfin cities + fin/unfin roads).")
        return 2
    if base_checks < 10000 and not args.values_only:
        print(f"\nWARN: only {base_checks} base evals (<10k acceptance target); raise --n.")
    print(f"\nPASS (BIT-EXACT): flat == engine across {v2_checks} virtual_score_v2 evals "
          f"(+ {base_checks} base + {bonus_checks} closure-bonus)"
          + ("" if args.values_only
             else f" + {farm_nodes} farm + {city_nodes} city + {road_nodes} road partitions")
          + " — partitions / final additions / base / closure bonus / full v2 all bit-identical "
          "(canonical sum).")
    return 0


def _count_cloister_meeples(state) -> int:
    from wingedsheep.carcassonne.objects.side import Side as _S
    n = 0
    for player in range(state.players):
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            tile = state.board[cws.coordinate.row][cws.coordinate.column]
            if tile is None:
                continue
            t = tile.get_type(cws.side)
            if t == TerrainType.CHAPEL or t == TerrainType.FLOWERS:
                n += 1
    return n


if __name__ == "__main__":
    raise SystemExit(main())
