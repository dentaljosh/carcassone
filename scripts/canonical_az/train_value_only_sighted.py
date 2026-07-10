#!/usr/bin/env python3
"""C-cheap — VALUE-ONLY trainer for the sighted (81ch/42-scalar) deck-aware value.

WHY A NEW SCRIPT (read this): neither existing trainer can do what C-cheap step 2
needs cleanly, so using them would SILENTLY train the wrong thing:
  * `train_warmstart.py --sighted --global-pool` builds a FRESH 81ch net but has NO
    warm-from flag — it cannot transfer the iter8 trunk.
  * `train_iter.py --warm-from iter8.pt` DERIVES the arch (n_input_channels, sighted,
    n_scalar) FROM the warm-from checkpoint. iter8 is a BLIND 78ch / 12-scalar net
    (sighted=None, value_global_pool=False), so it would build a 78ch net and CHOKE
    on (or silently mis-read) the 81ch sighted data — and it has no cross-channel
    stem re-init.
This script does exactly the spec's step 2: build an 81ch/42-scalar CarcassonneNet
with value_global_pool=True, WARM the ResNet TRUNK from the blind iter8 champion
(transfer only shape-matching non-stem/non-value keys), RE-INIT the 81ch stem + the
value head (their shapes changed), and train VALUE-ONLY (MSE against the stored
`score_diff_wide` fair-outcome labels; policy + ownership heads are NOT in the loss,
so they never train). Output a checkpoint that `eval_fair_puct.py --info fair-net
--net <ckpt>` consumes directly (it reads n_input_channels/n_scalar/sighted/
value_global_pool from the ckpt).

DATA: a flat directory of `seed_*.npz` shards from gen_fair_selfplay.py — each row is
VALUE-ONLY (aux_mask=False; sighted obs + scalars+bag + mover-POV score_diff_wide).
Streamed via warmstart.make_streaming_dataset (the dataset is ~40GB for 1-2k games,
too big for RAM, so it MUST stream).

TRAINING is GPU-latency-bound on this tiny net (memory reference_training_latency_bound)
→ run on the 5900XT; bigger --batch-size is the only real speed lever.

SMOKE first (confirms loss drops + a ckpt is written, ~seconds, no full epoch):
  .venv/bin/python scripts/canonical_az/train_value_only_sighted.py \
      --data-root /mnt/c/carc-shared/c_cheap_fairgen \
      --warm-from /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
      --output /tmp/c_cheap_value_smoke.pt --max-steps 30 --batch-size 64 --num-workers 2

FULL run:
  nice -n 19 .venv/bin/python -u scripts/canonical_az/train_value_only_sighted.py \
      --data-root /mnt/c/carc-shared/c_cheap_fairgen \
      --warm-from /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
      --output /mnt/c/carc-shared/c_cheap_value/value_head.pt \
      --epochs 8 --batch-size 512 --lr 1e-3 --value-loss-weight 1.0 --num-workers 6
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.warmstart import (  # noqa: E402
    count_positions,
    iter_game_dataset_files,
    make_streaming_dataset,
    split_files_train_val,
)

# Keys re-initialized (NOT transferred from the blind iter8 warm-from): the 81ch
# stem (input channels changed 78->81) and the whole value head (arch changed:
# +global-pool, +32 bag scalars). Everything else (the ResNet trunk, and any other
# shape-matching key) transfers. This is the spec's "re-init the 81ch stem + value
# head; trunk transfers".
_REINIT_PREFIXES = ("stem.", "value_project.", "value_fc1.", "value_fc2.")


def _warm_trunk_from(net: CarcassonneNet, warm_from: Path) -> tuple[list[str], list[str]]:
    """Load the blind iter8 checkpoint and copy ONLY shape-matching, non-stem,
    non-value-head weights into `net` (in place). Returns (transferred, reinit)
    key lists for a loud provenance print — no key is transferred silently."""
    ck = torch.load(warm_from, map_location="cpu", weights_only=False)
    src = ck["model_state"]
    dst = net.state_dict()
    transferred, reinit = [], []
    new_state = dict(dst)
    for k, v in dst.items():
        if k.startswith(_REINIT_PREFIXES):
            reinit.append(k)
            continue
        if k in src and tuple(src[k].shape) == tuple(v.shape):
            new_state[k] = src[k]
            transferred.append(k)
        else:
            reinit.append(k)   # missing in src or shape mismatch (e.g. policy_fc)
    net.load_state_dict(new_state, strict=True)
    return transferred, reinit


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="train_value_only_sighted")
    p.add_argument("--data-root", type=Path, required=True,
                   help="dir of seed_*.npz fair-value shards (gen_fair_selfplay.py output)")
    p.add_argument("--warm-from", type=Path, required=True,
                   help="blind champion ckpt to warm the TRUNK from (flywheel iter8.pt)")
    p.add_argument("--output", type=Path, required=True, help="output ckpt path")
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=0,
                   help="SMOKE: stop after N optimizer steps (0 = full --epochs)")
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--value-loss-weight", type=float, default=1.0,
                   help="scales the value MSE (the only loss term here)")
    p.add_argument("--freeze-trunk", action="store_true",
                   help="freeze stem+trunk, train ONLY the value head (default OFF: "
                        "train stem+trunk+value on the value MSE so the re-init 81ch "
                        "stem can learn the farm-connectivity planes).")
    p.add_argument("--val-fraction", type=float, default=0.05)
    p.add_argument("--num-workers", type=int, default=6)
    p.add_argument("--filters", type=int, default=96)
    p.add_argument("--blocks", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # --- net: the sighted 81ch / 42-scalar layout, value_global_pool ON ---------
    dims_game = Game(sighted=True)                         # include_farm_scalars=False
    n_input_channels = dims_game.get_input_channels()      # 81
    n_scalar_features = dims_game.get_scalar_feature_size()  # 42
    assert (n_input_channels, n_scalar_features) == (81, 42), \
        f"expected sighted 81ch/42-scalar, got {n_input_channels}/{n_scalar_features}"
    net = CarcassonneNet(
        n_filters=args.filters, n_blocks=args.blocks,
        n_input_channels=n_input_channels, n_scalar_features=n_scalar_features,
        value_global_pool=True,
    )
    transferred, reinit = _warm_trunk_from(net, args.warm_from)
    print(f"[warm] from {args.warm_from}")
    print(f"[warm] transferred {len(transferred)} tensors (trunk + shape-matching heads)")
    print(f"[warm] re-init     {len(reinit)} tensors (81ch stem + value head + policy_fc)")

    if args.freeze_trunk:
        for name, param in net.named_parameters():
            if name.startswith("stem.") or name.startswith("trunk."):
                param.requires_grad_(False)
        print("[warm] --freeze-trunk: stem+trunk frozen (training value head only)")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net.to(device)
    print(f"[train] device={device} params={net.param_count()} "
          f"value_global_pool=True sighted={n_input_channels}ch/{n_scalar_features}sc")

    # --- data: stream the flat seed_*.npz shards --------------------------------
    files = list(iter_game_dataset_files(args.data_root))
    if not files:
        raise SystemExit(f"no seed_*.npz under {args.data_root} — run gen_fair_selfplay.py first")
    train_files, val_files = split_files_train_val(files, val_fraction=args.val_fraction, seed=args.seed)
    print(f"[data] {len(files)} shards -> {len(train_files)} train / {len(val_files)} val "
          f"({count_positions(train_files)} train pos)")
    train_ds = make_streaming_dataset(train_files, shuffle_files_each_epoch=True,
                                      shuffle_within_file=True, seed=args.seed)
    val_ds = make_streaming_dataset(val_files, shuffle_files_each_epoch=False,
                                    shuffle_within_file=False, seed=args.seed)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, num_workers=args.num_workers,
                              pin_memory=(device.type == "cuda"), persistent_workers=False)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, num_workers=min(args.num_workers, 2),
                            pin_memory=(device.type == "cuda"),
                            persistent_workers=(args.num_workers > 0))

    opt = torch.optim.AdamW([q for q in net.parameters() if q.requires_grad],
                            lr=args.lr, weight_decay=args.weight_decay)

    def _run_value_forward(board_b, scalar_b):
        # value head only; policy/ownership heads are never in the loss (value-only).
        _policy_logits, value = net(board_b, scalar_b)
        return value

    step = 0
    epoch_train_mse: list[float] = []
    t0 = time.perf_counter()
    stop = False
    for epoch in range(args.epochs):
        if hasattr(train_ds, "set_epoch"):
            train_ds.set_epoch(epoch)
        net.train()
        run_loss = run_n = 0
        for board_b, scalar_b, _pol, value_b, _mask, _own, _aux, _grp in train_loader:
            board_b = board_b.to(device, non_blocking=True)
            scalar_b = scalar_b.to(device, non_blocking=True)
            value_b = value_b.to(device, non_blocking=True)
            value_pred = _run_value_forward(board_b, scalar_b)
            loss = args.value_loss_weight * F.mse_loss(value_pred, value_b)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            lv = float(loss.detach().cpu())
            run_loss += lv * value_b.shape[0]
            run_n += value_b.shape[0]
            step += 1
            if step % 50 == 0:
                print(f"  epoch {epoch} step {step}: value_mse={lv:.5f} "
                      f"({run_n/(time.perf_counter()-t0):.0f} pos/s)", flush=True)
            if args.max_steps and step >= args.max_steps:
                stop = True
                break
        # validation MSE
        net.eval()
        vloss = vn = 0
        with torch.no_grad():
            for board_b, scalar_b, _pol, value_b, _mask, _own, _aux, _grp in val_loader:
                board_b = board_b.to(device, non_blocking=True)
                scalar_b = scalar_b.to(device, non_blocking=True)
                value_b = value_b.to(device, non_blocking=True)
                vp = _run_value_forward(board_b, scalar_b)
                vloss += float(F.mse_loss(vp, value_b, reduction="sum").cpu())
                vn += value_b.shape[0]
        tr = run_loss / max(1, run_n)
        va = vloss / max(1, vn)
        epoch_train_mse.append(tr)
        print(f"[epoch {epoch}] train_value_mse={tr:.5f}  val_value_mse={va:.5f}  "
              f"(steps={step}, {time.perf_counter()-t0:.1f}s)", flush=True)
        if stop:
            break

    # --- save (arch dims match eval_fair_puct._load_net expectations) -----------
    ckpt = {
        "model_state": net.state_dict(),
        "n_filters": args.filters, "n_blocks": args.blocks,
        "n_input_channels": n_input_channels, "n_scalar_features": n_scalar_features,
        "sighted": True, "include_farm_scalars": False, "value_global_pool": True,
        "value_target": "score_diff_wide", "warm_from": str(args.warm_from),
        "trunk_transferred": len(transferred), "reinit_tensors": len(reinit),
        "freeze_trunk": bool(args.freeze_trunk), "train_steps": step,
        "provenance": "C-cheap value-only train (deck-aware fair value; policy=heuristic at play time)",
    }
    torch.save(ckpt, args.output)
    print(f"[done] wrote {args.output}")
    if len(epoch_train_mse) >= 2:
        e0, eN = epoch_train_mse[0], epoch_train_mse[-1]
        print(f"[done] epoch train_value_mse {e0:.5f} -> {eN:.5f} "
              f"({'DROPPED' if eN < e0 else 'did NOT drop — investigate'})")
    elif epoch_train_mse:
        print(f"[done] single-epoch train_value_mse={epoch_train_mse[0]:.5f} "
              "(run >=2 epochs / more --max-steps to see the trend)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
