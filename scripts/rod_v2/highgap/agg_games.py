#!/usr/bin/env python3
"""Aggregate eval_net_vs_heuristic result jsons: net WR / W-L-D / mean margin / elo /
paired-z. Schema: won_by_net, net_player, score_p0, score_p1, diff, drew. Paired games
pair by seed (same deck, net plays both seats) → deck-luck cancels."""
import sys, json, glob, math
from pathlib import Path
import numpy as np

out = sys.argv[1]
fs = glob.glob(str(Path(out) / "**" / "*seed*.json"), recursive=True)
games = [json.load(open(f)) for f in fs if "won_by_net" in json.load(open(f))]
n = len(games)
if n == 0:
    print("no games"); sys.exit(0)
w = sum(1 for g in games if g["won_by_net"] and not g.get("drew"))
dr = sum(1 for g in games if g.get("drew"))
l = n - w - dr
wr = (w + 0.5 * dr) / n
elo = -400 * math.log10(1 / max(wr, 1e-9) - 1) if 0 < wr < 1 else float("nan")

def net_margin(g):
    diff = g["score_p0"] - g["score_p1"]            # p0 - p1
    return diff if g.get("net_player", 0) == 0 else -diff

# paired by seed (deck): net plays both seats of the same deck
byseed = {}
for g in games:
    byseed.setdefault(g["seed"], []).append(net_margin(g))
paired = np.array([np.mean(v) for v in byseed.values()], float)
pz = (paired.mean() / (paired.std(ddof=1) / math.sqrt(len(paired)))) if len(paired) > 1 and paired.std() > 0 else float("nan")
se_wr = math.sqrt(wr * (1 - wr) / n)
z_wr = (wr - 0.5) / se_wr if se_wr > 0 else float("nan")

print(f"n={n}  W/L/D={w}/{l}/{dr}  WR={wr:.3f}  elo={elo:+.1f}")
print(f"mean net margin={paired.mean()*0+np.mean([net_margin(g) for g in games]):+.2f}  "
      f"paired decks={len(byseed)}  paired_z(margin>0)={pz:+.2f}  WR_z={z_wr:+.2f}")
print(f"COMPARE iter04 vs h6400_v2.9 (n=400): WR 0.463  elo -26.1  paired z -4.67")
