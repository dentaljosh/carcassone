# Post-Search Residual / Adaptive Compute Pilot — PLAN

**Status:** OPEN 2026-06-28 · branch `rod_v2_flywheel`
**Owner doc.** Results live in the sibling `POST_SEARCH_*.md`; this is the map + the target definitions.

---

## Core question

> **Can a learned model identify positions where h200 search is still materially wrong (vs h6400),
> so we can allocate deeper search ONLY where it matters — beating uniform search at MATCHED average
> compute?**

This is **not** value-head replacement, **not** policy distillation, **not** leaf correction. It is a
**search-allocation / adaptive-compute** experiment. The learned object answers one question per root:

```
"Is h200 good enough here, or should this root be escalated to deeper search?"
```

**Success** = adaptive search beats *uniform* search at *matched average compute*.
**Not success** = adaptive beats h200 by spending more compute (that is trivially true and forbidden).

## Why the target changed (the reframe that motivates this pilot)

Every prior learned-component pilot measured itself against the **static v2.9 leaf** and washed out
under search. The Feature-Graph Action Comparator Pilot (Decision C, 2026-06-28) made the mechanism
precise:

| reference | decisive-tail regret vs h6400 |
|---|---|
| static v2.9 leaf | **0.122** |
| HeuristicMCTS(200) | **0.019** (~6× collapse) |
| learned offline comparator | 0.075 (behind search) |

So **h200 search already fills the gap the static leaf misses** — `teacher_explored_frac = 1.0` at
sims=200. The right target is therefore not `h6400 − static_leaf`; it is **`h6400 − h200_search`**: the
residual error that *survives* shallow search. A learned component is only useful if it beats what
search already extracts. Adaptive compute is the one role where that's plausible: the model need not be
*smarter* than h6400 — it only needs to *predict where h200 is insufficient* so search can spend more
there.

## Stage 0 — the post-search residual target (precise definitions)

All Q values are HeuristicMCTS backed-up, root-POV, in tanh units ([-1,+1]); the same scale as the
prior pilots' `oracle_q`. For a root, let `aL = best_action(hL)` (the move agent hL would PLAY) and let
`Q6400[a]` be h6400's backed-up root-POV Q for child `a`. The deep reference is **h6400**.

```
best_action(hL)  := argmax over visited children of (Q_L[a], N_L[a])     # mcts.py best_action rule
regret(hL)       := Q6400[ best_action(h6400) ] − Q6400[ best_action(hL) ]   # ≥ 0, in Q units
q_gap_6400       := Q6400[top] − Q6400[2nd]                                  # how decisive h6400 is
```

**Labels (per root):**

```
positive_strong  :  q_gap_6400 ≥ 0.02  AND  regret(h200) ≥ 0.02
positive_medium  :  q_gap_6400 ≥ 0.01  AND  regret(h200) ≥ 0.01
negative         :  regret(h200) < 0.005   OR   best_action(h200)==best_action(h6400)
                                            OR   q_gap_6400 low / near-tie
```

i.e. a root is a *positive* (worth escalating) when **h200 picks a materially worse move than h6400
AND h6400 actually has a meaningful preference**. We also track `regret(h800)`, `regret(h1600)`,
`regret(h3200)` so we can measure *how much escalation depth removes the regret* and build the oracle
adaptive curve. (h12800 / exact only as an optional small-subset audit; h6400 is the agreed reference.)

## Method that makes Stages 1–2 cheap: ONE search per root, snapshotted

MCTS is **incremental** — the first 200 sims of a 6400-sim run are bit-identical to a standalone
HeuristicMCTS(200) (same root, same deterministic UCT, same seeded rng, same leaf). So we run **one
h6400 search per root** and snapshot the root's child statistics `{action → (N, Q_rootpov)}` at
cumulative counts **{200, 400, 800, 1600, 3200, 6400}**. That yields *all six uniform compute levels +
the h6400 reference from a single search* — a ~6× compute saving vs running each level separately.
Built-in correctness gate (smoke): snapshot-at-200 child N-distribution must equal a freshly
constructed HeuristicMCTS(200).search() on the same root, bit-for-bit. Fail loudly if not.

The frozen v2.9 leaf is enforced by the same provenance guard as the prior pilots:
`config_hash == 7fc930b82801cb43`, `EH._heur_leaf_cfg(2.0)`, `USE_FLAT_LEAF=1`. Net-free, pure CPU
(no orchestrator — there are no NN forwards to batch).

## Cheapest-informative-first: Stage 2 is the make-or-break gate

The spec's own kill switch (Stage 2): *"If oracle adaptive barely beats uniform search: stop. There is
no useful adaptive-compute opportunity."* A **perfect oracle** (escalates exactly the roots with the
largest true `regret(h200) − regret(hDeep)`) is the **upper bound** on any predictor, learned or not.
So before training anything we compute, on a modest sample:

- **Uniform curve:** mean regret at avg-sims ∈ {200,400,800,1600,3200} (6400 = 0 by construction).
- **Oracle adaptive frontier:** start all roots at h200, escalate the top-f fraction (by true gain) to
  h800 / h1600 / h3200; sweep f → traces regret vs avg-compute.
- **Random escalation:** escalate a random f — the no-information baseline.
- **Simple-heuristic escalation:** escalate the top-f by h200 entropy / low top-2 Q-gap / low
  top-visit-share / legal-action-count — the "can ML even beat a trivial rule" bar.

**Gate:** the oracle frontier must beat the uniform curve **at matched average compute** by a margin
worth chasing. If oracle ≈ uniform ≈ random → **Decision A, stop** (no opportunity), no training, no
games. This costs one dataset build (minutes, local, net-free) and seconds of numpy.

## Two-phase root sourcing (cost discipline)

- **Phase A (this gate):** reuse the **feature-graph / value-resurrection roots** already on disk
  (`measurement/feature_graph_comparator/data/rows_feat.npz` → unique `group_id`→`(game_seed, ply)`,
  10,067 roots across phases). Greedy-self-play distribution — a known bias (flagged in the FG pilot
  caveats) — but on disk, replayable, and it gives a **sanity anchor**: my h200-vs-h6400 regret should
  land near the FG pilot's 0.019 decisive figure. Sample ~2–3k roots stratified by phase. This answers
  *"is there ANY adaptive-compute room"* cheaply.
- **Phase B (only if Stage 2 passes):** broaden to **real MCTS-play distributions** (h200/h6400 &
  h3200/h6400 eval-game roots, RoD2_iter04 roots, close-score / endgame roots) for training the
  predictors and the held-out offline adaptive gate — avoiding the greedy-self-play overfit the spec
  warns against. We do NOT pay for Phase B until the oracle shows room.

## Cost posture (what spends what)

| Stage | Compute | Spend | Cluster? |
|---|---|---|---|
| 0 target defs | local read | none | no |
| 1 dataset (gate sample) | ~2.5k roots × 1×h6400 snapshot search, local CPU, parallel | none | local (state ETA, ask box) |
| 2 baselines / oracle gate | numpy, seconds | none | no — **[GATE: stop for review]** |
| 3 train predictors | logistic / GBM / small MLP, seconds–minutes | none | no |
| 4 offline adaptive gate | numpy simulation, seconds | none | no — **[GATE]** |
| 5 search implementation screen | real-search wall-clock w/ escalation, gated on 4 | minutes | maybe local |
| 6 games | paired games at matched avg compute, gated on 5 | the only real spend | laptop + local |

**No metered spend and no games until the offline matched-compute gate (Stage 4) passes.** Stage 1 is
net-free local CPU (state ETA + ask which box per standing norm).

## Hard constraints (from the brief)

Do not change the v2.9 evaluator or `PRODUCTION.yaml`. No RoD flywheel. No policy training. No scalar
value training. **Do not use static-leaf regret as the success metric** — the target is `h6400 − h200`.
No global leaf replacement. No games until the offline matched-compute gate passes. **Do not call this
a flywheel** unless a game-level matched-compute improvement exists. Do not compare adaptive to h200
while spending more compute. No architecture sprawl — cheap predictors (logistic/GBM) first; an MLP
only if signal exists.

## Decision labels (Stage 7)

- **A** No residual opportunity — h200 rarely wrong in an exploitable way, or oracle ≈ uniform → stop.
- **B** Residual exists but unpredictable — models can't beat random/simple.
- **C** Predictable, but not better than a simple heuristic (entropy/top-visit) → use the heuristic
  scheduler if useful; no ML flywheel.
- **D** Offline adaptive works, implementation/search overhead kills it.
- **E** Search/root works, games don't — root-metric trap repeats; do not promote.
- **F** Adaptive compute improves games at matched average compute → a real learned contribution.
- **G** Narrow slice only (one phase) → consider gated use, not a general flywheel.

## Stage roadmap → deliverables

| Stage | Deliverable |
|---|---|
| 0 target defs | `POST_SEARCH_PLAN.md` (this) |
| 1 dataset | `POST_SEARCH_DATASET.md` + `data/roots_adaptive.npz` (+ snapshot-equivalence audit) |
| 2 baselines / oracle gate | `POST_SEARCH_BASELINES.md` **[GATE — stop for review]** |
| 3 train | `POST_SEARCH_TRAINING.md` |
| 4 offline adaptive gate | `POST_SEARCH_OFFLINE_RESULTS.md` **[GATE]** |
| 5 search screen | `POST_SEARCH_SEARCH_RESULTS.md` **[GATE]** |
| 6 games | `POST_SEARCH_GAME_RESULTS.md` |
| 7 decision | `POST_SEARCH_DECISION.md` |
