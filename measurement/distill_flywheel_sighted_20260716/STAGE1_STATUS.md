# Distill-flywheel STAGE 1 (fair-champion distillation) — LIVE STATUS

**State:** DONE
**Updated:** 2026-07-17T05:30:46Z
**Branch:** rod_v2_flywheel · **Tag:** distill_flywheel_sighted_20260716 · **Iters:** 0..3 (STAGE 1 only)

STAGE 1 finished. Completed 4 iteration(s). Latest: `/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_03.pt`. STOP — stage 2 (fair-net flywheel, iters 4..11) is a SEPARATE task. Next: post-stage-1 review + the stage-2 build.

---
- Teacher: FairHeuristicPriorAgent (blind PIMC), k_dets=4 x sims=688 (=2752 budget), curve125 leaf.
- Recipe: GAMES/iter=600 · window=12 · epochs=3 · batch=256 · vlw=1.5 · aux_weight=0.
- Boxes (gen): local W16 + laptop W12 (enabled), shared-claim, orch-OFF.
- Warm: iter0 <- m2_sighted/warmstart_sighted.pt (SIGHTED 81ch/42); iterN <- iter_(N-1). Accumulate ALL iters. Checkpoints: `/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_*.pt`.
- GEN + TRAIN ONLY — no in-loop game eval. MEASUREMENT/EXPLORATORY; PRODUCTION.yaml untouched. STOP after iter 3 (stage 2 = separate task).
