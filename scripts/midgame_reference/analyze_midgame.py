#!/usr/bin/env python3
"""Midgame reference (Phases 4 & 5) — baseline ranking analysis + disagreement taxonomy.

Joins MIDGAME_ACTION_FEATURES.jsonl (Phase 2) with MIDGAME_REFERENCE_LABELS.jsonl (Phase 3).
The deep-search teacher heur@3200 is the primary (soft, NOT ground-truth) target:
  - top-1 agreement  = selector pick == heur3200_choice
  - in-top3          = heur3200_choice within the selector's top-3 by feature
  - teacher_q_regret = heur3200 best child mover-Q  −  child mover-Q of the selector's pick
                       (value units ~[-2,2]; ONLY over positions where the pick was visited)
  - Kendall tau      = feature ranking vs heur3200 child-Q ranking over VISITED legal actions

Reuses score_baseline_selectors.kendall_tau_b. A small offline diagnostic linear ranker
(strict train/test split, coefficients reported) is the only fit — diagnostic, not production.

Out (Phase 4): MIDGAME_BASELINE_RESULTS.csv / _BY_SOURCE.csv / _BY_PHASE.csv / _BY_DISAGREEMENT.csv
               + MIDGAME_BASELINE_RESULTS.md
Out (Phase 5): MIDGAME_DISAGREEMENTS_TOP100.md + MIDGAME_DISAGREEMENT_CATEGORIES.csv
"""
from __future__ import annotations
import os, sys, csv, json, math, random, statistics as st
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))
from score_baseline_selectors import kendall_tau_b  # noqa: E402 (REUSE)

DIR = os.path.join(REPO, "measurement", "midgame_reference")
BANDS = ["opening", "early_mid", "mid", "late_mid", "pre_endgame"]


# ---- feature selectors (operate on a position's list of per-action feature dicts) ----
def _imm_net(a):     return a["imm_net_pass"]
def _scorediff(a):   return a["score_diff_after"]
def _meeple(a):      return a["meeple_delta_mover"]
def _best_meeple(a): return a["best_meeple_net"]
def _v27(a):         return a["v27_score"]
def _completion(a):  return (1000 if a["completion_scored"] else 0) + a["imm_net_pass"]
def _open_prog(a):   return a["city_open_edge_delta"]
def _bag_closure(a): return a["bag_supply_factor"] * a["city_open_edge_delta"]
def _composite(a):   return a["imm_net_pass"] + 0.5 * a["meeple_delta_mover"] + 1.0 * a["city_open_edge_delta"]
def _composite_v27(a): return a["v27_score"] + 0.25 * a["city_open_edge_delta"] + 0.25 * a["meeple_delta_mover"]

SELECTORS = [  # (name, keyfn) — argmax
    ("immediate-score(forced-net)", _imm_net),
    ("score-diff-after", _scorediff),
    ("meeple-recovery", _meeple),
    ("best-meeple(incl-claim)", _best_meeple),
    ("completion-then-score", _completion),
    ("open-edge-progress", _open_prog),
    ("bag-aware-closure", _bag_closure),
    ("composite-simple", _composite),
    ("v2.7-static(depth0)", _v27),
    ("composite-v2.7+delta", _composite_v27),
]


def load():
    feats = {json.loads(l)["position_id"]: json.loads(l)
             for l in open(os.path.join(DIR, "MIDGAME_ACTION_FEATURES.jsonl"))}
    recs = []
    for l in open(os.path.join(DIR, "MIDGAME_REFERENCE_LABELS.jsonl")):
        lab = json.loads(l)
        f = feats.get(lab["position_id"])
        if f is None:
            continue
        cq = {int(k): v for k, v in lab["heur3200_child_q"].items()}
        recs.append({
            "pid": lab["position_id"], "band": lab["band"], "source": lab["source_bucket"],
            "n_legal": lab["n_legal"], "teacher": lab["heur3200_choice"],
            "heur800": lab["heur800_choice"], "gap_q": lab["teacher_gap_q"],
            "shallow_deep_agree": lab["shallow_deep_agree"],
            "iter8": lab["iter8_choice"], "iter8_prior": lab["iter8_prior_argmax"],
            "v27_static": lab["v27_static_choice"], "child_q": cq,
            "acts": f["actions"], "in_hand": f["in_hand_tile"], "k": lab["k_remaining"],
            "score_diff": f.get("score_diff_mover"),
        })
    return recs


def topk_pick(acts, keyfn, k=1):
    """Return (top1_action, set(top-k actions)). Ties: lowest action index joins the tie set."""
    scored = sorted(acts, key=lambda a: (keyfn(a), -a["action"]), reverse=True)
    top1 = scored[0]["action"]
    topk = {a["action"] for a in scored[:k]}
    # include all actions tied with the kth score
    if len(scored) > k:
        kth = keyfn(scored[k - 1])
        topk |= {a["action"] for a in scored if keyfn(a) == kth}
    return top1, topk


def q_regret(child_q, pick):
    if not child_q:
        return None, False
    best = max(child_q.values())
    if pick in child_q:
        return best - child_q[pick], True
    return None, False   # pick unvisited by teacher -> excluded from regret mean (coverage tracked)


def eval_selector(recs, keyfn):
    top1 = []; intop3 = []; regrets = []; visited = 0; total = 0
    for r in recs:
        p1, p3 = topk_pick(r["acts"], keyfn, k=3)
        top1.append(1.0 if p1 == r["teacher"] else 0.0)
        intop3.append(1.0 if r["teacher"] in p3 else 0.0)
        reg, vis = q_regret(r["child_q"], p1)
        total += 1
        if vis:
            visited += 1; regrets.append(reg)
    return {
        "n": len(recs),
        "top1": round(st.mean(top1), 4) if top1 else None,
        "top3": round(st.mean(intop3), 4) if intop3 else None,
        "q_regret": round(st.mean(regrets), 4) if regrets else None,
        "regret_cov": round(visited / total, 3) if total else None,
    }


def eval_reference(recs, key):
    """Reference label (iter8 / iter8_prior / v27_static / heur800) top-1 vs teacher + q_regret."""
    top1 = []; regrets = []; visited = 0
    for r in recs:
        pick = r[key]
        top1.append(1.0 if pick == r["teacher"] else 0.0)
        reg, vis = q_regret(r["child_q"], pick)
        if vis:
            visited += 1; regrets.append(reg)
    return {
        "n": len(recs),
        "top1": round(st.mean(top1), 4) if top1 else None,
        "top3": None,
        "q_regret": round(st.mean(regrets), 4) if regrets else None,
        "regret_cov": round(visited / len(recs), 3) if recs else None,
    }


def random_baseline(recs, seed=7):
    rng = random.Random(seed)
    top1 = []; regrets = []; visited = 0
    for r in recs:
        pick = rng.choice([a["action"] for a in r["acts"]])
        top1.append(1.0 if pick == r["teacher"] else 0.0)
        reg, vis = q_regret(r["child_q"], pick)
        if vis:
            visited += 1; regrets.append(reg)
    return {"n": len(recs), "top1": round(st.mean(top1), 4), "top3": None,
            "q_regret": round(st.mean(regrets), 4) if regrets else None,
            "regret_cov": round(visited / len(recs), 3) if recs else None}


# ---- Kendall tau of each feature vs teacher child-Q ranking (over visited legal actions) ----
TAU_FEATS = [("v2.7", _v27), ("imm_net", _imm_net), ("best_meeple", _best_meeple),
             ("score_diff", _scorediff), ("meeple_delta", _meeple),
             ("open_edge_delta", _open_prog), ("bag_closure", _bag_closure),
             ("composite", _composite)]


def tau_table(recs):
    acc = {name: [] for name, _ in TAU_FEATS}
    for r in recs:
        cq = r["child_q"]
        vis_acts = [a for a in r["acts"] if a["action"] in cq]
        if len(vis_acts) < 2:
            continue
        target = [cq[a["action"]] for a in vis_acts]
        for name, fn in TAU_FEATS:
            xs = [fn(a) for a in vis_acts]
            if len(set(xs)) < 2:
                continue  # feature constant here -> no ranking signal
            t = kendall_tau_b(xs, target)
            if not math.isnan(t):
                acc[name].append(t)
    out = {}
    for name, _ in TAU_FEATS:
        vals = acc[name]
        out[name] = (round(st.mean(vals), 4) if vals else None, len(vals), round(len(vals) / len(recs), 3))
    return out


# ---- small offline diagnostic linear ranker (train/test split by position) ----
RANKER_FEATS = [("imm_net", _imm_net), ("meeple_delta", _meeple), ("completion_pts",
                lambda a: a["imm_score_delta_mover"]), ("open_edge_delta", _open_prog),
                ("aff_min_open", lambda a: a["aff_city_min_open_after"]),
                ("bag_supply_factor", lambda a: a["bag_supply_factor"])]
RANKER_FEATS_V27 = RANKER_FEATS + [("v2.7", _v27)]


def fit_ranker(recs, feat_defs, seed=0):
    """Least-squares fit of teacher child-Q on standardized features (train split), report
    test top-1 vs teacher + standardized coefficients. Diagnostic only; NOT a production model."""
    import numpy as np
    rng = random.Random(seed)
    idx = list(range(len(recs))); rng.shuffle(idx)
    cut = int(0.7 * len(idx))
    train_i, test_i = set(idx[:cut]), set(idx[cut:])
    # assemble training rows (one per visited action)
    X, y = [], []
    for i, r in enumerate(recs):
        if i not in train_i:
            continue
        for a in r["acts"]:
            if a["action"] in r["child_q"]:
                X.append([fn(a) for _, fn in feat_defs]); y.append(r["child_q"][a["action"]])
    X = np.array(X, float); y = np.array(y, float)
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1.0
    Xs = (X - mu) / sd
    Xs = np.column_stack([Xs, np.ones(len(Xs))])
    coef, *_ = np.linalg.lstsq(Xs, y, rcond=None)
    # test top-1 vs teacher
    top1 = []
    for i, r in enumerate(recs):
        if i not in test_i:
            continue
        best_s, best_a = None, None
        for a in r["acts"]:
            xs = (np.array([fn(a) for _, fn in feat_defs], float) - mu) / sd
            s = float(xs @ coef[:-1] + coef[-1])
            if best_s is None or s > best_s:
                best_s, best_a = s, a["action"]
        top1.append(1.0 if best_a == r["teacher"] else 0.0)
    names = [n for n, _ in feat_defs]
    return {
        "n_train_pos": len(train_i), "n_test_pos": len(test_i),
        "test_top1_vs_teacher": round(st.mean(top1), 4) if top1 else None,
        "std_coefficients": {n: round(float(c), 4) for n, c in zip(names, coef[:-1])},
        "intercept": round(float(coef[-1]), 4),
    }


def agg_rows(recs, label):
    rows = []
    rows.append(["random", label, *random_baseline(recs).values()])
    for key, nm in [("iter8", "iter8(MCTS@200)"), ("iter8_prior", "iter8(policy-prior)"),
                    ("v27_static", "v2.7-static(label)"), ("heur800", "heur@800(shallow-teacher)")]:
        rows.append([nm, label, *eval_reference(recs, key).values()])
    for nm, fn in SELECTORS:
        rows.append([nm, label, *eval_selector(recs, fn).values()])
    return rows


def main():
    recs = load()
    print(f"[phase4] joined {len(recs)} positions", flush=True)

    HEAD = ["selector", "scope", "n", "top1", "top3", "q_regret", "regret_cov"]
    overall = agg_rows(recs, "all")
    with open(os.path.join(DIR, "MIDGAME_BASELINE_RESULTS.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(HEAD); w.writerows(overall)

    # by band (= phase)
    by_phase = []
    for b in BANDS:
        sub = [r for r in recs if r["band"] == b]
        if sub:
            by_phase += agg_rows(sub, b)
    with open(os.path.join(DIR, "MIDGAME_RESULTS_BY_PHASE.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(HEAD); w.writerows(by_phase)

    # by source
    by_src = []
    for s in sorted({r["source"] for r in recs}):
        sub = [r for r in recs if r["source"] == s]
        by_src += agg_rows(sub, s)
    with open(os.path.join(DIR, "MIDGAME_RESULTS_BY_SOURCE.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(HEAD); w.writerows(by_src)

    # by disagreement / confidence buckets
    buckets = {
        "teacher_sharp(gap>=0.15)": [r for r in recs if r["gap_q"] is not None and r["gap_q"] >= 0.15],
        "teacher_close(gap<0.15)": [r for r in recs if r["gap_q"] is not None and r["gap_q"] < 0.15],
        "iter8!=teacher": [r for r in recs if r["iter8"] != r["teacher"]],
        "iter8==teacher": [r for r in recs if r["iter8"] == r["teacher"]],
        "v27!=teacher": [r for r in recs if r["v27_static"] != r["teacher"]],
        "shallow!=deep": [r for r in recs if not r["shallow_deep_agree"]],
        "n_legal<=20": [r for r in recs if r["n_legal"] <= 20],
        "n_legal>=40": [r for r in recs if r["n_legal"] >= 40],
    }
    by_dis = []
    for nm, sub in buckets.items():
        if sub:
            by_dis += agg_rows(sub, f"{nm}|n={len(sub)}")
    with open(os.path.join(DIR, "MIDGAME_RESULTS_BY_DISAGREEMENT.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(HEAD); w.writerows(by_dis)

    # Kendall tau + offline rankers
    taus = tau_table(recs)
    ranker_plain = fit_ranker(recs, RANKER_FEATS)
    ranker_v27 = fit_ranker(recs, RANKER_FEATS_V27)

    # ---------- Phase 4 markdown ----------
    def fmt(rows):
        out = ["| selector | n | top1 | top3 | q_regret | reg_cov |", "|---|---|---|---|---|---|"]
        for r in rows:
            out.append(f"| {r[0]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |")
        return "\n".join(out)

    md = ["# Phase 4 — Midgame Baseline Ranking vs the heur@3200 Teacher", "",
          "> **Soft target, not ground truth.** heur@3200 (deep v2.7 search, real-deck) is the strongest",
          "> practical midgame ruler; its choice is the top-1 target and its root child mover-Q gives both",
          "> the ranking (Kendall τ) and `q_regret` (best−picked child-Q, value units, over visited picks).",
          "> Clairvoyance-leaning (see REUSE_AND_SCOPE.md). **FACT** unless marked INTERPRETATION.", "",
          f"Joined positions: **{len(recs)}**. Random top-1 ≈ {random_baseline(recs)['top1']}.", "",
          "## Overall (all bands)", "", fmt(overall), "",
          "## Kendall τ-b — feature vs teacher child-Q ranking (over VISITED legal actions)", "",
          "| feature | mean τ | informative positions | informative frac |", "|---|---|---|---|"]
    for name, (mt, ninf, frac) in taus.items():
        md.append(f"| {name} | {mt} | {ninf} | {frac} |")
    md += ["", "## Offline diagnostic linear ranker (train/test split by position — NOT production)", "",
           "**Without v2.7 (raw+bag features only):**",
           f"- test top-1 vs teacher: **{ranker_plain['test_top1_vs_teacher']}** "
           f"(train {ranker_plain['n_train_pos']} / test {ranker_plain['n_test_pos']} positions)",
           f"- standardized coefficients: `{ranker_plain['std_coefficients']}`", "",
           "**With v2.7 added:**",
           f"- test top-1 vs teacher: **{ranker_v27['test_top1_vs_teacher']}**",
           f"- standardized coefficients: `{ranker_v27['std_coefficients']}`", "",
           "(A ranker that needs v2.7 to match the teacher, and where the raw/bag coefficients are small,",
           "would indicate the features carry little signal independent of v2.7. INTERPRETATION in the report.)", "",
           "## Splits", "",
           "Full tables: [MIDGAME_RESULTS_BY_PHASE.csv](MIDGAME_RESULTS_BY_PHASE.csv) ·",
           "[_BY_SOURCE.csv](MIDGAME_RESULTS_BY_SOURCE.csv) ·",
           "[_BY_DISAGREEMENT.csv](MIDGAME_RESULTS_BY_DISAGREEMENT.csv).", "",
           "### top-1 vs teacher by band (key selectors)", ""]
    keysel = ["iter8(MCTS@200)", "v2.7-static(label)", "heur@800(shallow-teacher)",
              "immediate-score(forced-net)", "completion-then-score", "open-edge-progress",
              "composite-v2.7+delta", "random"]
    md.append("| selector | " + " | ".join(BANDS) + " |")
    md.append("|---|" + "---|" * len(BANDS))
    band_rows = {b: {r[0]: r for r in agg_rows([x for x in recs if x["band"] == b], b)} for b in BANDS}
    for sel in keysel:
        cells = []
        for b in BANDS:
            r = band_rows[b].get(sel)
            cells.append(str(r[3]) if r else "—")
        md.append(f"| {sel} | " + " | ".join(cells) + " |")
    md.append("")
    with open(os.path.join(DIR, "MIDGAME_BASELINE_RESULTS.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")

    # ---------- Phase 5: disagreement taxonomy ----------
    phase5(recs)

    # console summary
    print("[phase4] overall:")
    for r in overall:
        print(f"   {r[0]:32s} top1={r[3]} top3={r[4]} qreg={r[5]}", flush=True)
    print("[phase4] tau:")
    for name, (mt, ninf, frac) in taus.items():
        print(f"   {name:16s} tau={mt} inf_frac={frac}", flush=True)
    print(f"[phase4] offline ranker (raw+bag) test top1={ranker_plain['test_top1_vs_teacher']}  "
          f"(+v2.7) test top1={ranker_v27['test_top1_vs_teacher']}", flush=True)


def _category(r, best, second):
    """Diagnostic category for a disagreement case (NOT a claim)."""
    if best is None:
        return "unclear"
    if best.get("completion_scored") and not (second or {}).get("completion_scored"):
        return "completion/score-greed"
    if best.get("meeple_delta_mover", 0) != (second or {}).get("meeple_delta_mover", 0):
        return "meeple-economy"
    if abs(best.get("city_open_edge_delta", 0) - (second or {}).get("city_open_edge_delta", 0)) >= 1:
        return "structural/closure"
    if best.get("completion_scarcity_bucket") != (second or {}).get("completion_scarcity_bucket"):
        return "bag/scarcity"
    if best.get("imm_net_pass", 0) != (second or {}).get("imm_net_pass", 0):
        return "immediate-score"
    return "structural/unclear"


def phase5(recs):
    """Top disagreement cases (iter8 vs teacher, v27 vs teacher) + a category CSV."""
    def actmap(r):
        return {a["action"]: a for a in r["acts"]}

    cases = []
    for r in recs:
        am = actmap(r)
        t = r["teacher"]; cq = r["child_q"]
        # prioritise: iter8 disagrees w/ teacher AND teacher confident; or v27 disagrees but iter8 agrees
        gap = r["gap_q"] if r["gap_q"] is not None else 0.0
        iter8_miss = r["iter8"] != t
        v27_miss = r["v27_static"] != t
        v27_miss_iter8_ok = v27_miss and (r["iter8"] == t)
        v27_ok_iter8_miss = (not v27_miss) and iter8_miss
        if not (iter8_miss or v27_miss):
            continue
        best_a = am.get(t)
        # the "competing" action = what iter8 chose (the miss)
        comp = am.get(r["iter8"]) if iter8_miss else am.get(r["v27_static"])
        cat = _category(r, best_a, comp)
        # priority score: teacher confidence * (interesting pattern)
        prio = gap * (2.0 if v27_miss_iter8_ok else 1.0) + (0.3 if v27_ok_iter8_miss else 0)
        cases.append({
            "pid": r["pid"], "band": r["band"], "source": r["source"], "k": r["k"],
            "n_legal": r["n_legal"], "in_hand": r["in_hand"], "score_diff": r["score_diff"],
            "gap_q": round(gap, 4), "teacher": t, "iter8": r["iter8"], "v27": r["v27_static"],
            "iter8_miss": iter8_miss, "v27_miss": v27_miss,
            "v27_miss_iter8_ok": v27_miss_iter8_ok, "v27_ok_iter8_miss": v27_ok_iter8_miss,
            "category": cat, "prio": round(prio, 4),
            "teacher_q": cq.get(t), "iter8_q": cq.get(r["iter8"]), "v27_q": cq.get(r["v27_static"]),
        })
    cases.sort(key=lambda c: c["prio"], reverse=True)

    # categories CSV (all cases)
    with open(os.path.join(DIR, "MIDGAME_DISAGREEMENT_CATEGORIES.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pid", "band", "source", "k", "n_legal", "gap_q", "category",
                    "iter8_miss", "v27_miss", "v27_miss_iter8_ok", "v27_ok_iter8_miss",
                    "teacher", "iter8", "v27", "teacher_q", "iter8_q", "v27_q"])
        for c in cases:
            w.writerow([c["pid"], c["band"], c["source"], c["k"], c["n_legal"], c["gap_q"],
                        c["category"], c["iter8_miss"], c["v27_miss"], c["v27_miss_iter8_ok"],
                        c["v27_ok_iter8_miss"], c["teacher"], c["iter8"], c["v27"],
                        c["teacher_q"], c["iter8_q"], c["v27_q"]])

    from collections import Counter
    catc = Counter(c["category"] for c in cases)
    n_i8 = sum(1 for c in cases if c["iter8_miss"])
    n_v27 = sum(1 for c in cases if c["v27_miss"])
    n_v27miss_i8ok = sum(1 for c in cases if c["v27_miss_iter8_ok"])
    n_v27ok_i8miss = sum(1 for c in cases if c["v27_ok_iter8_miss"])

    md = ["# Phase 5 — Midgame Disagreement Taxonomy (top cases)", "",
          "> **Diagnostic labels, not claims** (teacher = heur@3200, soft target). Category is a coarse",
          "> mechanism guess from the competing actions' features. Cases ranked by teacher confidence",
          "> (`gap_q`) with priority to *v2.7-misses-but-iter8-agrees* (the net adds value over static)",
          "> and *v2.7-agrees-but-iter8-misses* (the net throws value away). Raw record: replay",
          "> `replay_actions(seed, prefix)` from MIDGAME_POSITION_SAMPLE.jsonl.", "",
          f"Total disagreement cases (iter8≠teacher OR v2.7≠teacher): **{len(cases)}** / {len(recs)} positions.",
          f"- iter8 ≠ teacher: **{n_i8}**  ·  v2.7-static ≠ teacher: **{n_v27}**",
          f"- v2.7 misses but iter8 agrees (net beats static): **{n_v27miss_i8ok}**",
          f"- v2.7 agrees but iter8 misses (net throws it away): **{n_v27ok_i8miss}**", "",
          "## Category counts (all disagreement cases)", "",
          "| category | count |", "|---|---|"]
    for cat, n in catc.most_common():
        md.append(f"| {cat} | {n} |")
    md += ["", "## Top 60 cases by teacher-confidence priority", "",
           "| pid | band | k | n_leg | gap_q | category | flags | teacher/iter8/v27 | Qs(t/i8/v27) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for c in cases[:60]:
        flags = []
        if c["v27_miss_iter8_ok"]: flags.append("NET>STATIC")
        if c["v27_ok_iter8_miss"]: flags.append("NET<STATIC")
        if c["iter8_miss"]: flags.append("i8miss")
        if c["v27_miss"]: flags.append("v27miss")
        md.append(f"| {c['pid']} | {c['band']} | {c['k']} | {c['n_legal']} | {c['gap_q']} | "
                  f"{c['category']} | {','.join(flags)} | {c['teacher']}/{c['iter8']}/{c['v27']} | "
                  f"{c['teacher_q']}/{c['iter8_q']}/{c['v27_q']} |")
    md.append("")
    with open(os.path.join(DIR, "MIDGAME_DISAGREEMENTS_TOP100.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")
    print(f"[phase5] {len(cases)} disagreement cases; categories={dict(catc)}", flush=True)


if __name__ == "__main__":
    main()
