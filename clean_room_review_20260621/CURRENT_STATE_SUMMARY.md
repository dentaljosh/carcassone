# Current Scientific State — Summary (2026-06-21)

Concise but complete state. Each item cites a source under [sources/](sources/) and/or a
`results.csv` row. Epistemic tags inline; a consolidated **Facts / Interpretations / Speculation**
split closes the document.

---

## 1. iter8 champion status
- iter8 (`0d355002…`) is the **production champion of record**, folded in 2026-06-11
  ([sources/PRODUCTION.yaml](sources/PRODUCTION.yaml), CL-005).
- The win that crowned it: **+67.4 elo / z=2.73** over the incumbent (`residual.pt`, == iter8's
  own iter0) on a **sealed, out-of-lineage** heur@800-v2.7 ruler, n=400 paired, band 1.7e9
  (`flywheel2_SEALED_champ_iter8_vs_heur800_v27_n400` vs `…_iter0_…`: iter0 −8.7, iter8 +58.7).
  This is a **real strength gain vs an independent ruler**, not the anchor-lie failure mode
  (CL-018, CL-005).
- **Bounded, not open-ended:** the gain plateaus by ~iter5 (iter6–10 within ~1.5σ). A 2026-06-10
  decomposition attributes ~95% of the gain to **policy distillation**, with the residual value head
  a static ~+22 additive, non-compounding (CL-011, CL-018).

## 2. Deepteacher audit result
- **Provenance defect (CL-020, Confirmed):** the deepteacher run's published "sealed/washout"
  baselines were `residual.pt` (`f1e67cab…`), **not** the warm-from iter8. So the headline
  +8.1/z0.34 (s800) and +82.8/z3.48 (s200) deltas are **iter12 − residual.pt**, not iter12 − iter8.
  The warm-start chain itself is clean (hash-verified iter8-rooted).
  ([sources/DEEPTEACHER_PROVENANCE_AUDIT.md](sources/DEEPTEACHER_PROVENANCE_AUDIT.md))
- Consequence: the experiment's actual question ("did a deeper teacher beat iter8 at the deep
  plane?") was **never measured at the verdict plane** until the clean rerun below.

## 3. iter8 vs iter12 result (clean rerun)
- Fresh band 2.5e9, n=400 paired, vs heur@800-v2.7
  ([sources/ITER8_VS_ITER12_VERDICT.md](sources/ITER8_VS_ITER12_VERDICT.md), CL-019):
  - **s200:** iter8 +72.2, iter12 +86.9 → Δ(iter12−iter8) = **+14.6 elo, z=0.65** = TIE
  - **s800:** iter8 +142.1, iter12 +154.5 → Δ = **+12.4 elo, z=0.51** = TIE
- Both planes are **powered nulls** for a ≥+24 elo effect. iter12 is **not** promoted; champion
  stays iter8. The earlier mid-run iter2 (+53.7/z2.14) and iter9 (+35.6/z1.21) "wins" were
  deck-band-favorable noise that did not carry. (`p2_iter{8,12}_vs_heur800_v27_s{200,800}_n400`)

## 4. Value-ranking / attention result
- Phase-4 kill-test ([sources/VALUE_RANKING_VERDICT.md](sources/VALUE_RANKING_VERDICT.md), CL-021):
  held-out Kendall-τ on sibling-move ranking — A(conv+MSE) −0.004, B(conv+rank) +0.029,
  **C(attention+rank, the swing) +0.012**, C0(conv-wide capacity match) +0.015, E(advantage) +0.014,
  vs **v2.7 leaf τ = 0.579**.
- The attention swing fails its own gate (C−C0 = −0.002, z −0.12 = no effect). Every learned arm
  ranks at **~3–5% of achievable**. The production net trained on millions still ranks at τ=0.081 ≪
  0.58, so "more data unlocks it" is not supported. Verdict: **tested learned value/ranking
  formulations are disfavored** (not merely probe-limited).

## 5. Clairvoyance-gap result
- Production search **is** deck-order clairvoyant (step-0 sentinel: root value moved 8/8). The elo
  worth of that future-sight is **small**: paired gap clair − nonclair(K=12) = **+26.6 elo, z=−0.9**
  (not distinguishable from zero), n=182, band 2.7e9
  ([sources/CLAIRVOYANCE_GAP_VERDICT.md](sources/CLAIRVOYANCE_GAP_VERDICT.md), CL-022;
  `clairvoyance_{clair,nonclair}_…`).
- P(gap ≥ 100) ≈ 2%. A non-clairvoyant agent keeps essentially all of iter8's strength (+40 vs
  heur@800). **Clairvoyance is excluded as a large/decision-changing artifact.** Our clairvoyant
  numbers ≈ transfer to honest play (at sims=200; not yet checked at other depths).

## 6. Level-2 heuristic ladder result
- Adjacent-rung paired ladder, fresh disjoint bands, heur at production c=1.5 / v2.7 env
  ([sources/LEVEL2_LADDER_VERDICT.md](sources/LEVEL2_LADDER_VERDICT.md), CL-023; `l2_ladder_R*`):
  - random→greedy +800 (z55.6); greedy→v1@200 +26.1 (z1.87, compressed); v1@200→v2.7@200 +24.4
    (z1.68, compressed) — **leaf quality and low-sim search buy little resolvable strength.**
  - **Depth re-separates cleanly:** v2.7 @200→@800 **+75.9** (z3.59), @800→@1600 **+55.2** (z3.23,
    n=400), @1600→@3200 **+34.9** (z2.36, n=400).
- **Saturation REFUTED:** the elo scale has headroom above the production heur@800 ruler; deeper
  heuristic search keeps climbing with **diminishing returns** (+76→+55→+35 per doubling). The ruler
  is **not saturated even at @1600**.

## 7. iter8 vs heur @800 / @1600 / @3200
- Same-band (3.10e9) n=400 paired ladder ([sources/LEVEL2_L22_VERDICT.md](sources/LEVEL2_L22_VERDICT.md),
  CL-024):
  - iter8 vs **heur@800**: **+40.1 elo, z=2.29** (`l22_iter8_vs_heur800_v27_s200_n400`)
  - iter8 vs **heur@1600**: **+24.4 elo, z=1.40** same-band control (`l22_ctrl_iter8_vs_heur1600_b310_n400`)
  - iter8 vs **heur@3200**: **−28.7 elo, paired z=−0.70** (`l22_iter8_vs_heur3200_b310_n400`)
- iter8's full-game edge **shrinks monotonically with heuristic depth and is erased by heur@3200**.
  Same-band control confirmed the elo scale is **transitive** (the earlier ~50-elo "non-transitivity"
  was cross-band artifact). An orch-off A/B proved the eval path is **bit-identical** to the historical
  path (zero apparatus bias). The residual caveat is just n=400 noise (±17.5/comparison).

## 8. Hybrid handoff result
- Hybrid = iter8 policy until first own TILES decision with `k_remaining ≤ K`, then HeuristicMCTS@N
  for the rest. Band b340, paired ([sources/LEVEL2_HYBRID_VERDICT.md](sources/LEVEL2_HYBRID_VERDICT.md),
  CL-026; `l2hyb_*`):
  - **vs iter8 (Phase 1):** every hybrid beats iter8 on paired margin, monotone in K (K≤2 z+2.65,
    K≤3 z+1.18, K≤5 z+3.45, K≤8 z+4.68 at n=200; reproduced n=400: K≤5 z+6.23, K≤8 z+5.79). iter8's
    endgame weakness is **locally patchable**; cheap heur@800 endgame captures most of it.
  - **vs heur@3200 (Phase 2, the champion question):** hybrid:5 **−13.9 elo (z−0.30)**, hybrid:8
    **−19.1 elo (z−0.51)** — both **lose** at |z|<1.
- **Verdict: gap-closing, NOT a new champion.** The hybrid closes most of iter8's −28.7 gap to the
  deep heuristic without surpassing it. **Nothing promoted.**

## 9. Solver-grounded endgame results (K=2 / K=3 / K=4)
First **non-circular** ground truth in the program (exact minimax / alpha-beta over the final K
tiles; brute-validated). Endgame-optimality is **decoupled from full-game Elo** and kept separate.
- **K=2** ([sources/LEVEL2_L23_VERDICT.md](sources/LEVEL2_L23_VERDICT.md), CL-025): 150 pos / 141
  decision. top-1: heur@3200 **0.837** = heur_v1@200 0.837 > heur@1600 0.780 > greedy 0.759 =
  heur@800 0.759 > **iter8 0.667 (worst)**. Blunders rare/small (no agent loses >10 pts); iter8's
  errors are *bidirectional* (also optimal where heuristics blunder up to 6 pts).
- **K=3** (partial, 68 decision pos, clairvoyant; same verdict doc): **iter8 worst** (top-1 0.574,
  highest mean regret 0.96). Deficit is depth-robust. (W=20 OOM truncated the suite to 74/150;
  qualitative finding settled.)
- **K=4** ([sources/LEVEL2_K4_PROBE_VERDICT.md](sources/LEVEL2_K4_PROBE_VERDICT.md), CL-027): exact
  alpha-beta clairvoyant solver, **200 balanced positions (50/source), 187 solved (94%)**, 13 genuine
  1M-node budget-hits. Overall top-1: heur@3200 **0.679** > heur@800 0.652 > greedy 0.647 > **iter8
  0.561 (worst)**. Disentangled via multi-source suite:
  - **(H1) "iter8 near-optimal on its own endgames" — NOT supported** (the pilot's 0.92 was n=12
    noise; real = 0.65, beaten there by greedy 0.75 & heur@3200 0.73). iter8-generated endgames are
    objectively *easier* (within1=28.5, randReg=1.1).
  - **(H2) iter8 worst on sharper / OOD endgames — SUPPORTED** (greedy-source 0.44 vs 0.58–0.60;
    sharp gap≥2 top-1 0.40, mean regret 3.34).
  - **(H3) heuristics generalize across sources, iter8 does not — SUPPORTED** (heur@3200 most
    consistent 0.58–0.73; iter8 most variable 0.44–0.65).

## 10. Current interpretation of iter8
*(interpretation, not raw fact)* iter8 is best read as a **learned policy / search-efficiency
agent**: it makes a fixed search budget more effective in the early/mid game (where it beats heur@800
and heur@1600 same-band), but it does **not** add precision the heuristic search lacks. Its edge is a
head-start that **deeper heuristic search erases** (heur@3200) and it is the **least precise endgame
technician** of all agents tested. Its strength is bounded by the v2.7 leaf it distills.

## 11. Current interpretation of heur@3200
*(interpretation, not raw fact)* heur@3200 is the **strongest known practical agent / ruler** — it
catches iter8 full-game and is the most endgame-precise on every solver suite. It is **not** optimal
or ground truth: the ladder shows deeper search keeps gaining (no saturation through @1600), so
heur@3200 is simply the deepest rung measured. All its numbers are **clairvoyant, in-ecosystem
(v2.7-leaf-family)**, not human-anchored.

## 12. What remains unknown
- **Absolute / human strength.** Every elo is clairvoyant and in-ecosystem; no human/expert anchor
  exists. Whether any agent is near human-expert — let alone superhuman — is **unmeasured**.
- **Whether any agent genuinely exceeds the v2.7 heuristic.** No supra-heuristic learned component
  exists; the ruler is heuristic-capped.
- **Marginalized (bag-expectation) endgame labels.** All solver results are *clairvoyant* (perfect
  deck order). The *preferred* fair-information ground truth is untested at K≥3 (needs make/unmake).
- **K≥5 endgame and clairvoyance gap at higher sims.** Both unmeasured.
- **Whether tool/feature augmentation helps.** Entirely unproven — the proposed branch.

---

## Established FACTS (measured, powered, provenance-verified)
1. iter8 beats its incumbent +67.4/z2.73 on a sealed out-of-lineage ruler (CL-018).
2. iter12 (deepteacher) **ties** iter8 at s200 (+14.6/z0.65) and s800 (+12.4/z0.51) — powered null (CL-019).
3. The deepteacher published sealed/washout deltas were vs `residual.pt`, not iter8 — a provenance defect (CL-020).
4. All tested learned value/ranking heads rank siblings at τ≈0.01–0.03 vs v2.7's 0.58 (CL-021).
5. Clairvoyance gap = +26.6 elo, z=−0.9; ≥100 excluded (CL-022).
6. Heuristic ladder is **not saturated**: depth scales it +76→+55→+35 per doubling through @3200 (CL-023).
7. iter8 vs heur same-band: +40.1 @800, +24.4 @1600, −28.7 @3200 — monotone, erased by @3200; scale transitive (CL-024).
8. iter8 is the **worst** top-1 endgame agent at K=2 (0.667), K=3 (0.574), and K=4 (0.561) exact-solver suites (CL-025/027).
9. Hybrid beats iter8 on paired margin (reproduced n=400) but **loses** to heur@3200 (CL-026).
10. Eval apparatus is provenance-guarded and the orch+CY path is bit-identical to the historical path (CL-013/CL-024).

## INTERPRETATIONS (supported readings, not raw measurements)
- iter8's gain is "policy distillation bounded by v2.7" (a decomposition reading, CL-011/018).
- iter8 is a "search-efficiency agent whose edge erases vs deeper heuristic search" (composition of CL-024 + CL-025/027).
- K=4 shows "distributional specialization / OOD endgame weakness," not blanket endgame incompetence (H1 rejected, H2/H3 supported, CL-027).
- heur@3200 is "the strongest known practical ruler" (composition of CL-024 + endgame suites) — *not* ground truth.
- Both strength levers (policy iteration, learned value) are "exhausted"; measurement is the binding constraint (MEASUREMENT_FIRST_SPEC §1).

## SPECULATION (hypotheses, explicitly unproven)
- Mechanism for iter8's endgame weakness: trained on full-game value where the last tile barely moves
  the outcome, so the policy underweights the last-tile point-grab (CL-025 #5, labelled hypothesis).
- The 7 excluded greedy budget-hits are even sharper, so the by-source effect is *conservative* (CL-027, plausible but unverified).
- Tool/feature augmentation or a learned action-ranker could add the endgame/OOD precision iter8 lacks
  — **no evidence either way**; this is the bet the proposed branch would test.
- A deeper heuristic (v2.8) might beat heur@3200 — untested.
