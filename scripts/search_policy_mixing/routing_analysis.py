#!/usr/bin/env python3
"""Phase 4 — routing-rule analysis (pure offline, no game playing).

The hybrid routes each decision to either iter8 (cheap neural) or a deep heuristic.
At the ROOT level we measure teacher-imitation (agreement with heur@3200). KEY HONEST
CAVEAT (stated in the report): root teacher-imitation ranks heur>iter8 everywhere,
but FULL-GAME strength ranks iter8>heur@800 (the champion validation) — so a router
CANNOT be decided on root-imitation alone. What this script CAN decide:

  (1) Does any cheap signal SEPARATE iter8's root-error (P[iter8 != teacher]) better
      than k_remaining/band already does?  -> is there headroom for a dynamic rule?
  (2) For a router that uses heur@800 when a signal crosses a threshold (else iter8),
      what teacher-agreement + coverage results, swept over thresholds, vs fixed-K?

Reads the joined audit+labels+sample; writes ROUTING_RULE_ANALYSIS.csv + stdout tables.
"""
from __future__ import annotations
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SPM = os.path.join(REPO, "measurement", "search_policy_mixing")
MID = os.path.join(REPO, "measurement", "midgame_reference")
TEACHER = "heur3200_choice"


def load():
    aud = {json.loads(l)["position_id"]: json.loads(l) for l in open(os.path.join(SPM, "ROOT_ACTION_AUDIT.jsonl"))}
    lab = {json.loads(l)["position_id"]: json.loads(l) for l in open(os.path.join(MID, "MIDGAME_REFERENCE_LABELS.jsonl"))}
    smp = {json.loads(l)["position_id"]: json.loads(l) for l in open(os.path.join(MID, "MIDGAME_POSITION_SAMPLE.jsonl"))}
    rows = []
    for pid in aud:
        if pid not in lab:
            continue
        r = dict(lab[pid]); r.update(aud[pid])
        if pid in smp:
            r["score_diff_mover"] = smp[pid].get("score_diff_mover")
            r["abs_score_diff"] = abs(smp[pid].get("score_diff_mover") or 0)
        rows.append(r)
    return rows


def frac(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else float("nan")


SIGNALS = [
    ("k_remaining",        lambda r: r.get("k_remaining"),          False),  # LOW k -> route to heur (endgame)
    ("n_legal",            lambda r: r.get("n_legal"),              True),   # HIGH legal -> sharper? route heur
    ("policy_entropy",     lambda r: r.get("policy_entropy"),       True),   # HIGH entropy -> diffuse policy
    ("policy_top1_prob",   lambda r: r.get("policy_top1_prob"),     False),  # LOW top1 -> unsure policy
    ("v27_gap",            lambda r: r.get("v27_gap"),              False),  # LOW gap -> sharp/contested
    ("noresid_topvisit",   lambda r: r.get("iter8_noresid_topvisit_frac"), False),  # LOW conc -> unsure search
    ("abs_score_diff",     lambda r: r.get("abs_score_diff"),       True),
]


def main():
    rows = load()
    n = len(rows)
    print(f"joined positions: {n}")
    err = [1 if r["iter8_choice"] != r[TEACHER] else 0 for r in rows]
    base_err = frac(err)
    always_iter8 = 1 - base_err
    always_h800 = frac([1 if r["heur800_choice"] == r[TEACHER] else 0 for r in rows])
    print(f"baseline: always-iter8 vs teacher = {always_iter8:.3f}; always-heur800 = {always_h800:.3f}; P[iter8 err] = {base_err:.3f}")

    # ---- (1) signal separation of iter8 root-error: split at quartiles, report P[iter8 err] per quartile ----
    print("\n=== (1) does the signal SEPARATE iter8 root-error?  P[iter8!=teacher] across signal quartiles ===")
    print(f"{'signal':18s} {'Q1(low)':>9s} {'Q2':>7s} {'Q3':>7s} {'Q4(high)':>9s}  {'spread':>7s}")
    sep_rows = []
    for name, fn, hi_is_route in SIGNALS:
        vals = sorted([fn(r) for r in rows if fn(r) is not None])
        if len(vals) < 8:
            continue
        qs = [vals[int(len(vals) * q)] for q in (0.25, 0.5, 0.75)]
        buckets = [[], [], [], []]
        for r in rows:
            v = fn(r)
            if v is None:
                continue
            b = 0 + (v > qs[0]) + (v > qs[1]) + (v > qs[2])
            buckets[b].append(1 if r["iter8_choice"] != r[TEACHER] else 0)
        ps = [frac(b) for b in buckets]
        spread = (max(ps) - min(ps)) if all(p == p for p in ps) else float("nan")
        sep_rows.append((name, *[round(p, 4) for p in ps], round(spread, 4)))
        print(f"{name:18s} {ps[0]:9.3f} {ps[1]:7.3f} {ps[2]:7.3f} {ps[3]:9.3f}  {spread:7.3f}")

    # ---- (2) threshold router: heur800 if signal past threshold else iter8 -> agreement + coverage ----
    print("\n=== (2) threshold router (heur@800 past threshold, else iter8): teacher-agree + heur-coverage ===")
    router_rows = []
    for name, fn, hi_is_route in SIGNALS:
        vals = sorted(set(fn(r) for r in rows if fn(r) is not None))
        best = None
        for thr in vals:
            # route to heur when (signal high & hi_is_route) or (signal low & not hi_is_route)
            agree, cov = [], 0
            for r in rows:
                v = fn(r)
                route_heur = (v is not None) and ((v >= thr) if hi_is_route else (v <= thr))
                pick = r["heur800_choice"] if route_heur else r["iter8_choice"]
                agree.append(1 if pick == r[TEACHER] else 0)
                cov += route_heur
            a = frac(agree)
            if best is None or a > best[1]:
                best = (thr, a, cov / n)
        router_rows.append((name, best[0], round(best[1], 4), round(best[2], 3)))
        print(f"{name:18s} best_thr={best[0]:<8} agree={best[1]:.3f} heur_coverage={best[2]/1:.3f}")

    # ---- fixed-K baselines (route heur if k_remaining <= K) ----
    print("\n=== fixed-K router baselines (route heur@800 if k_remaining <= K) ===")
    for K in (5, 8, 10, 16, 28, 40):
        agree, cov = [], 0
        for r in rows:
            route_heur = r["k_remaining"] <= K
            pick = r["heur800_choice"] if route_heur else r["iter8_choice"]
            agree.append(1 if pick == r[TEACHER] else 0)
            cov += route_heur
        print(f"  K<={K:<3} agree={frac(agree):.3f} heur_coverage={cov/n:.3f}")

    # ---- oracle ceiling: per-position pick whichever of {iter8,heur800} matches teacher ----
    oracle = frac([1 if (r["iter8_choice"] == r[TEACHER] or r["heur800_choice"] == r[TEACHER]) else 0 for r in rows])
    print(f"\noracle (per-pos best of iter8/heur800): {oracle:.3f}  (router upper bound)")

    with open(os.path.join(SPM, "ROUTING_RULE_ANALYSIS.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["section", "signal", "a", "b", "c", "d"])
        w.writerow(["baseline", "always_iter8", round(always_iter8, 4), "always_heur800", round(always_h800, 4), ""])
        w.writerow(["baseline", "oracle_iter8_or_heur800", round(oracle, 4), "", "", ""])
        for sr in sep_rows:
            w.writerow(["error_separation_quartiles", *sr])
        for rr in router_rows:
            w.writerow(["threshold_router", rr[0], f"thr={rr[1]}", f"agree={rr[2]}", f"cov={rr[3]}", ""])
    print("\n[done] wrote ROUTING_RULE_ANALYSIS.csv")


if __name__ == "__main__":
    main()
