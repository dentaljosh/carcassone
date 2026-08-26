#!/usr/bin/env python3
"""R1's estimator arithmetic, COPIED VERBATIM — do not re-derive.

Source: `scratchpad/evloss_autopsy/run/05_analyze_r1.py` (the R1 adjudicator that produced
`R1_READOUT.json`: R_champ = +1.4928485121941815, se 0.07179985263453552, n 800/498).

`hajek`, `cluster_sandwich`, `cluster_bootstrap`, `wsd` and `load_leg` below are byte-for-byte
the R1 functions. The R2 prereg (`R2_PREREG.md` §2) makes them binding: the estimator
conventions (Hajek weighting on `1/pi_s`, cluster-robust sandwich on `game_id`, the
10,000-rep cluster bootstrap) are R1's, not a re-implementation. The pooled reconciliation
in `r2_taxonomy.py` is what proves the copy is faithful.

Everything below the marked line is NEW R2 arithmetic (bucket-vs-complement contrast,
Holm), stated in the prereg.
"""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path

# =========================================================================== #
# VERBATIM FROM 05_analyze_r1.py — DO NOT EDIT                                #
# =========================================================================== #


def hajek(vals, wts):
    sw = sum(wts)
    return sum(v * w for v, w in zip(vals, wts)) / sw if sw else float("nan")


def cluster_sandwich(vals, wts, groups):
    """Cluster-robust SE of the Hajek weighted mean. Returns (se, deff, n_clusters)."""
    mu = hajek(vals, wts)
    sw = sum(wts)
    e = [w * (v - mu) for v, w in zip(vals, wts)]
    by_g = defaultdict(float)
    for ei, g in zip(e, groups):
        by_g[g] += ei
    G = len(by_g)
    if G < 2 or sw == 0:
        return float("nan"), float("nan"), G
    corr = G / (G - 1.0)
    var_cl = corr * sum(s * s for s in by_g.values()) / (sw * sw)
    var_naive = (len(vals) / (len(vals) - 1.0)) * sum(x * x for x in e) / (sw * sw) \
        if len(vals) > 1 else float("nan")
    deff = var_cl / var_naive if var_naive and var_naive == var_naive else float("nan")
    return math.sqrt(max(var_cl, 0.0)), deff, G


def cluster_bootstrap(vals, wts, groups, reps=10000, seed=20260824):
    idx_by_g = defaultdict(list)
    for i, g in enumerate(groups):
        idx_by_g[g].append(i)
    gkeys = sorted(idx_by_g)
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        num = den = 0.0
        for _ in range(len(gkeys)):
            g = gkeys[rng.randrange(len(gkeys))]
            for i in idx_by_g[g]:
                num += vals[i] * wts[i]
                den += wts[i]
        out.append(num / den if den else float("nan"))
    out.sort()

    def pct(p):
        k = min(len(out) - 1, max(0, int(round(p * (len(out) - 1)))))
        return out[k]
    return {"lo95": pct(0.025), "hi95": pct(0.975), "median": pct(0.5),
            "p_le_0": sum(1 for x in out if x <= 0) / len(out), "reps": reps}


def wsd(vals, wts):
    """Weighted sd (frequency-weight convention), the per-position spread."""
    sw = sum(wts)
    if sw <= 0 or len(vals) < 2:
        return float("nan")
    mu = hajek(vals, wts)
    v = sum(w * (x - mu) ** 2 for x, w in zip(vals, wts)) / sw
    return math.sqrt(v * len(vals) / (len(vals) - 1.0))


def load_leg(judge_root, leg):
    recs = Path(judge_root) / leg / "records"
    out = {}
    if not recs.is_dir():
        return out
    for p in recs.glob("*.json"):
        d = json.loads(p.read_text())
        if d.get("ok") is True and d.get("crn_verified") is True:
            out[d["rid"]] = d
    return out


# =========================================================================== #
# NEW R2 ARITHMETIC (R2_PREREG.md §2, §5.4)                                   #
# =========================================================================== #
Z95 = 1.959964


def contrast_cluster(vals, wts, groups, member):
    """Cluster-robust z of the (bucket - complement) difference of two Hajek means.

    The label-exchangeable statistic: under the label-permutation null of §5.3 the bucket
    mean is drawn from the same population as its complement, so THIS is the quantity the
    null prices. Same sandwich form as `cluster_sandwich`, applied to the influence
    function of the difference.
    """
    wa = [w * (1.0 if m else 0.0) for w, m in zip(wts, member)]
    wb = [w * (0.0 if m else 1.0) for w, m in zip(wts, member)]
    Wa, Wb = sum(wa), sum(wb)
    if Wa <= 0 or Wb <= 0:
        return float("nan"), float("nan"), float("nan")
    mua = sum(v * w for v, w in zip(vals, wa)) / Wa
    mub = sum(v * w for v, w in zip(vals, wb)) / Wb
    theta = mua - mub
    by_g = defaultdict(float)
    for v, a, b, g in zip(vals, wa, wb, groups):
        by_g[g] += a * (v - mua) / Wa - b * (v - mub) / Wb
    G = len(by_g)
    if G < 2:
        return theta, float("nan"), float("nan")
    var = (G / (G - 1.0)) * sum(s * s for s in by_g.values())
    se = math.sqrt(max(var, 0.0))
    return theta, se, (theta / se if se > 0 else float("nan"))


def norm_sf(z):
    """One-sided upper tail of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def two_sided_p(z):
    if z != z:
        return float("nan")
    return min(1.0, 2.0 * norm_sf(abs(z)))


def holm(pvals: dict, alpha: float = 0.05) -> dict:
    """Holm-Bonferroni step-down. Returns {key: {p, p_adj, reject}}."""
    items = sorted(((k, v) for k, v in pvals.items() if v == v), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(running, (m - i) * p))
        running = adj
        out[k] = {"p": p, "p_holm": adj, "reject": bool(adj <= alpha)}
    for k, v in pvals.items():
        if k not in out:
            out[k] = {"p": v, "p_holm": float("nan"), "reject": False}
    return out
