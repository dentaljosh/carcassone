# PREREG — DEFENSE-PRIMARY: the defense stratum's armed-continuation price, on NEW plies

> ⛔ **COMMITTED BEFORE THE TRIGGER DATA EXISTS.** At the moment this file was
> committed: **0 continuations had been played** for this round, no unit file
> existed under any defense-primary out-dir, no `DEFENSE_PRIMARY.json` existed,
> `governance/` and `governance/PRODUCTION.yaml` were untouched, and
> `experiments/results.csv` carried no row for it. The banked artifacts beside
> this file — [`NEW_PLIES.jsonl`](NEW_PLIES.jsonl), [`ACCRUAL.json`](ACCRUAL.json),
> [`PIN_VERIFICATION.json`](PIN_VERIFICATION.json) — are the CENSUS, which
> **classifies and counts and computes no price** (§2.5, the price wall).
>
> Standing-prereg precedent: [`../cl083_redteam_20260830/E3_PREREG.md`](../cl083_redteam_20260830/E3_PREREG.md)
> (frozen 2026-08-30, fires on a ply count that did not yet exist).
> Parent instrument: [`../e1b_armed_continuation_20260901/PREREG.md`](../e1b_armed_continuation_20260901/PREREG.md).
> Claim served: `governance/CLAIM_REGISTRY.csv` **CL-083** (the policy-conditional clause).
> Owner funding: 2026-09-01, the E-1b adjudication window.

---

## 0. WHY THIS INSTRUMENT EXISTS

E-1b re-priced E-1a's 91 banked divergent plies under an **S1-armed
(dose 0.25, mask 31, scope `opp`) continuation on both seats**, at E-1a's pinned
budget, with the continuation policy family as the only moving part. Its primary
(`invasion − control`) read `E1B-UNRESOLVED` — the §4.3-pre-registered modal null.

Its **named secondary** did something else. The `defense` stratum priced
**+3.47 ± 1.31 (z 2.65)** under the armed continuation against **+0.29 (z 0.18)**
under E-1a's champion continuation — family delta **+3.18 (z ≈ 1.95)**. That is
the direction CL-083's amended policy-conditional clause predicts, in the
stratum whose mechanism argument is the strongest:

> *the champion's PIMC search plays both seats with the champion's own priors, so
> its internal opponent never steals and never invades — "my big open farm is
> safe" is priced true and **defence is priced worthless**. That is a property of
> the CONTINUATION POLICY, not of the ply.*

A 2.65 among ~6 looks, on plies selected by a different round, is **a thread, not
a result**. This prereg is the promotion path E-1b's own read rule named: a
**pre-registered defense-PRIMARY read on NEW plies**, frozen before the plies
exist, fired by a count.

### 0.1 ⚠️ DISCLOSURE — what was seen before this freeze

Blind means blind, so this is stated here rather than discovered later.

1. ⭐ **THE MOTIVATING OBSERVATION IS FULLY VISIBLE AND IS THE REASON THIS ROUND
   EXISTS.** E-1b's defense stratum read **+3.47 ± 1.31 (z 2.65)**, sd across
   plies **6.684**, n = 28 plies in 20 game clusters, and its family delta was
   **+3.18 ± 1.64 (z 1.95)**. Those numbers are quoted throughout this file and
   are the **power model** of §5. ⛔ **They are NOT the bar.** §4 derives the bars
   from the promotion decision and from measured program quantities that predate
   the observation; the observation's own value (+3.47) appears in §5 only as a
   power reference point, never as a threshold. This is E-3's disclosure pattern.
2. **The whole census is visible** — 76 candidate plies, 35 divergent, 15
   divergent defense plies, the per-corpus divergence rates, the budget epochs.
   It is the trigger reader. It contains **no price** (§2.5).
3. **`PIN_VERIFICATION.json` re-derived 20 of E-1a's OWN counterfactual ACTIONS**
   (8 of them `defense`) to prove the pinned champion names the same moves E-1a
   banked. It read no E-1a price, and the plies it touched are excluded from this
   round at game level regardless (§2.1).
4. **No armed continuation has been played on any new ply.** Nothing about this
   round's own outcome exists.

---

## 1. WHAT IS FROZEN HERE

### 1.1 The frozen constants

The machine-readable copy is [`PREREG_CONSTANTS.json`](PREREG_CONSTANTS.json);
`test_defense_primary.py::test_prereg_prose_carries_every_frozen_number` asserts
the prose and the JSON agree, so a constant cannot drift out of its own prereg.

```
# THE TRIGGER
TRIGGER_N_DEFENSE              = 36     new divergent defense plies (any corpus mix)
TRIGGER_N_DEFENSE_CHAMPION_LEG = 20     champion-corpus plies needed for that leg to read a branch

# THE BARS  (pts/ply, mover-signed, armed family)
BAR_FUND           = +2.5
BAR_REOPEN_DEFENSE = +4.5

# THE CONTINUATION — INHERITED from E-1b, byte-for-byte
ARM_DOSE           = 0.25       (S1 G1's adjudicated d*)
ARM_MASK           = 31         (joshua_bot.PRESETS["current"])
ARM_SCOPE          = "opp"      (JrPriorScope::Opp — opponent-mover nodes)
SEATS              = BOTH       (one agent plays both seats; E-1b §2.2)
WORLD_SEED         = 20260828
CONTINUATION_SEED  = 0
M_WORLDS           = 8
ARM_WALL_CAP_S     = 600        (boxes run 1800; E-1a D-1, inherited)
BAND               = NONE       (no new decks are drawn — §8.4)

# THE BUDGET PIN — INHERITED from E-1a/E-1b
PINNED_K_DETS       = 8
PINNED_SIMS_PER_DET = 1376      (=> 11008)
PINNED_EXACT_K      = 2
LEAF_HASH_OF_RECORD = a36d2e15a3b3d71d
TIE ARBITER         = OFF, both seats, both arms

# THE CENSUS SELECTOR — INHERITED VERBATIM from ../e4_ply_pricing_20260827/build_targets.py
DEFENSE_WINDOW_PLIES = 8
CONTROL_TARGET_N     = 50
CONTROL_SEED         = 20260827
```

### 1.2 ⛔ THE BUDGET IS PINNED, NOT READ FROM `PRODUCTION.yaml`

`governance/PRODUCTION.yaml` `champion.fair_deploy` moved to **k16 × 1376 =
22016** on 2026-08-30 and carries a deployed `tiearb B = 64`. E-1a and E-1b both
ran at **k8 × 1376 = 11008**, arbiter-free. A YAML-default champion rebuilt today
would name a **different counterfactual move** and play a **different
continuation**, and neither could be contrasted with E-1b's +3.47 at all. So the
budget is pinned and re-asserted from the **RESOLVED** rust config on every arm
(`G-BUDGET`); the observed YAML values and a `drift_vs_pin` flag are recorded in
`manifest.json` rather than papered over.

⭐ **This pin is already PROVEN, not assumed.**
[`PIN_VERIFICATION.json`](PIN_VERIFICATION.json) replays 20 of E-1a's own frozen
target plies through this round's `build_pinned_champion` and reproduces the
banked `counterfactual_action` **20/20**, and the divergent/agrees verdict
**20/20**, across all four strata (8 of them `defense`). The divergence test that
names a new defense ply is therefore the same test that named E-1a's.

### 1.3 The stratum definition — INHERITED, and generalised in exactly one place

`defense` is [`../e4_ply_pricing_20260827/build_targets.py`](../e4_ply_pricing_20260827/build_targets.py)'s
definition verbatim: *for each owner `invasion` onset ply p, the **opponent's**
most recent TILES-phase ply q < p with p − q ≤ 8; one per invasion,
de-duplicated.* It is a **seat-1 move**, and its price is read from the
**defender's** side — the cost of the defender's choice at the moment before the
owner invades.

The single generalisation: `build_targets.py` says *"the CHAMPION's most recent
tiles ply"* because its corpus was owner-vs-champion only. In an
owner-vs-Carcasum archive the seat-1 agent is **Carcasum**, so the row is stamped
`opponent_kind` and `corpus` and the two can never be pooled without the declared
homogeneity check of §3.2. The selector code is identical (`actor == 1 and
phase == "tiles"`); nothing else moves.

---

## 2. THE PLY SET — how a ply becomes eligible

### 2.1 ⭐ THE EXCLUSION IS AT GAME LEVEL, AND IT IS A SUPERSET OF "the 91"

A ply is **NEW** iff **no prior pricing round selected a ply from its game.**

Not "not among the 91" — **game-level**. E-1a's 91 plies live in **38 games**
(the invasion stratum alone spans 18 of them, the defense stratum 20); a
different ply of the same game shares its deck, its board trajectory, its owner
plan and its CRN tail, so it is not an independent observation of the same
corpus. The exclusion set is computed mechanically at every run from **every**
prior target/diff file — `e4_ply_pricing_20260827` (targets + diffpos, all three
profiles), `e4_continuation_20260828` (E-1a), `e1b_armed_continuation_20260901`
(E-1b), `c1_pricing_prep` (C1) — and their sha256s are stamped into
`manifest.json`. Today that union is **56 games**, and the eligible remainder is
exactly the **16 archives of the 2026-09-01 pull**. Naming an excluded game on
the command line is a **refusal**, not a skip (`G-ELIGIBLE`;
`test_census_refuses_an_old_game_loudly`).

The set can only grow as pulls land; it can never shrink, because a game once
priced is never un-priced.

### 2.2 The corpus is MIXED, and corpus is a DECLARED STRATIFIER

| corpus tag | what it is | seat 1 |
|---|---|---|
| `champion_game` | owner vs the on-device champion | the champion |
| `carcasum_game` | owner vs `carcasum_remote_5000ms` — E-5 **epoch A** | Carcasum @ 5000 ms wall |
| `carcasum_p103500` | owner vs `carcasum_remote_p103500` — E-5 **epoch B** | Carcasum @ fixed 103,500 playouts |

The tag is read from the archive's own `opponent` stamp (and the server's
self-labelled playout pin), never from a date or a directory name. An **unknown
or absent** opponent **refuses** — a corpus nothing conditions on is a corpus
silently pooled, which is the exact hazard `scripts/e4_archives.py` was written
to close.

### 2.3 Two further declared stratifiers, because the divergence GENERATOR is not constant

Every ledger row carries `archive_era` (the archive's own budget/arbiter/profile
stamps) so no tally can be read without conditioning on the epoch, and the
readout must report:

| `divergence_generator` | the mover was | so a disagreement means |
|---|---|---|
| `same_budget_rebuild` | the champion, at k8×1376, arbiter-off | a rebuild/era artefact — **E-1a's own generator** |
| `cross_budget_champion` | the champion, at a different budget and/or arbiter-armed | a **budget/arbiter** difference E-1a's plies did not carry |
| `cross_agent` | not the champion at all (Carcasum) | two **different agents** disagreeing |

⚠️ **Measured, and it matters:** all 7 champion archives of the 2026-09-01 pull
are the **22k epoch** (`played k16 × 1376 = 22016`, tie arbiter armed at B = 32 or
64), so *none* of the currently banked new plies is `same_budget_rebuild`. The
15 banked defense plies are 5 `cross_budget_champion` + 10 `cross_agent`. §7.3
carries the non-inference limit this creates.

### 2.4 ⚠️ DEVIATION D-1 — the control sampler's salt (declared, does not touch the primary)

`build_targets.py` seeded its control sampler with `hash(stem)`, which Python
**randomises per process** (`PYTHONHASHSEED`), so that selector is not
reproducible across runs. It is replaced here by `zlib.crc32(stem)`. This touches
**only** the `control` stratum. The `defense` stratum — the primary — is named by
the invasion detector and the window rule and involves **no sampler at all**.
Asserted by `test_control_sampler_is_reproducible_across_processes`.

### 2.5 ⛔ THE PRICE WALL

The census that produces the trigger **must not look at a price**, or the trigger
becomes a selection on the outcome. `G-NOPRICE` refuses to write any row (or any
`notes` sub-dict) carrying a price-shaped field — `delta_pts_mover`,
`price_played`, `price_counterfactual`, `margin_p0_minus_p1`, `arm_values`,
`solve`, … — and `test_price_wall_refuses_a_price_shaped_row` proves the refusal
fires. The banked ledger is asserted price-free by
`test_the_banked_ledger_carries_no_price`.

### 2.6 Designed so pricing needs NO re-census

Each ledger row carries `game · ply · k · phase · actor · played_action ·
counterfactual_action · counterfactual_agrees · divergent · n_legal · n_plies ·
ply_frac · stratum · corpus · opponent_kind · profile · archive_era (incl.
deck_seed — the CRN world seed) · counterfactual_budget · counterfactual_resolved
· execution · notes`. The confirmation reads this file and launches; it never
re-runs the classifier. Asserted by
`test_ledger_rows_are_self_describing_and_pricable_without_recensus`.

---

## 3. THE MEASUREMENT

### 3.1 The unit, the arms, the estimator — E-1b's, unchanged

One unit is one `(game, ply, world)`, `M_WORLDS = 8` CRN worlds per ply, world
RNG seeded on `(WORLD_SEED, archive deck_seed, ply, world)` — **the E-1a
convention: the archive's own deck seed, no deck band, no new decks**. Two arms
from the identical root:

* **`arm_owner`** — the archive's own move at that ply (at a `defense` ply this is
  the **defender's** played move);
* **`arm_cf`** — the pinned champion's counterfactual move, already banked in
  `NEW_PLIES.jsonl`;

and from each, the continuation policy **plays both seats to termination**. The
price is `delta_pts_mover`, mover-signed exactly as in E-1a/E-1b: positive iff
the played move was worth more points **to the mover** than the counterfactual.

* a ply's price = the mean over its landed CRN worlds;
* a stratum's price = the **unweighted mean over plies**, with a **cluster-robust
  SE clustered on GAME**, plus z.

### 3.2 ⭐ PRIMARY — the `defense` stratum's armed-continuation price on NEW plies

**PRIMARY = mean `delta_pts_mover` over the new divergent `defense` plies, armed
family, pooled across corpora — conditional on `G-HOMOG`.**

`G-HOMOG` (pre-declared, computed before any branch is read):

```
z_homog = (mean_champion_corpus − mean_carcasum_corpus)
          / sqrt(se_champion^2 + se_carcasum^2)        # each cluster-robust on GAME;
                                                       # the corpora share no games
POOL  iff  |z_homog| < 1.96
```

If `G-HOMOG` **fails**, the round reads `DP-CORPUS-SPLIT`: the two corpus legs
are read separately under the same Holm family, and a licence attaches only to
the corpus that clears — with §7.2's limit stated in the readout. A corpus leg
with fewer than **20** plies (`TRIGGER_N_DEFENSE_CHAMPION_LEG`) is **reported with
its CI but reads no branch**; a cluster-robust SE on a handful of game clusters
is not a verdict.

### 3.3 SECONDARY-A — the family-paired difference-in-differences

For each new defense ply, `Δ = price_armed − price_champion_family` over the
**same landed world set**, then the stratum mean of `Δ` with the same
cluster-robust machinery. This is the direct test of *"does the continuation
family move the defense price?"* — E-1b's defense family delta was +3.18
(z 1.95), and it requires the **champion-family co-run** of §5.2.

⛔ Read on its **realized** se. The cross-family ρ is not predictable pre-outcome
(`se_D = se·√(2(1−ρ))`), so no modelled se appears in any branch test; the
realized ρ is reported beside it.

### 3.4 Reported, never a branch input

`control` / `invasion` / `farm_capture` prices and their family deltas on the new
plies (all are censused and priced — see §5.2); `defense − control` as a
descriptive contrast; per-corpus, per-budget-epoch and per-`divergence_generator`
cuts of the primary; coverage and attrition up front (units run, worlds landed vs
void, void reasons, plies with zero landed worlds); the `jr_expansions` scope
witness and its coverage; per-arm cost; the profile and epoch histograms;
`followup_agrees_with_archive` (descriptive — the banked defense consummation
rate is 0.893 and is **not** a price).

---

## 4. THE BARS — written from the decision, not from the instrument

> ⛔ **HOUSE RULE (owner ruling 2026-08-30):** *bars are set at the effect size
> the decision cares about, NEVER at 2σ̂ of the instrument.* What follows writes
> the bars from two decisions, sizes the instrument against them in §5, and —
> where the honest answer is that the round is under-powered — says so, with the
> null's expected read distribution.

### 4.0 The rate arithmetic both bars use

* **The owner's measured margin over the champion at phone conditions is
  ≈ +11 to +16 pts/game** ([`../cl083_redteam_20260830/SYNTHESIS.md`](../cl083_redteam_20260830/SYNTHESIS.md)
  §2.3 — +11.1 first half, +16.2 second half of the 11k epoch); take **+13**.
* **Divergent defense plies per game**: E-1a banked 28 across a 50-game censused
  corpus = **0.56/game**; this census banks 15 across 16 games = **0.94/game**
  (champion corpus 0.71, Carcasum corpus 1.11). Take the range **0.6–1.4/game**
  and, as E-1b §4.1 did, quote the **friendly end (1.4)** so the bar is the one
  the route could most easily clear.

### 4.1 `BAR_FUND = +2.5 pts/ply` — the PRIMARY bar

**The decision it serves:** does per-ply defense value, priced under an
exploit-aware continuation, justify **funding a defense/denial term** — a leaf or
search term that makes the champion price contested futures — at the program's
standard entry fee (an ablation cell plus a neighbour re-sweep)?

**The arithmetic, from measured quantities that predate the observation:**

* the largest deployable fold the program has ever made is the 2026-07-29
  k8×1376 budget promotion, worth **+2.9775 pts/deck** (`governance/PRODUCTION.yaml`
  `budget_folded_in` evidence (1), `results.csv` `cl060_h2h_k8x1376_vs_deploy_k4x688`);
  the 2026-08-30 22k fold was **+1.229 pts/deck**;
* at **1.4** divergent-defense plies/game, a per-ply defense value of **+2.5 pts**
  is **+3.5 pts/game** of value the champion's own continuation cannot see —
  **larger than the largest fold the program has ever banked**, and it is
  recoverable by construction if the missing term is buildable;
* below +2.5, the best case is smaller than a fold already banked at far lower
  cost, and the build is not worth its entry fee.

⛔ **The bar is NOT 2·se.** §5's projected se at the trigger is **1.153**, so
2·se = 2.31. +2.5 sits *near* it by coincidence of the affordable n and is **not**
where it comes from; if the realized se lands anywhere else, the bar does not
move. (It sits **above** 2σ̂ deliberately — a bar below 2σ̂ makes the bounded-null
branch unreachable, which is the other half of the 2026-08-30 failure mode.)
Asserted by `test_bar_is_not_two_sigma_of_the_instrument`.

### 4.2 `BAR_REOPEN_DEFENSE = +4.5 pts/ply` — the second, stronger bar

**The decision it serves:** does the **per-ply route reopen on the DEFENSE
axis**? CL-083's positive half says the owner's edge is *upstream* of single-ply
move choice; reopening means showing the divergent plies can carry a material
share of that edge.

To carry **half** the +13 pts/game edge (+6.5) through divergent defense plies at
**1.4**/game, each must be worth **≈ +4.6 pts** more than the champion's
counterfactual. Rounded to the friendly end: **+4.5**. At the less friendly 0.6
plies/game the same half-edge would need +10.8, so +4.5 is generous to the route,
not to the null.

### 4.3 The detection rule

`DP-FUND` requires **both**: the PRIMARY clears its Holm threshold (§6)
**positive**, **and** the point estimate is **≥ +2.5**. `DP-REOPEN` additionally
requires **≥ +4.5**. A leg is never read on a modelled se; the modelled/realized
se ratio is reported and flagged outside [0.70, 1.43] — flagged, never a branch
input.

---

## 5. POWER, THE TRIGGER, AND WHAT THIS ROUND CANNOT RESOLVE

### 5.1 The trigger, derived

E-1b's realized defense stratum: **sd across plies 6.684**, n = 28 plies in 20
game clusters, **cluster-robust se 1.3077**. The naive se would be
6.684/√28 = 1.2632, so the realized **cluster design effect is 1.0352**. Hence

```
se(n) = 1.0352 x 6.684 / sqrt(n)
      n = 30 -> 1.263      n = 34 -> 1.187      n = 36 -> 1.153
      n = 40 -> 1.094
```

**`TRIGGER_N_DEFENSE = 36`** — the smallest n whose projected se (**1.153**) sits
inside the 1.1–1.2 target band once the measured cluster design effect is priced.
(The naive n for se 1.15 is 34; the design effect carries it to 36.)

**Affordability, from the measured accrual rate.** 15 defense plies are banked
from 16 new games (0.94/game; Carcasum 1.11, champion 0.71). The remaining 21
need roughly **22 more E4 games** at the current mix — ~19 if Carcasum-heavy, ~30
if champion-only. The compute at fire time is small (§5.2); the real cost is
owner game-time, exactly as E-3 states for its own trigger.

### 5.2 Compute at fire time

E-1a's realized rate on the local box is **2.219 s per continuation-ply** at
W = 30, ×1.08 for the arming. A ~36-defense-ply round will carry roughly **90–110
new divergent plies in total** across all four strata (today's ledger: 35
divergent from 16 games), with Σ remaining plies ≈ 80/ply ⇒ order **8,000
continuation-plies × 2 arms × 8 worlds ≈ 130k** per family.

```
armed family alone      ~2.5-3.0 h wall, one box at W = 32
+ champion co-run       ~5-6 h wall single-box, ~2.5-3 h split local+laptop
```

⭐ **The champion-family co-run is REQUIRED** for SECONDARY-A; it is the only way
the DiD exists on new plies, and E-1b's defense signal *is* a family contrast. If
the orchestrator can afford only one family, the **armed** leg alone still reads
the PRIMARY, and SECONDARY-A is then **not run and not reported** — never
substituted by a contrast against E-1a's differently-rooted numbers (§9.3).

### 5.3 ⚠️ WHAT THIS INSTRUMENT CAN AND CANNOT RESOLVE — the uncomfortable line

At the projected `se = 1.153` (n = 36 plies, ~24 game clusters), two-sided against
the 1.96 threshold:

| hypothesised true defense price | z | power |
|---:|---:|---:|
| **+2.5** (`BAR_FUND`) | 2.17 | ⚠️ **≈ 0.58** |
| **+3.47** (E-1b's point — a reference, not a bar) | 3.01 | ≈ 0.85 |
| **+4.5** (`BAR_REOPEN_DEFENSE`) | 3.90 | ≈ 0.97 |

**Read this before the result, not after it.** The round is well powered against
a repeat of E-1b's observation and against the reopen bar, and only **~58 %**
powered at the funding bar itself. Sizing to 0.80 power at +2.5 would need
se ≈ 0.89, i.e. **n ≈ 60** defense plies ≈ 64 games — roughly triple the owner
game-time. That trade is stated here so a sub-threshold read is understood as
*"this size was always going to do this"*.

**The null's expected read distribution, stated pre-outcome** (true effect 0,
se 1.153, PRIMARY tested at 1.96):

| branch | P under a TRUE NULL |
|---|---:|
| `DP-FUND` | ≈ **1.5 %** (needs point ≥ 2.5, i.e. z ≥ 2.17) |
| `DP-NEGATIVE` | ≈ **2.5 %** |
| `DP-NULL-BOUNDED` (95 % upper bound < +2.5) | ≈ **56 %** |
| `DP-UNRESOLVED` | ≈ **40 %** |

⭐ Unlike E-1b (≈ 50 % discharged nothing), a dead-centre null here **discharges a
bound more often than not** — because the bar sits above 2σ̂ rather than at it.
Asserted by `test_null_read_distribution_is_declared_and_sums_to_one`.

⛔ **More WORLDS cannot move any of this.** Between-ply variance dominates
(SYNTHESIS §2.2; E-1b's own defense sd 6.68 across plies at M = 8). Only **more
PLIES** can — which is exactly what the trigger buys.

---

## 6. THE READ RULE

> **Holm step-down, two-sided, family α = 0.05 over exactly two legs
> {PRIMARY, SECONDARY-A}.** The **larger** |z| is tested at `z ≥ 2.2414` (α/2);
> only if it clears is the smaller tested at `z ≥ 1.9600` (α). A leg that does
> not clear fires no branch. Under `DP-CORPUS-SPLIT` the two corpus legs of the
> PRIMARY replace the single PRIMARY leg in the same family of two.

⛔ **The family is exactly two.** `control`, `invasion`, `farm_capture`, the
per-epoch and per-generator cuts, the coverage advisory and every rider are
**outside** it by construction — which is what keeps the correction honest.

| branch | condition | licence |
|---|---|---|
| `DP-VOID-INSTRUMENT` | **any** gate in §7.1 fails | ⛔ **NOTHING.** A void is not a null and may never be quoted as one. Fix, re-run, read again; the voided artefacts stay on disk UNMODIFIED and the amended re-read is a new document. |
| `DP-REOPEN` | PRIMARY clears positive AND point ≥ **+4.5** | **The per-ply route REOPENS on the DEFENSE axis** under an exploit-aware continuation. CL-083's headline clause must carry the policy-conditional qualifier as a **live** limitation. Licenses a CONFIRM on FRESH plies — ⛔ never a re-read of these (CL-084). Also licenses everything `DP-FUND` does. |
| `DP-FUND` | PRIMARY clears positive AND point ≥ **+2.5** | **Funds the defense/denial term build** at the standard entry fee (ablation cell + neighbour re-sweep). CL-083 amendment clause 1 becomes **MANDATORY**. Does **not** reopen the per-ply route. |
| `DP-POSITIVE-SUBTHRESHOLD` | PRIMARY clears positive, point < **+2.5** | *Named at freeze so the map has no hole.* Licenses the policy-conditional clause as measured; funds **no** build — a statistically nonzero price below the decision's own effect size is not a route. |
| `DP-NEGATIVE` | PRIMARY clears negative | Under an exploit-aware continuation the defender's played move at these plies is worth **less** than the champion's counterfactual. Report the magnitude; do **not** narrate a mechanism. |
| `DP-FAMILY-SENSITIVE` | PRIMARY does not clear; SECONDARY-A clears (either sign) | The defense price **IS** policy-conditional: swapping the continuation family moves it. CL-083 amendment clause 1 becomes MANDATORY. **No build is funded** — a moved price is not a large price. |
| `DP-NULL-BOUNDED` | neither leg clears **and** the primary's 95 % upper bound < **+2.5** | **The defense thread is measured and bounded.** E-1b's +3.47 is then a selection artefact of its own multiplicity, the defense clause **retires as a funding candidate**, and CL-083's concession may be restated as *measured and bounded* rather than *unpriced*. ⛔ Quote the bound. |
| `DP-UNRESOLVED` | neither leg clears and the upper bound ≥ **+2.5** | **NOTHING beyond the achieved bound**, which is reported. Re-opening needs **more plies**, never more worlds and never a moved bar. |
| `DP-CORPUS-SPLIT` | `G-HOMOG` fails | The corpora do not price defense alike. Read per corpus under the same Holm family; a licence attaches **only** to the clearing corpus, and if that corpus is Carcasum the §7.2 limit is stated **in the readout, in those words**. |

### 6.1 Riders that are NOT branches

* **Scope-witness coverage** below 0.5 — a flag, reported beside the bound.
* **Realized/modelled se** outside [0.70, 1.43] — a flag.
* **A per-corpus, per-epoch or per-generator cut** — descriptive. The primary is
  the pooled (or split) read the family names; a favourable sub-cut is not a
  finding.

---

## 7. GUARDS AND NON-INFERENCE LIMITS

### 7.1 Gates — every one must pass or the read is `DP-VOID-INSTRUMENT`

`ABSENT` is `FAIL` at every gate — never a skip, never a default. Config is read
from `manifest.json`, statistics from the unit rows; **no knob may be quoted from
a directory name.**

| gate | asserts | where it lives now |
|---|---|---|
| `G-ELIGIBLE` | every priced ply is NEW at game level (§2.1), and the exclusion set's source shas are stamped | census, **live** |
| `G-CORPUS` | every archive's `opponent` stamp resolves to a declared corpus tag; unknown/absent refuses | census, **live** |
| `G-SEAT` | `human_player == 0` on every archive (the strata are written for owner = seat 0) | census, **live** |
| `G-RECON` | the Stage-A replay reproduces the archive's own recorded scores, and the ply counts match | census, **live** |
| `G-NOPRICE` | no census artefact carries a price-shaped field (§2.5) | census, **live** |
| `G-BUDGET` | every arm and every counterfactual resolved **k8 × 1376, exact-K 2, seed 0** off the rust side's own stats | census **live**; continuation at fire time |
| `G-UNARMED` / `G-NOARB` | the **counterfactual** champion is dose-0 and arbiter-free (E-1b armed the continuation, never the counterfactual) | census, **live** |
| `G-LEAF` | the runtime-verified leaf hash equals `a36d2e15a3b3d71d` | census **live**; continuation at fire time |
| `G-PIN` | the pinned champion reproduces E-1a's banked `counterfactual_action` (20/20 today) | **banked**, `PIN_VERIFICATION.json` |
| `G-WITNESS` | the play-derived `jr_expansions` proof that the scope knob BOUND, on every landed arm, with E-1b §2.4's five hard checks | continuation at fire time (E-1b's code, verbatim) |
| `G-NEGCTRL` | the dose-0 census is all-zero and the dose-d\* census has `boosted > 0` on the same opening | continuation at fire time |
| `G-ARMING` | the RESOLVED knobs on every landed arm are exactly dose 0.25 / mask 31 / scope opp | continuation at fire time |
| `G-CRN-PAIR` | the seven CRN witness fields are identical across a unit's two arms; any mismatch VOIDS the pair | continuation at fire time |
| `G-N` | every triggered defense ply is PRICED (≥ 1 landed world) and ≥ 95 % of requested worlds landed | adjudication |
| `G-DECKS` | the priced `(game, ply)` set is EXACTLY the frozen trigger set — no strays, none missing | adjudication |
| `G-RULES` | every row's rules profile was RESOLVED FROM THE ARCHIVE and the R9 import latch was observed equal to expected | adjudication |
| `G-VOID` | void worlds ≤ 10 %, and **no** void carries a correctness reason | adjudication |
| `G-HOMOG` | the pooling decision of §3.2, computed **before** any branch is read | adjudication |
| `RECON` | the primary reproduces from raw rows by a deliberately DIFFERENT code path (flat, sorted, `math.fsum`) | adjudication |

⭐ **`G-ROOT` has no analogue here and is deliberately absent.** E-1b could assert
its units reproduced E-1a's CRN witnesses bit-for-bit because it re-priced the
*same* plies. These plies are new and have no sibling. `G-PIN` + `G-CRN-PAIR`
carry that weight instead, and this substitution is declared here rather than
discovered as a missing gate.

### 7.2 ⚠️ THE CARCASUM LIMIT — state it in these words

**A signal carried by the Carcasum stratum prices CL-083's policy-conditional
clause, but it WEAKENS the champion-edge inference.** In an owner-vs-Carcasum
archive the defender at a `defense` ply is **Carcasum**, and the champion appears
only as the counterfactual. A positive price there says *"at these plies,
Carcasum's move beat the champion's pick under an exploit-aware continuation"* —
which is evidence that defense value is real and policy-conditional, and is
**not** evidence about how the champion defends against the owner. The owner's
edge over the champion is a statement about **champion games**, and only the
`champion_game` leg speaks to it. If the pooled primary clears while the
champion leg alone does not, the readout must say so **explicitly** and must not
narrate the result as an explanation of the owner's anti-champion edge.

### 7.3 ⚠️ THE EPOCH LIMIT — the new champion plies are not E-1a's generator

All 7 champion archives currently eligible were played at **k16 × 1376 = 22016
with the tie arbiter armed**, while the counterfactual is pinned at **11008,
arbiter-off**. Their divergence therefore carries a **budget + arbiter**
component that E-1a's `same_budget_rebuild` plies did not. Consequences, all
pre-registered:

1. the primary is reported **per `divergence_generator`** as well as pooled;
2. a pooled mean across generators is **not** the same estimand as E-1b's +3.47,
   and the readout may not present it as a direct replication of that number;
3. re-pinning the counterfactual to 22016 to "match" would break the contrast
   with E-1a/E-1b in the other direction, and is **not** an option this round has
   — it would be a **new prereg**, not a deviation.

### 7.4 The other non-inference limits

1. **It does not price an exploit-PLAYING continuation.** `scope=opp` makes the
   continuation exploit-**aware**; DESIGN §0 is explicit that the armed agent's
   own move ordering is unchanged. A continuation that itself keeps pressing the
   exploit (S0v2, `scope=own`, a scripted invader) is a DIFFERENT family and
   stays unpriced. A null here does **not** close it, and the readout must say so.
2. **It does not measure S1's strength.** No head-to-head, no elo, no
   `PRODUCTION.yaml` change is licensed by any branch.
3. **It prices the TARGET PLY ONLY.** Every later move — including the same-turn
   meeple follow-up — is the continuation policy's own choice.
4. **It is not band-bearing.** No new decks are drawn; the worlds are
   permutations of the unseen tail of already-archived games, seeded on the
   archive's own `deck_seed`. It consumes **no** deck band, retires none, and
   produces **no** `results.csv` elo row. The launcher still gates on an explicit
   `BAND_CLAIMED` file so "no band is being spent" is an acknowledged decision.
5. **The E4 corpus is nonstationary.** Every ply carries its archive's era stamps
   and no tally may be read without conditioning on the budget epoch.
6. **The defense stratum is named by the INVASION detector** (the window rule),
   so it inherits that detector's properties and its selection is only as good as
   the Stage-A contest census.
7. **It says nothing about cross-game adaptation.** CL-083b's conjunct is
   untouched; E-5 remains the only instrument that separates steering from mining
   a stationary leak.

---

## 8. FORBIDDEN READINGS

1. **`|z| < 2` is never "refuted."** *Killed / dead / does nothing* are forbidden
   readings of a bounded null. **Quote the bound.**
2. **A void is not a null** (IS-A1) and may never be quoted as one.
3. **No contrast with E-1a's or E-1b's numbers is a statistic.** Those rounds
   priced different plies on different roots; only SECONDARY-A's within-round,
   CRN-paired family delta is a paired contrast. A difference of two means across
   differently-rooted runs is not this statistic.
4. **A large defense price with an equally large control price is not a finding
   about defense**; report `defense − control` beside it and say so.
5. **Do not re-read these plies under a moved bar.** A later argument that a bar
   was mis-set is a **new prereg on fresh plies**, not a re-read of this round.
6. **The armed and unarmed censuses are not comparable across strata as a
   mechanism claim.** The census counts expansions, not exploits.
7. **A stratum price larger than the feature's own final points is a bug
   signal**, not a discovery.
8. **The trigger may not be lowered to fire the round.** `TRIGGER_N_DEFENSE` is
   frozen; firing early is firing on a selected count.

---

## 9. THE TRIGGER MECHANICS — what runs, and when

### 9.1 At every E4 pull

```bash
measurement/defense_primary_prep/run_accrual_check.sh
#   exit 0  TRIGGER FIRED  -> the read below is AUTHORIZED (a fired prereg branch
#                             IS the authorization: run it, don't re-ask)
#   exit 1  not yet        -> report the count and the gap; no action
#   exit 3  ERROR/refusal  -> fix it; a refusal is NOT "not yet"
```

It censuses any eligible archive missing from the ledger, updates
`NEW_PLIES.jsonl` and `ACCRUAL.json` idempotently on `(game, ply)`, and prints
the accrual by corpus, budget epoch and divergence generator. It computes no
price. Wire it into the E4 pull runbook and the heartbeat.

### 9.2 At fire time

The instrument is **E-1b's harness, VERBATIM** — `continue_armed.py` +
`adjudicate_e1b.py`, re-pointed at `NEW_PLIES.jsonl` as its target set, with
`G-ROOT` replaced per §7.1 and `G-HOMOG` added. **No harness change without a
fresh prereg.** The two-commit house pattern applies: freeze, then stamp the
freeze sha into `BLIND_COMMIT.json`; deviations after the freeze go in
`DEVIATIONS.md`, never here.

### 9.3 If the champion family cannot be co-run

SECONDARY-A is **not run and not reported**. It is never substituted by a
contrast against E-1b's banked defense number, which sits on different plies and
different roots.

---

## 10. REPRODUCE

```bash
WT=<this worktree>
D=$WT/measurement/defense_primary_prep

$D/run_census.sh classify                 # pure replay, no search   (~1 s)
$D/run_census.sh counterfactual           # 1 pinned champion decision per candidate
$D/run_verify_pin.sh --stratum all --n 20 # G-PIN against E-1a's banked actions
$D/run_accrual_check.sh                   # the trigger read
$D/run_fixture.sh                         # regenerate the pytest fixtures (rarely)

PYTHONPATH=$WT/src:$WT/engine:$WT/scripts \
  /home/doctor/projects/carcassone/.venv/bin/python -m pytest $D/test_defense_primary.py -q
```

`PYTHONPATH` points at the worktree; the venv is editable-installed against the
main tree, so the census records the resolved `carcassonne_ai.__file__` in its
manifest rather than assuming it.
