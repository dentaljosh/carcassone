#!/usr/bin/env python3
"""Post-Search Residual Pilot — Stage 2: baselines + ORACLE adaptive-compute gate (the make-or-break).

A perfect oracle (escalates exactly the roots with the largest true regret-reduction) is the upper
bound on ANY escalation predictor. If the oracle frontier barely beats uniform search at matched
average compute -> Decision A (no adaptive-compute opportunity), stop before training/games.

Computes, on the held-out-agnostic full sample (this is baselines, not a learned model -> no split):
  - positive rates (how often is h200 materially wrong) + regret distribution + concentration
  - uniform curve: mean regret at avg-sims in {200,400,800,1600,3200} (6400 = 0 by construction)
  - oracle / random / heuristic(entropy, low top2-gap, low top-share, high legal_n) escalation frontiers
  - matched-average-compute comparison table at anchors {400, 800, 1600}

Writes POST_SEARCH_BASELINES.md + baselines.json.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "post_search_residual"))
import psr_lib as P                                       # noqa: E402

OUT = REPO / "measurement" / "post_search_residual"
DATA = OUT / "data"
BASE = 200
DEEPS = [800, 1600, 3200]
ANCHORS = [400, 800, 1600]
BUDGETS = [300, 400, 600, 800, 1200]


def _escalation_frontier(rows, D, score, fracs):
    """Escalate top-f roots (by `score`, desc) from BASE to D. Returns list of
    (avg_compute, mean_regret) over fracs. score: np.array aligned to rows (higher->escalate)."""
    rB = P.regret_array(rows, BASE)
    rD = P.regret_array(rows, D)
    order = np.argsort(-score)           # highest score first
    n = len(rows)
    out = []
    for f in fracs:
        k = int(round(f * n))
        esc = np.zeros(n, bool)
        esc[order[:k]] = True
        avg = BASE + (k / n) * (D - BASE)
        reg = float(np.where(esc, rD, rB).mean())
        out.append((avg, reg))
    return out


def _oracle_gain(rows, D):
    return P.regret_array(rows, BASE) - P.regret_array(rows, D)   # true reduction


def _adaptive_regret_at(rows, C, D, score):
    """Mean regret of escalating BASE->D for exactly the fraction that yields avg-compute==C."""
    if D <= BASE:
        return None
    f = (C - BASE) / (D - BASE)
    if not (0.0 <= f <= 1.0):
        return None
    rB = P.regret_array(rows, BASE)
    rD = P.regret_array(rows, D)
    order = np.argsort(-score)
    n = len(rows)
    k = int(round(f * n))
    esc = np.zeros(n, bool)
    esc[order[:k]] = True
    return float(np.where(esc, rD, rB).mean())


def _uniform_interp(rows, C):
    """Linear-in-sims interp of the measured uniform mean-regret curve at avg-compute C."""
    xs = P.LEVELS
    ys = [float(P.regret_array(rows, L).mean()) for L in xs]
    return float(np.interp(C, xs, ys))


def _multidepth_oracle_frontier(rows):
    """TRUE upper bound on adaptive compute: route EACH root to ANY level minimizing mean regret
    under a global compute budget. Lagrangian sweep — for price lambda (regret per sim), each root
    picks level argmin_L (regret_L + lambda*compute_L); traces the optimal (avg_compute, mean_regret)
    Pareto frontier (tight for the fractional relaxation, ~exact at this n). Returns sorted points."""
    levels = np.array(P.LEVELS, float)
    R = np.array([[r["regret"][L] for L in P.LEVELS] for r in rows], float)  # n x 6
    good = ~np.isnan(R).any(axis=1)
    R = R[good]
    lambdas = np.concatenate([[0.0], np.geomspace(1e-6, 1.0, 400)])
    pts = []
    for lam in lambdas:
        cost = R + lam * levels[None, :]      # n x 6
        pick = cost.argmin(axis=1)            # per-root chosen level index
        avg_c = float(levels[pick].mean())
        avg_r = float(R[np.arange(len(R)), pick].mean())
        pts.append((avg_c, avg_r))
    pts.sort()
    # dedup by compute keeping min regret
    out = {}
    for c, r in pts:
        if c not in out or r < out[c]:
            out[c] = r
    return sorted(out.items())


def _oracle_md_at(frontier, C):
    """Interp the multidepth-oracle frontier regret at avg-compute C."""
    xs = [c for c, _ in frontier]; ys = [r for _, r in frontier]
    if C < xs[0] or C > xs[-1]:
        return None
    return float(np.interp(C, xs, ys))


def main():
    t0 = time.time()
    path = DATA / "roots_adaptive.jsonl"
    rows = P.load_roots(path)
    n = len(rows)
    print(f"[load] {n} roots from {path}")

    # ---------- positive rates / regret distribution ----------
    r200 = P.regret_array(rows, BASE)
    ps = np.array([r["pos_strong"] for r in rows])
    pm = np.array([r["pos_medium"] for r in rows])
    neg = np.array([r["negative"] for r in rows])
    agree = np.array([r["agree_200_ref"] for r in rows])
    pos_rate_strong = float(ps.mean()); pos_rate_med = float(pm.mean())
    print(f"[labels] positive_strong={pos_rate_strong:.3f} ({ps.sum()})  "
          f"positive_medium={pos_rate_med:.3f} ({pm.sum()})  negative={neg.mean():.3f}  "
          f"h200==h6400 top agree={agree.mean():.3f}")

    # regret concentration: fraction of total h200 regret held by the top-k% of roots
    order = np.argsort(-r200)
    tot = r200.sum()
    conc = {}
    for kpct in [5, 10, 20, 50]:
        k = max(1, int(kpct / 100 * n))
        conc[kpct] = float(r200[order[:k]].sum() / tot) if tot > 0 else 0.0
    print(f"[concentration] top5%={conc[5]:.2f} top10%={conc[10]:.2f} "
          f"top20%={conc[20]:.2f} top50%={conc[50]:.2f} of total h200 regret")

    # uniform curve
    uniform = {L: float(P.regret_array(rows, L).mean()) for L in P.LEVELS}
    print("[uniform] mean regret:", {L: round(v, 5) for L, v in uniform.items()})

    # ---------- escalation scores ----------
    ent = np.array([r["entropy200"] for r in rows])
    neg_top2 = -np.array([r["top2_q_gap200"] for r in rows])   # low gap -> escalate
    neg_share = -np.array([r["top_share200"] for r in rows])   # low top-share -> escalate
    legal = np.array([r["legal_n"] for r in rows], float)
    heuristics = {"entropy": ent, "low_top2gap": neg_top2, "low_top_share": neg_share,
                  "legal_n": legal}

    # ---------- frontiers (for the markdown plot table) ----------
    fracs = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]
    frontiers = {}
    for D in DEEPS:
        gain = _oracle_gain(rows, D)
        frontiers[D] = {
            "oracle": _escalation_frontier(rows, D, gain, fracs),
            "random": _escalation_frontier(rows, D, np.zeros(n), fracs),  # rank arbitrary
            "entropy": _escalation_frontier(rows, D, ent, fracs),
        }
        # random as a true average line (escalate random subset -> linear blend)
        rB = float(P.regret_array(rows, BASE).mean()); rD = float(P.regret_array(rows, D).mean())
        frontiers[D]["random_line"] = [(BASE + f * (D - BASE), (1 - f) * rB + f * rD) for f in fracs]

    # ---------- multi-depth oracle (TRUE upper bound) ----------
    md_frontier = _multidepth_oracle_frontier(rows)

    # ---------- matched-compute comparison ----------
    table = {}
    for C in ANCHORS:
        uC = uniform[C]
        row = {"uniform": uC}
        # pairwise oracle (escalate 200->D), best over D
        best_pair = None; best_pair_D = None
        for D in DEEPS:
            if D < C:
                continue
            o = _adaptive_regret_at(rows, C, D, _oracle_gain(rows, D))
            if o is not None and (best_pair is None or o < best_pair):
                best_pair, best_pair_D = o, D
        # multi-depth oracle (true ceiling) at C
        o_md = _oracle_md_at(md_frontier, C)
        row["oracle_pairwise"] = best_pair; row["oracle_pairwise_D"] = best_pair_D
        row["oracle_md"] = o_md
        # the operative oracle = the better (lower regret) of the two ceilings
        cand = [x for x in (best_pair, o_md) if x is not None]
        best_oracle = min(cand) if cand else None
        best_oracle_D = best_pair_D if (best_oracle == best_pair) else "multi"
        row["oracle"] = best_oracle; row["oracle_D"] = best_oracle_D
        # best heuristic (over name and D)
        best_h = None; best_h_name = None; best_h_D = None
        for hname, hs in heuristics.items():
            for D in DEEPS:
                if D < C:
                    continue
                v = _adaptive_regret_at(rows, C, D, hs)
                if v is not None and (best_h is None or v < best_h):
                    best_h, best_h_name, best_h_D = v, hname, D
        row["heuristic"] = best_h; row["heuristic_name"] = best_h_name; row["heuristic_D"] = best_h_D
        # random at C (escalate an arbitrary subset to a concrete D)
        Du = best_pair_D or DEEPS[-1]
        row["random"] = _adaptive_regret_at(rows, C, Du, np.zeros(n))
        # deltas
        row["oracle_vs_uniform_abs"] = (uC - best_oracle) if best_oracle is not None else None
        row["oracle_vs_uniform_pct"] = (100 * (uC - best_oracle) / uC) if (best_oracle and uC) else None
        row["oracle_vs_heuristic_abs"] = (best_h - best_oracle) if (best_h is not None and best_oracle is not None) else None
        table[C] = row

    # budget sweep (uniform interp vs best-oracle) for the markdown
    sweep = {}
    for C in BUDGETS:
        ui = _uniform_interp(rows, C)
        best_o = _oracle_md_at(md_frontier, C)        # multi-depth ceiling
        for D in DEEPS:                               # ... or a pairwise escalation if better
            o = _adaptive_regret_at(rows, C, D, _oracle_gain(rows, D))
            if o is not None and (best_o is None or o < best_o):
                best_o = o
        sweep[C] = {"uniform_interp": ui, "oracle": best_o,
                    "oracle_vs_uniform_pct": (100 * (ui - best_o) / ui) if (best_o and ui) else None}

    # ---------- gate verdict ----------
    # PASS if oracle beats uniform at matched compute by a meaningful margin at >=1 anchor.
    # "meaningful" = >= 15% relative AND >= 0.002 absolute (about 1 sigma of mean regret here).
    gate_hits = []
    for C in ANCHORS:
        r = table[C]
        if r["oracle"] is None:
            continue
        rel = r["oracle_vs_uniform_pct"]; ab = r["oracle_vs_uniform_abs"]
        if rel is not None and rel >= 15.0 and ab is not None and ab >= 0.002:
            gate_hits.append((C, rel, ab))
    gate_pass = len(gate_hits) > 0

    payload = {
        "n_roots": n, "runtime_s": round(time.time() - t0, 1),
        "pos_rate_strong": pos_rate_strong, "pos_rate_medium": pos_rate_med,
        "n_pos_strong": int(ps.sum()), "n_pos_medium": int(pm.sum()),
        "negative_rate": float(neg.mean()), "agree_200_6400": float(agree.mean()),
        "regret_concentration": conc,
        "uniform_curve": uniform,
        "matched_compute": table, "budget_sweep": sweep,
        "multidepth_oracle_frontier": [[round(c, 1), round(r, 6)] for c, r in md_frontier],
        "frontiers": {str(D): {k: [[round(a, 1), round(b, 6)] for a, b in v]
                               for k, v in fr.items()} for D, fr in frontiers.items()},
        "gate_pass": gate_pass, "gate_hits": gate_hits,
        "gate_rule": "oracle beats uniform at matched avg-compute by >=15% rel AND >=0.002 abs at >=1 anchor",
    }
    (OUT / "baselines.json").write_text(json.dumps(payload, indent=2))
    _write_md(payload, rows)
    print(f"\n[GATE] {'PASS' if gate_pass else 'FAIL (Decision A)'}  hits={gate_hits}")
    print(f"[write] {OUT/'POST_SEARCH_BASELINES.md'}")


def _write_md(p, rows):
    L = []
    L.append("# Post-Search Residual — STAGE 2 BASELINES + ORACLE ADAPTIVE-COMPUTE GATE\n")
    L.append(f"_generated {time.strftime('%Y-%m-%d %H:%M')} · net-free · frozen v2.9 leaf · "
             f"{p['n_roots']} roots (Phase-A greedy-self-play distribution)_\n")
    L.append("**The make-or-break gate.** A perfect oracle (escalates exactly the roots with the "
             "largest TRUE regret-reduction) upper-bounds any predictor. If it barely beats uniform "
             "at matched average compute → **Decision A**, no adaptive-compute opportunity.\n")

    L.append("## How often is h200 materially wrong vs h6400?\n")
    L.append(f"- **positive_strong** (q_gap≥0.02 ∧ regret(h200)≥0.02): "
             f"**{p['pos_rate_strong']*100:.1f}%** ({p['n_pos_strong']} roots)")
    L.append(f"- **positive_medium** (q_gap≥0.01 ∧ regret(h200)≥0.01): "
             f"**{p['pos_rate_medium']*100:.1f}%** ({p['n_pos_medium']} roots)")
    L.append(f"- negative (h200 fine / agrees / h6400 near-tie): {p['negative_rate']*100:.1f}%")
    L.append(f"- h200 top move == h6400 top move: {p['agree_200_6400']*100:.1f}%\n")

    L.append("## Is the residual concentrated enough to predict?\n")
    c = p["regret_concentration"]
    cg = lambda k: c.get(k, c.get(str(k)))          # int or str keys (in-mem vs json reload)
    L.append(f"Share of TOTAL h200 regret held by the worst roots: "
             f"top-5%=**{cg(5)*100:.0f}%**, top-10%=**{cg(10)*100:.0f}%**, "
             f"top-20%=**{cg(20)*100:.0f}%**, top-50%={cg(50)*100:.0f}%.")
    L.append("_(High concentration → adaptive compute can win by routing deep search to the few "
             "bad roots. Diffuse regret → uniform is near-optimal → Decision A.)_\n")

    L.append("## Uniform compute curve (mean regret vs avg sims)\n")
    L.append("| sims | 200 | 400 | 800 | 1600 | 3200 | 6400 |")
    L.append("|---|---|---|---|---|---|---|")
    u = p["uniform_curve"]
    L.append("| mean regret | " + " | ".join(f"{u[str(x)]:.5f}" if str(x) in u else f"{u[x]:.5f}"
             for x in P.LEVELS) + " |")
    L.append("")

    L.append("## Matched-average-compute comparison (lower regret = better)\n")
    L.append("oracle = best of {pairwise escalate-200→D, multi-depth route-each-root} = the *ceiling* "
             "on any escalation predictor. heuristic = best simple rule (entropy / low-gap / low-share "
             "/ legal-n) = the bar a learned model must clear.\n")
    L.append("| avg compute C | uniform h(C) | random | best heuristic | pairwise oracle | multi-depth oracle | **ORACLE** | Δ vs uniform |")
    L.append("|---|---|---|---|---|---|---|---|")
    for C in ANCHORS:
        r = p["matched_compute"][str(C)] if str(C) in p["matched_compute"] else p["matched_compute"][C]
        def f(x): return f"{x:.5f}" if isinstance(x, (int, float)) and x is not None else "—"
        dv = (f"{r['oracle_vs_uniform_abs']:+.5f} ({r['oracle_vs_uniform_pct']:+.1f}%)"
              if r.get("oracle_vs_uniform_abs") is not None else "—")
        L.append(f"| {C} | {f(r['uniform'])} | {f(r.get('random'))} | "
                 f"{f(r.get('heuristic'))} ({r.get('heuristic_name')}→{r.get('heuristic_D')}) | "
                 f"{f(r.get('oracle_pairwise'))} (→{r.get('oracle_pairwise_D')}) | "
                 f"{f(r.get('oracle_md'))} | **{f(r['oracle'])}** (→{r.get('oracle_D')}) | {dv} |")
    L.append("")

    L.append("## Oracle vs uniform across a finer budget sweep (uniform = linear-interp; oracle = multi-depth ceiling)\n")
    L.append("| avg compute | uniform(interp) | best oracle | Δ vs uniform |")
    L.append("|---|---|---|---|")
    for C in BUDGETS:
        s = p["budget_sweep"][str(C)] if str(C) in p["budget_sweep"] else p["budget_sweep"][C]
        pc = f"{s['oracle_vs_uniform_pct']:+.1f}%" if s.get("oracle_vs_uniform_pct") is not None else "—"
        ov = f"{s['oracle']:.5f}" if s.get("oracle") is not None else "—"
        L.append(f"| {C} | {s['uniform_interp']:.5f} | {ov} | {pc} |")
    L.append("")

    gate = p["gate_pass"]
    L.append("## GATE VERDICT\n")
    L.append(f"Rule: _{p['gate_rule']}_.\n")
    L.append(f"### **{'PASS — adaptive-compute opportunity EXISTS' if gate else 'FAIL — Decision A (no opportunity)'}**\n")
    if gate:
        L.append("Anchors where oracle beats uniform meaningfully: " +
                 ", ".join(f"C={c} ({rel:+.1f}%, {ab:+.5f})" for c, rel, ab in p["gate_hits"]) + ".\n")
        L.append("→ Proceed to Stage 3 (train escalation predictors) — but first **broaden roots to "
                 "real MCTS-play distributions (Phase B)**; this gate ran on greedy-self-play roots.")
    else:
        L.append("The oracle — the *upper bound* on any predictor — does not beat uniform search at "
                 "matched average compute by a worthwhile margin. No learned escalation model can do "
                 "better than the oracle, so **there is no adaptive-compute opportunity to chase**. "
                 "Stop. Do not train predictors, do not run games. Write Decision A.\n")
        L.append("_Mechanism: h200's residual error vs h6400 is too diffuse (or too small) — uniform "
                 "compute is already near-optimal per-root, so concentrating compute buys little._")
    (OUT / "POST_SEARCH_BASELINES.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
