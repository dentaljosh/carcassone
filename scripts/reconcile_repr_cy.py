#!/usr/bin/env python3
"""Bit-exact equivalence gate for the Cython board-encoder port (2026-06-17).

NON-NEGOTIABLE before trusting `board_repr.USE_CY_REPR`. Mirrors
scripts/reconcile_cy_leaf.py: play N seeded random games, snapshot the Board at
every ply across both phases, and require EXACT array equality between the
Python reference (`board_repr.encode_board`) and the compiled port
(`flat_repr_cy.encode_board_cy`), for BOTH player perspectives at EVERY position.

The encoded tensor is a 0/1 float32 array, so the acceptance bar is
`np.array_equal` == True, full stop (no float-order escape hatch).

Checks:
  1. ENCODE  — encode_board (py) == encode_board_cy, per player, per ply.
  2. WIRING  — flipping board_repr.USE_CY_REPR at runtime actually routes
     encode_board through the compiled port and returns an identical array.

Usage:
  python scripts/reconcile_repr_cy.py --n 100 --snap-every 1
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import board_repr  # noqa: E402
from carcassonne_ai import flat_repr_cy  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402


def collect_boards(game: Game, seed: int, snap_every: int, max_plies: int = 400):
    """Random-legal play; snapshot live Boards across depth + the terminal."""
    random.seed(seed)
    board = game.get_init_board()
    boards = [board]
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        action = int(random.choice(legal.tolist()))
        board, _ = game.get_next_state(board, action)
        plies += 1
        if plies % snap_every == 0:
            boards.append(board)
    return boards


def _describe(state) -> str:
    return (
        f"phase={state.phase} cur={state.current_player} "
        f"n_placed={len(getattr(state, 'placed_coords', []))}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="games to play")
    ap.add_argument("--snap-every", type=int, default=1, help="snapshot cadence (plies)")
    ap.add_argument("--seed", type=int, default=13579)
    ap.add_argument("--max-mismatch", type=int, default=5, help="stop after this many mismatches")
    args = ap.parse_args()

    # Force the pure-Python reference path for the `py` side.
    board_repr.USE_CY_REPR = False

    game = Game()
    n_cmp = 0
    n_states = 0
    mismatches = []

    for gi in range(args.n):
        boards = collect_boards(game, seed=args.seed + gi, snap_every=args.snap_every)
        for board in boards:
            n_states += 1
            for player in (0, 1):
                py = board_repr.encode_board(board.state, player, board.offset)
                cy = flat_repr_cy.encode_board_cy(board.state, player, board.offset)
                n_cmp += 1
                if py.shape != cy.shape or not np.array_equal(py, cy):
                    # Locate the first differing channel for diagnostics.
                    diff_ch = -1
                    if py.shape == cy.shape:
                        d = np.argwhere(py != cy)
                        if d.size:
                            diff_ch = int(d[0][0])
                    mismatches.append(
                        (gi, player, diff_ch, _describe(board.state))
                    )
                    if len(mismatches) >= args.max_mismatch:
                        break
            if len(mismatches) >= args.max_mismatch:
                break
        if len(mismatches) >= args.max_mismatch:
            break
        if (gi + 1) % 20 == 0:
            print(f"  ... {gi + 1}/{args.n} games, {n_cmp} encodes compared, 0 mismatch")

    print(f"\nstates snapshotted: {n_states}")
    print(f"encodes compared (both players): {n_cmp}")
    if mismatches:
        print(f"\n❌ {len(mismatches)} MISMATCH(es):")
        for gi, player, ch, desc in mismatches:
            print(f"  game{gi} player{player} first-diff-channel={ch}  {desc}")
        return 1
    print("\n✅ 0 mismatches — flat_repr_cy.encode_board_cy is bit-exact to board_repr.encode_board")

    # --- wiring check ---------------------------------------------------------
    boards = collect_boards(game, seed=args.seed + args.n + 1, snap_every=10)
    test_board = boards[len(boards) // 2]
    board_repr._CY_ENCODE = None  # reset lazy bind
    board_repr.USE_CY_REPR = False
    py = board_repr.encode_board(test_board.state, 0, test_board.offset)
    board_repr.USE_CY_REPR = True
    routed = board_repr.encode_board(test_board.state, 0, test_board.offset)
    board_repr.USE_CY_REPR = False
    bound = board_repr._CY_ENCODE not in (None, False)
    ok = bound and np.array_equal(py, routed)
    print(f"wiring: lazy-bind fired={bound}  routed==py={np.array_equal(py, routed)}  -> {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
