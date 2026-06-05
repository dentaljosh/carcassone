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
from train_warmstart import masked_policy_ownership_loss  # noqa: E402


def listwise_ranking_loss(value_pred, value_b, group_b, temp: float):
    """Listwise sibling-ranking loss (STEP B.1, DECISIONS 2026-06-05 pm-3).

    Within each ranking group (rows sharing group_id >= 0 = the children of one
    search-tree node), match softmax(value_pred/temp) to softmax(search_Q/temp)
    via cross-entropy — training the value head to ORDER a node's children by
    their search Q. This directly optimizes the LOCAL discrimination that MSE
    cannot (STEP A/B.0: MSE heads rank siblings at chance, τ≈0.08, even fit to
    the optimal target). Returns a 0 scalar if no group with >=2 members is in
    the batch (so it's a no-op on non-ranking data / when --rank-weight 0).

    Groups are kept contiguous in the stream (train_iter sets
    shuffle_within_file=False when ranking is on), so a group's children almost
    always co-occur in one batch; a group split across a batch boundary just
    contributes a partial (still-valid) ranking signal. O(#groups) Python loop —
    cheap vs the forward pass (~tens of groups/batch)."""
    from collections import defaultdict
    gids = group_b.tolist()
    buckets: dict[int, list[int]] = defaultdict(list)
    for i, gid in enumerate(gids):
        if gid >= 0:
            buckets[gid].append(i)
    losses = []
    for idxs in buckets.values():
        if len(idxs) < 2:
            continue
        idx = torch.tensor(idxs, device=value_pred.device)
        logp = F.log_softmax(value_pred[idx] / temp, dim=0)
        tgt = F.softmax(value_b[idx] / temp, dim=0)
        losses.append(-(tgt * logp).sum())
    if not losses:
        return value_pred.new_zeros(())
    return torch.stack(losses).mean()


def _mean_policy_entropy(net, loader, device) -> float:
    """Mean entropy (nats) of the masked-softmax policy head over `loader`.

    Path B collapse signal: a healthy policy keeps spreading mass over legal
    moves; entropy crashing toward 0 means the head has collapsed to a
    near-deterministic policy (the closed-loop drift that wrecked early self-play
    runs). The entropy-floor gate compares this against the warmstart net's
    initial entropy. Returns 0.0 if the loader yields nothing.
    """
    net.train(False)
    total = 0.0
    n = 0
    with torch.no_grad():
        for board_b, scalar_b, _policy_b, _value_b, mask_b, _own_b, aux_b, _grp_b in loader:
            # Skip value-only rows (aux_mask=False): their masks are all-False so
            # the masked softmax is degenerate. Entropy is a POLICY-head signal.
            aux_b = aux_b.bool()
            if not aux_b.any():
                continue
            board_b = board_b[aux_b].to(device, non_blocking=True)
            scalar_b = scalar_b[aux_b].to(device, non_blocking=True)
            mask_b = mask_b[aux_b].to(device, non_blocking=True).bool()
            logits, _, _ = net.forward_train(board_b, scalar_b)
            log_probs = F.log_softmax(logits.masked_fill(~mask_b, float("-inf")), dim=-1)
            p = log_probs.exp()
            # legal: -p·log p ; illegal: exp(-inf)=0 but 0·-inf=nan, so zero them.
            plogp = torch.where(mask_b, p * log_probs, torch.zeros_like(p))
            ent = -plogp.sum(dim=-1)
            total += ent.sum().item()
            n += int(ent.shape[0])
    return total / max(n, 1)


def _value_outcome_corr(net, loader, device):
    """Pearson r between the value head's prediction and the stored value target
    (the game-outcome score_diff) over `loader`.

    The Path B diagnostic (PATH_B 'Diagnostic gate'): a learned value worth using
    must actually predict outcomes. The v2.7 heuristic leaf sits at ~0.61; the old
    data-starved NN value was ~0.18. This is the TRUSTWORTHY per-iter signal —
    unlike the self-anchored chain elo, it can't climb while absolute strength
    regresses. Returns None if a variance is degenerate or the loader is empty.
    """
    net.train(False)
    sx = sy = sxx = syy = sxy = 0.0
    n = 0
    with torch.no_grad():
        # Value applies to ALL rows (incl. aux_mask=False interior rows, whose
        # target is the node's search Q) → no aux subsetting here.
        for board_b, scalar_b, _policy_b, value_b, _mask_b, _own_b, _aux_b, _grp_b in loader:
            board_b = board_b.to(device, non_blocking=True)
            scalar_b = scalar_b.to(device, non_blocking=True)
            value_b = value_b.to(device, non_blocking=True)
            _, value_pred, _ = net.forward_train(board_b, scalar_b)
            x = value_pred.flatten().double()
            y = value_b.flatten().double()
            sx += x.sum().item()
            sy += y.sum().item()
            sxx += (x * x).sum().item()
            syy += (y * y).sum().item()
            sxy += (x * y).sum().item()
            n += int(x.numel())
    if n < 2:
        return None
    cov = sxy - sx * sy / n
    vx = sxx - sx * sx / n
    vy = syy - sy * sy / n
    if vx <= 0 or vy <= 0:
        return None
    return cov / (vx * vy) ** 0.5


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


def _stage_files_local(files: list[Path], stage_dir: Path) -> list[Path]:
    """Copy `files` into a LOCAL dir; return the staged paths (order preserved).

    Keeps the training read-path off slow/flaky 9p/drvfs or CIFS mounts. A 9p
    (Windows drvfs) stall wedged an 822K-position train mid-epoch — GPU idle ~50
    min, one CPU core spinning (2026-06-05). Streaming many small .npz from 9p is
    the exact pathological pattern. Dedupes by source path (warmstart mix samples
    with replacement) so a duplicated file_list entry copies the file only once.
    """
    import shutil
    stage_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, Path] = {}
    staged: list[Path] = []
    for src in files:
        key = str(src)
        dst = mapping.get(key)
        if dst is None:
            dst = stage_dir / f"{len(mapping):06d}_{src.name}"
            shutil.copy2(src, dst)
            mapping[key] = dst
        staged.append(dst)
    return staged


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
    p.add_argument("--augment-rotations", action="store_true",
                   help="C5 symmetry aug: expand each training file to its 4 board "
                        "rotations (4x label-correct data). Train set only; off by default.")
    p.add_argument("--stage-local", type=str, default=None,
                   help="Copy selected buffer/val .npz into this LOCAL dir before "
                        "streaming, to keep the training read-path off slow 9p/drvfs "
                        "or CIFS mounts. A 9p stall once wedged a train mid-epoch "
                        "(GPU idle ~50min, 2026-06-05). Use e.g. /tmp/carc_stage_<run>; "
                        "caller cleans it up afterward.")
    p.add_argument("--warmstart-mix-fraction", type=float, default=0.0,
                   help="Fraction of training samples from the warmstart "
                        "dataset (rest from self-play buffer). Plan: 1.0 "
                        "at iter 0, 0.7 at iter 1, 0.4 at iter 2, 0.0 from iter 3.")
    p.add_argument("--warm-from", type=Path, required=True,
                   help="Checkpoint to initialize the network from.")
    p.add_argument("--global-pool", action="store_true",
                   help="Flywheel step 2: build a global-pool value head (UPGRADES "
                        "the arch even from a non-pool warm-from). Pair with "
                        "--warm-value-fresh when the warm-from lacks global pool.")
    p.add_argument("--warm-value-fresh", action="store_true",
                   help="Partial warm: load stem/trunk/policy/ownership from "
                        "--warm-from but re-init the value head (use when the value "
                        "arch changed, e.g. --global-pool from a non-pool checkpoint).")
    p.add_argument("--output", type=Path, required=True,
                   help="Output checkpoint path (e.g. checkpoints/selfplay/iter_00.pt).")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument(
        "--lr-schedule", choices=["none", "cosine"], default="none",
        help="G-T1 (round-2 audit): LR schedule. 'none' (default) = flat lr "
             "(prior behavior). 'cosine' = CosineAnnealingLR over --epochs; use "
             "at Stage B for a low-LR value-head refine phase.",
    )
    p.add_argument(
        "--value-loss-weight", type=float, default=1.0,
        help="G-T2 (round-2 audit): coefficient on the value MSE in the total "
             "loss. Default 1.0 = prior behavior. Policy CE dominates the value "
             "term ~5-10x unweighted; raise this (1-5) at Stage B to stop "
             "starving the value head (esp. with --value-target score_diff_wide).",
    )
    p.add_argument(
        "--aux-weight",
        type=float,
        default=0.15,
        help="Path B ownership aux-loss weight (added to policy CE + value MSE).",
    )
    p.add_argument(
        "--rank-weight", type=float, default=0.0,
        help="STEP B.1 listwise sibling-ranking loss weight (alpha). 0 = off "
             "(prior behavior). >0 trains the value head to ORDER each search "
             "node's children by their search Q (needs --value-target "
             "search_value_rank data with group_id). Sets shuffle_within_file="
             "False so groups stay batch-contiguous. Sweep 0.5-3.",
    )
    p.add_argument(
        "--rank-temp", type=float, default=0.2,
        help="Softmax temperature for the ranking loss (both pred and target "
             "logits divided by it). Lower = sharper ordering target. Sweep 0.1-0.3.",
    )
    p.add_argument("--val-fraction", type=float, default=0.05)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--entropy-floor-frac",
        type=float,
        default=0.5,
        help="Path B collapse guard: halt the loop (exit 2) if the trained net's "
        "mean policy entropy falls below this fraction of the warmstart net's "
        "initial entropy. Baseline is measured at iter 0 and propagated forward in "
        "the checkpoint so every iter compares to the same fixed reference. "
        "0.0 disables the guard.",
    )
    args = p.parse_args(argv)

    # Seed every RNG that affects training so two runs with the same --seed
    # produce the same checkpoint. (split_files_train_val / _build_mixed_file_list
    # already take an explicit seed; this covers weight init, AdamW, and loader
    # worker shuffling.) Mirrors train_warmstart.py.
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

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
    # Stage the read-path onto local ext4 if asked — keeps streaming off slow
    # 9p/drvfs/CIFS (a 9p stall wedged a train mid-epoch, 2026-06-05).
    if args.stage_local:
        stage_root = Path(args.stage_local)
        train_files = _stage_files_local(train_files, stage_root / "train")
        if val_files:
            val_files = _stage_files_local(val_files, stage_root / "val")
        print(f"  staged {len(train_files)} train + {len(val_files)} val files "
              f"→ {stage_root} (local fs, off 9p/network)")
        sys.stdout.flush()
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

    # Ranking loss (STEP B.1) needs a group's children in the SAME batch →
    # keep them contiguous (no within-file shuffle). Files still shuffle across
    # epochs, and groups never span files, so this barely affects mixing.
    train_ds = make_streaming_dataset(
        train_files,
        shuffle_files_each_epoch=True,
        shuffle_within_file=(args.rank_weight == 0.0),
        seed=args.seed,
        augment_rotations=args.augment_rotations,
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
    # n_scalar_features propagates from the warmstart (Path B Step E: 12 if farm
    # scalars are on, else 10). Default 10 for pre-Step-E checkpoints. The
    # self-play .npz this trains on must carry matching-width scalars (i.e.
    # run_selfplay_iter used Game(include_farm_scalars=...) consistently).
    n_scalar_features = int(ckpt.get("n_scalar_features", 10))
    # flywheel step 2: --global-pool UPGRADES the value arch (adds the board-wide
    # global-pool summary) even when warming from a non-pool checkpoint; the
    # checkpoint's own flag is the default for plain continuation.
    value_global_pool = bool(ckpt.get("value_global_pool", False)) or args.global_pool
    net = CarcassonneNet(
        n_filters=n_filters, n_blocks=n_blocks, n_scalar_features=n_scalar_features,
        value_global_pool=value_global_pool,
    ).to(device)
    if args.warm_value_fresh:
        # Partial warm: load stem/trunk/policy/ownership from the warm-from net,
        # but leave the value head (value_fc*) at its fresh init — used when the
        # value ARCHITECTURE changed (global pool) so its shapes don't match.
        # Isolates the arch change: strong warm policy/trunk, value head retrained.
        sd = {k: v for k, v in ckpt["model_state"].items() if not k.startswith("value_fc")}
        net.load_state_dict(sd, strict=False)
        print(f"  WARM trunk+policy from {args.warm_from}; value head RE-INIT "
              f"(arch change: global_pool={value_global_pool})")
    else:
        net.load_state_dict(ckpt["model_state"])
    print(f"  net (filters={n_filters}, blocks={n_blocks}, "
          f"global_pool={value_global_pool}, params={net.param_count():,})")

    # Path B entropy-floor collapse guard: the baseline is the WARMSTART net's
    # initial policy entropy — measured once (at iter 0, when warm_from IS the
    # warmstart net) and then carried forward through the checkpoint so every
    # later iter compares against the same fixed reference, not its own warm-from.
    baseline_entropy = ckpt.get("baseline_policy_entropy")
    if args.entropy_floor_frac > 0 and do_validation:
        if baseline_entropy is None:
            baseline_entropy = _mean_policy_entropy(net, val_loader, device)
            print(f"  baseline policy entropy (warm net) = {baseline_entropy:.4f} nats")
        else:
            print(f"  baseline policy entropy (inherited) = {baseline_entropy:.4f} nats")

    optim = torch.optim.AdamW(
        net.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    # G-T1 (round-2 audit): optional LR schedule. Default "none" = flat lr
    # (exact prior behavior). "cosine" decays over the epochs — use at Stage B,
    # where the value head is in the loop and benefits from a low-LR refine phase.
    sched = None
    if args.lr_schedule == "cosine":
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(
            optim, T_max=max(args.epochs, 1)
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
        train_own_loss = 0.0
        train_rank_loss = 0.0
        n_batches = 0
        nan_skipped = 0
        for board_b, scalar_b, policy_b, value_b, mask_b, own_b, aux_b, group_b in train_loader:
            board_b = board_b.to(device, non_blocking=True)
            scalar_b = scalar_b.to(device, non_blocking=True)
            policy_b = policy_b.to(device, non_blocking=True)
            value_b = value_b.to(device, non_blocking=True)
            mask_b = mask_b.to(device, non_blocking=True)
            own_b = own_b.to(device, non_blocking=True)
            aux_b = aux_b.to(device, non_blocking=True)
            optim.zero_grad(set_to_none=True)
            policy_logits, value_pred, own_pred = net.forward_train(board_b, scalar_b)
            # Policy/ownership over full-trajectory rows only; value over all rows
            # (interior value-only rows train the value head — flywheel step 1).
            pol_loss, own_loss = masked_policy_ownership_loss(
                policy_logits, policy_b, mask_b, own_pred, own_b, board_b, aux_b
            )
            val_loss = F.mse_loss(value_pred, value_b)
            # STEP B.1: listwise sibling-ranking loss (0 unless --rank-weight>0 AND
            # the batch has groups). Trains the value head to ORDER each node's
            # children by search Q — the local discrimination MSE misses.
            if args.rank_weight > 0.0:
                rank_loss = listwise_ranking_loss(
                    value_pred, value_b, group_b, args.rank_temp
                )
            else:
                rank_loss = value_pred.new_zeros(())
            # G-T2 (round-2 audit): policy CE (O(2-6) over 2511 actions) dominates
            # value MSE (O(0.1-1)) ~5-10x in the unweighted sum, starving the value
            # head — the exact thing Stage B needs load-bearing. value_loss_weight
            # defaults to 1.0 (prior behavior); sweep it up (1-5x) at Stage B,
            # especially with score_diff_wide which shrinks the value-target scale.
            loss = (
                pol_loss
                + args.value_loss_weight * val_loss
                + args.aux_weight * own_loss
                + args.rank_weight * rank_loss
            )
            if not torch.isfinite(loss):
                # zero_grad already ran above this batch, so skipping here
                # leaves no stale gradient to leak into the next batch's step.
                nan_skipped += 1
                continue
            loss.backward()
            optim.step()
            train_pol_loss += pol_loss.item()
            train_val_loss += val_loss.item()
            train_own_loss += own_loss.item()
            train_rank_loss += float(rank_loss.item())
            n_batches += 1
        if nan_skipped:
            print(f"  [warn] skipped {nan_skipped} NaN-loss batch(es) this epoch")
        train_pol_loss /= max(n_batches, 1)
        train_val_loss /= max(n_batches, 1)
        train_own_loss /= max(n_batches, 1)
        train_rank_loss /= max(n_batches, 1)

        if do_validation:
            net.train(False)
            val_pol_loss = 0.0
            val_val_loss = 0.0
            val_own_loss = 0.0
            val_rank_loss = 0.0
            v_n = 0
            with torch.no_grad():
                for board_b, scalar_b, policy_b, value_b, mask_b, own_b, aux_b, group_b in val_loader:
                    board_b = board_b.to(device, non_blocking=True)
                    scalar_b = scalar_b.to(device, non_blocking=True)
                    policy_b = policy_b.to(device, non_blocking=True)
                    value_b = value_b.to(device, non_blocking=True)
                    mask_b = mask_b.to(device, non_blocking=True)
                    own_b = own_b.to(device, non_blocking=True)
                    aux_b = aux_b.to(device, non_blocking=True)
                    policy_logits, value_pred, own_pred = net.forward_train(board_b, scalar_b)
                    v_pol_loss, v_own_loss = masked_policy_ownership_loss(
                        policy_logits, policy_b, mask_b, own_pred, own_b, board_b, aux_b
                    )
                    val_pol_loss += v_pol_loss.item()
                    val_val_loss += F.mse_loss(value_pred, value_b).item()
                    val_own_loss += v_own_loss.item()
                    if args.rank_weight > 0.0:
                        val_rank_loss += float(
                            listwise_ranking_loss(
                                value_pred, value_b, group_b, args.rank_temp
                            ).item()
                        )
                    v_n += 1
            val_pol_loss /= max(v_n, 1)
            val_val_loss /= max(v_n, 1)
            val_own_loss /= max(v_n, 1)
            val_rank_loss /= max(v_n, 1)
        else:
            val_pol_loss = float("nan")
            val_val_loss = float("nan")
            val_own_loss = float("nan")
            val_rank_loss = float("nan")

        elapsed = time.perf_counter() - t0
        epoch_metric = {
            "epoch": epoch + 1,
            "n_batches": n_batches,
            "wallclock_sec": round(elapsed, 1),
            "train_pol_loss": round(train_pol_loss, 4),
            "train_val_loss": round(train_val_loss, 4),
            "train_own_loss": round(train_own_loss, 4),
            "train_rank_loss": round(train_rank_loss, 4),
            "val_pol_loss": round(val_pol_loss, 4) if do_validation else None,
            "val_val_loss": round(val_val_loss, 4) if do_validation else None,
            "val_own_loss": round(val_own_loss, 4) if do_validation else None,
            "val_rank_loss": round(val_rank_loss, 4) if do_validation else None,
        }
        metrics["epochs"].append(epoch_metric)
        rank_str = (
            f" rank={train_rank_loss:.4f}" + (f"/{val_rank_loss:.4f}" if do_validation else "")
            if args.rank_weight > 0.0 else ""
        )
        if do_validation:
            print(
                f"  epoch {epoch+1:2d}/{args.epochs} ({elapsed:.1f}s, {n_batches} batches)  "
                f"train pol/val/own={train_pol_loss:.3f}/{train_val_loss:.4f}/{train_own_loss:.4f}  "
                f"val pol/val/own={val_pol_loss:.3f}/{val_val_loss:.4f}/{val_own_loss:.4f}{rank_str}"
            )
        else:
            print(
                f"  epoch {epoch+1:2d}/{args.epochs} ({elapsed:.1f}s, {n_batches} batches)  "
                f"train pol/val/own={train_pol_loss:.3f}/{train_val_loss:.4f}/{train_own_loss:.4f}{rank_str}  (no val)"
            )
        sys.stdout.flush()
        if sched is not None:
            sched.step()

    # Trained-net policy entropy (post-training) for the collapse guard.
    trained_entropy = None
    if args.entropy_floor_frac > 0 and do_validation:
        trained_entropy = _mean_policy_entropy(net, val_loader, device)
        metrics["policy_entropy"] = round(trained_entropy, 4)
        metrics["baseline_policy_entropy"] = (
            round(baseline_entropy, 4) if baseline_entropy is not None else None
        )

    # Value↔outcome correlation — the TRUSTWORTHY per-iter progress signal (vs the
    # self-anchored chain elo, which can climb while absolute strength regresses).
    # Beat the v2.7 heuristic leaf's ~0.61 to believe the learned value is working.
    value_corr = _value_outcome_corr(net, val_loader, device) if do_validation else None
    if value_corr is not None:
        metrics["value_outcome_corr"] = round(value_corr, 4)
        print(
            f"  value↔outcome corr = {value_corr:+.4f}  "
            f"(target: beat heuristic 0.61; old data-starved NN was 0.18)"
        )

    # Atomic save (review R2-L1): write a temp file then rename, so a SIGKILL /
    # OOM / power-loss mid-write can't leave a truncated .pt that the next iter's
    # bare torch.load picks up (resume guards check exists() only) and crashes the
    # loop. Mirrors warmstart.py's temp-then-replace idiom.
    _tmp_output = args.output.with_name(args.output.stem + ".partial.pt")
    torch.save(
        {
            "model_state": net.state_dict(),
            "n_filters": n_filters,
            "n_blocks": n_blocks,
            "n_scalar_features": n_scalar_features,
            "value_global_pool": value_global_pool,
            "iter": args.iter_idx,
            "epochs": args.epochs,
            # Carry the fixed baseline forward so every iter compares against the
            # original warmstart net, not its immediate warm-from.
            "baseline_policy_entropy": baseline_entropy,
            "policy_entropy": trained_entropy,
        },
        _tmp_output,
    )
    _tmp_output.replace(args.output)
    metrics_path = args.output.with_suffix(".metrics.json")
    with metrics_path.open("w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"\nSaved {args.output} (+ {metrics_path.name})")

    # Entropy-floor collapse gate: report-and-halt AFTER saving (so the collapsed
    # checkpoint + metrics stay inspectable). Exit 2 propagates through the loop
    # harness (run_phase4_smoke._run_subcommand → RuntimeError) and stops the run.
    if (
        args.entropy_floor_frac > 0
        and baseline_entropy is not None
        and trained_entropy is not None
    ):
        floor = args.entropy_floor_frac * baseline_entropy
        if trained_entropy < floor:
            print(
                f"\nCOLLAPSE: policy entropy {trained_entropy:.4f} < "
                f"{args.entropy_floor_frac:.2f}× warmstart baseline "
                f"{baseline_entropy:.4f} (floor {floor:.4f}). The policy head has "
                f"collapsed toward determinism — halting the loop. Inspect "
                f"{args.output} / {metrics_path.name} and DECISIONS.md before "
                f"re-launching.",
                file=sys.stderr,
            )
            return 2
        print(
            f"  policy entropy {trained_entropy:.4f} nats — OK (floor {floor:.4f} "
            f"= {args.entropy_floor_frac:.2f}× baseline {baseline_entropy:.4f})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
