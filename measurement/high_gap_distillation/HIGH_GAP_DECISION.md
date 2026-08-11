# High-Contrast Decision-Signal Distillation — DECISION

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEAS/DIAGNOSTIC ONLY.**
No promotion · PRODUCTION.yaml / champion / v2.9 evaluator unchanged · v2.7 frozen.
Evidence: [HIGH_GAP_RESULTS.md](HIGH_GAP_RESULTS.md) · Gate: [HIGH_GAP_SIGNAL_DENSITY.md](HIGH_GAP_SIGNAL_DENSITY.md) ·
Plan: [HIGH_GAP_PLAN.md](HIGH_GAP_PLAN.md) · Training: [HIGH_GAP_TRAINING.md](HIGH_GAP_TRAINING.md).

## The question

> Is there enough **high-contrast, decision-relevant** teacher signal for the current net to learn
> beyond the heuristic — and does learning it on held-out high-gap states repair the RoD2 policy
> failure that self-play could not?

## Decision — **B: the policy learns the signal, but it does NOT convert through search. STOP.**

**The high-contrast signal exists and is learnable — but distilling it onto the policy is the wrong
lever. The binding constraint is value/search, not policy exposure.** (Decision B in the plan's
A–E menu, made *definitive* — not merely inferred — by the game screen.)

This **inverts** the prior hard-policy-repair experiment's selection (argmax disagreement →
value-*indifferent* states, no learnable signal) and confirms its **named boundary**: define "hard"
by h6400 **Q-gap/regret**, and the signal is real, dense, and learnable. But learnability ≠ strength.

## The six questions (plan Stage 7)

1. **Did enough high-Q-gap / high-regret signal exist?** **YES — abundant.** Across the 20k pool:
   gap≥0.02 = 37%, gap≥0.02 ∧ iter04-wrong = 22%, iter04 regret≥0.02 = 43% — phase-balanced
   (~20–24% every phase incl. endgame). (Prior experiment's disagreement-only selection: 3%.)
2. **Could the net learn it on held-out states?** **YES.** Held-out hard TEST (n=1390, game-disjoint):
   prior top1 **0.000 → 0.18** (R1), top3 0.30→0.42, mean regret **−27%**, median −42%; strong-gap
   top1 0→0.27; **endgame 0→0.17** (the autopsy's collapse region). The soft **Q-softmax** target
   generalised where the prior experiment's one-hot did not. The scale-up was decisive: the pilot's
   ambiguous +8pp became an unambiguous +18pp at 14× the test size.
3. **Did the repair survive ordinary-state regression?** **Modestly.** On decisive states iter04
   already got right (n=3611): R2 top1 1.00→0.95, mean regret 0→0.007 (R1 worse: 0.92). Not severe at
   the prior level — but see Q5: it does not wash out in play.
4. **Did NMCTS use the repaired policy?** **NO net benefit — washout.** NMCTS@200 top1 vs h6400:
   iter04 **0.497**, R2 **0.497** (R1 0.453). iter04's *wrong* prior already searches to 0.497;
   the better prior is redundant at the root at production depth. Only **endgame** moved
   (R2 0.552 vs 0.483).
5. **Did full-game strength move?** **NO — it got worse.** R2 vs h6400_v2.9 (n=126, paired): WR
   **0.409**, elo −64 — *below* the iter04 baseline (0.463) it was fine-tuned from (≤ iter04 at ~1σ,
   definitely not better). The eval's own read: *net loses to pure heuristic search at matched
   compute.* The redundant-at-root prior gain is bought at a broad-distribution cost that search does
   not recover in full play.
6. **Is a new flywheel recipe justified?** **NO.** Policy distillation does not break the ceiling.

## Mechanism (the load-bearing finding)

**Search already extracts the decision-relevant move from the existing prior.** iter04's policy is
wrong on every hard state (top1 0.000) yet NMCTS@200 recovers the right move 49.7% of the time — the
value head + v2.9 leaf + 200 sims compensate for the bad prior. Improving the prior to 18% top1 adds
**nothing** at the root (still 0.497) because the ceiling there is set by **value/search quality**,
not by the prior. Meanwhile the fine-tune perturbs the policy across the *whole* distribution (the
−5pp ordinary regression), and *that* cost is not washed out in full games → net strength flat-to-down.

This **sharpens RoD2 autopsy blocker #2** (the learned components can't exceed the v2.9 leaf): the
**policy** is not the binding learned component — it is already adequate for search. The binding
constraint is the **value/search** path. A superhuman lever must improve the *value* the search backs
up (or the search itself), not the policy prior.

## What is ruled out

- **Policy distillation (any target) as a strength lever for RoD — DEAD END.** Soft Q-softmax on
  genuinely high-contrast, learnable, generalising signal still does not convert (this experiment).
  The one-hot-on-indifferent-states variant was already dead (prior experiment). Both fail; the
  failure modes differ (no signal vs. signal-but-redundant-under-search).

## Named boundary (NOT pursued — governance: one narrow question, no new branches mid-run)

The endgame is the one place the repair survived search (NMCTS endgame 0.483→0.552, regret −15%).
IF policy distillation is ever revisited it should be **endgame-restricted** — but even there it must
clear a *game* screen, which the global R2 did not. The real next direction implied by this result is
**value/search**, not policy — explicitly a **separate** experiment, named here as the boundary, not
proposed or started.

## No new experiments

No new branches, curriculum, tools, aux heads, or RoD3 proposed. The one narrow question is answered:
high-contrast decision signal **exists and is learnable**, but distilling it onto the policy **does
not repair the flywheel** — search already compensates, so the bottleneck is value/search, not policy
exposure. PRODUCTION.yaml / champion / v2.9 evaluator unchanged.
