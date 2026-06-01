#!/usr/bin/env python3
"""
Pipeline bottleneck sweep — for each tuning config, measure STEADY-STATE self-play
throughput (games/min) AND a synchronized telemetry time series (GPU power/util/mem
+ whole-box CPU% + loadavg), then auto-classify the bottleneck. Run per-box
(5800x / xeon / laptop); each box appends rows to a shared CSV so the cluster
results merge into one source-of-truth table.

WHY (2026-05-31): the W=14/18/24 numbers and the fp16/shards/"marginal" findings
were measured pre- the 2026-05-29 farm/city-cache 1.48x leaf speedup, several were
single-box / single-point, and — Joshua's point — g/min alone can't explain the
bottleneck. The 47W-draw-at-90%-util case proved you must read power.draw (not
util%) to tell GPU-compute-bound from IPC-latency-bound. So every cell logs a
time series and we classify from it.

THROUGHPUT METHOD — the docs warn bench_workers.py (raw-engine random games) is the
WRONG proxy. This drives the REAL run_selfplay_iter.py as a subprocess, lets it
reach steady state (--warmup s), then counts seed_*.npz landings over --measure s:
    g/min = landed_during_window / (measure_s / 60)
canceling Pool-fork + eval-server-spawn startup. The whole process group is killed
and scratch wiped between cells. Cells are TIME-BOXED, so wall-clock per box =
cell_count x window, independent of how slow the box is (a slow box just lands
fewer games inside its window — that IS the measurement).

TELEMETRY — every --sample-every s during the window:
    GPU: power.draw(W), utilization.gpu(%), memory.used(MB), clocks.sm(MHz)
         (tries nvidia-smi, then nvidia-smi.exe for WSL; '' if unavailable)
    CPU: whole-box busy% from /proc/stat deltas
    loadavg(1m)  -> queue depth vs threads = oversubscription signal
Per cell we record idle GPU power + power-limit (one-time) so "high power" is
defined relative to the card, and dump the raw samples to samples_<box>.csv for
plotting.

BOTTLENECK CLASSIFIER (heuristic, from the cell's medians):
    cpu_high  := cpu_pct_p50 > 80                       (most of the box busy)
    gpu_high  := gpu_pw_p50  > idle + 0.4*(limit-idle)  (real GPU compute load)
        cpu_high & gpu_high  -> "balanced"
        cpu_high & !gpu_high -> "cpu_bound"     (MCTS tree / v2.7 leaf on CPU)
        !cpu_high & gpu_high -> "gpu_compute"
        !cpu_high & !gpu_high-> "ipc_latency"   (workers blocked on eval RTT;
                                                 the 47W batch-1 case)
    + loadavg_p50 >> threads flags oversubscription/thrash regardless.

LEVERS SWEPT (1-D around a per-box baseline; quality-NEUTRAL for produced data
EXCEPT mcts_batch, which changes the search and needs a SEPARATE strength check —
not done here, this is speed+telemetry only). Nothing mutates a checkpoint or
training set; the .npz are thrown away.

Usage (HELD for Joshua's go):
    nice -n 19 python -u scripts/bench_pipeline_sweep.py \
        --box 5800x --checkpoint /mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt \
        --out-csv /mnt/c/carc-shared/bench/sweep.csv \
        --scratch /mnt/c/carc-shared/bench/scratch_5800x \
        [--warmup 45 --measure 240 --sample-every 2 --only W=]
    # live view while it runs:  tail -f /mnt/c/carc-shared/bench/samples_5800x.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
ENV_EXTRA = {"CARCASSONNE_V25_DROP_THREE_OPEN": "1", "CARCASSONNE_V25_CAP": "12",
             "CARC_BENCH_TP": "1"}

# Three different GPU architectures across the cluster — relevant for fp16, whose
# autocast overhead vs Tensor-Core gain is arch-dependent: fp16 was benched SLOWER
# on Turing (Xeon Quadro RTX 4000) and Blackwell (5800x 5060Ti + cloud 5090) but
# has NEVER been tested on Ada (laptop 4070m), the one card with a real shot at it.
BOX = {
    "5800x":  {"threads": 16, "vram": 16, "arch": "Blackwell", "W": [8, 10, 12, 14, 16, 20], "Wdef": 14},
    "xeon":   {"threads": 12, "vram": 8,  "arch": "Turing",    "W": [8, 10, 12, 16, 18, 24], "Wdef": 18},
    "laptop": {"threads": 16, "vram": 8,  "arch": "Ada",       "W": [10, 14, 18, 24, 28],    "Wdef": 24},
}

_SMI = None  # resolved nvidia-smi exe (or False if none works)


def _smi_exe() -> str | bool:
    global _SMI
    if _SMI is not None:
        return _SMI
    for exe in ("nvidia-smi", "nvidia-smi.exe"):
        try:
            r = subprocess.run([exe, "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=8)
            if r.returncode == 0 and r.stdout.strip():
                _SMI = exe
                return exe
        except Exception:
            continue
    _SMI = False
    return False


def _smi_query(fields: list[str]) -> list[float | None]:
    exe = _smi_exe()
    if not exe:
        return [None] * len(fields)
    try:
        r = subprocess.run([exe, f"--query-gpu={','.join(fields)}",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=8)
        if r.returncode != 0 or not r.stdout.strip():
            return [None] * len(fields)
        parts = r.stdout.strip().splitlines()[0].split(",")
        out: list[float | None] = []
        for p in parts:
            p = p.strip()
            try:
                out.append(float(p))
            except ValueError:
                out.append(None)
        return out + [None] * (len(fields) - len(out))
    except Exception:
        return [None] * len(fields)


def gpu_static() -> dict:
    lim = _smi_query(["power.limit"])[0]
    idle = _smi_query(["power.draw"])[0]
    return {"limit": lim, "idle": idle}


def gpu_sample() -> dict:
    pw, util, mem, clk = _smi_query(
        ["power.draw", "utilization.gpu", "memory.used", "clocks.sm"])
    return {"pw": pw, "util": util, "mem": mem, "clk": clk}


class CpuReader:
    """Whole-box busy% from /proc/stat deltas between calls."""
    def __init__(self) -> None:
        self.prev = self._read()

    @staticmethod
    def _read() -> tuple[int, int]:
        with open("/proc/stat") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)  # idle + iowait
        return sum(parts), idle

    def pct(self) -> float:
        tot, idle = self._read()
        dt, di = tot - self.prev[0], idle - self.prev[1]
        self.prev = (tot, idle)
        return 100.0 * (1.0 - di / dt) if dt > 0 else 0.0


def _pctl(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def build_cmd(checkpoint: str, scratch: Path, cfg: dict) -> list[str]:
    if cfg.get("mode") == "eval":
        # PHASE-3 eval path: eval_net_vs_heuristic.py — per-worker batch-1, NO
        # orchestrator, CPU virtual_score leaf dominates (BACKLOG:23-29). Sweeps W
        # only to find the CPU-bound knee. Huge --n so it never finishes the window;
        # fresh out-root each cell (run_cell rmtree's scratch) -> no resume-cache.
        return [PY, "-u", "scripts/eval_net_vs_heuristic.py",
                "--checkpoint", checkpoint, "--n", "100000",
                "--sims", str(cfg.get("sims", 200)), "--c-puct", "3.0",
                "--workers", str(cfg["W"]),
                "--out-root", str(scratch), "--out-subdir", "benchtmp",
                "--seed-start", str(cfg.get("seed_start", 7_000_000))]
    cmd = [PY, "-u", "scripts/run_selfplay_iter.py",
           "--checkpoint", checkpoint, "--output-root", str(scratch),
           "--iter", "0", "--games", "100000",
           "--seed-start", str(cfg.get("seed_start", 7_000_000)),
           "--sims", str(cfg.get("sims", 200)),
           "--workers", str(cfg["W"]),
           "--batch-size", str(cfg.get("mcts_batch", 8)),
           # EXACT production self-play knobs (run_pathb_cluster_loop.sh:119):
           # v2.7 leaf VALUE (CPU) + score_diff target + the production
           # virtual-loss batch baseline of 8. run_selfplay_iter auto-handles the
           # 12-scalar width from the checkpoint — there is NO farm-scalar/aux/
           # temperature/dirichlet flag on this script (those live on the
           # warmstart/gen scripts; passing them = "unrecognized arguments").
           "--leaf-eval", "v2_5", "--value-target", "score_diff"]
    # NOTE: --fp16 is a top-level flag (run_selfplay_iter.py:409), wired into the
    # per-worker path. Whether it reaches the orchestrator server pool
    # (start_server_pool, ~line 710) needs confirming before trusting an
    # orchestrator-mode fp16 cell — that call passes n_shards/max_batch/
    # batch_timeout_ms but not use_fp16. So the fp16 cell is most meaningful in
    # the orch-off path until that's wired.
    if cfg.get("orch_fp16", False):
        cmd += ["--fp16"]
    if cfg.get("orchestrator", True):
        cmd += ["--orchestrator",
                "--orch-shards", str(cfg.get("orch_shards", 1)),
                "--orch-batch-timeout-ms", str(cfg.get("orch_batch_timeout_ms", 2.0)),
                "--orch-max-batch", str(cfg.get("orch_max_batch", 256))]
    return cmd


def count_npz(scratch: Path) -> int:
    return sum(1 for _ in scratch.rglob("seed_*.npz"))


def count_bench_moves(log: Path) -> int:
    """Sum over worker processes of each worker's latest cumulative move count.

    selfplay.py's _bench_tick() prints ``BENCHTP pid=<pid> t=<wall> moves=<cum>``
    roughly every 3 s per worker process (gated on CARC_BENCH_TP); <cum> is that
    worker's monotonic lifetime move count, NOT a per-interval delta. So window
    throughput is the DELTA of this sum across the measure window:
        moves_per_s = (count_bench_moves(end) - count_bench_moves(start)) / elapsed
    Parsing pid lets us track each worker independently and sum — robust to the
    pool interleaving its lines into one shared stdout.
    """
    try:
        latest = {}
        with open(log, errors="replace") as f:
            for line in f:
                if not line.startswith("BENCHTP "):
                    continue
                pid = mv = None
                for tok in line.split():
                    if tok.startswith("pid="):
                        pid = tok[4:]
                    elif tok.startswith("moves="):
                        try:
                            mv = int(tok[6:])
                        except ValueError:
                            mv = None
                if pid is not None and mv is not None:
                    latest[pid] = mv  # monotonic per pid -> last seen is the max
        return sum(latest.values())
    except FileNotFoundError:
        return 0


def classify(cpu_p50: float, gpu_pw_p50: float, stat: dict,
             load_p50: float, threads: int) -> str:
    cpu_high = cpu_p50 > 80
    lim, idle = stat.get("limit"), stat.get("idle")
    if gpu_pw_p50 != gpu_pw_p50:  # nan -> no GPU telemetry
        gpu_high = False
    elif lim and idle is not None:
        gpu_high = gpu_pw_p50 > idle + 0.4 * (lim - idle)
    else:
        gpu_high = gpu_pw_p50 > 60  # crude fallback
    base = ("balanced" if cpu_high and gpu_high else
            "cpu_bound" if cpu_high else
            "gpu_compute" if gpu_high else "ipc_latency")
    if load_p50 == load_p50 and load_p50 > threads * 1.3:
        base += "+oversub"
    return base


def run_cell(checkpoint: str, scratch: Path, cfg: dict, stat: dict,
             threads: int, warmup_s: int, measure_s: int,
             sample_every: int, samples_path: Path, axis: str) -> dict:
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    env = {**os.environ, **ENV_EXTRA}
    cmd = build_cmd(checkpoint, scratch, cfg)
    log = scratch.with_suffix(".celllog")
    with open(log, "w") as lf:
        proc = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=lf,
                                stderr=subprocess.STDOUT, start_new_session=True)

    status = "ok"
    for _ in range(warmup_s):
        time.sleep(1)
        if proc.poll() is not None:
            status = "crash_warmup"
            break

    pw, util, mem, cpu, load = [], [], [], [], []
    moves_s = 0.0
    games_landed = 0
    if status == "ok":
        cpu_rd = CpuReader()
        c0, t0 = count_bench_moves(log), time.perf_counter()
        with open(samples_path, "a", newline="") as sf:
            sw = csv.writer(sf)
            for i in range(measure_s):
                time.sleep(1)
                if proc.poll() is not None:
                    status = "crash_measure"
                    break
                if i % sample_every == 0:
                    g = gpu_sample()
                    c = cpu_rd.pct()
                    try:
                        l1 = os.getloadavg()[0]
                    except OSError:
                        l1 = float("nan")
                    if g["pw"] is not None:
                        pw.append(g["pw"])
                    if g["util"] is not None:
                        util.append(g["util"])
                    if g["mem"] is not None:
                        mem.append(g["mem"])
                    cpu.append(c)
                    load.append(l1)
                    sw.writerow([axis, i, g["pw"], g["util"], g["mem"],
                                 g["clk"], round(c, 1), round(l1, 2)])
        elapsed = time.perf_counter() - t0
        c1 = count_bench_moves(log)
        moves_s = (c1 - c0) / elapsed if elapsed > 0 else 0.0
        games_landed = count_npz(scratch)

    # teardown — kill the whole process group (workers + eval-server shards)
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=10)

    tail = ""
    if status != "ok":
        try:
            tail = log.read_text(errors="replace").strip().splitlines()[-1][:200]
        except Exception:
            tail = ""
    shutil.rmtree(scratch, ignore_errors=True)
    log.unlink(missing_ok=True)

    pw_p50 = _pctl(pw, 0.50)
    cpu_p50 = _pctl(cpu, 0.50)
    load_p50 = _pctl(load, 0.50)
    bottleneck = classify(cpu_p50, pw_p50, stat, load_p50, threads) if status == "ok" else status
    return {
        "moves_per_s": round(moves_s, 2),
        "games_landed": games_landed,
        "gpu_pw_p50": round(pw_p50, 1) if pw_p50 == pw_p50 else "",
        "gpu_pw_p95": round(_pctl(pw, 0.95), 1) if pw else "",
        "gpu_util_p50": round(_pctl(util, 0.50), 1) if util else "",
        "gpu_mem_max": round(max(mem), 0) if mem else "",
        "cpu_pct_p50": round(cpu_p50, 1) if cpu_p50 == cpu_p50 else "",
        "loadavg_p50": round(load_p50, 2) if load_p50 == load_p50 else "",
        "n_samples": len(cpu),
        "bottleneck": bottleneck,
        "status": status,
        "err_tail": tail,
    }


def matrix(box: str) -> list[tuple[str, dict]]:
    """1-D sweeps around the per-box baseline. (axis_label, override_dict)."""
    b = BOX[box]
    base = dict(orchestrator=True, orch_shards=1, mcts_batch=8,  # production baseline (run_pathb:119)
                orch_batch_timeout_ms=2.0, orch_fp16=False, W=b["Wdef"])
    cells: list[tuple[str, dict]] = []
    # Axis 1 — workers (re-confirm the flat-≥10 curve at current post-speedup code)
    for w in b["W"]:
        cells.append((f"W={w}", {**base, "W": w}))
    # Axis 2 — mcts_batch (virtual-loss). Production baseline is 8 (== the W=Wdef
    # cell); sweep around it. ** changes search — speed only here; strength is a
    # separate check before adopting any non-8 value **
    for mb in (1, 2, 4, 16):
        cells.append((f"mcts_batch={mb}", {**base, "mcts_batch": mb}))
    # Axis 3 — orchestrator OFF (per-worker local GPU loads the net into EVERY
    # worker). Only fits on the 16GB card and only to mid-W; the 8GB boxes (Xeon
    # Turing / laptop Ada) OOM above ~W=8. Few points to find the crossover, not
    # all W (keeps box cell-counts roughly even). An OOM at the 8GB low-W point
    # is itself the datum: "orchestrator is required at 8GB".
    if b["vram"] >= 16:
        off_W = [w for w in (8, 12, 16) if w in b["W"]]
    else:
        off_W = b["W"][:1]
    for w in off_W:
        cells.append((f"orch_off W={w}", {**base, "orchestrator": False, "W": w}))
    # Axis 4 — orch_shards (GIL relief): each shard owns a net copy (~2GB).
    # 4 shards ~8GB -> only on the 16GB card; 8GB boxes get the 2-shard point.
    for s in ((2, 4) if b["vram"] >= 16 else (2,)):
        cells.append((f"orch_shards={s}", {**base, "orch_shards": s}))
    # Axis 5 — coalesce linger (expected null per DECISIONS 1100)
    for t in (8.0, 16.0):
        cells.append((f"timeout_ms={t}", {**base, "orch_batch_timeout_ms": t}))
    # Axis 6 — fp16, labelled by arch; Ada (laptop) is the one untested card.
    cells.append((f"fp16[{b['arch']}]", {**base, "orch_fp16": True}))
    # DEPLOY — the STACKED per-box recommendation, measured as ONE cell. The
    # 1-D axes above confirm each lever alone; this confirms the COMBINATION we
    # ship (lever interactions are not guaranteed additive — e.g. fp16's GPU
    # win shrinks when orch-off makes the 5800x CPU-bound). Select via --only deploy.
    deploy = {
        "5800x":  {**base, "orchestrator": False, "W": 16, "orch_fp16": True},
        "xeon":   {**base, "orchestrator": True, "orch_shards": 2},
        "laptop": {**base, "orchestrator": True, "orch_shards": 2,
                   "orch_fp16": True, "mcts_batch": 16},
    }
    cells.append(("deploy", deploy[box]))
    return cells


def eval_matrix(box: str) -> list[tuple[str, dict]]:
    """PHASE-3 eval W-sweep (eval_net_vs_heuristic, no orchestrator, CPU leaf).
    Spans the CPU-bound knee incl. a bit of oversubscription past thread count."""
    b = BOX[box]
    base = dict(mode="eval", orchestrator=False, orch_shards=1, mcts_batch=8,
                orch_batch_timeout_ms=2.0, orch_fp16=False, W=b["Wdef"])
    ws = [w for w in (6, 8, 10, 12, 14, 16, 20) if w <= b["threads"] + 4]
    return [(f"eval W={w}", {**base, "W": w}) for w in ws]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", required=True, choices=list(BOX))
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--warmup", type=int, default=45)
    ap.add_argument("--measure", type=int, default=240)
    ap.add_argument("--sample-every", type=int, default=2)
    ap.add_argument("--only", default="",
                    help="comma-list of substrings; cell kept if ANY token matches its axis label")
    ap.add_argument("--repeats", type=int, default=1,
                    help="run each selected cell N times (round-robin) for a variance read")
    ap.add_argument("--mode", choices=["selfplay", "eval"], default="selfplay",
                    help="selfplay = run_selfplay_iter sweep; eval = Phase-3 eval_net_vs_heuristic W-sweep")
    args = ap.parse_args()

    stat = gpu_static()
    b = BOX[args.box]
    threads = os.cpu_count() or b["threads"]   # real count beats the hardcoded guess
    mat = eval_matrix if args.mode == "eval" else matrix
    only_toks = [t for t in args.only.split(",") if t]
    cells = [(lbl, cfg) for lbl, cfg in mat(args.box)
             if not only_toks or any(t in lbl for t in only_toks)]
    cells = cells * max(1, args.repeats)   # round-robin repeats for thermal/variance read
    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    samples_path = out.parent / f"samples_{args.box}.csv"
    if not samples_path.exists():
        with open(samples_path, "w", newline="") as sf:
            csv.writer(sf).writerow(
                ["axis", "t_rel", "gpu_pw", "gpu_util", "gpu_mem",
                 "gpu_clk", "cpu_pct", "load1"])

    fields = ["box", "axis", "W", "mcts_batch", "orchestrator", "orch_shards",
              "orch_batch_timeout_ms", "orch_fp16", "sims", "moves_per_s",
              "games_landed",
              "gpu_pw_p50", "gpu_pw_p95", "gpu_util_p50", "gpu_mem_max",
              "cpu_pct_p50", "loadavg_p50", "n_samples", "bottleneck",
              "status", "err_tail"]
    new_file = not out.exists()
    per_cell = args.warmup + args.measure + 35
    print(f"[{args.box}] gpu: limit={stat['limit']}W idle={stat['idle']}W  "
          f"arch={b['arch']} threads={threads}  smi={_smi_exe()}", flush=True)
    print(f"[{args.box}] {len(cells)} cells x ~{per_cell}s "
          f"= ~{len(cells)*per_cell//60} min -> {out}", flush=True)

    with open(out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        for i, (lbl, cfg) in enumerate(cells, 1):
            print(f"[{args.box} {i}/{len(cells)}] {lbl} ...", flush=True)
            res = run_cell(args.checkpoint, Path(args.scratch), cfg, stat,
                           threads, args.warmup, args.measure,
                           args.sample_every, samples_path, lbl)
            row = {"box": args.box, "axis": lbl, "W": cfg["W"],
                   "mcts_batch": cfg.get("mcts_batch", 1),
                   "orchestrator": cfg.get("orchestrator", True),
                   "orch_shards": cfg.get("orch_shards", 1),
                   "orch_batch_timeout_ms": cfg.get("orch_batch_timeout_ms", 2.0),
                   "orch_fp16": cfg.get("orch_fp16", False),
                   "sims": cfg.get("sims", 200), **res}
            w.writerow(row); f.flush()
            print(f"    -> {res['moves_per_s']} mv/s ({res['games_landed']}g)  gpu_pw={res['gpu_pw_p50']}W "
                  f"util={res['gpu_util_p50']}%  cpu={res['cpu_pct_p50']}%  "
                  f"load={res['loadavg_p50']}  [{res['bottleneck']}]", flush=True)
    print(f"[{args.box}] DONE -> {out}  (raw: {samples_path})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
