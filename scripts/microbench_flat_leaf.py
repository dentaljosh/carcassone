#!/usr/bin/env python3
"""Relative per-leaf micro-bench: flat leaf vs the production v2.7 leaf.

NOT a throughput bench (that needs a quiet box — Stage 5). This measures the
RELATIVE per-leaf cost of `flat_virtual_score_v2` (de-objectified, canonical sum)
vs `virtual_score_v2` (production: deepcopy + count_final_scores + object-BFS
closure bonus) back-to-back in ONE process, min-of-reps, so flywheel contention
hits both equally. Answers: did de-objectifying beat the compact attempt's 1.10x
REGRESSION, i.e. is flat already faster INTERPRETED (before Stage 4 compile)?

Run with nice -n 19.

Usage:
  PYTHONPATH=.../src:.../engine CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \
    nice -n 19 python scripts/microbench_flat_leaf.py --n 40 --reps 5
"""
from __future__ import annotations

import argparse
import cProfile
import os
import pstats
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2  # noqa: E402


def collect(n_games: int, snap_every: int, seed: int):
    g = Game()
    states = []
    for gi in range(n_games):
        random.seed(seed + gi)
        b = g.get_init_board()
        p = 0
        while g.get_game_ended(b, 0) == 0.0 and p < 400:
            legal = np.flatnonzero(g.get_valid_moves(b))
            if legal.size == 0:
                break
            b, _ = g.get_next_state(b, int(random.choice(legal.tolist())))
            p += 1
            if p % snap_every == 0 and g.get_game_ended(b, 0) == 0.0:
                states.append(b.state)
        states.append(b.state)
    return [s for s in states if s.players == 2]


def time_fn(fn, states, reps: int) -> float:
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        for s in states:
            for p in range(2):
                fn(s, p, DEFAULT_CONFIG)
        best = min(best, time.perf_counter() - t)
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--seed", type=int, default=777)
    a = ap.parse_args()

    states = collect(a.n, 5, a.seed)
    nleaf = len(states) * 2
    print(f"{len(states)} states, {nleaf} leaf evals/rep, reps={a.reps} (min-of-reps)")

    # warm
    time_fn(virtual_score_v2, states[:3], 1)
    time_fn(flat_leaf.flat_virtual_score_v2, states[:3], 1)

    off = time_fn(virtual_score_v2, states, a.reps)
    flat = time_fn(flat_leaf.flat_virtual_score_v2, states, a.reps)

    print("\n=== per-leaf wallclock (min of reps; lower = better) ===")
    print(f"  OFF  (deepcopy+count_final_scores) : {off * 1e3 / nleaf:.4f} ms/leaf  (total {off:.3f}s)")
    print(f"  FLAT (de-objectified)              : {flat * 1e3 / nleaf:.4f} ms/leaf  (total {flat:.3f}s)")
    verdict = "FLAT faster" if flat < off else "FLAT SLOWER"
    print(f"  ratio FLAT/OFF = {flat / off:.3f}x   -> {verdict}  (speedup {off / flat:.2f}x)")

    # Where does flat spend its time? (decompose vs scoring). Guides Stage 4.
    print("\n=== cProfile: flat_virtual_score_v2 (by self-time) ===")
    pr = cProfile.Profile()
    pr.enable()
    for s in states:
        flat_leaf.flat_virtual_score_v2(s, 0, DEFAULT_CONFIG)
        flat_leaf.flat_virtual_score_v2(s, 1, DEFAULT_CONFIG)
    pr.disable()
    st = pstats.Stats(pr, stream=sys.stdout)
    st.sort_stats("tottime")
    st.print_stats(16)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
