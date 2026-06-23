# RoD v2.8 Overnight Flywheel — FINAL STATUS

**State:** ⏹ STOPPED (user's call, 2026-06-23) — chain reached **iter_17** of a target 30.
**Branch:** rod_v28_overnight_flywheel · **Tag:** rod_v28_overnight_flywheel

## Outcome
- **Chain:** RoD_iter_01 → iter_02 → … → **iter_17** (16 continuation iters). All checkpoints retained at `/mnt/c/carc-shared/rod_v28_overnight_flywheel/ckpt/iter_02..17.pt`; `done/` markers iter2–17 match.
- **Evaluated (iters 02–10):** keep-best = **iter_08** (+33.1 elo / paired_z +2.00 vs RoD_iter_01, n=400). vs **heur@3200_v2.8 = TIE at n=800** (+6.5 wr / −0.38 paired) — reaches deep-heuristic **parity, does NOT exceed**. Full report: [EVAL_RESULTS.md](EVAL_RESULTS.md).
- **Unevaled (iters 11–17):** generated with `DO_SMOKE=0` (no per-iter eval); retained for a future keep-best + ruler pass if revisited.
- **Verdict:** modest internal gain that washes out non-transitively vs the external ruler → blocker #2 stands. Nothing promoted; champion (`flywheel2_champion_iter8`) + PRODUCTION.yaml unchanged; v2.7 frozen.

## To resume the chain later (from iter_18)
`START=18 ITERS=30 DO_SMOKE=0 DURATION_HOURS=0 OW_LOCAL=28 OW_LAPTOP=8 nohup nice -n 19 bash scripts/rod_v28/run_overnight_flywheel.sh &` (warms from iter_17). Both boxes are idle/clean.
