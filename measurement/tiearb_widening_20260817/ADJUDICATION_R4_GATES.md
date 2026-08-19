# ADJUDICATION — R4 corpus-stage gate results

> Ruling from the **frozen pair's words** (`shared_run_r4/` at rev R4.5), not from the outcome
> anyone would prefer. Nothing is scored; no `arb`/`ora`/`Δ`/CI exists for any position of this
> run; boxes are idle. **`governance/PRODUCTION.yaml` untouched.**
>
> S2's void and the scale-dependence finding: [`PREREG_FAILURE_S2.md`](PREREG_FAILURE_S2.md).

---

## RULING 1 — May S1 scoring proceed under this prereg as written?

# **AMBIGUOUS ⇒ NOT LICENSED.**

**The text does not decide it, and I decline to decide it in the direction that salvages the
cheap rung.** Under the pair's own fail-closed default, an unresolved licensing question resolves
to *not licensed* — so **S1 scoring does not proceed under this prereg as written.** That is a
statement about *this document's* authority, not a recommendation about what should happen next
(§1.4).

### 1.1 The two readings, both textually available

**Reading A — `PROCEED-S1-ONLY`.** Conjunct (iii) is written **"per stratum"**, and the remedy
clause for exceeding it is stratum-scoped in its own words: *"Exceeding the bound ⇒ **that
stratum** is VOID."* On this reading the bound produces a **stratum-scoped void**, not a
gate-scoped FAIL; S1 satisfied its own bound (1 ≤ 7); the carried preamble says **"S2 gates bind
rung 3 only"**; rung 2's cells are **S1-only** (`shared_run/DESIGN.md` §2); and the architecture
demonstrably supports rung 2 standing alone — R4-2.2 offers an **`S1 ONLY`** row and §2a spells
out what happens when rung 3 does not run.

**Reading B — `VOID-BOTH`.** The gate table's header is unqualified: **"conjunct (all must
hold)"**. Conjunct (iii) does not hold. The carve-out that lets one stratum's result stand alone
is written for gates **marked `{S1,S2}`** — *"Gates written `{S1,S2}` are evaluated separately on
each stratum and both must pass"* — and **`G-DISJOINT` carries no such marker** (`G-LEAF`,
`G-SALT` and `G-CRN` do; `G-DISJOINT` does not). Absent that carve-out, a violated conjunct is a
gate FAIL, and the precedence clause is then decisive: *"If any gate binding a rung FAILS, that
rung's answer is `W-UNREADABLE` and no branch of that rung fires."* And `G-DISJOINT` **is** a gate
binding rung 2, because the preamble's taxonomy classifies gates by which stratum they touch and
`G-DISJOINT` touches S1 throughout — `s1_vs_tiletie0812`, `s1_vs_tiearb2_0816`, S1's own digest
bound — so it is at least in part an **S1 gate**, and **"S1 gates bind BOTH rungs."**

### 1.2 Why neither reading is forced — the gap, named exactly

**`G-DISJOINT` is a whole-run object with a per-stratum conjunct, and the pair's binding taxonomy
has no cell for that.** The taxonomy offers three categories — S1 gate (binds both rungs), S2 gate
(binds rung 3 only), `{S1,S2}` gate (evaluated separately, both must pass). `G-DISJOINT` is none
of them cleanly: three of its conjuncts are **inherently cross-stratum** — (v)
`strata_root_overlap == 0`, (vi)'s `s1_vs_s2` comparison, and `base_vs_extension`'s **summed**
top-level layers — so it cannot be called "an S2 gate" that binds rung 3 only; yet conjunct (iii)
is explicitly per-stratum with a stratum-scoped remedy, so it cannot simply be collapsed into a
single indivisible FAIL either.

**The specific sentence that was never written:** *what a per-stratum VOID does to the other
stratum's readability.* Reading A supplies "nothing"; Reading B supplies "it fails the gate, and
the gate binds both". **Neither is in the document.**

### 1.3 What does NOT resolve it

- **§2a's `n₂ = 0` clause** ("rung 3 does not run… the J question was **not bought**") is
  conditioned on the **owner's pre-committed floor** in `FLOORS.json`, not on a mid-run void. This
  run was bought with `n₂ = 1100`. Converting a two-rung purchase into an S1-only run *after
  seeing a gate outcome* is not the pre-registered `S1 ONLY` option; it is a new design choice.
- **The driver's aggregate** ("do not start a scoring leg") is **not a clause of the rule**. It is
  the W6 aggregation behaviour. It cannot license or forbid; only the text can.
- **The branch tables' tie rule** ("ties resolve to the more conservative, lower-spend row") is
  written for **branches**, not gates, and may not be imported to settle a gate question.

### 1.4 What licensing the ambiguity would take, and why it is clean to ask now

An owner ruling on **which reading governs** is a **governance act**, not a reading of the text —
and it is available on unusually clean terms: **nothing is scored, so the ruling is blind to every
statistic it could affect.** Same legality class as the earlier re-commits. Whoever rules should
see: (a) rung 2 is the cheap rung (**+508 games, ≈684 wh**) and its corpus-stage gates all passed;
(b) `G-REPLICATE` — which **binds both rungs** and is evaluated **on S1** — has **not yet been
evaluated**, because it needs scoring, so "S1's gates passed" means *its corpus-stage* gates
passed and rung 2 is not yet safe; (c) under Reading A the rung-3 riders read on S1
(replication, interaction) are **orphaned** — they adjudicate nothing already, and with no S2
primary they become observations with nothing to ride on.

---

## RULING 2 — The S2 disposition

**S2 VOID stands, exactly as pre-registered.** Written up in
[`PREREG_FAILURE_S2.md`](PREREG_FAILURE_S2.md): the void, the **scale-dependence finding as a
first-class result** (density is not a constant of the generator — 0.181% at 858 games → 2.636% at
5,340, all 30 exclusions at **ply 2**, and a linear-in-`n` bound against a pair-counted density is
**the wrong shape**, not merely the wrong calibration), the frozen consequence (**no cure by
generation**), and the successor requirements (scale-aware bound · a mining **ply-floor**, for
which no knob exists today though `ply` is already recorded · probe→carry **iterated to a fixed
point**). Rung 3 is **unmeasured, not answered**.

---

## RULING 3 — What does `residual = 1` mean for S1's own gate result?

# **NOT DISQUALIFYING. Reported, not fatal — and S1's bound holds WITH it counted.**

**The text is unambiguous here.** Conjunct (iii) is `carried + residual ≤ ⌈0.005 × n⌉`. S1:
`0 + 1 = 1 ≤ 7`. The residual is **already inside** the quantity the bound governs, and the bound
holds with a factor of 7 to spare (rate 0.074%). **No clause anywhere in the pair makes
`residual > 0` disqualifying per se** — its only other consequence is a reporting obligation:
*"A nonzero `residual` is additionally reported as a determinism defect."* That is a duty to
**print**, not a condition to **fail**.

**But the pre-registered label is the wrong diagnosis, and that must be said rather than
quietly satisfied.** R4-0.2 asserted `residual` is "expected 0" and called a nonzero one a
**determinism defect** — probe and final disagreeing about one corpus. The evidence contradicts
the diagnosis while confirming the arithmetic:

- `residual = 1` fired on **both** strata, including the one that passed — a defect that appears
  identically in a healthy stratum and a degenerate one is not diagnosing degeneracy;
- the mechanism is **resampling, not nondeterminism**: excluding rids admits positions the probe
  never saw, so the final build legitimately contains collisions the probe could not have counted;
- S1's residual is **`tt_sp_135000000122_p2` — the R3.3 rid**, a position known in advance to
  collide with the banked corpus. Its appearance is the loop working, not the loop wobbling.

⇒ **`expected 0` is unreachable by construction** for any probe→carry pass that changes the
admitted set. The frozen text is **not rewritten**; the reporting obligation is **discharged by
reporting the residual together with this corrected mechanism**, so no reader inherits the false
inference that a determinism fault occurred. **The successor fix is structural, and it is already
named in `PREREG_FAILURE_S2.md` §4.3: iterate probe→carry to a fixed point**, at which point
`residual = 0` becomes a meaningful check instead of an unreachable one.

---

---

## OWNER RULING — 2026-08-18, made BLIND

> **Verbatim: "a and successor".**

**Reading A governs. S1 proceeds under the R4 pair; S2's void stands; rung 3 gets a successor
prereg.**

**Blindness, on the record.** The ruling was made **pre-statistic** — nothing scored, no `arb`,
`ora`, `Δ` or CI in existence for any position of this run, boxes idle — exactly the clean terms
§1.4 offered. The owner resolved a **drafting gap**, not a result.

**The reasoning adopted.** Reading A as written in §1.1 — conjunct (iii) is *per stratum* and its
remedy is stratum-scoped in its own words (*"that stratum is VOID"*), S1 satisfied its own bound
1 ≤ 7, and rung 2's cells are S1-only. Reading B's strongest move — that `G-DISJOINT` carries no
`{S1,S2}` marker and so gets no separate-evaluation carve-out — is read as a **drafting omission
rather than a substantive scope decision**, and the evidence for that reading is that
**every substantive cross-stratum conjunct came back at zero**: `strata_root_overlap = 0`, and all
seven comparisons zero at the **rid and root** layers, including `s1_vs_s2`. The conjuncts that
make `G-DISJOINT` a whole-run object all **passed**; the sole violated conjunct is the one the
text scopes to a single stratum. The taxonomy gap is fixed prospectively in the successor
(`rung3_r5/DESIGN.md` §R5-6), not retroactively here.

**CARRIED CAVEAT — scoring proceeds THROUGH `G-REPLICATE`, not past it.** `G-REPLICATE` **binds
BOTH rungs**, is evaluated **on S1**, and **has not yet run** — it needs scoring to exist. This
ruling licenses S1 scoring; it does **not** pre-clear rung 2. If `G-REPLICATE` fails at the
read-out, rung 2 is `UNINTERPRETABLE` and no branch fires, exactly as written. "S1's gates passed"
means its **corpus-stage** gates passed.

**W9 (`D-DRAW`): SKIPPED, ruled moot under Reading A.** It replays **S2 capped plies**, and S2 is
void — there is nothing left for it to measure here. It **transfers to the successor**.
⚠️ Consequence, recorded rather than buried: `I7-draw-scope`'s load-bearing conditional — that the
python and rust afterstate-dedupe keys induce the same partition — stays **UNMEASURED**. That
costs rung 2 nothing (`I7` is a rung-3 rider by construction, and with rung 3 unmeasured it has
nothing to ride on), but the successor **inherits the obligation**, not a clean slate.

**One phrase the read-out must NOT reach for.** §2a spells out what to say when `n₂ = 0` — *"the J
question was **not bought**"* — but that clause is conditioned on the owner's pre-committed floor,
and **this run bought rung 3 at `n₂ = 1100` and then lost it to a void.** The read-out must
therefore say the J question was **bought and lost to a stratum void**: not "not bought", not
"answered", not "inconclusive". The frozen text has no phrase for this case, so it is named here
before anyone reaches for the nearest available one.

---

## RULING 4 — Does §9's 4b enumeration bound the audit's address list? (2026-08-18)

# **YES — the enumeration BOUNDS the live 4b audit. This is a W8 CODE DEFECT, not a pair defect. No amendment.**

The executor's 4b failed on `G-SALT` alone, whose three addresses
(`RUN_MANIFEST_{S1,S2}::world_seed_salt` and the leg-manifest fallback) are written by
**scoring-time emitters** (`run_tiletie:929`, `tier1_rust_leg:255/402`, `oracle_score_pilot:731`).
A pre-scoring 4b can never resolve them **on any healthy run**.

### 4.1 The tension is real and internal to the pair — both texts exist

- **The narrow text**, DESIGN §9 step 4b, enumerates what 4b audits: `CHAMP_GAMES_VERIFY`,
  `GATE_DISJOINT`, `POSITIONS_PLAN`/`ARMS`, `GATE_DRAW`, `GEN_SMOKE`, the step-7 smoke manifests,
  and §7's `c` block. **`G-SALT`'s addresses are not in it.**
- **The broad text**, DESIGN §8 builder-delta 5 — the REVIEW_R2 class fix I adopted **verbatim** —
  says 4b resolves *"EVERY address … named anywhere in READ_RULE §2/§4/§5 OR in DESIGN §7's
  `c`-remeasure obligation."* Read alone, **that includes `G-SALT`.**

So the harness did **not** reach past the pair; **it implemented one of the pair's two texts.**
That is worth stating plainly rather than blaming the builder.

### 4.2 Why the narrow reading governs — three clauses, in order of force

1. ⭐ **§1.5's structural test forbids the broad reading outright.** *"Would this gate fail on a
   healthy run? If yes, it is an instrument defect, fixed **before** the run, never adjudicated
   around."* A 4b that demands scoring-time addresses resolve **before scoring** fails on **every**
   healthy run, without exception. The pair's own doctrine cannot license a reading that is
   guaranteed to fail a healthy run — that is the exact defect class this campaign has killed
   five times (`G-CAP`, the four R1 gates, the R4-0.2 vacuity).
2. ⭐ **§9 4b's own parenthetical already supplies the reconciling principle** — it is not a gap
   being filled by argument: *"(The remaining `READOUT::widening.*` and `per_position_*.jsonl`
   addresses are audited by **4a's fixture schema pass**; **they cannot exist before scoring by
   construction**.)"* `G-SALT`'s addresses are **the same class** — scoring-time by construction —
   so the pair already routes them to 4a's static pass. The narrow text is also the **more
   specific** provision, and it addresses **this exact question**; specific governs general.
3. **The broad text's own stated purpose is satisfied by that routing.** Its rationale is that
   *"a fallback that is only exercised the day it is needed is unaudited"* — a **coverage**
   concern. 4a's fixture set covers it: §0.G added a **leg-manifest fixture**
   (`resolved_config.*`, `preflight.seeds.*`), which is `G-SALT`'s fallback address shape exactly.

⇒ **The one-row scoping fix in W8 is code catching up to spec.** Nothing in the pair changes; no
post-blind disposition; the JCZ precedent is not triggered, because the pair is not the thing
that fails a healthy run — the harness is.

⚠️ **One coverage gap the builder should close in the same fix, not later:** 4a's fixture set has a
**leg-manifest** fixture (covering `G-SALT`'s *fallback*) and a **smoke-manifest** fixture, but
**no `RUN_MANIFEST` fixture** — so `G-SALT`'s *primary* is, today, audited at **neither** 4a nor
4b. Add a `RUN_MANIFEST_{S1,S2}` fixture to 4a. Otherwise this ruling trades a false failure for a
silent hole, which is the worse trade.

### 4.3 Where `G-SALT` IS checked instead

**At read-out, per the gate table's own semantics.** §2's gates are *"evaluated **before any
branch statistic is read**"* — i.e. at adjudication, which is when `RUN_MANIFEST_{S1,S2}` and the
leg manifests exist. `G-SALT` keeps its full force there: primary, fallback, `resolved_at`
printing, and ABSENT-IS-FAIL. **Nothing is weakened; only the moment of the check moves to the
first moment it can be performed.**

**Partial code confirmation, stated as partial.** `acceptance_widening.py` (W8) is the **only**
file naming `G-SALT`; and `analyze_tiearb2.py` already performs read-out-time salt realization
**off the records** (`rec["world_seed_salt"]` → `world_seed_salt_realized`, `:291`, `:1106`), the
Stage-1b-era cross-check. ⚠️ **What I did NOT verify: that W3's `widening.*` verdict block emits a
`G-SALT` gate result** at read-out. **Confirm that before the read-out**, do not assume it — a gate
that moved out of 4b and was never picked up at adjudication would be a gate that stopped existing.

---

## BLESSINGS — two executor judgment calls (2026-08-18)

**1. `GEN_SMOKE.json` copied byte-identically old-RUN → new-RUN: ✅ BLESSED.** This is the
**`STAGE1B_LADDER` treatment** established in R4-0.5, applied to an artifact with the identical
property set: it is **cited by the pair** (§R4-5 rests its generation cost basis on that exact
297.6 measurement), it **existed only under the old `RUN`**, and 4b **addresses it under the new
`RUN`** — so without the copy the address resolves to nothing and **ABSENT IS FAIL on a healthy
run**. Conditions, all met and all required: byte-identical, **the old `RUN` is not written to**,
and provenance recorded. **A copy, not an address carve-out** — the same reasoning as the ladder.

**2. `c_remeasure` recomputing against R4 constants rather than the smoke artifact's embedded
R3-era fields: ✅ BLESSED, and it would have been a defect to do otherwise.** §0.A defines
`c_remeasure`'s committed values and **§R4-5 re-based the generation `c` from 990 → 372.0**. A
field embedded in an older artifact is **a record of what was committed when that artifact was
written** — it is data, not a commitment. Grading a realized `c` against a superseded constant
would produce a wrong ratio in both directions: a **spurious HALT** (297.6 vs 990 reads as 0.301,
inviting a "3× cheaper!" misreading) or, in the other direction, a **missed** one.

**The realized numbers corroborate that the R4 constants were used**, which is the check worth
recording: `gen ratio 0.800 × 372.0 = 297.6` — exactly the §R4-5 measurement, and *not* what
grading against 990 would give. All three legs came in **cheaper than committed** (arb 0.781,
gen 0.800, IF 0.747) and **correctly produced no halt**: §0.A/§7 make the HALT **one-sided**, and
cheaper is **recorded, never halted**. The IF leg's realized 1.755 worker-s/playout sits between
the smoke-indicated 1.2313 and the committed 2.35, so the pair's decision to **size on 2.35 and
report both** was the right conservatism — the envelope was not undershot.

---

## Summary

| # | question | ruling |
|---|---|---|
| 1 | May S1 scoring proceed under this prereg as written? | **Was AMBIGUOUS ⇒ NOT LICENSED** on the text. **RESOLVED by blind owner ruling 2026-08-18 ("a and successor"): Reading A governs, S1 proceeds** — subject to the carried `G-REPLICATE` caveat above. |
| 2 | S2 disposition | **VOID stands.** Rung 3 unmeasured. Scale-dependence recorded as a first-class finding. |
| 3 | `residual = 1` on S1 | **Not disqualifying** — counted inside the bound, which holds 1 ≤ 7. Report-only, with the pre-registered "determinism defect" label corrected to *resampling*, and the fixed-point fix carried to the successor. |
| 4 | Does §9's 4b enumeration bound the audit's address list? | **YES — W8 code defect, no amendment.** §1.5 forbids a reading that fails every healthy run; §9 4b's own parenthetical already routes cannot-exist-yet addresses to 4a's fixture pass. `G-SALT` is checked **at read-out**. ⚠️ Add a `RUN_MANIFEST` fixture to 4a in the same fix, or the primary ends up audited nowhere. |
| — | Two executor judgment calls | **Both BLESSED**: `GEN_SMOKE.json` byte-identical copy (the `STAGE1B_LADDER` treatment); `c_remeasure` against **R4** constants, not the artifact's stale R3-era fields — the `0.800 × 372.0 = 297.6` identity confirms it did. |
