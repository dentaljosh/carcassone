#!/usr/bin/env python3
"""Split the frozen target set into per-box shard files.

One shard = one (profile, game) pair, so the R9 import latch is honoured
per process and a crashed shard loses exactly one game.

Balancing is by ESTIMATED COST, not by row count: a `realized` row costs one
champion counterfactual move, while an exact row additionally costs a solve
(and an `exact_clairvoyant_M` row costs `m_worlds` of them). The planner sorts
games by estimated cost and deals them alternately so neither box gets the whole
expensive tail.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default=str(HERE / "targets.jsonl"))
    ap.add_argument("--mode-cut", default=str(HERE / "MODE_CUT.json"))
    ap.add_argument("--cf-secs", type=float, required=True,
                    help="measured mean seconds per champion counterfactual move")
    ap.add_argument("--marg-secs", type=float, required=True,
                    help="measured p90 seconds per exact_marginalized solve")
    ap.add_argument("--clair-secs", type=float, required=True,
                    help="measured p90 seconds per clairvoyant+ab solve, ONE world")
    ap.add_argument("--boxes", default="local,laptop")
    ap.add_argument("--w", default=None,
                    help="comma-separated worker count per box (e.g. 14,22)")
    ap.add_argument("--out-prefix", default=str(HERE / "shards"))
    args = ap.parse_args()

    cut = json.loads(Path(args.mode_cut).read_text())
    rows = [json.loads(l) for l in Path(args.targets).open()]

    cost = defaultdict(float)
    prof = {}
    for r in rows:
        key = r["game"]
        prof[key] = r["profile"]
        c = args.cf_secs
        if r["k"] <= cut["k_marginalized_max"]:
            c += args.marg_secs
        elif r["k"] <= cut["k_clairvoyant_max"]:
            c += args.clair_secs * cut["m_worlds"]
        cost[key] += c

    boxes = args.boxes.split(",")
    ws = [int(x) for x in args.w.split(",")] if args.w else [1] * len(boxes)
    if len(ws) != len(boxes):
        raise SystemExit("--w must have one entry per box")
    W = dict(zip(boxes, ws))

    # CAPACITY-WEIGHTED longest-processing-time-first. Plain LPT balances SERIAL
    # seconds, which on boxes with different worker counts is the wrong quantity:
    # it hands the 22-worker laptop two expensive games and the 14-worker local box
    # forty-eight cheap ones. Dividing by W balances POOL time instead, which is
    # what the wall clock actually is. The critical path stays the single most
    # expensive GAME (a shard is one game and is not split).
    order = sorted(cost, key=lambda g: -cost[g])
    assign = {b: [] for b in boxes}
    load = {b: 0.0 for b in boxes}
    for g in order:
        b = min(load, key=lambda x: load[x] + cost[g] / W[x])
        assign[b].append(g)
        load[b] += cost[g] / W[b]

    summary = {}
    for b in boxes:
        p = Path(f"{args.out_prefix}_{b}.txt")
        with p.open("w") as fh:
            for g in sorted(assign[b]):
                fh.write(f"{prof[g]} {g}\n")
        serial = sum(cost[g] for g in assign[b])
        summary[b] = {"n_games": len(assign[b]), "W": W[b],
                      "est_serial_secs": round(serial, 1),
                      "est_pool_secs": round(load[b], 1),
                      "est_wall_secs_lower_bound": round(
                          max([cost[g] for g in assign[b]] or [0]), 1),
                      "shardfile": str(p)}
    summary["total_est_serial_secs"] = round(
        sum(cost[g] for gs in assign.values() for g in gs), 1)
    summary["est_wall_secs"] = round(max(
        max(s["est_pool_secs"], s["est_wall_secs_lower_bound"])
        for b, s in summary.items() if isinstance(s, dict)), 1)
    summary["est_wall_note"] = (
        "wall >= the single most expensive GAME (a shard is one game and is never "
        "split), so the critical path is that game, not the pool average.")
    summary["cost_model"] = {"cf_secs": args.cf_secs, "marg_secs": args.marg_secs,
                             "clair_secs_per_world": args.clair_secs,
                             "m_worlds": cut["m_worlds"]}
    Path(f"{args.out_prefix}_PLAN.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
