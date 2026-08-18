# TIE-ARBITER WIDENING — SHARED RUN, MECHANICAL READ RULE (rungs 2 + 3)

> **STATUS: BLIND PREREGISTRATION, DRAFT (revision R1). NOT LAUNCHED. NO NUMBER OF THIS RUN
> EXISTS.**
>
> ⚠️ **BLIND-ORDER REQUIREMENT — NOT YET SATISFIED.** Drafted in an isolated worktree under
> the main-tree commit freeze. **This file and [`DESIGN.md`](DESIGN.md) must be committed to
> the MAIN tree, in ONE commit, after the DESIGN §9 W-code merge and before the band claim and
> before one position is scored.** A worktree commit does not satisfy blindness.
>
> Revision R1 folds in [`REVIEW_R1.md`](REVIEW_R1.md): **four gates in the first draft would
> have voided a healthy run** (fictional or misspelled addresses, an unsatisfiable prefix
> conjunct, and an identity that is false by design ~16% of the time), and two branch tables
> were not total. Disposition: DESIGN §13.
>
> **SINGLE USE. SPENT ON LANDING.** One adjudication, one analyzer invocation, one read-out
> covering **both** rungs. No re-read, no second pass, no top-up at any `z`. The only
> pre-licensed top-up is DESIGN §3's **blind corpus top-up**, which expires the moment the
> first scoring leg starts.
>
> `governance/PRODUCTION.yaml` is **untouched on every branch**. No branch flips anything; at
> most a branch licenses a *DESIGN*. No claim id is minted. No strength row is written.

`RUN` = `measurement/tiearb_widening_20260817/shared_run/` (absolute paths, DESIGN §4).
`READOUT` = `RUN/verdicts/READOUT.json` (written by the W3 analyzer, one invocation).
`SHARE` = `/mnt/c/carc-shared/tiearb_widening_20260817/{s1,s2}/`.

---

## 1. Address discipline and fail-closed semantics

1. **Every gate and every branch input is named below by its exact address** — file path plus
   a dotted key path, verified against the emitter (REVIEW_R1 re-verified all of them).
2. **ABSENT IS FAIL.** File missing, key missing, key `null` ⇒ the gate **FAILS**. Absent is
   never a pass, never "assume healthy", never "recompute by hand and proceed".
3. **Fallbacks are pre-registered, not improvised.** Try the primary, then the fallback; the
   read-out **must print `resolved_at: <address>`** for every gate, or `UNRESOLVED`. A gate
   answered only by a fallback is reported as such on the branch line.
4. **No address may be invented at read time.** If a gate's inputs are unreachable at every
   pre-registered address, the answer is `W-UNREADABLE`, not a new address.
5. **Structural test, written into every row:** *would this gate fail on a healthy run?* If
   yes it is an instrument defect, fixed **before** the run, never adjudicated around. Four
   gates failed this test in the first draft; `G-CAP` failed it in PLAN_J. DESIGN §9 step 4
   makes address-resolution a **pre-run acceptance test** on the smoke's own output.

---

## 2. Gates. Any FAIL ⇒ `W-UNREADABLE` for the affected rung; nothing is licensed

S2 gates bind **rung 3 only**; an S2 failure leaves rung 2 readable, and vice versa. **The
exception is `G-REPLICATE`, which binds BOTH rungs — one shared instrument check, NOT two
independent confirmations; a joint pass must never be cited as if the two rungs corroborated
each other.**

| gate | conjunct (all must hold) | primary address | fallback | on a healthy run |
|---|---|---|---|---|
| `G-BAND` | `band_ok == true`; `seed_band == [135000000000, 135000000849]` (∪ the reserved range iff the blind top-up was exercised); `n_out_of_band == 0`; `n_duplicate_seeds == 0`; `n_games_realized ≥ 850` | `RUN/corpus/CHAMP_GAMES_VERIFY.json::{band_ok,seed_band,n_out_of_band,n_duplicate_seeds,n_games_realized}` | — (**no seed list exists anywhere by design**: the emitter publishes `sha256_of_sorted_seeds`, a disclosure-discipline choice this rule keeps) | **PASSES** |
| `G-DISJOINT` | `passed == true` **and** every `comparisons.<name>.layers.{a_root_id,b_rid,c_position_digest}.n_intersection == 0` over the **four** committed comparisons (S1 vs `tiletie_pricing_20260812`; S1 vs `tiearb2_20260816`; S2 vs both) **and** `strata_root_overlap == 0` | `RUN/GATE_DISJOINT.json::{passed, comparisons, strata_root_overlap}` | — (a missing gate file is a FAIL) | **PASSES** — but only against the **W5 merged** emitter: the stock `gate_disjoint.py` compares two ARMS.json corpora, emits `layers`/`passed` at top level with no `comparisons` or `strata_root_overlap`, and `load_rids` raises on a rid-txt. W5 must exist first (DESIGN §8) |
| `G-LEAF` | leaf hash of record `a36d2e15a3b3d71d` resolves and asserts | `RUN/RUN_MANIFEST_{S1,S2}.json::preflight.checks.leaf_hash.ok` | `…preflight.checks.leaf_hash.harness_leaf_hash` compared literally to `…expected` | **PASSES** |
| `G-SALT` | `world_seed_salt == "tiletie-v1"`; `deployed_cap_j == 4`; `cap_seed` present for **every** rid | `RUN/RUN_MANIFEST_S1.json::world_seed_salt` · `RUN/corpus/positions_s1/POSITIONS_PLAN.json::deployed_cap_j` · `…/ARMS.json::<rid>.cap_seed` | `RUN/legs/<judge>/walled/leg<N>/manifest.json::resolved_config.world_seed_salt` | **PASSES** — module constant, not a flag |
| `G-M` | S1: `m_worlds == 128`, `b_ceiling_from_m == 64`. S2: `32` / `16` | `RUN/RUN_MANIFEST_{S1,S2}.json::{m_worlds,b_ceiling_from_m}` | `RUN/legs/…/manifest.json::resolved_config.m` | **PASSES** |
| `G-BACKEND` | `arb_backend == "rust"`; every `tier1-greedy/walled` entry of `resolved_backend_by_leg` reads `rust`; `arb_legal_mask_cache == true` | `RUN/RUN_MANIFEST_{S1,S2}.json::{arb_backend,resolved_backend_by_leg,arb_legal_mask_cache}` | `RUN/legs/…/manifest.json::resolved_config.legal_mask_cache` | **PASSES** — the launcher refuses to fall back silently |
| `G-BITEXACT@HEAD` | `pass == true`; `n_playouts_compared ≥ 1024`; `n_value_mismatch == 0`; `legal_mask_cache == true`; `git_rev` equals the run's | `RUN/GATE_BITEXACT_HEAD.json::{pass,n_playouts_compared,n_value_bit_identical,n_value_mismatch,legal_mask_cache,git_rev}` (reached by `verify_tier1_rust.py --out`, W7) | — | **PASSES** — 15,360/15,360 at Phase A on this wheel. ⚠️ Without `--out` this gate can only write into the **closed** Stage-2 run dir and can never appear at the address above; with `--no-legal-mask-cache` it would fail on a healthy run (57/15,360 move). Both spellings are forbidden |
| `G-PREFIX` | `ok == true` **and** `prefix_stable_at ⊇ {1,2,4,8,16,32,64,128}` on S1 (`⊇ {1,2,4,8,16,32}` on S2) | `RUN/legs/<judge>/walled/leg<N>/manifest.json::preflight.seeds.{ok,prefix_stable_at}` | `…::preflight.seeds.derivation` present **and** `probe_world_seeds_head` non-empty | **PASSES** — `preflight_seeds()` asserts prefix stability fatally at launch and returns the ladder it verified. ⚠️ It emits a 4-entry head for a synthetic probe rid, **not** 32 seeds of run rids, and `prefix_ok` exists nowhere — the first draft's conjunct could not be met |
| `G-CRN` | per-judge smoke witness `true`; `n_crn_verified == n_ok` on **every** leg; exactly one witness kind per judge | `RUN/SMOKE_MANIFEST_S1_<judge>.json::crn_cross_leg_identical` · `READOUT::widening.gates.crn.{ok,witness_kinds}` | per-record `SHARE/<judge>/walled/leg<N>/*.jsonl::{crn_verified,world_deck_hash\|afterstate_deck_hash_a}` | **PASSES**. ⚠️ `run_smoke` is single-judge and writes one `--smoke-manifest` path, so two smokes at one path would overwrite: per-judge filenames are mandatory. `crn_witness` is a **per-record** field, never a leg-manifest key |
| `G-UNCAPPED` | `uncapped == true` and `cap_j == null` on both strata; and for every rid the **exact prefix+append identity**: `arms[:len(arms_full)] == arms_full`, `len(arms) − len(arms_full) ∈ {0,1}`, and any extra element equals `champ_arm_action` at `champ_arm_index == len(arms)−1` | `RUN/corpus/positions_{s1,s2}/POSITIONS_PLAN.json::{uncapped,cap_j}` · `…/ARMS.json::<rid>.{arms,arms_full,champ_arm_action,champ_arm_index}` | `READOUT::widening.gates.uncapped` | **PASSES**. ⚠️ A naive `arms == arms_full` **fails ~16% of rids by design** — `resolve_champion_arm` appends the champion pick when its transposition rep is absent (`champ_outside_tieset` 15.6–17.3% on the banked corpora; rust does the identical append) |
| `G-DRAW` (replaces the retired `G-CAP`) | for every rid: `[arms_full[0]] + _seeded_cap(rid, arms_full[1:], 4)[0] == subset_j4` (exact list identity, re-run at the run's `git_rev`); `subset_j4_id` matches the recomputed digest; `len(subset_j4) == min(4, len(arms_full))`; `n_mismatch == 0` | `RUN/GATE_DRAW.json::{n_checked,n_mismatch,ok,git_rev}` | `RUN/corpus/positions_{s1,s2}/ARMS.json::<rid>.{arms_full,subset_j4,subset_j4_id}` recomputed by the reader | **PASSES** — a pure function of `(rid, arms_full[1:])`. ⚠️ `_seeded_cap` returns `(kept, capped, dropped)` **without** the reference arm, while `subset_j4 = [ref] + kept`: comparing the raw return to `subset_j4` fails on every healthy run. It does **NOT** assert agreement with the deployed rust draw — retired as unsatisfiable (DESIGN §5); carried as rider `I7` |
| `G-ARMS` | every full-set arm scored on **all** `M` worlds — per-arm, not per-ply; `n_arms_complete == n_arms`; `include_partial == false` | `READOUT::widening.gates.arms.{n_arms,n_arms_complete,include_partial,ok}` | `RUN/verdicts/per_position_{s1,s2}.jsonl` per-arm world counts | **PASSES** — contingent on W3 (DESIGN §9 step 4) |
| `G-COMPLETE` | S1 scored `≥ 1,283` (95% of 1,350); S2 scored capped `≥ 1,045` (95% of 1,100); mining ceilings honoured (≤4 tied plies/root S1, ≤3 capped plies/root S2) | `READOUT::widening.completion.{s1_n,s2_n,s1_max_per_root,s2_max_per_root}` | `RUN/verdicts/per_position_{s1,s2}.jsonl` line counts + `root_id` grouping | **PASSES** — contingent on W3 |
| `G-REPLICATE` **(binds BOTH rungs)** | the `(B ≤ 16, E = 16)` sub-read on S1 lands inside the **2×-inflated** 2σ envelope of Stage-1b's ladder at every rung `B ∈ {1,2,4,8,16}`, **and** the shared cell convicts (`arb_16` CI excludes 0) | `READOUT::widening.stage1_replication.{pass, per_rung_inside_envelope, arb16_convicts, envelope_inflation}` — **booleans only** | `RUN/verdicts/SEALED_G_REPLICATE.json` (the z's; **sealed — not printed by the harness, not read by a fixing session**, §7) | **PASSES** if the instrument is sound. **A FAIL means `UNINTERPRETABLE`, NEVER `FAIL-the-lever`** — the fresh corpus is a different population. A rung that fails the naive-σ envelope but passes the inflated one is a **mandatory caveat on every branch** |

**Precedence.** Gates are evaluated **before** any branch statistic is read. If any gate
binding a rung FAILS, that rung's answer is `W-UNREADABLE` and **no branch of that rung
fires** — not even "for information".

---

## 3. The power arithmetic, restated as the bars are read

- **Significance is ONE test, everywhere:** a quantity is significant iff `lower(CI95) > 0`
  (or `upper(CI95) < 0` for a negative claim), where `CI95` is the **percentile
  root-bootstrap** interval — resample `root_id`, **2,000 reps, seed `20260819`**, cluster =
  root. No `point/se` test appears in either branch table (REVIEW_R1 §8: mixing the two lets a
  skewed bootstrap fire a "confirmed" branch while its CI straddles zero).
- **Rung 2 se, corrected (REVIEW_R1 §12).** The measured law `Var(Δ;E) = T + N/E`,
  `T = 0.19, N = 15.4`, is the **Δ(8→16)** law and reproduces it exactly (`se` at n=1350/E=16 =
  **0.02922** vs published 0.0290 ✓). **`T` for Δ(16→64) is UNMEASURED**; PLAN_B's published
  0.0198–0.0203 back-solves to `T ≈ 0.30`. Pre-registered bracket:
  **`se(Δ(16→64)) ∈ [0.0179, 0.0200]` ⇒ `2σ ∈ [0.0357, 0.0400]`**. The **committed floor is
  `+0.040`** and does not move with the realized se.
- **Rung 3.** `sd_Δ ∈ [0.9, 1.4]` (bracketed in advance). At **N_capped = 1,100**:
  `se(Δ_ora) ∈ [0.0271, 0.0422]`. Resolves +0.1382 (z 3.27–5.10) and +0.0842 (z 1.995–3.10 —
  **resolved at `sd_Δ ≤ 1.396`, NOT at 1.4**); **cannot** separate 1.400 from 1.244
  (Δ = 0.054 ⇒ z 1.28–2.00).

---

## 4. BRANCH TABLE — rung 2 (`B > 16`), on S1, primary `Δ(16→64)` at `E = 64`

Read in order; the **first** row whose condition holds is the branch. Ties resolve to the
**more conservative (lower-spend)** row. The table is **total**: row 5 is a catch-all.

| # | branch | condition (verbatim-takeable) | what it licenses |
|---|---|---|---|
| 1 | **`W-NOISY`** | `arb_64` does not convict: `0 ∈ CI95(arb_64)` | the level itself does not convict on the fresh corpus; the increment is uninterpretable regardless of sign. **Nothing licensed.** |
| 2 | **`W-REVERSAL`** | `upper(CI95(Δ(16→64))) < 0` | a strictly larger CRN sample cannot be worse in expectation for a consistent selector ⇒ a **mechanism anomaly, not a finding**. Report and diagnose (arm-order side channel? argmax tie-break? world-draw pathology?). **Licenses nothing.** |
| 3 | **`W-RISING`** | `lower(CI95(Δ(16→64))) > 0` **and** `Δ(16→64) ≥ +0.040` **and** `lower(CI95(arb_64)) > 0` **and** `arb(64) > arb(16)` | the ladder is still rising at the instrument's new ceiling. **Licenses (does not fund) ONE** prereg: a deck-paired game cell at the best-reading rung, **plus a mandatory cost re-measure in the contended currency**, carrying `R2` and `R6`. |
| 4 | **`W-SATURATED`** | `0 ∈ CI95(Δ(16→64))` **and** `lower(CI95(arb_64)) > 0` | `B = 16` is on the plateau **to within +0.04 pts/tied ply**. **CLOSES the `B` axis at 16.** The deploy question stays where Phase B left it. **Licenses nothing.** |
| 5 | **`W-INCONCLUSIVE`** (catch-all) | none of 1–4 — including a `Δ` significant but **below** the committed +0.040 floor (a live interval: `2σ` can be as small as 0.0357), and any degenerate/NaN/undefined se or CI | the run neither convicts the still-rising world nor lands on the plateau bar. **Report; adjudicate nothing; license nothing; no top-up.** |

**Mandatory on rows 3, 4 and 5:** a null here means *"no rung above 16 is worth ≥ +0.04
pts/tied ply"*, **not** `Δ = 0` — the saturating-exp (+0.017) and √B-noise (+0.021) models are
**not** resolved by this design. `Δ(16→32)` is reported with its CI and is **never** a branch
input on its own.

Addresses: `READOUT::widening.delta.d_16_64.{value,ci95,se_root}` · `…delta.d_16_32.{…}` ·
`…b_ladder.E64.B{1,2,4,8,16,32,64}.{arb,ci95,se}` · `…b_ladder.E16.…`. Fallback:
`RUN/verdicts/per_position_s1.jsonl` recomputed under §3, with `resolved_at` printed.

---

## 5. BRANCH TABLE — rung 3 (`J > 4`), on S2, primary `Δ_ora` at capped plies

**Pre-branch guard (REVIEW_R1 §10).** If `lower(CI95(ora_J4)) ≤ 0`, the ratio `R_ora` is
**degenerate and is NOT reported** (a ratio whose denominator replicates cross zero has no
meaningful percentile CI). In that case rung 3 adjudicates on `Δ_ora` alone, via the committed
sub-table below — never by substituting a different ratio or a different statistic.

**Main table** (`R_ora = ora_full / ora_J4`). Read in order; first match wins; ties → more
conservative row. Total by row 6.

| # | branch | condition (verbatim-takeable) | reading |
|---|---|---|---|
| 1 | **`X-CONFIRMED`** | `lower(CI95(Δ_ora)) > 0` **and** `1.400 ∈ CI95(R_ora)` | the pre-registered full-set extrapolation **holds**. Licenses a **DESIGN** for a `J`-widened deploy shape — nothing more. |
| 2 | **`X-ABOVE`** | `lower(CI95(Δ_ora)) > 0` **and** `lower(CI95(R_ora)) > 1.400` | the prize **exceeds** the legacy extrapolation. Licensing as `X-CONFIRMED`; the `I6` amendment is **NOT** triggered; the read-out must flag that **both** pre-registered predictions were under-statements and name that as unexplained. |
| 3 | **`X-PARTIAL`** | `lower(CI95(Δ_ora)) > 0` **and** `upper(CI95(R_ora)) < 1.400` **and** `upper(CI95(R_ora)) ≥ 1.244` | value exists but **below** the legacy prediction — the dedupe correction is vindicated. Report the corrected multiplier as the number of record and **put the DESIGN §11 `I6` amendment to the owner**. |
| 4 | **`X-BELOW`** | `lower(CI95(Δ_ora)) > 0` **and** `upper(CI95(R_ora)) < 1.244` | a **resolved** value below **both** predictions — the likeliest landing of this design. Not "inconclusive": the measured `R_ora` becomes the number of record, **both** predictions are recorded as over-statements, and the `I6` amendment is put to the owner. |
| 5 | **`X-FREE`** | `0 ∈ CI95(Δ_ora)` **and** `upper(CI95(Δ_ora)) < +0.0842` | **the cap was free.** `J = 4` is not a compromise; retire the rung and strike the ×1.40 extrapolation from the bound chain. |
| 6 | **`X-INCONCLUSIVE`** (catch-all) | none of 1–5, including any degenerate CI | underpowered or ambiguous. Report; **do not adjudicate**; **do not top up** without a fresh read rule. |

**`Δ_ora`-only sub-table** — used **only** when the pre-branch guard fires. Same order, same
tie rule; the bars are the predicted magnitudes, which are Stage-1b-derived and therefore carry
`R1`'s inflation when quoted as a comparison:
`X-CONFIRMED-D` = `lower(CI95(Δ_ora)) > 0` and `+0.1382 ∈ CI95(Δ_ora)` ·
`X-ABOVE-D` = `lower(CI95(Δ_ora)) > +0.1382` ·
`X-PARTIAL-D` = `lower > 0` and `upper < +0.1382` and `upper ≥ +0.0842` ·
`X-BELOW-D` = `lower > 0` and `upper < +0.0842` ·
`X-FREE-D` = `0 ∈ CI95(Δ_ora)` and `upper < +0.0842` ·
`X-INCONCLUSIVE-D` = otherwise.

**`X-NOISE` (rider, non-adjudicating, printed on whichever branch fires):**
`upper(CI95(Δ_arb)) < 0` while `lower(CI95(Δ_ora)) > 0` ⇒ *the value is there but `B = 16`
cannot reach it*. **Hands the finding to rung 2**; a `J`-widened deploy at `B = 16` would
**lose**. Never changes which X-branch fires.

**Mandatory prints on every X-branch.**
(i) *This design cannot separate 1.400 from 1.244* (Δ = 0.054 ⇒ z 1.28–2.00); a result between
them is `X-PARTIAL` only if the CI excludes 1.400 outright, never "whichever the reader
prefers". (ii) *`+0.0842` is unresolved at the top of the `sd_Δ` bracket* (z 1.995 at
`sd_Δ = 1.4`). (iii) **The `X-FREE` attainability window at the REALIZED se**: print the
interval of point estimates for which `X-FREE` was reachable, and state plainly if it was
**empty or near-empty** — at `sd_Δ = 1.4` it requires a point estimate `≤ +0.0015`, so a
non-firing `X-FREE` is not evidence against the cap being free.

Addresses:
`READOUT::widening.j_rider.s2.{delta_ora,ci95_ora,r_ora,ci95_r_ora,ora_j4_ci95,delta_arb,ci95_arb,n_capped,xfree_window}` ·
`…j_rider.s1_replication.{…}` · `…j_rider.interaction.{arb_full_64_minus_16,
arb_full_16_minus_j4_16}` · `…j_rider.d_draw.{n_checked,agreement_rate}`. Fallback:
`RUN/verdicts/per_position_{s2,s1}.jsonl` recomputed under §3.

**S1 and S2 are NEVER pooled** (different `E` ⇒ different `ora` estimand). The S1 capped subset
and `D-DRAW` are riders and adjudicate nothing.

---

## 6. Mandatory riders — every branch of both tables carries all of these

- **R1 — σ inflation (CL-068), applied where it belongs.** The primaries (`Δ(16→64)`,
  `Δ_ora`, `Δ_arb`, `R_ora`) are **within-run, within-position, CRN-paired** ⇒ **no
  inflation**. Any contrast against a **banked** corpus or band takes **1.5–2×** and the
  read-out quotes the **2×** envelope: this binds `G-REPLICATE`, any comparison of a level to
  Stage-1b's published ladder, and any comparison of a realized `Δ_ora` to the
  Stage-1b-**derived** magnitudes +0.1382 / +0.0842 (including the whole `Δ_ora`-only
  sub-table). The constants **1.400** and **1.244** are order-statistic arithmetic, not band
  measurements — no inflation — which is why the main table's membership tests are on `R_ora`.
- **R2 — translation caveat (CAMPAIGN ruling 5).** No pts/game figure may be quoted from any
  branch without, in the same sentence: *Stage-1b's offline read under-predicted Phase B's
  realized game cell by 3.9× (+0.79 predicted vs +3.07 realized), and the offline→game map is
  unestablished in BOTH directions.* **No game cell is sized on any branch.**
- **R3 — `I7-draw-scope` (rung 3, every branch), quoted in full from DESIGN §5** — including
  (a) the instrument draw is **not nested in `j`** (so no future `J = 8` sub-read of this
  corpus may be taken from these records) and (b) the licence is **conditional on the python
  and rust afterstate-dedupe keys inducing the same partition of the tie set, which this run
  does not verify**; `D-DRAW` reports the magnitude of that conditional and adjudicates nothing.
- **R4 — two currencies, never converted (Stage-2 §0.G).** Any deploy statement quotes
  `rho_wall` and the **realized contended** `ms_ratio` separately, each labelled
  **re-measure required**, never derived from the offline worker-seconds.
- **R5 — governance.** `governance/PRODUCTION.yaml` untouched. No claim minted, retired or
  moved. No `experiments/results.csv` strength row. A branch may license a **DESIGN**; a
  production flip is the owner's decision alone.
- **R6 — the N4 waiver above `B = 16` is OPEN and is re-priced at the flip decision (owner
  ruling 2026-08-18).** `rho_wall` is 1.2449 at B=32 and 2.4897 at B=64 against the 1.20 bar.
  **No branch may claim the waiver extends, and no branch may label this run
  informational-only.** `W-RISING` licenses a prereg whose cost section must re-measure and
  re-put that question.
- **R7 — the phone is out of scope for this axis** (owner ruling). `rho_phone` is a third
  currency; no branch says anything about on-device deploy, in either direction.
- **R8 — `|z| < 2` is never "refuted".** "Killed", "dead", "does nothing" are **forbidden**
  readings of `W-SATURATED`, `W-INCONCLUSIVE`, `W-NOISY`, `X-FREE` and `X-INCONCLUSIVE`.

---

## 7. What the read-out prints — and the blindness protection

**On any branch:** the fired branch verbatim; every gate with `PASS/FAIL` **and its
`resolved_at` address**; §3's arithmetic with the **realized** CIs beside the predicted
brackets; both rungs' full companion tables (DESIGN §2's "reported in full" list); all eight
riders; the realized worker-hours and wall against DESIGN §7's committed figures; and the
`c`-remeasure outcome for **all three** legs (judge ARB, judge IF, generation) — realized vs
committed, and whether the one-sided HALT fired.

**On `W-UNREADABLE` (any gate FAIL): the harness report prints GATE INPUTS ONLY — no `arb`,
no `ora`, no `Δ`, no CI, no per-position statistic.** This is a hard requirement: on
2026-08-17 a mandatory companion table printed alongside a gate failure made the orchestrating
session non-blind and forced the fixes to be written by a separate blind session.
**`G-REPLICATE` is the one gate whose natural inputs are themselves outcome statistics**, so it
resolves as **booleans only** (`pass`, `per_rung_inside_envelope`, `arb16_convicts`) and its
z's are written to `RUN/verdicts/SEALED_G_REPLICATE.json`, which the harness never prints and a
fixing session never opens. A gate-failure report must be safe for the fixing session to read.

**Deviations.** Any deviation from DESIGN or this READ_RULE is recorded in the read-out as a
numbered deviation with its direction of bias — never silently absorbed, never adjudicated
around (the `C5`-not-run precedent from the rung-1 census). A mid-run `WORKERS.conf` retune is
such a deviation (DESIGN §9.7).

---

## 8. Spent

**Single-use.** When the read-out lands this rule is spent: no re-read, no second
adjudication, no top-up, no re-scoring of this corpus under any other rule. Close-out is the
six-touch checklist — `results.csv` (no strength row: an explicit "none, offline instrument"
note), DECISIONS index line, status banners on `DESIGN.md`/`READ_RULE.md`/both PLANs,
governance row flips, `STATUS.md`, and the roadmap line — then `python3 scripts/doc_lint.py`.
