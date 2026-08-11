#!/usr/bin/env python3
"""FGSR Stage 3 — BASELINES on the post-search-residual MCTS-play roots.

Reuses the residual pilot's harness VERBATIM (psr_lib.load_roots / seed_split,
run_adaptive_gate's best_adaptive / md_oracle_at / auroc / matched-compute sim).
Computes, on THIS dataset's TEST split (66 game-seeds), the baselines the FGSR
graph models must beat:

  B0  uniform h200            (the shallow floor)
  B1  uniform h800
  B2  uniform h3200
  B3  low_top2gap scheduler   score = -top2_q_gap200   <-- THE baseline to beat
  B4  phase/opening scheduler (escalate opening-heavy tail)
  B5  flat MLP over 21 Tier-B structural + h200-diag scalars (reproduce ~AUROC 0.78)
  B7  multi-depth oracle (md_oracle_at)  -- upper bound

SANITY GATE: B3 AUROC(pos_strong) on TEST must reproduce ~0.72-0.73. If not, STOP
(harness mismatch) and do NOT proceed.

Matched-compute budgets C in {300,400,600,800,1200} via best_adaptive (escalate the
top-f roots by scheduler score from h200 to the best deeper level D in {800,1600,3200}
so avg compute == C). Writes baselines.json + draft FGSR_BASELINES.md.

NET-FREE, CPU, no search, no games.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "post_search_residual"))
import psr_lib as P                                            # noqa: E402
import run_adaptive_gate as AG                                 # noqa: E402

OUT = REPO / "measurement" / "feature_graph_search_residual"
SRC = REPO / "measurement" / "post_search_residual" / "data"
ROOTS = SRC / "roots_mcts.jsonl"
FEATB = SRC / "features_mcts.jsonl"

BASE = 200
DEEPS = AG.DEEPS                       # [800, 1600, 3200]
BUDGETS = [300, 400, 600, 800, 1200]


def load():
    rows = P.load_roots(str(ROOTS))
    rows = [r for r in rows if all(np.isfinite(r["regret"][L]) for L in P.LEVELS)]
    # Tier-B structural features join by group_id
    fb = {}
    for line in FEATB.read_text().splitlines():
        if line.strip():
            o = json.loads(line)
            fb[int(o["group_id"])] = o["features"]
    return rows, fb


def featurize_b5(rows, fb, mu=None, sd=None, names=None):
    """B5 input = h200 search diagnostics (Tier-A) + the 21 Tier-B structural scalars."""
    if names is None:
        tb_keys = sorted({k for v in fb.values() for k in v})
        names = (["entropy200", "top_share200", "top2_q_gap200", "log_n_visited200",
                  "log_legal_n", "ply"] + [f"phase_{p}" for p in P.PHASES]
                 + [f"tb_{k}" for k in tb_keys])
    else:
        tb_keys = [n[3:] for n in names if n.startswith("tb_")]
    X = []
    for r in rows:
        v = [r["entropy200"], r["top_share200"], r["top2_q_gap200"],
             np.log1p(r["n_visited200"]), np.log1p(r["legal_n"]), float(r["ply"])]
        v += [1.0 if r["phase"] == p else 0.0 for p in P.PHASES]
        ev = fb.get(r["group_id"], {})
        v += [float(ev.get(k, 0.0)) for k in tb_keys]
        X.append(v)
    X = np.asarray(X, float)
    if mu is None:
        mu = X.mean(0); sd = X.std(0); sd[sd < 1e-9] = 1.0
    return (X - mu) / sd, names, mu, sd


def matched_curve(rows, score):
    """best_adaptive at each budget. score: np.array aligned to rows (higher=escalate)."""
    out = {}
    for C in BUDGETS:
        v, D = AG.best_adaptive(rows, C, score)
        out[C] = {"regret": v, "D": D}
    return out


def main():
    t0 = time.time()
    rows, fb = load()
    tr, va, te = P.seed_split(rows)
    print(f"[load] {len(rows)} roots | tr={len(tr)} va={len(va)} te={len(te)} | "
          f"test seeds={len(set(r['seed'] for r in te))}")

    yte_strong = np.array([r["pos_strong"] for r in te], float)
    yte_medium = np.array([r["pos_medium"] for r in te], float)
    uniform = {L: float(AG.reg_arr(te, L).mean()) for L in P.LEVELS}

    baselines = {}

    # ---- B0/B1/B2 uniform (constant scheduler -> no escalation; matched curve uses uniform) ----
    for tag, L in [("B0_uniform_h200", 200), ("B1_uniform_h800", 800), ("B2_uniform_h3200", 3200)]:
        baselines[tag] = {"kind": "uniform", "level": L,
                          "regret_test": uniform[L],
                          "auroc_pos_strong": None}

    # ---- B3 low_top2gap scheduler ----
    s_b3 = -np.array([r["top2_q_gap200"] for r in te], float)
    au_b3 = AG.auroc(s_b3, yte_strong)
    baselines["B3_low_top2gap"] = {
        "kind": "scheduler", "score": "neg_top2_q_gap200",
        "auroc_pos_strong": au_b3,
        "auroc_pos_medium": AG.auroc(s_b3, yte_medium),
        "matched": matched_curve(te, s_b3),
    }

    # ---- B4 phase/opening scheduler (escalate opening-heaviest; tie-broken by low top2gap) ----
    # opening roots dominate the tail -> rank opening first, then by -top2gap within
    is_open = np.array([1.0 if r["phase"] == "opening" else 0.0 for r in te])
    s_b4 = is_open * 10.0 + (-np.array([r["top2_q_gap200"] for r in te], float))
    baselines["B4_phase_opening"] = {
        "kind": "scheduler", "score": "opening_then_neg_top2gap",
        "auroc_pos_strong": AG.auroc(s_b4, yte_strong),
        "auroc_pos_medium": AG.auroc(s_b4, yte_medium),
        "matched": matched_curve(te, s_b4),
    }

    # ---- B5 flat MLP over Tier-A diag + 21 Tier-B, trained on pos_medium, early-stop val AUROC ----
    Xtr, names, mu, sd = featurize_b5(tr, fb)
    Xva, *_ = featurize_b5(va, fb, mu, sd, names)
    Xte, *_ = featurize_b5(te, fb, mu, sd, names)
    ytr_med = np.array([r["pos_medium"] for r in tr], float)
    yva_med = np.array([r["pos_medium"] for r in va], float)
    s_b5, b5_va = AG.mlp_fit_predict(Xtr, ytr_med, Xva, yva_med, Xte)
    # emit B5 per-root TEST scores (gid + g3) for the offline gate vs-B5 comparison
    DATA = OUT / "data"
    DATA.mkdir(parents=True, exist_ok=True)
    np.savez(DATA / "scores_B5.npz",
             gid=np.array([r["group_id"] for r in te], np.int64),
             g3=np.asarray(s_b5, np.float32),
             g4=np.zeros(0, np.float32), g4_aid=np.zeros(0, np.int64),
             g4_gid=np.zeros(0, np.int64))
    au_b5_strong = AG.auroc(s_b5, yte_strong)
    au_b5_med = AG.auroc(s_b5, yte_medium)
    baselines["B5_flat_mlp"] = {
        "kind": "flat_mlp", "target": "pos_medium", "n_feat": len(names),
        "feat_names": names,
        "val_auroc_pos_medium": b5_va,
        "auroc_pos_strong": au_b5_strong,
        "auroc_pos_medium": au_b5_med,
        "matched": matched_curve(te, s_b5),
    }

    # ---- B7 multi-depth oracle (upper bound) ----
    b7 = {"kind": "oracle_md", "matched": {}}
    for C in BUDGETS:
        b7["matched"][C] = {"regret": AG.md_oracle_at(te, C)}
    baselines["B7_oracle_md"] = b7

    # ---- pos_strong sanity ----
    sanity = {"B3_auroc_pos_strong": au_b3,
              "reproduced": (au_b3 is not None and 0.70 <= au_b3 <= 0.75),
              "expected_range": [0.72, 0.73],
              "B5_auroc_pos_medium": au_b5_med,
              "B5_auroc_pos_strong": au_b5_strong}

    payload = {
        "n_roots": len(rows), "n_tr": len(tr), "n_va": len(va), "n_te": len(te),
        "n_test_seeds": len(set(r["seed"] for r in te)),
        "budgets": BUDGETS, "deeps": DEEPS,
        "uniform_test": uniform,
        "baselines": baselines,
        "sanity": sanity,
        "runtime_s": round(time.time() - t0, 1),
    }
    (OUT / "baselines.json").write_text(json.dumps(payload, indent=2, default=float))
    _write_md(payload)

    print("\n=== SANITY GATE ===")
    print(f"B3 AUROC(pos_strong) = {au_b3:.4f}  (expect 0.72-0.73)  "
          f"{'REPRODUCED' if sanity['reproduced'] else '*** MISMATCH ***'}")
    print(f"B5 flat-MLP AUROC(pos_medium) = {au_b5_med:.4f} (val {b5_va:.4f}), "
          f"AUROC(pos_strong) = {au_b5_strong:.4f}")
    print("\n=== matched-compute regret (TEST) ===")
    print(f"  uniform: " + " ".join(f"h{L}={uniform[L]:.5f}" for L in [200, 800, 3200]))
    for tag in ["B3_low_top2gap", "B4_phase_opening", "B5_flat_mlp", "B7_oracle_md"]:
        b = baselines[tag]
        cells = " ".join(
            f"C{C}={b['matched'][C]['regret']:.5f}" if b["matched"][C]["regret"] is not None
            else f"C{C}=--" for C in BUDGETS)
        print(f"  {tag:18s} {cells}")
    print(f"\n[done] {time.time()-t0:.1f}s -> {OUT/'baselines.json'}")
    return sanity["reproduced"]


def _write_md(p):
    L = []
    L.append("# FGSR_BASELINES.md — Stage 3 baselines (matched-compute, TEST split)\n")
    L.append(f"_generated {time.strftime('%Y-%m-%d %H:%M')} · net-free · frozen v2.9 leaf · "
             f"TEST = {p['n_te']} roots over {p['n_test_seeds']} game-seeds "
             f"(tr={p['n_tr']} va={p['n_va']})_\n")
    s = p["sanity"]
    L.append("## SANITY GATE\n")
    L.append(f"- **B3 `low_top2gap` AUROC(pos_strong) on TEST = {s['B3_auroc_pos_strong']:.4f}** "
             f"(expected 0.72–0.73) → **{'REPRODUCED' if s['reproduced'] else 'MISMATCH — STOP'}**.")
    L.append(f"- B5 flat-MLP AUROC(pos_medium) = {s['B5_auroc_pos_medium']:.4f}, "
             f"AUROC(pos_strong) = {s['B5_auroc_pos_strong']:.4f} "
             f"(prior pilot reported ~0.78 on pos_medium).\n")

    u = p["uniform_test"]
    L.append("## Uniform compute curve (mean h6400-regret vs avg sims, TEST)\n")
    L.append("| sims | " + " | ".join(str(x) for x in P.LEVELS) + " |")
    L.append("|---|" + "---|" * len(P.LEVELS))
    L.append("| mean regret | " + " | ".join(f"{u[x]:.5f}" for x in P.LEVELS) + " |\n")

    L.append("## Matched-compute regret (lower = better) — the bar to beat is **B3**\n")
    L.append("| baseline | AUROC(strong) | " + " | ".join(f"C={C}" for C in p["budgets"]) + " |")
    L.append("|---|---|" + "---|" * len(p["budgets"]))
    order = ["B0_uniform_h200", "B1_uniform_h800", "B2_uniform_h3200",
             "B3_low_top2gap", "B4_phase_opening", "B5_flat_mlp", "B7_oracle_md"]
    for tag in order:
        b = p["baselines"][tag]
        au = b.get("auroc_pos_strong")
        au_s = f"{au:.3f}" if au is not None else "—"
        if b.get("kind") == "uniform":
            # uniform: regret only defined at its own level; show its constant
            cells = " | ".join("—" for _ in p["budgets"])
            cells = cells.replace("—", f"{b['regret_test']:.5f}", 1) if False else cells
            row = f"| {tag} (h{b['level']}={b['regret_test']:.5f}) | {au_s} | " + cells + " |"
        else:
            mm = b["matched"]
            cells = " | ".join(
                f"{mm[C]['regret']:.5f}" + (f" (h{mm[C].get('D')})" if mm[C].get('D') else "")
                if mm[C]["regret"] is not None else "—" for C in p["budgets"])
            row = f"| {tag} | {au_s} | " + cells + " |"
        L.append(row)
    L.append("")
    L.append("_B0/B1/B2 are uniform constants (no escalation); the matched-compute columns apply to "
             "schedulers (B3/B4/B5) and the oracle (B7). D = the deeper level escalated to._\n")
    (OUT / "FGSR_BASELINES.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 2)
