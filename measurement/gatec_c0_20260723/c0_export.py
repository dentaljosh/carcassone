#!/usr/bin/env python3
"""Gate C0 stage 1 — solver-label + per-component-feature export.

Reuses solver_score.py's solve path: for each of the 1,119 K<=2 sibling roots
(qprobe_A JOIN pool_A, K<=2 == all K=2 marginalized), reconstruct the root, solve
ONCE with the exact endgame solver, orient the per-child value to the mover, and
emit the c0_features per-component feature vector for every child.  Cache the
whole (features, labels, group ids, leaf-score) to disk so the fit
(c0_fit.py) is repeatable WITHOUT re-solving.

Self-validation: the v2.9-leaf ranker's per-root (regret, top1, tau) are computed
here too (via the harness group_metrics) and aggregated — this MUST reproduce the
harness leaf tau = 0.6153, proving the solve + orientation match solver_score.py
before any learned fit is trusted.

MEASUREMENT ONLY.  Pure CPU, no CUDA.  Does not touch the champion / production
leaf / PRODUCTION.yaml.
"""
from __future__ import annotations

import os
# v2.9 leaf env — MUST precede the carcassonne_ai imports (EXACT copy of
# solver_score.py's block so the leaf terms / ranker are bit-identical).
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
HERE = REPO / "measurement" / "gatec_c0_20260723"
for p in ["src", "scripts/level2", "scripts/feature_planes_gate",
          "scripts/canonical_az", "measurement/gatec_c0_20260723"]:
    sys.path.insert(0, str(REPO / p))

import endgame_solver as S                                  # noqa: E402
from gen_endgame_positions import replay_to, k_remaining    # noqa: E402
from step1_train import group_metrics                       # noqa: E402
import eval_hybrid_handoff as EH                             # noqa: E402
from solver_score import (load_sibling_roots, make_v29_leaf_ranker,  # noqa: E402
                          DEFAULT_QPROBE, DEFAULT_POOL, MARG_MAX_K)
import c0_features as CF                                     # noqa: E402

CFG = EH._heur_leaf_cfg(2.0)
FEATURE_NAMES = CF.feature_order(CFG)
_LEAF_RANKER = make_v29_leaf_ranker()


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def process_root(rec, budget, max_k):
    """Solve one root + emit features for every child.  Returns a dict with the
    per-child feature matrix, oriented labels, and the v29-leaf self-check
    metrics — or {'_skip'/'_error': ...}."""
    seed, ply = int(rec["seed"]), int(rec["ply"])
    try:
        game, board = replay_to(seed, ply)
    except Exception as e:  # noqa
        return {"_error": f"{seed}:{ply} recon {type(e).__name__}: {e}"}
    if game.string_representation(board) != rec["checksum"]:
        return {"_error": f"{seed}:{ply} checksum_mismatch"}
    k = k_remaining(board)
    if k > max_k:
        return {"_skip": "k>max_k", "k": k}
    if k <= MARG_MAX_K:
        mode, ab = "marginalized", False
    else:
        mode, ab = "clairvoyant", True
    root_player = board.state.current_player
    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
    if legal.size < 2:
        return {"_skip": "<2 legal", "k": k}
    t0 = time.perf_counter()
    try:
        res = S.solve(game, board, mode=mode, budget=budget, alphabeta=ab)
    except S.BudgetExceeded:
        return {"_skip": "budget", "k": k, "mode": mode}
    solve_secs = time.perf_counter() - t0
    cv = res.child_values
    tm = res.to_move
    actions = list(cv.keys())
    solver_mover = np.array([(cv[a] if tm == 0 else -cv[a]) for a in actions],
                            dtype=np.float64)
    children = [game.get_next_state(board, int(a))[0] for a in actions]

    # features + leaf-score (== the v29_leaf ranker input on non-terminal children)
    X = np.empty((len(children), len(FEATURE_NAMES)), dtype=np.float64)
    leaf_score = np.empty(len(children), dtype=np.float64)
    for i, child in enumerate(children):
        d = CF.emit_features_dict(child.state, root_player, CFG)
        if list(d.keys()) != FEATURE_NAMES:
            return {"_error": f"{seed}:{ply} feature key drift"}
        X[i, :] = list(d.values())
        # exact ranker score (handles terminal children like the harness)
        leaf_score[i] = float(_LEAF_RANKER(children[i], root_player, game))

    # v29-leaf self-check: score the ranker vs solver_mover with the SAME
    # group_metrics the harness uses.  Must reproduce tau=0.6153 in aggregate.
    reg, top1, tau = group_metrics(leaf_score, solver_mover)
    return {
        "seed": seed, "ply": ply, "k": k, "mode": mode, "to_move": int(tm),
        "n_legal": len(actions), "solve_secs": solve_secs,
        "X": X, "y": solver_mover, "leaf_score": leaf_score,
        "leaf_regret": float(reg), "leaf_top1": int(top1), "leaf_tau": float(tau),
    }


_CTX = {}


def _worker(rec):
    return process_root(rec, _CTX["budget"], _CTX["max_k"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--qprobe", default=DEFAULT_QPROBE)
    ap.add_argument("--pool", default=DEFAULT_POOL)
    ap.add_argument("--max-k", type=int, default=2)
    ap.add_argument("--budget", type=int, default=5_000_000)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--n", type=int, default=0, help="cap #roots (0=all; for smoke)")
    ap.add_argument("--out", default=str(HERE / "cache" / "c0_cache.npz"))
    args = ap.parse_args(argv)

    recs = load_sibling_roots(args.qprobe, args.pool)
    cand = [r for r in recs if int(r.get("k_remaining", 99)) <= args.max_k]
    cand.sort(key=lambda r: (int(r["seed"]), int(r["ply"])))
    if args.n:
        cand = cand[: args.n]
    print(f"[load] {len(recs)} sibling roots; {len(cand)} with k_remaining<={args.max_k}",
          flush=True)
    print(f"[cfg] n_features={len(FEATURE_NAMES)} budget={args.budget} workers={args.workers}",
          flush=True)

    _CTX.update(budget=args.budget, max_k=args.max_k)
    scored, errs, skips = [], [], []
    t0 = time.perf_counter()

    def _handle(out):
        if out is None:
            return
        if "_error" in out:
            errs.append(out)
        elif "_skip" in out:
            skips.append(out)
        else:
            scored.append(out)

    if args.workers <= 1:
        for i, rec in enumerate(cand):
            _handle(_worker(rec))
            if (i + 1) % 50 == 0:
                el = time.perf_counter() - t0
                print(f"  {i+1}/{len(cand)} scored={len(scored)} ({el:.0f}s, "
                      f"{el/max(i+1,1):.2f}s/root)", flush=True)
    else:
        from multiprocessing import get_context
        ctx = get_context("fork")
        with ctx.Pool(args.workers) as pool:
            done = 0
            for out in pool.imap_unordered(_worker, cand, chunksize=1):
                _handle(out)
                done += 1
                if done % 50 == 0:
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(cand)} scored={len(scored)} "
                          f"skip={len(skips)} err={len(errs)} "
                          f"({el:.0f}s wall, {len(scored)/max(el,1e-9):.2f} root/s)",
                          flush=True)
    dt = time.perf_counter() - t0
    print(f"[done] scored={len(scored)} skipped={len(skips)} errors={len(errs)} "
          f"in {dt:.0f}s", flush=True)
    if errs[:5]:
        print("  errors:", [e["_error"] for e in errs[:5]], flush=True)
    if skips:
        print("  skips:", dict(Counter(s["_skip"] for s in skips)), flush=True)
    if not scored:
        print("[FATAL] nothing scored", flush=True)
        return 1

    # stable order by (seed, ply) for reproducibility
    scored.sort(key=lambda r: (r["seed"], r["ply"]))

    # assemble flat arrays
    Xs, ys, ls, groups = [], [], [], []
    root_seed, root_ply, root_tm, root_nlegal = [], [], [], []
    root_leaf_reg, root_leaf_t1, root_leaf_tau, root_solve_secs = [], [], [], []
    for gi, r in enumerate(scored):
        n = r["X"].shape[0]
        Xs.append(r["X"])
        ys.append(r["y"])
        ls.append(r["leaf_score"])
        groups.append(np.full(n, gi, dtype=np.int32))
        root_seed.append(r["seed"]); root_ply.append(r["ply"])
        root_tm.append(r["to_move"]); root_nlegal.append(r["n_legal"])
        root_leaf_reg.append(r["leaf_regret"]); root_leaf_t1.append(r["leaf_top1"])
        root_leaf_tau.append(r["leaf_tau"]); root_solve_secs.append(r["solve_secs"])
    X = np.concatenate(Xs, axis=0).astype(np.float32)
    y = np.concatenate(ys, axis=0).astype(np.float64)
    leaf_score = np.concatenate(ls, axis=0).astype(np.float64)
    group = np.concatenate(groups, axis=0)

    # aggregate v29-leaf self-check (mean over roots == harness _agg)
    leaf_tau_mean = float(np.nanmean(root_leaf_tau))
    leaf_top1_rate = float(np.mean(root_leaf_t1))
    leaf_reg_mean = float(np.mean(root_leaf_reg))
    n_seeds = len(set(root_seed))
    print(f"[leaf self-check] n_roots={len(scored)} distinct_seeds={n_seeds} "
          f"tau={leaf_tau_mean:.4f} top1={leaf_top1_rate:.4f} regret={leaf_reg_mean:.4f}",
          flush=True)
    print(f"[leaf self-check] EXPECT tau=0.6153 top1=0.6095 regret=0.9508 "
          f"(CL-064 harness) -> {'MATCH' if abs(leaf_tau_mean-0.6153)<0.002 else 'MISMATCH!!'}",
          flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        X=X, y=y, leaf_score=leaf_score, group=group,
        feature_names=np.array(FEATURE_NAMES),
        root_seed=np.array(root_seed, dtype=np.int64),
        root_ply=np.array(root_ply, dtype=np.int64),
        root_to_move=np.array(root_tm, dtype=np.int8),
        root_n_legal=np.array(root_nlegal, dtype=np.int32),
        root_leaf_regret=np.array(root_leaf_reg, dtype=np.float64),
        root_leaf_top1=np.array(root_leaf_t1, dtype=np.int32),
        root_leaf_tau=np.array(root_leaf_tau, dtype=np.float64),
        root_solve_secs=np.array(root_solve_secs, dtype=np.float64),
    )
    manifest = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "corpus": {"qprobe": args.qprobe, "pool": args.pool,
                   "qprobe_sha256": _sha256(args.qprobe),
                   "pool_sha256": _sha256(args.pool),
                   "max_k": args.max_k, "n_roots": len(scored),
                   "distinct_seeds": n_seeds,
                   "n_children_total": int(X.shape[0]),
                   "n_skipped": len(skips), "n_errors": len(errs)},
        "solver": {"budget": args.budget, "mode": "marginalized (K<=2)",
                   "solve_secs_total": float(sum(root_solve_secs)),
                   "solve_secs_mean": float(np.mean(root_solve_secs)),
                   "wall_secs": round(dt, 1), "workers": args.workers},
        "leaf_cfg": {"bonus_cap": CFG.bonus_cap, "opp_bonus_cap": CFG.opp_bonus_cap,
                     "meeple_k": CFG.meeple_k,
                     "v29_meeple_curve": list(CFG.v29_meeple_curve),
                     "closure_p": {str(k): v for k, v in CFG.closure_p.items()},
                     "bag_close": bool(getattr(CFG, "bag_close", False))},
        "leaf_self_check": {"tau_mean": leaf_tau_mean, "top1_rate": leaf_top1_rate,
                            "regret_mean": leaf_reg_mean,
                            "expected_tau": 0.6153,
                            "match": abs(leaf_tau_mean - 0.6153) < 0.002},
        "n_features": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
    }
    (out.parent / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[out] wrote {out} ({out.stat().st_size/1e6:.1f} MB) + manifest.json",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
