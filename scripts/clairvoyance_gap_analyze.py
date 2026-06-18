"""Analyze the clairvoyance-gap experiment: per-arm strength vs heur + the PAIRED
Δ(nonclair − clair) that isolates clairvoyance.

Reads the per-game JSONs from the clair and nonclair arm dirs (written by
clairvoyance_gap.py), matches games by (seed, net_player) so each comparison is
the SAME deck + SAME seat + SAME heur opponent differing only in clairvoyance,
and reports:
  - each arm's W/D/L, winrate, elo vs heur (the absolute anchors),
  - the paired per-cell score difference d = nonclair − clair → mean, se, z,
  - the clairvoyance GAP in elo (clair_elo − nonclair_elo),
  - V1 monotonicity check (nonclair <= clair expected),
  - V2 spot-check note.

Usage:
  python scripts/clairvoyance_gap_analyze.py \
    --clair-dir  /mnt/c/carc-shared/clairvoyance_gap/iter8_clair_K1_s200_h800_c30 \
    --nonclair-dir /mnt/c/carc-shared/clairvoyance_gap/iter8_nonclair_K12_s200_h800_c30 \
    --out measurement/clairvoyance/GAP_RESULTS.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _load(d: Path) -> dict:
    """Map (seed, net_player) -> result dict for every game json in dir."""
    out = {}
    for f in sorted(d.glob("seed*_p*.json")):
        try:
            r = json.load(open(f))
        except Exception:
            continue
        out[(int(r["seed"]), int(r["net_player"]))] = r
    return out


def _score(r) -> float:
    """iter8's match score vs heur: 1 win / 0.5 draw / 0 loss."""
    if r["drew"]:
        return 0.5
    return 1.0 if r["won_by_net"] else 0.0


def _elo(wr):
    wr = min(max(wr, 1e-6), 1 - 1e-6)
    return 400.0 * math.log10(wr / (1 - wr))


def _elo_sig(wr, n):
    if not (0 < wr < 1) or n == 0:
        return float("nan")
    sig = math.sqrt(wr * (1 - wr) / n)
    return (400.0 / math.log(10)) * sig / (wr * (1 - wr))


def _arm_stats(games: dict) -> dict:
    rs = list(games.values())
    n = len(rs)
    if not n:
        return {"n": 0}
    scores = [_score(r) for r in rs]
    w = sum(1 for s in scores if s == 1.0)
    dr = sum(1 for s in scores if s == 0.5)
    losses = sum(1 for s in scores if s == 0.0)
    wr = sum(scores) / n
    avg_diff = sum(r["diff"] for r in rs) / n
    return {"n": n, "W": w, "D": dr, "L": losses, "winrate": wr,
            "elo": _elo(wr), "elo_sig": _elo_sig(wr, n), "avg_diff": avg_diff}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clairvoyance_gap_analyze")
    ap.add_argument("--clair-dir", type=Path, required=True)
    ap.add_argument("--nonclair-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    clair = _load(args.clair_dir)
    nonclair = _load(args.nonclair_dir)
    cs = _arm_stats(clair)
    ns = _arm_stats(nonclair)

    # paired cells: (seed, player) present in BOTH arms
    keys = sorted(set(clair) & set(nonclair))
    diffs = []          # nonclair_score - clair_score per cell
    margin_diffs = []   # nonclair_diff - clair_diff (raw score margin vs heur)
    for k in keys:
        diffs.append(_score(nonclair[k]) - _score(clair[k]))
        margin_diffs.append(nonclair[k]["diff"] - clair[k]["diff"])
    npair = len(keys)
    mean_d = sum(diffs) / npair if npair else float("nan")
    if npair > 1:
        var = sum((x - mean_d) ** 2 for x in diffs) / (npair - 1)
        se_d = math.sqrt(var / npair)
    else:
        se_d = float("nan")
    z = mean_d / se_d if se_d and not math.isnan(se_d) and se_d > 0 else float("nan")
    mean_margin = sum(margin_diffs) / npair if npair else float("nan")

    # clairvoyance gap in elo: how many elo the agent LOSES going fair.
    gap_elo = (cs.get("elo", float("nan")) - ns.get("elo", float("nan"))) \
        if cs.get("n") and ns.get("n") else float("nan")
    delta_elo_signed = -gap_elo  # nonclair - clair (negative if fair is weaker)

    monotonic = (ns.get("winrate", 1) <= cs.get("winrate", 0) + 1e-9) \
        if (cs.get("n") and ns.get("n")) else None

    # interpretation per the pre-registered gates (guardrail #4)
    if not math.isnan(gap_elo):
        ag = abs(gap_elo)
        if ag >= 100:
            verdict = ("GAP >=100 elo: strength is HEAVILY clairvoyance-inflated. "
                       "Re-ground the strength narrative on non-clairvoyant play; "
                       "Level-2 must be built around the non-clairvoyant agent.")
        elif ag <= 30:
            verdict = ("GAP <=30 elo: hidden draw-order info is a MINOR contributor. "
                       "Clairvoyant numbers ~transfer; proceed toward the saturated-ruler/"
                       "ladder work (skip the expensive non-clairvoyant search).")
        else:
            verdict = ("GAP in (30,100): AMBIGUOUS. Top up n before committing to "
                       "Level 2/3; quantifies the deployable-strength discount.")
    else:
        verdict = "insufficient data"

    out = {
        "clair": cs, "nonclair": ns,
        "paired": {"n_cells": npair, "mean_d_nonclair_minus_clair": mean_d,
                   "se_d": se_d, "z": z, "mean_margin_diff": mean_margin},
        "gap_elo_clair_minus_nonclair": gap_elo,
        "delta_elo_nonclair_minus_clair": delta_elo_signed,
        "V1_monotonic_nonclair_le_clair": monotonic,
        "verdict": verdict,
    }

    def f(x, p="+.1f"):
        return ("{:" + p + "}").format(x) if isinstance(x, (int, float)) and not math.isnan(x) else "nan"

    print("=== CLAIRVOYANCE-GAP ANALYSIS ===")
    print(f"CLAIR    (K=1):  n={cs.get('n')}  {cs.get('W')}W/{cs.get('D')}D/{cs.get('L')}L  "
          f"wr={cs.get('winrate', float('nan')):.4f}  elo={f(cs.get('elo', float('nan')))} "
          f"(±{cs.get('elo_sig', float('nan')):.1f})  avg_diff={f(cs.get('avg_diff', float('nan')), '+.2f')}")
    print(f"NONCLAIR (K=12): n={ns.get('n')}  {ns.get('W')}W/{ns.get('D')}D/{ns.get('L')}L  "
          f"wr={ns.get('winrate', float('nan')):.4f}  elo={f(ns.get('elo', float('nan')))} "
          f"(±{ns.get('elo_sig', float('nan')):.1f})  avg_diff={f(ns.get('avg_diff', float('nan')), '+.2f')}")
    print()
    print(f"PAIRED cells: {npair}")
    print(f"  mean d (nonclair-clair score) = {f(mean_d, '+.4f')}  se={se_d:.4f}  z={f(z)}")
    print(f"  mean raw-margin diff (nonclair-clair, pts vs heur) = {f(mean_margin, '+.2f')}")
    print(f"  CLAIRVOYANCE GAP = clair_elo - nonclair_elo = {f(gap_elo)} elo")
    print(f"  Δelo(nonclair - clair) = {f(delta_elo_signed)}")
    print(f"  V1 monotonic (nonclair <= clair): {monotonic}")
    print()
    print("VERDICT:", verdict)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        json.dump(out, open(args.out, "w"), indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
