# High-Contrast Decision-Signal Distillation — TRAINING

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEAS/DIAGNOSTIC ONLY.** No promotion · v2.9 frozen.
Plan: [HIGH_GAP_PLAN.md](HIGH_GAP_PLAN.md) · Dataset: [HIGH_GAP_DATASET.md](HIGH_GAP_DATASET.md) ·
Results: [HIGH_GAP_RESULTS.md](HIGH_GAP_RESULTS.md).

## Objective + loss

Policy-only fine-tune of RoD2 `iter04` (value & ownership losses zeroed: `--aux-weight 0
--value-loss-weight 0`). **Target = Q-softmax soft labels** `softmax(Q_legal / temp)`, temp=0.03 —
advantage-based, peaked ∝ the h6400 Q-gap (decisive states → peaked; indifferent → diffuse).
Deliberately **not** one-hot argmax (the prior experiment's failure) and **not** the h6400 visit
distribution (which is ~flat even on decisive states). Stabiliser mix (decisive states the student
already gets right) via `--warmstart-root … --warmstart-mix-fraction`, anti-forgetting.

## Variants

| variant | start | hard/stabiliser mix | what it tests |
|---|---|---|---|
| R0 | iter04 | — (no train) | baseline |
| R1 | iter04 | 70% hard / 30% stabiliser | primary repair |
| R2 | iter04 | 50% hard / 50% stabiliser | less forgetting (best regression tradeoff) |
| R3 | iter04 | hard-only | regression-risk probe (not needed — R1/R2 sufficed) |

## Convergence

**Pilot** (1616-pool, 570 hard train, 15 epochs): R1 train pol 3.245 → 2.689. Held-out movement
modest-but-real (regret −16% mean / −32% median, top1 0→0.135 strong-gap on n=96) — de-risked the
scale-up.

**Scaled** (20k-pool, 6342 hard train + 3611 stabiliser, 20 epochs, temp 0.03):

| variant | positions | epoch 1 pol | epoch 20 pol |
|---|--:|--:|--:|
| R1 (70/30) | 9158 | 2.992 | 2.413 |
| R2 (50/50) | 12513 | 2.683 | 2.095 |

Both fit the peaked soft target well below the uniform-policy floor (~log(legal_n)≈3.0). R2's lower
loss reflects its larger easy-stabiliser fraction, not better hard-state fit. **Unlike the prior
experiment, training generalised:** held-out hard top1 rose 0.000→0.18 (R1), regret −27% — the soft
Q-gap target carries transferable signal where the one-hot disagreement target did not. Full held-out
+ regression numbers in [HIGH_GAP_RESULTS.md](HIGH_GAP_RESULTS.md).

## Checkpoints (not promoted)

`/mnt/c/carc-shared/high_gap_distillation/{R1,R2}_from_iter04.pt` (R2 sha256
`fb949fd5802712a7…`). Diagnostic only — PRODUCTION.yaml / champion unchanged.
