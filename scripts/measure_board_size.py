"""Empirically measure the bounding box of placed tiles across N random games
to inform Phase 1's board-representation window size.

Outputs:
  - data/measurements/board_size.csv (per-game width/height)
  - prints percentile summary

The prompt's recommendation is a 31x31 window; this script gives us evidence
to confirm or shrink that. We expect random play to undershoot real-game
spread (MCTS-driven games tend to sprawl more) — the MCTS-portion measurement
will be added in Phase 2 and may push the empirical 99th-pct higher.

Run:  python scripts/measure_board_size.py [n_games]
"""
from __future__ import annotations

import csv
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


def bbox_of_placed(state) -> tuple[int, int, int]:
    """Return (width, height, n_tiles) of the placed-tile bounding box."""
    rows, cols = [], []
    n = 0
    for r, row in enumerate(state.board):
        for c, tile in enumerate(row):
            if tile is not None:
                rows.append(r)
                cols.append(c)
                n += 1
    if not rows:
        return 0, 0, 0
    return (max(cols) - min(cols) + 1, max(rows) - min(rows) + 1, n)


def play_one(seed: int) -> tuple[int, int, int, int]:
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
    w, h, n = bbox_of_placed(game.state)
    return seed, w, h, n


def percentile(sorted_xs: list[int], p: float) -> int:
    if not sorted_xs:
        return 0
    idx = max(0, min(len(sorted_xs) - 1, int(round((p / 100.0) * (len(sorted_xs) - 1)))))
    return sorted_xs[idx]


def main() -> int:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "board_size_random.csv"

    # Worker count: full logical-core fan-out. Empirically (scripts/bench_workers.py)
    # 16 SMT threads beats 8 physical (~6.9x vs ~5.4x speedup) on this workload —
    # the engine spends enough time in pure-Python overhead that SMT siblings
    # don't bottleneck on shared ALU/cache.
    # See scripts/bench_workers.py — full SMT fan-out wins on this workload.
    n_workers = min(os.cpu_count() or 1, n_games)
    print(f"  using {n_workers} worker processes")

    # Sample a single run to print an ETA before fanning out.
    import time as _time
    _t0 = _time.perf_counter()
    play_one(0)
    _per_game = _time.perf_counter() - _t0
    _eta = (n_games * _per_game) / n_workers
    _m, _s = divmod(_eta, 60)
    print(f"  [ETA] {n_games} games × {_per_game * 1000:.0f}ms ≈ {int(_m)}m{int(_s):02d}s on {n_workers} workers")

    with Pool(processes=n_workers) as pool:
        rows = pool.map(play_one, range(n_games))

    widths = [w for _, w, _, _ in rows]
    heights = [h for _, _, h, _ in rows]
    longests = [max(w, h) for _, w, h, _ in rows]

    with out_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["seed", "bbox_width", "bbox_height", "tiles_placed"])
        writer.writerows(rows)

    widths.sort()
    heights.sort()
    longests.sort()

    def summary(name: str, xs: list[int]) -> None:
        print(
            f"  {name:8s}: "
            f"min={xs[0]} "
            f"p50={percentile(xs, 50)} "
            f"p90={percentile(xs, 90)} "
            f"p95={percentile(xs, 95)} "
            f"p99={percentile(xs, 99)} "
            f"max={xs[-1]}"
        )

    print(f"Board-size measurement: {n_games} random games")
    print(f"Tile sets: BASE + THE_RIVER  Supplementary: FARMERS  Players: 2")
    summary("width", widths)
    summary("height", heights)
    summary("longest", longests)
    print(f"\nCSV: {out_path}")

    p99 = percentile(longests, 99)
    suggested = p99 + 4
    if suggested % 2 == 0:
        suggested += 1
    print(
        f"\nSuggested window size: {suggested}x{suggested} "
        f"(longest p99={p99} + 4 tile margin, rounded to next odd integer)"
    )
    print("NOTE: random play undershoots real spread; redo with MCTS games in Phase 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
