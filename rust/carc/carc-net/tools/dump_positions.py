#!/usr/bin/env python3
"""Dump N real positions + torch REFERENCE priors into a flat binary the Rust
faithfulness harness reads.

WHY REAL POSITIONS. A faithfulness check on `torch.randn` inputs measures the
kernel, not the deployment. These positions come from the champion's own self-play
corpus (`/mnt/c/carc-shared/distill_strong_20260723/iter_03/*.npz`), which already
stores exactly the three arrays the evaluator contract needs — `boards
(N,81,25,25) f32`, `scalars (N,42) f32`, `valid_masks (N,2511) bool` — so no
re-encoding (and no chance of an encoder mismatch) enters the comparison.

WHY A FLAT BINARY. The Rust side must see byte-identical inputs to the ones torch
saw, or the residual it reports is a mixture of input drift and backend drift.
Little-endian f32/u8 with a tiny header is the least that can go wrong; masks are
one byte per entry rather than bit-packed for the same reason.

Layout (all little-endian):
    magic   "CARCPOS1"          8 bytes
    n       u32                 rows
    n_ch    u32
    window  u32
    n_sc    u32
    n_act   u32
    then, per row, contiguous:
        board   f32[n_ch*window*window]
        scalars f32[n_sc]
        mask    u8 [n_act]      (0/1)
        priors  f32[n_act]      TORCH REFERENCE, masked-softmax, illegal == 0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.network import CarcassonneNet  # noqa: E402

MAGIC = b"CARCPOS1"


def build(ckpt_path: Path):
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    net = CarcassonneNet(
        window_size=25,
        n_input_channels=ck["n_input_channels"],
        n_scalar_features=ck["n_scalar_features"],
        n_filters=ck["n_filters"],
        n_blocks=ck["n_blocks"],
        value_global_pool=ck["value_global_pool"],
    )
    net.load_state_dict(ck["model_state"])
    net.eval()
    return net, ck


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", type=Path,
                    default=Path("/mnt/c/carc-shared/distill_strong_20260723/iter_03"))
    ap.add_argument("--checkpoint", type=Path,
                    default=Path("/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=1200)
    a = ap.parse_args()

    net, ck = build(a.checkpoint)
    n_ch, n_sc = ck["n_input_channels"], ck["n_scalar_features"]

    boards, scalars, masks = [], [], []
    files = sorted(a.corpus_dir.glob("*.npz"))
    if not files:
        raise SystemExit(f"no .npz under {a.corpus_dir}")
    used = []
    for f in files:
        d = np.load(f)
        boards.append(d["boards"])
        scalars.append(d["scalars"])
        masks.append(d["valid_masks"])
        used.append(f.name)
        if sum(len(b) for b in boards) >= a.n:
            break

    B = np.concatenate(boards)[: a.n].astype(np.float32)
    S = np.concatenate(scalars)[: a.n].astype(np.float32)
    M = np.concatenate(masks)[: a.n]
    n = len(B)
    if n < a.n:
        print(f"WARNING: corpus yielded only {n} rows (asked {a.n})")

    # Torch reference, in the SAME chunking the rust side will not use — the
    # reference must be batch-independent, so take it at batch 1 where torch's own
    # reduction order is unambiguous.
    priors = np.zeros((n, M.shape[1]), dtype=np.float32)
    with torch.no_grad():
        for i in range(n):
            logits = net.forward_policy_only(
                torch.from_numpy(B[i:i + 1]), torch.from_numpy(S[i:i + 1]))
            mt = torch.from_numpy(M[i:i + 1].copy()).bool()
            priors[i] = net.policy_softmax_with_mask(logits, mt)[0].numpy()

    with open(a.out, "wb") as fh:
        fh.write(MAGIC)
        fh.write(struct.pack("<5I", n, n_ch, 25, n_sc, M.shape[1]))
        for i in range(n):
            fh.write(B[i].tobytes(order="C"))
            fh.write(S[i].tobytes(order="C"))
            fh.write(M[i].astype(np.uint8).tobytes(order="C"))
            fh.write(priors[i].tobytes(order="C"))

    legal = M.sum(axis=1)
    meta = {
        "schema": "carc-net-positions/v1",
        "n": int(n), "n_channels": int(n_ch), "window": 25,
        "n_scalars": int(n_sc), "action_size": int(M.shape[1]),
        "corpus_files": used,
        "checkpoint": str(a.checkpoint),
        "legal_moves": {"min": int(legal.min()), "median": float(np.median(legal)),
                        "mean": float(legal.mean()), "max": int(legal.max())},
        "sha256": hashlib.sha256(a.out.read_bytes()).hexdigest(),
        "bytes": a.out.stat().st_size,
    }
    Path(str(a.out) + ".json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
