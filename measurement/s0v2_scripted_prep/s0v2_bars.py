#!/usr/bin/env python3
"""S0v2 BARS — read the three arms against DESIGN.md §4's pre-registered gates.

⛔ SMOKE INSTRUMENT.  Every counter it reads comes from ``s0_signature.py``'s
own output (which comes from ``stage_a_census.py`` verbatim); this script only
applies the gates and prints the table.  It invents no statistic.

CTRL is champion-vs-champion, so its two "agents" are the same player: the base
rate is the POOLED per-game deliberate count over both seats (2n observations),
which is exactly how ``s0_exploiter_prep/SMOKE_READOUT.md`` reported its own
CTRL ("0.450 / 0.550 -> pooled 0.500 +- 0.076").

Usage:
    s0v2_bars.py --root /mnt/c/carc-shared/s0v2_smoke_20260828
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ARMS = ["CTRL", "S0V2_M", "S0V2_F"]

# DESIGN.md §4
G_EXPRESS_ABS = 0.90
G_EXPRESS_SEP_SIGMA = 2.0
G_DAMAGE_PP = 10.0
G_COMPETITIVE_FLOOR = -25.0
G_COMPETITIVE_PREFERRED = -12.0


def _mean(xs):
    return (sum(xs) / len(xs)) if xs else float("nan")


def _sem(xs):
    if len(xs) < 2:
        return float("nan")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def load(root: Path, arm: str):
    lo = arm.lower()
    sig = json.loads((root / f"{lo}_rows" / "signature.json").read_text())
    tel = json.loads((root / f"{lo}_rows" / "telemetry.json").read_text())
    return sig["summary"], sig["per_game"], tel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.root)

    data = {a: load(root, a) for a in ARMS}

    # ---- the CTRL base rate: pooled over both seats -------------------------- #
    _cs, cpg, _ct = data["CTRL"]
    ctrl_pool = [g["del_a"] for g in cpg.values()] + [g["del_b"] for g in cpg.values()]
    ctrl_rate, ctrl_sem = _mean(ctrl_pool), _sem(ctrl_pool)

    # the champion's farmer-zero rate under CTRL, pooled over both seats
    cs = data["CTRL"][0]
    ctrl_fz = ((cs["farmer_zero_rate_a"] * cs["farmer_commits_a"]
                + cs["farmer_zero_rate_b"] * cs["farmer_commits_b"])
               / (cs["farmer_commits_a"] + cs["farmer_commits_b"]))

    rows = []
    for arm in ("S0V2_M", "S0V2_F"):
        s, pg, tel = data[arm]
        rate = s["deliberate_per_game_a"]
        sem = s["deliberate_per_game_a_sem"]
        pooled_sem = math.sqrt(sem ** 2 + ctrl_sem ** 2)
        sep = (rate - ctrl_rate) / pooled_sem if pooled_sem else float("nan")
        fz = s["farmer_zero_rate_b"]                 # the CHAMPION side
        damage_pp = 100.0 * (fz - ctrl_fz)
        margin, msem = s["margin_mean_a_minus_b"], s["margin_sem"]
        g_express = (rate >= G_EXPRESS_ABS) and (sep >= G_EXPRESS_SEP_SIGMA)
        g_damage = damage_pp >= G_DAMAGE_PP
        g_comp_hard = margin >= G_COMPETITIVE_FLOOR
        g_comp_resolved = (margin - G_COMPETITIVE_FLOOR) >= 2 * msem
        rows.append({
            "arm": arm, "n": s["n_games"],
            "deliberate_per_game": rate, "sem": sem,
            "multiple_of_ctrl": rate / ctrl_rate if ctrl_rate else float("nan"),
            "separation_sigma": sep,
            "G_EXPRESS_a": rate >= G_EXPRESS_ABS,
            "G_EXPRESS_b": sep >= G_EXPRESS_SEP_SIGMA,
            "G_EXPRESS": g_express,
            "champ_farmer_zero_rate": fz, "ctrl_farmer_zero_rate": ctrl_fz,
            "G_DAMAGE_pp": damage_pp, "G_DAMAGE": g_damage,
            "margin": margin, "margin_sem": msem,
            "G_COMPETITIVE_hard": g_comp_hard,
            "G_COMPETITIVE_hard_resolved": g_comp_resolved,
            "G_COMPETITIVE_preferred": margin >= G_COMPETITIVE_PREFERRED,
            "VALID": bool(g_express and g_damage and g_comp_hard),
            "plan_completion_rate": tel["plan_completion_rate"],
            "census_deliberate_over_onsets": tel["census_completion_rate"],
            "agent_fires_vs_census": (tel["agent_merge_fires_total"],
                                      tel["census_deliberate_total"]),
            "worker_s_per_game_upper_bound": tel["worker_s_per_game"],
        })

    # ---- deck-matched margin contrasts (all arms ran the SAME decks) --------- #
    contrasts = {}
    for a in ("S0V2_M", "S0V2_F"):
        pg_a = data[a][1]
        pg_c = data["CTRL"][1]
        common = sorted(set(pg_a) & set(pg_c))
        d = [pg_a[g]["margin"] - pg_c[g]["margin"] for g in common]
        contrasts[f"{a}_minus_CTRL_deck_matched"] = {
            "n": len(d), "mean": _mean(d), "sem": _sem(d)}

    print(f"CTRL base deliberate/game (pooled over both seats, n={len(ctrl_pool)}): "
          f"{ctrl_rate:.4f} +- {ctrl_sem:.4f}")
    print(f"CTRL champion farmer-zero rate (pooled): {100*ctrl_fz:.2f} %")
    print()
    hdr = (f"{'arm':8s} {'n':>3s} {'delib/g':>9s} {'sem':>6s} {'xCTRL':>6s} "
           f"{'sep_s':>6s} {'EXPa':>5s} {'EXPb':>5s} {'dmg_pp':>7s} {'DMG':>4s} "
           f"{'margin':>8s} {'sem':>5s} {'COMP':>5s} {'VALID':>6s}")
    print(hdr)
    for r in rows:
        print(f"{r['arm']:8s} {r['n']:3d} {r['deliberate_per_game']:9.4f} "
              f"{r['sem']:6.3f} {r['multiple_of_ctrl']:6.2f} "
              f"{r['separation_sigma']:6.2f} "
              f"{'PASS' if r['G_EXPRESS_a'] else 'FAIL':>5s} "
              f"{'PASS' if r['G_EXPRESS_b'] else 'FAIL':>5s} "
              f"{r['G_DAMAGE_pp']:+7.2f} {'PASS' if r['G_DAMAGE'] else 'FAIL':>4s} "
              f"{r['margin']:+8.2f} {r['margin_sem']:5.2f} "
              f"{'PASS' if r['G_COMPETITIVE_hard'] else 'FAIL':>5s} "
              f"{'YES' if r['VALID'] else 'NO':>6s}")
    print()
    for k, v in contrasts.items():
        print(f"{k}: n={v['n']} mean={v['mean']:+.2f} sem={v['sem']:.2f} "
              f"z={v['mean']/v['sem'] if v['sem'] else float('nan'):+.2f}")
    print()
    for r in rows:
        print(f"{r['arm']}: plan completion {r['plan_completion_rate']}, "
              f"census deliberate/onset {r['census_deliberate_over_onsets']:.3f}, "
              f"agent fires vs census {r['agent_fires_vs_census']}, "
              f"{r['worker_s_per_game_upper_bound']:.1f} worker-s/game (upper bound)")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"ctrl_rate": ctrl_rate, "ctrl_sem": ctrl_sem,
             "ctrl_farmer_zero_rate": ctrl_fz, "arms": rows,
             "deck_matched_contrasts": contrasts}, indent=2, sort_keys=True))
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
