#!/usr/bin/env python3
"""Summarise every eff_linus round-3 Pop run dir: median p50 s/move per config."""
import json, statistics as st, sys
from pathlib import Path

root = Path(sys.argv[1])
out = {}
for rd in sorted(root.iterdir()):
    if not rd.is_dir() or not (rd / "cells").exists():
        continue
    for p in sorted((rd / "cells").glob("*.json")):
        cell, arm, rep = p.stem.split("__")
        try:
            d = json.loads(p.read_text())
            b = d["budgets"][0] if cell.startswith("champ_") else None
        except Exception as e:
            print(f"  !! {rd.name}/{p.name}: {e}")
            continue
        if b is None:
            tim = (d.get("rows") or [{}])[0].get("timings", {}).get("forward")
            v = tim["p50_ms"] if tim else None
            unit = "forward_p50_ms"
        else:
            v = b["overall"]["p50_s"]
            unit = "p50_s_per_move"
        key = (rd.name, cell, arm, unit)
        out.setdefault(key, {"vals": [], "gov": None, "nice": None, "actions": None})
        out[key]["vals"].append(v)
        if b is not None and out[key]["actions"] is None:
            out[key]["actions"] = [s["action"] for s in b["samples"]]
    nd = rd / "runs.ndjson"
    if nd.exists():
        for line in nd.read_text().splitlines():
            r = json.loads(line)
            for k in out:
                if k[0] == rd.name and k[1] == r["cell"] and k[2] == r["arm"]:
                    out[k]["gov"] = json.loads(r["state_before"]) if isinstance(r["state_before"], str) else r["state_before"]
                    out[k]["nice"] = r["nice"]
                    out[k]["aff"] = r["affinity"]

print(f"{'rundir':<16}{'cell':<14}{'arm':<10}{'n':>3}{'median':>10}{'spread':>8}  gov/epp  nice  aff")
print("-" * 100)
for (rd, cell, arm, unit), e in sorted(out.items()):
    v = [x for x in e["vals"] if x is not None]
    if not v:
        print(f"{rd:<16}{cell:<14}{arm:<10}  0   (no complete reps yet)")
        continue
    sp = 100 * (max(v) - min(v)) / st.median(v)
    g = e["gov"] or {}
    print(f"{rd:<16}{cell:<14}{arm:<10}{len(v):>3}{st.median(v):>10.4f}{sp:>7.1f}%  "
          f"{g.get('governor','?')}/{g.get('epp','?')}  {e['nice'] or '(none)':<12} {e.get('aff','?')}")
