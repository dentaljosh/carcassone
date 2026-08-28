#!/usr/bin/env python3
"""Turn the raw `tier1_costprobe` JSONs into the PROFILE_TIER1 breakdown table.

Two corrections are applied and both are reported, never silently folded:

  1. **Timer tax.** Each stage boundary costs one `Instant::now()`
     (`timer_now_ns`, measured in-process). A stage's accumulated nanoseconds
     therefore carry one timer call per tick it took. Tick counts are derivable
     from the counters, so the corrected stage time is
     `ns - n_ticks * timer_now_ns`, and the corrected shares are renormalised
     against the corrected inner total.
  2. **Shadow fidelity.** Shares are of the SHADOW's inner time; the absolute
     s/playout of record is the BASELINE (`carc_core::tier1::tier1_playout`,
     uninstrumented). `shadow_fidelity_ratio` states how far apart they are.

Usage: analyze_profile.py <probe_none.json> [probe_cache.json ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def tick_counts(c: dict, cache: bool) -> dict:
    """Timer calls charged to each stage, from the loop structure in main.rs."""
    scored = c["decisions"] - c["rule1"] - c["single_candidate"]
    loop_iters = c["plies"] + c.get("playouts", 0)
    return {
        "repr_key": c["decisions"] if cache else 0,
        # hit -> 1 tick; miss -> 2 (one before the mask build, one after insert)
        "memo_lookup": (c["memo_hits"] + 2 * c["memo_misses"]) if cache else 0,
        "legal_mask": c["mask_builds"],
        "legal_collect": c["mask_builds"],
        "filter": c["decisions"] - c["rule1"],
        "decode": c["candidate_evals"],
        "clone": c["candidate_evals"],
        "apply": c["candidate_evals"],
        "score": c["candidate_evals"],
        "argmax": scored,
        "rng": scored,
        "advance": loop_iters,
        "terminal": loop_iters,
    }


def analyse(path: Path) -> dict:
    o = json.loads(path.read_text())
    c = dict(o["counters"])
    c["playouts"] = o["n_playouts"]
    ticks = tick_counts(c, o["legal_mask_cache"])
    timer = o["timer_now_ns"]
    np_ = o["n_playouts"]

    rows = []
    corrected_total = 0.0
    for name, st in o["stages_ns_total"].items():
        raw = float(st["ns"])
        tax = ticks[name] * timer
        cor = max(raw - tax, 0.0)
        corrected_total += cor
        rows.append({"stage": name, "raw_ns": raw, "timer_tax_ns": tax,
                     "corrected_ns": cor, "ticks": ticks[name]})
    resid = float(o["residual"]["ns"])
    corrected_total += max(resid, 0.0)
    rows.append({"stage": "residual", "raw_ns": resid, "timer_tax_ns": 0.0,
                 "corrected_ns": max(resid, 0.0), "ticks": 0})

    base = o["baseline_s_per_playout"]
    for r in rows:
        r["share"] = r["corrected_ns"] / corrected_total if corrected_total else 0.0
        r["s_per_playout"] = r["share"] * base       # shares projected onto the baseline
        r["us_per_playout"] = r["s_per_playout"] * 1e6
    rows.sort(key=lambda r: -r["corrected_ns"])

    # cost-vs-plies fit: secs = a + b * plies, OLS
    pts = [(p["plies"], p["secs"]) for p in o["per_playout"]]
    n = len(pts)
    sx = sum(p for p, _ in pts)
    sy = sum(s for _, s in pts)
    sxx = sum(p * p for p, _ in pts)
    sxy = sum(p * s for p, s in pts)
    den = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / den if den else float("nan")
    a = (sy - b * sx) / n if den else float("nan")
    ybar = sy / n
    ss_tot = sum((s - ybar) ** 2 for _, s in pts)
    ss_res = sum((s - (a + b * p)) ** 2 for p, s in pts)
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")

    # per-root-ply groups — the fit above is poor for a reason worth showing
    groups = {}
    for p in o["per_playout"]:
        groups.setdefault(p["root_ply"], []).append(p)
    gtab = []
    for k in sorted(groups):
        v = groups[k]
        mp = sum(x["plies"] for x in v) / len(v)
        mms = sum(x["secs"] for x in v) / len(v) * 1000
        gtab.append({"root_ply": k, "n": len(v), "mean_plies": mp,
                     "mean_ms": mms, "ms_per_ply": mms / mp})

    return {
        "file": path.name,
        "mode": o["mode"],
        "legal_mask_cache": o["legal_mask_cache"],
        "n_playouts": np_,
        "baseline_s_per_playout": base,
        "shadow_fidelity_ratio": o["shadow_fidelity_ratio"],
        "instrumentation_tax": o["instrumentation_tax"],
        "timer_now_ns": timer,
        "identity_gate": o["identity_gate"],
        "counters": o["counters"],
        "vmhwm_kb": o["vmhwm_kb"],
        "alloc": o.get("alloc_census_baseline"),
        "rows": rows,
        "fit": {"intercept_s": a, "slope_s_per_ply": b, "r2": r2, "n": n,
                "plies_min": min(p for p, _ in pts), "plies_max": max(p for p, _ in pts)},
        "by_root_ply": gtab,
    }


def main() -> int:
    out = [analyse(Path(p)) for p in sys.argv[1:]]
    for o in out:
        print(f"\n=== {o['file']}  mode={o['mode']}  cache={o['legal_mask_cache']} ===")
        print(f"  baseline {o['baseline_s_per_playout']*1000:.2f} ms/playout over "
              f"{o['n_playouts']} playouts; shadow fidelity {o['shadow_fidelity_ratio']:.4f}, "
              f"instr tax {o['instrumentation_tax']:.4f}, timer {o['timer_now_ns']:.1f} ns")
        print(f"  {'stage':<16}{'ms/playout':>12}{'share':>9}{'timer tax %':>13}")
        for r in o["rows"]:
            if r["corrected_ns"] <= 0 and r["raw_ns"] <= 0:
                continue
            tt = r["timer_tax_ns"] / r["raw_ns"] * 100 if r["raw_ns"] else 0.0
            print(f"  {r['stage']:<16}{r['us_per_playout']/1000:>12.4f}"
                  f"{r['share']*100:>8.2f}%{tt:>12.1f}%")
        f = o["fit"]
        print(f"  cost-vs-plies: secs = {f['intercept_s']*1000:.3f} ms + "
              f"{f['slope_s_per_ply']*1000:.4f} ms/ply   R2={f['r2']:.3f} "
              f"(n={f['n']}, plies {f['plies_min']}-{f['plies_max']})")
        print(f"  {'root_ply':>9}{'n':>5}{'mean_plies':>12}{'mean_ms':>10}{'ms/ply':>9}")
        for g in o["by_root_ply"]:
            print(f"  {g['root_ply']:>9}{g['n']:>5}{g['mean_plies']:>12.1f}"
                  f"{g['mean_ms']:>10.2f}{g['ms_per_ply']:>9.4f}")
        if o["alloc"]:
            print(f"  alloc: {o['alloc']['allocs_per_playout']:.0f} allocs/playout, "
                  f"{o['alloc']['bytes_per_playout']/1e6:.2f} MB/playout")
        print(f"  peak RSS {o['vmhwm_kb']/1024:.1f} MiB")
    Path("ANALYSIS.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
