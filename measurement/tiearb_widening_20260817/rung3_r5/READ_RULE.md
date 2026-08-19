# RUNG 3 (`J > 4`) — MECHANICAL READ RULE, rev R5.1

> **STATUS: PREREGISTRATION PAIR, AMENDED AFTER `REVIEW_R2.md` (FAIL: 6 BLOCKING, 11 REQUIRED).
> NOT LAUNCHED. NO POSITION SCORED. NO `Δ_ora`, `R_ora`, `Δ_arb` OR CI EXISTS.**
>
> Commits in **ONE commit** with [`DESIGN.md`](DESIGN.md) and `FLOORS_R5.json`, before the first
> scoring leg. **SINGLE USE, spent on landing.**
>
> **Parent chain by reference:** R3.3 (`../shared_run/` @ `604edc83`) → R4.5 (`../shared_run_r4/`)
> → this. `governance/PRODUCTION.yaml` untouched on every branch.

## §0 — THE CARRIED-GATE SET, reconciled explicitly (B3)

**The previous revision carried nine gates in one file and a different nine in the other, and
dropped three without a word.** Reconciled here; **this table is the authority and `DESIGN.md`
§R5-7 points at it rather than restating it.**

| gate | status in R5 | why |
|---|---|---|
| `G-LEAF`, `G-SALT`, `G-M`, `G-BACKEND`, `G-PREFIX`, `G-CRN`, `G-UNCAPPED`, `G-DRAW`, `G-ARMS` | **CARRIED** | unchanged in substance; addresses re-marked and, where R3.3 had a second address, restored (R1) |
| **`G-BITEXACT@HEAD`** | **CARRIED** | the rust ARB judge prices this run; its identity gate carries |
| **`G-DISJOINT`** | ⭐ **RESTORED, rid/root layers only** | R5 previously read this gate's *artifact* for a consistency check while abandoning its *conjuncts*. Its **zero-tolerance rid/root layers are the LEAKAGE guard** and are distinct from the digest bound that voided R4. The digest layer is **not** carried — R5's degeneracy quantity is same-band internal duplication (§2 `G-INTERNAL-DUPE`), which no cross-set comparison can see |
| **`G-BAND`** | ⭐ **RESTORED** | R9: with it dropped, nothing gated seed-range integrity, duplicate seeds, or the released-unused `136e9` band. R5 generates nothing, so its form is *retrospective*: the retained substrate's seeds must lie in the committed ranges |
| **`G-REPLICATE`** | ⛔ **DROPPED, deliberately** | its `(B ≤ 16, E = 16)` corner is **S1's** and S1 is not this run's stratum. Dropped **with this sentence** rather than silently — R2's objection was the silence, not the drop |
| `G-COMPLETE`, `G-FAILED`, `G-CORPUS`, `G-INTERNAL-DUPE`, `G-DDRAW`, `G-TWOBOX` | **R5-SPECIFIC** | §2 |

**Stratum keying (R8): `s2` EVERYWHERE.** The previous revision spelled new addresses `r5` while
every carried address used `s2`; under ABSENT IS FAIL one spelling had to fail. **`r5` appears in
no address in this pair.**

## §1 — Existence-time markers, and the pass that audits them (B6)

Every address below carries **exactly one** of `[pre-corpus]` · `[post-corpus]` · `[post-scoring]`.
**"as carried" is not a marker**; the previous revision used it for a six-gate row whose members
resolve to two different markers, and marked nothing outside §2 at all.

⭐ **THE ACCEPTANCE PASS (previously undefined, which left the marker machinery with no auditor):**

- **`A1` `[pre-corpus]`, before the blind commit** — static schema audit against committed
  fixtures for every `[post-corpus]` and `[post-scoring]` address; **key presence and JSON type
  only, no value computed, printed or stored.**
- **`A2` `[post-corpus]`, before the first scoring leg** — resolve every `[pre-corpus]` and
  `[post-corpus]` address **live**, primary **and** fallback independently.
- **`A3` `[post-scoring]`, before adjudication** — resolve the `[post-scoring]` addresses.
- **Completeness assertion, mandatory in each pass:** the union of addresses audited across
  `A1`+`A2`+`A3` **equals** the set of addresses named in this file. **No address may be audited
  at neither pass**, and no pass may demand an address its own position makes impossible.

## §2 — Gates. Any FAIL ⇒ `W-UNREADABLE`; nothing licensed

All gates are `[RUN]` in scope (R5 has one stratum); the marker column is the **existence-time**
marker.

| gate | marker | conjunct | address |
|---|---|---|---|
| ⭐ `G-CORPUS` | `[post-corpus]` | The corpus is **R4's post-exclusion S2 leg file, ADOPTED AS-IS**, plus R5's own exclusion list — **not a fresh re-mine.** Conjuncts: the physical leg's **sha256 == `92ba1ee2dfbfed91…`** (full sha in `FLOORS_R5.json`); the R4 exclusion list's **sha256** matches the committed one; `--max-per-game 3`, `--cap-j inf`, `min_ply == 0`; and `n_positions_after_r5_exclusions == 1060` | `RUN/CORPUS_R5.json::{leg_path, leg_sha256, r4_exclusion_list_sha256, n_in, n_excluded_r5, n_positions}` |
| ⭐ `G-INTERNAL-DUPE` | `[post-corpus]` | **(i) LIVE:** `d_internal ≤ 0.05` — the absolute saturation guard, computed **at run time from the physical leg**, never read from a frozen constant. **(ii) CONSISTENCY:** `n_dupe_groups == 3`, `n_dupe_positions == 6`, every member at **ply 2** and **137e9↔137e9 same-band**. A mismatch **RAISES** | `RUN/GATE_INTERNAL_DUPE.json::{n_positions, n_dupe_groups, n_dupe_positions, d_internal, ply_histogram, band_pairs, leg_sha256}` |
| `G-DISJOINT` | `[post-corpus]` | **rid and root layers ZERO on every comparison** — the leakage guard, carried from R4 §2b(i). ⛔ The **digest layer is NOT carried** (see §0) | `RUN/GATE_DISJOINT_R5.json::{passed, comparisons.<name>.layers.{a_root_id,b_rid}.n_intersection}` |
| `G-BAND` | `[post-corpus]` | every retained seed lies in a committed range — banked `[135000000350, 135000000849]` or extension `[137000000508, 137000005347]`; `n_out_of_band == 0`; `n_duplicate_seeds == 0`; **no seed from the released-unused `136e9` band** | `RUN/CORPUS_R5.json::{seed_ranges, n_out_of_band, n_duplicate_seeds, n_seeds_136e9}` |
| `G-COMPLETE` | `[post-scoring]` | `n_analysed ≥ 1007` (= `⌈0.95 × 1060⌉`), after exclusions and after §3's failed-record drop | `READOUT::widening.completion.s2_n` |
| `G-FAILED` | `[post-scoring]` | **(i)** `n_failed_rids / n_attempted ≤ 0.02`; **(ii)** any failed record whose class is **not** `WindowTruncationError` ⇒ **RAISE regardless of count**. ⚠️ `n_attempted` is **addressed** (R5) | `READOUT::widening.failed.{n_failed_rids, n_attempted, rate, by_class}` |
| `G-M` | `[post-scoring]` **+ `[post-corpus]`** | `m_worlds == 32` ∧ `b_ceiling_from_m == 16`. ⚠️ **NOT 128.** ⭐ **A `[post-corpus]` address is required (R1)** so the one constant this revision exists to correct halts the run **before** ~300 wh is spent, not after | **pre-leg:** `RUN/SMOKE_R5.json::resolved_config.m` · **post:** `RUN/RUN_MANIFEST_R5.json::{m_worlds,b_ceiling_from_m}` · **fallback:** `RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json::resolved_config.m` |
| `G-SALT` | `[post-scoring]` | `world_seed_salt == "tiletie-v1"`; **`deployed_cap_j == 4` (now ADDRESSED, R6)**; `cap_seed` present for every rid | `RUN/RUN_MANIFEST_R5.json::world_seed_salt` · `RUN/corpus/positions_s2/POSITIONS_PLAN.json::deployed_cap_j` · `…/ARMS.json::<rid>.cap_seed` · fallback `RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json::resolved_config.world_seed_salt` |
| `G-BACKEND` | `[post-scoring]` | `arb_backend == "rust"`; every `tier1-greedy/walled` leg resolves `rust`; `arb_legal_mask_cache == true` | `RUN/RUN_MANIFEST_R5.json::{arb_backend,resolved_backend_by_leg,arb_legal_mask_cache}` · fallback `…/manifest.json::resolved_config.legal_mask_cache` |
| ⭐ `G-DDRAW` | `[post-scoring]` | **`d_draw_ran == true`** — R2: the previous revision *claimed* W9 discharged `I7`'s conditional while the mechanical rule still permitted the R4 outcome. Either the conjunct exists or the discharge claim goes; **the conjunct exists** | `READOUT::widening.j_rider.d_draw.d_draw_ran` · `RUN/D_DRAW.json` |
| `G-LEAF`, `G-PREFIX`, `G-CRN`, `G-UNCAPPED`, `G-DRAW`, `G-ARMS`, `G-BITEXACT@HEAD` | `G-UNCAPPED` `[post-corpus]`; `G-DRAW` `[post-corpus]`; `G-BITEXACT@HEAD` `[pre-corpus]`; `G-LEAF`, `G-PREFIX`, `G-CRN`, `G-ARMS` `[post-scoring]` | carried verbatim from R3.3/R4, `<judge>` bound to `tier1-greedy`, stratum `s2` | as carried |
| `G-TWOBOX` | `[post-scoring]` | `../DEVIATIONS.md` §D1/§D3/§D4.13 as ruled | `RUN/MERGE_REPORT_s2.json` |

### §2.1 ⚠️ What the two degeneracy gates DO and DO NOT establish — stated, not implied

**The collision quantity for this corpus is already known** (3 groups / 6 positions), because the
calibration measured **the same physical file** R5 will score. ⇒ **Both gates are CORPUS-IDENTITY
checks, not discovery gates.** Their live content is *"the corpus is the one that was measured"* —
which is a real and falsifiable property (a different leg file, a re-mine, a truncated read all
fail it), and it is **all** they establish.

⛔ **The previous revision's `G-SATURATION` read `CALIBRATION.json::…d_model_at_governed` — a
constant committed with the pair, and the FITTED value the pair's own text calls vacuous. A gate
whose input is frozen before the run cannot fire.** `G-INTERNAL-DUPE` recomputes `d_internal` from
the leg at run time instead. **A relative bound (`M × d`) remains retired**: on a pre-measured
corpus it is satisfied by construction (DESIGN §R5-FINAL.b), and it returns only when a successor
GENERATES fresh games.

## §3 — The failed-record policy, authored pre-data — **EXPECTATION CORRECTED (B5)**

Whole-rid drop across both judges (D4.18); typed accounting printed whether or not anything fails;
bound `≤ 0.02` of attempted; **any non-`WindowTruncationError` class RAISES regardless of count.**

⛔ **CORRECTION, on the record.** The previous revision pre-registered that R5's capped plies
*"skew EARLY"* so exposure *"should be LOWER than S1's realized 0.30%"*. **Measured on this
corpus's own `ply` field: mean 69.15, median 68, max 142; 63.3% at ply ≥ 50; only 2.63% at
ply ≤ 2** — against S1's mean 66.50. **R5's corpus sits slightly DEEPER than S1's, in exactly the
region where `WindowTruncationError` fires (~70 tiles placed).**

⇒ **The pre-registered expectation is EQUAL-OR-HIGHER than S1's 0.30%, not lower.**

**The inferential error, named so it is not repeated:** the prose reasoned from the ply of the
three *collisions* — forced early by the birthday argument, since few distinct boards exist at
ply 2 — and generalised it to the ply of the *corpus*. **Where collisions happen is not where the
population lives.** Left uncorrected, a perfectly healthy elevated failure rate would have read as
"a surprise worth naming".

## §4 — Branch table

**CARRIED VERBATIM from R3.3 §5** — `X-CONFIRMED` · `X-ABOVE` · `X-PARTIAL` · `X-BELOW` ·
`X-FREE` · `X-INCONCLUSIVE`, the `R_ora` degenerate guard and its `Δ_ora`-only sub-table, the
`X-NOISE` rider, the three mandatory prints. **Not one threshold, sign or condition moves.**
Primary `Δ_ora` at capped plies, `ora` adjudicating, `arb` riding, significance once on the
percentile root bootstrap. All addresses `[post-scoring]`; stratum key `s2`.

**Power at `n₂ = 1,060`** (§R5-FINAL.c), printed beside the realized CI:

| prediction | `Δ_ora` | resolves at 2σ iff |
|---|---|---|
| legacy ×1.400 | +0.1382 | `sd_Δ ≤ 2.250` — whole bracket ✅ |
| corrected ×1.244 | +0.0842 | `sd_Δ ≤ 1.371` |
| 1.400 **vs** 1.244 | 0.054 | `sd_Δ ≤ 0.879` — **not separable**, carried blind spot |

`se(Δ_ora) = sd_Δ/√1060 ∈ [0.0276, 0.0430]`.

## §5 — Riders

**R1–R8 carried verbatim** (σ-inflation · translation · **`I7-draw-scope`** · two currencies ·
governance · open N4 waiver · phone out of scope · `|z| < 2` never "refuted"). `I7`'s
dedupe-partition conditional is **discharged by W9**, now enforced by `G-DDRAW` (§2). All rider
addresses `[post-scoring]`.

## §6 — What the read-out prints

The carried §7 list, plus: the supply chain from `CORPUS_R5.json`'s realized integers · `d_internal`
against 0.05 **with §2.1's statement that both degeneracy gates are corpus-identity checks** · the
dupe-group consistency result · the failed-record accounting against §3's **corrected** expectation ·
`D-DRAW`'s agreement rate under `I7` · the two-box merge report · the `A1`/`A2`/`A3` completeness
assertions · and the fitted `d_model(G) = a·G^b` **REPORTED with `r² = 1.0` marked VACUOUS and
explicitly NOT the bound**.

## §7 — Spent

Single-use. Six-touch close-out, then `python3 scripts/doc_lint.py`. Any successor that **generates**
fresh games needs a fresh pair, a fresh band, and a **live relative bound**.
