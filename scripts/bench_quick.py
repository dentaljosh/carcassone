"""Quick benchmark suite: measures per-operation costs so the ETA for any
upcoming long-running job can be estimated in seconds.

Run:  python scripts/bench_quick.py

Outputs a single table with:
  - random self-play per game (1-worker baseline)
  - random self-play per game (multiprocessing Pool, full SMT fan-out)
  - get_valid_moves per call
  - get_canonical_form per call (board+scalar tensor build)
  - string_representation per call
  - torch matmul GPU sanity (proves GPU is alive and gives a flops baseline)

Numbers are printed in microseconds (μs) per call, plus a derived "ETA for X
games on N workers" cheat-sheet for the most common batch sizes.
"""
from __future__ import annotations

import os
import random
import sys
import time
from multiprocessing import Pool

import numpy as np

from carcassonne_ai.game_wrapper import (
    Game,
    _play_one_random_game,
    _self_play_random,
)


def _bench_call(label: str, fn, n: int) -> tuple[str, float, float]:
    """Time `fn` called n times. Returns (label, total_seconds, us_per_call)."""
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    elapsed = time.perf_counter() - t0
    return label, elapsed, (elapsed / n) * 1e6


def bench_per_call_ops(n: int = 200) -> list[tuple[str, float, float]]:
    """Time the small operations once we've reached a populated mid-game state."""
    g = Game()
    random.seed(0)
    board = g.get_init_board()
    # Step ~40 moves in to hit a representative mid-game state.
    for _ in range(40):
        if g.get_game_ended(board, 0) != 0.0:
            break
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))

    rows = []
    rows.append(_bench_call("get_valid_moves", lambda: g.get_valid_moves(board), n))
    rows.append(_bench_call("get_canonical_form", lambda: g.get_canonical_form(board, 0), n))
    rows.append(_bench_call("string_representation", lambda: g.string_representation(board), n))
    return rows


def bench_self_play(n_games_serial: int = 4, n_games_pool: int = 32) -> list[tuple[str, float, float]]:
    rows = []
    cpu = os.cpu_count() or 1

    # Serial baseline.
    t0 = time.perf_counter()
    for s in range(n_games_serial):
        _play_one_random_game((s, 25))
    serial_total = time.perf_counter() - t0
    rows.append(("self-play 1 game (serial)", serial_total / n_games_serial, (serial_total / n_games_serial) * 1e6))

    # Pool throughput.
    t0 = time.perf_counter()
    with Pool(processes=cpu) as pool:
        pool.map(_play_one_random_game, [(1000 + s, 25) for s in range(n_games_pool)])
    pool_total = time.perf_counter() - t0
    rows.append((f"self-play 1 game (Pool x{cpu})", pool_total / n_games_pool, (pool_total / n_games_pool) * 1e6))
    return rows


def bench_gpu() -> tuple[str, float, str]:
    """Sanity-check GPU: time a 4096x4096 fp16 matmul. Returns (label, sec, note)."""
    try:
        import torch
    except ImportError:
        return "GPU matmul (torch not installed)", float("nan"), "skipped"
    if not torch.cuda.is_available():
        return "GPU matmul (CUDA unavailable)", float("nan"), "skipped"
    dev = torch.device("cuda")
    a = torch.randn(4096, 4096, device=dev, dtype=torch.float16)
    b = torch.randn(4096, 4096, device=dev, dtype=torch.float16)
    # Warmup
    for _ in range(3):
        (a @ b).sum()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    iters = 20
    for _ in range(iters):
        (a @ b).sum()
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters
    flops = 2 * 4096 ** 3 / elapsed / 1e12  # TFLOPS
    return "GPU 4096^2 fp16 matmul", elapsed, f"{flops:.1f} TFLOPS effective"


def main() -> int:
    print("Carcassonne quick bench")
    print("=" * 70)

    print("\n[1] Per-call wrapper ops (mid-game state, n=200 each)")
    for label, total, us in bench_per_call_ops(n=200):
        print(f"  {label:30s}  {us:>10.1f} μs/call    ({total:.3f}s total)")

    print("\n[2] Random self-play throughput")
    rows = bench_self_play(n_games_serial=4, n_games_pool=32)
    serial_per_game = rows[0][1]
    pool_per_game = rows[1][1]
    cpu = os.cpu_count() or 1
    speedup = serial_per_game / pool_per_game if pool_per_game > 0 else 0
    for label, sec, _us in rows:
        print(f"  {label:30s}  {sec:>10.3f} s/game")
    print(f"  → speedup x{speedup:.2f} on {cpu} workers")

    print("\n[3] GPU sanity")
    label, sec, note = bench_gpu()
    if sec == sec:  # not NaN
        print(f"  {label:30s}  {sec * 1000:>9.2f} ms/iter   {note}")
    else:
        print(f"  {label:30s}  {note}")

    print("\n[4] ETA cheat-sheet (random self-play, Pool of all cores)")
    for n in (100, 500, 1000, 5000):
        eta_s = n * pool_per_game
        m, s = divmod(eta_s, 60)
        print(f"  {n:>5d} games  ≈  {int(m)}m{int(s):02d}s  ({eta_s:.1f}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
