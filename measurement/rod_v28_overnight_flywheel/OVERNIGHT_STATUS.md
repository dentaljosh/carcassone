# RoD v2.8 Overnight Flywheel — LIVE STATUS

**State:** RUNNING
**Updated:** 2026-06-23T05:06:09Z
**Branch:** rod_v28_overnight_flywheel · **Tag:** rod_v28_overnight_flywheel
**Deadline:** 2026-06-23T15:05:32Z (10 h)

iter 2 (RoD_iter_02) IN PROGRESS — warm from RoD_iter_01. Completed so far: 0. Stage: gen.

---
- Recipe (FROZEN): v2.8 leaf (meeple_k=2.0) · batch 256 · 3 epochs · VLW 1.5 · residual_scale 0.25 · sims 200 · c_puct 3.0 · games/iter 400
- Lineage: latest-chain RoD_iter_01 → iter_02 → … (warm-from previous iter)
- Workers (orch): local W48 · laptop W8 (enabled)
- Live deliverables: CHECKPOINT_MANIFEST.json · TRAINING_LOG_SUMMARY.md · CHEAP_SCREEN_RESULTS.csv
- Checkpoints: `/mnt/c/carc-shared/rod_v28_overnight_flywheel/ckpt/iter_*.pt` (all retained) · logs `/mnt/c/carc-shared/rod_v28_overnight_flywheel/logs/`
- MEASUREMENT ONLY — no promotion, PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen.
