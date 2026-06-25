# High-precision strategic-trap report

**Status: IN PROGRESS (fresh strict generation + harvest running). Results [FILL].**
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
  couldn't see it (it rewarded "play elsewhere"). [FILL: fresh take rates]
- **`MUST_PUNISH_WEAK` — REAL.** Clean discrimination: random repeatedly fails to complete its own 8-pt
  city or claim an exposed 9-pt field that every search agent takes. [FILL]
- **`HIGH_VALUE_FARM_CLAIM_REFINED` — REAL after tightening.** `live=2` fields are taken by strong agents
  and missed by random; `live=1` fields were **declined by every strong agent** (only random claimed) →
  a bad-claim class, dropped (now requires ≥2 finishable adj cities). [FILL]
- **`MUST_NOT_FEED` — could NOT be operationalised into a discriminating trap.** On the non-trivial (hard)
  cases h6400 avoids the feed only ~16% vs random ~10% — both feed ~85%; on easy cases both avoid ~95%.
  The lone "safe" move is usually forced/costly, so feeding is often correct. Reported as **inconclusive**
  (the detector can't isolate a *tempting* trap), **not** "agents lack the concept."

Fresh examples (20–50/motif): [`HIGH_PRECISION_EXAMPLES.md`](HIGH_PRECISION_EXAMPLES.md).

## Part C — take rates by agent / regime / phase  [FILL]
See [`STRICT_ANALYSIS.md`](STRICT_ANALYSIS.md), [`strict_positions.csv`](strict_positions.csv).

## Part D — RoD1 vs h6400 on identical strict positions  [FILL]
Counts, take-rate delta, h6400-take/rod1-miss split by competitive vs already-won padding, examples.

## Part E — pre-move-controlled outcome sanity (no collider)  [FILL]
Stratified by pre-move margin / opponent strength / phase. Does taking the trap predict better
margin/winrate in competitive pre-move states, or only pad already-won games?

## Part F — kill / survive criteria

**Kill** a motif if: examples not human-plausible; random/greedy ≈ h6400 on high-confidence examples;
RoD1/h6400 differences only in already-won states; taking it doesn't improve outcome after pre-move
controls; cells too small. **Survive** if: examples clearly plausible; stronger agents take it more;
h6400 differs from RoD1 on identical competitive positions; associated with better outcomes after
pre-move controls; plausible future tool/training target.

Provisional (from Part B): `MUST_BLOCK_CITY`, `MUST_PUNISH_WEAK`, `HIGH_VALUE_FARM_CLAIM_REFINED` survive
the plausibility + discrimination gates; `MUST_NOT_FEED` is killed/inconclusive. [FILL final after C–E]

## Part G — verdict  [FILL]

## 10-line executive summary  [FILL]
