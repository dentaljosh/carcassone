"""Reconciliation gate for the find_all_farms speedup (2026-05-29).

NON-NEGOTIABLE before trusting the batch farm decomposition (docs/PATH_B.md
Step 2 / DECISIONS 2026-05-29). Mirrors the aux-target n=2000 gate. Two checks,
across many random positions sampled at multiple game depths (farm regions grow
late, and the v2.7 leaf evaluates mid-game states, so we sample throughout —
not just terminal):

  1. REGION EQUIVALENCE — for every farmer-connection node on the board,
     `find_all_farms(state)[key]` returns exactly the same component (set of
     farmer connections) that `find_farm` returns starting from that node.
     This is the correctness core: the O(1) index lookup must equal the
     flood-fill it replaces.

  2. VALUE EQUIVALENCE — `virtual_score_v2(state, p)` is bit-identical whether
     the index path is active or disabled. The index is disabled by stubbing
     `find_all_farms` to return {} (every find_farm_by_coordinate then falls
     back to find_farm = pre-speedup behaviour), so this asserts the speedup
     changes the leaf VALUE by exactly zero.

Exits non-zero on any mismatch, and FAILS if no farms were exercised.

Usage:  python scripts/reconcile_farm_index.py --n 400 --snap-every 6
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from carcassonne_ai import virtual_score as _vs  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate_with_farmer_side import (  # noqa: E402
    CoordinateWithFarmerSide,
)
from wingedsheep.carcassonne.objects.farmer_connection_with_coordinate import (  # noqa: E402
    FarmerConnectionWithCoordinate,
)
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402


def _region(farm) -> frozenset:
    """Canonical, start-independent identity of a farm component: the set of
    node-keys (row, col, connection-id) it contains."""
    return frozenset(FarmUtil._farm_node_key(fcc) for fcc in farm.farmer_connections_with_coordinate)


def _all_nodes(state):
    """Every farmer-connection node on the board, as (key, fcc)."""
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


def check_region_equivalence(state) -> tuple[int, int]:
    """Returns (nodes_checked, mismatches)."""
    index = FarmUtil.find_all_farms(state)
    nodes = _all_nodes(state)
    mism = 0
    for key, fcc in nodes:
        idx_region = _region(index[key]) if key in index else None
        truth_region = _region(FarmUtil.find_farm(state, fcc))
        if idx_region != truth_region:
            mism += 1
    return len(nodes), mism


def check_value_equivalence(state) -> int:
    """Returns number of (player) value mismatches between caches-ON and
    caches-OFF virtual_score_v2. Toggles BOTH the farm and city leaf memos, so
    this asserts the combined speedup changes the leaf VALUE by exactly zero."""
    mism = 0
    for p in range(state.players):
        _vs.USE_FARM_CACHE = True
        _vs.USE_CITY_CACHE = True
        with_cache = virtual_score_v2(state, p, DEFAULT_CONFIG)
        _vs.USE_FARM_CACHE = False
        _vs.USE_CITY_CACHE = False
        try:
            without_cache = virtual_score_v2(state, p, DEFAULT_CONFIG)
        finally:
            _vs.USE_FARM_CACHE = True
            _vs.USE_CITY_CACHE = True
        if with_cache != without_cache:
            mism += 1
    return mism


def collect_states(game: Game, seed: int, snap_every: int, max_plies: int = 400):
    """Random-legal play; snapshot live states across depth + the terminal."""
    random.seed(seed)
    board = game.get_init_board()
    states = []
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        action = int(random.choice(legal.tolist()))
        board, _ = game.get_next_state(board, action)
        plies += 1
        if plies % snap_every == 0 and game.get_game_ended(board, 0) == 0.0:
            states.append(board.state)
    states.append(board.state)  # final (possibly terminal)
    return states


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="games to sample")
    ap.add_argument("--snap-every", type=int, default=6)
    ap.add_argument("--seed-start", type=int, default=0)
    args = ap.parse_args(argv)

    game = Game()  # 2p Base + River + Farmers (locked scope)

    states_checked = 0
    nodes_checked = 0
    region_fail = 0
    value_fail = 0
    farm_states = 0

    for i in range(args.n):
        for state in collect_states(game, args.seed_start + i, args.snap_every):
            states_checked += 1
            index = FarmUtil.find_all_farms(state)
            if index:
                farm_states += 1
            nc, rm = check_region_equivalence(state)
            nodes_checked += nc
            region_fail += rm
            value_fail += check_value_equivalence(state)

    print(f"games sampled:        {args.n}")
    print(f"states checked:       {states_checked}")
    print(f"states with farms:    {farm_states}")
    print(f"farm nodes checked:   {nodes_checked}")
    print(f"REGION mismatches:    {region_fail}")
    print(f"VALUE  mismatches:    {value_fail}")

    ok = region_fail == 0 and value_fail == 0 and farm_states > 0 and nodes_checked > 0
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
