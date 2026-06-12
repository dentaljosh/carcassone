"""Reconcile the incremental window-offset tracker against the full-scan.

Validation gate for the O(1) incremental centroid optimization (board_repr +
game_wrapper). Plays N>=40 seeded random games to the end; at EVERY ply,
along BOTH the get_next_state (new-Board) and apply_action_inplace (rollout)
paths, asserts that the Board's incrementally-tracked `offset` (and the
underlying sum_row/sum_col/tile_count) is BIT-IDENTICAL to the legacy full
board scan `compute_window_offset(state)`. Covers tile plies AND meeple plies,
multiple seeds, full games (the tail, where the board is largest, is where a
drift bug would surface).

Usage (numpy-only; no torch):
    nice -n 19 python3 scripts/reconcile_window_offset.py --n 40 --workers 4

Pass = 0 mismatches across all plies/games. Any mismatch prints the exact
failing (seed, ply, phase, expected, got) and the script exits non-zero.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (os.path.join(_ROOT, "src"), os.path.join(_ROOT, "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from carcassonne_ai.game_wrapper import Game, Board  # noqa: E402
from carcassonne_ai.board_repr import (  # noqa: E402
    centroid_sums,
    compute_window_offset,
)


@dataclass
class GameResult:
    seed: int
    plies: int
    tile_plies: int
    meeple_plies: int
    inplace_plies: int
    mismatches: list  # list of (where, ply, phase, expected, got)
    error: str | None = None


def _check(board: Board, game: Game, where: str, ply: int, out: list) -> None:
    """Assert the incremental offset + sums match a fresh full scan."""
    scan_off = compute_window_offset(board.state, game.window_size)
    scan_sr, scan_sc, scan_tc = centroid_sums(board.state)
    phase = board.state.phase.value
    if board.offset != scan_off:
        out.append((where + ":offset", ply, phase, scan_off, board.offset))
    inc = (board.sum_row, board.sum_col, board.tile_count)
    if inc != (scan_sr, scan_sc, scan_tc):
        out.append((where + ":sums", ply, phase, (scan_sr, scan_sc, scan_tc), inc))


def _play_one(args: tuple[int, int]) -> GameResult:
    seed, window_size = args
    game = Game(window_size=window_size)
    rng = random.Random(seed)
    mismatches: list = []
    tile_plies = meeple_plies = inplace_plies = 0
    ply = 0
    try:
        board = game.get_init_board()
        _check(board, game, "init", ply, mismatches)
        while game.get_game_ended(board, 0) == 0.0:
            phase = board.state.phase.value
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                return GameResult(seed, ply, tile_plies, meeple_plies,
                                  inplace_plies, mismatches,
                                  error=f"seed {seed}: empty legal mask at ply {ply}")
            idx = int(rng.choice(legal))

            # Path A: get_next_state (safe, new Board). This is the production
            # tree-expansion path.
            board, _ = game.get_next_state(board, idx)
            ply += 1
            if phase == "tiles":
                tile_plies += 1
            else:
                meeple_plies += 1
            _check(board, game, "get_next_state", ply, mismatches)

            # Path B: also exercise apply_action_inplace on an independent
            # deepcopy of the PARENT-of-this-board so the rollout mutation path
            # is covered at this same position. We re-derive a scratch board
            # from the current board and take one legal in-place step.
            if game.get_game_ended(board, 0) == 0.0:
                import copy
                scratch = Board(
                    state=copy.deepcopy(board.state),
                    total_tiles=board.total_tiles,
                    offset=board.offset,
                    sum_row=board.sum_row,
                    sum_col=board.sum_col,
                    tile_count=board.tile_count,
                )
                smask = game.get_valid_moves(scratch)
                slegal = np.flatnonzero(smask)
                if slegal.size:
                    sidx = int(rng.choice(slegal))
                    game.apply_action_inplace(scratch, sidx)
                    inplace_plies += 1
                    _check(scratch, game, "apply_action_inplace", ply, mismatches)
    except Exception as exc:  # surface, don't swallow
        return GameResult(seed, ply, tile_plies, meeple_plies, inplace_plies,
                          mismatches, error=f"seed {seed}: {type(exc).__name__}: {exc}")
    return GameResult(seed, ply, tile_plies, meeple_plies, inplace_plies, mismatches)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="number of seeded games")
    ap.add_argument("--seed", type=int, default=0, help="base seed")
    ap.add_argument("--window-size", type=int, default=25)
    ap.add_argument("--workers", type=int, default=4,
                    help="parallel processes (keep LOW; a flywheel may be running)")
    args = ap.parse_args(argv)

    arglist = [(args.seed + i, args.window_size) for i in range(args.n)]
    workers = max(1, min(args.workers, args.n))

    if workers <= 1:
        results = [_play_one(a) for a in arglist]
    else:
        from multiprocessing import Pool
        with Pool(processes=workers) as pool:
            results = pool.map(_play_one, arglist)

    total_plies = sum(r.plies for r in results)
    total_tile = sum(r.tile_plies for r in results)
    total_meeple = sum(r.meeple_plies for r in results)
    total_inplace = sum(r.inplace_plies for r in results)
    total_mismatch = sum(len(r.mismatches) for r in results)
    errors = [r.error for r in results if r.error]

    print(f"games:              {len(results)}")
    print(f"total plies:        {total_plies}")
    print(f"  tile plies:       {total_tile}")
    print(f"  meeple plies:     {total_meeple}")
    print(f"  inplace plies:    {total_inplace}")
    # checks: init(1) + one per get_next_state ply + one per inplace step,
    # each comparing both offset and sums.
    n_checks = (len(results) + total_plies + total_inplace) * 2
    print(f"reconcile checks:   {n_checks}")
    print(f"MISMATCHES:         {total_mismatch}")

    if errors:
        print("\nERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)

    if total_mismatch:
        print("\nFAILING CASES (first 20):", file=sys.stderr)
        shown = 0
        for r in results:
            for (where, ply, phase, expected, got) in r.mismatches:
                print(f"  seed={r.seed} {where} ply={ply} phase={phase} "
                      f"expected={expected} got={got}", file=sys.stderr)
                shown += 1
                if shown >= 20:
                    break
            if shown >= 20:
                break
        print("\nRESULT: FAIL", file=sys.stderr)
        return 1

    if errors:
        print("\nRESULT: ERRORED (no mismatches, but games errored)", file=sys.stderr)
        return 2

    print("\nRESULT: PASS (0 mismatches, all games to completion)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
