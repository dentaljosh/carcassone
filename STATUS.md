# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-06-02 late eve) — 🟢 PHASE 0 + RE-BASELINE + ROUND-2 AUDIT + EVAL-PATH FIXES + WORK-STEALING + CLUSTER DASHBOARD all done. 🔵 STAGE A2 VERDICT all but fpu04 done; FPU is the live lever.

**🔵 IN FLIGHT (Stage A2 verdict, WORK-STEALING relaunch):** the original disjoint-shard run (`sweep_stageA_verdict.sh`) stranded the laptop idle on the foregone c25 tail, so it was killed and relaunched as `~/sweep_verdict_steal.sh` (tracked `scripts/sweep_verdict_steal.sh`) with `--shared-claim` (all 3 boxes on the same seed range, atomic `.claim` sidecars). Launcher PID 1091646, watcher `bbaa5n1dj`, out `/mnt/c/carc-shared/verdictA/<cell>/eval/iter_NN_vs_MM/`, logs `/tmp/verdictS*.log`. **Resume:** `kill -0 1091646`; `grep VERDICT /tmp/verdictS.log`; tally cell dirs for `s*.json`.
- **VERDICT — c_puct + cap are FLAT (paired n=400, se≈2.5pp):** `self_c3` **49.5%** (z=−0.20) → deck-pairing VALIDATED (unpaired self-cell was 42% harness bias, gone). `c15` **+15.6** (z=0.90 n.s.), `c20` **−17.4** (z=−1.0 n.s. — REVERSES the n=100 "+18pp c=2.0" screen = noise), `c25` **−15.6** (z=−0.90 n.s.). **→ c_puct flat across 1.5–3.0; production c=3.0 + cap=12 STAY.** Rows in `results.csv` (`verdict_*`).
- **FPU is the ONE live lever:** `fpu02` (fpu_reduction=0.2) = **56.5% / +45.4 elo / z=+1.85** — the FIRST non-flat cell in the whole sweep. **n=200 is a SCREEN, not a verdict** (z<2; lone-spike discipline) → **must CONFIRM at n=400 paired before promoting to production.** `fpu04` (0.4) finishing now (~50 games out, 5800x+xeon on the tail; laptop drained early = claim-tail inefficiency, visible on the dashboard).

**✅ NEW — cluster dashboard (fe27b9c):** `scripts/cluster_heartbeat.py` (stdlib, per box → `<share>/status/<host>.json` every 4s: CPU%/load/GPU util-power-VRAM/job) + `scripts/cluster_status.py` (no flag = consolidated table = my deterministic status check; `--serve PORT` = live auto-refresh web page). **Live now:** heartbeats on all 3 boxes + server on 5800x `:8765`. ⚠️ bound inside WSL2 → reach from Mac via SSH `-L 8765:localhost:8765` (zero setup) or a Windows `netsh portproxy` (tailnet/phone). 4 long-lived procs (3 hb + server) need relaunch after any box reboot (e.g. the incoming 5950x swap).

**✅ Eval-path fixes shipped:** (f2a64b7) **G-M2** `eval_iter_head_to_head --paired` + **G-M6** `--seed-start`→1e9 + **F-D-FPU** `NeuralMCTS(fpu_reduction=)`/`--new-fpu`/`--old-fpu`. (12153b6) `--shared-claim` work-stealing verdict sweep. (14bcb75) **gauntlet `eval_net_vs_heuristic.py` got `--shared-claim` + `--paired`** (for the high-sim reference rung). 342 tests pass.
**✅ Safe fixes (b1a2055):** G-M1 n-doctrine corrected (n=400≈±17 elo not ±9; +25.2 re-baseline was inconclusive); `train_iter --lr-schedule/--value-loss-weight` knobs; A6 `--value-target score_diff_wide` (tanh/40).

**READ FIRST:** [docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) (path) + [docs/PHASE1_BUILD_SPEC_2026-06-02.md](docs/PHASE1_BUILD_SPEC_2026-06-02.md) (concrete build) + [docs/research/foundational_audit_2026-06-02.md](docs/research/foundational_audit_2026-06-02.md) (round-1 evidence) + **[docs/research/foundational_audit_round2_2026-06-02.md](docs/research/foundational_audit_round2_2026-06-02.md) (round-2: measurement/training/Stage-B gaps the first sweep missed — the G-* findings driving the NEXT ACTIONS).**

**✅ RE-BASELINE DONE (2026-06-02, n=400):** iter_11 vs HeuristicMCTS on the NEW base-only bug-fixed game = **212W/5D/183L = 53.6% = +25.2 elo (±17.4, ~1.45σ)** (`results.csv: ladder_iter11_vs_heuristic_baseonly_n400`). **COLLAPSED from the old-game +181.7 elo** — iter_11's apparent dominance was largely game-artifact (River + buggy farm scoring + off-distribution, since it trained on the old game). **On the real game the learned policy adds ~nothing over the v2.7 leaf.** This is the cleanest possible motivation for Stage B: the learned components must be REBUILT on the real game, and the question is whether value-head-in-loop can push past the v2.7 ceiling. iter_11 is NOT a meaningful champion anymore — it's ≈ the heuristic.

**The reframe (2026-06-02 foundational audit — `docs/research/foundational_audit_2026-06-02.md`):** 6 weeks of leaf-tuning treated a symptom. The learned value can't beat the v2.7 heuristic because it was (1) **never in the search loop** (prod self-play passes `--leaf-eval v2_5` → the net value never drives a move; F-B1 confirmed in `run_pathb_cluster_loop.sh`), (2) taught by a **clairvoyant teacher**, (3) on a **corrupted reward** (farm double-count) + **corrupted policy targets** (MCTS transposition), (4) through a representation **blind to farm connectivity + the bag**, (5) on un-augmented saturated-target (`tanh(diff/15)`) data, (6) in a loop whose gate is **advisory**. **Clairvoyance is NOT a strength lever** (n=76 screen, 0.474 = dead even) → the exact-chance-node rebuild is demoted.

**✅ Phase 0 complete (committed + pushed, verified without retrain):**
- **C1 farm double-count** — `count_farm_points` dedups touched cities by `frozenset(city_positions)`; `City` got `__eq__/__hash__`. `scripts/verify_farm_dedup_fix.py` (n=150, 876 farms): fixed == independent correct ref on ALL; 16.3% over-scored pre-fix (audit ~17%), 633 spurious pts removed.
- **C2 MCTS visit double-count** — `NeuralMCTS._deduped_children` (policy target + best_action) + `_link_child`/alias structure (PUCT selection); base `MCTS` selection LEFT unchanged (it's the reference ladder — changing it breaks comparability). `scripts/verify_mcts_transposition_fix.py`: collision-free vector, mass == unique-child sum.
- **RIVER DROPPED** — `Game` default `tile_sets=(BASE,)`, `DECK_NORM 85→72` (base deck = 72 tiles). Suite green (323 passed, 1 skip). Old river-trained checkpoints now off-distribution (expected — Stage B warmstarts from scratch).
- ⚠️ **Owed (do with the re-baseline, Stage A):** re-sweep v2.7 caps (C1 shifts scoring optima) + c_puct/FPU (C2 changed the visit distribution the old c-sweep tuned against).

**Stage-A progress (no-retrain, committed + pushed):** symmetry aug (C5) **COMPLETE end-to-end** — board/action/policy-vector rotation + dataset augment + streaming-loader flag `train_iter.py --augment-rotations` (default OFF, zero behavior change), 16 tests (`tests/test_symmetry_aug.py`); flip the flag at Stage B. Loop orchestrator version-controlled (`scripts/run_pathb_cluster_loop.sh`; the running copy stays in `~/` per the share chicken-egg). 3 boxes synced to HEAD via an offline git **bundle** (remotes have no github DNS — see DECISIONS 2026-06-02 + memory).

### NEXT ACTIONS — immediate sequence (updated 2026-06-02 eve)
0. ~~Rewrite big docs~~ ✅ · ~~code review iter-9~~ ✅ · ~~round-2 audit~~ ✅ · ~~eval-path + safe fixes~~ ✅
1. **Verdict ≈ done** (c_puct + cap FLAT, recorded in `results.csv verdict_*`; fpu04 finishing). **No production change** (c=3.0 + cap=12 stay). **The one open item: CONFIRM FPU at n=400 paired** — fpu02 screened +45 elo/z=1.85 (under 2σ). If fpu04 also leans positive, run an n=400 paired FPU cell (work-stealing) and promote `fpu_reduction` to the production NeuralMCTS config if it holds. FPU is also re-tuned at Stage B (G-S4), so this can fold into the Stage-B sweep.
2. **Stage-B-readiness batch (the round-2 G-* queue — do BEFORE Stage B, all in the round-2 doc):**
   - **G-S1** fix the `value_blend` ramp: it's only wired into the `v2_5` leaf path, so Stage B must ramp `CARCASSONNE_V25_VALUE_BLEND` (not `--leaf-eval nn`); add an iter-indexed blend SCHEDULE to the loop; fix the policy-only guard that reads the import-time `DEFAULT_CONFIG.value_blend` instead of the env-resolved one.
   - **G-S3** point the loop's keep-best gate at **HeuristicMCTS** (out-of-lineage), not in-lineage iter_11; wire `warm_from=best_ckpt` (C7).
   - **G-T2** wire `--value-loss-weight` (sweep 1–5×) + **G-T1** `--lr-schedule cosine` into the loop (value head is gradient-starved ~5–10× unweighted).
   - **G-S2** regenerate the base-only bug-fixed warmstart corpus (all on-disk warmstart data is April River-era) — gated on the final cap; multi-hour, needs box+ETA.
   - **High-sim HeuristicMCTS reference rung** (Joshua's pick for the measurement wall) — an above-amateur yardstick so Stage B/C verdicts mean something. Also add `--paired` to `eval_net_vs_heuristic.py` for the ladder.
3. **Pre-Stage-B code-review swarm** — NARROW, scoped to the Stage-B wiring diff only (not another full-foundation sweep), + a "will Stage B fail for a non-science reason?" critic. Then launch.

### THEN — staged B→C (Joshua-approved; NOT "one batched retrain")
- **Stage B — the cheap root-cause retrain (one question):** does the value head IN the search loop (C3, the F-B1 root cause) beat the v2.7 ceiling with NO new planes? `--leaf-eval nn` (or `value_blend` ramp) + de-saturated target (C6) + conditional gate (C7) + exploration (C8) + symmetry aug ON (`--augment-rotations`). Short loop, base-only, from-scratch warmstart at current width. Evaluate on the INDEPENDENT HeuristicMCTS ladder at n=400. **Gate Stage C on it.**
- **Stage C — the expensive representation retrain (C4):** live farm-connectivity input planes + bag histogram + open-feature planes + farm scalars ON. Only if Stage B breaks upward. Fresh warmstart at the new input width.

---

## Reference (stable)

- **Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + **c_puct=3.0** + sims=200 default. All production workers run `nice -n 19`. ✅ **Post-Phase-0 re-sweep DONE (2026-06-02, paired n=400):** cap + c_puct both **FLAT** → unchanged. **FPU (`fpu_reduction`) the only knob showing signal** (+45 elo screen) — pending n=400 confirmation.
- **Active branch:** `gpu-orchestrator` (pushed to origin; not merged to `main`/`phase-4-selfplay`). Parked side branches (safe to ignore): `leaf-memoization` (3db30f1 — ~6% memo, not worth merge-risk), `play-vs-mcts` (04e4330 — stale UI, needs forward-port).
- **Cluster (W defaults, orchestrator self-play):** 5800x **W=14** · xeon (`ssh xeon`) **W=18** · laptop (`ssh laptop`) **W=24**. Per-box hardware + launch patterns in [CLAUDE.md](CLAUDE.md); bench-sweep throughput numbers in [DECISIONS.md](DECISIONS.md) 2026-06-01 (mixed-mode self-play = +87% cluster, locked).
- **Checkpoints:** **iter_11** (`/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt`) was +181.7 elo on the OLD River+buggy game but only **+25.2 elo (≈ the heuristic) on the new base-only bug-fixed game** (re-baseline 2026-06-02, n=400). It's no longer a meaningful champion — Stage B retrains from scratch on the real game. 12 screening ckpts in `pathb_loop/ckpt/`.

## Key contact files for a fresh thread
1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) + [docs/PHASE1_BUILD_SPEC_2026-06-02.md](docs/PHASE1_BUILD_SPEC_2026-06-02.md) — current path + concrete build
3. [docs/research/foundational_audit_2026-06-02.md](docs/research/foundational_audit_2026-06-02.md) — why the learned value can't beat v2.7 (the evidence)
4. [DECISIONS.md](DECISIONS.md) — every non-trivial decision + why; supersedes the original prompt
5. [experiments/results.csv](experiments/results.csv) — **source of truth for experiment numbers** (other docs cite it)
6. [EXPERIMENTS.md](EXPERIMENTS.md) — ablation roadmap narrative · [BACKLOG.md](BACKLOG.md) — deferred ideas · [REVIEW_LOG.md](REVIEW_LOG.md) — code-review F/D items · [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec (win-condition framing superseded)

## Hooks active
- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks; if elapsed >5min, instructs Claude to actively check status rather than idle. Registered in `~/.claude/settings.json`.

## History
All prior "Right now" states + the pre-audit narrative (leaf gate MIXED → luck-adjusted SOFT-NO, anchor-fraction ladder-null / verdict arc, value-as-leaf calibration cliff, the bench sweep, Path B Steps 6–8 that produced iter_11, the 2026-05-28 goal→superhuman regroup, and earlier) are recorded as dated entries in [DECISIONS.md](DECISIONS.md) and git log. Not duplicated here.
