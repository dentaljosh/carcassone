#!/usr/bin/env python3
"""Consolidate the pipeline-bench CSVs into one tidy throughput table.

Reads the per-box per-pass sweep CSVs produced by bench_pipeline_sweep.py
(self-play throughput + Phase-3 eval) and emits a single de-duplicated table,
collapsing repeat measurements into mean±std. This is the THROUGHPUT record;
it is deliberately separate from experiments/results.csv (which is the ELO /
strength source-of-truth — throughput rows do not belong there).

Passes (parsed from filename sweep_[<pass>_]<box>.csv):
  full_sweep   sweep_<box>.csv              n=1/cell, the broad 1-D lever sweep
  confirm      sweep_confirm_<box>.csv      n=3/cell, verdict-grade re-measure of the doctrine-flip cells
  deploy       sweep_deploy_<box>.csv       n=3/cell, the stacked per-box deploy config
  eval_wsweep  sweep_evalw_<box>.csv        n=1/cell, Phase-3 eval_net_vs_heuristic W-sweep (mode=eval)

Regenerate after any new bench:  python scripts/aggregate_bench_results.py
"""
from __future__ import annotations

import csv
import statistics as st
from collections import defaultdict
from pathlib import Path

BENCH_DIR = Path("/mnt/c/carc-shared/bench")
OUT = Path(__file__).resolve().parent.parent / "experiments" / "bench_pipeline_results.csv"
BOXES = ("5800x", "xeon", "laptop")
PASS_ORDER = {"full_sweep": 0, "confirm": 1, "deploy": 2, "eval_wsweep": 3}

# the per-box self-play config selected for production (DECISIONS 2026-06-01).
# signature: (box, orchestrator, W, orch_shards, orch_fp16)
CHOSEN = {
    ("5800x", "False", "16", "1", "False"),   # orch-off W=16, no fp16  -> 14.70
    ("xeon",  "True",  "18", "2", "False"),    # orch_shards=2           -> 6.99
    ("laptop", "False", "10", "1", "False"),   # orch-off W=10           -> 19.26
}


def pass_of(fname: str) -> tuple[str, str]:
    """(pass, box) from a sweep filename."""
    stem = fname[len("sweep_"):-len(".csv")]
    for box in BOXES:
        if stem == box:
            return "full_sweep", box
        if stem == f"confirm_{box}":
            return "confirm", box
        if stem == f"deploy_{box}":
            return "deploy", box
        if stem == f"evalw_{box}":
            return "eval_wsweep", box
    raise ValueError(f"unrecognized bench file: {fname}")


def fnum(rows, key):
    vals = []
    for r in rows:
        try:
            vals.append(float(r[key]))
        except (ValueError, KeyError, TypeError):
            pass
    return vals


def main() -> int:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for f in sorted(BENCH_DIR.glob("sweep_*.csv")):
        pas, box = pass_of(f.name)
        for r in csv.DictReader(open(f)):
            groups[(pas, box, r["axis"])].append(r)

    out_rows = []
    for (pas, box, axis), rows in groups.items():
        mvps = fnum(rows, "moves_per_s")
        r0 = rows[0]
        mode = "eval" if pas == "eval_wsweep" else "selfplay"
        sig = (box, r0["orchestrator"], r0["W"], r0["orch_shards"], r0["orch_fp16"])
        # bottleneck: most common across reps
        bn = max(set(r["bottleneck"] for r in rows),
                 key=lambda b: sum(1 for r in rows if r["bottleneck"] == b))
        out_rows.append({
            "pass": pas, "mode": mode, "box": box, "config": axis,
            "orchestrator": r0["orchestrator"], "W": r0["W"],
            "orch_shards": r0["orch_shards"], "orch_fp16": r0["orch_fp16"],
            "mcts_batch": r0["mcts_batch"], "sims": r0["sims"],
            "n_reps": len(mvps),
            "mvps_mean": round(st.mean(mvps), 2) if mvps else "",
            "mvps_std": round(st.pstdev(mvps), 2) if len(mvps) > 1 else 0.0,
            "gpu_pw_p50": round(st.mean(fnum(rows, "gpu_pw_p50")), 1) if fnum(rows, "gpu_pw_p50") else "",
            "gpu_util_p50": round(st.mean(fnum(rows, "gpu_util_p50")), 0) if fnum(rows, "gpu_util_p50") else "",
            "cpu_pct_p50": round(st.mean(fnum(rows, "cpu_pct_p50")), 1) if fnum(rows, "cpu_pct_p50") else "",
            "load_p50": round(st.mean(fnum(rows, "loadavg_p50")), 1) if fnum(rows, "loadavg_p50") else "",
            "bottleneck": bn,
            "status": r0["status"],
            "selected_selfplay": "yes" if (mode == "selfplay" and sig in CHOSEN) else "",
        })

    out_rows.sort(key=lambda r: (r["mode"], r["box"], PASS_ORDER[r["pass"]],
                                 -(r["mvps_mean"] if isinstance(r["mvps_mean"], float) else 0)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(out_rows[0].keys())
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {len(out_rows)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
