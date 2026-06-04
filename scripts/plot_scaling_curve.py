#!/usr/bin/env python3
"""Read the scaling-curve sweep dirs and print a table + ASCII plot.

Scans  <root>/curve/s<net>_h<heur>_b<blend>/  for per-game *.json (the
eval_net_vs_heuristic GameResult format), pools each cell, and reports
wr / elo / sigma. Then draws:
  Curve A  elo vs net-sims  (heur held at 200, blend 0)  -> test-time scaling
  Curve B  elo vs heur-sims (net held at 200, blend 0)   -> reference hardness
  #1 probe value-blend at the 200/200 cell.

Usage: python scripts/plot_scaling_curve.py [--root /mnt/c/carc-shared/scaling_curve]
"""
import argparse
import json
import math
import re
from pathlib import Path

CELL_RE = re.compile(r"s(\d+)_h(\d+)_b(\d+)$")


def pool(cell_dir: Path):
    n = w = d = 0
    elapsed = 0.0
    for jf in cell_dir.glob("*.json"):
        try:
            r = json.loads(jf.read_text())
        except Exception:
            continue
        n += 1
        if r.get("drew"):
            d += 1
        elif r.get("won_by_net"):
            w += 1
        elapsed += float(r.get("elapsed_s", 0.0))
    if n == 0:
        return None
    wr = (w + 0.5 * d) / n
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        wr_sig = math.sqrt(wr * (1 - wr) / n)
        elo_sig = (400.0 / math.log(10)) * wr_sig / (wr * (1 - wr))
    else:
        elo = math.copysign(800.0, wr - 0.5)
        elo_sig = float("nan")
    return dict(n=n, w=w, d=d, wr=wr, elo=elo, elo_sig=elo_sig,
               avg_s=elapsed / n if n else 0.0)


def parse_cell(name: str):
    m = CELL_RE.search(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))  # net, heur, blend(x100-ish)


def ascii_plot(points, xlabel, title, logx=True):
    """points: list of (x, elo, sig). Simple terminal scatter."""
    if not points:
        print(f"  ({title}: no data yet)")
        return
    print(f"\n  {title}")
    elos = [p[1] for p in points]
    lo, hi = min(elos + [0]), max(elos + [0])
    span = max(hi - lo, 1.0)
    width = 48
    for x, elo, sig in sorted(points):
        col = int((elo - lo) / span * width)
        bar = " " * col + "*"
        sg = f"±{sig:.0f}" if sig == sig else "  "
        print(f"    {xlabel}={x:<5d} |{bar:<{width+1}} {elo:+6.1f} {sg}")
    print(f"    {'':<8} {lo:+.0f}{'':<{width-6}}{hi:+.0f}  (elo vs heuristic)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/mnt/c/carc-shared/scaling_curve")
    args = ap.parse_args()
    base = Path(args.root) / "curve"
    if not base.exists():
        print(f"no curve dir at {base}")
        return
    rows = []
    for cd in sorted(base.iterdir()):
        if not cd.is_dir():
            continue
        cell = parse_cell(cd.name)
        if cell is None:
            continue
        st = pool(cd)
        if st is None:
            continue
        rows.append((cell, st))

    print(f"{'net':>5} {'heur':>5} {'blend':>5} {'n':>4} {'wr':>6} {'elo':>8} {'sig':>5} {'s/game':>7}")
    for (net, heur, bl), st in sorted(rows):
        print(f"{net:>5} {heur:>5} {bl/100:>5.2f} {st['n']:>4} {st['wr']:>6.3f} "
              f"{st['elo']:>+8.1f} {st['elo_sig']:>5.0f} {st['avg_s']:>7.1f}")

    # Curve A: heur=200, blend=0, vary net
    a = [(net, st['elo'], st['elo_sig']) for (net, heur, bl), st in rows
         if heur == 200 and bl == 0]
    ascii_plot(a, "sims", "Curve A — strength vs net test-time sims (heur fixed @200)")
    # Curve B: net=200, blend=0, vary heur
    b = [(heur, st['elo'], st['elo_sig']) for (net, heur, bl), st in rows
         if net == 200 and bl == 0]
    ascii_plot(b, "heur", "Curve B — net@200 vs deeper-searching heuristic reference")
    # #1 probe: 200/200, vary blend
    pr = [(bl, st['elo'], st['elo_sig']) for (net, heur, bl), st in rows
          if net == 200 and heur == 200]
    if len(pr) > 1:
        print("\n  #1 value-at-play-time probe (net=200, heur=200):")
        for bl, elo, sig in sorted(pr):
            sg = f"±{sig:.0f}" if sig == sig else ""
            print(f"    blend={bl/100:.2f}  elo={elo:+6.1f} {sg}")


if __name__ == "__main__":
    main()
