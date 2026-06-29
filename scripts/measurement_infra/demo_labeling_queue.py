#!/usr/bin/env python3
"""Demo / smoke for the adaptive labeling queue. Builds an h200-tagged candidate pool from a games
file, samples the four strata, emits a queue jsonl, and prints a summary. Net-free, frozen v2.9 leaf.

Usage: python demo_labeling_queue.py [--games ...] [--candidates-per-game 8] [--n-per-stratum 300]
"""
from __future__ import annotations
import os
for _k, _v in {"CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
               "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
               "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
               "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_USE_FLAT_LEAF": "1",
               "CARCASSONNE_USE_CY_REPR": "1", "CARCASSONNE_V25_VALUE_BLEND": "0",
               "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
    os.environ[_k] = _v

import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import snapshot as SNAP                              # noqa: E402
from labeling_queue import AdaptiveLabelingQueue     # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", default=str(HERE.parents[1] / "measurement" /
                                           "post_search_residual" / "data" / "games_mcts.jsonl"))
    ap.add_argument("--candidates-per-game", type=int, default=8)
    ap.add_argument("--n-per-stratum", type=int, default=300)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--tau", type=float, default=0.02)
    ap.add_argument("--out", default=str(HERE.parents[1] / "measurement" /
                                         "post_search_residual" / "data" / "labeling_queue_demo.jsonl"))
    args = ap.parse_args()
    t0 = time.time()

    cfg = SNAP.frozen_v29_cfg()
    q = AdaptiveLabelingQueue.from_games(args.games, cfg, sims=200,
                                         candidates_per_game=args.candidates_per_game,
                                         workers=args.workers)
    print(f"[queue] built in {time.time()-t0:.0f}s · summary:")
    print("  " + json.dumps(q.summary(), indent=2).replace("\n", "\n  "))

    n = args.n_per_stratum
    strata = {
        "ordinary": q.sample("ordinary", n),
        "low_top2gap": q.sample("low_top2gap", n, tau=args.tau),
        "opening_heavy": q.sample("opening_heavy", n),
        "close_score": q.sample("close_score", n, margin=3),
    }
    for name, rows in strata.items():
        if rows:
            import numpy as np
            gaps = np.array([r["top2_q_gap"] for r in rows])
            mar = np.array([abs(r["score_margin"]) for r in rows])
            from collections import Counter
            ph = dict(Counter(r["phase"] for r in rows))
            print(f"  {name:14s} n={len(rows):4d}  median top2gap={np.median(gaps):.4f}  "
                  f"median |margin|={np.median(mar):.0f}  phases={ph}")
        else:
            print(f"  {name:14s} n=0")

    n_unique = q.emit(args.out, strata)
    print(f"[emit] {n_unique} unique roots -> {args.out}  ({time.time()-t0:.0f}s total)")


if __name__ == "__main__":
    main()
