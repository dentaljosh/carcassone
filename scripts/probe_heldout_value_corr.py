"""Held-out value-head correlation gate (the overfitting verdict, 2026-06-04).

Loads a real CarcassonneNet checkpoint, runs ITS value head over a held-out
set of OUTCOME-target self-play games, and reports Pearson corr between the
head's prediction and the TRUE game margin recovered from the held-out targets
(margin = SCALE * atanh(clip(value))).

This is THE gate for the in-loop search-value retrain (docs/IN_LOOP_SEARCHVALUE_
BUILD_2026-06-04.md step 6a): iter_01's outcome-trained head scores ~0.32 on
held-out (vs 0.79 on its own training games — the overfitting signature, and
below v2.7's ~0.4-0.65). A search-value-trained head that jumps toward v2.7's
level means the overfitting is fixed.

MEMORY: streams one .npz at a time via make_streaming_dataset + a DataLoader
(the same memory-safe path train_iter uses) and accumulates only the scalar
Pearson sufficient statistics. Loading every file into RAM OOMs the 31 GB 5800x
at ~1200 games (the 2026-06-04 crash) — never do that. Use --max-games to bound
the held-out size; a few hundred games is plenty for a stable corr.

IMPORTANT: the held-out set MUST be OUTCOME-target data (score_diff /
score_diff_wide), so atanh recovers a true margin. Pearson corr is invariant to
the linear margin scale, so /15 vs /40 (score_diff vs _wide) does not change the
reported number — SCALE only affects the printed margin range, not the corr.

Usage:
  python -u scripts/probe_heldout_value_corr.py \
      --checkpoint /mnt/c/carc-shared/stage_b/ckpt/iter_01.pt \
      --data-dir /mnt/c/carc-shared/stage_b \
      --iters 5 --max-games 200      # held-out iter(s), capped for memory/speed
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.warmstart import make_streaming_dataset


class _PearsonAccum:
    """Streaming Pearson accumulator (sums only; O(1) memory)."""

    def __init__(self) -> None:
        self.n = 0
        self.sx = self.sy = self.sxx = self.syy = self.sxy = 0.0

    def update(self, x: np.ndarray, y: np.ndarray) -> None:
        x = x.astype(np.float64)
        y = y.astype(np.float64)
        self.n += x.size
        self.sx += x.sum()
        self.sy += y.sum()
        self.sxx += (x * x).sum()
        self.syy += (y * y).sum()
        self.sxy += (x * y).sum()

    def corr(self) -> float:
        if self.n < 2:
            return float("nan")
        cov = self.sxy - self.sx * self.sy / self.n
        vx = self.sxx - self.sx * self.sx / self.n
        vy = self.syy - self.sy * self.sy / self.n
        if vx <= 0 or vy <= 0:
            return float("nan")
        return cov / math.sqrt(vx * vy)


def _collect_files(data_dir: Path, iters: list[int] | None) -> list[Path]:
    if iters is not None:
        files: list[Path] = []
        for i in iters:
            d = data_dir / f"iter_{i:02d}"
            files.extend(sorted(d.glob("seed_*.npz")))
        return files
    flat = sorted(data_dir.glob("seed_*.npz"))
    if flat:
        return flat
    return sorted(data_dir.glob("iter_*/seed_*.npz"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="probe_heldout_value_corr")
    p.add_argument("--checkpoint", type=Path, required=True, nargs="+",
                   help="One or more checkpoints. Multiple → evaluated on the "
                        "SAME streamed held-out batches (identical positions, one "
                        "CIFS pass) and printed as a comparison table — the clean "
                        "apples-to-apples gate (e.g. iter_01 vs the new head).")
    p.add_argument("--data-dir", type=Path, required=True,
                   help="Held-out OUTCOME-target data root (e.g. stage_b/).")
    p.add_argument("--iters", type=int, nargs="*", default=None,
                   help="Iter subdir indices to use as held-out (e.g. 5). Omit "
                        "to use seed_*.npz directly under --data-dir.")
    p.add_argument("--max-games", type=int, default=200,
                   help="Cap held-out games (files) loaded; bounds memory + time. "
                        "0 = all (DANGER: 1200 games OOMs the 31 GB 5800x).")
    p.add_argument("--scale", type=float, default=15.0,
                   help="Margin recovery scale: margin=scale*atanh(value). 15 for "
                        "score_diff, 40 for score_diff_wide. Does NOT affect corr "
                        "(linear) — only the printed margin range.")
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--num-workers", type=int, default=4,
                   help="DataLoader workers (parallel CIFS .npz IO).")
    args = p.parse_args(argv)

    files = _collect_files(args.data_dir, args.iters)
    if not files:
        print(f"ERROR: no .npz under {args.data_dir} (iters={args.iters})",
              file=sys.stderr)
        return 1
    if args.max_games and len(files) > args.max_games:
        # Deterministic subsample across the file list (spread, not the first K).
        idx = np.linspace(0, len(files) - 1, args.max_games).round().astype(int)
        files = [files[i] for i in dict.fromkeys(idx.tolist())]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    nets = []
    labels = []
    for cpath in args.checkpoint:
        ck = torch.load(cpath, map_location=device, weights_only=False)
        net = CarcassonneNet(
            n_filters=int(ck["n_filters"]),
            n_blocks=int(ck["n_blocks"]),
            n_scalar_features=int(ck.get("n_scalar_features", N_SCALAR_FEATURES)),
        ).to(device)
        net.load_state_dict(ck["model_state"])
        net.train(False)
        nets.append(net)
        labels.append(f"{cpath.parent.name}/{cpath.stem}")

    ds = make_streaming_dataset(
        files, shuffle_files_each_epoch=False, shuffle_within_file=False, seed=0
    )
    loader = DataLoader(
        ds, batch_size=args.batch_size, num_workers=args.num_workers,
        persistent_workers=False, pin_memory=(device.type == "cuda"),
    )

    # One accumulator pair per net; all share the SAME streamed batches.
    acc_margin = [_PearsonAccum() for _ in nets]
    acc_raw = [_PearsonAccum() for _ in nets]
    pred_rng = [(math.inf, -math.inf) for _ in nets]
    n_pos = 0
    mmin, mmax = math.inf, -math.inf
    n_sat = 0
    with torch.no_grad():
        for board_b, scalar_b, _pol, value_b, _mask, _own, _aux in loader:
            board_b = board_b.to(device, non_blocking=True)
            scalar_b = scalar_b.to(device, non_blocking=True)
            tgt = value_b.flatten().double().numpy()
            margin = args.scale * np.arctanh(np.clip(tgt, -0.9999, 0.9999))
            for i, net in enumerate(nets):
                _, v, _ = net.forward_train(board_b, scalar_b)
                pred = v.flatten().double().cpu().numpy()
                acc_margin[i].update(pred, margin)
                acc_raw[i].update(pred, tgt)
                lo, hi = pred_rng[i]
                pred_rng[i] = (min(lo, pred.min()), max(hi, pred.max()))
            n_pos += tgt.size
            n_sat += int(np.sum(np.abs(tgt) > 0.9999))
            mmin, mmax = min(mmin, margin.min()), max(mmax, margin.max())

    print(f"held-out   : {len(files)} games, {n_pos} positions "
          f"(iters={args.iters if args.iters is not None else 'flat'}, "
          f"max_games={args.max_games})")
    print(f"target sat (|v|>0.9999): {n_sat / max(n_pos,1):.3%}  (atanh ceiling clip)")
    print(f"margin rng : [{mmin:+.1f}, {mmax:+.1f}] (scale={args.scale})")
    print()
    print(f"  {'checkpoint':<34} {'corr(MARGIN)':>13} {'corr(raw)':>11} "
          f"{'pred range':>18}")
    print(f"  {'-'*34} {'-'*13} {'-'*11} {'-'*18}")
    for i, lab in enumerate(labels):
        lo, hi = pred_rng[i]
        print(f"  {lab:<34} {acc_margin[i].corr():>+13.4f} "
              f"{acc_raw[i].corr():>+11.4f} {f'[{lo:+.2f}, {hi:+.2f}]':>18}")
    print()
    print("  gate: corr(value_head, TRUE MARGIN) — iter_01 held-out +0.289; "
          "v2.7 ~0.4-0.65. A search-value head BEATS +0.289 → overfitting fixed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
