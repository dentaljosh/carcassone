#!/usr/bin/env python3
"""Isolated wall-clock A/B for the Cython board-encoder port (2026-06-17).

Sizes the REAL speedup of flat_repr_cy.encode_board_cy vs board_repr.encode_board
on a realistic pool of mid/late-game boards (cProfile distorts tiny-frequent fns;
this is a direct timed A/B — the playbook ruler). Steady-state (tile-repr cache
warmed) over both player perspectives.

Usage:
  python scripts/microbench_flat_repr.py --games 8 --reps 6
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import board_repr  # noqa: E402
from carcassonne_ai import flat_repr_cy  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402


def collect_boards(game, seed, snap_every=2, max_plies=400):
    random.seed(seed)
    board = game.get_init_board()
    boards = []
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        plies += 1
        if plies % snap_every == 0:
            boards.append(board)
    return boards


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("--reps", type=int, default=6)
    ap.add_argument("--seed", type=int, default=4242)
    args = ap.parse_args()

    board_repr.USE_CY_REPR = False
    game = Game()
    pool = []
    for gi in range(args.games):
        pool.extend(collect_boards(game, args.seed + gi))
    print(f"board pool: {len(pool)} states (mid/late-game distribution)")

    work = [(b, p) for b in pool for p in (0, 1)]

    # warm caches (tile-repr + any import-time work) and sanity-check equality
    for b, p in work:
        a = board_repr.encode_board(b.state, p, b.offset)
        c = flat_repr_cy.encode_board_cy(b.state, p, b.offset)
        assert np.array_equal(a, c)

    def timeit(fn):
        best = float("inf")
        for _ in range(args.reps):
            t0 = time.perf_counter()
            for b, p in work:
                fn(b.state, p, b.offset)
            dt = time.perf_counter() - t0
            best = min(best, dt)
        return best

    n = len(work)
    t_py = timeit(board_repr.encode_board)
    t_cy = timeit(flat_repr_cy.encode_board_cy)

    print(f"\nencodes/rep: {n}")
    print(f"  python  : {t_py*1e3:8.2f} ms/rep  ({t_py/n*1e6:7.2f} us/encode)")
    print(f"  cython  : {t_cy*1e3:8.2f} ms/rep  ({t_cy/n*1e6:7.2f} us/encode)")
    print(f"  speedup : {t_py/t_cy:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
