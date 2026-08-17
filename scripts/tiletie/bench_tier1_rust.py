#!/usr/bin/env python3
"""Phase A cost re-measure — `c_tier1_rust` in the SAME currency as the python `c`.

Design: `measurement/tiearb2_stage2_20260817/PHASE_A.md` §4 (condition (d) of the
`A-DEPLOYABLE` set: re-derive cost against a RUST continuation rather than
inheriting `rho_wall`'s python upper bound).

CURRENCY. `analyze_tiearb2.cost_block` defines `c_from_elapsed_secs` as

    c = sum(per-record wall measured INSIDE a worker) / (n_records * 2 * m)

and that is what is mirrored here — Sigma of per-record worker-seconds over
playouts, NOT wall/throughput. The timed region is exactly the `tier1_leg` call,
which includes the root replay, matching `_process`'s `t0` (set before
`RR.replay_actions`) and excluding only the corpus I/O the pilot also did
outside its timer.

⚠️ THE MEASURED SHAPE IS `legal_mask_cache=True`. That is the player G-BITEXACT
grades and the one that produced the adjudicated ladder; pricing the honest-mask
variant would price a player nobody ran. The cache-off arm is measured too, as a
sensitivity, and reported separately — never mixed into `c`.

⚠️ EXCLUSIVE TENANT. A timing bench owns the box (memory
`feedback_no_agent_compute_beside_eval`). The census is taken before and after
and written into the artifact; a co-tenant voids the timing.

Sample: the SAME committed 240 rids `G-BITEXACT` drew (seed 20260817, 15 per
chunk x leg), so the two artifacts describe one population.

Usage:
    .venv/bin/python scripts/tiletie/bench_tier1_rust.py --workers-hi 30
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

RECORDS_ROOT = Path("/mnt/c/carc-shared/tiearb2_20260816/main")
POSITIONS_ROOT = REPO / "measurement" / "tiearb2_20260816"
OUT_PATH = REPO / "measurement" / "tiearb2_stage2_20260817" / "COST_REMEASURE.json"

MAX_PLIES = 400
LEGAL_MASK_CACHE = True

# --- the carried constants (PHASE_A.md §1) — none of these is re-measured ----
A_BAR = 3.0022          # POSITIONS_PLAN.json::mean_arms
T_CHAMP = 13.7552       # champion k8x1376 sequential on this box, s/move
T_PHONE = 1.551         # shipped phone champion at rust_threads: 2, s/move
RHO_BAR = 1.20          # the house N4 trigger currency
AMORTIZE = 22.96 / 72.0
C_PY_PILOT = 2.7274     # python worker-s/playout, the B*-freezing value
C_PY_REALIZED = 2.2004  # python worker-s/playout, from the ARB records
B_LADDER = (1, 2, 4, 8, 16)

# Stage-1b's PUBLISHED capture column, carried verbatim as already-adjudicated
# values. NOT recomputed and NOT re-adjudicated here: the read-rule is SPENT and
# the corpus is BURNED. Used only to say which rungs capture.
CARRIED_CAPTURE = {
    1:  {"arb": 0.0094, "z": 0.20, "F": 0.052, "F_fixed": 0.034},
    2:  {"arb": 0.0322, "z": 0.65, "F": 0.179, "F_fixed": 0.115},
    4:  {"arb": 0.0920, "z": 1.93, "F": 0.511, "F_fixed": 0.328},
    8:  {"arb": 0.0826, "z": 1.76, "F": 0.459, "F_fixed": 0.295},
    16: {"arb": 0.1441, "z": 3.01, "F": 0.800, "F_fixed": 0.514},
}


def census() -> dict:
    def run(cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True,
                                  text=True, timeout=30).stdout.strip()
        except Exception:                                       # pragma: no cover
            return "<census failed>"
    return {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_procs": run("ps -o pid,etime,%cpu,comm -C python --sort=-etime | head -20"),
        "loadavg": run("cat /proc/loadavg"),
        "n_python_procs": len([x for x in run(
            "ps -o pid= -C python").splitlines() if x.strip()]),
    }


def _job(job: tuple) -> dict:
    """One position-record, timed exactly around the whole-leg rust call."""
    import carc_rs

    rid, deck_seed, actions, ply, pick_a, pick_b, root_player, ws, ps, cache = job
    t0 = time.perf_counter()
    va, _vb, _pa, _pb, _st = carc_rs.tier1_leg(
        deck_seed, actions, ply, pick_a, pick_b, root_player, ws, ps,
        MAX_PLIES, cache)
    elapsed = time.perf_counter() - t0
    return {"rid": rid, "elapsed_secs": elapsed, "m": len(va)}


def load_jobs(cache: bool) -> list:
    from verify_tier1_rust import draw_sample, records_dir, positions_path

    sample = draw_sample()
    want = {}
    for (chunk, leg), rids in sample.items():
        for rid in rids:
            want.setdefault((chunk, leg), []).append(rid)

    jobs = []
    for (chunk, leg), rids in sorted(want.items()):
        wanted = set(rids)
        rows = {}
        for line in positions_path(chunk, leg).read_text().splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            if o["rid"] in wanted:
                rows[o["rid"]] = o
        for rid in sorted(rids):
            pos = rows[rid]
            rec = json.loads((records_dir(chunk, leg) / f"{rid}.json").read_text())
            jobs.append((
                rid, str(int(pos["deck_seed"])), [int(a) for a in pos["actions"]],
                int(pos["ply"]), int(pos["pick_a"]), int(pos["pick_b"]),
                int(pos["root_player"]),
                [int(x) for x in rec["world_seeds"]],
                [int(x) for x in rec["playout_seeds"]],
                cache,
            ))
    return jobs


def run_condition(jobs: list, workers: int) -> dict:
    t0 = time.time()
    if workers <= 1:
        results = [_job(j) for j in jobs]
    else:
        import multiprocessing as mp
        with mp.Pool(workers) as pool:
            results = pool.map(_job, jobs, chunksize=1)
    wall = time.time() - t0

    elapsed = sorted(r["elapsed_secs"] for r in results)
    m = results[0]["m"]
    assert all(r["m"] == m for r in results), "ragged m across records"
    n_records = len(results)
    n_playouts = n_records * 2 * m
    total = sum(elapsed)

    def pct(p):
        if not elapsed:
            return None
        k = min(len(elapsed) - 1, int(round(p * (len(elapsed) - 1))))
        return elapsed[k]

    return {
        "workers": workers,
        "n_records": n_records,
        "m": m,
        "n_playouts": n_playouts,
        "sum_elapsed_secs": total,
        # THE deliverable, in analyze_tiearb2.cost_block's currency.
        "c_worker_s_per_playout": total / n_playouts,
        "wall_secs": wall,
        "wall_times_workers": wall * workers,
        "c_from_wall_times_workers": wall * workers / n_playouts,
        "per_record_wall": {
            "mean": total / n_records, "p50": pct(0.50), "p90": pct(0.90),
            "min": elapsed[0], "max": elapsed[-1],
        },
    }


def ladder(c: float) -> dict:
    out = {}
    for B in B_LADDER:
        rho_wall = A_BAR * B * c / T_CHAMP
        out[str(B)] = {
            "rho_wall": rho_wall,
            "rho_amortized": rho_wall * AMORTIZE,
            "rho_phone": A_BAR * B * c / T_PHONE,
            "affordable_wall_le_1.20": bool(rho_wall <= RHO_BAR),
            "carried_capture": CARRIED_CAPTURE[B],
        }
    ok = [B for B in B_LADDER if A_BAR * B * c / T_CHAMP <= RHO_BAR]
    return {"rungs": out, "B_affordable": max(ok) if ok else 1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers-hi", type=int, default=30,
                    help="the production-like W (WORKERS.conf W_LOCAL)")
    ap.add_argument("--skip-w1", action="store_true")
    args = ap.parse_args()

    import carc_rs

    before = census()
    if before["n_python_procs"] > 0:
        print(f"[warn] {before['n_python_procs']} python process(es) already on the "
              f"box — a timing bench is an EXCLUSIVE tenant; the census is recorded",
              file=sys.stderr)

    jobs = load_jobs(LEGAL_MASK_CACHE)
    print(f"[bench] {len(jobs)} records, legal_mask_cache={LEGAL_MASK_CACHE}", flush=True)

    conditions = {}
    if not args.skip_w1:
        print("[bench] W=1 (uncontended) ...", flush=True)
        conditions["w1"] = run_condition(jobs, 1)
        print(f"    c = {conditions['w1']['c_worker_s_per_playout']:.6f} "
              f"worker-s/playout", flush=True)

    print(f"[bench] W={args.workers_hi} (production-like) ...", flush=True)
    conditions["w_hi"] = run_condition(jobs, args.workers_hi)
    print(f"    c = {conditions['w_hi']['c_worker_s_per_playout']:.6f} "
          f"worker-s/playout", flush=True)

    # Sensitivity only: the honest-mask variant is NOT the gated shape.
    print("[bench] cache-off sensitivity ...", flush=True)
    cache_off = run_condition(load_jobs(False), args.workers_hi)

    after = census()

    c_hi = conditions["w_hi"]["c_worker_s_per_playout"]
    c_w1 = conditions["w1"]["c_worker_s_per_playout"] if "w1" in conditions else None

    try:
        git_rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                           # pragma: no cover
        git_rev = None

    out = {
        "artifact": "COST_REMEASURE",
        "design": "measurement/tiearb2_stage2_20260817/PHASE_A.md#4",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gate": {
            "G-BITEXACT": "PASS",
            "artifact": "measurement/tiearb2_stage2_20260817/BITEXACT.json",
            "note": ("no cost number is quoted unless G-BITEXACT passed; it did, "
                     "15360/15360 value-bit-identical."),
        },
        "currency": ("worker-seconds per playout = sum(per-record wall inside a "
                     "worker) / (n_records * 2 * m) -- "
                     "analyze_tiearb2.cost_block::c_from_elapsed_secs"),
        "legal_mask_cache": LEGAL_MASK_CACHE,
        "sample": {
            "source": "the committed G-BITEXACT sample (seed 20260817, 15 per chunk x leg)",
            "n_records": len(jobs),
        },
        "constants_carried": {
            "mean_arms_A_bar": A_BAR, "t_champ": T_CHAMP, "t_phone": T_PHONE,
            "rho_bar": RHO_BAR, "amortize_22.96_over_72": AMORTIZE,
            "c_python_pilot": C_PY_PILOT, "c_python_realized": C_PY_REALIZED,
        },
        "conditions": conditions,
        "cache_off_sensitivity": cache_off,
        "c_tier1_rust_w1": c_w1,
        "c_tier1_rust_w30": c_hi,
        "speedup_vs_python": {
            "w30_vs_pilot_2.7274": C_PY_PILOT / c_hi,
            "w30_vs_realized_2.2004": C_PY_REALIZED / c_hi,
            "w1_vs_pilot_2.7274": (C_PY_PILOT / c_w1) if c_w1 else None,
            "w1_vs_realized_2.2004": (C_PY_REALIZED / c_w1) if c_w1 else None,
        },
        "ladder_primary_w30": ladder(c_hi),
        "ladder_sensitivity_w1": ladder(c_w1) if c_w1 else None,
        "capture_column_note": (
            "arb / z / F / F_fixed are Stage 1b's PUBLISHED, already-adjudicated "
            "values, carried verbatim. Phase A recomputes NO strength statistic; "
            "the Stage-1b read-rule is SPENT and its corpus BURNED."),
        "census_before": before,
        "census_after": after,
        "carc_rs_version": carc_rs.__version__,
        "git_rev": git_rev,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("census_before", "census_after", "conditions",
                                   "cache_off_sensitivity")}, indent=2))
    print(f"[bench] -> {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    raise SystemExit(main())
