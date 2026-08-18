# TIE-ARBITER WIDENING — SHARED RUN, DESIGN **rev R4** (successor pair)

> **STATUS: BLIND PREREGISTRATION, DRAFT. NOT LAUNCHED. NO POSITION SCORED. NO OUTCOME
> STATISTIC OF THIS RUN OR ITS PREDECESSOR EXISTS OR WAS READ.**
>
> **Why there is a successor.** The R3.3 pair (blind commit **`604edc83`**, `../shared_run/`)
> is **SPENT-BY-GATE-FAILURE**: `G-DISJOINT` and `G-COMPLETE` fired **pre-scoring**, exactly as
> written. Disposition, and the blindness argument that makes band 135e9's games reusable as
> **input**: [`../PREREG_FAILURE.md`](../PREREG_FAILURE.md). That file is a precondition for
> reading this one.
>
> ⚠️ **`../shared_run/` IS FROZEN HISTORY.** Nothing in it moves. This document **incorporates
> it by reference at commit `604edc83`** and restates **only what changes**. A section marked
> **CARRIED** is binding in its R3.3 wording; do not re-derive it, do not paraphrase it.
>
> **Blind-order requirement:** this pair + `READ_RULE.md` commit to main in **ONE** commit,
> after the §8 W-code delta merges and its acceptance pass, before the extension band is claimed
> and before one position is scored.
>
> `governance/PRODUCTION.yaml` untouched on every branch. No claim minted. No strength row.

---

## What is CARRIED UNCHANGED from `shared_run/DESIGN.md` @ `604edc83`

Binding in their R3.3 wording, **not restated here**:

| § | content |
|---|---|
| §1 | what the run is; the two rungs; out-of-scope list (incl. the phone, owner ruling) |
| §2 | **cells and statistics** — every estimand, the declared shared cell, `ora` adjudicates rung 3 |
| §4 | instrument invocation, the W6 driver pointer, the three salts, the graded-knob table |
| §5 | the W4/`G-CAP` resolution and **`I7-draw-scope` verbatim** (incl. both R2 amendments) |
| §6 | **power arithmetic**: the `se` bracket `[0.0179, 0.0200]`, the +0.040 floor, `sd_Δ ∈ [0.9, 1.4]`, the root bootstrap (2,000 reps, seed 20260819), significance defined once on the percentile CI |
| §9 | freeze-and-sequence, 4a / 4b-pre / 4b, the two-source merge discipline |
| §10 | required manifests |
| §11 | the draft `I6` amendment text |
| §0.A–§0.O | every pre-blind amendment: `c_remeasure` spelling, the `allow_null` mechanism, `STAGE1B_LADDER.json`, W9/`D-DRAW`, the `WORKERS.conf` consumer mapping, `--backend rust`, the always-explicit `--positions-dir` rule |

**Also carried, by reference, not rebuilt:** `STAGE1B_LADDER.json` (the `G-REPLICATE` reference)
· the merged W-code (W2/W3/W5/W6/W7/W8/W10) · the fixtures · the 4a/4b acceptance harness.
R4's W-delta is §8 and is small.

---

## R4-1. What changes, in one table

| # | change | why |
|---|---|---|
| **A** | **§3 yield math re-derived from REALIZED rates**, full supply chain shown, **floors left as an owner parameter** | R3's §3 read raw census rows as final supply and set an S2 target its own capped-fraction constant refuted (`PREREG_FAILURE` §2) |
| **B** | **`G-DISJOINT` digest layer gains a pre-committed EXCLUSION rule with a hard bound** | a genuine cross-band board transposition is not a corpus leak, and "void the run" is the wrong price for one — but only while it is a trickle |
| **C** | **the two-box scoring layer (D1) is FIRST-CLASS**, not a deviation; **D2 is CLOSED AS UNNECESSARY** | the IF leg has dispatched to rust on `walled` since 2026-08-02; there was never a swap to make |
| **D** | **band arithmetic: base + extension (+ optional top-up), `G-BAND` generalised to N files** | 135e9 is retained as input; extension needs a fresh range; R3's two-file form does not stretch to three |
| **E** | **cost basis re-based on MEASUREMENT** (generation `c`; both IF `c` figures carried) | carrying a 3.3× stale commitment forward would re-manufacture the cost-model-miss disclosure |

Everything else — every estimand, bar, branch condition, rider and gate conjunct not named
above — is **identical to R3.3**.

---

## R4-2. (A) Supply chain and sizing — from realized rates

**The R3 error, in one line:** raw census rows are not positions. Two reductions apply, and the
second is mandated by the design's own §6 dedupe.

### R4-2.1 The measured chain (band 135e9, pre-scoring counts only)

```
S1  (--max-per-game 4, 350 games)
    raw census rows                    1,400
    x qualification        ~0.54         756
    x afterstate dedupe    ~0.735        556        <- the dedupe §6 itself mandates
    REALIZED                             551        =>  r_S1 = 1.574 / game

S2  (--max-per-game 3, 500 games)
    qualifying-deduped tied plies        613        =>  1.226 / game
    x capped fraction       0.168        103        =>  r_S2cap = 0.206 / game
                                                       (0.168 agrees with §3's 0.1807 constant;
                                                        it was the TARGET that contradicted it)
```

**These two rates — `r_S1 = 1.574` and `r_S2cap = 0.206` qualifying-deduped per game — are the
sizing constants of record for R4.** They are measured, on this exact configuration, at
`--max-per-game` 4 and 3 respectively. Changing either mining ceiling invalidates the
corresponding rate and requires a re-measure, not a re-scale.

### R4-2.2 Games needed — **the floor is an owner parameter**

Banked and reusable: **S1 551**, **S2 103**. Additional games
`= ⌈(n₁−551)/1.574⌉ + ⌈(n₂−103)/0.206⌉`. Cost basis §R4-5.

| option | n₁ | n₂ | **+games** | gen wh | scoring wh | **TOTAL wh** | at smoke `c_IF` | wall h |
|---|---|---|---|---|---|---|---|---|
| FULL targets | 1,350 | 1,100 | **5,348** | 552.6 | 929.0 | **1,493** | 1,082 | ≈32 |
| committed FLOORS | 1,283 | 1,045 | **5,039** | 520.7 | 882.8 | **1,414** | 1,024 | ≈30 |
| **S2 at 700** (PLAN_J's own floor) | 1,350 | 700 | **3,407** | 352.1 | 819.0 | **1,181** | 819 | ≈26 |
| S2 at 500 | 1,350 | 500 | **2,436** | 251.7 | 764.0 | **1,025** | 687 | ≈23 |
| S2 at 400 | 1,350 | 400 | **1,950** | 201.5 | 736.5 | **947** | 621 | ≈21 |
| **S1 ONLY** (rung 3 dropped) | 1,350 | — | **508** | 52.5 | 626.5 | **684** | 407 | ≈16 |

⭐ **The decision-relevant fact: rung 2 is nearly free and rung 3 is the entire cost.** The
B-ladder needs **508** more games; every game beyond that buys capped plies for the J rider,
which arrive at **0.206/game — 7.6× slower than S1's supply.** An owner choosing between these
rows is choosing how much to pay for rung 3, not for the run.

### R4-2.3 What each floor buys, in power — the honest ladder

`se(Δ_ora) = sd_Δ/√N`, `sd_Δ ∈ [0.9, 1.4]` (§6 CARRIED). A prediction resolves at 2σ iff
`sd_Δ ≤ d·√N/2`:

| N (capped) | resolves corrected **+0.0842** iff | resolves legacy **+0.1382** iff |
|---|---|---|
| 1,100 | `sd_Δ ≤ 1.396` — the bracket bar `1.4` (R3's known blind spot) | `≤ 2.292` ✅ whole bracket |
| 1,045 | `≤ 1.361` | `≤ 2.234` ✅ |
| 700 | `≤ 1.114` — **only the optimistic half of the bracket** | `≤ 1.828` ✅ |
| 500 | `≤ 0.941` — essentially the bracket floor only | `≤ 1.545` ✅ |
| 400 | `≤ 0.842` — **below the bracket: cannot resolve it at any `sd_Δ`** | `≤ 1.382` — **fails at the bracket top** |

**No option separates 1.400 from 1.244** (CARRIED §6). Below `N ≈ 700` the rung stops being a
test of the *corrected* multiplier and becomes a test of the *legacy* one only; at `N = 400` it
tests neither reliably. **A floor below 700 should be chosen only as a decision to answer a
narrower question, and the read-out must say which question was bought.**

---

## R4-3. (B) The `G-DISJOINT` digest layer — exclusion rule, pre-committed

**What happened is not a corpus leak.** One `c_position_digest` collision, **zero** root overlap,
**zero** rid overlap: two independently generated games from different bands reached the **same
board** — a transposition. **The three-layer gate did its job by catching it**, and the layered
design is vindicated: rid/root disjointness is guaranteed by construction, digest disjointness is
an empirical property that must be *measured*, and it was.

**The rule, fixed here, before any R4 number exists:**

1. **Exclusion, not void, for a trickle.** Any `c_position_digest` collision between an R4
   position and a position of **either spent corpus** excludes the **R4 (newer) rid**. The
   banked position is never touched.
2. **Intra-run collisions too.** An S1↔S2 digest collision excludes the **S2** rid (S1 is the
   B-ladder's primary; S2 is the rider). Two strata sharing a board would contaminate the
   independent-replication rider that compares them.
3. **The exclusion is OUTCOME-INDEPENDENT by construction and that is why it is legitimate.** The
   digest is a function of the board alone, computed at corpus-build time, before any value
   exists. It is the opposite of the 2026-08-14 open-city void, whose exclusion was rejected
   precisely because it was *not* outcome-independent.
4. **It happens before the positions are frozen.** Excluded rids never enter `POSITIONS_PLAN`,
   never reach a scoring leg, and **the completion floors are evaluated on the post-exclusion
   count** — so an exclusion can never be used to explain away a shortfall after the fact.
5. **The hard bound.** Exclusions must satisfy **≤ 0.5% of the stratum's qualifying-deduped
   positions AND ≤ 15 absolute**. Above **either**, the stratum is **VOID** — not excluded,
   not disclosed-and-continued.
6. **Why 0.5%.** The realized rate is **1 / 551 = 0.18%**, so the bar carries ≈2.8× headroom: it
   passes the observed world comfortably and still fails a world in which transposition
   degeneracy is a *property of the generator* rather than an accident. That second world is a
   different finding — it would mean champion self-play revisits boards at a rate that makes
   "fresh corpus" the wrong description — and it must surface as a VOID, not be absorbed silently.
7. **Always reported**, on every branch: the count, the rate, the excluded rids, and the bound
   they were measured against — whether or not any exclusion occurred.

---

## R4-4. (C) Two-box scoring is first-class; the rust-IF question is closed

**The two-box scoring layer (chunk / allocation / merge) is an instrument choice of R4, not a
deviation.** Its gate-neutrality analysis — the six clauses C1–C6, of which C1/C2/C6 are signed
from the seed derivation, the per-rid record shape and the join keys, and C3/C4/C5 are discharged
by the delivered layer — is at [`../DEVIATIONS.md`](../DEVIATIONS.md) §D1 and is **incorporated
here by reference**. **If any clause of D1 stands unsigned at launch, R4 scores single-box** —
wall-clock is the cheaper failure; an allocation-dependent value is not.

**D2 (rust IF judge) is CLOSED AS UNNECESSARY.** The `clair-puct` IF leg has dispatched to rust on
`walled` since 2026-08-02 (`run_tiletie.py:117` `JUDGE_BACKEND`, `:154` `RUST_OK_PROFILES`; gate
`measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` PASS, 20 positions / 940 field checks /
0 mismatches). There was never a swap to make: the estimand was never at risk, and the 9.4× is
that already-taken swap's own captured speedup. Recorded in `../DEVIATIONS.md` §D2.

⚠️ **Standing constraint, promoted to a threat-model line (it was previously implicit).** The rust
clairvoyant path **requires `walled`**: `RustCarryClairvoyantAgent` mirrors no rules config, and
`fixed_v1` / `app_aug2` **fail loud** rather than grade under the wrong rules. R4's corpus is
`walled`-only, so this is safe **today** — and it is stated here so that **no future stratum,
top-up or extension silently mixes rules profiles.** A profile change is not a knob change; it
changes which engine may price the leg.

---

## R4-5. (E) Cost basis — re-based on measurement

**Generation.** R3 committed **990** worker-s/game, inherited. The fresh same-config GEN smoke
measured **297.6**. R4 commits **372.0 = 297.6 × 1.25** — the measurement plus a margin, in the
direction that cannot under-commit. The one-sided HALT (CARRIED §7) therefore trips above
**465.0** worker-s/game, i.e. ≈1.56× the measured rate: a real trigger, not a formality. *Carrying
990 forward would have re-manufactured exactly the cost-model-miss disclosure this campaign has
already written twice.*

**IF (`clair-puct`) — both figures carried, deliberately.**

| figure | value | provenance |
|---|---|---|
| **committed** | **2.35** worker-s/playout | banked `elapsed_secs`; **plausibly the W30-CONTENDED rust price** |
| smoke-indicated | **1.2313** | `SMOKE_RUST_MANIFEST.json`, idle box, `M=32`, sims=100 |

The **1.91× gap is not resolved here and is not guessed at**: the pre-run `c`-remeasure (CARRIED
§7, at production knobs, on an idle box) settles it. **§R4-2.2's ETA is sized off the committed
2.35** — conservative, so the envelope cannot be undershot — and the **`at smoke c_IF` column
states the realized-likely total** so the owner's envelope math is honest in both directions.
`c_ARB` is unchanged at 0.178232.

**One consequence worth stating:** at the smoke-indicated price the FULL-targets option (1,082 wh)
lands **inside** the already-funded 1,174 wh envelope, while at the committed price it is
**+27%**. The floor decision and the `c`-remeasure outcome are therefore coupled, and the honest
order is: **remeasure first, then choose** — or choose at the committed price and bank the
surprise as headroom.

---

## R4-6. (D) Band arithmetic

| band | range | status |
|---|---|---|
| `135000000000` | +0…+849 (850 games) | **RETAINED as valid input** (`PREREG_FAILURE` §3), minus rids excluded by R4-3 |
| `136000000000` | — | **RELEASED UNUSED.** R3's top-up reservation; released rather than repurposed so "which prereg consumed which band" stays unambiguous |
| **`137000000000`** | +0…+(N−1), `N` = the owner-chosen row of R4-2.2 | **EXTENSION generation** — claimed at run time, `decision_influenced=no`, notes marking it **OFFLINE CORPUS SUBSTRATE** |
| `138000000000` | +0…+499 | **RESERVED** for the blind top-up clause, not licensed |

**`G-BAND` generalises from two files to N.** Each generated range emits its **own**
`verify-champgames` file and is checked **against its own range** — `band_ok`, `seed_band`,
`n_out_of_band == 0`, `n_duplicate_seeds == 0` — and **the per-file game floors are a committed
table, not one blanket number** (R3's B1 lesson generalised: the base carried the floor and the
top-up carried the increment; with three possible files that rule must be tabular). Never one
invocation over a widened band. Exact conjunct: `READ_RULE.md` §2.

---

## R4-7. Threat model — what could still make this unreadable

1. **The rates are measured on ONE band.** `r_S1`/`r_S2cap` come from 850 games of band 135e9.
   If the extension band's supply differs materially, the floors move. **Mitigation, and it is a
   real one:** supply is knowable **before scoring** — the corpus build counts it — so a shortfall
   surfaces at the corpus stage, where the only cost is generation, not pricing.
2. **The `c_IF` gap (1.91×) is unresolved until the remeasure.** Sized conservatively; the HALT is
   one-sided and fires before the expensive legs.
3. **Transposition degeneracy may be a generator property**, not an accident — R4-3's bound is
   the detector, and its answer is VOID, not absorption.
4. **`walled`-only is load-bearing** for the rust IF path (R4-4).
5. **D1's unsigned clauses** ⇒ single-box, by rule, not by argument.

## R4-8. W-code delta (small; everything else carries)

| item | change |
|---|---|
| **W5** | `GATE_DISJOINT.json` gains the R4-3 **exclusion** semantics: per-comparison collision lists, the excluded-rid set, the rate, the bound, and `void` vs `excluded` as distinct outcomes |
| **W6** | (i) **run ALL gates and aggregate — never `set -e`-abort on the first failure** (that is why `GATE_DRAW.json` never emitted); (ii) apply R4-3's exclusions **before** freezing `POSITIONS_PLAN`; (iii) size from the R4-2 rates |
| **W10** | extension-band generation: base + extension (+ optional top-up) as **separate invocations into separate directories**, each with its own `verify-champgames` file (the §0.L pattern, now three-way) |
| **W3** | `G-BAND`'s N-file form and the exclusion counters surfaced in the verdict block |
| carried unchanged | W2 · W7 · W8 + fixtures · W9 (`D-DRAW`) · `STAGE1B_LADDER.json` · the 4a/4b harness |

## R4-9. Owner decisions

1. ⭐ **The floor** — pick a row of R4-2.2. R4-2.3 says what each buys. **Recommendation: `S2 at
   700`** — PLAN_J's own floor, 3,407 games, ≈1,181 wh committed / ≈819 wh at the smoke price,
   and it keeps the corrected multiplier resolvable across the optimistic half of the `sd_Δ`
   bracket. `S1 ONLY` is the honest fallback if rung 3's price is not worth its question.
2. **Remeasure `c_IF` before choosing, or choose at the committed price?** The 1.91× gap moves the
   FULL option in and out of the funded envelope.
3. **Ratify the R4-3 exclusion rule and its 0.5% / 15 bound.**
4. Carried from R3.3 and still open: the `I6` amendment pre-approval; the offline-corpus band
   registry question; the `B=64` game-cell trigger.
