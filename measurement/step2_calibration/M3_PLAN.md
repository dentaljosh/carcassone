# M3 — Is Gate-B a fixable calibration/tails failure? (runbook, launch-ready)

**Status:** ✅ **DONE — FIRES → FPU axis CLOSED (2026-07-03).** Plan:
[docs/POST_REVIEW_PLAN.md](../../docs/POST_REVIEW_PLAN.md) §3. Scoped 2026-07-01 (subagent read-only pass).

> **Result (full n=400 FPU curve):** fpu=None 0.265 → 0.4 0.391 → 0.6 0.496 (PEAK = parity, z−0.15 vs the 0.500 pure-heuristic anchor) → 0.8 0.4825 → 1.0 0.476. **Gate-B (CL-038) refuted as a LAW** — isotonic recovered *less* than FPU → the mechanism is the MCTS max-operator hunting the value's optimistic tail (which FPU tames), the axis the 3 nails were blind to. BUT recovery is to PARITY, not exceeding, and rolls off beyond fpu=0.6 → FPU removes the weak value's *harm*, can't make it *exceed* the τ≈0.895 leaf. Value-leaf lever REOPENS; **M2** is the deciding "can it EXCEED" test. results.csv `m3_confirm_fpu0{4,6,8,10}_c3_b027_n400`; commits `0738450`, `1d962e6`, FPU patch `724c903`.

**Question.** Gate-B (CL-038) concluded a learned value "can rank but can't drive MCTS." Its 3 nails rule out
distribution/subtraction/retraining but are blind to **calibration / optimistic-tail** (MCTS's max-op hunts the
value's error tail). If a standard pessimism/calibration fix recovers play, "can't drive search" is not a law — it's
"an *uncalibrated heavy-tailed* value can't drive search." Cheapest config: **n=100, sims=100**, vs the **0.500
pure-heuristic anchor**. Fix bar: any arm climbs **0.285 → ≥0.45** (≥2σ).

## Fixed facts (from the scoping pass)
- Additive leaf: `src/carcassonne_ai/step2_leaf.py::make_step2_value_wrapper` (commit `c4be026`). Selector
  **`--leaf-mode {convex,additive}`** on `eval_step2.py` (or env `CARCASSONNE_STEP2_LEAF_MODE`). additive, blend>0:
  `value = clip(h + blend·v_net_leafpov, −1, 1)`.
- Policy net (both agents): `/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt`. Value (weaned ScalarMLP):
  `/home/doctor/carc_step2_pens/warmstart/warmstart.pt`.
- **Anchor = wr 0.500** = additive `BLEND=0.0` (results.csv `step2_nail2_armA_pureH_b0`). Prior nail-2: additive
  b0.27 = **0.285**.
- Runs via `scripts/step2_pens/eval_step2_orch.sh` (carc-orch, high W) — aligns with the orch-for-nets directive.
- **POV discipline:** `oracle_q`/features are parent-POV; leaf value negates to leaf-POV on player-flip transitions
  (`step2_leaf.py:448-462`). Do all LCB mean/std + isotonic math in raw **parent-POV**, negate AFTER.

## Launch order (cheapest-informative first)

**0. Reproduction control (0 code) — confirm 0.500 anchor + 0.285 additive reproduce on this box.**
```bash
cd /home/doctor/projects/carcassone
CAND_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
REF_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
SCALAR=/home/doctor/carc_step2_pens/warmstart/warmstart.pt \
OW=28 SIMS=100 N=100 BLEND=0.27 DROPOUT=0.0 \
OUT=/mnt/c/carc-shared/step2_pens/nail2/M3_repro_addbeta027 \
  bash scripts/step2_pens/eval_step2_orch.sh --leaf-mode additive
# anchor re-measure: same with BLEND=0.0
```

**1. Arm 3 — c_puct/FPU re-sweep (SMALLEST code: ~10-line flag plumbing, then 9-cell config sweep).**
- `eval_step2.py` hardcodes `CPUCT=3.0` (:97), passes to both agents (:141,:160); `fpu_reduction` never passed
  (always `None`). Add `--c-puct` / `--fpu` argparse, thread into `_build_candidate_mcts` (**candidate-only**, to
  isolate). `eval_step2_orch.sh` already forwards `"$@"`.
- Knobs are real `NeuralMCTS.__init__` args: `c_puct` (mcts.py:432), `fpu_reduction` (:441,:496; None=legacy q=0).
- Grid: c_puct{1.5,2,3} × FPU{None,0.2,0.4} = 9 cells. **FPU is the most on-hypothesis knob** (directly re-values
  the unvisited-child optimism the max-op hunts).

**2. Arm 2 — isotonic calibration (data ready; needs sklearn OR vendored PAV).**
- Held-out search-Q exists: `/home/doctor/carc_step2_pens/dataset/aux_step2.npz` (`oracle_q` + `child_scalars[89]` +
  `game_seed` + `col_mean/col_std`, 314,911 rows). Split via `train_warmstart.bucket(game_seed)` (train<70/val
  70-85/test≥85); fit isotonic on held-out val+test `(ScalarMLP(z-score(scalars)), oracle_q)` in parent-POV.
- sklearn NOT installed → `pip install scikit-learn` into `.venv` (fit-time only; inference is pure `np.interp`).
- ~50-line offline fit + ~15-line `np.interp` inference patch + `--leaf-mode additive_iso`.

**3. Arm 1 — LCB / ensemble pessimism (needs training: no dropout/ensemble in ScalarMLP).**
- `ScalarMLP` has zero `nn.Dropout` → MC-dropout infeasible. **Use a 4-head ensemble:** train 4× `train_warmstart.py
  --seed {0,1,2,3}` (trainer already takes `--seed`, no code change), patch `_v_mlp_leafpov` to forward all 4
  (batched (4,89)), `mean − k·std`, POV-negate after; add `--lcb-k`, sweep k∈{1,2}.

## Read-out
- **Success** (any arm ≥0.45, ≥2σ vs 0.500): Gate-B's generalization dissolves → the weaned loop earns its §10(b)
  budget WITH the fix installed; autopsy §7 "M3 fires" branch. Gate-B stays valid only narrowly.
- **Kill** (all arms ≤0.30): mechanism isn't tails/calibration/knobs → "can't drive search" hardens; autopsy §7
  "all-kill" contribution. Single read-out at pre-registered n, no peeking.

MEASUREMENT ONLY — no champion/PRODUCTION.yaml/v2.7/v2.9 change. Governance: contributes to CL-042 (autopsy; CL-041 = the S1 promotion).
