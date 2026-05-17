# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat. Keep this file SHORT — current state only. Historical narrative lives in [DECISIONS.md](DECISIONS.md).

## Right now (2026-05-17 ~00:10 EDT) — iter_02 retrain RUNNING. iter_01 confirmed global best. Joshua back Sun 11am.

**iter_02 retrain (in flight):**
- Launched 2026-05-16 22:01 EDT, detached (`nohup`, PID 93897). Log: `/tmp/iter02_local.log`.
- 1200-game v2.7 self-play from iter_01, W=14, sims=200, pure self-play training (`--warmstart-mix-schedule 0,0,0,0`), anchor-gate vs iter_01.
- Output: `checkpoints/v25_retrain_iter02/`, `data/selfplay/v25_retrain_iter02/`.
- ETA: retrain + n=20 anchor ~Sun 09:15 EDT; then auto-runs n=100 confirmation vs iter_01 (`/tmp/iter02_confirm.sh`) → final ~10:15.
- **Tests:** does the ~+13/iter compounding cadence hold, or has the policy saturated against the fixed leaf?

**iter_01 (confirmed global best):**
- `checkpoints/v25_retrain_iter01/iter_00.pt`. Beats iter_00 at n=100: 59.5% wr, +13.3 avg score diff, +66.8 elo.
- Data-scarcity hypothesis confirmed — iter_00 was +14.3 over warmstart, iter_01 is +13.3 over iter_00: two consecutive ~+14pt jumps from the same recipe. Ceiling is data quantity, not recipe/architecture.

**Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + c_puct=1.5 + sims=200. Self-play worker optimum W=14 on the 5800X.

**After iter_02 (pending Joshua — not auto-launched):**
1. If iter_02 keeps compounding (~+13): a longer multi-iter run is justified.
2. If iter_02 flattens: policy-saturation knee — leaf redesign (BACKLOG 2026-05-16, lit-review refinements) and/or NN value-head-as-correction-term.
3. **Human play vs the best checkpoint** — Tier-1 is saturated (~80-90% wr regardless), so it no longer measures progress. Direct human evidence is the only real superhuman test. Worth doing regardless.

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
