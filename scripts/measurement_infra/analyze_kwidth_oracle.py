#!/usr/bin/env python3
"""READ-OUT for the 11008-vs-22016 plateau discriminator — the PRE-REGISTERED §6 estimators.

Written and committed BEFORE any score exists, so no estimator is chosen after seeing
numbers. Prereg: measurement/classical_search/KWIDTH_22016_PREREG_20260729.md §6.

Recomputes everything from the ON-DISK per-position records, not from the harness's
`summary.json` — whose z is NAIVE and must not be cited. Records are (root, salt) cells
with up to 3 salts per root, so they are NOT independent and every statistic clusters on
`root_id`.

Sign convention: positive = the 22016 (k16x1376, wider) pick scores better.

    analyze_kwidth_oracle.py [--score-dir DIR] [--picks-dir DIR] [--bootstrap 20000]
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

# The pilot's measured effect for the rung BELOW this one (2752 -> 11008), on the IDENTICAL
# instrument. The headline contrast of this read-out is this step against that one.
PILOT_EFFECT = 0.7375
PILOT_SD = 2.406
HALF_PILOT = PILOT_EFFECT / 2.0     # the prereg's planning effect and its knee threshold


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _var(xs, ddof=1):
    xs = list(xs)
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    mu = _mean(xs)
    return sum((x - mu) ** 2 for x in xs) / (n - ddof)


def cluster_robust(rows):
    """Sandwich se for the MEAN, clustered on root, with the G/(G-1) finite-cluster
    correction. For a plain mean the sandwich reduces to
    var = sum_g (sum_{i in g} (y_i - ybar))^2 / n^2, scaled by G/(G-1)."""
    ys = [r["delta"] for r in rows]
    n = len(ys)
    ybar = _mean(ys)
    by_root = defaultdict(list)
    for r in rows:
        by_root[r["root_id"]].append(r["delta"] - ybar)
    g = len(by_root)
    meat = sum(sum(v) ** 2 for v in by_root.values())
    var = (meat / (n ** 2)) * (g / (g - 1)) if g > 1 else float("nan")
    return ybar, math.sqrt(var), n, g


def root_collapsed(rows):
    """One unit-weighted mean per root — the CONSERVATIVE read."""
    by_root = defaultdict(list)
    for r in rows:
        by_root[r["root_id"]].append(r["delta"])
    per = [_mean(v) for v in by_root.values()]
    m = _mean(per)
    se = math.sqrt(_var(per) / len(per)) if len(per) > 1 else float("nan")
    return m, se, len(per)


def bootstrap_roots(rows, n_boot, seed):
    """Resample ROOTS (not records) with replacement — the correct unit."""
    by_root = defaultdict(list)
    for r in rows:
        by_root[r["root_id"]].append(r["delta"])
    keys = sorted(by_root)
    rng = random.Random(seed)
    rec_means, col_means = [], []
    for _ in range(n_boot):
        pick = [keys[rng.randrange(len(keys))] for _ in range(len(keys))]
        flat = [d for k in pick for d in by_root[k]]
        rec_means.append(_mean(flat))
        col_means.append(_mean([_mean(by_root[k]) for k in pick]))
    def ci(v):
        v = sorted(v)
        lo = v[int(0.025 * len(v))]
        hi = v[min(len(v) - 1, int(0.975 * len(v)))]
        return _mean(v), lo, hi, sum(1 for x in v if x <= 0) / len(v)
    return ci(rec_means), ci(col_means)


def sign_test(vals):
    pos = sum(1 for v in vals if v > 0)
    neg = sum(1 for v in vals if v < 0)
    zer = sum(1 for v in vals if v == 0)
    n = pos + neg
    # exact one-sided binomial P(X >= pos | p = 0.5)
    p = (sum(math.comb(n, k) for k in range(pos, n + 1)) / (2 ** n)) if n else float("nan")
    return pos, neg, zer, p


def trimmed_mean(xs, frac=0.10):
    xs = sorted(xs)
    k = int(len(xs) * frac)
    core = xs[k:len(xs) - k] if len(xs) - 2 * k > 0 else xs
    return _mean(core)


def verdict(mean, se, lo95, hi95):
    """The PRE-REGISTERED verdict map (§6). Mechanical — no judgement here."""
    z = mean / se if se and se == se else float("nan")
    if z <= -2:
        return ("THE WIDER PICK IS WORSE", "k16 would be past the width optimum at 22016. "
                "Report as-is; do not rescue it.")
    if z >= 2:
        return ("THERE IS ROOM ABOVE 11008",
                "The plateau is (at least partly) the ruler again, one rung up. "
                "UNDERSTANDING ONLY — no deploy consequence; 22016 costs 2x the clock.")
    if hi95 == hi95 and hi95 < HALF_PILOT:
        return ("11008 IS AT / NEAR ITS KNEE (on this instrument)",
                "First budget rung where deeper search stops buying real improvement. "
                "⚠️ READ WITH PREREG §4: a weak continuation biases TOWARD this answer, "
                "so this is 'NOT DETECTED', never 'nothing above 11008'.")
    return ("INCONCLUSIVE at this n",
            "Report the interval. Do NOT promote a direction.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--score-dir",
                    default="/mnt/c/carc-shared/oracle_22016_20260729/score")
    ap.add_argument("--picks-dir",
                    default="/mnt/c/carc-shared/oracle_22016_20260729/picks")
    ap.add_argument("--bootstrap", type=int, default=20000)
    ap.add_argument("--boot-seed", type=int, default=20260729)
    args = ap.parse_args(argv)

    # ---- pick phase: the disagreement rate, a finding in its own right ----------
    pd = Path(args.picks_dir) / "records"
    picks = [json.loads(p.read_text()) for p in pd.glob("*.json")] if pd.exists() else []
    ok = [r for r in picks if r.get("ok")]
    dis = [r for r in ok if r.get("disagree")]
    print("=" * 78)
    print("PICK PHASE — does the pick still CHANGE at 2x the champion budget?")
    print("=" * 78)
    if ok:
        d_hat = len(dis) / len(ok)
        se_d = math.sqrt(d_hat * (1 - d_hat) / len(ok))
        nver = sum(1 for r in ok if r.get("agent_parity_verified"))
        print(f"  cells ok                : {len(ok)}  (failed {len(picks) - len(ok)})")
        print(f"  distinct roots          : {len({r['root_id'] for r in ok})}")
        print(f"  DISAGREEMENTS           : {len(dis)}")
        print(f"  D_hat(11008, 22016)     : {d_hat:.4f} +/- {se_d:.4f}")
        print(f"  CL-070 D_paired(2752,11008) : 0.2398   (the rung below)")
        print(f"  AGENT-PARITY VERIFIED   : {nver} cells "
              f"{'OK' if nver else '*** NONE — the prefix trick is UNPROVEN on this run ***'}")
    else:
        print("  (no pick records yet)")

    # ---- score phase: the pre-registered estimators -----------------------------
    sd = Path(args.score_dir) / "records"
    rows = [json.loads(p.read_text()) for p in sd.glob("*.json")] if sd.exists() else []
    rows = [r for r in rows if r.get("ok") and isinstance(r.get("delta"), (int, float))]
    print()
    print("=" * 78)
    print("SCORE PHASE — where they disagree, is the 22016 pick BETTER?")
    print("  sign convention: POSITIVE = the 22016 (wider) pick scores better")
    print("=" * 78)
    if len(rows) < 2:
        print(f"  only {len(rows)} scored positions — nothing to read yet.")
        return 0

    crn_all = all(r.get("crn_verified") for r in rows)
    n_ident = sum(1 for r in rows if r.get("distinct_afterstates") == 0)
    print(f"  scored positions        : {len(rows)}")
    print(f"  crn_verified_all        : {crn_all}"
          f"{'' if crn_all else '   *** VOID: arms not paired (prereg §8) ***'}")
    print(f"  identical afterstates   : {n_ident}"
          f"{'' if not n_ident else '   (zero deltas there are IDENTITIES, not evidence)'}")

    mean, se_cr, n, g = cluster_robust(rows)
    deltas = [r["delta"] for r in rows]
    sd_pos = math.sqrt(_var(deltas))
    se_naive = sd_pos / math.sqrt(n)
    col_m, col_se, n_roots = root_collapsed(rows)
    lo95, hi95 = mean - 1.96 * se_cr, mean + 1.96 * se_cr

    print()
    print(f"  {'estimator':<46}{'mean':>9}{'se':>9}{'z':>8}")
    print(f"  {'-' * 72}")
    print(f"  {'naive (record-level, i.i.d. — NOT CITED)':<46}"
          f"{mean:>9.4f}{se_naive:>9.4f}{mean / se_naive:>8.2f}")
    print(f"  {'** CLUSTER-ROBUST on root (THE CITED ROW) **':<46}"
          f"{mean:>9.4f}{se_cr:>9.4f}{mean / se_cr:>8.2f}")
    print(f"  {'root-collapsed (conservative)':<46}"
          f"{col_m:>9.4f}{col_se:>9.4f}{(col_m / col_se if col_se else float('nan')):>8.2f}")
    print(f"  design effect (CR/naive var)  : {(se_cr / se_naive) ** 2:.3f}")
    print(f"  clusters G / records n        : {g} / {n}")
    print(f"  95% CI (cluster-robust)       : [{lo95:+.4f}, {hi95:+.4f}]")

    (bm, blo, bhi, bp), (cm, clo, chi, cp) = bootstrap_roots(
        rows, args.bootstrap, args.boot_seed)
    print()
    print(f"  bootstrap OF ROOTS ({args.bootstrap} resamples, seed {args.boot_seed}):")
    print(f"    record-level   mean {bm:+.4f}  95% CI [{blo:+.4f}, {bhi:+.4f}]  P(<=0) {bp:.4f}")
    print(f"    root-collapsed mean {cm:+.4f}  95% CI [{clo:+.4f}, {chi:+.4f}]  P(<=0) {cp:.4f}")

    rp, rn, rz, rpv = sign_test(deltas)
    by_root = defaultdict(list)
    for r in rows:
        by_root[r["root_id"]].append(r["delta"])
    gp, gn, gz, gpv = sign_test([_mean(v) for v in by_root.values()])
    print()
    print(f"  sign test  records : {rp}+ / {rn}- / {rz}=0   one-sided binomial p {rpv:.4f}")
    print(f"  sign test  roots   : {gp}+ / {gn}- / {gz}=0   one-sided binomial p {gpv:.4f}")
    print(f"  robustness  sd {sd_pos:.4f}   median {sorted(deltas)[len(deltas) // 2]:+.4f}"
          f"   10%-trimmed {trimmed_mean(deltas):+.4f}"
          f"   range [{min(deltas):+.3f}, {max(deltas):+.3f}]")

    print()
    print("  THE HEADLINE CONTRAST — this step vs the rung below, SAME instrument:")
    print(f"    2752 -> 11008 (oracle pilot, n=100) : {PILOT_EFFECT:+.4f} pts/disagreement")
    print(f"    11008 -> 22016 (this run, n={n})    : {mean:+.4f} pts/disagreement")
    print(f"    ratio                               : {mean / PILOT_EFFECT:.2f}x")
    print("    undiminished => the elo plateau is a RULER artifact well past the champion.")
    print("    collapsed to ~0 => the champion really does sit at the knee.")

    v, why = verdict(mean, se_cr, lo95, hi95)
    print()
    print("  " + "=" * 74)
    print(f"  PRE-REGISTERED VERDICT: {v}")
    print(f"    {why}")
    print("  " + "=" * 74)
    print("  Strata (phase / gap tercile) are DESCRIPTIVE ONLY and are not printed as")
    print("  findings — the pilot's §3 splits were non-monotone noise. No CL id, no")
    print("  results.csv row, PRODUCTION.yaml untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
