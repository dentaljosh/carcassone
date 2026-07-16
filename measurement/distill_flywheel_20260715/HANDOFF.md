# Distill-flywheel — overnight HANDOFF (2026-07-16)

Answer-ready status for Joshua's morning + any fresh session. Live per-iter state is in
`STAGE1_STATUS.md` (driver-written); design in `DESIGN.md` + `DESIGN_FAIR_ADDENDUM.md`.

## What's running
**Stage 1 (iters 0-3): pure FAIR-champion distillation.** Both boxes (local W16 + laptop W12,
`--shared-claim` work-stealing) run the blind PIMC champion `FairHeuristicPriorAgent`
(k_dets=4 × sims=688 = 2752 budget, curve125 leaf, c1.5/tau5/vnorm15) as a net-free CPU
self-play teacher, recording the pooled root-visit POLICY target + game-outcome VALUE
(`tanh((p0-p1)/15)`). LOCAL trains a 96×6 net per iter (accumulate ALL iters, window 12;
warm iter0←`warmstart_canonical.pt`, iterN←iter_(N-1)). No in-loop game eval.
- Driver: `scripts/distill_flywheel/run_distill_stage1.sh` (STOPS after iter 3).
- Run root: `/mnt/c/carc-shared/distill_flywheel_20260715/` (`ckpt/`, `iter_00..03/`, `probe_data/`, `logs/`).
- **ETA: ~18-20h for stage 1** (measured 45.6 s/game at local W16 / ~730s single-core; both boxes ~28 workers → ~4.4h/iter gen + ~0.4h train, × 4 iters). Launched 2026-07-16 ~01:53 EDT.
- **G0 is a MANUAL check** (the driver does NOT auto-halt on it — only the collapse screen rc=3 auto-halts). After iter 0 (~5h), confirm `probe_metrics.jsonl` iter-0 `probe_ce` < ~2.09 (10% below the warmstart baseline 2.320) and `value_r` ≥ 0.30. If it didn't drop, the distillation isn't working — inspect before trusting iters 1-3.

## Why FAIR (not clairvoyant)
Joshua's call: distilling the clairvoyant champion injects strategy-fusion bias (the net,
always blind, would learn the *average of deck-aware policies* — deck-peeking "gambles").
The fair champion plays the correct blind information state, so its visit distribution is a
legitimate blind policy target. Fair is only ~1.3× clair compute (measured), not 4×.

## How to check progress
- `cat measurement/distill_flywheel_20260715/STAGE1_STATUS.md` — live state (which iter, stage).
- `ls /mnt/c/carc-shared/distill_flywheel_20260715/iter_0*/  | wc -l` — gen shard counts.
- `tail logs/train_it*.log`, `logs/gen_local_it*.log`, `probe_metrics.jsonl` — per-iter metrics.
- Diagnostics (no-eval safety net): probe CE vs champion (should DROP each iter), value_outcome_corr,
  policy entropy. Collapse screen (rc=3) auto-halts the chain on training pathology.

## If the LOCAL box rebooted overnight (it has a dirty-reboot history)
The driver is reboot-safe: `done/` markers + ckpt-exists skip. Just re-run:
`cd /home/doctor/projects/carcassone && setsid nice -19 bash scripts/distill_flywheel/run_distill_stage1.sh </dev/null >> measurement/distill_flywheel_20260715/stage1_driver.log 2>&1 &`
It skips completed iters and resumes. (Laptop drop is self-healed: shared-claim + local-only fallback.)

## KEY morning decision — sighted vs non-sighted net
Running **non-sighted** (78ch, no bag histogram) to match `warmstart_canonical` + the DESIGN.
But the blind champion reasons over the bag (public info), so a **bag-aware "sighted" net
(81ch/42-scalar) could distill it more faithfully**. That needs a sighted warm-from we don't
have (can't launch tonight). If you want it, it's a day-build (sighted warm-from + re-gen
stage 1). Non-sighted is DESIGN-consistent, validates the pipeline, and is relaunchable.

## Next steps
1. Build **stage-2 (fair-net flywheel, iters 4-11)** while stage-1 generates — net-priors +
   frozen champion-leaf value through carc-orch; `FairHeuristicPriorAgent(evaluator=...)`
   already supports it (~20-line evaluator factory). Resume at gate G1 (after iter 3).
2. After iter 12: FAIR eval — net vs fair champion (distillation quality) + net-iterN ladder
   (flywheel effect). Separate task.

## Invariants held
PRODUCTION.yaml / the champion UNTOUCHED. Measurement/exploratory only — no promotion.
Branch rod_v2_flywheel. Not pushed.
