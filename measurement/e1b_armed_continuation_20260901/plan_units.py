#!/usr/bin/env python3
"""Emit E-1b's unit lists (one file per rules profile) and the smoke list.

TWO RULES, inherited unchanged from E-1a's `plan_boxes.py`:

  1. **A box takes WHOLE PLIES.** All `M_WORLDS` worlds and both arms of a ply
     stay on one box, so a ply's paired estimate is never split.
  2. **One unit file per (box, rules profile).** R9 is import-latched, so a
     runner process may only ever see one profile.

E-1b is a SINGLE-BOX round (local, W = 32), so the "assignment" is trivial and
this file exists for the ORDERING and the SMOKE selection:

  * plies are ordered by DESCENDING predicted cost (`n_plies - ply`), so the
    long tail starts first and the last workers to finish are the cheap ones —
    the standard makespan ordering;
  * the SMOKE takes the CHEAPEST plies (largest `ply_frac`), because a smoke
    must be cheap AND real. It runs at the PRODUCTION knobs of the cell — only
    the unit COUNT differs (CLAUDE.md's pre-flight rule), and it writes into a
    SEPARATE `out_SMOKE_*` directory so a smoke unit can never be mistaken for
    a cell unit.
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
    ap.add_argument("--box", default="local")
    ap.add_argument("--worlds", type=int, default=M_WORLDS)
    ap.add_argument("--smoke-plies", type=int, default=4,
                    help="cheapest N plies (one per stratum where possible); 4 "
                         "== all four strata exercised")
    ap.add_argument("--smoke-worlds", type=int, default=1)
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.targets).open()]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # --- the SMOKE: cheapest ply per stratum, up to --smoke-plies ------------
    by_stratum = collections.defaultdict(list)
    for r in rows:
        by_stratum[r["stratum"]].append(r)
    cheapest = []
    for s in sorted(by_stratum):
        cheapest.append(min(by_stratum[s],
                            key=lambda r: (r["n_plies"] - r["ply"],
                                           r["game"], r["ply"])))
    cheapest.sort(key=lambda r: (r["n_plies"] - r["ply"], r["game"], r["ply"]))
    smoke = cheapest[:max(0, args.smoke_plies)]
    smoke_prof = {r["profile"] for r in smoke}
    if len(smoke_prof) > 1:
        # R9 is import-latched: keep the smoke inside ONE profile group.
        keep = smoke[0]["profile"]
        smoke = [r for r in smoke if r["profile"] == keep]

    # --- the CELL: every target ply, longest tail first ----------------------
    rows.sort(key=lambda r: (-(r["n_plies"] - r["ply"]), r["game"], r["ply"]))
    by_prof = collections.defaultdict(list)
    for r in rows:
        by_prof[r["profile"]].append(r)

    plan = {"box": args.box, "worlds": args.worlds, "n_plies": len(rows),
            "n_units": len(rows) * args.worlds, "files": [],
            "predicted_continuation_plies":
                sum((r["n_plies"] - r["ply"]) * 2 * args.worlds for r in rows),
            "strata": dict(collections.Counter(r["stratum"] for r in rows)),
            "profiles": dict(collections.Counter(r["profile"] for r in rows))}
    for prof, prs in sorted(by_prof.items()):
        f = out / f"units_{args.box}_{prof}.txt"
        with f.open("w") as fh:
            for r in prs:
                for w in range(args.worlds):
                    fh.write(f"{r['game']} {r['ply']} {w}\n")
        plan["files"].append({"path": str(f), "profile": prof,
                              "n_plies": len(prs),
                              "n_units": len(prs) * args.worlds})

    smoke_files = []
    for prof in sorted({r["profile"] for r in smoke}):
        f = out / f"smokeunits_{args.box}_{prof}.txt"
        with f.open("w") as fh:
            for r in [x for x in smoke if x["profile"] == prof]:
                for w in range(args.smoke_worlds):
                    fh.write(f"{r['game']} {r['ply']} {w}\n")
        smoke_files.append({"path": str(f), "profile": prof,
                            "n_plies": len([x for x in smoke
                                            if x["profile"] == prof]),
                            "n_units": len([x for x in smoke
                                            if x["profile"] == prof])
                            * args.smoke_worlds})
    plan["smoke"] = {
        "files": smoke_files, "worlds": args.smoke_worlds,
        "plies": [{"game": r["game"], "ply": r["ply"], "stratum": r["stratum"],
                   "profile": r["profile"],
                   "remaining_plies": r["n_plies"] - r["ply"]} for r in smoke],
        "predicted_continuation_plies":
            sum((r["n_plies"] - r["ply"]) * 2 * args.smoke_worlds for r in smoke),
        "note": "PRODUCTION knobs, tiny unit count, SEPARATE out dir.",
    }
    (out / "UNIT_PLAN.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps(plan, indent=1))


if __name__ == "__main__":
    main()
