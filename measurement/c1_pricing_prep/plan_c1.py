#!/usr/bin/env python3
"""C1 OUTCOME PRICING — deal the frozen target plies to boxes, per BLOCK.

Same two rules as `../e4_continuation_20260828/plan_boxes.py` (which this
deliberately mirrors rather than imports, because the world set here is a
per-stratum RANGE rather than `range(M)`):

  1. **A box takes WHOLE PLIES within a block.** Every world of a ply's block
     and both arms stay on one box, so a ply's paired estimate is never split
     across two binaries.
  2. **One unit file per (box, rules profile).** R9 is import-latched, so a
     runner process may only ever see one profile. (This instrument admits a
     single profile — `fixed_v1` — so there is exactly one file per box; the
     per-profile split is kept so the driver's glob is unchanged.)

The block selector is the ONLY knob:

    --block base     worlds [world_lo_base, world_hi_base)      (every stratum)
    --block E1|E2|E3 the matching `extension_blocks` entry      (its strata only)

Cost proxy = `n_remaining_plies * 2 * n_worlds_in_block` — every continuation
ply is one production-champion decision. Plies are dealt greedily to the box
with the least assigned cost per unit of capacity, which balances finish times
and interleaves strata across boxes.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def worlds_for(row: dict, block: str) -> range:
    if block == "base":
        return range(int(row["world_lo_base"]), int(row["world_hi_base"]))
    for e in row.get("extension_blocks") or []:
        if e["block"] == block:
            return range(int(e["world_lo"]), int(e["world_hi"]))
    return range(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default=str(HERE / "targets_c1.jsonl"))
    ap.add_argument("--out-dir", default=str(HERE))
    ap.add_argument("--block", default="base",
                    help="base | E1 | E2 | E3 (DESIGN.md §6)")
    ap.add_argument("--capacity", default="local=30,laptop=22",
                    help="box=capacity,... (the owner-directed W per box)")
    ap.add_argument("--exclude", default=None,
                    help="file of '<game> <ply>' lines to leave out "
                         "(the G-LEGAL pre-flight's drop list, and the smoke)")
    args = ap.parse_args()

    cap = {}
    for part in args.capacity.split(","):
        b, v = part.split("=")
        cap[b.strip()] = float(v)

    rows = [json.loads(l) for l in Path(args.targets).open()]
    skip = set()
    if args.exclude:
        for line in Path(args.exclude).open():
            line = line.strip()
            if line and not line.startswith("#"):
                g, p = line.split()[:2]
                skip.add((g, int(p)))
    rows = [r for r in rows if (r["game"], int(r["ply"])) not in skip]
    rows = [r for r in rows if len(worlds_for(r, args.block)) > 0]
    if not rows:
        raise SystemExit(f"block {args.block!r} selects no plies")

    rows.sort(key=lambda r: (-(r["n_remaining_plies"] * len(worlds_for(r, args.block))),
                             r["game"], r["ply"]))
    load = {b: 0.0 for b in cap}
    assign = {b: [] for b in cap}
    for r in rows:
        c = r["n_remaining_plies"] * 2 * len(worlds_for(r, args.block))
        b = min(cap, key=lambda k: (load[k] / cap[k], k))
        assign[b].append(r)
        load[b] += c

    out = Path(args.out_dir)
    plan = {"block": args.block, "capacity": cap, "n_plies": len(rows),
            "excluded": sorted(skip), "boxes": {}}
    for b, rs in assign.items():
        by_prof = collections.defaultdict(list)
        for r in rs:
            by_prof[r["profile"]].append(r)
        files, n_units = [], 0
        for prof, prs in sorted(by_prof.items()):
            f = out / f"units_{b}_{args.block}_{prof}.txt"
            k = 0
            with f.open("w") as fh:
                for r in sorted(prs, key=lambda r: (r["game"], r["ply"])):
                    for w in worlds_for(r, args.block):
                        fh.write(f"{r['game']} {r['ply']} {w}\n")
                        k += 1
            n_units += k
            files.append({"path": str(f), "profile": prof,
                          "n_plies": len(prs), "n_units": k})
        plan["boxes"][b] = {
            "n_plies": len(rs), "n_units": n_units,
            "predicted_continuation_plies": int(load[b]),
            "strata": dict(collections.Counter(r["stratum"] for r in rs)),
            "files": files,
        }
    plan["totals"] = {
        "n_units": sum(v["n_units"] for v in plan["boxes"].values()),
        "continuation_plies": sum(v["predicted_continuation_plies"]
                                  for v in plan["boxes"].values()),
    }
    (out / f"BOX_PLAN_{args.block}.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps(plan, indent=1))


if __name__ == "__main__":
    main()
