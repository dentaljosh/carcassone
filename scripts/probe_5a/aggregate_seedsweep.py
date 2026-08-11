#!/usr/bin/env python3
"""Probe §5A — aggregate the seed sweep into the read-out.

Per-config mean±std of regret_reduction% and net-alone τ; then the pre-registered
Δ_indep_tempo as a PAIRED-per-seed difference (all_three − both54), which cancels
the shared-per-seed init draw. Plus the tempo-vs-farm/bag magnitude comparison and
the both54-vs-both44 contamination check (did zero-padding kill farm+bag?)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "measurement/probe_5a/seedsweep")
SEEDS = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["0", "1", "2", "3"])]
CONFIGS = ["both44", "both54", "tempo_only", "all_three"]


def read(cfg, seed):
    p = OUT / f"{cfg}_s{seed}" / "V4_listwise" / "summary.json"
    if not p.exists():
        return None
    s = json.loads(p.read_text())["overall"]
    return {"rr": s["regret_reduction_pct"], "tau": s["net_alone"]["tau"],
            "best_alpha": s["best_alpha"], "beats": s["beats_leaf"]}


def main():
    data = {c: {s: read(c, s) for s in SEEDS} for c in CONFIGS}
    print(f"seeds={SEEDS}\n")
    print(f"{'config':12s} {'mean rr%':>10s} {'std':>6s} {'mean τ':>8s}   per-seed rr%")
    stats = {}
    for c in CONFIGS:
        vals = [data[c][s] for s in SEEDS if data[c][s] is not None]
        if not vals:
            print(f"{c:12s}  <no runs yet>"); continue
        rr = np.array([v["rr"] for v in vals]); tau = np.array([v["tau"] for v in vals])
        stats[c] = {"rr_mean": float(rr.mean()), "rr_std": float(rr.std()),
                    "tau_mean": float(tau.mean()), "n": len(vals),
                    "per_seed": {s: (data[c][s]["rr"] if data[c][s] else None) for s in SEEDS}}
        ps = " ".join(f"{data[c][s]['rr']:+.1f}" if data[c][s] else "  --" for s in SEEDS)
        print(f"{c:12s} {rr.mean():+10.1f} {rr.std():6.1f} {tau.mean():+8.3f}   {ps}")

    if not all(c in stats for c in ("both54", "all_three", "tempo_only")):
        print("\n[incomplete] key configs missing — rerun when the sweep finishes.")
        return

    # paired Δ_indep (per shared seed) — cancels the shared init draw
    paired = [(data["all_three"][s]["rr"] - data["both54"][s]["rr"])
              for s in SEEDS if data["all_three"][s] and data["both54"][s]]
    paired = np.array(paired)
    d_mean, d_std = float(paired.mean()), float(paired.std())
    d_sem = d_std / max(1, np.sqrt(len(paired)))

    print(f"\nΔ_indep_tempo (paired all_three − both54) = {d_mean:+.2f} ± {d_std:.2f}pp "
          f"(SEM {d_sem:.2f}, n={len(paired)})   per-seed: {[round(x,1) for x in paired]}")
    print(f"tempo_only mean = {stats['tempo_only']['rr_mean']:+.1f}%   vs "
          f"both44 (natural farm/bag) mean = {stats.get('both44',{}).get('rr_mean','?')}%")
    if "both44" in stats:
        print(f"contamination check: both54 mean {stats['both54']['rr_mean']:+.1f}% vs "
              f"both44 mean {stats['both44']['rr_mean']:+.1f}% "
              f"(if both54 << both44, zero-padding suppresses farm+bag -> use both44 as the baseline)")

    # verdict on the PAIRED Δ (2σ ~ SEM-based)
    if d_mean - 2 * d_sem >= 3.0:
        v = "CRACK (H-5A-live) — tempo adds a separated 3rd axis over farm+bag (≥3pp, 2σ)"
    elif d_mean + 2 * d_sem < 1.0:
        v = "CEILING-EARNED (H-5A-inert) — tempo adds <1pp; three independent axes"
    else:
        v = "WEAK/AMBIGUOUS — Δ within noise of the 1–3pp band; report as inconclusive-but-tempo-non-inert"
    print(f"\n===== §5A SEED-SWEPT VERDICT: {v} =====")
    (OUT / "seedsweep_verdict.json").write_text(json.dumps(
        {"seeds": SEEDS, "stats": stats, "delta_indep_paired_mean": d_mean,
         "delta_indep_paired_std": d_std, "delta_indep_sem": d_sem,
         "tempo_only_mean": stats["tempo_only"]["rr_mean"], "verdict": v}, indent=2))
    print(f"[saved] {OUT/'seedsweep_verdict.json'}")


if __name__ == "__main__":
    main()
