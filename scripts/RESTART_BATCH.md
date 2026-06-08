# Flywheel RESTART BATCH — deferred robustness fixes (apply when `flywheel_residual_v2` ends)

These fixes could NOT be applied to the **live** `run_residual_flywheel.sh` (editing a running
bash script corrupts its execution — bash re-reads by byte offset). They're staged in a verified
copy. Apply at the next flywheel launch.

## What's ready
**`scripts/run_residual_flywheel.next.sh`** = the live script + the 4 robustness fixes below
(`bash -n` clean; 43 lines changed vs live). Sources: shell-audit `w3gbnte6z`, round-4 `wconmb57r`.

| id | fix | where |
|---|---|---|
| **D-S1** | per-loop **heal cap** (`HEAL_CAP=8`, env-overridable) → a no-progress loop exits **1 loud** instead of hanging forever; + a `_share_writable` probe so a heal backs off when the share is gone instead of relaunch-storming | all 3 wait loops (gate/odo/gen) |
| **D-S2** | `_kill_pool` reaps the prior pool on all 3 boxes (`pkill -f eval_net_vs_heuristic` / `run_selfplay_iter`) **before** each heal relaunch → no orphan-worker accumulation (the ~56-proc pileup) | all 3 heals |
| **D-S3** | `_clean_stranded` in-loop age **4min → 30min** → the heal can't delete a slow-but-alive worker's claim → no duplicate-played seeds | all 3 heals |
| **D-S6** | `cp best.pt warm.pt` now **fails loudly** (`[ -s best.pt ]` guard + `|| exit 1`) instead of silently warming from nothing (`set -e` is off) | per-iter warm staging |
| **D-S7** | **plateau `break` ran BEFORE the odometer block** → the terminal iter's out-of-lineage odometer was **SKIPPED** (the 2026-06-08 iter3 miss; recovered manually via `scripts/odo_oneshot.sh`). Fixed: the `break` now happens **after** the odometer, and the odometer fires on **any terminal iter** (plateau OR last), not just the `ODO_EVERY` cadence — so the final out-of-lineage signal is never lost. | iter-loop tail |
| D-S4 | (ssh rc=255 box-drop) — **partially** covered: the heal's `_kill_pool`+relaunch re-adds a dropped box on the next stall. A dedicated launch-retry wrapper is a further improvement, not included (low impact: work-stealing + heal recover it). | — |

## How to apply (at restart, after the current run's processes are gone)
```bash
cd /home/doctor/projects/carcassone
bash -n scripts/run_residual_flywheel.next.sh          # sanity
cp scripts/run_residual_flywheel.next.sh scripts/run_residual_flywheel.sh
rm scripts/run_residual_flywheel.next.sh
git add scripts/run_residual_flywheel.sh && git commit -m "flywheel: apply restart-batch robustness (D-S1/2/3/6)"
git bundle create /mnt/c/carc-shared/code_sync/carc_stage-b-wiring.bundle stage-b-wiring   # so remotes get it
```

## Also apply before any **mix>0** retrain (NOT needed for the flywheel — it runs mix=0.0)
- **D-R4-1 — train/val LEAK (`src/carcassonne_ai/warmstart.py` `split_files_train_val`):**
  `_build_mixed_file_list` (`train_iter.py:~249`) samples warmstart files **with replacement**, and
  the split partitions by **list index**, so a duplicated path can land in BOTH train and val →
  leaks → inflates the val value-outcome corr (the "trustworthy" per-iter signal). **Fix:** assign
  each **unique** path to train xor val first, then expand with-replacement duplicates into the
  **train** side only. (Result-neutral at mix=0.0, so the live flywheel is unaffected.)
- **D-R4-2 — `auto_chain_h2h_flywheel.sh` count()/tally()** glob the whole eval dir with no
  seed-range filter (a pre-existing larger run in the same dir could end `wait_h2h` early). Latent
  (orchestrator already exited). Scope to the target's seed range before reusing that script.

## NOT in this batch — research decisions for attempt #2 (your call, not mechanical fixes)
- **S-R3-1** (the big one): residual target Δ∈[−2,2] vs tanh value head [−1,1] → high-|Δ| positions
  under-learned. Lever: clip the target to [−1,1], or a linear residual head.
- **Deck diversity:** every flywheel iter reuses seeds 0–399 → vary per iter (`--seed-start $((it*GAMES))`).
- **Leaf choice (CL-010):** the net beats heur@800-v2.7 but loses heur@800-v1, and v1 is the stronger
  standalone leaf — decide whether v2.7 should remain the production leaf.
