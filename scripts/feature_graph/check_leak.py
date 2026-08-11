#!/usr/bin/env python3
"""Robustness checks before trusting the Stage-4 offline pass:
1. LEAK SCAN: max |Pearson corr| of any single feature with oracle_q (a ~1.0 = label leak).
   Also assert is_teacher_best / oracle_q are NOT among the feat columns.
2. NEGATIVE CONTROLS: refit ridge_pointwise[all] on (a) globally-shuffled oracle_q and
   (b) within-group-shuffled oracle_q, eval on test. A real signal must COLLAPSE to ~leaf
   or worse under both; if it still 'beats' the leaf, the gain is a metric/harness artifact.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "feature_graph"))
import eval_lib as EL
RNG = np.random.default_rng(7)

d = EL.load_rows()
names = d["feat_names"]; feat = d["feat"]; oq = d["oracle_q"].astype(np.float64)
n_rows = feat.shape[0]

# ---- 1. leak scan
print("== LEAK SCAN ==")
print("feat has", feat.shape[1], "cols; label/aux cols present in npz but NOT in feat:",
      [k for k in ("oracle_q", "is_teacher_best", "leaf_q") if k not in names])
cors = []
for i, nm in enumerate(names):
    x = feat[:, i].astype(np.float64)
    if x.std() < 1e-9:
        cors.append((0.0, nm)); continue
    c = np.corrcoef(x, oq)[0, 1]
    cors.append((abs(c), nm))
cors.sort(reverse=True)
print("top-5 |corr(feat, oracle_q)|:")
for c, nm in cors[:5]:
    print(f"   {c:.3f}  {nm}")
print(f"  max single-feature |corr| = {cors[0][0]:.3f}  (>0.97 would signal a leak)")

# ---- shared eval helpers
tr_m, va_m, te_m = EL.seed_split(d["game_seed"])
te_groups = EL.make_groups(d, te_m)
te_rows = np.flatnonzero(te_m)
cols = EL.tier_columns(names)["all"]
mu = feat[tr_m][:, cols].mean(0); sd = feat[tr_m][:, cols].std(0); sd[sd < 1e-8] = 1.0
def std(X): return (X - mu) / sd
def ridge(X, y, lam=10.0):
    A = X.T @ X + lam * np.eye(X.shape[1]); return np.linalg.solve(A, X.T @ y)
def eval_score(score_vec):
    s = np.full(n_rows, -1e9); s[te_rows] = score_vec
    ev = EL.group_eval(te_groups, s)
    return EL.summarize(ev), EL.summarize(ev, EL.decisive_mask(ev))

# leaf reference
ovl, dec = eval_score(d["leaf_q"][te_rows])
print("\n== B0 leaf (reference) ==")
print(f"  overall regret={ovl['regret_mean']} top1={ovl['top1']}  | decisive regret={dec['regret_mean']}")

# real model
w = ridge(std(feat[tr_m][:, cols]), oq[tr_m])
ovl, dec = eval_score(std(feat[te_rows][:, cols]) @ w)
print("== ridge_pointwise[all] REAL labels ==")
print(f"  overall regret={ovl['regret_mean']} top1={ovl['top1']}  | decisive regret={dec['regret_mean']}")

# control A: global shuffle of oracle_q (train only)
yg = oq.copy(); idx = np.flatnonzero(tr_m); yg_tr = yg[idx].copy(); RNG.shuffle(yg_tr)
w = ridge(std(feat[tr_m][:, cols]), yg_tr)
ovl, dec = eval_score(std(feat[te_rows][:, cols]) @ w)
print("== NEG CONTROL A: global-shuffled train labels ==")
print(f"  overall regret={ovl['regret_mean']} top1={ovl['top1']}  | decisive regret={dec['regret_mean']}")

# control B: within-group shuffle of oracle_q (train only) — destroys which child is best
yb = oq.copy()
gid = d["group_id"]
tr_idx = np.flatnonzero(tr_m)
order = np.argsort(gid[tr_idx], kind="stable")
gs = gid[tr_idx][order]; rs = tr_idx[order]
start = 0
for i in range(1, len(gs) + 1):
    if i == len(gs) or gs[i] != gs[start]:
        r = rs[start:i]
        vals = yb[r].copy(); RNG.shuffle(vals); yb[r] = vals
        start = i
w = ridge(std(feat[tr_m][:, cols]), yb[tr_m])
ovl, dec = eval_score(std(feat[te_rows][:, cols]) @ w)
print("== NEG CONTROL B: within-group-shuffled train labels ==")
print(f"  overall regret={ovl['regret_mean']} top1={ovl['top1']}  | decisive regret={dec['regret_mean']}")
print("\nINTERPRETATION: real should beat leaf; BOTH controls should be ~leaf or WORSE.")
