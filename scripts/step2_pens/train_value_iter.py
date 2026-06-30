#!/usr/bin/env python3
"""Step-2 "PeNS" IN-LOOP ScalarMLP value RETRAIN (MEASUREMENT ONLY).

The per-iter value-head retrain for the weaned flywheel. Reads the self-play
.npz that gen_step2.py wrote this iter, pulls the per-ply 89-vec PeNS features +
the per-ply `score_diff_wide` value target, and trains the SAME `ScalarMLP`
(imported from train_warmstart.py) with **plain MSE on score_diff_wide** —
mirroring train_iter.py's `F.mse_loss(value_pred, value_b)`. It warm-starts from
the previous iter's scalar checkpoint (`--warm-from`, default warmstart.pt) and
saves the new checkpoint in the EXACT format warmstart.pt uses, so gen_step2.py's
`--scalar-ckpt` loads it unchanged for the next iter.

Normalization is held FIXED to the warm-from's `col_mean`/`col_std` (NOT
recomputed per-iter) — keeping the z-score frame identical across the whole run
so the wean is a clean lever (a drifting normalization would confound the blend
schedule). The arch (D / hidden / blocks) is also taken from the warm-from so the
state_dict always loads.

========================================================================
THE SEAM with gen_step2.py (the sibling agent owns gen_step2.py; field NAMES may
differ slightly — this is the ONE integration point to reconcile at the smoke):
  * FEATURE field  — the per-ply 89-vec PeNS scalars, shape (n, 89). We try, in
    order, the names in FEAT_FIELD_CANDIDATES (default ['step2_feats',
    'child_scalars', 'pens_feats', 'feat89']). Override with --feat-field.
  * VALUE  field   — score_diff_wide = tanh((p0-p1)/40), current-player POV,
    shape (n,). We try VALUE_FIELD_CANDIDATES (default ['values', 'value']).
    Override with --value-field.
If NEITHER a feature field NOR the value field is present in the .npz, we FAIL
LOUDLY naming exactly what we looked for and what the file actually contains, so
the reconcile is a one-line --feat-field / --value-field fix, not a silent wrong
train. We do NOT block on the exact name.
========================================================================

  python -u scripts/step2_pens/train_value_iter.py \
      --gen-dir /mnt/c/carc-shared/step2_pens/iter02_data/iter_00 \
      --warm-from /home/doctor/carc_step2_pens/warmstart/warmstart.pt \
      --out /mnt/c/carc-shared/step2_pens/scalar/iter_02.pt \
      --epochs 6
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO = Path(__file__).resolve().parent.parent.parent

# Import ScalarMLP from THIS package's train_warmstart.py explicitly by path —
# scripts/train_warmstart.py (a different file, no ScalarMLP) is also importable
# and would shadow a plain `import train_warmstart` (same trick gen_step2.py uses).
_tw_spec = _ilu.spec_from_file_location(
    "step2_train_warmstart", str(REPO / "scripts" / "step2_pens" / "train_warmstart.py")
)
_tw = _ilu.module_from_spec(_tw_spec)
_tw_spec.loader.exec_module(_tw)
ScalarMLP = _tw.ScalarMLP  # the EXACT arch the warmstart trainer / gen_step2 use

# --- THE SEAM: documented field-name constants (easy to fix at integration) --- #
# gen_step2.py persists the per-ply 89-vec + value target; the sibling agent may
# name the feature field slightly differently. We probe these in order.
FEAT_FIELD_CANDIDATES = ["pens_features", "step2_feats", "child_scalars", "pens_feats", "feat89"]
VALUE_FIELD_CANDIDATES = ["value_target", "values", "value"]


def _pick_field(npz_files: list[Path], candidates: list[str], override: str | None):
    """Return the first field name present in the FIRST loadable .npz. If an
    override is given it MUST be present (else loud error)."""
    if not npz_files:
        return None, []
    with np.load(npz_files[0], allow_pickle=False) as z:
        present = list(z.files)
    if override:
        if override not in present:
            raise SystemExit(
                f"FATAL: --field override '{override}' not in {npz_files[0].name}; "
                f"fields present = {present}"
            )
        return override, present
    for c in candidates:
        if c in present:
            return c, present
    return None, present


def _load_gen(gen_dir: Path, feat_field: str | None, value_field: str | None):
    """Glob gen .npz, read the per-ply 89-vec + value target by name, concat.

    TOLERATES the seam: if the resolved feature/value field is missing, raises a
    SystemExit naming exactly what was expected and what the file contains."""
    # gen_step2.py writes a companion seed_*_pens.npz holding the per-ply 89-vec
    # (pens_features) + value_target; the main seed_*.npz is the ResNet GameDataset
    # (no 89-vec). PREFER the companion files.
    files = sorted(gen_dir.glob("*_pens.npz"))
    if not files:
        files = sorted(gen_dir.glob("seed_*.npz"))
    if not files:
        # also accept a flat dir of *.npz (some gen layouts)
        files = sorted(p for p in gen_dir.glob("*.npz") if not p.name.startswith("."))
    if not files:
        raise SystemExit(f"FATAL: no gen .npz under {gen_dir} (looked for seed_*.npz / *.npz)")

    ff, present = _pick_field(files, FEAT_FIELD_CANDIDATES, feat_field)
    vf, _ = _pick_field(files, VALUE_FIELD_CANDIDATES, value_field)
    if ff is None:
        raise SystemExit(
            "FATAL: could not find the per-ply 89-vec PeNS feature array in the gen .npz.\n"
            f"  looked for (in order): {FEAT_FIELD_CANDIDATES}\n"
            f"  fields actually present in {files[0].name}: {present}\n"
            "  --> reconcile the seam: pass --feat-field <name> (the sibling agent's "
            "gen_step2.py field for the (n,89) per-ply scalars)."
        )
    if vf is None:
        raise SystemExit(
            "FATAL: could not find the per-ply value target (score_diff_wide) in the gen .npz.\n"
            f"  looked for (in order): {VALUE_FIELD_CANDIDATES}\n"
            f"  fields actually present in {files[0].name}: {present}\n"
            "  --> reconcile the seam: pass --value-field <name>."
        )

    feats, vals = [], []
    n_rows = 0
    for f in files:
        with np.load(f, allow_pickle=False) as z:
            if ff not in z.files or vf not in z.files:
                # a straggler/older file missing the field — skip with a note, do
                # not corrupt the train silently.
                print(f"  [skip] {f.name}: missing {ff!r} or {vf!r} (has {list(z.files)})", flush=True)
                continue
            x = np.asarray(z[ff]).astype(np.float32)
            y = np.asarray(z[vf]).astype(np.float32).reshape(-1)
            if x.ndim != 2:
                raise SystemExit(f"FATAL: {f.name}[{ff}] has shape {x.shape}, expected (n, D)")
            if x.shape[0] != y.shape[0]:
                raise SystemExit(
                    f"FATAL: {f.name}: feature rows {x.shape[0]} != value rows {y.shape[0]} "
                    f"({ff!r} vs {vf!r} are not row-aligned)"
                )
            feats.append(x)
            vals.append(y)
            n_rows += x.shape[0]
    if not feats:
        raise SystemExit(f"FATAL: every gen .npz under {gen_dir} was missing {ff!r}/{vf!r}")
    X = np.concatenate(feats, axis=0)
    Y = np.concatenate(vals, axis=0)
    return X, Y, ff, vf, len(files)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="train_value_iter")
    ap.add_argument("--gen-dir", required=True,
                    help="Dir of this iter's gen .npz (globs seed_*.npz / *.npz). The "
                         "89-vec PeNS features + score_diff_wide value target are read here.")
    ap.add_argument("--warm-from", required=True,
                    help="Previous iter's ScalarMLP ckpt (warmstart.pt format). The arch "
                         "AND the FIXED col_mean/col_std normalization are taken from here.")
    ap.add_argument("--out", required=True, help="Output ScalarMLP ckpt (.pt, warmstart format).")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--val-fraction", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    # --- the seam overrides (default = auto-probe FEAT/VALUE_FIELD_CANDIDATES) --- #
    ap.add_argument("--feat-field", default=None,
                    help="Override the gen-npz per-ply 89-vec field name "
                         f"(auto-probe order: {FEAT_FIELD_CANDIDATES}).")
    ap.add_argument("--value-field", default=None,
                    help="Override the gen-npz value-target field name "
                         f"(auto-probe order: {VALUE_FIELD_CANDIDATES}).")
    args = ap.parse_args(argv)

    dev = torch.device(args.device)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    # ---- warm-from: arch + FIXED normalization (do NOT recompute per-iter) ---- #
    wf = torch.load(args.warm_from, map_location="cpu", weights_only=False)
    D = int(wf["D"])
    hidden = int(wf["hidden"])
    blocks = int(wf["blocks"])
    feat_names = [str(x) for x in wf["feat_names"]]
    col_mean = np.asarray(wf["col_mean"], np.float32)
    col_std = np.asarray(wf["col_std"], np.float32)
    col_std = np.where(col_std < 1e-6, 1.0, col_std).astype(np.float32)
    print(f"[warm-from] {args.warm_from}  D={D} hidden={hidden} blocks={blocks} "
          f"(normalization HELD FIXED from warm-from)", flush=True)

    # ---- gen data (the seam) ---- #
    X, Y, ff, vf, n_files = _load_gen(Path(args.gen_dir), args.feat_field, args.value_field)
    if X.shape[1] != D:
        raise SystemExit(
            f"FATAL: gen feature width {X.shape[1]} (field {ff!r}) != warm-from D={D}. "
            "The 89-vec column count must match the warmstart MLP exactly."
        )
    print(f"[gen] {n_files} files -> {X.shape[0]} plies, D={X.shape[1]} "
          f"(feat_field={ff!r}, value_field={vf!r}); "
          f"value range [{Y.min():+.3f},{Y.max():+.3f}] mean {Y.mean():+.3f}", flush=True)

    # z-score with the FIXED normalization
    Xn = (X - col_mean) / col_std
    Xt = torch.from_numpy(Xn.astype(np.float32))
    Yt = torch.from_numpy(Y.astype(np.float32))

    # train/val split (row-level; MSE is per-row so no group structure needed)
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(X.shape[0])
    n_val = int(round(args.val_fraction * X.shape[0]))
    val_idx = perm[:n_val]
    tr_idx = perm[n_val:]
    do_val = n_val >= args.batch_size or (0 < n_val < args.batch_size and n_val >= 2)
    print(f"[split] train {len(tr_idx)} / val {len(val_idx)} rows "
          f"(val_fraction={args.val_fraction})", flush=True)

    # ---- model: warm-start from the previous scalar ckpt ---- #
    net = ScalarMLP(D, hidden=hidden, blocks=blocks).to(dev)
    net.load_state_dict(wf["state_dict"])
    n_params = sum(p.numel() for p in net.parameters())
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    print(f"[model] ScalarMLP D={D} params={n_params/1e3:.0f}k warm-started on {dev}", flush=True)

    def run(idx, train):
        net.train(train)
        order = rng.permutation(idx) if train else idx
        tot = 0.0
        nb = 0
        for b0 in range(0, len(order), args.batch_size):
            sel = order[b0:b0 + args.batch_size]
            if train and len(sel) < 2:
                continue  # BatchNorm1d needs >=2 in train mode
            xb = Xt[sel].to(dev)
            yb = Yt[sel].to(dev)
            with torch.set_grad_enabled(train):
                pred = net(xb)
                loss = F.mse_loss(pred, yb)  # mirrors train_iter.py value MSE
                if train:
                    opt.zero_grad(set_to_none=True)
                    loss.backward()
                    opt.step()
            tot += float(loss.detach())
            nb += 1
        return tot / max(nb, 1)

    metrics = {"warm_from": str(args.warm_from), "gen_dir": str(args.gen_dir),
               "feat_field": ff, "value_field": vf, "n_files": n_files,
               "n_train": int(len(tr_idx)), "n_val": int(len(val_idx)),
               "D": D, "hidden": hidden, "blocks": blocks, "epochs": []}
    for ep in range(args.epochs):
        t0 = time.time()
        tl = run(tr_idx, True)
        vl = run(val_idx, False) if do_val else float("nan")
        metrics["epochs"].append({"epoch": ep + 1, "train_mse": round(tl, 6),
                                  "val_mse": (round(vl, 6) if do_val else None),
                                  "sec": round(time.time() - t0, 1)})
        vstr = f" val_mse={vl:.5f}" if do_val else ""
        print(f"  ep{ep+1}/{args.epochs} train_mse={tl:.5f}{vstr} ({time.time()-t0:.0f}s)", flush=True)

    # ---- save in the EXACT warmstart.pt format (gen_step2 --scalar-ckpt loads it) ---- #
    torch.save({
        "state_dict": net.state_dict(),
        "D": int(D), "feat_names": feat_names,
        "col_mean": col_mean, "col_std": col_std,
        "hidden": hidden, "blocks": blocks,
        "arch": "ScalarMLP",
        "rank_temp": wf.get("rank_temp", 0.25),
        "v29_hash": wf.get("v29_hash"),
        # provenance for the in-loop retrain (not read by gen; just lineage)
        "step2_value_retrain": {
            "warm_from": str(args.warm_from), "gen_dir": str(args.gen_dir),
            "feat_field": ff, "value_field": vf, "epochs": args.epochs,
            "n_train": int(len(tr_idx)), "loss": "mse_score_diff_wide",
        },
    }, outp)
    (outp.with_suffix(".value_metrics.json")).write_text(json.dumps(metrics, indent=2))
    print(f"\n[saved] {outp}  (+ {outp.with_suffix('.value_metrics.json').name}) "
          f"— warmstart format, normalization preserved", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
