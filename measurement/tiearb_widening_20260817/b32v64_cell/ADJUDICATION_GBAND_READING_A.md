# ADJUDICATION — `G-BAND` conjunct 4 vs `G-FAILED`, and the owner's Reading-A ruling

> **Ruling from the frozen pair's words** ([`DESIGN.md`](DESIGN.md) + [`READ_RULE.md`](READ_RULE.md),
> blind commit `71b3286c`), not from the outcome anyone would prefer. The cells are complete and
> spent; boxes are idle; **`governance/PRODUCTION.yaml` untouched by this document.**
>
> **⛔ THIS DOCUMENT AND [`verdicts/READOUT_B32V64.json`](verdicts/READOUT_B32V64.json) TOGETHER
> ARE THE VERDICT OF RECORD, AND THE VERDICT IS `L-AMBIGUOUS`.** The human read-out is
> [`verdicts/READOUT_B32V64.md`](verdicts/READOUT_B32V64.md); it carries this ruling as a banner
> and may not be read without it.
>
> ⚠️ **The blindness disclosure in §5 is NOT optional context.** The owner's ruling was **not
> blind to the outcome**, because the adjudicator printed `z_D` and `UB95(D)` beside the failed
> gate. Read §5 before reading §6.

---

## 0. The mechanical record — what the tool actually returned, and it stands

The adjudicator (`scripts/tiletie/analyze_b32v64_cell.py`) ran **2026-08-22** (emit stamp
`generated_utc 2026-08-23T03:06:30Z`) with the owner's `G-FAILED` clause-3 escalation
confirmation recorded verbatim, and returned:

| field | value |
|---|---|
| `n_gates` | **13** |
| `gates_all_pass` | **false** |
| `gates_failed` | **`["G-BAND"]`** — 12/13 PASS |
| `branch` | **`U-UNREADABLE`** |
| `branch_detail.reason` | *"a §3 precondition failed"* |
| `branch_detail.adjudicated` | **false** |

**That mechanical result is not being overturned, edited, or re-run.** `U-UNREADABLE` is what
the frozen rule, executed literally by the tool, produced from these artifacts, and
`READOUT_B32V64.json` carries it unaltered. This document does not amend the pair and does not
re-run the adjudicator. What it records is a **governance act on a drafting defect** — the owner
resolving which of two textually-available readings of `G-BAND` conjunct 4 governs — after which
the pair's own branch table, unamended, applies to the resolved statistics.

**What failed, exactly.** `G-BAND` is four conjuncts, all required. Three passed; the fourth did
not:

| conjunct | realized | result |
|---|---|---|
| 1. a claim sentinel predating game 1 | `BAND_CLAIM.json`, `claimed_before_game_1: true`, dated 2026-08-20 | ✅ |
| 2. the sentinel names the pinned band | `sentinel_band 140000000000` == `expected_band` | ✅ |
| 3. both cells on that same band | `config.band_seed_start` = `140000000000` in **both** cells | ✅ |
| 4. **identical realized deck sets** | `same_decks: false` — `n_decks` **1,497** (`CELL_B32`) vs **1,500** (`CELL_B64`) | ⛔ **FAILED** |

And the entire content of that failure:

```
decks_only_in[CELL_B64] = [140000001096, 140000001115, 140000001286]
decks_only_in[CELL_B32] = []
```

**Exactly the three owner-confirmed panic-failed decks, and nothing else.** `CELL_B32` holds
**no** deck that `CELL_B64` lacks. The set difference is one-directional, fully enumerated, and
identical — deck for deck — to the failure set the owner confirmed under `G-FAILED` clause 3
hours earlier ([`ESCALATION_20260822.md`](ESCALATION_20260822.md);
[`verdicts/HALT_B32V64.json`](verdicts/HALT_B32V64.json)).

---

## 1. RULING — does `G-BAND` conjunct 4 fire on a run whose only deck-set difference is `G-FAILED`'s own tolerated failures?

# **The text does not decide it. Two readings are available, they contradict each other, and the pair contains no sentence that chooses.**

**Resolved by owner ruling 2026-08-22 (§6): Reading A governs.**

### 1.1 The two gates, quoted verbatim from [`READ_RULE.md`](READ_RULE.md) §3.1

**`G-BAND`** — scope `[RUN]`, marker `[pre-run]`+`[post-cells]`, the condition that FIRES it:

> *"the band was not claimed from `governance/BAND_REGISTRY.csv` **before game 1** (no
> `BAND_CLAIM.json` sentinel predating the first record); **or** the sentinel does not read
> `140000000000`; **or** the two cells did not run on the **same band and the same decks**
> (`config.band_seed_start` equal **and** equal to 140000000000, realized deck sets identical)"*

…with the healthy run declared as: *"sentinel dated 2026-08-20, both cells `band_seed_start`
140000000000, identical deck sets"*.

**`G-FAILED`** — scope `[RUN]`+`[PER-CELL]`, marker `[post-cells]`, clause 1 and clause 3:

> *"**(1)** `F_x / n_attempted_x > 0.02` in either cell"*

> *"**(3)** If `F_w + F_n > 0`, the read-out must print, for every failed game, the harness's raw
> failure record verbatim (message and traceback tail as emitted), and the run **HALTS for owner
> escalation before adjudication** unless every failure is manually confirmed to be the known
> `WindowTruncationError` class. **The confirmation is a human act recorded in the read-out, and
> it is the one place this rule admits one** — it gates escalation, never a branch."*

…with `G-FAILED`'s own healthy-run column reading: *"`F_32 = F_64 = 0` (b64_cell realized 0/1500
in both cells) ⇒ clauses 1 and 2 pass, clause 3 is vacuous"*.

And [`DESIGN.md`](DESIGN.md) §8.1 clause 1, which sets the level and says why:

> *"A 2% bar is ≈60 games in a 3,000-game cell against a realized prior of **zero** ⇒ it fires
> only on a regime change. Deliberately generous: its job is to catch a broken run, not to grade
> a good one."*

### 1.2 The contradiction, named exactly

**`G-FAILED` clause 1 licenses up to 2% of a cell's games to fail. `G-BAND` conjunct 4, read
literally, voids the run on *any* failure. The pair therefore contradicts itself the moment
`n_failed > 0` in one cell — which is precisely the regime clause 1 was written to tolerate.**

The mechanism is not subtle, and it is structural rather than incidental:

- `D` is defined ([`READ_RULE.md`](READ_RULE.md) §2) as *"`M_64 − M_32`, **deck-paired over the
  decks completed in BOTH cells**"*, and each cell's `M` is a **seat-balanced** per-deck margin.
  A deck that loses one of its two seatings is therefore dropped **whole** from that cell's
  realized set — the campaign's own D4.18 whole-rid discipline, applied to decks.
- ⇒ **any tolerated failure necessarily makes the realized deck sets differ.** The two clauses
  cannot both be satisfied at `n_failed > 0`. There is no `n_failed` between 1 and the 2% bar at
  which `G-FAILED` passes and `G-BAND` conjunct 4 also passes.
- ⇒ `G-FAILED`'s 2% tolerance, its clause-2 candidate-correlation test (`max(F) ≥ 5 AND
  max(F) > 3 × max(min(F), 1)`), its clause-3 escalation machinery, and the owner confirmation
  that clause 3 exists to obtain are all **dead letters** on the literal reading: the run is void
  at `G-BAND` regardless of how any of them resolve.

**This is the unsatisfiable-gate class — the campaign's signature disease — in its fourth
instance.** [`DESIGN.md`](DESIGN.md) §1.5's structural test is *"Would this gate fail on a
healthy run? If yes, it is an instrument defect, fixed **before** the run, never adjudicated
around."* A run with 3 tolerated failures in 6,000 games at 20× under its own bar **is** a
healthy run by the pair's own arithmetic, and the literal conjunct 4 fails it. The prior three
catches — `G-CAP` (fail-always), `G-TOOL`'s `+rustcunpinned` (this pair's own §3 row calls it
*"this campaign's THIRD unsatisfiable-gate catch"*), and Stage 2's unreachable `G-N` — were all
found **before** their runs. This one was not.

### 1.3 Why both reviews missed it, stated rather than excused

**`REVIEW_R1` (FAIL, 7 findings) and `REVIEW_R2` (PASS, 0) both read this pair, and neither
raised it.** The reason is a fact about the fixture, not about the reviewers' diligence: the
`b64_cell` sibling — the run every check was calibrated against, and the source of the
known-good evaluation — realized **`n_failed = 0` in both cells**. At zero failures the two
clauses are consistent, `G-BAND` conjunct 4 passes, `G-FAILED` clause 3 is *vacuous* (the pair's
own §3 row says so, in those words), and **the contradiction is invisible**. A known-good
evaluation over a zero-failure fixture cannot surface a conjunct that only contradicts at
`n_failed ≥ 1`.

⛔ **That is a lesson about the known-good method, and it is recorded as one**
([`../DEVIATIONS.md`](../DEVIATIONS.md) **D7.1**): *a known-good fixture proves a rule passes a
healthy run of the fixture's shape, not of every healthy shape the rule admits.* The fixture had
no failures; the bound admitted 60.

### 1.4 The two readings, both textually available

**Reading A — `DISCHARGED-BY-THE-CONFIRMED-SET`.** Conjunct 4's job, read against the gate's own
declared purpose, is **one deck set by construction, no contamination**: the semantics field the
adjudicator itself emits reads *"four conjuncts, ALL required: a pre-dated claim sentinel, the
sentinel naming the PINNED band, both cells on that same band, and identical realized deck
sets"* — three provenance conjuncts and a fourth that exists to catch **divergent draws**. Where
the *entire* difference is the failure set `G-FAILED` already adjudicated and the owner already
confirmed, conjunct 4 has nothing left to catch: the sets were identical **by construction**
(one band, one seed range, `same_band: true`), and the difference is a *downstream* consequence
of the failure policy the pair separately wrote and separately tolerated. On this reading the
conjunct is **DISCHARGED by the confirmed failure set**, and the branch table applies unamended.

**Reading B — `LITERAL-AND-VOID`.** The conjunct's text is unqualified — *"realized deck sets
identical"* — and `n_decks` 1,497 ≠ 1,500. The gate table's own header says the marker `[RUN]`
means *"the run fails; no cell is readable"*, and §4.1 row 1 says a failing gate **SUPPRESSES**
the verdict. `G-FAILED` carries no carve-out sentence pointing at `G-BAND`, and `G-BAND` carries
no exception clause for tolerated failures. A conjunct with no exception written into it has no
exception.

**Why neither is forced — the sentence that was never written.** *What a `G-FAILED`-tolerated
failure does to `G-BAND` conjunct 4's deck-set identity.* Reading A supplies *"discharges it"*;
Reading B supplies *"nothing — the conjunct still fires"*. **Neither sentence is in the
document.** The pair pins the failure policy (§8.1, three clauses, authored before its data) and
pins the deck-set identity requirement (§3 `G-BAND`) and **never relates them**, because at the
sibling cell's zero failures they never met.

### 1.5 What does NOT resolve it

- **`G-N`'s completion floors do not.** `n_common` 1,497 ≥ 1,200 and both cells cleared 2,400
  games — `G-N` **PASSES** and is explicitly the *completion* gate. But `G-N` is a floor on
  *how many* decks survive; conjunct 4 is a predicate on *which* decks. Passing a floor is not
  an exception to an identity requirement, and importing one to settle the other would be
  reading a gate the pair scoped elsewhere.
- **The adjudicator's behaviour does not.** The tool implemented the literal text and returned
  `U-UNREADABLE`. That is the harness doing its job, not a clause of the rule; a tool cannot
  license or forbid a reading (R4 `ADJUDICATION_R4_GATES.md` §1.3, same principle).
- **The branch table's first-match-wins rule does not.** It is written for **branches**, not
  gates, and §3 pre-empts §4 entirely.
- **`failure_surface_REPORT_ONLY` does not.** It is `"REPORT ONLY — wired into NO conjunct"`
  by the pair's own words ([`DESIGN.md`](DESIGN.md) §13.2 item 2). It cannot discharge a
  conjunct it is deliberately not wired into.

---

## 2. The intent witness — what conjunct 4 exists to prevent, and whether it happened

**It did not happen, and the evidence is fully enumerated in the artifact rather than argued
from silence.** Conjunct 4 guards against the two cells drawing **different decks** — different
bands, drifting seed ranges, a re-seeded or re-launched cell, a partially-stolen claim, a
clock-drift box silently taking work outside the range. Every one of those failure modes is
witnessed **absent**:

| what conjunct 4 protects against | realized witness |
|---|---|
| different bands | `same_band: true`; both cells `config.band_seed_start = 140000000000` |
| a band other than the claimed one | `sentinel_matches_expected: true`, `band_is_expected: true` |
| an unclaimed / post-hoc band | `claimed_before_game_1: true`, sentinel dated 2026-08-20 |
| range drift | `deck_range 140000000000..140000001499`, `deck_seed_min/max` 140000000000 / 140000001499 |
| `CELL_B32` holding decks `CELL_B64` never played | **`decks_only_in[CELL_B32] = []`** — empty |
| `CELL_B64` holding unexplained extra decks | `[140000001096, 140000001115, 140000001286]` — **the confirmed failure set, exactly, three for three** |
| the difference being outcome-correlated in an unknown way | the drop predicate reads record **validity**, never a value (D4.18's own acceptability property); one seating each failed and **the sibling seating of each deck succeeded** |

⭐ **And the direction is disclosed rather than argued away.** The three decks are absent from
`CELL_B32`, the **cheaper** cell — so the surviving common set is, in principle, correlated with
board geometry (the panic fires at extreme board extents, at the 35×35 grid edge). At
**3/2,997 = 0.100%** against the 2% bar (20× of margin) and with clause 2's
candidate-correlation test **not firing** (`max(F) = 3 < 5`), the disclosed correlation cannot
move `D`. **A 3-vs-0 split at these counts is p ≈ 0.09 under equal rates — suggestive, not
conviction** — and that too is disclosed, not resolved.

⚠️ **What the intent witness is NOT.** It is not a finding that conjunct 4 *passed*. It did not
pass; `same_decks` is `false` and `READOUT_B32V64.json` says so on its face. It is the evidence
on which a governance ruling about the conjunct's **discharge** could be made.

---

## 3. The failure class — recorded, not repaired here

All three failures are identical in surface: `exc_type: PanicException`,
`exc: "IndexError: board row index 35 out of range (len 35)"`, `window_truncation: false`,
`attempts: 1`, `permanent: false`. Seeds `140000001096` (a_seat 1), `140000001115` (a_seat 0),
`140000001286` (a_seat 0) — one seating each, sibling seating succeeded in every case, all three
in `CELL_B32`, zero in `CELL_B64`.

This is the **parked rust engine board-bounds panic family** (`carc-core/src/engine/mod.rs:411`,
proven PRE-EXISTING 2026-08-17, triage unfunded — roadmap parking lot), now observed at ~0.1% in
live production-knob games rather than only in fixture replay. **It is not an arbiter defect and
not an instrument defect**: `tiearb_errors_total: 0` and `tiearb_partial_argmax_total: 0` in
**both** cells. ⭐ **The three reproducible seeds at production knobs are a triage lead the
parked bug did not have before** and travel to that row.

⛔ **Nothing here is fixed by this document.** No code changed; the panic stays parked.

---

## 4. What the resolved statistics are, and which branch they select

**Under Reading A the conjunct is discharged, all 13 §3 preconditions are satisfied, and
[`READ_RULE.md`](READ_RULE.md) §4.1 applies unamended, first-match-wins, to statistics the
adjudicator already computed and `G-STAT` already validated** (`nan_inf_or_absent: []`,
`se_D_positive: true`):

```
D      =  +0.6459585838343354   pts/game   (M_B64 − M_B32, deck-paired, n_common 1,497 decks)
se_D   =   0.4670671296585714
z_D    =  +1.3830101559630938
UB95(D)=  +1.4142840121226854   ONE-SIDED 95% UPPER BOUND ON THE COST
MARGIN =   0.93                 pts/game   (TOLERANCE_PTS, WORKERS.conf)
```

| # | branch | condition | fires? |
|---|---|---|---|
| 1 | `U-UNREADABLE` | any §3 gate fails | **no** — under Reading A conjunct 4 is discharged; 13/13 |
| 2 | `L-REVERSED` | `z_D ≤ −2.0` | **no** — `z_D` = +1.3830 |
| 3 | `L-RISING` | `z_D ≥ +2.0` | **no** — `z_D` = +1.3830; the edge is `D ≥ 2·se_D = +0.9341` |
| 4 | `L-SATURATED` | `UB95(D) ≤ +0.93` | **no** — `UB95(D)` = **+1.4143 > 0.93**; the edge is `D̂ ≤ 0.93 − 1.645·se_D = +0.1617` |
| 5 | **`L-AMBIGUOUS`** | everything else (`−2.0 < z_D < +2.0` **and** `¬EQUIV`) | ⭐ **FIRES** |

⇒ **`L-AMBIGUOUS`.** Exactly one branch matches, by the pair's own §4.4 totality-and-disjointness
argument.

⛔ **This is the branch that licenses nothing and favors no one.** Its own row states the read:
*"UNRESOLVED — NEITHER A CONVICTED COST NOR A CONVICTED NON-INFERIORITY. The deploy STAYS at
`B` = 64 (the incumbent), and `B` = 128 is UNFUNDED BY DEFAULT. Nothing closes and nothing is
licensed."* The deployed shape does not move; no swap-down decision is put to the owner; the
`B` = 128 question is neither licensed nor killed; `PRODUCTION.yaml` is untouched; no claim is
minted. **That property is load-bearing for §5.**

---

## 5. ⛔ BLINDNESS DISCLOSURE — the ruling was NOT blind, and here is exactly why

# **THE ADJUDICATOR PRINTED `z_D` AND `UB95(D)` IN ITS CONSOLE LINE BESIDE THE FAILED GATE. THE OWNER'S RULING WAS THEREFORE NOT BLIND TO THE OUTCOME IT COULD AFFECT.**

**This is a TOOL DEFECT, and it is against the house blindness protection, quoted verbatim**
([`../shared_run/READ_RULE.md`](../shared_run/READ_RULE.md) §7, the campaign's standing rule):

> *"**On `W-UNREADABLE` (any gate FAIL): the harness report prints GATE INPUTS ONLY — no `arb`,
> no `ora`, no `Δ`, no CI, no per-position statistic.** This is a hard requirement: on
> 2026-08-17 a mandatory companion table printed alongside a gate failure made the orchestrating
> session non-blind and forced the fixes to be written by a separate blind session."*

…and against this pair's own restatement of it, [`READ_RULE.md`](READ_RULE.md) §4.1 row 1:

> *"⛔ The read-out may **not** print `D`, `z_D` or a branch label as if adjudicated."*

**What happened.** The adjudicator emitted its gate summary with the `D`-block statistics on the
same console line as `gates_failed: ["G-BAND"]`. So at the moment the contradiction was
discovered and the ruling was drafted, the session — and therefore the option card put to the
owner — **already knew** that `z_D` = +1.3830 and `UB95(D)` = +1.4143, i.e. that Reading A
selects `L-AMBIGUOUS` and not `L-SATURATED` or `L-RISING`.

⚠️ **CORRECTED ON THE RECORD AT WRITE-UP TIME — THE LEAK SURFACE IS WIDER THAN THE CONSOLE
LINE, AND THE WIDER FACT IS STATED RATHER THAN THE NARROWER ONE.** The defect is in the
**emitted artifact** too. The tool's own read-out, preserved byte-identical as
[`verdicts/READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md`](verdicts/READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md),
prints under its `## BRANCH: U-UNREADABLE` heading:

- a full **`## §4.3 item 2 — the D block: THE PRIMARY`** section — `D` +0.6460, `se_D` 0.4671,
  **`z_D` +1.3830**, **`UB95(D)` +1.4143**, `CI90(D)` [−0.1224, +1.4143], `rho` +0.0895,
  **`EQUIV` (one_sided) = False**, and both resolving-`n` figures; and
- **`UB95` again inside the gate table itself** — the `G-STAT` row reads
  `PASS | UB95=+1.4143 se_D>0=True`.

⇒ **the `U-UNREADABLE` suppression clause was enforced by nothing but the read-out author's
discipline, and it leaked on the first gate failure this campaign's game cells ever had.** The
suppression is a property the **emitter** must own, not the prose.

⚠️ **It is stated as a defect, not softened.** The R4 precedent for a clean ruling
([`../ADJUDICATION_R4_GATES.md`](../ADJUDICATION_R4_GATES.md) *"OWNER RULING — 2026-08-18, made
BLIND"*) was available on *"unusually clean terms: nothing is scored, so the ruling is blind to
every statistic it could affect."* **Those terms were not available here, and the difference is
the tool's fault, not the owner's.**

### 5.1 Why the ruling is nonetheless defensible — the argument, in advance and on the record

**Two facts, both fixed before the ruling was given:**

1. ⭐ **Reading A lands on `L-AMBIGUOUS`, the one branch of five that licenses NOTHING and
   favors NO ONE.** It does not swap the deploy down, does not confirm the incumbent at 2σ, does
   not license a `B` = 128 prereg, does not kill the `B` = 128 question, does not mint a claim,
   does not touch `PRODUCTION.yaml`. A non-blind ruling that buys the ruler **nothing** is the
   weakest possible form of the objection blindness exists to prevent. Under Reading B the run
   is void and also licenses nothing — ⇒ **the two readings differ in what is *recorded*, not in
   what is *authorized*.**
2. ⭐ **The orchestrator's written recommendation, put to the owner BEFORE the ruling, stated in
   advance that a non-blind ruling toward any REWARDING branch would instead have drawn a
   "stand + fresh-band re-run" recommendation.** I.e. had the statistics selected `L-SATURATED`
   (which licenses the owner's one-word swap-down and kills `B` = 128) or `L-RISING` (which
   licenses a `B` = 128 prereg), the recommendation would **not** have been to rule the conjunct
   discharged post-hoc — it would have been to let `U-UNREADABLE` stand and re-run on a fresh
   band under a successor pair with the defect fixed. **The asymmetry was declared before the
   ruling, not discovered after it.**

⛔ **What this disclosure does NOT do.** It does not make the ruling blind, does not retroactively
satisfy §7, and does not set a precedent that a non-blind gate ruling is acceptable when the
ruler judges the stakes low. **The successor's obligation is to fix the print, not to rely on
this argument again** ([`../DEVIATIONS.md`](../DEVIATIONS.md) **D7.2**).

⛔ **And the defect is NOT patched into this adjudicator.** `analyze_b32v64_cell.py` is a **spent**
tool for a **spent** read-rule; editing it now would change the behaviour of the instrument that
produced the artifact of record, after the fact. The fix is **owed to any successor adjudicator**
and is recorded as owed. Blindness cannot be restored by editing the tool that already spent it.

---

## 6. THE OWNER RULING — 2026-08-22 (post-havdalah)

> ## Verbatim: **"reading a"**

**Reading A governs. `G-BAND` conjunct 4 is DISCHARGED by the confirmed failure set. The branch
table applies unamended to the resolved statistics, and the branch is `L-AMBIGUOUS`.**

**What the owner resolved:** a **drafting defect** — the unwritten relation between `G-FAILED`'s
tolerance and `G-BAND` conjunct 4's identity requirement — on a written analysis that (i) named
the contradiction and showed the pair is self-inconsistent for every `n_failed > 0`, and (ii)
exhibited the intent witness of §2. **A governance act on the pair's text, not a reading of a
result.**

**What the owner did NOT resolve, and what no ruling in this document does:**

- ⛔ **No bar, branch, statistic, estimand, address, seed derivation or power figure moves.**
  `TOLERANCE_PTS` stays 0.93; `EQUIV_SHAPE` stays `one_sided`; the five branches and their
  first-match order are untouched; `D`, `se_D`, `z_D` and `UB95(D)` are the adjudicator's own
  numbers, recomputed by nobody.
- ⛔ **The pair is not amended.** [`DESIGN.md`](DESIGN.md) and [`READ_RULE.md`](READ_RULE.md)
  stay exactly as blind-committed at `71b3286c`. The taxonomy gap is fixed **prospectively**, in
  the standing lesson of D7.1, never retroactively here.
- ⛔ **The `G-FAILED` clause-3 confirmation still adjudicates nothing.** It gated escalation
  only; this ruling gates a **conjunct's discharge**. They are two owner acts on two different
  questions and neither one moved a statistic.
- ⛔ **`governance/PRODUCTION.yaml` is untouched**, no claim is minted in
  `governance/CLAIM_REGISTRY.csv`, and the read-rule is **SPENT** on every branch — including
  this one. Band `140000000000` **retires from confirmatory use**.

### 6.1 The mechanical record survives the ruling

⚠️ **`U-UNREADABLE` is not deleted and is not "corrected".** It stands, permanently, as **what
the frozen rule executed literally produced from these artifacts** — the same way `B-COSTKILL`
stands as the `b64_cell`'s verdict even though the owner subsequently bought B=64. The two
records are different objects and both are true:

| | record |
|---|---|
| **Mechanical, tool-emitted** | `U-UNREADABLE` — `G-BAND` FAILED on conjunct 4, `same_decks: false`, 12/13 gates PASS (`READOUT_B32V64.json::branch`) |
| **Verdict of record, post-ruling** | ⭐ **`L-AMBIGUOUS`** — under owner Reading A, 2026-08-22, this document + `READOUT_B32V64.json` |

**Anyone citing this cell must carry both, and must carry §5.**

---

## 7. Summary

| # | question | ruling |
|---|---|---|
| 1 | Does `G-BAND` conjunct 4 fire when the *only* deck-set difference is `G-FAILED`'s own tolerated, owner-confirmed failures? | **Was AMBIGUOUS on the text** — the two clauses contradict each other for every `n_failed > 0`, a drafting defect of the unsatisfiable-gate class. **RESOLVED by owner ruling 2026-08-22, verbatim "reading a": the conjunct is DISCHARGED.** |
| 2 | What is the mechanical record? | **`U-UNREADABLE`, and it stands unedited.** 12/13 gates PASS; `G-BAND` failed on conjunct 4 alone; `decks_only_in[CELL_B32] = []`. |
| 3 | What is the verdict of record? | ⭐ **`L-AMBIGUOUS`** — `z_D` +1.3830 (`−2.0 < z_D < +2.0`) and `UB95(D)` +1.4143 > 0.93 (`¬EQUIV`). **This document + `READOUT_B32V64.json` together are the verdict of record.** |
| 4 | What does it license? | ⛔ **NOTHING.** Deploy stays `B` = 64 / `J` = 4; `B` = 128 unfunded by default; `PRODUCTION.yaml` untouched; no claim minted; read-rule SPENT; band 140e9 retired. |
| 5 | Was the ruling blind? | ⛔ **NO** — the adjudicator printed `z_D` and `UB95(D)` beside the failed gate, a tool defect against [`../shared_run/READ_RULE.md`](../shared_run/READ_RULE.md) §7. Defensible because the branch it landed on licenses nothing and favors no one, and because the recommendation declared **in advance** that a rewarding branch would have drawn "stand + fresh-band re-run" instead. **Fix owed to the successor, never patched into this spent tool** (D7.2). |
| 6 | Why did neither review catch it? | The `b64_cell` fixture realized **0 failures**, where the two clauses are consistent and clause 3 is *vacuous*. **A known-good fixture proves a rule passes a healthy run of the fixture's shape, not of every healthy shape the rule admits** (D7.1's standing lesson). |

**Deviation record:** [`../DEVIATIONS.md`](../DEVIATIONS.md) **D7.1** (the contradiction) and
**D7.2** (the §7 print defect).
**Read-out:** [`verdicts/READOUT_B32V64.md`](verdicts/READOUT_B32V64.md) +
[`verdicts/READOUT_B32V64.json`](verdicts/READOUT_B32V64.json).
**Escalation record:** [`ESCALATION_20260822.md`](ESCALATION_20260822.md) +
[`verdicts/HALT_B32V64.json`](verdicts/HALT_B32V64.json).
**Governing pair:** [`DESIGN.md`](DESIGN.md) + [`READ_RULE.md`](READ_RULE.md), blind commit
`71b3286c` — **SPENT**.
