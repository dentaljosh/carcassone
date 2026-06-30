#!/usr/bin/env python3
"""Overlap analysis for the farm-vs-bag feature ablation.

Joins probe_farm/V4_listwise/per_group.npz and probe_bag/.../per_group.npz by
group_id and answers: do the farm-connectivity features and the bag/deck features
fix the SAME sibling-ranking mistakes (redundant) or DIFFERENT ones (complementary)?

delta_X[g] = leaf_regret[g] - best_alpha_net_regret[g]  (per-group regret reduction
             from adding feature-set X, at X's OVERALL-slice best alpha)
A positive delta = X moved that group's pick closer to the oracle pick.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")


def _rankdata(a):
    # average ranks (ties → mean rank), numpy-only Spearman helper
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average tied ranks
    _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.zeros(len(cnt)); np.add.at(sums, inv, ranks)
    return (sums / cnt)[inv]


def pearsonr(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 2 or x.std() == 0 or y.std() == 0:
        return float("nan"), float("nan")
    r = float(np.corrcoef(x, y)[0, 1])
    return r, float("nan")  # p-value not needed for this verdict


def spearmanr(x, y):
    return pearsonr(_rankdata(x), _rankdata(y))
FARM = REPO / "measurement/feature_planes_gate/probe_farm/V4_listwise/per_group.npz"
BAG = REPO / "measurement/feature_planes_gate/probe_bag/V4_listwise/per_group.npz"
THRESH = 1e-4  # "fixed by X" = delta_X > THRESH (a small positive regret reduction)


def load(p):
    d = np.load(p)
    return {int(g): (float(lr), float(nr), float(dl))
            for g, lr, nr, dl in zip(d["group_id"], d["leaf_regret"],
                                     d["best_alpha_net_regret"], d["delta"])}, float(d["best_alpha"])


def main():
    if not FARM.exists() or not BAG.exists():
        print(f"missing: farm={FARM.exists()} bag={BAG.exists()}", file=sys.stderr); sys.exit(1)
    fmap, fa = load(FARM); bmap, ba = load(BAG)
    common = sorted(set(fmap) & set(bmap))
    print(f"farm groups={len(fmap)} bag groups={len(bmap)} common={len(common)} "
          f"(best_alpha farm={fa} bag={ba})")
    assert len(common) == len(fmap) == len(bmap), "TEST split should be identical (seed=0)"

    g = np.array(common)
    df = np.array([fmap[k][2] for k in common])   # farm delta per group
    db = np.array([bmap[k][2] for k in common])   # bag delta per group
    leaf = np.array([fmap[k][0] for k in common]) # leaf_regret (same in both files)
    n = len(common)

    # --- correlation of per-group improvement ---
    pr, _ = pearsonr(df, db); sr, _ = spearmanr(df, db)
    # restrict to groups either feature touches (most groups have delta==0 → inflate corr)
    touched = (np.abs(df) > THRESH) | (np.abs(db) > THRESH)
    pr_t, _ = pearsonr(df[touched], db[touched]) if touched.sum() > 2 else (float("nan"), 0)
    sr_t, _ = spearmanr(df[touched], db[touched]) if touched.sum() > 2 else (float("nan"), 0)

    # --- "fixed by X" sets ---
    farm_fixed = set(g[df > THRESH]); bag_fixed = set(g[db > THRESH])
    both = farm_fixed & bag_fixed; only_f = farm_fixed - bag_fixed; only_b = bag_fixed - farm_fixed
    union = farm_fixed | bag_fixed
    jac = len(both) / len(union) if union else float("nan")
    frac_f_also_b = len(both) / len(farm_fixed) if farm_fixed else float("nan")
    frac_b_also_f = len(both) / len(bag_fixed) if bag_fixed else float("nan")

    # --- total regret-reduction decomposition (sum of per-group deltas) ---
    # how much of each feature's TOTAL reduction lands on groups the OTHER also fixes?
    farm_total = df.sum(); bag_total = db.sum()
    bothmask = np.isin(g, list(both)); fmask = np.isin(g, list(only_f)); bmask = np.isin(g, list(only_b))
    # decompose farm's reduction by which bucket the group falls in
    farm_on_both = df[bothmask].sum(); farm_on_onlyf = df[fmask].sum()
    bag_on_both = db[bothmask].sum(); bag_on_onlyb = db[bmask].sum()
    # mean-regret-reduction% framing (matches the aggregate −17.1%/−19.7%)
    mean_leaf = leaf.mean()
    farm_red_pct = 100 * farm_total / n / mean_leaf
    bag_red_pct = 100 * bag_total / n / mean_leaf

    print("\n=== CORRELATION of per-group delta (farm vs bag) ===")
    print(f"  Pearson  (all {n} groups): r={pr:+.4f}")
    print(f"  Spearman (all {n} groups): r={sr:+.4f}")
    print(f"  groups touched by either (|delta|>{THRESH}): {int(touched.sum())}")
    print(f"  Pearson  (touched only):   r={pr_t:+.4f}")
    print(f"  Spearman (touched only):   r={sr_t:+.4f}")

    print("\n=== OVERLAP of FIXED sets (delta > {:g}) ===".format(THRESH))
    print(f"  farm-fixed={len(farm_fixed)}  bag-fixed={len(bag_fixed)}  union={len(union)}")
    print(f"  BOTH fix={len(both)}  only-farm={len(only_f)}  only-bag={len(only_b)}")
    print(f"  Jaccard(farm,bag) = {jac:.3f}")
    print(f"  frac of farm-fixed also bag-fixed = {frac_f_also_b:.3f}")
    print(f"  frac of bag-fixed  also farm-fixed = {frac_b_also_f:.3f}")

    print("\n=== TOTAL regret-reduction decomposition (sum of positive+negative per-group deltas) ===")
    print(f"  mean leaf_regret = {mean_leaf:.6f}  (n={n})")
    print(f"  FARM total delta = {farm_total:+.5f}  -> mean-regret-reduction {farm_red_pct:+.2f}%")
    print(f"     of which on BOTH-fixed groups: {farm_on_both:+.5f}  on only-farm: {farm_on_onlyf:+.5f}")
    print(f"  BAG  total delta = {bag_total:+.5f}  -> mean-regret-reduction {bag_red_pct:+.2f}%")
    print(f"     of which on BOTH-fixed groups: {bag_on_both:+.5f}  on only-bag:  {bag_on_onlyb:+.5f}")
    frac_farm_red_on_both = farm_on_both / farm_total if farm_total else float("nan")
    frac_bag_red_on_both = bag_on_both / bag_total if bag_total else float("nan")
    print(f"  fraction of FARM's reduction on BOTH-fixed groups: {frac_farm_red_on_both:.3f}")
    print(f"  fraction of BAG's  reduction on BOTH-fixed groups: {frac_bag_red_on_both:.3f}")

    print("\n=== VERDICT INPUTS ===")
    print(f"  corr(touched)~{pr_t:+.3f}/{sr_t:+.3f}  Jaccard~{jac:.2f}  "
          f"both-fix share of farm-fixed~{frac_f_also_b:.2f}")


if __name__ == "__main__":
    main()
