# RoD v2.8 Overnight Flywheel — LIVE STATUS

**State:** NOT YET LAUNCHED (pre-flight)
**Updated:** 2026-06-23 (setup)
**Branch:** rod_v28_overnight_flywheel · **Tag:** rod_v28_overnight_flywheel

This file is **overwritten live** by `scripts/rod_v28/run_overnight_flywheel.sh` at each stage (gen → train → smoke → screen) and on exit. **Read it first in the morning.**

---
- Recipe (FROZEN): v2.8 leaf (meeple_k=2.0) · batch 256 · 3 epochs · VLW 1.5 · residual_scale 0.25 · sims 200 · c_puct 3.0 · games/iter 400
- Lineage: latest-chain RoD_iter_01 → iter_02 → … (warm-from previous iter)
- Workers (orch): local W48 · laptop W26
- Live deliverables: CHECKPOINT_MANIFEST.json · TRAINING_LOG_SUMMARY.md · CHEAP_SCREEN_RESULTS.csv
- MEASUREMENT ONLY — no promotion, PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen.
