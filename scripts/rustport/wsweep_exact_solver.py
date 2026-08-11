#!/usr/bin/env python3
"""W-sweep driver for the Rust exact endgame solver bench.

The feasibility bench (`bench_exact_solver.py`) answers *what one solve costs*.
This driver answers the throughput question that follows it: **how many workers
should a box carry when it is labeling a batch of endgame positions?**  Each
solve is serial and RAM-hungry, so W trades DRAM headroom against wall clock and
the answer is per-box, not universal.

Protocol (the house sweep rules, encoded here so a run cannot forget them):

* **One cell per point.**  Every W point invokes the bench with exactly one
  (mode, K) cell — the default cell list is suppressed with empty-valued flags —
  so the only thing varying across points is `--workers`.
* **Points run sequentially, exclusive tenant.**  A throughput measurement
  beside another job measures the other job.  The census guard aborts rather
  than contaminate (memory: `feedback_no_agent_compute_beside_eval`).
* **RAM guard before wall clock.**  `W * rss_max_mb * 1.5 <= ram_cap_mb`, with
  `rss_max_mb` taken from the feasibility bench's measured per-solve peak; the
  1.5 is tail headroom.  A W that cannot fit is refused, not attempted.
* **Capability check on `sys.executable`.**  The stale-wheel trap (a `carc_rs`
  without `solve_endgame`) burned two launches on 2026-08-03 and shows up only
  as a jsonl full of instant `EXCEPTION` rows.  Checked up front, and any
  `EXCEPTION` row still aborts the sweep loudly.
* **Recommendation = SMALLEST W within 10% of peak throughput, never the
  argmax** (memory: `feedback_worker_count_by_bottleneck`), with an explicit
  "extend before adopting" note when the peak sits at a ladder endpoint
  (memory: `feedback_bracket_hyperparams`).

Exit codes: 2 = another tenant, 3 = RAM guard, 4 = capability check,
5 = EXCEPTION rows in a point's jsonl, 1 = a bench subprocess failed.

Usage:
  python scripts/rustport/wsweep_exact_solver.py --k 4 --mode marginalized \\
      --w-points 4 12 30 --n 20 --timeout-s 3600 \\
      --ram-cap-mb 24000 --rss-max-mb 1237 \\
      --out measurement/rust_solver_bench_20260803/wsweep_k4
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
BENCH = REPO / "scripts" / "rustport" / "bench_exact_solver.py"

#: tail headroom multiplier on the measured per-solve RSS peak
RAM_HEADROOM = 1.5
#: a W is "as good as peak" if it reaches this fraction of peak throughput
WITHIN_FRAC = 0.90

RC_TENANT = 2
RC_RAM = 3
RC_CAPABILITY = 4
RC_EXCEPTION = 5


# --------------------------------------------------------------------------
# pure functions (importable without running anything)
# --------------------------------------------------------------------------

def cell_flags(k: int, mode: str) -> list[str]:
    """Flags that make `bench_exact_solver.py` run EXACTLY ONE cell.

    Its argparse defaults are `--k-clair 4 5 6`, `--k-marg 3 4`,
    `--k-marg-probe 5`, `--python-k-clair 4` — i.e. bare defaults run seven
    cells.  Each of those options is `nargs="*"`, so passing the flag with no
    values yields an empty list and suppresses its cells (the trick the
    2026-08-03 launch used).  Every one of the four must therefore appear here,
    with values on exactly one of them.
    """
    if mode == "marginalized":
        return ["--k-clair", "--k-marg", str(k), "--k-marg-probe",
                "--python-k-clair"]
    if mode == "clairvoyant":
        return ["--k-clair", str(k), "--k-marg", "--k-marg-probe",
                "--python-k-clair"]
    raise ValueError(f"unknown mode: {mode!r}")


def point_tag(k: int, w: int) -> str:
    return f"wsweep_k{k}_w{w}"


def plan_commands(args) -> list[dict]:
    """One plan record per W point.  No side effects — safe to call in tests."""
    out_root = Path(args.out)
    plans: list[dict] = []
    for w in args.w_points:
        tag = point_tag(args.k, w)
        point_dir = out_root / f"w{w}"
        cmd = [sys.executable, "-u", str(BENCH)]
        cmd += cell_flags(args.k, args.mode)
        cmd += ["--n", str(args.n),
                "--timeout-s", str(args.timeout_s),
                "--workers", str(w),
                "--out", str(point_dir),
                "--tag", tag]
        plans.append({
            "w": w,
            "tag": tag,
            "cmd": cmd,
            "point_dir": point_dir,
            "rows_path": point_dir / f"BENCH_{tag}_rows.jsonl",
            "log_path": point_dir / "bench.log",
        })
    return plans


def check_ram(w_points, rss_max_mb: float, ram_cap_mb: int) -> list[dict]:
    """`W * rss_max * 1.5 <= cap` for every point.  Returns per-W verdicts."""
    verdicts = []
    for w in w_points:
        need = w * rss_max_mb * RAM_HEADROOM
        verdicts.append({"w": w, "need_mb": need, "cap_mb": ram_cap_mb,
                         "ok": need <= ram_cap_mb})
    return verdicts


def parse_point(rows_path, timeout_s: int) -> dict:
    """Fold one point's jsonl into counts + cost.

    An `EXCEPTION` row is never a data point — it is the stale-wheel signature —
    so it raises instead of being counted.
    """
    rows_path = Path(rows_path)
    rows: list[dict] = []
    for line in rows_path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    bad = [r for r in rows if r.get("status") == "EXCEPTION"]
    if bad:
        raise RuntimeError(
            f"{len(bad)} EXCEPTION row(s) in {rows_path}: "
            f"{bad[0].get('error', '?')} — the capability guard should have "
            f"caught this (stale carc_rs wheel?); sweep aborted")
    ok = [r for r in rows if r.get("status") == "ok"]
    n_timeout = sum(1 for r in rows if r.get("status") == "timeout")
    other = [r for r in rows
             if r.get("status") not in ("ok", "timeout", "EXCEPTION")]
    return {
        "n": len(rows),
        "n_ok": len(ok),
        "n_timeout": n_timeout,
        "n_other": len(other),
        "other_statuses": sorted({str(r.get("status")) for r in other}),
        "ok_wall_ms_sum": sum(float(r.get("wall_ms", 0.0)) for r in ok),
        "waste_worker_s": n_timeout * timeout_s,
        "rss_peak_max_mb": max((float(r.get("rss_peak_mb", 0.0)) for r in ok),
                               default=0.0),
    }


def summarize(points: list[dict]) -> dict:
    """Throughput table + the smallest-W-within-10%-of-peak recommendation.

    `points` are the merged plan/parse records: each needs `w`, `n`, `n_ok`,
    `n_timeout`, `point_wall_s`, `waste_worker_s`, `rss_peak_max_mb`.
    """
    rows = sorted(points, key=lambda p: p["w"])
    for p in rows:
        hours = p["point_wall_s"] / 3600.0
        p["solved_per_h"] = (p["n_ok"] / hours) if hours > 0 else 0.0
        p["waste_worker_h"] = p["waste_worker_s"] / 3600.0
        p["point_wall_min"] = p["point_wall_s"] / 60.0

    lines = ["| W | ok/n | timeouts | point wall min | solved/h | "
             "waste worker-h | rss_peak max MB |",
             "|---|---|---|---|---|---|---|"]
    for p in rows:
        lines.append(
            f"| {p['w']} | {p['n_ok']}/{p['n']} | {p['n_timeout']} | "
            f"{p['point_wall_min']:.1f} | {p['solved_per_h']:.2f} | "
            f"{p['waste_worker_h']:.2f} | {p['rss_peak_max_mb']:.0f} |")
    table = "\n".join(lines)

    if not rows:
        return {"rows": rows, "table": table, "recommended_w": None,
                "peak_w": None, "peak_solved_per_h": 0.0,
                "endpoint_peak": False, "recommendation": "no points measured"}

    peak = max(rows, key=lambda p: p["solved_per_h"])
    if peak["solved_per_h"] <= 0:
        return {"rows": rows, "table": table, "recommended_w": None,
                "peak_w": peak["w"], "peak_solved_per_h": 0.0,
                "endpoint_peak": False,
                "recommendation": "NO RECOMMENDATION — no point solved "
                                  "anything (every position timed out, or the "
                                  "wall clock did not advance)."}
    threshold = WITHIN_FRAC * peak["solved_per_h"]
    within = [p for p in rows if p["solved_per_h"] >= threshold]
    rec = min(within, key=lambda p: p["w"]) if within else peak
    endpoint = len(rows) > 1 and peak["w"] in (rows[0]["w"], rows[-1]["w"])

    text = (f"RECOMMEND W={rec['w']} "
            f"({rec['solved_per_h']:.2f} solved/h, "
            f"{100 * rec['solved_per_h'] / peak['solved_per_h']:.0f}% of the "
            f"W={peak['w']} peak {peak['solved_per_h']:.2f}/h) — smallest W "
            f"within {100 * (1 - WITHIN_FRAC):.0f}% of peak, per the house "
            f"sweep protocol (never the argmax).")
    if endpoint:
        text += (f" ⚠️ peak sits at W={peak['w']}, a ladder endpoint — "
                 f"extend before adopting (feedback_bracket_hyperparams).")
    return {"rows": rows, "table": table, "recommended_w": rec["w"],
            "peak_w": peak["w"], "peak_solved_per_h": peak["solved_per_h"],
            "endpoint_peak": endpoint, "recommendation": text}


def render_summary_md(args, summary: dict) -> str:
    return "\n".join([
        f"# W sweep — rust exact solver, {args.mode} K={args.k}",
        "",
        f"- generated: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        f"- host: `{os.uname().nodename}`",
        f"- n per point: {args.n} · timeout: {args.timeout_s}s · "
        f"W points: {' '.join(str(w) for w in args.w_points)}",
        f"- RAM guard: `W * {args.rss_max_mb} MB * {RAM_HEADROOM} <= "
        f"{args.ram_cap_mb} MB`",
        f"- interpreter: `{sys.executable}`",
        "",
        summary["table"],
        "",
        f"**{summary['recommendation']}**",
        "",
    ])


# --------------------------------------------------------------------------
# guards (side-effecting)
# --------------------------------------------------------------------------

def _pgrep(pattern: str) -> list[tuple[int, str]]:
    """`pgrep -af` → [(pid, cmdline)].  Empty on no match (rc=1 is normal)."""
    proc = subprocess.run(["pgrep", "-af", pattern], capture_output=True,
                          text=True)
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_s, _, cmd = line.partition(" ")
        try:
            out.append((int(pid_s), cmd))
        except ValueError:
            continue
    return out


def guard_exclusive_tenant() -> None:
    """Abort if any OTHER bench/sweep process is live.

    Self-matching is the trap: this process' own cmdline contains
    `wsweep_exact_solver.py`, and so does the shell that launched it.  Both are
    filtered by pid, and the pgrep child cannot match its own pattern because
    pgrep excludes itself.
    """
    mine = {os.getpid(), os.getppid()}
    hits: list[tuple[int, str]] = []
    for pat in (r"bench_exact_solver\.py", r"wsweep_exact_solver\.py"):
        for pid, cmd in _pgrep(pat):
            if pid in mine:
                continue
            hits.append((pid, cmd))
    if hits:
        print("[wsweep] ABORT — a throughput bench is an EXCLUSIVE tenant, "
              "and these processes are live:", file=sys.stderr)
        for pid, cmd in sorted(set(hits)):
            print(f"  {pid} {cmd}", file=sys.stderr)
        raise SystemExit(RC_TENANT)


def guard_ram(args) -> None:
    verdicts = check_ram(args.w_points, args.rss_max_mb, args.ram_cap_mb)
    for v in verdicts:
        flag = "ok" if v["ok"] else "OVER"
        print(f"[wsweep] RAM W={v['w']}: {v['need_mb']:.0f} MB needed vs "
              f"{v['cap_mb']} MB cap — {flag}", flush=True)
    bad = [v for v in verdicts if not v["ok"]]
    if bad:
        v = bad[0]
        print(f"[wsweep] ABORT — W={v['w']} needs {v['need_mb']:.0f} MB "
              f"({v['w']} × {args.rss_max_mb} MB × {RAM_HEADROOM} tail "
              f"headroom) but the cap is {v['cap_mb']} MB. Drop the W point or "
              f"raise --ram-cap-mb only if the box really has it.",
              file=sys.stderr)
        raise SystemExit(RC_RAM)


def guard_capability() -> None:
    """The stale-wheel trap: a `carc_rs` without `MirrorState.solve_endgame`."""
    probe = ("import carc_rs; "
             "assert hasattr(carc_rs.MirrorState, 'solve_endgame'), "
             "'no solve_endgame'; print(carc_rs.__version__)")
    proc = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                          text=True)
    if proc.returncode != 0:
        print(f"[wsweep] ABORT — capability check failed on {sys.executable}:",
              file=sys.stderr)
        print((proc.stderr or proc.stdout).strip(), file=sys.stderr)
        print("[wsweep] This is the stale-wheel trap (2026-08-03: two launches "
              "burned, visible only as instant EXCEPTION rows). Reinstall the "
              "extension, e.g. "
              "`maturin develop --release -m rust/carc_rs/Cargo.toml` (or "
              "`pip install -e` the crate) with THIS interpreter, then rerun.",
              file=sys.stderr)
        raise SystemExit(RC_CAPABILITY)
    print(f"[wsweep] capability ok — carc_rs {proc.stdout.strip()} on "
          f"{sys.executable}")


# --------------------------------------------------------------------------

def run_point(plan: dict) -> float:
    """Run one W point, tee-ing bench stdout to its log.  Returns wall seconds."""
    plan["point_dir"].mkdir(parents=True, exist_ok=True)
    print(f"[wsweep] W={plan['w']} -> {' '.join(plan['cmd'])}", flush=True)
    t0 = time.time()
    with plan["log_path"].open("w") as log:
        proc = subprocess.Popen(plan["cmd"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                bufsize=1, cwd=str(REPO))
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
            sys.stdout.write(f"  [w{plan['w']}] {line}")
            sys.stdout.flush()
        rc = proc.wait()
    wall = time.time() - t0
    if rc != 0:
        print(f"[wsweep] ABORT — bench exited {rc} at W={plan['w']}; see "
              f"{plan['log_path']}", file=sys.stderr)
        raise SystemExit(1)
    return wall


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--mode", choices=("marginalized", "clairvoyant"),
                    default="marginalized")
    ap.add_argument("--w-points", type=int, nargs="+", required=True,
                    help="worker counts to sweep, e.g. 4 12 22")
    ap.add_argument("--n", type=int, default=20, help="positions per point")
    ap.add_argument("--timeout-s", type=int, default=3600)
    ap.add_argument("--out", required=True, help="sweep output directory")
    ap.add_argument("--ram-cap-mb", type=int, required=True,
                    help="usable RAM on this box (WSL VM cap, not host RAM)")
    ap.add_argument("--rss-max-mb", type=float, required=True,
                    help="measured per-solve rss_peak MAX from the feasibility "
                         "bench for this (mode, K)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the planned commands (RAM guard still runs) "
                         "and exit 0")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    plans = plan_commands(args)

    if args.dry_run:
        guard_ram(args)
        print(f"[wsweep] DRY RUN — {len(plans)} point(s); census and "
              f"capability guards skipped.")
        for p in plans:
            print(f"\n# W={p['w']} -> {p['rows_path']}")
            print(" ".join(p["cmd"]))
        return 0

    guard_exclusive_tenant()
    guard_ram(args)
    guard_capability()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    points: list[dict] = []
    for plan in plans:
        wall = run_point(plan)
        try:
            parsed = parse_point(plan["rows_path"], args.timeout_s)
        except RuntimeError as exc:
            print(f"[wsweep] ABORT — {exc}", file=sys.stderr)
            raise SystemExit(RC_EXCEPTION)
        point = {"w": plan["w"], "point_wall_s": wall, **parsed}
        points.append(point)
        print(f"[wsweep] W={plan['w']} done: ok={point['n_ok']}/{point['n']} "
              f"timeouts={point['n_timeout']} wall={wall / 60:.1f} min "
              f"rss_max={point['rss_peak_max_mb']:.0f} MB", flush=True)
        (out_root / "WSWEEP_POINTS.json").write_text(
            json.dumps(points, indent=2, sort_keys=True))

    summary = summarize(points)
    md = render_summary_md(args, summary)
    (out_root / "WSWEEP_SUMMARY.md").write_text(md)
    print("\n" + md)
    print(f"-> {out_root / 'WSWEEP_SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
