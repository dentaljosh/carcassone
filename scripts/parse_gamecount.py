#!/usr/bin/env python3
"""Parse laptop_orch_ab game-count logs -> verdict table with Poisson stats.

Usage: parse_gamecount.py <box-label> <gc.log> [<gc.log> ...]
Reads:
  === laptop orch vs orch-off A/B (sims=200, 300s, ...) ===
  ORCH    W=16  games=32  peak_mem=...  fwd_busy=...
  OFF     W=10  games=36  ...
Games is ground truth. Verdict by Poisson z = (Go-Gf)/sqrt(Go+Gf); |z|<2 = tie.
"""
import math
import re
import sys

HEADER = re.compile(r"A/B\s*\(sims=(\d+)")
ROW = re.compile(r"^(ORCH|OFF)\s+W=(\d+)\s+games=(\d+)")


def parse(paths):
    cur_sims = None
    data = {}  # (sims, mode) -> [(W, games)]
    for p in paths:
        try:
            lines = open(p).read().splitlines()
        except OSError:
            continue
        for ln in lines:
            h = HEADER.search(ln)
            if h:
                cur_sims = int(h.group(1))
                continue
            m = ROW.match(ln.strip())
            if m and cur_sims is not None:
                mode = "orch" if m.group(1) == "ORCH" else "off"
                data.setdefault((cur_sims, mode), []).append((int(m.group(2)), int(m.group(3))))
    return data


def main():
    box = sys.argv[1]
    data = parse(sys.argv[2:])
    print(f"\n===== {box} =====")
    for sims in (200, 800):
        peaks = {}
        for mode in ("orch", "off"):
            rows = data.get((sims, mode), [])
            if not rows:
                peaks[mode] = None
                continue
            W, g = max(rows, key=lambda r: r[1])
            peaks[mode] = (W, g)
            allW = " ".join(f"W{w}={gg}" for w, gg in sorted(rows))
            print(f"  sims={sims} {mode:4s} peak: W={W} games={g} (±{math.sqrt(g):.0f})   [{allW}]")
        o, f = peaks.get("orch"), peaks.get("off")
        if o and f:
            go, gf = o[1], f[1]
            z = (go - gf) / math.sqrt(go + gf) if (go + gf) else 0
            ratio = go / gf if gf else 0
            if abs(z) < 2:
                v = f"~TIE (z={z:+.1f}, {ratio:.2f}x) -> orch-off W={f[0]} (lower-W/simpler tie-break)"
            elif go > gf:
                v = f"ORCH wins {ratio:.2f}x (z={z:+.1f}) -> orch W={o[0]}"
            else:
                v = f"ORCH-OFF wins {gf/go:.2f}x (z={z:+.1f}) -> off W={f[0]}"
            print(f"  sims={sims} VERDICT: {v}\n")


if __name__ == "__main__":
    main()
