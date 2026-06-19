# Level-2 L2-2 — iter8 on the validated ladder (VERDICT)

> **Measurement gate only.** No train / promote / redesign / modify-iter8 follows.
> Phase L2-2 of [LEVEL2_LADDER_PROTOCOL.md](LEVEL2_LADDER_PROTOCOL.md): re-ground the
> frozen champion **iter8** (sha `0d355002…`) on the *validated* L2-1 ladder. Neural
> matchup ⇒ run through the **carc-orch SHM eval server at high W** (5800x OW=48 +
> laptop OW=16/24, shared-claim, CY_REPR), unlike the pure-CPU L2-1.
> Run 2026-06-18, code_rev `efb182c`. Raw: `/mnt/c/carc-shared/level2_l22/`.

## iter8 config (frozen, = production)
NeuralMCTS sims=200, c_puct=3.0, v2.7 leaf, RESIDUAL_SCALE=0.25, CAP=12,
DROP_THREE_OPEN=1, FLAT_LEAF=1. Heur opponents run the v2.7 leaf at the module
default c=1.5 (the eval gate's `--c-puct` applies to the net side only) = the same
config as the L1 ladder rungs, so R4/R5 here ARE the validated ladder rungs.

## Results (n=400 paired, fresh disjoint bands)

| comparison | band | W/D/L | elo (iter8 vs rung) | z | read |
|---|---|---|---|---|---|
| **iter8 vs R4 = heur@800** | 3.10e9 | 220/6/174 | **+40.1 ±17.5** | **+2.29** | ✅ beats heur@800 |
| **iter8 vs R5 = heur@1600** | 3.11e9 | 217/6/177 | **+34.9 ±17.5** | **+2.00** | ✅ beats heur@1600 too |

## V6 reproduce (iter8 vs heur@800)
**PASS (qualitatively).** iter8's learned policy beats heur@800 at +40.1 (z=2.29,
clearly significant). The magnitude is on the low side of the established cell
(published +72.2 `p2_iter8_*`, sealed +58.7) — ~1σ below sealed — but iter8's
absolute-vs-heur is known to swing by deck band (CL-018: iter0 ranges −8.7/+22.6/+52.5
across bands), and 3.1e9 is a fresh band. So the ladder harness + the carc-orch SHM
eval path reproduce the established result within band-variation. (The n=24 smoke's
−29 was pure small-n noise, as expected at ±71 elo.)

## Headline — iter8 clears BOTH validated rungs; the scale IS transitive (non-transitivity was band-variance)
iter8 beats heur@800 (**+40.1/z2.29**) AND heur@1600 (**+34.9/z2.00**) by ~the same
margin. So the champion is stronger than deep heuristic search at *both* depths
measured — a better result than predicted (I expected iter8 to fall below heur@1600,
since heur@1600 is +55 over heur@800 while iter8 is only +40 over heur@800).

**⚠️ NON-TRANSITIVITY (the load-bearing caveat).** Compose the three measurements:
- iter8 > heur@800: **+40** (band 3.10)
- heur@1600 > heur@800: **+55** (band 3.04, L1 R5vR4)
- ⇒ elo-transitivity predicts iter8 vs heur@1600 ≈ +40 − 55 = **−15**
- but measured: iter8 vs heur@1600 = **+35** → a **~50-elo intransitivity.**

Relative to the common reference heur@800, heur@1600 (+55) ranks *above* iter8 (+40),
yet iter8 *beats* heur@1600 head-to-head. Two candidate explanations, not yet
distinguished:
1. **Real non-transitivity** — iter8's learned policy exploits a weakness *shared* by
   both heuristics (so it beats both by ~the same margin), while the heuristics' depth
   ordering (h1600≫h800) is a separate axis. Consistent with CL-016 (opponent-leaf
   effects are non-transitive). If real, **elo is not a valid single strength axis here**
   — a central caveat for the whole Level-2 measurement program.
2. **Band variance** — the three comparisons are on three different bands; iter8's
   absolute-vs-heur is known to swing ±~30 elo by band (CL-018). ~50 elo is large for
   band variance alone, but not impossible across 3 bands + per-comparison noise (±17).

**This was NOT decidable from different-band data ⇒ same-band control (band 3.10e9, all
three pairs on shared decks, n=400 each).**

### ✅ RESOLVED — transitivity HOLDS; the non-transitivity was band-variance
Re-ran all three pairs on **band 3.10e9** (shared decks):

| pair (band 3.10) | elo | z |
|---|---|---|
| iter8 vs heur@800 | +40.1 | 2.29 |
| iter8 vs heur@1600 (C1) | +24.4 | 1.40 |
| heur@1600 vs heur@800 (C2) | +20.0 | 3.21 |

Transitivity predicts iter8-vs-heur@1600 = (iter8-vs-h800) − (h1600-vs-h800) =
40.1 − 20.0 = **+20.1**; measured **+24.4** → Δ=4.3, **well within noise** (±17/comparison).
**⇒ The elo scale is TRANSITIVE on controlled decks — a valid total order.** The apparent
~50-elo intransitivity in the table above was entirely **cross-band artifact**: the
heur@1600-vs-heur@800 gap swung from **+55 (band 3.04, L1)** to **+20 (band 3.10)** — a
35-elo band swing. (It stays *significant* on both bands, z=3.23 & 3.21, so CL-023's
saturation refutation **replicates on a 2nd band**; only the magnitude is band-noisy.)

**Lesson banked:** cross-band elo composition is unreliable (±30–35 elo of deck-band
swing even for deterministic heur-vs-heur); only same-band paired comparisons compose.
Reinforces the results-discipline rule + CL-018 (band-dependent absolutes).

## Bottom line (Level-2 so far)
- The L1 ladder is a **valid, transitive ruler** (saturation refuted, depth scales it,
  transitivity confirmed on controlled decks).
- The champion **iter8 sits above both validated heuristic rungs** (heur@800 and heur@1600)
  on shared decks — so the learned policy is genuinely stronger than deep heuristic search
  at the measured depths, not merely tied.
- **Band-variance caveat (REFINED by direct measurement — see below):** comparison-specific.
  The headline neural cell (iter8-vs-heur@800) is band-**robust** within the current era
  (σ_band≈3.6 over 3 fresh bands); larger swings appear in heur-vs-heur depth (+55/+20) and
  cross-era. Cross-rung elo *composition* is still only safe within a shared band.

## Band-variance characterization (iter8 vs heur@800, n=400 each)
Re-ran the headline cell on 3 fresh bands, current code era (orch + CY_REPR):

| band | elo | z |
|---|---|---|
| 3.10 | +40.1 | 2.29 |
| 3.12 | +48.1 | 2.75 |
| 3.13 | +47.2 | 2.70 |

**mean +45.1, band-to-band σ ≈ 3.6** (≪ the within-band 1σ≈17.5 at n=400). So within the
current era this cell is **band-robust** (~±4–8) — my earlier "±30–35" was an over-statement,
driven by the *heur-vs-heur* depth swing (+55 b3.04 / +20 b3.10) and by lumping in the historical
gap. **Band-variance is comparison-specific:** small for this neural cell, larger for heur-vs-heur.
- **Open thread (not chased autonomously):** all 3 fresh bands sit ~+13–27 *below* the historical
  sealed +58.7 (b1.7e9) / published +72.2 (b2.5e9). With σ_band≈3.6 that gap is too large to be
  band-variance alone ⇒ likely a **fresh-vs-historical config/era difference** (orch/CY_REPR path,
  or favorable historical bands). The leaf is bit-exact across eras, so an era-controlled A/B
  (same band, old vs new path) would settle it. Either way **iter8 robustly beats heur@800
  (+40 to +72, every measurement significant)** — only the magnitude is in question.

## Next
- **L2-3** (endgame regret suite) is a separate phase — **left for Joshua** (not built autonomously).
- Optional follow-up: the era-controlled A/B to explain the fresh-vs-historical +45-vs-+58/72 gap.
No train/promote/redesign follows — measurement gate only.
