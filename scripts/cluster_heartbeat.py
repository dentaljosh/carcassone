#!/usr/bin/env python3
"""Per-box heartbeat writer for the cluster dashboard.

Runs on EACH box (5800x / xeon / laptop), samples CPU + GPU + running-job state
every --interval seconds, and writes it atomically to <share>/status/<host>.json.
The share is the bus: boxes never talk to each other, they just drop a file.

STDLIB ONLY — runs with any python3 (no venv/torch). Launch:
  # 5800x (local, native survives):
  nohup nice -n 19 python3 scripts/cluster_heartbeat.py --share /mnt/c/carc-shared \
      > /tmp/heartbeat.log 2>&1 & disown
  # laptop (native Linux, plain nohup survives):
  ssh laptop "nohup nice -n 19 python3 /mnt/carc-shared/code_sync/cluster_heartbeat.py \
      --share /mnt/carc-shared > /tmp/heartbeat.log 2>&1 & disown"
  # xeon (WSL2 teardown kills nohup -> held-ssh-foreground from the 5800x):
  nohup ssh -o ServerAliveInterval=60 xeon "wsl -d Ubuntu-24.04 -- \
      python3 /mnt/carc-shared/code_sync/cluster_heartbeat.py --share /mnt/carc-shared" &
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# python procs whose presence means "a real job is live"; value = friendly label
KNOWN_JOBS = {
    "eval_iter_head_to_head": "eval(iter-vs-iter)",
    "eval_net_vs_heuristic": "eval(net-vs-heuristic)",
    "run_selfplay_iter": "selfplay",
    "run_pathb_cluster_loop": "pathb-loop",
    "train_iter": "train",
    "sweep_verdict_steal": "sweep(verdict-steal)",
    "sweep_stageA": "sweep(stageA)",
}


def _cpu_pct(sample_s: float = 0.5) -> float:
    """Whole-box CPU utilisation % over a short window, from /proc/stat."""
    def read():
        with open("/proc/stat") as f:
            v = list(map(int, f.readline().split()[1:]))
        idle = v[3] + (v[4] if len(v) > 4 else 0)  # idle + iowait
        return idle, sum(v)
    try:
        i1, t1 = read(); time.sleep(sample_s); i2, t2 = read()
        dt = t2 - t1
        return round(100.0 * (1.0 - (i2 - i1) / dt), 1) if dt > 0 else 0.0
    except Exception:
        return -1.0


def _gpu() -> dict | None:
    """First GPU's name/util/power/VRAM. Tries native nvidia-smi, then the
    Windows-interop nvidia-smi.exe (xeon's WSL-native one throws NVML errors)."""
    q = ("--query-gpu=name,utilization.gpu,power.draw,power.limit,"
         "memory.used,memory.total")
    fmt = "--format=csv,noheader,nounits"
    for cmd in (["nvidia-smi", q, fmt], ["nvidia-smi.exe", q, fmt]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        except Exception:
            continue
        if out.returncode != 0 or not out.stdout.strip():
            continue
        line = out.stdout.strip().splitlines()[0].replace("\r", "")
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue

        def _f(x):  # laptop GPUs report [N/A] for power.limit etc.
            try:
                return float(x)
            except ValueError:
                return None
        if _f(parts[1]) is None:  # util must parse, else not a real GPU line
            continue
        return {
            "name": parts[0],
            "util": _f(parts[1]),
            "power": _f(parts[2]),
            "power_limit": _f(parts[3]),
            "vram_used": _f(parts[4]),
            "vram_total": _f(parts[5]),
        }
    return None


def _jobs() -> tuple[dict, int]:
    """Detect live jobs by cmdline, and count total python procs.

    Returns ({job_label: n_main_procs}, total_python_procs). The job dict counts
    procs whose cmdline names a known script (the launcher/parent); spawn-pool
    children have a generic cmdline (`multiprocessing.spawn`) so they don't match
    a script — they're captured in the total count instead. loadavg is the
    truest parallelism signal; py_procs is the honest worker tally.
    """
    found: dict[str, int] = {}
    py_total = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cl = f.read().replace(b"\0", b" ").decode(errors="replace")
        except Exception:
            continue
        if "python" not in cl:
            continue
        py_total += 1
        for key, label in KNOWN_JOBS.items():
            if key in cl:
                found[label] = found.get(label, 0) + 1
    return found, py_total


def _sample(host: str) -> dict:
    la = os.getloadavg()
    jobs, py_procs = _jobs()
    return {
        "host": host,
        "ts": time.time(),
        "ncpu": os.cpu_count() or 0,
        "loadavg": [round(x, 2) for x in la],
        "cpu_pct": _cpu_pct(),
        "gpu": _gpu(),
        "jobs": jobs,
        "py_procs": py_procs,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cluster_heartbeat")
    ap.add_argument("--share", required=True,
                    help="mounted CIFS share root (e.g. /mnt/carc-shared)")
    ap.add_argument("--interval", type=float, default=4.0)
    ap.add_argument("--host", default=socket.gethostname())
    ap.add_argument("--once", action="store_true", help="write one sample and exit")
    args = ap.parse_args(argv)

    status_dir = Path(args.share) / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    out = status_dir / f"{args.host}.json"
    tmp = status_dir / f".{args.host}.json.tmp"

    print(f"heartbeat: host={args.host} -> {out} every {args.interval}s", flush=True)
    while True:
        try:
            data = _sample(args.host)
            tmp.write_text(json.dumps(data))
            tmp.replace(out)
        except Exception as e:  # never die on a transient share/stat hiccup
            print(f"heartbeat warn: {e}", file=sys.stderr, flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
