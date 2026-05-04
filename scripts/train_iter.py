"""Train one Phase 4 iteration's network on the current replay buffer.

Inputs:
  - Last K iterations of self-play games (`data/selfplay/<run>/iter_*/*.npz`)
  - Optionally a fraction of warmstart positions mixed in
    (`data/warmstart/heuristic_tau05/*.npz`)
  - The previous iteration's checkpoint as the warm-start

Output:
  - Numbered checkpoint at `checkpoints/selfplay/iter_NN.pt` (kept forever
    for Phase 6 emergence analysis)
  - Sibling `checkpoints/selfplay/iter_NN.metrics.json` with per-epoch
    train/val pol/val losses + the warmstart-mix fraction used.

The iter-0 case warms from `checkpoints/warmstart_canonical.pt`; iter > 0
warms from `checkpoints/selfplay/iter_(NN-1).pt`.

Usage:
  python -u scripts/train_iter.py \\
      --output-root data/selfplay/calibration \\
      --warmstart-root data/warmstart/heuristic_tau05 \\
      --iter 0 \\
      --warmstart-mix-fraction 1.0 \\
      --warm-from checkpoints/warmstart_canonical.pt \\
      --output checkpoints/selfplay/iter_00.pt \\
      --epochs 3
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.warmstart import (
    GameDataset,
    count_positions,
    iter_game_dataset_files,
    make_streaming_dataset,
    split_files_train_val,
)

# Reuse the same masked-policy CE used by warmstart training.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_warmstart import policy_cross_entropy  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent


def _select_buffer_files(
    output_root: Path, current_iter: int, window: int
) -> list[Path]:
    """Last `window` iterations' .npz files, oldest → newest. Includes
    iters [max(0, current_iter - window + 1), current_iter]."""
    lo = max(0, current_iter - window + 1)
    files: list[Path] = []
    for i in range(lo, current_iter + 1):
        d = output_root / f"iter_{i:02d}"
        if not d.exists():
            continue
        files.extend(sorted(d.glob("seed_*.npz")))
    return files


def _build_mixed_file_list(
    buffer_files: list[Path],
    warmstart_files: list[Path],
    warmstart_mix_fraction: float,
    seed: int,
) -> list[Path]:
    """Return a file list whose effective sampling rate matches the target
    warmstart_mix_fraction, defined as the fraction of training samples
    drawn from warmstart files vs. buffer files.

    Approach: epochs sample uniformly across files in the returned list,
    so we just need the warmstart-vs-buffer file *count ratio* to match
    the desired sample fraction. Concretely:

      n_warmstart_in_list / n_total = warmstart_mix_fraction

    Sample (with replacement) from `warmstart_files` to hit that count.
    Edge cases:
      - mix == 0 → just return buffer_files
      - mix == 1 → just return all warmstart_files
      - buffer empty → return all warmstart_files
    """
    if warmstart_mix_fraction <= 0.0:
        return list(buffer_files)
    if not buffer_files or warmstart_mix_fraction >= 1.0:
        return list(warmstart_files)

    n_buffer = len(buffer_files)
    # n_warmstart_in_list / (n_warmstart_in_list + n_buffer) = mix
    # → n_warmstart_in_list = mix * n_buffer / (1 - mix)
    n_warmstart_in_list = int(round(
        warmstart_mix_fraction * n_buffer / (1.0 - warmstart_mix_fraction)
    ))
    n_warmstart_in_list = max(0, min(n_warmstart_in_list, len(warmstart_files) * 50))
    rng = random.Random(seed)
    sampled = rng.choices(warmstart_files, k=n_warmstart_in_list) if n_warmstart_in_list > 0 else []
    return list(buffer_files) + sampled


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="train_iter")
    p.add_argument("--output-root", type=Path, required=True,
                   help="Root containing iter_NN/ subdirs of self-play games.")
    p.add_argument("--warmstart-root", type=Path,
                   default=REPO_ROOT / "data" / "warmstart" / "heuristic_tau05",
                   help="Warmstart .npz dir for the optional mix-in.")
    p.add_argument("--iter", type=int, required=True, dest="iter_idx")
    p.add_argument("--window", type=int, default=10,
                   help="Replay-buffer window: last K iters' games (default 10).")
    p.add_argument("--warmstart-mix-fraction", type=float, default=0.0,
                   help="Fraction of training samples from the warmstart "
                        "dataset (rest from self-play buffer). Plan: 1.0 "
                        "at iter 0, 0.7 at iter 1, 0.4 at iter 2, 0.0 from iter 3.")
    p.add_argument("--warm-from", type=Path, required=True,
                   help="Checkpoint to initialize the network from.")
    p.add_argument("--output", type=Path, required=True,
                   help="Output checkpoint path (e.g. checkpoints/selfplay/iter_00.pt).")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--val-fraction", type=float, default=0.05)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    buffer_files = _select_buffer_files(args.output_root, args.iter_idx, args.window)
    warmstart_files = (
        sorted(args.warmstart_root.glob("seed_*.npz"))
        if args.warmstart_root.exists() else []
    )
    file_list = _build_mixed_file_list(
        buffer_files, warmstart_files, args.warmstart_mix_fraction, args.seed
    )
    if not file_list:
        print("ERROR: no training files found (buffer empty + no warmstart mix)",
              file=sys.stderr)
        return 1

    train_files, val_files = split_files_train_val(
        file_list, val_fraction=args.val_fraction, seed=args.seed
    )
    do_validation = len(val_files) > 0
    n_train = count_positions(train_files)
    n_val = count_positions(val_files) if do_validation else 0

    print(
        f"iter={args.iter_idx}: buffer_files={len(buffer_files)}, "
        f"warmstart_in_list={len(file_list) - len(buffer_files)}, "
        f"file_list_total={len(file_list)} → "
        f"train {len(train_files)} files ({n_train} positions), "
        f"val {len(val_files)} files ({n_val} positions)"
    )
    sys.stdout.flush()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  device: {device}")

    train_ds = make_streaming_dataset(
        train_files,
        shuffle_files_each_epoch=True,
        shuffle_within_file=True,
        seed=args.seed,
    )
    if do_validation:
        val_ds = make_streaming_dataset(
            val_files,
            shuffle_files_each_epoch=False,
            shuffle_within_file=False,
            seed=args.seed,
        )

    # Workers > 0 needs persistent_workers=False to let set_epoch propagate.
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        persistent_workers=False,
        pin_memory=(device.type == "cuda"),
    )
    val_loader = (
        DataLoader(
            val_ds,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            persistent_workers=(args.num_workers > 0),
            pin_memory=(device.type == "cuda"),
        )
        if do_validation else None
    )

    # Load warm-from checkpoint to grab architecture params.
    ckpt = torch.load(args.warm_from, map_location=device, weights_only=False)
    n_filters = int(ckpt["n_filters"])
    n_blocks = int(ckpt["n_blocks"])
    net = CarcassonneNet(n_filters=n_filters, n_blocks=n_blocks).to(device)
    net.load_state_dict(ckpt["model_state"])
    print(f"  warm-started from {args.warm_from} "
          f"(filters={n_filters}, blocks={n_blocks}, "
          f"params={net.param_count():,})")

    optim = torch.optim.AdamW(
        net.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )

    metrics = {
        "iter": args.iter_idx,
        "warm_from": str(args.warm_from),
        "warmstart_mix_fraction": args.warmstart_mix_fraction,
        "buffer_files": len(buffer_files),
        "warmstart_in_list": len(file_list) - len(buffer_files),
        "n_train_positions": n_train,
        "n_val_positions": n_val,
        "epochs": [],
    }

    for epoch in range(args.epochs):
        train_ds.set_epoch(epoch)
        net.train(True)
        t0 = time.perf_counter()
        train_pol_loss = 0.0
        train_val_loss = 0.0
        n_batches = 0
        nan_skipped = 0
        for board_b, scalar_b, policy_b, value_b, mask_b in train_loader:
            board_b = board_b.to(device, non_blocking=True)
            scalar_b = scalar_b.to(device, non_blocking=True)
            policy_b = policy_b.to(device, non_blocking=True)
            value_b = value_b.to(device, non_blocking=True)
            mask_b = mask_b.to(device, non_blocking=True)
            policy_logits, value_pred = net(board_b, scalar_b)
            pol_loss = policy_cross_entropy(policy_logits, policy_b, mask_b)
            val_loss = F.mse_loss(value_pred, value_b)
            loss = pol_loss + val_loss
            if not torch.isfinite(loss):
                nan_skipped += 1
                continue
            optim.zero_grad(set_to_none=True)
            loss.backward()
            optim.step()
            train_pol_loss += pol_loss.item()
            train_val_loss += val_loss.item()
            n_batches += 1
        if nan_skipped:
            print(f"  [warn] skipped {nan_skipped} NaN-loss batch(es) this epoch")
        train_pol_loss /= max(n_batches, 1)
        train_val_loss /= max(n_batches, 1)

        if do_validation:
            net.train(False)
            val_pol_loss = 0.0
            val_val_loss = 0.0
            v_n = 0
            with torch.no_grad():
                for board_b, scalar_b, policy_b, value_b, mask_b in val_loader:
                    board_b = board_b.to(device, non_blocking=True)
                    scalar_b = scalar_b.to(device, non_blocking=True)
                    policy_b = policy_b.to(device, non_blocking=True)
                    value_b = value_b.to(device, non_blocking=True)
                    mask_b = mask_b.to(device, non_blocking=True)
                    policy_logits, value_pred = net(board_b, scalar_b)
                    val_pol_loss += policy_cross_entropy(policy_logits, policy_b, mask_b).item()
                    val_val_loss += F.mse_loss(value_pred, value_b).item()
                    v_n += 1
            val_pol_loss /= max(v_n, 1)
            val_val_loss /= max(v_n, 1)
        else:
            val_pol_loss = float("nan")
            val_val_loss = float("nan")

        elapsed = time.perf_counter() - t0
        epoch_metric = {
            "epoch": epoch + 1,
            "n_batches": n_batches,
            "wallclock_sec": round(elapsed, 1),
            "train_pol_loss": round(train_pol_loss, 4),
            "train_val_loss": round(train_val_loss, 4),
            "val_pol_loss": round(val_pol_loss, 4) if do_validation else None,
            "val_val_loss": round(val_val_loss, 4) if do_validation else None,
        }
        metrics["epochs"].append(epoch_metric)
        if do_validation:
            print(
                f"  epoch {epoch+1:2d}/{args.epochs} ({elapsed:.1f}s, {n_batches} batches)  "
                f"train pol/val={train_pol_loss:.3f}/{train_val_loss:.4f}  "
                f"val pol/val={val_pol_loss:.3f}/{val_val_loss:.4f}"
            )
        else:
            print(
                f"  epoch {epoch+1:2d}/{args.epochs} ({elapsed:.1f}s, {n_batches} batches)  "
                f"train pol/val={train_pol_loss:.3f}/{train_val_loss:.4f}  (no val)"
            )
        sys.stdout.flush()

    torch.save(
        {
            "model_state": net.state_dict(),
            "n_filters": n_filters,
            "n_blocks": n_blocks,
            "iter": args.iter_idx,
            "epochs": args.epochs,
        },
        args.output,
    )
    metrics_path = args.output.with_suffix(".metrics.json")
    with metrics_path.open("w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"\nSaved {args.output} (+ {metrics_path.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
