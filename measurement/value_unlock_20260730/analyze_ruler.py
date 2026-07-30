#!/usr/bin/env python3
"""Adjudicate the pre-registered STEP-3 bar (READOUT.md §3.4) off the solver_score
report, using the project's OWN conventions:

  * paired sign-z on per-root solver_regret vs a chosen baseline
    -> scripts/canonical_az/analyze_v210_screen.py:33
  * bootstrap-over-roots (B=10,000) sigma for mean tau and paired dtau
    -> scripts/canonical_az/solver_score_agent.py:bootstrap_block

Baseline is `curve125` (the CHAMPION's leaf), which is what the bar is written
against; `v29_leaf` (curve100) is also reported as the harness's own baseline.
Read-only. Prints JSON.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "canonical_az"))


def paired(roots, name, baseline):
    """analyze_v210_screen.py:24-38 convention, verbatim arithmetic."""
    better = worse = tie = 0
    dsum = 0.0
    for r in roots:
        rb = r["rankers"][baseline]["solver_regret"]
        rv = r["rankers"][name]["solver_regret"]
        dsum += rv - rb
        if rv < rb:
            better += 1
        elif rv > rb:
            worse += 1
        else:
            tie += 1
    # sign of z is oriented so POSITIVE = `name` beats `baseline` (lower regret).
    z = (better - worse) / math.sqrt(better + worse) if (better + worse) else 0.0
    return {
        "vs": baseline, "better": better, "worse": worse, "tie": tie,
        "sign_z": round(z, 3), "mean_dregret": round(dsum / len(roots), 4),
    }


def tau_boot(roots, name, baseline, B=10_000, seed=0):
    rng = np.random.default_rng(seed)
    n = len(roots)
    idx = rng.integers(0, n, size=(B, n))
    t = np.array([r["rankers"][name]["tau"] for r in roots], dtype=np.float64)
    tb = np.array([r["rankers"][baseline]["tau"] for r in roots], dtype=np.float64)
    out = {
        "tau_mean": round(float(np.nanmean(t)), 4),
        "tau_sigma_boot": round(float(np.nanstd(np.nanmean(t[idx], axis=1))), 5),
        "n_tau_nan": int(np.isnan(t).sum()),
    }
    ok = np.isfinite(t) & np.isfinite(tb)
    dt = t[ok] - tb[ok]
    if dt.size:
        idx2 = rng.integers(0, dt.size, size=(B, dt.size))
        sig = float(dt[idx2].mean(axis=1).std())
        out["dtau_vs_%s_mean" % baseline] = round(float(dt.mean()), 4)
        out["dtau_sigma_boot"] = round(sig, 5)
        out["dtau_z"] = round(float(dt.mean() / sig), 3) if sig > 0 else None
        out["n_paired"] = int(dt.size)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else str(
        REPO / "measurement" / "value_unlock_20260730" / "solver_score_value_unlock.json")
    rep = json.loads(Path(path).read_text())
    roots = rep["per_root"]
    names = list(rep["rankers"])
    res = {
        "report": path,
        "n_roots": len(roots),
        "n_scored": rep["n_scored"], "n_skipped": rep["n_skipped"], "n_errors": rep["n_errors"],
        "max_k": rep["max_k"],
        "checkpoints": rep["checkpoints"],
        "aggregate": rep["aggregate"],
        "arms": {},
    }
    for nm in names:
        ent = {"aggregate": rep["aggregate"][nm]}
        for base in ("curve125", "v29_leaf"):
            if base in names and nm != base:
                ent["paired_vs_" + base] = paired(roots, nm, base)
        if "curve125" in names and nm != "curve125":
            ent["tau_boot_vs_curve125"] = tau_boot(roots, nm, "curve125")
        res["arms"][nm] = ent

    # --- the PRE-REGISTERED adjudication (READOUT.md 3.4) ---
    cand, base = "value_unlock_v1", "curve125"
    if cand in names and base in names:
        rc = rep["aggregate"][cand]["solver_regret_mean"]
        rb = rep["aggregate"][base]["solver_regret_mean"]
        z = res["arms"][cand]["paired_vs_" + base]["sign_z"]
        if rc < rb and z >= 2.0:
            verdict = "YES"
        elif rc > rb and z <= -2.0:
            verdict = "NO"
        else:
            verdict = "AMBIGUOUS"
        res["PREREGISTERED_VERDICT"] = {
            "candidate": cand, "baseline": base,
            "candidate_regret_mean": rc, "baseline_regret_mean": rb,
            "paired_sign_z": z, "verdict": verdict,
        }
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
