# Hard-Position Policy Repair — DECISION

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.**
No promotion · PRODUCTION.yaml / champion / v2.9 evaluator unchanged · v2.7 frozen.
Evidence: [HARD_POLICY_REPAIR_RESULTS.md](HARD_POLICY_REPAIR_RESULTS.md) ·
Plan: [HARD_POLICY_REPAIR_PLAN.md](HARD_POLICY_REPAIR_PLAN.md).

## The question

> Can explicit h6400-labeled hard-position exposure repair the RoD2 policy failure (diffuse,
> no movement toward h6400 on `h3200≠h6400` disagreement states)?

## Decision — **A (with a sharper mechanism): the policy does NOT move on held-out hard states. STOP. No games.**

The literal Stage-4 gate **fails**: across three targets, repaired-net top1 on the held-out hard
test set stays at or below the 0.091 baseline (P1-visit 0.076, P1-onehot 0.061), lean stays ≈ 0
to negative, P_neither stays ~0.80. Per the plan, **stop — do not run the Stage-6 game screen**
(it was gated on Stage 4 passing). P2 (ordinary mix) and P3 (from RoD1) were **not run**: they face
the identical signal-free target, so they cannot change the verdict.

But the mechanism is more precise — and more useful — than the literal outcome A ("the setup can't
absorb the signal"):

1. **The net has full capacity.** P1-onehot *memorized* the training argmax to top1 **0.775**
   (lean +0.752). The architecture/optimizer can absolutely learn "pick h6400's move."
2. **The target carries no generalizable signal on disagreement states.** It memorizes train and
   collapses to **0.061** on held-out (below baseline). The reason: on `h3200≠h6400` states the
   deep teacher's top two moves are **value-tied to ~0.002** (Q-gap median 0.0007, vs 0.040 on
   ordinary states; only 3% of hard states have a gap > 0.02). The argmax is a near-coin-flip, so
   what's memorized is position-specific **noise** that cannot transfer.

**So the repair fails for a signal reason, not a capacity or training reason.**

## The reframe (the load-bearing finding)

**"h3200≠h6400 disagreement" selects value-INDIFFERENT states, not deep-distinctive ones.** Two
search depths disagree on a position precisely when its top moves are near-equal in value (else
both agree on the obvious best). On these states a **diffuse policy is correct** — there is no
single right move to put mass on. The policy's diffuseness on the disagreement subset — the RoD2
autopsy's headline "policy stuck / not moving toward h6400" signal (Stage A-lite) — was therefore
**measuring a non-failure.** Corroboration: the SAME nets agree with h6400 **3.4× more often** on
ordinary (decisive, Q-gap 0.040) states than on hard (indifferent, Q-gap 0.002) states
(top1 0.311 vs 0.091). The policy is already aligned with the teacher *wherever the teacher is
decisive*.

This **does not overturn** the RoD2 autopsy decision **C** (stop the AZ-style blind flywheel): the
binding constraint there was **blocker #2** (the learned value cannot exceed the v2.9 leaf), which
this experiment does not touch. It **refines** the autopsy: the "diffuse policy" supporting mode
should be **downweighted** as evidence of a learnable failure. The bottleneck is the value/eval
ceiling, not policy diffuseness.

## What is ruled out for the policy-distillation direction

- **Distilling h6400 onto the policy on argmax-disagreement states — DEAD END.** No transferable
  signal (this experiment). Neither soft (visit) nor hard (one-hot) targets, nor a from-RoD1 warm,
  can change that — the labels are noise on the chosen state set.

## Named boundary (NOT pursued — governance: no new branches/curriculum/tools mid-experiment)

IF policy distillation is ever revisited, "hard" must be defined by **decision-relevance** — the
h6400 root **Q-gap** (does the choice matter?) — **not** by argmax disagreement. The genuinely
deep-distinctive states (large Q-gap where shallow search errs) are a different, much rarer set
(~3% of the disagreement pool here). Whether the policy fails *there* is an **open, untested**
question and a **separate** experiment — named here as the decision boundary, **not** proposed or
started. It would also require mining states by Q-gap, which this pilot did not do.

## No new experiments

No new branches, curriculum, tools, feature channels, aux heads, or RoD3 proposed. The one narrow
question is answered: explicit h6400-labeled exposure on disagreement states **cannot** repair the
policy, because those states are value-indifferent and the labels are noise.
