# PREREG — E-1b: THE 91 BANKED PLIES, RE-PRICED UNDER AN S1-ARMED CONTINUATION

> **STATUS 2026-09-01: ADJUDICATED `E1B-UNRESOLVED`** — primary invasion−control
> −0.63 ± 2.32 (z −0.27) vs BAR_REOPEN +3.5, the §4.3-pre-registered ~50%-modal
> null read; 728/728 worlds, 0 voids, 12/12 gates PASS. Named-secondary by-catch:
> DEFENSE +3.47 ± 1.31 (z +2.65) under the armed continuation vs +0.29 under
> E-1a's (family delta +3.18, z ≈1.95) — the policy-conditional clause's predicted
> direction; promotion needs a pre-registered defense-primary on NEW plies.
> See `E1B.json` + results.csv `e1b_armed_continuation_*` + DECISIONS 2026-09-01.

> ⛔ **COMMITTED BEFORE ANY E-1b OUTCOME EXISTS.**
> At the moment this file was committed: **0 armed continuations had been
> played**, no `unit_*.json` existed under any E-1b out-dir, no `E1B.json`
> existed, `PRODUCTION.yaml` was untouched, `governance/` was untouched, and
> `experiments/results.csv` carried no E-1b row. House two-commit pattern: this
> commit is the FREEZE; the next commit stamps its sha into
> [`BLIND_COMMIT.json`](BLIND_COMMIT.json). Deviations after the freeze go in
> [`DEVIATIONS.md`](DEVIATIONS.md), never here.
>
> Parent spec: [`../cl083_redteam_20260830/SYNTHESIS.md`](../cl083_redteam_20260830/SYNTHESIS.md)
> §4 **E-1(b)** and its sequencing note (*"S1's armed opponent IS the missing
> continuation family, and re-pricing the 91 banked plies under it is ~1
> box-hour of by-catch that converts CL-083's largest scope hole into a
> measurement"*). Instrument adapted from
> [`../e4_continuation_20260828/PREREG.md`](../e4_continuation_20260828/PREREG.md)
> — **that directory is FROZEN and is not edited by this round.**
> Arming provenance: [`../s1_asymmetry_prep/G1_VERDICT.md`](../s1_asymmetry_prep/G1_VERDICT.md)
> (`G1-EXPRESSES`, **d\* = 0.25**) and
> [`../s1_asymmetry_prep/READ_RULE_G3.md`](../s1_asymmetry_prep/READ_RULE_G3.md)
> §6.1 (the `jr_expansions` witness).
> Claim served: `governance/CLAIM_REGISTRY.csv` **CL-083**.

---

## 0. WHY THIS INSTRUMENT EXISTS

The 2026-08-28 continuation run priced the 91 divergent E4 plies by playing them
out to termination and reading the **realized final score** — no judge, no
evaluator, no search score. Its adjudicated verdict is a **PRIMARY NULL**:
`invasion − control` = **−1.87 ± 1.88, z −0.99**.

The 2026-08-30 CL-083 red-team found that null's largest scope hole, and the
amendment it proposes states it verbatim:

> *"Per-ply value that materialises only under an **exploit-expressing
> (non-champion) continuation** is UNPRICED, not excluded."*

The mechanism is named in
[`../s1_asymmetry_prep/DESIGN.md`](../s1_asymmetry_prep/DESIGN.md) §0: the
champion's PIMC search **plays both seats with the champion's own priors**, so
its internal opponent never steals and never invades — *"my big open farm is
safe" is priced true and defence is priced worthless.* Contested futures are
**never visited**, therefore never priced, therefore a ply whose value lives on
a contested future prices at ~0 by construction. That is a property of the
CONTINUATION POLICY, not of the ply.

S1 built exactly the agent that removes that blindness: `JrPriorScope::Opp` —
the J-rules policy prior (which carries the restored **J2 farm-steal JOIN
predicate**, i.e. the invasion predicate) applied **only at nodes where the
opponent is to move**. G1 adjudicated it `G1-EXPRESSES` at **d\* = 0.25**; G3
played three arms at that dose with `G-WITNESS` passing.

**E-1b is the re-price.** Same 91 plies, same CRN worlds, same arm actions, same
estimator, same budget — **the continuation policy family is the only thing that
moves.**

### 0.1 ⚠️ Disclosure — what was seen before this freeze

Blind means blind, so this is stated here rather than discovered later.

1. **The E-1a numbers are FULLY VISIBLE and are quoted throughout this file.**
   They are the adjudicated verdict of record (`CONTINUATION.json` on the share,
   `results.csv` `e4_continuation_pricing_PRIMARY_NULL_n91_judgefree`), and §4's
   bar arithmetic is anchored to E-1a's realized SE. Nothing about E-1b's own
   outcome exists.
2. **[`CRN_BASELINE.json`](CRN_BASELINE.json) freezes E-1a's 728 CRN witnesses
   and its 728 already-public per-world prices**, so `G-ROOT` and the
   family-paired secondary have a comparator that cannot be re-derived
   favourably afterwards. Freezing published numbers spends no blindness.
3. **A wiring probe** was run before this commit (`continue_armed.py`'s
   negative control, four opening decisions at the pinned budget): dose 0
   emitted an all-zero census, dose 0.25 scope=`opp` emitted
   `total 30689 / own_mover 17206 / boosted 13483`. It played **no target ply**
   and produced **no price**. It is reported in §5.2 as the measurement it is.
4. ⚠️ **THE SMOKE RAN BEFORE THIS COMMIT, AND FOUR ARMED OUTCOMES WERE
   THEREFORE VISIBLE AT FREEZE TIME.** Stated here rather than discovered later,
   on exactly E-1a's D-0 terms. The smoke played **4 of the 728 units** — the
   cheapest ply in each stratum, world 0 only — at the pinned production knobs,
   and it PASSED all eight of its gates. The outcomes seen:

   | stratum | game#ply | E-1b `delta_pts_mover` | E-1a's banked value |
   |---|---|---:|---:|
   | `control` | `1786454767_166575`#100 | **−10** | −7 |
   | `invasion` | `1786454767_166575`#108 | **−11** | −3 |
   | `defense` | `1786904828_407067`#134 | **0** | 0 |
   | `farm_capture` | `1786939252_94231`#134 | **0** | 0 |

   The design, the target set, the estimator, the bars, the branch map and every
   constant in this file were written and on disk BEFORE the smoke ran; the
   smoke's job was to prove the arming binds in play and that the harness emits
   what the adjudicator reads. **Those 4 units stay in the round**: the
   instrument is deterministic in `(deck_seed, ply, world, arm, family)`, so the
   cell recomputes them bit-identically, and excluding them would be a post-hoc
   filter on a seen outcome — which is worse than declaring it. They are 4 of
   728 worlds (0.55 %) and 2 of the 8 world-slots of 2 of the 91 plies.
   Their units live in `out_SMOKE_local_selftest/` and are copied into
   `selftest_fixture/` as the pytest fixtures (§6 of `test_e1b.py`); the cell's
   own `out_local/` never reads them.

---

## 1. WHAT IS FROZEN HERE

### 1.1 The target ply set — INHERITED, byte-identical

[`targets_continuation.jsonl`](targets_continuation.jsonl) is a **byte-identical
copy** of the E-1a frozen target set (sha256
`5c371bdf9b027e347ff56ad44c722adbd2b6f3a8f867ffd2ed3197baa17140bb`, asserted by
`test_e1b.py::test_targets_are_byte_identical_to_the_frozen_e1a_set`). E-1b
selects nothing: **the selection is E-1a's, and it was outcome-blind by
construction there.**

| stratum | n plies | n games | Σ remaining plies | E-1a price |
|---|---:|---:|---:|---:|
| `invasion` | 21 | 18 | 1,986 | −1.399 (se 1.967) |
| `defense` | 28 | 20 | 2,192 | +0.286 (se 1.551) |
| `farm_capture` | 12 | 10 | 360 | +2.531 (se 1.508) |
| `control` | 30 | 24 | 2,996 | +0.467 (se 1.046) |
| **total** | **91** | **38** | **7,534** | PRIMARY **−1.8655 ± 1.8822** |

### 1.2 The pre-registered constants

```
# INHERITED from E-1a — ⛔ any change here breaks the CRN and G-ROOT
WORLD_SEED         = 20260828
CONTINUATION_SEED  = 0
M_WORLDS           = 8
ARM_WALL_CAP_S     = 600        (boxes run 1800; see DEVIATIONS D-1, inherited)

# NEW to E-1b — the single variable, and the pin that keeps it single
ARM_DOSE           = 0.25       (S1 G1's adjudicated d*)
ARM_MASK           = 31         (joshua_bot.PRESETS["current"], S1 G3's mask)
ARM_SCOPE          = "opp"      (JrPriorScope::Opp — opponent-mover nodes)
PINNED_K_DETS      = 8
PINNED_SIMS_PER_DET= 1376       (=> 11008, E-1a's budget)
PINNED_EXACT_K     = 2
LEAF_HASH_OF_RECORD= a36d2e15a3b3d71d
```

### 1.3 ⛔ THE BUDGET IS PINNED, NOT INHERITED FROM `PRODUCTION.yaml`

`governance/PRODUCTION.yaml` `champion.fair_deploy` moved to **k16 × 1376 =
22016** on 2026-08-30 — **after** E-1a ran at k8 × 1376 = 11008 — and the same
fold added a deployed `tiearb B=64`. A YAML-default champion rebuilt today would
therefore differ from E-1a's continuation in **three** ways at once, and its
number could not be contrasted with −1.87 at all.

So E-1b **pins E-1a's budget** and re-asserts it from the RESOLVED rust config
on every arm (`G-BUDGET`). The observed YAML values and the drift flag are
recorded in `manifest.json` (`production_yaml_observed`) rather than papered
over. The tie arbiter stays **OFF on both seats**: E-1a was arbiter-free, and
`make_production_champion` does not read `fair_deploy.tiearb`, so an unmodified
rebuild is arbiter-free without any special handling — this is recorded, not
engineered.

⚠️ **The assumption this creates, stated up front.** G1 adjudicated d\* = 0.25
at the CURRENT deploy budget (k16 × 1376). E-1b arms at the same **per-world
depth** (1376 sims per determinization — the quantity DESIGN's own measured
deviation note identifies as what this surface needs to express: *"at 256 sims
`scope=opp` is entirely unexpressed … that flatline is itself a real pre-G1
prior: this surface needs depth to express at all"*), with half the number of
pooled worlds. **Expression is therefore not assumed — `G-WITNESS` measures it
in every played cell**, and a cell whose arming did not bind VOIDS rather than
banking a config echo.

---

## 2. THE MEASUREMENT

### 2.1 The unit of work, and the two arms — unchanged

One unit is one `(game, ply, world)`. It runs **two arms** from the identical
root state at the target ply:

* **`arm_owner`** — the archive's own move at that ply is applied;
* **`arm_cf`** — the production champion's counterfactual move (banked by the
  2026-08-27 ply-pricing run) is applied instead;

and from each, **the continuation policy plays both seats to termination**. The
price is `delta_pts_mover`, mover-signed (§3.1).

### 2.2 ⭐ WHICH SIDE(S) CARRY THE ARMED POLICY: **BOTH SEATS**

The instrument's continuation policy is **one agent that plays both seats**. The
family swap is therefore symmetric by construction, and the estimand stays
exactly parallel to E-1a's:

> E-1a: *the value of the target ply's move, under subsequent **production-champion**
> play by both seats.*
> **E-1b: *the value of the target ply's move, under subsequent **S1-armed
> (dose 0.25, mask 31, scope=opp)** play by both seats.***

Three reasons this is the right reading of SYNTHESIS §4's *"the armed opponent
IS the missing continuation family"*, and not a one-sided arming:

1. **The hole is about a POLICY FAMILY, not about a seat.** CL-083's conceded
   scope is *"champion-continuation futures price defense/steering value ~0 by
   construction (the continuation estimand is policy-conditional)"*. The
   estimand's conditioning variable is the continuation policy; swapping it
   symmetrically is the minimal, single-variable change.
2. **A one-sided arming would grade a MATCH, not a family.** Arming one seat and
   not the other makes the two seats different agents; the realized margin would
   then confound the ply's value with the strength difference between the two
   agents, and the `arm_owner`/`arm_cf` difference would no longer isolate the
   ply.
3. **`scope=opp` is symmetric in what it fixes.** It boosts expansion priors at
   whichever side is the opponent *of the node's root mover*, so with one agent
   at both seats each side's search now visits futures in which the OTHER side
   invades. That is precisely the blindness DESIGN §0 names, removed on both
   sides of the contest the invasion plies live in.

⚠️ **And the honest limit, stated here rather than in a readout** (see also §8):
`scope=opp` makes the continuation **exploit-AWARE**, not **exploit-PLAYING** —
DESIGN §0 is explicit that *"the champion's own move ordering is unchanged"*.
The scripted-invader family (S0v2; a `scope=own` agent) remains **unpriced by
this round**, and a null here does **not** close it. `scope=own` at the same
dose is the **named licensed follow-on** (`--scope own`, one extra cell, same
cost); it is deliberately **not** an arm of this round, because a second arm
would double the multiplicity of an already bound-limited instrument.

### 2.3 The CRN pairing — and the NEW cross-family witness

Held IDENTICAL across a unit's two arms **by construction**, exactly as in E-1a
(`root_repr_sha` · `world_deck_sha` + `world_deck_len` · `n_drawn_prefix` ·
`n_legal_root` · `det_seed_base_at_root` · `move_idx_at_root`). Any mismatch
VOIDS the pair.

⭐ **E-1b adds a second, stronger identity check.** Every one of those seven
fields is a property of the ROOT and the WORLD and carries **no
continuation-policy term** (`world_rng` is seeded only on
`(WORLD_SEED, deck_seed, ply, world)`). So an E-1b unit **must reproduce its
E-1a sibling's witness bit-for-bit**. `G-ROOT` asserts it against
[`CRN_BASELINE.json`](CRN_BASELINE.json), unit by unit. **That is the machine
check that the continuation family is the only variable** — and it is the same
check that makes §3.4's family-paired statistic a genuinely paired one.

### 2.4 ⭐⭐ THE SCOPE WITNESS — play-derived, never a config echo

A resolved `jrules_prior_scope` in a manifest proves the knob was **requested**.
It cannot prove it **bound**. This program has banked knob-never-bound cells
twice (the FPU knob; the phasegate smoke), and an arm whose knob never bound is
champion-vs-champion wearing the round's name: it moves no leaf hash, sits
inside every rail, and reads as a **clean, credible null**. S1's R7 review is
what added the play-derived census; E-1b reuses it.

Every arm reads `FairAgentRs.stats()`'s
`jr_expansions_{total, own_mover, boosted}` **after** the continuation and
stores it on the unit row. `G-WITNESS` (§6) is HARD on every landed arm:

1. all three keys present and integral — an absent key is a **stale (pre-R7)
   `carc_rs` wheel**, never "the arm did not boost";
2. `total > 0` — the census ran;
3. `0 ≤ own_mover ≤ total`;
4. **`boosted > 0`** — the knob **expressed in play**;
5. **`boosted ≤ total − own_mover`** — the boost never reached a node outside
   `opp`'s scope.

Check 5 is an **inequality on purpose**. The §5.2 probe measured *exact*
equality, but terminal and no-legal-child expansions can legitimately boost
nothing, and a gate written to the reader's expectation rather than the
emitter's real output is the PG-A1 defect that voids healthy cells. `coverage
= boosted / (total − own_mover)` is reported and is **ADVISORY ONLY**.

Two further checks make the witness non-vacuous:

* **`G-NEGCTRL` — the census is DOSE-GATED.** Before any unit runs, the manifest
  emitter builds the **dose-0** champion and plays four real decisions: its
  census must be **all-zero**, while the dose-`d*` agent on the same opening
  must have `boosted > 0`. Without this, a nonzero `boosted` could in principle
  be champion traffic the wheel counts unconditionally.
* **The prefix must not search.** Each arm asserts the census is still all-zero
  at the target root, so the recorded census counts **continuation** expansions
  only (the archive prefix is REPLAYED via `advance`, never searched).

### 2.5 Caps and isolation — inherited unchanged

Every arm runs in its own forked child under `RLIMIT_AS` (`--job-mem-cap-gb 6`)
and `RLIMIT_CPU` (`--arm-cap-secs`, boxes run 1800 s per E-1a's D-1: the cap is
a CPU cap, DRAM-contention stalls are charged to CPU time, and a cap that fires
on legitimately slow contention-hit arms biases WHICH plies get priced). An arm
over either cap is `TIME_SKIPPED` / `OOM_SKIPPED` and **voids its unit's pair** —
a half-priced pair would break the pairing the estimator rests on. Units are
written one file each, atomically, so the run is resumable.

---

## 3. PRE-REGISTERED READOUTS

1. **Per-ply row**: game, ply, world, stratum, K, actor, rules profile, budget
   epoch, both arms' final scores, `delta_pts_mover`, the CRN witness, the
   `jr_expansions` census + resolved arming, the E-1a sibling's price, per-arm
   cost.
2. **A ply's price** = the mean of its landed CRN worlds' `delta_pts_mover`.
3. **A stratum's price** = the unweighted mean over its plies, with a
   **cluster-robust SE clustered on GAME** (91 plies live in 38 games), plus z.
4. ⭐ **PRIMARY — `invasion − control`, under the armed family.** Both arms are
   divergent plies. Games contribute to both, so the contrast's SE is built from
   per-game influence contributions **of the difference**.
5. ⭐ **SECONDARY-A — the FAMILY-PAIRED difference-in-differences.** For each
   ply, `Δ = price_armed − price_E1a` over the **same landed world set**; then
   `Δ(invasion) − Δ(control)` with the same cluster-robust machinery. This is
   the direct test of *"does the continuation family move the price?"*.
6. **`defense` read separately** (the cost of the champion's non-defense) with
   its own family-delta. ⭐ It is the stratum S1's mechanism argument is
   *strongest* about, and it is never pooled into the primary.
7. **`farm_capture − control`** secondary, with the standing CL-083 caveat that
   its two banked reads are correlated `r = 0.78` on 12 shared plies and halve
   when the single highest-leverage ply is dropped.
8. **Coverage and attrition, up front**: units run, worlds landed vs void, void
   reasons, per-arm status histogram, plies with zero landed worlds.
9. **Descriptive, never a price**: `followup_agrees_with_archive` rate;
   `jr_expansions` totals and mean coverage; per-arm cost; profile histogram.

### 3.1 The sign convention (pinned by fixtures, `test_e1b.py` §1)

`margin_p0_minus_p1` is the realized final `P0 − P1`. `delta_pts_mover =
(owner − cf)` for a seat-0 mover and its negation for a seat-1 mover —
**positive iff the played move was worth more points TO THE MOVER** than the
champion's counterfactual, at either seat. Identical to E-1a.

---

## 4. THE BARS — written from the decision, not from the instrument

> ⛔ **HOUSE RULE (owner ruling 2026-08-30):** *bars are set at the effect size
> the decision cares about, NEVER at 2σ̂ of the instrument.* A bar defined as
> 2·se makes the kill branch fire only on a negative point estimate, and a true
> null then reads UNRESOLVED about half the time. What follows writes the bar
> from the decision, sizes the instrument against it, and — because the honest
> answer here is that **we can only afford the bounding direction** — says so,
> with the null's expected read distribution.

### 4.1 `BAR_REOPEN = +3.5 pts/ply` on `invasion − control`

**The decision this bar serves:** does per-ply move value, priced under an
exploit-aware continuation, become large enough to **reopen the per-ply route**
as an explanation of the owner's edge? CL-083's positive half says the edge is
**upstream** of single-ply move choice; reopening the per-ply route means
showing that the divergent plies can carry a material share of that edge.

**The arithmetic, from measured quantities:**

* the owner's measured margin over the champion at phone conditions is
  **≈ +11 to +16 pts/game** (`../cl083_redteam_20260830/SYNTHESIS.md` §2.3 —
  +11.1 first half, +16.2 second half of the 11k budget epoch); take **+13**;
* the owner plays **≈ 1.76 invasion plies/game**, of which the divergent subset
  (this instrument's targets) is 21 plies across 18 games ≈ **1.2/game**;
* to carry even **half** the edge (+6.5 pts/game) through divergent invasion
  plies at 1.2–1.8 per game, each such ply must be worth
  **≈ +3.6 to +5.4 pts** more than an ordinary champion-divergence.

Rounding down to the friendly end of that range gives **+3.5 pts/ply**. Below
it, the per-ply route cannot carry half the edge even if the estimate were
exact, and the steering conclusion stands; at or above it, the route is live and
must be confirmed on fresh plies.

⛔ **The bar is NOT 2·se.** E-1a's realized primary se is **1.8822**; 2·se would
be 3.76, which is *close to* +3.5 by coincidence of this instrument's size and
is **not** where the bar comes from. If the realized se lands anywhere else, the
bar does not move.

### 4.2 The detection rule

`E1B-POSITIVE` requires **both**:

* the primary clears its Holm threshold (§7) **positive** — i.e. `|z| ≥ 2.2414`
  if it is the larger `|z|` of the two legs, `≥ 1.9600` otherwise, on the
  primary's **own realized** cluster-robust se; **and**
* the point estimate is **≥ +3.5**.

A leg is never read on a modelled se. The modelled/realized se ratio is reported
and **flagged outside [0.70, 1.43]** — flagged, never a branch input.

### 4.3 ⚠️ WHAT THIS INSTRUMENT CAN AND CANNOT RESOLVE — the uncomfortable line

At E-1a's realized `se = 1.88` on the primary (**n = 91 plies in 38 game
clusters, M = 8 worlds**):

| hypothesised true `invasion − control` | z | reads |
|---:|---:|---|
| **+5.0** | 2.66 | `E1B-POSITIVE` with high probability |
| **+3.5** (the bar) | 1.86 | ⚠️ **below 1.96** — a true effect AT the bar reads POSITIVE only ~40 % of the time |
| **0.0** | 0.00 | see the distribution below |
| **−1.87** (E-1a's own point) | −0.99 | `E1B-NULL-BOUNDED` |

**Read this before the result, not after it.** The instrument is powered to see
a LARGE effect, not one exactly at the bar. Two-sided power against the Holm
step-2 threshold: **≈ 0.40 at +3.5**, **≈ 0.76 at +5.0**.

**The null's expected read distribution, stated pre-outcome** (true effect 0,
se 1.88, PRIMARY the smaller `|z|` so its threshold is 1.96):

| branch | P under a TRUE NULL |
|---|---:|
| `E1B-POSITIVE` | ≈ **2.5 %** (needs `diff ≥ 3.68`, which also clears +3.5) |
| `E1B-NEGATIVE` | ≈ **2.5 %** |
| `E1B-NULL-BOUNDED` (95 % upper bound < 3.5, i.e. `diff ≤ −0.19`) | ≈ **46 %** |
| `E1B-FAMILY-SENSITIVE` (primary flat, the family delta clears) | unknown — depends on the cross-family ρ, which is not predictable pre-outcome |
| `E1B-UNRESOLVED` | ≈ **49 %** minus whatever FAMILY-SENSITIVE takes |

⛔ **So roughly half of a dead-centre null discharges nothing but a bound wider
than the bar.** That is the honest cost of re-pricing 91 banked plies, and it is
recorded here so an `E1B-UNRESOLVED` reads as *"this size was always going to do
this"* rather than as a surprise. **More WORLDS cannot fix it** — SYNTHESIS §2.2
measured that between-ply variance dominates and worlds provably do not move the
se. Only **more PLIES** can: the full 120 divergent banked plies (vs the 91
selected), or new E4 plies, are the only levers.

### 4.4 SECONDARY-A's bar, and why the family-paired leg exists

SECONDARY-A (`Δ(invasion) − Δ(control)`, the difference-in-differences across
continuation families) is CRN-paired **across families** on identical roots and
worlds, so the ply's own level cancels. Its se is therefore
`se_D = se·√(2(1−ρ))` in the cross-family correlation ρ — **which is not
predictable before the outcome**: `ρ = 0` gives `se_D ≈ 2.66` (worse than the
primary), `ρ = 0.5` gives `≈ 1.88` (no gain), `ρ = 0.86` gives `≈ 1.00`. ⛔ It is
therefore read on its **realized** se, the realized ρ is reported beside it, and
**no modelled se appears in any branch test.**

Its bar is the same **+3.5**, for a different decision: a family delta of that
size means the divergence price is materially policy-conditional, which makes
CL-083 amendment clause 1 **mandatory** — but it does **not** reopen the per-ply
route, because a moved price is not a large price. That asymmetry is why
`E1B-FAMILY-SENSITIVE` is its own branch with its own, weaker licence.

---

## 5. COMPUTE — the arithmetic, before the launch

### 5.1 The model, from E-1a's REALIZED artifacts

Read off the 728 banked E-1a units (728/728 pairs OK, 1456/1456 arms OK, zero
voids):

```
total E-1a arm-seconds                            248,202 s = 68.94 worker-h
total continuation decisions                      119,064
local box  (W=30):  146,758 s / 66,127 dec  =  2.219 s/continuation-ply
laptop box (W=22):  101,443 s / 52,937 dec  =  1.916 s/continuation-ply
worst single arm (measured)                       384.3 s
```

E-1b is a **single-box, local, W = 32** round, so the local rate is the one that
binds:

```
continuation-plies  = 7,534 x 2 arms x 8 worlds        = 120,544
      @ 2.219 s/ply (local, W30-contended)             =  74.3 worker-h
      x 1.08 for the arming (SIZING §3 predicts ms_ratio 1.078-1.085 for `opp`)
                                                        =  80.3 worker-h
      / W = 32                                          =  2.51 h WALL
```

> **ETA: ~2.5 h wall on the local box at W = 32 (range 2.2–3.0 h).**
> ⚠️ SYNTHESIS §4's *"~1.1 two-box hours"* is a **two-box** figure; the
> single-box local equivalent is ~2.5 h. If the orchestrator splits it
> local + laptop as E-1a did, the wall drops to **~1.3–1.5 h**, and E-1a's
> `plan_boxes.py` is the tool for it. **Gate: if the smoke-measured ETA
> exceeds 6 h, this round does not launch.**

W = 32 is **throughput-only**: every unit is deterministic in
`(deck_seed, ply, world, arm, family)`, so results are bit-identical at any W
and no reading depends on the worker count.

### 5.2 The wiring probe (measured, pre-freeze — see §0.1)

Four opening decisions at the pinned k8 × 1376 budget, `rust_threads = 1`:

| build | census `{total, own_mover, boosted}` | reads |
|---|---|---|
| dose **0** (the unmodified champion) | `{0, 0, 0}` | the counters are **dose-gated** |
| dose **0.25**, mask 31, scope `opp` | `{30689, 17206, 13483}` | `boosted > 0`; and `13483 == 30689 − 17206` **exactly** — the partition is clean |

The exact partition is recorded as an **expectation**, not as a gate (§2.4).

### 5.3 The smoke — RUN, PASSED (see §0.1's disclosure)

Four target plies — one per stratum, the cheapest in each — at **PRODUCTION
knobs**, 1 world each, in a separate `out_SMOKE_*` directory with its own
`manifest.json`. It is **adjudicated from its own emitted documents** by
`adjudicate_e1b.py --smoke`, which **exits non-zero on an empty cell**, on a
cell with no priced pair, on an absent manifest, on a failed witness, on a
budget/arming drift, or on any correctness void — so the launcher's `|| DIE` is
reachable. ⛔ The adjudicator writes `SMOKE_VALIDATION.json` itself via `--out`;
a shell `| tee` would have made the pipeline's exit status *tee's* and swallowed
the very refusal the smoke exists to produce (found by
`test_the_smoke_adjudicator_refuses_an_EMPTY_cell`).

**Realized** (2026-09-01, local box, W = 4, `rust_threads = 1`):

```
units            4/4 priced · arms 8/8 OK · voids 0
gates            8/8 PASS  (incl. G-ROOT on all 4 — E-1b landed on E-1a's roots)
census (summed)  total 975,426 · own_mover 436,997 · boosted 538,429
                 boosted == total - own_mover EXACTLY; coverage 1.000 on every arm
continuation     174 plies over 8 arms, 141.7 arm-seconds
```

⚠️ The smoke's 0.27–1.08 s/continuation-ply is **not** the ETA input: it is
uncontended (W = 4) and its plies are late-game (few legal moves). §5.1's
contention-matched, whole-set E-1a figure is the model of record.

---

## 6. GUARDS — every one must pass or the read is `E1B-VOID-INSTRUMENT`

`ABSENT` is `FAIL` at every gate — never a skip, never a default. Each gate
prints the document and address that answered it. Config is read from
`manifest.json`, statistics from the unit rows; **no knob may be quoted from a
directory name.**

| gate | what it asserts |
|---|---|
| **`G-MANIFEST`** | `manifest.json` exists, is `e1b-armed-continuation/v1`, and its FROZEN fields (`m_worlds`, `arming`, `budget_pin`, the targets/baseline sha256s) are the ones this adjudicator was written against. |
| **`G-LEAF`** | ⭐ **INVERTED** — the runtime-verified leaf hash **EQUALS** `a36d2e15a3b3d71d` and the resolved leaf is curve125 / cap 8 / value_blend 0. Surface B moves no leaf hash, so a MOVED hash was never this round's doing. |
| **`G-NEGCTRL`** | the dose-0 census is all-zero **and** the dose-`d*` census has `boosted > 0`, on the same opening — the census is dose-gated. |
| ⭐⭐ **`G-WITNESS`** | the play-derived proof that the scope knob BOUND, on **every landed arm** (§2.4's five hard checks). Advisory: mean coverage < 0.5 flags, never voids. |
| **`G-ARMING`** | the **RESOLVED** knobs on every landed arm are exactly `dose 0.25 / mask 31 / scope opp`, read off the rust side's own stats — never off what the launcher asked for. |
| **`G-BUDGET`** | every arm resolved **k8 × 1376 and exact-K 2**. An arm at today's YAML k16 would move the budget and the family at once. |
| ⭐ **`G-ROOT`** | every unit's seven CRN witness fields equal its E-1a sibling's, from `CRN_BASELINE.json`. **The single-variable proof.** A mismatch is a BUG SIGNAL, never attrition. |
| **`G-N`** | **every one of the 91 frozen target plies is PRICED (≥ 1 landed CRN world), AND at least 95 % of the 728 requested worlds landed.** |
| **`G-DECKS`** | **the priced `(game, ply)` set is EXACTLY the frozen 91 targets — no strays, none missing — and every world index lies in [0, 8).** |
| **`G-RULES`** | every row's rules profile was RESOLVED FROM THE ARCHIVE and agrees with the frozen target's stamp, and the R9 import latch was observed equal to expected. |
| **`G-VOID`** | void worlds ≤ 10 %, **and no void carries a correctness reason** (`crn_witness_mismatch`, `root_identity_mismatch`, `arm_witness_failed`) — those are guards, not attrition: one is enough to void the round. |
| **`RECON`** | the primary reproduces from the raw rows by a deliberately DIFFERENT code path (flat, sorted, `math.fsum`). It can only VOID a number, never move it. |

`adjudicate_e1b.py --selftest` is a pre-launch checklist item: it proves every
branch is reachable and that **every named defect fires its own gate and voids
the round**.

---

## 7. THE READ RULE

> **Holm step-down, two-sided, family α = 0.05 over exactly two legs
> {PRIMARY, SECONDARY-A}.** The **larger** |z| is tested at `z ≥ 2.2414` (α/2);
> only if it clears is the smaller tested at `z ≥ 1.9600` (α). A leg that does
> not clear fires no branch.

⛔ **The family is exactly two.** `defense`, `farm_capture − control`, the
coverage advisory, the descriptive rates and every rider are **outside** it by
construction — which is what keeps the correction honest.

| branch | condition | licence |
|---|---|---|
| `E1B-VOID-INSTRUMENT` | **any** gate in §6 fails | ⛔ **NOTHING.** A void is not a null and may never be quoted as one. Fix, re-run, read again; the voided artefacts stay on disk UNMODIFIED and the amended re-read is a new document. |
| `E1B-POSITIVE` | PRIMARY clears **positive** AND `diff ≥ +3.5` | **The per-ply route REOPENS under an exploit-aware continuation.** CL-083's headline clause must carry the policy-conditional qualifier as a **live** limitation, not a conceded one. Licenses a **CONFIRM on FRESH plies** — ⛔ never a re-read of these 91; the selecting observation is never pooled with the confirming one (CL-084). |
| `E1B-POSITIVE-SUBTHRESHOLD` | PRIMARY clears **positive**, `diff < +3.5` | *Named at freeze so the map has no hole.* Licenses the policy-conditional clause; **does NOT** reopen the per-ply route — a statistically nonzero price below the decision's own effect size is not a route. |
| `E1B-NEGATIVE` | PRIMARY clears **negative** | Under an exploit-aware continuation the divergent invasion plies are worth **less** than ordinary champion-divergences. Strengthens the per-ply null. Report the magnitude; do **not** narrate a mechanism. |
| `E1B-FAMILY-SENSITIVE` | PRIMARY does not clear; SECONDARY-A clears (either sign) | The divergence price **IS** policy-conditional: swapping the family moves it. **CL-083 amendment clause 1 becomes MANDATORY rather than prudent.** No per-ply route reopens. |
| `E1B-NULL-BOUNDED` | neither leg clears **and** the primary's 95 % upper bound < +3.5 | **The per-ply null SURVIVES an exploit-aware continuation.** CL-083 gains one genuinely new evidence axis (its §3 amendment 2 counts independent axes as ≈ two; this makes three), and clause 1's concession may be restated as **measured and bounded** rather than **unpriced**. ⛔ Quote the bound. |
| `E1B-UNRESOLVED` | neither leg clears and the upper bound ≥ +3.5 | **NOTHING beyond the achieved bound**, which is reported. Pre-registered as the modal outcome under a true null (§4.3, ≈ 50 %). Re-opening needs **more plies**, not more worlds. |

### 7.1 Riders that are NOT branches

* **Coverage** (`boosted / (total − own_mover)`) below 0.5 — a flag. Read a low
  coverage as *"the surface is thinner than expected"*, and report it beside the
  bound; it is never a defect and never a branch input.
* **Realized/modelled se** outside [0.70, 1.43] — a flag.
* **`followup_agrees_with_archive`** — descriptive, never a price. Note the
  banked split: it is a consummation rate on the tiles-phase strata (invasion
  0.810, control 0.800, defense 0.893) and **is not a consummation statistic at
  all on `farm_capture`** (0.240 — those plies *are* the meeple).

---

## 8. ⚠️ NON-INFERENCE LIMITS — what this round does NOT measure

1. **It does not price an exploit-PLAYING continuation.** `scope=opp` makes the
   continuation **exploit-aware** — it visits and prices contested futures — but
   DESIGN §0 is explicit that the armed agent's **own move ordering is
   unchanged**. A continuation that itself keeps pressing the exploit (S0v2, a
   `scope=own` agent, a scripted invader) is a DIFFERENT family and stays
   unpriced. **A null here does not close that family**, and the readout must
   say so in those words.
2. **It does not measure S1's strength.** Nothing here is a head-to-head; no elo
   is computed; no `PRODUCTION.yaml` change is licensed by any branch. S1's own
   deployability question was answered by G3 (`S1-BOUNDED-NULL`) and is not
   re-opened by anything in this file.
3. **It does not re-select plies.** The 91 targets are E-1a's, chosen
   outcome-blind there. E-1b inherits both the selection **and its known
   imperfection** (the control decile match filled 3 of 30 slots from the
   nearest decile; achieved mean ply-fraction 0.297 vs invasion's 0.334, skewed
   toward EARLIER controls).
4. **It prices the TARGET PLY ONLY.** Every later move — including the
   same-turn meeple follow-up — is the continuation policy's own choice. E-2
   (`arm_owner_turn`, forcing the archived meeple too) is a separate, optional
   instrument and is **not** run here.
5. **It says nothing about cross-game adaptation.** CL-083b's conjunct has no
   positive instrument on either side; E-4's Tier-0 re-cut is flat and
   underpowered, and E-5 (the Carcasum ARM-ON session) is the only instrument in
   the program that separates steering from mining a stationary leak.
6. **It is not a band-bearing measurement.** No new decks are drawn (§11), so it
   contributes no `results.csv` elo row and retires no band.
7. **The E4 corpus itself is nonstationary.** Every ply carries its archive's
   `budget_note` / `played_sims_effective` / `played_k_dets_effective`, and no
   tally may be read without conditioning on the budget epoch. The 91 targets
   are 90 `fixed_v1` + 1 `walled`; the walled ply is priced and reported but
   never pooled across profiles.
8. **`farm_capture` is 12 plies at mean ply-fraction 0.788**, where the world
   set is *smaller than* `M_WORLDS` (a ply with 3 unseen tiles has only 6
   distinct completions). The paired estimator stays unbiased; its se simply
   does not shrink as `1/√M`. `world_deck_len` is recorded per unit.

---

## 9. FORBIDDEN READINGS

1. **`|z| < 2` is never "refuted."** *Killed / dead / does nothing* are
   forbidden readings of a bounded null. **Quote the bound.**
2. **A void is not a null** (IS-A1). It may never be quoted as one.
3. **No contrast with any other continuation cell is a statistic** except the
   pre-registered family-paired one, which is CRN-paired on identical roots and
   worlds and is only valid because `G-ROOT` passes. A difference of two means
   across differently-rooted runs is not this statistic.
4. **A large invasion price with an equally large control price is NOT a finding
   about invasions**; it is a finding about champion divergence in general, and
   `invasion − control` is the primary precisely so that cannot be misread.
5. **Nothing here licenses a `PRODUCTION.yaml` change**, an S1 re-opening, or a
   `results.csv` elo row.
6. **Do not re-read these 91 plies under a moved bar.** A later argument that
   the bar was mis-set is a **new prereg on fresh plies**, not a re-read of this
   round.
7. **The armed and unarmed censuses are not comparable across strata as a
   mechanism claim.** The census counts expansions, not exploits.
8. **A stratum price larger than the feature's own final points is a bug
   signal**, not a discovery.

---

## 10. REPRODUCE

R9 is import-latched, so every stage runs one process per rules-profile group.
`PYTHONPATH` points at the worktree; the venv is editable-installed against the
main tree, so verify `carcassonne_ai.__file__` resolves inside the worktree.

```bash
WT=<this worktree>
D=$WT/measurement/e1b_armed_continuation_20260901
export PYTHONPATH=$WT/src:$WT/engine:$WT/scripts

# 1. the frozen comparator (already committed; this regenerates it)
python3 $D/freeze_baseline.py \
    --units <e1a>/out_local <e1a>/out_laptop \
    --targets $D/targets_continuation.jsonl \
    --verdict /mnt/c/carc-shared/e4_continuation_20260828/CONTINUATION.json \
    --out $D/CRN_BASELINE.json

# 2. tests, then the FREEZE commit, then the smoke, then the cell
.venv/bin/python -m pytest $D/test_e1b.py -q
python3 $D/adjudicate_e1b.py --selftest
python3 $D/plan_units.py --targets $D/targets_continuation.jsonl \
                         --out-dir $D --box local
REPO=$WT $D/launch_local.sh                      # ladder + smoke + detached cell

# 3. the readout
python3 $D/adjudicate_e1b.py --units $D/out_local \
    --manifest $D/out_local/manifest.json \
    --targets $D/targets_continuation.jsonl --out $D/E1B.json
```

---

## 11. THE BAND

**TBD AT LAUNCH — the orchestrator claims it, not this file.** See
[`BAND_CLAIMED.placeholder`](BAND_CLAIMED.placeholder).

⭐ E-1b draws **no new decks**: every world is a permutation of the *unseen tail*
of an already-archived E4 game, seeded on `(WORLD_SEED, deck_seed, ply, world)`
with the archive's own `deck_seed`. It therefore consumes **no deck band** and
retires none, and it produces no `results.csv` elo row. The launcher still gates
on an explicit `BAND_CLAIMED` file so that "no band is being spent" is an
**acknowledged decision** by the orchestrator rather than an omission — the same
fail-closed posture S1's `run_g3.sh` takes, for the opposite reason.
