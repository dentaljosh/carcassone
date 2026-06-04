# The +87 ceiling and the C4/C6 value-head rebuild — sketch (2026-06-04)

## ⚡ PROBE RESULT (2026-06-04 pm): C4a is REFUTED — don't build the farm-connectivity rebuild

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
premise* behind C4a is refuted. **Remaining cheap value lever: C6 only (de-saturated target, already
built). Otherwise the value head won't cheaply beat v2.7 → +87 stands → pivot to measurement / a more
fundamental change.** The sketch below is retained for the record (the plan that the probe just gated).

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
