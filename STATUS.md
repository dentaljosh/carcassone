# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat.

## Right now (2026-04-28, mid-Phase-2)

**Branch:** `phase-2-mcts` (all Phase 0 + 1 + 2 commits stacked here; not yet merged to `main`)

**Latest commits:**
1. `534043a` phase 2: vanilla MCTS with state-mutation rollout optimization
2. `9c05fd3` chore: disable noisy markdownlint rules in this repo
3. `bfab407` patch engine: open_positions adjacency tracking for fast legal-move queries
4. `d1e80fd` phase 1: AlphaZero-style game wrapper

**Active background task:** MCTS(s=10) vs random tournament, 100 games, 16 parallel Pool workers.
- Launched: 2026-04-28 ~09:15 local
- Output file: `/tmp/claude-1000/-home-doctor-projects-carcassone/<session>/tasks/bcsp6v7w6.output`
- Expected wall-clock: ~16 min total (post in-place rollout optimization)
- Acceptance criterion: MCTS wins ≥95/100 games

> Note: stdout is buffered when redirected to file; progress prints will appear in chunks rather than continuously. Verify health via `ps -o pid,etime,%cpu,comm | grep python` (expect 16 workers at ~95% CPU). Do NOT trust silent output as a sign of being stuck.

## When the tournament finishes

1. Read the result. If MCTS wins ≥95%, Phase 2 acceptance is met.
2. If <95%, retry at `--sims 20` (~30 min wallclock).
3. Update DECISIONS.md with the tournament outcome.
4. Optional: extend `scripts/measure_board_size.py` to support `--source mcts` for the prompt's "MCTS-driven board-size re-measurement" step. Not strictly required for Phase 2 acceptance.
5. Phase 2 is then complete. Decide with Joshua whether to merge `phase-2-mcts` → `main` or stay branch-separate.
6. **Phase 3** is next. Plan-mode session before implementation: network architecture (10-15 ResNet blocks, 128 filters), warm-start labeled-position generation (~500K positions), supervised pre-training. Acceptance: warm-started network beats random 90%+ standalone, network+MCTS(s=50) beats vanilla MCTS(s=100) at >55%.

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
