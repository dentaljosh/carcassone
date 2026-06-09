#!/usr/bin/env python3
"""Analyze the W/thermal sweep (scripts/sweep_w_thermal.sh).

Separates two reasons a higher worker count can fail to pay off:
  (1) diminishing parallel returns  -> pos/s-per-worker falls but clock holds
  (2) VRM thermal throttling        -> effective clock decays warmup->steady

Reads summary.csv + freq_w<W>.csv from the sweep dir, prints a throttle-aware
table + verdict, and (if matplotlib is present) renders a 2-panel PNG:
  top : games/min vs W (the production metric)
  bot : effective clock % over time per W (the throttle trace)

Usage: python scripts/analyze_w_thermal.py [--dir DIR] [--png PATH]
"""
import argparse
import csv
import os
import sys

NOMINAL_GHZ = 3.3  # 5900XT base; '% Processor Performance' is relative to this


def read_summary(d):
    rows = []
    p = os.path.join(d, "summary.csv")
    with open(p) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def read_freq(d, w):
    """Return list of (perf_pct, load_pct) samples for worker count w."""
    p = os.path.join(d, f"freq_w{w}.csv")
    out = []
    if not os.path.exists(p):
        return out
    with open(p) as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            try:
                perf = float(parts[1])
            except ValueError:
                continue
            if perf <= 0:
                continue
            load = None
            if len(parts) >= 3:
                try:
                    load = float(parts[2])
                except ValueError:
                    load = None
            out.append((perf, load))
    return out


def f(x, nd=2):
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "NA"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/mnt/c/carc-shared/wsweep_thermal")
    ap.add_argument("--png", default="/mnt/c/carc-shared/wsweep_thermal/wsweep_thermal.png")
    args = ap.parse_args()

    rows = read_summary(args.dir)
    if not rows:
        print("no summary rows found in", args.dir)
        return 1

    # baseline pos/s-per-worker = the lowest-W row (least likely to be throttled)
    valid = [r for r in rows if r.get("pos_per_s") not in (None, "", "NA")]
    base_eff = None
    if valid:
        b = min(valid, key=lambda r: int(r["w"]))
        base_eff = float(b["pos_per_s"]) / int(b["w"])

    print(f"\n{'W':>3} {'games/min':>10} {'pos/s':>8} {'pos/s/wkr':>10} {'par-eff':>8} "
          f"{'clk_warm%':>10} {'clk_steady%':>12} {'throttleΔ':>10} {'GHz_steady':>10}")
    print("-" * 96)
    analyzed = []
    for r in rows:
        w = int(r["w"])
        gpm = r.get("games_per_min", "NA")
        pps = r.get("pos_per_s", "NA")
        per_w = eff = "NA"
        if pps not in ("NA", "", None):
            per_w = float(pps) / w
            eff = (per_w / base_eff) if base_eff else None
        warm = r.get("freq_warm", "NA")
        steady = r.get("freq_steady", "NA")
        thr = "NA"
        ghz = "NA"
        if warm not in ("NA", "") and steady not in ("NA", ""):
            thr = float(steady) - float(warm)        # negative => clock fell under heat
            ghz = float(steady) / 100.0 * NOMINAL_GHZ
        print(f"{w:>3} {f(gpm):>10} {f(pps):>8} {f(per_w):>10} "
              f"{(f(eff*100,0)+'%' if isinstance(eff,float) else 'NA'):>8} "
              f"{f(warm,1):>10} {f(steady,1):>12} {f(thr,1):>10} {f(ghz,2):>10}")
        analyzed.append(dict(w=w, gpm=gpm, pps=pps, per_w=per_w, eff=eff,
                             warm=warm, steady=steady, thr=thr, ghz=ghz))

    # verdict
    print("\n--- VERDICT ---")
    best = max((a for a in analyzed if a["gpm"] not in ("NA", "", None)),
               key=lambda a: float(a["gpm"]), default=None)
    if best:
        print(f"Peak throughput: W={best['w']} at {f(best['gpm'])} games/min "
              f"({f(best['pps'])} pos/s).")
    # throttle flags
    for a in analyzed:
        if isinstance(a["thr"], float):
            if a["thr"] <= -8:
                print(f"  ⚠ W={a['w']}: clock fell {f(a['thr'],1)}pts warmup→steady "
                      f"(→{f(a['ghz'],2)}GHz) = VRM throttling under sustained load.")
            if isinstance(a["steady"], str) and a["steady"] not in ("NA", "") and float(a["steady"]) < 100:
                print(f"  ⛔ W={a['w']}: steady clock {f(a['steady'],1)}% < 100% "
                      f"= throttled BELOW base clock.")
    # diminishing-returns note
    for a in analyzed:
        if isinstance(a["eff"], float) and a["eff"] < 0.85 and isinstance(a["thr"], float) and a["thr"] > -8:
            print(f"  • W={a['w']}: par-eff {f(a['eff']*100,0)}% but clock held "
                  f"→ diminishing SMT returns, not throttle.")

    # optional chart
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ws = [a["w"] for a in analyzed if a["gpm"] not in ("NA", "", None)]
        gpms = [float(a["gpm"]) for a in analyzed if a["gpm"] not in ("NA", "", None)]
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 9))
        ax1.bar([str(w) for w in ws], gpms, color="#4477aa")
        ax1.set_title("Self-play throughput vs worker count (5900XT)")
        ax1.set_xlabel("workers"); ax1.set_ylabel("games/min")
        for x, y in zip([str(w) for w in ws], gpms):
            ax1.text(x, y, f"{y:.1f}", ha="center", va="bottom")
        for a in analyzed:
            samples = read_freq(args.dir, a["w"])
            if samples:
                ax2.plot(range(len(samples)), [s[0] for s in samples],
                         marker=".", label=f"W={a['w']}")
        ax2.axhline(100, color="red", ls="--", lw=0.8, label="base clock (100%)")
        ax2.set_title("Effective clock over time (throttle trace)")
        ax2.set_xlabel("sample (~6s each)"); ax2.set_ylabel("% of 3.3GHz nominal")
        ax2.legend()
        fig.tight_layout()
        fig.savefig(args.png, dpi=110)
        print(f"\nchart -> {args.png}")
    except Exception as e:
        print(f"\n(no chart: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
