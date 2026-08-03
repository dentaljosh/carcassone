#!/usr/bin/env python3
"""Paper P1 gap G2 — the architecture-control trainer.

Trains ONE arm (`resnet_scratch`, `tf_match`, `tf_large`) from RANDOM INIT on the
EXACT corpus, split, targets, losses and optimizer recipe the published ResNet
baseline `value_unlock_v1` used (measurement/value_unlock_20260730/READOUT.md
sect 2), differing only in (a) the trunk architecture and (b) the number of corpus
passes, which is set to the baseline's CUMULATIVE lineage budget because these
arms get no warm start.

Everything task-shaped is IMPORTED from the shared pipeline rather than re-typed:
the file selection, the by-game train/val split, the streaming dataset, the
masked policy/ownership loss, and the value<->outcome correlation diagnostic all
come from `scripts/train_iter.py` / `carcassonne_ai.warmstart`. The only thing
this script owns is the model constructor, the epoch loop, and checkpointing.

MEASUREMENT ONLY. No PRODUCTION.yaml, no shared trainer default changed, no
champion touched. See measurement/paper_g2_20260803/PREREG.md.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(HERE))

from carcassonne_ai.network import CarcassonneNet                 # noqa: E402
from carcassonne_ai.warmstart import (                            # noqa: E402
    count_positions, make_streaming_dataset, split_files_train_val,
)
import train_iter as TI                                           # noqa: E402
from train_warmstart import masked_policy_ownership_loss          # noqa: E402
from g2_transformer import CONFIGS as TF_CONFIGS, build as build_tf  # noqa: E402


# --------------------------------------------------------------------------- #
# The frozen task definition — identical to value_unlock_v1's (READOUT sect 2). #
# --------------------------------------------------------------------------- #
CORPUS_ROOT = Path("/mnt/c/carc-shared/distill_strong_20260723")
CORPUS_ITER = 3
CORPUS_WINDOW = 4          # -> iter_00..03, 2,400 files / 345,333 rows
VAL_FRACTION = 0.05        # -> 2,280 train files / 120 val files, split BY GAME
SPLIT_SEED = 0
BATCH_SIZE = 256
LR = 3e-4
LR_SCHEDULE = "cosine"
WEIGHT_DECAY = 1e-4
VALUE_LOSS_WEIGHT = 5.0
AUX_WEIGHT = 0.0
N_INPUT_CHANNELS = 81      # sighted rep
N_SCALAR_FEATURES = 42
ACTION_SIZE = 2511

# Corpus passes. value_unlock_v1's lineage on this corpus family is
# iter_00..iter_03 at 3 epochs each (12) + the 4-epoch value refine = 16 passes.
# The G2 arms get no warm start, so they get the full cumulative budget.
DEFAULT_EPOCHS = 16


def build_net(arm: str):
    if arm == "resnet_scratch":
        net = CarcassonneNet(
            n_input_channels=N_INPUT_CHANNELS,
            n_scalar_features=N_SCALAR_FEATURES,
            n_filters=96, n_blocks=6, value_global_pool=True,
        )
        arch = {"arch": "resnet", "n_filters": 96, "n_blocks": 6,
                "n_input_channels": N_INPUT_CHANNELS,
                "n_scalar_features": N_SCALAR_FEATURES,
                "value_global_pool": True}
        return net, arch
    if arm in TF_CONFIGS:
        net = build_tf(arm, n_input_channels=N_INPUT_CHANNELS,
                       n_scalar_features=N_SCALAR_FEATURES,
                       action_size=ACTION_SIZE, value_global_pool=True)
        return net, net.arch_dict()
    raise KeyError(f"unknown arm {arm!r}")


def save_ckpt(path: Path, net, arch, arm, epoch, metrics):
    """Checkpoint layout is a SUPERSET of the CarcassonneNet checkpoints the
    solver ruler already reads (n_filters/n_blocks/n_input_channels/
    n_scalar_features/sighted/value_global_pool + model_state), plus `g2_arch`
    which the ruler's G2 ranker dispatches on."""
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = {
        "model_state": net.state_dict(),
        "g2_arm": arm,
        "g2_arch": arch,
        "n_input_channels": N_INPUT_CHANNELS,
        "n_scalar_features": N_SCALAR_FEATURES,
        "sighted": True,
        "include_farm_scalars": False,
        "value_global_pool": True,
        "epoch": epoch,
        "metrics": metrics,
    }
    if arch.get("arch") == "resnet":
        blob["n_filters"] = arch["n_filters"]
        blob["n_blocks"] = arch["n_blocks"]
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(blob, tmp)
    os.replace(tmp, path)


@torch.no_grad()
def evaluate(net, loader, device):
    """Held-out policy CE / value MSE / ownership loss, in fp32 (no autocast) so
    the numbers are directly comparable to the published fp32 baseline's."""
    net.train(False)
    pol = val = own = 0.0
    n = 0
    for board_b, scalar_b, policy_b, value_b, mask_b, own_b, aux_b, _grp in loader:
        board_b = board_b.to(device, non_blocking=True)
        scalar_b = scalar_b.to(device, non_blocking=True)
        policy_b = policy_b.to(device, non_blocking=True)
        value_b = value_b.to(device, non_blocking=True)
        mask_b = mask_b.to(device, non_blocking=True)
        own_b = own_b.to(device, non_blocking=True)
        aux_b = aux_b.to(device, non_blocking=True)
        logits, v, o = net.forward_train(board_b, scalar_b)
        p_loss, o_loss = masked_policy_ownership_loss(
            logits, policy_b, mask_b, o, own_b, board_b, aux_b)
        pol += float(p_loss.item())
        val += float(F.mse_loss(v, value_b).item())
        own += float(o_loss.item())
        n += 1
    return (pol / max(n, 1), val / max(n, 1), own / max(n, 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True,
                    choices=["resnet_scratch", *sorted(TF_CONFIGS)])
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    ap.add_argument("--micro-batch", type=int, default=256,
                    help="per-forward batch; gradient accumulation keeps the "
                         "EFFECTIVE optimizer batch at 256 regardless.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--stage-local", type=str, default=None)
    ap.add_argument("--precision", choices=["bf16", "fp32"], default="bf16")
    ap.add_argument("--resume", action="store_true",
                    help="resume from <out-dir>/last.pt if present (dirty-reboot guard)")
    args = ap.parse_args(argv)

    if BATCH_SIZE % args.micro_batch:
        raise SystemExit("--micro-batch must divide 256")
    accum = BATCH_SIZE // args.micro_batch

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ---- corpus: identical selection + identical by-game split -------------
    buffer_files = TI._select_buffer_files(CORPUS_ROOT, CORPUS_ITER, CORPUS_WINDOW)
    file_list = TI._build_mixed_file_list(buffer_files, [], 0.0, SPLIT_SEED)
    train_files, val_files = split_files_train_val(
        file_list, val_fraction=VAL_FRACTION, seed=SPLIT_SEED)
    if args.stage_local:
        stage = Path(args.stage_local)
        train_files = TI._stage_files_local(train_files, stage / "train")
        val_files = TI._stage_files_local(val_files, stage / "val")
    n_train = count_positions(train_files)
    n_val = count_positions(val_files)
    print(f"[data] {len(buffer_files)} corpus files -> train {len(train_files)} "
          f"({n_train} rows) / val {len(val_files)} ({n_val} rows)", flush=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_ds = make_streaming_dataset(train_files, shuffle_files_each_epoch=True,
                                      shuffle_within_file=True, seed=args.seed)
    val_ds = make_streaming_dataset(val_files, shuffle_files_each_epoch=False,
                                    shuffle_within_file=False, seed=args.seed)
    train_loader = DataLoader(train_ds, batch_size=args.micro_batch,
                              num_workers=args.num_workers,
                              persistent_workers=False,
                              pin_memory=(device.type == "cuda"))
    # Validation runs in fp32 (no autocast) so its numbers are comparable to the
    # published baseline's; use the same micro-batch so tf_large cannot OOM here.
    val_loader = DataLoader(val_ds, batch_size=args.micro_batch,
                            num_workers=args.num_workers,
                            persistent_workers=(args.num_workers > 0),
                            pin_memory=(device.type == "cuda"))

    net, arch = build_net(args.arm)
    net = net.to(device)
    n_params = sum(p.numel() for p in net.parameters() if p.requires_grad)
    print(f"[net] arm={args.arm} arch={arch} params={n_params:,}", flush=True)

    optim = torch.optim.AdamW(net.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=max(args.epochs, 1))

    start_epoch = 0
    history = []
    best = {"val_value_mse": float("inf"), "epoch": None}
    last_path = args.out_dir / "last.pt"
    state_path = args.out_dir / "train_state.pt"
    if args.resume and last_path.exists() and state_path.exists():
        st = torch.load(state_path, map_location=device, weights_only=False)
        net.load_state_dict(torch.load(last_path, map_location=device,
                                       weights_only=False)["model_state"])
        optim.load_state_dict(st["optim"])
        sched.load_state_dict(st["sched"])
        start_epoch = int(st["epoch"]) + 1
        history = st["history"]
        best = st["best"]
        print(f"[resume] restarting at epoch {start_epoch + 1}", flush=True)

    amp = (args.precision == "bf16")
    manifest = {
        "run": "paper_g2_20260803",
        "arm": args.arm,
        "arch": arch,
        "n_params": n_params,
        "corpus": {"root": str(CORPUS_ROOT), "iter": CORPUS_ITER,
                   "window": CORPUS_WINDOW, "n_files": len(buffer_files),
                   "n_train_rows": n_train, "n_val_rows": n_val,
                   "n_train_files": len(train_files), "n_val_files": len(val_files),
                   "split": "by-game (one seed_*.npz = one game)",
                   "split_seed": SPLIT_SEED, "val_fraction": VAL_FRACTION},
        "recipe": {"init": "random (no warm start)", "epochs": args.epochs,
                   "effective_batch": BATCH_SIZE, "micro_batch": args.micro_batch,
                   "grad_accum": accum, "lr": LR, "lr_schedule": LR_SCHEDULE,
                   "weight_decay": WEIGHT_DECAY,
                   "value_loss_weight": VALUE_LOSS_WEIGHT,
                   "aux_weight": AUX_WEIGHT, "seed": args.seed,
                   "precision": args.precision,
                   "optimizer_steps_per_epoch": math.ceil(n_train / BATCH_SIZE)},
        "device": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
        "torch": torch.__version__,
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))

    for epoch in range(start_epoch, args.epochs):
        train_ds.set_epoch(epoch)
        net.train(True)
        t0 = time.perf_counter()
        tp = tv = to = 0.0
        n_micro = 0
        nan_skipped = 0
        optim.zero_grad(set_to_none=True)
        pending = 0
        for board_b, scalar_b, policy_b, value_b, mask_b, own_b, aux_b, _grp in train_loader:
            board_b = board_b.to(device, non_blocking=True)
            scalar_b = scalar_b.to(device, non_blocking=True)
            policy_b = policy_b.to(device, non_blocking=True)
            value_b = value_b.to(device, non_blocking=True)
            mask_b = mask_b.to(device, non_blocking=True)
            own_b = own_b.to(device, non_blocking=True)
            aux_b = aux_b.to(device, non_blocking=True)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                logits, v, o = net.forward_train(board_b, scalar_b)
            logits, v, o = logits.float(), v.float(), o.float()
            pol_loss, own_loss = masked_policy_ownership_loss(
                logits, policy_b, mask_b, o, own_b, board_b, aux_b)
            val_loss = F.mse_loss(v, value_b)
            loss = pol_loss + VALUE_LOSS_WEIGHT * val_loss + AUX_WEIGHT * own_loss
            if not torch.isfinite(loss):
                nan_skipped += 1
                continue
            (loss / accum).backward()
            pending += 1
            if pending == accum:
                optim.step()
                optim.zero_grad(set_to_none=True)
                pending = 0
            tp += float(pol_loss.item())
            tv += float(val_loss.item())
            to += float(own_loss.item())
            n_micro += 1
        if pending:                      # flush a partial accumulation group
            optim.step()
            optim.zero_grad(set_to_none=True)
        sched.step()
        d = max(n_micro, 1)
        vp, vv, vo = evaluate(net, val_loader, device)
        corr = TI._value_outcome_corr(net, val_loader, device)
        ent = TI._mean_policy_entropy(net, val_loader, device)
        rec = {"epoch": epoch + 1, "wallclock_sec": round(time.perf_counter() - t0, 1),
               "lr": sched.get_last_lr()[0],
               "train_pol_loss": round(tp / d, 4), "train_val_loss": round(tv / d, 4),
               "train_own_loss": round(to / d, 4),
               "val_pol_loss": round(vp, 4), "val_val_loss": round(vv, 4),
               "val_own_loss": round(vo, 4),
               "val_value_outcome_corr": None if corr is None else round(corr, 4),
               "val_policy_entropy": round(ent, 4),
               "nan_skipped": nan_skipped}
        history.append(rec)
        print(f"  epoch {epoch+1:2d}/{args.epochs} ({rec['wallclock_sec']:.1f}s) "
              f"train pol/val={rec['train_pol_loss']:.4f}/{rec['train_val_loss']:.4f}  "
              f"val pol/val={rec['val_pol_loss']:.4f}/{rec['val_val_loss']:.4f}  "
              f"r={rec['val_value_outcome_corr']}  H={rec['val_policy_entropy']:.4f}",
              flush=True)

        save_ckpt(args.out_dir / f"epoch_{epoch+1:02d}.pt", net, arch, args.arm,
                  epoch + 1, rec)
        save_ckpt(last_path, net, arch, args.arm, epoch + 1, rec)
        if vv < best["val_value_mse"]:
            best = {"val_value_mse": vv, "epoch": epoch + 1,
                    "val_value_outcome_corr": rec["val_value_outcome_corr"]}
            save_ckpt(args.out_dir / "best.pt", net, arch, args.arm, epoch + 1, rec)
        torch.save({"optim": optim.state_dict(), "sched": sched.state_dict(),
                    "epoch": epoch, "history": history, "best": best}, state_path)
        (args.out_dir / "history.json").write_text(json.dumps(
            {"manifest": manifest, "history": history, "best": best}, indent=1))

    save_ckpt(args.out_dir / "final.pt", net, arch, args.arm, args.epochs,
              history[-1] if history else {})
    print(f"[done] arm={args.arm} best val_value_mse={best['val_value_mse']:.4f} "
          f"@ epoch {best['epoch']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
