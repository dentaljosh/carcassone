# RoD v2 Flywheel (v2.9 leaf Bmild_cap8) — LIVE STATUS

**State:** RUNNING
**Updated:** 2026-06-26T12:36:47Z
**Branch:** rod_v2_flywheel · **Tag:** rod_v2_flywheel
**Deadline:** none (run all iters)

iter 7 (RoDv2_iter_07) — gen done (400 npz). Stage: train. Completed: 5.

---
- Leaf (FROZEN v2.9): Bmild_cap8 — curve -8,-4,-1,0,2,3,4,5 replaces flat meeple · cap 8 · 3-open
- Recipe (FROZEN): batch 256 · 3 epochs · VLW 1.5 · residual_scale 0.25 · sims 200 · c_puct 3.0 · games/iter 400
- Lineage: latest-chain RoD_iter_01 → iter_02 → … (warm-from previous iter)
- Workers (orch, GEN): local W28 · laptop W8 (enabled)
- GEN + TRAIN ONLY — no eval between iters. Checkpoints: `/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_*.pt` (all retained).
- MEASUREMENT/EXPLORATORY — no promotion, PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen.
