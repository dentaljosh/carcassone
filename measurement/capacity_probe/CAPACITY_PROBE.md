# Capacity-scaling probe — pre-registered read-out

**Status: RUNNING (launched 2026-07-04). Thresholds below were fixed BEFORE any
result existed. Do not move them after seeing the numbers.**

## Question

Does model **capacity** move the Q-label sibling-ranking ceiling toward the
leaf? This is the pre-registered disambiguator for the "would 10x scale help"
question: the M2/CL-039 closure showed the learned ranker plateauing far below
the v2.9 leaf under the exact-solver ruler — but every arm so far was the same
386K-param RankNet. If a bigger net on the *same data, same labels, same
representation* climbs, capacity was the binding constraint and the scale
question reopens. If it doesn't, the closure extends to "capacity- and
data-limit-independent on this representation".

## Context (measured, prior to this probe)

| Ranker | Solver Kendall-τ (exact K≤2 ruler) | Source |
|---|---|---|
| v2.9 leaf | **0.615** | M2 Part A solver scoring |
| all_three RankNet (f64/b4, 386K), Q-labels | **~0.13** | 5A rescore (arms_retrain solver_score) |
| outcome-trained net @2K games | **0.02** | M2 |

The label axis is already anchored: outcome labels = τ 0.02 (M2); **Q-labels =
the data-limit condition** (this probe trains on them); leaf = 0.615. This
probe varies only the capacity axis on the best-known (Q-label, all_three)
cell.

## Design (fixed)

- **Dataset:** the CL-037/§5A sighted dump `/home/doctor/carc_step1_gate/dataset_both`
  (81ch / 25W / 44 scalars, 314,911 rows) + the 10-col gate-zero tempo block
  `/home/doctor/carc_step1_gate/tempo_5a/tempo_resid.npz` appended → n_scalar 54,
  **NO drop flags** (the all_three config — richest input, gives capacity its
  best shot).
- **Labels/loss:** oracle_q absolute, V4_listwise — the exact
  `scripts/probe_5a/run_arm_retrains.sh` all_three invocation of
  `scripts/feature_planes_gate/step1_train.py` (groups-per-batch 8,
  --save-model), only the size flags vary.
- **Capacity axis (3 sizes):**
  | size | trunk_filters | trunk_blocks | ~params |
  |---|---|---|---|
  | baseline | 64 | 4 | 386K |
  | mid | 128 | 6 | ~2M |
  | large | 256 | 8 | ~8–10M |
- **Seeds:** 2 per size (0, 1) = 6 runs, sequential solo, ascending size.
- **Trainer flags already existed** (`--trunk-filters/--trunk-blocks`,
  step1_train.py:115-116 → RankNet ctor :260 → saved arch dict :318-319); the
  solver-side loader `solver_score.py:make_tempo_arm_ranker` reconstructs from
  the arch dict (:198-200), so all 3 sizes load with **zero code changes**.
- **Launcher:** `scripts/probe_5a/run_capacity_probe.sh` → out dirs
  `measurement/capacity_probe/f<F>b<B>_s<seed>/`.
- **Read-out:** solver-τ per checkpoint via
  ```
  .venv/bin/python scripts/canonical_az/solver_score.py --max-k 2 \
    --arm-ckpt measurement/capacity_probe/f64b4_s0/V4_listwise/ranknet_best.pt \
    --arm-ckpt measurement/capacity_probe/f64b4_s1/V4_listwise/ranknet_best.pt \
    --arm-ckpt measurement/capacity_probe/f128b6_s0/V4_listwise/ranknet_best.pt \
    --arm-ckpt measurement/capacity_probe/f128b6_s1/V4_listwise/ranknet_best.pt \
    --arm-ckpt measurement/capacity_probe/f256b8_s0/V4_listwise/ranknet_best.pt \
    --arm-ckpt measurement/capacity_probe/f256b8_s1/V4_listwise/ranknet_best.pt \
    --workers 12 --out measurement/capacity_probe/solver_score_capacity.json
  ```
  (the same non-circular exact-solver ruler as the 5A rescore; NOT the
  in-training h6400 test-tau, which is circular w.r.t. the labels).

## Pre-registered thresholds (FIXED before results)

Per-size solver-τ = mean over the 2 seeds. "Size→τ slope" = τ gain per ~4×
params step (f64→f128b6 is ~5×, f128b6→f256b8 is ~4–5×; use the mean of the
two step deltas).

- **DEAD** if best solver-τ **< 0.25** AND the size→τ slope is **< +0.05 per
  ~4× params** → capacity is not binding; the M2/CL-039 closure extends to
  "capacity- and data-limit-independent on this representation". 10x scale
  would not help; the gap to the leaf is a representation/label problem, not a
  model-size problem.
- **LIVE** if solver-τ **≥ 0.3 anywhere** with a **rising size curve** →
  capacity was binding; the scale question reopens with an earned direction
  (train bigger on Q-labels before touching representation).
- In-between (e.g. τ 0.25–0.3, or a rising curve that stays < 0.25): report as
  AMBIGUOUS, extend the axis one more size before adjudicating — do not
  round up to LIVE.

Sanity guards: the f64b4 replicate must land near the known ~0.13 (else the
pipeline changed and nothing is comparable); a lone seed spiking >1σ above its
partner + neighbors is a noise signature, not a peak (results-discipline rule).

## Results

*(to be filled by the solver-scoring run after all 6 trainings — leave empty
until then)*
