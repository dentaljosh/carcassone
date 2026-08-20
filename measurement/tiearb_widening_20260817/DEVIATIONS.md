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
| **D3** | `execution` merge classification + the unwitnessed cross-box link | **CLASSIFICATION RULED** (PER_CHUNK, §D3.2); **`D3-WITNESS` PENDING** — amended by D4 to run **before the completion scoring**, not merely before analysis |
| **D5** | R5's two-rev merge licence + **the orchestrator's own freeze violation** | **LICENCE RULED**; binary-sha conjunct ruled **conditionally, decision rule pre-committed** (§D5.2); freeze violation named with `W-FREEZE-LATCH` recommended (§D5.3) |
| **D4** | the union assembled ARMS but not leg files — **551 committed rids never scored** | **RULED: completion-scoring licensed**, sequenced behind `D3-WITNESS` (**PASSED** 23,184/23,184); S2 orphans moot (stays void). **§D4.10-12: the two-rev tranche split is foreseen and NOT forbidden** — enumerated licence + instrument witness, in code. **§D4.13: `carc_rs_build` licensed under four conjuncts**, closing a within-box staleness hole D3 opened. **§D4.14: `preflight.checks` ruled exhaustively (7/7); the classification sweep COMMISSIONED**. **§D4.15: sweep SIGNED OFF** — 355 artifacts, 134 rows, 0 unclassified, 0 gate-addressed paths missing; the closed-by-enumeration property holds and the fail-closed default now means *schema change*. **§D4.16: merge SUCCEEDED 1344/1344; the two Reading-A consequences ruled** (analyzer `VOID_S2` guard on a positive witness; S2-addressed conjuncts scoped `VOID (stratum)` in the harness). **§D4.17: implementation SIGNED OFF** — `G-COMPLETE`'s S2 conjunct void-scoped under the same uniform rule; the X-token enumeration dropped for zero occurrences. **§D4.18: 4 window-truncation rids dropped WHOLE-RID** (what `G-ARMS` already implies); **no post-hoc numeric bound enacted** — the pair's own floor governs, 1,340 ≥ 1,283. **§D4.19: the S2 void-scope stated GENERALLY** (artifact paths · analyzer conjuncts · READOUT key-paths alike), dual-witness, exact-segment match |

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

## D3 — `execution` merge classification, and the unwitnessed cross-box link

**Status: RULED (classification) + WITNESS REQUIRED (§D3.5) before analysis.**
**Post-blind legality: execution/merge layer only — no gate, bar, address, branch or statistic of
the R4 pair changes.** Verified by grep across all four documents (`shared_run{,_r4}/{DESIGN,
READ_RULE}.md`): **`execution`, `carc_rs_binary_sha`, `carc_rs_build`, `binary_sha` and `G-TOOL`
appear ZERO times.** No conjunct binds on `execution` identity. `G-BACKEND` binds
`arb_backend` / `resolved_backend_by_leg` / `arb_legal_mask_cache`; `G-SALT` binds
`world_seed_salt`; `G-M` binds `m_worlds` / `b_ceiling_from_m`; `G-LEAF` binds the leaf hash;
`G-BITEXACT@HEAD` binds its own gate file. **None reaches inside `execution`.**

### D3.1 What happened

`merge_legs.py` raised on key **`execution`** — UNCLASSIFIED, the fail-closed default — for all
**11 multi-chunk `clair-puct` legs**. `tier1-greedy` legs merged clean (python judge, no
`execution` block, all 8 chunks local). Within `execution` **exactly two keys differ, split on the
box boundary**: `carc_rs_binary_sha` (`a4318fd5…` local / `8ae0b984…` laptop) and `carc_rs_path`
(py3.12 vs py3.14 site-packages). Everything else is equal — `git_rev 58c2b539` identical on all
16 chunk manifests, leaf `a36d2e15a3b3d71d`, **`carc_rs_build` equal**, env block byte-equal,
tile-data digests equal.

⭐ **The merge did exactly what the pair pre-registered.** `shared_run_r4/DESIGN.md` R4-7.5,
quoted: *"…and **an unclassified differing key raises** rather than defaulting. That last rule is
the important one: **it fails closed on fields nobody anticipated.**"* `execution` is such a
field. **This is a schema gap in the throughput layer, not a gate failure and not a defect in the
run.**

### D3.2 RULING (A) — classification, with one amendment to the proposed reading

**ACCEPTED with a refinement: `execution` is PER_CHUNK, but NOT as an opaque block.**

Blanket-PER_CHUNK on the whole `execution` block would open it permanently — a *future*
divergence inside `execution` that is **not** box-local (a different rust version, a different
build) would then be recorded silently instead of raising, which is precisely the property R4-7.5
calls "the important one". So:

| key | class | why |
|---|---|---|
| `execution.carc_rs_binary_sha` | **PER_CHUNK** (⚠️ **AMENDED by §D4.13**: PER_CHUNK for *cross-host* purposes — never compared across boxes — **plus a WITHIN-BOX constancy assertion** across all of that box's chunks) | **JCZ §0.F.2c** (`READ_RULE.md:135-164`, commit `0db347f0`): the `.so` is **not machine-reproducible**; this value is **BOX-LOCAL and may NEVER be compared across hosts.** The pair of shas observed here is the identical pair that ruling measured on these same two boxes. |
| `execution.carc_rs_path` | **PER_CHUNK** | site-packages path — box-local by construction, carries no run semantics. Same category as `workers`, which R4-7.5 already **nulls** as *"box-specific, meaningless merged"*; PER_CHUNK is strictly better than nulling because it **records** rather than discards. |
| `execution.carc_rs_build` | **IDENTITY_REQUIRED** | the **cross-host witness named by the JCZ ruling** — the value that legitimately *may* be compared across hosts. Equal here (`carc_rs-0.1.0+58c2b5395569+rustcunpinned`). If it ever differs, the merge **must** raise. |
| any **other** key inside `execution` | **RAISE (unchanged default)** | preserves R4-7.5's fail-closed-on-the-unanticipated property. Opening the block wholesale would trade a real guarantee for a one-time convenience. |

**`--allow-varying` is REJECTED** — it silences rather than records, and provenance is the merge
layer's entire job.

⚠️ **Flag spelling not verified: `merge_legs.py` is not in the main tree** (the two-box layer is
still in the builder's worktree at `1670f030`), so I specify the classification **semantically**
and decline to invent a command line. **The executor must map this onto the tool's actual
constants** — reported as `AGGREGATE_SUM` / `PER_CHUNK` / `IDENTITY_REQUIRED` — and confirm the
nested-key form is supported. **If the tool only classifies top-level keys**, the equivalent is:
classify `execution` PER_CHUNK **plus** an explicit pre-merge assertion that
`execution.carc_rs_build` is equal across all chunks and that **no key inside `execution` other
than `carc_rs_binary_sha` / `carc_rs_path` differs** — that assertion is not optional, it is what
carries the IDENTITY_REQUIRED and RAISE rows above.

### D3.3 The laptop backend-gate defect — valid for what they tested, wrong corpus

All 16 `GATE_BACKEND_RECHECK` PASS bit-exact (raw-f64). **But the 3 laptop gates drew a synthetic
champ-game fallback set DISJOINT from the local gates' bank set**: `gate_oracle_pilot_backend.py`'s
`_share()` picks `/mnt/c/carc-shared` **first**, which *exists* on the laptop — as that box's own
**empty C: mount** — so the bank lookup silently fell through to the synthetic fallback.

**Consequence, stated precisely:** the laptop gates are **valid for what they tested**
(laptop-rust ≡ laptop-python, on the synthetic set) and the local gates are valid for theirs
(local-rust ≡ local-python, on the bank set). **They do not compose.** No position exists that
both boxes ever computed, so **laptop-python ≡ local-python is NOT witnessed** by any artifact.

**For the fix list (code, not this run):** `_share()`'s path ordering — probing `/mnt/c/carc-shared`
before `/mnt/carc-shared` — is a **latent cross-box defect wherever it appears**, because the
losing path *exists but is empty* on the remote box, so it fails **silently** rather than loudly.
The CLUSTER_OPS invariant ("the share path differs by box") is exactly this hazard, and a
silent-fallthrough is the worst form of it. **A `_share()` that cannot find the bank must RAISE,
never substitute a synthetic set.**

**Also recorded, not adjudicated:** the gates ran **8 positions against the script's own stated
`>=20` bar** — a shortfall in the gate's own terms, disclosed here rather than discovered later;
and the 8 files labelled `tier1-greedy` are **`clair-puct` re-runs**, so they gate nothing about
`tier1-greedy` — **moot**, since `tier1-greedy` is the python judge and ran single-box.

### D3.4 ⚠️ The gap is in a clause I SIGNED, and I state it as mine

**D1 never contained a cross-box numerical-identity clause.** C1 establishes that the **seed
derivation** is box-invariant (`sha256(tag|rid|j|salt)` — true, and it covers the seeds only).
C2/C4 establish that the **merge** does not rewrite records and that **chunking** is invariant *on
one box* — C4's discharge argues that "a chunk is an ordinary run over fewer rids", which
generalises across **chunks**, not across **hosts**. **The assumption that two boxes compute
bit-identical values from identical seeds was implicit and unwitnessed**, and whole-rid containment
(793 clair-puct rids = 479 local + 314 laptop, empty intersection) means it *cannot* be witnessed
by the run's own records: no rid was ever computed twice.

### D3.5 RULING (B) — `G-REPLICATE` is NOT the witness; a direct witness is required

**Checked against the implementation** (`analyze_widening.py:759-810`) and the pair's
`G-REPLICATE` row. **Answer: NO, on four independent grounds.**

1. **It recomputes nothing.** It reads the already-derived `ladder_e16` rungs and compares each
   `arb` to `STAGE1B_LADDER.json`'s banked `arb` via `z = (run − ref)/sqrt(run_se² + ref_se²)`.
   No position value is re-derived, so no arithmetic is re-executed anywhere.
2. **Its unit is a stratum-wide mean.** Boxes first mix in the stratum mean; a per-position
   divergence on 314 laptop rids is diluted into an average over 793.
3. **Its envelope is deliberately 2×-INFLATED** (`ENVELOPE_INFLATION = 2.0`, CL-068) — calibrated
   to tolerate a *different population*, hence far too coarse to resolve a numerical-identity
   question.
4. ⭐ **Its FAIL semantics are wrong for this question.** A `G-REPLICATE` failure means
   **"UNINTERPRETABLE — the fresh corpus is a different population"**, *never* "the boxes
   disagree". Even a fail would misdiagnose.

**⇒ SPEC — `D3-WITNESS`, a disclosed pre-analysis check, run BEFORE the read-out:**

- **What:** on the **local** box, re-score **N = 16** laptop-scored S1 `clair-puct` rids with the
  committed CRN seeds (salt `tiletie-v1`, the leg's own `--m`), and diff the results against the
  **laptop's stored records** in **raw f64 bit patterns** (`_f64_bits` — the same currency
  `G-BITEXACT` uses). Rids chosen **deterministically and recorded** (first 16 by sorted rid across
  both S1 legs); 16 rather than 8 because the check is cheap and a systematic libm/build
  divergence should be visible on essentially every position.
- **Bar: 100% bit-identical, `n_mismatch == 0`.** Not "within tolerance". **Any single mismatch
  refutes the implicit assumption**, means the merged corpus mixes two arithmetics, and is an
  **owner-level escalation** — not something this deviation may absorb.
- **Disclosure discipline, reusing `verify_tier1_rust`'s verbatim:** the artifact
  `RUN/CROSSBOX_WITNESS.json` carries **counts and digests only** —
  `{n_rids, rids, n_values_compared, n_bit_identical, n_mismatch, sha256_local, sha256_laptop,
  digests_equal, pass}`. *"A digest is not a value and is not invertible, so no adjudicated
  per-leg value leaves this gate."* No `arb`, no `ora`, no Δ.
- **Cost:** ≈660 playouts/position × 16 × realized `c_IF` 1.755 worker-s ≈ **5.2 worker-h**
  (~10 min at W30). Negligible against the run.
- **Also record** (free, and the artifacts do not carry it today): python / numpy / glibc versions
  per box — local 3.12.3 / 2.4.4 / 2.39 vs laptop 3.14.4 / 2.4.6 / 2.43. **A cross-box run whose
  manifests do not record the interpreter and libm stack cannot answer this question from its own
  artifacts**, which is why the witness has to be run rather than looked up.

**RESULT: ⬜ PENDING** — to be filled with `n_values_compared / n_mismatch / digests_equal` and the
PASS/FAIL. **Analysis does not proceed until this reads PASS.**

### D3.6 Signature

> **CLASSIFICATION (A): RULED — PER_CHUNK per §D3.2's table, `--allow-varying` rejected.** The
> pair's text does **not** forbid it: no conjunct binds on `execution`, and R4-7.5 predicted and
> licensed exactly this fail-closed raise on an unanticipated field.
> **WITNESS (B): D1's six clauses stand as signed, but they never covered cross-box numerical
> identity (§D3.4). `D3-WITNESS` supplies it, and until it reads PASS the two-box merge is not
> cleared for analysis.**

---

## D4 — the union assembled ARMS but not LEG FILES: 551 committed rids never scored

**Status: RULED — COMPLETION-SCORING LICENSED, sequenced behind `D3-WITNESS`.**
**Post-blind legality: assembly/execution layer only — no gate, bar, address, branch, statistic or
estimand of the R4 pair changes.**

### D4.1 What happened, and why every check said "complete"

`union_positions.py` merged `ARMS.json` (**1,344 S1 rids** = 551 retained 135e9 + 793 fresh 137e9)
but **the leg files in the union dirs are extension-only**: `POSITIONS_PLAN.json`'s `files` block
points every leg file at `positions_s1_ext/`, and only the ext `leg1` jsonl physically exists in
the union dir. **Both judges therefore scored only the 793 fresh rids; the 551 retained rids were
never scored by any box.** S2 is the same shape (103 orphaned).

⭐ **The lesson, and it is the whole point of this entry: three independent "complete" signals were
all true — each of a different population, none of them the committed corpus.**

| check | denominator it used | true? |
|---|---|---|
| supply gate | `POSITIONS_PLAN.n_positions = 1344` — an **ARMS** count | yes, of the ARMS layer |
| `CORPUS_UNION.json` | `retained = 551`, `copied_not_symlinked = true` — asserted at the **ARMS** layer | yes, of an assembly that **did not happen at the leg layer** |
| merge completeness | records vs the **(ext-only) leg files** | yes — **793/793 against a denominator that was itself the defect** |

**The missing invariant, in one line: nothing ever asserted that the leg files enumerate exactly
the `ARMS.json` rids.** Every layer checked itself against itself. This is the R3.3 miss class —
**a gate reading a non-supply count as supply** — one layer down, and this time discovered *after*
the scoring spend rather than before it.

**Blindness is intact and that is load-bearing for everything below:** `analyze` never ran,
`--mode post` never ran, **no statistic has been revealed**. The 793's records are complete and
valid.

### D4.2 RULING (1) — COMPLETION, not re-registration. **ACCEPTED.** Nothing in the pair forbids it.

**Checked, quoting the finality clauses, all of which key on events that have not occurred:**

- *"**SINGLE USE. SPENT ON LANDING.** One adjudication, one analyzer invocation, one read-out…
  **No re-read, no second pass, no top-up at any `z`.**"* — **"at any `z`" presupposes a `z`. None
  exists.** These clauses govern **adjudication**, not scoring.
- §8: *"**When the read-out lands** this rule is spent: no re-read, no second adjudication, no
  top-up, **no re-scoring of this corpus under any other rule**."* — expressly conditioned on the
  read-out landing. It has not. And this is not *re*-scoring: the 551 have **never** been scored.
- *"The only pre-licensed top-up is DESIGN §3's blind corpus top-up, which **expires the moment the
  first scoring leg starts**."* — that clause governs **adding games**. The 551 add **no game and
  no rid**: they are inside the committed `ARMS.json`, inside `POSITIONS_PLAN.n_positions = 1344`,
  and inside `FLOORS.json`'s committed `n₁`.
- Scoring is **already multi-tranche by construction** — 8 chunks per stratum, two boxes, strata
  sequential. **A supplementary chunk is not a new kind of act**; it is the ninth chunk of a plan
  that always had chunks.

⇒ **No clause forbids completion-scoring. I do not escalate.**

⚠️ **But the honest caveat, stated because it must be:** the *shape* of this action — score more,
then evaluate the completion gate — is **superficially identical to the forbidden adaptive
pattern**. Three facts distinguish it, and all three must hold or the ruling collapses:

1. **The population was pre-committed** (`n₁` in `FLOORS.json`, before the band claim);
2. **No outcome has been observed** — the stopping rule cannot have been conditioned on a result
   that does not exist;
3. **The increment is exactly the pre-committed remainder** — not "more", but "the rest".

**Guard that makes (3) checkable rather than asserted:** the supplementary chunks must contain
**exactly** the set `ARMS.json rids − already-scored rids`, asserted as a set equality in the
re-stage artifact. Any rid outside that set, in either direction, voids the completion.

**G-COMPLETE** is therefore evaluated **once the committed corpus is fully scored**. Evaluating it
on 793 would grade the run against an artifact of a build defect rather than against the committed
corpus — and it has never been *legitimately* evaluated, since the population it read was never
the one the pair committed.

### D4.3 RULING (2) — the fix. **ACCEPTED**, with one addition

W-code fix in `union_positions.py` + a re-stage: leg files for the 551 assembled into the union
dirs (**copied, never symlinked** — per `CORPUS_UNION`'s own claim, and per R4-0.5's reasoning
that a symlink into a frozen dir invites write-through), then **supplementary chunks containing
exactly the not-yet-scored rids, whole-rid, derived deterministically from the SAME committed
`POSITION_ORDER.json` seed** — no new randomness, no re-shuffle of already-scored rids. Both
judges score the 551 (`tier1-greedy` also covered only 793).

**Addition:** the fix must also install **the missing cross-layer invariant** — an assertion that
**the union's leg files enumerate exactly the `ARMS.json` rid set**, run at assembly time and
re-checked before the first supplementary leg. Without it, this entry documents a defect it does
not prevent.

### D4.4 RULING (3) — **AMENDED: `D3-WITNESS` runs BEFORE the completion scoring**

The coordinator's reading was that D3 blocks analysis but not the 551 scoring. **I disagree,
mildly, on cost-discipline grounds rather than textual ones** — the invitation to say so is taken:

1. **`D3-WITNESS` costs ~10 minutes at W30 (≈5.2 worker-h).** The completion scoring is **≈177
   worker-h / several hours wall**. The house rule is the cheap check before the expensive spend.
2. **A `D3-WITNESS` FAIL puts the entire two-box corpus in question**, which would make the 551
   spend wasted work on a corpus that is already unusable. Spending hours to find that out is the
   avoidable order.
3. It is **the premise of the two-box completion itself**: if the 551 are to be scored two-box
   (§D4.6), the witness is what licenses mixing their records with the existing ones.

**Sequence: `D3-WITNESS` → (PASS) → union fix + re-stage → completion scoring → merge → 4b/verify →
analysis.** On FAIL: **stop, score nothing further, escalate to the owner.**

### D4.5 RULING (4) — S2. **ACCEPTED: moot.**

S2 stays **VOID** under the owner's Reading-A ruling. The 103 orphaned rids change nothing: a void
stratum is not completed into readability, and completing it would be exactly the "cure by
generation/scoring" that R4-3 rule 7 forbids. **Do not assemble or score the S2 orphans.**

### D4.6 RULING (c) — box allocation for the 551: **TWO-BOX, conditional on `D3-WITNESS` PASS**

**Does the pair's text care about box composition? NO — verified.** No gate, bar, address, branch
or statistic reads the box: the analyzer is box-blind, the primaries are **within-rid** (crossfit
over `matrix_if` rows of one rid), and boxes first mix only in the stratum-wide mean. **The pair
is silent on box composition because nothing in it depends on box composition.**

Given that, the choice is operational, and it collapses once §D4.4's sequencing is adopted:

- **If `D3-WITNESS` PASSES**, cross-box arithmetic identity is *witnessed*, box composition is
  **irrelevant by measurement rather than by assumption**, and two-box is simply faster
  (≈3.4 h vs ≈5.9 h single-box local).
- **If it FAILS**, nothing further is scored at all, so single-box was never the safe hedge — it
  would have bought nothing on PASS and saved nothing on FAIL.

⇒ **Two-box, using the same deterministic allocation machinery against the committed
`POSITION_ORDER.json`.** The corpus's box composition shifts either way; **it is disclosed here and
it is not a statistic.**

### D4.7 RULING (5) — `CORPUS_UNION.json`. **ACCEPTED**, with a required new field

Correct/reissue **only as part of the fixed assembly**; preserve the old file renamed
(`CORPUS_UNION.defective_r4.5.json` or the executor's house-style suffix); **never silently
overwrite** — the false assertion is evidence of the defect and must remain readable.

**Required in the reissued file: a LEG-LAYER witness** — per-stratum counts of rids whose leg files
are physically present in the union dir, and the set-equality assertion of §D4.3. The old file's
failure was not that it lied; it is that **it asserted at the ARMS layer a property that only the
leg layer could witness**, and a reissue without a leg-layer field would repeat that exactly.

### D4.8 The `c`-remeasure clauses: do they RE-BIND on the second tranche? **NO — and record anyway**

**Textually they do not re-bind.** §7.1's obligation is worded as a one-time precondition —
*"**Before the S1 IF leg starts**, on an IDLE box…"* — not "before each leg" and not "before each
tranche". It was discharged, and all three legs came in **cheaper than committed** (arb 0.781 /
gen 0.800 / IF 0.747, no halt; the HALT is one-sided so cheaper is recorded, never halted).

**Recommended anyway, as a record and not a gate:** log the supplementary tranche's realized `c`
into the same `c_remeasure` block as a second observation. It is free, it keeps the cost record
complete across both tranches, and it would surface a throughput surprise that the one-time
obligation is not positioned to catch.

### D4.9 Signature

> **RULED: completion-scoring is licensed** — no clause forbids it, the population was
> pre-committed, and **no statistic has been observed**. **Sequenced behind `D3-WITNESS`**, which
> is amended below. **S2 stays void.** The three distinguishing facts of §D4.2 and the set-equality
> guard of §D4.3 are **conditions of this ruling, not commentary**: if any fails, the completion is
> void and the question goes to the owner.

### D4.10 ADDENDUM — the two-rev tranche split: **foreseen, NOT forbidden**

`D3-WITNESS` **PASSED** (23,184/23,184 bit-identical, digests equal, stacks genuinely different —
`d3_witness/D3_WITNESS.json`), so §D4.4's precondition is discharged and the completion tranche is
licensed to score two-box.

**The rev split is a NECESSARY consequence of completion-scoring, not an incident.** The committed
tranche (chunks 1-8) scored at **`58c2b539`**; the completion tranche (chunks 9-16) scores at
**`4b24f512`** — the rev that exists *because* it contains the D4 fixes. **Holding the tranche at
`58c2b539` was impossible: the staging code did not exist there.** Recorded here as the foreseen
price of §D4.2's ruling, which licensed the completion knowing it would have to run at a later rev.

**Not forbidden — checked, and the check is narrower than it looks.** `git_rev` appears in exactly
**two** gate rows, and **neither constrains `RUN_MANIFEST::git_rev`**:

- **`G-BITEXACT@HEAD`** constrains `GATE_BITEXACT_HEAD.json::git_rev` — *"is the §9 step-2 W-code
  merge commit **or** a descendant of it whose cumulative diff touches nothing under…"*. The gate
  was produced **at** that merge (§9.3: *"This gate is produced HERE, at step 2's HEAD"*), so the
  **first disjunct is satisfied outright and the descendant branch is never reached.** The tranche
  revs do not enter it. The row's own ⚠️ note **expressly rejects** comparing the gate's rev to the
  run's — *"a literal `git_rev == the run's` conjunct fails a healthy run twice over"*.
- **`G-DRAW`** constrains `GATE_DRAW.json::git_rev` — one artifact, one rev, no cross-tranche
  identity claim.

⇒ **No gate constrains the run's `git_rev`.** `git_rev`/`code_rev` being IDENTITY_REQUIRED in
`merge_legs.py` is therefore a **merge-layer schema choice, not a pre-registered conjunct** —
exactly the D3 situation, and the same latitude applies. **I do not escalate.**

### D4.11 RULING (a) — the mechanism: enumerated licence + instrument witness, in CODE

**ACCEPTED with three amendments.** Keep `git_rev`/`code_rev` **IDENTITY_REQUIRED by default**;
add a **narrowly-scoped, explicitly-enumerated licensed pair** `{58c2b539 → committed tranche,
4b24f512 → completion tranche}`; **any other rev, or any third value, still refuses.**

**In CODE, not a CLI allowance** — for the reason `--allow-varying` was rejected: a flag is
invisible in the artifact and passable by anyone at any time, whereas a code-resident enumerated
licence is **reviewable, testable, diffable, and refuses everything not enumerated**. Small and
tested, before the tranche drains.

**Amendment 1 — the licence requires TWO independent things to agree.** The code holds the
enumerated pair **and** requires `RUN/INSTRUMENT_IDENTITY.json` to exist and to assert the empty
instrument diff. Either alone is weaker than both: a file can be edited, and a hard-coded pair
alone asserts nothing about *why* the pair is safe. **Both, or refuse.**

**Amendment 2 — ⚠️ the proposed instrument path list is MISSPELLED, and the error is the vacuous
kind.** `scripts/tiletie/oracle_score_pilot.py` **does not exist** — the pilot is at
**`scripts/measurement_infra/oracle_score_pilot.py`** (`run_tiletie.py:94`). A witness asserting
"empty diff" over a non-existent path is **vacuously true**, and the file it was meant to cover is
the one that executes the `clair-puct` leg — **93% of the run's cost, unwitnessed.** The corrected
instrument set:

```
scripts/tiletie/run_tiletie.py
scripts/measurement_infra/oracle_score_pilot.py      <-- corrected path
scripts/tiletie/tier1_rust_leg.py
src/  engine/  rust/
```

**Amendment 3 — the witness must cover the WORKING TREE, not only the committed tree.** A
`git diff A..B` compares commits and is **blind to uncommitted dirt in the instrument scripts**.
`INSTRUMENT_IDENTITY.json` must therefore record **both**: the committed diff (re-derivable — both
full shas plus the path list, so a reader can **re-run it**, a recipe rather than a claim) **and**
`git status --porcelain` scoped to the same paths, captured at witness time on each box.

**Completeness note, and it is the reassuring half:** this witness covers the **interpreted** half
of the instrument; D3's `execution.carc_rs_build` IDENTITY_REQUIRED already covers the **compiled**
half (equal across all chunks). Together they close both halves — which is why the enumerated
licence is safe rather than merely convenient.

### D4.12 RULING (c) — the `-dirty` suffix

Old legs recorded `58c2b539-dirty`, new will record `4b24f512-dirty`.

**Rule: match the licence on the BASE REV (sha prefix), and require, per chunk,
`preflight.checks.git_clean.ok == true`.**

- **Not exact-string matching including the suffix**: if any chunk happened to record a clean
  `code_rev` with no suffix, an exact-string licence would **refuse a healthy chunk** — a
  false-refusal of the class this campaign keeps generating.
- **Not bare suffix-stripping either**: stripping alone would silently accept a chunk whose
  *instrument* was dirty. The scoped assertion is the one with semantics —
  `run_tiletie.check_git_clean` computes `dirty` over **`src/carcassonne_ai/` and `engine/`** and
  sets `ok = not dirty`. Requiring `ok == true` per chunk checks the thing the suffix only gestures
  at, and checks it better.
- ⚠️ **Named residual:** `git_clean.ok`'s scope is `src/carcassonne_ai/` + `engine/` **only** — it
  does not cover `rust/` or `scripts/tiletie/`. `rust/` is covered by D3's `carc_rs_build`
  equality; `scripts/tiletie/` is covered by Amendment 3's porcelain capture. **The three together
  are what make the suffix safely ignorable; any one of them dropped and it is not.**

### D4.13 RULING — `carc_rs_build` across tranches: **ACCEPTED**, and it closes a hole D3 opened

The builder was **right to refuse to self-extend** the licence to a field D3 made
IDENTITY_REQUIRED. Ruling it is mine.

**The load-bearing fact, verified this session against the emitter** (`rust_agent.py:352-395`),
and it is stronger than reported: `carc_rs_build_id()` builds `carc_rs-<version>+<rev12>+rustc<tc>`
where `rev` comes from **`git rev-parse HEAD` at stamp time** — *"a property of the repo when the
process started, NOT of the compiled artifact."* **The emitter's own docstring states the
taxonomy this ruling relies on**, so this is the field's designed meaning, not a reinterpretation:

> *"A `G-TOOL` gate is an EQUALITY check between two boxes' stamps, and the compiled `.so` is not
> reproducible across machines… **The box-local staleness question is answered separately, by
> `carc_rs_binary_sha`** plus the per-host positive control, **which is the only thing that can
> prove the installed wheel actually carries the surface under test.**"

⇒ `carc_rs_build` = **cross-host source-rev** witness. `carc_rs_binary_sha` = **within-box
staleness/rebuild** witness. Across tranches HEAD moved (the D4 fixes) and the stamp followed;
**the `.so` was not rebuilt.**

⭐ **The self-correction, which I state because it is a defect in my own D3 ruling.** At a single
rev, `carc_rs_build` **cannot detect a mid-run rebuild** — same HEAD ⇒ same stamp, different `.so`.
D3 classified `carc_rs_binary_sha` **PER_CHUNK** (recorded, *not compared*), so **D3 as ruled left
the within-box staleness case unchecked entirely**, while I described `carc_rs_build` as though it
covered it. Conjunct (ii) below does not merely license this extension — **it closes that hole**,
and it therefore becomes a **standing requirement** (the D3.2 amendment above), whether or not the
tranche licence is ever exercised. As the coordinator observed, this makes the merge **strictly
stronger than any single-rev run**, which never checks `.so` constancy at all.

**The conjunction — accept a `carc_rs_build` divergence across tranches IFF ALL of:**

| # | conjunct | failure ⇒ |
|---|---|---|
| **(i)** | Parse `carc_rs-<version>+<rev12>+rustc<toolchain>`. **`<version>` and `rustc<toolchain>` byte-equal** across all chunks; **only `<rev12>` may differ**, and every distinct `<rev12>` is a **12-char prefix of one of the licensed full revs**. | R1 or R3 |
| **(ii)** | **Per box**, `carc_rs_binary_sha` is **CONSTANT across that box's chunks spanning BOTH tranches** (local `a4318fd59d9d8349` in both; laptop `8ae0b98427debb2e` in both). **Evaluated from the chunk manifests at merge time — an ACTIVE conjunct, not an assumption.** ⚠️ **Compared WITHIN a host only, never across** — JCZ §0.F.2c is untouched. | R2 |
| **(iii)** | `INSTRUMENT_IDENTITY.json` includes **`rust/`** in its empty-diff scope *and* its porcelain capture shows `rust/` clean. | R4 |
| **(iv)** | **Within each tranche**, `carc_rs_build` equal across boxes — D3's original check, preserved intact. ⚠️ **Vacuous for single-box legs** (the tier1 ARB legs are all-local): it must be **reported as vacuous, never as passed** — a vacuous pass read as evidence is how a witness stops witnessing. | R3 |

⚠️ **A width trap, called out because this campaign's failures are spelling failures.** D4.11's
licence matches `code_rev` on the **7-char short form**; `carc_rs_build` carries a **fixed 12-char
slice** of the full commit — deliberately, because `--short` length is `core.abbrev` and therefore
**per box** (the docstring records `cf51bf17` locally vs `cf51bf176b` on the laptop for one
commit). **Compare 12-char prefixes of the licensed 40-char shas here; do not reuse the 7-char
comparison.** Same underlying sha, three different widths in play.

**Second address, same reading:** **`preflight.wheel.carc_rs_build`** on the tier1 rust ARB legs —
same field, different emitter schema. Identical conjunction, with (iv) vacuous per above, so
**(ii) carries the whole weight there.**

**Refusal messages — three distinguished, plus one new:**

- **`R1 CARC_RS_BUILD_UNLICENSED_REV`** — a `<rev12>` that is not a 12-prefix of a licensed rev.
  Print the offending value, its parsed fragments, the licensed pair, and the leg/chunk.
- **`R2 CARC_RS_BINARY_SHA_MOVED_WITHIN_BOX`** — (ii) fails. Print the box, every distinct sha, the
  chunks each appeared in, and the meaning verbatim: *"the installed wheel changed under one box
  mid-run — the `.so` that executed tranche 1 is not the `.so` that executed tranche 2."*
- **`R3 CARC_RS_BUILD_VERSION_OR_TOOLCHAIN_DIFFERS`** — (i)'s byte-equality on the non-rev
  components fails, or (iv) fails within a tranche. **This is D3's original message and is never
  licensed**: print both full values with the differing component marked.
- **`R4 INSTRUMENT_IDENTITY_RUST_SCOPE`** — (iii) fails (`rust/` absent from the diff scope, or
  dirty in the porcelain capture).

Any **other** key under `execution` / `preflight.wheel` that differs keeps the **unchanged RAISE
default** (D3). **This ruling licenses one field, under four conjuncts, for one enumerated rev
pair; it opens nothing else.**

### D4.14 RULING — `preflight.checks`, ruled EXHAUSTIVELY; and the classification sweep, COMMISSIONED

**`preflight.checks` is a CLOSED SET of seven sub-keys** — verified against the emitter
(`run_tiletie.preflight()`): `gate`, `leaf_hash`, `process_census`, `git_clean`, `positions`, `m`,
`arb_backend`. So I rule all seven, not only the five that diverged: this block becomes
**closed-by-enumeration today**, which is the sweep's goal applied to one block.

| sub-key | class | grounds |
|---|---|---|
| `leaf_hash` | **IDENTITY_REQUIRED** *(unchanged — do not touch)* | ⚠️ **GATE-ADDRESSED**: `G-LEAF` reads `preflight.checks.leaf_hash.ok`. Constant across chunks; passes silently today. **May not be reclassified without a ruling.** |
| `m` | **IDENTITY_REQUIRED** *(unchanged)* | `M` is a design constant per stratum (128 / 32), not chunk-scoped. Constant today; passes silently. |
| `process_census` | **PER_CHUNK** | Timestamped telemetry — `ps` + loadavg at launch, **differs by construction on every invocation, even for byte-identical re-runs.** ⭐ **The emitter itself classifies it**: `ok` is computed `for name, c in checks.items() if name != "process_census"` — *"the process census is informational and never gates."* |
| `gate` | **PER_CHUNK** | chunk-scoped `--gate-out` path. |
| `positions` | **PER_CHUNK** | chunk-scoped `--positions-dir`. ⚠️ **Sweep item, not assumed away:** if this block carries a *count* sub-field, that count is a **completeness quantity** and must not be silently PER_CHUNK'd — D4's whole lesson was a completeness count nobody aggregated. The sweep enumerates its sub-keys and says which. |
| `git_clean` | **PER_CHUNK (recorded) + LICENCE-GOVERNED (asserted)** | See the interaction below — it is **not** double-ruled. |
| `arb_backend` | **JUDGE_SCOPED_IDENTITY** | equal across all chunks **within a judge**; cross-judge comparison **not performed** — `clair-puct` records the inert-flag note, `tier1-greedy` the wheel block, so the two shapes are not comparable and an equality between them would be meaningless rather than false. |

**Two traps in that table, both worth stating explicitly.**

⚠️ **`preflight.checks.arb_backend` is NOT the field `G-BACKEND` reads.** `G-BACKEND` reads
**top-level** `RUN_MANIFEST::arb_backend` — the resolved string — while `preflight.checks.arb_backend`
is `check_arb_backend()`'s **result dict**. Same name, two depths, different objects. **Classifying
the preflight one JUDGE_SCOPED must not relax the top-level one, which stays IDENTITY_REQUIRED and
gate-addressed.**

⚠️ **Judge-scoped constancy must be ASSERTED, not assumed.** The evidence reports the *axis* of
variation as the judge; it does not by itself prove constancy *within* a judge. So the class is an
**active check** — equal across every chunk of the same judge, evaluated at merge time, refusing on
a within-judge divergence — the same discipline that turned D4.13's conjunct (ii) from an
assumption into a check.

**How the `git_clean` merge rule and the D4.12 licence interact (so it is ruled once, not twice).**
They govern different verbs: **the merge rule says how the field is CARRIED; the licence says what
must be TRUE.**

- **Merge rule (PER_CHUNK):** each chunk's `{ok, git_rev, dirty_paths}` is recorded per chunk. It
  raises on nothing by itself, because `git_rev` legitimately differs across the licensed tranche
  pair and `dirty_paths` is telemetry.
- **D4.12 licence (assertion):** consumes `preflight.checks.git_clean.git_rev` for the **base-rev**
  match against the enumerated pair, and asserts `preflight.checks.git_clean.ok == true` **on every
  chunk**. A failure here refuses under the licence's own message, not under a merge-rule message.

⇒ **One field, one recording rule, one assertion, no overlap.** The merge never independently
compares `git_rev` across chunks — that comparison belongs to the licence, and duplicating it in
the merge rule would produce a second, differently-worded refusal for one condition.

**Everything else under `preflight.checks`** — and every dotted path already IDENTITY_REQUIRED —
**keeps the fail-closed default.**

### D4.14b COMMISSIONED — the classification sweep: exhaustive-by-ENUMERATION, not by crash

**The executor's point is correct and is the real finding here: this is the THIRD telemetry-shaped
field discovered by refusal** (`execution` → D3, `git_rev`/`code_rev` → D4.11, `preflight.checks` →
here). Three refusals is a pattern, and the pattern says the classification is being built by
crashing into it. **Commissioned**, to be presented for sign-off **in the same round**:

1. **Enumerate from the REAL artifacts, not from reading code** — the full key set of the
   `RUN_MANIFEST` (all 32 sources) **and** the per-leg manifests from **BOTH emitters**
   (`run_tiletie`/`oracle_score_pilot` and `tier1_rust_leg` — different schemas; `execution` vs
   `preflight.wheel` is exactly that difference, and reading one would have missed the other).
2. **Classify EVERY remaining unclassified key**, one of: `IDENTITY_REQUIRED` · `AGGREGATE_SUM` ·
   `PER_CHUNK` · `JUDGE_SCOPED_IDENTITY` · `LICENCE_GOVERNED` · `TELEMETRY` (PER_CHUNK, differs by
   construction).
3. **Record the OBSERVED divergence axis per key** — none / box / chunk / judge / invocation / rev
   — **evidenced from the 32 artifacts**, so a classification is a measurement, not an opinion.
4. ⭐ **Flag every GATE-ADDRESSED key by dotted path, cross-checked against the READ_RULE's address
   list — and assert the converse: that every gate-addressed dotted path in the READ_RULE EXISTS in
   the enumerated schema.** This is the check that would have caught `G-SALT`'s primary being
   audited at neither pass, and the missing `RUN_MANIFEST` fixture. Gate-addressed keys are
   IDENTITY_REQUIRED and may not be reclassified without a ruling.
5. **Deliver it as a RE-RUNNABLE script**, not a one-time table, so the next schema change diffs
   mechanically instead of refusing at merge time.

**After the sweep, the fail-closed default changes meaning, and that is the point:** an
unclassified-key raise no longer means *"a field nobody thought about"* — it means **a SCHEMA
CHANGE: a new emitter field**. **That is exactly what should raise**, and it is the first time in
this campaign that the default will be doing that job rather than absorbing the backlog of fields
never enumerated.

### D4.15 SIGN-OFF — the classification sweep (builder `684647f9` on `206e259f`)

**SIGNED OFF. Both findings confirmed, both `(a)` and `(b)` confirmed, nothing rejected.** Verified
against the artifacts and the code, not the summary: 355 artifacts, 134 rows, 0 UNCLASSIFIED,
0 gate-addressed paths missing.

**Finding 1 — the third `carc_rs_build` address: CONFIRMED as a NARROWING.** I checked the mask
itself rather than the characterization. `_mask_licensed_build` replaces **only the key literally
named `carc_rs_build`, and only when its value is a string**, recursing through dicts and lists;
**everything else in the judge-scoped block — `carc_rs_binary_sha`, the version and toolchain
components, the wheel path — remains under `preflight.checks.arb_backend`'s judge-scoped
equality.** The extracted value is returned and routed through D4.13's four conjuncts exactly once,
with `BUILD_LICENSED_PATHS` enumerating all three addresses. **The refusal is narrowed by exactly
one field; the licence is not widened.** ⭐ And the sweep found this by **enumeration rather than by
a merge refusal** — nested inside another classified block, invisible to top-level classification.
That is the sweep doing precisely the job it was commissioned for, on its first outing.

> **Recommended hardening, explicitly NON-BLOCKING:** the mask matches by **key name**, while the
> licence matches by **dotted path** — two different scopes for one field. Assert that the set of
> masked occurrences **equals** the set of enumerated licensed paths present in that manifest, so
> the two cannot silently diverge if a fourth occurrence ever appears. It is non-blocking because
> the sweep's freshness test is wired to `merge_legs` and a fourth occurrence is a **schema
> change**, which now raises — but the assertion is one line and closes it definitively.

**Finding 2 — the carry-forward rule: CONFIRMED as the correct GENERAL behaviour, NOT an
enumerated preserve-list.** Grounds, in order:

1. ⭐ **An enumerated preserve-list has the exact failure mode this campaign spent three rulings
   fixing** — you enumerate what you have already crashed into. `c_remeasure` would have been on
   the list only because it nearly broke; the next such key would not be.
2. **The merge has no mandate to delete what it does not produce.** Its job is to *produce* merged
   fields, not to own the file.
3. **The asymmetry of harm favours carry-forward**: deleting a gate-addressed block makes the gate
   read **ABSENT ⇒ FAIL**, discovered only at read-out, after the spend.

Verified in code: **top-level only**, carried **verbatim**, *"never merged into and never
rewritten"*, and recorded in `merge.preserved_from_existing` (live: `['c_remeasure','stub']`).
Top-level-only is right — nested carry-forward could resurrect a deleted sub-key inside a block the
merge *does* produce, which would be worse than either failure it prevents.

> ⚠️ **Named residual — STALE PRESERVATION.** A key whose producer stops writing it is preserved
> forever **from the merge's own prior output**, self-perpetuating and invisible. The guard already
> exists: the sweep's freshness test surfaces a disappeared key as a schema change.
> **Recommended hardening, non-blocking:** record the source file's **sha256 + mtime** per preserved
> key, so a preserved block's *age* is visible rather than inferred.

**(a) The 7/7 implementation matches D4.14 — verified row by row**, and both traps are honored:
top-level `arb_backend` is **IDENTITY_REQUIRED, flagged gate-addressed** (row 21) and untouched;
`preflight.checks.arb_backend` is JUDGE_SCOPED_IDENTITY *"equal WITHIN a judge, **ACTIVELY
checked**; cross-judge not compared"* (row 39). `git_clean` reads *"carried per chunk; ASSERTED by
the D4.12 licence (**ruled once, not twice**)"* — the interaction as ruled. The dry-check result is
the **D4.13 trap honored**: `clair-puct` conjunct (iv) PASSED with chunk14 landed, **tier1 reported
VACUOUS** both tranches — *vacuous reported as vacuous, never as passed*.

- **`TELEMETRY` as a distinct class label for `process_census` is ACCEPTED and is an improvement**
  on my "PER_CHUNK (telemetry)": it distinguishes *recorded per chunk because chunk-scoped* from
  *recorded per chunk because it differs by construction*.
- ✅ **My D4.14 `positions` flag CLOSES, with the reason rather than by assumption.**
  `check_positions` returns `n_leg_files` — a **file** count, not a **rid** count. It could not
  have caught D4: a leg file can exist and contain 793 of 1,344 rids. The rid-coverage quantity —
  the one D4 was actually about — is carried by D4.3's cross-layer invariant and the merge's own
  completeness check (**1344/1344, every leg, both judges**). PER_CHUNK is correct for it.
- **The builder generalised D4.11 Amendment 2 better than I specified it**: rather than only
  correcting the mis-spelled pilot path, the witness now **asserts every instrument path EXISTS at
  both revs** — the generalisable form of the lesson, and it would catch the next vacuous-path
  witness rather than that one.

**(b) Closed-by-enumeration HOLDS, so the D4.14 meaning-change GOES LIVE.** 0 UNCLASSIFIED,
0 gate-addressed paths missing, every classification carrying its observed divergence axis, and the
generator re-runnable with a freshness test wired to `merge_legs`. **From here, an unclassified-key
raise means a SCHEMA CHANGE — a new emitter field — which is exactly what should raise.** The
default has stopped absorbing a backlog and started doing its job.

> **SIGNATURE: the classification layer is complete and signed. The pipeline may rerun.** The two
> hardenings above are follow-ups, **not conditions** — neither blocks the verdict.

### D4.16 RULING — the two Reading-A consequences, and two execution notes

The merge **SUCCEEDED** (1344/1344 every leg both judges; licence self-rederived; `c_remeasure`
preserved). Both blockers are **execution-layer W-code fixes: no gate, bar, address, branch or
statistic of the R4 pair changes.** Under Reading A the rung-3 branch table is simply **never
evaluated**, which the owner's ruling already settled.

**⭐ Both blockers are governed by a distinction this log already drew, and I anchor them there
rather than invent new semantics** — `ADJUDICATION_R4_GATES.md`, owner-ruling section:

> *"§2a spells out what to say when `n₂ = 0` — 'the J question was **not bought**' — but that
> clause is conditioned on the owner's pre-committed floor, and **this run bought rung 3 at
> `n₂ = 1100` and then lost it to a void.** The read-out must therefore say the J question was
> **bought and lost to a stratum void**: not 'not bought', not 'answered', not 'inconclusive'."*

**`FLOORS.json::rung3_bought = true` is CORRECT and stays frozen** (sha `7771435e`). It is a true
statement about what was **purchased**; flipping it to `false` would both falsify the record and
make the READOUT emit the one phrase expressly forbidden above. **The executor was right to refuse
to touch it.**

**BLOCKER 1 — the analyzer's void-stratum guard. CONFIRMED as proposed, with one hardening.**

The READOUT emits a rung-3 block carrying:

| field | value |
|---|---|
| `status` | **`VOID_S2`** — ⚠️ a token that **must not collide with any rung-3 branch token** (`X-CONFIRMED` / `X-ABOVE` / `X-PARTIAL` / `X-BELOW` / `X-FREE` / `X-INCONCLUSIVE`). **No X-token may appear anywhere in the READOUT.** |
| `bought` | `true`, with `n₂ = 1100` from `FLOORS.json` — truthful about what was purchased |
| `estimand_read` | `false` |
| `reason` | verbatim: *stratum voided at `G-DISJOINT` per `PREREG_FAILURE_S2.md` and `ADJUDICATION_R4_GATES.md` Reading A* |
| `forbidden_readings` | inline: **not "not bought", not "answered", not "inconclusive", not any X-branch** |
| `obligation_inherited_by` | `rung3_r5` — **including `I7`'s dedupe-partition conditional, which stays UNMEASURED** because W9/`D-DRAW` was skipped as moot |

⭐ **HARDENING, and it is the D4 lesson applied: absence must NEVER be read as a void.** The guard
fires **only** on a **positive witness** — `GATE_DISJOINT.json::digest_exclusions.<s2>.void == true`
— **conjoined** with the absence of S2 inputs. **If S2 inputs are absent and that witness is NOT
true, the analyzer must RAISE, not emit `VOID_S2`.** Missing inputs are exactly what D4 was: an
assembly defect wearing the shape of a decision. A guard keyed on absence alone would have silently
blessed D4's 551 missing rids.

**The S1-side rung-3 riders** (the ≈244-capped-ply replication rider, the interaction rider) were
computed and are real S1 measurements, so **report them** — suppressing measured quantities is
worse — but under a heading that states they **adjudicate nothing and, with rung 3 void, have no
primary to ride on**, and that **no rung-3 branch may be inferred from them.** That inference is
the live risk of reporting them at all, so the prohibition travels with the number.

**BLOCKER 2 — S2-addressed conjuncts. CONFIRMED, and it needs a HARNESS SCOPE, not a reading.**

`G-SALT`'s S2 conjunct addresses `RUN_MANIFEST_S2.json::world_seed_salt`, which **cannot exist**
under Reading A. Its S1 primary **RESOLVED**. The three candidate treatments and why only one is
right: **FAIL** is false (nothing failed — a pre-registered rule voided the stratum); **PASS** is a
lie (nothing was checked); **silent absence** violates §1.3's `resolved_at` duty.
⇒ **`VOID (stratum) — not evaluated`**, citing the same positive witness.

**This must be a harness scope in `acceptance_widening`, not a documented reading of the existing
output.** A prose reading would require a human to translate `UNRESOLVED` into *"void, correctly"*
— which is a **carve-out by interpretation**, and R4.5 already ruled that *carve-outs are how this
class recurs* (that is why `STAGE1B_LADDER.json` was copied rather than address-excepted). The
scope must be **derived from the artifact, never a human-passed flag** — a flag is silenceable, and
`ABSENT IS FAIL` may not become silenceable. **Scope precisely: only addresses bearing the S2
stratum marker, and only when the void witness is present.** `ABSENT IS FAIL` is untouched for S1
and for every non-S2 address.

**EXECUTION NOTE 3 — the briefed step order was circular; the executor's correction is right.**
`post`-before-`analyze` cannot work: **7 of 8** unresolved post-gates address
`verdicts/READOUT.json`, **which analysis produces**. Correct order is **`analyze` THEN `post`**.
⭐ **This is the THIRD instance of one class** — an audit pass demanded an address its own position
in the sequence made impossible (`G-SALT` at 4b, the 4a corpus-free contradiction, now this) — and
it is **already fixed prospectively** by `rung3_r5/DESIGN.md` §R5-6.1's existence-time markers, in
which `READOUT::*` is `[post-scoring]`: audited statically pre-commit, live at read-out, never in
between. Recorded here as the third data point for a fix already written.

**EXECUTION NOTE 4 — the leg-manifest copy-back is WITHIN the pair's §9 sequence. CONFIRMED.**
24 manifests to `shared_run_r4/legs/s1/` (S2 skipped as void) is the specified population of the
**fallback** addresses that `G-SALT` / `G-M` / `G-BACKEND` / `G-PREFIX` read — DESIGN §4: *"the
driver's final phase **copies every leg `manifest.json` back** to `RUN/legs/…` — the address the
READ_RULE reads"*, and R4-0.5's builder-delta item 4. **Ordering requirement, stated because it is
load-bearing: the copy-back must PRECEDE the post-pass**, or those fallbacks resolve `UNRESOLVED`
for a reason that is pure sequencing. Skipping S2 is correct — no S2 legs exist to copy.

> **All four are execution-layer. Nothing in the frozen pair moves. This is the last ruling before
> the branch table.**

### D4.17 SIGN-OFF — the D4.16 implementation (builder `499922fb` on `d56add33`)

**BOTH SIGNED.** Extension 1 confirmed as the general rule I already wrote, not a new exception;
extension 2 resolved by taking the **stricter** option.

**Extension 1 — `G-COMPLETE`'s S2 conjunct: CONFIRMED, and it is Reading A applied, not a widening.**

I checked this against the temptation, because *"the gate that blocks the verdict gets void-scoped"*
is precisely the shape a bad ruling would take. It survives on four grounds:

1. **It is the rule D4.16 already stated, applied to a conjunct I failed to enumerate.** Blocker 2
   ruled *"only addresses bearing the S2 stratum marker, and only when the void witness is
   present."* `G-COMPLETE`'s `s2_n` conjunct bears the S2 marker. I scoped my ruling to the
   **acceptance harness** and the rung-3 block; `G-COMPLETE` is evaluated by the **analyzer**, so
   the builder is right that I did not rule it and right that the mechanism is identical.
2. **The adjudication's own logic:** *"S2 gates bind rung 3 only."* The `s2_n` conjunct binds rung
   3; rung 3 is not adjudicated (`VOID_S2`). It governs a rung that is not being read — the
   identical position `G-SALT`'s S2 conjunct occupies.
3. **Consistency forbids the alternative.** Ruling `G-SALT`'s S2 conjunct void-scoped and
   `G-COMPLETE`'s fatal would be incoherent: same stratum, same witness, same reason.
4. **Otherwise the owner's ruling is self-defeating** — S2's floor evaluates against the empty
   voided stratum, `gates_ok` goes false, and the whole read-out including **rung 2** collapses to
   `W-UNREADABLE`, making the outcome Reading A specifies **unreachable**. A reading that annuls
   the ruling it implements is the wrong reading.

⚠️ **Two conditions, because uniformity is what separates this from gate-shopping:**

- **The scope is UNIFORM, not selective.** *Every* S2-addressed conjunct is void-scoped by the
  witness — **not only the ones that block.** If a future S2-addressed conjunct would have
  *passed*, it is **still** reported `VOID (stratum) — not evaluated`; a void-scope applied only
  where it helps is gate-shopping wearing this ruling's clothes.
- **The void-scope may NOT leak to S1.** `G-COMPLETE`'s S1 conjunct is evaluated normally and is
  what binds rung 2 — **1,344 ≥ 1,283 on real scored data**, which is the whole of D4's repair.

**Displayed, never dropped:** the void-scoped conjunct appears in the READOUT as
`s2_conjunct: "VOID (stratum) — not evaluated"` with the witness cited, and `gates_ok` is computed
over the **evaluated** conjuncts. The read-out stays truthful about what was checked versus what
was not. `rung3_bought` stays `true`.

**Extension 2 — the X-token enumeration: I take OPTION (b), DROP THE ENUMERATION.**

Not the strip-one-line carve-out. Reasons:

1. **The rule's value is that it is UNCONDITIONAL.** "Zero occurrences" is checkable by anyone with
   `grep`, including tools nobody has written yet. A rule with a carve-out is one you must know the
   carve-out to apply — and the actual risk is a **naive downstream grep** finding an X-token in
   the READOUT, which option (a) leaves fully live.
2. **A special-cased scanner is a scanner with a blind spot**, and this campaign's failures have
   been blind spots in checks. Strip-one-line also breaks silently if the line's format ever moves.
3. **The prohibition does not need the tokens to be effective.** *"No branch token from the rung-3
   table appears here; that table was never evaluated"* is fully informative, and the six tokens
   are enumerated in the READ_RULE, which is where a reader looks for them.

⚠️ **Keep the PROSE prohibitions** — *not "not bought", not "answered", not "inconclusive"* — and
drop only the six tokens. Those phrases are not tokens, they do not trip a token scan, and they
carry the distinction the owner-ruling section drew. **Zero token occurrences, prohibition intact.**

**The two fixes the rule forced: both correct, and neither skips a frozen requirement.**
The degenerate S2 `j_rider` slice → a void stub (its `xfree_window` note named `X-FREE`), and the
S1 rider's `xfree_window` dropped as *"an attainability annotation for a never-evaluated branch has
no referent."* ⭐ **That reasoning is right and worth affirming explicitly**, because it could
otherwise look like a frozen mandatory-print was quietly skipped: READ_RULE §5's mandatory prints —
including the `X-FREE` attainability window — are required **"on every X-branch"**. **No X-branch
fires.** `VOID_S2` is not an X-branch, so the obligation is **never triggered**, and printing an
attainability window for a branch that was never in play would be both meaningless and an
invitation to infer that `X-FREE` was considered.

> **BOTH SIGNED. Nothing rejected. The pipeline may rerun — `analyze` THEN `post` — and the branch
> table may fire on the real data.**

### D4.18 RULING — failed clair-puct records: whole-rid drop, and NO new numeric bound

*(Numbered D4.18: D4.17 is the implementation sign-off.)*

6 `clair-puct` records `ok:False` across **4 distinct rids**; `tier1-greedy` zero. All six carry
the identical **`WindowTruncationError`** — PUCT reached a node where all 4 legal actions fell
outside the 25-wide encoding window (late game, 70 tiles placed, extent `[0,10,2,19]`, depth 5).
**This is the known class studied in `measurement/window_truncation_20260813/`: an instrument
limitation of the encoder at extreme board extents, not data corruption.**

**(a) POLICY — WHOLE-RID DROP. Confirmed, and it is not a new policy: it is what `G-ARMS` already
implies.**

**First, as instructed, I checked the pair for an existing clause. There is none** — the only
"excluded" machinery is the digest-collision apparatus (R4-3), which is about disjointness, not
scoring failure. Two existing clauses govern instead, and the proposal maps onto them:

- **`G-ARMS`**: *"every full-set arm scored on all `M` worlds — per-arm, not per-ply;
  `n_arms_complete == n_arms`; `include_partial == false`."* ⇒ **a rid with a valueless arm is not
  analysable at all.** Whole-rid drop is the consequence of that conjunct, not an addition to it.
  Dropping from **both** judges follows too: `tier1-greedy` succeeded on these rids, but the paired
  per-position contrast needs the IF side, so a half-present rid is not a contrast.
- **`G-COMPLETE`**: `s1_n ≥ ⌈0.95 × n₁⌉ = 1,283`. **That 5% headroom is the closest thing the pair
  has to a pre-registered attrition tolerance**, and the post-drop count clears it with margin:
  **1,340 ≥ 1,283**.

**⛔ I DECLINE to enact the proposed `⌈0.5% × stratum⌉ = 7` refuse-bound, and the reason is the
principle this whole campaign runs on: we already know the value.** The attrition is 4 rids /
0.30%. **A bar chosen now is chosen with knowledge of the datum it grades — that is not a bar**,
even a generous one that the data comfortably clears. Enacting it would look like rigour while
being its opposite, and it would set the precedent that a bound may be authored after its
measurement.

**What governs instead, in place of a post-hoc number:**

1. **The pair's own floor**, which was set before the data: `1,340 ≥ 1,283`. It clears by 57.
2. ⭐ **A QUALITATIVE escalation trigger, which does not grade the observed value:** **any failed
   record whose diagnostic class is not the known `WindowTruncationError` class ⇒ RAISE and
   escalate, regardless of count.** A novel failure class is a different question from a studied
   instrument limitation, and count is the wrong axis for it. This is safe to add post-hoc
   precisely because it is not a threshold on the number we can already see.
3. **A pre-registered failed-record bound is carried to `rung3_r5`** — authored **before** its
   data, which is the only way a bound of that shape is worth anything.

**(b) HOW THE DROP READS INTO THE GATES — consumed ONCE, by `G-COMPLETE` alone.**

| gate | effect | why |
|---|---|---|
| **`G-COMPLETE`** | **consumes it**: evaluated on the **post-drop analysed count**, `1,340` vs floor `1,283` | the same "counts evaluated **after** exclusions" discipline R4 §2a already applies to digest exclusions |
| **`G-CRN`** | **unaffected** | its conjunct is `n_crn_verified == n_ok`, and both sides are computed **over `ok` records only**; a failed record lives in `n_failed`, outside both. It never enters the equality, so there is nothing to double-count |
| **`G-ARMS`** | **unaffected** | a whole-dropped rid never enters the arm accounting; the conjunct is evaluated over surviving rids |

⇒ **One consumption, no double-counting.** The attrition reduces exactly one denominator — the one
whose floor was pre-registered for it.

**(c) THE SELECTION-EFFECT SENTENCE, for the READOUT verbatim:**

> **The 4 dropped rids are not a random subsample.** `WindowTruncationError` fires at extreme board
> extents, so the dropped set is correlated with board geometry — late-game, large-extent positions.
> At **4 / 1,344 = 0.30%** the maximum arithmetic influence on the primary is bounded by
> `(4/1,340)·|Δ|_max ≈ 0.003·|Δ|_max`, a fraction of `se ≈ 0.02` for any plausible `|Δ|_max`; the
> point of this note is that the correlation is **disclosed rather than argued away**, so it is not
> rediscovered later as a gotcha. Diagnostic class and study:
> `measurement/window_truncation_20260813/`.

**(d) THE STALE ARTIFACTS — moved aside, never overwritten. Confirmed.**

The 08:13 mispathed `READOUT`/`SEALED` artifacts from the empty-rowset run are
**worthless-by-construction** and must be **renamed** (e.g. `.invalid-empty-rowset`) **before** the
clean run — never merely overwritten. Same discipline as `CORPUS_UNION.defective_r4.5.json`
(§D4.7): **a superseded artifact is evidence and stays readable; what must be impossible is
mistaking it for a verdict.** The suffix must make invalidity obvious on sight, and the move must
be **named in the READOUT's provenance** so the gap in the record is documented rather than silent.
*Recommended, non-blocking:* have the analyzer **refuse to overwrite an existing `READOUT.json`**,
so the move-aside is enforced rather than remembered.

**BUILDER SPEC**

1. `build_rows:303` — **check `ok` before dereferencing `ref["values_a"]`**; never crash on a
   failed record.
2. Collect `failed_rids` = every rid with **any** `ok:False` record in **either** judge; **drop
   those rids from both judges' row sets before any contrast is computed** (complete-case on
   intact rids).
3. **Typed accounting in the READOUT**: `n_failed_rids`, and per rid `{judge, legs, diagnostic_class}`,
   plus the pointer to `measurement/window_truncation_20260813/`. Printed whether or not any
   failure occurred.
4. `G-COMPLETE` reads the **post-drop** analysed count; `G-CRN` and `G-ARMS` are untouched (b).
5. **RAISE** — do not drop — if any failed record's diagnostic class is not the known
   `WindowTruncationError` class.
6. Emit the (c) sentence in the READOUT.
7. Move the stale 08:13 artifacts aside before the run; record the move in provenance.

### D4.19 RULING — READOUT-internal S2 keys void-scope too; the rule stated GENERALLY this time

**CONFIRMED.** `widening.j_rider.s2.*` bears the S2 stratum marker, so it falls under the rule
D4.16 blocker 2 already stated — *"only addresses bearing the S2 stratum marker, and only when the
void witness is present."* The artifact is already honest
(`j_rider.s2 = {status: VOID_S2, void: true, n_capped: 0}`); it is the **harness's address
resolution** that had not been told.

⭐ **This is the THIRD time I have stated a general rule and scoped my implementation guidance
narrowly** (D4.16 → artifact paths; D4.17 ext 1 → `G-COMPLETE`'s analyzer-side conjunct; now →
READOUT-internal keys). Rather than enumerate a third instance, **the rule is restated in its
general form so it stops requiring per-instance rulings:**

> **ANY address bearing the S2 stratum marker void-scopes under the positive witness — whether it
> is an artifact PATH (`RUN_MANIFEST_S2.json`, `per_position_s2.jsonl`), an analyzer-side CONJUNCT
> (`G-COMPLETE`'s `s2_n`), or a KEY PATH INSIDE an artifact (`widening.j_rider.s2.*`). The two
> conditions travel with it unchanged: UNIFORM across all S2 addresses (not only blocking ones),
> and NO LEAK TO S1.**

**The dual-witness refinement: ACCEPTED, and it is the right shape.** Scope on the artifact's own
`widening.j_rider.s2.void == true` **cross-checked against** `GATE_DISJOINT`'s
`digest_exclusions.<s2>.void == true` — **both must agree; disagreement RAISES.** This is the same
"two independent things must agree" form as D4.11's licence (code-resident pair **and** witness
file), and it closes both one-sided failures:

- **gate says void, READOUT does not** ⇒ the analyzer ignored the void — RAISE.
- **READOUT says void, gate does not** ⇒ the analyzer **self-declared** a void with no gate basis
  — RAISE. This is D4.16's *"absence must never be read as a void"* hardening, applied one layer
  in: a component may not vouch for itself.

⚠️ **THE OVER-MATCH TRAP, named because it is the failure this campaign keeps producing.** The
marker is the **exact path segment `.s2.`** (or a declared S2-key list) — **never a prefix match on
`j_rider.*` or a substring match on `s2`.** Three sibling addresses live under `j_rider.` and
**must remain fully in force**:

| address | status | why |
|---|---|---|
| `widening.j_rider.s1_replication.*` | **NOT void-scoped** | an **S1** quantity — the ≈244-capped-ply replication rider |
| `widening.j_rider.interaction.*` | **NOT void-scoped** | also **S1** (computed on S1 ∩ capped) |
| `widening.j_rider.d_draw.*` | **NOT void-scoped** | already governed by the **`allow_null` closed list** (§1.2) — `null` until W9 runs, with `d_draw_ran == false` as its witness. **Two different mechanisms; do not conflate them.** |

**§5 then resolves at primary**, reported `VOID (stratum) — not evaluated` with both witnesses
cited — **not** `resolved_at: <path>`, because nothing resolved and nothing was checked. Its
fallback (`per_position_s2.jsonl`) is already void-scoped as an artifact path, so **both** sides of
the row report VOID rather than one silently standing in for the other. **No rung-2 address is
touched**, which is the non-leak condition doing its work: rung 3's branch table is never
evaluated, so these six addresses feed nothing that fires.

**BUILDER SPEC (one paragraph).** In `acceptance_widening`, extend the existing S2 void-scope from
artifact paths to **address key-paths**: an address whose dotted path contains the exact segment
`.s2.` is scoped `VOID (stratum) — not evaluated` **iff** `GATE_DISJOINT.json::digest_exclusions.<s2>.void`
**and** `READOUT.json::widening.j_rider.s2.void` are **both** `true`; if exactly one is true,
**RAISE** with a message naming which side disagreed. Match on the exact segment, never a prefix or
substring — `s1_replication`, `interaction` and `d_draw` stay in force, and `d_draw`'s nullability
remains the `allow_null` mechanism, untouched. Report the scoped row with both witnesses cited and
no `resolved_at`. `ABSENT IS FAIL` is unchanged for every non-`.s2.` address, in this artifact and
every other.

**For the record, the verdict facts as reported** (adjudicated by the frozen branch table, not by
me): rung 2 **`W-RISING`** — `Δ(16→64) = 0.0670`, `se 0.0228`, `z 2.94`, `CI [0.0215, 0.1111]`,
against the committed floor `+0.040`; both conjuncts hold (`lower(CI) > 0` **and** `Δ ≥ 0.040`).
All seven analyzer gates PASS; `G-REPLICATE` in envelope at every rung with
`naive_envelope_caveat false`; rung 3 `VOID_S2`; 4 window-truncated rids dropped whole per D4.18.
⚠️ **One observation the read-out already owes**: the realized `se 0.0228` sits **above** the
pre-registered bracket `[0.0179, 0.0200]` — the design's variance model under-predicted modestly.
It changes no branch (the realized CI governs, and the floor is fixed), and READ_RULE §3 **already
requires** the realized CIs to be printed **beside the predicted brackets**, so this is a
requirement already in force rather than anything new.

## D5 — R5's two-rev merge licence, and the ORCHESTRATOR'S freeze violation

**Status: LICENCE RULED; binary-sha conjunct ruled CONDITIONALLY with the decision rule
pre-committed (§D5.2). Post-blind legality: merge layer only — no gate, bar, address, branch or
statistic of the R5 pair changes.**

### D5.1 The R5 licence — D4.11's mechanism, instantiated

`merge_legs` refused, and **it was right twice over**: its enumerated licence names **R4's** pair,
which R5 could never satisfy **even single-rev**. R5 needs its own.

**Realized pair, enumerated (full shas, per D4.13's width discipline):**

```
9bc2ab77...   chunks 1-2, 6-8   (laptop)
a5aa4a5e...   chunks 3-5        (local)
```

⚠️ **The `9bc2ab772` in the record is the SAME commit at 9-char abbrev** — `core.abbrev` is per
box, which is exactly why D4.13 fixed the comparison to **prefix-matching on the full sha** with a
minimum width, and why `carc_rs_build` carries a **fixed 12-char slice**. **Enumerate full shas;
match by prefix; never compare two abbreviations to each other.**

**Conditions, unchanged from D4.11:** the merge holds the enumerated pair in **code**; it requires
`RUN/INSTRUMENT_IDENTITY_R5.json` (both full shas, the instrument path list, the **re-derivable**
empty-diff recipe, and the per-box `git status --porcelain` scoped to those paths); and **the merge
re-derives the diff itself and refuses if non-empty.** The reported diff over the full instrument
list is **empty** — the changes (`analyze_b64_cell.py`, `run_cells.sh`, tests, `BAND_REGISTRY`,
`BAND_CLAIM`) are **nothing the scorer imports** — so the licence is genuinely available rather
than merely asserted. Completeness is perfect: **24 legs, 13,204 records, per-leg counts exactly
the pinned thinning ladder.**

### D5.2 ⚠️ Does binary-sha constancy bind across the rev split? **YES — and the decision rule is pre-committed HERE, before the evidence.**

**The rev licence does NOT absorb this question.** D4.11 licenses a **source-rev** split whose
**instrument diff is empty**. `carc_rs_binary_sha` constancy is a **separate, standing requirement**
(D3.2 as amended by D4.13 §ii) that exists precisely so a **compiled-artifact** change cannot ride
in on a source-rev licence. **A wheel rebuild is a different fact from a HEAD move.**

The B64 preflight rebuilt wheels ≈04:00; local's chunks 3-5 ran 23:45–05:16. **The rebuild may have
landed mid-chunk.** Ruling, fixed now so the builder's report resolves it mechanically:

| finding on local's per-chunk leg manifests | ruling |
|---|---|
| `carc_rs_binary_sha` **CONSTANT** across chunks 3-5 | D4.13 (ii) holds. **Licence applies; merge proceeds.** |
| `carc_rs_binary_sha` **CHANGED** mid-run | ⛔ **D4.13 (ii) FIRES FOR REAL — the standing requirement doing its job.** The `.so` that executed chunk 3 is not the one that executed chunk 5. **NOT licensable by the rev licence**, and **not** waved through on "the rust source diff is empty". **RAISE**, and require a **within-box D3-WITNESS**: re-score **N ≥ 16** chunk-3 rids on the **current** wheel and raw-f64 diff against their stored records. **100% bit-identical ⇒ merge proceeds with the witness recorded; any mismatch ⇒ rescore the affected chunks on one wheel.** |

⭐ **Why a witness rather than a refusal, and why not a waiver.** D3-WITNESS already measured
**23,184/23,184 bit-identical** values across two *different builds of the same source* on two
boxes — so same-source/different-build producing identical values has **precedent**. But that
precedent is **cross-box at one instant**, not **within-box across a rebuild**, and the honest move
is to **measure the case we have** rather than extend the one we measured. The instrument already
exists; it costs minutes.

**Builder action:** report `carc_rs_binary_sha` **per chunk** for local's chunks 3-5 (and the
laptop's, for completeness) **before** the merge is attempted.

### D5.3 ⛔ THE ORCHESTRATOR'S FREEZE VIOLATION — named plainly

**The B64 aggregator commit `a5aa4a5e` was merged to `main` while rung-3's local scoring leg was
live.** That violates the standing mid-run commit freeze — **the same class that voided the first
JCZ run** — and it is the direct cause of R5's chunks being scored across two revs.

**The mitigation is a witnessed fact, not an excuse.** The instrument diff over the full instrument
list is **empty**, so the scored values are not in question on the *source* axis. ⭐ **But the
mitigation was luck, not design:** nothing about the merge checked whether a scoring leg was live,
and had the commit touched `rust/`, `src/` or `scripts/tiletie/`, R5's chunks 3-5 would have been
**unrecoverable** — rescored at best, void at worst. **The freeze exists because "we checked
afterwards and it was fine" is not a control.**

⭐ **The discipline has now failed TWICE — JCZ, and here — and both times the failure was the
ORCHESTRATOR's, not a builder's or an executor's.** That is the argument for a mechanism rather
than more care:

> **W-ITEM `W-FREEZE-LATCH` (recommended, owner floated it after the JCZ incident):** a PreToolUse
> latch that **refuses a `main`-tree commit while any scoring leg is live** — live-ness detected
> from the run roots' claim/record activity or an explicit `RUN_LIVE` sentinel dropped by the
> launchers and cleared at close-out. **A convention that has failed twice at the same hands is a
> hook's job.**

### D5.4 The merge driver (c) — executor's direct `merge_legs` use is BLESSED

`run_scoring_r5.sh` carries a TODO where the merge driver would be. **Using `merge_legs` directly
is blessed**, per DESIGN line 448, on the same grounds D3/D4.13 already govern its behaviour: the
classification, the licence and the carry-forward are all **in `merge_legs` itself**, so a thin
driver would add a wrapper without adding a check. ⚠️ **Two conditions:** the exact invocation
(out-roots, licence file, `INSTRUMENT_IDENTITY_R5.json` path) is **recorded in the read-out**, and
the driver TODO is either **filled or deleted** — a TODO that reads as an unbuilt step, next to a
step that was in fact performed by hand, is how a runbook lies to its next reader.

---

## D3 — AMENDED SPEC (selection rule), per D4

`D3-WITNESS`'s sample selection is restated to be deterministic, non-empty by construction, and
free of any cherry-picking discretion:

> **Selection: the first 16 rids in `POSITION_ORDER.json` order among rids possessing
> laptop-produced `clair-puct` records.** Deterministic (the order is committed), auditable, and
> **guaranteed non-empty** — 314 laptop rids exist. If fewer than 16 qualify, take all qualifying
> rids and record the realized `N`.

Everything else in §D3.5 stands unchanged: **bar 100% bit-identical (`n_mismatch == 0`)**, counts
and digests only in `RUN/CROSSBOX_WITNESS.json`, per-box python/numpy/glibc recorded, any mismatch
an **owner-level escalation**. **Per §D4.4 it now runs before the completion scoring, not merely
before analysis.**

---

## D6 — `A2` ran LATE: the pair named a pass and named no tool (third instance)

**2026-08-20. Recorded, not excused.**

### D6.1 What the pair required, and what happened

`rung3_r5/READ_RULE.md` §1 places `A2` at **`[post-corpus]`, before the first scoring leg**. It ran
**after all scoring**. **Root cause: no auditor existed.** The pair specified the pass, pinned its
completeness assertion, and **named no tool to perform it** — so at the moment `A2` was due there
was nothing to invoke, and the run proceeded past its own checkpoint without anyone declining it.

**The proposed reading is CONFIRMED: `A2` runs NOW, late, and the lateness is disclosed here as a
numbered deviation.** The reasoning, stated so a reader can check it rather than accept it:

- **`A2`'s inputs are frozen and were frozen before scoring began.** Its addresses are
  `[pre-corpus]`/`[post-corpus]` artifacts — `ARMS_R5.json`, `CORPUS_R5`, `STAGING_R5`, the leg
  files, the `GATE_*` outputs — every one sha-pinned in the R5 licence. **Scoring reads them and
  writes `[post-scoring]` artifacts, which `A2` does not audit.** So nothing `A2` inspects was
  produced or modified by the work that overtook it: **the audit is late, not contaminated.**
- ⚠️ **But its protective value is spent, and that is a real loss.** `A2` sat before the first
  scoring leg **so that an address defect would be free to fix**. Discovering one now costs the
  entire scoring spend. **The audit's validity survives the delay; its purpose does not.** If `A2`
  fails, the run has already paid for the failure — that is the price of the omission, and it is
  not to be softened in the write-up.
- ⛔ **`A2` must VERIFY the freeze, not assume it.** Re-check each pinned sha against the artifact
  on disk as part of the pass. "Frozen" is the premise of everything above; an unchecked premise
  carrying this much weight is exactly what this campaign keeps getting wrong. Any drift ⇒ **RAISE
  to the owner**, not repair.

### D6.2 STANDING RULE — a pair may not name a pass without naming its tool

**Adopted.** This is the **third instance of one disease**:

| # | The pair named… | …and named no tool | Cost |
|---|---|---|---|
| 1 | the R4 **merge** | no merge driver | merge improvised post-hoc, licensed by deviation |
| 2 | the B64 **SMOKE** | no emitter | blocking finding at sign-off |
| 3 | R5's **`A2`/`A3`** | no auditor | **the checkpoint was silently skipped** |

> **STANDING RULE (campaign-wide, effective now).** *A preregistration may not name a pass, gate,
> merge, witness or audit without naming, in the same commit, the **tool** that performs it and the
> **address** it writes. An activity with no actor is not preregistered — it is a wish, and it will
> be skipped exactly when it matters.*

This is the address sweep (D4.14b) generalized **one level up**. The sweep made *addresses*
exhaustive by enumeration and caught the unresolvable ones. It could not catch these, because
**every address here resolved fine** — what was missing was the *actor*. **Enumerate the verbs, not
only the nouns.** Instance 3 shows the failure mode is not cosmetic: it is a checkpoint that
**cannot fail**, because nothing runs it — the same **pass-always** disease this campaign has now
found in `G-CAP`, `G-TOOL`, `G-COLLIDE`, `G-SATURATION` and `G-BAND`, wearing different clothes.

*No bar, branch, statistic or estimand moves under D6. The execution-layer completion that supplies
the missing tools is ruled in `rung3_r5/DESIGN.md` §"EXECUTION-LAYER COMPLETION".*

---

*No gate, address, bar, branch, statistic or estimand of the frozen pair is altered by D1, D2, D3,
D4, D5 or D6. `governance/PRODUCTION.yaml` untouched. D1 and D2 are not in force until their
signature blocks read SIGNED; D3's classification is in force on ruling and its witness on PASS;
D4's completion licence is in force subject to its §D4.9 conditions; D5's merge licence is in force
subject to its pre-committed binary-sha decision rule; D6 is a disclosure and a standing rule, and
both bind on writing.*
