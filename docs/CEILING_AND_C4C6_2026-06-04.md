# The +87 ceiling and the C4/C6 value-head rebuild — sketch (2026-06-04)

## ⚡⚡ DEEPER FINDING (2026-06-04 pm): the value head OVERFITS — that's the real bottleneck

While gating the value-target-source lever I measured iter_01's **actual** value head (not the small-CNN
probe proxy) corr with the true margin, train vs held-out:

```
iter_01 value head, corr(value, true POV margin):
  iter_01 self-play (IN training buffer):  +0.787   <- memorized
  iter_02 self-play (HELD-OUT, post-train): +0.327
  iter_05 self-play (further held-out):     +0.314
```

A **0.79 → 0.32 train/test collapse** = severe overfitting. Held-out 0.32 is **well below v2.7 (~0.65)** —
which is *exactly* why blending the value head into the search HURTS (Stage B; the −123 play-time probe):
on the off-distribution positions MCTS explores, the learned value is far worse than the heuristic, while
v2.7 (hand-crafted) generalizes uniformly. Note the small-CNN C4a/C6 probes got ~0.5 held-out — *better*
than the big net's 0.32 — i.e. the 7M net's capacity actively hurts generalization here.

**Root cause:** the value target is the game OUTCOME, **one value per game shared across all ~144
positions** → only ~600–1200 *independent* value labels per iteration vs a 7M-param net → it memorizes.
This reframes the whole value-head problem: the bottleneck is **NOT representation (C4a refuted) or target
saturation (C6 refuted) — it's label scarcity → overfitting.**

**Why this vindicates the value-target-SOURCE lever (chosen 2026-06-04):** the MCTS **search value
(root.Q) is distinct per position** → ~100× more independent labels → directly attacks the overfitting.
So the lever isn't just "lower variance," it's "~100× more label signal." The gate below tests whether
search-value is also a better *predictor* than v2.7; the definitive test (pending) is whether a head
trained on per-position search-value **generalizes** above the 0.32 (and above v2.7's 0.65).

---

## ⚡ PROBE RESULTS (2026-06-04 pm): BOTH cheap value levers (C4a + C6) REFUTED — cheap path exhausted

**C6 (de-saturated target) — REFUTED** (`scripts/probe_value_target_c6.py`, commit 1c862ce). Same deep
CNN trained on tanh(m/15) vs tanh(m/40), scored by corr(head output, true margin):

```
                 corr(all)        corr(|m|>33 saturated subset)
t15 (current)   +0.521 ±0.036     +0.733 ±0.021
t40 (C6 wide)   +0.491 ±0.048     +0.690 ±0.046   <- no better; marginally worse
```

De-saturation gives NO gain. The head already tracks big margins fine with the "saturating" tanh/15
target (corr 0.733 on |m|>33) — MSE on ±0.99 targets still carries graded gradient and corr is
scale-invariant, so saturation never destroyed the ranking. C6 was a theoretical worry that doesn't
bite. **Cheap value path is now FULLY EXHAUSTED** (C4a + C6 both dead). Next moves are all
expensive/external — see "Where that leaves us" below.

---

## ⚡ C4a REFUTED — don't build the farm-connectivity rebuild

The cheap offline kill-test (`scripts/probe_value_head_c4.py`, commit c26e468) ran. A value CNN
predicting tanh((p0−p1)/15) on Stage-B iter_01 self-play, BLIND vs +OWN (oracle terminal-ownership
planes = strict upper bound on what live farm-connectivity C4a could give):

```
baseline (predict-mean) MSE 0.695
BLIND  corr +0.469 ± 0.008   MSE 0.557
+OWN   corr +0.447 ± 0.050   MSE 0.568   <- oracle ownership does NOT help
```

With adequate capacity the blind encoding reaches corr 0.47 and **adding the oracle ownership planes
gives NO improvement** (tied/worse, within noise). Across the two runs, fixing the model's capacity
made BLIND jump 0.28→0.47 and *absorb* the gain ownership gave the under-capacity model → **a capable
model already reads farm-relevant signal from the existing board encoding; explicit ownership/
connectivity planes are redundant.** Since the oracle (terminal truth) is a ceiling on C4a (live
approximation), **C4a — the ~½–1 day headline piece — will not lift the value head. DO NOT BUILD IT.**

Caveats: outcome-prediction proxy (not a direct beat-v2.7, which needs stored states); C4b (bag
histogram, different info) untested; from-scratch CNN ≠ the 7M net. But the *representational-blindness
premise* behind C4a is refuted. (C6, the other cheap lever, is also refuted — see above.) The sketch
below is retained for the record (the plan the probes just gated out).

## Where that leaves us (both cheap levers dead)

The value head won't cheaply beat v2.7, and **+87-over-strong-amateur stands as the ceiling.** Every
cheap lever is now exhausted: policy-iteration, value-blend, depth-vs-fixed-ref, C4a representation,
C6 target. The remaining paths are all expensive or external:

1. **Different value-TARGET source (untested, most promising of the hard options).** Every probe + the
   training all used the **raw MC game outcome** as the value label — fundamentally noisy (one game's
   result is high-variance), which is why outcome-corr tops out ~0.5. v2.7 doesn't predict the noisy
   outcome; it's a low-variance heuristic *estimate*. A value head trained on a **lower-variance target**
   — MCTS search value / n-step bootstrap (proper AlphaZero), or many-rollout-averaged position value,
   or "predict v2.7 + a learned residual" — might finally beat v2.7. This is the hypothesis the cheap
   probes did NOT address (they varied representation and target-scale, not the target's variance/source).
2. **Bigger / different value architecture.** Less likely the bottleneck (a small CNN already hit 0.47),
   but not ruled out.
3. **Measurement (external).** No humans available now (deferred). Compute-only harder references
   (heur@high-sims) make a stiffer yardstick but can't *prove* superhuman. Calibrates the ceiling; can't
   raise it.
4. **Accept ~strong-amateur+ and pivot** to the analyzer (Phase 5, the original prompt's win condition).

Recommendation: if pursuing strength, **(1) the value-target-source change is the only untested lever
with a real mechanism** — but it's a genuine build + retrain, not a cheap probe. Otherwise this is the
honest stopping point for the cheap superhuman push.

---

## What we proved today

iter_01 (clean-data λ=0 policy retrain) = **+87 elo vs HeuristicMCTS@200** (n=400, confirmed). That
is a **hard ceiling**: the three *cheap* levers to exceed it all fail.

| Lever | Result | Evidence (results.csv, game=base) |
|---|---|---|
| Policy **iteration** (more self-play iters) | erodes to +38 | policy_scale 7 gates pooled +38±10 (killed) |
| **Value-blend** at play-time | hurts, λ0.5 → −123 | `scalingcurve_iter01_s200_h200_b{25,50}_base` |
| **Test-time depth** vs fixed heur@200 | flat top (artifact) | `scalingcurve_iter01_s*_h200_base` (−74→+49→+85→+70) |

Depth-scaling in *matched* play is **OPEN** (only iter_11's ~1.5σ ladder hint; iter_01 unmeasured) —
but even if real it's ~+32/4× sims = modest. **None of the cheap levers raise the ceiling.**

## Why +87 is a ceiling — the root cause (foundational audit, confirmed)

Our agent = `learned policy priors` + **`v2.7 heuristic leaf value`** + MCTS. The *evaluation* is the
hand-crafted heuristic. The **learned value head is worse than v2.7** (it hurts both in self-play —
Stage B — and at play-time — today). So the eval is heuristic-capped, and the heuristic was built to
play ~strong-amateur. Superhuman, by construction, needs the **learned eval to beat v2.7** — which it
can't, today. That is the whole game now.

## The diagnosis the rebuild bets on (C4 + C6)

Two reasons the value head may be losing to v2.7 (from `CORRECTION_PLAN_2026-06-02.md`):

- **C4 — representation blind spots.** The net's input is *blind to the things v2.7 actually computes*:
  - **C4a farm-connectivity:** which fields merge, which cities each field borders, current farm
    majority — computed LIVE (reuse `FarmUtil.find_farm` flood-fill, not the terminal-only
    `aux_targets` recorder). ~2–3 input planes. *Biggest piece (~½–1 day).*
  - **C4b bag histogram:** per-tile-type remaining counts from `state.deck` (~24 types, normalized) →
    scalars. The net can't reason about what's drawable. ~1hr.
  - **C4c open-feature planes:** per-cell city open-edge count / monastery neighbor count. ~1hr.
  - **C4d farm scalars ON** (`include_farm_scalars=True`, currently OFF).
  - Changes input width → **fresh warmstart** at the new width.
- **C6 — saturated value target.** `tanh((p0−p1)/15)` pins to ±1 for 30–80pt margins, so the head
  can't learn fine endgame distinctions. Fix: `--value-target score_diff_wide` (tanh/40) — **already
  built** (commit b1a2055), just needs to be the training target.

The bet: the value head is losing *because it literally can't see farm connectivity + the bag* (exactly
what v2.7 hand-computes). Give it those inputs + a non-saturated target and it may finally match/beat
v2.7 — which would lift the ceiling.

## ⚠️ The honesty flag

`PHASE1_BUILD_SPEC_2026-06-02.md` set an explicit gate: *"if value-in-loop is flat/worse even
on-distribution → the ceiling is deeper than F-B1; **reconsider before spending a day on C4.**"*
**Stage B was worse.** So C4/C6 is **not an automatic go** — it's a hypothesis (blindness is the cause)
that could be wrong (maybe a 7M ResNet value head just can't out-evaluate a tuned game-specific
heuristic, representation or not). Spending ~1.5 days of build + a full retrain on an unverified bet
violates cost-discipline.

## Cheapest-informative-first: test the C4 hypothesis OFFLINE before the retrain

Before any AZ retrain, answer the gating question cheaply and directly:

> **Can a value head that CAN see farm-connectivity + bag out-predict v2.7 on held-out positions?**

- Take existing clean base-only self-play positions (we have warmstart corpora + Stage-B self-play
  games) with their game outcomes / score-diffs as labels.
- Train a **small supervised value head** with the C4 features (farm-connectivity planes + bag
  histogram) — offline, minutes-to-an-hour on one GPU, no MCTS, no cluster.
- Compare its held-out value accuracy (corr / MSE vs the true outcome) to **v2.7's** prediction on the
  same positions.
- **If the featured head clearly beats v2.7 offline → C4 is justified; do the full retrain.**
  **If it can't → the ceiling is deeper than representation; don't spend the retrain.** Pivot to:
  measurement (calibrate the ceiling vs a real reference), or a stronger eval family (bigger net /
  different value architecture / search-based targets), or accept ~strong-amateur+ as the result.

This is a ~1-hour probe that gates a ~1.5-day spend. Run it first.

## If the probe says go — the full build (Stage C)

1. C6 target switch (`score_diff_wide`) — already built.
2. C4b bag histogram + C4c open-feature planes + C4d farm scalars — ~half day.
3. C4a farm-connectivity live planes — ~½–1 day (the real work; reuse `find_farm`).
4. Fresh warmstart at the new input width (`network.py` takes `n_scalar_features`; confirm channel
   count propagates). C5 symmetry aug ON for data efficiency.
5. Retrain loop; **gate on the independent HeuristicMCTS ladder, n≥400** (out-of-lineage; self/same-
   lineage anchors lie). One lever per question — don't co-vary with C3.
6. Verdict: does the learned value (now with sight) beat v2.7 *in the loop*? That's the superhuman gate.

## Still true regardless

The **measurement wall** is unchanged: HeuristicMCTS ≈ strong-amateur is our only reference, so even a
ceiling-break can't be *proven* superhuman without an above-amateur yardstick (the "meatbag" —
deferred). C4/C6 raises the ceiling; measurement tells us how high it actually is.

---

## ⚡ gate-2 RESULT (2026-06-04 pm): mechanism CONFIRMED, cheap test underpowered

`scripts/gate2_value_head_searchvalue.py` (24 games, sims=50, held-out by-game), corr with true margin:
```
  v2.7 value                  : +0.401
  search-value target (root.Q): +0.423   (~= v2.7 at sims=50)
  head trained on OUTCOME      : -0.04    (overfit to noise -- confirms the bug)
  head trained on SEARCH-VALUE : +0.166   (per-position helps vs outcome, but underfits)
```
CONFIRMED: per-position search-value targets generalize FAR better than game-shared outcome targets
(0.166 vs -0.04). But two underpowering limits prevent a clean GO: (1) the **sims=50** search-value
target is only ~= v2.7 (0.42 vs 0.40) -> a head can't exceed its target -> need HIGHER-sims search-value
for the target itself to beat v2.7; (2) **24 games** too few -> head underfits (0.166 << its 0.423 target).
Properly testing the lever needs high-sims search-value targets at production data scale -> fold them
into the production self-play loop (fast gen) + a real retrain iteration (~day+). The ad-hoc generator
can't do it cheaply (single-board GPU eval doesn't parallelize across processes -> hours single-stream).
DECISION pending (Joshua): invest in the value-head rebuild (search-value targets, high-sims, in-loop)
vs bank strong-amateur+ and pivot to measurement / Phase 5.
