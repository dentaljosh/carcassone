# JCZ disagreement mining — PRE-REGISTRATION

> **Status: PRE-REGISTERED 2026-08-09, FUNDED by Joshua ("build it, don't launch it — the box is
> mine today and the phase ladder has first claim tonight").** Written and committed **BEFORE any
> extraction or scoring code ran against `confirm.jsonl`.** Nothing here may be edited after the
> first scored cell lands; corrections go in the READOUT.
>
> This is **step 1** of BACKLOG 2026-08-09 *"JCZ disagreement mining"*. Step 2 (term archaeology)
> is [TERM_ARCHAEOLOGY.md](../jcz_match_20260809/TERM_ARCHAEOLOGY.md); step 3 (native build + play
> gate) is **gated on this readout** and is not funded by it.
>
> House pattern: [FARMWAR_PREREG.md](../analyzer_evloss_20260805/FARMWAR_PREREG.md). Same judges,
> same CRN machinery, same cluster-robust statistic, same two-sided discipline.

---

## 1. The question

The archaeology read both evaluators line by line and returned **convergent evolution with one
genuinely different organ**: our meeple economy is a single convex function of the **free** count and
our closure probability is a two-entry constant table blind to the bag; JCZ's meeple economy is three
terms on the **committed** side (feature-class-convex lock-up, deadness-banded stranding, a phase
gate) and its closure probability is computed from the actual remaining-tile multiset matched by edge
pattern per cell.

Reading a term says nothing about its value — our own ablation proved that four separate ways
(`capoff` ≈ null, both-halves `anticoff` ≈ null, Term R **−251.9**, `farmgrowthoff` unconfirmable).
So the question this experiment answers is behavioural, not textual:

> **Where does THEIR evaluator out-earn OURS?**

Operationalised: on real positions from the n=400 confirmatory corpus, find plies where JCZ's
preferred move differs from our production leaf's preferred move, score **both picks** over M=32
common-random-number deck completions, and cut the result by a taxonomy that maps onto the named
steal candidates — so that a win **localises to a term** rather than to a vibe.

**This experiment cannot promote anything.** Its maximum output is a *conviction* that funds a
native term build and a C5 play gate. See §8 rider R2.

---

## 2. Position source and the disagreement screen

**Corpus:** [`measurement/jcz_match_20260809/confirm.jsonl`](../jcz_match_20260809/confirm.jsonl) —
400 games (200 decks × 2 seatings), 56,777 plies, band `1.08e11`, `fixed_v1` + `CARCASSONNE_FIX_R9=1`,
0 voids, 0 REAL divergences, `final_agree` 400/400, `replay_ok` 400/400
([CONFIRM_READOUT](../jcz_match_20260809/CONFIRM_READOUT.md)).

**The screen is free, and that is the central design win.** JCZ's `LegacyAiPlayer` is a one-turn
breadth-first enumeration of the acting player's own action chain, ranked by **one** static
evaluation of the resulting state — no opponent reply, no lookahead
([`RankingAiPlayer.java`](../../scripts/jcz_match/java/com/jcloisterzone/ai/RankingAiPlayer.java)).
Therefore **JCZ's played move IS its evaluator's argmax.** Every ply where JCZ was the actor is
already a recorded, ground-truth answer from their evaluator, stamped verbatim in the archive
(`moves[i].jcz_message`) and mapped to our action space (`actions[i]`). We do not have to run the
JVM to learn what they prefer — we only have to compute what *we* prefer at the same state.

**Mined plies.** Every ply with `moves[ply].seat == jcz_seat` and
`moves[ply].kind ∈ {jcz_tile, jcz_meeple, jcz_meeple_pass}`, replayed under `fixed_v1` from
`(deck_seed, actions[:ply])`. Excluded by construction:

- `jcz_meeple_pass_implicit` — JCZ had no meeple option; **not a decision**.
- `tile_pass_redraw` — the A3 unplaceable redraw; **forced**.
- any ply where our replayed legal-action set has size 1 — **forced**, no disagreement possible.
- champion-actor plies — see §2.3.

### 2.1 Leaf-vs-leaf, and why (the load-bearing choice)

Both sides are evaluated **leaf-greedy**, not search-vs-search.

- **The steal question is a question about evaluators.** Search-vs-search has already been measured
  at n=400: champion +111.4 elo, deck-paired margin +6.50 ± 0.86 pts/deck. Re-running it answers
  nothing new. What is unknown is whether their *pricing* of a decision class beats ours.
- **Their side is leaf-greedy whether we like it or not.** `LegacyRanking` is applied once, to the
  terminal state of a one-turn chain. There is no deeper JCZ to compare against — the opponent has
  zero configuration knobs.
- **So the matched procedure on our side is chain-greedy on our production leaf**, over the *same*
  chain space: the acting player's own-turn action chain. Same decision procedure, different
  evaluator. That is the tightest available isolation of the thing under test.
- The champion's **full-search pick** (k8×1376 = 11008 PIMC sims) is recorded as a **third column
  for context only** on the sampled positions. It never enters the decision map. Its job is to let
  the readout say *"on the plies where their leaf beat our leaf, did our search already find their
  move anyway?"* — which is the sims-washout question (rider R2) asked cheaply.

### 2.2 Two position classes, one scored action each

JCZ's decision unit is the **chain** (tile placement, then meeple decision). Our scoring instrument
(`oracle_score_pilot.py`) scores **one action** per arm. Rather than modify a banked instrument, the
frame splits the chain at its natural seam. Each mined ply yields **at most one** candidate:

| class | root position | our pick (`pick_a`) | their pick (`pick_b`) |
|---|---|---|---|
| **TILE** | the state at a `jcz_tile` ply | the **tile action of our chain-argmax**: `argmax_t [ max_m leaf(s ∘ t ∘ m) ]`, where the inner max runs over the meeple decisions available after `t` (and is skipped when the successor is no longer JCZ's turn) | `actions[ply]` |
| **MEEPLE** | the state at a `jcz_meeple` / `jcz_meeple_pass` ply — JCZ's tile is already down | `argmax_a leaf(s ∘ a)` over all legal actions **including pass** | `actions[ply]` |

A candidate exists iff `pick_a != pick_b`.

The inner `max_m` on the TILE class is **not decoration** — it makes our tile choice chain-optimal in
exactly the sense JCZ's BFS is, removing an instrument asymmetry that would otherwise hand their arm
a free lookahead advantage. On the MEEPLE class there is no asymmetry at all: the tile is fixed and
both sides answer the same one-action question.

Leaf of record: the production leaf from `governance/PRODUCTION.yaml` via
`champion_factory.production_leaf_cfg()` (`v2_9_2_Bmild_cap8_curve125`, hash `a36d2e15a3b3d71d`),
evaluated with `flat_leaf.flat_virtual_score_v2_float(state, jcz_seat, cfg, bag_close=None)` — the
**pre-round float**, so ties are real ties and not quantisation artifacts. Verified at load with
`champion_factory.verify_leaf`.

### 2.3 Why champion-actor plies are out of scope

To learn JCZ's preference at a ply where *our* champion moved, the JVM must be driven from
`GAME_SETUP` through every prior ply — `AiEngine` has no "load this state" directive and `%aimove`
*applies* the move it returns, so there is no rewind. That is one JVM boot plus a full protocol
replay **per queried ply**, and the disagreement screen would have to query all 14,187 champion tile
plies to find the disagreements. The JCZ-actor frame gets the identical comparison for free.

The cost is a **known, one-sided selection effect**, pre-registered as rider R3.

---

## 3. Strata — FIXED NOW, before any scoring

Every stratum predicate is computed **from our own state features**, never from JCZ's evaluator
internals. All predicates are evaluated on the two **arm successor states**, from the acting
player's (`jcz_seat`) point of view. Strata are **mutually exclusive**, assigned by the precedence
below, first match wins.

### 3.0 The primitive: `DEAD`

A committed meeple is **`DEAD`** iff our production leaf assigns its feature **closure-anticipation
probability exactly zero** — i.e. the leaf prices it through `base` alone and has no term that can
see it coming back or paying off. Read straight off `flat_leaf`:

| feature class | `DEAD` when | why |
|---|---|---|
| **FIELD** (farmer) | **always** | farms never close; the leaf's farm-growth block credits the adjacent *city*, never the farmer's return |
| **ROAD** | **always** | open and closed road points are equal ⇒ Δ = 0; roads are absent from `flat_closure_bonus` **by design** |
| **CITY** | `city_root_finished` or `city_root_open_n <= 0` or `cfg.closure_p.get(open_n, 0.0) == 0.0` | the schedule's last nonzero entry sets the boundary — see the correction note below |
| **CLOISTER** | `needed = 8 - _surrounding_count(...)`; `needed <= 0` or `cfg.closure_p.get(needed, 0.0) == 0.0` | same schedule |

The `closure_p` table is **read from the loaded production config**, never hardcoded, so a leaf
change cannot silently invalidate the stratifier. Every boundary is pinned in
`tests/test_jcz_mining_extract.py`, including a test that feeds a modified schedule and proves the
classifier's boundary moves with it.

> **⚠️ CORRECTION, stamped 2026-08-09 BEFORE any scoring cell ran (extraction only had been run;
> no world drawn, no Δ computed).** The prose above originally asserted the production schedule is
> `{1: 0.5, 2: 0.2}` so that `open_n >= 3` is exactly 0. **That is wrong.** The shipped production
> leaf resolves to **`closure_p = {1: 0.5, 2: 0.2, 3: 0.05}`** — `CARCASSONNE_V25_DROP_THREE_OPEN`
> is an **opt-in env flag, default OFF** (`virtual_score_v2.py:221-224`), and nothing in the
> production env sets it. So the real DEAD boundary is **`open_n >= 4`** (and `needed >= 4` for
> cloisters), not `>= 3`; a 3-open city carries a real, if small, anticipation credit.
> The inherited claim in
> [TERM_ARCHAEOLOGY.md](../jcz_match_20260809/TERM_ARCHAEOLOGY.md) §2 and §3c ("≥3 open ⇒ 0
> exactly") is stale for the same reason and has been annotated there.
>
> **Nothing about the design changes.** The `DEAD` predicate was specified as *"the leaf assigns
> closure-anticipation probability exactly zero"* and mandated to read `closure_p` from the loaded
> cfg — that rule is what surfaced the error, and the implementation was correct throughout. Only
> this worked example was stale. The consequence is that the DEAD/LIVE split sits one step further
> out than the prose described, which makes STRAT-A slightly *narrower* and STRAT-B's `live_vec`
> slightly *wider* than a reader of the original text would have guessed. The resolved table is
> stamped into the extractor's `.meta.json` and must be quoted in the readout.

`DEAD` is precisely the set our leaf is blind to and JCZ prices with two extra resolutions —
**which feature class** (S4) and **how dead** (S1). It is the located hole, made computable.

### 3.1 STRAT-A — COMMITMENT (S1 stranded-meeple + S4 category-convex lock-up)

```
dead_vec(S) := Counter over {FIELD, ROAD, CITY, CLOISTER}
               of jcz_seat's placed meeples that are DEAD in S

STRAT_A  iff  dead_vec(S_ours) != dead_vec(S_theirs)
```

The two arms disagree about **how much, and what kind of, dead commitment to accept**. This fires
on exactly the discriminations our free-count curve cannot represent: deploy-vs-pass onto a dead
feature, farmer-vs-knight, a 4-open city vs a 1-open city, a road meeple vs a cloister meeple.

It deliberately does **not** fire when both arms commit the same class to the same deadness at a
different *location* (farmer here vs farmer there) — that is a `base`-points discrimination, not a
commitment-pricing one, and counting it would dilute the stratum with noise the candidate terms
cannot explain.

**A cannot separate S1 from S4.** Their territories overlap almost completely on this predicate and
no cheap state feature separates a deadness-band penalty from a class-convex lock-up table. A
conviction on A convicts **S1 and S4 jointly**; separating them is the build's job (bracket both,
above and below, per the standing hyperparameter rule).

### 3.2 STRAT-B — SUPPLY (S2 deck-graded closure probability)

```
live_vec(S) := Counter over (class, open_n) of jcz_seat's NON-DEAD placed meeples in S

STRAT_B  iff  (not STRAT_A)
              and live_vec(S_ours) != live_vec(S_theirs)
              and k_remaining <= K_LATE
```

`k_remaining` = tiles left in our replayed deck at the root. **`K_LATE = 14`**, pre-registered, and
not arbitrary: it is JCZ's *own* phase constant. Their stuck-meeple penalty is gated on
`remainingTurns = ceil(tilePack.totalSize() / nPlayers) > 7`, which at 2 players is exactly
`totalSize > 14`. `K_LATE = 14` therefore selects the region where their evaluator's phase behaviour
provably differs from ours — and ours provably has no `k_remaining` dependence anywhere.

**Deliberate non-implementation.** The stratifier does **not** re-implement their edge-pattern
supply match. Doing so would be expensive, error-prone, and a de-facto adoption of the formula under
test inside the instrument that is supposed to be judging it. `k_remaining` is used as an explicit
**proxy for supply scarcity** and is declared as such. This is the weakest predicate of the three and
is labelled so in advance.

**Pre-registered widening ladder.** If the counts-only extractor dry run yields fewer than **30**
distinct games with a STRAT-B candidate at `K_LATE = 14`, `K_LATE` steps to **20**, then **28**, in
that order, stopping at the first value that clears 30. The chosen value is stamped into
`RUN_MANIFEST.json` and into the READOUT. This is a decision on the **sampling frame taken from ply
counts alone, before any outcome is computed** — no Δ, no score, no world is drawn during the dry
run. It cannot bias the effect estimate; it only sets n.

### 3.3 STRAT-C — CONTROL

```
phase_bucket(row) := "LATE" if row.k_remaining <= K_LATE else "EARLY"

pool  := disagreement plies that are neither STRAT_A nor STRAT_B
STRAT_C := nearest-neighbour match of `pool` to A ∪ B, WITHOUT replacement,
           exact on (`ply_class`, `phase_bucket`), nearest on `our_leaf_gap`
```

> **⚠️ AMENDMENT, stamped 2026-08-09, made from PLY COUNTS ALONE — before any world was drawn, any
> continuation played, or any Δ computed.** The matching key originally read *"exact on `ply_class`,
> nearest on `our_leaf_gap`"*. The extractor's dry run showed that leaves a **phase confound between
> STRAT-B and its own control**: STRAT-B is late-deck *by construction* (median `k_remaining` 9, mean
> 8.05), while a `ply_class`-only match drew C from mid-game (median 36) and put only **2 of 80** C
> positions at `k_remaining <= 14`. If per-ply Δ runs systematically larger late in the deck — which
> is plausible on its face, since fewer tiles remain and positions are more decisive — STRAT-B could
> clear the CONVICT predicate for reasons that have nothing to do with S2's deck-graded closure
> probability. Left unfixed, **B could only ever EXONERATE**, never convict interpretably.
>
> Adding `phase_bucket` to the exact-match key costs **nothing** — no extra positions, no extra
> compute — and phase-matches *both* primary strata rather than neither, since A is predominantly
> EARLY and B is entirely LATE. Supply was verified before the change: the control pool holds 200
> candidates at `k_remaining <= 14` across 154 distinct games (120 TILE-games, 52 MEEPLE-games)
> against B's requirement of 26 TILE + 14 MEEPLE controls.
>
> This is the same class of decision as §3.2's pre-registered `K_LATE` widening ladder — a change to
> the **sampling frame**, taken from ply counts, with no outcome in view. It cannot bias the effect
> estimate; it only decides which positions the control is drawn from. `STRATA.json` stamps the
> exact-match key actually used in `control_match.match_key`, and the readout must quote it.

`our_leaf_gap := leaf(S_ours) - leaf(S_theirs)` under **our** leaf, in leaf points, always ≥ 0 by
construction — how hard our evaluator disagrees. It is the direct analogue of farm-war's `|ΔQ|`
matching variable, and matching on it is what makes C a control rather than a different question:
without it, C would systematically hold the *mild* disagreements and A/B the *sharp* ones, and any
A-minus-C contrast would be reading disagreement severity, not decision class.

Matching **exactly on `ply_class`** is equally load-bearing: without it a stratum could be all-MEEPLE
and its control all-TILE, and the contrast would silently be a class contrast.

C separates **"their meeple pricing wins"** from **"their evaluator wins generally"**. It is the
single most important cell in the design; consequently it is scored at **1:1 against A ∪ B**, i.e.
roughly twice the n of either primary stratum, so a null on C is a *tight* null.

### 3.4 Recorded but not decisive

- `ply_class` ∈ {TILE, MEEPLE} — reported per stratum as a sensitivity; a stratum >80% one class is
  flagged in the readout and not over-read.
- `merge_exposure_differs` — a boolean covariate for **S3** (`rateConnections`, city/road merge-flip
  anticipation). **S3 is explicitly NOT tested by this design.** Its territory is a tile-placement
  property that needs its own stratum and its own n; the archaeology already names it the likeliest
  sims-washout victim ("a merge one tile away is exactly what a deep search sees for free"), so it
  stays deprioritised. The covariate is recorded so a future cut is a query, not a re-run.
- `search_pick` — the champion's full-search action at the root (context only, §2.1).
- `k_remaining`, `n_legal`, `jcz_seat`, `game_label`, `deck_seed`, `ply`.

---

## 4. Sampling, n, and power

**One scored position per game, at most.** 400 games, ≤160 scored positions ⇒ every cluster is a
singleton, the CR1 sandwich reduces exactly to `sd/√n` (pinned in the farm-war test suite), and the
design effect is 1.0 by construction. This is bought deliberately: the pilot's own design-effect
lesson was 628 records spanning only 385 roots.

**Assignment order:** A first (highest prior per the archaeology verdict), then B, then C from games
not already claimed. Within a stratum, candidates are ordered by a **deterministic hash of
`(deck_seed, champ_seat, ply)`** — never Python `hash()` — and `jcz_seat` is balanced to within ±1.

**Targets:** `N_TARGET_A = N_TARGET_B = 40`; `|C| = |A| + |B|` (≤ 80). Total ≤ **160 positions**.

**Gate:** any stratum arriving at the analyzer with **n < 25** scored positions is
**INCONCLUSIVE BY CONSTRUCTION** — reported and stopped, never reinterpreted. If both A and B fail
the gate the run is inconclusive as a whole.

### Power

Calibrated on the farm-war run's *measured* numbers, not on an assumption: at M=32 it observed
`se_cluster_root` = **0.970** (n=21) and **0.915** (n=21), implying a per-position sd of ≈ **4.3 pts**
across positions. Then `se(n) ≈ 4.3/√n`:

| n | se (pts) | 2σ detectable | Bonferroni-2 (z 2.24) detectable |
|---:|---:|---:|---:|
| 25 (gate floor) | 0.86 | 1.72 | 1.93 |
| 30 | 0.78 | 1.57 | 1.76 |
| **40 (target, A and B)** | **0.68** | **1.36** | **1.52** |
| 80 (C) | 0.48 | 0.96 | 1.08 |

**What n = 40 buys: 2σ on a +1.4 pt/ply effect, and nothing smaller.** A +0.5 pt/ply effect would
need n ≈ 300 and is out of reach at this budget — pre-registered as unresolvable, not as absent.

**Is +1.4 pts/ply a plausible size for a real steal?** Yes, and the arithmetic is not the naive one.
JCZ loses the *game* by 6.50 pts/deck, which might seem to cap any per-ply advantage — but these are
**selected disagreement plies**, and more importantly **our leaf-greedy pick is not what we play**.
The champion plays 11008 sims of PIMC on top of that leaf; the search covers for the evaluator. So a
large per-ply *evaluator* gap is fully compatible with a small game-level *agent* deficit. That gap
is exactly the quantity worth measuring, and exactly the one the match statistic cannot see. For
scale, the farm-war scope note reasoned in the same units and expected 2–4 pts/ply if its effect was
real.

---

## 5. Judges

Unchanged from farm-war — same instrument, same conservatism, same sign-only secondary.

- **Primary — in-family clairvoyant PUCT** (`--oracle-policy clair-puct`, `--oracle-sims 100`):
  `champion_factory.build_clairvoyant_champion` on the production curve125 leaf. Both arms
  continued by the **same** policy over the **same** M=32 CRN deck completions; `crn_verified` (the
  per-world afterstate deck-hash witness) is required on every position, `--strict-crn` on.
- **Secondary — out-of-family Tier-1 greedy** (`--oracle-policy tier1-greedy`): no search, v1 OBJECT
  leaf, ~1.83× noisier. **SIGN ONLY — never a magnitude comparison.** Run on **A and B only**; C's
  control role does not need a second judge, and skipping it saves ~1.4 h of box time.

**Statistic.** `Δ = mean(V_theirs − V_ours)` in game points from `jcz_seat`'s view, i.e.
`pick_a = our pick`, `pick_b = JCZ's pick`, and `oracle_score_pilot.position_delta` returns
`mean(V_B − V_A)` — so **Δ > 0 means their pick was better**. Two-sided z throughout: a negative
result is informative here (it vindicates our leaf and closes the steal route), so the test must be
able to see it.

SE is **cluster-robust (CR1) on `root_id`**, with `game_label` reported as a sensitivity. By the
one-position-per-game rule these coincide and both equal `sd/√n`; both are computed anyway, and any
divergence between them is a bug signal, not a result.

---

## 6. Decision map

`Z_GATE = 2.0` two-sided. The Bonferroni-2 threshold `z = 2.2414` is **reported alongside every
primary z** but is not the gating threshold — the real error control is that a conviction buys a
*build and a play gate*, not an adoption (rider R2, rider R8).

Evaluated in order; **first match wins** at the global level, then per-stratum verdicts are read.

**G0 — GATE FAIL.** Any stratum with n < 25 scored is INCONCLUSIVE BY CONSTRUCTION and is reported
as such. If **both** A and B fail, the run is inconclusive; stop, do not reinterpret, and do not
read C on its own.

**G1 — ALL WASH.** `|z_A| < 2` and `|z_B| < 2` and `|z_C| < 2`.
⇒ **CONVERGENT EVOLUTION IS CONFIRMED AT THE MOVE LEVEL.** The two evaluators disagree on a
measurable fraction of real plies (the readout reports the rate) and **neither pick is
detectably better**. This is a *finding*, not a failure: it upgrades the archaeology's §5 verdict
from a source reading to a behavioural measurement, and it closes the steal route on current
evidence at the stated power (nothing ≥1.4 pts/ply survives; smaller effects remain unresolved).
**No term is funded.** This is the outcome the standing base rate favours — four of our own terms
read sensible and measured null or harmful.

**G2 — NOT LOCALISED.** all three of `z_A, z_B, z_C ≥ 2` with all means > 0, **and**
`mean_C >= 0.5 × min(mean_A, mean_B)`.
⇒ Their evaluator out-earns ours **including on the stratum built to be neutral**. **Convict
nothing.** Two readings are live and this prereg refuses to choose between them on this evidence:
(a) a frame artifact — the JCZ-actor selection of rider R3 — or (b) their evaluator is genuinely
better as a whole, which would be a far larger and stranger finding than any single term and would
contradict the n=400 match. **Mandatory next step is the frame audit** (mine ~30 champion-actor
plies with the JVM under the same judge and check the sign), **before** any build. This is the
structural echo of farm-war's H3.

**G3 — LOCALISED** (otherwise). Read the per-stratum verdicts:

For `X ∈ {A, B}`:

| verdict | predicate | consequence |
|---|---|---|
| **CONVICT** | `mean_X > 0` and `|z_X| ≥ 2` and (`C`'s 95% CI covers 0 **or** `mean_C < 0.5 × mean_X`) | the corresponding candidate is **CONVICTED** and goes to native implementation + C5 play gate |
| **EXONERATE** | `mean_X ≤ 0` and `|z_X| ≥ 2` | our pricing on that axis is **better**; the candidate is **deprioritised** — do not build |
| **INCONCLUSIVE** | otherwise | no action; the axis is unresolved at this power |

Mapping to the candidates:

- **A CONVICT ⇒ S1 (`v29_stranded_k`) and S4 (`v29_lockup_table`) are convicted jointly.** Funds a
  native from-scratch `LeafConfig` term build (AGPL rider: ideas and measurements yes, JCZ code
  never enters our leaf), bracketed above and below, then a **C5 play gate**: n=400 deck-paired,
  within-band, on a **fresh** band, under the **production** rules profile. Not a promotion.
- **A EXONERATE ⇒** the committed side is not the hole. Deprioritise S1/S4; the meeple-axis story
  reverts to the curve, which the ablation already prices at −299.6 / −177.2 shape.
- **B CONVICT ⇒ S2 (deck-graded closure P) is convicted.** Funds a flat-path implementation of
  `closure_continuous_slack` (specified in Option-1 Step 5, never play-gated) + C5 gate. Would give
  the leaf its **first `k_remaining` dependence**, so it re-opens caps/curve125 per the standing
  bug-fix-shifts-optima rule.
- **B EXONERATE ⇒** deprioritise S2, consistent with the existing null evidence stack
  (`bag_close` −6.1, C5 cell null; `tile_counting_closure` off).

**Tier-1 sign check** (A and B only): per-position sign agreement with the primary judge, with an
exact two-sided binomial p against 50/50. The farm-war precedent sets the scale — 80% agreement,
p 0.0012 corroborated; 61.9%, p 0.38 did not. **A CONVICT that the Tier-1 sign check fails to
corroborate is reported as CONVICTED-UNCORROBORATED** and its build is sequenced behind any
corroborated one.

**S3 gets no verdict** — it is not tested (§3.4).

---

## 7. Pre-stated threats — the ones that could make a positive wrong

1. **The in-family judge is biased toward US, and that cuts in our favour here.** The continuation
   is our own clairvoyant PUCT on our own curve125 leaf. It prefers lines our family likes, and our
   arm is `pick_a`. So a **positive** result — their pick winning — has survived a judge tilted
   against it and is **conservative**. Symmetrically, a **null is weak evidence for their side** and
   must not be read as "we are equal". Note this is the *opposite* orientation from farm-war, where
   the same judge favoured the same arm but that arm was the champion's; here the bias direction
   makes G1 slightly *harder* to trust and a conviction slightly *easier* to trust.
2. **A leaf-level win is not a play-level win.** The standing sims-washout pattern (+82.8 elo at
   sims=200 read +8 at sims=800 on the same nets) says a term load-bearing under a one-ply evaluator
   can be entirely redundant under 11008 sims of PIMC, because the search discovers it for free. The
   archaeology names S3 as the obvious victim and S1/S4 as the better bets *because* they are
   horizon-independent valuations of commitment — but that is an argument, not evidence. **A
   conviction here funds a C5-gated term build. It is NOT a promotion, it does not touch
   `governance/PRODUCTION.yaml`, and no claim id is minted except on G2 or a CONVICT.**
3. **JCZ-actor-ply selection (the one-sided threat).** Positions are drawn from turns where JCZ was
   to move, in games JCZ partly steered. The *comparison* at each position is fair — both evaluators
   answer about the same state — but the *distribution* of positions is JCZ-preferred. If their
   evaluator steers toward states where it is well calibrated, their arm is inflated. Direction is
   known: it can only help their side. Therefore a **negative** result is strong and a **positive**
   result carries this asterisk, which G2's mandatory frame audit exists to discharge.
4. **Chain-granularity on the TILE class.** Our tile pick is chain-argmax (tile + best meeple
   jointly, matching JCZ's BFS semantics), but the scoring continuation then re-picks the meeple
   with clair-PUCT in both arms — so neither arm actually gets the meeple its chain assumed. This is
   **symmetric across arms**. The MEEPLE class has no such mismatch. Per-`ply_class` means are
   reported so the reader can check the two classes agree in sign.
5. **Rules epoch is `fixed_v1` + R9 ON, not production.** This is the only provably rules-identical
   configuration, so it is not optional — but **R9 moves farm scoring**, which is exactly the axis
   S4's most striking row turns on (their `OPEN_FARM` = −5 for the first farmer). A conviction here
   is a conviction *under fixed_v1*; the C5 gate must additionally run under the production profile
   before any adoption. Unlike farm-war there is only one epoch, so no pooling question arises.
6. **One band, and it is retired from confirmatory use.** Band `1.08e11` influenced the confirm
   verdict, so per `governance/BAND_REGISTRY.csv` discipline it cannot carry a confirmatory claim.
   This experiment is **exploratory by construction** — it locates, it does not confirm — so reuse is
   licensed. Any C5 gate must be on a fresh band.
7. **Their evaluator is inseparable from their search.** `LegacyRanking`'s constants were tuned
   against precisely this one-turn enumeration. A win localises to *"their pricing of this decision
   class, under their own decision procedure"* — not to a specific line of their source, and not to
   a term that will necessarily behave the same inside our leaf.
8. **Multiplicity.** Two primary strata, two-sided, at `|z| ≥ 2` ⇒ familywise false-positive ≈ 9%
   under the global null. Reported, and priced: the Bonferroni-2 threshold accompanies every primary
   z, and the real error control is that a conviction buys a **gate**, not an adoption.
9. **Ties in the leaf argmax — and they are not rare.** Our pick is `argmax` over a float leaf;
   exact ties are resolved by lowest action index, deterministically. A ply whose top-2 leaf gap is
   exactly 0.0 is recorded with `leaf_tie = true` and **excluded from the candidate pool** — at such
   a ply "our preferred move" is not well defined, and admitting it would manufacture disagreements
   out of tie-break convention.
   **Measured on the full corpus: 7,817 / 14,190 TILE plies (55.1%) and 1,928 / 11,681 MEEPLE plies
   (16.5%) are exact ties.** The leaf lands on a coarse lattice (integer base + `{0.5, 0.2, 0.05} ×
   Δ` + curve steps), so with ~40 legal tile placements an exact top-2 tie is the common case, not
   the exception. Two consequences, both pre-registered:
   (a) **The frame is conditioned on the leaf being able to discriminate at all**, which is a real
   restriction on the TILE class in particular — the readout must state that the TILE result speaks
   only for the 45% of tile plies where our leaf expresses a strict preference.
   (b) **The tie rate is itself a finding worth reporting**, independent of any Δ: it says our
   production leaf is indifferent among top tile placements more than half the time, which is the
   move-discrimination story of CL-073 ("outcome prediction is not move discrimination") showing up
   as a raw structural fact about the leaf rather than as a learned-vs-heuristic contrast.

---

## 8. Cost, launch discipline, and governance

**ETA:** ≤160 positions × M=32 on the primary judge, plus ≤80 on Tier-1. Scaled from the farm-war
run's measured 42 positions × 2 judges in ~1–1.5 h at W16 (≈14.3 worker-minutes per position-judge
cell), and marked up for longer playouts from earlier-game roots: **≈4–6 h at W=14**, with the
**primary judge complete at ≈3–4 h** (judges run sequentially, primary first, so the deciding
statistic lands before the sign check).

**Hard operational constraints, enforced by the launcher, not by discipline:**

- **W = 14 HARD CAP.** Not a tuning choice — the box is DRAM-latency-bound (W* ≈ 14–16 regardless of
  the 16C/32T core count) *and* it is Joshua's interactive machine. All workers `nice -n 19`.
- **The launcher REFUSES to start** if any of `eval_fair_puct.py`, `curvephase_ladder_launcher.sh`,
  `phase_seam_gate`, `night_chain` / `pull_and_chain.sh`, or another `oracle_score_pilot.py` is
  running. The phase-arm ladder has first claim on the box. A timing/throughput tenant beside this
  run contaminates both (memory: `feedback_no_agent_compute_beside_eval`).
- **Detached** (`setsid` + `nohup`), per-position atomic checkpoint, `--resume` — so the run can be
  killed for box priority at any moment and resumed without losing a cell.
- **Memory:** the run is capped under a `systemd-run --user --scope -p MemoryMax=…` scope; the local
  box has taken repeated WSL-VM teardowns from unsegmented memory pressure.

**Governance.** Measurement only. `governance/PRODUCTION.yaml` is untouched. A claim id is minted
only on **G2** or on a **CONVICT**; G1 and EXONERATE are recorded in the readout, `LEVER_INDEX`, and
`results.csv` without a claim. The readout is `MINING_READOUT.md` in this directory and lands with
the standard six-touch close-out.

**AGPL rider (inherited from the BACKLOG entry):** ideas and measurements are fair game; **JCZ code
never gets copied into our leaf.** Every candidate, if convicted, is written from scratch as a native
`LeafConfig` term.

---

## 9. Extraction dry run — counts only, stamped 2026-08-09 before any scoring

Recorded here because §3.2's `K_LATE` ladder and §3.3's matching key are pre-registered to be
resolved from these numbers. **No world was drawn, no continuation played, no Δ computed.**

**Ground-truth check — PASSED, 25,871 / 25,871, zero failures.** Every JCZ-actor ply carrying a
`jcz_message` had that raw wire payload re-inverted, in our own independently replayed position,
back to exactly the action int the archive recorded. This is the strongest available proof that the
root the scorer will replay is the same position JCZ was standing in. 400/400 games used, 0 skipped.

| class | inspected | agree | **disagree** | leaf_tie (excluded) | forced | agreement rate |
|---|---:|---:|---:|---:|---:|---:|
| TILE | 14,190 | 2,669 | **3,702** | 7,817 | 2 | **41.9%** |
| MEEPLE | 11,681 | 6,655 | **3,098** | 1,928 | 0 | **68.2%** |

6,800 candidate disagreements in 6.5 min on one niced core. Read the agreement rates as *conditional
on our leaf expressing a strict preference*: where it does, the two independently-evolved evaluators
pick the same tile placement only 42% of the time and the same meeple decision 68% of the time.
Whether that disagreement costs anything is the whole question, and this table cannot answer it.

**Stratum yields (candidates / distinct games — distinct games is the binding constraint, since
sampling is ≤1 position per game):**

| stratum | candidates | distinct games | verdict |
|---|---:|---:|---|
| STRAT-A (commitment) | 3,992 | **400** | oversupplied ~10× |
| STRAT-B (supply, `K_LATE = 14`) | 387 | **245** | clears the 30-game floor ~8× |
| control pool | 2,421 | 399 | oversupplied |

**No stratum is starved. `K_LATE` stays at the pre-registered 14 — the widening ladder does NOT
fire** (it would have offered 303 games at 20 and 352 at 28; neither is needed). Seats are balanced
in the candidate pool (A: 1,990/2,002; B: 187/200).

Realised design after assignment: **A = 40, B = 40, C = 80, 160 positions over 160 distinct games**
(every cluster a singleton, design effect 1.0 by construction, exactly as §4 intends).
