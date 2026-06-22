# Phase 3 — Simple-Selector Baselines vs the Exact Solver

> **What this is.** Each simple selector picks one legal action per position; we score it
> against the EXACT solver target. **K=2** uses the re-solved full per-action value map
> ([k2_childvalues.jsonl](k2_childvalues.jsonl), clairvoyant = marginalized at K=2) so *every*
> selector + rank-correlation is exact; **K=3 / K=4** use the persisted per-agent regrets.
> Source: [ACTION_AUDIT_DATASET.jsonl](ACTION_AUDIT_DATASET.jsonl). Numbers in
> [BASELINE_RESULTS.csv](BASELINE_RESULTS.csv) / `_BY_SOURCE.csv` / `_BY_DIFFICULTY.csv`.
>
> **⚠️ CORRECTED (v2).** The first pass computed per-action score/meeple/completion deltas
> ONE half-move too early — a TILES-phase action transitions to the MEEPLES sub-phase on the
> same `get_next_state`, and the engine **scores completions only after the meeple sub-decision
> resolves**. So all deltas read as 0/constant (an artifact, NOT a finding). They are now computed
> on the **scoring-resolved** afterstate (tile + meeple-pass for forced completions; + a best-meeple
> scan for claim-and-score). v2.7 (`v27_score`) was always correct (it was on the same child both
> times). See [PRE_TOOL_AUDIT.md §Correction](PRE_TOOL_AUDIT.md). **FACT vs INTERPRETATION** marked.

## Pipeline validation (cross-check vs committed verdicts) — FACT

Recomputed agent top-1 reproduces the published verdicts to the decimal (results-discipline cross-check):

| agent | K=2 decision (mine / [L23](../level2/LEVEL2_L23_VERDICT.md)) | K=4 (mine / [K4 probe](../level2/LEVEL2_K4_PROBE_VERDICT.md)) |
|---|---|---|
| heur@3200 | 0.8369 / **0.837** ✓ | 0.6791 / **0.679** ✓ |
| heur_v1@200 | 0.8369 / **0.837** ✓ | — |
| iter8 | 0.6667 / **0.667** ✓ | 0.5615 / **0.561** ✓ |
| greedy | 0.7589 / **0.759** ✓ | 0.6471 / **0.647** ✓ |

K=4 by-source (iter8 0.65 own / 0.44 greedy-gen) and sharpness (iter8 sharp 0.39, regret 3.34)
also reproduce the K4-probe disentangler exactly. (Agent numbers are unaffected by the delta fix.)

## Headline selector table — K=2 (decision positions, n=141) — FACT

| selector | top-1 | mean regret | median | >2 | >5 |
|---|---|---|---|---|---|
| heur@3200 (deep v2.7 search) | **0.837** | 0.397 | 0 | 0.057 | 0.014 |
| heur_v1@200 | **0.837** | 0.369 | 0 | 0.043 | 0.007 |
| heur@1600 | 0.780 | 0.461 | 0 | 0.057 | 0.014 |
| heur@800 | 0.759 | 0.518 | 0 | 0.078 | 0.014 |
| greedy | 0.759 | 0.738 | 0 | 0.128 | 0.028 |
| **iter8** | **0.667** | 0.610 | 0 | 0.064 | 0.014 |
| **v2.7-action-score-only (depth-0)** | **0.661** | 0.896 | 0 | 0.149 | 0.028 |
| immediate-score+meeple-claim (best) | 0.373 | 1.245 | 0.98 | 0.163 | 0.028 |
| immediate-score-only (forced net) | 0.344 | 1.432 | 1.0 | 0.213 | 0.043 |
| score+meeple | 0.337 | 1.474 | 1.0 | 0.213 | 0.043 |
| meeple-delta-only | 0.327 | 1.642 | 1.03 | 0.227 | 0.050 |
| **completion-then-score (greedy-complete)** | **0.288** | **2.625** | 1.08 | **0.312** | **0.142** |
| random legal | 0.238 | 1.888 | 1.08 | 0.277 | 0.064 |

## The decisive finding — rank-correlation of cheap quantities vs the exact target (K=2) — FACT

Kendall τ-b between each cheap per-action quantity and the exact mover-perspective solver value,
averaged over the positions where the quantity is **informative** (varies across legal moves).
"informative %" = fraction of positions where the quantity is NOT constant.

| quantity | mean τ-b (where informative) | informative positions |
|---|---|---|
| **v2.7 action score** | **+0.55** | **133 / 150 (89%)** |
| immediate net score (forced) | +0.49 | 48 / 150 (32%) |
| score-diff-after | +0.49 | 48 / 150 (32%) |
| best-meeple net (incl. claim) | +0.46 | 57 / 150 (38%) |
| meeple delta | +0.29 | 29 / 150 (19%) |

**Corrected core result.** The raw cheap quantities are **SPARSE, not dead**: in ~62–81% of K=2
positions nothing closes this turn, so immediate-score/meeple/completion are **constant** (no ranking
signal). But **where they do vary (~20–38% of positions, the ones with a completion in play) they
carry real signal** (τ ≈ 0.46–0.49, comparable to v2.7's 0.55). The catch: that signal is **largely
already inside the v2.7 leaf** — v2.7 anticipates the same closures *and* ranks the positional
majority (informative 89%, τ 0.55), which is why v2.7-depth-0 (0.66) ≈ iter8 while the raw selectors
(0.33–0.37) sit barely above random (0.24) and far below.

**The completion trap (FACT).** "Always prefer to complete" (completion-then-score) is the **worst**
simple selector — top-1 **0.288** with the **highest blunder rate (>5pt: 0.142, >10pt: 0.057)**, below
even plain immediate-score. Greedily grabbing an immediate completion at the endgame actively
*mis*-ranks (e.g. position `g3200000003`: completing for +8 now is regret 3 vs the patient optimum that
iter8/heur_v1 find). A naive "completion" tool would not just be weak — it would be a hazard.

## K=3 (n=71, agents only) and K=4 (n=187) — FACT

| selector | K=3 top-1 | K=3 regret | K=4 top-1 | K=4 regret |
|---|---|---|---|---|
| heur_v1@200 | 0.761 | 0.493 | — | — |
| greedy | 0.761 | 0.606 | 0.647 | 1.326 |
| heur@1600 | 0.662 | 0.747 | — | — |
| heur@800 | 0.648 | 0.775 | 0.652 | 1.214 |
| heur@3200 | 0.634 | 0.789 | **0.679** | **1.070** |
| iter8 | **0.592** | 0.916 | **0.561** | 1.481 |
| random | 0.268 (top-1 only) | — | 0.297 | 2.791 |

(K=3 has no full child-value map / no `difficulty` block persisted, so K=3 new selectors / random-regret
need a re-solve — see manifest. At K=3 the *shallow* agents top the list, n small, ordering noisy.)

## By difficulty (sharp gap≥2 vs forgiving gap<2) — FACT

| selector | K=2 sharp top-1 / regret | K=2 forgiving | K=4 sharp top-1 / regret | K=4 forgiving |
|---|---|---|---|---|
| heur@3200 | 0.791 / 0.79 | 0.857 / 0.22 | 0.447 / 2.82 | 0.738 / 0.62 |
| iter8 | 0.721 / 1.05 | 0.643 / 0.42 | **0.395 / 3.34** | 0.604 / 1.01 |
| greedy | 0.674 / 1.37 | 0.796 / 0.46 | 0.500 / 2.71 | 0.685 / 0.97 |
| v2.7-depth-0 | 0.561 / 1.77 | 0.705 / 0.51 | — | — |
| imm-score+meeple(best) | 0.397 / 2.12 | 0.363 / 0.86 | — | — |
| immediate-score-only | 0.387 / 2.33 | 0.325 / 1.04 | — | — |

(On K=2 *sharp* positions iter8 (0.721) beats v2.7-depth-0 (0.561) — its MCTS adds value over the static
leaf when the position is sharp — but heur@3200 (0.791) beats both. The immediate-score selectors stay
low in both buckets.)

## Interpretation (marked INTERPRETATION)

1. **The cheap raw quantities are a sparse, largely-redundant endgame signal.** They rank well only
   where a completion is in play (~20–38% of K=2 positions) and that signal is mostly already captured
   by the v2.7 leaf (which also ranks the positional majority). A selector built on them alone reaches
   only ~0.34–0.37 top-1 (vs iter8/v2.7 0.66, deep heur 0.84). **Completion-greed is a hazard** (0.29,
   high blunders). ⇒ At the endgame, these tools would add little over v2.7 and could mislead.
2. **iter8 already consumes the one broadly-informative quantity** (v2.7 is its MCTS leaf). Its endgame
   deficit is therefore NOT primarily a missing cheap feature (Phase 4: only ~7/158 misses are clearly
   completion-mechanism; the rest are structural/positional). It is that its policy+search under-weight
   the endgame vs *deeper* v2.7 search (heur@3200) — matching the hybrid-handoff fix (CL-026).
3. **Scope caveat (the load-bearing one for tools).** This is the K=2/K=4 ENDGAME, where these
   quantities are *sparse by construction* (few features close in the last 2–4 tiles). In the
   opening/midgame many features are simultaneously in play, so immediate-score/meeple/completion would
   vary far more often and could carry materially more (and less v2.7-redundant) signal. **We have NO
   solver labels there to test it.** The endgame neither clears nor condemns a midgame tool.
4. **What the audit has NOT tested:** feeding the **per-action v2.7 score** directly to a policy/ranker
   (vs only via the MCTS leaf), or a **bag-aware completion** signal — both absent from the net input
   (INPUT_INVENTORY.md #6/#9), neither tested here.
