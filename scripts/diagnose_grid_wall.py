"""Quantify how many rule-legal tile placements the engine grid silently denies.

The engine board is 35x35 with ``starting_position = Coordinate(6, 15)`` — only 6
rows of headroom above the start tile versus 28 below. Boards that drift upward
hit row 0, and ``StateUpdater.play_tile``'s bounds check keeps those cells out of
``open_positions``, so ``TilePositionFinder`` never offers them. No error, no
signal: on the Android app it renders as an "invisible border" along the top.

Method: play on an oversized board so the grid never binds, but restrict move
CHOICE to the cells the production 35x35 @ (6,15) board would contain (so the
trajectory distribution matches production). At every tile ply, count the legal
placements falling outside that region — those are the moves production cannot
offer.

    .venv/bin/python scripts/diagnose_grid_wall.py [n_games]

Measured 2026-07-30 over 400 random base+farmers games:
    games with >=1 denied placement   67.8%
    tile plies with >=1 denied         21.7%
    denied share of legal placements    2.6%
    denials on a side other than row<0     0
    plies forced to PASS by the wall       0

The second mode replays a phone archive (`measurement/e4_games/*.json`) and
separates the layers, which is what identified this bug:

    .venv/bin/python scripts/diagnose_grid_wall.py --archive PATH.json

At every tile ply it compares three sets of placeable cells — rules-legal (from an
oversized board), the engine/wrapper mask, and the bridge's `all_legal_tile_cells`
(what the GUI draws). Cells in the first but not the second are engine bugs; in
the second but not the third would be bridge/GUI bugs. On the reported game
(1785466497_161583) the board first touched row 0 at ply 88 (44 tiles down) and 25
later tile plies — 12 of them the human's — had rules-legal placements missing from
the engine mask, every one at row -1, with ZERO bridge/GUI disagreements. The
2026-07-27 control game never touched row 0 and had zero denials.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "engine")]

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState  # noqa: E402
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction  # noqa: E402
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule  # noqa: E402
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet  # noqa: E402
from wingedsheep.carcassonne.utils.action_util import ActionUtil  # noqa: E402
from wingedsheep.carcassonne.utils.state_updater import StateUpdater  # noqa: E402

PAD = 40
BIG = 35 + 2 * PAD
R0, R1 = PAD, PAD + 34          # the production grid's rows 0..34, shifted by PAD
C0, C1 = PAD, PAD + 34
START = Coordinate(PAD + 6, PAD + 15)


def _in_production_grid(c: Coordinate) -> bool:
    return R0 <= c.row <= R1 and C0 <= c.column <= C1


def run(n_games: int, seed: int = 0) -> dict:
    rng = random.Random(seed)
    st = {
        "games": 0, "games_any_denied": 0,
        "tile_plies": 0, "plies_any_denied": 0,
        "legal_total": 0, "legal_denied": 0,
        "denied_above_row0": 0, "denied_other_sides": 0,
        "forced_pass_by_wall": 0,
    }
    for _ in range(n_games):
        state = CarcassonneGameState(
            tile_sets=[TileSet.BASE],
            supplementary_rules=[SupplementaryRule.FARMERS],
            players=2,
            board_size=(BIG, BIG),
            starting_position=START,
        )
        st["games"] += 1
        denied_here = False
        while not state.is_terminated():
            actions = ActionUtil.get_possible_actions(state)
            tiles = [a for a in actions if isinstance(a, TileAction)]
            if not tiles:
                state = StateUpdater.apply_action(state, rng.choice(actions))
                continue
            st["tile_plies"] += 1
            inside = [a for a in tiles if _in_production_grid(a.coordinate)]
            st["legal_total"] += len(tiles)
            if len(inside) < len(tiles):
                denied_here = True
                st["plies_any_denied"] += 1
                for a in tiles:
                    if _in_production_grid(a.coordinate):
                        continue
                    st["legal_denied"] += 1
                    if a.coordinate.row < R0:
                        st["denied_above_row0"] += 1
                    else:
                        st["denied_other_sides"] += 1
            if not inside:
                st["forced_pass_by_wall"] += 1
                choice = PassAction()
            else:
                choice = rng.choice(inside)
            state = StateUpdater.apply_action(state, choice)
        if denied_here:
            st["games_any_denied"] += 1
    return st


def replay_archive(path: str) -> None:
    """Layer separation on a real phone game (see the module docstring)."""
    import numpy as np

    sys.path.insert(0, str(REPO / "android" / "app" / "src" / "main" / "python"))
    import android_bridge as AB

    from carcassonne_ai.action_space import tile_action_count
    from carcassonne_ai.game_wrapper import Board, Game

    with open(path) as fh:
        arc = json.load(fh)
    actions, human = arc["actions"], int(arc["human_player"])
    print(f"{Path(path).name}  seed={arc['deck_seed']}  actions={len(actions)}  "
          f"human=P{human}")

    def cells_of(mask, off) -> set[tuple[int, int]]:
        out = set()
        for idx in np.flatnonzero(mask[:tile_action_count(off.size)]):
            wr, wc = divmod(int(idx) // 4, off.size)
            c = off.to_engine(wr, wc)
            out.add((c.row, c.column))
        return out

    g = Game()
    random.seed(arc["deck_seed"])
    b = g.get_init_board()
    # An oversized twin on which the grid never binds. PAD is EVEN on both axes, so
    # the centred window translates exactly and the SAME action index means the same
    # relative cell on both boards.
    oversized = CarcassonneGameState(
        tile_sets=[TileSet.BASE], supplementary_rules=[SupplementaryRule.FARMERS],
        players=2, board_size=(BIG, BIG), starting_position=START)
    oversized.deck = list(b.state.deck)
    oversized.next_tile = b.state.next_tile
    bb = Board.from_state(oversized, total_tiles=72, window_size=g.window_size)

    first_touch, denied_plies, bridge_mismatch = None, [], []
    for ply, idx in enumerate(actions):
        if b.state.is_terminated():
            break
        if b.state.phase.value == "tiles" and b.state.placed_coords:
            rows = [c.row for c in b.state.placed_coords]
            cols = [c.column for c in b.state.placed_coords]
            bbox = (min(rows), max(rows), min(cols), max(cols))
            if first_touch is None and min(rows) == 0:
                first_touch = (ply, len(b.state.placed_coords), bbox)
            prod = cells_of(g.get_valid_moves(b), b.offset)
            unconstrained = {(r - PAD, c - PAD)
                             for (r, c) in cells_of(g.get_valid_moves(bb), bb.offset)}
            if unconstrained - prod:
                denied_plies.append(
                    (ply, sorted(unconstrained - prod), bbox, int(b.state.current_player)))
            if AB.all_legal_tile_cells(g, b) != prod:
                bridge_mismatch.append(ply)
        b = g.get_next_state(b, int(idx))[0]
        bb = g.get_next_state(bb, int(idx))[0]

    print(f"\n  first ply the board touched row 0: {first_touch}")
    print(f"  tile plies with rules-legal moves MISSING from the engine mask: "
          f"{len(denied_plies)}")
    for ply, d, bbox, cp in denied_plies[:10]:
        print(f"    ply {ply:3d} player {cp} bbox(rows {bbox[0]}..{bbox[1]}, "
              f"cols {bbox[2]}..{bbox[3]})  denied: {d}")
    if len(denied_plies) > 10:
        print(f"    ... and {len(denied_plies) - 10} more")
    print(f"  ... of which on the HUMAN's turn: "
          f"{sum(1 for p in denied_plies if p[3] == human)}")
    print(f"  bridge/GUI disagreements with the engine mask: {len(bridge_mismatch)}")


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--archive":
        replay_archive(sys.argv[2])
        return
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    s = run(n)
    for k, v in s.items():
        print(f"{k:22s} {v}")
    print()
    print(f"games with >=1 denied placement : {s['games_any_denied'] / max(1, s['games']):.1%}")
    print(f"tile plies with >=1 denied      : {s['plies_any_denied'] / max(1, s['tile_plies']):.1%}")
    print(f"denied share of legal placements: {s['legal_denied'] / max(1, s['legal_total']):.2%}")


if __name__ == "__main__":
    main()
