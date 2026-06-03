#!/usr/bin/env python3
"""Deterministic process provenance — no hand-maintained table.

Joins the live `ps` snapshot with each process's `CARC_RUN` env tag read from
`/proc/<pid>/environ`. Because the environment is inherited at fork and is
immutable from outside, the tag travels with the process: mp-spawn workers and
ORPHANS (reparented to PID 1) are attributed just like their parent. The only
discipline required is that launchers export `CARC_RUN=<tag>` (and ideally
`setsid` so a run owns a process group) — the kernel propagates it; this tool
reads it back. Untagged long-running python = unknown provenance, flagged.

Usage:
  python scripts/cluster_census.py              # python procs, newest-launched first
  python scripts/cluster_census.py --all        # every process, not just python
  python scripts/cluster_census.py --tag stage_b   # only procs carrying this tag
  python scripts/cluster_census.py --kill-tag stage_b   # SIGTERM every proc with this tag (deterministic run-kill)
  python scripts/cluster_census.py --unknown    # only untagged python >10min (the stale-orphan suspects)

Run over ssh for remotes:  ssh xeon "wsl -d Ubuntu-24.04 -- python3 /home/.../cluster_census.py"
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys


def env_tag(pid: str) -> str | None:
    """CARC_RUN from /proc/<pid>/environ (NUL-separated), or None."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            for kv in f.read().split(b"\0"):
                if kv.startswith(b"CARC_RUN="):
                    return kv.split(b"=", 1)[1].decode(errors="replace")
    except Exception:
        return None
    return None


def snapshot() -> list[dict]:
    out = subprocess.run(
        ["ps", "-eo", "pid,ppid,pgid,etimes,pcpu,comm,args"],
        capture_output=True, text=True,
    ).stdout.splitlines()
    rows = []
    for line in out[1:]:
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        pid, ppid, pgid, etimes, pcpu, comm, args = parts
        rows.append({
            "pid": pid, "ppid": ppid, "pgid": pgid,
            "etimes": int(etimes) if etimes.isdigit() else 0,
            "pcpu": float(pcpu) if pcpu.replace(".", "").isdigit() else 0.0,
            "comm": comm, "args": args, "tag": env_tag(pid),
        })
    return rows


def is_ours(r: dict) -> bool:
    """A carcassonne COMPUTE proc (our venv or repo), vs system/IDE python."""
    a = r["args"]
    return ("/carcassone" in a or "carcassone/.venv" in a
            or "run_selfplay" in a or "eval_net_vs_heur" in a
            or "eval_iter_head" in a or "multiprocessing.spawn" in a
            or "run_pathb" in a or "train_iter" in a)


def fmt_etime(s: int) -> str:
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m, sec = divmod(r, 60)
    if d:
        return f"{d}d{h:02d}h"
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m{sec:02d}s"


def main() -> int:
    args = sys.argv[1:]
    show_all = "--all" in args
    only_unknown = "--unknown" in args
    tag_filter = None
    kill_tag = None
    if "--tag" in args:
        tag_filter = args[args.index("--tag") + 1]
    if "--kill-tag" in args:
        kill_tag = args[args.index("--kill-tag") + 1]

    rows = snapshot()
    host = os.uname().nodename

    if kill_tag:
        victims = [r for r in rows if r["tag"] == kill_tag and int(r["pid"]) != os.getpid()]
        if not victims:
            print(f"[{host}] no live procs with CARC_RUN={kill_tag}")
            return 0
        for r in victims:
            try:
                os.kill(int(r["pid"]), signal.SIGTERM)
                print(f"[{host}] SIGTERM {r['pid']} ({fmt_etime(r['etimes'])}) {r['args'][:70]}")
            except Exception as e:
                print(f"[{host}] failed {r['pid']}: {e}")
        return 0

    def keep(r: dict) -> bool:
        is_py = "python" in r["comm"] or "python" in r["args"]
        if tag_filter is not None:
            return r["tag"] == tag_filter
        if only_unknown:
            return is_ours(r) and r["tag"] is None and r["etimes"] > 600
        return show_all or is_py

    sel = sorted((r for r in rows if keep(r)), key=lambda r: -r["etimes"])
    print(f"=== cluster_census [{host}]  {len(sel)} procs ===")
    print(f"{'PID':>7} {'PPID':>6} {'PGID':>6} {'ETIME':>8} {'%CPU':>5}  {'CARC_RUN':<26} CMD")
    for r in sel:
        tag = r["tag"]
        flag = ""
        if tag is None and r["etimes"] > 600 and is_ours(r):
            flag = "  <-- UNTAGGED carc proc (stale orphan?)"
        print(f"{r['pid']:>7} {r['ppid']:>6} {r['pgid']:>6} {fmt_etime(r['etimes']):>8} "
              f"{r['pcpu']:>5}  {(tag or '-'):<26} {r['args'][:58]}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
