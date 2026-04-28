"""Train the small warm-start network on a labeled dataset.

Usage:
  python -u scripts/train_warmstart_smoke.py --strategy mcts --epochs 20 --output checkpoints/warmstart_mcts_smoke.pt
  python -u scripts/train_warmstart_smoke.py --strategy heuristic --epochs 20 --output checkpoints/warmstart_heuristic_smoke.pt

For the smoke comparison, default config:
  - 4-block by 64-filter network (smaller than the eventual 6 by 96; faster to train)
  - 20 epochs over the dataset
  - AdamW, lr=1e-3, weight_decay=1e-4
  - 90/10 train/val split by game (not by position) so games don't leak
  - cross-entropy on policy + MSE on value, equal weight

This is a SMOKE training script, not the production warm-start trainer.
The production trainer will use the full 6 by 96 network and a more careful
LR schedule.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.warmstart import GameDataset, iter_game_dataset_files


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_all(strategy: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[int]]:
    root = REPO_ROOT / "data" / "warmstart" / strategy
    files = list(iter_game_dataset_files(root))
    if not files:
        raise SystemExit(f"No data found at {root}. Run generate_warmstart_smoke.py first.")
    boards_chunks = []
    scalars_chunks = []
    policies_chunks = []
    values_chunks = []
    masks_chunks = []
    game_starts: list[int] = []  # for game-level train/val split
    cursor = 0
    for f in files:
        ds = GameDataset.load(f)
        if len(ds) == 0:
            continue
        game_starts.append(cursor)
        cursor += len(ds)
        boards_chunks.append(ds.boards)
        scalars_chunks.append(ds.scalars)
        policies_chunks.append(ds.policies)
        values_chunks.append(ds.values)
        masks_chunks.append(ds.valid_masks)
    boards = np.concatenate(boards_chunks, axis=0)
    scalars = np.concatenate(scalars_chunks, axis=0)
    policies = np.concatenate(policies_chunks, axis=0)
    values = np.concatenate(values_chunks, axis=0)
    masks = np.concatenate(masks_chunks, axis=0)
    return boards, scalars, policies, values, masks, game_starts


def split_by_game(n_total: int, game_starts: list[int], val_fraction: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Split positions into train/val by GAME (so games don't leak across)."""
    n_games = len(game_starts)
    val_n_games = max(1, int(n_games * val_fraction))
    perm = rng.permutation(n_games)
    val_games = set(perm[:val_n_games].tolist())
    train_idx = []
    val_idx = []
    for g in range(n_games):
        start = game_starts[g]
        end = game_starts[g + 1] if g + 1 < n_games else n_total
        target = val_idx if g in val_games else train_idx
        target.extend(range(start, end))
    return np.array(train_idx, dtype=np.int64), np.array(val_idx, dtype=np.int64)


def policy_cross_entropy(logits: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Soft cross-entropy: -sum(target * log_softmax(logits)) over valid actions.

    target is already a probability distribution over valid actions (zero on
    invalid). We mask logits to -inf on invalid before log_softmax so invalid
    actions don't dilute the normalization.
    """
    masked = logits.masked_fill(~mask.bool(), float("-inf"))
    log_probs = F.log_softmax(masked, dim=-1)
    # When the row is all-invalid (no legal moves), masked is all -inf, log_probs has nans.
    # In that case target row is all zeros so the contribution is 0 anyway; replace nans.
    log_probs = torch.where(torch.isfinite(log_probs), log_probs, torch.zeros_like(log_probs))
    return -(target * log_probs).sum(dim=-1).mean()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="train_warmstart_smoke")
    p.add_argument("--strategy", choices=("mcts", "heuristic"), required=True)
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--filters", type=int, default=64, help="trunk channel count (smoke=64, prod=96)")
    p.add_argument("--blocks", type=int, default=4, help="ResBlock count (smoke=4, prod=6)")
    p.add_argument("--val-fraction", type=float, default=0.1)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    rng = np.random.default_rng(args.seed)

    boards, scalars, policies, values, masks, game_starts = load_all(args.strategy)
    n = boards.shape[0]
    print(f"Loaded {n} positions across {len(game_starts)} games for strategy={args.strategy}")
    train_idx, val_idx = split_by_game(n, game_starts, args.val_fraction, rng)
    print(f"  split: train={len(train_idx)}, val={len(val_idx)}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  device: {device}")

    boards_t = torch.from_numpy(boards)
    scalars_t = torch.from_numpy(scalars)
    policies_t = torch.from_numpy(policies)
    values_t = torch.from_numpy(values)
    masks_t = torch.from_numpy(masks)

    train_ds = TensorDataset(
        boards_t[train_idx], scalars_t[train_idx], policies_t[train_idx],
        values_t[train_idx], masks_t[train_idx],
    )
    val_ds = TensorDataset(
        boards_t[val_idx], scalars_t[val_idx], policies_t[val_idx],
        values_t[val_idx], masks_t[val_idx],
    )
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=2, pin_memory=(device.type == "cuda"))
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2, pin_memory=(device.type == "cuda"))

    net = CarcassonneNet(n_filters=args.filters, n_blocks=args.blocks).to(device)
    print(f"  net params: {net.param_count():,}")

    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    steps_per_epoch = max(1, len(train_loader))
    total_steps = steps_per_epoch * args.epochs
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=total_steps)

    best_val = math.inf
    best_path = args.output.with_suffix(".best.pt")

    for epoch in range(args.epochs):
        net.train()
        t0 = time.perf_counter()
        train_pol_loss = 0.0
        train_val_loss = 0.0
        n_batches = 0
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
            loss.backward()
            opt.step()
            scheduler.step()
            train_pol_loss += pol_loss.item()
            train_val_loss += val_loss.item()
            n_batches += 1
        train_pol_loss /= max(n_batches, 1)
        train_val_loss /= max(n_batches, 1)

        # Validation
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
            f"  epoch {epoch+1:2d}/{args.epochs} ({elapsed:.1f}s)  "
            f"train pol/val={train_pol_loss:.3f}/{train_val_loss:.4f}  "
            f"val pol/val={val_pol_loss:.3f}/{val_val_loss:.4f}"
        )
        sys.stdout.flush()

        if val_total < best_val:
            best_val = val_total
            args.output.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state": net.state_dict(),
                "n_filters": args.filters,
                "n_blocks": args.blocks,
                "epoch": epoch,
                "val_pol_loss": val_pol_loss,
                "val_val_loss": val_val_loss,
                "strategy": args.strategy,
            }, best_path)

    # Final checkpoint
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model_state": net.state_dict(),
        "n_filters": args.filters,
        "n_blocks": args.blocks,
        "strategy": args.strategy,
    }, args.output)
    print(f"\nSaved final checkpoint: {args.output}")
    print(f"Saved best (by val loss) checkpoint: {best_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
