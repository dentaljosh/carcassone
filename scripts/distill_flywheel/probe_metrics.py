#!/usr/bin/env python3
"""Distill-flywheel per-iter DISTILLATION-FIDELITY probe (DESIGN §4.2 / §6).

Pure forward pass (NO games): load a checkpoint + the FROZEN probe shards
(``probe_data/iter_00/seed_*.npz``, champion-generated, never trained on) and
report how faithfully the net imitates the champion on that fixed set:

  * probe_ce  — mean policy cross-entropy  −Σ π_champ·log p_net  over the
                legal-masked softmax, on aux_mask (full-trajectory) rows only;
  * top1      — top-1 agreement: argmax(π_champ) == argmax(p_net) over legal;
  * value_mse — MSE(net value, stored champion score_diff value);
  * value_r   — Pearson r of the same.

Appends one JSON line ``{iter, ckpt_sha, n_rows, probe_ce, top1, value_mse,
value_r}`` to ``$OUT/probe_metrics.jsonl``. This is the no-eval distillation
ruler — FIXED data, comparable across all iters (unlike train_iter's rotating
val split). Runs in <2 min on the local GPU; called by the driver after train.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.warmstart import GameDataset


def _sha12(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _load_net(ckpt_path: Path, device: torch.device) -> CarcassonneNet:
    ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_input_channels=int(ckpt.get("n_input_channels", N_CHANNELS)),
        n_scalar_features=int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
        value_global_pool=bool(ckpt.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net


def _load_probe(probe_dir: Path):
    shards = sorted(probe_dir.glob("seed_*.npz"))
    if not shards:
        raise SystemExit(f"FATAL: no probe shards under {probe_dir}")
    boards, scalars, policies, values, masks, aux = [], [], [], [], [], []
    for s in shards:
        ds = GameDataset.load(s)
        boards.append(ds.boards)
        scalars.append(ds.scalars)
        policies.append(ds.policies)
        values.append(ds.values)
        masks.append(ds.valid_masks)
        aux.append(np.asarray(ds.aux_mask, dtype=bool))
    return (
        np.concatenate(boards).astype(np.float32),
        np.concatenate(scalars).astype(np.float32),
        np.concatenate(policies).astype(np.float32),
        np.concatenate(values).astype(np.float32),
        np.concatenate(masks).astype(bool),
        np.concatenate(aux),
        len(shards),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="distill-flywheel probe metrics")
    ap.add_argument("--iter", type=int, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--probe-dir", type=Path, required=True,
                    help="dir of frozen champion probe shards (seed_*.npz)")
    ap.add_argument("--out", type=Path, required=True,
                    help="dir; appends probe_metrics.jsonl here")
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    device = torch.device(args.device)
    net = _load_net(args.ckpt, device)
    boards, scalars, policies, values, masks, aux, n_shards = _load_probe(args.probe_dir)
    n_rows = int(boards.shape[0])

    ce_sum = 0.0
    top1_hits = 0
    aux_count = 0
    v_net = np.empty(n_rows, dtype=np.float64)
    pol_arg = np.argmax(policies, axis=1)  # champ argmax (pol is 0 off-legal)

    with torch.no_grad():
        for lo in range(0, n_rows, args.batch):
            hi = min(lo + args.batch, n_rows)
            b = torch.from_numpy(boards[lo:hi]).to(device)
            s = torch.from_numpy(scalars[lo:hi]).to(device)
            m = torch.from_numpy(masks[lo:hi]).to(device)
            logits, value = net(b, s)
            priors = net.policy_softmax_with_mask(logits, m)  # (k, A), 0 off-legal
            v_net[lo:hi] = value.reshape(-1).double().cpu().numpy()

            a = torch.from_numpy(aux[lo:hi]).to(device)
            if a.any():
                pol = torch.from_numpy(policies[lo:hi]).to(device)
                logp = torch.log(priors.clamp_min(1e-12))
                ce = -(pol * logp).sum(dim=1)  # (k,)
                ce_sum += float(ce[a].sum().item())
                net_arg = priors.argmax(dim=1).cpu().numpy()
                ax = aux[lo:hi]
                top1_hits += int((net_arg[ax] == pol_arg[lo:hi][ax]).sum())
                aux_count += int(a.sum().item())

    probe_ce = ce_sum / aux_count if aux_count else float("nan")
    top1 = top1_hits / aux_count if aux_count else float("nan")
    v_champ = values.astype(np.float64)
    value_mse = float(np.mean((v_net - v_champ) ** 2))
    if np.std(v_net) > 0 and np.std(v_champ) > 0:
        value_r = float(np.corrcoef(v_net, v_champ)[0, 1])
    else:
        value_r = float("nan")

    rec = {
        "iter": args.iter,
        "ckpt_sha": _sha12(args.ckpt),
        "n_rows": n_rows,
        "n_aux_rows": aux_count,
        "n_shards": n_shards,
        "probe_ce": round(probe_ce, 6),
        "top1": round(top1, 6),
        "value_mse": round(value_mse, 6),
        "value_r": round(value_r, 6),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "probe_metrics.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
