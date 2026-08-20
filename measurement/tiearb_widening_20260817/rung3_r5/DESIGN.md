# RUNG 3 (`J > 4`) — SUCCESSOR PREREG, rev R5.1

> **STATUS: PREREGISTRATION PAIR, AMENDED AFTER [`REVIEW_R2.md`](REVIEW_R2.md) (FAIL: 6 BLOCKING,
> 11 REQUIRED, 5 COSMETIC). NOT LAUNCHED. NOTHING SCORED.** The mechanical
> [`READ_RULE.md`](READ_RULE.md) **is written** and commits with this file and `FLOORS_R5.json`.
> ⚠️ **R11 fixed:** the previous banner said the pair was *"not a preregistration yet"* and that
> the read-rule was *"deliberately not written yet"* — both false once §R5-FINAL and the read-rule
> shipped. **A blind-commit pair must not carry a banner saying it is not one.** §R5-8 is
> superseded by §R5-FINAL and now says so.
>
> **Naming, deliberately not `shared_run_r5/`:** this run is **rung 3 only**. Rung 2 is being
> answered by the R4 pair under the owner's Reading-A ruling, so calling the successor "shared"
> would misdescribe it. Cross-referenced from
> [`ADJUDICATION_R4_GATES.md`](../ADJUDICATION_R4_GATES.md) and
> [`PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md) so it is findable.
>
> **Parent chain, by reference:** R3.3 (`../shared_run/` @ `604edc83`) → R4.5 (`../shared_run_r4/`)
> → this. Every rung-3 estimand, branch condition, rider and power figure is **CARRIED**; §R5-7
> lists what changes. **Priority: launches after S1 scoring completes, earliest.**
>
> `governance/PRODUCTION.yaml` untouched. No claim minted. No strength row.

## R5-0. What this exists to fix

R4's S2 stratum voided on `G-DISJOINT`'s digest bound: **29 exclusions against a bound of 6**
([`PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md)). The corpus was **not short and not leaky** —
supply passed, every rid/root layer was zero. It was **degenerate in one measurable way**, and the
bound was **the wrong shape** to see it coming. This successor fixes the shape, the mining
predicate, the loop, and the drafting gap that made the void's scope arguable.

## R5-FINAL — DESIGN FINALIZED AGAINST THE MEASURED CALIBRATION (2026-08-19)

The sweep ran under the §R5-1.0 ruling. `CALIBRATION.json` is the measured input; the six design
decisions are taken here and the pair is ready for blind commit.

**⚠️ A constant the brief got wrong, caught before it propagated.** The task brief named the
scoring shape as **`M = 128`**. **It is `M = 32`.** Rung 3 **is** stratum S2, and R3.3's `G-M`
conjunct reads *"S1: `m_worlds == 128` … **S2: `32` / `16`**"*. R4's own reasoning is why: rung 3
reads only `B = 16`, which `M = 32` fully supplies (sel 16 / eva 16), and **`E = 16` is the
precision Stage-1b's `capped_only` levels — the source of the +0.1382 / +0.0842 predictions — were
measured at.** Matching it keeps prediction and measurement in one currency **and costs 4× less**.
Committing `M = 128` would have quadrupled the bill to buy a currency mismatch.

**Pre-registered constants, verified against `shared_run_r4/`:** `--m 32` · `--oracle-sims 100` ·
`--arb-backend rust` · `--arb-legal-mask-cache` on · `--only-profiles walled` · `--cap-j inf` ·
`--max-per-game 3` · CRN salt **`tiletie-v1`** · instrument cap draw **`tiletie-cap|<rid>|20260812`**
· deployed draw **`tiearb2-deploy-v1`** · **every `run_tiletie` path flag explicit** (§0.O as
widened by R4-0.4 — all six, three of them git-tracked in a spent run). **The two-box scoring layer
is the instrument** — proven on R4 and governed by `../DEVIATIONS.md` §D1/§D3/§D4.13.

### R5-FINAL.a — THE PLY FLOOR: **`k = 0`.** The original estimand is kept.

| | `k = 0` | `k = 3` |
|---|---|---|
| positions | **1,064** | 1,036 (**−2.6%**) |
| collisions at governed scale | **3 GROUPS of 2 = 6 positions involved** (all ply 2, all 137e9↔137e9); excluding the later member of each removes **3** (N8) | **0**, at every scale |
| `d` at governed scale | **0.282%** vs the 5% guard ⇒ clears **17.7×** | 0 |
| estimand | **`Δ_ora` over capped tied plies — what rung 3 was bought to measure** | `Δ_ora(ply ≥ 3)` — a sub-population |

**Ruled `k = 0`.** The ply-floor existed to rescue a bound that could not hold. **The bound holds:**
`d = 0.282%` against an absolute 5% guard is a 17.7× margin, **measured on the exact corpus that
will be scored**. Paying an **estimand change** — with R5-2.3's mandatory population-mismatch rider
on every branch, and the 1.400/1.244 multipliers derived on the *unfloored* population — to fix a
problem that is already measured-clear is a **bad trade**. ⚠️ **`k` stays a built knob (R5-W1) and
the floor becomes live again the moment a successor GENERATES fresh games at a larger `G`**, where
growth and extrapolation genuinely bite. It is set to 0 **for this run**, on this corpus, for this
reason.

### R5-FINAL.b — THE BOUND: the relative bound is **RETIRED as circular**; the absolute guard governs.

⭐ **`M × d_model` cannot fire on a corpus that has already been measured.** `bound = 3 × (3/1064) ×
1064 = 9` against a realized **3** — **satisfied by construction, with exactly `M` as its headroom,
incapable of failing.** That is **pass-always**, the mirror of the R4-0.2 vacuity, and it must not
be shipped as though it were a live test.

**What governs instead:**

1. **`G-INTERNAL-DUPE` — the ABSOLUTE 5% guard, RECOMPUTED AT RUN TIME.** `d_internal ≤ 0.05`;
   realized 0.002820, clearing **17.7×**. ⛔ **B2/C1 CORRECTED:** the previous revision named this
   gate `G-SATURATION` and addressed it at
   `CALIBRATION.json::by_ply_floor.0.d_model_at_governed` — **a constant committed with the pair,
   and the FITTED value this very section calls vacuous.** A gate whose input is frozen before the
   run **cannot fire**: the retirement had swapped one vacuous bound for another. The replacement
   **recomputes `d_internal` from the physical leg at corpus time** (READ_RULE §2), so the quantity
   can differ from expectation if the corpus does. ⚠️ And see READ_RULE §2.1: because the
   calibration measured **this same file**, both degeneracy gates are **corpus-identity checks, not
   discovery gates** — that is stated rather than implied.
2. **`G-COLLIDE` — a consistency check.** Realized collisions must **equal 3**, all at ply 2; a
   mismatch **RAISES**, because it would mean the scored corpus is not the measured one.
3. **The fit is REPORTED, never load-bearing.** `d_model(G) = a·G^b`, `b ≈ 0.906`, **`r² = 1.0` on
   `n_points = 2` — vacuous by construction** (two points determine a line exactly), and both lie
   above the `G = 500` composition break. ⭐ **No extrapolation is needed at all: the successor
   scores the EXISTING corpus at exactly `G = 5,340`, generating nothing.** A fit exists to
   extrapolate; there is nothing to extrapolate to.

*The R4 death was a bound of the wrong shape — calibrated at 858 games, applied at 5,340. The fix
is not a better fit; it is **not needing one**, because calibration and governance are the same
corpus at the same scale.*

### R5-FINAL.b2 — ⛔ CORPUS PROVENANCE (B4): it is R4's POST-EXCLUSION file, and it is adopted AS-IS

**The previous revision said the retained positions "enter the probe build and are gated exactly
like fresh ones … pre-cleared of nothing". THAT IS FALSE and is withdrawn.** Checked against the
artifact: of R4's 29 excluded S2 rids, **28 are already ABSENT** from
`corpus/positions_s2/positions_walled_leg1.jsonl` and **1 is present** —
exactly `carried = 28` removed and `residual = 1` left behind. **Every R5 number rests on a file
R4 had already cleaned.**

Three consequences, all now handled rather than inherited:

1. **The 0.282% was a POST-CLEANING RESIDUAL presented as the corpus's raw degeneracy.** It is now
   labelled as such wherever it appears.
2. **The 1 residual collider was still in the corpus and no R5 gate removed it.** It is
   **`tt_sp_135000000839_p2`** (a banked-`135e9` rid, at ply 2) and **R5 excludes it.**
3. **`n_positions == 1064` was an identity test that only passes if R5 silently reuses R4's
   exclusion list** — while `G-CORPUS`'s own address implied a *fresh build*, which re-mines
   **1,092** (= 1,064 + 28) and would have **failed the conjunct by 28 on a healthy run.**

⭐ **RULED: the corpus is R4's post-exclusion leg file, ADOPTED AS-IS, with its provenance stated
and pinned by hash — not re-mined.** Re-mining would re-admit the 28 and force R5 to re-derive an
exclusion decision R4 already made and recorded. The pinning is `leg_sha256` +
`r4_exclusion_list_sha256`, both committed in `FLOORS_R5.json` and gated by `G-CORPUS`.

**R5's own exclusion list**, applied on top and committed before the run:

```
R4 post-exclusion leg file                                   1,064   ADOPTED AS-IS (sha-pinned)
  - residual collider left behind by R4 (tt_sp_135000000839_p2)   1
  - later-ordered member of each same-band internal-dupe group    3
  =  n2 committed                                            1,060
     G-COMPLETE floor = ceil(0.95 x 1060)                     1,007
```

⚠️ **The internal-dupe count is GROUPS, not positions — a distinction the calibration's bare
`n_collisions: 3` hides.** Measured on the leg: **3 groups of size 2 = 6 positions involved**, all
at **ply 2**, all **137e9↔137e9 same-band**. Excluding the later member of each group removes **3**
positions and leaves one representative of each board, which is what independence requires.

### R5-FINAL.c — `n₂` AND THE FLOOR, from REALIZED supply. **Nothing inherited.**

```
retained S2 substrate                    5,340 games generated   (no generation in R5)
  games producing >=1 capped ply           980                   MEASURED (18.4% yield)
  capped plies in R4's POST-EXCLUSION leg 1,064                  MEASURED, sha-pinned (R5-FINAL.b2)
  mean positions per producing game      1.086, max 3 (= --max-per-game 3)
  same-band internal-dupe GROUPS             3 (= 6 positions), all ply 2, all 137e9<->137e9
  - R4 residual collider left behind         1  (tt_sp_135000000839_p2)
  - later member of each dupe group          3
  =>  n2 committed                       1,060
      G-COMPLETE floor = ceil(0.95 x n2) 1,007
```

⛔ **R4's `n₂ = 1,100` is NOT inherited** — it was a target set before the supply was known.
⛔ **And the previous revision's `1,064` is superseded**: it was R4's post-exclusion count taken as
if it were raw supply, with the residual collider and the internal duplicates left in
(§R5-FINAL.b2). `FLOORS_R5.json` records **1,060**.

**Power is essentially unchanged across all three figures**: the corrected +0.0842 resolves at
`sd_Δ ≤ 1.371` (vs 1.373 at 1,064 and 1.396 at 1,100), the legacy +0.1382 across the whole bracket,
and 1.400-vs-1.244 remains unseparable at `sd_Δ ≤ 0.879`. **The 4 excluded positions cost 0.002 of
`sd_Δ` headroom** — the exclusions are an independence correction, not a power decision.

### R5-FINAL.d — `I7`: **W9 `D-DRAW` is FUNDED.** The obligation is discharged, not inherited again.

R4 skipped W9 as moot when S2 voided, leaving `I7`'s **dedupe-partition conditional** unmeasured
with the successor inheriting it. **R5 funds it** (≈2 worker-h; the corpus exists): post-corpus,
no playouts, non-adjudicating, reported under `I7`, and it **may never correct, reweight or
re-scale `Δ_ora`**. Binding location: `I7` rides **every** rung-3 branch (READ_RULE §5).

### R5-FINAL.e — Existence-time markers: applied throughout (READ_RULE §1, R5-6.1).

### R5-FINAL.f — The failed-record bound, authored PRE-DATA, with its expected class.

`n_failed_rids / n_attempted ≤ 0.02`; **any non-`WindowTruncationError` class RAISES regardless of
count**; whole-rid drop across both judges (D4.18).

⛔ **THE EXPECTATION IS CORRECTED (B5), and the previous one is withdrawn.** The previous revision
pre-registered that capped plies *"skew EARLY"* so exposure *"should be LOWER than S1's realized
0.30%"*. **The corpus's own `ply` field refutes it: mean 69.15, median 68, max 142; 63.3% at
ply ≥ 50; only 2.63% at ply ≤ 2** — against S1's mean 66.50. `WindowTruncationError` fires at
**extreme board extents (~70 tiles placed)**, and **R5's corpus sits slightly DEEPER in that region
than S1's.**

⇒ **The pre-registered expectation is EQUAL-OR-HIGHER than S1's 0.30%.**

⚠️ **The inferential error, named so it cannot recur:** the prose reasoned from the ply of the
three **collisions** — forced early by the birthday argument, since few distinct boards exist at
ply 2 — and generalised it to the ply of the **corpus**. **Where collisions happen is not where the
population lives.** Uncorrected, a perfectly healthy elevated failure rate would have been reported
as *"a surprise worth naming"*, which is worse than having no expectation at all.

### R5-FINAL.g — Cost and wall. **No generation.**

```
scoring, M=32, per capped ply (R4-2.2 marginal S2 rate 302.5wh/1100 = 0.27500 wh/ply)
  x n2 = 1,060                                              291.5 wh   at COMMITTED c
champ picks  1,060 x 13.755 s                                 4.1 wh
corpus assembly + gates (counts only)                        ~2   wh
W9 D-DRAW                                                     2.0 wh
TOTAL, committed c                                         ~299.6 wh
TOTAL, at the S2 @ M=32 REALIZED c (below)                 ~211   wh
```

⭐ **R3 CORRECTED — the lower bound used the WRONG SMOKE, the same currency error this revision
exists to fix for `M`.** The previous figure applied **S1 @ M=128** ratios (IF 0.7471, ARB 0.7812)
when the same `c_remeasure` block carries **S2 @ M=32** smokes: **IF `1.6278605/2.35 = 0.69271`,
ARB `0.13595312/0.178232 = 0.76279`** ⇒ **0.191824 wh/ply**. At `n₂ = 1,060`:
`0.191824 × 1060 + 8.1 = 211.4 wh`.

⇒ **≈211–300 worker-h.** Wall: at `W_EVAL_LOCAL 30 + W_EVAL_LAPTOP 22 = 52` (C3 — the previous
5.3–7.0 h implied `W ≈ 43`, an unstated ~83%-of-nameplate derate), **≈4.1–5.8 h two-box at
nameplate**; the committed figure carries the derate explicitly rather than burying it.
R4 spent ≈500 wh *generating* these games; retaining them is the whole saving.

⚠️ **C2, disclosed:** `_positions_s2_pass1/POSITIONS_PLAN.json::champ_pick_secs ≈ 21.5 wh` was
already spent on this substrate, and R5 budgets another 4.1 wh for picks. **Double-paid and
conservative** — left in rather than netted out, so the bill is never understated.

### R5-FINAL.i — ⭐ EMITTER SPEC (N3): five artifacts, every addressed key, and the A1 fixture set

**Five run-time artifacts are addressed by the read-rule and none had a builder.** Specified here
so a builder implements without interpretation. **`RUN` = `measurement/tiearb_widening_20260817/rung3_r5/`.**

| artifact | key → type / semantics | built by |
|---|---|---|
| **`RUN/CORPUS_R5.json`** | `leg_path` str · `leg_sha256` str(64) — of the **adopted R4 leg** · `r4_exclusion_list_sha256` str(64) — §R5-FINAL.j · `n_in` int (1064) · `n_excluded_r5` int (4) · `n_positions` int (**1060**) · `excluded_rids` list[str] (the 1 residual + 3 dupe-later-members) · `n_distinct_seeds` int (980) · `max_positions_per_seed` int (≤3) · `n_out_of_band` int (0) · `n_seeds_136e9` int (0) · `seed_ranges` obj (from `FLOORS_R5.json`) | **NEW** `scripts/tiletie/build_r5_corpus.py` — reads the leg, applies §R5-FINAL.b2's exclusion rule, emits. Pure counts; no scoring |
| **`RUN/GATE_INTERNAL_DUPE.json`** | `n_positions` int · `n_dupe_groups` int (3) · `n_dupe_positions` int (6) · `d_internal` float (`n_dupe_groups / n_positions`) · `ply_histogram` obj{ply→count} over dupe members · `band_pairs` list[str] (`"137e9<->137e9"`) · `leg_sha256` str(64) | **NEW**, same script — the digest map is `sha256(checksum)` per row, grouped; **groups, not positions**, is the numerator |
| **`RUN/GATE_DISJOINT_R5.json`** | `passed` bool · `comparisons.<name>.layers.{a_root_id,b_rid}.n_intersection` int — **rid/root layers only**; the digest layer is not carried (READ_RULE §0). ⭐ **THE COMPARISON SET IS PINNED, and so is the exclude-rids REFERENCE** — see the two lines below | **EXTENDS** `scripts/tiletie/gate_disjoint.py` — same shape as R4's artifact, restricted to two layers |

### ⭐ RULING (2026-08-19, launch-blocking) — `ARMS_R5.json` IS MATERIALIZED. Shape (a).

`gate_disjoint --r5` needs the R5 corpus's `ARMS.json`; `build_r5_corpus.py` emits only counts,
shas, `excluded_rids` and seed ranges; **the only ARMS on disk is R4's 1,064 — the PRE-exclusion
population, which this design explicitly does not pin.** The executor was right to refuse to
hand-synthesize the input.

**RULED: shape (a) — `build_r5_corpus.py` EMITS `RUN/ARMS_R5.json` for the surviving 1,060.**

> **`RUN/ARMS_R5.json`** — the **materialized population authority** for R5. Same schema as
> `build_positions.build_arms_index` output (rid → `{arms, arms_full, subset_j4, root_id, ply,
> deck_seed, cap_seed, …}`), **restricted to the 1,060 surviving rids**. Built by
> `build_r5_corpus.py` in the same pass that writes `CORPUS_R5.json`. **Its rid set MUST equal
> `R4_ARMS.rids − excluded_rids` — asserted at build time in BOTH directions and gated.** Its
> sha256 is recorded in `CORPUS_R5.json::arms_r5_sha256` and in `FLOORS_R5.json`. It carries a
> `G-CORPUS` address, an A1 fixture (`fixtures/ARMS_R5.fixture.json`) and the `[post-corpus]`
> marker. ⛔ **Every consumer — `gate_disjoint --r5`, staging, scoring, the analyzer — READS
> `ARMS_R5.json`. None re-derives the population by subtraction.**

**Why (a) and not (b), on the campaign's own most expensive lesson.** Shape (b) — deriving
`R4_ARMS − excluded_rids` at read time — leaves the 1,060-population existing **only as a
subtraction that four consumers each repeat**. ⭐ **That is D4 with the operands swapped.** D4's
union assembled ARMS but not leg files, and **three independent "complete" signals were each true
of a different population because nothing materialized the one population they were all supposed
to agree on**; the missing invariant was *"the leg files enumerate exactly the ARMS rids"*. Shape
(b) reproduces that exactly: four subtractions, four chances to diverge, and **no artifact to
compare them against**. Shape (a) creates one authority and makes the invariant checkable.

⚠️ **And the pair already names an output nothing materialized** — §R5-FINAL pins *"the
1,060-position OUTPUT"* while `CORPUS_R5.json` carries counts but no rid list. **That gap is mine**,
and (a) closes it rather than papering it with a convention.

⚠️ **The G-CORPUS address + fixture + marker are MANDATORY, not optional** — without them
`ARMS_R5.json` is simply *the next unwitnessed layer*, one level down from the one this ruling
exists to fix. **A1 enforces this automatically:** its completeness assertion is over the **marker
list**, so an address added without its fixture **fails A1** rather than passing silently.

### ⭐ EXECUTION-LAYER COMPLETION — RULED (2026-08-19). Where the verdict is written, who audits, and what adjudicates.

The pair defines `A1`/`A2`/`A3` and carries the branch table, but **names no tool for `A2`/`A3`
and has no read-out address at all** — the addressed artifacts stop at `MERGE_REPORT_s2.json`.
**Ruled here** on the D4.16 precedent: naming **where** a committed branch table's verdict gets
**written**, and **who** performs a committed pass, **moves no bar, branch or statistic.**

**1. EMISSION TARGET.** `RUN/READOUT_R5.json` + `RUN/READOUT_R5.md`, marker `[post-scoring]`,
A1 fixture `fixtures/READOUT_R5.fixture.json`. Every `READOUT::…` address in the READ_RULE resolves
against `READOUT_R5.json`.

**2. THE `A2`/`A3` AUDITOR — `acceptance_r5` mode**, over **the pair's own address list**, with the
completeness assertion the pair already specifies:

```
A1 (pre-corpus, static/fixtures) + A2 (post-corpus, live) + A3 (post-scoring, live)
    ==  the COMPLETE set of addresses named in READ_RULE.md
Per address: resolved / UNRESOLVED, plus JSON type. NO VALUE is printed, ever.
Primary AND fallback resolved INDEPENDENTLY. Any address in neither pass FAILS the assertion.
```

**3. THE ADJUDICATOR — I/O pinned.**

```
INPUTS
  merged leg records   RUN/legs/s2/**/records/<rid>.json   -- per-(rid, leg) arm values
  ARMS_R5.json         the population authority: arms_full and subset_j4 per rid
  FLOORS_R5.json       n2=1060, gate_floor=1007, and the pinned constants
  the §2 gate artifacts (CORPUS_R5, STAGING_R5, GATE_INTERNAL_DUPE,
                         GATE_DISJOINT_R5, RUN_MANIFEST_R5, MERGE_REPORT_s2, D_DRAW)

PRIMARY
  Delta_ora = ora_full - ora_J4, at capped plies, per rid, where
    ora_full = cross-fit oracle value of the best arm over ARMS_R5[rid].arms_full
    ora_J4   = same, restricted to ARMS_R5[rid].subset_j4
  significance ONCE, on the percentile ROOT bootstrap (2,000 reps, seed 20260819, cluster root_id)
  R_ora = ora_full / ora_J4, subject to the degenerate-denominator guard
  Delta_arb, R_arb  -- deploy RIDERS, adjudicate nothing

BRANCH TABLE -- VERBATIM from READ_RULE §4, not one threshold, sign or condition moved:
  X-CONFIRMED  X-ABOVE  X-PARTIAL  X-BELOW  X-FREE  X-INCONCLUSIVE
  + the R_ora degenerate guard and its committed Delta_ora-only sub-table
  + the X-NOISE rider (non-adjudicating)
  + the three mandatory prints (1.400-vs-1.244 unseparable; +0.0842 at the bracket top;
    the X-FREE attainability window at the REALIZED se)
```

⛔ **THE S1-RIDER PROHIBITION APPLIES, and it is not optional.** R3.3 §5's address list includes
`widening.j_rider.s1_replication.*` and `…interaction.*` — **S1 quantities. R5 HAS NO S1 STRATUM.**
They must be **absent or null with their witness**, and **may never be reported as if measured**.
A rider with no stratum behind it is not a weak result; it is **not a result**.

⛔ **TOKEN DISCIPLINE, as ruled for R4 but inverted here.** R4's rung 3 fired **no** X-branch, so
**no X-token could appear anywhere**. R5 **does** fire one, so **its token appears legitimately —
and no other X-token may appear anywhere in the READOUT**, and the non-fired branches must not be
narrated as near-misses. **`VOID_S2` must not appear at all**: R5 is the successor to that void,
not a continuation of it.

**4. `READOUT_R5.json` SCHEMA (the addresses the READ_RULE already names, made concrete):**

```
widening.j_rider.s2.{delta_ora, ci95_ora, r_ora, ci95_r_ora, ora_j4_ci95,
                     delta_arb, ci95_arb, n_capped, xfree_window, r_ora_reported}
widening.j_rider.d_draw.{n_checked, agreement_rate, d_draw_ran}
widening.completion.s2_n            widening.failed.{n_failed_rids, n_attempted, rate, by_class}
widening.gates.{<gate>: {ok, resolved_at}}          -- every §2 gate, never short-circuited
widening.supply_chain.{...}         widening.branch.{fired, reasons, mandatory_prints}
```

### ⭐ THE LEG STRUCTURE — RULED (2026-08-19, launch-blocking). The premise was wrong; the conclusion holds.

The smoke refused on a missing leg2. **Verified against the artifacts, and the situation is worse
than the diagnosis — but the fix is cleaner.**

**Three facts, measured, not assumed (the N1 lesson):**

1. ⛔ **`positions_s2/` — the adopted final build — contains ONLY `leg1`.** `positions_s1/` has 12
   legs and the probe `_positions_s2_pass1/` has 11. **The final S2 build is TRUNCATED**, and the
   brief's premise that "R4's S2 source carries legs 1-12" is **false for the build R5 adopts**.
2. ⛔ **Legs are NOT "rungs over the SAME rids".** `build_positions.write_leg_files` emits, for
   `r in 1..len(arms)-1`, one row per position pairing **`arms[0]` vs `arms[r]`**. They are
   **arm-index pairings, and they THIN** as `r` rises (Stage-1b's banked counts 1350/792/448/113
   are the same signature). S2's arm counts run **5–13** (mean 7.2283), so every capped position
   belongs in legs 1–4 at minimum.
3. ⛔ **The probe cannot supply the missing legs.** `_positions_s2_pass1/` is a **different
   population** — 5,617 `leg1` rows (all tied plies, extension-only), and only **961 of the 1,064**
   capped rids appear in it; the **103 banked capped rids are absent entirely.**

**(a) RULED — DERIVE legs 2–12 from the pinned authority; do not adopt them from anywhere.** A leg
file is a **deterministic function** of `(arm list, per-rid source fields)`, and both are already
pinned: `ARMS_R5.json` (sha `adb4c5bd…cf8a`) carries the arm lists, and the adopted `leg1` carries
every source field (`checksum`, `actions`, `deck_seed`, `ply`, `root_player`, `game_label`) for all
1,060 rids. **This changes no population, re-mines nothing, and makes `ARMS_R5.json` genuinely the
authority rather than one of three sources.**

**The invariant is EXACT — not "equal", not "subset":**

```
for r in 1..12:  set(leg_r rids) == { rid in ARMS_R5 : len(arms[rid]) > r }
EXPECTED ROWS (pinned, from the 1,060 population):
  leg1 1060  leg2 1060  leg3 1060  leg4 1060  leg5 866  leg6 509
  leg7  366  leg8  265  leg9  171  leg10 110  leg11  66  leg12   9
  TOTAL 6,602 arm-pair rows   (= n x (A_bar - 1), A_bar = 7.2283)
```

⚠️ **Equality across legs is FALSE from leg5 on, and "subset" is true but too weak to catch a
truncated leg** — the exact predicate is what makes the missing legs detectable. `G-STAGED`'s
cross-layer invariant extends to **every** leg under this predicate, and `check_leg_layer` is
already multi-file.

**Cost is unaffected:** `6,602 pairs × 2 × M(32) = 422,528` playouts, identical to R4-2.2's
`n × 2 × (Ā−1) × M`, so §R5-FINAL.g's ≈211–300 wh stands.

**(b) The pair does NOT consume leg1 only — verified structurally.** Rung 3's primary is
`Δ_ora = ora_full − ora_J4`, which requires the **full deduped arm set** priced; `leg1` alone
prices `arm0`-vs-`arm1`, i.e. **~1 of ~6.2 pairs per position**. ⇒ **leg1-only staging would have
produced an unobtainable estimand at scoring**, and the smoke's CRN cross-leg witness caught at
zero cost what would otherwise have surfaced after ~200 worker-h. **The single-leg smoke mode is
therefore NOT adopted** — there is nothing to replace `crn_cross_leg_identical` with, because the
run genuinely has multiple legs.

**(c) ETA denominators — the watch sizes on the invocation's ACTUAL worker count.** The plan's
**8.987 h @ W22 single-box** and the committed **4.1–5.8 h @ W52 two-box** are **the same work at
two denominators**; the committed figure is the two-box one, 8.987 h is the single-box fallback,
and **the watch must size on whichever the launcher actually runs — never mix them.**

### ⭐ THE SMOKE INVOCATION — PINNED (2026-08-19)

The pair named `SMOKE_R5.json`'s **fields** but never its **judge** or **`n`**, leaving both to
whoever ran it. Pinned verbatim, at the carried §7.1 shape:

```
run_tiletie.py --judges tier1-greedy --smoke-judge tier1-greedy --smoke-n 20 \
               --m 32 --arb-backend rust --only-profiles walled \
               --positions-dir <explicit> --smoke-manifest RUN/SMOKE_R5.json \
               --manifest-out <explicit> --gate-out <explicit> --logs-dir <explicit> \
               --out-root <explicit>            # every path flag explicit, R4-0.4
```

⚠️ **THE FLAG-INERT TRAP — `--smoke-judge` ALONE IS NOT ENOUGH; `--judges` IS REQUIRED TOO.**
Found empirically by the executor, and it is why the invocation is pinned rather than described.
**Likely mechanism, flagged as likely rather than asserted:** `run_smoke` keys off
`args.smoke_judge` throughout, but `write_manifest`'s **`resolved_backend_by_leg`** is built from
the `--judges` loop — so with `--judges` at its `clair-puct` default the **ARB leg never appears in
the manifest at all**, and `G-BACKEND`'s conjunct (*"every `tier1-greedy/walled` entry reads
`rust`"*) has nothing to range over. **A conjunct with an empty domain is not a satisfied
conjunct** — it is the vacuous-pass shape this pair has now caught four times.

### ⭐ A GATE THAT FIRED CORRECTLY, recorded because the record is otherwise one-sided

While the staging assembly was being built, the **`afterstate_dedupe` carry-forward** defect in the
staged plan was **caught by its own gate**, before any scoring. ⭐ **It belongs in the record.**
This campaign's history is dominated by gates that failed a healthy run or could not fire at all —
`G-CAP`, the four R1 gates, R4-0.2's vacuity, `G-COLLIDE`, `G-SATURATION`, the `s2_vs_exclude_rids`
default — and reading only that history would suggest the discipline produces nothing but
false alarms. **It also produces this: a real defect, caught by a pre-registered check, at the
cheapest possible moment.** `build_positions`' own dedupe assertion (*"a plan built before the
dedupe landed … must not be launched"*) is the check that fired, and it fired exactly as written.

### ⭐ THE STAGING ASSEMBLY RECIPE — BLESSED AS AMENDED (2026-08-19), and it needs its own witness

`ARMS_R5.json` is built and **sha-landed: `adb4c5bd7cf904a1fe00c839eab722fa79798b9f719b631b6f788900f3e5cf8a`**
(1,060 rids; `G-DISJOINT_R5` PASS, all four comparisons `n_intersection = 0`). The staging
assembly is blessed **with three amendments**, numbered so the builder implements without
interpretation. **New artifact: `RUN/STAGING_R5.json`, marker `[post-corpus]`, A1 fixture
`fixtures/STAGING_R5.fixture.json`, gated by `G-STAGED` (READ_RULE §2).**

```
1. mkdir RUN/corpus/positions_s2/

2. COPY  ARMS_R5.json -> positions_s2/ARMS.json
   ASSERTS: sha256(staged copy) == sha256(ARMS_R5.json) == adb4c5bd...cf8a
   WITNESS: STAGING_R5.json::{arms_r5_sha256, staged_arms_sha256, arms_copy_identical}
   (a) RULED: the copy does NOT breach "one authority". It is a NAME ADAPTATION for
       stage_chunks' hardcoded ARMS_NAME, and byte-identity is ASSERTED AT STAGING TIME
       and RECORDED -- so there is one authority and one witnessed transcription of it,
       not two populations. A symlink is NOT used: R4-0.5 already ruled symlinks out
       (write-through hazard; breaks on archive/move).

3. FILTER the R4 leg jsonl to the SAME 1,060 rids (drop CORPUS_R5::excluded_rids)
        -> positions_s2/positions_walled_leg1.jsonl
   (b) RULED: this MUST run through an EXISTING CHECKED TOOL --
       build_r5_corpus.assert_rid_sets_equal (or union_positions.check_leg_layer) --
       and NEVER an ad-hoc jq/sed/awk filter.

4. THE CROSS-LAYER INVARIANT, asserted AT ASSEMBLY TIME, in BOTH DIRECTIONS:
        set(leg rids) == set(positions_s2/ARMS.json rids) == set(ARMS_R5.json rids)
        and |each| == 1060
   WITNESS: STAGING_R5.json::{n_leg_rids, n_arms_rids, rid_sets_equal, missing_in_leg,
                              missing_in_arms}
   (b) This is D4's missing invariant, installed at the layer that lacked it.

5. WRITE positions_s2/POSITIONS_PLAN.json: n_positions=1060, cap_j=null, uncapped=true,
   max_per_game=3, and a files BLOCK THAT ENUMERATES THE LEG FILE THAT ACTUALLY EXISTS.
   ASSERTS: every path in files{} exists on disk and its rid set matches step 4.
   ⚠️ D4's defect was a files block pointing at an ext-only set while the plan claimed the
      union -- a plan may never name a population its files do not contain.

6. stage_chunks stage --s2-dir RUN/corpus/positions_s2
   ASSERTS: stage_chunks' own re-derivation agrees with step 4's rid set.
   WITNESS: STAGING_R5.json::{stage_chunks_rid_set_agrees, n_chunks}
```

**(c) RULED: `CORPUS_R5`'s identity does NOT suffice; the assembled dir needs its own witness.**
`CORPUS_R5.json` is written **before** staging and describes the **population**; it cannot witness
a **layer that did not exist when it was written**. ⭐ **That is precisely the D4.7 finding —
`CORPUS_UNION` "asserted at the ARMS layer a property only the leg layer could witness"** — and
accepting `CORPUS_R5` as sufficient here would repeat it one artifact later. Hence `STAGING_R5.json`,
with its own marker, fixture and gate. **A1's completeness assertion is over the marker list, so
adding `G-STAGED`'s addresses without the fixture fails A1 rather than passing silently.**

⭐ **`GATE_DISJOINT_R5` — the two lines REVIEW_R4 requires (P1), because an unpinned reference
defaults to an EMPTY list and the comparison is then PASS-ALWAYS (the campaign's third
mirror-disease catch):**

```
(a) COMPARISON SET, pinned:
      { s2_vs_tiletie0812, s2_vs_tiearb2_0816, base_vs_extension, s2_vs_exclude_rids }
    = R4's seven minus the three that require an in-run S1 side
      (s1_vs_tiletie0812, s1_vs_tiearb2_0816, s1_vs_s2), with exclude-rids renamed.

(b) EXCLUDE-RIDS REFERENCE, pinned (NEVER a default, NEVER an empty list):
      sorted( GATE_DISJOINT.json::digest_exclusions.S2.rids )        -- the real 29-rid R4 S2 list
      from  measurement/tiearb_widening_20260817/shared_run_r4/GATE_DISJOINT.json
      under the SAME canonical serialization as R5-FINAL.j (whose sha 76f9ac58... already pins it)
      passed as run_r5_gate(exclude_rids=...)
    EXPECTED: n_intersection == 0 on the 1,060-position OUTPUT
              and NON-ZERO (1) on the pre-exclusion 1,064 INPUT
    => this is the LIVE WITNESS that R5's four exclusions were actually applied.
       A test MUST assert the comparison FAILS on the pre-exclusion corpus; a reference that
       cannot fail on the un-cleaned corpus is not a reference.
```

⭐ **Why R4's S1 gets NO comparison, written down as REVIEW_R4 asks** — the one substantive gap in
the set above, and it resolves in the pair's favour: **rid/root disjointness from R4's S1 is
GUARANTEED BY `G-BAND`(i)'s range conjunct**, not by a comparison. R4-6 split band 135e9 at
`+349/+350` (S2 takes `+350…+849`), and the 137e9 sub-ranges are disjoint by construction
(S1 `+0…+507`, S2 `+508…+5347`). All 1,064 seeds lie inside R5's two committed ranges with **0
out-of-range** ⇒ **no R5 rid can be an R4-S1 rid.** The guarantee is structural, so a comparison
would be redundant — but the *reason* must be on the record, or a later reader sees only a missing
comparison.

⭐ **Band-label mapping, declared once (REVIEW_R4 (c)):** two vocabularies coexist deliberately —
short `"137e9<->137e9"` in `GATE_INTERNAL_DUPE.band_pairs`, long `banked_135e9` /
`extension_137e9` in `CORPUS_R5.seed_ranges` — **`banked_135e9` ≡ `135e9`, `extension_137e9` ≡
`137e9`**. Each artifact's vocabulary matches the conjunct that reads it, and **`G-BAND` names its
ranges numerically and never by label**, so no conjunct has to resolve a label across the two. ⚠️
**This is NOT an R8-class hazard** (there, one key path had to resolve under a single spelling);
it is declared here so the coexistence is deliberate rather than discovered.
| **`RUN/SMOKE_R5.json`** | `m_worlds` int (**32, top level**) · `oracle_sims` int · `arb_backend` str · `c_worker_secs_per_playout` float · `crn_cross_leg_identical` bool | **EXISTING** `run_tiletie.py --smoke` with `--smoke-manifest RUN/SMOKE_R5.json`; **no code change** |
| **`RUN/MERGE_REPORT_s2.json`** | `preserved_from_existing` obj · per-chunk `execution` block · `carc_rs_build` equality result · per-box `carc_rs_binary_sha` constancy result | **EXISTING** `merge_legs.py` (D1/D3/D4.13), pointed at R5's out-root |

**A1's committed fixture set** — `RUN/fixtures/` (committed **with** the blind pair; A1 audits key
presence + JSON type only, never a value):

```
fixtures/CORPUS_R5.fixture.json          fixtures/RUN_MANIFEST_R5.fixture.json
fixtures/GATE_INTERNAL_DUPE.fixture.json fixtures/leg_manifest.fixture.json   <- resolved_config.*
fixtures/GATE_DISJOINT_R5.fixture.json   fixtures/READOUT.fixture.json        <- widening.*
fixtures/SMOKE_R5.fixture.json           fixtures/D_DRAW.fixture.json
fixtures/MERGE_REPORT_s2.fixture.json  fixtures/ARMS_R5.fixture.json        <- population authority
fixtures/STAGING_R5.fixture.json      <- staged-layer witness (G-STAGED)
```

⚠️ **The fixture set must cover EVERY `[post-corpus]` and `[post-scoring]` address** — R5-6.1
diagnosed exactly this leak in R4 ("covered the leg manifest and the smoke manifest but **not**
`RUN_MANIFEST`"), and A1's completeness assertion is over the **marker list**, not over this
filename list, so a missing fixture fails A1 rather than passing silently.

### R5-FINAL.j — `r4_exclusion_list_sha256`: referent and canonical serialization (N4)

The value `76f9ac58e2694a54…` is correct but was unreproducible because neither its referent nor
its serialization was written. **Both are now pinned, exactly:**

```
r4_exclusion_list_sha256
  = sha256( json.dumps( sorted( <GATE_DISJOINT.json>::digest_exclusions.S2.rids ) ) )
  where <GATE_DISJOINT.json> = measurement/tiearb_widening_20260817/shared_run_r4/GATE_DISJOINT.json
  json.dumps default separators, no sort_keys (input is a list), UTF-8, no trailing newline
```

⚠️ **It is NOT any of the four `EXCLUDE_RIDS_*.txt` files** — a verifier that reached for those
would fail to reproduce it, which is what happened on review.

### R5-FINAL.h — For a second reviewer, before blind commit

1. **`M = 32`, not 128** (above) — the one inherited constant I had to correct.
2. **The retired relative bound** (§b) — the ruling that a pre-measured corpus makes `M × d`
   pass-always. If a reviewer disagrees, the alternative is to *generate* fresh games, which
   changes the run.
3. **`k = 0` over `k = 3`** (§a) — trading 2.6% supply for an estimand change was refused.
4. **The S2 union-plan pointer defect stands** (physical leg file complete and executor-verified;
   `POSITIONS_PLAN` `files` block ext-only; `CORPUS_UNION` S2 `witnessed:false`). S2's *void* is
   R4's; **this run reads the PHYSICAL file and `G-CORPUS` says so explicitly.** No repair is
   licensed and none is taken.

---

## R5-1.0 ⚠️ PRE-DESIGN RULING (2026-08-19) — units, and a confound that changes the sweep's purpose

The calibration sweep **refused on a unit mismatch and was right to refuse.** Ruling the three
questions, plus one finding the refusal exposed that matters more than the units.

### R5-1.0.a THE UNIT OF `G`: **games GENERATED.** Confirmed.

`rung3_calibrate.py --scales` currently means *a prefix of games PRESENT in the mined leg file*.
That cannot price the successor: **the successor sizes a generation run**, `FLOORS.json` is written
in **generated** games, and only **18.4%** of generated games produce a capped ply at all
(980 producing / 5,340 generated; 1,064 rids; mean 1.086 positions per producing game, max 3 = the
per-root ceiling). A density indexed by *producing* games cannot be inverted into "how many games
must I generate", which is the only question the bound is asked.

**The seed → generation-index mapping, verified against `FLOORS.json` and the pair:**

```
S2 generation order (5,340 games):
  [135000000350 … 135000000849]  -> idx    0 …  499   (banked; band 135e9, S2 sub-range)
  [137000000508 … 137000005347]  -> idx  500 … 5339   (extension; FLOORS.sub_ranges.s2)
  anything else                   -> RAISE
```

Verified: `FLOORS.json::sub_ranges.s2 = [137000000508, 137000005347]` and
`games_extension_s2 = 4840`; the pair's R4-2.1 gives S2 = **500** banked games and R4-6 splits band
135e9 at `+349/+350`. `500 + 4,840 = 5,340` ✓.

⭐ **Why seed order is the correct order, since someone will object that work-stealing means games
were not *produced* in seed order:** a successor sizing `G` games runs `--seed-start S --games G`
and gets seeds `S … S+G−1`. **So a prefix of seeds is exactly the corpus `G` generated games would
be** — which is the counterfactual the bound must price. Wall-clock/claim order is an artifact of
`--shared-claim` and **must not be used**. **Zero-yield games advance `G` silently**, which is the
entire point of the unit.

### R5-1.0.b THE NUMERATOR: **NOT re-based.** Density stays per-POSITION.

`d` must be in the same currency as the quantity the bound grades. R4's bound compared
`carried + residual` (a **count of excluded positions**) against `⌈0.005 × qualifying_deduped⌉` (a
**fraction of positions**). So:

> **`d(G) = collisions / qualifying-deduped POSITIONS`, indexed by `G` = games GENERATED.**

A hybrid, deliberately: the **independent** variable is what you buy (games), the **dependent**
variable is what the bound grades (positions). §R5-1.2 as originally drafted said "a bound on the
density" without pinning the density's own denominator — **that ambiguity is closed here.**

### R5-1.0.c ⛔ SECOND REVERSAL (R4) — the stratum mechanism below is ITSELF WRONG, and the scale-growth story is RESTORED

> **This section reversed the original scale-growth reading. `REVIEW_R2.md` §R4 reversed it back,
> and the reviewer is right. Recorded as a SECOND reversal on one point, with both errors named,
> because a quiet re-reversal would be worse than either mistake.**
>
> **The claim below — that capped plies are "disproportionately ply-2", so S2 may be dense because
> it is capped-only rather than because it is big — is refuted by the corpus's own `ply` field.**
> Measured this session on the two final builds: **S1 ply-2 share `35/1344 = 2.60%`; S2 ply-2 share
> `28/1064 = 2.63%` — identical.** The strata have the **same** early-ply composition, so there is
> no stratum mechanism to explain the density gap.
>
> **And the same-currency contrast I said did not exist is available on those same two builds:**
> internal-dupe density **S1 `1/1344 = 0.074%` at 858 generated games** vs **S2 `3/1064 = 0.282%`
> at 5,340** — the *same quantity* (same-band internal duplication) at two scales, **3.8× on 6.22×
> the games**, consistent with the fitted `b ≈ 0.906`. ⇒ **The scale-growth reading SURVIVES in the
> correct currency; the replacement mechanism does not.**
>
> **Both of my errors, named:** (1) the original comparison was cross-stratum *and* mismatched
> (S1's *banked* rate against S2's), which was a real defect — that part of the reversal stands;
> (2) the replacement mechanism generalised **collision** ply to **corpus** ply, the same
> inferential error as B5. **The right fix was to find the same-currency contrast, not to invent a
> mechanism.**
>
> **No consequence for R5**, which generates nothing and whose guards are corpus-identity checks
> (READ_RULE §2.1). Corrected in place here and in
> [`../PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md) §2.

### R5-1.0.c (original text, superseded above) — the two "calibration points" are CROSS-STRATUM

Checking the units surfaced something larger. The two points §R5-1 was built on —
**858 games → 0.181%** and **5,340 → 2.636%** — are **not two points on one curve**:

- `858` is **S1's** generated total; `0.181%` is **S1's banked** rate (1/551, from 350 games).
  S1's *full-corpus* rate is **1/1,344 = 0.074%**. The original pairing mixed two S1 corpora.
- More seriously, `2.636%` is **S2's** — and **S1 and S2 are different strata with different
  mining predicates**: uniform tied plies at `--max-per-game 4` versus **capped-only** plies at
  `--max-per-game 3`.

**Within S1 the collision count is 1 at both 350 and 858 games — one event, no growth signal.** The
S2 rate really is ~36× S1's, but that gap is **confounded between scale and stratum**, and the
mechanism favours *stratum*: **all 30 collisions are at ply 2**, and capped plies are
disproportionately ply-2 (a near-empty board offers many equal-valued symmetric placements — which
is what makes a large tie set, hence a capped ply). **S2 may be dense because it is capped-only,
not because it is big.** Corrected in place at [`../PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md) §2.

⇒ **The sweep's primary purpose is now to DISENTANGLE scale from stratum, not to add points to an
established curve.** It must therefore run **entirely within S2** (S2's own 5,340 generated games),
so the fitted `d(G)` isolates the scale effect. **The a priori pair-counting argument survives
untouched** — a linear-in-`n` bound must eventually fire for any nonzero revisit rate — but **the
exponent and the magnitude are unmeasured**, and §R5-1.2's `M = 3` multiplier is applied to a
`d_model` that does not exist yet. That is the correct order; it is only worth saying because the
withdrawn numbers made it look as though it already did.

### R5-1.0.d THE SCALES: **five, not four** — `{500, 1000, 1500, 3000, 5340}`

The briefed `{500, 1500, 3000, 5340}` meets the ≥4 floor, but **`G = 500` is exactly the
banked/extension boundary**, so the corpus composition **changes structurally there**: at
`G ≤ 500` only band 135e9 is present and **no cross-band collision can occur**; above it, the
`base_vs_extension` category (D4.11/B1) switches on. A single power law fitted across that break is
fitting two regimes. **Adding `G = 1000` characterises the break** at zero extra cost (counts
only). Mandatory reportables per scale: **band composition** and an explicit note that the
**structural break at `G = 500`** makes any single-law fit an approximation across a composition
change rather than a law.

### R5-1.0.e TOOL AMENDMENT SPEC (builder)

Add `--generated-order` (or equivalent): map each leg record's deck seed to a generation index via
the **declared, committed ranges** above, in that order; a scale `G` selects records whose index is
`< G`. **RAISE if any leg seed falls outside the declared ranges** — fail-loud on the unexpected,
never silently skip, since an out-of-range seed means the corpus is not the one `FLOORS.json`
describes. Per scale emit: `G`, `n_games_producing`, `n_positions`, `n_collisions`, `d`, and the
**per-band game counts**. Declare the ranges in the tool's own manifest so the mapping is auditable
without re-deriving it.

⚠️ **Recorded, and the calibration must SAY it: the S2 union-plan pointer defect stands.** The
physical leg file is **complete** (1,064 rows, both bands — the executor verified this before
trusting it), while `POSITIONS_PLAN`'s `files` block is still **ext-only** and
`CORPUS_UNION` S2 `witnessed:false`. **S2 is void, so no repair is licensed** — but the calibration
reads the **physical file**, not the plan, and **must state that explicitly in its output**, so no
later reader assumes the plan pointer was the source. Reading around a known-defective pointer is
acceptable **only when it is disclosed**; undisclosed, it is the D4 failure again.

---

## R5-1. ⭐ (a) The scale-aware bound — and the honest limit of what two points support

> ⚠️ **SUPERSEDED IN PART by §R5-1.0.c — read that first.** The table and exponent below were the
> pre-ruling framing; **the two rows are cross-stratum and the derived magnitudes are withdrawn.**
> Retained only so the correction has its referent. **The design conclusion — that the bound must be
> scale-aware and that `d_model` must be *measured* — is unchanged and is if anything stronger,
> since `d_model` is now known to be entirely unmeasured rather than roughly known.**

**The finding to design against:** ~~collision density is **not a constant of the generator**; it
grows with games mined.~~ **Amended:** whether density grows with games mined is **exactly what the
sweep must establish** — the apparent growth below is confounded with the stratum (§R5-1.0.c). What
*is* established a priori is that a **linear-in-`n` bound must eventually fire** for any nonzero
revisit rate.

| corpus | games `G` | density `d` | ⚠️ |
|---|---|---|---|
| ~~base calibration~~ | ~~858~~ | ~~0.181%~~ | **S1**, and the rate is S1's *banked* 1/551; S1's full-corpus rate is **0.074%** |
| ~~S2 (governed scale)~~ | ~~5,340~~ | ~~2.636%~~ | **S2** — a different stratum and a different mining predicate |

~~`G` grew 6.22×; `d` grew 14.56× … `d ∝ G^1.46`.~~ **WITHDRAWN (§R5-1.0.c):** that contrast reads
a scale effect off a cross-stratum comparison. No exponent is currently supported by any data.

⚠️ **The original caveat stands and is now doubled.** Two points could not have fixed an exponent
in any case; and these two are not even two points on one curve. **The whole failure being fixed
here was a bound calibrated at one scale and applied at another — the fix must not repeat it with
one extra point, still less with one point per population.** So:

**R5-1.1 — REQUIRED PRE-RUN: a counts-only density sweep, ≥4 scales, ENTIRELY WITHIN S2.** Re-mine
the **already generated** 5,340 S2 games at **`G ∈ {500, 1000, 1500, 3000, 5340}`** — five scales,
`G` in **games GENERATED** per §R5-1.0.a, the extra point placed to characterise the structural
break at the banked/extension boundary (§R5-1.0.d) — and count collisions at each. No
generation, no scoring, no champ picks — **counts only**, the class
[`PREREG_FAILURE.md`](../PREREG_FAILURE.md) §3.3 established as non-leaking. Emits
`RUN/DENSITY_SWEEP.json`: per `G`, the positions mined, collisions found, density, and the
**collision-depth histogram** (§R5-2 needs it).

**R5-1.2 — the bound's FORM, fixed now; its VALUE, set from the sweep.** The bound is on the
**density at the governed scale**, not on a fraction of `n`:

```
bound(G_governed)  =  d_model(G_governed) x M
```

where `d_model` is fitted from the sweep and `M` is a **pre-committed multiple** of the modelled
density. `M` is the one number chosen before the sweep runs, and it is **committed in this DESIGN
before any `d` is fitted**: **`M = 3`.** *(Rationale: R4's bound sat at 2.8× the calibration
density and was defeated by a 14.6× scale shift, not by a 2.8× fluctuation. A multiple of the
**modelled** density absorbs ordinary Poisson noise — at the observed counts, 3× is ≈4–5σ — while
still failing a corpus whose degeneracy departs from the model, which is the event worth voiding
on.)*

**R5-1.3 — the saturation guard, which is the real bar.** A model-relative bound cannot catch a
corpus that is *uniformly* degenerate — if `d_model` itself is large, `3 × d_model` is a licence
to proceed on a corpus that is mostly transpositions. So, independently:

> **If `d_model(G_governed) > 5%`, the corpus design is VOID before it is built** — no bound
> applies, and the answer is a ply-floor (§R5-2) or fewer games, never a bigger bound.

~~The illustrative curve puts `d` at 6.6% by 10,000 games and 18% by 20,000 — i.e. the 5% guard
binds not far above the scale R4 already reached.~~ ⚠️ **WITHDRAWN with the exponent it was
extrapolated from (§R5-1.0.c).** No projection of `d` beyond the measured scales is currently
supported by anything. **The guard itself is unaffected and is not a projection:** it is a bar on
the *measured* `d_model(G_governed)`, and it fires or does not fire on the sweep's own output. The
claim it was illustrating — *"rung 3 cannot be bought by scaling the corpus"* — is now **an open
question the sweep answers**, not a conclusion the design may assume. Stating it as settled before
the measurement would be the R4 bound's error in the opposite direction.

## R5-2. ⭐ (b) The mining ply-floor — a new knob, and a first-class estimand change

**All 30 collisions, both strata, were at ply 2.** A `--min-ply k` predicate removes exactly the
region where boards are scarce and revisits are near-certain.

**R5-2.1 — the knob does not exist; the data for it does.** Verified: `run_census.py` has
`--max-per-game` and **no ply predicate**; `build_positions.py` carries `ply` on every row
(alongside `phase_bucket`, `tercile`) and **filters on none of them**. **W-item R5-W1:
`--min-ply` on `run_census.py` and `build_positions.py`**, recorded in `POSITIONS_PLAN.json` and
asserted by a gate. A new knob, not a new instrument.

**R5-2.2 — `k` is chosen FROM THE DATA, from a committed rule.** The prior from current evidence
is `k = 3` (it removes 100% of the 30 observed collisions). But `k = 3` is fitted to collisions at
**one** scale, and deeper plies will begin colliding as `G` grows — so the committed rule is:

> ⚠️ **R10, on the record: this rule had exactly ONE reachable answer.** "Smallest floor clearing
> the guard, with supply above the floor" selects `k = 0` for **any** corpus that clears at `k = 0`
> — and the supply floor is itself derived from `k = 0`'s supply. The outcome (`k = 0`) is right
> and §R5-FINAL.a's estimand argument is right, but **presenting it as a discretionary "bad trade"
> obscured that the pre-registered rule could not have returned anything else.** A selection rule
> with one reachable value is a constant wearing a rule's clothes.
>
> **`k` = the smallest ply floor such that `d_model(G_governed | ply ≥ k) ≤ 5%` AND the retained
> capped-ply supply still meets the floor in `FLOORS.json`** — both read off `DENSITY_SWEEP.json`'s
> depth histogram. If no `k` satisfies both, **rung 3 is not affordable by re-mining** and the
> successor stops rather than widening the bound.

**R5-2.3 — ⚠️ THE ESTIMAND CHANGES, and this is disclosed first-class, not in a footnote.**
With a ply-floor the measured population is **tied capped plies at ply ≥ `k`**, not *tied capped
plies*. The arbiter fires at ply 2 in real play; excluding those plies **excludes a real part of
its firing distribution**. Therefore, on **every** branch of the successor's read rule:

- the statistic is named **`Δ_ora(ply ≥ k)`**, never bare `Δ_ora`;
- **no result may be generalised to all tied plies**, and the pre-registered multipliers
  (1.400 legacy, 1.244 corrected) were derived on the **unfloored** population — so a comparison
  against them carries an explicit population-mismatch rider;
- the read-out reports **what fraction of capped plies the floor removed**, so the reader can see
  the size of the exclusion.

**R5-2.4 — the supply risk is real and must be measured, not assumed.** It is tempting to assume
ply-2 plies are rare among *capped* plies. The evidence points the other way: **29 of S2's
exclusions were capped ply-2 positions**, so ply 2 evidently produces capped plies in quantity —
plausibly because a near-empty board offers many symmetric placements of equal value, which is
exactly what makes a large tie set. **A ply-floor may therefore cost a large fraction of rung 3's
supply.** `DENSITY_SWEEP.json`'s histogram settles it before anything is priced.

## R5-3. (c) probe → carry, iterated to a fixed point

R4-0.2's loop ran **once** and pre-registered `residual = 0`, which
[`ADJUDICATION_R4_GATES.md`](../ADJUDICATION_R4_GATES.md) ruling 3 showed is **unreachable by
construction**: excluding rids admits positions the probe never saw, so a single pass leaves a
residual on a perfectly healthy corpus (it did, on both strata).

**The loop:** probe → gate → apply exclusions → re-probe → … until **`residual == 0`**, with
**`max_iterations = 5`**. Non-convergence at the cap is **fail-closed**: the stratum is **VOID**,
not "carried at iteration 5". The gate records `n_iterations` and the per-iteration exclusion
counts, and the bound of §R5-1.2 is evaluated on the **fixed point's cumulative total**.

## R5-4. (d) The 5,340 S2 games are RETAINED INPUT

**The same counts-only argument that let R4 retain band 135e9** ([`PREREG_FAILURE.md`](../PREREG_FAILURE.md)
§3): the S2 games were **never scored** — no `arb`, `ora`, `Δ` or CI exists for any position built
from them — and only structure counts were read. The **void attached to the R4 stratum and its
read rule, not to the games.**

⚠️ **This corrects a line in [`PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md) §5** ("the
extension band's S2 sub-range is spent; a successor claims fresh seeds"), which was over-strict
and is amended there. **What is spent is the R4 S2 *stratum* — the positions built under R4's
rule — not the substrate.** Re-mining the same games under a **ply-floor** produces a *different
position set* from the same games, which is the intended use and is not a re-read of anything.

**Conditions:** the retained games enter R5's gates **fresh and pre-cleared of nothing** — R4's
gate **failed**, so no position built from them ever passed anything; and `CORPUS_UNION.json`
(R4-0.5's shape) records origin commit, per-file sha256 and retained/fresh counts.

## R5-5. ⛔ SUPERSEDED by §R5-FINAL.g (N7)

> **This section's cost table priced `N ∈ {700, 1,100}` — both superseded by the realized
> `n₂ = 1,060`, and its ≈197–309 wh conflicted with §R5-FINAL.g's ≈211–300 on the same page.**
> **Two cost tables with different totals in one document is exactly the drift the house rule
> against carrying numbers in prose exists to prevent.** The figure of record is **§R5-FINAL.g**;
> the table below is struck.

| ~~item~~ | ~~worker-h~~ |
|---|---|
| ~~density sweep + census (counts only)~~ | ~~≈2~~ |
| ~~champ picks~~ | ~~2.7 – 4.2~~ |
| ~~pricing, `M = 32`~~ | ~~192.5 (`N`=700) – 302.5 (`N`=1,100)~~ |
| ~~**TOTAL**~~ | ~~**≈197 – ≈309**~~ **→ see §R5-FINAL.g: ≈211.4 – 299.6 at `n₂` = 1,060** |

**No generation.** R4 spent ≈**500 worker-h** generating those 5,340 games; retaining them is the
entire saving, and it is why the successor is cheap. ⚠️ **Contingency:** if §R5-2's ply-floor cuts
supply below the floor, generation returns to the bill at the R4-2.2 rates — and per §R5-2.2 the
correct response may be to stop rather than to buy more games, since §R5-1.3's guard tightens as
`G` grows.

## R5-6. ⭐ (e) The scope-marker taxonomy — so the per-stratum-void question cannot recur

R4's ambiguity existed because `G-DISJOINT` was **unmarked** and the binding taxonomy had no cell
for "one gate, per-stratum conjunct, one stratum void". Fixed prospectively and programme-wide:

> **Every gate row carries an explicit scope marker. An unmarked gate is a DRAFTING DEFECT that
> must be fixed before the blind commit — never adjudicated at read time.**

| marker | meaning | on a single-stratum failure |
|---|---|---|
| `[RUN]` | whole-run conjunct (cross-stratum quantities) | the **run** fails; no stratum is readable |
| `[S1]` / `[S2]` | evaluated on that stratum only | binds only the rungs whose cells live there |
| `[PER-STRATUM]` | evaluated separately per stratum | **that stratum** voids; the other **remains readable** — stated in the row, not inferred |

**A gate with conjuncts of mixed scope must be SPLIT into separately-named gates**, one per scope
— which is what `G-DISJOINT` should always have been: its cross-stratum conjuncts
(`strata_root_overlap`, `s1_vs_s2`) are `[RUN]`, its per-stratum bound is `[PER-STRATUM]`, and
mixing them in one row is what made the void's scope arguable. R5 has one stratum, so this costs
it nothing; it is written for the next multi-stratum prereg.

### R5-6.1 — the second drafting fix: acceptance audits carry an EXISTENCE-TIME marker

R4 carried **two** texts for what the pre-scoring audit covers — §9 4b's **enumeration** and §8's
verbatim class fix (*"EVERY address named anywhere in READ_RULE §2/§4/§5"*) — and they disagree
about addresses written by **scoring-time** emitters. It cost a failed 4b run
([`ADJUDICATION_R4_GATES.md`](../ADJUDICATION_R4_GATES.md) ruling 4, resolved in the pair's favour
by §1.5's structural test). Fixed here by construction:

> **Every address in this prereg carries an existence-time marker: `[pre-corpus]`,
> `[post-corpus]` or `[post-scoring]`. Each acceptance pass audits exactly the markers that can
> exist at its point in the sequence — statically against a fixture otherwise. No pass may demand
> an address its own position in the sequence makes impossible, and no address may be audited at
> neither pass.**

Concretely: a `[post-scoring]` address is audited **statically at the pre-commit pass** (fixture
schema, presence + type only) and **live at the read-out**, never live pre-scoring. ⚠️ The
fixture set must cover **every** `[post-scoring]` address — R4's covered the leg manifest and the
smoke manifest but **not `RUN_MANIFEST`**, which is how `G-SALT`'s primary ended up audited at
neither pass. A completeness assertion over the marker list, not a hand-maintained fixture list.

## R5-7. What is CARRIED unchanged

⭐ **THE GATE SET IS THE READ_RULE's §0 TABLE — this section no longer restates it (B3).** The two
files previously carried **different nines** (this one had `G-BITEXACT@HEAD` and omitted `G-ARMS`;
the read-rule did the reverse) and **both silently dropped `G-DISJOINT`, `G-BAND` and
`G-REPLICATE`**. There is now **one authority**, with `carried / restored / dropped + why` for
every gate: [`READ_RULE.md`](READ_RULE.md) §0.

Otherwise carried: rung 3's **estimand** (`Δ_ora`, `ora` adjudicates, `arb` rides) · the **branch
table** verbatim · the **power arithmetic** (`sd_Δ ∈ [0.9, 1.4]`, root bootstrap 2,000 reps,
significance once on the percentile CI) · **all eight riders**, including **`I7-draw-scope`** ·
the `I6` amendment draft · the `allow_null` closed list · fail-closed address discipline.

**`W9 (D-DRAW)` transfers here and IS FUNDED** — and, per R2, the claim of discharge is now
**enforced by a conjunct** (`G-DDRAW`: `d_draw_ran == true`). The previous revision claimed `I7`'s
conditional was discharged while the mechanical rule still permitted the exact R4 outcome; **either
the conjunct exists or the claim goes, and the conjunct exists.**

⛔ **The `ply ≥ k` population qualifier does NOT apply.** `k = 0` (§R5-FINAL.a), so the estimand is
the **unfloored** capped-tied-ply population and the 1.400/1.244 multipliers need no
population-mismatch rider. The qualifier returns only if a successor sets `k > 0`.

## R5-8. ⛔ SUPERSEDED by §R5-FINAL and the shipped READ_RULE (R11)

> **This section explained why the read-rule did not exist yet. It exists.** The calibration ran,
> `d_model`, `k` and `n₂` are all fixed, and [`READ_RULE.md`](READ_RULE.md) commits with this file.
> Retained only so the sequencing argument stays readable; **it describes no live state.**
>
> *(Original heading: "Why the READ_RULE is not written yet".)*

Three of its bars are numbers that do not exist: **`d_model` and the bound** (§R5-1.2, from the
sweep), **`k`** (§R5-2.2, from the depth histogram), and **`N_capped` / `FLOORS.json`** (from the
post-floor supply). **Writing them before the calibration is precisely the R4 failure.** Sequence:
`R5-W1` knob → density sweep (counts only) → fit → owner picks `N` → `FLOORS.json` →
**then** the mechanical READ_RULE → blind commit → run. The sweep is **counts-only and
outcome-free**, so it may run before the blind commit without spending blindness — the same
licence §R5-4 rests on.

## R5-9. Open for the owner

1. **Fund the successor at all?** ≈211–300 worker-h (§R5-FINAL.g), no generation — but §R5-1.3's guard may
   VOID the design before it is built, and §R5-2.2 may find no affordable `k`. **Both outcomes are
   possible answers, and neither is a strength result.**
2. **Accept the estimand change** to *tied plies at ply ≥ k* (§R5-2.3), with the multipliers'
   population mismatch carried on every branch?
3. **Ratify `M = 3` and the 5% saturation guard** — committed here **before** any density is
   fitted, which is what makes them bars rather than accommodations.
