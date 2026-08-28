#!/usr/bin/env python3
"""C1 OUTCOME PRICING — the pre-registered readout. Run ONCE, at the very end.

Everything here is judge-free: every number is a difference of REALIZED final
scores of games played to termination, or an arithmetic transform of one.

The estimator, stated before any outcome exists (DESIGN.md §4):

  * a PLY's price is the unweighted mean of its landed CRN worlds'
    `delta_pts_mover` — pooled over the base block AND every completed
    elasticity block, because the extension worlds are pre-registered world
    INDEX RANGES and their landing is not outcome-dependent;
  * `delta_pts_mover` reads, mover-signed, as **C1 pick minus champion pick**
    (the arm-slot remap of READ_RULE.md §1, asserted here on every row);
  * a STRATUM's price is the unweighted mean over its plies with a
    CLUSTER-ROBUST SE clustered on GAME;
  * **P1 (PRIMARY) = `farm_capture`**; **P2 (CO-PRIMARY) = the contested cut,
    `invasion` U `farm_capture`**; Holm-Bonferroni over {P1, P2} at family
    alpha = 0.05, two-sided.

The estimator helpers are IMPORTED from `../e4_continuation_20260828/aggregate.py`
— the same `collapse_worlds` / `cluster_stats` / `contrast` that produced the
2026-08-28 continuation verdict, not a re-implementation.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONT = REPO / "measurement" / "e4_continuation_20260828"
sys.path.insert(0, str(CONT))

import aggregate as AGG                                       # noqa: E402

# --- pre-registered bars (DESIGN.md §5; asserted by selftest_c1.py) --------- #
ALPHA = 0.05
SE_PRECISION_BAR_P2 = 1.2      # pts; above this a null is UNRESOLVED, not bounded
VOID_WORLD_RATE = 0.10         # per co-primary stratum
CO_PRIMARIES = ("P1_farm_capture", "P2_contested")


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def two_sided_p(z):
    return None if z is None else 2.0 * (1.0 - _phi(abs(float(z))))


def holm(pvals: dict, alpha: float = ALPHA) -> dict:
    """Holm-Bonferroni over a small family. Returns {name: {p, thresh, reject}}."""
    items = sorted(((k, v) for k, v in pvals.items() if v is not None),
                   key=lambda kv: kv[1])
    m, out, still = len(items), {}, True
    for i, (k, p) in enumerate(items):
        thresh = alpha / (m - i)
        still = still and (p <= thresh)
        out[k] = {"p": p, "holm_threshold": thresh, "holm_reject": bool(still)}
    for k, v in pvals.items():
        out.setdefault(k, {"p": v, "holm_threshold": None, "holm_reject": False})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", nargs="+", required=True,
                    help="directories of unit_*.json (one per box)")
    ap.add_argument("--targets", default=str(HERE / "targets_c1.jsonl"))
    ap.add_argument("--microgates",
                    default=str(REPO / "measurement" / "microgates_20260828"
                               / "MICROGATES.json"))
    ap.add_argument("--exact-leg", default=str(HERE / "EXACT_LEG.json"))
    ap.add_argument("--preflight", default=str(HERE / "LEGAL_PREFLIGHT.json"))
    ap.add_argument("--out", default=str(HERE / "C1_PRICING.json"))
    args = ap.parse_args()

    rows, files = [], []
    for d in args.units:
        for f in sorted(Path(d).glob("unit_*.json")):
            files.append(str(f))
            rows.append(json.loads(f.read_text()))
    targets = {(t["game"], int(t["ply"])): t
               for t in (json.loads(l) for l in Path(args.targets).open())}

    # ---- instrument gates, before any statistic ---------------------------- #
    stray = {(r["game"], r["ply"]) for r in rows} - set(targets)
    if stray:
        raise SystemExit(f"units outside the frozen target set: {sorted(stray)[:5]}")
    armmap_bad = [(r["game"], r["ply"]) for r in rows
                  if int(r["played_action"]) != int(targets[(r["game"], r["ply"])]["c1_action"])
                  or int(r["counterfactual_action"]) != int(targets[(r["game"], r["ply"])]["champ_action"])]
    world_lo_bad = sorted({r["world"] for r in rows if int(r["world"]) < 16})

    plies = AGG.collapse_worlds(rows)
    for p in plies:                      # carry the frozen selection statistic
        t = targets[(p["game"], p["ply"])]
        p["insample_gap_pts"] = float(t["insample_gap_pts"])
        p["m_worlds_base"] = int(t["m_worlds_base"])
    priced = [p for p in plies if p["price"] is not None]
    by_s = collections.defaultdict(list)
    for p in priced:
        by_s[p["stratum"]].append(p)
    contested = by_s.get("invasion", []) + by_s.get("farm_capture", [])

    def world_rate(pool):
        ok = sum(p["m_worlds_ok"] for p in pool)
        void = sum(p["m_worlds_void"] for p in pool)
        return (void / (ok + void)) if (ok + void) else 0.0

    # ---- the two co-primaries --------------------------------------------- #
    P = {"P1_farm_capture": AGG.cluster_stats(by_s.get("farm_capture", [])),
         "P2_contested": AGG.cluster_stats(contested)}
    pvals = {k: two_sided_p(v.get("z")) for k, v in P.items()}
    hol = holm(pvals)
    for k in P:
        P[k].update(hol[k])
        P[k]["achieved_2sigma_MDE"] = (2 * P[k]["se"]) if P[k].get("se") else None

    # ---- secondaries ------------------------------------------------------- #
    strata_stats = {s: AGG.cluster_stats(v) for s, v in sorted(by_s.items())}
    allp = AGG.cluster_stats(priced)

    # Deployment ("policy-level") price: agreeing plies have a price of EXACTLY
    # zero (both arms are byte-identical), so the price of running C1 over a
    # WHOLE stratum is D_stratum * the divergent-conditional price. D is a fixed
    # constant of the frozen microgates set, not estimated here (DESIGN.md §4.3).
    mg = json.loads(Path(args.microgates).read_text())["G2"]
    D = {s: v["D_champ"] for s, v in mg["by_stratum"].items()}
    D["contested"] = mg["contested"]["D_champ"]
    D["all"] = mg["pooled"]["D_champ"]
    deployment = {}
    for name, st in list(strata_stats.items()) + [("contested", P["P2_contested"]),
                                                  ("all", allp)]:
        d = D.get(name)
        if d is None or st.get("mean") is None:
            continue
        deployment[name] = {
            "D_champ": d, "divergent_price": st["mean"],
            "policy_price_per_ply": d * st["mean"],
            "policy_se": d * st["se"] if st.get("se") else None}

    # ---- the winner's-curse cross-fit (the reason worlds >= 16 exist) ------- #
    # In-sample gap is the microgates' own argmax-minus-champion arm value on
    # the SAME 16 worlds the argmax was chosen on; the price here is the same
    # contrast on INDEPENDENT worlds. Their difference IS the winner's curse.
    def curse(pool):
        if not pool:
            return {"n": 0}
        shim = [{"game": p["game"], "price": p["insample_gap_pts"] - p["price"]}
                for p in pool]
        st = AGG.cluster_stats(shim)
        st["mean_insample_gap_pts"] = statistics.fmean(
            p["insample_gap_pts"] for p in pool)
        st["mean_out_of_sample_price_pts"] = statistics.fmean(
            p["price"] for p in pool)
        return st
    curse_out = {s: curse(v) for s, v in sorted(by_s.items())}
    curse_out["contested"] = curse(contested)
    curse_out["all"] = curse(priced)

    # ---- the pre-registered branch ----------------------------------------- #
    voids = {s: world_rate(by_s.get(s, [])) for s in ("farm_capture", "invasion")}
    instrument_void = []
    if armmap_bad:
        instrument_void.append("arm_map_violation")
    if world_lo_bad:
        instrument_void.append("world_index_below_16")
    for s, rate in voids.items():
        if rate > VOID_WORLD_RATE:
            instrument_void.append(f"void_worlds_{s}>{VOID_WORLD_RATE}")
    reasons = collections.Counter(r for p in plies for r in p["void_reasons"])
    for bad in ("crn_witness_mismatch", "root_state_diverged",
                "world_not_a_permutation", "deck_tail_mismatch",
                "world_prefix_mutated", "replay_desync"):
        if reasons.get(bad):
            instrument_void.append(f"guard:{bad}")

    def sig(k):
        return (P[k].get("z") is not None and abs(P[k]["z"]) >= 2.0
                and P[k]["holm_reject"])
    if instrument_void:
        branch = "C1-VOID"
    elif any(sig(k) and P[k]["mean"] > 0 for k in CO_PRIMARIES):
        branch = "C1-PRICED-POSITIVE"
    elif any(sig(k) and P[k]["mean"] < 0 for k in CO_PRIMARIES):
        branch = "C1-NEGATIVE"
    elif (P["P2_contested"].get("se") is not None
          and P["P2_contested"]["se"] <= SE_PRECISION_BAR_P2):
        branch = "C1-NULL-BOUNDED"
    else:
        branch = "C1-UNRESOLVED"

    exact = None
    if Path(args.exact_leg).exists():
        e = json.loads(Path(args.exact_leg).read_text())
        exact = {k: v for k, v in e.items() if k != "rows"}
    pref = None
    if Path(args.preflight).exists():
        pf = json.loads(Path(args.preflight).read_text())
        pref = {k: pf[k] for k in ("n_plies", "n_ok", "n_drop", "by_stratum",
                                   "drop_reasons", "VOID_TRIGGERED") if k in pf}

    out = {
        "schema": "carcassonne-c1-outcome-pricing/v1",
        "BRANCH": branch,
        "instrument_void_reasons": instrument_void,
        "arm_map": {"arm_owner": "c1_rollout_argmax",
                    "arm_cf": "production_champion_pick",
                    "delta_pts_mover": "C1 pick MINUS champion pick, mover-signed"},
        "coverage": {
            "n_unit_files": len(files), "n_units": len(rows),
            "n_target_plies": len(targets),
            "n_plies_with_units": len(plies), "n_plies_priced": len(priced),
            "n_plies_missing": sorted(set(targets)
                                      - {(p["game"], p["ply"]) for p in plies}),
            "worlds_ok": sum(p["m_worlds_ok"] for p in plies),
            "worlds_void": sum(p["m_worlds_void"] for p in plies),
            "void_reasons": dict(reasons),
            "world_index_histogram": dict(
                collections.Counter(int(r["world"]) for r in rows)),
            "achieved_m_worlds": dict(collections.Counter(
                p["m_worlds_ok"] for p in plies)),
            "arm_status": dict(collections.Counter(
                a.get("status") for r in rows
                for a in (r.get("arms") or {}).values())),
            "arm_map_violations": armmap_bad,
            "world_index_violations": world_lo_bad,
            "profiles": dict(collections.Counter(r["profile"] for r in rows)),
            "budget_notes": dict(collections.Counter(
                str(r.get("budget_note")) for r in rows)),
        },
        "PRIMARY": {k: P[k] for k in CO_PRIMARIES},
        "holm": {"family": list(CO_PRIMARIES), "alpha": ALPHA,
                 "se_precision_bar_P2": SE_PRECISION_BAR_P2},
        "secondary": {
            "by_stratum": strata_stats,
            "all_divergent_plies": allp,
            "farm_capture_minus_control": AGG.contrast(
                by_s.get("farm_capture", []), by_s.get("control", [])),
            "contested_minus_uncontested": AGG.contrast(
                contested, by_s.get("defense", []) + by_s.get("control", [])),
        },
        "deployment_policy_price": deployment,
        "winners_curse": curse_out,
        "exact_leg_bonus_DIFFERENT_ESTIMAND": exact,
        "preflight": pref,
        "plies": sorted(priced, key=lambda p: (p["stratum"], p["game"], p["ply"])),
        "caveat": "Every price is a difference of REALIZED final scores over "
                  "CRN-paired continuations under production-champion play by "
                  "BOTH seats. No judge, no evaluation function, no search "
                  "score. It prices the TARGET PLY ONLY: every later move, "
                  "including the meeple follow-up, is the champion's. The "
                  "`arm_owner` slot holds the C1 pick, NOT an owner move.",
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "plies"}, indent=1))


if __name__ == "__main__":
    main()
