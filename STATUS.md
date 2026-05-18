# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat. Keep this file SHORT — current state only. Historical narrative lives in [DECISIONS.md](DECISIONS.md).

## Right now (2026-05-18 ~15:15 EDT) — sims ladder COMPLETE (knee at 800; 800v200=76%, 800v400=62%, 1600v800=52%; 400 not enough → deeper-search self-play = full 4×). Xeon 2nd box deployed + benched + self-play-validated (ready for a shard, ~0.6× the 5800X → combined ~1.6×). Nothing in flight. Open: next strength lever (deeper-search self-play vs leaf redesign) — Joshua's call.

**iter_B1 — Option 2 Phase B stage 1 — DONE 2026-05-18 00:29 (533.9 min):**
- 1200-game v2.7 self-play from iter_01 + train + anchor-gate. Checkpoint: `checkpoints/v25_retrain_optionB_iter1/iter_00.pt`. Self-play value targets are `score_diff` (`tanh(margin/15)`), not W/L — the deliverable for the iter_B2 blend.
- **Anchor-gate vs iter_01: 14W/0D/6L, wr=0.70, avg diff +12.6 — PASS.** STATUS expected iter_B1 ≈ iter_02 (flat); it *gained* over iter_01 instead. But n=20 is noisy — treat as "promising, wants n=100 to confirm" before calling it a new global best.
- log `/tmp/optionB_iter1.log`.

**Overnight chain — RESULT (2026-05-18 00:53):** orchestrator ran iter_B1 → n=50 re-smoke → **POORLY**, stopped. **No iter_B2 launched.**
- Re-smoke (iter_B1 blended-leaf λ=0.5 vs plain leaf, n=50): **−15.5 avg diff, 31% wr (15W/1D/34L)** — worse than Phase A's W/L blend (−11.3/46%). **Option 2 (NN value-head blend) is dead** — the score-diff currency fix did not rescue it; the currency hypothesis is refuted.
- Residual diagnostic (`/tmp/residual_structure.log`): NN value head corr **+0.18** with the outcome vs the heuristic's **+0.61**, beaten by the heuristic in every game phase; best static blend cuts prediction MSE only 4% (in-sample-optimised → inflated). The script auto-verdict said "headroom" but that threshold is miscalibrated — honest read: **value-head injection (blend AND residual) is exhausted.** Don't spend 10h on residual.
- **iter_B1 strength — n=20 anchor (70%/+12.6) was a fluke.** n=100 confirm: **49W/0D/51L, +4.6 avg diff, elo −6.9** — iter_B1 ≈ iter_01, no new global best. The plain v2.7 recipe is **plateaued** (iter_00→01 +13.3, 01→02 +0.2, 01→B1 +4.6/49%).
- **Pivot (Branch B) — sims-depth A/B DONE 2026-05-18 ~10:30.** iter_01 @ sims=800 vs iter_01 @ sims=200, same checkpoint both sides (only search depth varies), n=50, plain v2.7 leaf: **38W/0D/12L = 76% wr, +24.9 avg diff, +200 elo.** Decisive (3.7σ) — **the policy is significantly under-searched at the production sims=200; deeper search is a large, under-exploited lever.** Reframes the "plateau": the v2.7 leaf is *not* a hard wall — iter_01→02→B1 flattening was the *training* recipe saturating, not the ceiling of what net+leaf can do with more search at play time. Log `/tmp/sims_ab_800v200.log`. Code: `eval_iter_head_to_head.py` gained an `--old-sims` flag, committed d613e13.
- **Sims ladder — COMPLETE 2026-05-18.** 3 rungs, all n=50, iter_01 both sides: 800 v 200 = **76%**; 800 v 400 = **62%/+10.8/+85 elo**; 1600 v 800 = **52%/+3.1/+14 elo**. **Knee at 800, confirmed both sides** — 400 is not enough (800 wins 62%), 1600 buys nothing over 800. 200→800 ≈ +200 elo. Logs `/tmp/sims_ab_{800v200,800v400,1600v800}.log`.
- **Free win available:** set production/play inference sims 200→800 (~+200 elo, no retrain, ~4× per-move latency — fine for human-paced play). Search is now a closed lever.
- **Next strength lever — Joshua's call (nothing auto-started):** (a) deeper-search self-play — retrain with sims=800 self-play (stronger teacher, may un-stick the policy plateau). Cost confirmed ~4× per-iter compute — 400 was tested, not enough, no 2× shortcut. ~1.5-2 day local on the 5800X; the Xeon (Quadro RTX 4000, WSL CUDA OK) could add ~1.4-1.6× throughput via a seed-range split once deployed. (b) leaf-eval redesign — the v2.7 heuristic is the other ceiling; bigger project.
- **Still open:** human benchmark (the documented superhuman blocker) — deferred until Joshua can play. Other harder levers: heuristic-leaf redesign, net capacity — see EXPERIMENTS.md.
- Artefacts (one-off, in `/tmp`): `optionB_overnight.sh`, `optionB_iter1_resmoke*.sh`, `residual_structure.py`, logs. Not committed.

**Option 2 (NN value-head blend) — why a 2-stage Phase B:** Phase A wired the leaf↔value-head blend — `LeafConfig.value_blend`, the evaluators, the eval_server `compute_value` path, `--value-target score_diff` (committed eb42c25). The λ=0.5 fixed-checkpoint smoke blended iter_01's *W/L*-trained value head and was mildly harmful (46% wr, −11.3 avg diff) — a currency mismatch with the graded score-diff leaf. So Phase B splits: iter_B1 mints a score-diff value head; iter_B2 is the real blended co-improvement test.

**Self-play perf optimization — parked (full rationale: DECISIONS.md 2026-05-17):**
- **Shipped** (`gpu-orchestrator`, 080fea7): hash-cache the engine value objects + precompute `FarmerSide.get_side` → ~20-24% faster leaf eval (cProfile). Live in iter_B1.
- **Option A** (memoize the find_* flood-fills) and **Option B** (incremental union-find) both **parked**. `find_farm` — the #1 hot path, ~58% of leaf cost — is start-dependent in the vendored engine and can't be safely cached or union-found. The find_city+find_road half (Option A) is verified-correct on branch `leaf-memoization` (3db30f1, unmerged) but only ~6% — not worth merge-risk attention.

**Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + c_puct=1.5 + sims=200, W=14 on the 5800X.

## Active branch

`gpu-orchestrator` — ahead of `origin/gpu-orchestrator` by 8. The v2.7-leaf retrain line + GPU orchestrator + Option-2 blend wiring live here. Single worktree (`carcassone`) — side worktrees removed 2026-05-18. Two unmerged side branches (no worktrees, reachable from the main repo): `leaf-memoization` (3db30f1 — parked find_city/road memo, ~6%, not worth merge-risk) and `play-vs-mcts` (04e4330 — stale human-vs-AI play UI, 93 commits behind, needs a forward-port before it runs). No merge to `phase-4-selfplay`/`main` pending.

## Second machine (Xeon) — deployed 2026-05-18

Xeon W-2135 (192.168.0.110, `ssh xeon` → WSL Ubuntu-24.04). Repo rsync'd, venv built (torch 2.11.0+cu128, CUDA OK on the Quadro RTX 4000). **Deployed + benched 2026-05-18 — ready to take a self-play shard.** Worker bench: engine-sim peak W≈10. Self-play smoke DONE — path validated end-to-end (orchestrator + Quadro eval-server + v2.7 leaf, 28 games across both boxes, 0 failures). Self-play throughput **~0.6× the 5800X** (single sims=200 game: 5800X ~307s, Xeon ~375s; optimal W=10 vs 14) → **combined ~1.6×**. GPU not the bottleneck on either box (eval-server 70%+ idle). **WSL gotcha:** detached processes die when the ssh/wsl session closes — hold the ssh session open for the run, or use `systemd-run` for a multi-day run. Full Xeon details in CLAUDE.md.

## Cloud note

vast.ai's docker-pull infra failed across 7 boxes on 2026-05-15 (all images, all regions, "Verifying Checksum" stalls) — iter_01/iter_02 ran locally instead ($0). If cloud is needed again, evaluate **RunPod Secure Cloud** (pre-cached templates sidestep the cold-pull stall). cloud helper scripts: `scripts/cloud_bootstrap.sh`, `cloud_pull_destroy.sh`, `cloud_retrain_watchdog.sh`.

## Recent history (full detail in DECISIONS.md)

- **2026-05-14** — diagnosed v1-v6 failure: the NN value head was the broken leaf eval. Pivoted to hand-crafted `virtual_score` leaf (v1 → v2 → v2.5).
- **2026-05-15** — v2.5 dedup bug fix + cap/P re-sweep → v2.7 (`cap=12`, drop-3-open); cloud-retrained iter_00 (+21pp over warmstart). v3 leaf cap tuning = n=20 noise (v2.7 holds). PUCT c sweep: low c catastrophic, c=1.5 default holds. W-bench: W=14 optimum for v2.7 recipe.
- **2026-05-16** — iter_01 retrain confirmed (+13.3, new global best). Strategy lit-review parked in BACKLOG. Docs hygiene + checkpoint cleanup (v1-v6 checkpoints removed, 2.7G→563M; `iter_12.pt` kept as `checkpoints/v6_iter12.pt`).
- **2026-05-17** — iter_02 flattened (+0.2 — policy saturated against the fixed leaf). Closure-P leaf refinement = null (pooled 47.5%, n=200) → pivot to Option 2 (NN value-head blend). Phase A wired (eb42c25); W/L-blend smoke mildly harmful → 2-stage Phase B, iter_B1 launched. Self-play hot path profiled + optimized (hash-cache + get_side, ~20-24%, 080fea7); deeper memoization (Options A/B) parked — find_farm is start-dependent.

## Key contact files for a fresh thread

1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec
3. [DECISIONS.md](DECISIONS.md) — every non-trivial decision + why; supersedes the original prompt
4. [EXPERIMENTS.md](EXPERIMENTS.md) — open ablation roadmap + findings ledger
5. [BACKLOG.md](BACKLOG.md) — deferred ideas (don't action without Joshua's OK)
6. This file (STATUS.md) — what's running, what's next

## Hooks active in this environment

- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks; if elapsed >5min, instructs Claude to actively check status (`ps`, tail output) rather than idle. Registered in `~/.claude/settings.json`.
