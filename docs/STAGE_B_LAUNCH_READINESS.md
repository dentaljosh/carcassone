# Stage B — launch readiness (built overnight 2026-06-03, on branch `stage-b-wiring`)

**STATUS (2026-06-03 AM): wiring DONE + code-reviewed + G-S3 wired + all decisions LOCKED.
Cluster synced (11965b6). Final gate = the Xeon OOM smoke; then launch.** Stage B is the
value-in-loop retrain that tests whether the learned value head, finally put INTO the search
loop (the F-B1 fix), can beat the v2.7 leaf ceiling on the clean base-only game. Branch
`stage-b-wiring` (merge to `gpu-orchestrator` is your call — branch-per-phase).

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

## ✅ DECISIONS — ALL LOCKED (Joshua, 2026-06-03)
1. **Success bar:** Stage B succeeds iff the best iter beats **iter_11 by ≥25 elo @ n=400
   paired** (~1.5σ; pre-registered to avoid post-hoc rationalizing a null).
2. **Blend curve:** iters 0–1 = 0.0 (warmup), then **0.15 / 0.30 / 0.50 / 0.70 / 1.0** —
   exactly `blend_for_iter()` as coded.
3. **Warm-from = iter_11** (NOT a fresh corpus net). The 2026-06-03 high-sim ladder showed
   iter_11 = **+56.7 elo vs HeuristicMCTS @ sims=800** (n=1143), i.e. its *policy priors*
   transfer to the clean base-only game despite River-era training (base ⊂ base+river; the
   bad part — the value head — is what Stage B retrains on clean self-play, value-blend
   ramping from 0). So we inherit the good policy instead of climbing back from a weaker
   imitation net. `WARM_SRC` default already = `pathb_loop/ckpt/iter_11.pt`; no train step.
4. **G-S3 gate (wired, commit 11965b6):** per-iter gate = iter_N **vs HeuristicMCTS**
   (out-of-lineage, same currency as the +56.7 rung), n=200 paired, c=3.0, value_blend=0;
   adopt as new best (→ next `warm_from`) iff elo ≥ best+10; stop after MAX_FLAT no-new-best.

## Launch command (after the OOM smoke passes)
```bash
# fresh RUN dir, Stage-B knobs, warm from iter_11 (default WARM_SRC):
RUN=stage_b STAGE_B_BLEND=1 VALUE_LOSS_WEIGHT=3 LR_SCHEDULE=cosine \
  nohup nice -n 19 bash ~/run_pathb_cluster_loop.sh > /tmp/stageb.log 2>&1 & disown
# 3-box work-stealing; ITERS=12 / GAMES=600 / SIMS=200 / GATE_GAMES=200 defaults.
# Per-iter ≈ self-play(600 g) + train + gate(n=200 vs heuristic). ETA/iter measured on iter 0.
```
**Cluster readiness (2026-06-03 AM):** xeon + laptop synced to 11965b6; home launcher
refreshed to 11965b6; xeon `stage_launcher.sh` present.
**✅ OOM SMOKE PASSED (Xeon, blend=0.5, prod knobs W=18 shards=2 sims=200):** peak
**2227 MiB / 8192 (27%)**, rc=0, zero CUDA/OOM errors, 12 g / 1365 pos / 295s. The value-head
full-forward path is NOT a VRAM risk on the 8GB card. **All gates cleared — ready to launch.**
(Throughput note, not a blocker: eval_server log shows dequeue=~85% → orchestrator dispatch
is the limiter on xeon, GPU ~19W; that's the known shards=2 IPC-bound profile, fine for prod.)

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
