# Distill-flywheel STAGE 2 (fair-NET-prior flywheel) — LIVE STATUS

**State:** DONE
**Updated:** 2026-07-19T00:34:46Z
**Branch:** rod_v2_flywheel · **Tag:** distill_flywheel_sighted_20260716 · **Iters:** 17..20 (STAGE 2)

STAGE 2 finished. Completed 4 stage-2 iteration(s). Latest: `/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_20.pt`. Next: the fair iter-12 eval (sighted net vs fair champion + net-iterN ladder) — a SEPARATE task.

---
- Gen agent (LOCAL): FairHeuristicPriorAgent + net-priors evaluator (severed value loop: net POLICY -> priors, FROZEN champion leaf -> value), k_dets=4 x sims=200, through carc-orch SHM (distill_stage2, 81 ch/42 sc).
- Champ side-stream (LAPTOP, net-free): FairHeuristicPriorAgent k_dets=4 x sims=688, curve125 — the 25% anti-drift anchor.
- Recipe: net 300 + champ 0 = 300/iter · window=12 · epochs=3 · batch=256 · vlw=1.5 · aux_weight=0.
- Warm: iter N <- iter_(N-1).pt (net ckpt for iter N gen = iter_(N-1).pt). Accumulate ALL iters. Checkpoints: `/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_*.pt`.
- GEN + TRAIN ONLY — no in-loop game eval. MEASUREMENT/EXPLORATORY; PRODUCTION.yaml untouched. STOP after iter 20 (eval = separate task).
