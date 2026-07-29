#!/usr/bin/env python3
"""W-ladder AGGREGATE throughput bench — how many moves/s does a whole box do?

WHY THIS EXISTS — ``bench_champion.py`` answers "what does ONE decision cost when
nothing else is running" (single-stream latency). That is the number a phone pays.
It is NOT the number a cluster box is worth: gen/eval run W independent worker
processes and the box's value is the AGGREGATE moves/s at its best W. On the local
5900XT that optimum is W=16 (DRAM-latency wall, not core count). This driver
measures the same curve on any box, so an M5 (4P+6E, unified memory) can be judged
on the axis that actually decides whether it joins the cluster.

WHAT IT DOES — for each W in the ladder it spawns W **independent** ``bench_champion.py``
processes (distinct seeds, ``OMP_NUM_THREADS=1`` each, no shared memory, no
orchestrator), waits for all of them, and reads their JSONs. Worker independence is
the point: it is exactly the shape of a ``--shared-claim`` gen/eval fan-out, and it
means the only coupling between workers is the hardware (cores, memory bandwidth,
thermal headroom) — which is what we are trying to measure.

THE THROTTLE TEST — the ladder runs in ASCENDING W and then repeats the W=1 cell at
the end (labelled ``1_post``). A ``1_post`` that is slower than the opening W=1 cell
is direct, sudo-free evidence that the box got hot and stayed hot. ``pmset -g therm``
is sampled throughout each cell as a second, independent witness (it needs no sudo,
unlike ``powermetrics``).

MEASUREMENT ONLY. Spawns nothing but the existing bench, touches no champion, no
config, no claim.

Usage (path-stable; safe under the project's "Claude Code drops ``cd`` in SSH" rule)::

    ~/m5_bench_20260728/.venv/bin/python ~/m5_bench_20260728/w_ladder.py --ladder 1,4
    nohup ~/m5_bench_20260728/.venv/bin/python -u ~/m5_bench_20260728/w_ladder.py \
        > ~/m5_bench_20260728/w_ladder.log 2>&1 < /dev/null &

Output: ``results/w_ladder_<host>_<stamp>.json``, rewritten atomically after EVERY
cell so it is harvestable live and a killed run still yields the finished cells.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LADDER = "1,4,6,8,10,1"
DEFAULT_BUDGET = "k4x688"          # the champion of record (PRODUCTION.yaml fair_deploy)


# --------------------------------------------------------------------------- #
# Cheap, sudo-free machine + thermal probes. Every one is guarded; none is      #
# required for the bench to produce a number.                                   #
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], timeout: float = 10) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:                                          # noqa: BLE001
        return None
    out = (r.stdout or "").strip()
    return out or None


def loadavg() -> list[float] | None:
    try:
        return list(os.getloadavg())
    except OSError:
        return None


def top_procs(n: int = 6) -> list[str]:
    """Who ELSE is on this box, recorded per cell so contention is auditable.

    A laptop is not a cluster node: it runs a browser, a music player and — on macOS —
    background indexers like ``mediaanalysisd`` that can sit on two cores for days.
    Any aggregate-throughput number taken here has to be read next to this list, so it
    goes IN the JSON rather than into someone's memory of the terminal."""
    txt = _run(["ps", "-Ao", "pid,pcpu,comm"], timeout=15)
    if not txt:
        return []
    rows = []
    for line in txt.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3:
            try:
                rows.append((float(parts[1]), line.strip()))
            except ValueError:
                continue
    rows.sort(key=lambda r: -r[0])
    return [r[1][:160] for r in rows[:n]]


def thermal_probe() -> dict:
    """One-shot thermal state. ``pmset -g therm`` is the sudo-free throttle read.

    On Apple Silicon it reports CPU_Speed_Limit / CPU_Scheduler_Limit as percentages;
    anything below 100 is the OS actively de-rating the CPU. ``powermetrics`` would
    give more but is root-only, so it is deliberately not attempted here."""
    out: dict = {}
    if platform.system() != "Darwin":
        return out
    txt = _run(["pmset", "-g", "therm"], timeout=8)
    if txt:
        out["raw"] = txt
        for line in txt.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                k = k.strip().lstrip("* ").strip()
                v = v.strip()
                try:
                    out[k] = int(v)
                except ValueError:
                    out[k] = v
    return out


def machine_info() -> dict:
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "node": platform.node(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
    }
    if platform.system() == "Darwin":
        for key, name in (("hw.model", "hw_model"),
                          ("machdep.cpu.brand_string", "cpu_brand"),
                          ("hw.memsize", "mem_bytes"),
                          ("hw.perflevel0.physicalcpu", "p_cores"),
                          ("hw.perflevel1.physicalcpu", "e_cores"),
                          ("hw.physicalcpu", "physical_cpus")):
            v = _run(["sysctl", "-n", key])
            if v is None:
                continue
            try:
                info[name] = int(v)
            except ValueError:
                info[name] = v
        info["os_version"] = _run(["sw_vers", "-productVersion"])
        # MacBook (fanless Air vs actively-cooled Pro/Mini/Studio) is the whole
        # thermal story, so spend the one extra second to name the chassis.
        sp = _run(["system_profiler", "SPHardwareDataType"], timeout=45)
        if sp:
            info["system_profiler_hardware"] = sp
            for line in sp.splitlines():
                if "Model Name" in line:
                    info["model_name"] = line.split(":", 1)[1].strip()
                elif "Model Identifier" in line:
                    info["model_identifier"] = line.split(":", 1)[1].strip()
    return info


class ThermalSampler(threading.Thread):
    """Samples ``pmset -g therm`` every ``period`` s for the life of one cell.

    ⚠️ The halt flag is ``_halt``, NOT ``_stop``: ``threading.Thread`` already owns a
    private ``_stop()`` METHOD, and ``Thread.join()`` calls it. Binding an Event over
    that name makes every ``join()`` die with ``TypeError: 'Event' object is not
    callable`` — which is exactly how this failed on its first real launch."""

    def __init__(self, period: float = 10.0) -> None:
        super().__init__(daemon=True)
        self.period = period
        self.samples: list[dict] = []
        self._halt = threading.Event()

    def run(self) -> None:
        while not self._halt.is_set():
            t = thermal_probe()
            if t:
                t["t"] = time.time()
                t["loadavg"] = loadavg()
                self.samples.append(t)
            self._halt.wait(self.period)

    def stop(self) -> list[dict]:
        self._halt.set()
        self.join(timeout=15)
        return self.samples


# --------------------------------------------------------------------------- #
# One cell = W concurrent independent bench_champion.py processes.              #
# --------------------------------------------------------------------------- #
def run_cell(w: int, label: str, args, results_dir: Path) -> dict:
    bench = args.bench.resolve()
    if not bench.is_file():
        raise SystemExit(f"w_ladder: bench_champion.py not found at {bench}")

    env = dict(os.environ)
    # Production pins each worker to one thread; without this, 10 numpy/Accelerate
    # processes would each fan out and the "W workers" axis would be meaningless.
    env.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": ""})

    cell_dir = results_dir / f"cell_W{label}"
    if cell_dir.exists():
        shutil.rmtree(cell_dir)
    cell_dir.mkdir(parents=True)

    lo_before, therm_before = loadavg(), thermal_probe()
    procs_before = top_procs()
    sampler = ThermalSampler(period=args.therm_period)
    sampler.start()

    procs: list[dict] = []
    t_cell0 = time.time()
    for i in range(w):
        out_json = cell_dir / f"worker{i:02d}.json"
        log = open(cell_dir / f"worker{i:02d}.log", "w")           # noqa: SIM115
        cmd = [sys.executable, str(bench),
               "--bundle", str(args.bundle.resolve()),
               "--budgets", args.budget,
               "--limit", str(args.limit),
               "--repeat", str(args.repeat),
               "--warmup", str(args.warmup),
               # Distinct seed per worker: same positions, different PIMC
               # determinizations — independent work, controlled position mix.
               "--seed", str(args.seed + 1000 * i),
               "--out", str(out_json),
               "--tag", f"w_ladder W={w} worker={i} {args.tag}".strip()]
        p = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, cwd=str(bench.parent))
        procs.append({"i": i, "proc": p, "log": log, "json": out_json,
                      "t_start": time.time()})

    for rec in procs:
        rec["rc"] = rec["proc"].wait()
        rec["t_end"] = time.time()
        rec["log"].close()
    t_cell1 = time.time()

    therm_samples = sampler.stop()
    lo_after, therm_after = loadavg(), thermal_probe()

    # ---------------- aggregate ---------------- #
    workers: list[dict] = []
    for rec in procs:
        w_rec = {"worker": rec["i"], "rc": rec["rc"],
                 "proc_wall_s": rec["t_end"] - rec["t_start"],
                 "t_start": rec["t_start"], "t_end": rec["t_end"]}
        try:
            doc = json.loads(rec["json"].read_text())
            b = doc["budgets"][0]
            times = [s["s"] for s in b["samples"]]
            w_rec.update({
                "n_moves": len(times),
                "mean_s_per_move": sum(times) / len(times),
                "p50_s_per_move": b["overall"]["p50_s"],
                "p90_s_per_move": b["overall"]["p90_s"],
                "search_s": sum(times),
                "exact_latches": b["exact_latches"],
                "leaf_path": doc["cython"]["leaf_path"],
                "by_phase_mean": {k: v["mean_s"] for k, v in b["by_phase"].items()},
            })
            # Everything the process spent that was NOT a timed decision: import,
            # champion construction + verify, position replay. Once per process here;
            # a real gen worker pays it once per HOURS, so it must not be folded into
            # the throughput number without saying so.
            w_rec["overhead_s"] = w_rec["proc_wall_s"] - w_rec["search_s"]
        except Exception as exc:                                   # noqa: BLE001
            w_rec["error"] = f"{type(exc).__name__}: {exc}"
        workers.append(w_rec)

    ok = [x for x in workers if "mean_s_per_move" in x]
    cell: dict = {
        "label": label, "W": w, "budget": args.budget,
        "cell_wall_s": t_cell1 - t_cell0,
        "workers_ok": len(ok), "workers_failed": w - len(ok),
        "loadavg_before": lo_before, "loadavg_after": lo_after,
        "top_procs_before": procs_before, "top_procs_after": top_procs(),
        "thermal_before": therm_before, "thermal_after": therm_after,
        "thermal_samples": therm_samples,
        "workers": workers,
    }
    if not ok:
        cell["error"] = "no worker produced a readable JSON"
        return cell

    means = sorted(x["mean_s_per_move"] for x in ok)
    total_moves = sum(x["n_moves"] for x in ok)
    # PRIMARY: steady-state search throughput = the sum of the per-worker rates.
    # Excludes per-process startup, which a long-lived gen worker amortises away.
    agg_search = sum(x["n_moves"] / x["search_s"] for x in ok)
    # LOWER BOUND: end-to-end, startup included.
    agg_wall = total_moves / (t_cell1 - t_cell0)
    # How much of the cell had ALL workers running? Below ~0.9 the per-worker means
    # are diluted by an uncontended tail and the ladder understates contention.
    overlap = min(x["t_end"] for x in ok) - max(x["t_start"] for x in ok)
    cell.update({
        "total_moves": total_moves,
        "per_worker_mean_s_per_move": sum(means) / len(means),
        "per_worker_mean_s_min": means[0],
        "per_worker_mean_s_max": means[-1],
        "per_worker_spread_ratio": means[-1] / means[0],
        "aggregate_moves_per_s": agg_search,
        "aggregate_moves_per_s_wall": agg_wall,
        "overlap_s": overlap,
        "overlap_fraction": overlap / (t_cell1 - t_cell0),
        "mean_overhead_s": sum(x["overhead_s"] for x in ok) / len(ok),
        "exact_latches_total": sum(x["exact_latches"] for x in ok),
        "leaf_paths": sorted({x["leaf_path"] for x in ok}),
    })
    return cell


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ladder", default=DEFAULT_LADDER,
                   help=f"comma-separated worker counts (default {DEFAULT_LADDER}; a "
                        f"repeated value is auto-labelled _post and is the throttle test)")
    p.add_argument("--budget", default=DEFAULT_BUDGET, help="single kNxM cell")
    p.add_argument("--bench", type=Path, default=HERE / "bench_champion.py",
                   help="the single-stream bench this driver fans out (default: next to me)")
    p.add_argument("--bundle", type=Path, default=HERE / "bundle",
                   help="standalone champion bundle (default: next to me)")
    p.add_argument("--results-dir", type=Path, default=HERE / "results")
    p.add_argument("--limit", type=int, default=24,
                   help="positions per pass (alternating tile/meeple, so keep it even)")
    p.add_argument("--repeat", type=int, default=2, help="passes over the positions")
    p.add_argument("--warmup", type=int, default=2)
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--settle", type=float, default=15.0,
                   help="idle seconds between cells")
    p.add_argument("--therm-period", type=float, default=10.0)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--tag", default="")
    a = p.parse_args(argv)

    ladder = [int(x) for x in a.ladder.split(",") if x.strip()]
    if not ladder:
        raise SystemExit("w_ladder: empty ladder")

    stamp = time.strftime("%Y%m%dT%H%M%S")
    host = platform.node().split(".")[0] or "unknown"
    results_dir = a.results_dir
    out_path = a.out or (results_dir / f"w_ladder_{host}_{stamp}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mach = machine_info()
    moves_each = a.limit * a.repeat - a.warmup
    print(f"w_ladder: {mach.get('model_name') or mach.get('hw_model') or '?'} / "
          f"{mach.get('cpu_brand') or mach['machine']}  "
          f"({mach.get('p_cores', '?')}P+{mach.get('e_cores', '?')}E, "
          f"{mach['cpu_count']} logical)")
    print(f"  ladder  : {ladder}   budget {a.budget}")
    print(f"  per wkr : {moves_each} timed moves ({a.limit} positions x {a.repeat})")
    print(f"  out     : {out_path}")

    result = {
        "schema": "carcassonne-m5-bench/w_ladder-v1",
        "kind": "aggregate_throughput_w_ladder",
        "tag": a.tag,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": mach,
        "config": {"ladder": ladder, "budget": a.budget, "limit": a.limit,
                   "repeat": a.repeat, "warmup": a.warmup, "seed": a.seed,
                   "settle_s": a.settle, "moves_per_worker": moves_each},
        "cells": [],
    }

    def _flush() -> None:
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result, indent=2, default=str))
        tmp.replace(out_path)

    _flush()
    seen: dict[int, int] = {}
    for w in ladder:
        seen[w] = seen.get(w, 0) + 1
        label = str(w) if seen[w] == 1 else f"{w}_post{seen[w] - 1}"
        print(f"\n  -> W={w} (cell {label}) ...", flush=True)
        cell = run_cell(w, label, a, results_dir)
        result["cells"].append(cell)
        if "aggregate_moves_per_s" in cell:
            print(f"     per-worker {cell['per_worker_mean_s_per_move']:.3f} s/move "
                  f"[{cell['per_worker_mean_s_min']:.3f}-"
                  f"{cell['per_worker_mean_s_max']:.3f}]   "
                  f"aggregate {cell['aggregate_moves_per_s']:.3f} moves/s   "
                  f"(wall {cell['cell_wall_s']:.0f}s, overlap "
                  f"{cell['overlap_fraction']:.2f})", flush=True)
        else:
            print(f"     FAILED: {cell.get('error')}", flush=True)
        _flush()
        if w != ladder[-1] and a.settle > 0:
            time.sleep(a.settle)

    ok_cells = [c for c in result["cells"] if "aggregate_moves_per_s" in c]
    if ok_cells:
        best = max(ok_cells, key=lambda c: c["aggregate_moves_per_s"])
        result["w_optimum"] = {"label": best["label"], "W": best["W"],
                               "aggregate_moves_per_s": best["aggregate_moves_per_s"]}
        firsts = [c for c in ok_cells if c["label"] == "1"]
        posts = [c for c in ok_cells if c["label"].startswith("1_post")]
        if firsts and posts:
            result["throttle_check"] = {
                "w1_open_s_per_move": firsts[0]["per_worker_mean_s_per_move"],
                "w1_post_s_per_move": posts[-1]["per_worker_mean_s_per_move"],
                "post_over_open": (posts[-1]["per_worker_mean_s_per_move"]
                                   / firsts[0]["per_worker_mean_s_per_move"]),
            }
    _flush()

    print(f"\nw_ladder: wrote {out_path}")
    print(f"  {'cell':>8} {'s/move':>9} {'agg mv/s':>9} {'spread':>7} {'wall s':>7}")
    for c in ok_cells:
        print(f"  {c['label']:>8} {c['per_worker_mean_s_per_move']:9.3f} "
              f"{c['aggregate_moves_per_s']:9.3f} "
              f"{c['per_worker_spread_ratio']:7.2f} {c['cell_wall_s']:7.0f}")
    if "w_optimum" in result:
        o = result["w_optimum"]
        print(f"  W optimum: {o['label']} at {o['aggregate_moves_per_s']:.3f} moves/s")
    if "throttle_check" in result:
        t = result["throttle_check"]
        print(f"  throttle : W=1 open {t['w1_open_s_per_move']:.3f} -> post "
              f"{t['w1_post_s_per_move']:.3f} s/move  "
              f"({t['post_over_open']:.3f}x)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
