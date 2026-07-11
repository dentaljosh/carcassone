# C5 curve125 — promotion proposal (DRAFT — Joshua's call, PRODUCTION.yaml untouched)

**Status: DRAFT 2026-07-11 — S1+S2 clair evidence in; S3 fair re-confirm RUNNING; S4 τ-interaction probe queued.**
**Proposed change:** `v29_meeple_curve: (-8,-4,-1,0,2,3,4,5) → (-10,-5,-1.25,0,2.5,3.75,5,6.25)` (production curve ×1.25 exactly; every other leaf tunable unchanged). One-line LeafConfig constant change; compute-neutral (S2 ms ratio 1.00x).

## Why it's believable (in order of strength)
1. **S2 n=400 confirm, FRESH band 1.24e10:** +66.8 elo ±17.7 (z≈3.8 unpaired), **paired_z 4.59**, W235/D6/L159 vs the exact champion-sibling at equal sims. `results.csv c5_s2_curve125_n400`.
2. **Coherent monotone axis in S1** (band 1.2e10, n=100/cell): curve OFF −92.5 (z−3.77) → ×0.75 −34.9 (z−1.65) → ×1.0 ≡0 → **×1.25 +81.4 (z2.05)** — a dose-response curve, not a lone-spike noise signature. `results.csv c5_curve*/c5_nocurve*`.
3. **Mechanism fits the C5 premise:** the meeple-commitment curve was tuned under random-expansion UCT (v2.9 era); PUCT+priors visits meeple-heavy lines far more selectively, so the old curve under-weights meeple commitment for the lines PUCT actually explores. The screen's other axes behaved sanely (opp_cap wings both negative = 8 confirmed; caps flat; bagclose null) — the harness discriminates in both directions.

## Pre-registered remaining gates
- **S3 fair re-confirm (RUNNING):** fair PIMC (kd8×s344, blind) with curve125 vs unchanged clairvoyant h800 on the EXACT cached D0 decks (band 15e9, n=200 paired) → CRN-paired Δ vs fair +81.4. **Gate: Δ>0 with paired z ≥ 2.0.** A clair-only win gets graded CLAIR-ONLY (like reuse CL-044) and is NOT proposed for the deployed fair config (clair dev config only).
  - S3 result: **[PENDING]**
- **S4 τ×curve interaction probe (queued):** leaf-Δ at τ_p∈{3,8} (shared-axis cells) vs S2's leaf-Δ(τ5)=+66.8. Stable Δ ⇒ τ5 stands; wild variation ⇒ direct τ A/B before the proposal number is final.
  - S4 result: **[PENDING]**

## If adopted (Joshua's decision, not before S3+S4 read out)
- PRODUCTION.yaml leaf block: the curve constant (+ note in `reuse_tree`-style provenance comment). New leaf tag = the S0 hash suffix (`leaf96d2c075`).
- Close-out: results.csv rows (already written per stage) · DECISIONS entry · CL-051 · CHECKPOINT_LINEAGE note (leaf-era change, net unchanged) · STATUS · roadmap C5 line → FIRED/FOLDED.
- **Re-sweep note (bug-fix-shifts-optima rule):** τ covered by S4; c_puct re-check {1.0, 2.25} at curve125 is the remaining 2-cell follow-up recommended post-adoption (cheap, non-blocking).
- ⚠️ Bystander hygiene item found during design: PRODUCTION.yaml `meeple_k: 2.0` is INERT (the Bmild curve replaces the flat term; flat_leaf.py:835-840) — remove or annotate in the same governance touch.

## Paper trail
Design: [C5_LEAF_RETUNE_DESIGN.md](C5_LEAF_RETUNE_DESIGN.md) · S0 harness `7605ef9` · cells+launcher `d3b0b73` · fair-harness override `f541323` (rung-side proven untouched) · S1 close-out `3f09fd5` · S2 confirm `f284681`. All rows in `experiments/results.csv` (`c5_*`); per-run manifests carry per-side leaf hashes.
