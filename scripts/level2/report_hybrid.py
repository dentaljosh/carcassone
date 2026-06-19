"""Aggregate + report the L2 hybrid-handoff bands.

Scans every band dir under --root (a dir holding seed*_a*.json per-game results),
recomputes the canonical paired stats (= ladder_rung_eval / eval_hybrid_handoff),
and prints one row per band: W/D/L, raw winrate (+z vs 0.5), Elo (+1sigma), paired
seat-balanced margin + z, n_paired, distinct deck hashes, and the handoff
instrumentation (mean heur/neural decisions per game, games latched). All from
A's perspective (A = agent_a, the hybrid in the vs-iter8 / vs-heur bands).

Usage:
  python scripts/level2/report_hybrid.py --root /mnt/c/carc-shared/level2_hybrid
  python scripts/level2/report_hybrid.py --root /mnt/c/carc-shared/level2_hybrid --md verdict.md
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
from pathlib import Path


def _paired_z(games):
    by_seed = {}
    for g in games:
        by_seed.setdefault(g["seed"], {})[g["a_seat"]] = g["diff"]
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, 0
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    return mean, (mean / se if se > 0 else float("nan")), len(ds)


def _band_stats(d: Path):
    files = [f for f in glob.glob(str(d / "seed*_a*.json"))]
    games = []
    for f in files:
        try:
            games.append(json.load(open(f)))
        except Exception:
            pass
    if not games:
        return None
    n = len(games)
    w = sum(1 for g in games if g["won_by_a"])
    drew = sum(1 for g in games if g["drew"])
    losses = n - w - drew
    wr = (w + 0.5 * drew) / n
    wr_z = (wr - 0.5) / math.sqrt(0.25 / n)
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    mean_d, pz, npair = _paired_z(games)
    a_heur = [g.get("a_heur_moves", 0) for g in games]
    a_neu = [g.get("a_neural_moves", 0) for g in games]
    latched = sum(1 for g in games if g.get("a_latch_k") is not None)
    return {
        "band": d.name, "agent_a": games[0]["agent_a"], "agent_b": games[0]["agent_b"],
        "n": n, "W": w, "D": drew, "L": losses, "wr": wr, "wr_z": wr_z,
        "elo": elo, "elo_sig": elo_sig, "paired_margin": mean_d, "paired_z": pz,
        "n_paired": npair, "deck_hashes": len({g.get("deck_hash", "") for g in games}),
        "a_heur_mean": sum(a_heur) / n, "a_neural_mean": sum(a_neu) / n, "latched": latched,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--md", default=None, help="also write a markdown table here")
    args = ap.parse_args(argv)
    root = Path(args.root)
    rows = []
    for d in sorted(root.iterdir()):
        if d.is_dir():
            s = _band_stats(d)
            if s:
                rows.append(s)
    if not rows:
        print("no band data yet under", root)
        return 0

    hdr = (f"{'band':<42} {'n':>4} {'W/D/L':>11} {'wr':>6} {'wrz':>6} "
           f"{'elo':>8} {'±1σ':>6} {'pmargin':>8} {'pz':>6} {'npair':>6} "
           f"{'decks':>6} {'heur/g':>7} {'neu/g':>7} {'latch':>6}")
    lines = [hdr, "-" * len(hdr)]
    for r in rows:
        lines.append(
            f"{r['band']:<42} {r['n']:>4} {r['W']:>3}/{r['D']:>2}/{r['L']:>3} "
            f"{r['wr']:>6.3f} {r['wr_z']:>+6.2f} {r['elo']:>+8.1f} {r['elo_sig']:>6.1f} "
            f"{(r['paired_margin'] if r['paired_margin'] is not None else float('nan')):>+8.2f} "
            f"{(r['paired_z'] if r['paired_z'] is not None else float('nan')):>+6.2f} "
            f"{r['n_paired']:>6} {r['deck_hashes']:>6} {r['a_heur_mean']:>7.1f} "
            f"{r['a_neural_mean']:>7.1f} {r['latched']:>4}/{r['n']:<1}")
    out = "\n".join(lines)
    print(out)
    if args.md:
        Path(args.md).write_text(out + "\n")
        print("\nwrote", args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
