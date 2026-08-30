#!/usr/bin/env python3
"""CENSUS 1 (GT-M1) + CENSUS 3 (SA-M1) read-out. PREREG bars applied verbatim.

Reads the `C13_<profile>.jsonl` rows from `census13_rootstats.py`, emits
`CENSUS1.json` and `CENSUS3.json`.

CENSUS 1 statistics (PREREG):
  per-world argmax a_i (per-world Q = W_i/N_i, N_i >= min_pooled_visits, tie key
  (q, N, -a) -- the same key `pooled_q_argmax` uses); pooled argmax a*;
  agree_frac = |{i: a_i == a*}| / k; unanimous; CVaR_alpha over CVaR-ELIGIBLE
  actions (N_i >= min_pooled_visits in ALL k worlds), lower tail, alpha grid
  {0.25, 0.50, 0.75, 1.00}; reach(alpha) = CVaR argmax != a*.
  alpha = 1.00 is the arithmetic identity CONTROL, not a finding.

CENSUS 3 statistics (PREREG):
  EXISTS = >=1 legal action tagged onset|extend; N_seed = max pooled visits over
  tagged actions; m = 110 = 1% of the 11008 deploy budget.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

ALPHAS = (0.25, 0.50, 0.75, 1.00)
M_VISITS = 110
CONTEST_STRATA = ("invasion", "defense", "farm_capture")
BOOT_REPS = 2000
BOOT_SEED = 20260830


def per_world_argmax(stats, minpv):
    """(argmax action, {action: q}) for ONE world -- the deployed tie key."""
    q = {}
    for a, n, w in stats:
        if n > 0:
            q[int(a)] = (w / n, n)
    elig = [a for a, (_qq, n) in q.items() if n >= minpv] or list(q)
    if not elig:
        return None, {}
    best = max(elig, key=lambda a: (q[a][0], q[a][1], -a))
    return best, {a: v[0] for a, v in q.items()}


def cvar(vals, alpha):
    """Mean of the ceil(alpha*k) SMALLEST values (lower tail)."""
    s = sorted(vals)
    j = max(1, math.ceil(alpha * len(s)))
    return sum(s[:j]) / j


def census1_row(r):
    k = int(r["k_dets"])
    minpv = int(r["min_pooled_visits"])
    star = int(r["pooled_argmax"])
    worlds = r["world_stats"]

    picks, qmaps, nmaps = [], [], []
    for stats in worlds:
        p, qm = per_world_argmax(stats, minpv)
        picks.append(p)
        qmaps.append(qm)
        nmaps.append({int(a): n for a, n, _w in stats})

    agree = sum(1 for p in picks if p is not None and p == star)
    # CVaR-eligible: N_i >= minpv in EVERY world
    elig = [a for a in qmaps[0]
            if all(nm.get(a, 0) >= minpv for nm in nmaps)
            and all(a in qm for qm in qmaps)]
    reach, cv_pick = {}, {}
    for al in ALPHAS:
        if not elig:
            reach[str(al)] = None
            cv_pick[str(al)] = None
            continue
        scores = {a: cvar([qm[a] for qm in qmaps], al) for a in elig}
        pick = max(elig, key=lambda a: (scores[a],
                                        sum(nm.get(a, 0) for nm in nmaps), -a))
        cv_pick[str(al)] = int(pick)
        reach[str(al)] = bool(pick != star)
    # DISCLOSED (see DEVIATIONS.md D-1): alpha=1.00 is the EQUAL-WEIGHT-WORLDS mean of
    # per-world Q, which is NOT the deployed pooled Q = sum(W)/sum(N) whenever visit
    # counts differ across worlds. So it is not an identity control. `reach_vs_eqw`
    # isolates the marginal effect of RISK AVERSION on top of equal weighting.
    eqw = cv_pick.get("1.0")
    reach_vs_eqw = {str(al): (None if (cv_pick.get(str(al)) is None or eqw is None)
                              else bool(cv_pick[str(al)] != eqw))
                    for al in ALPHAS}
    return {
        "agree_frac": agree / k, "n_agree": agree, "k": k,
        "unanimous": bool(agree == k),
        "n_distinct_world_picks": len({p for p in picks if p is not None}),
        "n_cvar_eligible": len(elig), "cvar_pick": cv_pick, "reach": reach,
        "reach_vs_eqw": reach_vs_eqw,
        "star_is_cvar_eligible": bool(star in elig),
    }


def census3_row(r):
    seeds = sorted(set(r.get("seeds_onset") or []) | set(r.get("seeds_extend") or []))
    onset = sorted(set(r.get("seeds_onset") or []))
    pooled = {int(a): float(n) for a, n in (r.get("pooled_n") or {}).items()}
    tot = sum(pooled.values()) or 1.0
    order = sorted(pooled, key=lambda a: -pooled[a])
    rank = {a: i + 1 for i, a in enumerate(order)}

    def blk(tagged):
        vis = [(pooled.get(a, 0.0), a) for a in tagged]
        if not tagged:
            return {"exists": False, "n_tagged": 0, "n_seed": None,
                    "rank": None, "share": None, "well_visited": None}
        n_seed, best = max(vis)
        return {"exists": True, "n_tagged": len(tagged), "n_seed": n_seed,
                "rank": rank.get(best), "share": n_seed / tot,
                "well_visited": bool(n_seed >= M_VISITS)}
    return {"primary": blk(seeds), "onset_only": blk(onset),
            "n_legal": r.get("n_legal"), "sum_pooled_n": tot}


def boot_ci(rows, fn, seed=BOOT_SEED, reps=BOOT_REPS):
    """Game-cluster percentile bootstrap of a rate."""
    by = defaultdict(list)
    for r in rows:
        by[r["game"]].append(r)
    gids = sorted(by)
    if not gids:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        flat = [x for _ in range(len(gids))
                for x in by[gids[rng.randrange(len(gids))]]]
        v = fn(flat)
        if v is not None:
            out.append(v)
    out.sort()
    return [out[int(0.025 * len(out))], out[int(0.975 * len(out))]] if out else None


def rate(rows, pred):
    ok = [r for r in rows if pred(r) is not None]
    return (sum(bool(pred(r)) for r in ok) / len(ok)) if ok else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--primary-profile", default="fixed_v1")
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    raw = []
    for p in a.inputs:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                raw.append(json.loads(line))

    faults = {
        "n_rows": len(raw),
        "n_not_ok": sum(1 for r in raw if not r.get("ok")),
        "errors": dict(Counter(r.get("error") for r in raw if not r.get("ok"))),
        "n_exact_region": sum(1 for r in raw if r.get("ok") and r.get("exact_region")),
    }
    ok = [r for r in raw if r.get("ok") and not r.get("exact_region")]

    # ---- annotate ---------------------------------------------------------- #
    for r in ok:
        r["_c1"] = census1_row(r)
        r["_c3"] = census3_row(r)

    # DISCLOSED, NOT A VOID (DEVIATIONS.md D-1): the PREREG called alpha=1.00 an
    # arithmetic identity control. It is not one -- equal-weight world mean != the
    # deployed visit-weighted pooled Q. Counted and reported, never used to void.
    faults["prereg_alpha1_control_disagreements"] = sum(
        1 for r in ok if r["_c1"]["reach"].get("1.0") is True
        and r["_c1"]["star_is_cvar_eligible"])
    faults["alpha1_control_note"] = (
        "NOT a void trigger -- the PREREG's identity premise was arithmetically "
        "wrong (see DEVIATIONS D-1); reported as the equal-weight pooling reach.")

    def select(profile, salt, strata=None):
        return [r for r in ok if r["profile"] == profile and r["salt"] == salt
                and (strata is None or r["stratum"] in strata)]

    P = a.primary_profile

    # ======================= CENSUS 1 ======================================= #
    def c1_block(rows):
        if not rows:
            return {"n": 0}
        b = {"n": len(rows),
             "U_unanimous": rate(rows, lambda r: r["_c1"]["unanimous"]),
             "dissent_rate": rate(rows, lambda r: not r["_c1"]["unanimous"]),
             "mean_agree_frac": sum(r["_c1"]["agree_frac"] for r in rows) / len(rows),
             "mean_distinct_world_picks": sum(r["_c1"]["n_distinct_world_picks"]
                                              for r in rows) / len(rows),
             "mean_cvar_eligible": sum(r["_c1"]["n_cvar_eligible"]
                                       for r in rows) / len(rows),
             "agree_frac_hist": dict(sorted(Counter(
                 round(r["_c1"]["agree_frac"], 3) for r in rows).items())),
             "P_star_cvar_eligible": rate(
                 rows, lambda r: r["_c1"]["star_is_cvar_eligible"]),
             "reach": {}, "reach_vs_equalweight": {}, "reach_star_eligible_only": {}}
        elig_rows = [r for r in rows if r["_c1"]["star_is_cvar_eligible"]]
        for al in ALPHAS:
            k = str(al)
            b["reach"][k] = rate(rows, lambda r, k=k: r["_c1"]["reach"].get(k))
            b["reach_vs_equalweight"][k] = rate(
                rows, lambda r, k=k: r["_c1"]["reach_vs_eqw"].get(k))
            b["reach_star_eligible_only"][k] = rate(
                elig_rows, lambda r, k=k: r["_c1"]["reach"].get(k))
        b["n_star_cvar_eligible"] = len(elig_rows)
        b["U_ci95"] = boot_ci(rows, lambda rr: rate(rr, lambda r: r["_c1"]["unanimous"]))
        b["max_reach_excl_control"] = max(
            (v for k, v in b["reach"].items() if k != "1.0" and v is not None),
            default=None)
        b["max_reach_ci95"] = boot_ci(
            rows, lambda rr: max((rate(rr, lambda r, k=k: r["_c1"]["reach"].get(k))
                                  or 0.0) for k in ("0.25", "0.5", "0.75")))
        return b

    contest = select(P, 0, CONTEST_STRATA)
    c1 = {
        "schema": "carcassonne-cl083-census1-readout/v1",
        "prereg": "measurement/cl083_mech_censuses_20260830/PREREG.md",
        "judge_free": True, "alphas": list(ALPHAS),
        "instrument_faults": faults,
        "PRIMARY_contest_exposed": c1_block(contest),
        "COMPANION_control_stratum": c1_block(select(P, 0, ("control",))),
        "by_stratum": {s: c1_block(select(P, 0, (s,)))
                       for s in ("invasion", "defense", "farm_capture", "control")},
        "STABILITY_salt1_contest_exposed": c1_block(select(P, 1, CONTEST_STRATA)),
        "OTHER_PROFILE_LEG": {
            pr: c1_block([r for r in ok if r["profile"] == pr and r["salt"] == 0
                          and r["stratum"] in CONTEST_STRATA])
            for pr in sorted({r["profile"] for r in ok} - {P})},
    }
    mr = c1["PRIMARY_contest_exposed"].get("max_reach_excl_control")
    U = c1["PRIMARY_contest_exposed"].get("U_unanimous")
    if mr is None:
        v = "VOID (no contest-exposed plies)"
    elif mr <= 0.10:
        v = f"GT-M1 KILLED (max reach {mr:.3f} <= 0.10)"
    elif mr >= 0.30:
        v = f"GT-M1 NOT KILLED (max reach {mr:.3f} >= 0.30)"
    elif U is not None and U >= 0.80:
        v = (f"GT-M1 DEAD-ON-CEILING (reach {mr:.3f} AMBER but U {U:.3f} >= 0.80 "
             f"caps every world-monotone rule below 1-U)")
    else:
        v = f"GT-M1 AMBER / NOT KILLED (max reach {mr:.3f} in (0.10, 0.30))"
    c1["VERDICT"] = v
    c1["already_agree_label"] = ("TRUE (U >= 0.80)" if (U or 0) >= 0.80
                                else "FALSE (U <= 0.50)" if (U or 1) <= 0.50
                                else "UNLABELLED (0.50 < U < 0.80)")

    # ======================= CENSUS 3 ======================================= #
    def c3_block(rows, tag="primary"):
        if not rows:
            return {"n": 0}
        ex = [r for r in rows if r["_c3"][tag]["exists"]]
        wv = [r for r in ex if r["_c3"][tag]["well_visited"]]
        compound = [r for r in rows if r["_c3"][tag]["exists"]
                    and not r["_c3"][tag]["well_visited"]]
        ns = sorted(r["_c3"][tag]["n_seed"] for r in ex)
        return {
            "n": len(rows), "n_exists": len(ex),
            "P_exists": len(ex) / len(rows),
            "P_exists_ci95": boot_ci(
                rows, lambda rr, t=tag: (
                    sum(r["_c3"][t]["exists"] for r in rr) / len(rr)) if rr else None),
            "P_wellvisited_given_exists": (len(wv) / len(ex)) if ex else None,
            "P_wv_ci95": boot_ci(
                ex, lambda rr, t=tag: (
                    sum(r["_c3"][t]["well_visited"] for r in rr) / len(rr))
                if rr else None),
            "compound_reachable_share": len(compound) / len(rows),
            "compound_ci95": boot_ci(
                rows, lambda rr, t=tag: (
                    sum(r["_c3"][t]["exists"] and not r["_c3"][t]["well_visited"]
                        for r in rr) / len(rr)) if rr else None),
            "n_seed_quartiles": ([ns[0], ns[len(ns) // 4], ns[len(ns) // 2],
                                  ns[3 * len(ns) // 4], ns[-1]] if ns else None),
            "median_rank_of_best_seed": (
                sorted(r["_c3"][tag]["rank"] for r in ex)[len(ex) // 2] if ex else None),
            "mean_budget_share_of_best_seed": (
                sum(r["_c3"][tag]["share"] for r in ex) / len(ex)) if ex else None,
            "mean_n_tagged": sum(r["_c3"][tag]["n_tagged"] for r in rows) / len(rows),
            "mean_n_legal": sum((r["_c3"]["n_legal"] or 0) for r in rows) / len(rows),
        }

    allp = select(P, 0)
    c3 = {
        "schema": "carcassonne-cl083-census3-readout/v1",
        "prereg": "measurement/cl083_mech_censuses_20260830/PREREG.md",
        "judge_free": True, "m_visits": M_VISITS,
        "m_as_budget_share": M_VISITS / 11008,
        "instrument_faults": faults,
        "PRIMARY_all_crux_plies": c3_block(allp),
        "ONSET_ONLY": c3_block(allp, "onset_only"),
        "by_stratum": {s: c3_block(select(P, 0, (s,)))
                       for s in ("invasion", "defense", "farm_capture", "control")},
        "by_phase": {ph: c3_block([r for r in allp if r["phase"] == ph])
                     for ph in sorted({r["phase"] for r in allp})},
        "by_actor": {str(ac): c3_block([r for r in allp if r["actor"] == ac])
                     for ac in sorted({r["actor"] for r in allp})},
        "STABILITY_salt1": c3_block(select(P, 1)),
        "OTHER_PROFILE_LEG": {
            pr: c3_block([r for r in ok if r["profile"] == pr and r["salt"] == 0])
            for pr in sorted({r["profile"] for r in ok} - {P})},
    }
    b = c3["PRIMARY_all_crux_plies"]
    fired = []
    if b["P_exists"] < 0.50:
        fired.append(f"BRANCH A (P_exists {b['P_exists']:.3f} < 0.50)")
    if (b["P_wellvisited_given_exists"] or 0) >= 0.80:
        fired.append(f"BRANCH B (P_wv|exists {b['P_wellvisited_given_exists']:.3f} "
                     f">= 0.80)")
    if b["compound_reachable_share"] <= 0.20:
        fired.append(f"COMPOUND (reachable share {b['compound_reachable_share']:.3f} "
                     f"<= 0.20)")
    c3["VERDICT"] = ("SA-M1 KILLED -- " + "; ".join(fired) if fired
                     else "SA-M1 NOT KILLED (no branch fired)")

    od = Path(a.outdir)
    (od / "CENSUS1.json").write_text(json.dumps(c1, indent=1))
    (od / "CENSUS3.json").write_text(json.dumps(c3, indent=1))
    print(json.dumps({"census1": c1["VERDICT"], "already_agree": c1["already_agree_label"],
                      "U": U, "reach": c1["PRIMARY_contest_exposed"]["reach"],
                      "census3": c3["VERDICT"],
                      "P_exists": b["P_exists"],
                      "P_wv": b["P_wellvisited_given_exists"],
                      "compound": b["compound_reachable_share"],
                      "faults": faults}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
