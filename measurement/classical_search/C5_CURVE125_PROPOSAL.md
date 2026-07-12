# C5 curve125 — promotion proposal (DRAFT — Joshua's call, PRODUCTION.yaml untouched)

**Status: EVIDENCE COMPLETE 2026-07-12 (S1→S5 all measured) — AWAITING JOSHUA'S ADOPTION CALL (3 options in the S3 block). PRODUCTION.yaml untouched.**
**Proposed change:** `v29_meeple_curve: (-8,-4,-1,0,2,3,4,5) → (-10,-5,-1.25,0,2.5,3.75,5,6.25)` (production curve ×1.25 exactly; every other leaf tunable unchanged). One-line LeafConfig constant change; compute-neutral (S2 ms ratio 1.00x).

## Why it's believable (in order of strength)
1. **S2 n=400 confirm, FRESH band 1.24e10:** +66.8 elo ±17.7 (z≈3.8 unpaired), **paired_z 4.59**, W235/D6/L159 vs the exact champion-sibling at equal sims. `results.csv c5_s2_curve125_n400`.
2. **Coherent monotone axis in S1** (band 1.2e10, n=100/cell): curve OFF −92.5 (z−3.77) → ×0.75 −34.9 (z−1.65) → ×1.0 ≡0 → **×1.25 +81.4 (z2.05)** — a dose-response curve, not a lone-spike noise signature. `results.csv c5_curve*/c5_nocurve*`.
3. **Mechanism fits the C5 premise:** the meeple-commitment curve was tuned under random-expansion UCT (v2.9 era); PUCT+priors visits meeple-heavy lines far more selectively, so the old curve under-weights meeple commitment for the lines PUCT actually explores. The screen's other axes behaved sanely (opp_cap wings both negative = 8 confirmed; caps flat; bagclose null) — the harness discriminates in both directions.

## Pre-registered remaining gates
- **S3 fair re-confirm — ✅ RAN, verdict = POSITIVE-UNRESOLVED (2026-07-12):** fair curve125 **+115.2** vs h800 (131W/2D/67L) against the cached fair **+81.4** on the same 200 decks → **Δ +33.9 elo; CRN paired Δ +1.07 pts/deck, z = +0.58** (`c5_s3_curve125_fair/crn_delta.json`; results.csv row). **The pre-registered z≥2.0 fair gate is NOT met — but this is NOT the reuse/CLAIR-ONLY pattern:** there is no mechanism for a zero fair effect (the fair agent evaluates every leaf of every determinization with the same LeafConfig; a better leaf ranker transfers by construction, only the *magnitude* is uncertain under the ~120-elo tax), and the point estimate sits at half the clair effect, exactly where a real transfer would land. It is an **underpowered positive**: per-deck margin σ≈18 pts → resolving ~1 pt/deck at z≥2 needs **~1200 decks ≈ 3+ box-days** (both arms must extend to stay CRN-paired). **Decision for Joshua:** (a) fund the fair extension, (b) adopt on clair evidence + mechanism (the deployed agent shares the leaf; S2 is z4.6), or (c) adopt for the clair/dev config only. My read: (b) is defensible — unlike reuse there's no transfer-breaking mechanism — but it's a governance call above my pay grade.
- **S4 τ×curve interaction probe — ✅ CLEAN (2026-07-12): no interaction, τ5 stands.** Leaf-Δ(τ3) = +54.3±24.9 (paired_z 2.54) · leaf-Δ(τ5) = +66.8±17.7 (S2, z4.59) · leaf-Δ(τ8) = +56.1±24.9 (z1.38) — statistically indistinguishable, stable dose across the τ bracket (also retires the never-run R7 τ item). `results.csv c5_s4_*`.
- **S5 c_puct×curve probe — ✅ RAN (2026-07-12): c1.5 stands; mild attenuation flag at high c.** Leaf-Δ(c1.0) = +36.6±24.9 (z1.84) · leaf-Δ(**c1.5**) = **+66.8**±17.7 (S2) · leaf-Δ(c2.25) = +8.7±24.9 (z1.09). The gain is strongest at the production c1.5; the c2.25 attenuation is ~1.9σ vs the center — logged as a *possible* c×curve interaction (if c_puct is ever re-tuned, re-check the curve, and vice versa), not a blocker: the champion runs c1.5. Re-sweep box closed pre-adoption. `results.csv c5_s5_*`.

## If adopted (Joshua's decision, not before S3+S4 read out)
- PRODUCTION.yaml leaf block: the curve constant (+ note in `reuse_tree`-style provenance comment). New leaf tag = the S0 hash suffix (`leaf96d2c075`).
- Close-out: results.csv rows (already written per stage) · DECISIONS entry · CL-051 · CHECKPOINT_LINEAGE note (leaf-era change, net unchanged) · STATUS · roadmap C5 line → FIRED/FOLDED.
- **Re-sweep note (bug-fix-shifts-optima rule):** τ covered by S4; c_puct re-check {1.0, 2.25} at curve125 is the remaining 2-cell follow-up recommended post-adoption (cheap, non-blocking).
- ⚠️ Bystander hygiene item found during design: PRODUCTION.yaml `meeple_k: 2.0` is INERT (the Bmild curve replaces the flat term; flat_leaf.py:835-840) — remove or annotate in the same governance touch.

## Paper trail
Design: [C5_LEAF_RETUNE_DESIGN.md](C5_LEAF_RETUNE_DESIGN.md) · S0 harness `7605ef9` · cells+launcher `d3b0b73` · fair-harness override `f541323` (rung-side proven untouched) · S1 close-out `3f09fd5` · S2 confirm `f284681`. All rows in `experiments/results.csv` (`c5_*`); per-run manifests carry per-side leaf hashes.
