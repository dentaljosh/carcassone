# Results Digest

Human-readable digest of the key numbers. **Every value cites a `results.csv` row name
(see [sources/results_csv_relevant_rows.csv](sources/results_csv_relevant_rows.csv)) and/or a
verdict file.** No number here is invented; rounding follows the verdict docs.

**Universal caveats:** all elo is **clairvoyant, in-ecosystem (v2.7-leaf ruler), not human-anchored**.
n=400 paired ≈ **±17.5 elo (1σ)**; n=200 paired ≈ **±24.6 elo (1σ)**. "z" is the **paired** z unless
noted. Cross-band elo composition is unreliable (stacks noise) — **only same-band paired comparisons
compose.**

---

## A. Attempt / champion history

### A1. iter8 vs original baselines
| comparison | plane | band | W/D/L | elo | z | source row |
|---|---|---|---|---|---|---|
| **iter8 vs incumbent `residual.pt` (=iter0)** — SEALED | s200 | 1.7e9 | — | **+67.4** (paired Δ) | **2.73** | `flywheel2_SEALED_champ_iter8…` − `…_iter0…` |
| iter0 (`residual.pt`) vs heur@800-v2.7 | s200 | 1.7e9 | 193/4/203 | −8.7 | — | `flywheel2_SEALED_iter0_vs_heur800_v27_n400` |
| iter8 vs heur@800-v2.7 (sealed) | s200 | 1.7e9 | 232/3/165 | +58.7 | — | `flywheel2_SEALED_champ_iter8_vs_heur800_v27_n400` |
| iter8 vs heur@800-v2.7 (published) | s200 | 2.5e9 | 237/8/155 | +72.2 | — | `p2_iter8_vs_heur800_v27_s200_n400` |
| iter8 vs heur@800-v2.7 (deep) | s800 | 2.5e9 | 274/7/119 | +142.1 | — | `p2_iter8_vs_heur800_v27_s800_n400` |

> The crowning result is the **paired** Δ(iter8 − iter0) = **+67.4 / z=2.73** on the sealed
> out-of-lineage ruler. iter0 *is* `residual.pt` (the incumbent), both scored vs the same anchor →
> this is a real strength gain, not anchor-lie. **Bounded:** gain plateaus by ~iter5, ~95% policy
> (CL-018; decomp `stageB_decomp_*`).

### A2. deepteacher iter12 vs iter8 (clean fresh band 2.5e9, n=400 paired)
| plane | iter8 elo | iter12 elo | **Δ(iter12−iter8)** | z | iter12 W/D/L | read |
|---|---|---|---|---|---|---|
| **s200** | +72.2 | +86.9 | **+14.6** | **0.65** | 246/6/148 | TIE |
| **s800** | +142.1 | +154.5 | **+12.4** | **0.51** | 280/7/113 | TIE |

Rows: `p2_iter{8,12}_vs_heur800_v27_s{200,800}_n400`. Verdict:
[sources/ITER8_VS_ITER12_VERDICT.md](sources/ITER8_VS_ITER12_VERDICT.md). Both = powered nulls for a
≥+24 elo effect. **Champion stays iter8.**

> ⚠️ **STALE / MISLABELED (do not cite as "vs iter8"):** the deepteacher *published* "sealed
> +8.1/z0.34 (s800)" and "washout +82.8/z3.48 (s200)" were measured **vs `residual.pt`**, not iter8
> (provenance defect CL-020). Against the real warm-from iter8 the s200 gain is +15.3/z0.68 (within
> noise). See [sources/DEEPTEACHER_PROVENANCE_AUDIT.md](sources/DEEPTEACHER_PROVENANCE_AUDIT.md).

---

## B. Heuristic ladder (pure heur-vs-heur, v2.7 leaf, c=1.5; paired, fresh bands)
| step | higher vs lower | n | W/D/L | elo | z | flag |
|---|---|---|---|---|---|---|
| R1vR0 | greedy vs random | 200 | 200/0/0 | +800 (cap) | 55.62 | clean floor |
| R2vR1 | heur_v1@200 vs greedy | 200 | 107/1/92 | +26.1 | 1.87 | compressed |
| R3vR2 | heur_v2.7@200 vs heur_v1@200 | 200 | 106/2/92 | +24.4 | 1.68 | compressed |
| **R4vR3** | **heur@800 vs heur@200** | 200 | 120/3/77 | **+75.9** | **3.59** | ✅ clean |
| **R5vR4** | **heur@1600 vs heur@800** | 400 | 228/7/165 | **+55.2** | **3.23** | ✅ saturation REFUTED |
| **R5'vR5** | **heur@3200 vs heur@1600** | 400 | 217/6/177 | **+34.9** | **2.36** | ✅ clean (n=200 was +43.7/z1.68, under-power) |

Rows: `l2_ladder_R1vR0…` → `l2_ladder_R5bvR5_heurv27s3200_vs_heurv27s1600_n400`. Verdict:
[sources/LEVEL2_LADDER_VERDICT.md](sources/LEVEL2_LADDER_VERDICT.md).

- **Depth headroom continues with diminishing returns:** per-doubling +75.9 → +55.2 → +34.9. The
  heuristic ruler is **not saturated even at @1600**.
- **Leaf quality / low-sim search are compressed** (greedy ≈ v1@200 ≈ v2.7@200, each ~+25/z≈1.7).
  **Depth, not leaf design, moves the ruler.**

> **⚠️ Deck-band variance & same-band requirement.** The heur@1600-vs-heur@800 step is **+55.2 on
> band 3.04** (R5vR4) but **+20.0 on band 3.10** (`l22_ctrl_heur1600_vs_heur800_b310_n400`, z3.21) — a
> ~35-elo magnitude swing (the *sign/significance* replicates; only magnitude moves). The difference
> is itself only ~1.4σ (within noise). **Lesson:** compose only same-band paired comparisons.

---

## C. iter8 placement on the validated ladder (same-band 3.10e9, n=400 paired, sims=200)
| comparison | W/D/L | elo | z | source row |
|---|---|---|---|---|
| iter8 vs **heur@800** | 220/6/174 | **+40.1** | 2.29 | `l22_iter8_vs_heur800_v27_s200_n400` |
| iter8 vs **heur@1600** (same-band control) | 213/2/185 | **+24.4** | 1.40 | `l22_ctrl_iter8_vs_heur1600_b310_n400` |
| iter8 vs **heur@3200** | 180/7/213 | **−28.7** | −0.70 | `l22_iter8_vs_heur3200_b310_n400` |

Verdict: [sources/LEVEL2_L22_VERDICT.md](sources/LEVEL2_L22_VERDICT.md).

- **Monotone, erased by @3200:** +40.1 → +24.4 → −28.7. iter8 beats heuristic search up to ~@1600 and
  is caught at @3200.
- iter8 vs heur@1600 on a *different* band (3.11e9) read +34.9/z2.0 (`l22_iter8_vs_heur1600_v27_s200_n400`);
  the same-band control (+24.4) is the authoritative composing value. Scale is **transitive** on
  shared decks (40.1 − 20.0 = 20.1 predicted vs 24.4 measured, within noise).
- **Apparatus check:** `l22_orchoff_iter8_vs_heur800_b310_n400` = 220/6/174 = +40.1, **bit-identical**
  to the orch+CY run → zero eval-path bias.

---

## D. Clairvoyance gap (band 2.7e9, paired, vs heur@800-v2.7, sims=200)
| arm | search | n | W/D/L | winrate | elo vs heur (±1σ) | avg pts diff | source row |
|---|---|---|---|---|---|---|---|
| **CLAIR** | clairvoyant (true deck order), K=1 | 200 | 119/0/81 | 0.595 | **+66.8** (±25.0) | +5.41 | `clairvoyance_clair_iter8…s200_n200` |
| **NONCLAIR** | K=12 root-determinization, best_action pooled | 182 | 100/3/79 | 0.558 | **+40.3** (±25.9) | +2.79 | `clairvoyance_nonclair_iter8_K12…s200_n182` |

**Gap = clair − nonclair = +26.6 elo, paired z = −0.9** (not distinguishable from 0). P(gap≥100) ≈ 2%.
Verdict: [sources/CLAIRVOYANCE_GAP_VERDICT.md](sources/CLAIRVOYANCE_GAP_VERDICT.md) (CL-022).

**Interpretation:** clairvoyance is a **small-to-moderate** contributor (~25–30 elo), not a
decision-changing artifact. A non-clairvoyant agent keeps essentially all of iter8's strength
(+40 vs heur@800). The CLAIR arm reproduces the published +72.2 within CI → harness validated. (sims=200
only; the gap crept up with n — +16 → +21 → +27 — so "small-to-moderate," not "negligible.")

---

## E. Hybrid handoff (band b340, paired, sims=200; iter8 production config → HeuristicMCTS@N endgame)

### E1. Phase 1 — hybrid:K vs iter8 (PATCHABLE)
| hybrid (vs iter8) | n | W/D/L | winrate | elo | paired margin (pts/game) | paired z |
|---|---|---|---|---|---|---|
| K≤2 → heur@3200 | 200 | 97/8/95 | 0.505 | +3.5 | +0.36 | +2.65 |
| K≤3 → heur@3200 | 200 | 96/8/96 | 0.500 | +0.0 | +0.25 | +1.18 |
| K≤5 → heur@3200 | 200 | 100/6/94 | 0.515 | +10.4 | +0.80 | +3.45 |
| K≤8 → heur@3200 | 200 | 103/6/91 | 0.530 | +20.9 | +1.36 | +4.68 |
| K≤5 → heur@**800** (cost sanity) | 200 | 101/5/94 | 0.517 | +12.2 | +0.60 | +2.89 |
| **K≤5 (n=400 top-up)** | 400 | — | — | — | **+0.90** | **+6.23** |
| **K≤8 (n=400 top-up)** | 400 | — | — | — | **+1.32** | **+5.79** |

Rows: `l2hyb_K{2,3,5,8}h3200_vs_iter8_b340_n200`, `l2hyb_K5h800_vs_iter8_b340_n200`. Monotone in K;
reproduced at n=400; cheap heur@800 endgame captures most of the gain.

### E2. Phase 2 — hybrid:K vs heur@3200 (the champion question)
| hybrid vs heur@3200 | n | W/D/L | winrate | elo | paired margin | paired z |
|---|---|---|---|---|---|---|
| K≤5 → heur@3200 | 200 | 94/4/102 | 0.480 | **−13.9** | −0.43 | −0.30 |
| K≤8 → heur@3200 | 200 | 92/5/103 | 0.472 | **−19.1** | −0.76 | −0.51 |

Rows: `l2hyb_K{5,8}h3200_vs_heur3200_b340_n200`. Verdict:
[sources/LEVEL2_HYBRID_VERDICT.md](sources/LEVEL2_HYBRID_VERDICT.md) (CL-026).

**Read:** both hybrids **lose** to heur@3200 at |z|<1 (tie-to-slight-loss) — better than plain iter8's
−28.7, but they do **not** surpass the deep heuristic. **Gap-closing, NOT a new champion. Nothing
promoted.** (Single band b340; Phase-1 reproduced at n=400 on the *same* band, not a 2nd band.)

---

## F. Solver-grounded endgame (exact minimax / alpha-beta; first non-circular labels)

### F1. K=2 / K=3 summary (clairvoyant; CL-025)
**K=2** (150 positions, 141 decision; band 3.2e9). top-1 (fraction agent's move is solver-optimal):
| agent | top-1 | mean regret | >5 pt |
|---|---|---|---|
| heur@3200 | **0.837** | 0.40 | 1.4% |
| heur_v1@200 | **0.837** | 0.37 | 0.7% |
| heur@1600 | 0.780 | 0.46 | 1.4% |
| greedy | 0.759 | 0.74 | 2.8% |
| heur@800 | 0.759 | 0.52 | 1.4% |
| **iter8** | **0.667** | 0.61 | 1.4% |

**K=3** (partial, 68 decision positions, clairvoyant — suite OOM-truncated to 74/150 at W=20):
iter8 again **worst** (top-1 **0.574**, highest mean regret 0.96). Deficit is depth-robust. Verdict:
[sources/LEVEL2_L23_VERDICT.md](sources/LEVEL2_L23_VERDICT.md); data
[sources/L23_REGRET_RESULTS.json](sources/L23_REGRET_RESULTS.json).

> Blunders are rare and small (no agent ever loses >10 pts at K=2). iter8's errors are
> **bidirectional**: its single worst is 9 pts, but it is optimal where heuristics blunder up to 6 pts
> → "less precise," not "uniformly worse." **Not an Elo statement** (iter8 still wins full games).

### F2. K=4 full result (exact alpha-beta clairvoyant solver; CL-027)
**Suite:** 200 balanced positions (50 each from greedy / iter8 / heur@3200 / hybrid:8:3200), **187
solved (94%)**, 13 genuine 1M-node budget-hits. Verdict:
[sources/LEVEL2_K4_PROBE_VERDICT.md](sources/LEVEL2_K4_PROBE_VERDICT.md); data
[sources/K4_PROBE_RESULTS.json](sources/K4_PROBE_RESULTS.json).

**Overall (n=187), top-1:**
| agent | top-1 | mean regret | >2 pt | >5 pt |
|---|---|---|---|---|
| **heur@3200** | **0.679** | 1.07 | 0.134 | 0.053 |
| heur@800 | 0.652 | 1.214 | 0.144 | 0.064 |
| greedy | 0.647 | 1.326 | 0.160 | 0.080 |
| **iter8** | **0.561** | 1.481 | 0.198 | 0.064 |

**Source breakdown** (top-1 by which agent generated the endgame; the multi-source disentangler):
| positions from → | iter8 | heur@3200 | heur@800 | greedy | n |
|---|---|---|---|---|---|
| iter8-generated | 0.646 | 0.729 | 0.708 | **0.750** | 48 |
| heur@3200-gen | 0.583 | 0.729 | 0.688 | 0.646 | 48 |
| hybrid-gen | 0.562 | 0.667 | 0.604 | 0.604 | 48 |
| greedy-generated | **0.442** | 0.581 | 0.605 | 0.581 | 43 |

**Difficulty by source** (within1 = # moves within 1 pt of optimal; randReg = random-legal regret):
| source | n_within1 (med) | randReg (med) | iter8 top-1 |
|---|---|---|---|
| iter8-gen | 28.5 | 1.1 | 0.646 |
| heur@3200-gen | 24.0 | 1.1 | 0.583 |
| greedy-gen | 7 | 1.9 | 0.442 |
| hybrid-gen | 6 | 2.0 | 0.562 |

**Sharpness split** (best-vs-2nd-best gap):
| split | n | iter8 top-1 | iter8 mean regret | heur@3200 top-1 |
|---|---|---|---|---|
| forgiving (gap<2) | 149 | 0.604 | 1.007 | 0.738 |
| sharp (gap≥2) | 38 | **0.395** | **3.342** | 0.447 |

**The 3 hypotheses (CL-027):**
- **H1 ("iter8 near-optimal on its own endgames") — NOT supported.** The pilot's 0.92/0.36 was n=12
  noise; real = 0.65 on its own source (beaten there by greedy 0.75 & heur@3200 0.73). iter8-generated
  endgames are objectively *easier* (within1=28.5, randReg=1.1).
- **H2 ("iter8 worst on sharper/OOD endgames") — SUPPORTED** (greedy-source 0.44; sharp gap≥2 top-1
  0.40, mean regret 3.34 — worst of all agents).
- **H3 ("heuristics generalize across sources, iter8 does not") — SUPPORTED** (heur@3200 0.58–0.73;
  iter8 most variable 0.44–0.65).

**Source breakdown of the 13 excluded budget-hits:** greedy 7, heur@3200 2, hybrid 2, iter8 2. These
**exceed** the 1M-node budget even uncapped (higher-branching: unsolved legalN med 49 vs solved 40) →
correct selection-bias data, **not failures**. Because the 7 sharpest greedy positions are dropped,
the by-source greedy column (iter8 0.44) is **conservative**.

**K=4 caveats:** clairvoyant (perfect-information) labels **only** — marginalized/bag-expectation GT is
untested at K=4 (needs make/unmake). Regrets small in absolute points (mean 1.07–1.48) → the **rank**
is the signal, not the magnitude. Single band (suite `038f7ec`). In-ecosystem v2.7 ruler. Solver
gated bit-equal vs the no-prune oracle on K=2/K=3 (0 mismatch).
