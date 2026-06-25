# High-precision strategic-trap report

**Status: COMPLETE ✅ (2026-06-25).** 312 strict positions (fresh strong-vs-weak + competitive) +
the 1,918-position bank re-labelled. **Headline: the broad "block is dead / no lever" was PARTLY a
detector-fidelity artifact — the narrowing revealed a real, competitive ~8pp RoD1 punish-deficit.**
Branch `strategic-behavior-ladder`. **Diagnostic only — no training on these labels, no promotion;
full-game winrate vs `h6400_v2.8` remains the strength arbiter. PRODUCTION.yaml + v2.7 frozen, v2.8 opt-in.**

## What this answers

The broad ladder concluded `block`/`avoid_feeding` were "dead". This follow-up tests whether that was a
**detector-fidelity artifact** rather than a real agent failure. Narrow, human-plausible **strategic-trap**
detectors (Part A) replace the broad arg-min equity proxies, which mostly meant "play somewhere else."
Precision over coverage; inspect examples before trusting any aggregate.

## Part A — strict definitions
Full: [`HIGH_PRECISION_MOTIF_DEFINITIONS.md`](HIGH_PRECISION_MOTIF_DEFINITIONS.md). Four detectors;
the qualifying action must **physically interfere** with a concrete ≥8-pt opponent plan (not "play
elsewhere"). All structural; no outcome/score/agent/exact leakage.

| motif | phase | the strict requirement |
|---|---|---|
| `MUST_BLOCK_CITY` | TILES | place a tile **into** an opp ≥8-pt, 1-from-done city's open cell, leaving it **unfinished + strictly harder** (open_n↑) — a real spoil |
| `MUST_NOT_FEED` | TILES | a placement hands opp a ≥8-pt completable city that a safe alternative avoids |
| `MUST_PUNISH_WEAK` | TILES/MEEPLES | complete own ≥8 city, or sole-claim a ≥8 live field the opp left exposed (competitive states only) |
| `HIGH_VALUE_FARM_CLAIM_REFINED` | MEEPLES | sole-claim proj ≥9 farm with **≥2 finishable** adj cities, not already-won |

## Part B — precision audit (inspection-first)

A first pass re-labelled the existing 1,918-position bank with the strict detectors and inspected
examples by hand (the gate: *if the examples are silly, the detector is dead*). Findings:

- **`MUST_BLOCK_CITY` — REAL, and the broad "block is dead" was a detector artifact.** Examples are
  human-plausible (e.g. *opp city ~10pts, 1 tile from done at cell (6,14); this placement spoils it,
  open_n 1→3*), and they **discriminate**: search agents (greedy/h800/h3200/h6400/**rod1**) play the
  spoil, **random does not**. So the agents *do* recognise blocking; the broad arg-min detector simply
  couldn't see it (it rewarded "play elsewhere"). Fresh take rate: random 8% → h6400 50% (n=12, thin).
- **`MUST_PUNISH_WEAK` — REAL.** Clean discrimination: random repeatedly fails to complete its own 8-pt
  city or claim an exposed 9-pt field that every search agent takes. Fresh: random 15% → h-agents 92%, rod1 84%.
- **`HIGH_VALUE_FARM_CLAIM_REFINED` — REAL after tightening.** `live=2` fields are taken by strong agents
  and missed by random; `live=1` fields were **declined by every strong agent** (only random claimed) →
  a bad-claim class, dropped (now requires ≥2 finishable adj cities). Fresh: random 25% → h6400 89%, rod1 82%.
- **`MUST_NOT_FEED` — could NOT be operationalised into a discriminating trap.** On the non-trivial (hard)
  cases h6400 avoids the feed only ~16% vs random ~10% — both feed ~85%; on easy cases both avoid ~95%.
  The lone "safe" move is usually forced/costly, so feeding is often correct. Reported as **inconclusive**
  (the detector can't isolate a *tempting* trap), **not** "agents lack the concept."

Fresh examples (20–50/motif): [`HIGH_PRECISION_EXAMPLES.md`](HIGH_PRECISION_EXAMPLES.md).

## Part C — take rates by agent / regime / phase

Fresh strong-vs-weak + competitive generation (312 strict positions, full tables in
[`STRICT_ANALYSIS.md`](STRICT_ANALYSIS.md), [`strict_positions.csv`](strict_positions.csv)).
Take rate (opportunity-normalized), weak→strong agents:

| motif (n) | random | greedy | h200 | h800 | h3200 | h6400 | **rod1** |
|---|---|---|---|---|---|---|---|
| **MUST_PUNISH_WEAK** (179) | 15 | 55 | 89 | 93 | 92 | 92 | **84** |
| **HIGH_VALUE_FARM_CLAIM_REFINED** (95) | 25 | 13 | 86 | 89 | 87 | 89 | **82** |
| **MUST_BLOCK_CITY** (12 ⚠thin) | 8 | 33 | 50 | 50 | 50 | 50 | **42** |
| MUST_NOT_FEED (115) | 77 | 85 | 85 | 85 | 85 | 85 | 82 |

The first three show a **clean strength gradient** (random ≪ search agents) — the agents *do* recognise
these concepts. `MUST_NOT_FEED` barely moves (random 77 → h-agents 85) — weak/borderline (confirming Part B).

## Part D — RoD1 vs h6400 on identical strict positions

| motif | h6400 | rod1 | Δ | h6400-take/rod1-miss (competitive / padding) |
|---|---|---|---|---|
| MUST_PUNISH_WEAK | 92% | 84% | **−8pp** | 14 (**10 competitive** / 4 padding) |
| HIGH_VALUE_FARM_CLAIM_REFINED | 89% | 82% | −7pp | 7 (**6 competitive** / 1 padding) |
| MUST_BLOCK_CITY | 50% | 42% | −8pp | 1 (1 comp) ⚠thin |
| MUST_NOT_FEED | 85% | 82% | −3pp | 5 (3 comp / 2 padding) |

RoD1 is consistently **~7–8pp below h6400** on the surviving motifs, and — unlike the broad `farm_claim`
(where 62% of misses were vs-weak already-won padding) — **the disagreements here are mostly COMPETITIVE**
(10/14 punish, 6/7 farm). That is the key difference: a genuine competitive gap, not margin-padding.

## Part E — pre-move-controlled outcome sanity (no collider)

`MUST_PUNISH_WEAK` (ACTUAL mover, stratified by PRE-move margin — no close-game conditioning):

| stratum | take win% (n) | miss win% (n) | Δwin |
|---|---|---|---|
| all | 68 (118) | 41 (61) | **+27pp** |
| even (−4..4) | 71 (68) | 40 (30) | **+31pp** |
| vs strong | 53 (38) | 24 (21) | **+29pp** |
| ahead (≥5) | 84 (32) | 92 (12) | −7pp (ceiling ⚠) |

The association **survives the pre-move-margin control** (even-score +31pp, vs-strong +29pp) — exactly the
competitive cells where the broad `farm_claim` collapsed to +5pp. `HIGH_VALUE_FARM_CLAIM_REFINED` is
weaker (even +15pp, vs-strong +16pp, thin cells). **⚠ Honest confound:** the outcome is the *actual*
mover's, and "took" correlates strongly with "mover is a strong agent" (random 15% → h-agents 92%) — the
pre-move-margin control removes the leading-state confound but **NOT the agent-identity confound** (strong
agents both take and win). So Part E is *suggestive, not causal*. The **clean** agent-difference is Part D's
counterfactual (rod1 −8pp on identical positions, competitive).

## Part F — kill / survive

| motif | plausible? | discriminates (random≪strong)? | rod1<h6400 competitive? | outcome (controlled) | verdict |
|---|---|---|---|---|---|
| **MUST_PUNISH_WEAK** | yes | yes (15→92) | yes (−8pp, 10/14 comp) | +31pp even ⚠confounded | **SURVIVE** |
| **HIGH_VALUE_FARM_CLAIM_REFINED** | yes | yes (25→89) | yes (−7pp, 6/7 comp) | +15pp even (thin) | **SURVIVE (weaker)** |
| **MUST_BLOCK_CITY** | yes | yes (8→50) | dir. (−8pp, n=12) | +25pp (n=4 ⚠) | **SURVIVE-plausibility, n too thin for a quantitative claim** |
| MUST_NOT_FEED | partly | no (77→85; h6400≈random on forced cases) | no (−3pp) | — | **KILL / inconclusive** |

## Part G — verdict

1. **Were the broad detectors too crude? PARTLY YES — this is the headline.** The broad ladder's
   "block is dead" and "no actionable lever" were **partly detector-fidelity artifacts**. With strict,
   human-plausible detectors, `MUST_BLOCK_CITY` (random 8% → h6400 50%) and `MUST_PUNISH_WEAK`
   (random 15% → h6400 92%) **clearly discriminate** and the examples are real (e.g. spoiling a 17-pt
   1-from-done city; completing your own 8-pt city; claiming a 9-pt live field a weak opp left open).
2. **Does RoD1 understand the concepts? Yes, at heuristic level** — punish 84%, farm 82%, block 42%, far
   above random — but **consistently ~7–8pp below h6400**.
3. **Is there a real RoD1 deficit? Yes, and it is COMPETITIVE** (the key upgrade over the broad result):
   RoD1's misses vs h6400 are 10/14 (punish) and 6/7 (farm) in competitive positions, not already-won
   padding. The cleanest single deficit is **under-taking obvious tactical PUNISH shots** (complete-own /
   claim-exposed ≥8) by ~8pp.
4. **Is it actionable? More than after the broad benchmark — but stay conservative.** The deficit is
   *modest* (8pp); the outcome relevance (+31pp even-score) is *agent-confounded* (not a clean causal
   estimate); and `MUST_BLOCK_CITY`'s n (12) is too thin for a quantitative claim.
5. **Which motif is the target?** `MUST_PUNISH_WEAK` — the strongest combination of plausibility,
   discrimination, competitive rod1<h6400 gap, and (suggestive) outcome association. `HIGH_VALUE_FARM_CLAIM_REFINED`
   second. `MUST_BLOCK_CITY` is a real concept worth a *larger* targeted sample before quantifying.
6. **Recommendation — ONE gated probe is now justified (a change from the broad-benchmark STOP).** Distill
   h6400's tactical-punish/block policy into RoD1 (or recalibrate the value head toward immediate ≥8-pt
   completions/claims). **Gate: full-game PAIRED winrate vs `h6400_v2.8`, n≥400, must clear ≥2σ (≈ +24 Elo).**
   If it doesn't move that arbiter, the 8pp punish-gap was not the bottleneck (RoD1's loss to h6400 stays
   dominated by the endgame placement/conversion leak). Do **not** train on or optimise the benchmark score.
7. **Falsification:** the punish hypothesis dies if the gated probe fails to move winrate vs h6400, or if a
   within-agent (rod1-self-play) analysis at larger n shows rod1's *own* punish-taking is outcome-neutral.

## 10-line executive summary

1. Precision-first follow-up: built 4 narrow strategic-trap detectors (physical interference, not
   "play elsewhere"), inspected examples before any aggregate. **Diagnostic only; no training; no promotion.**
2. **The broad "block is dead / no lever" was PARTLY a detector-fidelity artifact** — the narrowing worked.
3. `MUST_BLOCK_CITY` is a real, human-plausible concept that discriminates (random 8% → h6400 50%); the
   broad arg-min detector simply couldn't see it (it rewarded playing elsewhere). [n=12, thin — needs more.]
4. `MUST_PUNISH_WEAK` discriminates strongly (random 15% → h-agents 92%, rod1 84%) and is the cleanest signal.
5. `HIGH_VALUE_FARM_CLAIM_REFINED` survives after tightening to ≥2 finishable cities (live=1 fields are
   declined by every strong agent). `MUST_NOT_FEED` is killed (random 77% ≈ h6400 85%; forced-feed-dominated).
6. **RoD1 plays the traps at heuristic level but ~7–8pp below h6400**, and — unlike the broad farm_claim —
   **the disagreements are COMPETITIVE** (10/14 punish, 6/7 farm), not already-won padding.
7. Taking the punish is associated with winning even in competitive cells (+31pp even-score, +29pp vs strong),
   surviving the pre-move-margin control — **but confounded by agent identity** (strong agents take + win), so suggestive not causal.
8. The clean, unconfounded number is the counterfactual: **RoD1 −8pp vs h6400 on identical competitive positions.**
9. **Verdict: ONE gated probe is now justified** (distil h6400 tactical-punish / value-head recal),
   GATED on ≥2σ full-game winrate vs `h6400_v2.8` — else the 8pp gap wasn't the bottleneck.
10. PRODUCTION.yaml + champion + v2.7 UNCHANGED, v2.8 opt-in; nothing promoted; `MUST_BLOCK_CITY` needs a larger sample to quantify.
