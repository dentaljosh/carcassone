# Gate C0 — "learnability probe" — PRE-REGISTRATION

> **Status:** PRE-REGISTERED 2026-07-23, BEFORE any learned-model τ was computed.
> Thresholds below are fixed by the Fable scoping and are **NOT** to be moved
> after seeing the result. The sanity-floor number (leaf-terms-only OLS ≈ 0.615)
> MAY be inspected before revealing the learned τ — it is a pipeline unit test,
> not the gate statistic.

## The question C0 answers

The whole learned-component program is closed (CL-039 / CL-042 / CL-059 / CL-061
/ CL-063 / CL-064). Mechanism (CL-062): deep search converges to the **leaf's**
own move-ordering, so only a better **leaf** transfers. CL-064 proved model
**capacity** is not the bottleneck — but it tested nets on an 81-channel CONV
board tensor whose small receptive field cannot even reconstruct board-spanning
farm topology. The v2.9 leaf, by contrast, IS a hand-weighted graph read-out: a
sum over components (cities / roads / farms / cloisters) of hand-crafted
per-component scores, computed over the union-find decomposition that
`flat_leaf.py` already produces per leaf.

**C0 hands a boring learner that same component decomposition + exact-solver
labels, and asks: can ANY learnable re-weighting of component-level features beat
the leaf's ordering?** Because the feature set CONTAINS the leaf's own terms, the
leaf's τ is the guaranteed floor; the only question is whether anything sits
above it.

This is the terminal, representation-independent extension of CL-039 / CL-064:
CL-064 killed the *capacity* axis on a conv representation; C0 kills (or opens)
the *representation* axis by handing the learner the leaf's OWN graph read-out.

## Corpus (fixed)

- The existing `solver_score.py` sibling-root set: `qprobe_A/probe.jsonl` JOIN
  `pool_A.jsonl` (the 10,067-root CL-033/§3A pool), filtered to **K ≤ 2**.
- **K ≤ 2 = 1,119 roots, all K = 2, all MARGINALIZED** (exact bag-expectation ==
  clairvoyant at K = 2). This is EXACTLY the CL-064 corpus (same 1,119 roots,
  0 skipped, 0 errors in that read).
- Note (verified): all 1,119 roots have **distinct deck seeds** (one K = 2
  position per greedy game) — so grouping by seed == grouping by root; a seed
  cannot span the train/test split by construction. We still fold by seed
  explicitly and assert it.
- **NO new corpus is generated for C0.** If the read lands AMBIGUOUS we REPORT an
  extension proposal with ETA + box; we do not launch it (hard line).

## Metric (fixed)

- Per root, `step1_train.group_metrics(score, solver_mover)` →
  `(solver_regret, top1, kendall_tau_b)`, oriented to the **mover's** POV
  (argmax == best move), using the **exact-solver child value** as ground truth
  (`solver_mover[a] = child_value[a]` if to_move == 0 else `-child_value[a]`).
  `kendall_tau_b` is the identical function `solver_score.py` uses (imported from
  `value_ranking_train.py`), so the number is directly comparable to the leaf's.
- Aggregate = **mean over roots** of the per-root τ (nan-mean), exactly as
  `solver_score._agg`. Same for top1 (mean) and regret (mean).
- **Reference numbers to beat/compare (CL-064 / M2 Part A, same ruler):**
  - v2.9 leaf τ = **0.6153** (the floor; leaf top1 = 0.6095, regret = 0.9508).
  - best net ever (CL-064, 25× param range) τ = **~0.17** (single ckpt 0.1686;
    per-size mean best 0.1331).

## Grouping (fixed)

- **5-fold cross-fitting, GROUPED BY DECK SEED.** No seed appears in both a
  train and a test fold (mirrors CL-063's grouping to avoid leakage). Each root's
  children go to exactly one test fold; τ on a held-out root is computed on
  children the model never trained on. Fold assignment is deterministic
  (`np.random.default_rng(0)` shuffle of the sorted unique seeds → 5 contiguous
  folds) and recorded in `results.json`.

## Learners (fixed, boring on purpose)

- **(a) Ridge / linear regression** — closed-form numpy OLS with L2 (λ swept over
  a small fixed grid; the leaf-terms-only fit uses λ→0 OLS for the floor check).
- **(b) Gradient-boosted trees** — `sklearn.ensemble.HistGradientBoostingRegressor`
  with modest, fixed hyper-parameters (no per-result tuning).
- Both predict the exact-solver child value; siblings within each held-out root
  are ranked by the prediction and scored with `group_metrics` τ.

## Feature set (fixed design)

Per child, from `flat_leaf.decompose(child.state)` + the flat scorers, all
oriented to the mover (root_player) POV = "me", opponent = "them":

- **Leaf's own terms (guarantee the floor):** `lt_base` (flat_base_score),
  `lt_bonus_self` (capped self closure bonus, cap 8), `lt_bonus_opp` (capped opp
  closure bonus, cap 8), `lt_meeple_curve` (v2.9 curve diff), and `lt_leaf_score`
  (the full `virtual_score_v2` int — a linear/step function of the first four).
  An OLS on `lt_leaf_score` alone reproduces the leaf ordering EXACTLY (monotone).
- **Raw pooled component features:** per component type (city / road / farm /
  cloister), pooled to fixed length by **owner** (me / opp / unowned) via
  sums / counts / max — component size, open-edge count, shields, closure delta,
  finished-vs-open, farm→city adjacency & finished-city counts, cloister
  completion-needed & current points.
- **Global / meeple economy:** running score diff, free-meeple counts & diff,
  placed-meeple counts, bag statistics (`_bag_stats`), k-remaining context.

The feature set MUST contain the leaf's own terms so an OLS on just those
reproduces the leaf. Exact column list is emitted to `results.json` / the cache
manifest.

## Sanity floor (REQUIRED, treated as a unit test)

Two checks, both must pass before the gate is trusted:

1. **Ironclad harness check:** cross-fit OLS on the single feature `lt_leaf_score`
   must reproduce τ = **0.6153** (to ~1e-3). A positive OLS slope preserves the
   leaf ordering exactly; any deviation means the corpus / metric / orientation
   diverged from `solver_score.py` and everything downstream is void.
2. **Leaf-terms-only floor:** cross-fit ridge/OLS on the four decomposed leaf
   terms (`lt_base, lt_bonus_self, lt_bonus_opp, lt_meeple_curve`) must land
   **τ ≈ 0.615** (free weights can only match-or-beat the hand weights on the
   quantity they parametrise; small deviations from OLS-minimises-MSE-not-τ are
   expected but must be small). If it lands far below 0.615, the feature mapping
   is broken — fix before trusting anything.

Both numbers are reported explicitly in REPORT.md.

## PRE-REGISTERED GATE (thresholds fixed in advance — DO NOT tune to the result)

Statistic = held-out (cross-fit) mean τ of the best boring learner (ridge or
GBDT) on the **full** feature set, over the 1,119 K ≤ 2 roots.

- **FIRE — learned τ ≥ 0.65** → clears CL-064's seed-spread noise (~0.05–0.10)
  with margin above the 0.6153 leaf floor → C0 FIRES: a learnable re-weighting of
  the leaf's own component read-out DOES exceed the hand-crafted ordering → fund
  C1 (a real GNN/NNUE leaf).
- **DEAD — learned τ < 0.62** → even with the leaf's OWN representation + exact
  labels, learning cannot exceed the hand-crafted ordering → the entire
  learned-leaf (Gate-C "d") direction dies; the terminal,
  representation-independent extension of CL-039 / CL-064.
- **AMBIGUOUS — 0.62 ≤ τ < 0.65** → Joshua's call (the CL-063 §6 pattern). If we
  believe more roots would resolve it, we REPORT that with an ETA + box — we do
  NOT launch the extension.

Guard: a learned τ that "fires" must be re-checked for leakage (seed spanning
folds, per-root normalisation, target echo) BEFORE it is believed. A leaked FIRE
is the worst possible outcome; when in doubt, report conservatively and flag.

## Hard lines (from the task)

- No new large solver corpus (the ~5–10K-root extension) is generated.
- No C1 (real GNN/NNUE) or C2 (deployment) work.
- No touch to the champion, production leaf, `PRODUCTION.yaml`, or any released
  hash. C0 is a standalone offline ranker scored against the solver.
- No game-playing eval, cluster/ssh job, or cloud rental.
