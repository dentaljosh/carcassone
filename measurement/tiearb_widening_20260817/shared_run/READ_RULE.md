# TIE-ARBITER WIDENING — SHARED RUN, MECHANICAL READ RULE (rungs 2 + 3)

> **STATUS: BLIND PREREGISTRATION, DRAFT. NOT LAUNCHED. NO NUMBER OF THIS RUN EXISTS.**
>
> ⚠️ **BLIND-ORDER REQUIREMENT — NOT YET SATISFIED.** Drafted in an isolated worktree under
> the main-tree commit freeze. **This file and [`DESIGN.md`](DESIGN.md) must be committed to
> the MAIN tree, in ONE commit, before the band is claimed and before one position is
> scored.** A worktree commit does not satisfy blindness.
>
> **SINGLE USE. SPENT ON LANDING.** One adjudication, one analyzer invocation, one read-out
> covering **both** rungs. No re-read, no second pass, no top-up at any `z`. Any extension
> needs a fresh corpus, a fresh band and a fresh read rule. The only pre-licensed top-up is
> DESIGN §3's **blind corpus top-up**, which expires the moment the first scoring leg starts.
>
> `governance/PRODUCTION.yaml` is **untouched on every branch**. No branch flips anything; at
> most a branch licenses a *DESIGN*. No claim id is minted. No strength row is written.

`RUN` = `measurement/tiearb_widening_20260817/shared_run/`.
`READOUT` = `RUN/verdicts/READOUT.json` (written by the W3 analyzer, one invocation).

---

## 1. Address discipline and fail-closed semantics

1. **Every gate and every branch input is named below by its exact address.** An address is
   a file path plus a dotted key path into that file.
2. **ABSENT IS FAIL.** If a named address does not resolve — file missing, key missing, key
   `null` — the gate **FAILS**. Absent is never a pass, never "assume healthy", never
   "recompute by hand and proceed".
3. **Fallback addresses are pre-registered, not improvised.** Where a fallback is listed, the
   reader tries the primary first, then the fallback, and the read-out **must print
   `resolved_at: <address>`** for every gate — naming *which* address answered — or
   `UNRESOLVED`. A gate answered only by a fallback is reported as such on the branch line.
4. **No address may be invented at read time.** If a gate's inputs are unreachable at every
   pre-registered address, the correct answer is `W-UNREADABLE`, not a new address.
5. **Structural test, applied to every gate in §2 and written into its own row:** *would this
   gate fail on a healthy run?* If yes, it is an instrument defect and must be fixed **before**
   the run, never adjudicated around. (Three JCZ gates and PLAN_J §6's `G-CAP` failed this
   test; `G-CAP` is retired in DESIGN §5.)

---

## 2. Gates. Any FAIL ⇒ `W-UNREADABLE` for the affected rung; nothing is licensed

S1 gates bind **both** rungs (the shared cell lives there). S2 gates bind **rung 3 only** —
an S2 failure leaves rung 2 fully readable, and vice versa.

| gate | conjunct (all must hold) | primary address | fallback | on a healthy run |
|---|---|---|---|---|
| `G-BAND` | band row exists in `governance/BAND_REGISTRY.csv` **before** game 1; every generated deck seed ∈ `135000000000+0…+849` (∪ `136000000000+0…+199` iff the blind corpus top-up was exercised) | `RUN/corpus/GEN_MANIFEST.json::band.{seed_start,seed_end,n_games}` | `RUN/corpus/GEN_MANIFEST.json::seeds_used` (explicit list) | **PASSES** — the band is claimed by the launcher before generation |
| `G-DISJOINT` | `ok == true`; 0 shared rid / root / board digest with `tiletie_pricing_20260812`, `tiearb2_20260816`, `EXCLUDE_RIDS_all.txt`; **and** S1∩S2 root overlap `== 0` | `RUN/GATE_DISJOINT.json::{ok, overlap_counts, strata_root_overlap}` | — (no fallback: a missing gate file is a FAIL) | **PASSES** — fresh band + disjoint stratum split |
| `G-LEAF` | leaf hash of record `a36d2e15a3b3d71d` resolves and asserts | `RUN/RUN_MANIFEST_S1.json::preflight.checks.leaf_hash.ok` (and `_S2`) | `RUN/RUN_MANIFEST_S1.json::preflight.checks.leaf_hash.hash` compared literally | **PASSES** |
| `G-SALT` | `world_seed_salt == "tiletie-v1"`; `deployed_cap_j == 4`; `cap_seed` present for **every** rid | `RUN/RUN_MANIFEST_S1.json::world_seed_salt`, `RUN/corpus/positions_s1/POSITIONS_PLAN.json::deployed_cap_j`, `…/ARMS.json::<rid>.cap_seed` | per-leg `…/tier1-greedy/walled/leg*/manifest.json::config.world_seed_salt` | **PASSES** — module constant, not a flag |
| `G-M` | `m_worlds == 128` and `b_ceiling_from_m == 64` on S1; `m_worlds == 32`, `b_ceiling_from_m == 16` on S2 | `RUN/RUN_MANIFEST_{S1,S2}.json::{m_worlds,b_ceiling_from_m}` | per-leg `manifest.json::config.m` | **PASSES** |
| `G-BACKEND` | `arb_backend == "rust"`; **every** `tier1-greedy/walled` leg in `resolved_backend_by_leg` reads `rust`; `arb_legal_mask_cache == true` | `RUN/RUN_MANIFEST_{S1,S2}.json::{arb_backend,resolved_backend_by_leg,arb_legal_mask_cache}` | per-leg `manifest.json::{driver,legal_mask_cache}` | **PASSES** — the launcher refuses to fall back silently |
| `G-BITEXACT@HEAD` | Phase A's identity gate re-run at the run's `git_rev`, **with the legal-mask cache ON**; `n_compared ≥ 1024`; `n_identical == n_compared` | `RUN/GATE_BITEXACT_HEAD.json::{git_rev,n_compared,n_identical,legal_mask_cache,ok}` | — | **PASSES** — 15,360/15,360 at Phase A on this wheel. ⚠️ run with `--no-legal-mask-cache` it would fail on a healthy run (57/15,360 move); that spelling is forbidden |
| `G-PREFIX` | worlds `0…31` byte-equal `world_seed(rid, j, "tiletie-v1")`; `M` absent from the derivation | `RUN/…/tier1-greedy/walled/leg*/manifest.json::seeds.prefix_ok` | `…::seeds` (compare the first 32 entries literally) | **PASSES** — `M` never enters `sha256(tag\|rid\|j\|salt)` |
| `G-CRN` | smoke witness `true`; **100%** of ARB records `crn_verified`; one witness kind per judge (never `world_deck_hash` mixed with `afterstate_deck_hash` inside one judge's legs) | `RUN/SMOKE_MANIFEST_S1.json::crn_cross_leg_identical`, `RUN/…/leg*/manifest.json::{n_ok,n_crn_verified,crn_witness}` | `READOUT::widening.gates.crn.{ok,witness_kinds}` | **PASSES** |
| `G-UNCAPPED` | `uncapped == true` and `cap_j == null` on **both** strata; for every rid `arms == arms_full` | `RUN/corpus/positions_{s1,s2}/POSITIONS_PLAN.json::{uncapped,cap_j}`, `…/ARMS.json::<rid>.arms_full` | `READOUT::widening.gates.uncapped` | **PASSES** — built with `--cap-j inf` |
| `G-DRAW` (replaces the retired `G-CAP`) | for every rid: `subset_j4 ⊆ arms_full`; `len(subset_j4) == min(4, 1+len(candidates))`; re-running `build_positions._seeded_cap(rid, candidates, 4)` at the run's `git_rev` reproduces `subset_j4` **exactly**; `subset_j4_id` matches the recomputed digest; `n_mismatch == 0` | `RUN/GATE_DRAW.json::{n_checked,n_mismatch,ok,git_rev}` | `RUN/corpus/positions_{s1,s2}/ARMS.json::<rid>.{subset_j4,subset_j4_id}` recomputed by the reader | **PASSES** — a pure function of `(rid, candidates)`. ⚠️ It does **NOT** assert agreement with the deployed rust draw; that conjunct is retired as unsatisfiable (DESIGN §5) and its absence is carried as rider `I7` |
| `G-ARMS` | every full-set arm scored on **all** `M` worlds — per-arm, not per-ply; `n_arms_complete == n_arms`; `--include-partial-arms` NOT used | `READOUT::widening.gates.arms.{n_arms,n_arms_complete,include_partial,ok}` | `RUN/verdicts/per_position_{s1,s2}.jsonl` (per-arm world counts) | **PASSES** |
| `G-COMPLETE` | S1 scored positions `≥ 1,283` (95% of 1,350); S2 scored capped positions `≥ 1,045` (95% of 1,100); mining ceilings honoured (≤4 tied plies/root S1, ≤3 capped plies/root S2) | `READOUT::widening.completion.{s1_n,s2_n,s1_max_per_root,s2_max_per_root}` | `RUN/verdicts/per_position_{s1,s2}.jsonl` line counts + `root_id` grouping | **PASSES** |
| `G-REPLICATE` | the `(B ≤ 16, E = 16)` sub-read on **S1** lands inside the **2×-inflated** 2σ envelope of Stage-1b's ladder at **every** rung `B ∈ {1,2,4,8,16}`, **and** `z(arb_16) ≥ +2.0` | `READOUT::widening.stage1_replication.{per_rung_z, arb16_z, envelope_inflation}` | `RUN/verdicts/per_position_s1.jsonl` (recompute) | **PASSES** if the instrument is sound. **A FAIL means `UNINTERPRETABLE`, NEVER `FAIL-the-lever`** — the fresh corpus is a different population and no widening statement may be made from it. Report the naive-σ verdict alongside the inflated one; a rung that fails naive but passes inflated is a **mandatory caveat on every branch** |

**Precedence.** Gates are evaluated **before** any branch statistic is read. If any gate
binding a rung FAILS, that rung's answer is `W-UNREADABLE` and **no branch of that rung
fires** — not even a "for information" one.

---

## 3. The power arithmetic, restated as the bars are read

- **Rung 2.** `Var(Δ; E) = T + N/E`, `T = 0.19`, `N = 15.4` (validated: predicted
  `se(Δ 8→16)` at n=1350/E=16 = 0.0297 vs published 0.0290). At **n₁ = 1,350, E = 64**:
  `se(Δ(16→64)) ≈ 0.0198–0.0203` ⇒ **committed 2σ floor `+0.040`**. Resolves +0.064 / +0.053
  / +0.196; **does not** resolve +0.017 / +0.021.
- **Rung 3.** `sd_Δ ∈ [0.9, 1.4]` (bracketed in advance; bounded above by the per-position
  level sd 1.7197, reduced by the ~61% exact zeros). At **N_capped = 1,100**:
  `se(Δ_ora) ∈ [0.0271, 0.0422]` ⇒ 2σ bar `∈ [+0.054, +0.084]`. Resolves +0.1382 (z 3.3–5.1)
  and +0.0842 (z 2.0–3.1); **cannot** separate 1.400 from 1.244 (Δ = 0.054 ⇒ z 1.28–2.0).
- **All SEs are root-bootstrap** — resample `root_id`, **2,000 reps, seed `20260819`**, cluster
  = root. A naive per-ply se is never a branch input. CIs are percentile (2.5 / 97.5).
- **`σ_realized` governs.** Every "2σ" below means **2 × the realized root-bootstrap se**, and
  additionally, for rung 2's primary, the **committed floor `+0.040`** — both conjuncts, so
  neither an optimistic nor a pessimistic realized se can move the bar alone.

---

## 4. BRANCH TABLE — rung 2 (`B > 16`), on S1, primary `Δ(16→64)` at `E = 64`

Read in this order; the **first** row whose condition holds is the branch. Ties resolve to
the **more conservative (lower-spend)** row.

| # | branch | condition (verbatim-takeable) | what it licenses |
|---|---|---|---|
| 1 | **`W-NOISY`** | `z(arb_64) < +2.0` | the level itself does not convict on the fresh corpus; the increment is uninterpretable regardless of sign. **Nothing licensed.** |
| 2 | **`W-REVERSAL`** | `Δ(16→64) ≤ −2σ_realized` | a strictly larger CRN sample cannot be worse in expectation for a consistent selector ⇒ a **mechanism anomaly, not a finding**. Report and diagnose (arm-order side channel? argmax tie-break? world-draw pathology?). **Licenses nothing.** |
| 3 | **`W-RISING`** | `Δ(16→64) ≥ +2σ_realized` **and** `Δ(16→64) ≥ +0.040` **and** `z(arb_64) ≥ +2.0` **and** `arb(64) > arb(16)` | the ladder is still rising at the instrument's new ceiling. **Licenses (does not fund) ONE** prereg: a deck-paired game cell at the best-reading rung, **plus a mandatory cost re-measure in the contended currency** (§6 R2/R6). |
| 4 | **`W-SATURATED`** | `\|Δ(16→64)\| < 2σ_realized` **and** `z(arb_64) ≥ +2.0` | `B = 16` is on the plateau **to within +0.04 pts/tied ply**. **CLOSES the `B` axis at 16.** The deploy question stays where Phase B left it. **Licenses nothing.** |

**Mandatory on rows 3 and 4 alike:** the read-out states in the same paragraph that a null
here means *"no rung above 16 is worth ≥ +0.04 pts/tied ply"*, **not** `Δ = 0` — the
saturating-exp (+0.017) and √B-noise (+0.021) models are **not** resolved by this design
(DESIGN §6). `Δ(16→32)` is reported with its CI and is **never** a branch input on its own.

Addresses: `READOUT::widening.delta.d_16_64.{value,se_root,z,ci95}` ·
`…delta.d_16_32.{…}` · `…b_ladder.E64.B{1,2,4,8,16,32,64}.{arb,se,z}` ·
`…b_ladder.E16.…`. Fallback for all: `RUN/verdicts/per_position_s1.jsonl` recomputed under
§3's bootstrap spec, with `resolved_at` printed.

---

## 5. BRANCH TABLE — rung 3 (`J > 4`), on S2, primary `Δ_ora` at capped plies

`R_ora = ora_full / ora_J4`; CI95 by the same root bootstrap (percentile on the ratio).
Read in order; first match wins; ties → more conservative row.

| # | branch | condition (verbatim-takeable) | reading |
|---|---|---|---|
| 1 | **`X-CONFIRMED`** | `Δ_ora ≥ +2σ_realized` **and** `1.400 ∈ CI95(R_ora)` | the pre-registered full-set extrapolation **holds**; the cap left ≈1.4× on the table at capped plies. Licenses a **DESIGN** for a `J`-widened deploy shape — nothing more. |
| 2 | **`X-ABOVE`** *(added by DESIGN §12.4; PLAN_J §6 had no row for this and would have mis-read it as `X-PARTIAL`)* | `Δ_ora ≥ +2σ_realized` **and** `lower(CI95(R_ora)) > 1.400` | the prize **exceeds** the legacy extrapolation. Treated exactly as `X-CONFIRMED` for licensing, and the `I6` amendment is **NOT** triggered; the read-out must flag that both pre-registered predictions were **under**-statements and name that as unexplained. |
| 3 | **`X-PARTIAL`** | `Δ_ora ≥ +2σ_realized` **and** `upper(CI95(R_ora)) < 1.400` **and** `upper(CI95(R_ora)) ≥ 1.244` | value exists but **below** the legacy prediction — the dedupe correction is vindicated. Report the corrected multiplier as the number of record and **put the DESIGN §10 `I6` amendment to the owner** (the multiplier cancels out of `F`, so **no prior verdict moves**). |
| 4 | **`X-FREE`** | `0 ∈ CI95(Δ_ora)` **and** `upper(CI95(Δ_ora)) < +0.0842` | **the cap was free.** `J = 4` is not a compromise; retire the rung and strike the ×1.40 extrapolation from the bound chain. |
| 5 | **`X-INCONCLUSIVE`** | none of 1–4 | underpowered or ambiguous. Report; **do not adjudicate**; **do not top up** without a fresh read rule. |

**`X-NOISE` (rider, non-adjudicating, printed on whichever branch fires):**
`Δ_arb ≤ −2σ_arb` while `Δ_ora ≥ +2σ_ora` ⇒ *the value is there but `B = 16` cannot reach
it* — widening the arm set widened the selection noise. **Hands the finding to rung 2**; a
`J`-widened deploy at `B = 16` would **lose**. This rider never changes which X-branch fires.

**Mandatory on every X-branch:** *this design cannot separate 1.400 from 1.244* (Δ = 0.054 ⇒
z 1.28–2.0). A result landing between them is `X-PARTIAL` **only** if the CI excludes 1.400
outright; otherwise it is `X-INCONCLUSIVE`. It may never be read as "whichever prediction the
reader prefers".

Addresses: `READOUT::widening.j_rider.s2.{delta_ora,se_root,ci95,r_ora,r_ora_ci95,delta_arb,se_arb,ci95_arb,n_capped}` ·
replication rider `…j_rider.s1_replication.{…}` · interaction rider
`…j_rider.interaction.{arb_full_64_minus_16, arb_full_16_minus_j4_16}`. Fallback:
`RUN/verdicts/per_position_s2.jsonl` (and `_s1.jsonl` for the rider) recomputed under §3.

**S1 and S2 are NEVER pooled.** They carry different `E` and therefore different `ora`
estimands (DESIGN §4). The S1 capped subset is a replication rider and adjudicates nothing.

---

## 6. Mandatory riders — every branch of both tables carries all of these

- **R1 — σ inflation (CL-068), applied where it belongs.** The primaries (`Δ(16→64)`,
  `Δ_ora`, `Δ_arb`, `R_ora`) are **within-run, within-position, CRN-paired** ⇒ **no
  inflation**. Any contrast against a **banked** corpus or band takes **1.5–2×**, and the
  read-out quotes the **2×** envelope: this binds `G-REPLICATE`, any comparison of a level
  to Stage-1b's published ladder, and the comparison of a realized `Δ_ora` to the
  Stage-1b-**derived** predicted magnitudes +0.1382 / +0.0842. (The constants **1.400** and
  **1.244** are order-statistic arithmetic, not band measurements — they take no inflation,
  which is why the CI-membership tests in §5 are written on `R_ora`, a within-run ratio.)
- **R2 — translation caveat (CAMPAIGN ruling 5).** No pts/game figure may be quoted from any
  branch without, in the same sentence: *Stage-1b's offline read under-predicted Phase B's
  realized game cell by 3.9× (+0.79 predicted vs +3.07 realized), and the offline→game map is
  unestablished in BOTH directions.* **No game cell is sized on any branch of this read rule.**
- **R3 — `I7-draw-scope` (rung 3, every branch).** The J=4 comparator is the **instrument's**
  seeded draw, not the deployed arbiter's (different salt, different RNG, by construction —
  DESIGN §5). The population claim is licensed; the per-ply claim *"at this ply the shipped
  arbiter left X on the table"* is **not**.
- **R4 — two currencies, never converted (Stage-2 §0.G).** Offline worker-seconds and the
  deploy per-move wall are different numbers. Any deploy statement quotes `rho_wall`, the
  **realized contended** `ms_ratio`, and `rho_phone` separately, each labelled
  **re-measure required**, never derived from the other.
- **R5 — governance.** `governance/PRODUCTION.yaml` untouched. No claim minted, retired or
  moved. No `experiments/results.csv` strength row. A branch may license a **DESIGN**; a
  production flip is the owner's decision alone and is not on this table.
- **R6 — the N4 waiver question is open.** Unless the owner's answer to DESIGN §11.2 is on
  record, `W-RISING` licenses an **informational** prereg only: `rho_wall` is 1.2449 at B=32
  and 2.4897 at B=64 against the 1.20 bar, so no deploy branch can fire from rung 2 without it.
- **R7 — `|z| < 2` is never "refuted".** "Killed", "dead", "does nothing" are **forbidden**
  readings of `W-SATURATED`, `X-FREE`, `X-INCONCLUSIVE` and `W-NOISY`.

---

## 7. What the read-out prints — and the blindness protection

**On any branch:** the fired branch verbatim; every gate with `PASS/FAIL` **and its
`resolved_at` address**; the §3 arithmetic with the **realized** se's beside the predicted
ones; both rungs' full companion tables (DESIGN §2's "reported in full" list); all seven
riders; the realized worker-hours and wall against DESIGN §7's committed figures; and the
`c`-remeasure outcome (realized vs committed `c`, and whether the >25% halt fired).

**On `W-UNREADABLE` (any gate FAIL): the harness report prints GATE INPUTS ONLY — no `arb`,
no `ora`, no `Δ`, no `z`, no per-position statistic.** This is a hard requirement, not a
courtesy: on 2026-08-17 a mandatory companion table printed alongside a gate failure made the
orchestrating session non-blind and forced the fixes to be written by a separate blind
session. A gate-failure report must be safe for the fixing session to read.

**Deviations.** Any deviation from DESIGN or this READ_RULE is recorded in the read-out as a
numbered deviation with its direction of bias — never silently absorbed, never adjudicated
around (the `C5`-not-run precedent from the rung-1 census).

---

## 8. Spent

This read rule is **single-use**. When the read-out lands it is spent: no re-read, no second
adjudication, no top-up, no re-scoring of this corpus under any other rule. Close-out is the
six-touch checklist — `results.csv` (no strength row: an explicit "none, offline instrument"
note), DECISIONS index line, status banners on `DESIGN.md`/`READ_RULE.md`/both PLANs,
governance row flips, `STATUS.md`, and the roadmap line — then `python3 scripts/doc_lint.py`.
