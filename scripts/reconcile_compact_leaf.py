#!/usr/bin/env python3
"""Bit-exact equivalence gate for the compact-leaf rewrite (2026-06-09).

NON-NEGOTIABLE before trusting `virtual_score.USE_COMPACT_LEAF`. The compact
path (`compact_leaf.build_farm_cache` / `build_city_cache`, flat union-find)
pre-populates the SAME engine memo dicts that `FarmUtil.find_farm` /
`CityUtil._compute_city` fill lazily. This gate proves the swap changes the leaf
by EXACTLY ZERO, across many random positions sampled at every game depth (farm
regions grow late; the v2.7 leaf evaluates mid-game states — so we sample
throughout, not just terminal).

Checks (all HARD unless noted), compact-ON vs the PRODUCTION path
(USE_FARM_CACHE=USE_CITY_CACHE=True, USE_COMPACT_LEAF=False — what the cluster
actually runs):

  1. FARM PARTITION — for every farmer-connection node, the compact farm cache's
     component == `FarmUtil.find_farm` from that node (set of node-keys). The
     object BFS is the ground truth the rewrite must reproduce.
  2. CITY PARTITION — for every city edge, the compact city cache's
     (positions, finished) == `CityUtil._compute_city` for that edge.
  3. count_final_scores SCORES — the full `scores[]` array after end-of-game
     resolution is identical compact-ON vs production. (The v1/base path.)
  4. virtual_score_v2 INT — the production leaf return (int) is identical, for
     every player. THIS IS THE LEAF CONTRACT — the value that flows to MCTS /
     training. Also checks `virtual_score` (base) int.
  5. FLOAT-ORDER AUDIT (soft, reported) — the UNCAPPED closure-anticipation
     bonus float compact-ON vs production. Identical partitions can still
     reorder float adds in the farmer-growth branch; this quantifies whether any
     residual ULP drift exists. The contract (the int, check 4) is what gates;
     a nonzero soft count with zero int mismatches is acceptable per the plan.

Coverage (HARD if zero): farms, cities, finished + unfinished cities exercised;
board-edge cities (D16 geometry) reported.

Exits non-zero on ANY hard mismatch, on a build/lookup miss, or if coverage is
empty. Run under the production env (CARCASSONNE_V25_DROP_THREE_OPEN=1
CARCASSONNE_V25_CAP=12) so DEFAULT_CONFIG matches v2.7.

Usage:  python scripts/reconcile_compact_leaf.py --n 400 --snap-every 4
"""
from __future__ import annotations

import argparse
import copy
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import compact_leaf  # noqa: E402
from carcassonne_ai import virtual_score as _vs  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score import virtual_score  # noqa: E402
from carcassonne_ai.virtual_score_v2 import (  # noqa: E402
    DEFAULT_CONFIG,
    _capped,
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
from wingedsheep.carcassonne.utils.city_util import CityUtil  # noqa: E402
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402
from wingedsheep.carcassonne.utils.points_collector import PointsCollector  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _farm_region(farm) -> frozenset:
    """Start-independent identity of a farm component: its set of node keys."""
    return frozenset(
        FarmUtil._farm_node_key(fcc) for fcc in farm.farmer_connections_with_coordinate
    )


def _all_farm_nodes(state):
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


def _all_city_edges(state):
    """Every (CoordinateWithSide) city edge on the board, deduped."""
    out = []
    seen = set()
    for row in range(len(state.board)):
        for col in range(len(state.board[row])):
            tile = state.board[row][col]
            if tile is None:
                continue
            for city_group in tile.city:
                for side in city_group:
                    cws = CoordinateWithSide(Coordinate(row, col), side)
                    if cws not in seen:
                        seen.add(cws)
                        out.append(cws)
    return out


def _scores_after_count(state, use_compact: bool):
    """Full scores[] after end-of-game resolution, compact or production."""
    snap = copy.deepcopy(state)
    if use_compact:
        snap._farm_cache = compact_leaf.build_farm_cache(snap)
        snap._city_cache = compact_leaf.build_city_cache(snap)
    else:
        snap._farm_cache = {}
        snap._city_cache = {}
    PointsCollector.count_final_scores(game_state=snap)
    return tuple(snap.scores)


def _bonus_floats(state, player: int, use_compact: bool):
    """Uncapped closure-anticipation bonus (self, opp) under compact or the
    object-BFS path. Caches are attached so find_farm/find_city resolve the
    chosen way; we read on a deepcopy so the live state is never mutated."""
    snap = copy.deepcopy(state)
    if use_compact:
        snap._farm_cache = compact_leaf.build_farm_cache(snap)
        snap._city_cache = compact_leaf.build_city_cache(snap)
    else:
        snap._farm_cache = {}
        snap._city_cache = {}
    opp = 1 - player
    return (
        _closure_anticipation_bonus(snap, player, DEFAULT_CONFIG),
        _closure_anticipation_bonus(snap, opp, DEFAULT_CONFIG),
    )


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
    ap.add_argument(
        "--values-only",
        action="store_true",
        help="skip the per-node farm/city partition BFS truth checks (faster; "
        "use once the partition equivalence is already proven)",
    )
    ap.add_argument(
        "--canonical",
        action="store_true",
        help="enable CANONICAL_BONUS_SUM (order-independent math.fsum) on BOTH "
        "paths -> demonstrates the closure-bonus reorder flips vanish, i.e. "
        "compact becomes a TRUE bit-exact drop-in",
    )
    args = ap.parse_args()

    if args.canonical:
        import carcassonne_ai.virtual_score_v2 as _v2mod

        _v2mod.CANONICAL_BONUS_SUM = True
        print("CANONICAL_BONUS_SUM = True (order-independent fsum on both paths)")

    # Production leaf config sanity (so DEFAULT_CONFIG == v2.7).
    print(
        f"DEFAULT_CONFIG: closure_p={DEFAULT_CONFIG.closure_p} "
        f"bonus_cap={DEFAULT_CONFIG.bonus_cap} opp_cap={DEFAULT_CONFIG.opp_bonus_cap}"
    )

    game = Game()

    # counters
    states_seen = 0
    farm_nodes = farm_mism = 0
    city_nodes = city_mism = 0
    score_checks = score_mism = 0
    vs_checks = vs_mism = 0
    v2_checks = v2_mism = 0
    float_checks = float_diffs = 0
    max_score_drift = 0.0          # max |pre-round score(prod) - score(compact)|
    min_half_margin = float("inf")  # min distance any pre-round score got to a .5 boundary
    cov_farms = cov_cities = cov_fin = cov_unfin = cov_edge = 0
    first_fail = None

    for g in range(args.n):
        states = collect_states(game, args.seed + g, args.snap_every)
        for state in states:
            if state.players != 2:
                continue
            states_seen += 1

            if not args.values_only:
                # --- check 1: farm partition (compact build vs find_farm) ---
                farm_cache = compact_leaf.build_farm_cache(state)
                for key, fcc in _all_farm_nodes(state):
                    cov_farms += 1
                    farm_nodes += 1
                    truth = _farm_region(FarmUtil.find_farm(state, fcc))
                    got_farm = farm_cache.get(key)
                    got = _farm_region(got_farm) if got_farm is not None else None
                    if got != truth:
                        farm_mism += 1
                        if first_fail is None:
                            first_fail = f"FARM node {key}: compact={got} truth={truth}"

                # --- check 2: city partition (compact build vs _compute_city)
                city_cache = compact_leaf.build_city_cache(state)
                H, W = len(state.board), len(state.board[0])
                for cws in _all_city_edges(state):
                    city_nodes += 1
                    cov_cities += 1
                    t_positions, t_finished = CityUtil._compute_city(state, cws)
                    hit = city_cache.get(cws)
                    if hit is None:
                        city_mism += 1
                        if first_fail is None:
                            first_fail = f"CITY edge {cws.coordinate.row},{cws.coordinate.column},{cws.side} missing from compact cache"
                        continue
                    c_positions, c_finished = hit
                    if frozenset(c_positions) != frozenset(t_positions) or c_finished != t_finished:
                        city_mism += 1
                        if first_fail is None:
                            first_fail = (
                                f"CITY edge {cws.coordinate.row},{cws.coordinate.column},{cws.side}: "
                                f"compact(fin={c_finished},n={len(c_positions)}) "
                                f"truth(fin={t_finished},n={len(t_positions)})"
                            )
                    if t_finished:
                        cov_fin += 1
                    else:
                        cov_unfin += 1
                    # board-edge geometry (D16-flavour): an edge whose opposite
                    # is out of bounds.
                    dr, dc, _os = compact_leaf._CITY_OPP[cws.side]
                    nr, nc = cws.coordinate.row + dr, cws.coordinate.column + dc
                    if not (0 <= nr < H and 0 <= nc < W):
                        cov_edge += 1

            # --- check 3: count_final_scores scores[] ----------------------
            score_checks += 1
            s_prod = _scores_after_count(state, use_compact=False)
            s_comp = _scores_after_count(state, use_compact=True)
            if s_prod != s_comp:
                score_mism += 1
                if first_fail is None:
                    first_fail = f"SCORES prod={s_prod} compact={s_comp}"

            # --- checks 4 + 5: leaf int + float-order audit ----------------
            for p in range(state.players):
                # base virtual_score int
                _vs.USE_COMPACT_LEAF = False
                vs_prod = virtual_score(state, p)
                _vs.USE_COMPACT_LEAF = True
                try:
                    vs_comp = virtual_score(state, p)
                finally:
                    _vs.USE_COMPACT_LEAF = False
                vs_checks += 1
                if vs_prod != vs_comp:
                    vs_mism += 1
                    if first_fail is None:
                        first_fail = f"virtual_score p={p} prod={vs_prod} compact={vs_comp}"

                # v2 leaf int (the contract)
                _vs.USE_COMPACT_LEAF = False
                v2_prod = virtual_score_v2(state, p, DEFAULT_CONFIG)
                _vs.USE_COMPACT_LEAF = True
                try:
                    v2_comp = virtual_score_v2(state, p, DEFAULT_CONFIG)
                finally:
                    _vs.USE_COMPACT_LEAF = False
                v2_checks += 1
                if v2_prod != v2_comp:
                    v2_mism += 1
                    if first_fail is None:
                        first_fail = f"virtual_score_v2 p={p} prod={v2_prod} compact={v2_comp}"

                # float-order audit (soft) + structural int-invariance proof.
                # The closure-bonus float can reorder (commutative adds in the
                # farmer-growth branch) even with identical partitions. Track:
                #  - max_score_drift: the largest |Δ| in the PRE-ROUND v2 score,
                #  - min_half_margin: the closest any pre-round score got to a
                #    rounding (.5) boundary.
                # If max_score_drift < min_half_margin, no reorder can ever flip
                # int(round(score)) -> the leaf output is bit-exact by structure.
                bf_prod = _bonus_floats(state, p, use_compact=False)
                bf_comp = _bonus_floats(state, p, use_compact=True)
                float_checks += 1
                if bf_prod != bf_comp:
                    float_diffs += 1
                cap, opp_cap = DEFAULT_CONFIG.bonus_cap, DEFAULT_CONFIG.opp_bonus_cap
                sf_prod = vs_prod + _capped(bf_prod[0], cap) - _capped(bf_prod[1], opp_cap)
                sf_comp = vs_comp + _capped(bf_comp[0], cap) - _capped(bf_comp[1], opp_cap)
                max_score_drift = max(max_score_drift, abs(sf_prod - sf_comp))
                frac = sf_prod - math.floor(sf_prod)
                min_half_margin = min(min_half_margin, abs(frac - 0.5))

        if (g + 1) % max(1, args.n // 10) == 0:
            print(
                f"  [{g + 1}/{args.n}] states={states_seen} "
                f"farm_nodes={farm_nodes} city_nodes={city_nodes} "
                f"v2_checks={v2_checks} | mism farm={farm_mism} city={city_mism} "
                f"score={score_mism} vs={vs_mism} v2={v2_mism} floatΔ={float_diffs}"
            )

    # ---------------------------------------------------------------------- #
    print("\n=== reconcile_compact_leaf summary ===")
    print(f"states evaluated      : {states_seen}")
    print(f"farm partition checks : {farm_nodes:>8}   mismatches: {farm_mism}")
    print(f"city partition checks : {city_nodes:>8}   mismatches: {city_mism}")
    print(f"scores[] checks       : {score_checks:>8}   mismatches: {score_mism}")
    print(f"virtual_score   checks: {vs_checks:>8}   mismatches: {vs_mism}")
    print(f"virtual_score_v2 checks: {v2_checks:>7}   mismatches: {v2_mism}")
    print(f"float-order audit     : {float_checks:>8}   bonus-float diffs (soft): {float_diffs}")
    print(f"  max pre-round score drift : {max_score_drift:.3e}")
    print(f"  min margin to .5 boundary : {min_half_margin:.3e}")
    drift_safe = max_score_drift == 0.0 or max_score_drift < min_half_margin
    print(
        f"  int-invariance by structure: {'YES' if drift_safe else 'NO'} "
        f"(drift={max_score_drift:.2e} vs margin={min_half_margin:.2e})"
    )
    print(
        f"coverage: farms={cov_farms} cities={cov_cities} "
        f"finished={cov_fin} unfinished={cov_unfin} board-edge-city={cov_edge}"
    )

    # LOGIC equivalence (the actual rewrite correctness): partitions, end
    # scores, and the base value must be bit-identical. v2 int flips are
    # classified separately — they come from non-associative float summation
    # order in the bonus, NOT from the compact logic.
    logic_mism = farm_mism + city_mism + score_mism + vs_mism
    reorder_flips = v2_mism
    coverage_ok = args.values_only or (
        cov_farms > 0 and cov_cities > 0 and cov_fin > 0 and cov_unfin > 0
    )
    total_evals = vs_checks + v2_checks

    if first_fail is not None:
        print(f"\nFIRST FAILURE: {first_fail}")

    if logic_mism > 0:
        print(
            f"\nFAIL: {logic_mism} LOGIC mismatch(es) "
            f"(farm={farm_mism} city={city_mism} scores={score_mism} base={vs_mism}). "
            "Compact leaf is NOT logic-equivalent — real bug."
        )
        return 1
    if not coverage_ok:
        print("\nFAIL: insufficient coverage (need farms + finished + unfinished cities).")
        return 2
    if total_evals < 10000 and not args.values_only:
        print(
            f"\nWARN: only {total_evals} leaf evals (<10k acceptance target). "
            "Re-run with larger --n for the verdict."
        )

    print(
        f"\nLOGIC-EQUIVALENT: compact == production across {total_evals} leaf evals"
        + (
            f" + {farm_nodes} farm + {city_nodes} city partition checks"
            if not args.values_only
            else ""
        )
        + " (partitions / scores[] / base virtual_score all bit-identical)."
    )

    if reorder_flips == 0:
        print(
            f"PASS (BIT-EXACT): virtual_score_v2 int identical; "
            f"closure-bonus float drift={float_diffs}, max={max_score_drift:.2e}."
        )
        return 0

    # Logic-equivalent but v2 int differs. If the score drift is ULP-scale it's
    # a pure float-add reorder at rounding boundaries, not a logic error.
    if max_score_drift < 1e-9:
        print(
            f"NOT INT-BIT-EXACT (reorder): {reorder_flips}/{v2_checks} virtual_score_v2 "
            f"int flips (≤±1 pt), from ULP closure-bonus reorder "
            f"(max score drift {max_score_drift:.2e} << 1e-9; "
            f"min .5-margin {min_half_margin:.2e}). "
            "This is a pre-existing order-sensitivity in the v2.7 leaf, not a "
            "compact bug. Re-run with --canonical for true bit-exactness."
        )
        return 3
    print(
        f"\nFAIL: {reorder_flips} virtual_score_v2 int flips with max score drift "
        f"{max_score_drift:.2e} >= 1e-9 — too large to be float reorder; investigate."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
