"""Benchmark optimal worker count for parallel random-game simulation on this
host. Runs a fixed workload (default 64 games) with varying pool sizes and
reports wall-clock + per-game throughput.

Helps decide the cap for measure_*.py scripts (and later, self-play workers).
On AMD 5800X (8C/16T) we expect the curve to plateau around 8 (physical core
count) and degrade past that as SMT siblings contend for ALU/cache.

Run:  python scripts/bench_workers.py [n_games_per_run]
"""
from __future__ import annotations

import os
import random
import sys
import time
from multiprocessing import Pool

from wingedsheep.carcassonne.carcassonne_game import CarcassonneGame
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet


def play_one(seed: int) -> int:
    random.seed(seed)
    game = CarcassonneGame(
        players=2,
        tile_sets=[TileSet.BASE, TileSet.THE_RIVER],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    moves = 0
    while not game.is_finished():
        actions = game.get_possible_actions()
        if not actions:
            break
        game.step(game.get_current_player(), random.choice(actions))
        moves += 1
    return moves


def bench(n_workers: int, n_games: int, seed_base: int = 0) -> float:
    seeds = list(range(seed_base, seed_base + n_games))
    t0 = time.perf_counter()
    if n_workers == 1:
        for s in seeds:
            play_one(s)
    else:
        with Pool(processes=n_workers) as pool:
            list(pool.imap_unordered(play_one, seeds, chunksize=max(1, n_games // (n_workers * 4))))
    return time.perf_counter() - t0


def main() -> int:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    cpu = os.cpu_count() or 8
    # Ladder hits 1, half-physical, physical, 2x physical (full SMT).
    candidates = sorted({1, 2, 4, max(1, cpu // 2), max(1, cpu // 2) - 1, max(1, cpu // 2) + 1, cpu, cpu // 2 * 3, max(1, cpu - 2)})
    candidates = [c for c in candidates if 1 <= c <= cpu]

    print(f"Worker-count benchmark: {n_games} random games per run, cpu_count={cpu}")
    print("(first run is a warmup and is discarded)")
    print()

    # Warmup with a small pool to load engine modules into cache
    bench(n_workers=2, n_games=min(8, n_games), seed_base=0)

    print(f"  {'workers':>8s}  {'wall (s)':>10s}  {'games/s':>9s}  {'speedup':>8s}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*9}  {'-'*8}")
    base = None
    seed_offset = 100
    for w in candidates:
        t = bench(n_workers=w, n_games=n_games, seed_base=seed_offset)
        seed_offset += n_games  # avoid identical seeds across runs (page cache)
        rate = n_games / t
        if base is None:
            base = t
        speedup = base / t
        print(f"  {w:>8d}  {t:>10.2f}  {rate:>9.2f}  {speedup:>7.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
