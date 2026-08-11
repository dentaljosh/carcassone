#!/usr/bin/env python3
"""Paired per-root read-out of a v2.10 solver screen (solver_score.py --out JSON).

For every non-baseline ranker vs the baseline (default v29_leaf), on the SAME
solved roots: aggregate regret/top1/tau + the PAIRED per-root better/worse/tie
counts on solver_regret and the sign-test z = (better - worse)/sqrt(better+worse).
The spec's game-gate trigger is paired sign-z >= 2 (docs/V210_LEAF_SPEC_2026-07-04.md).
"""
from __future__ import annotations

import argparse
import json
import math


def analyze(path: str, baseline: str = "v29_leaf"):
    rep = json.loads(open(path).read())
    roots = rep["per_root"]
    names = [n for n in rep["rankers"] if n != baseline]
    rows = []
    for nm in names:
        better = worse = tie = 0
        dsum = 0.0
        for r in roots:
            rb = r["rankers"][baseline]["solver_regret"]
            rv = r["rankers"][nm]["solver_regret"]
            dsum += rv - rb
            if rv < rb:
                better += 1
            elif rv > rb:
                worse += 1
            else:
                tie += 1
        z = (better - worse) / math.sqrt(better + worse) if (better + worse) else 0.0
        agg = rep["aggregate"][nm]
        rows.append({
            "name": nm, "regret": agg["solver_regret_mean"], "top1": agg["top1_rate"],
            "tau": agg["tau_mean"], "better": better, "worse": worse, "tie": tie,
            "sign_z": round(z, 2), "mean_dregret": round(dsum / len(roots), 4),
        })
    rows.sort(key=lambda r: (r["regret"], -r["sign_z"]))
    return rep, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("screen_json")
    ap.add_argument("--baseline", default="v29_leaf")
    args = ap.parse_args()
    rep, rows = analyze(args.screen_json, args.baseline)
    b = rep["aggregate"][args.baseline]
    print(f"baseline {args.baseline}: n={b['n']} regret={b['solver_regret_mean']} "
          f"top1={b['top1_rate']} tau={b['tau_mean']}\n")
    hdr = f"{'variant':<18} {'regret':>7} {'top1':>6} {'tau':>6} {'better':>6} {'worse':>5} {'tie':>5} {'sign_z':>6} {'dregret':>8}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        flag = "  <-- GAME-GATE TRIGGER (sign-z>=2 & lower regret)" if (
            r["sign_z"] >= 2 and r["regret"] < b["solver_regret_mean"]) else ""
        print(f"{r['name']:<18} {r['regret']:>7.4f} {r['top1']:>6.4f} {r['tau']:>6.4f} "
              f"{r['better']:>6} {r['worse']:>5} {r['tie']:>5} {r['sign_z']:>6.2f} "
              f"{r['mean_dregret']:>8.4f}{flag}")


if __name__ == "__main__":
    main()
