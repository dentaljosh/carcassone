"""Production warm-start trainer — streaming/IterableDataset, scales to 500K+.

Difference vs. train_warmstart_smoke.py:
- Uses warmstart.make_streaming_dataset, which lazy-loads one .npz file at a
  time instead of pre-loading the whole dataset into RAM. 500K positions ≈
  ~60 GB raw — does not fit in 31 GB system RAM.
- Train/val split is by FILE (== by GAME, since one .npz = one game), so
  positions never leak between train and val.
- Default network: 6 ResBlocks × 96 filters (production capacity).
- Per-epoch progress logged to stdout; checkpoints every epoch + best-by-val.

Usage:
  python -u scripts/train_warmstart.py \\
    --data-root data/warmstart/heuristic \\
    --epochs 20 \\
    --output checkpoints/warmstart_heuristic_prod.pt
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.warmstart import (
    count_positions,
    iter_game_dataset_files,
    make_streaming_dataset,
    split_files_train_val,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def policy_cross_entropy(
    logits: torch.Tensor, target: torch.Tensor, mask: torch.Tensor
) -> torch.Tensor:
    """Soft cross-entropy: -sum(target * log_softmax(logits)) over valid actions.
    Mask invalid logits to -inf before log_softmax. Rows that are all-invalid
    have nan log_probs but zero target rows, so we replace nans with zero to
    keep the per-row sum well-defined.

    Validates inputs to fail loud on malformed data: target mass on invalid
    actions, target rows that don't sum to ~1 on legal positions, or
    all-invalid rows (which silently contribute zero loss). Reviewer flagged
    that the previous version silently absorbed garbage.
    """
    mask_b = mask.bool()
    if (target * (~mask_b)).abs().sum() > 1e-5:
        raise ValueError(
            "policy target has mass on invalid (masked-off) actions"
        )
    has_legal = mask_b.any(dim=-1)
    if not has_legal.all():
        # All-invalid rows would silently contribute zero loss. The data
        # generator should never produce these; if it does, surface it.
        raise ValueError(
            f"{(~has_legal).sum().item()}/{has_legal.numel()} target rows "
            "have no legal action — bad sample slipped through generation"
        )
    legal_sums = target.sum(dim=-1)
    if not torch.allclose(legal_sums, torch.ones_like(legal_sums), atol=1e-3):
        raise ValueError(
            f"policy target rows must sum to ~1 over legal actions, got "
            f"min={legal_sums.min().item():.4f} max={legal_sums.max().item():.4f}"
        )
    masked = logits.masked_fill(~mask_b, float("-inf"))
    log_probs = F.log_softmax(masked, dim=-1)
    log_probs = torch.where(torch.isfinite(log_probs), log_probs, torch.zeros_like(log_probs))
    return -(target * log_probs).sum(dim=-1).mean()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="train_warmstart")
    p.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Directory of seed_*.npz files (e.g. data/warmstart/heuristic).",
    )
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--filters", type=int, default=96)
    p.add_argument("--blocks", type=int, default=6)
    p.add_argument("--val-fraction", type=float, default=0.05)
    p.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="DataLoader worker processes for streaming. 0 means main-thread only.",
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    files = list(iter_game_dataset_files(args.data_root))
    if not files:
        raise SystemExit(
            f"No .npz files found at {args.data_root}. "
            "Run scripts/generate_warmstart_smoke.py (or its prod equivalent) first."
        )
    train_files, val_files = split_files_train_val(
        files, val_fraction=args.val_fraction, seed=args.seed
    )

    n_train = count_positions(train_files)
    n_val = count_positions(val_files)
    print(
        f"Loaded {len(files)} game files ({n_train + n_val} positions). "
        f"Split: {len(train_files)} train ({n_train} pos), "
        f"{len(val_files)} val ({n_val} pos)."
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  device: {device}")

    train_ds = make_streaming_dataset(
        train_files,
        shuffle_files_each_epoch=True,
        shuffle_within_file=True,
        seed=args.seed,
    )
    val_ds = make_streaming_dataset(
        val_files,
        shuffle_files_each_epoch=False,
        shuffle_within_file=False,
        seed=args.seed,
    )
    # persistent_workers=False on train_loader: workers cache the dataset
    # snapshot at construction, so train_ds.set_epoch(...) on the main thread
    # never reaches them and per-epoch file shuffling silently sticks at
    # epoch 0. Recreating workers per epoch costs ~Pool-startup-time which
    # is negligible vs. one full pass through the data.
    # val_loader can use persistent_workers — set_epoch is not relevant
    # there (val files have a fixed deterministic order).
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
        persistent_workers=False,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        num_workers=min(args.num_workers, 2),
        pin_memory=(device.type == "cuda"),
        persistent_workers=(args.num_workers > 0),
    )

    net = CarcassonneNet(n_filters=args.filters, n_blocks=args.blocks).to(device)
    print(f"  net params: {net.param_count():,}  (filters={args.filters}, blocks={args.blocks})")

    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    # ceil so we don't underestimate batch count and let the cosine schedule
    # finish ahead of the actual training tail. With multi-worker streaming
    # there can also be one partial batch per worker, so add a small fudge.
    steps_per_epoch = max(1, -(-n_train // args.batch_size) + max(1, args.num_workers))
    total_steps = steps_per_epoch * args.epochs
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=total_steps)

    best_val = math.inf
    best_path = args.output.with_suffix(".best.pt")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(args.epochs):
        train_ds.set_epoch(epoch)
        net.train()
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
            opt.zero_grad()
            policy_logits, value_pred = net(board_b, scalar_b)
            pol_loss = policy_cross_entropy(policy_logits, policy_b, mask_b)
            val_loss = F.mse_loss(value_pred, value_b)
            loss = pol_loss + val_loss
            if not torch.isfinite(loss):
                nan_skipped += 1
                continue  # skip the step; weights stay clean
            loss.backward()
            opt.step()
            scheduler.step()
            train_pol_loss += pol_loss.item()
            train_val_loss += val_loss.item()
            n_batches += 1
        if nan_skipped:
            print(f"  [warn] skipped {nan_skipped} NaN-loss batch(es) this epoch")
        train_pol_loss /= max(n_batches, 1)
        train_val_loss /= max(n_batches, 1)

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
        val_total = val_pol_loss + val_val_loss

        elapsed = time.perf_counter() - t0
        print(
            f"  epoch {epoch+1:2d}/{args.epochs} ({elapsed:.1f}s, {n_batches} batches)  "
            f"train pol/val={train_pol_loss:.3f}/{train_val_loss:.4f}  "
            f"val pol/val={val_pol_loss:.3f}/{val_val_loss:.4f}"
        )
        sys.stdout.flush()

        if val_total < best_val:
            best_val = val_total
            torch.save(
                {
                    "model_state": net.state_dict(),
                    "n_filters": args.filters,
                    "n_blocks": args.blocks,
                    "epoch": epoch,
                    "val_pol_loss": val_pol_loss,
                    "val_val_loss": val_val_loss,
                    "data_root": str(args.data_root),
                },
                best_path,
            )

    torch.save(
        {
            "model_state": net.state_dict(),
            "n_filters": args.filters,
            "n_blocks": args.blocks,
            "data_root": str(args.data_root),
        },
        args.output,
    )
    print(f"\nSaved final checkpoint: {args.output}")
    print(f"Saved best (by val loss) checkpoint: {best_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
