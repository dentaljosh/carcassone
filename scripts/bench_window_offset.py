"""Bench: incremental window-offset vs full board scan.

Two measurements, both interleaved A/B/A/B so the flywheel's load contamination
cancels in the RATIO (absolute ns are meaningless on a busy box):

  1. per-call offset cost: offset_from_centroid_sums (incremental) vs
     compute_window_offset (full 35x35 scan), over a realistic distribution of
     mid/late-game board states harvested from real games.
  2. whole get_next_state cost: the real transition with the incremental tracker
     vs a forced-full-scan variant (old behavior) — same action sequence.

Usage:
    nice -n 19 python3 scripts/bench_window_offset.py --games 6 --reps 3
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

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
    offset_from_centroid_sums,
)
from wingedsheep.carcassonne.utils.state_updater import StateUpdater  # noqa: E402


def harvest_states(n_games: int, window_size: int, seed: int) -> list:
    """Play random games; snapshot the engine state at every ply."""
    states = []
    for g in range(n_games):
        game = Game(window_size=window_size)
        rng = random.Random(seed + g)
        board = game.get_init_board()
        while game.get_game_ended(board, 0) == 0.0:
            states.append(board.state)
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        states.append(board.state)
    return states


def harvest_action_sequences(n_games: int, window_size: int, seed: int) -> list:
    """Record (init-not-needed) the legal action index chosen at each ply, so a
    game can be replayed deterministically for the get_next_state bench."""
    seqs = []
    for g in range(n_games):
        game = Game(window_size=window_size)
        rng = random.Random(seed + g)
        board = game.get_init_board()
        seq = []
        while game.get_game_ended(board, 0) == 0.0:
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            idx = int(rng.choice(legal))
            seq.append(idx)
            board, _ = game.get_next_state(board, idx)
        seqs.append((seed + g, seq))
    return seqs


def bench_per_call(states, window_size, reps):
    """Interleaved A/B timing of the two offset computations over `states`."""
    sums = [centroid_sums(s) for s in states]
    inc_t = scan_t = 0.0
    for _ in range(reps):
        # incremental
        t0 = time.perf_counter()
        for s, (sr, sc, tc) in zip(states, sums):
            offset_from_centroid_sums(s, sr, sc, tc, window_size)
        inc_t += time.perf_counter() - t0
        # full scan
        t0 = time.perf_counter()
        for s in states:
            compute_window_offset(s, window_size)
        scan_t += time.perf_counter() - t0
    n = len(states) * reps
    return inc_t, scan_t, n


def replay_incremental(seed, seq, window_size):
    game = Game(window_size=window_size)
    board = game.get_init_board()
    for idx in seq:
        try:
            board, _ = game.get_next_state(board, idx)
        except Exception:
            # The engine's terminal count_final_scores crashes on a few random
            # games (pre-existing, unrelated to this optimization). Stop this
            # game's replay; the timing collected so far is still valid and the
            # SAME games stop in BOTH variants, so the ratio is unaffected.
            break
    return board


def replay_fullscan(seed, seq, window_size):
    """Same transitions but force a full board scan for the offset every ply
    (reproduces the pre-optimization get_next_state cost)."""
    game = Game(window_size=window_size)
    board = game.get_init_board()
    for idx in seq:
        try:
            state = board.state
            action = game._decode_for(state, board.offset, idx)
            new_state = StateUpdater.apply_action(game_state=state, action=action)
            # OLD behavior: full scan.
            off = compute_window_offset(new_state, window_size)
            board = Board(state=new_state, total_tiles=board.total_tiles, offset=off)
        except Exception:
            break
    return board


def bench_get_next_state(seqs, window_size, reps):
    inc_t = scan_t = 0.0
    n_trans = sum(len(s) for _, s in seqs) * reps
    for _ in range(reps):
        t0 = time.perf_counter()
        for seed, seq in seqs:
            replay_incremental(seed, seq, window_size)
        inc_t += time.perf_counter() - t0
        t0 = time.perf_counter()
        for seed, seq in seqs:
            replay_fullscan(seed, seq, window_size)
        scan_t += time.perf_counter() - t0
    return inc_t, scan_t, n_trans


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--window-size", type=int, default=25)
    args = ap.parse_args(argv)

    print(f"harvesting {args.games} games (window={args.window_size})...")
    states = harvest_states(args.games, args.window_size, args.seed)
    seqs = harvest_action_sequences(args.games, args.window_size, args.seed)
    print(f"  {len(states)} board states, {sum(len(s) for _, s in seqs)} transitions")

    inc_t, scan_t, n = bench_per_call(states, args.window_size, args.reps)
    print("\n[1] per-call offset computation (interleaved A/B):")
    print(f"  incremental: {inc_t / n * 1e6:8.3f} us/call")
    print(f"  full scan:   {scan_t / n * 1e6:8.3f} us/call")
    print(f"  speedup:     {scan_t / inc_t:6.2f}x")

    inc_g, scan_g, nt = bench_get_next_state(seqs, args.window_size, args.reps)
    print("\n[2] whole get_next_state (interleaved A/B):")
    print(f"  incremental: {inc_g / nt * 1e6:8.3f} us/transition")
    print(f"  full scan:   {scan_g / nt * 1e6:8.3f} us/transition")
    print(f"  speedup:     {scan_g / inc_g:6.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
