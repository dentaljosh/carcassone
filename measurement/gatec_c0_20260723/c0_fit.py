#!/usr/bin/env python3
"""Gate C0 stage 2 — cross-fit train/eval + the pre-registered gate.

Loads the c0_export cache (per-child features + exact-solver labels + group ids),
runs 5-fold cross-fitting GROUPED BY DECK SEED (no seed spans train/test), fits
the boring learners (ridge/OLS + sklearn HistGradientBoosting), ranks siblings
within each held-out root by prediction, and scores with the EXACT harness
group_metrics tau.  Aggregates held-out tau/top1/regret (mean over roots, ==
solver_score._agg) and applies the PREREG.md gate.

kendall_tau_b + group_metrics are VERBATIM copies of the harness functions
(value_ranking_train.kendall_tau_b / step1_train.group_metrics) so the number is
directly comparable to the leaf's 0.6153 with NO torch dependency; a unit test
(tests/test_gatec_c0.py) asserts the copies match the originals bit-for-bit.

MEASUREMENT ONLY.  Reads the cache; touches nothing in production.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

HERE = Path("/home/doctor/projects/carcassone/measurement/gatec_c0_20260723")

# leaf-term feature subsets (must match c0_features.py)
LEAF_TERM_KEYS = ("lt_base", "lt_bonus_self", "lt_bonus_opp", "lt_meeple_curve")
LEAF_SCORE_KEY = "lt_leaf_score"
LEAF_PREFIX = "lt_"

N_FOLDS = 5
FOLD_RNG_SEED = 0


# --------------------------------------------------------------------------- #
# VERBATIM harness metric functions (value_ranking_train.py / step1_train.py). #
# Copied so the fit has no torch dep; test_gatec_c0.py asserts equality.       #
# --------------------------------------------------------------------------- #
def kendall_tau_b(x, y):
    n = len(x)
    if n < 2:
        return float("nan")
    c = d = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            sx = int(x[i] > x[j]) - int(x[i] < x[j]); sy = int(y[i] > y[j]) - int(y[i] < y[j])
            if sx == 0 and sy == 0:
                continue
            if sx == 0:
                ty += 1; continue
            if sy == 0:
                tx += 1; continue
            c += int(sx == sy); d += int(sx != sy)
    denom = math.sqrt((c + d + tx) * (c + d + ty))
    return (c - d) / denom if denom else float("nan")


def group_metrics(score, oq):
    best = int(np.argmax(oq)); pick = int(np.argmax(score))
    return float(oq[best] - oq[pick]), int(pick == best), kendall_tau_b(score, oq)


# --------------------------------------------------------------------------- #
def make_folds(root_seed: np.ndarray, n_folds: int, rng_seed: int):
    """Assign each ROOT (== one unique seed here) to a fold, grouped by seed.
    Returns fold_of_root (len n_roots) and asserts no seed spans folds."""
    uniq = np.unique(root_seed)
    rng = np.random.default_rng(rng_seed)
    order = rng.permutation(len(uniq))
    shuffled = uniq[order]
    seed_fold = {}
    for i, s in enumerate(shuffled):
        seed_fold[int(s)] = i % n_folds
    fold_of_root = np.array([seed_fold[int(s)] for s in root_seed], dtype=np.int32)
    # assert grouping: every seed maps to exactly one fold
    from collections import defaultdict
    seed_folds = defaultdict(set)
    for s, f in zip(root_seed, fold_of_root):
        seed_folds[int(s)].add(int(f))
    assert all(len(v) == 1 for v in seed_folds.values()), "a seed spans multiple folds!"
    return fold_of_root


def ridge_fit_predict(Xtr, ytr, Xte, lam):
    """Standardized closed-form ridge (intercept unregularized). Returns test
    predictions.  lam=0 == OLS."""
    mu = Xtr.mean(axis=0)
    sd = Xtr.std(axis=0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    Xtr_s = (Xtr - mu) / sd
    Xte_s = (Xte - mu) / sd
    n, d = Xtr_s.shape
    A = np.hstack([np.ones((n, 1)), Xtr_s])          # intercept col
    reg = np.eye(d + 1) * lam
    reg[0, 0] = 0.0                                   # don't penalize intercept
    w = np.linalg.solve(A.T @ A + reg, A.T @ ytr)
    B = np.hstack([np.ones((Xte_s.shape[0], 1)), Xte_s])
    return B @ w


def gbdt_fit_predict(Xtr, ytr, Xte):
    """sklearn HistGradientBoostingRegressor with fixed, modest hyper-parameters."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    m = HistGradientBoostingRegressor(
        loss="squared_error", learning_rate=0.05, max_iter=300,
        max_leaf_nodes=31, min_samples_leaf=50, l2_regularization=1.0,
        early_stopping=False, random_state=0,
    )
    m.fit(Xtr, ytr)
    return m.predict(Xte)


def _demean_by_group(yv, grp):
    """Subtract each group's mean from its labels (within-root ADVANTAGE target).
    Ranking-aligned objective: removes the cross-root LEVEL the global-MSE fit
    otherwise spends capacity on, so the learner optimises within-root ORDER."""
    out = yv.astype(np.float64).copy()
    order = np.argsort(grp, kind="stable")
    gs = grp[order]
    # group-wise mean via reduceat on the sorted view
    uniq, first = np.unique(gs, return_index=True)
    sums = np.add.reduceat(out[order], first)
    counts = np.diff(np.append(first, len(gs)))
    means = sums / counts
    gmean = np.empty(len(uniq)); gmean[:] = means
    lut = {int(u): m for u, m in zip(uniq, gmean)}
    return out - np.array([lut[int(g)] for g in grp])


def crossfit_eval(X, y, group, fold_of_root, predict_fn, n_folds, demean=False):
    """Cross-fit: predict each root in its held-out fold, then per-root
    group_metrics -> arrays of (regret, top1, tau) over roots.

    demean=True centres the TRAIN labels within each train root (advantage
    target) before fitting — a ranking-aligned objective that isolates whether
    the DEAD verdict is a global-MSE-dilution artefact vs a real info ceiling.
    Test roots are still ranked by the raw prediction (no test-root info used)."""
    n_roots = fold_of_root.shape[0]
    fold_of_child = fold_of_root[group]
    preds = np.empty(y.shape[0], dtype=np.float64)
    for f in range(n_folds):
        tr = fold_of_child != f
        te = fold_of_child == f
        ytr = _demean_by_group(y[tr], group[tr]) if demean else y[tr]
        preds[te] = predict_fn(X[tr], ytr, X[te])
    regret = np.empty(n_roots); top1 = np.empty(n_roots); tau = np.empty(n_roots)
    for gi in range(n_roots):
        m = group == gi
        r, t, k = group_metrics(preds[m], y[m])
        regret[gi] = r; top1[gi] = t; tau[gi] = k
    return regret, top1, tau, fold_of_root


def agg(regret, top1, tau, fold_of_root, n_folds):
    per_fold_tau = [float(np.nanmean(tau[fold_of_root == f])) for f in range(n_folds)]
    return {
        "tau_mean": float(np.nanmean(tau)),
        "top1_rate": float(np.mean(top1)),
        "regret_mean": float(np.mean(regret)),
        "per_fold_tau": per_fold_tau,
        "fold_tau_std": float(np.std(per_fold_tau)),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", default=str(HERE / "cache" / "c0_cache.npz"))
    ap.add_argument("--out", default=str(HERE / "results.json"))
    ap.add_argument("--ridge-lam", type=float, default=1.0,
                    help="fixed ridge L2 for the headline full-feature ridge")
    args = ap.parse_args(argv)

    z = np.load(args.cache, allow_pickle=True)
    X = z["X"].astype(np.float64)
    y = z["y"].astype(np.float64)
    group = z["group"].astype(np.int64)
    leaf_score = z["leaf_score"].astype(np.float64)
    names = [str(s) for s in z["feature_names"]]
    root_seed = z["root_seed"].astype(np.int64)
    root_leaf_tau = z["root_leaf_tau"].astype(np.float64)
    n_roots = root_seed.shape[0]
    name_ix = {nm: i for i, nm in enumerate(names)}
    print(f"[load] X={X.shape} y={y.shape} n_roots={n_roots} "
          f"distinct_seeds={len(set(root_seed.tolist()))} n_features={len(names)}",
          flush=True)

    fold_of_root = make_folds(root_seed, N_FOLDS, FOLD_RNG_SEED)
    print(f"[folds] {N_FOLDS}-fold by seed; sizes="
          f"{[int((fold_of_root==f).sum()) for f in range(N_FOLDS)]}", flush=True)

    # --- LEAF FLOOR (self-check from the cache; == harness 0.6153) ------------ #
    leaf_floor = {
        "tau_mean": float(np.nanmean(root_leaf_tau)),
        "note": "v29-leaf ranker vs solver, per-root mean (from c0_export self-check)",
    }
    # recompute leaf tau via THIS module's group_metrics on leaf_score (proves the
    # copied metric matches the export's harness metric)
    lt = np.empty(n_roots)
    for gi in range(n_roots):
        m = group == gi
        _, _, k = group_metrics(leaf_score[m], y[m])
        lt[gi] = k
    leaf_floor["tau_recomputed_here"] = float(np.nanmean(lt))
    print(f"[leaf floor] cache={leaf_floor['tau_mean']:.4f} "
          f"recomputed={leaf_floor['tau_recomputed_here']:.4f} (expect 0.6153)",
          flush=True)

    # --- feature subsets ------------------------------------------------------ #
    idx_leaf_score = [name_ix[LEAF_SCORE_KEY]]
    idx_leaf_terms = [name_ix[k] for k in LEAF_TERM_KEYS]
    idx_full = list(range(len(names)))
    idx_raw_no_leaf = [i for i, nm in enumerate(names) if not nm.startswith(LEAF_PREFIX)]

    results = {"leaf_floor": leaf_floor, "n_roots": n_roots,
               "n_features": len(names), "feature_names": names,
               "fold_sizes": [int((fold_of_root == f).sum()) for f in range(N_FOLDS)],
               "ridge_lam_headline": args.ridge_lam,
               "gbdt_params": {"learning_rate": 0.05, "max_iter": 300,
                               "max_leaf_nodes": 31, "min_samples_leaf": 50,
                               "l2_regularization": 1.0},
               "runs": {}}

    def run(tag, cols, learner, demean=False):
        Xc = X[:, cols]
        if learner == "ols":
            fn = lambda a, b, c: ridge_fit_predict(a, b, c, 0.0)  # noqa: E731
        elif learner == "ridge":
            fn = lambda a, b, c: ridge_fit_predict(a, b, c, args.ridge_lam)  # noqa: E731
        elif learner == "gbdt":
            fn = gbdt_fit_predict
        else:
            raise ValueError(learner)
        reg, t1, tau, forr = crossfit_eval(Xc, y, group, fold_of_root, fn, N_FOLDS,
                                           demean=demean)
        a = agg(reg, t1, tau, forr, N_FOLDS)
        results["runs"][tag] = {"learner": learner, "n_cols": len(cols),
                                "demean": demean, **a}
        print(f"[{tag:30s}] ({learner:5s}, {len(cols):2d} feats"
              f"{', demean' if demean else '        '})  "
              f"tau={a['tau_mean']:.4f}  top1={a['top1_rate']:.4f}  "
              f"regret={a['regret_mean']:.4f}  fold_tau_std={a['fold_tau_std']:.4f}",
              flush=True)
        return a

    # SANITY FLOOR CHECKS (may be inspected before the gate)
    run("sanity_leaf_score_ols", idx_leaf_score, "ols")     # must == 0.6153
    run("sanity_leaf_terms_ols", idx_leaf_terms, "ols")     # must ~= 0.615
    run("sanity_leaf_terms_ridge", idx_leaf_terms, "ridge")

    # DIAGNOSTIC: raw pooled features WITHOUT any leaf term
    run("diag_raw_no_leaf_ridge", idx_raw_no_leaf, "ridge")
    run("diag_raw_no_leaf_gbdt", idx_raw_no_leaf, "gbdt")

    # GATE: full feature set (leaf terms + raw pooled), the two boring learners
    full_ridge = run("gate_full_ridge", idx_full, "ridge")
    full_gbdt = run("gate_full_gbdt", idx_full, "gbdt")

    # ROBUSTNESS DIAGNOSTIC (NOT the pre-registered gate): within-root-demeaned
    # target (advantage) — a ranking-aligned objective. Tests whether the DEAD
    # verdict is a global-MSE-dilution artefact vs a real information ceiling.
    run("diag_leaf_terms_ridge_demean", idx_leaf_terms, "ridge", demean=True)
    run("diag_full_ridge_demean", idx_full, "ridge", demean=True)
    run("diag_full_gbdt_demean", idx_full, "gbdt", demean=True)

    # --- gate verdict --------------------------------------------------------- #
    gate_tau = max(full_ridge["tau_mean"], full_gbdt["tau_mean"])
    best_learner = "ridge" if full_ridge["tau_mean"] >= full_gbdt["tau_mean"] else "gbdt"
    if gate_tau >= 0.65:
        verdict = "FIRE"
    elif gate_tau < 0.62:
        verdict = "DEAD"
    else:
        verdict = "AMBIGUOUS"
    results["gate"] = {
        "statistic": "max held-out full-feature tau (ridge, gbdt)",
        "gate_tau": gate_tau, "best_learner": best_learner,
        "leaf_floor_tau": leaf_floor["tau_mean"],
        "thresholds": {"FIRE": ">=0.65", "DEAD": "<0.62", "AMBIGUOUS": "[0.62,0.65)"},
        "verdict": verdict,
    }
    print("\n" + "=" * 64)
    print(f"LEAF FLOOR tau = {leaf_floor['tau_mean']:.4f}")
    print(f"GATE tau (best of ridge/gbdt full) = {gate_tau:.4f} ({best_learner})")
    print(f"VERDICT: {verdict}  "
          f"(FIRE>=0.65 / DEAD<0.62 / AMBIGUOUS[0.62,0.65))")
    print("=" * 64)

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"[out] wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
