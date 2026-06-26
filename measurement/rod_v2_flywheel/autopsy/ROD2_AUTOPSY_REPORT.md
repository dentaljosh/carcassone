# ROD2 Flywheel Autopsy — v2.9 leaf (Bmild_cap8)

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT ONLY.** No promotion,
PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen + bit-identical.
Scope: diagnose why the RoD2 flywheel trained cleanly but did not restart compounding.
**No new fixes proposed** — diagnosis + an A/B/C/D decision only.

Deliverables (this dir): `TRAINING_DYNAMICS_AUDIT.md` (F), `DATA_DISTRIBUTION_AUDIT.md` (D),
`NONTRANSITIVITY_SELECTION_AUDIT.md` (E), `POLICY_ROOT_AUDIT.md` (A-lite). Generators:
`scripts/rod_v2/autopsy/stage_a_lite.py`, `phase_breakdown.py`. Precedent (same flywheel, one
leaf-version earlier): `../../rod_v28_overnight_flywheel/autopsy/AUTOPSY_RoD_v28_iter08.md`.

---

## 1. Executive summary

The RoD2 flywheel (warm-start RoD_iter_01, frozen v2.9 leaf, residual value targets, 5 train
iters) trained cleanly but produced **no strength gain on any fixed reference**. Every checkpoint
loses to h6400_v2.9 (−22 to −32 elo, paired z up to −4.7) with no climb across iters, sits at
~h3200_v2.9 parity, and is statistically indistinguishable from its own RoD1 start (adjacent/parent
deltas are non-transitive: `iter04 − RoD1` is +6 elo vs h6400 but −40 elo vs h3200). The learned
components did not exceed the heuristic — they reshaped laterally. Direct root-audit on 400 fixed
positions shows the policy **prior is diffuse, not deeper**: on h3200≠h6400 disagreement states it
picks *neither* ruler's move 77.5% of the time, its lean toward the deep ruler is ~0 and flat across
RoD1→iter04→iter06 (−0.009→−0.063→−0.027, within noise), and its agreement with both rulers collapses
in the endgame (0.10–0.13) — exactly where the deep ruler is most decisive. Training is healthy but
**target-limited**: the residual value target has near-zero dynamic range so the value head is inert
(corr flat ~0.45), and the policy target gets *noisier* each iter (train_pol & entropy rising), so
self-play is **diffusing, not climbing**. RoD2's play strength is carried by the **v2.9 leaf inside
MCTS, not by the learned net** — which is precisely why it cannot exceed the heuristic. This
reproduces the v2.8 flywheel autopsy signature; the v2.9 leaf swap did not change the outcome.

## 2. What is ruled out

- **Pipeline broken / training not happening — RULED OUT.** Every iter converges within its 3 epochs
  (train_pol falls per-epoch, no NaN/divergence), writes 400/400 npz + a checkpoint with full
  provenance (gen leaf = `v2_9_bmild_cap8` in every metrics.json). A prior 3-agent code audit found
  no bug. (Stage F.)
- **Checkpoints identical — RULED OUT.** Distinct sha256 per iter; they differ behaviorally
  (non-transitive head-to-head differences). The problem is not "nothing changed."
- **v2.9 substrate failed — RULED OUT (as a leaf).** The frozen v2.9 leaf loads and computes
  correctly (ruler provenance verified at audit time: bonus_cap 8 + Bmild curve −8,−4,−1,0,2,3,4,5);
  the heuristic built on it is a legitimate stronger ruler (RoD1 beats h3200_v2.9 +34.9 elo but loses
  h6400_v2.9 −32.2). The substrate works — it just is not a component the *net* learns to exceed.
- **Parent / adjacent eval is a valid improvement signal — RULED OUT.** Adjacent and parent results
  do not transfer to a fixed ruler: `iter04 − RoD1` sign-flips by ruler (+6 vs h6400, −40 vs h3200),
  and the inter-checkpoint net-vs-net harness deadlocked (unusable). Same as v2.8 (+33 adjacent elo →
  0 ruler transfer). (Stage E.)

## 3. What is supported

- **Policy stuck — not moving toward h6400, and DIFFUSE — SUPPORTED (direct, Stage A-lite).** On the
  h3200≠h6400 disagreement subset (n=111), the prior lean toward h6400 is ~0 and flat across iters
  (RoD1 −0.009 → iter04 −0.063 → iter06 −0.027; Δ −0.018 vs ±0.095 noise). The net picks *neither*
  ruler's move 77.5% of the time (prior); search (NMCTS@200) recovers agreement to ~0.5 but stays
  h6400≈h3200-equidistant with no iter trend. Endgame agreement collapses to 0.10–0.13 and the lean
  goes negative there — the costliest, most persistent disagreement is the endgame, and the
  continuation does not close it (v2.8 finding, reproduced).
- **Value residual unhelpful — SUPPORTED (strong).** Residual target std ~0.13 with 38–43% of targets
  within ±0.02 of zero (Stage D); train_val_loss flat ~0.007, value_outcome_corr flat ~0.45 with no
  trend (Stage F). The head saturates on the mean.
- **Data distribution non-climbing — SUPPORTED (strong).** Later self-play is *merely different*:
  residual spread flat, policy-target entropy rising 1.494→1.538, margins flat, only a mild meeple
  style drift. Drifting, not climbing (Stage D).
- **Policy not sharpening — SUPPORTED (strong).** train_pol rises 1.562→1.619, policy_entropy rises
  1.567→1.609 toward the warmstart baseline (Stage F).
- **Tether too strong — NOT THE PRIMARY CAUSE (untested directly).** With a near-zero-dynamic-range
  value target the value head is inert regardless of residual_scale, so loosening the tether has
  little signal to amplify. Flagged untested (Stage C not run); not the operative lever.
- **Stochastic / compute ceiling — the operative limit is STRUCTURAL, not compute.** Blocker #2
  (learned components cannot exceed the hand-crafted leaf) is the binding constraint: the net's
  strength is carried by the v2.9 leaf inside MCTS, with a diffuse prior and an inert value head.

## 4. Ranked failure modes (confidence)

1. **No source of supra-heuristic signal (ROOT CAUSE) — ~0.9.** The value target is residual-around-
   the-heuristic with no dynamic range, and the policy target is heuristic-MCTS visit counts — neither
   can carry information that *exceeds* the leaf. So the net asymptotes to the leaf, not past it.
   (Composes modes 1+2+3+6 below; they are facets of this.)
2. **Value head / residual gives no local discrimination (mode 2) — ~0.85.** Inert head, flat corr,
   near-zero-range target (Stage D+F).
3. **Self-play data different but not stronger (mode 3) — ~0.85.** Drifting ecology, noisier policy
   targets (Stage D).
4. **Policy not moving toward the deep ruler (mode 1) — ~0.85.** Diffuse prior, flat lean, no iter
   trend; endgame divergence (Stage A-lite).
5. **Parent/adjacent wins don't transfer (mode 4) — confirmed.** Non-transitive, ruler-sign-flip
   (Stage E).
6. **v2.9 better leaf but RoD2 only compresses ~h3200-level search (mode 6) — ~0.8.** Whole chain
   pinned in the h3200–h6400 band where RoD1 already sat (Stage E + precedent).
7. **Tether too strong (mode 5) — ~0.15.** Unlikely primary; value inert regardless of scale.

## 5. Decision — **C: stop the AlphaZero-style blind flywheel; keep classical v2.9 as the strength.**

The RoD2 run is a clean, well-powered demonstration that **blocker #2 still stands**: with the better
v2.9 leaf, 5 iterations of warm-start self-play produced a diffuse policy, an inert value head,
drifting (not climbing) data, and zero transfer to any fixed ruler — the same wall the v2.8 flywheel
hit. Continuing (option A) will not break it; the recipe has no mechanism to generate signal above the
leaf it imitates. Changing one component (option B) is not justified *by this autopsy* — the failure is
joint across policy target, value target, and data, not a single tunable; the only single-component
edit with a coherent thesis (a value target that out-ranks the leaf) is itself a new research program,
not a knob.

The one direction with an EV thesis is **D-flavored**: the net's gap is *localized to the endgame*
(Stage A + v2.8 both), and the only lever that can *provably exceed* a heuristic there is an exact /
endgame-solver signal (or distillation from a supra-heuristic teacher), pursued as a **separate
project** — not as a continuation of this flywheel. Per the governance rule, that is **named as the
decision boundary, not proposed or started here.** Immediate decision: **C** (stop the blind RoD
flywheel; classical v2.9 remains the strength of record; champion/PRODUCTION.yaml unchanged).

## 6. No new experiments

No new branches, curriculum, tools, or RoD3 are proposed in this autopsy. Stage B (value/sibling
ranking) and Stage C (residual scale) remain **un-run** because Stage A-lite *confirmed* — did not
contradict — the free-stage diagnosis.
