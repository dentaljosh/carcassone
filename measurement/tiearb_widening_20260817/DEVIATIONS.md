# TIE-ARBITER WIDENING — POST-BLIND DEVIATION LOG

> **Scope: the shared rung-2+3 instrument run.** The prereg pair
> [`shared_run/DESIGN.md`](shared_run/DESIGN.md) + [`shared_run/READ_RULE.md`](shared_run/READ_RULE.md)
> is **BLIND-COMMITTED AND FROZEN**. Nothing in either file moves. This log lives **outside**
> `shared_run/` deliberately: it is **referenced by** the frozen pair's deviation clause
> (READ_RULE §7), never embedded in it.
>
> **Owner ruling 2026-08-18, verbatim "b+c"** on the scoring wall-clock: **(B)** build the two-box
> scoring layer; **(C)** *if* the running feasibility check lands FEASIBLE, swap the `clair-puct`
> IF leg to the existing rust clairvoyant under a Phase-A-style bit-exactness gate.

## The rule this log instantiates

1. **A post-blind change may touch ONLY emitter and execution machinery** — how work is split,
   launched, resumed, merged, and how fast it runs. It may **never** touch a **gate**, an
   **address**, a **bar**, a **branch**, a **statistic**, an estimand, a seed derivation, or a
   power figure. A change that cannot be described without naming one of those is not a
   deviation; it is a new prereg.
2. **Each deviation carries its own neutrality proof**, written *before* it runs, clause by
   clause, naming for each clause the evidence that discharges it. **A clause I cannot sign is a
   rejected deviation, not a caveated one.**
3. **The read-out must print this deviation list** — every numbered deviation, its status, and its
   signature verdict — on whichever branch fires. A deviation that appears for the first time in
   the read-out is a defect, not a disclosure.
4. **Signature discipline.** A deviation is `SIGNED` only when every clause of its neutrality
   analysis is discharged by delivered code or a committed artifact. Until then it is
   `FRAME DRAFTED — SIGNATURE HELD`, and **the run does not use it**.
5. `governance/PRODUCTION.yaml` untouched by every deviation, as by every branch.

| # | deviation | status |
|---|---|---|
| **D1** | two-box scoring layer (chunk / allocation / merge) | ✅ **ALL SIX CLAUSES SIGNED** on the delivered layer (`1670f030`: `stage_chunks.py`, `ALLOCATION.conf`, `run_scoring.sh`, `merge_legs.py`/`merge_scoring.sh`, 36 tests). **TRANSFERS TO R4** as a **first-class instrument choice, not a deviation** — the clause-by-clause discharge is `shared_run_r4/DESIGN.md` R4-4; this section remains the neutrality argument of record. **Confirmed on the real corpus by `stage_chunks verify`, post-corpus; a failure there sends R4 single-box.** |
| **D2** | rust IF judge swap (owner ruling C) | ⛔ **CLOSED AS UNNECESSARY — no deviation exists.** See the closing note below |

> ⚠️ **The run these deviations were drafted against STOPPED PRE-SCORING** and its pair is
> **SPENT-BY-GATE-FAILURE** ([`PREREG_FAILURE.md`](PREREG_FAILURE.md)). Neither deviation was ever
> in force; **neither was used to score anything.** D1's analysis transfers intact to the R4
> successor pair — the scoring layer it describes is unchanged and so is every clause of its
> neutrality argument, because none of those clauses depended on the corpus or its size.

## D2 — CLOSED AS UNNECESSARY (investigated; found already first-class)

**Verdict: there was never a swap to make, and the estimand was never at risk.** The
`clair-puct` IF leg has dispatched to **rust** on `walled` since **2026-08-02**:
`run_tiletie.py:117` (`JUDGE_BACKEND: clair-puct → rust`) and `:154`
(`RUST_OK_PROFILES = {"walled"}`), and this run's corpus is `walled`-only. The bit-exactness
evidence already exists and is committed:
**`measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` — PASS, 20 positions / 940 field
checks / 0 mismatches** at the pilot's own record interface. The **9.4×** figure quoted in the
campaign is *that already-taken swap's own captured speedup*, from the same gate family — not a
speedup still available to be bought.

**What this means for §D2.1's premise-pinning demand: it is answered, and the answer is that the
premise was false.** A deviation framed as "python → rust" had no referent; `c_IF = 2.35`
worker-s/playout — 93% of the run's bill — **was already a rust figure.** The correct disposition
is closure, not a parity run: **no parity was executed, none is owed, and no artifact is pending.**
The gate conditions in §D2.2 and the legal-mask-cache rule in §D2.3 are retained below **only as
the record of what would have been required**, and bind nothing.

⭐ **The one durable output of the investigation** is a constraint now promoted into the successor
pair's threat model (`shared_run_r4/DESIGN.md` R4-4): **the rust clairvoyant path requires
`walled`** — `RustCarryClairvoyantAgent` mirrors no rules config, and `fixed_v1` / `app_aug2`
**fail loud** rather than grade under the wrong rules. Safe today because the corpus is
`walled`-only; stated so that **no future stratum, top-up or extension silently mixes profiles.**

*(A stale "python-era" label on this leg was corrected on main at `894699e3`; it is not
inherited here.)*

---

## D1 — Two-box scoring layer

**Status: FRAME DRAFTED — SIGNATURE HELD.** Signature verdict below is **not yet given**; §D1.4
lists exactly what discharges each held clause.

### D1.1 What is being added

Per the tiearb2 pattern (`measurement/tiearb2_20260816/`): a committed position permutation
(`POSITION_ORDER.json`), a per-box allocation file (`ALLOCATION.conf`), and
`run_scoring` / `merge_scoring` drivers that split the scoring legs across the local box and the
laptop and merge the per-box record trees into one tree the analyzer reads.

**Nothing else.** No knob of the measurement changes: same `--m` per stratum, same salt, same
judges, same `--arb-backend rust`, same `--positions-dir` (explicit, DESIGN §0.O), same arm sets,
same worlds.

### D1.2 The neutrality claim, clause by clause

The deviation is gate-neutral iff **every** clause below holds. I sign C1, C2 and C6 now from code
already read; C3, C4 and C5 are **held** pending the builder's delivery.

**C1 — the CRN seed derivation is box-invariant. ✅ SIGNED.**
`oracle_score_pilot.world_seed / playout_seed` are `sha256(tag | rid | j | salt)`. **Neither the
box, the chunk, the allocation, nor `M` enters the derivation** — this is the same property
`G-PREFIX` already rests on (`preflight_seeds()` asserts it fatally at launch, on every box). Two
boxes scoring disjoint rid sets under one salt therefore produce exactly the worlds a single box
would have produced for those rids. This is the load-bearing clause and it is the one the
instrument was already built to guarantee.

**C2 — the merged tree is per-rid byte-indistinguishable from single-box, and the pattern is
precedented. ✅ SIGNED.**
Records are written one JSON object per rid (`records/<rid>.json`, per-leg), so a merge is a
**union of disjoint filenames**, not a rewrite: no record is recombined, re-serialised or
re-ordered internally. Stage-1b already scored in four chunks and analysed from a `merged/` tree
(`…/tiearb2_20260816/main/merged/tier1-greedy::walled/leg<N>`), and `analyze_tiearb2 --arb-records`
is `action="append"` — multi-root, merge-then-analyse is the instrument's existing shape, not a
new one.

**C3 — chunking partitions WHOLE rids, with no rid split across boxes. ⏸ HELD.**
A rid's legs (`leg1…leg<A−1>`) and both judges' records for that rid must land in one allocation
unit. A partition that split a rid across boxes would still be seed-identical (C1), but it would
break the per-rid completeness accounting `G-ARMS` and `G-COMPLETE` read, and could strand a
half-scored rid on a failure. **Evidence required:** the builder's report showing the allocation
unit is the rid (not the leg, not the arm), and that `POSITION_ORDER.json` ∪ `ALLOCATION.conf`
partition the rid set **exactly once** — a checked disjoint-and-covering assertion, not a comment.

**C4 — no cross-record state leaks between positions within a worker. ⏸ HELD.**
`game_wrapper.Game._legal_cache` is an **instance** attribute (`src/carcassonne_ai/game_wrapper.py:556`),
not a process global, and Phase A showed the memo is not injective for 180°-symmetric tiles
(57/15,360 values moved on it). So the memo is chunk-invariant **iff each record is scored on its
own `Game` instance**; if any worker reuses one `Game` across records, the served mask — and
therefore a value — could depend on **which other positions that worker happened to see**, which
is exactly a box/chunk dependence. **Evidence required:** confirmation that the chunked path
constructs one `Game` per record (as the single-box legs do) and reuses none across records.
⚠️ This is the clause most likely to be assumed rather than checked, and it is the one that would
silently make values allocation-dependent.

**C5 — claims, resume and clock discipline do not drop or duplicate work. ⏸ HELD.**
The house failure modes are on record: a `--shared-claim` kill **strands `.claim` files and stalls
resume**, and **WSL clock drift after host sleep lets a fast box silently steal every claim**. A
two-box layer must be robust to both, and must fail **loudly** rather than quietly scoring fewer
positions — a silent shortfall would surface only as a `G-COMPLETE` failure after the money is
spent. **Evidence required:** the resume/claim design, plus a stated guard for the clock-drift
case (the launcher-side F7c guard is the precedent).

**C6 — the gates' and analyzer's join keys are `rid`, never box or chunk. ✅ SIGNED.**
`G-CRN` joins per-record witnesses by rid; `G-ARMS`/`G-COMPLETE` count per-arm and per-rid;
`G-DRAW`, `G-UNCAPPED`, `G-SALT` read `ARMS.json`/`POSITIONS_PLAN.json`, which the scoring layer
does not touch; the analyzer's pairing of IF against ARB is per rid, and the bootstrap clusters on
`root_id`. **No gate, address, bar, branch or statistic named in the frozen pair takes the box,
the chunk, the allocation or the merge order as an input.** The one place ordering could have
mattered — `--n` subsampling — is already neutralised: `run_tiletie` passes `--n` explicitly as
each leg's own line count precisely so a differing subsample can never arise.

### D1.3 Signature

> **VERDICT: HELD.** C1, C2, C6 signed. **C3, C4, C5 unsigned pending the builder's delivered code
> and its own neutrality report.**
>
> **If any of C3/C4/C5 cannot be discharged, D1 is REJECTED and the run scores single-box.** That
> is the cheaper failure by a wide margin: single-box costs wall-clock, an allocation-dependent
> value costs the measurement.

### D1.4 What discharges the held clauses

| clause | discharged by |
|---|---|
| C3 | allocation unit = rid, and a **checked** disjoint-and-covering assertion over `POSITION_ORDER.json` ∪ `ALLOCATION.conf` |
| C4 | one `Game` per record in the chunked path; no `Game` reuse across records in any worker |
| C5 | resume/claim design that fails loudly on stranded claims, plus a clock-drift guard |

---

## D2 — Rust IF judge swap — the retained frame (BINDS NOTHING; see the closure note above)

**Status: CLOSED AS UNNECESSARY.** Everything below is the record of what the deviation *would*
have had to satisfy. **No parity was run, none is owed.** Retained because a future proposal to
re-point any judge at a different engine should inherit these conditions rather than re-invent
them — and because §D2.1's premise question is exactly the one that dissolved the deviation.

### D2.1 ⚠️ The premise needed pinning first — and pinning it is what closed the deviation

✅ **ANSWERED: the premise was false.** What follows is the reasoning that produced that answer.

**The IF leg is already rust-backed on this run's profile.** `run_tiletie.JUDGE_BACKEND` maps
`clair-puct → rust`, `RUST_OK_PROFILES = {"walled"}` and this run is walled-only; the pilot itself
records *"`--oracle-policy clair-puct` DOES run on carc_rs since 2026-08-02 — Gap 2 closed"*
(`oracle_score_pilot.py:270`) and **refuses** a non-python backend for any other policy (`:1062`).
So `c_IF = 2.35` worker-s/playout — 93% of this run's bill — **is already a rust figure.**

Consequently the swap cannot be "python → rust". It must be a **different rust entry point** — a
direct `carc_rs` clairvoyant leg runner in the shape W1 built for the ARB judge, cutting the
pilot's per-position python overhead — and the parity is therefore **rust-vs-rust**, not
python-vs-rust. **Before D2 can be signed, the builder's report must state, in one paragraph and
with file:line: what the incumbent IF leg executes today, what the replacement executes, and where
the claimed speedup comes from.** A feasibility verdict resting on "it's python today" is
answering a question this run does not have.

### D2.2 The gate — the swap is legitimate iff ALL of these hold

1. **Full f64 bit equality, zero mismatches.** A Phase-A-style gate over **real corpus smoke
   positions** (not fixtures) shows **0 value mismatches at raw f64 bit-pattern equality** —
   `_f64_bits`, the currency Phase A and `G-BITEXACT` already use. Not "within tolerance", not
   "agrees to 1e-12": **bit-identical**.
2. **Both strata's knob sets.** Parity is run at **`m = 128` (S1) and `m = 32` (S2)**, on that
   stratum's own positions. A parity at one `M` does not license the other.
3. **The parity artifact is committed beside this deviation** — the same shape
   `GATE_BITEXACT_HEAD.json` uses (`pass`, `n_playouts_compared`, `n_value_bit_identical`,
   `n_value_mismatch`, `git_rev`, and the knob block) — before the swapped leg scores one paid
   position.
4. **Estimand unchanged by construction.** Under bit-exactness the swap changes *who computes* a
   value, never *what the value is*: every downstream statistic, CI, gate and branch reads
   identical inputs. This is the whole argument, and it holds **only** while (1) holds exactly —
   which is why nothing weaker than bit equality is acceptable here.
5. **The CRN contract survives.** The replacement consumes the same `world_seed`/`playout_seed`
   derivation (`sha256(tag|rid|j|salt)`, salt `tiletie-v1`) and emits a CRN witness `G-CRN` can
   read — and if it emits a *different* witness kind than the incumbent (W1's ARB port had to,
   `world_deck_hash` vs `afterstate_deck_hash`), **that kind must be declared and must not mix
   within one judge's legs**, which is `G-CRN`'s existing conjunct.

### D2.3 The legal-mask-cache question, stated explicitly

Phase A's ARB port needed `legal_mask_cache=True` to reproduce `game_wrapper.Game._legal_cache`'s
**non-injective** memo — without it, 57/15,360 values moved, and the honest recomputed mask is
**not** python-comparable. `G-BITEXACT@HEAD` therefore forbids the `--no-legal-mask-cache`
spelling outright.

**The rule for D2:** the parity **must be run at whatever setting the incumbent IF leg actually
uses — determined by reading the incumbent's code path and its manifest, never assumed.** Two
cases, and the builder's report must say which one obtains:

- **If the incumbent IF path exercises the python memo**, the replacement must reproduce it, and
  parity runs with the memo **on** — the Phase-A situation exactly.
- **If the incumbent IF path never touches `Game._legal_cache`** (plausible: it is the *python
  continuation's* memo, and the incumbent runs the rust clairvoyant), then the memo is **not a
  compat axis for D2 at all**, and the replacement must likewise not introduce one. Saying so
  explicitly matters: silently carrying the ARB leg's `legal_mask_cache=True` convention into a
  judge that never used it would be a change of computation dressed as a compatibility measure.

**Either way the setting is recorded in the parity artifact and in the run manifest**, so a reader
can see which regime was in force.

### D2.4 Rejection condition

> **Any nonzero mismatch — one value, one bit, on either stratum — and D2 is REJECTED: the
> incumbent IF judge stands and the run pays the wall-clock.** No partial adoption (e.g. "swap
> S2 only because S2's parity passed"), no tolerance band, no "the mismatches are in positions
> that don't matter". The estimand argument in D2.2(4) is *entirely* load-bearing on exact
> equality; weaken it and the deviation stops being a deviation and becomes a new instrument
> needing a new prereg.
>
> Equally: **if the feasibility check does not land FEASIBLE, D2 simply does not happen.** The
> owner's ruling is conditional and this frame does not make it less so.

### D2.5 To be filled when the evidence exists

`premise pinning (D2.1)` · `parity: m=128 n_compared / n_mismatch` ·
`parity: m=32 n_compared / n_mismatch` · `legal_mask_cache regime` · `CRN witness kind` ·
`parity artifact path + git_rev` · `realized c_IF vs the committed 2.35 worker-s/playout` ·
**`SIGNATURE`**.

---

*No gate, address, bar, branch, statistic or estimand of the frozen pair is altered by D1 or D2.
`governance/PRODUCTION.yaml` untouched. Neither deviation is in force until its signature block
reads SIGNED.*
