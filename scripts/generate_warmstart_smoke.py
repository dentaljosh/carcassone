"""Generate labeled positions for the Phase 3 warm-start smoke comparison.

Usage:
  python -u scripts/generate_warmstart_smoke.py --label-strategy mcts --n 5000 --positions-per-game 10
  python -u scripts/generate_warmstart_smoke.py --label-strategy heuristic --n 5000 --positions-per-game 10
  python scripts/generate_warmstart_smoke.py --summary-only --label-strategy mcts

Output: data/warmstart/<strategy>/seed_<NNNNN>.npz, one per game.
Resumable: skips seeds whose .npz already exists.

For 5000 positions at 10 positions/game: 500 games per strategy.
ETA per game:
  heuristic: ~20-30 sec (10 × ~2 sec virtual_score-style 1-ply lookahead)
  mcts s=50: ~6-9 min (10 × ~30-50 sec MCTS at s=50, mid-game)

With 16-worker Pool, 500 games is:
  heuristic: ~10 min
  mcts s=50: ~3-5 hours
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from carcassonne_ai.warmstart import (
    GameDataset,
    generate_one_game_dataset,
    iter_game_dataset_files,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "warmstart"


def _seed_path(subdir: str, seed: int) -> Path:
    return DATA_ROOT / subdir / f"seed_{seed:05d}.npz"


def _worker(args: tuple[int, str, str, int, int, float, str, bool]) -> tuple[int, str, int]:
    """One-game worker. Returns (seed, status, n_positions)."""
    (seed, strategy, subdir, n_positions, mcts_sims, heuristic_tau,
     heuristic_lookahead, include_farm_scalars) = args
    path = _seed_path(subdir, seed)
    if path.exists():
        try:
            ds = GameDataset.load(path)
            return seed, "cached", len(ds)
        except Exception:
            path.unlink(missing_ok=True)
    ds = generate_one_game_dataset(
        seed=seed,
        label_strategy=strategy,
        n_positions_per_game=n_positions,
        mcts_sims=mcts_sims,
        heuristic_tau=heuristic_tau,
        heuristic_lookahead=heuristic_lookahead,
        include_farm_scalars=include_farm_scalars,
    )
    ds.save(path)
    return seed, "fresh", len(ds)


def _summarize(subdir: str) -> int:
    root = DATA_ROOT / subdir
    if not root.exists():
        print(f"No data at {root}")
        return 0
    files = list(iter_game_dataset_files(root))
    if not files:
        print(f"No files in {root}")
        return 0
    total_positions = 0
    for f in files:
        try:
            ds = GameDataset.load(f)
            total_positions += len(ds)
        except Exception as exc:
            print(f"  {f.name}: load failed: {exc}")
    print(f"subdir={subdir}: {len(files)} games, {total_positions} positions in {root}")
    return total_positions


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="generate_warmstart_smoke")
    p.add_argument("--label-strategy", choices=("mcts", "heuristic"), required=True)
    p.add_argument(
        "--include-farm-scalars",
        action="store_true",
        help="Path B Step E: emit 12-scalar feature vectors (10 base + 2 farm-control) "
        "in the generated data. Pair with train_warmstart --include-farm-scalars.",
    )
    p.add_argument("--n", type=int, default=5000, help="target total positions")
    p.add_argument("--positions-per-game", type=int, default=10)
    p.add_argument("--mcts-sims", type=int, default=50, help="MCTS sims/move when strategy=mcts")
    p.add_argument(
        "--heuristic-tau",
        type=float,
        default=10.0,
        help="Softmax temperature for heuristic policy targets. Lower = sharper. "
             "Default 10.0 produces top-1 mass ~45%; try 5.0 if the policy head is undertrained.",
    )
    p.add_argument(
        "--heuristic-lookahead",
        choices=("1ply", "2ply"),
        default="1ply",
        help="Lookahead depth for heuristic policy. 1ply (default) scores each "
             "tile-phase action by virtual_score after applying just the tile. "
             "2ply applies the tile, enumerates meeple/skip follow-ups, and "
             "uses the BEST follow-up score — captures joint tile+meeple "
             "value. ~3-4x slower gen.",
    )
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--reset", action="store_true",
                   help="Wipe the output subdir before starting")
    p.add_argument("--summary-only", action="store_true",
                   help="Just report what's on disk")
    p.add_argument(
        "--output-subdir",
        type=str,
        default=None,
        help="Subdir under data/warmstart/ to write to. Default = label-strategy name. "
             "Use to keep ablation runs (e.g. heuristic_tau05) separate from the main run.",
    )
    args = p.parse_args(argv)

    subdir = args.output_subdir or args.label_strategy

    if args.summary_only:
        _summarize(subdir)
        return 0

    if args.reset:
        target = DATA_ROOT / subdir
        if target.exists():
            shutil.rmtree(target)
            print(f"Wiped {target}")

    n_games = (args.n + args.positions_per_game - 1) // args.positions_per_game
    n_workers = args.workers or min(os.cpu_count() or 1, n_games)

    pool_args = [
        (args.seed_start + i, args.label_strategy, subdir,
         args.positions_per_game, args.mcts_sims, args.heuristic_tau,
         args.heuristic_lookahead, args.include_farm_scalars)
        for i in range(n_games)
    ]
    already = sum(1 for a in pool_args if _seed_path(subdir, a[0]).exists())
    remaining = n_games - already
    print(
        f"warmstart/{subdir}: {n_games} games "
        f"({args.positions_per_game} pos/game = {n_games * args.positions_per_game} positions), "
        f"strategy={args.label_strategy}, tau={args.heuristic_tau}, "
        f"lookahead={args.heuristic_lookahead}, "
        f"{n_workers} workers, {already} cached, {remaining} to play"
    )

    t0 = time.perf_counter()
    completed = 0
    fresh = 0
    cached = 0
    first_fresh_t: float | None = None

    with Pool(processes=n_workers) as pool:
        for (seed, status, n_positions) in pool.imap_unordered(_worker, pool_args, chunksize=1):
            completed += 1
            if status == "fresh":
                fresh += 1
                if first_fresh_t is None:
                    first_fresh_t = time.perf_counter()
                    elapsed = first_fresh_t - t0
                    print(f"  [ETA] first fresh game took {elapsed:.0f}s; "
                          f"~{(remaining * elapsed / n_workers / 60):.1f} min for {remaining} fresh")
                    sys.stdout.flush()
            else:
                cached += 1
            if completed % max(1, n_games // 20) == 0 or completed == n_games:
                print(f"  ... {completed}/{n_games} games done (fresh={fresh}, cached={cached})")
                sys.stdout.flush()

    total_positions = _summarize(subdir)
    print(f"\nDone. {completed} games processed, {total_positions} total positions on disk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
