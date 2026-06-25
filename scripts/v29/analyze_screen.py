"""Aggregate v2.9 screen result dirs into a markdown table + CSV + verdict per cell.

Reads every `v29_<cand>_vs_<base>_s<sims>/` dir under --out-root, loads the per-game
GameResult JSONs, and reports WR / Elo / avg margin / paired z / WDL + the pre-endgame
lead split (snapshot at deck<=K, a PRE-OUTCOME bucket, not the final-margin collider).
Verdict per the V29_EVAL_PLAN acceptance rules.

Usage:
  python scripts/v29/analyze_screen.py --out-root /mnt/c/carc-shared/v29_eval [--sims 200]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def _bucket(m):
    if m <= -5: return "behind"
    if m >= 20: return "blowout"
    if abs(m) <= 4: return "even"
    return "ahead"


def _load(d: Path):
    rows = []
    for p in d.glob("s*_seed*_a*.json"):
        try:
            rows.append(json.load(open(p)))
        except Exception:
            pass
    return rows


def _cell_stats(rows):
    n = len(rows)
    if n == 0:
        return None
    w = sum(1 for r in rows if r["won_by_a"])
    d = sum(1 for r in rows if r["drew"])
    losses = n - w - d
    wr = (w + 0.5 * d) / n
    avg = sum(r["diff"] for r in rows) / n
    sd = statistics.pstdev([r["diff"] for r in rows]) if n > 1 else 0.0
    z = (avg / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    bb = defaultdict(list)
    for r in rows:
        bb[_bucket(r.get("snap_margin", 0))].append(r)
    def bwr(k):
        sub = bb.get(k, [])
        if not sub:
            return None
        return ((sum(1 for r in sub if r["won_by_a"]) + 0.5 * sum(1 for r in sub if r["drew"])) / len(sub), len(sub))
    return {"n": n, "w": w, "d": d, "l": losses, "wr": wr, "avg": avg, "z": z,
            "elo": elo, "elo_sig": elo_sig,
            "even": bwr("even"), "behind": bwr("behind"), "ahead": bwr("ahead"), "blowout": bwr("blowout")}


def _verdict(s):
    """Coarse screen verdict (n~200). Promote nothing here — flag for n=400."""
    wr, n = s["wr"], s["n"]
    if n < 60:
        return "thin"
    if wr >= 0.55:
        return "STRONG-flag"
    if wr >= 0.52:
        return "flag->n400"
    if wr <= 0.48:
        return "kill"
    return "null(~0.50)"


def _fmt_bucket(b):
    return f"{b[0]:.2f}(n{b[1]})" if b else "--"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="/mnt/c/carc-shared/v29_eval")
    ap.add_argument("--sims", type=int, default=None, help="filter to one sims depth")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()
    root = Path(args.out_root)
    cells = []
    for d in sorted(root.glob("v29_*_vs_*_s*")):
        # parse: v29_<cand>_vs_<base>_s<sims>
        name = d.name[len("v29_"):]
        try:
            head, sims_s = name.rsplit("_s", 1)
            sims = int(sims_s)
            cand, base = head.rsplit("_vs_", 1)
        except ValueError:
            continue
        if args.sims and sims != args.sims:
            continue
        s = _cell_stats(_load(d))
        if s:
            cells.append((cand, base, sims, s))
    # stable order: null control first, then A*, B*, D*, E*
    def keyf(c):
        cand = c[0]
        order = {"v28": 0}.get(cand, 1)
        return (order, cand)
    cells.sort(key=keyf)

    print(f"\n{'cand':10} {'n':>4} {'wr':>6} {'elo':>7} {'±1σ':>5} {'avgΔ':>6} {'z':>6} "
          f"{'even':>11} {'behind':>11} {'ahead':>11} {'blowout':>11}  verdict")
    print("-" * 120)
    for cand, base, sims, s in cells:
        print(f"{cand:10} {s['n']:>4} {s['wr']:>6.3f} {s['elo']:>+7.0f} {s['elo_sig']:>5.0f} "
              f"{s['avg']:>+6.1f} {s['z']:>+6.2f} {_fmt_bucket(s['even']):>11} "
              f"{_fmt_bucket(s['behind']):>11} {_fmt_bucket(s['ahead']):>11} "
              f"{_fmt_bucket(s['blowout']):>11}  {_verdict(s)}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["candidate", "baseline", "sims", "n", "W", "D", "L", "wr", "elo",
                         "elo_sig", "avg_margin", "paired_z", "verdict"])
            for cand, base, sims, s in cells:
                wr.writerow([cand, base, sims, s["n"], s["w"], s["d"], s["l"],
                             f"{s['wr']:.4f}", f"{s['elo']:.1f}", f"{s['elo_sig']:.1f}",
                             f"{s['avg']:.2f}", f"{s['z']:.2f}", _verdict(s)])
        print(f"\nwrote {args.csv}")


if __name__ == "__main__":
    main()
