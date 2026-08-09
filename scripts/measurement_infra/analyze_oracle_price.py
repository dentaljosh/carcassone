#!/usr/bin/env python3
"""Cluster-robust recompute of an `oracle_score_pilot.py` run's per-disagreement price.

The pilot's own `summary.json` reports a NAIVE (i.i.d.) se/z, but the records are NOT
independent: several records (salts) can share a `root_id`, so inference must cluster on
`root_id`. This script re-reads `<run_dir>/records/*.json` and emits the cluster-robust
statistics as JSON.

ACCEPTANCE TEST — pointed at `/mnt/c/carc-shared/classical_search/oracle_score_pilot`
(the n=100 2752-vs-11008 run) it must reproduce
`measurement/classical_search/ORACLE_PILOT_EXT_READOUT_20260728.md` §1:
  n=100 / G=89 roots, mean +0.7375, naive se 0.2406 / z +3.07,
  cluster-robust se 0.2486 / z +2.97 (p 0.0030), design effect 1.067,
  root-collapsed +0.5920 / se 0.2416 / z +2.45,
  cluster bootstrap of roots 95% CI [+0.251, +1.226], P(<=0) 0.0014.
(The bootstrap seed here defaults to 20260809, not the read-out's 20260728, so the CI
bounds agree only to Monte-Carlo error ~few 1e-3, not bit-exactly.)

Sign convention is the harness's: positive = the deeper (B) pick scores better.
Read-only; writes nothing unless --out is given. Pure stdlib + numpy.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os

import numpy as np


def _norm_sf(z: float) -> float:
    """Upper-tail standard-normal probability."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def load_records(run_dir: str) -> tuple[list[dict], int]:
    paths = sorted(glob.glob(os.path.join(run_dir, "records", "*.json")))
    if not paths:
        raise SystemExit(f"no records under {run_dir}/records/")
    recs = [json.load(open(p)) for p in paths]
    ok = [r for r in recs if r.get("ok")]
    return ok, len(recs) - len(ok)


def cluster_robust_se(deltas: np.ndarray, groups: np.ndarray) -> float:
    """Sandwich se of the mean, clustered on `groups`, with the G/(G-1) small-G correction.

    For the mean, the sandwich reduces to var = (G/(G-1)) * sum_g (sum_{i in g} e_i)^2 / n^2
    with e_i the residual from the overall mean.
    """
    n = deltas.size
    resid = deltas - deltas.mean()
    uniq = np.unique(groups)
    g = uniq.size
    meat = sum(resid[groups == u].sum() ** 2 for u in uniq)
    return math.sqrt((g / (g - 1.0)) * meat / (n * n))


def cluster_bootstrap(deltas: np.ndarray, groups: np.ndarray, reps: int, seed: int):
    """Resample ROOTS with replacement; recompute the record-level mean each rep."""
    uniq = np.unique(groups)
    per_root = [deltas[groups == u] for u in uniq]
    sums = np.array([a.sum() for a in per_root], dtype=float)
    cnts = np.array([a.size for a in per_root], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, uniq.size, size=(reps, uniq.size))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return means


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out")
    ap.add_argument("--boot-reps", type=int, default=20000)
    ap.add_argument("--boot-seed", type=int, default=20260809)
    ap.add_argument("--reference-mean", type=float, default=None,
                    help="denominator for price_ratio (e.g. +0.7375, the 2752-vs-11008 price)")
    args = ap.parse_args()

    recs, n_failed = load_records(args.run_dir)
    deltas = np.array([float(r["delta"]) for r in recs], dtype=float)
    groups = np.array([r["root_id"] for r in recs])
    n = deltas.size
    if n < 2:
        raise SystemExit("need >= 2 completed positions")

    mean = float(deltas.mean())
    sd = float(deltas.std(ddof=1))
    naive_se = sd / math.sqrt(n)
    cr_se = cluster_robust_se(deltas, groups)
    cr_z = mean / cr_se

    uniq = np.unique(groups)
    root_means = np.array([deltas[groups == u].mean() for u in uniq], dtype=float)
    rc_mean = float(root_means.mean())
    rc_se = float(root_means.std(ddof=1)) / math.sqrt(uniq.size)

    boot = cluster_bootstrap(deltas, groups, args.boot_reps, args.boot_seed)
    lo, hi = (float(x) for x in np.percentile(boot, [2.5, 97.5]))

    out = {
        "run_dir": os.path.abspath(args.run_dir),
        "n_positions": n,
        "n_roots": int(uniq.size),
        "n_failed": n_failed,
        # over the COMPLETED (ok) records only — failed ones never produced values
        "crn_verified_all": all(bool(r.get("crn_verified")) for r in recs),
        "mean_delta_pts": mean,
        "sd_delta_positions": sd,
        "naive_se": naive_se,
        "naive_z": mean / naive_se,
        "cluster_robust_se": cr_se,
        "cluster_robust_z": cr_z,
        "cluster_robust_p": 2.0 * _norm_sf(abs(cr_z)),
        "root_collapsed_mean": rc_mean,
        "root_collapsed_se": rc_se,
        "root_collapsed_z": rc_mean / rc_se,
        "bootstrap_reps": args.boot_reps,
        "bootstrap_seed": args.boot_seed,
        "bootstrap_mean": float(boot.mean()),
        "bootstrap_ci95_lo": lo,
        "bootstrap_ci95_hi": hi,
        "bootstrap_p_le_zero": float((boot <= 0).mean()),
        "design_effect": (cr_se ** 2) / (naive_se ** 2),
    }

    if args.reference_mean is not None:
        ref = args.reference_mean
        out["reference_mean"] = ref
        out["price_ratio"] = mean / ref
        r_lo, r_hi = (float(x) for x in np.percentile(boot / ref, [2.5, 97.5]))
        out["price_ratio_ci95_lo"], out["price_ratio_ci95_hi"] = (
            (r_lo, r_hi) if r_lo <= r_hi else (r_hi, r_lo))

    txt = json.dumps(out, indent=2, sort_keys=False)
    print(txt)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(txt + "\n")


if __name__ == "__main__":
    main()
