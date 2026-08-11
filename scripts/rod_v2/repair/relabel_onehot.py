#!/usr/bin/env python3
"""Rebuild a hard-state training split with ONE-HOT policy targets on h6400's best
move (argmax), instead of the flat h6400 visit distribution. Zero new MCTS — uses the
already-stored h6400_choice from the manifest. The strongest possible target: kills
the 'you trained on a flat distribution' objection. Row-aligned: npz row i ↔ manifest
row i (both written from the same ordered list)."""
import sys, json, glob
from pathlib import Path
import numpy as np

M = Path("/home/doctor/projects/carcassone/measurement/hard_policy_repair")

def relabel(split):
    man = [json.loads(l) for l in open(M / f"manifest_{split}.jsonl")]
    src = sorted(glob.glob(str(M / "data" / split / "iter_00" / "seed_*.npz")))
    out_dir = M / "data" / f"{split}_onehot" / "iter_00"
    out_dir.mkdir(parents=True, exist_ok=True)
    gi = 0
    nbad = 0
    for f in src:
        d = dict(np.load(f))
        pol = np.zeros_like(d["policies"])
        masks = d["valid_masks"]
        for r in range(pol.shape[0]):
            h6 = man[gi]["h6400_choice"]
            if 0 <= h6 < pol.shape[1] and masks[r, h6]:
                pol[r, h6] = 1.0
            else:
                # fallback: shouldn't happen (h6400_choice is always legal)
                legal = np.flatnonzero(masks[r]); pol[r, legal] = 1.0/len(legal); nbad += 1
            gi += 1
        d["policies"] = pol.astype(np.float32)
        np.savez_compressed(out_dir / Path(f).name, **d)
    print(f"  {split}: relabeled {gi} rows -> {out_dir}  ({nbad} fallback)")

for s in ("train",):
    relabel(s)
print("done")
