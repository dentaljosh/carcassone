# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat.

## Right now (2026-05-12 evening) — v5 cloud peaked above warmstart (iter_06 = 65% wr!) but halted at iter 9; GPU orchestrator landed on `gpu-orchestrator` branch

**Branch:** `gpu-orchestrator` (off `phase-4-selfplay`), pushed to `https://github.com/dentaljosh/carcassone` — public GH repo created today; cloud bootstrap can now `git clone` instead of rsync-over-proxy.

**v5 cloud result (~$5 total spend):**
- Recipe: mix-floor 0.5 + K=30 + best-so-far rachet + anchor-gate n=20 + sims=200 on rented 5090 + 48-core EPYC.
- Harness halted at iter 9 (3 consecutive FAILs, max-fails=3).
- Anchor trajectory: 40 PASS → 20 FAIL → 50 PASS → **60 PASS** → 30 FAIL → 50 PASS → **65 PASS** → 35 FAIL → 35 FAIL → 25 FAIL.
- **iter 3 and iter 6 are the first checkpoints that beat warmstart_canonical by a meaningful margin** (+20-25 pp). Recipe peaks above baseline but drifts back down. Rachet couldn't recover after iter 6.

**v5 artifacts pulled** (379 MB in `/tmp/cloud_v5_results/`, NOT in repo since checkpoints/+data/ are gitignored — needs `cp -r` into `checkpoints/selfplay_v5/` + `data/selfplay/v5_cloud/` for reboot persistence). Cloud box destroyed.

**GPU orchestrator landed today (commit `2191a61` on `gpu-orchestrator`):**
- `src/carcassonne_ai/eval_server.py` + `remote_evaluators.py` + `tests/test_eval_server.py` (4/4 pass in 24 s).
- `--orchestrator` flag on `run_selfplay_iter.py` (1 server) + `eval_iter_head_to_head.py` (2 servers).
- Numerical agreement < 1e-5 vs `make_batch_evaluator`. Local 5060 Ti bench: 0.91× (selfplay) / 0.88× (eval) — IPC overhead dominates on small GPU. Cloud W=48 vs current OOM-cap-W=20 is the actual proof-point.

**Recipe ceiling chronology:**
- v1: -330 ELO at iter 24 (chain-ELO discredited)
- v2: -200 ELO at iter 4
- v3: -107 to -123 ELO at iter 3/4
- v4: ceiling at ~50% wr, no above-baseline iter
- v5: **peaked at +25 pp (iter 6, 65%)** but couldn't sustain — first real partial-success

**Next-decision (plan-mode session needed):** "Phase 4 v6 + orchestrator-on" cloud run. Forks worth considering:
1. Use v5 `iter_06.pt` (the +25 pp peak) as the new warmstart and re-run v5 recipe
2. Bigger net (10×128 or 14×192) — orchestrator unlocks the VRAM headroom
3. Async training (train continuously while self-play runs)
4. Cheapest single experiment first: orchestrator cloud bench at W=48 chain h2h (~$1-2, ~1 h, proves the OOM fix)

**Vast.ai balance**: check before next launch.

---

## (Archive) 2026-05-12 morning — v3/v4 recipe both regressed; cloud bench validated W=48 + fp32

**Branch:** `phase-4-selfplay`. Latest commits `20aa166` (v3 recipe), `de8abd4` (fp16 batch bench), `503d004` (v2 fail docs).

**v3 result (2026-05-11)**: 5-iter sanity with mix=0.5 floor + best-so-far rachet + anchor-gate ran 4h on local 5800X+5060Ti. Anchor curve oscillated 40-60% (n=10 noisy); definitive 50-game anchors revealed **iter_3 at 34% wr, iter_4 at 32% wr → ELO -107 to -123 vs warmstart_canonical**. Improvement over v2's -200 ELO but still failed the ≥40% acceptance bar. Rachet kept rolling back to iter_0 (best at 55-80% n=10, true ~50%); chain never advanced. Quarantined.

**v4 attempt (2026-05-11 → -12)**: Same v3 recipe but **n=20 anchor gate** (tighter signal). Ran 5 iters on local W=16: iter 0=55%, iter 1=40%, iter 2=20% FAIL, iter 3=40%, iter 4=40%, iter 5=35% FAIL. Killed after 5 iters — pattern crystal clear: **iter_0 (55%) remains best-so-far indefinitely, rachet keeps rolling back, no iter ever exceeds warmstart**. Local recipe ceiling confirmed at ~50% wr vs warmstart.

**Cloud bench (2026-05-12 05:00-07:00 UTC, ~$0.40 spent)**:
- Rented RTX 5090 + 48-core EPYC 9J14 at $0.387/hr (Japan)
- Worker scaling sweep at sims=100/games=64: W=8→W=48 near-linear (~7× speedup), W=64 OOM at 32 GB VRAM
- **W=48 is the safe max** without MPS
- fp16 bench on Blackwell: single 0.82×, batch=8 0.92× (SLOWER both ways) — autocast overhead exceeds GPU compute savings for our 7M-param net + small batch
- Conclusion: **stay fp32, use W=48 for prod**

**MPS attempt #1 (2026-05-12, ~$0.40 wasted)**: Second 5090 rental had flaky network; rsync deadlocked twice for 30+ min. Destroyed without bench.

**MPS attempt #2 (2026-05-12, ~$0.40 wasted)**: Killed `uv pip install` mid-way to save time after it took 6+ min on torch>=2.7 upgrade. Bench ran but VRAM samples showed 0 processes — selfplay python failed silently at runtime (likely missing dep). Auto-destroy fired before I could cancel. No usable data.

**MPS test landed 2026-05-12 (~13:00 UTC, instance 36616189)**: per-worker VRAM is 662 MB no_mps / ~600 MB MPS (only ~10% savings — bottleneck is PyTorch allocator pool, not CUDA context). W=52 + MPS fits VRAM (31977/32607 = 98% used) but is *slower* than W=48 due to cgroup CPU oversubscription (5.3s/game wallclock vs 3.4s at W=48). **W=48 + fp32 + no-MPS is the locked optimum.** Real fix for scaling past 48 is inference-server pattern (1-2 days eng) or rent an 80 GB GPU (~$2/hr).

**Lesson learned**: `torch>=2.7` pin in requirements.txt is load-bearing for Blackwell (sm_120). Two wasted MPS rental attempts ($0.80) because we tried to skip the torch upgrade and use the pre-installed 2.4.0. Never skip uv pip install on a fresh box.

**Prod run plan (waiting on MPS data):**
- Recipe: same v3/v4 (mix=0.5, best-so-far, anchor-gate n=20) at sims=200, games=80
- Box: 5090 + 48-core EPYC, host 384353 has been reliable
- Workers: W=48 (or higher if MPS validates)
- 30 iters ≈ 25h × $0.387 ≈ $10 ($5 if MPS works)

**Vast.ai balance**: $2.07 → top up to ~$15 before prod.

**Open items deferred:**
- Bigger network (10×128 or 14×192) for if even cloud sims=200 plateaus
- Inference-server pattern (single network on GPU, workers query via queue) — addresses VRAM bottleneck structurally vs MPS

---

## (Archive) 2026-05-11 — Phase 4 v2 also regressed (-200 ELO); v3 recipe TBD

**Branch:** `phase-4-selfplay`. Latest commit `a1f29ec` (v2 recipe fixes).

**Headline:** v2 recipe (mix-floor 0.3, K=30, anchor-gate, eval-games 50) ran 5 iters in 4h. Chain ELO drift -98 (vs v1's misleading +612). Definitive iter_4 vs warmstart_canonical at n=50: **24% wr, ELO -200** (95% CI [13%, 37%], upper bound below the 40% acceptance threshold). Real regression, not noise. Recipe fix wasn't strong enough at this floor value. See DECISIONS.md "2026-05-11 — Phase 4 v2 recipe FAILED acceptance".

**Quarantined v2 artifacts (alongside v1; do NOT use as warmstart):**
- `checkpoints/selfplay_v2/iter_*.pt` (iters 0-4)
- `data/selfplay/v2_sanity/`
- Both kept on disk for Phase 6 emergence analysis.

**v3 recipe candidates (needs plan-mode session before implementing — don't piecemeal):**
1. Higher warmstart-mix floor (0.5 or 0.7) — most direct fix
2. Best-so-far reference instead of warmstart_canonical
3. Higher sims for self-play (200 vs 100) — addresses noisy policy targets
4. Reject-iter on anchor FAIL — restart from prev good iter instead of advancing

Select 1-2 for v3 (don't try all four — confounds the diagnosis if v3 also fails).

**Vast.ai rental still gated.** Balance unchanged at $2.07. Don't rent until v3 passes the anchor-bar acceptance.

**Open items deferred:**
- Bench fp16 with the BATCH evaluator on a meaningful checkpoint (single-evaluator was 0.83× = SLOWER on local 5060Ti). Wait until v3+ produces a non-quarantined checkpoint.
- Root-cause snapshot-mask vs MCTS-mask divergence (defensive clip handles symptom).

---

## (Archive) 2026-05-10 — Phase 4 RE-OPENED; 30-iter v1 recipe regressed; cloud rental aborted

**Branch:** `phase-4-selfplay`. Latest commit `2af55be`.

**Headline:** chain-vs-prev ELO climbed +612 over 24 iters, but anchor eval (`iter_24 vs warmstart_canonical`) showed iter_24 = **6W/1D/43L = -330 ELO** in absolute terms. The recipe drove an absolute-strength regression while the chained metric reported steady improvement. Full write-up in DECISIONS.md "2026-05-10 — Chain-vs-prev ELO discredited as standalone metric". 30-iter run was killed at iter 26; cloud rental aborted.

**Active background task (launched 2026-05-10 21:57):**
- Diagnostic anchors: `iter_5/10/15/20 vs warmstart_canonical`, 30 games each at sims=100, 16 workers. Serial loop in `/tmp/diag_anchor_loop.sh`, output `/tmp/diag_anchors.log`.
- iter_5 done: **9W/1D/20L vs warmstart, ELO -134** (regression already in place by iter 5). iter_10/15/20 still running (~45 min remaining).
- Confirms the recipe broke very early (likely as soon as warmstart-mix dropped to 0 at iter 3), not as a late-stage drift.

**Quarantined artifacts (do NOT use as warmstart for any subsequent run):**
- `checkpoints/selfplay/iter_*.pt` (iters 0-25, plus partial iter_26 self-play data)
- `data/selfplay/sanity_30iter/`
- Kept on disk only for the Phase 6 emergence-analysis archive. The 2026-05-03 "Phase 4 PASS" smoke artifacts (`data/selfplay/smoke_v1/`) are similarly quarantined.

**Recipe-fix shortlist (will be sequenced in a future plan-mode session before re-launching Phase 4):**
- Floor warmstart-mix at ≥0.3 throughout (do NOT drop to 0)
- K=10 → K=30 replay-buffer window
- Anchor-gate accept/reject for each iter's checkpoint vs warmstart_canonical (~3 min cost per iter)
- Bump eval games per chained head-to-head 20 → 50

**Production-readiness landed in this session (commits `fe8ede3` + `2af55be`):**
- skip-on-error in `run_selfplay_iter._play_one_pool`: failed games log+drop, no whole-iter abort (engine `farm_util.IndexError` rate ~1/1500 games)
- `--fp16` plumbed through `run_selfplay_iter.py`, `eval_iter_head_to_head.py`, `run_phase4_smoke.py` (default off; expects 1.5-2× forward speedup on Blackwell — fp16 is the right precision; fp4/fp8 require calibration not worth it for our 7M-param net)
- `--no-elo-log` flag for ad-hoc anchor evals (the lifesaver — caught the regression at $0)
- New `scripts/bench_fp16_vs_fp32.py` (numerical agreement + wallclock delta on N mid-game positions; not yet run)
- Updated `scripts/vastai_phase4_runbook.sh` with current 5090 pricing ($0.295/hr min) — held in reserve until Phase 4 recipe fixes land
- **Vast.ai balance: $2.07** — no top-up needed yet; cloud rental gated on Phase 4 v2 sanity passing

**Next steps (after diagnostic completes):**
1. Read iter_10/15/20 anchor curve, confirm regression slope
2. Plan-mode session for Phase 4 v2 recipe (the four fixes above; sequence + verification plan)
3. Re-run 5-iter smoke v2 with fixed recipe, anchor-eval gating from iter 0
4. If smoke v2 anchors POSITIVE vs warmstart, only then consider 200-iter cloud

**Open items deferred:**
- Root-cause the snapshot-mask vs MCTS-mask divergence (defensive clip handles symptom; benign at our scale).
- Larger eval game count per head-to-head (20 → 50+ — folded into recipe-fix shortlist).
- fp16 numerical+wallclock bench (`scripts/bench_fp16_vs_fp32.py`) — run once Phase 4 v2 has a meaningful checkpoint to bench against; meaningless on the quarantined ones.

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
