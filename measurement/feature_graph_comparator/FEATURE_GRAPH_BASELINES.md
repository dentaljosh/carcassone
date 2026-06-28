# Feature-Graph Action Comparator — BASELINES (Stage 2)

**Status:** computed · 2026-06-28 · driver `scripts/feature_graph/run_offline.py` · held-out TEST groups=1509
All metrics are per-sibling-set selection metrics (see `eval_lib.py`). Lower regret = better.

## Baseline definitions & results (TEST)

| baseline | what it scores children by | overall regret | top1 | τ | decisive regret |
|---|---|---|---|---|---|
| **B0 v2.9 leaf** | `leaf_q` (frozen Bmild_cap8) | 0.02891 | 0.4639 | 0.9027 | 0.14726 |
| **B3 linear** (ridge pointwise, all-feat) | `w·feat` fit to `oracle_q`, λ=10 | 0.01790 | 0.5335 | 0.5302 | 0.08296 |
| **B3 linear** (ridge, Tier-1 only) | leaf-components only | 0.02668 | 0.4818 | 0.8186 | 0.12772 |
| **B4 small MLP** | 2×64 ReLU residual MLP (best α) | 0.01870 | 0.5162 | 0.4896 | 0.08509 |

> B0 is the **binding baseline** — the gate is "beat the v2.9 leaf." Its numbers reproduce the known
> leaf audit (overall regret 0.0289, decisive 0.147, top1 0.464, τ 0.903) exactly, confirming the
> harness scores the leaf correctly.

## B1 / B2 (old scalar value net) — deferred, not binding

B1 (old neural value alone) and B2 (old value + α·leaf) require a GPU pass running the champion
`flywheel_residual_attempt2/iter8.pt` value head over each child's CNN encoding. They are **not run
here** because:
- The Value/Search autopsy (`b99c9ed`) already established the old scalar value head is **inert**
  under search and weak as a sibling ranker; B1 is confirmatory, not the bar to clear.
- The bar to clear is **B0 (v2.9 leaf)**, which the leaf already wins against the old net.
- This pilot's question is *representation*, so the meaningful contrast is **handcrafted feature/action
  models vs the leaf**, both net-free.

If the gate had been borderline, B1/B2 would be added on the existing `dataset_v29_h6400/rows.npz`
child_obs subset (4,000 groups). It is not borderline.

## B3 pairwise-logistic (C1) — implementation note

The pairwise-logistic linear comparator (C1/B3 in the brief) was coded but **skipped at runtime: the
venv has no `scikit-learn`**. The **ridge pointwise linear** model above IS a linear scoring function
(`score = w·feat`) and stands in for the linear comparator — it establishes the linear result
cleanly. Pairwise-logistic can be added (numpy fallback or `pip install scikit-learn`) if a
ranking-loss linear variant is wanted; it is not expected to change the gate verdict.

## Robustness of the baseline comparison (leak + negative controls)

`scripts/feature_graph/check_leak.py` (results in `FEATURE_GRAPH_OFFLINE_RESULTS.md`):
- **No label leak.** Max single-feature |corr| with `oracle_q` = 0.996 = `T1_leaf_q_tanh` (the leaf
  score itself, expected); label columns are not in `feat`.
- **Negative controls collapse.** Refitting B3-linear on globally-shuffled labels → regret 0.144 /
  top1 0.066; within-group-shuffled → 0.0566 / 0.248. Both fall **below** the leaf, so the real
  model's win is genuine signal, not a metric artifact.
