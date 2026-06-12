#!/usr/bin/env python3
"""Interleaved A/B bench: Python flat leaf vs the Cython port.

Same harness shape as /tmp/profile_leaf.py (realistic random-play snapshots at
production knobs), but A/B-interleaved in alternating full-pass blocks so
background load (the box runs a production flywheel) cancels out of the RATIO.
Absolute per-leaf numbers are load-contaminated; the ratio is the result.

Usage (production knobs):
  CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 \
    nice -n 19 python scripts/bench_cy_leaf.py --games 30 --blocks 8
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import flat_leaf_cy  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--snap-every", type=int, default=12)
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--blocks", type=int, default=8, help="A/B block pairs")
    args = ap.parse_args()

    print(f"collecting {args.games} games of snapshots...", flush=True)
    states = collect(args.games, args.snap_every, args.seed)
    n = len(states)
    print(f"got {n} two-player states; {args.blocks} interleaved block-pairs "
          f"of {n} evals each side", flush=True)
    cfg = DEFAULT_CONFIG
    print(f"cfg: closure_p={cfg.closure_p} cap={cfg.bonus_cap}")

    py = flat_leaf.flat_virtual_score_v2
    cy = flat_leaf_cy.flat_virtual_score_v2_cy

    # warmup (touch tile-feature caches on both sides) + sanity
    for s in states[:20]:
        if py(s, 0, cfg) != cy(s, 0, cfg):
            print("MISMATCH during warmup — bench aborted; run reconcile_cy_leaf.py")
            return 1

    t_py, t_cy = [], []
    for blk in range(args.blocks):
        t0 = time.perf_counter()
        for s in states:
            py(s, 0, cfg)
        t1 = time.perf_counter()
        for s in states:
            cy(s, 0, cfg)
        t2 = time.perf_counter()
        t_py.append((t1 - t0) / n * 1e6)
        t_cy.append((t2 - t1) / n * 1e6)
        print(f"  block {blk + 1}/{args.blocks}: py={t_py[-1]:8.1f} us/leaf  "
              f"cy={t_cy[-1]:8.1f} us/leaf  ratio={t_py[-1] / t_cy[-1]:.2f}x", flush=True)

    med_py = statistics.median(t_py)
    med_cy = statistics.median(t_cy)
    ratios = sorted(p / c for p, c in zip(t_py, t_cy))
    print("\n=== bench_cy_leaf summary ===")
    print(f"evals per side          : {args.blocks * n}")
    print(f"python flat leaf (median): {med_py:.1f} us/leaf  (min {min(t_py):.1f})")
    print(f"cython port      (median): {med_cy:.1f} us/leaf  (min {min(t_cy):.1f})")
    print(f"speedup (median-of-block ratios): {statistics.median(ratios):.2f}x "
          f"(range {ratios[0]:.2f}-{ratios[-1]:.2f})")
    print("NOTE: absolute numbers are contaminated by background load; the "
          "interleaved ratio is the result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
