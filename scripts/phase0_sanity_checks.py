"""Phase 0 engine sanity checks.

Verifies the vendored wingedsheep engine behaves correctly under our locked
Phase 1 scope (Base + River + Farmers, 2 players). If any check fails, the
engine is unsafe to build on top of and must be patched before Phase 1.

Checks:
  1. 100 random games complete without exceptions, with non-trivial scoring
  2. Cloister surrounded by 8 tiles scores 9 points
  3. 3-tile completed city with one shield scores 8 points (3*2 + 2)
  4. Tied feature scoring: a finished road with one meeple from each player
     awards full points to BOTH (this is a vendored-fork patch — original
     engine returned None on ties and nobody scored)
  5. Engine's bundled pytest tests still pass (we patched points_collector)

Run:  python scripts/phase0_sanity_checks.py
Exit code 0 = all green.
"""
from __future__ import annotations

import random
import subprocess
import sys
import traceback
from pathlib import Path

from wingedsheep.carcassonne.carcassonne_game import CarcassonneGame
from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
from wingedsheep.carcassonne.utils.points_collector import PointsCollector


REPO_ROOT = Path(__file__).resolve().parent.parent


def check_random_games(n: int = 100) -> None:
    """Play n random games end-to-end. Fail if any errors or pathological scores."""
    failures: list[str] = []
    move_lengths: list[int] = []
    score_sums: list[int] = []
    placed_tile_counts: list[int] = []

    for seed in range(n):
        random.seed(seed)
        game = CarcassonneGame(
            players=2,
            tile_sets=[TileSet.BASE, TileSet.THE_RIVER],
            supplementary_rules=[SupplementaryRule.FARMERS],
        )
        moves = 0
        try:
            while not game.is_finished():
                player = game.get_current_player()
                actions = game.get_possible_actions()
                if not actions:
                    failures.append(f"seed {seed}: empty action list at move {moves}")
                    break
                game.step(player, random.choice(actions))
                moves += 1
        except Exception:
            failures.append(f"seed {seed}: exception at move {moves}\n{traceback.format_exc()}")
            continue

        scores = list(game.state.scores)
        placed = sum(1 for row in game.state.board for tile in row if tile is not None)
        if sum(scores) <= 0:
            failures.append(f"seed {seed}: zero/negative total score {scores}")
        if placed < 30:
            failures.append(f"seed {seed}: only {placed} tiles placed (suspiciously few)")
        if any(s < 0 for s in scores):
            failures.append(f"seed {seed}: negative score {scores}")
        move_lengths.append(moves)
        score_sums.append(sum(scores))
        placed_tile_counts.append(placed)

    print(f"  {n} random games:")
    print(f"    moves: min={min(move_lengths)}, mean={sum(move_lengths)/len(move_lengths):.1f}, max={max(move_lengths)}")
    print(f"    score sums: min={min(score_sums)}, mean={sum(score_sums)/len(score_sums):.1f}, max={max(score_sums)}")
    print(f"    tiles placed: min={min(placed_tile_counts)}, mean={sum(placed_tile_counts)/len(placed_tile_counts):.1f}, max={max(placed_tile_counts)}")

    if failures:
        for f in failures[:10]:
            print(f"  FAIL: {f}")
        print(f"  ... ({len(failures)} total failures)")
        raise AssertionError(f"{len(failures)} of {n} random games failed")
    print("  OK")


def check_cloister_scoring() -> None:
    """A chapel surrounded by 8 tiles scores 9 points."""
    state = CarcassonneGameState()
    state.players = 2
    state.placed_meeples = [[], []]
    state.scores = [0, 0]

    # 3x3 grid: chapel in middle, anything in the 8 neighbors.
    state.board = [[None] * 3 for _ in range(3)]
    chapel_tile = base_tiles["chapel"]
    filler = base_tiles["chapel"]  # filler doesn't matter for chapel scoring
    for r in range(3):
        for c in range(3):
            state.board[r][c] = chapel_tile if (r, c) == (1, 1) else filler

    # Place a player-0 meeple on the chapel center.
    state.placed_meeples[0].append(
        MeeplePosition(
            meeple_type=MeepleType.NORMAL,
            coordinate_with_side=CoordinateWithSide(Coordinate(1, 1), Side.CENTER),
        )
    )

    PointsCollector.remove_meeples_and_collect_points(
        game_state=state, coordinate=Coordinate(1, 1)
    )

    if state.scores != [9, 0]:
        raise AssertionError(f"cloister score expected [9, 0], got {state.scores}")
    print(f"  cloister surrounded by 8 tiles: scored {state.scores[0]} (expected 9)  OK")


def check_shielded_city_scoring() -> None:
    """A 3-tile completed city with one shield scores 3*2 + 2 = 8 points.

    Layout (1 row, 3 cols):
        col 0: city_top.turn(1)            (city on RIGHT)
        col 1: city_narrow_shield          (city on LEFT and RIGHT, shield=True)
        col 2: city_top.turn(3)            (city on LEFT)

    All city sides connect; city is closed; one tile has a shield → 8 pts.
    """
    state = CarcassonneGameState()
    state.players = 2
    state.placed_meeples = [[], []]
    state.scores = [0, 0]

    state.board = [[None, None, None]]
    state.board[0][0] = base_tiles["city_top"].turn(1)
    state.board[0][1] = base_tiles["city_narrow_shield"]
    state.board[0][2] = base_tiles["city_top"].turn(3)

    # Place a meeple on the city in the middle tile (left side of middle tile).
    state.placed_meeples[0].append(
        MeeplePosition(
            meeple_type=MeepleType.NORMAL,
            coordinate_with_side=CoordinateWithSide(Coordinate(0, 1), Side.LEFT),
        )
    )

    PointsCollector.remove_meeples_and_collect_points(
        game_state=state, coordinate=Coordinate(0, 1)
    )

    if state.scores != [8, 0]:
        raise AssertionError(
            f"shielded 3-tile city expected [8, 0], got {state.scores}"
        )
    if len(state.placed_meeples[0]) != 0:
        raise AssertionError(
            f"meeple should be returned after city scored, still placed: "
            f"{state.placed_meeples[0]}"
        )
    print(f"  3-tile city with 1 shield: scored {state.scores[0]} (expected 8)  OK")


def check_tied_road_scoring() -> None:
    """A finished feature with tied meeple counts must award points to all
    tied players (Carcassonne rule). Build a 2-tile finished road with one
    meeple from each player on it and confirm both score 2 points.

    This protects against the original wingedsheep bug where ties returned
    None and nobody scored — see DECISIONS.md for the patch rationale.
    """
    state = CarcassonneGameState()
    state.players = 2
    state.placed_meeples = [[], []]
    state.scores = [0, 0]

    # Two road-end tiles facing each other to form a closed 2-tile road.
    # We'll use chapel_with_road tiles — they have a road from BOTTOM to CENTER
    # (a road end). Place two of them with the road sides facing each other.
    # Two `crossroads` tiles vertically: the engine's road_util_test confirms
    # this creates a finished road segment between the two crossroad centers
    # (each crossroad terminates roads at its center).
    state.board = [[None] for _ in range(2)]
    state.board[0][0] = base_tiles["crossroads"]
    state.board[1][0] = base_tiles["crossroads"]

    # Place one meeple per player on the same finished road segment
    # (top tile's bottom edge + bottom tile's top edge are the same road).
    state.placed_meeples[0].append(
        MeeplePosition(
            meeple_type=MeepleType.NORMAL,
            coordinate_with_side=CoordinateWithSide(Coordinate(0, 0), Side.BOTTOM),
        )
    )
    state.placed_meeples[1].append(
        MeeplePosition(
            meeple_type=MeepleType.NORMAL,
            coordinate_with_side=CoordinateWithSide(Coordinate(1, 0), Side.TOP),
        )
    )

    # Trigger scoring at the second-placed coordinate.
    PointsCollector.remove_meeples_and_collect_points(
        game_state=state, coordinate=Coordinate(1, 0)
    )

    # 2-tile road, no inn → 2 points. Tied → both players score 2.
    if state.scores != [2, 2]:
        raise AssertionError(
            f"tied 2-tile road expected [2, 2] (both score), got {state.scores}"
        )
    print(f"  tied 2-tile road: scored {state.scores} (expected [2, 2])  OK")


def check_engine_pytests() -> None:
    """Run the engine's bundled unittest suite to verify our patches didn't break anything."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(REPO_ROOT / "engine" / "tests"), "-q"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise AssertionError("engine bundled pytest suite failed")
    last_line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    print(f"  engine bundled tests: {last_line}  OK")


def main() -> int:
    print("Phase 0 engine sanity checks")
    print("============================")
    print("[1/5] random fuzz (100 games)")
    check_random_games(n=100)
    print("[2/5] cloister scoring (chapel + 8 neighbors → 9 pts)")
    check_cloister_scoring()
    print("[3/5] shielded city scoring (3 tiles + shield → 8 pts)")
    check_shielded_city_scoring()
    print("[4/5] tied feature scoring (both tied players score full pts)")
    check_tied_road_scoring()
    print("[5/5] engine bundled pytest suite")
    check_engine_pytests()
    print("\nAll sanity checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
