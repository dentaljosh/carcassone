# RUNG 3 (`J > 4`) — MECHANICAL READ RULE, rev R5

> **STATUS: PREREGISTRATION DRAFT, READY FOR BLIND COMMIT. NOT LAUNCHED. NO POSITION SCORED.
> NO `Δ_ora`, `R_ora`, `Δ_arb` OR CI EXISTS.**
>
> Commits in **ONE commit** with [`DESIGN.md`](DESIGN.md) and `FLOORS_R5.json`, before the first
> scoring leg. **SINGLE USE, spent on landing.** No re-read, no second adjudication, no top-up.
>
> **Parent chain by reference:** R3.3 (`../shared_run/` @ `604edc83`) → R4.5 (`../shared_run_r4/`)
> → this. Every rung-3 estimand, branch condition, rider and power figure is **CARRIED**; §0 lists
> what R5 changes.
>
> `governance/PRODUCTION.yaml` untouched on every branch. No claim minted. No strength row.

## §0 — What R5 changes, and what it carries

**CARRIED UNCHANGED** (binding in their R3.3/R4 wording, not restated): §1 address discipline and
**ABSENT IS FAIL** · the `allow_null` closed list · §3's power arithmetic (`sd_Δ ∈ [0.9, 1.4]`,
root bootstrap 2,000 reps seed `20260819`, significance **once** on the percentile CI) · **§5's
rung-3 branch table verbatim** (`X-CONFIRMED` · `X-ABOVE` · `X-PARTIAL` · `X-BELOW` · `X-FREE` ·
`X-INCONCLUSIVE`, the `R_ora` degenerate guard and its `Δ_ora`-only sub-table, the `X-NOISE`
rider, the three mandatory prints) · **all eight riders R1–R8, including `I7-draw-scope`** ·
`G-LEAF`, `G-SALT`, `G-M`, `G-BACKEND`, `G-PREFIX`, `G-CRN`, `G-UNCAPPED`, `G-DRAW`, `G-ARMS` ·
§7's gate-inputs-only rule on `W-UNREADABLE`.

**R5 CHANGES, all recorded in [`DESIGN.md`](DESIGN.md) §R5-FINAL:** the ply floor (`k = 0`) · the
exclusion bound's form (`G-SATURATION` replaces the circular relative bound) · `n₂` and the
completion floor, from **realized** supply · the failed-record bound, authored pre-data · **W9
`D-DRAW` funded** · existence-time markers on every address.

## §1 — Existence-time markers

Every address carries one: **`[pre-corpus]`** · **`[post-corpus]`** · **`[post-scoring]`**
(R5-6.1). **An unmarked address is a drafting defect, fixed before the blind commit, never
adjudicated at read time.** Each acceptance pass audits exactly the markers that can exist at its
point in the sequence — statically against a fixture otherwise. **No pass may demand an address its
own position makes impossible, and no address may be audited at neither pass.**

## §2 — Gates. Any FAIL ⇒ `W-UNREADABLE`; nothing licensed

Scope markers per R5-6: **`[RUN]`** (whole-run) · **`[PER-STRATUM]`** (R5 has ONE stratum, so every
gate here is `[RUN]` in effect; the marker is carried so the taxonomy stays total). **An unmarked
gate is a drafting defect.**

| gate | marker | conjunct | address |
|---|---|---|---|
| `G-CORPUS` | `[post-corpus]` | the corpus is the **retained S2 substrate**, re-mined: `n_positions == 1064`, `--max-per-game 3`, `--cap-j inf`, **`min_ply == 0`**; and the physical leg file is the source, **not** the defective `POSITIONS_PLAN` `files` block (§0 note) | `RUN/corpus/positions_r5/POSITIONS_PLAN.json::{n_positions,cap_j,uncapped,max_per_game,min_ply}` |
| ⭐ `G-SATURATION` | `[post-corpus]` | **`d_measured(G=5340) ≤ 0.05`** — the ABSOLUTE saturation guard, the live collision gate. Realized **0.002820** ⇒ clears **17.7×** | `RUN/CALIBRATION.json::by_ply_floor.0.d_model_at_governed` |
| ⭐ `G-COLLIDE` | `[post-corpus]` | the run's realized digest-collision count **equals the calibration's `3`**, and every collision is at **ply 2**. ⚠️ **A MISMATCH RAISES** — it would mean the corpus is not the one the calibration measured | `RUN/GATE_DISJOINT.json::digest_exclusions.r5.{n_excluded,ply_histogram}` |
| `G-COMPLETE` | `[post-scoring]` | `n_analysed ≥ 1011` (= `⌈0.95 × 1064⌉`), evaluated **after** exclusions and after the §3 failed-record drop | `READOUT::widening.completion.r5_n` |
| ⭐ `G-FAILED` | `[post-scoring]` | **(i)** `n_failed_rids / n_attempted ≤ 0.02`; **(ii)** **any** failed record whose diagnostic class is **not** `WindowTruncationError` ⇒ **RAISE and escalate, regardless of count** | `READOUT::widening.failed.{n_failed_rids,rate,by_class}` |
| `G-M` | `[post-scoring]` | **`m_worlds == 32`** and `b_ceiling_from_m == 16`. ⚠️ **NOT 128** — see §0 note | `RUN/RUN_MANIFEST_R5.json::{m_worlds,b_ceiling_from_m}` |
| `G-SALT` | `[post-scoring]` | `world_seed_salt == "tiletie-v1"`; `deployed_cap_j == 4`; `cap_seed` present for every rid | `RUN/RUN_MANIFEST_R5.json::world_seed_salt` · `…/ARMS.json::<rid>.cap_seed` |
| `G-BACKEND` | `[post-scoring]` | `arb_backend == "rust"`; every `tier1-greedy/walled` leg resolves `rust`; `arb_legal_mask_cache == true` | `RUN/RUN_MANIFEST_R5.json::{arb_backend,resolved_backend_by_leg,arb_legal_mask_cache}` |
| `G-LEAF`, `G-PREFIX`, `G-CRN`, `G-UNCAPPED`, `G-DRAW`, `G-ARMS` | as carried | **carried verbatim from R3.3/R4**, with `{s1,s2}` read as this run's single stratum and `<judge>` bound to `tier1-greedy` | as carried |
| `G-TWOBOX` | `[post-scoring]` | the D1 two-box layer's conjuncts as ruled in `../DEVIATIONS.md` §D1/§D3/§D4.13: `execution` per-chunk classification, `carc_rs_build` **equal across boxes**, `carc_rs_binary_sha` **constant within each box**, merge `preserved_from_existing` recorded | `RUN/MERGE_REPORT_r5.json` |

⚠️ **`G-SATURATION` is the live collision gate and `G-COLLIDE` is a consistency check — and the
distinction is stated because the alternative would have been PASS-ALWAYS.** R5-1.2's relative
bound `M × d_model` is **circular on a corpus already measured**: `bound = 3 × (3/1064) × 1064 = 9`
against a realized 3, i.e. **satisfied by construction with exactly 3× headroom, incapable of
firing.** It is **retired for this run** (DESIGN §R5-FINAL.b). The absolute 5% guard is not
circular — it is an external bar the measurement either clears or does not — and it is what
governs. **The relative bound returns the moment a successor GENERATES fresh games**, where `d` at
the new scale is genuinely unmeasured.

## §3 — The failed-record policy, authored PRE-DATA

**Whole-rid drop, both judges**, per `../DEVIATIONS.md` §D4.18 — it is what `G-ARMS` implies (a rid
with a valueless arm is not analysable, and the paired contrast needs both sides). Typed accounting
printed **whether or not any failure occurred**: `n_failed_rids`, per rid `{judge, legs,
diagnostic_class}`, and the pointer to `measurement/window_truncation_20260813/`.

**The bound is authored here, before any R5 datum exists** — which is the only way a bound of this
shape is worth anything (D4.18): **`n_failed_rids / n_attempted ≤ 0.02`**, and **any non-`WindowTruncationError`
class RAISES regardless of count.**

⭐ **Stated expectation, pre-data, so the realized rate is legible rather than reassuring.**
`WindowTruncationError` fires at **extreme board extents** (late game, ~70 tiles placed). R5's
population is **capped plies** — tied plies with >4 distinct afterstates — and the calibration
shows those skew **EARLY**: all three digest collisions are at **ply 2**, consistent with the
mechanism that a near-empty board offers many equal-valued symmetric placements, which is what
makes a large tie set. ⇒ **R5's window-truncation exposure should be LOWER than S1's realized
0.30% (4/1,344), not higher.** A realized rate at or above S1's would be a surprise worth naming
in the read-out even while passing the bound.

## §4 — Branch table

**CARRIED VERBATIM from R3.3 §5** — `X-CONFIRMED` · `X-ABOVE` · `X-PARTIAL` · `X-BELOW` ·
`X-FREE` · `X-INCONCLUSIVE`, the `R_ora` degenerate-denominator guard and its committed
`Δ_ora`-only sub-table, and the `X-NOISE` rider. **Not one threshold, sign or condition moves.**

Primary: **`Δ_ora` at capped plies**, `ora` adjudicating, `arb` riding. Significance **once**, on
the percentile root bootstrap.

**Power at the realized `n₂ = 1,064`** (§R5-FINAL.c), printed beside the realized CI:

| prediction | `Δ_ora` | resolves at 2σ iff |
|---|---|---|
| legacy ×1.400 | +0.1382 | `sd_Δ ≤ 2.254` — **whole bracket** ✅ |
| corrected ×1.244 | +0.0842 | `sd_Δ ≤ 1.373` — **most of the bracket**, fails only above 1.373 |
| 1.400 **vs** 1.244 | Δ = 0.054 | `sd_Δ ≤ 0.881` — **NOT separable**, the carried blind spot |

`se(Δ_ora) = sd_Δ/√1064 ∈ [0.0276, 0.0429]`. **Essentially unchanged from R4's `n₂ = 1,100`** —
the realized supply costs 0.023 of `sd_Δ` headroom on the corrected prediction and nothing on the
legacy one.

## §5 — Riders, all carried

**R1–R8 verbatim** (σ-inflation · translation caveat · **`I7-draw-scope`** · two currencies ·
governance · the open N4 waiver · phone out of scope · `|z| < 2` is never "refuted").

⭐ **`I7` binds here and R5 DISCHARGES it rather than inheriting it again.** R4 skipped W9 as moot
when S2 voided, leaving `I7`'s **dedupe-partition conditional** — that the python afterstate key and
rust `string_representation` induce the same partition — **UNMEASURED**, with the successor
inheriting the obligation. **W9 `D-DRAW` is FUNDED in R5** (≈2 worker-h, the corpus already
exists): it replays each capped ply and calls `tiearb_probe(j=4, salt="tiearb2-deploy-v1")`,
emitting `RUN/D_DRAW.json::{n_checked, n_agree, agreement_rate, n_unreconstructible, git_rev}`,
surfaced at `widening.j_rider.d_draw.*`. **No playouts, no outcome statistic; non-adjudicating; it
may never correct, reweight or re-scale `Δ_ora`.** If it does not run, `d_draw.*` is `null` with
`d_draw_ran == false` under the `allow_null` closed list, and `I7` rides **unmeasured** exactly as
it did in R4 — but the funded path is the ruling.

## §6 — What the read-out prints

Everything in the carried §7, plus: **the full supply chain from `CALIBRATION.json`'s realized
integers** (§R5-FINAL.c) · `G-SATURATION`'s realized `d` against 0.05 **and** the note that the
relative bound was retired as circular · `G-COLLIDE`'s realized count against the calibration's 3,
with the ply histogram · the failed-record accounting with §3's stated expectation · **`D-DRAW`'s
agreement rate under `I7`** · the two-box merge report · and the **fitted `d_model(G) = a·G^b`
(`b ≈ 0.906`) REPORTED with its `r² = 1.0` marked VACUOUS** — two points determine a line exactly,
and the fit is **not** the bound.

## §7 — Spent

Single-use. On landing: the six-touch close-out, then `python3 scripts/doc_lint.py`. Any successor —
including one that generates fresh games — needs a fresh pair, a fresh band, and a **live**
relative bound.
