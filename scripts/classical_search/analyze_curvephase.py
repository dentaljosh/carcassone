#!/usr/bin/env python3
"""Part-C beta ladder: the FITTED WITHIN-DECK SLOPE, and the pre-registered C-readings.

Pre-registration: measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part C.

  "Primary statistic for Part C is the FITTED WITHIN-DECK SLOPE of `margin` on beta
   across the five points -- not any individual cell."

WHY WITHIN-DECK. All five cells share band 1.15e11, so every deck is played in every
cell. Deck identity is therefore a paired factor and differencing it out removes the
deck-luck variance that dominates a single cell at n=200 (~+/-17 elo at 1 sigma). The
line across the ladder is the measurement; the individual cells are underpowered BY
DESIGN and must not be read as five verdicts.

MARGIN SIGN. Per-game `diff` is score_p0 - score_p1 and `a_seat` says which seat the
CANDIDATE took, so candidate-minus-opponent is `diff if a_seat == 0 else -diff`. A deck's
seat-balanced margin is the mean over its two seatings, which cancels any seat advantage.

ESTIMATOR. Deck-demeaned OLS of margin on beta (equivalent to deck fixed effects), with
a CLUSTER-ROBUST sandwich SE on deck -- the same discipline the oracle-price read uses,
because a deck contributes five correlated points.

C-readings, in the prereg's order:
  C-KILL      |slope z| < 2.0            -> PHASE AXIS DEAD in the modern era with the
                                            magnitude confound removed. Materially
                                            stronger than the 2026-06-22 v28 kill.
  C-RECONFIRM slope significantly NEGATIVE -> v28 reconfirmed on clean ground; axis closes.
  C-FIRE      slope z >= 2.0 (either sign) -> one n=400 fresh-deck confirm at the best-fit
                                            beta; escalate only if margin_z >= 2.0 there.

⚠️ The beta=0 cell is ALSO the wiring gate: |elo| < 25 or the ladder is VOID.
⚠️ A cell under 90% completion is VOID and is excluded from the fit (stated in output).
"""
import argparse
import json
import math
from pathlib import Path

CELLS = {"bm0p6": -0.6, "bm0p3": -0.3, "b0p0": 0.0, "b0p3": 0.3, "b0p6": 0.6}
IDENTITY = "b0p0"


def deck_margins(cell_dir: Path):
    """seed -> seat-balanced candidate-minus-opponent margin (only decks with both seats)."""
    per = {}
    for f in cell_dir.glob("seed*.json"):
        if "summary" in f.name:
            continue
        try:
            g = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "diff" not in g or "a_seat" not in g:
            continue
        m = float(g["diff"]) * (1.0 if int(g["a_seat"]) == 0 else -1.0)
        per.setdefault(int(g["seed"]), {})[int(g["a_seat"])] = m
    return {s: (v[0] + v[1]) / 2.0 for s, v in per.items() if 0 in v and 1 in v}


def fit_within_deck_slope(points):
    """points: list of (deck, beta, margin). Deck-demeaned OLS + cluster-robust SE on deck."""
    by_deck = {}
    for d, b, m in points:
        by_deck.setdefault(d, []).append((b, m))
    # keep only decks observed at >=2 distinct betas -- a deck seen once carries no slope
    by_deck = {d: v for d, v in by_deck.items() if len({b for b, _ in v}) >= 2}
    if not by_deck:
        return None
    num = den = 0.0
    for d, v in by_deck.items():
        bb = sum(b for b, _ in v) / len(v)
        mm = sum(m for _, m in v) / len(v)
        for b, m in v:
            num += (b - bb) * (m - mm)
            den += (b - bb) ** 2
    if den <= 0:
        return None
    slope = num / den
    # cluster-robust sandwich: meat = sum_d (sum_i x_it * e_it)^2, bread = 1/den
    meat = 0.0
    for d, v in by_deck.items():
        bb = sum(b for b, _ in v) / len(v)
        mm = sum(m for _, m in v) / len(v)
        s = 0.0
        for b, m in v:
            x = b - bb
            s += x * ((m - mm) - slope * x)
        meat += s * s
    se = math.sqrt(meat) / den if meat > 0 else float("nan")
    return {"slope": slope, "se": se, "z": (slope / se) if se and se == se and se > 0 else float("nan"),
            "n_decks": len(by_deck), "n_points": sum(len(v) for v in by_deck.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-root", default="/mnt/c/carc-shared/curvephase_ladder")
    ap.add_argument("--prefix", default="cp_")
    ap.add_argument("--n-expected", type=int, default=200)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.run_root)

    cells, points, notes = [], [], []
    for cid, beta in CELLS.items():
        d = root / f"{a.prefix}{cid}"
        sp = d / "summary.json"
        row = {"cell": cid, "beta": beta, "present": sp.exists()}
        if sp.exists():
            s = json.loads(sp.read_text())
            row.update(n=s.get("n"), elo=s.get("elo"), elo_sig=s.get("elo_sig_1sigma"),
                       paired_z=s.get("paired_z"),
                       paired_mean_margin=s.get("paired_mean_margin"))
            row["completion"] = (s.get("n", 0) / a.n_expected) if a.n_expected else 0
        if d.exists():
            dm = deck_margins(d)
            row["n_decks_paired"] = len(dm)
            if dm:
                row["mean_margin_recomputed"] = sum(dm.values()) / len(dm)
            if row.get("completion", 0) >= 0.90:
                for seed, m in dm.items():
                    points.append((seed, beta, m))
            elif row.get("present"):
                notes.append(f"{cid}: completion {row.get('completion'):.0%} < 90% -> VOID, excluded from the fit")
        cells.append(row)

    ident = next((c for c in cells if c["cell"] == IDENTITY), None)
    gate = "PENDING"
    if ident and ident.get("present"):
        gate = "OK" if (ident.get("elo") is not None and abs(ident["elo"]) < 25) else "INSTRUMENT-BROKEN"

    fit = fit_within_deck_slope(points) if points else None
    verdict, why = "PENDING", "not all cells complete"
    if gate == "INSTRUMENT-BROKEN":
        verdict, why = "INSTRUMENT-BROKEN", (
            f"beta=0 identity cell reads elo {ident['elo']:+.1f} (|elo| >= 25) => ladder VOID")
    elif fit and sum(1 for c in cells if c.get("present")) == len(CELLS):
        z = fit["z"]
        if z == z and abs(z) >= 2.0:
            if z < 0:
                verdict, why = "C-RECONFIRM", (
                    f"slope {fit['slope']:+.4f} pts/deck per unit beta, z {z:+.2f} -- significantly "
                    "NEGATIVE. v28's finding is RECONFIRMED on clean ground with the magnitude "
                    "confound removed; the phase axis closes permanently.")
            else:
                verdict, why = "C-FIRE", (
                    f"slope {fit['slope']:+.4f}, z {z:+.2f} >= 2.0 => run ONE n=400 fresh-deck "
                    "confirm at the best-fit beta; escalate only if margin_z >= 2.0 there.")
        else:
            verdict, why = "C-KILL", (
                f"fitted within-deck slope {fit['slope']:+.4f} pts/deck per unit beta, "
                f"se {fit['se']:.4f}, z {z:+.2f} -- |z| < 2.0 => PHASE AXIS DEAD in the modern "
                "era with the magnitude confound removed. Materially stronger than the "
                "2026-06-22 v28 kill (one unbracketed endpoint, magnitude confounded). "
                "Wording: this kills the axis at THIS instrument's resolution.")

    notes.append("Primary statistic is the FITTED WITHIN-DECK SLOPE; the five cells are "
                 "underpowered individually BY DESIGN (n=200 ~ +/-17 elo at 1 sigma) and must "
                 "not be read as five verdicts.")
    notes.append("E[f]=1 renormalization is the ONLY thing licensing this retry of the v28 "
                 "kill; norms are an approximation of the MCTS leaf-k histogram (~0.5% residue).")
    out = {"verdict": verdict, "why": why, "identity_gate": gate, "slope_fit": fit,
           "cells": cells, "notes": notes}
    txt = json.dumps(out, indent=2, default=str)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
