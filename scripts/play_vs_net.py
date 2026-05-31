"""Headless terminal play: YOU vs the trained net (NeuralMCTS).

The tkinter GUI (play_vs_tier1_gui.py) is unusable over the Mac->Windows->WSL SSH
chain. This is a text-only play loop:

  - the board is rendered as ASCII each turn (placed tiles + your/AI meeples),
  - on YOUR turn you pick from the engine's enumerated legal moves by number,
  - the AI plays via NeuralMCTS(net priors + v2.7 leaf value) — the production
    play config. Crank --sims for full strength (sims=800 ~ +200 elo over 200).

This is rung 3 of the strength ladder: you play it, and it (hopefully) destroys
you. Records the final score.

Usage:
  python scripts/play_vs_net.py --checkpoint <ckpt> --sims 800 --human 0
"""
from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import torch

from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.utils.action_util import ActionUtil


def load_net(checkpoint, device):
    ck = torch.load(checkpoint, map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, (ns > 10)


def render_board(state) -> str:
    """ASCII map of placed tiles. '.' = empty, '#' = tile, 'M' = a meeple sits on
    that tile. Cropped to the bounding box of placed tiles + a 1-cell margin."""
    coords = list(getattr(state, "placed_coords", []))
    if not coords:
        return "(empty board)"
    rows = [c.row for c in coords]
    cols = [c.column for c in coords]
    r0, r1 = min(rows) - 1, max(rows) + 1
    c0, c1 = min(cols) - 1, max(cols) + 1
    meeple_cells = set()
    for pl in range(state.players):
        for mp in state.placed_meeples[pl]:
            cs = mp.coordinate_with_side.coordinate
            meeple_cells.add((cs.row, cs.column, pl))
    lines = []
    header = "     " + "".join(f"{c%10}" for c in range(c0, c1 + 1))
    lines.append(header)
    for r in range(r0, r1 + 1):
        cells = []
        for c in range(c0, c1 + 1):
            tile = state.board[r][c] if 0 <= r < len(state.board) and 0 <= c < len(state.board[0]) else None
            if tile is None:
                cells.append(".")
            else:
                m = [pl for (mr, mc, pl) in meeple_cells if mr == r and mc == c]
                cells.append(str(m[0]) if m else "#")
        lines.append(f"{r:>4} {''.join(cells)}")
    return "\n".join(lines)


def describe(action) -> str:
    if isinstance(action, TileAction):
        co = action.coordinate
        return f"TILE  at (row={co.row}, col={co.column}) rot={action.tile_rotations}"
    if isinstance(action, MeepleAction):
        cs = action.coordinate_with_side
        return f"MEEPLE {action.meeple_type.name} on {cs.side.name} of (row={cs.coordinate.row}, col={cs.coordinate.column})"
    if isinstance(action, PassAction):
        return "PASS"
    return str(action)


def human_move(game, board):
    state = board.state
    actions = ActionUtil.get_possible_actions(state)
    if not actions:
        print("  (no legal moves — passing)")
        return PassAction()
    print(f"\n  phase: {state.phase.value}   your legal moves:")
    for i, a in enumerate(actions):
        print(f"    [{i:>3}] {describe(a)}")
    while True:
        raw = input("  pick move # (or 'b' for board): ").strip()
        if raw == "b":
            print(render_board(state))
            continue
        try:
            idx = int(raw)
            if 0 <= idx < len(actions):
                return actions[idx]
        except ValueError:
            pass
        print("  invalid; try again.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="play_vs_net")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--sims", type=int, default=800, help="NeuralMCTS sims (800 ~ full strength)")
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--human", type=int, choices=(0, 1), default=0, help="your player index")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net, include_farm = load_net(args.checkpoint, device)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    base = make_single_evaluator(net, device, game)
    leaf_eval = make_v25_value_wrapper(base)
    ai = NeuralMCTS(game=game, evaluator=leaf_eval, simulations=args.sims, c_puct=args.c_puct,
                    seed=(args.seed or 0))

    board = game.get_init_board()
    print(f"\n=== YOU (player {args.human}) vs NET (player {1-args.human}) ===")
    print(f"net: {args.checkpoint}  sims={args.sims}  c={args.c_puct}  scalars={'12' if include_farm else '10'}\n")
    print(render_board(board.state))

    move_no = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == args.human:
            action_obj = human_move(game, board)
            # find the matching action index the wrapper expects
            from carcassonne_ai.action_space import encode
            idx = encode(action_obj, off=board.offset, phase=board.state.phase.value)
            board, _ = game.get_next_state(board, idx)
        else:
            ai.clear()
            print(f"\n  net is thinking ({args.sims} sims)...")
            a = ai.best_action(board)
            from carcassonne_ai.action_space import decode
            act = decode(a, off=board.offset, phase=board.state.phase.value,
                         next_tile=board.state.next_tile,
                         last_tile_coord=(board.state.last_tile_action.coordinate
                                          if board.state.last_tile_action is not None else None))
            print(f"  NET plays: {describe(act)}")
            board, _ = game.get_next_state(board, a)
        move_no += 1
        if move_no % 1 == 0:
            print(render_board(board.state))
            s = board.state.scores
            print(f"  score — you(p{args.human}): {s[args.human]}   net(p{1-args.human}): {s[1-args.human]}")

    s = board.state.scores
    you, them = s[args.human], s[1 - args.human]
    print("\n=== GAME OVER ===")
    print(f"  YOU: {you}    NET: {them}")
    print("  " + ("YOU WIN 🎉" if you > them else "NET WINS" if them > you else "DRAW"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
