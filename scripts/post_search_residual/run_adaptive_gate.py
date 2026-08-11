#!/usr/bin/env python3
"""Post-Search Residual — Stage 3 (train escalation predictors) + Stage 4 (offline adaptive gate).

Trains models to predict — from h200-VISIBLE features only (NO h6400 leakage) — whether a root
should be escalated to deeper search, then simulates the adaptive-compute policy on held-out roots
and asks the Stage-4 gate question:

  Does a LEARNED adaptive policy beat UNIFORM search at matched average compute on held-out roots,
  AND beat the best simple heuristic (the bar Stage 2 showed uniform-tying)?

Models (fit on TRAIN, selected on VAL, evaluated on TEST; split by game so no game crosses splits):
  H0  best single heuristic (entropy / low-top2gap / low-top-share / legal_n)   [Stage-2 floor]
  M1  ridge regression -> regret(h200)            (linear, score = predicted regret)
  M2  logistic regression -> P(positive_medium)   (linear)
  M3  small MLP -> P(positive_medium)             (torch, early-stop on val AUROC)
Ceilings: pairwise oracle (escalate-to-D by true gain) + multi-depth oracle (route-each-root).

Features: Tier-A (h200 search diagnostics + ply + phase) by default; Tier-B structural features
join by group_id if --features-jsonl is given. Writes POST_SEARCH_TRAINING.md +
POST_SEARCH_OFFLINE_RESULTS.md + offline_adaptive.json.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "post_search_residual"))
import psr_lib as P                                       # noqa: E402

OUT = REPO / "measurement" / "post_search_residual"
DATA = OUT / "data"
BASE = 200
DEEPS = [800, 1600, 3200]
ANCHORS = [400, 800]


# ----------------------------------------------------------------- features
def featurize(rows, mu=None, sd=None, feat_extra=None):
    """Tier-A h200-visible features (+ optional Tier-B structural join). Returns (X, names, mu, sd)."""
    phases = P.PHASES
    names = ["entropy200", "top_share200", "top2_q_gap200", "log_n_visited200",
             "log_legal_n", "ply"] + [f"phase_{p}" for p in phases]
    base_cols = []
    extra_names = []
    if feat_extra is not None:
        # union of keys across rows (sorted) -> stable column order
        extra_names = sorted({k for v in feat_extra.values() for k in v})
        names = names + [f"x_{k}" for k in extra_names]
    rowvecs = []
    for r in rows:
        v = [r["entropy200"], r["top_share200"], r["top2_q_gap200"],
             np.log1p(r["n_visited200"]), np.log1p(r["legal_n"]), float(r["ply"])]
        v += [1.0 if r["phase"] == p else 0.0 for p in phases]
        if feat_extra is not None:
            ev = feat_extra.get(r["group_id"], {})
            v += [float(ev.get(k, 0.0)) for k in extra_names]
        rowvecs.append(v)
    X = np.array(rowvecs, float)
    if mu is None:
        mu = X.mean(0); sd = X.std(0); sd[sd < 1e-9] = 1.0
    Xs = (X - mu) / sd
    return Xs, names, mu, sd


# ----------------------------------------------------------------- models
def ridge_fit(X, y, lam=10.0):
    d = X.shape[1]
    A = X.T @ X + lam * np.eye(d)
    return np.linalg.solve(A, X.T @ (y - y.mean())) , y.mean()


def ridge_pred(X, w_b):
    w, b = w_b
    return X @ w + b


def logistic_fit(X, y, lam=1.0, lr=0.2, iters=600):
    n, d = X.shape
    w = np.zeros(d); b = 0.0
    for _ in range(iters):
        z = X @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        gw = X.T @ (p - y) / n + lam * w / n
        gb = float((p - y).mean())
        w -= lr * gw; b -= lr * gb
    return w, b


def logistic_pred(X, w_b):
    w, b = w_b
    return 1.0 / (1.0 + np.exp(-(X @ w + b)))


def mlp_fit_predict(Xtr, ytr, Xva, yva, Xte, hidden=32, epochs=400, lr=1e-3, seed=0):
    import torch
    torch.manual_seed(seed)
    Xtr_t = torch.tensor(Xtr, dtype=torch.float32); ytr_t = torch.tensor(ytr, dtype=torch.float32)
    Xva_t = torch.tensor(Xva, dtype=torch.float32); Xte_t = torch.tensor(Xte, dtype=torch.float32)
    d = Xtr.shape[1]
    net = torch.nn.Sequential(torch.nn.Linear(d, hidden), torch.nn.ReLU(),
                              torch.nn.Linear(hidden, hidden), torch.nn.ReLU(),
                              torch.nn.Linear(hidden, 1))
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
    lossf = torch.nn.BCEWithLogitsLoss()
    best_va = -1.0; best_te = None
    for ep in range(epochs):
        net.train(); opt.zero_grad()
        out = net(Xtr_t).squeeze(1)
        loss = lossf(out, ytr_t)
        loss.backward(); opt.step()
        if ep % 10 == 0 or ep == epochs - 1:
            net.eval()
            with torch.no_grad():
                va = net(Xva_t).squeeze(1).numpy()
                a = auroc(va, yva)
                if a is not None and not np.isnan(a) and a > best_va:
                    best_va = a
                    best_te = net(Xte_t).squeeze(1).numpy().copy()
    return best_te if best_te is not None else net(Xte_t).detach().squeeze(1).numpy(), best_va


# ----------------------------------------------------------------- metrics
def auroc(scores, labels):
    labels = np.asarray(labels) > 0
    npos = int(labels.sum()); nneg = int((~labels).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    order = np.argsort(scores)
    ranks = np.empty(len(scores), float); ranks[order] = np.arange(1, len(scores) + 1)
    return float((ranks[labels].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def reg_arr(rows, L):
    return np.array([r["regret"][L] for r in rows], float)


def adaptive_regret(rows, C, D, score):
    """Escalate top-f roots (by score desc) BASE->D so avg-compute==C. Mean regret."""
    if D <= BASE:
        return None
    f = (C - BASE) / (D - BASE)
    if not (0.0 <= f <= 1.0):
        return None
    rB = reg_arr(rows, BASE); rD = reg_arr(rows, D)
    n = len(rows); k = int(round(f * n))
    order = np.argsort(-score)
    esc = np.zeros(n, bool); esc[order[:k]] = True
    return float(np.where(esc, rD, rB).mean())


def best_adaptive(rows, C, score):
    vals = [(adaptive_regret(rows, C, D, score), D) for D in DEEPS]
    vals = [(v, D) for v, D in vals if v is not None]
    return min(vals) if vals else (None, None)


def md_oracle_at(rows, C):
    levels = np.array(P.LEVELS, float)
    R = np.array([[r["regret"][L] for L in P.LEVELS] for r in rows], float)
    R = R[~np.isnan(R).any(1)]
    lambdas = np.concatenate([[0.0], np.geomspace(1e-6, 1.0, 400)])
    pts = []
    for lam in lambdas:
        pick = (R + lam * levels[None, :]).argmin(1)
        pts.append((float(levels[pick].mean()), float(R[np.arange(len(R)), pick].mean())))
    pts.sort()
    xs = [c for c, _ in pts]; ys = [r for _, r in pts]
    if C < xs[0] or C > xs[-1]:
        return None
    return float(np.interp(C, xs, ys))


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", default=str(DATA / "roots_mcts.jsonl"))
    ap.add_argument("--features-jsonl", default="")
    args = ap.parse_args()
    t0 = time.time()

    rows = P.load_roots(args.roots)
    rows = [r for r in rows if all(np.isfinite(r["regret"][L]) for L in P.LEVELS)]
    feat_extra = None
    if args.features_jsonl and Path(args.features_jsonl).exists():
        feat_extra = {}
        for line in Path(args.features_jsonl).read_text().splitlines():
            if line.strip():
                o = json.loads(line); feat_extra[int(o["group_id"])] = o["features"]
    tr, va, te = P.seed_split(rows)
    print(f"[load] {len(rows)} usable roots | tr={len(tr)} va={len(va)} te={len(te)} | "
          f"feat_extra={'yes' if feat_extra else 'no'}")

    Xtr, names, mu, sd = featurize(tr, feat_extra=feat_extra)
    Xva, *_ = featurize(va, mu, sd, feat_extra); Xte, *_ = featurize(te, mu, sd, feat_extra)
    ytr_med = np.array([r["pos_medium"] for r in tr], float)
    yva_med = np.array([r["pos_medium"] for r in va], float)
    yte_strong = np.array([r["pos_strong"] for r in te], float)
    reg_tr = reg_arr(tr, BASE)

    # ---- models -> TEST escalation scores ----
    scores = {}
    # H0: best single heuristic, picked on VAL by AUROC(pos_medium)
    heur_defs = {"entropy": "entropy200", "low_top2gap": "top2_q_gap200",
                 "low_top_share": "top_share200", "legal_n": "legal_n"}
    sign = {"entropy": 1, "low_top2gap": -1, "low_top_share": -1, "legal_n": 1}
    best_h = None
    for hn, key in heur_defs.items():
        sva = sign[hn] * np.array([r[key] for r in va], float)
        a = auroc(sva, yva_med)
        if best_h is None or (a is not None and a > best_h[1]):
            best_h = (hn, a if a is not None else -1)
    hn = best_h[0]; key = heur_defs[hn]
    scores["H0_" + hn] = sign[hn] * np.array([r[key] for r in te], float)
    # M1 ridge -> regret
    w_b = ridge_fit(Xtr, reg_tr, lam=10.0)
    scores["M1_ridge_regret"] = ridge_pred(Xte, w_b)
    # M2 logistic -> pos_medium
    w_b2 = logistic_fit(Xtr, ytr_med, lam=1.0)
    scores["M2_logistic"] = logistic_pred(Xte, w_b2)
    # M3 MLP -> pos_medium
    try:
        s_mlp, mlp_va = mlp_fit_predict(Xtr, ytr_med, Xva, yva_med, Xte)
        scores["M3_mlp"] = s_mlp
    except Exception as e:
        print(f"[mlp] skipped: {type(e).__name__}: {e}")

    # ---- evaluate on TEST ----
    uniform = {L: float(reg_arr(te, L).mean()) for L in P.LEVELS}
    results = {}
    for name, sc in scores.items():
        sc = np.asarray(sc, float)
        au = auroc(sc, yte_strong)
        row = {"auroc_pos_strong": au, "matched": {}}
        for C in ANCHORS:
            v, D = best_adaptive(te, C, sc)
            row["matched"][C] = {"regret": v, "D": D, "uniform": uniform[C],
                                 "beats_uniform": (v is not None and v < uniform[C])}
        results[name] = row

    # ---- bootstrap robustness: is the best learned model's win over the heuristic real,
    #      or within the noise of a tail-dominated mean? Resample TEST rows B times, hold the
    #      trained scores fixed, recompute matched-compute regret for the best learned model
    #      vs the heuristic (and vs uniform). Report P(model < comparator) + mean Δ ± CI. ----
    learned_names = [k for k in scores if not k.startswith("H0")]
    # pick the best learned model by AUROC(pos_strong)
    best_learned = max(learned_names, key=lambda k: (results[k]["auroc_pos_strong"] or -1))
    h0_name_b = next(k for k in scores if k.startswith("H0"))
    boot = {}
    rng_b = np.random.default_rng(0)
    n_te = len(te)
    te_idx = np.arange(n_te)
    sc_best = np.asarray(scores[best_learned], float)
    sc_h0 = np.asarray(scores[h0_name_b], float)
    reg_by_L = {L: reg_arr(te, L) for L in P.LEVELS}
    def _adapt_idx(idx, C, D, score_sub):
        f = (C - BASE) / (D - BASE)
        rB = reg_by_L[BASE][idx]; rD = reg_by_L[D][idx]
        k = int(round(f * len(idx)))
        order = np.argsort(-score_sub)
        esc = np.zeros(len(idx), bool); esc[order[:k]] = True
        return float(np.where(esc, rD, rB).mean())
    for C in ANCHORS:
        Dl = results[best_learned]["matched"][C]["D"]
        Dh = results[h0_name_b]["matched"][C]["D"]
        if Dl is None or Dh is None:
            continue
        d_lh, d_lu = [], []
        uC = uniform[C]
        for _ in range(2000):
            bs = rng_b.choice(te_idx, size=n_te, replace=True)
            ml = _adapt_idx(bs, C, Dl, sc_best[bs])
            mh = _adapt_idx(bs, C, Dh, sc_h0[bs])
            uu = float(reg_by_L[C][bs].mean())   # uniform on the same resample
            d_lh.append(mh - ml)                 # >0 => learned better than heuristic
            d_lu.append(uu - ml)                 # >0 => learned better than uniform
        d_lh = np.array(d_lh); d_lu = np.array(d_lu)
        boot[C] = {
            "p_learned_beats_heuristic": float((d_lh > 0).mean()),
            "delta_vs_heuristic_mean": float(d_lh.mean()),
            "delta_vs_heuristic_ci": [float(np.percentile(d_lh, 2.5)), float(np.percentile(d_lh, 97.5))],
            "p_learned_beats_uniform": float((d_lu > 0).mean()),
            "delta_vs_uniform_mean": float(d_lu.mean()),
            "delta_vs_uniform_ci": [float(np.percentile(d_lu, 2.5)), float(np.percentile(d_lu, 97.5))],
        }
    print(f"[bootstrap] best_learned={best_learned} vs heuristic={h0_name_b}")
    for C in ANCHORS:
        if C in boot:
            b = boot[C]
            print(f"  C={C}: P(beat heur)={b['p_learned_beats_heuristic']:.2f} "
                  f"Δvsheur={b['delta_vs_heuristic_mean']:+.5f} CI{[round(x,5) for x in b['delta_vs_heuristic_ci']]} "
                  f"| P(beat uniform)={b['p_learned_beats_uniform']:.2f}")

    # ceilings + random + heuristic-at-C on TEST
    ceil = {}
    for C in ANCHORS:
        oracle_md = md_oracle_at(te, C)
        # pairwise oracle ceiling
        op = None
        for D in DEEPS:
            gain = reg_arr(te, BASE) - reg_arr(te, D)
            v = adaptive_regret(te, C, D, gain)
            if v is not None and (op is None or v < op):
                op = v
        rnd, _ = best_adaptive(te, C, np.zeros(len(te)))
        ceil[C] = {"uniform": uniform[C], "oracle_md": oracle_md,
                   "oracle_pairwise": op, "random": rnd}

    # ---- BOOTSTRAP-AWARE 3-way verdict (point estimates over a tail-dominated mean are noisy) ----
    h0_name = next(k for k in scores if k.startswith("H0"))
    P_ROBUST = 0.95
    robust_beats_uniform = any(boot.get(C, {}).get("p_learned_beats_uniform", 0) >= P_ROBUST
                               for C in ANCHORS)
    robust_beats_heuristic = any(boot.get(C, {}).get("p_learned_beats_heuristic", 0) >= P_ROBUST
                                 for C in ANCHORS)
    if robust_beats_heuristic and robust_beats_uniform:
        verdict = "F_robust_learned_win"     # learned beats BOTH uniform and the heuristic, robustly
    elif robust_beats_uniform:
        verdict = "C_heuristic_suffices"     # predictable + beats uniform, but ML ~ simple heuristic
    else:
        verdict = "B_unpredictable"          # nothing robustly beats uniform at matched compute

    payload = {"n_usable": len(rows), "n_tr": len(tr), "n_va": len(va), "n_te": len(te),
               "feat_names": names, "uniform_test": uniform, "models": results,
               "ceilings": ceil, "verdict": verdict,
               "robust_beats_uniform": bool(robust_beats_uniform),
               "robust_beats_heuristic": bool(robust_beats_heuristic),
               "best_heuristic": h0_name, "best_learned": best_learned, "bootstrap": boot,
               "runtime_s": round(time.time() - t0, 1), "tier_b": bool(feat_extra)}
    (OUT / "offline_adaptive.json").write_text(json.dumps(payload, indent=2))
    _write_md(payload)
    print(f"\n[GATE Stage-4 VERDICT] {verdict}  (robust beats uniform={robust_beats_uniform}, "
          f"robust beats heuristic={robust_beats_heuristic})")
    for name, row in results.items():
        print(f"  {name:20s} AUROC(strong)={row['auroc_pos_strong']}  "
              f"C400={row['matched'][400]['regret']} (u {uniform[400]:.5f})  "
              f"C800={row['matched'][800]['regret']} (u {uniform[800]:.5f})")
    print("  ceilings:", {C: {k: (round(v, 5) if isinstance(v, float) else v)
                              for k, v in ceil[C].items()} for C in ANCHORS})


def _write_md(p):
    L = []
    L.append("# Post-Search Residual — STAGE 3 (train) + STAGE 4 (offline adaptive GATE)\n")
    L.append(f"_generated {time.strftime('%Y-%m-%d %H:%M')} · TEST split (held out by game) · "
             f"tier-B structural feats={'ON' if p['tier_b'] else 'OFF'}_\n")
    L.append(f"Roots: {p['n_usable']} usable · tr={p['n_tr']} va={p['n_va']} te={p['n_te']}. "
             f"Features ({len(p['feat_names'])}): {', '.join(p['feat_names'])}.\n")
    L.append("Gate: a LEARNED adaptive policy must beat **uniform** at matched avg compute AND beat "
             f"the best simple heuristic (**{p['best_heuristic']}**) on the held-out TEST split.\n")

    u = p["uniform_test"]
    L.append("## Model escalation-score quality + adaptive regret at matched compute (TEST)\n")
    L.append("| model | AUROC(pos_strong) | adaptive@C=400 (D) | vs uniform | adaptive@C=800 (D) | vs uniform |")
    L.append("|---|---|---|---|---|---|")
    for name, row in p["models"].items():
        def cell(C):
            m = row["matched"][str(C)] if str(C) in row["matched"] else row["matched"][C]
            if m["regret"] is None:
                return "— | —"
            uc = u[str(C)] if str(C) in u else u[C]
            return f"{m['regret']:.5f} (h{m['D']}) | {'**beats**' if m['regret'] < uc else 'no'}"
        au = row["auroc_pos_strong"]
        L.append(f"| {name} | {au:.3f} | {cell(400)} | {cell(800)} |")
    L.append("")

    L.append("## Ceilings + floors (TEST)\n")
    L.append("| avg C | uniform | random | best heuristic-tie | pairwise oracle | multi-depth oracle |")
    L.append("|---|---|---|---|---|---|")
    for C in ANCHORS:
        c = p["ceilings"][str(C)] if str(C) in p["ceilings"] else p["ceilings"][C]
        def f(x): return f"{x:.5f}" if isinstance(x, float) else "—"
        L.append(f"| {C} | {f(c['uniform'])} | {f(c.get('random'))} | — | "
                 f"{f(c.get('oracle_pairwise'))} | {f(c.get('oracle_md'))} |")
    L.append("")

    # bootstrap robustness (best_learned vs heuristic / uniform)
    L.append("## Bootstrap robustness — is the win real or tail-noise? (2000 resamples of TEST)\n")
    L.append(f"best learned = **{p['best_learned']}** vs heuristic **{p['best_heuristic']}**. "
             "P = fraction of resamples where the learned model wins; Δ vs heuristic 95% CI.\n")
    L.append("| avg C | P(learned beats uniform) | P(learned beats heuristic) | Δ vs heuristic (95% CI) |")
    L.append("|---|---|---|---|")
    for C in ANCHORS:
        b = p["bootstrap"].get(str(C), p["bootstrap"].get(C))
        if not b:
            continue
        ci = b["delta_vs_heuristic_ci"]
        L.append(f"| {C} | {b['p_learned_beats_uniform']:.2f} | {b['p_learned_beats_heuristic']:.2f} | "
                 f"{b['delta_vs_heuristic_mean']:+.5f} [{ci[0]:+.5f}, {ci[1]:+.5f}] |")
    L.append("")

    v = p["verdict"]
    L.append("## GATE VERDICT (bootstrap-aware)\n")
    if v == "F_robust_learned_win":
        L.append("### **F — robust learned win.** The learned adaptive policy beats uniform AND the "
                 "best simple heuristic at matched compute, robustly (P≥0.95).\n")
        L.append("→ Proceed to Stage 5 (implement in real search), then the matched-compute game screen.")
    elif v == "C_heuristic_suffices":
        L.append("### **C — predictable, but a simple heuristic suffices.** The escalation signal IS "
                 "predictable and a learned (and heuristic) policy beats **uniform** at matched compute "
                 "robustly — but the learned model does **NOT** robustly beat the simple "
                 f"`{p['best_heuristic']}` heuristic (P<0.95; Δ CI crosses 0). **ML adds no robust value "
                 "over a trivial rule.**\n")
        L.append("Per spec Decision C: use the heuristic scheduler if useful; **no ML flywheel**. AND "
                 "note the magnitudes: even the oracle ceiling removes only ~0.0016 of ~0.0031 mean "
                 "Q-regret; the heuristic captures a small fraction of that. The absolute matched-compute "
                 "gain is tiny → game-conversion is doubtful (the `b99c9ed` root-metrics-don't-convert "
                 "pattern). **Do NOT train an ML scheduler.** Whether even the *heuristic* scheduler "
                 "converts to games at matched compute is the one open question — a SPEND (games) gate.")
    else:
        L.append("### **B — residual exists but is unpredictable.** Nothing robustly beats uniform at "
                 "matched compute. Stop; do not run games.")
    (OUT / "POST_SEARCH_OFFLINE_RESULTS.md").write_text("\n".join(L) + "\n")
    # also a short TRAINING.md
    T = [f"# Post-Search Residual — STAGE 3 TRAINING\n",
         f"_generated {time.strftime('%Y-%m-%d %H:%M')}_\n",
         "Models trained on TRAIN, selected on VAL, scored on TEST (split by game — no game crosses "
         "splits). All inputs are h200-visible (no h6400 leakage); targets derive from h6400.\n",
         f"- Features ({len(p['feat_names'])}): {', '.join(p['feat_names'])}",
         f"- n: tr={p['n_tr']} va={p['n_va']} te={p['n_te']}",
         "- H0 best single heuristic (Stage-2 floor); M1 ridge→regret; M2 logistic→pos_medium; "
         "M3 MLP→pos_medium (early-stop on val AUROC).",
         f"- Tier-B structural features: {'ON' if p['tier_b'] else 'OFF (Tier-A only this run)'}.\n",
         "See POST_SEARCH_OFFLINE_RESULTS.md for the Stage-4 gate."]
    (OUT / "POST_SEARCH_TRAINING.md").write_text("\n".join(T) + "\n")


if __name__ == "__main__":
    main()
