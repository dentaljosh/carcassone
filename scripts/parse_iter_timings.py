#!/usr/bin/env python3
"""Extract per-iter wall-clock + gate/value signals from a Path-B driver log.

The cluster loop (`run_pathb_cluster_loop.sh`) prints dated phase markers per iter:
    ########## ITER N: self-play @ <date> ...
    ########## ITER N: train @ <date> ...
    ########## ITER N: anchor-gate ... @ <date> ...
    ########## ITER N COMPLETE @ <date> ...
plus  `ANCHOR-GATE: ...WR=0.xxxx`  and  `value↔outcome corr = +0.xx`.

This parses those into a tidy per-iter table and UPSERTs (by run+iter) into
experiments/iter_timings.csv — a PERFORMANCE record, deliberately SEPARATE from
experiments/results.csv (which is the ELO / strength source-of-truth; wall-clock
rows do not belong there).

Usage:
    python scripts/parse_iter_timings.py [LOG ...] [--run NAME]
    python scripts/parse_iter_timings.py /tmp/pathb_anchor.log --run pathb_anchor
Idempotent: rerun any time during/after a run to refresh the rows it can see.
Note the loop truncates its log on (re)start, so parse before a restart (or keep
per-run logs) if you want phases for early iters; rows already in the CSV survive.
"""
from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "experiments" / "iter_timings.csv"
FIELDS = ["run", "iter", "date", "selfplay_sec", "train_sec", "gate_sec",
          "total_sec", "total_min", "games", "sims", "gate_wr", "value_corr", "notes"]

# "Mon Jun  1 14:01:35 EDT 2026" — strip the tz abbrev (strptime %Z is unreliable
# for arbitrary zones); all markers in one run share a zone so deltas are exact.
_DATE_RE = re.compile(r"@\s+([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+[A-Z]{2,4}\s+(\d{4})")
_HDR_RE = re.compile(r"GAMES=(\d+)\s+SIMS=(\d+)")
_PHASE_RE = re.compile(r"ITER (\d+):\s+(self-play|train|anchor-gate)")
_DONE_RE = re.compile(r"ITER (\d+) COMPLETE")
_WR_RE = re.compile(r"WR=([0-9.]+)")
_CORR_RE = re.compile(r"value.outcome corr\s*=\s*([+-]?[0-9.]+)")


def _ts(line: str):
    m = _DATE_RE.search(line)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%a %b %d %H:%M:%S %Y")


def parse_log(path: Path, run: str) -> dict[int, dict]:
    iters: dict[int, dict] = {}
    games = sims = ""
    cur_corr = None  # most-recent corr line (emitted during train, before the gate)
    for line in path.read_text(errors="replace").splitlines():
        h = _HDR_RE.search(line)
        if h:
            games, sims = h.group(1), h.group(2)
        c = _CORR_RE.search(line)
        if c:
            cur_corr = c.group(1)
            if iters:  # corr is emitted during the current iter's train (after its marker)
                iters[max(iters)]["value_corr"] = cur_corr
        p = _PHASE_RE.search(line)
        if p:
            n = int(p.group(1)); d = iters.setdefault(n, {})
            key = {"self-play": "t_sp", "train": "t_tr", "anchor-gate": "t_gt"}[p.group(2)]
            d[key] = _ts(line)
            d["run"] = run; d["games"] = games; d["sims"] = sims  # set on every phase (partial iters too)
        if "ANCHOR-GATE:" in line and (w := _WR_RE.search(line)):
            # the gate tally line belongs to the iter whose gate just ran (max seen)
            if iters:
                iters[max(iters)]["gate_wr"] = w.group(1)
        dn = _DONE_RE.search(line)
        if dn:
            n = int(dn.group(1)); d = iters.setdefault(n, {})
            d["t_end"] = _ts(line); d["games"] = games; d["sims"] = sims; d["run"] = run
    return iters


def _sec(a, b):
    return int((b - a).total_seconds()) if a and b else ""


def to_rows(iters: dict[int, dict]) -> list[dict]:
    rows = []
    for n in sorted(iters):
        d = iters[n]
        sp, tr, gt, end = d.get("t_sp"), d.get("t_tr"), d.get("t_gt"), d.get("t_end")
        total = _sec(sp, end)
        rows.append({
            "run": d.get("run", ""), "iter": n,
            "date": sp.strftime("%Y-%m-%d %H:%M") if sp else "",
            "selfplay_sec": _sec(sp, tr), "train_sec": _sec(tr, gt),
            "gate_sec": _sec(gt, end), "total_sec": total,
            "total_min": round(total / 60, 1) if total != "" else "",
            "games": d.get("games", ""), "sims": d.get("sims", ""),
            "gate_wr": d.get("gate_wr", ""), "value_corr": d.get("value_corr", ""),
            "notes": "",
        })
    return rows


def upsert(rows: list[dict]) -> None:
    existing: dict[tuple, dict] = {}
    if OUT.exists():
        for r in csv.DictReader(open(OUT)):
            existing[(r["run"], r["iter"])] = r
    for r in rows:
        key = (r["run"], str(r["iter"]))
        # don't clobber a richer existing row with blanks (e.g. hand-backfilled)
        if key in existing:
            merged = dict(existing[key])
            for k, v in r.items():
                if v != "" and v is not None:
                    merged[k] = v
            existing[key] = merged
        else:
            existing[key] = {k: r.get(k, "") for k in FIELDS}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(existing.values(), key=lambda r: (r["run"], int(r["iter"])))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="*", default=["/tmp/pathb_anchor.log"])
    ap.add_argument("--run", default="pathb_anchor")
    args = ap.parse_args()
    all_rows = []
    for lg in args.logs:
        p = Path(lg)
        if not p.exists():
            print(f"skip (missing): {lg}")
            continue
        all_rows += to_rows(parse_log(p, args.run))
    if all_rows:
        upsert(all_rows)
    # echo the current table
    if OUT.exists():
        print(f"-> {OUT}")
        for r in csv.DictReader(open(OUT)):
            print(f"  {r['run']:14} iter {r['iter']:>2}  total={r['total_min'] or '?':>5}min  "
                  f"sp={r['selfplay_sec'] or '?'}s tr={r['train_sec'] or '?'}s gt={r['gate_sec'] or '?'}s  "
                  f"wr={r['gate_wr'] or '?'} corr={r['value_corr'] or '?'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
