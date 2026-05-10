# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat.

## Right now (2026-05-08) — vloss MCTS landed; mid-prod calibration running

**Branch:** `phase-4-selfplay`. Latest commit `f9d805e` (virtual-loss + batched-eval). One uncommitted change: vloss wired into `eval_iter_head_to_head.py` + plumbed through `run_phase4_smoke.py`.

**Active background task (launched 2026-05-08):**
- `nohup python -u scripts/run_phase4_smoke.py --iters 2 --games 10 --sims 100 --eval-sims 100 --eval-games 10 --workers 7 --eval-workers 4 --batch-size 8 --output-root data/selfplay/midprod_calibration > /tmp/phase4_midprod_calibration.log 2>&1 &`
- Purpose: measure per-iter wallclock at mid-prod sims (sims=100, eval-sims=100) with vloss=8 on multi-worker pool. The 1.44× single-process measurement is a floor; multi-worker GPU contention dynamics could shift it either way.
- Detached so it survives any SSH disconnect. Resumable via per-game .npz / per-game .json caches.

**vloss MCTS landed (commit `f9d805e`):**
- `NeuralMCTS` constructor gained `batch_size`, `batch_evaluator`, `virtual_loss`. Default `batch_size=1` preserves serial behavior.
- Vloss applied in PARENT's perspective (sign depends on parent-child same/different player), so PUCT actually drops in alternating-player trees. 9 new tests in `test_neural_mcts_virtual_loss.py`.
- `run_selfplay_iter.py` and `run_phase4_smoke.py` accept `--batch-size N` and `--virtual-loss V`. Eval (`eval_iter_head_to_head.py`) wired up the same way as part of the calibration prep.
- Single-process bench at sims=25, batch_size=8: 48.9s → 34.0s (1.44×) for one self-play game.

**Phase 4 smoke (closed 2026-05-03) — see DECISIONS.md "2026-05-03 — Phase 4 smoke PASS":** 5 iters, 53.7 min wallclock, ELO 0→175.7. Strictly non-decreasing. No crashes, no NaN losses, no policy collapse. Acceptance bar met.

**Phase 4 artifacts on disk:**
- `data/selfplay/smoke_v1/iter_0[0-4]/seed_*.npz` + `eval/iter_NN_vs_MM/*.json` + `elo_log.json`
- `checkpoints/selfplay/iter_0[0-4].pt` + `.metrics.json`

**Next decisions when calibration completes:**
- If wallclock extrapolates to a reasonable mid-prod budget (~1 weekend for 50 iters), launch the full mid-prod run.
- Otherwise tune sims/games or accept the smoke endpoint and start Phase 5.
- Phase 5 (position analyzer / coach) is the project's actual goal; production-scale Phase 4 is optional polish.

**Open items deferred:**
- Root-cause the snapshot-mask vs MCTS-mask divergence (defensive clip handles symptom; benign at our scale).
- Larger eval game count per head-to-head (10 → 30+ for production).

## Phase 4 archive (2026-04-29 → 2026-05-03)

(See DECISIONS.md "2026-05-03 — Phase 4 smoke PASS" for the full closure entry.)

## Phase 3 archive (2026-04-28 → 2026-04-29)

## Phase 3 attempt history

### v1 (tau=10.0) — 2026-04-28 evening

| Test | Result | Threshold | Pass? |
|---|---|---|---|
| T1 net argmax vs random, n=100 | 84/100 (+19.0) | ≥90% | NO |
| T2 smoke n=2 at s=20/s=20 | 0/2 (-6.5) | smoke | NO |

Diagnosis: policy head couldn't fit near-uniform heuristic targets at tau=10. Train pol CE 1.86 → 1.86 (flat).

### v2 (tau=0.5) — 2026-04-28 night

| Test | Result | Threshold | Pass? |
|---|---|---|---|
| T1 net argmax vs random, n=100 | 88/100 (+32.1) | ≥90% | NO (within statistical noise) |
| T2 partial n=16 at s=50/s=100 | 5/16 (31%, -18.2) | >55% | NO (~97% confidence per Bayesian P(true≥55%)=3.0%) |

Diagnosis: policy now learning (train pol CE 1.79 → 1.26, val 1.79 → 1.66) but the policy is the wrong policy — losing decisively on low-roll-rule games. Either c_puct miscalibration (Plan B step 1) or labels still too noisy (Plan B step 2 = 2-ply).

T2 was killed twice by Mac sleep before nohup workflow rule landed. Per-game checkpoints saved 16/100 for v2 partial — not resumed because n=16 already gives >97% confidence T2 fails.

## v1 acceptance — Phase 3 misses (2026-04-28)

| Test | Result | Threshold | Pass? |
|---|---|---|---|
| T1 net argmax vs random, n=100 | **84/100** (84%, +19.0 avg diff) | ≥90% | NO |
| T2 smoke NeuralMCTS s=20 vs vanilla s=20, n=2 | **0/2** (avg diff -6.5) | (smoke only) | likely NO at scale |

**v1 training metrics (100K positions, tau=10.0):**
- Train value MSE: 0.165 → 0.030 (5.5× reduction — strong)
- Val value MSE: 0.137 → 0.081, best at epoch 14
- Train pol CE: 1.860 → 1.855 (FLAT)
- Val pol CE: 1.879 → 1.879 (FLAT)
- Diagnosis: value head learned, policy head couldn't fit near-uniform targets.

**T2 production cost estimate** that drove the pause: NeuralMCTS s=50 vs vanilla MCTS s=100 = ~28 min/game × 100 games / 2 spawn workers ≈ 24h wallclock. Bottleneck is vanilla side at s=100 (random rollouts, ~300ms each).

### Smoke comparison — COMPLETE (2026-04-28)

| Step | Status | Result |
|---|---|---|
| Heuristic gen (5K positions) | DONE | ~2 min wallclock |
| Heuristic train (4×64, 20 ep) | DONE | val MSE 0.21→0.10; pol CE flat at 1.93 |
| Heuristic tournament (50 games vs random) | DONE | **35/50 (70%)** wins, +3.0 avg diff |
| MCTS s=50 gen (5K positions) | DONE | ~55 min wallclock (Pool x16) |
| MCTS train (4×64, 20 ep) | DONE | val MSE 0.21→0.21; pol CE 1.85→1.90 |
| MCTS tournament (50 games vs random) | DONE | **39/50 (78%)** wins, +7.6 avg diff |
| `compare_warmstart_smoke.py` decision | DONE | **HEURISTIC wins by 24.7x in wins-per-hour-of-gen** |

**DECISION:** Production warm-start uses Option D (heuristic-only, scale to 500K). Logged in DECISIONS.md.

**GATED on 3 prerequisite fixes** before kicking off the 500K production gen:
1. Board encoding richness (meeple side/corner + tile internal topology)
2. Scalar feature normalization
3. Streaming/IterableDataset trainer

These are in BACKLOG and must land before the production warmstart commits compute.

### Active background tasks

- **MCTS s=50 generation:** 500 games × 10 positions/game = 5K labeled positions. 16-worker Pool. **Revised ETA ~2.5 hours total** (steady-state 5 min/game/worker; my earlier 55-min estimate from the 2-game smoke was too low — that test had low SMT contention).
   - Output dir: `data/warmstart/mcts/seed_*.npz`
   - Script: `scripts/generate_warmstart_smoke.py --label-strategy mcts --n 5000`
   - Resumable: skips cached seeds. To wipe: `--reset`.
   - Job died once at 125/500 (cause unknown — possibly SSH disconnect propagating SIGHUP). Resumed cleanly at 148/500. Currently 250-260/500 done (~50% through). ETA ~30 min from now.

### NeuralMCTS + Tournament 2 script (added during the gen wait)

- `src/carcassonne_ai/mcts.py` now has `NeuralMCTS` (PUCT selection, network leaf evaluator). 5 tests pass.
- `scripts/eval_neural_mcts_vs_vanilla.py` runs Phase 3 acceptance Tournament 2 (NeuralMCTS(s=50) vs vanilla MCTS(s=100)). Pattern matches `play_mcts_vs_random.py` checkpointing.

### External review 2026-04-28

Two bugs found and fixed:
- `Game.get_canonical_form` was double-swapping mine/opp when player != current_player. Fixed; new regression test in `tests/test_invariants.py`.
- `warmstart.generate_one_game_dataset` didn't seed the global `random` module before `get_init_board()`. Engine deck shuffle uses global random, so seeds weren't reproducible. Fixed.

Three production-prerequisites flagged for BACKLOG (must land before scaling smoke up):
- Board encoding richness (meeple side/corner; tile internal topology)
- Scalar feature normalization
- Streaming/IterableDataset trainer

Smoke comparison is unaffected — both label strategies share these limitations.

### When both background tasks finish

1. Train MCTS-net on the just-generated 5K MCTS dataset: same params (4×64, 20 epochs). ~5 min.
2. Eval both nets vs random, 50 games each (no MCTS at inference, network argmax-policy):
   - `python -u scripts/eval_warmstart_smoke.py --checkpoint checkpoints/warmstart_heuristic_smoke.best.pt --n 50`
   - `python -u scripts/eval_warmstart_smoke.py --checkpoint checkpoints/warmstart_mcts_smoke.best.pt --n 50`
3. Decision rule: pick winner by **wins per hour of generation cost**. Heuristic gen ≈ 1 min for 5K, MCTS gen ≈ 55 min. So heuristic must produce non-zero useful signal to win; if it lands at 30+/50 wins, it's the right answer (10x cheaper for similar quality).
4. Commit smoke results + decision in DECISIONS.md.
5. Run the full chosen-strategy generation: 500K positions for D (~1.5h) or 50K for C (~9h post-fix from the plan's 26h estimate).

### Files added this session (Phase 3 prep, uncommitted)

- `src/carcassonne_ai/virtual_score.py` — engine-`count_final_scores`-based labeler. 8 tests pass.
- `src/carcassonne_ai/network.py` — 6×96 ResNet with 1×1 conv heads (~7.4M params). 7 tests pass.
- `src/carcassonne_ai/warmstart.py` — dataset IO + heuristic/MCTS labeling.
- `scripts/generate_warmstart_smoke.py` — Pool-parallel labeled-position generation, --reset / --summary-only.
- `scripts/train_warmstart_smoke.py` — supervised training, train/val split by game.
- `scripts/eval_warmstart_smoke.py` — N-game tournament vs random.
- `tests/test_virtual_score.py`, `tests/test_network.py` — coverage.
- DECISIONS.md updated with Phase 3 network-capacity rationale.

All 63 tests pass.

## (Archive) Phase 2 status (now historical)

**Branch:** `phase-2-mcts` (all Phase 0 + 1 + 2 commits stacked here; not yet merged to `main`)

**Latest commits:**
1. `508c1c1` mcts: best_action picks by Q, not N (fixes near-random play at low s)
2. `dd88386` add per-game checkpointing + resume to play_mcts_vs_random
3. `d236477` docs: handoff scaffolding (CLAUDE.md, STATUS.md, ORIGINAL_PROMPT.md)
4. `534043a` phase 2: vanilla MCTS with state-mutation rollout optimization
5. `9c05fd3` chore: disable noisy markdownlint rules in this repo
6. `bfab407` patch engine: open_positions adjacency tracking for fast legal-move queries
7. `d1e80fd` phase 1: AlphaZero-style game wrapper

**Known issue caught and fixed:** Initial `best_action` picked the most-visited child. At s=10 with ~50 root actions, most children have N=1, so the choice was effectively arbitrary — empirically MCTS won only ~47% vs random. Fixed by picking by Q-value (mean rollout reward); falls back to N for ties. Tournament re-running with `--reset` to confirm.

**Active background task:** MCTS(s=10) vs random tournament, 100 games, 16 parallel Pool workers (restarted ~09:55 with `python -u` + per-game checkpointing).
- Launched: 2026-04-28 ~09:55 local (after a non-checkpointed run was killed at 32 min for opacity)
- Expected wall-clock: ~30 min total
- Acceptance criterion: MCTS wins ≥95/100 games
- **Resumable:** results stream to `data/tournament/s0010_seed*_p*.json` as each game completes. If killed mid-run for any reason (laptop sleep, manual stop, optimization swap), rerun the SAME command to pick up where it stopped:

  ```bash
  python -u scripts/play_mcts_vs_random.py --n 100 --sims 10
  ```

  To inspect progress without running:
  ```bash
  ls data/tournament/ | wc -l                # files = games done
  python scripts/play_mcts_vs_random.py --summary-only --n 100 --sims 10
  ```

  To restart from scratch, add `--reset`.

## When the tournament finishes (Joshua away ~60 min from 2026-04-28 ~10:30)

Joshua left during the run. I will:

1. Read the final result, write a summary at the bottom of this file under "Tournament outcome".
2. **Wait for Joshua's decision** on whether to accept the result or rerun at higher s. Won't autonomously launch a rerun.
3. Idle until Joshua returns or instructs further. The harness's hooks will keep firing during my idle but I'll have genuinely nothing actionable to do until you're back.

When you return, the decisions waiting for you are:

- **If MCTS wins ≥95/100:** Phase 2 acceptance met. Commit the tournament results, update DECISIONS.md, and decide whether to start Phase 3 plan-mode or pause for review.
- **If MCTS wins 80-94/100:** strong but below target. Either (a) accept (MCTS is verifiably real; the 95% target was based on Ameneyro's s=100, not s=10), or (b) rerun at `--sims 20` (~50 min wallclock) for a more decisive number. My weak preference is (a) — the bot's job in Phase 2 is to be a sparring partner, not optimal play. Phase 3+ replaces it.
- **If MCTS wins <80/100:** something else is wrong (not just budget). Investigate before proceeding to Phase 3.

In any case: the per-game results in `data/tournament/` are durable; subsequent runs (different `--sims` values) write to non-conflicting filenames, so there's no need to wipe.

**Phase 3** is the next big chunk: network architecture (10-15 ResNet blocks, 128 filters), warm-start labeled-position generation (~500K positions), supervised pre-training. Acceptance: warm-started network beats random 90%+ standalone, network+MCTS(s=50) beats vanilla MCTS(s=100) at >55%. Plan-mode session recommended before any code.

## Tournament outcome

**Phase 2 PASS** — MCTS(s=20) vs random, 100 games, 16 parallel workers:

| Metric | Value |
|---|---|
| MCTS wins | **96 / 100 (96.0%)** |
| Draws | 0 |
| MCTS losses | 4 |
| Avg score diff (MCTS − random) | +30.9 |
| Avg moves/game | 166 |
| Avg wall-clock/game | 11m16s |

Acceptance criterion (≥95%) met. Per-game JSON results in `data/tournament/s0020_seed*_p*.json`.

Phase 2 finalization commit: `508c1c1` (Q-tiebreak fix is the load-bearing change). Tournament data not committed (gitignored under `data/`); reproducible via `python scripts/play_mcts_vs_random.py --n 100 --sims 20`.

Next: Phase 3 (network + warm start) — see plan file `~/.claude/plans/new-project-in-this-spicy-finch.md`.

## Pending non-blocking items

- BACKLOG entry: in-place state mutation for MCTS rollouts (DONE — applied during Phase 2; remove from BACKLOG)
- BACKLOG entry: GPU forward batching for Phase 4 — virtual-loss MCTS pattern. Mandatory for Phase 4 wallclock budget.
- BACKLOG entry: Phase 3 prerequisite: implement `virtual_score_estimate` (currently a NotImplementedError stub in mcts.py)
- BACKLOG entry: cloud rental ($30-200) for Phase 4 long runs once local smoke-test confirms loop is healthy

## Hooks active in this environment

- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks via fuser; if elapsed >5min, instructs Claude to actively check status (`ps`, tail output) instead of just "find adjacent work". Settings registered in `~/.claude/settings.json`.

## Key contact files for a fresh thread

1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec
3. [DECISIONS.md](DECISIONS.md) — what we decided and why; supersedes any specific number in the original prompt
4. This file (STATUS.md) — what's running, what's next

## Outstanding questions for Joshua

- Whether to merge `phase-2-mcts` → `main` once acceptance is met, or keep all phase branches separate. Default per Joshua's earlier instruction: keep branches separate.
- Whether to start Phase 3 immediately after Phase 2 commit, or pause for review. Default: pause for review.
