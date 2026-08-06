# Farm-war discriminator — READOUT

**Status: RAN AND CLOSED 2026-08-06. Pre-registered branch 4 fired: INCONCLUSIVE.**
Pre-registration: [FARMWAR_PREREG.md](FARMWAR_PREREG.md) (committed `226a676`, before any cell).
Verdict artifact: `farmwar/FARMWAR_VERDICT.json`. **Nothing promoted, no claim id minted,
`governance/PRODUCTION.yaml` untouched.**

## The question and the answer

Do Joshua's contested-farm moves — the ones the EV-loss grader calls blunders — actually earn
more than the champion's preferred moves, scored against an **independent** reference?

**Answer: cannot tell at this sample size, and what signal exists does not support the
hypothesis.** The pre-registered decision map's branch 4 fired on its own terms.

## Health first

`scoring_health`: **42/42 positions scored, 0 failures**, `crn_verified_all: true`,
M = 32 distinct afterstates in every cell. Both strata cleared the n ≥ 10 floor after scoring
(`n_gate.gate_ok_after_scoring: true`). Statistic, as stamped in the artifact:
**`delta = V(played) − V(best)`, engine points, Joshua's seat** — positive means his move
earned more.

## The result

| stratum | n | mean Δ (pts) | se (cluster-root) | z (two-sided) | 95% CI | sign split |
|---|---:|---:|---:|---:|---|---:|
| **FARM** | 21 | **+0.753** | 0.970 | **+0.78** | [−1.15, +2.65] | 11+ / 10− |
| **CONTROL** | 21 | +0.313 | 0.915 | +0.34 | [−1.48, +2.11] | 10+ / 11− |

Both CIs cover zero comfortably. The FARM point estimate is positive and ~2.4× the control's —
the *direction* H1 predicts — but at z 0.78 that is indistinguishable from noise, and the
**11/10 sign split is a coin flip**. `farm_mean_gt_0: true` and
`control_mean_lt_half_farm: true` both hold; `farm_abs_z_ge_gate: false` is what sends it to
branch 4.

## Three things that push AGAINST the hypothesis, and must travel with the estimate

1. **⚠️ THE POOLED +0.753 IS NOT A LICENSED ESTIMATE.** The prereg says *"report the per-epoch
   split; do not pool if the epochs disagree in sign."* **They disagree, in both strata**
   (`per_epoch.*._epochs_agree_in_sign: false`, `_pooling_licensed: false`):

   | epoch | FARM n | FARM mean | CONTROL mean |
   |---|---:|---:|---:|
   | `app_aug2` | 3 | **+2.97** | +0.33 |
   | `walled` | 7 | **+1.64** | +0.83 |
   | `fixed_v1` | 11 | **−0.41** | −0.22 |

   The **largest epoch is the negative one — and it is `fixed_v1`, the rules he plays now.**
   The positive pooled number is carried by the two legacy epochs, one of which contributes
   three positions.

2. **The out-of-family judge does not corroborate.** Tier-1 greedy agreed on the sign of only
   **13/21 = 61.9%** of FARM positions (binomial p 0.38 two-sided — not distinguishable from
   chance), and its own FARM mean is **negative** (−0.49). Per the prereg this is a **sign
   check only** and its magnitude is never comparable to the primary's — but the 2026-07-28
   precedent for this check was 80% agreement with p 0.0012, and this is nothing like that.

3. **The in-family judge was supposed to be the *conservative* direction.** It shares the leaf
   under test, so it is biased toward the champion's own picks; a positive through it would
   have been meaningful. A null through it, as the prereg states up front, **is uninformative
   about H1** — it cannot distinguish "no effect" from "effect hidden by the shared leaf".

## What this does and does not establish

- It **does not** support "the leaf mis-prices contested farm wars." No branch-1 evidence.
- It **does not** refute it either. Branch 2 required a *significant* non-positive FARM mean;
  z −0.78-ish in the one epoch that matters is not that. The hypothesis is **unresolved**, not
  killed — and the design cannot resolve it at n = 21 with a judge that shares the leaf.
- It **does** close the cheap version of the question. Per the prereg, *"the default next step
  is more E4 games, not more compute on n=6."*

## Scope limits, stated plainly

- **15 of 70 candidate plies (21%) were dropped as degenerate** — the two actions had identical
  immediate leaf values, so "farm share of the leaf difference" is undefined. The prereg did
  not anticipate this. Those are exactly the plies where the champion's disagreement comes from
  the **search**, not the immediate leaf, so they cannot speak to a leaf-pricing question in
  either direction. Recorded in `STRATA.json` as `n_dropped_degenerate: 15`.
- **The primary stratifier was used** (`stratifier_rule: primary`), not the fallback: farm terms
  *are* severable via `farm_base_off`/`farm_growth_off`, live in both `flat_leaf` and
  `carc-core`, with production `v29_farm_flip_k == 0.0`. A stale LEVER_INDEX line suggested
  otherwise and has been corrected (`f48b3f3`).
- Strata are well matched on the selection variable: |ΔQ| 0.206 (FARM) vs 0.199 (CONTROL),
  mean match gap 0.030.
- **Selection on high ΔQ biases Δ toward 0** on re-scoring (regression to the mean). This makes
  a positive harder to obtain, so the null is *softer* than it looks — a further reason not to
  read branch 4 as a refutation.
- Every ply was replayed under **its own game's rules profile** (R9 is import-latched, so the
  three epochs ran as separate concurrent processes).

## The honest bottom line

The farm ledger that motivated this remains striking and is **unexplained, not explained**:
Joshua is 6-for-6 on farms across every archived game, and the champion averages 11.0 farm
pts/seat against him versus 20.5 in its own corpus (0 in g6, its own p5). This instrument was
the cheap test of *one* explanation for that, and it came back inconclusive with the current
rules epoch leaning the wrong way for the hypothesis. **The ledger fact still wants an
explanation; "the leaf mis-prices farm wars" is no longer the leading candidate on evidence,
merely the untested one.** The cheapest thing that would move it is more fixed_v1-epoch games —
which is also what the E4 rating stream needs for entirely independent reasons.
