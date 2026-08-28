#!/usr/bin/env python3
"""Aggregate the priced rows into the pre-registered readouts.

⚠️ THE POOLING RULE IS BINDING (PREREG §1.4): `exact_marginalized`,
`exact_clairvoyant_M` and `realized` are THREE DIFFERENT INSTRUMENTS and are
never pooled with each other. Every table below is reported per mode.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

STRATA = ("invasion", "farm_capture", "defense", "control")
MODES = ("exact_marginalized", "exact_clairvoyant_M", "realized")


def mean_sem(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, None, n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var / n), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    all_rows = []
    for p in args.rows:
        for line in Path(p).open():
            all_rows.append(json.loads(line))

    # FORCED PLIES CARRY NO DECISION AND THEREFORE NO PRICE. A ply with one legal
    # action prices to exactly 0 for everyone, which would drag every mean toward
    # zero and read as "the exploit is worth nothing". Stage B lost 108/405 rows
    # this way; they are excluded here and counted, never silently averaged in.
    rows = [r for r in all_rows if r.get("n_legal", 2) > 1]
    forced = [r for r in all_rows if r.get("n_legal", 2) <= 1]

    out = {"n_rows_total": len(all_rows), "n_rows_analyzed": len(rows),
           "n_forced_excluded": len(forced),
           "forced_by_stratum": {s: sum(1 for r in forced if r["stratum"] == s)
                                 for s in STRATA},
           "n_games": len({r["game"] for r in rows})}

    # --- coverage, stated first ------------------------------------------- #
    cov = defaultdict(lambda: defaultdict(int))
    for r in rows:
        cov[r["pricing_mode"]][r["stratum"]] += 1
        if r.get("delta_pts_mover") is not None:
            cov[r["pricing_mode"]]["_priced"] += 1
        st = (r.get("solve") or {}).get("status")
        if st and st not in ("OK", "NOT_SOLVED"):
            cov[r["pricing_mode"]][f"_skip_{st}"] += 1
    out["coverage"] = {m: dict(v) for m, v in cov.items()}

    # --- the priced tables, per mode, per stratum -------------------------- #
    tables = {}
    for mode in MODES:
        t = {}
        for s in STRATA:
            sub = [r for r in rows if r["pricing_mode"] == mode and r["stratum"] == s]
            d = [r.get("delta_pts_mover") for r in sub]
            g = [r.get("regret_pts_mover") for r in sub]
            agree = [r.get("counterfactual_agrees") for r in sub
                     if r.get("counterfactual_agrees") is not None]
            md, sd, nd = mean_sem(d)
            mg, sg, ng = mean_sem(g)
            t[s] = {
                "n_rows": len(sub), "n_priced": nd,
                "mean_delta_pts_mover": md, "sem_delta": sd,
                "total_delta_pts_mover": sum(x for x in d if x is not None) or 0.0,
                "mean_regret_pts_mover": mg, "sem_regret": sg, "n_regret": ng,
                "champion_agreement_rate": (sum(agree) / len(agree)) if agree else None,
                "n_agreement": len(agree),
            }
        tables[mode] = t
    out["by_mode_by_stratum"] = tables

    # --- invasion vs its matched control, per mode (the actual test) ------- #
    excess = {}
    for mode in MODES:
        e = {}
        ctrl = [r.get("delta_pts_mover") for r in rows
                if r["pricing_mode"] == mode and r["stratum"] == "control"]
        mc, sc, nc = mean_sem(ctrl)
        for s in ("invasion", "farm_capture", "defense"):
            sub = [r.get("delta_pts_mover") for r in rows
                   if r["pricing_mode"] == mode and r["stratum"] == s]
            ms, ss, ns = mean_sem(sub)
            if ms is None or mc is None:
                e[s] = {"n": ns, "excess": None}
                continue
            se = math.sqrt((ss or 0) ** 2 + (sc or 0) ** 2)
            e[s] = {"n": ns, "n_control": nc, "mean": ms, "control_mean": mc,
                    "excess": ms - mc, "sem_excess": se or None,
                    "z": ((ms - mc) / se) if se else None}
        excess[mode] = e
    out["excess_over_control"] = excess

    # --- per-game totals of the invasion channel --------------------------- #
    per_game = defaultdict(lambda: defaultdict(float))
    for r in rows:
        if r["stratum"] in ("invasion", "farm_capture") \
                and r.get("delta_pts_mover") is not None:
            per_game[r["game"]][r["pricing_mode"]] += r["delta_pts_mover"]
    out["invasion_channel_per_game"] = {g: dict(v) for g, v in per_game.items()}

    # --- the census gross, alongside (NOT pooled) -------------------------- #
    gross_gain = [(r.get("notes") or {}).get("invader_gain") for r in rows
                  if r["stratum"] == "invasion"]
    gross_den = [(r.get("notes") or {}).get("incumbent_denied") for r in rows
                 if r["stratum"] == "invasion"]
    mg, sg, ng = mean_sem(gross_gain)
    md, sd, nd = mean_sem(gross_den)
    out["stage_a_gross_reference"] = {
        "mean_invader_gain_per_event": mg, "n": ng,
        "mean_incumbent_denied_per_event": md,
        "note": "Stage A DESCRIPTIVE gross. Never an EV; never pooled with a price.",
    }

    # --- champion agreement, pooled over ALL K (judge-free at every K) ----- #
    # This is the one readout defined on the whole 290-ply set: it counts how often
    # the production champion would have played the owner's move. It is a POLICY
    # AGREEMENT COUNT, not a score — the champion never grades anything here — so
    # it survives above the exact cut where no price exists.
    agree_all = {}
    for s in STRATA:
        a = [r["counterfactual_agrees"] for r in rows
             if r["stratum"] == s and r.get("counterfactual_agrees") is not None]
        n_err = sum(1 for r in rows
                    if r["stratum"] == s and r.get("counterfactual_error"))
        agree_all[s] = {"n": len(a),
                        "agreement_rate": (sum(a) / len(a)) if a else None,
                        "n_counterfactual_errors": n_err}
    out["champion_agreement_all_K"] = agree_all

    # --- realized-outcome arithmetic (descriptive) ------------------------- #
    real = {}
    for s in STRATA:
        sub = [r for r in rows if r["stratum"] == s and r.get("realized")]
        mw, sw, nw = mean_sem([r["realized"]["realized_swing_W"] for r in sub])
        me, se, ne = mean_sem([r["realized"]["realized_swing_end"] for r in sub])
        real[s] = {"n": nw, "mean_swing_W": mw, "sem_swing_W": sw,
                   "mean_swing_end": me, "sem_swing_end": se}
    out["realized_descriptive"] = real
    out["caveats"] = {
        "pooling": "exact_marginalized / exact_clairvoyant_M / realized are three "
                   "different instruments and are never pooled.",
        "clairvoyance_gap": "exact_clairvoyant_M is an OPTIMISTIC bound for both "
                            "seats, not a calibrated EV.",
        "realized": "descriptive archive arithmetic, wide error bars, no counterfactual.",
        "cross_band": "n/a — this is analysis over existing archives, no game cells.",
    }

    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in
                      ("n_rows_total", "n_rows_analyzed", "n_forced_excluded",
                       "n_games", "coverage", "excess_over_control")},
                     indent=1))


if __name__ == "__main__":
    main()
