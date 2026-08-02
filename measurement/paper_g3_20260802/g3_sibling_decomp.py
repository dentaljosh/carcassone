#!/usr/bin/env python3
"""G3 / step 2 — between-root vs within-sibling variance decomposition on the
1,119-root exact-solver ruler bank, plus the same decomposition for the
hand-crafted leaf's values (the reference arm).

Input (pre-existing, no re-solve):
  measurement/gatec_c0_20260723/cache/c0_cache.npz  — the CL-065 C0 export:
    X            (50637, 84)  the leaf's own component features
    y            (50637,)     EXACT endgame-solver child value, MOVER-oriented,
                              RAW POINTS  (c0_export.py:104 `solver_mover`)
    leaf_score   (50637,)     the v2.9 leaf ranker's per-child value,
                              tanh(virtual_score_v2/15), mover-POV
    group        (50637,)     root index 0..1118 == the SIBLING SET
    root_*       (1119,)      per-root metadata + the leaf self-check
  Provenance: cache/manifest.json records n_roots=1119, n_children_total=50637,
  mode "marginalized (K<=2)", and a leaf_self_check reproducing the ruler's
  regret 0.9508 / top1 0.6095 / tau 0.6153 (== READOUT.md §4.1 curve125 row).

Decomposition (one-way ANOVA on the sibling set):
    SS_total = SS_between_root + SS_within_root
  SS_between_root : variance of the ROOT MEAN about the grand mean, n-weighted
                    -> the position-level component; what an outcome-regression
                       objective can reduce its loss on.
  SS_within_root  : variance of a child about ITS OWN root's mean
                    -> the between-sibling residual; the ONLY component argmax
                       and Kendall tau over siblings can see.

Also computed:
  * the same split for tanh(y/15)  — i.e. the solver label expressed in the
    training head's own target units (values = tanh((p0-p1)/15));
  * the same split for `leaf_score` (the reference arm);
  * cross-level agreement between the leaf and the solver: between-root r and
    within-root r (the latter is the leaf's discrimination signal);
  * a SUPPLEMENTARY in-silico predictor: a 5-fold-by-root cross-fit ridge on the
    same 84 features trained with a POOLED-MSE objective, whose R^2 is then split
    into a between-root and a within-root part.  This is a re-fit of CL-065's
    `gate_full_ridge` arm and must reproduce its tau (0.3466) as a provenance
    check; the new content is only the R^2 split.

Pure arithmetic: no engine, no search, no net forward, no GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
C0 = REPO / "measurement" / "gatec_c0_20260723"
sys.path.insert(0, str(C0))

import c0_fit as CF  # noqa: E402  (make_folds / ridge_fit_predict / group_metrics)

VALUE_NORM = 15.0  # the project's tanh normalisation (manifest config.outcome_norm)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def decompose(v: np.ndarray, group: np.ndarray, n_roots: int) -> dict:
    """One-way between/within decomposition of `v` by sibling set `group`."""
    v = np.asarray(v, dtype=np.float64)
    n = v.shape[0]
    counts = np.bincount(group, minlength=n_roots).astype(np.float64)
    sums = np.bincount(group, weights=v, minlength=n_roots)
    means = sums / counts
    grand = v.mean()
    resid = v - means[group]
    ss_total = float(((v - grand) ** 2).sum())
    ss_within = float((resid ** 2).sum())
    ss_between = float((counts * (means - grand) ** 2).sum())
    # per-root within variance (population, ddof=0), and the unweighted average
    ss_within_per_root = np.bincount(group, weights=resid ** 2, minlength=n_roots)
    var_within_per_root = ss_within_per_root / counts
    return {
        "n_children": int(n),
        "n_roots": int(n_roots),
        "grand_mean": float(grand),
        "var_total": ss_total / n,
        "sd_total": float(np.sqrt(ss_total / n)),
        "ss_total": ss_total,
        "ss_between_root": ss_between,
        "ss_within_root": ss_within,
        "frac_between_root": ss_between / ss_total,
        "frac_within_root": ss_within / ss_total,
        "sd_between_root": float(np.sqrt(ss_between / n)),
        "sd_within_root": float(np.sqrt(ss_within / n)),
        "root_mean_sd": float(means.std(ddof=0)),
        "within_root_sd_mean_over_roots": float(np.sqrt(var_within_per_root).mean()),
        "within_root_sd_median_over_roots": float(np.median(np.sqrt(var_within_per_root))),
        "frac_roots_with_zero_within_var": float((var_within_per_root <= 1e-12).mean()),
        "_means": means,
        "_resid": resid,
        "_counts": counts,
    }


def pub(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(C0 / "cache" / "c0_cache.npz"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--ridge-lam", type=float, default=1.0)
    args = ap.parse_args()

    t0 = time.time()
    z = np.load(args.cache, allow_pickle=True)
    X = z["X"].astype(np.float64)
    y = z["y"].astype(np.float64)
    leaf = z["leaf_score"].astype(np.float64)
    group = z["group"].astype(np.int64)
    root_seed = z["root_seed"].astype(np.int64)
    root_leaf_tau = z["root_leaf_tau"].astype(np.float64)
    root_n_legal = z["root_n_legal"].astype(np.int64)
    n_roots = root_seed.shape[0]

    y_tanh = np.tanh(y / VALUE_NORM)

    dy = decompose(y, group, n_roots)
    dyt = decompose(y_tanh, group, n_roots)
    dl = decompose(leaf, group, n_roots)

    # ---- cross-level agreement leaf <-> solver ------------------------------
    def corr(a, b):
        a = np.asarray(a, float); b = np.asarray(b, float)
        if a.std() < 1e-15 or b.std() < 1e-15:
            return float("nan")
        return float(np.corrcoef(a, b)[0, 1])

    between_r = corr(dy["_means"], dl["_means"])
    within_r = corr(dy["_resid"], dl["_resid"])
    pooled_r = corr(y, leaf)
    # MATCHED UNITS: the leaf is tanh(score/15) and y is points, so a pooled
    # within-root Pearson in points under-reads the leaf (tanh compresses
    # exactly where |value| is large).  Two fairer within-root readings:
    #   (i)  against tanh(y/15) — same nonlinearity on both sides;
    #   (ii) residuals z-scored WITHIN each root before pooling — removes the
    #        per-root scale differences entirely (roots with zero within-root
    #        spread on either side are dropped; count reported).
    within_r_tanh = corr(dyt["_resid"], dl["_resid"])

    def within_z_corr(res_a, res_b, grp, n_r):
        sa = np.sqrt(np.bincount(grp, weights=res_a ** 2, minlength=n_r)
                     / np.bincount(grp, minlength=n_r))
        sb = np.sqrt(np.bincount(grp, weights=res_b ** 2, minlength=n_r)
                     / np.bincount(grp, minlength=n_r))
        ok = (sa > 1e-12) & (sb > 1e-12)
        m = ok[grp]
        za = res_a[m] / sa[grp][m]
        zb = res_b[m] / sb[grp][m]
        return corr(za, zb), int(ok.sum()), int(m.sum())

    within_rz_leaf, n_r_z_leaf, n_c_z_leaf = within_z_corr(dy["_resid"], dl["_resid"],
                                                           group, n_roots)

    # ---- what a root-mean-only ("position-level perfect") predictor buys ----
    # MSE of predicting each child by its own root's mean == within-root variance.
    r2_rootmean_oracle = dy["frac_between_root"]

    # ---- SUPPLEMENTARY: pooled-MSE ridge on the leaf's own 84 features ------
    fold_of_root = CF.make_folds(root_seed, CF.N_FOLDS, CF.FOLD_RNG_SEED)
    fold_of_child = fold_of_root[group]
    pred = np.empty_like(y)
    for f in range(CF.N_FOLDS):
        tr = fold_of_child != f
        te = fold_of_child == f
        pred[te] = CF.ridge_fit_predict(X[tr], y[tr], X[te], args.ridge_lam)

    dp = decompose(pred, group, n_roots)
    # R^2 decomposition of the cross-fit prediction against the solver label
    sse_total = float(((y - pred) ** 2).sum())
    r2_pooled = 1.0 - sse_total / dy["ss_total"]
    # between-root part: root means of pred vs root means of y (n-weighted)
    sse_between = float((dy["_counts"] * (dy["_means"] - dp["_means"]) ** 2).sum())
    r2_between = 1.0 - sse_between / dy["ss_between_root"]
    # within-root part: residuals about each root's own mean
    sse_within = float(((dy["_resid"] - dp["_resid"]) ** 2).sum())
    r2_within = 1.0 - sse_within / dy["ss_within_root"]
    within_rz_ridge, _, _ = within_z_corr(dy["_resid"], dp["_resid"], group, n_roots)

    # provenance check: this ridge must reproduce CL-065 gate_full_ridge tau
    regret = np.empty(n_roots); top1 = np.empty(n_roots); tau = np.empty(n_roots)
    lregret = np.empty(n_roots); ltop1 = np.empty(n_roots); ltau = np.empty(n_roots)
    for gi in range(n_roots):
        m = group == gi
        regret[gi], top1[gi], tau[gi] = CF.group_metrics(pred[m], y[m])
        lregret[gi], ltop1[gi], ltau[gi] = CF.group_metrics(leaf[m], y[m])

    # ---- the leaf's own R^2 against the solver, split by level --------------
    # The leaf lives in tanh units and the solver label in points, so score the
    # leaf by its BEST LINEAR RESCALING at each level (an r^2, not an MSE) —
    # that is r^2 of the level-specific correlation above.
    leaf_r2_between = between_r ** 2
    leaf_r2_within = within_r ** 2

    out = {
        "kind": "g3_sibling_variance_decomposition",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_rev": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "inputs": {
            "cache": args.cache,
            "cache_sha256": sha256(Path(args.cache)),
            "cache_manifest": str(C0 / "cache" / "manifest.json"),
            "root_bank": "1,119 K=2 marginalized exact-solver roots (qprobe_A JOIN pool_A); "
                         "the identical bank used by measurement/value_unlock_20260730 and "
                         "measurement/canonical_az/solver_score_derisk_it00_03.json",
            "y_units": "raw points, mover-oriented exact solver child value",
            "leaf_units": "tanh(virtual_score_v2/15), mover-POV; curve100 cfg — READOUT §4.3(b) "
                          "records curve125 and curve100 pick the SAME child on 1119/1119 roots",
            "value_norm": VALUE_NORM,
        },
        "provenance_checks": {
            "leaf_tau_from_cache": float(np.nanmean(root_leaf_tau)),
            "leaf_tau_recomputed": float(np.nanmean(ltau)),
            "leaf_top1_recomputed": float(ltop1.mean()),
            "leaf_regret_recomputed": float(lregret.mean()),
            "expected_from_READOUT": {"tau": 0.6153, "top1": 0.6095, "regret": 0.9508},
            "ridge_tau_recomputed": float(np.nanmean(tau)),
            "ridge_top1_recomputed": float(top1.mean()),
            "ridge_regret_recomputed": float(regret.mean()),
            "expected_from_CL065_gate_full_ridge": {"tau": 0.3466, "top1": 0.4638, "regret": 0.7900},
        },
        "bank_shape": {
            "n_roots": int(n_roots),
            "n_children": int(y.shape[0]),
            "children_per_root_mean": float(y.shape[0] / n_roots),
            "children_per_root_median": float(np.median(np.bincount(group, minlength=n_roots))),
            "children_per_root_min": int(np.bincount(group, minlength=n_roots).min()),
            "children_per_root_max": int(np.bincount(group, minlength=n_roots).max()),
            "root_n_legal_mean": float(root_n_legal.mean()),
        },
        "decomposition": {
            "solver_child_value_points": pub(dy),
            "solver_child_value_tanh15": pub(dyt),
            "heuristic_leaf_value_tanh15": pub(dl),
            "ridge_pooled_mse_prediction_points": pub(dp),
        },
        "cross_level_agreement_leaf_vs_solver": {
            "pooled_pearson_r": pooled_r,
            "between_root_pearson_r": between_r,
            "within_root_pearson_r": within_r,
            "between_root_r2": leaf_r2_between,
            "within_root_r2": leaf_r2_within,
            "within_root_pearson_r_matched_tanh_units": within_r_tanh,
            "within_root_pearson_r_zscored_by_root": within_rz_leaf,
            "within_root_zscored_n_roots_used": n_r_z_leaf,
            "within_root_zscored_n_children_used": n_c_z_leaf,
            "within_root_kendall_tau_mean": float(np.nanmean(ltau)),
            "note": "the points-scale within-root Pearson under-reads the leaf because the leaf "
                    "is a tanh of its score; the matched-unit and z-scored-by-root readings are "
                    "the fair ones. Kendall tau (rank, per-root) is the paper's primary statistic "
                    "and is scale-free.",
        },
        "supplementary_pooled_mse_ridge": {
            "learner": "closed-form standardized ridge, lam=%g, 5-fold cross-fit BY ROOT "
                       "(c0_fit.make_folds seed %d) on the leaf's own 84 component features"
                       % (args.ridge_lam, CF.FOLD_RNG_SEED),
            "objective": "pooled MSE against the exact solver child value (points)",
            "r2_pooled": r2_pooled,
            "r2_between_root": r2_between,
            "r2_within_root": r2_within,
            "within_root_pearson_r_zscored_by_root": within_rz_ridge,
            "within_root_kendall_tau_mean": float(np.nanmean(tau)),
            "note": "the same fit that CL-065 reports as gate_full_ridge; the R^2 split is the new number.",
        },
        "position_level_oracle": {
            "r2_of_perfect_root_mean_predictor": r2_rootmean_oracle,
            "its_within_root_kendall_tau": 0.0,
            "note": "a predictor that knows each root's mean exactly and nothing else explains "
                    "frac_between_root of the total label variance and has zero sibling-ordering "
                    "information by construction.",
        },
        "wall_secs": time.time() - t0,
    }
    js = json.dumps(out, indent=2)
    if args.out:
        Path(args.out).write_text(js + "\n")
    print(js)


if __name__ == "__main__":
    main()
