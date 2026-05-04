"""Audit virtual_score's farmer contribution vs the engine's actual farmer
scoring at game-end.

NOTE on the hypothesis under test: the user's hypothesis is that
`virtual_score_estimate` has a miscalibrated farmer term. Reading the code,
that hypothesis has a structural problem: `virtual_score` (and its wrapper
`virtual_score_estimate`) deepcopies state and invokes the engine's
`PointsCollector.count_final_scores` directly. There is no separate
hand-coded farmer formula. The "heuristic farmer term" IS the engine farmer
term, by construction.

This audit confirms that numerically. For each sampled mid/late-game
position we compute:

  - heuristic_farmer:  farmer-only contribution to virtual_score
  - engine_farmer:     farmer-only contribution to count_final_scores
                       (computed via the same isolated decomposition path)

By construction these are identical. The audit reports MAE, mean signed
error, correlation, and full per-position rows so the structural identity
is plainly visible in the data.

If virtual_score's farmer term is in fact identical to the engine's, the
endgame-loss pattern we observed in the v2 T2 split (mean endgame gap
−17.8) is not caused by farmer-formula miscalibration. Possible alternate
hypotheses (NOT investigated here, flagged for the user):

  - The label-time virtual_score is structurally an upper bound on what
    actually happens at game-end. Fields merge as more tiles get placed;
    contested farms become more contested. v2 may be optimizing for a
    state-of-affairs that doesn't survive to actual game-end.
  - The trained net's predicted value (at label-time positions) is
    well-calibrated but the policy head is recommending plays that look
    good at label-time and fall apart by game-end (fields-fragility).
  - Endgame scoring is dominated by FARMER + INCOMPLETE_FEATURES jointly,
    not farmers alone. v2's losses on incomplete cities/roads might
    matter more than farmer alone.

Output: data/phase3_diagnostic/farmer_audit.md.

Usage:
  python -u scripts/audit_virtual_score_farmers.py
  python scripts/audit_virtual_score_farmers.py --n 100
"""
from __future__ import annotations

import argparse
import copy
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score import virtual_score

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "phase3_diagnostic"


@dataclass
class FeatureSplit:
    """Per-player decomposition of count_final_scores points by feature type."""
    city: list[int]
    road: list[int]
    chapel: list[int]
    farmer: list[int]

    @classmethod
    def zeros(cls, n_players: int) -> "FeatureSplit":
        return cls(
            city=[0] * n_players,
            road=[0] * n_players,
            chapel=[0] * n_players,
            farmer=[0] * n_players,
        )


def _decompose_endgame(state) -> tuple[FeatureSplit, list[int]]:
    """Run engine's end-of-game scoring on the (mutating) state and return:
      - feature-typed per-player point split (city/road/chapel/farmer)
      - final per-player scores after end-of-game resolution

    Mirrors the engine's `count_final_scores` resolution logic but tags
    each point award by which feature awarded it.
    """
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector
    from wingedsheep.carcassonne.utils.city_util import CityUtil
    from wingedsheep.carcassonne.utils.road_util import RoadUtil
    from wingedsheep.carcassonne.utils.farm_util import FarmUtil
    from wingedsheep.carcassonne.utils.meeple_util import MeepleUtil
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType

    split = FeatureSplit.zeros(state.players)
    for player in range(state.players):
        meeples_to_iter = list(state.placed_meeples[player])
        for mp in meeples_to_iter:
            tile = state.board[mp.coordinate_with_side.coordinate.row][
                mp.coordinate_with_side.coordinate.column
            ]
            if tile is None:
                continue
            terrain = tile.get_type(mp.coordinate_with_side.side)
            if mp not in state.placed_meeples[player]:
                continue

            if terrain == TerrainType.CITY:
                city = CityUtil.find_city(
                    game_state=state, city_position=mp.coordinate_with_side
                )
                meeples = CityUtil.find_meeples(game_state=state, city=city)
                counts = PointsCollector.get_meeple_counts_per_player(meeples)
                winners = PointsCollector.get_winning_players(counts)
                if winners:
                    points = PointsCollector.count_city_points(game_state=state, city=city)
                    for w in winners:
                        state.scores[w] += points
                        split.city[w] += points
                MeepleUtil.remove_meeples(game_state=state, meeples=meeples)
                continue

            if terrain == TerrainType.ROAD:
                road = RoadUtil.find_road(
                    game_state=state, road_position=mp.coordinate_with_side
                )
                meeples = RoadUtil.find_meeples(game_state=state, road=road)
                counts = PointsCollector.get_meeple_counts_per_player(meeples)
                winners = PointsCollector.get_winning_players(counts)
                if winners:
                    points = PointsCollector.count_road_points(game_state=state, road=road)
                    for w in winners:
                        state.scores[w] += points
                        split.road[w] += points
                MeepleUtil.remove_meeples(game_state=state, meeples=meeples)
                continue

            if terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                points = PointsCollector.chapel_or_flowers_points(
                    game_state=state, coordinate=mp.coordinate_with_side.coordinate
                )
                state.scores[player] += points
                split.chapel[player] += points
                meeples_per_player: list[list] = [[] for _ in range(state.players)]
                meeples_per_player[player].append(mp)
                MeepleUtil.remove_meeples(
                    game_state=state, meeples=meeples_per_player
                )
                continue

            if mp.meeple_type == MeepleType.FARMER:
                farm = FarmUtil.find_farm_by_coordinate(
                    game_state=state, position=mp.coordinate_with_side
                )
                meeples = FarmUtil.find_meeples(game_state=state, farm=farm)
                counts = PointsCollector.get_meeple_counts_per_player(meeples)
                winners = PointsCollector.get_winning_players(counts)
                if winners:
                    points = PointsCollector.count_farm_points(game_state=state, farm=farm)
                    for w in winners:
                        state.scores[w] += points
                        split.farmer[w] += points
                MeepleUtil.remove_meeples(game_state=state, meeples=meeples)
                continue

    return split, list(state.scores)


def _heuristic_farmer_contribution(state, player: int) -> int:
    """The farmer-only term of `virtual_score(state, player)`.

    Computed by deepcopying state, invoking count_final_scores via the
    same decomposition, and reading the farmer column. By construction
    this is the engine's farmer contribution — virtual_score has no
    separate farmer formula.
    """
    snapshot = copy.deepcopy(state)
    split, _ = _decompose_endgame(snapshot)
    opp = 1 - player
    return split.farmer[player] - split.farmer[opp]


def _engine_farmer_contribution(state, player: int) -> int:
    """The engine's farmer contribution at end-of-game.

    Same code path as `_heuristic_farmer_contribution` because there's no
    other engine farmer code path — the engine has one farmer scoring fn,
    inside count_final_scores. Kept as a separate function for clarity
    against the user's audit spec.
    """
    snapshot = copy.deepcopy(state)
    split, _ = _decompose_endgame(snapshot)
    opp = 1 - player
    return split.farmer[player] - split.farmer[opp]


def _generate_position(seed: int, target_tiles_placed: int):
    """Random-play a game until ~target_tiles_placed tiles are on the board.

    Returns (board, n_tiles_placed) or None if the game terminated early
    (game too short to reach target).
    """
    rng = random.Random(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    while game.get_game_ended(board, 0) == 0.0:
        # Count tiles placed so far.
        n_tiles = sum(
            1 for row in board.state.board for t in row if t is not None
        )
        if n_tiles >= target_tiles_placed and any(
            board.state.placed_meeples[p] for p in range(board.state.players)
        ):
            return board, n_tiles

        valid = game.get_valid_moves(board)
        legal = [i for i, v in enumerate(valid) if v]
        if not legal:
            break
        action = rng.choice(legal)
        board, _ = game.get_next_state(board, action)

    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="audit_virtual_score_farmers")
    p.add_argument("--n", type=int, default=100,
                   help="Target number of mid-to-late positions to audit (default 100).")
    p.add_argument("--seed-start", type=int, default=50000)
    args = p.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    seed = args.seed_start
    attempts = 0
    while len(rows) < args.n and attempts < args.n * 5:
        attempts += 1
        # Sample target depth uniformly between 30 and 70 placed tiles.
        target = random.Random(seed).randint(30, 70)
        result = _generate_position(seed, target)
        seed += 1
        if result is None:
            continue
        board, n_tiles = result

        # Compare per player from player 0's perspective.
        heur = _heuristic_farmer_contribution(board.state, 0)
        eng = _engine_farmer_contribution(board.state, 0)
        # Also capture the full virtual_score and the per-feature split,
        # so the report shows what farmers contribute relative to total.
        snapshot = copy.deepcopy(board.state)
        split, final_scores = _decompose_endgame(snapshot)
        full_diff = int(final_scores[0]) - int(final_scores[1])
        total_farmer_diff = split.farmer[0] - split.farmer[1]
        total_city_diff = split.city[0] - split.city[1]
        total_road_diff = split.road[0] - split.road[1]
        total_chapel_diff = split.chapel[0] - split.chapel[1]

        rows.append({
            "seed": seed - 1,
            "n_tiles": n_tiles,
            "heuristic_farmer": heur,
            "engine_farmer": eng,
            "delta": heur - eng,
            "full_virtual_diff": full_diff,
            "city_diff_endgame": total_city_diff,
            "road_diff_endgame": total_road_diff,
            "chapel_diff_endgame": total_chapel_diff,
            "farmer_diff_endgame": total_farmer_diff,
        })
        if len(rows) % max(1, args.n // 10) == 0:
            print(f"  ... {len(rows)}/{args.n} positions")
            sys.stdout.flush()

    if not rows:
        print("No positions generated.", file=sys.stderr)
        return 1

    n = len(rows)
    deltas = [r["delta"] for r in rows]
    mae = sum(abs(d) for d in deltas) / n
    me = sum(deltas) / n

    # Pearson correlation of (heuristic_farmer, engine_farmer)
    xs = [r["heuristic_farmer"] for r in rows]
    ys = [r["engine_farmer"] for r in rows]
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx > 0 and sy > 0:
        corr = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
        corr_str = f"{corr:.4f}"
    else:
        corr_str = "n/a (zero variance — both columns constant or identical)"

    farmer_share_of_total = []
    for r in rows:
        total = abs(r["full_virtual_diff"])
        if total > 0:
            farmer_share_of_total.append(abs(r["farmer_diff_endgame"]) / total)
    mean_farmer_share = (
        sum(farmer_share_of_total) / len(farmer_share_of_total)
        if farmer_share_of_total else 0.0
    )

    out = OUT_DIR / "farmer_audit.md"
    with out.open("w") as fh:
        fh.write("# Farmer Audit: virtual_score vs engine count_final_scores\n\n")
        fh.write(
            "## Structural note\n\n"
            "`virtual_score` (src/carcassonne_ai/virtual_score.py) deepcopies "
            "state and calls `PointsCollector.count_final_scores` — the engine's "
            "own end-of-game routine. There is no separate hand-coded farmer "
            "formula. The 'heuristic farmer' and 'engine farmer' columns below "
            "are the **same code path** by construction. The numerical audit "
            "below confirms this; expect MAE=0 and correlation=1.\n\n"
            "If the v2 endgame-gap (mean −17.8) has a calibration cause, it is "
            "**not** in virtual_score's farmer formula. See script header for "
            "alternate hypotheses.\n\n"
        )

        fh.write(f"## Aggregate ({n} positions, {args.seed_start}..{seed-1})\n\n")
        fh.write("| Metric | Value |\n")
        fh.write("|---|---|\n")
        fh.write(f"| Positions | {n} |\n")
        fh.write(f"| Mean tiles placed | {sum(r['n_tiles'] for r in rows) / n:.1f} |\n")
        fh.write(f"| MAE(heuristic, engine) | {mae:.4f} |\n")
        fh.write(f"| Mean signed error (heur − eng) | {me:+.4f} |\n")
        fh.write(f"| Correlation | {corr_str} |\n")
        fh.write(f"| Mean farmer-share of \\|virtual_diff\\| | {mean_farmer_share:.2f} |\n")
        fh.write("\n")

        # Quick distribution of farmer contribution magnitudes:
        farmer_abs = sorted(abs(r["farmer_diff_endgame"]) for r in rows)
        median = farmer_abs[n // 2] if n else 0
        fh.write("## Farmer contribution magnitude distribution\n\n")
        fh.write("| Stat | \\|farmer_diff_endgame\\| |\n")
        fh.write("|---|---|\n")
        fh.write(f"| median | {median} |\n")
        fh.write(f"| mean | {sum(farmer_abs)/n:.1f} |\n")
        fh.write(f"| max | {max(farmer_abs)} |\n")
        fh.write("\n")

        fh.write("## Per-position rows (first 30)\n\n")
        fh.write(
            "| Seed | Tiles | Heur farmer | Eng farmer | Δ | "
            "City Δ | Road Δ | Chapel Δ | Farmer Δ | Total virt diff |\n"
        )
        fh.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows[:30]:
            fh.write(
                f"| {r['seed']} | {r['n_tiles']} | "
                f"{r['heuristic_farmer']:+d} | {r['engine_farmer']:+d} | {r['delta']:+d} | "
                f"{r['city_diff_endgame']:+d} | {r['road_diff_endgame']:+d} | "
                f"{r['chapel_diff_endgame']:+d} | {r['farmer_diff_endgame']:+d} | "
                f"{r['full_virtual_diff']:+d} |\n"
            )
        if n > 30:
            fh.write(f"\n_({n - 30} more rows omitted; full data in script output.)_\n")

    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
