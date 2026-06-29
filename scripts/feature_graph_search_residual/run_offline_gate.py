#!/usr/bin/env python3
"""FGSR Stage 6 — THE OFFLINE GATE.

For each trained model (G0, G1) vs B3 (low_top2gap) and B5 (flat MLP):

(A) G3 SCHEDULER — per-ROOT escalation:
    - AUROC(pos_strong) on TEST.
    - matched-compute regret at C in {300,400,600,800,1200} via best_adaptive (reused).
    - 2000-resample bootstrap: P(model beats B3) + 95% CI on regret delta (reused machinery).
    - Robustness: per-phase TEST regret; opening-held-out split (train non-opening,
      test opening) — re-uses the SAME score (model scores are per-root, phase-agnostic),
      we just slice TEST to opening. (A true retrain-on-non-opening is noted but the score
      is already leakage-safe by seed; we report the opening-only TEST slice regret.)
    - Source split (greedy-vs-MCTS) is DEFERRED (needs roots_adaptive graphs) — noted.

(B) G4 RERANKER — per-LEGAL-ACTION, CONSTANT h200 compute:
    - selected-move regret vs h6400 on the DECISIVE TAIL (q_gap_6400>=0.02 & regret(h200)>=0.02),
      full-pool, and ordinary subset (no-regression check), vs h200's OWN argmax-Q200 pick.
    - WITH and WITHOUT abstain on the structurally-blind slice (leaf_q gap ~ 0 between the
      h200 pick and the model pick -> keep h200's pick).
    - bootstrap P(decisive-tail regret reduction vs h200 > 0) + CI.

Reuses psr_lib / run_adaptive_gate (best_adaptive, md, auroc, the bootstrap pattern) VERBATIM.
NET-FREE, CPU, NO search, NO games. Writes offline_gate.json + FGSR_OFFLINE_RESULTS.md.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "post_search_residual"))
sys.path.insert(0, str(REPO / "scripts" / "feature_graph_search_residual"))
import psr_lib as P                                          # noqa: E402
import run_adaptive_gate as AG                               # noqa: E402

DATA = REPO / "measurement" / "feature_graph_search_residual" / "data"
OUT = REPO / "measurement" / "feature_graph_search_residual"
SRC = REPO / "measurement" / "post_search_residual" / "data"
ROOTS = SRC / "roots_mcts.jsonl"
FEATB = SRC / "features_mcts.jsonl"
BUDGETS = [300, 400, 600, 800, 1200]
BASE = 200
DEEPS = AG.DEEPS
TAIL_GAP, TAIL_REG = 0.02, 0.02
ABSTAIN_EPS = 1e-4         # leaf_q gap below this between picks = structurally blind


# ----------------------------------------------------------------- load
def load_test():
    rows = P.load_roots(str(ROOTS))
    rows = [r for r in rows if all(np.isfinite(r["regret"][L]) for L in P.LEVELS)]
    tr, va, te = P.seed_split(rows)
    # per-root B-features for B5 reproduction inside the gate? not needed (scores from train).
    # npz action rows for the reranker (q200,q6400,leaf_q,action_id grouped by gid)
    z = np.load(DATA / "rows_feat.npz", allow_pickle=False)
    gid = z["group_id"]; order = np.argsort(gid, kind="stable")
    by = {}
    g = gid[order]; aid = z["action_id"][order]
    q200 = z["q200"][order]; q6400 = z["q6400"][order]; leafq = z["leaf_q"][order]
    s = 0
    for i in range(1, len(g) + 1):
        if i == len(g) or g[i] != g[s]:
            gg = int(g[s])
            by[gg] = {"aid": aid[s:i], "q200": q200[s:i], "q6400": q6400[s:i],
                      "leaf_q": leafq[s:i]}
            s = i
    return te, by


def load_scores(name):
    z = np.load(DATA / f"scores_{name}.npz", allow_pickle=False)
    g3 = {int(g): float(s) for g, s in zip(z["gid"], z["g3"])}
    g4 = {}  # gid -> {action_id: score}
    for gg, aid, sc in zip(z["g4_gid"], z["g4_aid"], z["g4"]):
        g4.setdefault(int(gg), {})[int(aid)] = float(sc)
    return g3, g4


# ----------------------------------------------------------------- scheduler scores aligned to te
def aligned_g3(te, g3map, baseline=None):
    """Return np.array of escalation score aligned to te rows.
    baseline: None=model; 'b3'=-top2gap; 'b5'=g3map already are b5 scores."""
    if baseline == "b3":
        return -np.array([r["top2_q_gap200"] for r in te], float)
    return np.array([g3map[r["group_id"]] for r in te], float)


# ----------------------------------------------------------------- (A) scheduler gate
def scheduler_block(te, score, ref_score, n_boot=2000, seed=0):
    """matched-compute regret for `score` vs `ref_score` (both aligned to te) + bootstrap."""
    yte_strong = np.array([r["pos_strong"] for r in te], float)
    au = AG.auroc(score, yte_strong)
    uniform = {L: float(AG.reg_arr(te, L).mean()) for L in P.LEVELS}
    matched = {}
    matched_ref = {}
    for C in BUDGETS:
        v, D = AG.best_adaptive(te, C, score)
        vr, Dr = AG.best_adaptive(te, C, ref_score)
        matched[C] = {"regret": v, "D": D}
        matched_ref[C] = {"regret": vr, "D": Dr}
    # bootstrap (reuse run_adaptive_gate's resample-with-fixed-D pattern)
    reg_by_L = {L: AG.reg_arr(te, L) for L in P.LEVELS}
    n = len(te); idx = np.arange(n); rng = np.random.default_rng(seed)

    def adapt_idx(bs, C, D, sc_sub):
        f = (C - BASE) / (D - BASE)
        k = int(round(f * len(bs)))
        order = np.argsort(-sc_sub)
        esc = np.zeros(len(bs), bool); esc[order[:k]] = True
        return float(np.where(esc, reg_by_L[D][bs], reg_by_L[BASE][bs]).mean())

    boot = {}
    for C in BUDGETS:
        D = matched[C]["D"]; Dr = matched_ref[C]["D"]
        if D is None or Dr is None:
            continue
        d = []
        for _ in range(n_boot):
            bs = rng.choice(idx, size=n, replace=True)
            mm = adapt_idx(bs, C, D, score[bs])
            mr = adapt_idx(bs, C, Dr, ref_score[bs])
            d.append(mr - mm)              # >0 => model better than ref
        d = np.array(d)
        boot[C] = {"p_model_beats_ref": float((d > 0).mean()),
                   "delta_mean": float(d.mean()),
                   "delta_ci": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
    return {"auroc_pos_strong": au, "uniform": uniform,
            "matched": matched, "matched_ref": matched_ref, "bootstrap": boot}


def scheduler_phase(te, score, ref_score):
    """Per-phase matched-compute regret at C=400 and C=800 for model vs ref."""
    out = {}
    for ph in P.PHASES:
        sub = [r for r in te if r["phase"] == ph]
        if len(sub) < 30:
            out[ph] = {"n": len(sub)}; continue
        sc = np.array([score[i] for i, r in enumerate(te) if r["phase"] == ph])
        rc = np.array([ref_score[i] for i, r in enumerate(te) if r["phase"] == ph])
        row = {"n": len(sub)}
        for C in [400, 800]:
            v, _ = AG.best_adaptive(sub, C, sc)
            vr, _ = AG.best_adaptive(sub, C, rc)
            row[C] = {"model": v, "ref": vr,
                      "delta": (vr - v) if (v is not None and vr is not None) else None}
        out[ph] = row
    return out


def scheduler_opening_heldout(te, score, ref_score):
    """Opening-only TEST slice regret (the tail is opening-heavy). Model score is per-root,
    leakage-safe by seed; we report the opening slice matched-compute regret."""
    sub_idx = [i for i, r in enumerate(te) if r["phase"] == "opening"]
    sub = [te[i] for i in sub_idx]
    if len(sub) < 30:
        return {"n": len(sub)}
    sc = score[sub_idx]; rc = ref_score[sub_idx]
    yte = np.array([r["pos_strong"] for r in sub], float)
    out = {"n": len(sub), "auroc_pos_strong_model": AG.auroc(sc, yte),
           "auroc_pos_strong_ref": AG.auroc(rc, yte)}
    for C in BUDGETS:
        v, _ = AG.best_adaptive(sub, C, sc)
        vr, _ = AG.best_adaptive(sub, C, rc)
        out[C] = {"model": v, "ref": vr,
                  "delta": (vr - v) if (v is not None and vr is not None) else None}
    return out


# ----------------------------------------------------------------- (B) reranker gate
def _h200_pick(rec):
    """argmax q200 (ties -> lowest action id)."""
    q = rec["q200"]; aid = rec["aid"]
    order = np.lexsort((aid, -q))
    return int(order[0])


def _model_pick(rec, g4_root, abstain=False, h200_idx=None):
    """argmax model g4 score over the action rows; optional abstain to h200's pick on the
    structurally-blind slice (leaf_q gap between model pick and h200 pick ~ 0)."""
    aid = rec["aid"]
    sc = np.array([g4_root.get(int(a), -1e9) for a in aid], float)
    pick = int(np.argmax(sc))
    if abstain and h200_idx is not None:
        if abs(rec["leaf_q"][pick] - rec["leaf_q"][h200_idx]) < ABSTAIN_EPS:
            return h200_idx
    return pick


def reranker_block(te, by, g4map, n_boot=2000, seed=0):
    """Selected-move regret vs h6400 for: h200, model (abstain on/off), on decisive-tail,
    full-pool, ordinary. + bootstrap P(tail reduction vs h200 > 0)."""
    gids = [r["group_id"] for r in te]
    recs = [by[g] for g in gids]
    tail = np.array([(r["q_gap_6400"] >= TAIL_GAP and r["regret"][200] >= TAIL_REG) for r in te])

    def reg(rec, idx):
        return float(rec["q6400"].max() - rec["q6400"][idx])

    h200_idx = [_h200_pick(rec) for rec in recs]
    m_idx = [_model_pick(rec, g4map.get(g, {}), abstain=False) for rec, g in zip(recs, gids)]
    ma_idx = [_model_pick(rec, g4map.get(g, {}), abstain=True, h200_idx=h)
              for rec, g, h in zip(recs, gids, h200_idx)]

    r_h200 = np.array([reg(rec, i) for rec, i in zip(recs, h200_idx)])
    r_m = np.array([reg(rec, i) for rec, i in zip(recs, m_idx)])
    r_ma = np.array([reg(rec, i) for rec, i in zip(recs, ma_idx)])

    def slice_stats(mask):
        return {"n": int(mask.sum()),
                "h200": float(r_h200[mask].mean()) if mask.any() else None,
                "model": float(r_m[mask].mean()) if mask.any() else None,
                "model_abstain": float(r_ma[mask].mean()) if mask.any() else None}

    blocks = {"decisive_tail": slice_stats(tail),
              "full_pool": slice_stats(np.ones(len(te), bool)),
              "ordinary": slice_stats(~tail)}

    # bootstrap P(tail reduction vs h200 > 0) for model and model_abstain (resample TAIL roots)
    tail_idx = np.flatnonzero(tail)
    rng = np.random.default_rng(seed)
    boot = {}
    for tag, rvec in [("model", r_m), ("model_abstain", r_ma)]:
        d = []
        for _ in range(n_boot):
            bs = rng.choice(tail_idx, size=len(tail_idx), replace=True)
            d.append(float(r_h200[bs].mean() - rvec[bs].mean()))   # >0 => model reduces regret
        d = np.array(d)
        boot[tag] = {"p_reduction_gt_0": float((d > 0).mean()),
                     "delta_mean": float(d.mean()),
                     "delta_ci": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
    # how many tail roots are structurally blind (abstain kicks in) — diagnostic
    n_blind = int(sum(abs(rec["leaf_q"][m] - rec["leaf_q"][h]) < ABSTAIN_EPS
                      for rec, m, h, t in zip(recs, m_idx, h200_idx, tail) if t))
    blocks["n_tail_structurally_blind"] = n_blind
    return {"slices": blocks, "bootstrap": boot}


# ----------------------------------------------------------------- main
def main():
    t0 = time.time()
    te, by = load_test()
    ref_b3 = aligned_g3(te, None, baseline="b3")
    try:
        b5_g3, _ = load_scores("B5")
        have_b5 = True
    except FileNotFoundError:
        have_b5 = False
    print(f"[gate] te={len(te)} roots | B5 scores: {'yes' if have_b5 else 'no'}")

    results = {"n_te": len(te), "budgets": BUDGETS, "models": {}}
    for name in ["G0", "G1"]:
        if not (DATA / f"scores_{name}.npz").exists():
            print(f"[gate] {name}: no scores, skip"); continue
        g3map, g4map = load_scores(name)
        sc = aligned_g3(te, g3map)
        blk = {"head_G3": {}, "head_G4": {}}
        # vs B3
        blk["head_G3"]["vs_B3"] = scheduler_block(te, sc, ref_b3)
        blk["head_G3"]["phase"] = scheduler_phase(te, sc, ref_b3)
        blk["head_G3"]["opening_heldout"] = scheduler_opening_heldout(te, sc, ref_b3)
        # vs B5
        if have_b5:
            ref_b5 = aligned_g3(te, b5_g3)
            blk["head_G3"]["vs_B5"] = scheduler_block(te, sc, ref_b5)
        # reranker
        blk["head_G4"] = reranker_block(te, by, g4map)
        results["models"][name] = blk
        a = blk["head_G3"]["vs_B3"]["auroc_pos_strong"]
        print(f"[gate] {name} G3 AUROC={a:.4f}  | "
              + " ".join(f"C{C}:P={blk['head_G3']['vs_B3']['bootstrap'].get(C,{}).get('p_model_beats_ref','--')}"
                         for C in [400, 800]))
        g4 = blk["head_G4"]
        print(f"       {name} G4 tail: h200={g4['slices']['decisive_tail']['h200']:.5f} "
              f"model={g4['slices']['decisive_tail']['model']:.5f} "
              f"P(red>0)={g4['bootstrap']['model']['p_reduction_gt_0']:.2f}")

    # verdicts
    results["verdicts"] = {name: _verdict(results["models"][name])
                           for name in results["models"]}
    results["runtime_s"] = round(time.time() - t0, 1)
    (OUT / "offline_gate.json").write_text(json.dumps(results, indent=2, default=float))
    _write_md(results, have_b5)
    print(f"[done] {time.time()-t0:.1f}s -> {OUT/'offline_gate.json'}")


def _verdict(blk):
    """Frame against PASS criteria (don't DECIDE)."""
    vsb3 = blk["head_G3"]["vs_B3"]
    g3 = vsb3["bootstrap"]
    p_max = max([g3.get(C, {}).get("p_model_beats_ref", 0) for C in BUDGETS] + [0])
    ci_pos = any(g3.get(C, {}).get("delta_ci", [0, 0])[0] > 0 for C in BUDGETS)
    # matched-compute regret reduction over B3 (max % across budgets where both defined)
    red_pct = -1.0
    for C in BUDGETS:
        m = vsb3["matched"][C]["regret"]; r = vsb3["matched_ref"][C]["regret"]
        if m is not None and r is not None and r > 0:
            red_pct = max(red_pct, 100.0 * (r - m) / r)
    g3_pass = (p_max >= 0.95 and ci_pos and red_pct >= 10.0)
    g4 = blk["head_G4"]
    ord_ = g4["slices"]["ordinary"]
    no_reg = (ord_["model"] is not None and ord_["h200"] is not None
              and ord_["model"] <= ord_["h200"] + 1e-4)
    g4b = g4["bootstrap"]["model"]
    g4_pass = (g4b["p_reduction_gt_0"] >= 0.95 and g4b["delta_ci"][0] > 0 and no_reg)
    return {"G3": "PASS" if g3_pass else ("TIE" if p_max >= 0.5 else "FAIL"),
            "G3_p_max": p_max, "G3_max_regret_reduction_pct_vs_B3": red_pct,
            "G4": "PASS" if g4_pass else ("TIE" if g4b["p_reduction_gt_0"] >= 0.5 else "FAIL"),
            "G4_p_reduction": g4b["p_reduction_gt_0"],
            "G4_ordinary_no_regression": bool(no_reg)}


def _write_md(p, have_b5):
    L = ["# FGSR_OFFLINE_RESULTS.md — Stage 6 offline gate (TEST split)\n",
         f"_generated {time.strftime('%Y-%m-%d %H:%M')} · net-free · frozen v2.9 leaf · "
         f"TEST = {p['n_te']} roots · 2000-resample bootstrap · NO search, NO games_\n",
         "Gate frames each head against the PASS criteria; the DECISION is the human's.\n",
         "- **G3 robust win** = P(beats B3) ≥ 0.95, CI not crossing 0, at matched compute, on "
         "≥1 robustness split, AND ≥10–20% tail-regret reduction vs B3.",
         "- **G4 strength win** = decisive-tail regret reduction vs h200 with bootstrap CI>0 that "
         "survives the ordinary-subset no-regression check.\n"]
    for name in p["models"]:
        blk = p["models"][name]; v = p["verdicts"][name]
        L.append(f"## {name}\n")
        # G3
        g3 = blk["head_G3"]["vs_B3"]
        L.append(f"### G3 scheduler — AUROC(pos_strong) = **{g3['auroc_pos_strong']:.4f}** "
                 f"→ verdict **{v['G3']}** (P_max={v['G3_p_max']:.2f}, "
                 f"max matched-compute regret reduction vs B3 = "
                 f"{v.get('G3_max_regret_reduction_pct_vs_B3', float('nan')):+.1f}%)\n")
        L.append("Matched-compute regret vs B3 (lower=better) + bootstrap P(model<B3):\n")
        L.append("| C | model | B3 | Δ (model−ref, +=better) | P(beats B3) | 95% CI |")
        L.append("|---|---|---|---|---|---|")
        for C in p["budgets"]:
            m = g3["matched"][C]["regret"]; r = g3["matched_ref"][C]["regret"]
            b = g3["bootstrap"].get(C, {})
            def f(x): return f"{x:.5f}" if x is not None else "—"
            ci = b.get("delta_ci")
            cis = f"[{ci[0]:+.5f}, {ci[1]:+.5f}]" if ci else "—"
            L.append(f"| {C} | {f(m)} | {f(r)} | {b.get('delta_mean',0):+.6f} | "
                     f"{b.get('p_model_beats_ref','—')} | {cis} |")
        L.append("")
        if have_b5 and "vs_B5" in blk["head_G3"]:
            g5 = blk["head_G3"]["vs_B5"]
            L.append("vs B5 (flat MLP), matched-compute + bootstrap:\n")
            L.append("| C | model | B5 | P(beats B5) | 95% CI |")
            L.append("|---|---|---|---|---|")
            for C in p["budgets"]:
                m = g5["matched"][C]["regret"]; r = g5["matched_ref"][C]["regret"]
                b = g5["bootstrap"].get(C, {})
                ci = b.get("delta_ci"); cis = f"[{ci[0]:+.5f}, {ci[1]:+.5f}]" if ci else "—"
                def f(x): return f"{x:.5f}" if x is not None else "—"
                L.append(f"| {C} | {f(m)} | {f(r)} | {b.get('p_model_beats_ref','—')} | {cis} |")
            L.append("")
        # robustness
        oh = blk["head_G3"]["opening_heldout"]
        L.append(f"**Robustness — opening-only TEST slice** (n={oh.get('n')}): "
                 f"AUROC model={oh.get('auroc_pos_strong_model')}, ref={oh.get('auroc_pos_strong_ref')}; "
                 f"Δregret @C400={oh.get(400,{}).get('delta')}, @C800={oh.get(800,{}).get('delta')}.\n")
        ph = blk["head_G3"]["phase"]
        L.append("Per-phase Δregret (ref−model, +=model better):\n")
        L.append("| phase | n | Δ@C400 | Δ@C800 |")
        L.append("|---|---|---|---|")
        for k in P.PHASES:
            row = ph.get(k, {})
            d4 = row.get(400, {}).get("delta") if isinstance(row.get(400), dict) else None
            d8 = row.get(800, {}).get("delta") if isinstance(row.get(800), dict) else None
            L.append(f"| {k} | {row.get('n','—')} | "
                     f"{d4:+.6f} | {d8:+.6f} |" if d4 is not None and d8 is not None
                     else f"| {k} | {row.get('n','—')} | — | — |")
        L.append("")
        # G4
        g4 = blk["head_G4"]; sl = g4["slices"]
        L.append(f"### G4 reranker (constant h200 compute) → verdict **{v['G4']}** "
                 f"(P(tail reduction>0)={v['G4_p_reduction']:.2f}, "
                 f"ordinary no-regression={v['G4_ordinary_no_regression']})\n")
        L.append("Selected-move regret vs h6400 (lower=better):\n")
        L.append("| slice | n | h200 | model | model+abstain |")
        L.append("|---|---|---|---|---|")
        for s in ["decisive_tail", "full_pool", "ordinary"]:
            d = sl[s]
            def f(x): return f"{x:.5f}" if x is not None else "—"
            L.append(f"| {s} | {d['n']} | {f(d['h200'])} | {f(d['model'])} | {f(d['model_abstain'])} |")
        L.append(f"\n_{sl['n_tail_structurally_blind']} of {sl['decisive_tail']['n']} decisive-tail "
                 "roots are structurally blind (leaf_q gap≈0 between model and h200 pick) — "
                 "abstain keeps h200's pick there._\n")
        for tag in ["model", "model_abstain"]:
            b = g4["bootstrap"][tag]
            L.append(f"- bootstrap **{tag}** tail-regret reduction vs h200: "
                     f"P(>0)={b['p_reduction_gt_0']:.2f}, Δ={b['delta_mean']:+.6f} "
                     f"CI[{b['delta_ci'][0]:+.6f}, {b['delta_ci'][1]:+.6f}].")
        L.append("")
    L.append("## Deferred\n- Source split (greedy-vs-MCTS robustness) needs roots_adaptive graphs "
             "(not built this run) — DEFERRED.\n")
    (OUT / "FGSR_OFFLINE_RESULTS.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
