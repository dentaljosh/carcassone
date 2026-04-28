"""Empirically measure the score-differential distribution to validate
the value-head normalization scale `tanh(diff / D)`.

The right D puts ~90% of games in the non-saturated range [-0.9, +0.9],
leaving headroom for blowouts.

Sources of game data:
  --source random    Play random-vs-random games via the engine (default).
                     Seeds: 0..n-1 (or --seed-start..--seed-start+n-1).
  --source csv       Load score differentials from a pre-collected CSV.
                     Used after Phase 3 to re-validate D against trained-bot
                     self-play games. Provide --csv path/to/file.csv with at
                     least a `diff` column (or `score_p0`,`score_p1`).

This script is intentionally reusable: re-run after Phase 3 warm-start once
network self-play games are produced (those will have a tighter
distribution than random; D will likely shift down to /10).

Run examples:
  python scripts/measure_reward_distribution.py
  python scripts/measure_reward_distribution.py --n 500
  python scripts/measure_reward_distribution.py --source csv --csv data/measurements/phase3_selfplay.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

from wingedsheep.carcassonne.carcassonne_game import CarcassonneGame
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "measurements"


def _random_final_diff(seed: int) -> tuple[int, int, int, int]:
    """Play one random game, return (seed, score_p0, score_p1, diff)."""
    random.seed(seed)
    game = CarcassonneGame(
        players=2,
        tile_sets=[TileSet.BASE, TileSet.THE_RIVER],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    while not game.is_finished():
        actions = game.get_possible_actions()
        if not actions:
            break
        game.step(game.get_current_player(), random.choice(actions))
    s0, s1 = game.state.scores
    return seed, s0, s1, s0 - s1


def collect_random(n_games: int, seed_start: int = 0) -> list[tuple[int, int, int, int]]:
    n_workers = min(os.cpu_count() or 1, n_games)

    import time as _time
    _t0 = _time.perf_counter()
    _random_final_diff(seed_start)
    per_game = _time.perf_counter() - _t0
    eta = (n_games * per_game) / n_workers
    m, s = divmod(eta, 60)
    print(f"  [ETA] {n_games} games × {per_game * 1000:.0f}ms ≈ {int(m)}m{int(s):02d}s on {n_workers} workers")

    with Pool(processes=n_workers) as pool:
        rows = pool.map(_random_final_diff, range(seed_start, seed_start + n_games))
    return rows


def collect_csv(csv_path: Path) -> list[tuple[int, int, int, int]]:
    """Load (seed, score_p0, score_p1, diff) rows from a CSV.

    Accepts either:
      - columns 'seed','score_p0','score_p1','diff' (preferred)
      - columns 'score_p0','score_p1' (diff computed)
      - column 'diff' alone (seed/scores filled with -1)
    """
    rows: list[tuple[int, int, int, int]] = []
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            if "diff" in r and r["diff"] != "":
                d = int(r["diff"])
                p0 = int(r.get("score_p0") or -1)
                p1 = int(r.get("score_p1") or -1)
                seed = int(r.get("seed") or -1)
            elif "score_p0" in r and "score_p1" in r:
                p0 = int(r["score_p0"])
                p1 = int(r["score_p1"])
                d = p0 - p1
                seed = int(r.get("seed") or -1)
            else:
                raise ValueError(f"unrecognized CSV columns: {list(r.keys())}")
            rows.append((seed, p0, p1, d))
    if not rows:
        raise ValueError(f"no rows loaded from {csv_path}")
    print(f"  loaded {len(rows)} rows from {csv_path}")
    return rows


def percentile(sorted_xs: list[int], p: float) -> float:
    if not sorted_xs:
        return 0.0
    idx = max(0, min(len(sorted_xs) - 1, int(round((p / 100.0) * (len(sorted_xs) - 1)))))
    return float(sorted_xs[idx])


def report(rows: list[tuple[int, int, int, int]], label: str, out_csv: Path | None) -> None:
    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["seed", "score_p0", "score_p1", "diff"])
            w.writerows(rows)
        print(f"\n  → wrote {out_csv}")

    diffs = sorted(d for _s, _a, _b, d in rows)
    abs_diffs = sorted(abs(d) for d in diffs)

    print(f"\nReward distribution: {label} ({len(rows)} games)")
    print(
        f"  diff (signed):       min={diffs[0]} p1={percentile(diffs, 1):.0f} "
        f"p5={percentile(diffs, 5):.0f} p25={percentile(diffs, 25):.0f} "
        f"p50={percentile(diffs, 50):.0f} p75={percentile(diffs, 75):.0f} "
        f"p95={percentile(diffs, 95):.0f} p99={percentile(diffs, 99):.0f} "
        f"max={diffs[-1]}"
    )
    print(
        f"  |diff|:              min={abs_diffs[0]} mean={sum(abs_diffs) / len(abs_diffs):.1f} "
        f"p50={percentile(abs_diffs, 50):.0f} p90={percentile(abs_diffs, 90):.0f} "
        f"p95={percentile(abs_diffs, 95):.0f} p99={percentile(abs_diffs, 99):.0f} "
        f"max={abs_diffs[-1]}"
    )

    print(f"\n  D       in [-0.9, +0.9]   |y|>=0.99 (saturated)")
    for D in (8, 10, 12, 15, 20, 25, 30, 40):
        non_sat = sum(1 for d in diffs if abs(math.tanh(d / D)) <= 0.9) / len(diffs)
        sat = sum(1 for d in diffs if abs(math.tanh(d / D)) >= 0.99) / len(diffs)
        flag = "  ←" if 0.85 <= non_sat <= 0.95 else ""
        print(f"  /{D:<5d}  {non_sat:>6.1%}             {sat:>6.1%}{flag}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="measure_reward_distribution")
    p.add_argument("--source", choices=("random", "csv"), default="random",
                   help="random self-play (default) or load existing CSV")
    p.add_argument("--n", type=int, default=1000, help="games for --source random")
    p.add_argument("--seed-start", type=int, default=0, help="first seed for random play")
    p.add_argument("--csv", type=Path, default=None, help="input CSV for --source csv")
    p.add_argument("--out", type=Path, default=None,
                   help="output CSV path (default: data/measurements/reward_distribution_<source>.csv)")
    p.add_argument("--label", type=str, default=None, help="label for the report header")
    args = p.parse_args(argv)

    if args.source == "random":
        rows = collect_random(args.n, seed_start=args.seed_start)
        out = args.out or (OUT_DIR / "reward_distribution_random.csv")
        label = args.label or "random self-play"
    else:
        if args.csv is None:
            p.error("--source csv requires --csv path/to/file.csv")
        rows = collect_csv(args.csv)
        out = args.out  # don't auto-overwrite when reading external data
        label = args.label or args.csv.stem

    report(rows, label=label, out_csv=out)
    print("\nCAVEAT: random-play differentials are wider than trained-bot")
    print("        differentials. Re-run with --source csv after Phase 3 to update D.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
