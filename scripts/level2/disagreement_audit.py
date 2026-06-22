#!/usr/bin/env python3
"""Pre-tool audit (Phase 4) — high-value disagreements where iter8 misses the target.

For each position we compare iter8's chosen action against a REFERENCE better action:
  K=2  : an exact-optimal action (from k2_childvalues.jsonl child-value map).
  K=3/4: heur@3200's action when heur@3200 has lower regret (the strongest practical ruler).

Two-axis first-pass categorization (NOT proven — diagnostic labels):
  MECHANISM      : completion / immediate-points / meeple-economy / structural-or-farm / unclear
  V2.7 AXIS      : 'v2.7-rankable'  -> v2.7 leaf already scores the better move higher (iter8
                                       deviated from a signal it ALREADY has) ;
                   'beyond-v2.7'    -> v2.7 also mis-ranks it (a new exact-tactical signal would
                                       be needed).
The V2.7 axis is the load-bearing one for the tool decision.

Outputs: DISAGREEMENTS_TOP100.md, DISAGREEMENT_CATEGORIES.csv
"""
from __future__ import annotations
import csv, json, os, statistics as st
from collections import Counter

AUD = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "measurement", "pre_tool_audit")
DS = os.path.join(AUD, "ACTION_AUDIT_DATASET.jsonl")
CV = os.path.join(AUD, "k2_childvalues.jsonl")
V27_MARGIN = 2  # v2.7 must prefer the better move by > this to count as 'v2.7-rankable'


def raw_path(gid, k):
    if k in (2, 3):
        return f"/mnt/c/carc-shared/l23_regret/{gid}_k{k}.json"
    return f"/mnt/c/carc-shared/l23_k4_expand_probe/{gid}_k4.json"


def feat_of(actions, a):
    for f in actions:
        if f["action"] == a:
            return f
    return None


def net_imm(f):
    return (f["imm_score_delta_mover"] - f["imm_score_delta_opp"]) if f else 0


def mechanism(iter_f, ref_f):
    """First-pass mechanism label from the iter8-move vs reference-move feature delta."""
    if ref_f is None or iter_f is None:
        return "unclear"
    if ref_f["completion_scored"] and not iter_f["completion_scored"]:
        return "completion"
    if net_imm(ref_f) - net_imm(iter_f) >= 2:
        return "immediate-points"
    if ref_f["meeple_delta_mover"] - iter_f["meeple_delta_mover"] >= 1:
        return "meeple-economy"
    if iter_f["completion_scored"] and not ref_f["completion_scored"]:
        return "structural-or-farm"   # iter8 grabbed points but the better move sets up more
    return "structural-or-farm"


def v27_axis(iter_f, ref_f):
    if ref_f is None or iter_f is None:
        return "unclear"
    if ref_f["v27_score"] - iter_f["v27_score"] > V27_MARGIN:
        return "v2.7-rankable"
    if ref_f["v27_score"] - iter_f["v27_score"] < -V27_MARGIN:
        return "iter8-move-v2.7-preferred"  # v2.7 prefers iter8's move yet it's worse: clearly beyond-v2.7
    return "beyond-v2.7"


def main():
    ds = [json.loads(l) for l in open(DS) if json.loads(l)["label_kind"] != "none"]
    cv = {r["gen_id"]: r for r in (json.loads(l) for l in open(CV))}

    disagreements = []
    iter8_wins = []  # iter8 optimal, field misses

    for d in ds:
        k = d["k_remaining"]
        gid = d["position_id"].rsplit("_k", 1)[0]
        lab = d["labels"]["clairvoyant"]
        pa = lab["per_agent"]
        if "iter8" not in pa:
            continue
        ir = pa["iter8"]["regret"]
        iter_a = pa["iter8"]["move"]
        iter_f = feat_of(d["actions"], iter_a)
        h3 = pa.get("heur@3200")
        h3r = h3["regret"] if h3 else None
        h3_a = h3["move"] if h3 else None

        # reference better action + its features
        ref_a = ref_f = ref_regret = None
        if k == 2 and gid in cv and cv[gid].get("clairvoyant", {}).get("child_values"):
            ci = cv[gid]["clairvoyant"]; opt = ci["optimal_actions"]
            # pick the optimal action with v27 closest to iter8's (most "reachable") for fair mechanism read
            if opt:
                ref_a = max(opt, key=lambda a: feat_of(d["actions"], a)["v27_score"] if feat_of(d["actions"], a) else -1e9)
                ref_f = feat_of(d["actions"], ref_a); ref_regret = 0.0
        elif h3 is not None and h3r is not None and h3r < ir:
            ref_a = h3_a; ref_f = feat_of(d["actions"], h3_a); ref_regret = h3r

        diff = lab.get("difficulty") or {}
        gap = diff.get("best_vs_second_gap")
        sharp = (gap is not None and gap >= 2)

        rec = {
            "position_id": d["position_id"], "k": k, "source": d["source_bucket"],
            "in_hand_tile": d["in_hand_tile"], "scores": d["scores"],
            "score_diff_mover": d["score_diff_mover"], "legal_n": lab["n_legal"],
            "n_optimal": lab["n_optimal"], "sharp": sharp, "gap": gap,
            "iter8_regret": ir, "iter8_action": iter_a,
            "heur3200_regret": h3r, "heur3200_action": h3_a,
            "ref_action": ref_a, "ref_regret": ref_regret,
            "iter8_v27": iter_f["v27_score"] if iter_f else None,
            "ref_v27": ref_f["v27_score"] if ref_f else None,
            "iter8_imm_net": net_imm(iter_f), "ref_imm_net": net_imm(ref_f),
            "iter8_meeple": iter_f["meeple_delta_mover"] if iter_f else None,
            "ref_meeple": ref_f["meeple_delta_mover"] if ref_f else None,
            "iter8_completion": iter_f["completion_scored"] if iter_f else None,
            "ref_completion": ref_f["completion_scored"] if ref_f else None,
            "mechanism": mechanism(iter_f, ref_f) if ref_f else "no-stronger-ref(both-miss)",
            "v27_axis": v27_axis(iter_f, ref_f) if ref_f else "no-stronger-ref(both-miss)",
            "raw_path": raw_path(gid, k),
        }
        if ir > 1e-9:
            disagreements.append(rec)
        elif h3r is not None and h3r > 1e-9:
            iter8_wins.append(rec)

    # rank: high regret first, sharp as tiebreak
    disagreements.sort(key=lambda r: (r["iter8_regret"], 1 if r["sharp"] else 0), reverse=True)
    top = disagreements[:100]
    iter8_wins.sort(key=lambda r: (r["heur3200_regret"] or 0), reverse=True)

    # ---- CSV ----
    cols = ["position_id", "k", "source", "in_hand_tile", "score_diff_mover", "legal_n",
            "n_optimal", "sharp", "gap", "iter8_regret", "iter8_action", "heur3200_regret",
            "ref_action", "ref_regret", "iter8_v27", "ref_v27", "iter8_imm_net", "ref_imm_net",
            "iter8_meeple", "ref_meeple", "iter8_completion", "ref_completion",
            "mechanism", "v27_axis", "raw_path"]
    with open(os.path.join(AUD, "DISAGREEMENT_CATEGORIES.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in disagreements:
            w.writerow({c: r[c] for c in cols})

    # category tallies (over all iter8 misses, and over the top-100)
    def tally(recs, key):
        return dict(Counter(r[key] for r in recs).most_common())
    mech_all = tally(disagreements, "mechanism")
    v27_all = tally(disagreements, "v27_axis")
    mech_top = tally(top, "mechanism")
    v27_top = tally(top, "v27_axis")
    by_k = tally(disagreements, "k")
    by_src = tally(disagreements, "source")

    # ---- markdown ----
    md = []
    md.append("# Phase 4 — iter8 Disagreement Audit (top 100)\n")
    md.append("> High-value positions where iter8's move is NOT solver-optimal. Reference 'better' "
              "move = an exact-optimal action (K=2) or heur@3200's better move (K=3/K=4). "
              "Categories are **first-pass diagnostic labels, NOT proven** (prompt §Phase4). "
              "Full table: [DISAGREEMENT_CATEGORIES.csv](DISAGREEMENT_CATEGORIES.csv).\n")
    md.append(f"**Totals:** {len(disagreements)} positions where iter8 is sub-optimal "
              f"(of {len(ds)} labelled). iter8-correct-but-heur@3200-misses: {len(iter8_wins)}.\n")
    md.append(f"**By K:** {by_k}  ·  **By source:** {by_src}\n")
    md.append("\n## The load-bearing split — would iter8's OWN leaf (v2.7) have caught the miss?\n")
    md.append("| v2.7 axis | all iter8 misses | top-100 |\n|---|---|---|")
    for kx in set(list(v27_all) + list(v27_top)):
        md.append(f"| {kx} | {v27_all.get(kx,0)} | {v27_top.get(kx,0)} |")
    md.append("\n*'v2.7-rankable' = the v2.7 leaf already scores the better move higher (by >"
              f"{V27_MARGIN}) — iter8 deviated from a signal it already consumes. 'beyond-v2.7' / "
              "'iter8-move-v2.7-preferred' = v2.7 ALSO mis-ranks it (a new exact signal would be needed).*\n")
    md.append("\n## Mechanism (first-pass)\n")
    md.append("| mechanism | all | top-100 |\n|---|---|---|")
    for kx in set(list(mech_all) + list(mech_top)):
        md.append(f"| {kx} | {mech_all.get(kx,0)} | {mech_top.get(kx,0)} |")

    md.append("\n## Top 30 disagreements (highest iter8 regret)\n")
    md.append("| # | position | K | src | tile | legalN | sharp | iter8 reg | iter8 v27 | ref v27 | mech | v2.7 axis |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(top[:30], 1):
        tile = (r["in_hand_tile"] or "")[:22]
        md.append(f"| {i} | {r['position_id']} | {r['k']} | {r['source'].replace('_selfplay','')} | "
                  f"{tile} | {r['legal_n']} | {'Y' if r['sharp'] else ''} | {r['iter8_regret']:.0f} | "
                  f"{r['iter8_v27']} | {r['ref_v27']} | {r['mechanism']} | {r['v27_axis']} |")

    md.append("\n## A few worked examples (iter8 misses)\n")
    for r in top[:5]:
        md.append(f"- **{r['position_id']}** (K={r['k']}, src={r['source'].replace('_selfplay','')}, "
                  f"tile=`{r['in_hand_tile']}`, legal_n={r['legal_n']}, n_optimal={r['n_optimal']}): "
                  f"iter8 played action {r['iter8_action']} (regret **{r['iter8_regret']:.0f}**, "
                  f"v27={r['iter8_v27']}, imm_net={r['iter8_imm_net']}, meeple Δ={r['iter8_meeple']}); "
                  f"better action {r['ref_action']} (v27={r['ref_v27']}, imm_net={r['ref_imm_net']}, "
                  f"meeple Δ={r['ref_meeple']}, completes={r['ref_completion']}). "
                  f"→ mechanism: *{r['mechanism']}*, axis: *{r['v27_axis']}*. raw: `{r['raw_path']}`")

    md.append("\n## iter8 right, heur@3200 wrong (learned-policy strengths) — top 10\n")
    md.append("| position | K | src | iter8 reg | heur@3200 reg | iter8 v27 | tile |")
    md.append("|---|---|---|---|---|---|---|")
    for r in iter8_wins[:10]:
        md.append(f"| {r['position_id']} | {r['k']} | {r['source'].replace('_selfplay','')} | "
                  f"{r['iter8_regret']:.0f} | {r['heur3200_regret']:.0f} | {r['iter8_v27']} | "
                  f"{(r['in_hand_tile'] or '')[:24]} |")

    with open(os.path.join(AUD, "DISAGREEMENTS_TOP100.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")

    # print summary
    print(f"disagreements={len(disagreements)} iter8_wins={len(iter8_wins)}")
    print("v27_axis (all):", v27_all)
    print("v27_axis (top100):", v27_top)
    print("mechanism (all):", mech_all)
    print("by_k:", by_k, "by_src:", by_src)
    # axis by source/K for the report
    for kx in (2, 3, 4):
        sub = [r for r in disagreements if r["k"] == kx]
        if sub:
            print(f"  K={kx}: n={len(sub)} v27_axis={tally(sub,'v27_axis')}")


if __name__ == "__main__":
    main()
