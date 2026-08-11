"""Union tally for a ladder run (net vs HeuristicMCTS), across boxes.

The 3-box fan-out writes disjoint seed ranges into ONE shared folder, so the
authoritative result is just: glob ALL result JSONs in the dir and tally. (The
eval script's own --summary-only reconstructs only one box's --n/--seed-start
range, so it under-counts a fanned-out run — use THIS instead.)

Usage:
  python scripts/tally_ladder.py <dir>
  e.g. python scripts/tally_ladder.py /mnt/c/carc-shared/ladder_n400/iter_11_s200_h200_c30
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: tally_ladder.py <eval_dir>")
        return 2
    d = argv[1]
    files = [f for f in glob.glob(os.path.join(d, "*.json"))
             if not f.endswith("partial.json")]
    if not files:
        print(f"no result files in {d}")
        return 1
    w = dd = lo = bad = 0
    margin = 0.0
    p0 = p1 = 0
    for f in files:
        try:
            r = json.load(open(f))
        except Exception:
            bad += 1
            continue
        if r.get("drew"):
            dd += 1
        elif r.get("won_by_net"):
            w += 1
        else:
            lo += 1
        margin += r.get("diff", 0)
        if r.get("net_player") == 0:
            p0 += 1
        else:
            p1 += 1
    n = w + dd + lo
    wr = (w + 0.5 * dd) / n if n else 0.0
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        wr_sig = math.sqrt(wr * (1 - wr) / n)
        elo_sig = (400.0 / math.log(10)) * wr_sig / (wr * (1 - wr))
    else:
        elo = math.copysign(800.0, wr - 0.5)
        elo_sig = float("nan")
    print(f"=== LADDER UNION TALLY ({d}) ===")
    print(f"games:        {n}   (corrupt/skipped: {bad})")
    print(f"net-player slot balance: p0={p0} p1={p1}  (want ~50/50)")
    print(f"net record:   {w}W / {dd}D / {lo}L   winrate {wr:.3f}")
    print(f"avg score margin (net - heuristic): {margin/n:+.2f}")
    print(f"ELO (net vs heuristic): {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma, {elo/elo_sig:.1f}sigma)"
          if elo_sig == elo_sig and elo_sig > 0 else f"ELO: {elo:+.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
