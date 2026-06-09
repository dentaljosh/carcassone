#!/usr/bin/env python3
"""Phase-4 step 1: relative per-leaf micro-bench + profile of the compact leaf.

No pause / no quiet box needed. Measures the RELATIVE per-leaf cost of compact-ON
(pure-Python flat union-find) vs compact-OFF (lazy object-BFS) back-to-back in
ONE process, so CPU contention from the flywheel hits both equally (we report the
min over reps, the least-interrupted run, and a ratio — both robust to a busy
box). Then profiles WHERE the compact build spends its time so we know whether
compiling the union-find core (`_label_components`) is worth it, or whether the
enumeration/reconstruction (engine-object work numba can't touch) dominates and
must be de-objectified first.

Read-only; run with nice -n 19. NOT a throughput bench (that needs a quiet box).

Usage:
  PYTHONPATH=.../src:.../engine CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \
    nice -n 19 python scripts/microbench_compact_leaf.py --n 40 --reps 5
"""
from __future__ import annotations

import argparse
import cProfile
import pstats
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import compact_leaf  # noqa: E402
from carcassonne_ai import virtual_score as _vs  # noqa: E402
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


def time_leaf(states, reps: int) -> float:
    """Min total wallclock over `reps` of one full leaf pass (both players)."""
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        for s in states:
            for p in range(2):
                virtual_score_v2(s, p, DEFAULT_CONFIG)
        best = min(best, time.perf_counter() - t)
    return best


def time_builds(states, reps: int) -> float:
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        for s in states:
            compact_leaf.build_farm_cache(s)
            compact_leaf.build_city_cache(s)
        best = min(best, time.perf_counter() - t)
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="games to play for state collection")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--seed", type=int, default=777)
    a = ap.parse_args()

    states = collect(a.n, 5, a.seed)
    nleaf = len(states) * 2
    print(f"{len(states)} states, {nleaf} leaf evals/rep, reps={a.reps} (min-of-reps)")

    # warm caches/JITs of nothing, just touch code paths
    _vs.USE_COMPACT_LEAF = False
    time_leaf(states[:3], 1)
    off = time_leaf(states, a.reps)
    _vs.USE_COMPACT_LEAF = True
    time_leaf(states[:3], 1)
    on = time_leaf(states, a.reps)
    _vs.USE_COMPACT_LEAF = False

    print("\n=== per-leaf wallclock (min of reps; lower = better) ===")
    print(f"  OFF (lazy object-BFS) : {off * 1e3 / nleaf:.4f} ms/leaf  (total {off:.3f}s)")
    print(f"  ON  (pure-Py compact) : {on * 1e3 / nleaf:.4f} ms/leaf  (total {on:.3f}s)")
    verdict = "compact FASTER" if on < off else "compact SLOWER"
    print(f"  ratio ON/OFF = {on / off:.2f}x   -> {verdict}")

    # Isolated cost of the two whole-board builds (what compact ADDS per leaf,
    # though it removes the lazy BFS work in return).
    bt = time_builds(states, a.reps)
    print(f"\n  build_farm_cache+build_city_cache only: {bt * 1e3 / len(states):.4f} ms/state "
          f"({bt * 1e3 / nleaf:.4f} ms/leaf-equiv)")

    # Profile WHERE the build spends time: union-find core vs enumeration vs
    # reconstruction. Decides numba-the-core (if _label_components dominates) vs
    # de-objectify-first (if enumeration/reconstruction dominate).
    print("\n=== cProfile: build_farm_cache + build_city_cache over states (cumulative) ===")
    pr = cProfile.Profile()
    pr.enable()
    for s in states:
        compact_leaf.build_farm_cache(s)
        compact_leaf.build_city_cache(s)
    pr.disable()
    st = pstats.Stats(pr, stream=sys.stdout)
    st.sort_stats("tottime")
    st.print_stats(18)

    # Explicit: fraction of build self-time inside the pure-int union-find core.
    total = 0.0
    core = 0.0
    sd = st.stats  # {(file,line,name): (cc, nc, tt, ct, callers)}
    for (file, line, name), val in sd.items():
        tt = val[2]
        total += tt
        if name == "_label_components":
            core = tt
    if total > 0:
        print(f"\n  union-find core (_label_components) self-time: {100 * core / total:.1f}% of build self-time")
        print("  -> if this is small, compiling JUST the core won't help much; "
              "the enumeration/reconstruction (engine-object work) must be de-objectified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
