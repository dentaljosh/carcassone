#!/usr/bin/env python3
"""Parse step2-flywheel per-stage timings from a run log → table + median + ETA,
and APPEND completed-iter rows to a persistent CSV so ETAs accumulate across runs.

The launcher (run_step2_flywheel.sh) already logs, per iter:
    ########## STEP-2 ITER <n> (arm <A>) @ <date> — blend=<b> dropout=<d> ...
    [it<n>] ✅ iter complete @ <date> — gen <G>s / pol <P>s / val <V>s / eval <E>s
This is read-only: it never touches the running launcher (editing a script bash
is mid-loop on can corrupt it). Run it anytime for a live ETA.

Usage:
    parse_timings.py [LOG ...]              # default: the arm B' log
    parse_timings.py --no-append            # don't write the persistent CSV
The persistent CSV (measurement/step2_pens/iter_timings.csv) is deduped by
(tag, iter) so re-running is idempotent; rows from every run/tag accumulate.
"""
from __future__ import annotations
import argparse
import csv
import re
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOG = Path("/home/doctor/step2_flywheel_Bprime.log")
CSV_PATH = REPO / "measurement" / "step2_pens" / "iter_timings.csv"
CSV_COLS = ["tag", "arm", "iter", "blend", "gen_s", "pol_s", "val_s", "eval_s", "total_s", "completed_at"]

RE_HEADER = re.compile(r"TAG=(\S+).*iters 1\.\.(\d+)")
RE_ITER = re.compile(r"STEP-2 ITER (\d+) \(arm (\w+)\) @ (.+?) — blend=([\d.]+)")
RE_DONE = re.compile(
    r"\[it(\d+)\] .*iter complete @ (.+?) — gen (\d+)s / pol (\d+)s / val (\d+)s / eval (\d+)s")


def parse_log(path: Path) -> dict:
    txt = path.read_text(errors="replace") if path.exists() else ""
    tag, n_iters = "?", None
    m = RE_HEADER.search(txt)
    if m:
        tag, n_iters = m.group(1), int(m.group(2))
    blends, arms = {}, {}
    for m in RE_ITER.finditer(txt):
        it = int(m.group(1)); arms[it] = m.group(2); blends[it] = float(m.group(4))
    rows = []
    for m in RE_DONE.finditer(txt):
        it = int(m.group(1))
        g, p, v, e = (int(m.group(i)) for i in (3, 4, 5, 6))
        rows.append({"tag": tag, "arm": arms.get(it, "?"), "iter": it,
                     "blend": blends.get(it, ""), "gen_s": g, "pol_s": p,
                     "val_s": v, "eval_s": e, "total_s": g + p + v + e,
                     "completed_at": m.group(2).strip()})
    started = sorted(blends)  # iters that started (header seen)
    done = {r["iter"] for r in rows}
    in_progress = [i for i in started if i not in done]
    return {"tag": tag, "n_iters": n_iters, "rows": rows,
            "in_progress": in_progress, "blends": blends}


def append_csv(rows: list[dict]) -> int:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CSV_PATH.exists():
        with CSV_PATH.open() as f:
            for r in csv.DictReader(f):
                existing[(r["tag"], r["iter"])] = r
    n_new = 0
    for r in rows:
        key = (r["tag"], str(r["iter"]))
        if key not in existing:
            existing[key] = {k: r.get(k, "") for k in CSV_COLS}
            n_new += 1
    with CSV_PATH.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS); w.writeheader()
        for key in sorted(existing, key=lambda k: (k[0], int(k[1]))):
            w.writerow(existing[key])
    return n_new


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="*", type=Path, default=[DEFAULT_LOG])
    ap.add_argument("--no-append", action="store_true")
    args = ap.parse_args(argv)

    all_rows = []
    for log in args.logs:
        d = parse_log(log)
        all_rows += d["rows"]
        print(f"\n=== {d['tag']}  ({log})  iters 1..{d['n_iters']} ===")
        if not d["rows"]:
            print("  (no completed iters yet)")
        else:
            print(f"  {'it':>3} {'blend':>5} {'gen':>6} {'pol':>5} {'val':>5} {'eval':>6} {'total':>6}")
            for r in sorted(d["rows"], key=lambda r: r["iter"]):
                print(f"  {r['iter']:>3} {r['blend']:>5} {r['gen_s']:>5}s {r['pol_s']:>4}s "
                      f"{r['val_s']:>4}s {r['eval_s']:>5}s {r['total_s']:>5}s "
                      f"({r['total_s']/60:.1f}m)")
            tot = [r["total_s"] for r in d["rows"]]
            med = st.median(tot)
            for st_name in ("gen_s", "pol_s", "val_s", "eval_s"):
                vals = [r[st_name] for r in d["rows"]]
                print(f"  median {st_name[:-2]:>4}: {st.median(vals):.0f}s", end="")
            print(f"  | median total: {med:.0f}s ({med/60:.1f}m)")
            if d["n_iters"]:
                remaining = d["n_iters"] - max(r["iter"] for r in d["rows"])
                if remaining > 0:
                    print(f"  ETA remaining ({remaining} iters @ median): "
                          f"{remaining*med/60:.0f}m ({remaining*med/3600:.1f}h)")
        if d["in_progress"]:
            print(f"  in progress: iter {d['in_progress']} (blend "
                  f"{[d['blends'].get(i) for i in d['in_progress']]})")

    if all_rows and not args.no_append:
        n = append_csv(all_rows)
        print(f"\n[csv] {CSV_PATH.relative_to(REPO)}: +{n} new iter rows "
              f"({len(all_rows)} parsed; deduped by tag,iter)")


if __name__ == "__main__":
    main()
