# PREREG — SYNTHETIC MECHANISM-CORROBORATION OF CL-083's POLICY-CONDITIONAL PRICING CLAUSE

**Status: DESIGN ONLY — FROZEN, NOT LAUNCHED.** No cell has run, no band is
claimed, no `governance/` file is touched, `BLIND_COMMIT.json` reads `PENDING`.
The only compute spent is the pre-freeze DRY smoke disclosed in §0.2.

---

## 0. WHY THIS INSTRUMENT EXISTS

### 0.1 ⛔⛔ SCOPE LIMIT — READ THIS BEFORE ANY NUMBER IN THIS FILE

**This round prices the CLAUSE. It does not price the owner's edge, and it
cannot.**

CL-083's amended clause reads:

> *champion-continuation futures price defense/steering value ~0 by construction
> (the continuation estimand is policy-conditional).*

That is a statement about **an instrument** — about what a continuation-pricing
future can and cannot see, given the policy it conditions on. It is not a
statement about Joshua, about the E4 corpus, or about how much of the owner's
measured margin runs through defense. This round tests the instrument claim on
**synthetic plies from synthetic games**, where plies are unlimited and the
n = 28 owner-ply constraint that produced the motivating observation does not
apply.

Four things follow, and they bind every readout:

1. **No owner ply is in this instrument.** Not one. The corpus is
   champion-vs-armed self-play generated for this round.
2. **The position distribution is not the owner's.** Even a `CLAUSE-CORROBORATED`
   read says the pricing mechanism is policy-conditional *on this distribution*;
   it says nothing about the size of the effect on E4 plies, and it may never be
   quoted as a re-measurement of E-1b's `+3.47`.
3. ⛔ **This cannot substitute for the defense-primary standing read.**
   [`measurement/defense_primary_prep/`](../defense_primary_prep/PREREG.md) is that instrument — a pre-registered,
   accruing primary on real owner plies (trigger 36 plies; accrual 15/36 at the
   time this file was frozen). It is the only instrument in the program licensed
   to say anything about the owner's defense edge. A result here — in either
   direction — **neither discharges it nor changes its bar**, and the two must
   never be pooled. (That path is quoted as a path and not linked, because it
   merged to `main` after this worktree branched.)
4. **"Exploit-expressing" here means S1-armed at `d* = 0.25`, mask 31,
   `scope = opp`.** Per E-1b §8.1 that continuation is exploit-**AWARE**, not
   exploit-**PLAYING** — its own move ordering is unchanged. A different
   exploit family (`scope = own`, the S0v2 scripted invader) stays unpriced by
   this round, and a null here does not close it.

### 0.2 ⚠️ Disclosure — what was seen before this freeze

Nothing outcome-bearing. In full:

1. **The motivating observation, stated openly.** E-1b's `defense` by-catch read
   `+3.47 ± 1.31 (z 2.65)` under the armed continuation against `+0.29` under
   E-1a's champion continuation, family delta `+3.18 ± 1.64`, on **n = 28 owner
   plies** (`../e1b_armed_continuation_20260901/E1B.json`). That number is what
   the owner funded this round to corroborate. It is **disclosed, not used**: it
   sets no bar here (§4 derives the bar from the decision), and it appears in
   §4.3's power table only as "the effect size the motivating observation would
   imply".
2. **A pre-freeze yield + wiring probe was RUN** — 32 synthetic games, 1,185
   selector rows, 576 eligible plies, at production knobs. It measured the
   selector's yield, the shape predicate's discrimination, the scope witness and
   the per-ply cost. It priced **nothing**: no continuation was played, so no
   `delta_pts_mover` existed for any ply, in either family. Its numbers are quoted
   throughout (§2.2, §5) because the design *depends* on them.
3. **A 14-unit DRY smoke was RUN at production knobs** on throwaway seeds
   (`999900000000+`, outside any band) to produce real-emitter fixtures. Those
   14 units DO carry prices. They are on **throwaway games that are not in the
   band and can never enter the frozen target set**, they are kept on disk, and
   they are tabulated in §5.3. No selection, bar or branch was moved after seeing
   them.
4. **The predicate was changed after seeing pre-freeze census data, and here is
   exactly how.** The first draft's shape condition ("a one-tile steal against
   the mover is geometrically available") measured **100 % true** on 46 late
   plies — a predicate with no control stratum is not a contrast. The legality
   step (§2.2 step 3) was added in response, taking the rate to 13.7 %. This was
   a **discrimination fix made on covariates only, before any price existed**;
   it is disclosed here rather than hidden because a selector tuned against
   outcomes would be a fatal defect and a reader must be able to tell the two
   apart.

### 0.3 ⭐ What this round can do that E-1b could not

E-1b's own §4.3 named its limit: *"More WORLDS cannot fix it … Only more PLIES
can."* Synthetic plies are unlimited. This round buys **n = 200 per stratum
against E-1b's 28**, and prices **both continuation families on the identical
world**, which E-1b could only do by comparing against a separately-run E-1a.
That is why it is worth running at all.

---

## 1. WHAT IS FROZEN HERE

### 1.1 The pre-registered constants

```
# --- inherited pins (so this round corroborates the SAME instrument) -------
PINNED_K_DETS        = 8
PINNED_SIMS_PER_DET  = 1376        (=> 11008, E-1a's and E-1b's budget)
PINNED_EXACT_K       = 2
LEAF_HASH_OF_RECORD  = a36d2e15a3b3d71d
ARM_DOSE             = 0.25        (S1 G1's adjudicated d*)
ARM_MASK             = 31          (joshua_bot.PRESETS["current"], S1 G3's mask)
ARM_SCOPE            = "opp"       (JrPriorScope::Opp)
M_WORLDS             = 8
RULES_PROFILE        = fixed_v1    (+ CARCASSONNE_FIX_R9=1, import-latched)

# --- this round's own frozen constants -------------------------------------
WORLD_SEED           = 20260902    ⛔ DIFFERENT from E-1a/E-1b's 20260828
CONTINUATION_SEED    = 0
SELECT_SEED          = 0
MATCH_SEED           = 20260902
GEN_K_DETS           = 4           the position source's budget (see §2.1)
GEN_SIMS_PER_DET     = 1376
PLY_FRAC_MIN/MAX     = 0.62 / 0.88
MIN_UNSEEN_TILES     = 8
SELECT_PHASE         = "tiles"
MAX_PER_GAME_PER_STRATUM = 2
N_TARGET_PER_STRATUM = 200
N_IDENTITY           = 8
BAR_CLAUSE           = +1.75 pts/ply
ARM_WALL_CAP_S       = 1800        (E-1a's D-1 CPU cap, inherited)
```

⛔ **`WORLD_SEED` is deliberately NOT E-1b's.** These are different games
entirely; **no CRN relationship with E-1a or E-1b exists or is claimed**, and
sharing the constant would invite exactly that misreading. Every cross-round
number in this file is a *context* figure, never a paired statistic.

⛔ **The budget is PINNED, not read from `governance/PRODUCTION.yaml`.** The
deployed champion moved to k16 × 1376 = 22016 on 2026-08-30 and gained a
`tiearb B = 64`. Pinning k8 × 1376 keeps this round's "pricing instrument"
identical to the one whose clause is under test. The observed YAML values are
recorded in `manifest.json` (`production_yaml_observed`) as a **disclosure**, not
a config source. The tie arbiter is **OFF on every seat and every family**:
E-1a/E-1b were arbiter-free and `make_production_champion` does not read
`fair_deploy.tiearb`, so this is recorded rather than engineered.

### 1.2 The frozen code

`synth_mech.py` (generator, selector, frozen stratifier, pricer),
`adjudicate_synth.py` (gates + read-rule executor), `test_synth.py` +
`selftest_fixture/` (contract tests on REAL emitter output), this file. The
selection is executed by `synth_mech.build_targets`, which is frozen at the
BLIND_COMMIT and re-asserted by the adjudicator (`G-SELECT`).

---

## 2. THE MEASUREMENT

### 2.1 The position source — a DISTRIBUTION, never a statistic

Synthetic games are played **champion vs S1-armed** (`d* = 0.25`, mask 31,
`scope = opp`), one game per deck seed, the champion at seat `seed % 2` so the
band is seat-balanced by construction. The generation budget is **k4 × 1376 =
5504**, half the pinned budget's determinizations at the **same per-world depth**
— S1 DESIGN measured that `scope = opp` is entirely unexpressed at shallow
per-world depth, so halving `k` rather than `sims_per_det` keeps the arming
expressed while halving the bill. Measured on the probe: the armed seat's census
runs `{71769, 26399, 45370}` with `boosted == total − own_mover` **exactly**, and
the champion seat's is `{0, 0, 0}`.

⛔ **No margin, win rate or elo is read off these games, ever.** They exist to
put the selector in front of contested, developed positions. The champion-vs-armed
pairing is chosen because those are the positions where the two policies' pick
disagreement is a live event; **which agent played a given ply is irrelevant to
the selector**, which recomputes both policies' picks from scratch at every
candidate root.

### 2.2 ⭐ THE PLY SELECTOR — judge-free, pre-declared, outcome-blind

A ply is a **candidate** iff, from a search-free replay of the game:

* `phase == tiles`;
* `len(state.deck) >= 8` — at least 8 unseen tiles, so 8 CRN worlds are
  genuinely distinct completions (8! = 40 320 ≫ M = 8);
* `PLY_FRAC_MIN <= ply / n_plies <= PLY_FRAC_MAX` (0.62–0.88).

The window is *not* a pure cost hack, though it is also that (§5): below it the
board carries no components large enough for the shape predicate to mean
anything, and above it the unseen tail is too short for M = 8 distinct worlds.
Measured: **18.0 candidates per game** (games run 141–144 plies).

At each candidate root, **both policies take one decision at the PINNED 11008
budget** in their own capped child, prefix replayed by `advance` (never searched
— the census at the root is asserted all-zero). Then:

**DIVERGENCE.** `pick_champ != pick_armed`. Measured **28/576 = 4.86 %** on the
pre-freeze probe — which independently reproduces S1 G1's banked flip rate at
`d* = 0.25`, **5.01 % [4.32 %, 5.81 %] on n = 3311 graded plies**
(`../s1_asymmetry_prep/G1_VERDICT.md`). Two corpora, two harnesses, same number.
Non-divergent plies are not discarded: they feed the `identity` set (§2.5).

**SHAPE — three mechanical steps, all Stage-A / S0v2 symbols
(`../s0v2_scripted_prep/s0v2_agent.py`), nothing judged, nothing looking
forward:**

1. **THREAT PAIRS.** `V ∈ Structure.victims_of(mover, PlanConfig())` — a
   component held *exclusively* by the mover, unfinished, `n_tiles >= 5`,
   `potential_pts >= 4` ("worth invading") — crossed with `B` held exclusively by
   the opponent, same feature class, satisfying
   `merge_plausible(struct, V, B)`: a single empty cell touches both, so **one
   tile could merge the opponent's part into the mover's feature**.
2. **MERGE CELLS.** `C = ⋃ (adj_empty(V) ∩ adj_empty(B))` — exactly the cells
   where that one-tile steal could land.
3. ⭐ **PLUGS.** The **mover's own legal tile placements this ply** whose
   coordinate lies in `C` — the defensive options that physically exist right
   now, with the tile actually in hand.

```
    stratum  defense  iff  n_plugs >= 1      (a defensive move EXISTS here)
             control  iff  n_plugs == 0
```

⚠️ **Step 3 is there because steps 1–2 SATURATE, and that was measured, not
guessed.** On 46 late-window plies a live threat pair existed at **100 %** of
them — all farm-class, because in this window no city or road survives
`victim_min_tiles = 5` unfinished and exclusively held. A predicate true
everywhere has no control stratum. With step 3 the rate is **79/576 = 13.7 %**
overall and **6/28 = 21.4 %** among divergent plies — and the resulting claim is
the sharper one: the strata differ in whether *taking a defensive move was an
option*, which is what "defense/steering value" has to mean.

Every count above (`n_plugs`, `n_merge_cells`, `n_threat_pairs`,
`max_threat_pts`, `plug_share`, the threat classes) is written to the artefact,
so the adjudicator re-derives the stratum rather than trusting a stored label.

### 2.3 ⭐ THE MATCHED CONTROL — and why the PRIMARY is a stratum contrast

⛔ **This is the single most important design decision in this file, and it
departs from the funded sketch.** The sketch named "the defense stratum's family
delta" as PRIMARY. **That quantity is biased positive by construction and cannot
test the clause.** Each policy's pick is *that policy's own argmax*, so under its
own continuation it wins by roughly its own root top-2 gap — for reasons with
nothing to do with defense. The raw family delta is therefore positive at
**every** stratum, including one with no defensive content at all.

This is E-1b FORBIDDEN READING 4 (*"a large invasion price with an equally large
control price is NOT a finding about invasions"*) applied to a synthetic corpus,
and it is handled the same way E-1b handled it: **the confirmatory leg is a
stratum contrast**, and the raw family delta is demoted to a rider.

The control stratum is drawn to **reproduce the defense stratum's joint
histogram** over three **terciles** (27 cells):

| covariate | why it is matched |
|---|---|
| `ply_frac` | remaining-game variance and the endgame solver's reach |
| `n_legal` | plug availability rises mechanically with the branching factor |
| `top2_gap_champ` = `(v₁ − v₂)/Σv` on the champion's pooled root visits | ⭐ **the direct proxy for the argmax-selection bias above** |

Cells short of supply are filled from the nearest cell by L1 distance in cell
coordinates and **every fill is recorded** (E-1a's decile match disclosed its
3-of-30 nearest-decile fills; so does this). `n_merge_cells`, `max_threat_pts`
and `n_threat_pairs` are **reported but deliberately not matched** — matching on
the threat *surface* would over-constrain a 27-cell design, and it is nonzero on
essentially every eligible ply anyway.

Quintiles were considered and rejected on paper: 75 cells against a 200-ply
target leaves ~2.7 targets per cell and forces fills across a large share of the
stratum.

At most **2 plies per game per stratum** are taken, in a seeded random order
(never "the first two", which would bias toward the early end of the window). At
the measured yield the cap essentially never binds (~0.19 defense plies/game), so
game-clustering inflation lands near 1.0; §4 still budgets 1.05.

### 2.4 THE CONTRAST — four arms, one world

One unit is one `(game, ply, world)` and runs **four** arms from the identical
root:

| | continuation `champ` (dose 0.0) | continuation `armed` (dose 0.25/31/opp) |
|---|---|---|
| **apply `pick_champ`** | `pick_champ__champ` | `pick_champ__armed` |
| **apply `pick_armed`** | `pick_armed__champ` | `pick_armed__armed` |

In each arm **one agent of that family plays BOTH SEATS to termination**. Both
seats carry the family for E-1b §2.2's reasons, unchanged: the estimand's
conditioning variable is the continuation *policy*, and arming one seat only
would confound the ply's value with a strength difference between two different
agents.

Per family, mover-signed:

```
delta_pts_mover[fam] = ±( margin(pick_armed, fam) − margin(pick_champ, fam) )
                       +  for a seat-0 mover, −  for a seat-1 mover
```

— positive iff the **armed agent's own pick** was worth more points **to the
mover** than the **champion's pick**, under that family's continuation.

```
family_delta(ply) = mean over landed worlds of ( delta[armed] − delta[champ] )
```

The clause's two halves map onto this exactly: it predicts
`delta[champ] ≈ 0` on defense-shaped plies (the champion continuation cannot
see defensive value) and `delta[armed] > 0` (the exploit-aware one can), i.e.
`family_delta > 0` **specifically on the defense stratum**.

### 2.5 ⭐⭐ THE WITNESSES — the dose gate now runs on EVERY unit

E-1b could dose-gate its census only once, in a four-decision pre-flight, because
every one of its arms was armed. **This round plays both doses on every root**,
so the negative control runs *in-band*, on every unit:

* **armed-family arms** must pass E-1b §2.4's five hard checks — all three
  integer keys present (an absent key is a stale pre-R7 `carc_rs` wheel, never
  "the arm did not boost"); `total > 0`; `0 <= own_mover <= total`;
  **`boosted > 0`** (the knob expressed IN PLAY); `boosted <= total − own_mover`
  (the boost stayed inside `opp`'s scope — an inequality on purpose, per the
  PG-A1 lesson). Coverage is ADVISORY and never voids.
* **champion-family arms** must have a census that is **EXACTLY all-zero**. A
  nonzero counter on a dose-0 arm means the census is not dose-gated and every
  `boosted > 0` in the round is uninterpretable.

Measured on the probe: champion-family census all-zero on **1185/1185** selector
rows; `boosted == total − own_mover` exactly on **1185/1185**; and **0/576
eligible rows** fail the armed witness. The 197 rows that do fail are **every one
of them a meeples-phase forced root** (median `n_legal` = 1) where the search
expands nothing at all — a phase this round never selects, and a continuation arm
accumulates its census over ~35 decisions rather than one.

**The prefix must not search.** Every arm and every selector call asserts its
census is still all-zero at the target root, so the recorded census counts
continuation expansions only.

**IDENTITY SET (`G-IDENTITY`).** 8 plies where the two policies **agree**, drawn
from the defense-shaped pool (the closest possible neighbours of the defense
stratum), priced through the *entire* pipeline in both families. Both picks are
the same action, so **every world's `delta_pts_mover` must be exactly `0.0` in
both families**. Any nonzero value is an RNG leak or a nondeterminism in the
harness, and voids the round. They are never priced into a stratum and never
enter a statistic.

### 2.6 CRN and caps

Held identical across a unit's four arms **by construction**:
`root_repr_sha` · `world_deck_sha` + `world_deck_len` · `n_drawn_prefix` ·
`n_legal_root` · `move_idx_at_root`. `world_rng` is seeded only on
`(WORLD_SEED, deck_seed, ply, world)` — **no arm term, no pick term, no family
term** — which is what makes `G-ROOT` checkable *across the two family pricings
on identical worlds* and the family delta a genuinely paired statistic.

⚠️ `det_seed_base_at_root` is **not** in that list: it is a property of the AGENT
(seed × move index), and the two families are different agents. It is recorded
per arm and checked **within family** only.

Every arm runs in its own forked child under `RLIMIT_AS` (`--job-mem-cap-gb 6`)
and `RLIMIT_CPU` (`--arm-cap-secs 1800`, E-1a's D-1: DRAM-contention stalls are
charged to CPU time, and a cap firing on legitimately slow arms biases *which*
plies get priced). An arm over either cap voids its whole unit — a partially
priced unit would break the pairing the estimator rests on. Units are written one
file each, atomically, so the run is resumable.

---

## 3. PRE-REGISTERED READOUTS

1. **Per-unit row**: game, ply, world, stratum, mover, ply fraction, `n_legal`,
   matching cell, the full shape census, both picks, all four arms' final scores,
   `delta_pts_mover` per family, `family_delta`, the CRN witness, the per-arm
   `jr_expansions` census + resolved arming, per-arm cost.
2. **A ply's price** per family = the mean of its landed CRN worlds'
   `delta_pts_mover`; its **family delta** = the mean of `delta[armed] −
   delta[champ]` over the same landed world set (paired by construction).
3. **A stratum's family delta** = the unweighted mean over its plies, with a
   **cluster-robust SE clustered on GAME**, plus z.
4. ⭐ **PRIMARY — `family_delta(defense) − family_delta(control)`**, the
   defense-specific family delta, with the SE built from per-game influence
   contributions **of the difference**. The clause predicts **> 0**.
5. **SECONDARY-A — `delta_champ(defense) − delta_champ(control)`**, the
   clause's *"~0 by construction"* half, read as a **bound**, not a leg (§7).
6. **Riders, outside every family**: `delta_armed(defense) −
   delta_armed(control)`; each stratum's raw family delta (with the §2.3 bias
   caveat attached, always); the realized cross-family correlation ρ; the
   realized between-ply sd; the achieved matching balance; coverage; per-arm cost.
7. **Coverage and attrition, up front**: units run, worlds landed vs void, void
   reasons, per-arm status histogram, plies with zero landed worlds.
8. **Descriptive, never a price**: `followup_agrees_with_pick` rate;
   `jr_expansions` totals; profile histogram; the identity set's exact zeros.

### 3.1 The sign convention (pinned by fixtures, `test_synth.py` §1)

`margin_p0_minus_p1` is the realized final `P0 − P1`. `delta_pts_mover` is
`(pick_armed − pick_champ)` for a seat-0 mover and its negation for a seat-1
mover — positive iff the armed agent's pick was worth more **to the mover**.

---

## 4. THE BAR — written from the decision, not from the instrument

> ⛔ **HOUSE RULE (owner ruling 2026-08-30):** *bars are set at the effect size
> the decision cares about, NEVER at 2σ̂ of the instrument.*

### 4.1 `BAR_CLAUSE = +1.75 pts/ply` on the PRIMARY

**The decision this bar serves:** *may a champion-continuation null be trusted at
the bars this program actually writes?* E-1a and E-1b both wrote their
decision bar at **+3.5 pts/ply**. If swapping the continuation family moves a
defense-shaped ply's price by **less than half that bar**, a champion-continuation
reading cannot be flipped at that instrument's resolution and the clause is a
technicality — the nulls stand as written. If it moves it by **half the bar or
more**, a champion-continuation null at +3.5 could be understating by half the
bar, and CL-083's amendment clause 1 has to be carried as a live limitation on
every continuation-priced null in the program.

Half of +3.5 is **+1.75 pts/ply**. That is the bar.

⛔ **The bar is NOT 2·se.** The modelled se is 0.798 (§4.2); 2·se = 1.596, which
is *near* +1.75 by coincidence of this instrument's size. **If the realized se
lands anywhere else, the bar does not move.** The instrument was sized so that
1.96·se sits comfortably *below* the bar — which is what gives the kill branch
real probability under a true null (§4.3) and is exactly the failure the house
rule exists to prevent.

### 4.2 Sizing

Modelled from E-1b's **realized** artefacts and this round's measured
pre-freeze covariates:

```
between-ply sd of the family delta      7.63   (E-1b's realized `defense` family-delta sd)
game-clustering inflation               1.05   (design cap 2 plies/game/stratum;
                                                measured yield ~0.19 defense plies/game,
                                                so the cap essentially never binds)
se(one stratum's family delta) @ n=200  1.05 x 7.63 / sqrt(200)  =  0.566
se(PRIMARY) = sqrt(2) x 0.566                                    =  0.800
```

n is therefore **200 defense + 200 control** priced plies, **+ 8 identity**.
⛔ **A read requires `n_defense >= 160` AND `n_control >= 160`** (`G-N`); below
that the round reports `SYNTH-HARVEST-SHORT` and prices nothing further.

### 4.3 ⚠️ WHAT THIS INSTRUMENT CAN AND CANNOT RESOLVE

At `se = 0.800`, two-sided α = 0.05:

| hypothesised true PRIMARY | P(`CLAUSE-CORROBORATED`) | reads |
|---:|---:|---|
| **+3.18** (what E-1b's *raw* defense family delta would imply) | **≈ 0.96** | corroborated with high probability |
| **+2.50** | ≈ 0.83 | |
| **+1.75** (the bar) | **≈ 0.50** | ⚠️ a true effect exactly AT the bar corroborates half the time |
| **0.00** | ≈ 0.014 | see below |

**The null's expected read distribution, stated pre-outcome** (true effect 0,
se 0.800):

| branch | P under a TRUE NULL |
|---|---:|
| `CLAUSE-GENERALITY-REFUTED` (95 % upper bound < +1.75) | ≈ **59 %** |
| `SYNTH-UNRESOLVED` | ≈ **36 %** |
| `SYNTH-NEGATIVE` | ≈ 2.5 % |
| `CLAUSE-CORROBORATED` (+ its `-WEAK` variant) | ≈ 1.4 % |
| `SYNTH-POSITIVE-SUBTHRESHOLD` | ≈ 1.1 % |

⭐ **A dead-centre null discharges a decision ~59 % of the time here, against
E-1b's ~46 %.** That improvement is the entire purchase this round makes with
unlimited plies, and it is stated pre-outcome so that a `SYNTH-UNRESOLVED`
reads as *"this size does this a third of the time"* rather than as a surprise.

---

## 5. COMPUTE — the arithmetic, before the launch

### 5.1 The measured rate model

Pre-freeze, at production knobs, `rust_threads = 1`, `nice -n 19`:

```
generation (k4 x 1376)     17.2 s/game  @ W=1     23.4 worker-s/game  @ W=16
selection  (2 dec @ 11008)  2.69 s/ply  @ W=1      3.46 worker-s/ply   @ W=16
                            => 1.345 s per 11008-sim decision, UNCONTENDED
remaining plies at an eligible root   mean 35.0  (min 18, max 52)
eligible candidates per game          18.0
```

⭐ **The ETA model of record is E-1b's own realized local figure,
2.219 s per continuation-decision at W = 30** — same budget, same box class,
contention included. Against this round's measured uncontended 1.345 s that is a
contention factor of **1.65**, which is the factor used below.

⚠️ **This is deliberately conservative, and the honest spread is stated rather
than hidden.** The 14-unit DRY smoke's own realized four-arm mean was
**1.430 s/decision at W = 14** — a contention factor of only ~1.06 at that width.
No measurement of *this* round at W = 32 exists yet, so the larger, externally
realized figure is the one the bill is written against; the uncontended
**1.345 s floor is quoted beside every number** so the range is visible, and the
launcher re-measures before committing (§5.2's gate).

### 5.2 The bill

**HARVEST** — sized on the *independence* product of the two measured rates
(`0.0486 x 0.137 x 18.0 = 0.120` defense plies/game), which is the conservative
reading; the observed joint is higher (`0.187/game`, plug rate 21.4 % among
divergent vs 13.3 % among not — plausible, but n = 28):

```
games needed at 0.120/game                      1,670   (at 0.187/game: 1,070)
HARVEST CAP (frozen)                            2,000 games
  generation  2,000 x 17.2 x 1.65               =  56,760 s =  15.8 worker-h
  selection   2,000 x 18.0 x 2.69 x 1.65        = 159,700 s =  44.4 worker-h
                                                              ---------------
                                                                60.2 worker-h
                                                              = 1.9 h wall @ W=32
```

**PRICING**

```
408 plies x 4 arms x 8 worlds x 35.0 decisions  = 456,960 continuation-decisions
  @ 2.219 s (E-1b realized, W=30)               = 281.9 worker-h = 8.8 h wall @ W=32
  @ 1.345 s (uncontended floor)                 = 170.8 worker-h = 5.3 h wall @ W=32
```

> **ETA: ~10.7 h wall on the local box at W = 32 (range 7.2–12 h).** One box-night.
> ⛔ **Gate: if the smoke-measured rate projects a total above 14 h, this round
> does not launch.**

W = 32 is **throughput-only**: every unit is deterministic in
`(deck_seed, ply, world, pick, family)`, so results are bit-identical at any W
and no reading depends on the worker count.

### 5.3 The DRY smoke — RUN, PASSED (§0.2 item 3)

14 units (7 plies × 2 worlds) at **production knobs** on **throwaway seeds**
outside any band, in `out_DRY/`, adjudicated from their own emitted documents.
Realized figures and the fixture inventory are in `SMOKE_READOUT.json`;
`selftest_fixture/` holds real-emitter copies. ⚠️ The smoke's per-decision rate
is **not** the ETA input — §5.1's contention-matched model is.

### 5.4 The harvest is ADAPTIVE, and that is outcome-blind

Generation + selection run in blocks of 200 games; after each block
`freeze-targets` re-runs and the harvest **stops as soon as
`n_defense >= 200`**, or at the 2,000-game cap. ⭐ **No outcome exists at that
point** — not one continuation has been played — so the stopping rule is a
function of covariates only and introduces no selection bias. It is frozen here
so it cannot later be described as "we kept generating until it looked right".

---

## 6. GUARDS — every one must pass or the read is `SYNTH-VOID-INSTRUMENT`

`ABSENT` is `FAIL` at every gate — never a skip, never a default. Each gate
prints the document and address that answered it. Config is read from
`manifest.json`, statistics from the unit rows; **no knob may be quoted from a
directory name.**

| gate | what it asserts |
|---|---|
| **`G-MANIFEST`** | `manifest.json` exists, is `defense-mech-synth/v1`, and its FROZEN fields (`world_seed`, `m_worlds`, `arming`, `budget_pin`, `targets_sha256`, `leaf_hash_of_record`) are the ones this adjudicator was written against. |
| **`G-LEAF`** | ⭐ **INVERTED** — the runtime-verified leaf hash **EQUALS** `a36d2e15a3b3d71d`. Surface B moves no leaf hash, so a MOVED hash was never this round's doing. |
| **`G-NEGCTRL`** | the pre-flight dose-0 census is all-zero **and** the dose-`d*` census has `boosted > 0`, on the same opening — the census is dose-gated. |
| ⭐⭐ **`G-WITNESS`** | on **every landed arm**: armed-family arms pass §2.5's five hard checks; **champion-family arms are EXACTLY all-zero**. The in-band dose gate. Advisory: mean coverage < 0.5 flags, never voids. |
| **`G-ARMING`** | the **RESOLVED** knobs on every landed arm are read off the rust side's own stats and equal `dose 0.25 / mask 31 / scope opp` (armed) or `dose 0.0` (champion) — never off what the launcher asked for. |
| **`G-BUDGET`** | every arm AND every selector row resolved **k8 × 1376 and exact-K 2**. |
| ⭐ **`G-ROOT`** | within every unit, all four arms agree bit-for-bit on the six CRN witness fields, and `det_seed_base_at_root` agrees within family. **The single-variable proof, across the two family pricings on identical worlds.** A mismatch is a BUG SIGNAL, never attrition. |
| ⭐ **`G-IDENTITY`** | every identity-set unit prices **exactly `0.0`** in **both** families in **every** world. A nonzero value is an RNG leak. |
| **`G-SELECT`** | the priced `(game, ply)` set is EXACTLY the frozen target set; the target file's sha256 matches the manifest; and re-running the frozen `build_targets` on the frozen selector rows reproduces the target file byte-for-byte. |
| **`G-MATCH`** | the achieved standardised mean difference between strata is `|SMD| <= 0.25` on **each** matched covariate (`ply_frac`, `n_legal`, `top2_gap_champ`). ⛔ A GATE, not a rider: unmatched strata reintroduce the §2.3 argmax-selection bias the PRIMARY exists to difference out. Unmatched covariates are reported, never gated. |
| **`G-N`** | `n_defense >= 160` AND `n_control >= 160`, every target ply priced (≥ 1 landed world), and ≥ 95 % of requested worlds landed. |
| **`G-DECKS`** | every priced `deck_seed` lies inside the CLAIMED band (and none in the throwaway sub-range); every world index in [0, 8); every game's `n_plies` consistent with its recorded actions. |
| **`G-RULES`** | every row's rules profile is `fixed_v1` and the R9 import latch was observed equal to expected. |
| **`G-VOID`** | void worlds ≤ 10 %, **and no void carries a correctness reason** (`root_identity_mismatch`, `arm_witness_failed`) — those are guards, not attrition: one is enough to void the round. |
| **`RECON`** | the PRIMARY reproduces from the raw rows by a deliberately DIFFERENT code path (flat, sorted, `math.fsum`). It can only VOID a number, never move it. |

`adjudicate_synth.py --selftest` is a pre-launch checklist item: it proves every
branch is reachable and that **every named defect fires its own gate and voids
the round**.

---

## 7. THE READ RULE

> **ONE confirmatory leg — the PRIMARY — two-sided α = 0.05, `|z| >= 1.9600` on
> its own REALIZED cluster-robust se.** There is no Holm correction because there
> is no multiplicity: SECONDARY-A is a **bound that qualifies the licence**, not
> a leg that can fire a branch, and every rider in §3.6 is outside by
> construction.

⛔ **A leg is never read on a modelled se.** The modelled/realized ratio is
reported and flagged outside [0.70, 1.43] — flagged, never a branch input.

| branch | condition | licence |
|---|---|---|
| `SYNTH-VOID-INSTRUMENT` | **any** gate in §6 fails | ⛔ **NOTHING.** A void is not a null and may never be quoted as one. Fix, re-run, read again; the voided artefacts stay on disk UNMODIFIED and the amended re-read is a new document. |
| `SYNTH-HARVEST-SHORT` | `G-N`'s n floor not reached at the 2,000-game cap | ⛔ **NOTHING.** Report the achieved n and the realized yield. A successor round needs fresh owner funding and a fresh band, never a top-up of this one. |
| `CLAUSE-CORROBORATED` | PRIMARY clears **positive** AND `>= +1.75` AND SECONDARY-A's 95 % CI **contains 0** | **The clause generalises beyond the 28 owner plies.** Champion-continuation futures do price defense-shaped divergences ≈ 0 while an exploit-aware family prices them materially higher, on a corpus with no owner in it. CL-083 amendment clause 1 becomes a **live, general limitation** on every continuation-priced null in the program, and must be carried as such. ⛔ Still licenses **nothing** about the owner's edge (§0.1). |
| `CLAUSE-CORROBORATED-WEAK` | PRIMARY clears **positive** AND `>= +1.75` but SECONDARY-A's CI **excludes 0** | The price **is** policy-conditional, but the champion-continuation half was not ≈ 0 to begin with. Licenses the policy-conditional qualifier; ⛔ the *"~0 by construction"* wording must be **restated as "materially understated"**, because this round measured it not to be ~0. |
| `SYNTH-POSITIVE-SUBTHRESHOLD` | PRIMARY clears **positive**, point `< +1.75` | *Named at freeze so the map has no hole.* A statistically nonzero family effect below the decision's own effect size is not a reason to re-read any existing null. Report and stop. |
| `SYNTH-NEGATIVE` | PRIMARY clears **negative** | Under an exploit-aware continuation, defense-shaped divergences price **lower** relative to matched controls than under the champion continuation — the opposite of the clause's direction. Report the magnitude; ⛔ do **not** narrate a mechanism. |
| `CLAUSE-GENERALITY-REFUTED` | PRIMARY does not clear **and** its 95 % upper bound `< +1.75` | ⭐ **The clause's GENERALITY is refuted.** On 200 matched defense-shaped divergent synthetic plies, swapping the continuation family moves the price by less than half the decision scale the program's continuation bars are written at. CL-083's amendment clause 1 must be **restated as observed on n = 28 owner plies and NOT reproduced on synthetic plies**, and the E-1b defense by-catch stands as an **unreplicated, possibly owner-specific or chance** observation. ⛔ Quote the bound. ⛔ This does **not** refute the E-1b observation itself, and does **not** touch `measurement/defense_primary_prep/`'s standing read. |
| `SYNTH-UNRESOLVED` | neither: doesn't clear and the upper bound `>= +1.75` | **NOTHING beyond the achieved bound**, which is reported. Pre-registered at ≈ 36 % under a true null (§4.3). Re-opening needs **more plies**, not more worlds. |

### 7.1 Riders that are NOT branches

* **Coverage** below 0.5 — a flag; read it as *"the surface is thinner than
  expected"*, report it beside the bound, never a branch input.
* **Realized/modelled se** outside [0.70, 1.43] — a flag.
* **Realized cross-family ρ** — reported beside SECONDARY-A; not predictable
  pre-outcome and never a branch input.
* **The raw family delta of either stratum** — always reported **with the §2.3
  argmax-selection caveat physically attached to it**, and never on its own.
* **`RIDER-SELFCONSISTENCY`** — `delta[champ]` is expected `<= 0` and
  `delta[armed] >= 0` at both strata (each argmax winning under its own
  continuation). A violation is interesting and is reported; it is **advisory**,
  because search noise and the exact-endgame horizon can legitimately invert it
  at small magnitudes.

---

## 8. ⚠️ NON-INFERENCE LIMITS — what this round does NOT measure

1. **It does not measure the owner's edge, and cannot** (§0.1). No owner ply is
   in it. `measurement/defense_primary_prep/` is the standing instrument for that
   question; nothing here discharges it, moves its bar, or may be pooled with it.
2. **It does not price an exploit-PLAYING continuation.** `scope = opp` is
   exploit-AWARE; the armed agent's own move ordering is unchanged. S0v2 /
   `scope = own` remain unpriced, and a null here does not close them.
3. **It does not measure S1's strength.** No head-to-head, no elo, no
   `results.csv` row, no `PRODUCTION.yaml` change is licensed by any branch. S1's
   deployability was answered by G3 (`S1-BOUNDED-NULL`) and is not reopened.
4. **The shape predicate is a mechanical PROXY for "defense", not defense.** It
   asks whether a one-tile steal against the mover is live *and* pluggable now.
   It does not know whether plugging is correct, and a `control` ply is only
   "no plug is legal at this root", not "nothing defensive is happening".
5. **It prices the TARGET PLY ONLY.** Every later move — including the same-turn
   meeple follow-up — is the continuation policy's own choice.
6. **The position distribution is champion-vs-armed self-play in a
   0.62–0.88 ply-fraction window,** which is neither the owner's distribution nor
   the whole game. Nothing here extrapolates outside that window.
7. **The matched control differences out the FIRST-ORDER argmax-selection bias,
   not all of it.** Matching on `top2_gap_champ` makes the two strata comparable
   in the champion's own root decisiveness; a residual stratum-specific component
   of that bias is possible and is not separately identified. This is the
   round's main internal-validity assumption and it is stated here rather than
   buried.
8. **Generation ran at k4 × 1376 while selection and pricing ran at k8 × 1376.**
   The positions are therefore drawn from slightly weaker play than they are
   priced under. This affects the *distribution*, never an estimate, but it is a
   real difference from an all-11008 corpus.

---

## 9. FORBIDDEN READINGS

1. **`|z| < 2` is never "refuted."** *Killed / dead / does nothing* are forbidden
   readings of a bounded null. **Quote the bound.**
2. **A void is not a null** (IS-A1). It may never be quoted as one.
3. ⛔ **No number in this round may be contrasted with E-1a's or E-1b's as a
   statistic.** Different games, a different `WORLD_SEED`, a different selector,
   a different corpus. Any such comparison is context, and must be labelled so.
4. ⛔ **The raw family delta of a single stratum is NOT the clause.** It is
   positive by construction (§2.3). Quoting `family_delta(defense)` without
   `family_delta(control)` beside it is a forbidden reading of this round.
5. **Nothing here licenses a `PRODUCTION.yaml` change**, an S1 re-opening, a
   `results.csv` elo row, or any statement about Joshua's play.
6. **Do not re-read these plies under a moved bar.** A later argument that the
   bar was mis-set is a **new prereg on fresh plies**, not a re-read.
7. **The censuses are not comparable across strata as a mechanism claim.** They
   count expansions, not exploits.
8. **A stratum price larger than the threatened feature's own points is a bug
   signal**, not a discovery.
9. **`CLAUSE-GENERALITY-REFUTED` does not refute the E-1b observation.** It says
   the mechanism did not reproduce on a synthetic corpus. Those are different
   sentences and only the second one is licensed.

---

## 10. REPRODUCE

R9 is import-latched, so every stage runs one process per rules-profile group.
`PYTHONPATH` points at the worktree; the venv is editable-installed against the
main tree, so verify `carcassonne_ai.__file__` resolves inside the worktree.

```bash
WT=<this worktree>
D=$WT/measurement/defense_mech_synth_prep
export PYTHONPATH=$WT/src:$WT/engine:$WT/scripts

# 1. tests + adjudicator selftest (pre-launch checklist)
.venv/bin/python -m pytest $D/test_synth.py -q
python3 $D/adjudicate_synth.py --selftest

# 2. the FREEZE commit, then BAND_CLAIMED + BLIND_COMMIT.json, then:
REPO=$WT $D/launch_local.sh          # negctrl + smoke + adaptive harvest + cell

# 3. the readout
python3 $D/adjudicate_synth.py --units $D/out_local/units \
    --manifest $D/out_local/manifest.json \
    --targets $D/targets_synth.jsonl \
    --selection $D/SELECTION.json --out $D/SYNTH.json
```

---

## 11. THE BAND

**TBD AT LAUNCH — the orchestrator claims it, not this file.** See
[`BAND_CLAIMED.placeholder`](BAND_CLAIMED.placeholder).

⛔ **Unlike E-1a and E-1b, this round DOES spend a deck band.** Every synthetic
game is a fresh deck drawn from its own seed. The placeholder proposes a range
and states the accounting; the tree sweep, the `governance/BAND_REGISTRY.csv`
append and the claim are the orchestrator's, not this agent's.
