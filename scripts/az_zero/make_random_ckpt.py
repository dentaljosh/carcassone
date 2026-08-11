#!/usr/bin/env python3
"""az_zero — build the TABULA-RASA (random-init) iter_-1 checkpoint.

The first true zero-start experiment in the project: an AlphaZero self-play loop
that begins from a RANDOMLY INITIALIZED network instead of the heuristic
warm-start (`m2_sighted/warmstart_sighted.pt`). This script mints that starting
checkpoint.

WHAT IT DOES:
  1. Loads the SIGHTED reference checkpoint (`--src`, default
     m2_sighted/warmstart_sighted.pt) ONLY to copy its architecture hyperparams
     and the checkpoint-dict metadata format that scripts/train_iter.py's
     `--warm-from` load path expects. The reference WEIGHTS are discarded.
  2. Seeds every RNG (`--seed`, default 20260724) and constructs a fresh
     CarcassonneNet with the SAME arch (81ch board / 42 scalars / 96x6 /
     value_global_pool). PyTorch's default module init draws the weights from the
     seeded RNG, so the result is reproducible.
  3. Saves the ckpt dict with the EXACT keys train_iter.py reads
     (n_filters, n_blocks, n_input_channels, n_scalar_features, sighted,
     include_farm_scalars, value_global_pool, model_state, baseline_policy_entropy)
     plus a provenance stamp marking it random-init.

The saved ckpt is a drop-in `--warm-from` / `--checkpoint` for train_iter.py,
run_selfplay_iter.py, and the eval harness — same format as any trained iter,
just with random weights.

Usage:
  CUDA_VISIBLE_DEVICES="" scripts/az_zero/make_random_ckpt.py \
      --src /mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt \
      --out /mnt/c/carc-shared/az_zero_20260724/ckpt/iter_-1_random.pt \
      --seed 20260724
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from carcassonne_ai.network import CarcassonneNet  # noqa: E402


DEFAULT_SRC = "/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt"
DEFAULT_OUT = "/mnt/c/carc-shared/az_zero_20260724/ckpt/iter_-1_random.pt"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make_random_ckpt")
    ap.add_argument("--src", type=str, default=DEFAULT_SRC,
                    help="Reference SIGHTED checkpoint whose ARCH + metadata format "
                         "are copied (weights discarded). Default: warmstart_sighted.pt")
    ap.add_argument("--out", type=str, default=DEFAULT_OUT,
                    help="Output random-init checkpoint path (iter_-1_random.pt).")
    ap.add_argument("--seed", type=int, default=20260724,
                    help="RNG seed for the random weight init (reproducible).")
    args = ap.parse_args(argv)

    # CPU-only: this is a tiny construct-and-save; never needs CUDA. (The caller
    # is expected to export CUDA_VISIBLE_DEVICES="" but we don't depend on it —
    # map_location='cpu' + a CPU net keeps us off the GPU regardless.)
    device = torch.device("cpu")

    src = Path(args.src)
    if not src.exists():
        print(f"FATAL: reference checkpoint missing: {src}", file=sys.stderr)
        return 1
    ref = torch.load(src, map_location=device, weights_only=False)

    # Copy the arch hyperparams from the reference (the sighted 81ch/42 96x6 net).
    n_filters = int(ref["n_filters"])
    n_blocks = int(ref["n_blocks"])
    n_input_channels = int(ref.get("n_input_channels", 81))
    n_scalar_features = int(ref.get("n_scalar_features", 42))
    sighted = bool(ref.get("sighted", True))
    include_farm_scalars = bool(ref.get("include_farm_scalars", False))
    value_global_pool = bool(ref.get("value_global_pool", True))

    # Seed EVERY RNG that touches weight init so the random net is reproducible.
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    # Fresh net — PyTorch default init draws from the seeded RNG. This is the
    # tabula-rasa net: no heuristic knowledge, random weights. The value head ends
    # in tanh (bounded [-1,1]); the masked policy softmax starts near-uniform.
    net = CarcassonneNet(
        n_filters=n_filters,
        n_blocks=n_blocks,
        n_input_channels=n_input_channels,
        n_scalar_features=n_scalar_features,
        value_global_pool=value_global_pool,
    ).to(device)
    net.train(False)

    # Sanity: the arch must match the reference weights' shapes, otherwise a later
    # --warm-from that expects this format would mis-load. (We don't load ref
    # weights; this just confirms we reproduced the same architecture.)
    ref_sd = ref["model_state"]
    new_sd = net.state_dict()
    if set(ref_sd.keys()) != set(new_sd.keys()):
        only_ref = sorted(set(ref_sd) - set(new_sd))[:5]
        only_new = sorted(set(new_sd) - set(ref_sd))[:5]
        print(f"FATAL: arch mismatch vs reference state_dict. "
              f"ref-only={only_ref} new-only={only_new}", file=sys.stderr)
        return 1
    for k in ref_sd:
        if ref_sd[k].shape != new_sd[k].shape:
            print(f"FATAL: shape mismatch at {k}: ref {tuple(ref_sd[k].shape)} "
                  f"!= new {tuple(new_sd[k].shape)}", file=sys.stderr)
            return 1

    prov = {
        "schema": "carcassonne-training-provenance/v1",
        "created_iter": "-1",
        "run_tag": "az_zero_tabula_rasa",
        "init": "random",
        "random_seed": args.seed,
        "arch_source": str(src),
        "note": ("TABULA-RASA (random-init) iter_-1 for the az_zero AlphaZero loop. "
                 "Weights are random (seeded); only the ARCH + metadata format are "
                 "copied from arch_source. No heuristic warm-start."),
        "value_target": "n/a (random init)",
        "policy_target": "n/a (random init)",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Atomic save (temp + rename), mirroring train_iter.py / warmstart.py.
    tmp = out.with_name(out.stem + ".partial.pt")
    torch.save(
        {
            "model_state": net.state_dict(),
            "n_filters": n_filters,
            "n_blocks": n_blocks,
            "n_input_channels": n_input_channels,
            "n_scalar_features": n_scalar_features,
            "sighted": sighted,
            "include_farm_scalars": include_farm_scalars,
            "value_global_pool": value_global_pool,
            "iter": -1,
            "epochs": 0,
            # No inherited entropy baseline: this is the ROOT of the lineage. Left
            # None so train_iter measures a fresh baseline at iter 0 IF the entropy
            # floor is enabled (the az_zero loop disables it — see DESIGN.md; a
            # random net's near-uniform policy makes the 0.5x floor false-trip as
            # the policy legitimately sharpens).
            "baseline_policy_entropy": None,
            "provenance": prov,
        },
        tmp,
    )
    tmp.replace(out)

    print(
        f"wrote {out}\n"
        f"  arch: {n_input_channels}ch / {n_scalar_features} scalars / "
        f"{n_filters}x{n_blocks} / value_global_pool={value_global_pool} / "
        f"sighted={sighted}\n"
        f"  params: {net.param_count():,}   seed: {args.seed}   init: RANDOM (tabula rasa)\n"
        f"  arch copied from: {src}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
