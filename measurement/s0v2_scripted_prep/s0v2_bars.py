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

ROUNDS = {
    1: ("CTRL", ["S0V2_M", "S0V2_F"]),
    2: ("CTRL2", ["S0V2_F2", "S0V2_FM"]),   # the MAJORITY amendment
    # round 3: HOLD + the two instrument fixes, on TWO disjoint fresh ranges.
    # `--round 3` reads range A, `--round 4` range B, `--round 34` applies the
    # TWO-RANGE REPLICATION CLAUSE across both (DESIGN.md §4.2).
    3: ("CTRL_A", ["FM_A", "FMH_A"]),
    4: ("CTRL_B", ["FM_B", "FMH_B"]),
}
REPLICATION = {34: (3, 4)}

# DESIGN.md §4
G_EXPRESS_ABS = 0.90
G_EXPRESS_SEP_SIGMA = 2.0
G_DAMAGE_PP = 10.0
G_COMPETITIVE_FLOOR = -25.0
G_COMPETITIVE_PREFERRED = -12.0
# DESIGN.md §4.2: G-DENY replaces G-DAMAGE as the PRIMARY damage gate.
G_DENY_UPLIFT = 1.5          # pts/game over the same-range CTRL, deck-matched
G_DENY_POOLED_Z = 2.0        # on the two-range pooled estimate


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


def replication(root: Path, ra: int, rb: int, out_path=None) -> int:
    """The TWO-RANGE REPLICATION CLAUSE (DESIGN.md §4.2).

    An arm is S0v2-VALID only if it clears EVERY gate on BOTH disjoint fresh
    ranges, **and** its pooled G-DENY uplift clears the bar at z >= 2.  Round 2
    proved a single range cannot certify: the SAME agent read G-DAMAGE +2.25 pp
    on one range and +10.66 pp on the next."""
    a = {r["arm"].rsplit("_", 1)[0]: r for r in _round_rows(root, ra)}
    b = {r["arm"].rsplit("_", 1)[0]: r for r in _round_rows(root, rb)}
    out = {}
    print("\n=== TWO-RANGE REPLICATION CLAUSE (DESIGN §4.2) ===")
    print(f"{'arm':6s} {'A:delib':>8s} {'B:delib':>8s} {'A:deny+':>8s} {'B:deny+':>8s} "
          f"{'pooled':>7s} {'sem':>5s} {'z':>6s} {'A:VALID':>8s} {'B:VALID':>8s} "
          f"{'REPLICATED':>11s}")
    for name in sorted(set(a) & set(b)):
        ra_, rb_ = a[name], b[name]
        pooled = list(ra_["deny_by_game"].values()) + list(rb_["deny_by_game"].values())
        pm, ps = _mean(pooled), _sem(pooled)
        z = (pm / ps) if ps else float("nan")
        rep = bool(ra_["VALID"] and rb_["VALID"]
                   and pm >= G_DENY_UPLIFT and z >= G_DENY_POOLED_Z)
        out[name] = {
            "range_a": ra_["arm"], "range_b": rb_["arm"],
            "a_valid": ra_["VALID"], "b_valid": rb_["VALID"],
            "pooled_deny_uplift": pm, "pooled_deny_sem": ps, "pooled_deny_z": z,
            "pooled_n": len(pooled), "REPLICATED": rep,
        }
        print(f"{name:6s} {ra_['deliberate_per_game']:8.3f} "
              f"{rb_['deliberate_per_game']:8.3f} {ra_['G_DENY_uplift']:+8.2f} "
              f"{rb_['G_DENY_uplift']:+8.2f} {pm:+7.2f} {ps:5.2f} {z:+6.2f} "
              f"{'YES' if ra_['VALID'] else 'NO':>8s} "
              f"{'YES' if rb_['VALID'] else 'NO':>8s} "
              f"{'YES' if rep else 'NO':>11s}")
    if out_path:
        Path(out_path).write_text(json.dumps(out, indent=2, sort_keys=True))
        print(f"\nwrote {out_path}")
    return 0


def _round_rows(root: Path, rnd: int) -> list:
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rows, _ = _evaluate(root, rnd)
    return rows


def _evaluate(root: Path, rnd: int):
    CTRL, ARM_NAMES = ROUNDS[rnd]

    data = {a: load(root, a) for a in [CTRL] + ARM_NAMES}

    # ---- the CTRL base rate: pooled over both seats -------------------------- #
    _cs, cpg, _ct = data[CTRL]
    ctrl_pool = [g["del_a"] for g in cpg.values()] + [g["del_b"] for g in cpg.values()]
    ctrl_rate, ctrl_sem = _mean(ctrl_pool), _sem(ctrl_pool)

    # the champion's farmer-zero rate under CTRL, pooled over both seats
    cs = data[CTRL][0]
    ctrl_fz = ((cs["farmer_zero_rate_a"] * cs["farmer_commits_a"]
                + cs["farmer_zero_rate_b"] * cs["farmer_commits_b"])
               / (cs["farmer_commits_a"] + cs["farmer_commits_b"]))

    rows = []
    for arm in ARM_NAMES:
        s, pg, tel = data[arm]
        rate = s["deliberate_per_game_a"]
        sem = s["deliberate_per_game_a_sem"]
        pooled_sem = math.sqrt(sem ** 2 + ctrl_sem ** 2)
        sep = (rate - ctrl_rate) / pooled_sem if pooled_sem else float("nan")
        fz = s["farmer_zero_rate_b"]                 # the CHAMPION side
        damage_pp = 100.0 * (fz - ctrl_fz)
        margin, msem = s["margin_mean_a_minus_b"], s["margin_sem"]
        # ---- G-DENY: deck-matched denial uplift over the same-range CTRL ----- #
        db_a = tel["census_outcomes"]["denied_by_game"]
        db_c = data[CTRL][2]["census_outcomes"]["denied_by_game"]
        common = sorted(set(db_a) & set(db_c))
        dd = [db_a[g] - db_c[g] for g in common]
        deny_up, deny_sem = _mean(dd), _sem(dd)
        g_deny = deny_up >= G_DENY_UPLIFT
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
            "G_DAMAGE_pp": damage_pp, "G_DAMAGE_reported_only": g_damage,
            "deny_per_game": tel["denied_per_game"],
            "ctrl_deny_per_game": data[CTRL][2]["denied_per_game"],
            "G_DENY_uplift": deny_up, "G_DENY_sem": deny_sem,
            "G_DENY_z": (deny_up / deny_sem) if deny_sem else float("nan"),
            "G_DENY": g_deny,
            "deny_by_game": {g: db_a[g] - db_c[g] for g in common},
            "margin": margin, "margin_sem": msem,
            "G_COMPETITIVE_hard": g_comp_hard,
            "G_COMPETITIVE_hard_resolved": g_comp_resolved,
            "G_COMPETITIVE_preferred": margin >= G_COMPETITIVE_PREFERRED,
            # DESIGN §4.2: VALID = G-EXPRESS AND G-DENY AND G-COMPETITIVE.
            # G-DAMAGE is REPORTED, not gating (see §4.2's disclosure).
            "VALID": bool(g_express and g_deny and g_comp_hard),
            "plan_completion_rate": tel["plan_completion_rate"],
            "took_all_rate": tel["census_outcomes"]["outcome_rates"].get(
                "invader_took_all", 0.0),
            "incumbent_held_rate": tel["census_outcomes"]["outcome_rates"].get(
                "incumbent_held", 0.0),
            "outnumbering_rate": tel["census_outcomes"]["outnumbering_rate"] or 0.0,
            "majority_fires": tel["telemetry_totals"].get("majority_fires", 0),
            "majority_from_tie": tel["telemetry_totals"].get("majority_from_tie", 0),
            "meeples_spent_on_reinforcement":
                tel["telemetry_totals"].get("meeples_spent_on_reinforcement", 0),
            "reinforce_plans": (tel["telemetry_totals"].get("reinforce_plans_started", 0),
                                tel["telemetry_totals"].get("reinforce_plans_completed", 0)),
            "census_deliberate_over_onsets": tel["census_completion_rate"],
            "agent_fires_vs_census": (tel["agent_merge_fires_total"],
                                      tel["census_deliberate_total"]),
            "worker_s_per_game_upper_bound": tel["worker_s_per_game"],
        })

    # ---- deck-matched margin contrasts (all arms ran the SAME decks) --------- #
    contrasts = {}
    for a in ARM_NAMES:
        pg_a = data[a][1]
        pg_c = data[CTRL][1]
        common = sorted(set(pg_a) & set(pg_c))
        d = [pg_a[g]["margin"] - pg_c[g]["margin"] for g in common]
        contrasts[f"{a}_minus_{CTRL}_deck_matched"] = {
            "n": len(d), "mean": _mean(d), "sem": _sem(d)}
    if len(ARM_NAMES) == 2:
        pg_x, pg_y = data[ARM_NAMES[1]][1], data[ARM_NAMES[0]][1]
        common = sorted(set(pg_x) & set(pg_y))
        d = [pg_x[g]["margin"] - pg_y[g]["margin"] for g in common]
        contrasts[f"{ARM_NAMES[1]}_minus_{ARM_NAMES[0]}_deck_matched"] = {
            "n": len(d), "mean": _mean(d), "sem": _sem(d)}

    print(f"CTRL base deliberate/game (pooled over both seats, n={len(ctrl_pool)}): "
          f"{ctrl_rate:.4f} +- {ctrl_sem:.4f}")
    ctrl_took_all = data[CTRL][2]["census_outcomes"]["outcome_rates"].get(
        "invader_took_all", 0.0)
    print(f"CTRL champion farmer-zero rate (pooled): {100*ctrl_fz:.2f} %")
    print(f"CTRL invader_took_all rate: {100*ctrl_took_all:.2f} %")
    print()
    hdr = (f"{'arm':8s} {'n':>3s} {'delib/g':>9s} {'sem':>6s} {'sep_s':>6s} "
           f"{'EXP':>4s} {'deny+':>7s} {'sem':>5s} {'z':>5s} {'DENY':>5s} "
           f"{'margin':>8s} {'sem':>5s} {'COMP':>5s} {'VALID':>6s} {'[dmg_pp]':>9s}")
    print(hdr)
    for r in rows:
        print(f"{r['arm']:8s} {r['n']:3d} {r['deliberate_per_game']:9.4f} "
              f"{r['sem']:6.3f} {r['separation_sigma']:6.2f} "
              f"{'PASS' if r['G_EXPRESS'] else 'FAIL':>4s} "
              f"{r['G_DENY_uplift']:+7.2f} {r['G_DENY_sem']:5.2f} "
              f"{r['G_DENY_z']:+5.2f} {'PASS' if r['G_DENY'] else 'FAIL':>5s} "
              f"{r['margin']:+8.2f} {r['margin_sem']:5.2f} "
              f"{'PASS' if r['G_COMPETITIVE_hard'] else 'FAIL':>5s} "
              f"{'YES' if r['VALID'] else 'NO':>6s} "
              f"{r['G_DAMAGE_pp']:+9.2f}")
    print("  (dmg_pp = G-DAMAGE, REPORTED ONLY since DESIGN §4.2; G-DENY gates)")
    print()
    for k, v in contrasts.items():
        print(f"{k}: n={v['n']} mean={v['mean']:+.2f} sem={v['sem']:.2f} "
              f"z={v['mean']/v['sem'] if v['sem'] else float('nan'):+.2f}")
    print()
    for r in rows:
        print(f"{r['arm']}: took_all {100*r['took_all_rate']:.1f}% "
              f"(CTRL {100*ctrl_took_all:.1f}%, owner 28.9%), "
              f"out-numbering {100*r['outnumbering_rate']:.1f}%, ")
        print(f"{r['arm']}: plan completion {r['plan_completion_rate']}, "
              f"census deliberate/onset {r['census_deliberate_over_onsets']:.3f}, "
              f"agent fires vs census {r['agent_fires_vs_census']}, "
              f"{r['worker_s_per_game_upper_bound']:.1f} worker-s/game (upper bound)")

    return rows, {"round": rnd, "ctrl_arm": CTRL,
                  "ctrl_took_all_rate": ctrl_took_all,
                  "ctrl_rate": ctrl_rate, "ctrl_sem": ctrl_sem,
                  "ctrl_deny_per_game": data[CTRL][2]["denied_per_game"],
                  "ctrl_farmer_zero_rate": ctrl_fz, "arms": rows,
                  "deck_matched_contrasts": contrasts}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--round", type=int, default=1,
                    choices=sorted(ROUNDS) + sorted(REPLICATION))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.root)

    if args.round in REPLICATION:
        ra, rb = REPLICATION[args.round]
        for r in (ra, rb):
            print(f"\n########## RANGE {r} ##########")
            _evaluate(root, r)
        return replication(root, ra, rb, args.out)

    _rows, blob = _evaluate(root, args.round)
    if args.out:
        Path(args.out).write_text(json.dumps(blob, indent=2, sort_keys=True))
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
