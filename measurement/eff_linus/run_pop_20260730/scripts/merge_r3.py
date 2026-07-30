#!/usr/bin/env python3
"""eff_linus round 3 merger — Pop!_OS arm vs the COMMITTED round-2 WSL arm.

Reuses wsl_vs_native_merge.py's extraction rules verbatim:
  champ_* -> budgets[0].overall.p50_s   (p50 seconds per decision)
  net_*   -> rows[0].timings.forward.p50_ms

The WSL arm is NOT re-run (dual boot); it is read out of
measurement/eff_linus/run_laptop_20260729/.
"""
from __future__ import annotations
import json, sys, statistics as st
from pathlib import Path

REPO = Path("/home/doctor/projects/carcassone")
WSL_RUN = REPO / "measurement/eff_linus/run_laptop_20260729"


def central(cell: str, child: dict):
    if cell.startswith("champ_"):
        b = (child.get("budgets") or [])
        return (float(b[0]["overall"]["p50_s"]), "p50_s_per_move") if b else (None, "p50_s_per_move")
    rows = child.get("rows") or []
    if not rows:
        return None, "forward_p50_ms"
    tim = (rows[0].get("timings") or {}).get("forward")
    return (float(tim["p50_ms"]), "forward_p50_ms") if tim else (None, "forward_p50_ms")


def facts(cell: str, child: dict) -> dict:
    if cell.startswith("champ_"):
        cy = child.get("cython") or {}
        m = child.get("machine") or {}
        return {"python": m.get("python"), "platform": m.get("platform"),
                "leaf_active": cy.get("leaf_active"), "leaf_path": cy.get("leaf_path"),
                "use_cy_leaf_flag": cy.get("use_cy_leaf_flag"),
                "use_flat_leaf": cy.get("use_flat_leaf"),
                "champion_id": (child.get("champion") or {}).get("id"),
                "n_positions": child.get("n_positions")}
    man = child.get("manifest") or {}
    r0 = (child.get("rows") or [{}])[0]
    return {"python": man.get("python"), "platform": man.get("platform"),
            "torch_version": man.get("torch_version"),
            "cuda_available": man.get("cuda_available"),
            "ckpt_sha256": man.get("ckpt_sha256"),
            "n_params": (r0.get("rep") or {}).get("n_params"),
            "torch_num_threads": r0.get("torch_num_threads")}


def agg(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"samples": vals, "median": st.median(vals), "min": min(vals), "max": max(vals),
            "spread_pct": 100.0 * (max(vals) - min(vals)) / st.median(vals)}


def collect_pop(rundirs: list[Path]) -> dict:
    out: dict = {}
    for rd in rundirs:
        for p in sorted((rd / "cells").glob("*.json")):
            stem = p.stem              # cell__pop_arm__repN
            cell, arm, rep = stem.split("__")
            child = json.loads(p.read_text())
            v, unit = central(cell, child)
            e = out.setdefault(cell, {}).setdefault(arm, {"samples": [], "facts": [], "unit": unit,
                                                          "actions": None})
            e["samples"].append(v)
            e["facts"].append(facts(cell, child))
            if cell.startswith("champ_") and e["actions"] is None:
                e["actions"] = [s["action"] for s in child["budgets"][0]["samples"]]
    for cell, arms in out.items():
        for arm, e in arms.items():
            e.update(agg(e["samples"]) or {})
    return out


def collect_wsl() -> dict:
    merged = next(WSL_RUN.glob("wsl_vs_native_ab_*.json"))
    d = json.loads(merged.read_text())
    res = {}
    for cell, arms in d["cells"].items():
        res[cell] = {"wsl": arms["wsl"], "win": arms["win"]}
    # per-cell chosen-action sequence for the determinism cross-check
    for cell in list(res):
        f = WSL_RUN / "cells" / f"{cell}__wsl__rep1.json"
        if f.exists():
            c = json.loads(f.read_text())
            if cell.startswith("champ_"):
                res[cell]["wsl_actions"] = [s["action"] for s in c["budgets"][0]["samples"]]
    return res


def main():
    rundirs = [Path(a) for a in sys.argv[1:-1]]
    outp = Path(sys.argv[-1])
    pop = collect_pop(rundirs)
    wsl = collect_wsl()
    table = []
    for cell in ["champ_k1x32", "champ_k4x172", "net_cuda_b1", "net_cpu_1t"]:
        if cell not in pop:
            continue
        w = wsl.get(cell, {}).get("wsl")
        for arm in sorted(pop[cell]):
            e = pop[cell][arm]
            row = {"cell": cell, "pop_arm": arm,
                   "unit": e["unit"],
                   "pop_median": e["median"], "pop_spread_pct": e["spread_pct"],
                   "pop_samples": e["samples"],
                   "wsl_median": (w or {}).get("median"),
                   "wsl_spread_pct": (w or {}).get("spread_pct"),
                   "wsl_samples": (w or {}).get("samples"),
                   "win_median": (wsl.get(cell, {}).get("win") or {}).get("median")}
            if row["wsl_median"]:
                row["ratio_pop_over_wsl"] = row["pop_median"] / row["wsl_median"]
                row["speedup_wsl_over_pop"] = row["wsl_median"] / row["pop_median"]
                # is the gap bigger than either arm's own rep spread?
                row["gap_exceeds_run_spread"] = (
                    abs(row["pop_median"] - row["wsl_median"]) / row["wsl_median"] * 100.0
                    > max(row["pop_spread_pct"], row["wsl_spread_pct"]))
            if cell.startswith("champ_") and e.get("actions") is not None:
                row["actions_identical_to_wsl"] = (e["actions"] == wsl.get(cell, {}).get("wsl_actions"))
            table.append(row)
    doc = {"schema": "eff_linus-round3/v1", "table": table, "pop_facts": {
        c: {a: pop[c][a]["facts"][0] for a in pop[c]} for c in pop}}
    outp.write_text(json.dumps(doc, indent=1))
    hdr = f"{'cell':<14}{'pop_arm':<10}{'pop':>10}{'wsl':>10}{'ratio':>9}{'spr_pop':>9}{'spr_wsl':>9}  det"
    print(hdr); print("-" * len(hdr))
    for r in table:
        print(f"{r['cell']:<14}{r['pop_arm']:<10}{r['pop_median']:>10.4f}"
              f"{(r['wsl_median'] or 0):>10.4f}{r.get('ratio_pop_over_wsl', 0):>9.3f}"
              f"{r['pop_spread_pct']:>8.1f}%{r.get('wsl_spread_pct', 0):>8.1f}%  "
              f"{r.get('actions_identical_to_wsl', '-')}")
    print(f"\nwrote {outp}")


if __name__ == "__main__":
    sys.exit(main())
