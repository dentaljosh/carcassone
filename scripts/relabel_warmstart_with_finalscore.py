"""Relabel warmstart positions with game-final-score value targets.

Hypothesis under test: virtual_score-at-position-N (a snapshot evaluation of
"who would win if the game ended right now") is a poor proxy for actual
final-score-differential when N is mid-late game with substantial
development remaining. The value head is being trained on a target that
systematically misses the long-horizon endgame component (farmer fields
merging, cities completing, fields-fragility).

Plausible fix: replace the value target with the game's actual final score
differential — same tanh(diff/15) normalization, just measured at game-end
instead of at-position. Policy targets, board encodings, scalars, and
masks all stay the same; only `values` changes.

Determinism: the existing dataset was generated with `random.seed(seed)` +
`random.Random(seed+1)` for action choices, so replaying the same seed
deterministically reproduces the same game (and the same `chosen` position
indices via `rng.sample`). We replay each seed, record per-chosen-position
player, play the game to terminal, run `count_final_scores`, and emit
the new value target per position.

Two modes:

  --check N     Replay N games (10 positions each); print Pearson
                correlation between virtual_score-target and
                final-score-target; do NOT write any output. Use this to
                gate whether the experiment is worth running.

  (default)     Replay all seeds in the input dir, write new .npz files
                to the output dir with identical boards/scalars/policies/
                masks but final-score-derived values. Pool-parallel.

Usage:
  python -u scripts/relabel_warmstart_with_finalscore.py --check 100
  python -u scripts/relabel_warmstart_with_finalscore.py \\
      --input-subdir heuristic_tau05 \\
      --output-subdir heuristic_tau05_finalscore
"""
from __future__ import annotations

import argparse
import math
import os
import random
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.warmstart import (
    GameDataset,
    SCORE_NORM_SCALE_FOR_LABELS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "warmstart"

_SEED_RE = re.compile(r"seed_(\d+)\.npz$")


def _seed_from_path(p: Path) -> int:
    m = _SEED_RE.search(p.name)
    if not m:
        raise ValueError(f"Cannot parse seed from {p.name}")
    return int(m.group(1))


def _replay_game(seed: int, n_positions_per_game: int = 10,
                 skip_early: int = 10, skip_late: int = 10):
    """Replay a random-play game with the same seeding the original
    generator used. Returns (chosen_positions, final_score_diff_p0).

    `chosen_positions` is a list of (idx, current_player) tuples — one per
    chosen position, in the same order the original dataset emitted them.
    """
    random.seed(seed)
    rng = random.Random(seed + 1)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    snapshots: list[int] = []  # current_player at each step
    while game.get_game_ended(board, 0) == 0.0:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        snapshots.append(board.state.current_player)
        board, _ = game.get_next_state(board, int(rng.choice(legal)))

    n_total = len(snapshots)
    eligible_lo = skip_early
    eligible_hi = max(skip_early + 1, n_total - skip_late)
    if eligible_hi <= eligible_lo:
        eligible_indices = list(range(n_total))
    else:
        eligible_indices = list(range(eligible_lo, eligible_hi))

    if len(eligible_indices) <= n_positions_per_game:
        chosen_idx = eligible_indices
    else:
        chosen_idx = sorted(rng.sample(eligible_indices, n_positions_per_game))

    # Final-score differential from player-0 perspective.
    # Game has already been played to terminal (or until no legal moves);
    # `count_final_scores` is invoked by the engine via state_updater on
    # game termination, so state.scores already reflects final.
    final_p0 = int(board.state.scores[0]) - int(board.state.scores[1])

    chosen = [(idx, snapshots[idx]) for idx in chosen_idx]
    return chosen, final_p0


def _check_one_seed(seed: int) -> list[tuple[float, float]] | None:
    """For one seed, return list of (virtual_score_target, final_score_target)
    per chosen position. Loads the existing .npz to get the
    virtual-score-derived value the original generator wrote.
    """
    src = DATA_ROOT / "heuristic_tau05" / f"seed_{seed:05d}.npz"
    if not src.exists():
        return None
    with np.load(src) as data:
        existing_values = data["values"].astype(np.float32).copy()
    chosen, final_p0 = _replay_game(seed)
    if len(chosen) != len(existing_values):
        # Skip if replay determinism is off (shouldn't happen, but guard).
        return None
    pairs: list[tuple[float, float]] = []
    for (idx, player), virt_value in zip(chosen, existing_values):
        diff = final_p0 if player == 0 else -final_p0
        final_value = math.tanh(diff / SCORE_NORM_SCALE_FOR_LABELS)
        pairs.append((float(virt_value), float(final_value)))
    return pairs


def _relabel_one_seed(args: tuple[int, str, str]) -> tuple[int, str]:
    """Worker: read input .npz, recompute values from game-final-score,
    write to output dir. Returns (seed, status)."""
    seed, in_subdir, out_subdir = args
    src = DATA_ROOT / in_subdir / f"seed_{seed:05d}.npz"
    dst = DATA_ROOT / out_subdir / f"seed_{seed:05d}.npz"
    if dst.exists():
        return seed, "cached"
    if not src.exists():
        return seed, "missing"

    ds = GameDataset.load(src)
    chosen, final_p0 = _replay_game(seed)
    if len(chosen) != len(ds):
        return seed, f"length-mismatch (replay={len(chosen)}, file={len(ds)})"

    new_values = np.empty(len(ds), dtype=np.float32)
    for i, (_, player) in enumerate(chosen):
        diff = final_p0 if player == 0 else -final_p0
        new_values[i] = math.tanh(diff / SCORE_NORM_SCALE_FOR_LABELS)

    new_ds = GameDataset(
        boards=ds.boards,
        scalars=ds.scalars,
        policies=ds.policies,
        values=new_values,
        valid_masks=ds.valid_masks,
        ownership=ds.ownership,  # carry ownership labels through the relabel
    )
    new_ds.save(dst)
    return seed, "fresh"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="relabel_warmstart_with_finalscore")
    p.add_argument("--input-subdir", default="heuristic_tau05",
                   help="Source dataset under data/warmstart/.")
    p.add_argument("--output-subdir", default="heuristic_tau05_finalscore",
                   help="Destination dataset under data/warmstart/.")
    p.add_argument("--check", type=int, default=None,
                   help="Correlation-check mode: replay N games, print "
                        "Pearson correlation between virtual_score and "
                        "final-score value targets, write nothing.")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--max-games", type=int, default=None,
                   help="Cap number of games processed (smoke testing).")
    args = p.parse_args(argv)

    in_root = DATA_ROOT / args.input_subdir
    if not in_root.exists():
        print(f"input dir does not exist: {in_root}", file=sys.stderr)
        return 1

    files = sorted(in_root.glob("seed_*.npz"))
    if not files:
        print(f"no seed_*.npz files in {in_root}", file=sys.stderr)
        return 1
    seeds = [_seed_from_path(f) for f in files]

    if args.check is not None:
        n = min(args.check, len(seeds))
        sample_seeds = seeds[:n]
        n_workers = args.workers or min(n, os.cpu_count() or 1)
        print(f"Correlation check: {n} games (~{n*10} positions), {n_workers} workers")
        sys.stdout.flush()
        all_pairs: list[tuple[float, float]] = []
        with Pool(processes=n_workers) as pool:
            for i, pairs in enumerate(pool.imap_unordered(_check_one_seed, sample_seeds, chunksize=4), 1):
                if pairs:
                    all_pairs.extend(pairs)
                if i % max(1, n // 10) == 0:
                    print(f"  ... {i}/{n} games processed")
                    sys.stdout.flush()
        if not all_pairs:
            print("No data collected.", file=sys.stderr)
            return 1
        xs = np.array([a for a, _ in all_pairs], dtype=np.float64)
        ys = np.array([b for _, b in all_pairs], dtype=np.float64)
        mx = xs.mean()
        my = ys.mean()
        sx = xs.std()
        sy = ys.std()
        if sx > 0 and sy > 0:
            corr = float(np.mean((xs - mx) * (ys - my)) / (sx * sy))
        else:
            corr = float("nan")
        # Aggregate stats so the user can sanity-check.
        diffs = ys - xs
        print()
        print(f"=== Correlation check ({len(all_pairs)} positions, {n} games) ===")
        print(f"Pearson r(virtual_target, final_target): {corr:.4f}")
        print(f"  virtual_target  mean={mx:+.4f} std={sx:.4f} min={xs.min():+.3f} max={xs.max():+.3f}")
        print(f"  final_target    mean={my:+.4f} std={sy:.4f} min={ys.min():+.3f} max={ys.max():+.3f}")
        print(f"  per-position diff (final - virtual)  mean={diffs.mean():+.4f}  abs-mean={np.abs(diffs).mean():.4f}  max-abs={np.abs(diffs).max():.4f}")
        print()
        if corr >= 0.85:
            print(f"r={corr:.4f} >= 0.85 → targets agree closely; relabel unlikely to change network behavior.")
        else:
            print(f"r={corr:.4f} < 0.85 → targets disagree meaningfully; relabel experiment is worth running.")
        return 0

    # Full relabel.
    if args.max_games is not None:
        seeds = seeds[: args.max_games]
    out_root = DATA_ROOT / args.output_subdir
    out_root.mkdir(parents=True, exist_ok=True)
    n_workers = args.workers or min(len(seeds), os.cpu_count() or 1)
    pool_args = [(s, args.input_subdir, args.output_subdir) for s in seeds]
    print(f"Relabel: {len(seeds)} games {args.input_subdir} → {args.output_subdir}, {n_workers} workers")
    sys.stdout.flush()
    fresh = cached = missing = errors = 0
    with Pool(processes=n_workers) as pool:
        for i, (seed, status) in enumerate(pool.imap_unordered(_relabel_one_seed, pool_args, chunksize=4), 1):
            if status == "fresh":
                fresh += 1
            elif status == "cached":
                cached += 1
            elif status == "missing":
                missing += 1
            else:
                errors += 1
                print(f"  seed={seed}: {status}", file=sys.stderr)
            if i % max(1, len(seeds) // 20) == 0:
                print(f"  ... {i}/{len(seeds)} (fresh={fresh}, cached={cached}, missing={missing}, errors={errors})")
                sys.stdout.flush()
    print(f"\nDone. fresh={fresh}, cached={cached}, missing={missing}, errors={errors}")
    print(f"Output: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
