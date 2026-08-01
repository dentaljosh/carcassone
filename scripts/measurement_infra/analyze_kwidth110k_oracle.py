#!/usr/bin/env python3
"""READ-OUT for the "champ vs 10x champ" SCREEN (11008 vs 110080) — PRE-REGISTERED §6.

Written and committed BEFORE any score exists, so no estimator and no verdict threshold is
chosen after seeing numbers. Prereg:
measurement/classical_search/KWIDTH_110K_PREREG_20260801.md.

Recomputes everything from the ON-DISK per-position records, not from the harness's
`summary.json` — whose z is NAIVE and must not be cited. Records are (root, salt) cells with
up to 3 salts per root, so they are NOT independent and every statistic clusters on
`root_id`. The estimators themselves are IMPORTED from `analyze_kwidth_oracle` (the
2026-07-29 read-out pass) rather than re-implemented, so the two rungs are computed by
literally the same code.

Sign convention: positive = the 110080 (k80x1376, 10x) pick scores better.

THE DELIVERABLE IS A FUNDING RECOMMENDATION, so the headline statistic is not the
per-disagreement mean but the COMPOUND it implies:

    pts/move = D_hat x mean_delta        (budget must BOTH change the move AND improve it)
    elo      = pts/move -> pts/game -> wr -> elo, the same chain the 22016 read-out used
               (x71.5 decisions, /3.2 non-additivity, sigma_game 22.2, luck floor)

    analyze_kwidth110k_oracle.py [--score-dir DIR] [--picks-dir DIR] [--bootstrap 20000]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_kwidth_oracle import (            # noqa: E402  — SAME estimators, not a copy
    _mean,
    _var,
    bootstrap_roots,
    cluster_robust,
    root_collapsed,
    sign_test,
    trimmed_mean,
)

# --- the two rungs BELOW this one, on the IDENTICAL instrument (M=32, oracle-sims 100) ---
RUNG_4X = {"name": "2752 -> 11008 (oracle pilot, n=100)", "D": 0.2398, "mean": 0.7375}
RUNG_2X = {"name": "11008 -> 22016 (kwidth, n=237)", "D": 0.1244, "mean": 0.1054}

# --- the pts -> elo chain, verbatim from KWIDTH_22016_READOUT §3 -------------------------
DECISIONS_PER_GAME = 71.5      # champion decisions in a 2p base+farmers game
NON_ADDITIVITY = 3.2           # measured on the rung below: swapping one decision per game
SIGMA_GAME = 22.2              # sd of the game margin, measurement/human_anchor/LUCK_FLOOR.md
NORMAL_PDF0 = 0.3989422804014327

# --- THE PRE-REGISTERED FUNDING BAR -----------------------------------------------------
# The screen exists to answer "should we fund a champ-vs-10x head-to-head?". A h2h can only
# CONFIRM an effect it can resolve: CLAUDE.md's own n-thresholds put a deck-PAIRED n=400 at
# ~+/-12 elo (1 sigma), so ~+25 elo is the smallest effect such a run could land at 2 sigma.
# Below that bar the h2h is unaffordable-to-resolve and the answer is "do not fund".
ELO_BAR = 25.0


def pts_per_move_to_elo(pts_per_move: float) -> float:
    """pts/move -> elo, the chain the 22016 read-out used. Reported as an ORDER-OF-MAGNITUDE
    CONSISTENCY FIGURE, never as a measurement: swapping one decision per game does not sum
    linearly (the 3.2x divisor is itself measured only on the rung below)."""
    pts_game = pts_per_move * DECISIONS_PER_GAME / NON_ADDITIVITY
    wr = 0.5 + (pts_game / SIGMA_GAME) * NORMAL_PDF0
    wr = min(max(wr, 1e-6), 1 - 1e-6)
    return 400.0 * math.log10(wr / (1.0 - wr))


def verdict(mean, se_cr, d_hat, col_mean):
    """The PRE-REGISTERED verdict map. Mechanical — no judgement at read time.

    Returns (branch, recommendation, reachability_note)."""
    z = mean / se_cr if se_cr and se_cr == se_cr else float("nan")
    hi95 = mean + 1.96 * se_cr
    elo_hi = pts_per_move_to_elo(d_hat * hi95)
    # what point estimate would each branch have required, at the REALIZED se and D_hat?
    # (the 22016 read-out's §4 self-criticism, promoted to a MANDATORY pre-registered field)
    mean_at_bar = None
    for cand in [x / 10000.0 for x in range(-20000, 20001)]:
        if pts_per_move_to_elo(d_hat * (cand + 1.96 * se_cr)) < ELO_BAR:
            mean_at_bar = cand
    reach = (f"the NOT-DETECTED branch required a point estimate <= "
             f"{mean_at_bar:+.4f} pts at the realized se {se_cr:.4f} and D_hat {d_hat:.4f}; "
             f"the DETECTED branch required >= {2 * se_cr:+.4f}")
    if z <= -2:
        return ("THE 10x PICK IS WORSE",
                "k80 would be PAST the PIMC width optimum at 110080 — i.e. the 10x budget "
                "is mis-allocated, not valueless. Report as-is; do NOT rescue it, and do "
                "NOT fund a h2h at this allocation.", reach)
    if z >= 2 and col_mean > 0:
        return ("DETECTED — the 10x pick is genuinely better",
                "FUND the confirm: size the deck-paired h2h from the elo-equivalent below. "
                "UNDERSTANDING first — CL-068 stands, 110080 is 10x an already "
                "clock-unusable budget, so this can never be a deploy lever.", reach)
    if elo_hi < ELO_BAR:
        return (f"NOT DETECTED — a fundable effect (>= {ELO_BAR:.0f} elo) is EXCLUDED",
                "Do NOT fund the champ-vs-10x h2h: its predicted result is null and it "
                "could not resolve what is left. Port speedup goes to science throughput. "
                "⚠️ 'NOT DETECTED', never 'nothing above 11008' — the weak judge and the "
                "untested k80 allocation BOTH bias toward zero.", reach)
    return ("UNDERPOWERED / INCONCLUSIVE at this n",
            "Report the interval and do NOT promote a direction. Default recommendation is "
            "still DO NOT FUND (a screen that cannot exclude the bar cannot justify the "
            "spend), but state explicitly what the screen failed to exclude.", reach)


def cross_run_arm_a_check(rows_110k, ref_picks_dir):
    """FREE VALIDITY CHECK: the 2026-07-29 22016 run used the SAME bank, the SAME
    `order_seed`, the SAME pool and the SAME arm-A construction (k8x1376, world-0..7 prefix,
    agent seed from `root_seed(deck_seed, ply, salt)`). Arm A's pick is therefore a function
    of the cell alone — it CANNOT depend on how many worlds arm B ran. So every cell present
    in both runs must report the SAME 11008 pick. Any mismatch means the prefix identity (or
    the champion config) moved between the runs and the comparison across rungs is void."""
    ref = Path(ref_picks_dir) / "records"
    if not ref.exists():
        return None
    have = {r["rid"]: r for r in rows_110k if r.get("ok")}
    shared = agree = 0
    bad = []
    for p in ref.glob("*.json"):
        try:
            d = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not d.get("ok") or d["rid"] not in have:
            continue
        a_ref = (d.get("q_pick_by_level") or {}).get("11008")
        a_new = (have[d["rid"]].get("q_pick_by_level") or {}).get("11008")
        if a_ref is None or a_new is None:
            continue
        shared += 1
        if int(a_ref) == int(a_new):
            agree += 1
        elif len(bad) < 5:
            bad.append((d["rid"], a_ref, a_new))
    return shared, agree, bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--score-dir", default="/mnt/c/carc-shared/oracle_110k_20260801/score")
    ap.add_argument("--picks-dir", default="/mnt/c/carc-shared/oracle_110k_20260801/picks")
    ap.add_argument("--ref-picks-dir",
                    default="/mnt/c/carc-shared/oracle_22016_20260729/picks",
                    help="the 22016 run, for the arm-A cross-run identity check")
    ap.add_argument("--bootstrap", type=int, default=20000)
    ap.add_argument("--boot-seed", type=int, default=20260801)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    out: dict = {"prereg": "measurement/classical_search/KWIDTH_110K_PREREG_20260801.md",
                 "elo_bar": ELO_BAR}

    # ---- pick phase: the disagreement rate, a finding in its own right ----------
    pd = Path(args.picks_dir) / "records"
    picks = [json.loads(p.read_text()) for p in pd.glob("*.json")] if pd.exists() else []
    ok = [r for r in picks if r.get("ok")]
    dis = [r for r in ok if r.get("disagree")]
    print("=" * 78)
    print("PICK PHASE — does the champion's pick still CHANGE at 10x its budget?")
    print("  arms: A = k8x1376 = 11008 (champion)   B = k80x1376 = 110080 (10x, width)")
    print("=" * 78)
    d_hat = float("nan")
    if ok:
        d_hat = len(dis) / len(ok)
        se_d = math.sqrt(d_hat * (1 - d_hat) / len(ok))
        nver = sum(1 for r in ok if r.get("agent_parity_verified"))
        print(f"  cells ok                    : {len(ok)}  (failed {len(picks) - len(ok)})")
        print(f"  distinct roots              : {len({r['root_id'] for r in ok})}")
        print(f"  DISAGREEMENTS               : {len(dis)}"
              f"  (roots {len({r['root_id'] for r in dis})})")
        print(f"  D_hat(11008, 110080)        : {d_hat:.4f} +/- {se_d:.4f}")
        print(f"  D_paired(2752, 11008)  CL-070 : {RUNG_4X['D']:.4f}   (4x rung)")
        print(f"  D_hat(11008, 22016)  kwidth   : {RUNG_2X['D']:.4f}   (2x rung)")
        print(f"  AGENT-PARITY VERIFIED       : {nver} cells "
              f"{'OK' if nver else '*** NONE — the prefix trick is UNPROVEN on this run ***'}")
        out.update(n_cells_ok=len(ok), n_failed=len(picks) - len(ok),
                   n_disagreements=len(dis), d_hat=d_hat, se_d_hat=se_d,
                   n_parity_verified=nver,
                   n_roots=len({r['root_id'] for r in ok}))
        x = cross_run_arm_a_check(picks, args.ref_picks_dir)
        if x:
            shared, agree, bad = x
            flag = "OK" if shared and agree == shared else "*** MISMATCH — see prereg §8 ***"
            print(f"  ARM-A CROSS-RUN IDENTITY    : {agree}/{shared} vs the 22016 run {flag}")
            if bad:
                print(f"    first mismatches: {bad}")
            out.update(arm_a_shared=shared, arm_a_agree=agree)
    else:
        print("  (no pick records yet)")

    # ---- score phase: the pre-registered estimators -----------------------------
    sd_dir = Path(args.score_dir) / "records"
    rows = [json.loads(p.read_text()) for p in sd_dir.glob("*.json")] if sd_dir.exists() else []
    rows = [r for r in rows if r.get("ok") and isinstance(r.get("delta"), (int, float))]
    print()
    print("=" * 78)
    print("SCORE PHASE — where they disagree, is the 110080 pick BETTER?")
    print("  sign convention: POSITIVE = the 110080 (10x) pick scores better")
    print("=" * 78)
    if len(rows) < 2:
        print(f"  only {len(rows)} scored positions — nothing to read yet.")
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(out, indent=2))
        return 0

    crn_all = all(r.get("crn_verified") for r in rows)
    n_ident = sum(1 for r in rows if r.get("distinct_afterstates") == 0)
    print(f"  scored positions            : {len(rows)}")
    print(f"  crn_verified_all            : {crn_all}"
          f"{'' if crn_all else '   *** VOID: arms not paired (prereg §8) ***'}")
    print(f"  identical afterstates       : {n_ident}"
          f"{'' if not n_ident else '   (zero deltas there are IDENTITIES, not evidence)'}")

    mean, se_cr, n, g = cluster_robust(rows)
    deltas = [r["delta"] for r in rows]
    sd_pos = math.sqrt(_var(deltas))
    se_naive = sd_pos / math.sqrt(n)
    col_m, col_se, n_roots = root_collapsed(rows)
    lo95, hi95 = mean - 1.96 * se_cr, mean + 1.96 * se_cr

    print()
    print(f"  {'estimator':<46}{'mean':>9}{'se':>9}{'z':>8}")
    print(f"  {'-' * 72}")
    print(f"  {'naive (record-level, i.i.d. — NOT CITED)':<46}"
          f"{mean:>9.4f}{se_naive:>9.4f}{mean / se_naive:>8.2f}")
    print(f"  {'** CLUSTER-ROBUST on root (THE CITED ROW) **':<46}"
          f"{mean:>9.4f}{se_cr:>9.4f}{mean / se_cr:>8.2f}")
    print(f"  {'root-collapsed (conservative)':<46}"
          f"{col_m:>9.4f}{col_se:>9.4f}{(col_m / col_se if col_se else float('nan')):>8.2f}")
    print(f"  design effect (CR/naive var)  : {(se_cr / se_naive) ** 2:.3f}")
    print(f"  clusters G / records n        : {g} / {n}")
    print(f"  95% CI (cluster-robust)       : [{lo95:+.4f}, {hi95:+.4f}]")
    print(f"  per-position sd               : {sd_pos:.4f}")

    (bm, blo, bhi, bp), (cm, clo, chi, cp) = bootstrap_roots(
        rows, args.bootstrap, args.boot_seed)
    print()
    print(f"  bootstrap OF ROOTS ({args.bootstrap} resamples, seed {args.boot_seed}):")
    print(f"    record-level   mean {bm:+.4f}  95% CI [{blo:+.4f}, {bhi:+.4f}]  P(<=0) {bp:.4f}")
    print(f"    root-collapsed mean {cm:+.4f}  95% CI [{clo:+.4f}, {chi:+.4f}]  P(<=0) {cp:.4f}")

    rp, rn, rz, rpv = sign_test(deltas)
    by_root = defaultdict(list)
    for r in rows:
        by_root[r["root_id"]].append(r["delta"])
    gp, gn, gz, gpv = sign_test([_mean(v) for v in by_root.values()])
    print()
    print(f"  sign test  records : {rp}+ / {rn}- / {rz}=0   one-sided binomial p {rpv:.4f}")
    print(f"  sign test  roots   : {gp}+ / {gn}- / {gz}=0   one-sided binomial p {gpv:.4f}")
    print(f"  robustness  sd {sd_pos:.4f}   median {sorted(deltas)[len(deltas) // 2]:+.4f}"
          f"   10%-trimmed {trimmed_mean(deltas):+.4f}"
          f"   range [{min(deltas):+.3f}, {max(deltas):+.3f}]")

    # ---- THE LADDER + THE COMPOUND ---------------------------------------------
    print()
    print("  THE LADDER — three rungs, ONE instrument (M=32, oracle-sims 100):")
    print(f"    {'rung':<34}{'D':>9}{'mean':>10}{'pts/move':>11}{'~elo':>8}")
    for r in (RUNG_4X, RUNG_2X,
              {"name": f"11008 -> 110080 (THIS RUN, n={n})", "D": d_hat, "mean": mean}):
        ppm = r["D"] * r["mean"]
        print(f"    {r['name']:<34}{r['D']:>9.4f}{r['mean']:>10.4f}{ppm:>11.4f}"
              f"{pts_per_move_to_elo(ppm):>8.1f}")

    ppm = d_hat * mean
    ppm_lo, ppm_hi = d_hat * lo95, d_hat * hi95
    e, e_lo, e_hi = (pts_per_move_to_elo(ppm), pts_per_move_to_elo(ppm_lo),
                     pts_per_move_to_elo(ppm_hi))
    print()
    print("  THE FUNDING NUMBER — expected value of the 10x budget PER MOVE, and in elo:")
    print(f"    pts/move  {ppm:+.5f}   95% CI [{ppm_lo:+.5f}, {ppm_hi:+.5f}]")
    print(f"    ~elo      {e:+.2f}      95% CI [{e_lo:+.2f}, {e_hi:+.2f}]"
          f"      (funding bar {ELO_BAR:.0f} elo)")
    print("    ⚠️ ORDER-OF-MAGNITUDE CONSISTENCY FIGURE, NOT A MEASUREMENT — one swapped")
    print("       decision per game does not sum linearly (3.2x non-additivity divisor).")
    out.update(mean_delta=mean, se_cluster_robust=se_cr, z_cluster_robust=mean / se_cr,
               ci95=[lo95, hi95], sd_positions=sd_pos, n_scored=n, n_clusters=g,
               root_collapsed_mean=col_m, root_collapsed_se=col_se,
               design_effect=(se_cr / se_naive) ** 2, crn_verified_all=crn_all,
               boot_record=[bm, blo, bhi, bp], boot_collapsed=[cm, clo, chi, cp],
               sign_records=[rp, rn, rz, rpv], sign_roots=[gp, gn, gz, gpv],
               pts_per_move=ppm, pts_per_move_ci=[ppm_lo, ppm_hi],
               elo_equiv=e, elo_equiv_ci=[e_lo, e_hi])

    v, why, reach = verdict(mean, se_cr, d_hat, col_m)
    print()
    print("  " + "=" * 74)
    print(f"  PRE-REGISTERED VERDICT: {v}")
    print(f"    {why}")
    print(f"    REACHABILITY (mandatory, prereg §6): {reach}")
    print("  " + "=" * 74)
    print("  Strata are DESCRIPTIVE ONLY and are not printed as findings. No CL id, no")
    print("  results.csv row, PRODUCTION.yaml untouched — pre-committed in the prereg.")
    out.update(verdict=v, recommendation=why, reachability=reach)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2))
        print(f"\n  json -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
