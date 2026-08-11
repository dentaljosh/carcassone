#!/usr/bin/env python3
"""C-cheap v2 Stage-3 OFFLINE kill-gate (free; run before any eval compute).

The residual net predicts r̂ ≈ z − tanh(leaf/15). At play time the value is
``leaf_tanh + λ·r̂``; the target is the outcome ``z``. So the blended value's
error against the outcome is:

    blended_MSE(λ) = mean( (λ·r̂ − residual)² )      # residual = z − leaf_tanh = the stored `values`
    null_MSE       = mean( residual² )               # λ=0 → predict-zero-residual = the HEURISTIC leaf alone

The net EARNS an online eval iff, on the HELD-OUT val shards (same split as the
trainer), the blended value beats the heuristic-alone null for some λ — AND the
deck-aware net (A) beats the bag-blind control (B), else the signal isn't
deck-awareness. If A can't beat null offline, it cannot out-PLAY the leaf in the
loop (a value that can't out-rank the leaf offline never out-plays it — the
value-inertness ledger). KILL without playing a single game.

Usage:
  kill_gate_blend.py --net-a value_A.pt [--net-b value_B_zerobag.pt] \
     --data-root /mnt/c/carc-shared/c_cheap_fairgen_v2 [--lambdas 0.1,0.25,0.5]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.warmstart import iter_game_dataset_files, split_files_train_val  # noqa: E402


def _load_net(path):
    ck = torch.load(path, map_location="cpu", weights_only=False)
    net = CarcassonneNet(
        n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
        n_input_channels=ck["n_input_channels"], n_scalar_features=ck["n_scalar_features"],
        value_global_pool=ck.get("value_global_pool", False),
    )
    net.load_state_dict(ck["model_state"]); net.eval()
    return net, ck


def _predict_residuals(net, val_files, zero_bag, batch=2048, device="cpu"):
    """Return (r_hat, residual_target) concatenated over all val plies."""
    net.to(device)
    preds, tgts = [], []
    for f in val_files:
        d = np.load(f)
        boards = d["boards"].astype(np.float32)          # (N,81,W,W)
        scalars = d["scalars"].astype(np.float32).copy()  # (N,42)
        values = d["values"].astype(np.float32)           # (N,) = residual target
        if zero_bag:
            scalars[:, 10:42] = 0.0                        # deck-BLIND control (match training)
        with torch.no_grad():
            for i in range(0, boards.shape[0], batch):
                b = torch.from_numpy(boards[i:i+batch]).to(device)
                s = torch.from_numpy(scalars[i:i+batch]).to(device)
                _logits, v = net(b, s)
                preds.append(v.reshape(-1).cpu().numpy())
        tgts.append(values)
    return np.concatenate(preds), np.concatenate(tgts)


def _report(label, r_hat, residual, lambdas):
    null_mse = float(np.mean(residual ** 2))
    corr = float(np.corrcoef(r_hat, residual)[0, 1]) if r_hat.std() > 0 else float("nan")
    print(f"\n=== {label} ===  (n={len(residual)})")
    print(f"  null_MSE (heuristic leaf alone, predict-0-residual): {null_mse:.5f}")
    print(f"  corr(r_hat, residual): {corr:+.3f}   r_hat std {r_hat.std():.4f}")
    best = None
    for lam in lambdas:
        blended = float(np.mean((lam * r_hat - residual) ** 2))
        impr = null_mse - blended
        pct = 100.0 * impr / null_mse if null_mse > 0 else 0.0
        flag = "BEATS null" if blended < null_mse else "worse-than-null"
        print(f"  λ={lam:<4}: blended_MSE {blended:.5f}  Δ vs null {impr:+.5f} ({pct:+.2f}%)  {flag}")
        if best is None or blended < best[1]:
            best = (lam, blended, impr)
    return null_mse, best  # best = (lam, mse, improvement)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kill_gate_blend")
    ap.add_argument("--net-a", type=Path, required=True, help="deck-aware full sighted net")
    ap.add_argument("--net-b", type=Path, default=None, help="bag-blind control net (trained --zero-bag-scalars)")
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--lambdas", type=str, default="0.1,0.25,0.5")
    ap.add_argument("--val-fraction", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args(argv)
    lambdas = [float(x) for x in args.lambdas.split(",")]

    files = list(iter_game_dataset_files(args.data_root))
    if not files:
        raise SystemExit(f"no shards under {args.data_root}")
    # SAME split the trainer uses (by shard, same seed) -> honest held-out val.
    _train_files, val_files = split_files_train_val(files, val_fraction=args.val_fraction, seed=args.seed)
    print(f"[data] {len(files)} shards -> {len(val_files)} val shards (held out, seed={args.seed})")

    netA, _ = _load_net(args.net_a)
    rA, resid = _predict_residuals(netA, val_files, zero_bag=False, device=args.device)
    nullA, bestA = _report("A: deck-aware (full sighted)", rA, resid, lambdas)

    verdict = f"A best λ={bestA[0]} improves null by {bestA[2]:+.5f}"
    a_beats_null = bestA[2] > 0
    if args.net_b:
        netB, _ = _load_net(args.net_b)
        rB, residB = _predict_residuals(netB, val_files, zero_bag=True, device=args.device)
        nullB, bestB = _report("B: bag-BLIND control (--zero-bag-scalars)", rB, residB, lambdas)
        a_beats_b = bestA[2] > bestB[2]
        print("\n" + "=" * 70)
        print(f"KILL-GATE: A beats null? {'YES' if a_beats_null else 'NO'}  "
              f"({bestA[2]:+.5f})  |  A's gain > B's gain (deck-awareness)? "
              f"{'YES' if a_beats_b else 'NO'}  (A {bestA[2]:+.5f} vs B {bestB[2]:+.5f})")
        proceed = a_beats_null and a_beats_b
    else:
        print("\n" + "=" * 70)
        print(f"KILL-GATE (A only): A beats null? {'YES' if a_beats_null else 'NO'} ({bestA[2]:+.5f})")
        proceed = a_beats_null

    print(f"VERDICT: {'PROCEED to online eval' if proceed else 'KILL — no online eval'} "
          f"(the offline gate is necessary, not sufficient; a fire still needs the online +35).")
    return 0 if proceed else 2


if __name__ == "__main__":
    raise SystemExit(main())
