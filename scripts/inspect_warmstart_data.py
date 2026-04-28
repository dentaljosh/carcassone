"""Quick diagnostic tool — summarize a warmstart .npz directory.

Reports per-channel activation, value distribution, policy concentration,
and legal-action distribution. Use to sanity-check freshly-generated data
before kicking off training.

Usage:
  python scripts/inspect_warmstart_data.py data/warmstart/heuristic
  python scripts/inspect_warmstart_data.py data/warmstart/heuristic --max-files 30
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.warmstart import GameDataset, iter_game_dataset_files


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="inspect_warmstart_data")
    p.add_argument("data_dir", type=Path)
    p.add_argument("--max-files", type=int, default=100,
                   help="Sample at most this many files (whole dataset can be huge)")
    args = p.parse_args(argv)

    if not args.data_dir.is_dir():
        print(f"Not a directory: {args.data_dir}", file=sys.stderr)
        return 1

    files = list(iter_game_dataset_files(args.data_dir))
    if not files:
        print(f"No .npz files in {args.data_dir}")
        return 1
    print(f"Found {len(files)} files in {args.data_dir}; sampling first {min(len(files), args.max_files)}.")

    sample_files = files[: args.max_files]
    boards_chunks: list[np.ndarray] = []
    scalars_chunks: list[np.ndarray] = []
    policies_chunks: list[np.ndarray] = []
    values_chunks: list[np.ndarray] = []
    masks_chunks: list[np.ndarray] = []
    for f in sample_files:
        ds = GameDataset.load(f)
        if len(ds) == 0:
            continue
        boards_chunks.append(ds.boards)
        scalars_chunks.append(ds.scalars)
        policies_chunks.append(ds.policies)
        values_chunks.append(ds.values)
        masks_chunks.append(ds.valid_masks)
    if not boards_chunks:
        print("No positions in any sampled file.")
        return 1

    boards = np.concatenate(boards_chunks)
    scalars = np.concatenate(scalars_chunks)
    policies = np.concatenate(policies_chunks)
    values = np.concatenate(values_chunks)
    masks = np.concatenate(masks_chunks)

    n = len(boards)
    print(f"\n--- {n} positions sampled ---")
    print(f"boards: {boards.shape} dtype={boards.dtype}")
    print(f"scalars: {scalars.shape} dtype={scalars.dtype}")
    print(f"policies: {policies.shape} dtype={policies.dtype}")
    print(f"values: {values.shape} dtype={values.dtype}")
    print(f"masks: {masks.shape} dtype={masks.dtype}")

    print("\n--- value distribution ---")
    print(f"  mean={values.mean():.3f}, std={values.std():.3f}, min={values.min():.3f}, max={values.max():.3f}")
    print(f"  fraction near zero (|v|<0.1): {(np.abs(values) < 0.1).mean():.2%}")
    print(f"  fraction near saturation (|v|>0.9): {(np.abs(values) > 0.9).mean():.2%}")

    print("\n--- scalar feature ranges ---")
    for i, name in enumerate(
        ["meeple_mine", "meeple_opp", "score_mine", "score_opp", "score_diff",
         "tiles_left", "cur_player", "phase_tiles", "phase_meeples", "progress"]
    ):
        col = scalars[:, i]
        print(f"  [{i}] {name:14s}  min={col.min():+.3f}  mean={col.mean():+.3f}  max={col.max():+.3f}")

    print("\n--- policy concentration ---")
    n_legal = masks.sum(axis=1)
    print(f"  n_legal: mean={n_legal.mean():.1f}, p50={np.median(n_legal):.0f}, p99={np.percentile(n_legal, 99):.0f}")
    sorted_probs = np.sort(policies, axis=1)[:, ::-1]
    print(f"  top-1 prob (mean across positions): {sorted_probs[:, 0].mean():.3f}")
    print(f"  top-3 cumulative mass: {sorted_probs[:, :3].sum(axis=1).mean():.3f}")
    print(f"  top-5 cumulative mass: {sorted_probs[:, :5].sum(axis=1).mean():.3f}")
    uni = 1.0 / n_legal.clip(min=1)
    print(f"  top-1 / uniform ratio: {(sorted_probs[:, 0] / uni).mean():.2f}x  (1.0 = perfectly uniform)")

    print("\n--- per-channel activation summary (78 ch expected) ---")
    if boards.shape[1] != N_CHANNELS:
        print(f"  WARNING: board has {boards.shape[1]} channels; expected {N_CHANNELS}")
    ch_means = boards.mean(axis=(0, 2, 3))
    ranges = [
        ("edges (T,R,B,L) x4 cat", 0, 16),
        ("tile_present", 16, 17),
        ("shield", 17, 18),
        ("chapel/flowers", 18, 19),
        ("internal road pairs", 19, 25),
        ("internal city pairs", 25, 31),
        ("normal meeple mine (5 sides)", 31, 36),
        ("normal meeple opp (5 sides)", 36, 41),
        ("farmer mine (4 corners)", 41, 45),
        ("farmer opp (4 corners)", 45, 49),
        ("ref tile edges", 49, 65),
        ("ref tile internal", 65, 77),
        ("last tile pos", 77, 78),
    ]
    for name, lo, hi in ranges:
        block = ch_means[lo:hi]
        print(f"  ch[{lo:>2d},{hi:>2d}) {name:30s} mean={block.mean():.5f}, max={block.max():.5f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
