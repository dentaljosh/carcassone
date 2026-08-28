#!/usr/bin/env python3
"""Assign the frozen target plies to boxes and emit their unit lists.

TWO RULES, both pre-registered (PREREG.md §5):

  1. **A box takes WHOLE PLIES.** All `M_WORLDS` worlds and both arms of a ply
     stay on one box, so a ply's paired estimate is never split across two
     binaries. Boxes parallelise over `(ply, world)` units WITHIN their share.
  2. **One unit file per (box, rules profile).** R9 is import-latched, so a
     runner process may only ever see one profile.

Plies are ordered by predicted cost (Σ remaining plies is the cost proxy —
every continuation ply is one champion decision) and dealt greedily to the box
with the least assigned cost per unit of capacity, which both balances the
finish times and interleaves the strata across boxes.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

M_WORLDS = 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--capacity", default="local=30,laptop=22",
                    help="box=capacity,... ; capacity is W x measured per-worker "
                         "throughput (default: the raw worker counts)")
    ap.add_argument("--worlds", type=int, default=M_WORLDS)
    ap.add_argument("--exclude", default=None,
                    help="file of '<game> <ply>' lines to leave out (e.g. smoke)")
    args = ap.parse_args()

    cap = {}
    for part in args.capacity.split(","):
        b, v = part.split("=")
        cap[b.strip()] = float(v)

    rows = [json.loads(l) for l in Path(args.targets).open()]
    skip = set()
    if args.exclude:
        for line in Path(args.exclude).open():
            if line.strip():
                g, p = line.split()[:2]
                skip.add((g, int(p)))
    rows = [r for r in rows if (r["game"], int(r["ply"])) not in skip]

    rows.sort(key=lambda r: (-(r["n_plies"] - r["ply"]), r["game"], r["ply"]))
    load = {b: 0.0 for b in cap}
    assign = {b: [] for b in cap}
    for r in rows:
        c = (r["n_plies"] - r["ply"]) * 2 * args.worlds
        b = min(cap, key=lambda k: (load[k] / cap[k], k))
        assign[b].append(r)
        load[b] += c

    out = Path(args.out_dir)
    plan = {"capacity": cap, "worlds": args.worlds, "n_plies": len(rows),
            "excluded": sorted(skip), "boxes": {}}
    for b, rs in assign.items():
        by_prof = collections.defaultdict(list)
        for r in rs:
            by_prof[r["profile"]].append(r)
        files = []
        for prof, prs in sorted(by_prof.items()):
            f = out / f"units_{b}_{prof}.txt"
            with f.open("w") as fh:
                for r in sorted(prs, key=lambda r: (r["game"], r["ply"])):
                    for w in range(args.worlds):
                        fh.write(f"{r['game']} {r['ply']} {w}\n")
            files.append({"path": str(f), "profile": prof,
                          "n_plies": len(prs), "n_units": len(prs) * args.worlds})
        plan["boxes"][b] = {
            "n_plies": len(rs), "n_units": len(rs) * args.worlds,
            "predicted_continuation_plies": int(load[b]),
            "strata": dict(collections.Counter(r["stratum"] for r in rs)),
            "profiles": dict(collections.Counter(r["profile"] for r in rs)),
            "files": files,
        }
    (out / "BOX_PLAN.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps(plan, indent=1))


if __name__ == "__main__":
    main()
