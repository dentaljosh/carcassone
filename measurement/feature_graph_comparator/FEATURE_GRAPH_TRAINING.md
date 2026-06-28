# Feature-Graph Action Comparator — TRAINING (Stage 3)

**Status:** trained · 2026-06-28 · `scripts/feature_graph/run_offline.py` (CPU, net-free, ~8 min total)
Data: `data/rows_feat.npz` (314,911 children × 50 feat). Split by game_seed 70/15/15 →
train 7,049 groups / val 1,509 / test 1,509 (no sibling set spans splits).

## Common setup
- Features standardized (μ,σ fit on TRAIN only).
- **Ablation:** every linear candidate run twice — `tier1` (context F + Tier-1 leaf-component feats
  only) vs `all` (+ Tier-2 structural/action). A win that appears only in `all` ⇒ the gain is
  **representation**, not reweighting (the pilot's headline question).
- Selection object = per-child score; group argmax = chosen child; reported on held-out TEST.

## Candidates

**C1 pairwise-linear (logistic on child_i−child_j, weighted |ΔQ|, ×3 for ΔQ≥0.02)**
Coded; skipped at runtime (no scikit-learn in venv). The linear result is covered by the ridge
pointwise linear scorer below. Add later if a ranking-loss linear variant is wanted.

**ridge pointwise → oracle_q** (linear; stands in for B3/B4-linear)
Closed-form ridge (λ=10) predicting `oracle_q`; score = prediction. Tier-1 and all-feat.

**C4 residual-ridge → (oracle_q − leaf_q)**, select by `leaf_q + α·resid`, α∈{0,.05,.1,.25,.5,1}.
α=0 reproduces B0 exactly (plumbing check ✓). Tier-1 and all-feat.

**C4 residual-MLP** — 2×64 ReLU MLP, target `oracle_q − leaf_q`, Adam lr1e-3 wd1e-5, ≤60 epochs,
**early-stop on VAL selected-child regret** (not train loss). Select by `leaf_q + α·resid`, α swept.
all-feat.

**C3 listwise-MLP** — same 2×64 MLP; per-group loss = −Σ softmax(oracle_q/0.1)·log_softmax(score);
early-stop on VAL regret; select by raw score. all-feat. This explicitly optimizes the top of the
sibling order (selection), which is why it posts the best top1 / decisive regret.

## Training observations
- α=0 (pure leaf) is reproduced bit-for-bit by every residual variant → residual blending is correct.
- For residual models, decisive-tail regret **decreases monotonically with α** (e.g. residual-ridge
  all-feat: 0.147→0.083 from α=0→1). This **reverses** the Value Resurrection Pilot's "best α=0,
  regret rises with α" — the difference is the Tier-2 feature/action representation (see ablation in
  `FEATURE_GRAPH_OFFLINE_RESULTS.md`).
- Early-stopping on VAL **regret** (not loss) matters: loss keeps falling while selection regret
  plateaus; the chosen checkpoints are the val-regret minima.
- τ (full-order rank corr) drops sharply for the strong selectors (0.90→0.53). The MLPs/regressors
  trade fine mid/low-sibling ordering for argmax accuracy — fine for selection, flagged as a risk
  for any search use that consumes the full child ordering (Stage 5 watch-item).

Full TEST metric table + α-sweeps + robustness controls → `FEATURE_GRAPH_OFFLINE_RESULTS.md`.
