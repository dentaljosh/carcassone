#!/usr/bin/env python3
"""Part C/D/F analysis for the exact-endgame-hybrid eval.

Reads a cell's per-game GameResult JSONs (eval_hybrid_handoff schema) and computes:
  - headline: WDL, winrate, winrate-Elo (+1sigma), paired score margin, paired_z, seat split
  - Part D slices on the exact agent (A side): actual K@latch, margin@handoff bucket,
    close/blowout, seat, meeples@latch, legal@latch bucket, timeout, solver-node bucket
  - handoff/solver instrumentation summary (exact-moves/game, solver s/game, timeouts)
  - Part F paired-Delta vs a baseline cell on the SAME decks (e.g. cached RoD1-vs-h3200):
    per (seed,a_seat) Delta = my_diff - baseline_diff, then mean Delta + paired_z(Delta).
    This isolates the EXACT TAIL's effect vs an identical opponent on identical decks.

  python scripts/exact_hybrid/analyze_exact_eval.py --cell <dir> [--baseline <dir>] \
      [--label "exact:2 vs h3200"] [--out <digest.md>]
"""
from __future__ import annotations
import argparse, json, math, statistics as st
from pathlib import Path


def load_games(d: Path) -> list[dict]:
    out = []
    for p in sorted(d.glob("seed*_a*.json")):
        try:
            out.append(json.load(open(p)))
        except Exception:
            pass
    return out


def wr_elo(wr, n):
    if not (0 < wr < 1):
        return math.copysign(800.0, wr - 0.5), float("nan")
    elo = 400.0 * math.log10(wr / (1 - wr))
    sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    return elo, sig


def paired(records, key="diff"):
    """records: list of dicts w/ seed,a_seat,<key>. Pair (seed,0)+(seed,1) -> mean margin."""
    by = {}
    for r in records:
        by.setdefault(r["seed"], {})[r["a_seat"]] = r[key]
    ds = [(v[0] + v[1]) / 2.0 for v in by.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, len(ds)
    m = sum(ds) / len(ds)
    var = sum((d - m) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    return m, (m / se if se else float("nan")), len(ds)


def headline(games, label):
    n = len(games)
    w = sum(1 for g in games if g["won_by_a"])
    d = sum(1 for g in games if g["drew"])
    losses = n - w - d
    wr = (w + 0.5 * d) / n
    wr_z = (wr - 0.5) / math.sqrt(0.25 / n) if n else float("nan")
    elo, sig = wr_elo(wr, n)
    mm, z, npair = paired(games)
    avg = sum(g["diff"] for g in games) / n
    s0 = [g for g in games if g["a_seat"] == 0]
    s1 = [g for g in games if g["a_seat"] == 1]
    def swr(gs):
        return (sum(1 for g in gs if g["won_by_a"]) + 0.5 * sum(1 for g in gs if g["drew"])) / len(gs) if gs else float("nan")
    L = [f"### {label}",
         f"- games **{n}** | **{w}W / {d}D / {losses}L** | winrate **{wr:.3f}** (z={wr_z:+.2f}) | Elo **{elo:+.1f}** (±{sig:.1f})",
         f"- avg score margin (A−B) **{avg:+.2f}** | **paired margin {mm:+.3f}** (z=**{z:+.2f}**, {npair} decks)",
         f"- seat split: A@seat0 wr {swr(s0):.3f} (n={len(s0)}), A@seat1 wr {swr(s1):.3f} (n={len(s1)})"]
    return L, dict(n=n, w=w, d=d, l=losses, wr=wr, elo=elo, paired=mm, paired_z=z, npair=npair, avg=avg)


def solver_summary(games):
    ex = [g.get("a_exact_moves", 0) for g in games]
    sv = [g.get("a_solver_secs", 0.0) for g in games]
    to = [g.get("a_timeouts", 0) for g in games]
    lk = [g.get("a_latch_k") for g in games if g.get("a_latch_k") is not None]
    nd = [g.get("a_solver_nodes", 0) for g in games]
    n = len(games)
    return [f"- A exact: exact-moves/game {sum(ex)/n:.2f} (range {min(ex)}-{max(ex)}); "
            f"solver {sum(sv)/n:.2f}s/game (max {max(sv):.1f}s); nodes/game {sum(nd)/n:.0f}; "
            f"timeouts {sum(to)} over {n}; latched {len(lk)}/{n}; "
            f"K@latch dist {dict(sorted({k: lk.count(k) for k in set(lk)}.items()))}"]


def slices(games):
    """Part D: paired margin within slices of the A-side exact instrumentation."""
    out = ["#### Part D slices (paired margin within slice; n=decks w/ both seats)"]
    def emit(name, keyfn):
        buckets = {}
        for g in games:
            b = keyfn(g)
            if b is None:
                continue
            buckets.setdefault(b, []).append(g)
        rows = []
        for b, gs in sorted(buckets.items(), key=lambda x: str(x[0])):
            mm, z, npair = paired(gs)
            wr = (sum(1 for g in gs if g["won_by_a"]) + 0.5 * sum(1 for g in gs if g["drew"])) / len(gs)
            rows.append(f"    - {name}={b}: n={len(gs)} wr={wr:.3f} paired={mm if mm is None else round(mm,2)} "
                        f"(z={z if z is None else round(z,2)}, {npair} decks)")
        if rows:
            out.append(f"  - **by {name}**")
            out.extend(rows)
    emit("K@latch", lambda g: g.get("a_latch_k"))
    emit("seat", lambda g: g.get("a_seat"))
    emit("margin@latch", lambda g: None if g.get("a_latch_score") is None else
         ("behind(<-3)" if g["a_latch_score"] < -3 else "close(-3..3)" if g["a_latch_score"] <= 3 else "ahead(>3)"))
    emit("meeples@latch", lambda g: None if g.get("a_latch_meeples") is None else
         ("0-1" if g["a_latch_meeples"] <= 1 else "2-3" if g["a_latch_meeples"] <= 3 else "4+"))
    emit("legal@latch", lambda g: None if g.get("a_latch_nlegal") is None else
         ("lo(<20)" if g["a_latch_nlegal"] < 20 else "mid(20-45)" if g["a_latch_nlegal"] <= 45 else "hi(>45)"))
    emit("game", lambda g: "blowout(|d|>=20)" if abs(g["diff"]) >= 20 else "close(|d|<20)")
    emit("timeout", lambda g: "timeout" if g.get("a_timeouts", 0) > 0 else "clean")
    emit("solver_nodes", lambda g: None if not g.get("a_solver_nodes") else
         ("<1k" if g["a_solver_nodes"] < 1000 else "1k-5k" if g["a_solver_nodes"] < 5000 else ">5k"))
    return out


def paired_delta(cell, baseline, label):
    """Part F: per (seed,a_seat) Delta = cell.diff - baseline.diff (same decks/opponent)."""
    bidx = {(g["seed"], g["a_seat"]): g["diff"] for g in baseline}
    deltas = []
    for g in cell:
        k = (g["seed"], g["a_seat"])
        if k in bidx:
            deltas.append({"seed": g["seed"], "a_seat": g["a_seat"], "diff": g["diff"] - bidx[k]})
    if not deltas:
        return ["#### Part F paired-Δ vs baseline: NO overlapping (seed,seat) — different decks"]
    mm, z, npair = paired(deltas)
    raw = [x["diff"] for x in deltas]
    return ["#### Part F — paired Δ vs baseline (same decks, same opponent; isolates the exact tail)",
            f"- overlapping games: {len(deltas)} ({npair} decks w/ both seats) — baseline = {label}",
            f"- mean per-game Δ(margin) {sum(raw)/len(raw):+.3f}; **paired Δ margin {mm:+.3f} (z=**{z:+.2f}**)**",
            f"  (Δ>0 ⇒ the exact tail improves RoD1's margin vs this opponent on these decks)"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    ap.add_argument("--baseline", default=None, help="cached cell on the SAME decks/opponent for the paired Δ")
    ap.add_argument("--baseline-label", default="cached RoD1-vs-opponent")
    ap.add_argument("--label", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    cell = load_games(Path(args.cell))
    label = args.label or Path(args.cell).name
    if not cell:
        print(f"no games in {args.cell}"); return 1
    L, summ = headline(cell, label)
    L += solver_summary(cell)
    L += [""] + slices(cell)
    if args.baseline:
        base = load_games(Path(args.baseline))
        L += [""] + paired_delta(cell, base, args.baseline_label)
    txt = "\n".join(L)
    print(txt)
    if args.out:
        open(args.out, "w").write(txt + "\n")
        print(f"\n[written] {args.out}")
    json.dump(summ, open(Path(args.cell) / "analysis_summary.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
