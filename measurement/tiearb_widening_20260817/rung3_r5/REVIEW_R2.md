# REVIEW_R2 — rung3_r5 prereg pair, SECOND REVIEWER (fresh, independent). Reviewed commit `eda625cf`. Date 2026-08-19.

> **Reviewer: second reviewer, fresh session, no part in drafting the pair.** Scope: the blind-commit
> pair in the drafter's worktree `agent-a43f00f675fd11b65` — `DESIGN.md`, `READ_RULE.md`,
> `FLOORS_R5.json` — read read-only, against `CALIBRATION.json`, `../shared_run_r4/`,
> `../shared_run/`, `../PREREG_FAILURE_S2.md`, `../DEVIATIONS.md` §D4.18–19, and the R4-era review
> exemplars. Method: **re-derive from primitives**, per house discipline — the campaign's three
> prereg deaths were all supply/bound arithmetic that survived prose review.
>
> **This review is the review of record for `eda625cf`.**

## REVIEW — `rung3_r5` prereg pair (worktree `agent-a43f00f675fd11b65`, commit `eda625cf`). **VERDICT: FAIL** — 6 BLOCKING, 11 REQUIRED, 5 COSMETIC.

**Rebuilt from primitives this round.** Power ladder 6/6 exact (√1064 = 32.6190 ⇒ se ∈ [0.02759, 0.04292]; +0.0842 at 2σ ⇒ sd ≤ 1.3733; +0.1382 ⇒ sd ≤ 2.2540; Δ=0.054 ⇒ sd ≤ 0.8807; 1.3963 at n=1100, delta 0.023 — all as printed). Floor: ⌈0.95×1064⌉ = **1011** ✓; `1,100` appears nowhere as a floor ✓. Supply chain: 980/5340 = 18.35% ✓, 1064/980 = 1.0857 ✓, max-per-game 3 ✓, k=3 → 1036 = −2.63% ✓, d = 3/1064 = 0.0028195, 5/0.28195 = **17.73×** ✓. Retired-bound arithmetic 3×(3/1064)×1064 = 9 vs realized 3 ✓ — the pass-always diagnosis is correct. **M = 32 is CORRECT and well-grounded**: `shared_run/READ_RULE.md:102` G-M reads *"S1: `m_worlds == 128`, `b_ceiling_from_m == 64`. S2: `32` / `16`"*, and `STAGE1B_LADDER.json::context` states verbatim *"Stage-1b ran M=32, so its evaluation half is E=16"* — the brief's 128 would indeed have quadrupled the bill into a currency mismatch. G-COMPLETE ∧ G-FAILED joint headroom checked and **passes** (1064 − 21 = 1043 ≥ 1011; 32 positions of slack). Blindness checked: **clean** — no gate conditions on an unmeasured statistic.

---

## BLOCKING

**B1. `G-COLLIDE` fails every healthy run, two independent ways.** Its address is `GATE_DISJOINT.json::digest_exclusions.r5.{n_excluded,ply_histogram}` and it demands realized `== 3`.
- *Currency.* R4's S2 `n_excluded = 29` decomposes (I counted the evidence block): **16 vs `tiearb2_0816` + 6 vs `tiletie0812` + 8 vs S1 = 30 records / 29 unique rids, ZERO of them internal to S2.** `gate_disjoint.py` runs seven **cross-set** comparisons and R4 §2b(vii) states that same-rank pairs "are out of scope **by construction** — no comparison measures them". The calibration's 3 collisions are provably that class: digests `dc8ab4a4`, `c08bc3f3`, `3ab719cc`, all **137e9↔137e9 same-band** (verified by re-running `GD.load_digest_map` on the leg). The quantity at the address **cannot contain the 3**. It will read ~0 (reused corpus) or ~29 (fresh re-mine); never 3 ⇒ RAISE on a healthy run.
- *Address.* `digest_exclusions.<stratum>` has keys `{bound_basis, bound_fraction, bound_n, carried, denominator, denominator_source, determinism_defect, evidence, n_excluded, note, rate, residual, rids, void}`. **There is no `ply_histogram`.** ABSENT IS FAIL, and no W-item builds it (R5-W1 is `--min-ply`, made moot by k=0).

This is the same disease the previous cell review (`769da984`) already caught once this campaign.

**B2. `G-SATURATION` is PASS-ALWAYS — the retirement swapped one vacuous bound for another.** Its address is `CALIBRATION.json::by_ply_floor.0.d_model_at_governed` — a **constant committed with the pair**, known to be 0.002820 at drafting time. A gate whose input is frozen before the run cannot fire. Worse, `d_model_at_governed = d_model_value(fit, g_gov)` (`rung3_calibrate.py:639`) is the **fitted** value, not the measured one; it equals 0.002820 only because a 2-point fit passes exactly through G=5340. So the pair's single live collision gate reads *through the fit it simultaneously declares "VACUOUS ... and the fit is **not** the bound"*. Combined with B1 and B3: **R5 ships with no functioning collision or leakage guard at all.**

**B3. `G-DISJOINT`, `G-BAND` and `G-REPLICATE` are dropped without a word, and the two files disagree on what is carried.** R4's gate set was G-LEAF/SALT/M/BACKEND/BITEXACT@HEAD/PREFIX/CRN/UNCAPPED/DRAW/ARMS/REPLICATE + COMPLETE/DISJOINT/BAND. READ_RULE §0 carries nine (adds `G-ARMS`, omits `G-BITEXACT@HEAD`); DESIGN §R5-7 carries nine (adds `G-BITEXACT@HEAD`, omits `G-ARMS`). Neither carries DISJOINT, BAND or REPLICATE. G-DISJOINT's **zero-tolerance rid/root layers** — the leakage guard, distinct from the digest bound that voided R4 — vanish entirely; R5 reads that gate's *artifact* for a consistency check while abandoning its conjuncts. Dropping G-REPLICATE is defensible (its corner is S1's), but silence is not.

**B4. `n₂ = 1,064` is R4's POST-EXCLUSION count, and §R5-4's "pre-cleared of nothing" is false.** I checked all 29 excluded rids against `corpus/positions_s2/positions_walled_leg1.jsonl`: **28 absent, 1 present** — exactly `carried=28` removed and `residual=1` left behind. The file every R5 number rests on has already had R4's total-order exclusions applied. Consequences: (a) the 0.282% that "clears 17.7×" is a *post-cleaning residual* presented as the corpus's raw degeneracy; (b) the 1 residual collider is still in the corpus and no R5 gate removes it; (c) `G-CORPUS`'s `n_positions == 1064` is an identity test that only passes if R5 silently reuses R4's exclusion list — but its own address (`RUN/corpus/positions_r5/POSITIONS_PLAN.json`) implies a fresh build, which re-mines **1,092** (1064 + 28) and **fails the conjunct by 28 on a healthy run**.

**B5. The pre-data failed-record expectation is refuted by the corpus's own `ply` field.** §R5-FINAL.f / READ_RULE §3 pre-register that "R5's capped plies skew **EARLY**" ⇒ exposure "should be **LOWER** than S1's realized 0.30%". Measured over the 1,064 positions: **mean ply 69.15, median 68, max 142; 63.3% at ply ≥ 50; only 5.7% at ply ≤ 5.** S1 (1,344 positions): mean 66.5, median 64.5, 47.2% at ply ≥ 70 vs S2's **49.7%**. `WindowTruncationError` fires at ~70 tiles placed (D4.18) — **R5's corpus sits slightly deeper in that region than S1's**, so the correct pre-registration is equal-or-higher, not lower. The prose reasoned from the ply of the 3 *collisions* (forced early by the birthday argument) and generalised it to the ply of the corpus. The 2% bound survives; the pre-registered expectation will read "surprise worth naming" on a perfectly healthy run.

**B6. Existence-time markers are not applied, by the pair's own definition of the defect.** §1: *"An unmarked address is a drafting defect, fixed before the blind commit."* The row `G-LEAF, G-PREFIX, G-CRN, G-UNCAPPED, G-DRAW, G-ARMS` carries marker **"as carried"** — not one of the three, and unresolvable to one (G-UNCAPPED reads `POSITIONS_PLAN::cap_j` = `[post-corpus]`; G-CRN/G-LEAF are `[post-scoring]`). Outside §2 **no address is marked at all** — §4's CI addresses, §5's `RUN/D_DRAW.json` and `widening.j_rider.d_draw.*`, §6's read-out list. DESIGN §R5-FINAL.e's "applied throughout" is false (10 marker tokens in READ_RULE, all inside one table). Compounding: R5-6.1 requires each acceptance pass to audit its own markers with "a completeness assertion over the marker list" — **the pair defines no acceptance pass** (R5-8's sequence has no 4a/4b analogue), so the marker machinery has nothing to be audited by.

---

## REQUIRED

**R1. M=32 is verified only *after* the whole ~300 wh is spent.** `G-M` is `[post-scoring]` with sole address `RUN_MANIFEST_R5.json`. R3.3's G-M carried a second address (`legs/…/manifest.json::resolved_config.m`) and R5 drops it. Same for G-SALT and G-BACKEND (R3.3's leg-manifest fallbacks dropped). Add a pre-leg address (smoke manifest `resolved_config.m`) so the run halts on the one constant this revision exists to correct. R5-6.1 diagnosed exactly this shape ("G-SALT's primary ended up audited at neither pass") and then reproduced it.

**R2. "W9 `D-DRAW` is FUNDED / the obligation is discharged" is not enforced.** No conjunct requires `d_draw_ran == true`; §5 explicitly pre-licenses the null under the closed `allow_null` list (which *does* legitimately contain `widening.j_rider.d_draw.*` with witness `d_draw_ran == false` — verified against R3.3 §1.2, so the list is not being extended). The mechanical rule therefore permits the exact R4 outcome. Either add the conjunct or stop claiming discharge.

**R3. Cost lower bound uses the wrong smoke — the same currency error corrected for M.** My derivation: R4-2.2's own table gives the marginal S2 scoring rate as 929.0 − 626.5 = **302.5 wh @ n=1,100 = 0.27500 wh/ply** (cross-check 819.0 − 626.5 = 192.5 @ 700 ✓ linear). Committed: 1,064 × 0.275 = **292.6** + champ picks (1064 × 13.755 s = **4.065**) + census 2 + D-DRAW 2 = **300.7 wh** — their 300.6 ✓, and the ARB/IF split 0.01936/0.2556 reproduces the committed ratio 0.178232/2.35 = 13.19 exactly ✓. But the realized figure applies the **S1 @ M=128** ratios (IF 0.7471, ARB 0.7812) when the same `c_remeasure` block carries **S2 @ M=32** smokes: IF 1.6278605/2.35 = **0.69271**, ARB 0.13595312/0.178232 = **0.76279**. ⇒ 0.191824 wh/ply × 1064 + 8.1 = **212.2 wh**. **My envelope: ≈212–301 wh** (theirs 226–301). Upper bound exact; lower bound is 14 wh pessimistic.

**R4. §R5-1.0.c's stratum mechanism is refuted by primitives, and the "correction in place" pushed to `PREREG_FAILURE_S2.md` §2 is itself wrong.** The claim is that capped plies are "disproportionately ply-2", so S2 may be dense because it is capped-only, not because it is big. Measured: **S1 ply-2 share 35/1344 = 2.60%; S2 ply-2 share 28/1064 = 2.63%** — identical. And the same-currency contrast the drafter needed is available on the same two final builds: internal-dupe density **S1 858 games → 1/1344 = 0.074%; S2 5,340 games → 3/1064 = 0.282%** (3.8× on 6.22× the games — consistent with the fitted b ≈ 0.906). The growth story survives in the correct currency; the replacement mechanism does not. No consequence for R5 (it generates nothing), but it is now stated as a first-class finding in two documents.

**R5. `G-FAILED`'s denominator has no address.** The bound is `n_failed_rids / n_attempted ≤ 0.02` but the address list is `{n_failed_rids, rate, by_class}` — `n_attempted` is unpinned, which is precisely the read-time ambiguity D4.18 exists to prevent.

**R6. `G-SALT`'s `deployed_cap_j == 4` has no address.** The row's addresses cover `world_seed_salt` and `ARMS.json::<rid>.cap_seed` only. (The value 4 is in `FLOORS_R5.json`, which no gate reads.)

**R7. `G-CORPUS` contradicts itself in one row.** The conjunct says the physical leg file is the source "**not** the defective `POSITIONS_PLAN` `files` block", while the *address* is `POSITIONS_PLAN.json::{...}`. No address names the physical file (path + sha256). The pointer "(§0 note)" is **dangling** — READ_RULE §0 contains no such note. `CORPUS_UNION.json`, which DESIGN §R5-4 makes load-bearing, is addressed by no gate.

**R8. Stratum keying is inconsistent across the pair.** New addresses use `r5` (`digest_exclusions.r5`, `widening.completion.r5_n`); every carried address uses `s2` (the closed `allow_null` table's `widening.j_rider.s2.r_ora` / `.ci95_r_ora`, the §5 branch-table prints). The only mapping note — "`{s1,s2}` read as this run's single stratum" — sits inside one gate row and does not license the `r5` spelling. Under ABSENT IS FAIL one spelling or the other fails.

**R9. `FLOORS_R5.json` drops the seed provenance the design depends on.** R4's FLOORS carried `sub_ranges`, `extension_band`, `games_extension_s2`; R5's carries none. §R5-1.0.a's seed→generation-index mapping (and the `RAISE if out of range` rule) rests on those ranges, and with `G-BAND` dropped (B3) **nothing gates seed-range integrity, duplicate seeds, or the released-unused 136e9 band.** The ranges exist only in `CALIBRATION.json::config.generation_index_ranges` — an unaddressed file.

**R10. R5-2.2's committed k-rule was incapable of returning anything but 0.** "Smallest floor with `d_model ≤ 5%` AND supply ≥ floor" selects k=0 for any corpus clearing the guard at k=0, and the floor is itself derived from k=0's supply. The outcome (k=0) is right and the estimand argument is right; presenting it as a discretionary "bad trade" obscures that the pre-registered rule had one reachable answer.

**R11. §R5-8's banner is now false.** "Why the READ_RULE is not written yet" and the DESIGN's own STATUS block ("**DRAFT, NOT A PREREGISTRATION YET**", "the mechanical READ_RULE is **deliberately not written yet**") contradict §R5-FINAL and the shipped READ_RULE. A blind-commit pair must not carry a banner saying it is not one.

---

## COSMETIC

**C1.** `d_measured(G=5340)` (DESIGN §b, READ_RULE §2) names a field that is the fit's output — rename or read a measured field.
**C2.** Champ picks may be double-paid: `_positions_s2_pass1/POSITIONS_PLAN.json::champ_pick_secs = 77,262.96 s ≈ 21.5 wh` already spent on this substrate; R5 adds 4.1 wh. Conservative, so harmless.
**C3.** The 5.3–7.0 h wall implies W ≈ 43; `WORKERS.conf` gives `W_EVAL_LOCAL 30 + W_EVAL_LAPTOP 22 = 52` ⇒ 4.1–5.8 h. Conservative, but the ~83%-of-nameplate assumption is unstated.
**C4.** The calibration's saturation guard **fails open on null**: `saturation_void = (d_gov is not None) and (...)`, so floors 3/4 report `saturation_void: false` with `d_model_at_governed: null`. Not R5's path (k=0), but `recommended_ply_floor_k` inherits the hazard.
**C5.** §R5-5's cost table still prices `N` ∈ {700, 1100} — superseded by §R5-FINAL.g's realized 1,064; two cost tables with different totals (197–309 vs 226–301) in one document.

---

**Bottom line.** The M=32 correction is right and load-bearing, the retirement of `M × d_model` is arithmetically justified, and the supply/power/cost chain re-derives almost exactly. But the *replacement* for the retired bound is one pass-always gate (B2) and one fail-always gate (B1) over a corpus that has already been silently pre-cleaned of the very exclusions R4 voided on (B4), with the disjointness gate itself dropped (B3) — so the pair currently has **no live guard on the failure mode it was written to fix**, plus a pre-registered expectation its own data refutes (B5) and unmarked addresses under a rule that calls that a blocking drafting defect (B6). Do not blind-commit.
