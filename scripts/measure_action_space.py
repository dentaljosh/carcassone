"""Empirically measure the legal-action distribution at every move of N random
games to inform Phase 1's action-space encoding decision.

Outputs:
  - data/measurements/action_space.csv (per-decision count of legal actions)
  - prints distribution summary

If max legal actions exceed ~500, the flat-softmax-with-mask plan should be
re-evaluated against factored-policy heads.

Action-space size also drives Dirichlet noise alpha — rule of thumb is
alpha ≈ 10 / mean_legal_moves.

Run:  python scripts/measure_action_space.py [n_games]
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


def _play_one(seed: int) -> list[tuple[int, int, int]]:
    """Play a random game; return list of (seed, move_idx, n_actions) per move."""
    random.seed(seed)
    game = CarcassonneGame(
        players=2,
        tile_sets=[TileSet.BASE, TileSet.THE_RIVER],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    out: list[tuple[int, int, int]] = []
    move_idx = 0
    while not game.is_finished():
        actions = game.get_possible_actions()
        out.append((seed, move_idx, len(actions)))
        if not actions:
            break
        game.step(game.get_current_player(), random.choice(actions))
        move_idx += 1
    return out


def percentile(sorted_xs: list[int], p: float) -> int:
    if not sorted_xs:
        return 0
    idx = max(0, min(len(sorted_xs) - 1, int(round((p / 100.0) * (len(sorted_xs) - 1)))))
    return sorted_xs[idx]


def main() -> int:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "action_space_random.csv"

    # Worker count: full logical-core fan-out. See scripts/bench_workers.py —
    # 16 SMT threads beats 8 physical on this workload by ~28% (Python-bound
    # enough that SMT siblings don't contend much on the shared ALU/cache).
    n_workers = min(os.cpu_count() or 1, n_games)
    print(f"  using {n_workers} worker processes")
    with Pool(processes=n_workers) as pool:
        per_game_rows = pool.map(_play_one, range(n_games))

    counts: list[int] = []
    rows: list[tuple[int, int, int]] = []
    for game_rows in per_game_rows:
        for s, m, n in game_rows:
            counts.append(n)
            rows.append((s, m, n))

    with out_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["seed", "move_idx", "n_actions"])
        writer.writerows(rows)

    counts_sorted = sorted(counts)
    mean = sum(counts) / len(counts)

    print(f"Action-space measurement: {n_games} random games, {len(counts)} decisions")
    print(f"Tile sets: BASE + THE_RIVER  Supplementary: FARMERS  Players: 2")
    print(
        f"  legal actions per decision: "
        f"min={counts_sorted[0]} "
        f"mean={mean:.1f} "
        f"p50={percentile(counts_sorted, 50)} "
        f"p90={percentile(counts_sorted, 90)} "
        f"p99={percentile(counts_sorted, 99)} "
        f"max={counts_sorted[-1]}"
    )
    print(f"\nCSV: {out_path}")

    p99 = percentile(counts_sorted, 99)
    if p99 > 500:
        verdict = (
            f"⚠ p99={p99} > 500 — plan calls for flat softmax with mask; reconsider "
            f"factored policy heads (position / rotation / meeple) before Phase 3."
        )
    else:
        verdict = f"flat-action-space plan is safe (p99={p99} ≤ 500)."
    print(f"\nVerdict: {verdict}")

    suggested_alpha = 10.0 / max(mean, 1.0)
    print(
        f"Dirichlet noise alpha rule-of-thumb (10 / mean_legal_moves): "
        f"alpha ≈ {suggested_alpha:.3f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
