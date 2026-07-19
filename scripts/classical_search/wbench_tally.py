#!/usr/bin/env python3
"""Tally the eval-W micro-sweep: games/min per point from json mtimes.
Drop the first WARM jsons (pipeline fill); throughput = remaining/(t_last-t_warm).
All points play the SAME 48 games (band 90e9) -> deck-paired comparison."""
import glob, json, os, sys

WARM = 8
base = '/mnt/c/carc-shared/distill_flywheel_sighted_20260716/'
rows = []
for d in sorted(glob.glob(base + 'wbench_*_w*')):
    fs = glob.glob(d + '/seed*_a*.json')
    if len(fs) < WARM + 4:
        rows.append((os.path.basename(d), len(fs), None, None))
        continue
    ts = sorted(os.path.getmtime(f) for f in fs)
    gpm = (len(ts) - 1 - WARM) / (ts[-1] - ts[WARM]) * 60
    el = [json.load(open(f)).get('elapsed_s') for f in fs]
    el = [e for e in el if e]
    rows.append((os.path.basename(d), len(fs), gpm, sum(el) / len(el)))
print(f"{'point':24s} {'jsons':>5s} {'games/min':>9s} {'s/game(1game)':>13s}")
for name, n, gpm, avg in rows:
    print(f"{name:24s} {n:5d} {gpm if gpm else 0:9.2f} {avg if avg else 0:13.1f}")
