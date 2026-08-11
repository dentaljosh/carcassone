#!/usr/bin/env python3
"""Aggregate deeper-search ruler matchup dirs into one headline table + runtime profile.

Each matchup dir holds seed*_a*.json GameResults (from eval_hybrid_handoff.py). We recompute
the canonical stats so the report cites ONE source: WDL, winrate, winrate-Elo +/-1sigma,
winrate-z, deck-PAIRED seat-balanced score margin + paired_z (distinct from winrate Elo),
n paired decks, n deck-hashes, and the runtime profile (mean/median/p95 sec/game, moves/game).

  python scripts/deeper_search/analyze_ladder.py DIR1 DIR2 ... [--out measurement/deeper_search_ruler/ladder]
"""
from __future__ import annotations
import argparse, json, glob, math, statistics as st
from pathlib import Path


def _paired(results):
    by_seed = {}
    for r in results:
        by_seed.setdefault(r["seed"], {})[r["a_seat"]] = r["diff"]
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, 0
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    return mean, (mean / se if se > 0 else float("nan")), len(ds)


def summarize(d: Path):
    rs = [json.load(open(p)) for p in glob.glob(str(d / "seed*_a*.json"))]
    if not rs:
        return None
    n = len(rs)
    w = sum(1 for r in rs if r["won_by_a"]); dr = sum(1 for r in rs if r["drew"]); l = n - w - dr
    wr = (w + 0.5 * dr) / n
    wr_z = (wr - 0.5) / math.sqrt(0.25 / n)
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    mean_d, pz, npair = _paired(rs)
    es = sorted(r["elapsed_s"] for r in rs)
    mv = [r["moves"] for r in rs]
    a = rs[0]["agent_a"]; b = rs[0]["agent_b"]
    return dict(
        matchup=f"{a} vs {b}", a=a, b=b, n=n, W=w, D=dr, L=l,
        winrate=round(wr, 4), winrate_z=round(wr_z, 2),
        elo=round(elo, 1), elo_sig=round(elo_sig, 1),
        avg_diff=round(sum(r["diff"] for r in rs) / n, 3),
        paired_margin=round(mean_d, 3) if mean_d is not None else None,
        paired_z=round(pz, 2) if pz is not None else None,
        n_paired=npair, n_deckhash=len({r["deck_hash"] for r in rs}),
        sec_mean=round(st.mean(es), 1), sec_median=round(st.median(es), 1),
        sec_p95=round(es[min(int(0.95 * len(es)), len(es) - 1)], 1),
        sec_max=round(max(es), 1), moves_mean=round(st.mean(mv), 0),
        timeouts=sum(r.get("a_timeouts", 0) + r.get("b_timeouts", 0) for r in rs),
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="measurement/deeper_search_ruler/ladder")
    args = ap.parse_args(argv)
    rows = [s for d in args.dirs if (s := summarize(Path(d)))]
    rows.sort(key=lambda r: r["matchup"])
    cols = ["matchup", "n", "W", "D", "L", "winrate", "winrate_z", "elo", "elo_sig",
            "avg_diff", "paired_margin", "paired_z", "n_paired", "n_deckhash",
            "sec_mean", "sec_median", "sec_p95", "sec_max", "moves_mean", "timeouts"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(str(out) + ".csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader()
        for r in rows:
            wr.writerow({k: r.get(k) for k in cols})
    # console table
    print(f"{'matchup':<34} {'n':>4} {'WDL':>11} {'wr':>6} {'wr_z':>5} {'elo':>7} "
          f"{'pmargin':>8} {'p_z':>6} {'npair':>5} {'s/game':>7} {'p95':>6}")
    for r in rows:
        print(f"{r['matchup']:<34} {r['n']:>4} {r['W']:>3}/{r['D']}/{r['L']:<3} "
              f"{r['winrate']:>6.3f} {r['winrate_z']:>+5.1f} {r['elo']:>+7.1f} "
              f"{str(r['paired_margin']):>8} {str(r['paired_z']):>6} {r['n_paired']:>5} "
              f"{r['sec_mean']:>7.1f} {r['sec_p95']:>6.1f}")
    print(f"\n[written] {out}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
