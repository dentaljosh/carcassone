# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat.

## Right now (2026-04-28, mid-Phase-2)

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
