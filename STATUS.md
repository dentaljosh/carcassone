# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat. Keep this file SHORT — current state only. Historical narrative lives in [DECISIONS.md](DECISIONS.md).

## Right now (2026-05-17 ~10:20 EDT) — iter_02 DONE: compounding flattened. iter_01 stays global best. Nothing in flight.

**iter_02 result — the compounding ceiling is found:**
- 1200-game v2.7 self-play from iter_01, local, W=14, 11.3h, $0.
- n=100 vs iter_01: 51W/5D/44L = **53.5% wr, +0.2 avg score diff, +24.4 elo** — 0.7σ above 50%, within noise.
- iter_00→01 was +13.3; iter_01→02 is **+0.2**. The policy has **saturated against the fixed v2.7 leaf**. Data-scarcity helped for exactly 2 iterations then hit the leaf-defined ceiling.
- **iter_01 (`checkpoints/v25_retrain_iter01/iter_00.pt`) remains the global best.** iter_02 NOT promoted — 0.7σ is not a confident gain (same discipline as the v3/PUCT n=20 false winners). iter_02's checkpoint is kept; it's interchangeable with iter_01.

**Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + c_puct=1.5 + sims=200. Self-play worker optimum W=14 on the 5800X.

**Next — the lever is leaf-eval quality (plan-mode decision, nothing auto-started):**
1. **Improve the heuristic leaf** — lit-review refinements in BACKLOG 2026-05-16 (tile-counting closure prob, large-open-city penalty, targeted denial, stranding-risk meeple weighting). Lower-risk.
2. **NN value head as a correction term** — train a value head on iter_01/iter_02 self-play outcomes, use it to correct virtual_score's blind spots (farms especially). Higher-ceiling, more invasive.
3. **Human benchmark** — iter_01 has never played a human; Tier-1 is saturated. Sizes the real gap to superhuman. Worth doing first or in parallel.
- **Ruled out by the iter_02 result:** more iterations of this recipe (iter_03+ would land ~+0), and bigger policy net (saturates against the same leaf — capacity isn't the bottleneck).

## Active branch

`gpu-orchestrator` — ahead of `origin/gpu-orchestrator`. The v2.7-leaf retrain line + GPU orchestrator infra live here. No merge to `phase-4-selfplay`/`main` pending.

## Cloud note

vast.ai's docker-pull infra failed across 7 boxes on 2026-05-15 (all images, all regions, "Verifying Checksum" stalls) — iter_01/iter_02 ran locally instead ($0). If cloud is needed again, evaluate **RunPod Secure Cloud** (pre-cached templates sidestep the cold-pull stall). cloud helper scripts: `scripts/cloud_bootstrap.sh`, `cloud_pull_destroy.sh`, `cloud_retrain_watchdog.sh`.

## Recent history (full detail in DECISIONS.md)

- **2026-05-14** — diagnosed v1-v6 failure: the NN value head was the broken leaf eval. Pivoted to hand-crafted `virtual_score` leaf (v1 → v2 → v2.5).
- **2026-05-15** — v2.5 dedup bug fix + cap/P re-sweep → v2.7 (`cap=12`, drop-3-open); cloud-retrained iter_00 (+21pp over warmstart). v3 leaf cap tuning = n=20 noise (v2.7 holds). PUCT c sweep: low c catastrophic, c=1.5 default holds. W-bench: W=14 optimum for v2.7 recipe.
- **2026-05-16** — iter_01 retrain confirmed (+13.3, new global best). Strategy lit-review parked in BACKLOG. Docs hygiene + checkpoint cleanup (v1-v6 checkpoints removed, 2.7G→563M; `iter_12.pt` kept as `checkpoints/v6_iter12.pt`).

## Key contact files for a fresh thread

1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec
3. [DECISIONS.md](DECISIONS.md) — every non-trivial decision + why; supersedes the original prompt
4. [EXPERIMENTS.md](EXPERIMENTS.md) — open ablation roadmap + findings ledger
5. [BACKLOG.md](BACKLOG.md) — deferred ideas (don't action without Joshua's OK)
6. This file (STATUS.md) — what's running, what's next

## Hooks active in this environment

- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks; if elapsed >5min, instructs Claude to actively check status (`ps`, tail output) rather than idle. Registered in `~/.claude/settings.json`.
