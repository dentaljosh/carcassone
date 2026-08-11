#!/usr/bin/env python3
"""Post-process calibration_surface.csv into the intuitive stage-contrast view:
for each margin bucket, empirical p_win across tiles-remaining bands (pivot),
alongside the single tanh(m/15) prediction (stage-invariant by construction).

The review's mechanism ("+10 at 60 tiles left != +10 at 2 tiles left") shows up
here as a horizontal spread in p_win across stage columns at a fixed margin row,
versus the single tanh15 value that ignores stage.
"""
import csv, sys, os

CSV = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/doctor/projects/carcassone/measurement/utility_calibration_20260719/calibration_surface.csv"
BANDS = ["60-72", "45-59", "30-44", "15-29", "6-14", "1-5"]

rows = list(csv.DictReader(open(CSV)))
buckets = []
seen = set()
for r in rows:
    b = r["margin_bucket"]
    if b not in seen:
        seen.add(b); buckets.append((float(r["margin_center"]), b))
buckets.sort()

# pivot: bucket -> band -> (p_win, n_games)
piv = {}
tanh15 = {}
for r in rows:
    piv.setdefault(r["margin_bucket"], {})[r["tiles_band"]] = (
        float(r["p_win"]), int(r["n_games"]))
    tanh15[r["margin_bucket"]] = float(r["tanh15_pwin"])

hdr = f"{'margin':>10} {'tanh/15':>8} | " + " ".join(f"{b:>9}" for b in BANDS) + \
      "  | spread"
print(hdr)
print("-" * len(hdr))
for _, b in buckets:
    cells = []
    vals = []
    for band in BANDS:
        if band in piv.get(b, {}):
            p, n = piv[b][band]
            vals.append(p)
            cells.append(f"{p:.2f}({n:>4})"[:9].rjust(9))
        else:
            cells.append(f"{'-':>9}")
    spread = (max(vals) - min(vals)) if len(vals) >= 2 else float("nan")
    # use tanh15 at the representative margin (recompute from center for display)
    t15 = tanh15.get(b, float("nan"))
    print(f"{b:>10} {0.5*(1+__import__('math').tanh(_/15)):>8.2f} | "
          + " ".join(cells) + f"  | {spread:.2f}")
