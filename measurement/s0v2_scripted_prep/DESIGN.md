# S0v2 — THE SCRIPTED EXPLOITER (design + pre-registration)

**Status: DESIGN + PREREG FROZEN 2026-08-28 (commit `s0v2: PRE-REGISTER the
scripted exploiter`, BEFORE the first smoke game); SMOKE RAN 2026-08-28 →
⛔ NEITHER ARM IS S0v2-VALID — both fail G-DAMAGE. The finding that outranks
the bars — S0v2's invasions TIE where the owner's take a MAJORITY, and a tie
denies the incumbent nothing under the vendored full-points-on-tie rule — is
in [SMOKE_READOUT.md](SMOKE_READOUT.md) §2 finding (1).
AMENDED 2026-08-28 (§4.1): the MAJORITY fire, and a RE-SMOKE on seeds
`900000020000..029`. The bars did not move. ROUND 2 RAN 2026-08-28 →
⛔ STILL NO CERTIFIED RULER, and its headline is a METHOD result: the SAME
agent reads G-DAMAGE +2.25 pp on one deck range and +10.66 pp on the next, so
**G-DAMAGE is not resolvable at n=60 and needs a two-range replication clause**
— [SMOKE_READOUT.md](SMOKE_READOUT.md) §6.2. The MAJORITY fire itself works
(took-all 17.9 % → 26.4 % vs the owner's 28.9 %; plan completion 17.6 % →
28.7 %), at ~4 pts/game and under-powered at this n.
AMENDED AGAIN 2026-08-28 (§4.2, FINAL iteration of this funding line): the HOLD
fire, the TWO-RANGE REPLICATION CLAUSE, and G-DENY replacing G-DAMAGE as the
damage gate. Re-smoke on ranges `900000030000..029` + `900000040000..029`.
ROUND 3 RAN 2026-08-28 → ⛔ **PARKED. No arm is valid on either range and
nothing replicates.** The control itself is the unmeasurable thing: over four
disjoint 60-game ranges the champion-vs-champion denial base spans 5.1x and its
took-all rate 7.0x. Pooled two-range denial uplift −0.17 ± 1.04 / −0.57 ± 1.00 —
consistent with ZERO. Next mechanism, named not built: invasion QUALITY (victim
selection by expected realised value), which needs search, not a rule —
[SMOKE_READOUT.md](SMOKE_READOUT.md) §7.**
Owner-funded 2026-08-28 ("start the build now") as the fallback
[`measurement/s0_exploiter_prep/DESIGN.md`](../s0_exploiter_prep/DESIGN.md) §8.5
pre-named and [`SMOKE_READOUT.md`](../s0_exploiter_prep/SMOKE_READOUT.md) §3
fired: *"shape B cannot host an S0, and the next cheapest exploiter is a
**scripted** one … a script carries the plan instead of hoping PUCT does."*

Results → [SMOKE_READOUT.md](SMOKE_READOUT.md).

---

## §0 WHAT THIS IS — AND WHAT IT IS NOT

⛔ **S0v2 IS RULER INFRASTRUCTURE, NOT A STRENGTH LEVER. S0v2 MUST NEVER BE
ADOPTED INTO PRODUCTION.** It is a python-side *policy override* deliberately
built to express ONE mechanism — the owner's invasion steal — and nothing about
it enters the adoption chain, `governance/PRODUCTION.yaml`,
`CHECKPOINT_LINEAGE.csv` or `CLAIM_REGISTRY.csv`. The precedent and the exact
wording are `screen_lib.SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE`; S0's DESIGN §0
says the same thing for the config-only attempt and it carries over verbatim.

Three independent reasons the ban is structural, not decorative:

1. **It is asymmetric by construction.** S0v2 invades and never defends. A
   production agent that only knows the offence half of a mechanism is strictly
   worse than one that knows neither.
2. **It overrides its own search.** The plan module replaces the champion's move
   with a move the champion did not choose. Any margin it earns is not evidence
   that the override is good play — it is evidence about *this opponent on these
   decks*.
3. **Its margin is not evidence about anything else either.** No leaf term, no
   search knob, no dose. Both sides here run the SAME champion leaf
   (`a36d2e15a3b3d71d`); S0v2 changes NO leaf and NO search config, so there is
   not even a knob a reader could mistakenly promote.

**Funding line.** Owner-funded 2026-08-28: build + tests + a signature smoke.
No band, no `results.csv` row, no claim, no gate ladder.

---

## §1 WHY A SCRIPT, AND WHAT EXACTLY IT HAS TO AUTHOR

The S0 smoke's finding (3) is the whole brief: expression is **non-monotone in
dose and saturates at ~1.5× the self-play base**; at α 0.90 the shape-B agent
*starts* plans (47 contest onsets, foothold→victim 2.72 → 8.64 tiles, essentially
the owner's 2.75 → 8.29) but *completes* 28 of 47, because a depth-0 leaf term
makes step one attractive and cannot carry a tile-conditional plan several plies
out. **Completion is the number this build exists to move.**

### 1.1 The target is a census EVENT, not a paraphrase of one

S0v2 targets the exact statistic that grades it. From
[`stage_a_census.py`](../e4_exploit_grading_20260825/stage_a_census.py) §H2 +
[`s0_signature.py`](../s0_exploiter_prep/s0_signature.py), a **deliberate
invasion** is credited to player P iff, at the ply P moved:

* a feature component becomes contested for the FIRST time (both seats hold
  meeples on one component);
* its pre-ply split into meepled sub-components has ≥ 2 occupied parts, and P's
  parts hold **strictly fewer tiles** than the opponent's (a tie is
  `merge_equal`, invader `None`, **not counted**);
* the actor of that ply is P.

Two engine rules then force the plan's shape, and there is no other route:

* a meeple may only be placed on the tile just played;
* the engine forbids claiming a feature the opponent already occupies.

⇒ **SETUP** (play a tile whose own fresh segment is a small component beside a
big opponent-held one) → **FOOTHOLD** (claim it) → **MERGE** (later, play the
tile that joins them). `s0v2_agent.py`'s three fires are exactly those steps.

### 1.2 The detector is the census re-derived, with one honest gap

`invasion_events(pre, post)` re-derives the census's `mech == "merge"` branch
from two `flat_leaf.decompose` snapshots. It agrees with the census on the
"already contested" skip *by construction* — components only grow or merge, so a
feature contested earlier still carries both seats in ONE pre-part.

⚠️ **The one place it cannot agree, and it is the census's own semantics, not a
bug here.** The census's `pre_parts` are collected by a **global union-find id
computed over the WHOLE game**, so at ply *t* it sums the tiles of every
sub-component that *ever* joins that feature — including ones that merge in 20
plies later. S0v2's detector is **causal**: it can only see the parts merged at
ply *t*. Measured on a 10-game dev corpus: **9 agent merge fires, 8 census
deliberate invasions**, the single difference being a farm the agent read as
5 vs 8 tiles and the census, after later merges, as 10 vs 10 (`merge_equal`).
**The census is the scorer of record** — every number in the read-out's bar table
comes from it; the agent's own fire counts are telemetry, and the read-out
reports the reconciliation explicitly.

---

## §2 ARCHITECTURE

```
ScriptedExploiter(base = the CHAMPION OF RECORD, cfg = PlanConfig)
  start_game / advance  -> forwarded to the base (its rust mirror advances on
                           EVERY applied action, including overridden plies)
  move(board):
      pre = Structure(state)                  # flat_leaf.decompose + meeple index
      ledger.refresh(pre)                     # abandon dead plans
      TILES  : 0. MAJORITY fire (amendment §4.1) — the tile that merges one of
                                 my own components into a CONTESTED one where I
                                 am tied or behind, ending strictly ahead.  A
                                 tie denies the incumbent nothing under
                                 full-points-on-tie; a majority denies all of it.
                                 Outranks MERGE.  Never gated.
               1. MERGE   fire — scan legal tiles that land in a cell touching
                                 BOTH one of my components and a bigger
                                 opponent-held one of the same class; take the
                                 best child whose invasion_events name ME the
                                 invader.  Never gated: it IS the exploit, and
                                 the merge-only arm calibrated FREE.
               2. SETUP   fire — else, a tile whose fresh unclaimed segment
                                 becomes a <= stub_max stub beside a worthwhile
                                 victim, with >= setup_min_merge_cells ways to
                                 merge later.  GATED (see below).
      MEEPLES: 2b. REINFORCE-FOOTHOLD (amendment §4.1) — claim the SECOND part
                                 that a later MAJORITY merges in.  GATED, plus a
                                 meeple reserve and a concurrency cap.
               3. FOOTHOLD fire — claim a <= stub_max unclaimed component that is
                                 merge-plausible with a bigger opponent-held one
                                 of the same class; opens a Plan.  GATED.
      otherwise -> base.move(board), byte for byte.
```

**Base = the champion of record, not a heuristic.** Justification: G-COMPETITIVE
is a bar, and the strongest cheap base is the one that makes the games
informative; it also makes the CTRL arm (champion vs champion) the *exact*
counterfactual, so every point of margin is attributable to the plan module and
nothing else. Cost is not a reason to weaken it — the realized cost is ~45
worker-s/game at 2752, and the plan module adds < 1 s/game of python.

**The competitiveness gate is search-grounded, not leaf-grounded.** A SETUP or
FOOTHOLD override fires only if the base agent's own pooled root visits
(`RustFairAgent.last_pooled_visits`) give that action at least
`min_visit_share` of the top action's visits — i.e. only moves the champion's
own search took seriously. This replaced a depth-0 leaf tolerance after the
calibration in §5 measured the leaf bar to be **no gate at all** against a
searching base (the champion's chosen move often has a poor depth-0 leaf, which
makes the comparison bar *lower*, not higher, and lets bad overrides through).
A decision the exact endgame solver owned has NO visit distribution — S0v2
never overrides those. The leaf tolerance survives as a loose secondary bound.

**MERGE is never gated.** It is the event being measured, and gating it on the
champion's own preferences would re-introduce exactly the "the champion doesn't
value this" bias the instrument exists to escape.

### 2.1 Determinism

Every plan decision is a pure function of the engine state and the frozen
`PlanConfig`; candidates are ordered by `(-rank, action index)` so ties resolve
to the lowest action index; no RNG is consulted in `s0v2_agent.py`. `seed`
is carried for provenance and reaches only the base agent. A pure function of
state is a fortiori a function of `(state, seed)`.
`tests/test_s0v2_agent.py::test_the_same_seed_and_config_reproduce_the_game_exactly`
pins it, and `test_disabling_every_fire_reproduces_the_base_agent_exactly` pins
that the module is a pure override.

### 2.2 Files

| file | what |
|---|---|
| [`s0v2_agent.py`](s0v2_agent.py) | the plan module + the wrapper. Reads `flat_leaf.decompose` / `flat_virtual_score_v2_float` through their public entry points. |
| [`s0v2_smoke.py`](s0v2_smoke.py) | the smoke driver — `s0_smoke.py`'s instrument, plumbing and archive schema, with the candidate side wrapped instead of leaf-overridden. |
| [`s0v2_devplay.py`](s0v2_devplay.py) | a search-free dev harness (greedy-leaf base + greedy-leaf opponent) for seconds-per-game iteration. **Not a measurement.** |
| [`run_smoke.sh`](run_smoke.sh) | play / grade, resumable, time-bounded. |
| [`s0v2_readout.py`](s0v2_readout.py) / [`s0v2_bars.py`](s0v2_bars.py) | the telemetry ledger + census outcome distribution, and the pre-registered gate table. |
| [`../../tests/test_s0v2_agent.py`](../../tests/test_s0v2_agent.py) | 33 tests: detector on constructed fixtures, plan state machine, real-board structural contracts, legality, no-parent-mutation, determinism, and the MAJORITY detector + reinforce ledger. |

**No file under `src/carcassonne_ai/`, `engine/`, `scripts/` or `rust/` is
modified by this work.**

---

## §3 THE ARMS

All three run the SAME instrument and the SAME decks, so every contrast is
within-range and deck-matched — the only robust class (`CLAUDE.md`, CL-068).

| arm | `--plan` | what it is |
|---|---|---|
| **CTRL** | `off` | champion vs champion, no plan module. Supplies the base deliberate-invasion rate ON THIS SEED RANGE, so G-EXPRESS(b) is a within-range contrast rather than a cross-range one. (S0's CTRL read **0.500 ± 0.076**/game at n=40 on its own range; that is the *prior*, not the comparator.) |
| **S0V2-M** | `merge` | MERGE fire only. Spends no meeple and no tile choice on setting a plan up; it only authors the event when one is already available. The cheap arm, and the one that isolates "how much of the base rate is opportunity the champion declines". |
| **S0V2-F** | `full` | SETUP → FOOTHOLD → MERGE. The arm that tests whether a script can *manufacture* invasions rather than only harvest them. |

`PROFILES` is frozen inside `s0v2_smoke.py` and the resolved `PlanConfig` is
written into every arm's `manifest.json`, so a read-out can never be re-cut
against a knob the games never used.

---

## §4 PRE-REGISTERED BARS — "IS S0v2 A VALID RULER?"

Written and committed before any smoke game exists. **S0v2-VALID requires all
three, per arm; no pooling across arms, no promotion by sympathy.**

### G-EXPRESS (does it do the thing?) — PRIMARY

The arm's **census** deliberate invasions per game must satisfy **both**:

* **(a) absolute: ≥ 0.90 / game.** Half the owner's measured 1.80/game — the
  same judgment call S0 made, kept identical so the two smokes are readable side
  by side. It is also strictly above the best config-S0 arm ever reached
  (S0-B3, 0.729), so the bar still discriminates.
* **(b) separation: the excess over THIS smoke's own CTRL arm resolved at
  ≥ 2 × the pooled SEM of the two per-game rates.**

⚠️ **Clause (b) is a DELIBERATE, DISCLOSED RELAXATION of S0's literal "≥ 3× the
CTRL rate", and here is the whole reason.** S0 wrote "3×" when the base of
record was **0.14**/game — 3× = 0.42/game, i.e. a clause that sat *below*
clause (a)'s 0.90 and could never bind. Its own smoke then corrected the base to
**0.50**, which turns a mechanical "3×" into **1.50/game — 83 % of the owner's
own 1.80 rate**, and the strictest rung in the ladder. Re-using the multiplier
against the corrected base would silently convert a non-binding clause into the
binding one, which is not what re-deriving a bar against a corrected input is
supposed to do. Clause (b) keeps the job the clause was written for — rule out
"0.90 is just the base rate" — and does it with the statistic the smoke can
actually settle. **The multiple is REPORTED for every arm; it is not gated.**

*Power, stated in advance.* From S0's realized per-game SEMs the deliberate-count
sd is ≈ 0.76/game; at n = 60 per arm the SEM is ≈ 0.10 and the pooled SEM of an
arm-minus-CTRL difference ≈ 0.14, so clause (b) binds at a difference of ≈ 0.28
(rate ≈ 0.78 against a 0.50 base). **Clause (a) at 0.90 is therefore the binding
gate, and that is intentional.**

### G-DAMAGE (do the invasions actually kill champion claims?) — PRIMARY

The **champion's farmer-deployments-scoring-ZERO rate** under the arm, minus the
same rate under THIS smoke's CTRL, must be **≥ +10 percentage points**.
(Frame: 46.2 % against the owner, 5.4 % for the owner himself, 17.02 % in S0's
champion self-play CTRL.)

Reported, **not** gating: champion games farm-zeroed (E4: 18 %); champion
big-claim contested rate (E4: 39.1 %); points denied to the incumbent;
foothold → victim tile profile (owner: 2.75 → 8.29); share of deliberate
invasions landing on FARMS (owner: 41 %).

G-DAMAGE exists because G-EXPRESS can be gamed by cosmetic invasions — stubs
merged onto features worth nothing.

### G-COMPETITIVE (are the games still informative?)

**HARD FLOOR: mean per-game margin (S0v2 − champion) ≥ −25 pts/game.
PREFERRED BAND: ≥ −12 pts/game.** Derivation unchanged from S0 §5 and repeated
because it is a derivation, not a round number: the per-game score-margin sd is
**25.34 pts** (E4 corpus, n=50), so −25 leaves S0v2 winning ≈ 16 % of games —
inside the linear region; at −40 (≈1.6 sd) the win rate falls to ≈ 6 % and the
reference **saturates**, the failure mode that disqualified Tier-1 and is
structural blocker #1 in `CLAUDE.md`.

At n = 60 the margin SEM is ≈ 25.3/√60 ≈ **3.3 pts/game**, so G-COMPETITIVE is
decided only when the observed mean is more than ~2 SEM clear of the floor;
anything inside **−25 ± 6.5** is UNRESOLVED and needs a bigger n before the arm
is used as a ruler. Deck-pairing and deck-matching across arms tighten the
*contrast* between arms but not this absolute.

### Read rules

1. **A smoke cannot mint a verdict.** Invasion COUNTS are the powered statistic
   at this n; margins are context.
2. **An arm that clears G-EXPRESS and G-DAMAGE but fails G-COMPETITIVE is not a
   ruler** — it is a blunderer that happens to invade, and a defence signal
   measured against it would be confounded by its blunders.
3. **No leaf, search or dose conclusion may be drawn from any number here** (§0).
4. Naming a "best of N" when none is valid is promotion by sympathy and is
   forbidden; the honest ranking may be reported WITH its label attached.

---

## §4.1 AMENDMENT 2026-08-28 — the MAJORITY fire

**This is an AMENDMENT, not a rewrite. Every bar in §4 stands exactly as first
registered and none of them moved:** G-EXPRESS ≥ 0.90/game absolute AND ≥ 2 σ
over CTRL; G-DAMAGE ≥ +10 pp on the champion's farmer-zero rate; G-COMPETITIVE
hard floor −25, preferred band −12. What changes is the AGENT (a fourth fire)
and the TELEMETRY registered below. Committed before the first game of the
re-smoke.

**Why.** [SMOKE_READOUT.md](SMOKE_READOUT.md) §2 finding (1): S0v2's invasions
**tie**, the owner's take a **majority** (`invader_took_all` owner 28.9 % vs
S0V2-F 9.3 %; the invader out-numbers the incumbent at scoring in 26 of the
owner's 90 invasions and 5 of S0V2-F's 54). Under the vendored
full-points-on-tie rule a 1-v-1 tie denies the incumbent **exactly zero**, and
G-DAMAGE's statistic only moves when the incumbent loses the majority — which is
why S0V2-F could reach the expression bar and still fail the damage bar at
+2.25 pp.

**The rules constraint that determines the design.** The engine forbids placing
a meeple on a feature the opponent already occupies, so a second meeple can
**never** be added to a contested feature by placement. A majority is reachable
only by **merging a second separately-claimed part in**. The fire is therefore a
TILE-phase fire fed by a meeple-phase one:

| fire | phase | what it does | GATED? |
|---|---|---|---|
| **MAJORITY** | tiles | play the tile that merges one of my own components into a contested one where I am tied or behind, ending strictly ahead | **NO** |
| **REINFORCE-FOOTHOLD** | meeples | claim a small unclaimed component that is merge-plausible with such a contested component | **YES** + two scarcity guards |
| **REINFORCE-SETUP** | tiles | play a tile whose fresh unclaimed segment could become that second part | **YES**, exactly as SETUP |

`majority_events(pre, post, me)` counts two sub-kinds and flags them:
`from_tie=True` (a contested part I was tied on or behind flips) and
`from_tie=False` (two of my parts and one of theirs land 2-v-1 in one ply, which
the census **also** counts as a deliberate invasion — the two counters overlap by
construction and the read-out says so). MAJORITY outranks MERGE in the tile
phase, ranked at 2× a merge's victim points, because a majority takes the
feature *and* denies it where a tie denies nothing.

### The gating decision, and why it is split

**MAJORITY is NOT gated by the search-grounded visit filter**, for exactly the
reason MERGE is not: it spends only a tile choice, no meeple, and it *is* the
mechanism under measurement. Gating the measured mechanism on the champion's own
preferences would re-import the "the champion doesn't value this" bias the whole
instrument exists to escape (§2, and the S0 DESIGN §2 ruler argument).

**REINFORCE-FOOTHOLD keeps the visit gate AND adds two guards the other fires do
not have,** because it is the only fire that commits a **second** meeple to a
feature already committed — the meeple-lockup trade H3′ is about, and the first
smoke measured this build already over-spending farmers (S0V2-F's own farmer
deployments scored ZERO **29.88 %** of the time, against the owner's 5.4 %):

* `min_meeples_for_reinforce = 2` — never spend the last meeple reinforcing;
* `max_open_reinforcements = 2` — a cap on *concurrent* reinforcement plans, so
  the agent cannot mortgage its whole supply on unresolved ties.

**REINFORCE-SETUP is gated exactly as SETUP** (same visit filter, same
`max_setup_fires` cap, same `setup_victim_min_pts` / `setup_min_merge_cells`
bars). It is the expensive fire and nothing about it is relaxed.

### Arms for the re-smoke, and the CTRL decision

**Both G-EXPRESS(b) and G-DAMAGE are CTRL-RELATIVE**, and `CLAUDE.md`'s CL-068
rule says cross-range contrasts are over-dispersed 1.8–2.2×. Re-using the first
smoke's CTRL would make both of those gates cross-range comparisons for the sake
of ~7 minutes of compute. **CTRL is therefore RE-RUN on the new range**, and so
is **S0V2-F with MAJORITY off**, so that the amendment's own effect is a
within-range, deck-matched difference rather than a cross-smoke one.

| arm | `--plan` | what it is |
|---|---|---|
| **CTRL** | `off` | champion vs champion, no plan module |
| **S0V2-F** | `full` | the arm the first smoke ran, `majority_enabled=False` — bit-for-bit the same agent (pinned by `test_majority_off_is_the_previous_agent_exactly`) |
| **S0V2-FM** | `full_major` | identical, plus MAJORITY + REINFORCE |

**Seeds: `900000020000..900000020029`** — 30 decks / 60 games per arm,
deck-paired and deck-matched across all three arms. Disjoint from every prior
range: `900000000000`-area (the S0 smoke), `900000009000`-area (the S0v2
calibration), `900000010000`-area (the first S0v2 smoke). No band, no
`results.csv` row, no claim.

### Additional pre-registered telemetry for this amendment

`majority_fires` · `majority_candidates_seen` · **`majority_from_tie`** (ties
converted to a majority — the amendment's own headline) ·
`reinforce_foothold_fires` · `reinforce_setup_fires` ·
`reinforce_candidates_seen` · `reinforce_vetoed_by_visits` ·
`reinforce_vetoed_by_leaf` · **`meeples_spent_on_reinforcement`** ·
`reinforce_plans_started` / `reinforce_plans_completed` /
`reinforce_plan_completion_rate` (and the same three for `invade` plans) ·
and from the census, the statistic finding (1) named: the **outcome
distribution** (`invader_took_all` / `shared_tie` / `incumbent_held`) and the
**out-numbering-at-score rate** (owner 28.9 %, S0V2-F 9.3 %).

---

## §4.2 AMENDMENT 2026-08-28 (round 3) — the HOLD fire + TWO instrument fixes

**Again an AMENDMENT, not a rewrite, and again committed before the first game
of the round it governs.** G-EXPRESS and G-COMPETITIVE stand **exactly** as
registered in §4. Two things change and both are disclosed here as changes:
a **fourth fire** (HOLD), and the **two instrument fixes** round 2's read-out
named — the two-range replication clause and the gate conflict.

**This is the FINAL iteration of this funding line.** If round 3 does not
produce a certified ruler, the work PARKS with a written diagnosis.

### §4.2.1 The HOLD fire

Round 2 left `incumbent_held` at **17.0 %** against the owner's **4.4 %**: after
MAJORITY, S0v2 *wins* its invasions about as often as the owner does and still
**loses** them four times too often, because the champion merges *its* own second
part in and out-numbers S0v2 back.

A component where I am **strictly behind** scores me **ZERO**. Lifting it back to
a **tie** scores me the feature **IN FULL** (full-points-on-tie). That is HOLD:

| | MAJORITY (§4.1) | **HOLD (§4.2)** |
|---|---|---|
| target | contested, I am tied **or behind** | contested, I am **strictly behind** |
| result | post `me > opp` — strict majority | post `me == opp` — exact tie |
| what it buys | I take the feature **and** they lose it (~2× swing) | my award goes 0 → full; **they lose nothing** |
| disjoint? | yes, by construction — `majority_events` requires `post[me] > post[opp]`, `hold_events` requires `post[me] == post[opp]` | |

HOLD is a **tile-phase** fire and spends **no meeple**. Its targets are a strict
subset of MAJORITY's, so it is fed by the **same** REINFORCE foothold/setup and
therefore inherits, unchanged: `min_meeples_for_reinforce = 2` (never the last
meeple) and `max_open_reinforcements = 2` — **one shared concurrency cap across
reinforcements and holds**, because they are literally the same plan objects.
`test_hold_targets_are_only_components_i_am_losing` pins the subset relation and
`test_hold_on_is_deterministic_legal_and_guarded` pins that HOLD spends no
meeple.

**HOLD is NOT visit-gated**, on the same grounds as MERGE and MAJORITY: it costs
only a tile choice, and gating a measured mechanism on the champion's own
preferences re-imports the bias the instrument exists to escape. Only the three
**meeple-spending** fires (SETUP, FOOTHOLD, REINFORCE-FOOTHOLD) are gated.

### §4.2.2 Fire priority — MERGE > MAJORITY > HOLD > SETUP

Round 2 ran **MAJORITY > MERGE** and §6.3 showed that is the mechanical reason
its expression fell (merge fires 61 → 57, merge candidates 88 → 79). One move
per ply, so the order is an argument about scarcity and about which counter each
fire feeds:

1. **MERGE** — the **only** fire that scores a census *deliberate invasion*
   (the census counts a feature's FIRST contest and nothing after), and the
   scarcest: it needs an un-invaded victim, one of my smaller parts, and the
   right tile, simultaneously.
2. **MAJORITY** — ~2× the point swing, but its targets **persist**: a contested
   feature stays contested for many plies, so deferring one ply rarely loses
   the chance. A merge opportunity is tile-conditional and evaporates.
3. **HOLD** — same swing as MERGE (my award 0 → full) but denies nothing and
   scores no gate directly; it is the fire that stops the instrument being a
   blunderer, which is what G-COMPETITIVE is a bar on.
4. **SETUP** — gated, meeple-feeding, last.

`merge_over_majority` counts the plies where the new order actually bit, so the
fix is measured rather than assumed.

⚠️ **Consequence for the arms:** round 3's `full_major` arm is therefore **NOT
bit-identical to round 2's S0V2-FM** — it carries the priority fix. Both round-3
arms carry it, so the **FMH − FM** contrast isolates HOLD and nothing else.

### §4.2.3 INSTRUMENT FIX 1 — the TWO-RANGE REPLICATION CLAUSE

Round 2 §6.2 proved a single range cannot certify a ruler: the **same agent**
(`S0V2-F` / `S0V2-F2`, pinned bit-for-bit by a test) read G-DAMAGE **+2.25 pp**
on one range and **+10.66 pp** on the next. So:

> **An arm is S0v2-VALID only if it clears EVERY gate on BOTH of two disjoint
> fresh deck ranges, AND its POOLED damage uplift clears the bar at z ≥ 2.**

Ranges, fixed here before any game: **`900000030000..900000030029` (range A)**
and **`900000040000..900000040029` (range B)**, 30 decks × 2 seats × 3 arms each.
Disjoint from `900000002000`-area (the S0 smoke), `900000009000`-area (the
calibration), `900000010000`-area (round 1) and `900000020000`-area (round 2).
**CTRL is run on BOTH ranges** — every gate is CTRL-relative and CL-068 puts
cross-range contrasts at 1.8–2.2× over-dispersion, so a cross-range CTRL would
re-import the very error this clause exists to catch.

### §4.2.4 INSTRUMENT FIX 2 — G-DENY replaces G-DAMAGE as the damage gate

**The choice, stated plainly: G-DAMAGE is DEMOTED to reported-only and
G-DENY becomes the primary damage gate.** Demoting a registered gate mid-line is
exactly the goalpost-moving a prereg exists to prevent, so the reasoning and the
honesty check are both on the record.

*Why G-DAMAGE has to go.* It is (i) **farm-only** — it cannot see a denied city
or road; (ii) a **rate over a small denominator** (~200 farmer deployments), so
it is noisy by construction; (iii) **demonstrably non-reproducible** across
ranges (§6.2); and (iv) it **fights G-EXPRESS for the one move per ply** (§6.3):
G-EXPRESS counts *first contests*, G-DAMAGE needs *majorities on contests
already made*, and no single move can serve both.

*Why G-DENY is the right statistic.* **Points denied to the champion per game** —
the census's own `incumbent_denied`, summed over the features this agent invaded.
It is:

* **unified** — monotone in BOTH invasion count and majority conversion, so the
  fire-priority question stops being a gate conflict and becomes a plain
  maximisation. One move, one counter.
* **zero for a tie**, by construction, which is exactly the property G-DAMAGE was
  introduced to supply (it refuses to reward cosmetic invasions).
* **all-class** — cities, roads and farms, not farms alone.
* **the quantity the ruler actually exists to create.** DESIGN §7's defence cell
  measures `Δ = M1 − M0`, the points a defence term recovers. A defence can
  recover at most what the exploit takes. G-DAMAGE was always a proxy for this;
  G-DENY measures it directly, in points.

**G-DENY, pre-registered:** the arm's deck-matched denial uplift over the
**same-range** CTRL must be **≥ +1.5 pts/game on EACH range**, and the
**two-range pooled** uplift must be **≥ +1.5 at z ≥ 2**.

*Where +1.5 comes from, honestly.* Not from the owner — he denies **12.4
pts/game** and half of that would be an automatic fail for any instrument this
program can build. It comes from **the effect the D-cells chase**: the C ladder's
defence signal is ~**+0.9 pts/deck**, so an exploiter that takes less than
~1.5 pts/game from the champion cannot host a measurable defence contrast at all.
It is a **floor for usefulness**, not an aspiration.

*The honesty check — this bar is NOT easier.* Applied **retrospectively** to
round 2, G-DENY **fails both arms**, including the one that passed G-DAMAGE:

| round-2 arm | G-DAMAGE (old gate) | **G-DENY (new gate)** |
|---|---|---|
| S0V2-F2 | +10.66 pp — **PASS** | **+0.50 ± 1.13 (z 0.44) — FAIL** |
| S0V2-FM | +12.37 pp — **PASS** | **+1.45 ± 1.09 (z 1.33) — FAIL** |

The replacement makes the ladder **strictly harder**, and it moves the arm that
G-DAMAGE certified into the fail column. **G-DAMAGE continues to be reported on
both ranges**, with its own two-range clause applied, so a reader can see whether
the demoted gate would have agreed.

*Power, stated in advance.* Per-game denial has sd ≈ 7–8 pts, so at n=60 the
deck-matched uplift SEM is ≈ 1.1 and at the pooled n=120 it is ≈ 0.8. **A +1.5
uplift is therefore z ≈ 1.4 per range and z ≈ 1.9 pooled — right at the clause's
z ≥ 2.** This smoke may well return **UNRESOLVED on G-DENY**, and that is a
legitimate, pre-registered outcome which will be reported as such rather than
rounded into a pass.

### §4.2.5 S0v2-VALID, restated in full

**VALID = G-EXPRESS AND G-DENY AND G-COMPETITIVE, on BOTH ranges, plus the
pooled G-DENY z ≥ 2.** G-DAMAGE: reported, not gating.

### §4.2.6 Additional pre-registered telemetry

`hold_fires` · `hold_candidates_seen` · **`contested_holdings_defended`**
(distinct holdings HOLD rescued) · **`incumbent_held_conversions`** ·
`merge_over_majority` (plies where the priority fix bit) · and, from the census,
**`denied_per_game` and its per-game vector** (G-DENY's raw material), alongside
everything registered in §4 and §4.1.


### Pre-registered telemetry (reported for every arm; not gating)

The config-S0 diagnosis was *plans START but do not COMPLETE*, so the fire-rate
ledger is part of the deliverable, not a debugging aid:

`plies_seen` · `base_moves` · `merge_fires` · `setup_fires` · `foothold_fires` ·
`merge_candidates_seen` · `setup_candidates_seen` · `foothold_candidates_seen` ·
`setup_vetoed_by_visits` · `foothold_vetoed_by_visits` · `setup_vetoed_by_leaf` ·
`foothold_vetoed_by_leaf` · `override_declined_no_visits` · `scan_plies` ·
**`plans_started` / `plans_completed` / `plans_abandoned` (+ reason) /
`plans_open_at_end` / `plan_completion_rate`** · per-fire `visit_share` and
`leaf_cost` distributions · **`merge_fires` vs census deliberate invasions
(the causal-vs-global-UF reconciliation of §1.2)** · realized s/game and
worker-s/game.

---

## §5 THE CALIBRATION THAT PRECEDED THIS PREREG — DISCLOSED IN FULL

Dose-finding ran BEFORE these bars were written, on seeds **disjoint from the
smoke's**. It is disclosed because a bar written after a peek is only honest if
the peek is on the record.

* **Dev sweeps** (`s0v2_devplay.py`, greedy-leaf both sides, seeds `777000+`,
  n=30/config, 16 configs). Not a measurement — a greedy-leaf opponent is far
  below the champion. Used only to find which knobs move which counter.
* **Champion calibration** (`s0v2_smoke.py`, seeds `900000009000..9003`,
  8 games per arm, the smoke instrument):

  | arm | merge fires/game | mean margin (n=8) |
  |---|---|---|
  | merge only | 0.75 | **+8.4** |
  | merge + foothold | 0.75 | −6.1 |
  | full, loose SETUP (leaf gate only) | 1.00 | **−27.1** → then **−15.6** with the visit gate |
  | full, tight SETUP (the frozen `full` profile) | 0.75 | −3.25 |

  n=8 gives a margin SEM of ≈ 9 pts, so these order the arms; they do not size
  them. Two things they DID establish and that changed the build: the depth-0
  leaf tolerance is not a competitiveness gate against a searching base (§2), and
  the SETUP fire is the expensive one (`setup_victim_min_pts`,
  `setup_min_merge_cells`, `max_setup_fires` exist because of it).

**Honest prior, stated before the smoke:** the calibration's central estimate for
both arms is **≈ 0.75 merge fires/game**, i.e. **below clause (a)'s 0.90 bar**.
S0v2 is expected to be cheaper than any config-S0 arm and only comparably
expressive. The smoke is being run to size that, not to confirm a hoped-for pass.

---

## §6 THE SMOKE

| | |
|---|---|
| instrument | the r3 screening instrument verbatim, via `s0_smoke.py`'s `INSTRUMENT` dict: **k4×688 = 2752 total sims BOTH sides**, rust both sides, `fixed_v1` + `CARCASSONNE_FIX_R9=1`, exact-K 2 marginalized, c_puct 1.5 / τ_p 5 / `float` / `visits`, tie-arbiter OFF both sides |
| opponent | the **champion of record**, leaf `a36d2e15a3b3d71d`. S0v2's own base is the same champion with the same leaf — **no leaf override anywhere**; the invasion/J-rules env is pinned to `0.0` in-process before any import so a stray export cannot move it |
| pairing | deck-paired (both seatings of every deck) AND deck-matched across all three arms |
| **seeds** | **`900000010000`..`900000010029`** — a throwaway range, deliberately **DISJOINT** from the `900000000000`-area range `s0_smoke.py` burned and from the `900000009000`-area calibration range. **NO band is claimed, no `BAND_CLAIM.json`, no `BAND_REGISTRY.csv` row.** These decks are burned and must never be cited. |
| n | **30 decks / 60 games per arm**, three arms = 180 games |
| grading | `stage_a_census.py` verbatim → `s0_signature.py` verbatim |
| box / W | local, `nice -n 19`, **W=8** (another agent's 8-worker job shares the box) |
| cost | ~45 worker-s/game measured in calibration ⇒ ≈ **6 min per 60-game arm** at W8, ≈ 20 min for all three. ⚠️ The box is SHARED, so every wall-clock and s/game figure in the read-out is an UPPER BOUND and must not be used to price a cell. |

**What the smoke can decide:** whether the scripted agent reaches a material
invasion rate and roughly what it costs. **What it cannot decide:** the value of
any leaf term, any margin to better than ±3–4 pts/game, or anything about the
owner.

---

## §7 HOW S0v2 WOULD GET USED IF IT IS VALID

Unchanged from S0 §7 — the 2×2 defence-cell design (`D1` candidate-vs-S0v2,
`D0` champion-vs-S0v2, `D2` candidate-vs-champion; primary statistic
`Δ = M1 − M0` differenced deck by deck; adopt-eligible iff `Δ > 0` at z ≥ 2 AND
`M2 ≥ 0` at z > −2), and its arithmetic (a 2σ verdict on a ~+0.9 pts/deck effect
costs ~1450 decks per arm). Read that section there rather than re-deriving it;
nothing about the exploiter's implementation changes it.

⚠️ S0's finding (2) still stands and still gates that work: the shape-B agent
used as the invader in invasion rounds 2 and 3 does **not** invade above the
champion's own rate, so the C ladder's two +0.9/+1.0 reads are candidate-vs-a-
different-leaf margins, not defence deltas. Whether S0v2 can serve as that
invader is exactly what §4's bars decide.

---

## §8 KNOWN WEAKNESSES

1. **S0v2 is a proxy for a proxy.** It expresses the mechanism through one
   scripted reading of it. The E4 stream against the actual owner remains the
   only judge-free out-of-family arbiter and stays the arbiter.
2. **It invades but does not defend** (§0). Desirable here, disqualifying for
   any production use.
3. **The detector's causal-vs-global-UF gap** (§1.2) means agent fire counts and
   census counts differ by a few percent. The census is the scorer of record.
4. **The visit gate makes the plan partly the champion's.** An override must be
   a move the champion's own search took seriously, which bounds the strength
   cost but also caps how alien S0v2's play can get. If the owner's real steal
   lives *outside* the champion's search support, S0v2 cannot reach it — and
   `setup_vetoed_by_visits` / `foothold_vetoed_by_visits` measure exactly how
   often that bites.
5. **Expression may simply be opportunity-limited.** The calibration says only
   ~8 % of the agent's own tile plies ever have a merge cell available at all,
   and the plain champion already harvests much of that (its self-play base is
   0.50/game). If the smoke confirms it, the honest conclusion is that
   *authoring* invasions at owner rates needs the agent to build toward them many
   plies ahead — a planner, not a per-ply override — and that is a different,
   larger build which this funding line does not cover.
