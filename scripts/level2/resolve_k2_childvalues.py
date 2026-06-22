#!/usr/bin/env python3
"""Pre-tool audit (Phase 3 enabler) — re-solve the 150 K=2 positions dumping the
FULL per-root-action value map (child_values), which the original L2-3 run computed
but did not persist. K=2 is cheap (median ~7.5s/pos) and is the only fully-tractable
slice that also carries fair-information (marginalized) labels.

Output: k2_childvalues.jsonl — one line per position:
  {gen_id, seed, ply, k_remaining, to_move,
   clairvoyant:{value, optimal_actions, nodes, child_values:{action:value}},
   marginalized:{...}}

This lets Phase 3 score ANY selector's exact regret + rank-correlate any per-action
quantity against the exact solver values. Pure CPU alpha-beta; no net, no orchestrator.
"""
from __future__ import annotations

import os
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")

import argparse
import glob
import json
import sys
from multiprocessing import Pool

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

from gen_endgame_positions import replay_to   # noqa: E402
import endgame_solver as ES                    # noqa: E402

BUDGET = 5_000_000


def _solve_one(task):
    gid, seed, ply, k = task["gen_id"], task["seed"], task["ply"], task["k_remaining"]
    try:
        game, board = replay_to(seed, ply)
    except Exception as e:
        return {"gen_id": gid, "_error": f"recon {type(e).__name__}: {e}"}
    out = {"gen_id": gid, "seed": seed, "ply": ply, "k_remaining": k}
    for mode, ab in (("clairvoyant", True), ("marginalized", False)):
        try:
            res = ES.solve(game, board, mode=mode, budget=BUDGET, alphabeta=ab)
            out[mode] = {
                "value": res.value,
                "to_move": res.to_move,
                "nodes": res.nodes,
                "n_optimal": len(res.optimal_actions),
                "optimal_actions": [int(a) for a in res.optimal_actions],
                "child_values": {str(int(a)): float(v) for a, v in res.child_values.items()},
            }
        except ES.BudgetExceeded:
            out[mode] = {"solved": False}
        except Exception as e:
            out[mode] = {"_error": f"{type(e).__name__}: {e}"}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", default="/mnt/c/carc-shared")
    ap.add_argument("--out", default=os.path.join(REPO, "measurement", "pre_tool_audit", "k2_childvalues.jsonl"))
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    tasks = []
    for f in sorted(glob.glob(os.path.join(args.share, "l23_regret", "g*_k2.json"))):
        d = json.load(open(f))
        tasks.append({"gen_id": d["gen_id"], "seed": d["seed"], "ply": d["ply"], "k_remaining": 2})
    print(f"[resolve-k2] {len(tasks)} positions, budget={BUDGET}, W={args.workers}", flush=True)

    with Pool(args.workers) as p:
        results = p.map(_solve_one, tasks, chunksize=2)

    errs = [r for r in results if "_error" in r]
    with open(args.out, "w") as fh:
        for r in sorted(results, key=lambda x: x["gen_id"]):
            fh.write(json.dumps(r) + "\n")
    ok = [r for r in results if "_error" not in r and r.get("clairvoyant", {}).get("child_values")]
    print(f"[resolve-k2] wrote {len(results)} -> {args.out}; ok={len(ok)} errors={len(errs)}", flush=True)
    if errs:
        print("[resolve-k2] sample errors:", [e["_error"] for e in errs[:5]], flush=True)
    # quick parity check vs the committed per-agent regrets
    return results


if __name__ == "__main__":
    main()
