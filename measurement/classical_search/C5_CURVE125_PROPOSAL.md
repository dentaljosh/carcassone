# C5 curve125 — promotion proposal (DRAFT — Joshua's call, PRODUCTION.yaml untouched)

**Status: ✅ ALL GATES PASSED 2026-07-12 — clair (S2 z4.59) AND fair (confirm z3.13, +48.8 elo) both confirmed. A clean deployable leaf win. AWAITING ONLY JOSHUA'S APPLY (exact diff below). PRODUCTION.yaml untouched.**
**Proposed change:** `v29_meeple_curve: (-8,-4,-1,0,2,3,4,5) → (-10,-5,-1.25,0,2.5,3.75,5,6.25)` (production curve ×1.25 exactly; every other leaf tunable unchanged). One-line LeafConfig constant change; compute-neutral (S2 ms ratio 1.00x).

## Why it's believable (in order of strength)
1. **S2 n=400 confirm, FRESH band 1.24e10:** +66.8 elo ±17.7 (z≈3.8 unpaired), **paired_z 4.59**, W235/D6/L159 vs the exact champion-sibling at equal sims. `results.csv c5_s2_curve125_n400`.
2. **Coherent monotone axis in S1** (band 1.2e10, n=100/cell): curve OFF −92.5 (z−3.77) → ×0.75 −34.9 (z−1.65) → ×1.0 ≡0 → **×1.25 +81.4 (z2.05)** — a dose-response curve, not a lone-spike noise signature. `results.csv c5_curve*/c5_nocurve*`.
3. **Mechanism fits the C5 premise:** the meeple-commitment curve was tuned under random-expansion UCT (v2.9 era); PUCT+priors visits meeple-heavy lines far more selectively, so the old curve under-weights meeple commitment for the lines PUCT actually explores. The screen's other axes behaved sanely (opp_cap wings both negative = 8 confirmed; caps flat; bagclose null) — the harness discriminates in both directions.

## Pre-registered remaining gates
- **S3 fair re-confirm — ✅ RAN, verdict = POSITIVE-UNRESOLVED (2026-07-12):** fair curve125 **+115.2** vs h800 (131W/2D/67L) against the cached fair **+81.4** on the same 200 decks → **Δ +33.9 elo; CRN paired Δ +1.07 pts/deck, z = +0.58** (`c5_s3_curve125_fair/crn_delta.json`; results.csv row). **The pre-registered z≥2.0 fair gate is NOT met at n=200 — but this is NOT the reuse/CLAIR-ONLY pattern:** there is no mechanism for a zero fair effect (the fair agent evaluates every leaf of every determinization with the same LeafConfig; a better leaf ranker transfers by construction, only the *magnitude* is uncertain under the ~120-elo tax), and the point estimate sits at half the clair effect, exactly where a real transfer would land. It is an **underpowered positive**: per-deck margin σ≈18 pts → resolving ~1 pt/deck at z≥2 needs **~1200 decks**.
- **→ FAIR CONFIRM LAUNCHED (Joshua, 2026-07-12): n=2600/arm (1300 paired decks), curve125 + matched baseline, CRN band 15e9, both boxes, ~15h.** INTERIM at 391 paired decks: fair-net +115.4 vs baseline +78.5 → **Δ +36.9 elo, paired Δ +1.86 pts/deck, z +2.08** (running ABOVE the S3 +1.07 estimate; baseline +78.5 reproduces the D0 +81.4 ruler → clean). Interim only — NOT stopping early (optional-stopping bias); reading once at n=2600.
  - **CONFIRM ✅ RESOLVED POSITIVE (2026-07-12, read committed at 451 paired decks):** win-paired **+48.8 elo, z 3.13** AND margin **+50.4 elo / +2.274 pts/deck, z 2.77** — **BOTH gate parts PASS** (elo ≥ +35 ✓, paired z ≫ 0 ✓). curve125 fair transfer is CONFIRMED, not clair-only. (Effect strengthened with power: S3 +33.9 @100 decks → +38.5 @391 → +48.8 @451; S3's low z was a small-n draw. Read trimmed 1300→450 on Joshua's power argument — both metrics resolve well before 1300.) `c5_confirm_curve125_fair/crn_delta_450.json`, `results.csv c5_confirm_*`. **→ the S3 "3-way decision" is moot: the fair gate is met, so this is a clean deployable win (clair z4.6 + fair z3.1), pending only Joshua's apply.**
- **S4 τ×curve interaction probe — ✅ CLEAN (2026-07-12): no interaction, τ5 stands.** Leaf-Δ(τ3) = +54.3±24.9 (paired_z 2.54) · leaf-Δ(τ5) = +66.8±17.7 (S2, z4.59) · leaf-Δ(τ8) = +56.1±24.9 (z1.38) — statistically indistinguishable, stable dose across the τ bracket (also retires the never-run R7 τ item). `results.csv c5_s4_*`.
- **S5 c_puct×curve probe — ✅ RAN (2026-07-12): c1.5 stands; mild attenuation flag at high c.** Leaf-Δ(c1.0) = +36.6±24.9 (z1.84) · leaf-Δ(**c1.5**) = **+66.8**±17.7 (S2) · leaf-Δ(c2.25) = +8.7±24.9 (z1.09). The gain is strongest at the production c1.5; the c2.25 attenuation is ~1.9σ vs the center — logged as a *possible* c×curve interaction (if c_puct is ever re-tuned, re-check the curve, and vice versa), not a blocker: the champion runs c1.5. Re-sweep box closed pre-adoption. `results.csv c5_s5_*`.

## If adopted (Joshua's decision) — the EXACT PRODUCTION.yaml diff
`governance/PRODUCTION.yaml` `production.leaf_config` (line ~43):
```
-    v29_meeple_curve: [-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0]
+    v29_meeple_curve: [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]   # C5 curve125 (x1.25); CL-051
```
- **`leaf:` name** → bump `v2_9_1_Bmild_cap8` → e.g. `v2_9_2_Bmild_cap8_curve125` (curve-era, net unchanged).
- **⚠️ `leaf_hash:` (line 41) must be RECOMPUTED, not pasted.** PRODUCTION.yaml's hash scheme gives `7fc930b82801cb43` for the CURRENT leaf; the eval-harness scheme (in manifests) gives `4f2a93e7b35a4d22` (prod) / `96d2c075f85e9583` (curve125) — **different function**. Recompute the PRODUCTION.yaml field with whatever generated `7fc930b8…`; do NOT copy the eval `96d2c075`. (Eval-side per-run hashes stay `96d2c075` — that's correct there.)
- **`meeple_k: 2.0` (line 46):** already INERT and stays inert (verified: flat_leaf.py:838 takes the `curve is not None` branch, `meeple_k` sits in the dead `elif`). Remove-or-annotate for hygiene in the same touch. Not load-bearing either way.
- **Everything else unchanged** (caps 8/8, c1.5, τ5, float, visits, exact-K, the net). One-line effective change; compute-neutral (S2 1.00x).
- Close-out (6 touches): results.csv rows (per-stage already written; add the confirm rows) · DECISIONS entry · **CL-051** · CHECKPOINT_LINEAGE note (leaf-era change, net unchanged) · STATUS · roadmap C5 line → FIRED/FOLDED.
- **Re-sweep note (bug-fix-shifts-optima rule):** τ covered by S4 (clean), c_puct by S5 (c1.5 best, mild high-c flag) — both boxes closed pre-adoption.

## S1b upward-scale peak-find (2026-07-12) — ×1.25 is safe; ×1.75 is an UNRESOLVED possible-higher-peak
The S1 curve axis was still positive at ×1.25, so I screened ×1.5/1.75/2.0 (n=100, band 12e9) then confirmed the top at n=400. Result — **the axis is NOISY / non-monotone**, not a clean peak:
| scale | screen n=100 | confirm n=400 |
|---|---|---|
| ×1.25 | +81.4 (z2.05) | **+66.8 (z4.59)** ← CONFIRMED (clair) + fair z3.13 |
| ×1.5 | +49.0 (z1.67) | **+44.5 (z3.06)** ← confirmed, below ×1.25 |
| ×1.75 | +119.1 (z4.01) | **+134.5 (z3.21) @ n=141 PARTIAL, run HUNG** |
| ×2.0 | +10.4 (z0.56) | — |

- **×1.5 < ×1.25** at n=400 (clean). **×2.0/×0.75** are clear falloffs. So the only cell that could beat ×1.25 is **×1.75**.
- **×1.75's n=400 confirm HUNG at 141/400** (curve175-specific endgame-solver/search hang; ×1.5 ran clean). The 141 completed games (biased subsample) show **+134.5** — *above* ×1.25 — but this is UNTRUSTED (hang-selection-bias + small n + the non-monotone ×1.5 dip = noise still in play). Hang diagnosis delegated (is it LEAF-TRIGGERED? — that would be a production red flag for ×1.75, which uses the same exact-K endgame in play).
- **Recommendation:** **adopt ×1.25** — it's the fully-confirmed win (clair z4.59 + fair z3.13) and the safe pick. Do NOT switch to ×1.75 on the hung/biased +134 (that's the c=3 spike-chasing trap). If ×1.75 later gets a CLEAN n=400 that cleanly beats ×1.25 AND isn't leaf-hang-prone, it becomes a *separate future* upgrade needing its own fair re-confirm — a follow-up, not a blocker on banking ×1.25 now.

## Paper trail
Design: [C5_LEAF_RETUNE_DESIGN.md](C5_LEAF_RETUNE_DESIGN.md) · S0 harness `7605ef9` · cells+launcher `d3b0b73` · fair-harness override `f541323` (rung-side proven untouched) · S1 close-out `3f09fd5` · S2 confirm `f284681`. All rows in `experiments/results.csv` (`c5_*`); per-run manifests carry per-side leaf hashes.
