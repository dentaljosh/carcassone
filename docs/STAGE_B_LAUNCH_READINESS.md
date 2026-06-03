# Stage B — launch readiness (built overnight 2026-06-03, on branch `stage-b-wiring`)

**STATUS: wiring DONE + smoke-verified; code-review pending; NOT launched.** Stage B is
the cheap value-in-loop retrain that tests whether the learned value head, finally put
INTO the search loop (the F-B1 fix), can beat the v2.7 leaf ceiling on the clean base-only
game. Everything below is on branch `stage-b-wiring` (review + merge to `gpu-orchestrator`
when satisfied — branch-per-phase, merge is your call).

## What's wired (3 commits)
- **7fa696d G-S1** — `--value-blend` in `run_selfplay_iter.py`; the 3 guard sites read the
  per-iter value (not import-time `DEFAULT_CONFIG`); `dataclasses.replace` leaf cfg so the
  blend reaches the worker leaf. `blend_for_iter()` schedule in `run_pathb_cluster_loop.sh`,
  **default OFF** (`STAGE_B_BLEND=1` to enable).
- **8965852 G-T1/T2** — `LR_SCHEDULE` (none|cosine) + `VALUE_LOSS_WEIGHT` env knobs into the
  train step; defaults (none / 1.0) = current behavior.
- **b2ba341 anchor fix** — the fixed iter_11 anchor stays blend=0.0 (plays pure v2.7 as
  trained), not the learner's ramp (plan risk #4).

**Verified:** same-seed self-play differs between blend 0.0 and 0.9 (net value reaches the
leaf + changes the search); anchor-fraction=1.0 run completes 0-failed; `test_evaluators`
+ `test_selfplay` green; default-off path preserves current behavior.

## ⚠️ TWO DECISIONS NEEDED FROM JOSHUA before launch
1. **Pre-register the success bar.** "Stage B succeeds iff value-in-loop beats iter_11 by
   ≥ X elo on the HeuristicMCTS ladder at n=Y." Pick X, Y *now* so we don't post-hoc
   rationalize a null (the project's recurring failure). Suggest X≥25 elo, Y=400 paired.
2. **The blend ramp curve.** Current PROPOSAL in `blend_for_iter()`: iters 0–1=0.0 (warmup),
   then 0.15 / 0.30 / 0.50 / 0.70 / 1.0. Adjust the curve / length as you see fit.

## Pre-launch steps still owed (cheap; can be done before/at launch)
- **Train the Stage-B starting checkpoint** (from-scratch base-only warmstart): the corpus
  is ready at `data/warmstart/baseonly_v27cap12/` (300K, 12-scalar, cap=12). Run
  `train_warmstart.py --include-farm-scalars` on it → `warm.pt`. (Old iter_11 is River-era;
  Stage B starts fresh.) ~minutes.
- Decide which `--warm-from` Stage B starts at (the new warm.pt) and `WARM`/anchor (the
  ladder/gate reference — likely HeuristicMCTS via G-S3, still pending wiring).

## Launch shape (fill the decisions, then)
```bash
# from the loop launcher, with Stage-B knobs:
STAGE_B_BLEND=1 VALUE_LOSS_WEIGHT=3 LR_SCHEDULE=cosine \
  nohup nice -n 19 bash ~/run_pathb_cluster_loop.sh > /tmp/stageb.log 2>&1 & disown
# (set ITERS / WARM / warm-from per the loop's env; 3-box work-stealing; ETA TBD from a
#  1-iter smoke at production knobs — DON'T extrapolate, measure.)
```

## Open risks (from the G-S1 plan + review)
- **CUDA OOM:** blend>0 makes the orchestrator run full-forward (value head) vs the old
  policy-only path → higher per-request VRAM on the 8GB xeon/laptop. Smoke 1 iter at prod
  knobs and watch the Compute/CUDA engine before trusting the full run.
- **Score-diff currency:** the leaf blends `tanh(vs2/15)` with `v_nn`; the value head must
  be trained on matching-scale targets (`score_diff`, /15). If `score_diff_wide` (/40) is
  used, align the divisor or the blend is miscalibrated.
- **FPU re-sweep (G-S4):** fpu_reduction was tuned for the pure v2.7 leaf; blend>0 shifts
  the PUCT balance. Re-sweep FPU at an intermediate blend before ramping to 1.0. (FPU screen
  this session: 0.2≈+45 elo/z1.85, 0.4≈+31/z1.28 — both positive, unconfirmed.)
- **G-S3 still pending:** point the keep-best gate at HeuristicMCTS (out-of-lineage) +
  `warm_from=best_ckpt`. Not yet wired — do before trusting the loop's gate decisions.

## Code review (done — subagent, 2026-06-03)
**Bottom line: wiring is correct + safe to launch Stage B**, pending the Xeon OOM smoke below.
All categories clean: value_blend propagation (both no-orch + orch paths), anchor correctness
(plays pure v2.7), default-off byte-identical to current production, no silent no-op, no
set-u bugs, score-diff currency matches (leaf `/15` == `score_diff` target `/15`).
- **One issue found + FIXED (commit bfbd47d):** the anchor orch server wastefully ran the
  value-head forward during Stage B (its `policy_only` keyed off the learner's `--value-blend`),
  raising VRAM on the 8GB Xeon where OOM is the flagged risk. Now `policy_only=(leaf_eval!="nn")`
  unconditional — the anchor always plays blend=0 so it can always skip the value head.
- **Remaining gate before launch (not a code bug):** 1-iter smoke at production knobs on the
  Xeon (W=18, sims=200, blend>0) watching the Compute/CUDA VRAM, to confirm full-forward
  doesn't OOM. DON'T extrapolate wallclock from a cheaper smoke.
