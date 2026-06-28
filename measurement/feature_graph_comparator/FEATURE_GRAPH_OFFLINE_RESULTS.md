# Feature-Graph Comparator — OFFLINE RESULTS (Stage 4) — GATE

**Status:** GATE **PASSES** (offline) · 2026-06-28 · TEST groups=1509 · decisive-tail n=196
Source: `scripts/feature_graph/run_offline.py` → `offline_results.json`; robustness from `check_leak.py`.
**Read with the project caveat in force:** offline sibling-ranking ≠ strength. `b99c9ed` proved root
metrics can mislead; this pass earns the right to the **Stage-5 search screen only**, not promotion.

## Primary: selected-child teacher regret (lower=better). Gate = beat B0_v29_leaf.

| model | overall regret | top1 | τ | **decisive regret** | dec top1 | ordinary regret |
|---|---|---|---|---|---|---|
| **B0_v29_leaf** | 0.02891 | 0.4639 | 0.9027 | **0.14726** | 0.000 | 0.01125 |
| ridge_pointwise[tier1] | 0.02668 | 0.4818 | 0.8186 | **0.12772** | 0.138 | 0.01159 |
| resid_ridge[tier1] α0.25 | 0.02666 | 0.4864 | 0.840 | **0.12881** | 0.122 | 0.01142 |
| **ridge_pointwise[all]** | 0.01790 | 0.5335 | 0.5302 | **0.08296** | 0.434 | 0.00819 |
| resid_ridge[all] α0.25 | 0.02117 | 0.5235 | 0.5387 | **0.10476** | 0.311 | 0.00869 |
| resid_mlp_C4[all] α0.5 | 0.01870 | 0.5162 | 0.4896 | **0.08509** | 0.413 | 0.00878 |
| **listwise_mlp_C3[all]** | **0.01712** | **0.5355** | 0.5326 | **0.07108** | **0.505** | 0.00907 |

α=0 rows omitted (they reproduce B0 exactly — residual-blend plumbing check ✓).

**Residual α-sweeps (decisive-tail regret), monotone in α:**
- tier1: 0.147 → 0.129 → 0.129 → 0.1288 → 0.1287 → 0.1277  (α=0→1) — small.
- all:   0.147 → 0.1088 → 0.1085 → 0.1048 → 0.0918 → **0.0830** — large; **best α nonzero**.

## What this says

1. **The learned feature/action comparator beats the v2.9 leaf offline** — on the *full* (non-circular)
   pool, not just the leaf-selected tail: overall regret −41% (0.0289→0.0171), top1 +9pp
   (0.464→0.535), and **ordinary-subset regret also improves** (0.01125→0.0091) — no broad regression.
   Decisive-tail regret −44% (ridge[all]) to **−52% (listwise)**; the leaf recovers 0/196 decisive
   roots by construction, the comparator recovers ~half (dec top1 0.50).
2. **The win is REPRESENTATION, not reweighting (the headline).** Tier-1 (reweighting the leaf's own
   components) buys only −13% decisive / −8% overall and keeps τ high (~0.82–0.90) — i.e. it behaves
   like the prior pilots. Adding **Tier-2 structural/action features** (contested control, open-edge
   exposure, meeple lockup/return, completed value, move semantics) drives the −44/−52% and crashes τ
   to ~0.53. So explicit Carcassonne feature/action structure carries the extra ranking signal.
3. **This reverses the Value Resurrection Pilot** (Decision B): VR found best-α=0 and net-alone τ=0.105
   on the *same* h6400 sibling labels. The only material difference is the **input representation** —
   VR used the CNN board/scalar value head; here a 50-dim handcrafted feature/action vector. VR ≈ our
   Tier-1 (small/no gain); our Tier-2 supplies the structure VR's representation lacked. **Contradiction
   resolved:** it was the representation, not learned value being hopeless.

## Robustness — the offline pass is not an artifact

`check_leak.py`:
- **No label leak.** Max single-feature |corr| with `oracle_q` = 0.996 = `T1_leaf_q_tanh` (the leaf
  score itself, the baseline-as-feature; next: leaf_total/pretransform/base — its ingredients). The
  label columns (`oracle_q`, `is_teacher_best`, `leaf_q`) are **not** in `feat`. The 0.996 is *pooled*
  between-position corr; within-sibling discrimination stays hard (leaf τ=0.90, top1=0.46).
- **Negative controls collapse below the leaf.** Refit ridge[all] on shuffled labels:
  global-shuffle → 0.144 / top1 0.066; within-group-shuffle → 0.0566 / 0.248. Both **worse** than the
  leaf while the real model beats it → the gain is genuine teacher-ranking signal, not metric framing.

## Caveats / risks carried into Stage 5

- **Offline ≠ strength.** This is exactly the metric class that misled in `b99c9ed`; net gains have
  also **washed out under deep search** before (memory `sims_washout_net_eval`). The roots are
  *greedy-self-play* positions — sibling-ranking gains there may not transfer to MCTS-play distribution.
- **τ collapse (0.90→0.53).** The strong selectors nail the argmax but order mid/low siblings worse.
  Fine for root/greedy selection; a risk for any search use that consumes the full child ordering.
  Stage-5 integration should prefer **argmax/top-of-order** use (child reranking / leaf correction on
  the slice it won), not wholesale replacement of the leaf's value ordering.
- **No pairwise-logistic (C1)** run (sklearn absent); linear result covered by ridge-pointwise.

## Gate verdict

**PASS (offline).** A cheap, net-free feature/action comparator beats the v2.9 leaf on held-out
sibling regret (full-pool −41%, decisive-tail −44/−52%, no ordinary regression), the gain is
representation-driven (Tier-1 −13% vs Tier-2-full −44%), and it survives leak + negative-control
scrutiny — answering the pilot's core question: **the scalar head was dead for lack of explicit
feature/action structure, not because learned value is hopeless.**

→ Earns the **Stage-5 search-integration screen**. Per governance, no games until search also passes.
This is a known mirage-prone juncture → **stop for review before Stage 5.**
