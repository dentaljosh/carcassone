#!/usr/bin/env python3
"""Measure the RUST solve-cost ladder on real E4 positions — the cost model the
pricing-mode cut is set against.

⚠️ EXCLUSIVE TENANT. This is a TIMING bench; run it with nothing else on the box
(one niced 1-core DRAM churner has been measured inflating a saturated eval
~1.8x/move). Census by FULL ARGS (`ps -eo args`) before launching.

Sizes by **p90 and max**, never the mean — the cost wall is the tail, and the
marginalized mode has no alpha-beta so its tail is what decides `k_marginalized_max`.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
ARCHIVES = REPO / "measurement" / "e4_games"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--positions", required=True)
    ap.add_argument("--per-k", type=int, default=4)
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=12)
    ap.add_argument("--marg-k-max", type=int, default=6)
    ap.add_argument("--budget", type=int, default=200_000_000)
    ap.add_argument("--per-solve-cap-s", type=int, default=900)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from analyzer.ev_loss import prepare_env
    env = prepare_env(args.profile)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from price_plies import solve_isolated  # noqa: E402

    rows = [json.loads(l) for l in Path(args.positions).open()]
    rows = [r for r in rows if r.get("profile") == args.profile]
    by_k = defaultdict(list)
    for r in sorted(rows, key=lambda r: (r["k"], r["game"], r["ply"])):
        if args.k_min <= r["k"] <= args.k_max and len(by_k[r["k"]]) < args.per_k:
            by_k[r["k"]].append(r)

    samples = []
    for k in sorted(by_k):
        for r in by_k[k]:
            arc = json.loads((ARCHIVES / r["game"]).read_text())
            payload = {"profile": args.profile, "deck_seed": int(arc["deck_seed"]),
                       "actions": [int(x) for x in arc["actions"]], "ply": int(r["ply"]),
                       "budget": args.budget, "world": 0}
            for mode in ("exact_clairvoyant_world", "exact_marginalized"):
                if mode == "exact_marginalized" and k > args.marg_k_max:
                    continue
                t0 = time.time()
                res = solve_isolated({**payload, "mode": mode},
                                     mem_cap_gb=8.0, cpu_cap_s=args.per_solve_cap_s)
                s = {"k": k, "game": r["game"], "ply": r["ply"], "mode": mode,
                     "status": res.get("status"), "wall_s": round(time.time() - t0, 3),
                     "solve_s": res.get("solve_s"), "nodes": res.get("nodes")}
                samples.append(s)
                print(json.dumps(s), flush=True)

    ladder = {}
    for mode in ("exact_clairvoyant_world", "exact_marginalized"):
        for k in sorted(by_k):
            ok = [s["wall_s"] for s in samples
                  if s["mode"] == mode and s["k"] == k and s["status"] == "OK"]
            skipped = [s for s in samples
                       if s["mode"] == mode and s["k"] == k and s["status"] != "OK"]
            if not ok and not skipped:
                continue
            ladder[f"{mode}:k{k}"] = {
                "n_ok": len(ok), "n_skipped": len(skipped),
                "mean_s": round(statistics.fmean(ok), 3) if ok else None,
                "p90_s": round(sorted(ok)[max(0, int(0.9 * len(ok)) - 1)], 3) if ok else None,
                "max_s": round(max(ok), 3) if ok else None,
                "skip_statuses": sorted({s["status"] for s in skipped}),
            }
    out = {"profile": args.profile, "env": env, "budget": args.budget,
           "per_solve_cap_s": args.per_solve_cap_s,
           "note": "exact_clairvoyant_world is ONE world, so wall_s IS the per-world "
                   "cost; the real per-ply cost at the frozen cut is "
                   "(m_worlds + 1) * wall_s. Sized by p90/max, never the mean.",
           "clair_worlds_per_sample": 1,
           "ladder": ladder, "samples": samples}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(ladder, indent=1))


if __name__ == "__main__":
    main()
