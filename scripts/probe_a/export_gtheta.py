#!/usr/bin/env python3
"""PROBE A — MILESTONE 2: export the torch-trained g_theta to the NUMPY leaf head.

The trainer (train_gtheta.py) fed z-scored features to a torch GTheta
(FEAT_DIM -> H -> 1, tanh hidden). The leaf hot path uses the NUMPY
structured_leaf.GThetaStub, which feeds RAW Cython features. So we FOLD the
per-column z-score normalization into the first linear layer:

    norm = (raw - mean) / std
    z1   = norm @ W1 + b1  =  raw @ (W1/std[:,None]) + (b1 - (mean/std) @ W1)
         = raw @ W1_folded + b1_folded

The exported .npz carries W1_folded,b1,W2,b2,tanh_scale so the numpy head
reproduces the torch head bit-close on RAW features. We then VERIFY:
  * numpy per-component == torch per-component (raw feats) to tight tolerance,
  * numpy v_leaf (tanh((running+sum)/15)) == torch v_leaf to tight tolerance,
on a batch of real boards drawn from the component dataset.

  nice -n 19 .venv/bin/python -u scripts/probe_a/export_gtheta.py \
      --ckpt /home/doctor/carc_probe_a/gtheta/gtheta.pt \
      --dataset /home/doctor/carc_probe_a/component_ds \
      --out-npz checkpoints/probe_a/gtheta_numpy.npz
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

import numpy as np
import torch

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "probe_a"))
from train_gtheta import GTheta, FEAT_DIM  # noqa: E402
import structured_leaf as SL  # noqa: E402


def fold_norm(sd, col_mean, col_std, p="fc"):
    """Return raw-feature numpy weights (W1_folded, b1, W2, b2) for a 2-layer MLP
    with layer prefix `p` (fc1/fc2). Folds the z-score norm into the first layer."""
    W1 = sd[f"{p}1.weight"].cpu().numpy().T.astype(np.float64)   # (in, H)
    b1 = sd[f"{p}1.bias"].cpu().numpy().astype(np.float64)       # (H,)
    W2 = sd[f"{p}2.weight"].cpu().numpy().T.astype(np.float64)   # (H, 1)
    b2 = sd[f"{p}2.bias"].cpu().numpy().astype(np.float64)       # (1,)
    m = col_mean.astype(np.float64); s = col_std.astype(np.float64)
    W1_folded = W1 / s[:, None]
    b1_folded = b1 - (m / s) @ W1
    return W1_folded, b1_folded, W2, b2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/home/doctor/carc_probe_a/gtheta/gtheta.pt")
    ap.add_argument("--dataset", default="/home/doctor/carc_probe_a/component_ds")
    ap.add_argument("--out-npz", default=str(REPO / "checkpoints" / "probe_a" / "gtheta_numpy.npz"))
    ap.add_argument("--n-verify", type=int, default=4000)
    args = ap.parse_args()

    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    sd = ck["state_dict"]
    hidden = int(ck["hidden"]); tanh_scale = float(ck.get("tanh_scale", 15.0))
    col_mean = np.asarray(ck["col_mean"], np.float32)
    col_std = np.asarray(ck["col_std"], np.float32)
    col_std = np.where(col_std < 1e-6, 1.0, col_std).astype(np.float32)
    assert hidden == 32, f"head hidden={hidden} != 32 (must match GThetaStub / speed bench)"

    W1f, b1f, W2, b2 = fold_norm(sd, col_mean, col_std)

    use_bag = bool(ck.get("use_bag", False))
    save_kw = dict(
        W1=W1f.astype(np.float32), b1=b1f.astype(np.float32),
        W2=W2.astype(np.float32), b2=b2.astype(np.float32),
        tanh_scale=np.float32(tanh_scale),
        col_mean=col_mean, col_std=col_std, hidden=np.int32(hidden),
        v29_hash=np.array(str(ck.get("v29_hash", "")), dtype="<U32"),
    )
    bW1f = None
    if use_bag:
        # fold the bag z-score norm into the bag head's first layer (raw bag in).
        bag_mean = np.asarray(ck["bag_mean"], np.float32)
        bag_std = np.asarray(ck["bag_std"], np.float32)
        bag_std = np.where(bag_std < 1e-6, 1.0, bag_std).astype(np.float32)
        bsd = ck["bag_state_dict"]
        bW1f, bb1f, bW2, bb2 = fold_norm(bsd, bag_mean, bag_std)
        save_kw.update(
            bag_W1=bW1f.astype(np.float32), bag_b1=bb1f.astype(np.float32),
            bag_W2=bW2.astype(np.float32), bag_b2=bb2.astype(np.float32),
            bag_mean=bag_mean, bag_std=bag_std,
        )

    outp = Path(args.out_npz); outp.parent.mkdir(parents=True, exist_ok=True)
    np.savez(outp, **save_kw)
    print(f"[export] {outp}  W1{W1f.shape} b1{b1f.shape} W2{W2.shape} b2{b2.shape} "
          f"tanh_scale={tanh_scale}  bag={'ON '+str(bW1f.shape) if use_bag else 'OFF'}")

    # ---- VERIFY numpy == torch on real boards. ----------------------------- #
    net = GTheta(FEAT_DIM, hidden)
    net.load_state_dict(sd); net.eval()
    npm = SL.GThetaStub.from_trained_npz(outp)

    from train_gtheta import BagHead  # noqa: E402
    bag_net = None
    if use_bag:
        bag_net = BagHead(32, int(ck["bag_hidden"]))
        bag_net.load_state_dict(ck["bag_state_dict"]); bag_net.eval()

    z = np.load(Path(args.dataset) / "component_ds.npz", allow_pickle=False)
    feat = z["feat"].astype(np.float32)            # RAW features (Ncomp, 24)
    offsets = z["board_offsets"].astype(np.int64)
    running = z["running_diff"].astype(np.float32)
    cloister = z["cloister_slice"].astype(np.float32)   # exact cloister offset
    nb = len(offsets) - 1
    # the leaf's exact offset: running (+cloister when bag mode pulled it out).
    offset_exact = (running + cloister) if use_bag else running
    if use_bag:
        bagt = np.load(Path(args.dataset) / "bag_sidetable.npz")["bag"].astype(np.float32)
        bag_mean = np.asarray(ck["bag_mean"], np.float32); bag_std = np.asarray(ck["bag_std"], np.float32)
        bag_std = np.where(bag_std < 1e-6, 1.0, bag_std)
        bag_norm = (bagt - bag_mean) / bag_std
    rng = np.random.default_rng(0)
    sel = rng.choice(nb, size=min(args.n_verify, nb), replace=False)

    max_comp_err = 0.0; max_leaf_err = 0.0; max_bag_err = 0.0
    feat_norm = (feat - col_mean) / col_std
    with torch.no_grad():
        for b in sel:
            sl = slice(int(offsets[b]), int(offsets[b + 1]))
            raw = feat[sl]
            g_np = npm.per_component(raw)
            g_t = net(torch.from_numpy(feat_norm[sl])).numpy()
            max_comp_err = max(max_comp_err, float(np.abs(g_np - g_t).max()) if len(g_np) else 0.0)
            # bag scalar (numpy on raw bag; torch on normalized bag).
            raw_bag = bagt[b] if use_bag else None
            bs_np = npm.bag_scalar(raw_bag) if use_bag else 0.0
            if use_bag:
                bs_t = float(bag_net(torch.from_numpy(bag_norm[b:b+1].astype(np.float32)))[0].item())
                max_bag_err = max(max_bag_err, abs(bs_np - bs_t))
            else:
                bs_t = 0.0
            # enriched leaf value: tanh((offset_exact + sum g + bag_scalar)/scale).
            v_np = npm.aggregate_with_offset(raw, float(offset_exact[b]),
                                             0.0, raw_bag)  # cloister already in offset_exact
            v_t = math.tanh((float(offset_exact[b]) + float(g_t.sum()) + bs_t) / tanh_scale)
            max_leaf_err = max(max_leaf_err, abs(v_np - v_t))

    print(f"[verify] over {len(sel)} boards (bag={'ON' if use_bag else 'OFF'}):")
    print(f"  max |numpy_per_component - torch_per_component| = {max_comp_err:.3e}")
    if use_bag:
        print(f"  max |numpy_bag_scalar    - torch_bag_scalar|    = {max_bag_err:.3e}")
    print(f"  max |numpy_v_leaf        - torch_v_leaf|        = {max_leaf_err:.3e}")
    ok = (max_comp_err < 1e-4) and (max_leaf_err < 1e-5) and (max_bag_err < 1e-4)
    print(f"  numpy==torch: {'PASS' if ok else 'FAIL'} "
          f"(tol comp<1e-4, bag<1e-4, leaf<1e-5)")
    if not ok:
        sys.exit(1)

    meta = {
        "ckpt": args.ckpt, "out_npz": str(outp), "hidden": hidden,
        "tanh_scale": tanh_scale, "n_verified": int(len(sel)), "use_bag": use_bag,
        "max_comp_err": max_comp_err, "max_bag_err": max_bag_err,
        "max_leaf_err": max_leaf_err, "numpy_eq_torch": bool(ok),
    }
    (outp.parent / "export_verify.json").write_text(json.dumps(meta, indent=2))
    print(f"-> {outp}  (+ export_verify.json)")


if __name__ == "__main__":
    main()
