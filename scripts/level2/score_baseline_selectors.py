#!/usr/bin/env python3
"""Pre-tool audit (Phase 3) — score simple selectors against the exact solver target.

Targets:
  K=2  : exact regret from the re-solved full child-value map (k2_childvalues.jsonl) →
         ALL selectors scorable + rank-correlation of cheap quantities vs solver values.
  K=3  : agents only (per-agent regret from the dataset) + random top-1 (n_opt/n_legal).
  K=4  : agents only + random (random_legal_regret from the persisted difficulty block).

Emits BASELINE_RESULTS.csv / _BY_SOURCE.csv / _BY_DIFFICULTY.csv and prints a summary
(folded into BASELINE_RESULTS.md). Clairvoyant target unless noted; K=2 also has
marginalized (== clairvoyant at K=2).
"""
from __future__ import annotations
import csv, json, math, os, statistics as st
from collections import defaultdict

AUD = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "measurement", "pre_tool_audit")
DS = os.path.join(AUD, "ACTION_AUDIT_DATASET.jsonl")
CV = os.path.join(AUD, "k2_childvalues.jsonl")


def kendall_tau_b(x, y):
    n = len(x)
    if n < 2:
        return float("nan")
    conc = disc = 0
    tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tx += 1; continue
            if dy == 0:
                ty += 1; continue
            if (dx > 0) == (dy > 0):
                conc += 1
            else:
                disc += 1
    n0 = conc + disc + tx + ty + 0  # pairs that are not both-tied
    denom = math.sqrt((conc + disc + tx) * (conc + disc + ty))
    return (conc - disc) / denom if denom > 0 else float("nan")


def load():
    ds = [json.loads(l) for l in open(DS)]
    ds = [d for d in ds if d["label_kind"] != "none"]
    cv = {r["gen_id"]: r for r in (json.loads(l) for l in open(CV))}
    return ds, cv


# ---- per-action score functions for computed selectors (K=2) ----
# NOTE: imm_score_delta_*/score_diff_after/meeple_delta_mover/completion_scored are now the
# SCORING-RESOLVED (meeple-pass) values; best_meeple_net is the best achievable own-net this turn.
def f_imm_net(a):    return a["imm_score_delta_mover"] - a["imm_score_delta_opp"]  # forced-completion net
def f_best_meeple(a): return a["best_meeple_net"]                                  # incl. claim+score
def f_meeple(a):     return a["meeple_delta_mover"]
def f_score_meeple(a): return (a["imm_score_delta_mover"] - a["imm_score_delta_opp"]) + 0.5 * a["meeple_delta_mover"]
def f_v27(a):        return a["v27_score"]
def f_scorediff(a):  return a["score_diff_after"]
def f_completion(a): return (1000 if a["completion_scored"] else 0) + (a["imm_score_delta_mover"] - a["imm_score_delta_opp"])

COMPUTED = [
    ("immediate-score-only(forced-net)", f_imm_net),
    ("immediate-score+meeple-claim(best)", f_best_meeple),
    ("meeple-delta-only", f_meeple),
    ("score+meeple", f_score_meeple),
    ("v2.7-action-score-only", f_v27),
    ("completion-then-score", f_completion),
    ("score-diff-after", f_scorediff),
]
AGENTS_K23 = ["iter8", "heur@3200", "heur@1600", "heur@800", "greedy", "heur_v1@200"]
AGENTS_K4 = ["iter8", "heur@3200", "heur@800", "greedy"]


def k2_regret_fn(cvmode):
    value = cvmode["value"]; to_move = cvmode["to_move"]; cvs = cvmode["child_values"]
    def reg(a):
        v = cvs[str(a)]
        return (value - v) if to_move == 0 else (v - value)
    return reg


def eval_computed(actions, reg, score_fn, maximize=True):
    scored = [(score_fn(a), a["action"]) for a in actions]
    best = max(s for s, _ in scored) if maximize else min(s for s, _ in scored)
    tie = [a for s, a in scored if s == best]
    regs = [reg(a) for a in tie]
    return st.mean(regs), st.mean(1.0 if r <= 1e-9 else 0.0 for r in regs)  # (exp_regret, exp_top1)


def agg(per_pos):
    """per_pos = list of (regret, top1). Return metrics dict."""
    if not per_pos:
        return None
    regs = [r for r, _ in per_pos]; tops = [t for _, t in per_pos]
    return {
        "n": len(per_pos),
        "top1": round(st.mean(tops), 4),
        "mean_regret": round(st.mean(regs), 4),
        "median_regret": round(st.median(regs), 4),
        "blunder_gt2": round(st.mean(1.0 if r > 2 else 0.0 for r in regs), 4),
        "blunder_gt5": round(st.mean(1.0 if r > 5 else 0.0 for r in regs), 4),
        "blunder_gt10": round(st.mean(1.0 if r > 10 else 0.0 for r in regs), 4),
    }


def main():
    ds, cv = load()
    rows = []        # BASELINE_RESULTS.csv
    rows_src = []    # BY_SOURCE
    rows_diff = []   # BY_DIFFICULTY
    tau_acc = defaultdict(list)

    # ============ K=2 (full child_values) ============
    k2 = [d for d in ds if d["k_remaining"] == 2]
    # precompute per-position: regret fn (clairvoyant), decision flag, difficulty
    POS = []
    for d in k2:
        gid = d["position_id"].rsplit("_k", 1)[0]
        cvi = cv.get(gid, {}).get("clairvoyant")
        if not cvi or not cvi.get("child_values"):
            continue
        reg = k2_regret_fn(cvi)
        acts = d["actions"]
        mvals = []  # mover-perspective values
        to_move = cvi["to_move"]; value = cvi["value"]
        for a in acts:
            v = cvi["child_values"][str(a["action"])]
            mvals.append(v if to_move == 0 else -v)
        best = max(mvals); srt = sorted(set(mvals), reverse=True)
        gap = (srt[0] - srt[1]) if len(srt) > 1 else 0.0
        within1 = sum(1 for mv in mvals if mv >= best - 1.0 + 1e-9)
        rand_reg = st.mean(reg(a["action"]) for a in acts)
        n_opt = cvi.get("n_optimal", sum(1 for mv in mvals if abs(mv - best) <= 1e-9))
        decision = n_opt < len(acts)
        POS.append({"d": d, "reg": reg, "acts": acts, "gap": gap, "within1": within1,
                    "rand_reg": rand_reg, "decision": decision, "sharp": gap >= 2,
                    "to_move": to_move})
        # tau: cheap quantity vs mover-value
        target = mvals
        for qn, qf in [("v2.7", f_v27), ("imm_net_forced", f_imm_net), ("best_meeple_net", f_best_meeple),
                       ("meeple_delta", f_meeple), ("scorediff_after", f_scorediff)]:
            q = [qf(a) for a in acts]
            tau_acc[qn].append(kendall_tau_b(q, target))

    for scope, mask in (("all", lambda p: True), ("decision", lambda p: p["decision"])):
        sub = [p for p in POS if mask(p)]
        # random
        rnd = [(p["rand_reg"], (1.0 - p["within1"] / len(p["acts"])) if False else
                (sum(1 for a in p["acts"] if p["reg"](a["action"]) <= 1e-9) / len(p["acts"]))) for p in sub]
        m = agg(rnd);  rows.append(["random", 2, scope, *m.values()])
        # agents
        for ag in AGENTS_K23:
            pp = []
            for p in sub:
                pa = p["d"]["labels"]["clairvoyant"]["per_agent"].get(ag)
                if pa is None: continue
                pp.append((pa["regret"], 1.0 if pa["regret"] <= 1e-9 else 0.0))
            m = agg(pp)
            if m: rows.append([ag, 2, scope, *m.values()])
        # computed
        for name, fn in COMPUTED:
            pp = [eval_computed(p["acts"], p["reg"], fn) for p in sub]
            m = agg(pp)
            if m: rows.append([name, 2, scope, *m.values()])

    # K=2 by difficulty (sharp vs forgiving), decision positions
    for bucket, bmask in (("sharp_gap>=2", lambda p: p["sharp"]), ("forgiving_gap<2", lambda p: not p["sharp"])):
        sub = [p for p in POS if p["decision"] and bmask(p)]
        if not sub: continue
        for ag in ["iter8", "heur@3200", "greedy"]:
            pp = [( p["d"]["labels"]["clairvoyant"]["per_agent"][ag]["regret"],
                    1.0 if p["d"]["labels"]["clairvoyant"]["per_agent"][ag]["regret"] <= 1e-9 else 0.0)
                  for p in sub if p["d"]["labels"]["clairvoyant"]["per_agent"].get(ag)]
            m = agg(pp)
            if m: rows_diff.append([ag, 2, bucket, m["n"], m["top1"], m["mean_regret"]])
        for name, fn in [("v2.7-action-score-only", f_v27), ("immediate-score+meeple-claim(best)", f_best_meeple),
                         ("immediate-score-only(forced-net)", f_imm_net)]:
            pp = [eval_computed(p["acts"], p["reg"], fn) for p in sub]
            m = agg(pp)
            if m: rows_diff.append([name, 2, bucket, m["n"], m["top1"], m["mean_regret"]])

    # ============ K=3 (agents only) ============
    k3 = [d for d in ds if d["k_remaining"] == 3]
    for ag in AGENTS_K23:
        pp = []
        for d in k3:
            pa = d["labels"]["clairvoyant"]["per_agent"].get(ag)
            if pa is None: continue
            pp.append((pa["regret"], 1.0 if pa["regret"] <= 1e-9 else 0.0))
        m = agg(pp)
        if m: rows.append([ag, 3, "all", *m.values()])
    # K=3 random top-1 only (n_opt/n_legal); regret unavailable
    rnd3 = []
    for d in k3:
        g = d["labels"]["clairvoyant"]; rnd3.append((float("nan"), g["n_optimal"] / g["n_legal"]))
    if rnd3:
        tops = [t for _, t in rnd3]
        rows.append(["random(top1-only)", 3, "all", len(rnd3), round(st.mean(tops), 4),
                     "NA", "NA", "NA", "NA", "NA"])

    # ============ K=4 (agents + random from difficulty block) ============
    k4 = [d for d in ds if d["k_remaining"] == 4]
    for ag in AGENTS_K4:
        pp = []
        for d in k4:
            pa = d["labels"]["clairvoyant"]["per_agent"].get(ag)
            if pa is None: continue
            pp.append((pa["regret"], 1.0 if pa["regret"] <= 1e-9 else 0.0))
        m = agg(pp)
        if m: rows.append([ag, 4, "all", *m.values()])
    # K=4 random: random_legal_regret + top1 = n_opt/n_legal
    rnd4 = []
    for d in k4:
        g = d["labels"]["clairvoyant"]; diff = g.get("difficulty") or {}
        rr = diff.get("random_legal_regret")
        if rr is None: continue
        rnd4.append((rr, g["n_optimal"] / g["n_legal"]))
    if rnd4:
        m = agg(rnd4); rows.append(["random", 4, "all", *m.values()])

    # K=4 by source + by sharpness
    for ag in AGENTS_K4:
        bysrc = defaultdict(list); bysharp = defaultdict(list)
        for d in k4:
            pa = d["labels"]["clairvoyant"]["per_agent"].get(ag)
            if pa is None: continue
            tup = (pa["regret"], 1.0 if pa["regret"] <= 1e-9 else 0.0)
            bysrc[d["source_bucket"]].append(tup)
            diff = d["labels"]["clairvoyant"].get("difficulty") or {}
            gap = diff.get("best_vs_second_gap")
            if gap is not None:
                bysharp["sharp_gap>=2" if gap >= 2 else "forgiving_gap<2"].append(tup)
        for s, pp in sorted(bysrc.items()):
            m = agg(pp); rows_src.append([ag, 4, s, m["n"], m["top1"], m["mean_regret"]])
        for s, pp in sorted(bysharp.items()):
            m = agg(pp); rows_diff.append([ag, 4, s, m["n"], m["top1"], m["mean_regret"]])

    # ---- write CSVs ----
    with open(os.path.join(AUD, "BASELINE_RESULTS.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["selector", "k", "scope", "n", "top1", "mean_regret", "median_regret",
                    "blunder_gt2", "blunder_gt5", "blunder_gt10"])
        for r in rows: w.writerow(r)
    with open(os.path.join(AUD, "BASELINE_RESULTS_BY_SOURCE.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["selector", "k", "source", "n", "top1", "mean_regret"])
        for r in rows_src: w.writerow(r)
    with open(os.path.join(AUD, "BASELINE_RESULTS_BY_DIFFICULTY.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["selector", "k", "difficulty_bucket", "n", "top1", "mean_regret"])
        for r in rows_diff: w.writerow(r)

    # ---- print summary ----
    print("=== Kendall tau-b (K=2, cheap quantity vs exact mover-value ranking) ===")
    print("    (NaN tau = the quantity is CONSTANT across all legal actions in that position → no ranking signal)")
    tau_summary = {}
    for qn, vals in tau_acc.items():
        n_total = len(vals)
        good = [v for v in vals if not math.isnan(v)]
        mean_tau = st.mean(good) if good else float("nan")
        informative_frac = len(good) / n_total if n_total else 0.0
        tau_summary[qn] = (mean_tau, len(good), n_total, informative_frac)
        mt = f"{mean_tau:+.3f}" if good else "  n/a"
        print(f"  {qn:18s} mean_tau={mt}  informative_positions={len(good)}/{n_total} ({informative_frac:.0%})")
    print("\n=== BASELINE_RESULTS.csv ===")
    print("selector,k,scope,n,top1,mean_regret,median_regret,blunder_gt2,>5,>10")
    for r in rows:
        print(",".join(str(x) for x in r))
    print("\n=== BY_SOURCE (K=4) ===")
    for r in rows_src: print(",".join(str(x) for x in r))
    print("\n=== BY_DIFFICULTY ===")
    for r in rows_diff: print(",".join(str(x) for x in r))


if __name__ == "__main__":
    main()
