# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-06-02 eve) — 🟢 PHASE 0 + RE-BASELINE + DOCS + CODE-REVIEW(iter-9) + ROUND-2 AUDIT + EVAL-PATH FIXES all done. 🔵 STAGE A2 n=400 PAIRED VERDICT RUNNING.

**🔵 IN FLIGHT (Stage A2 verdict, launched 16:22, ETA done ~23:00–23:30):** n=400 **PAIRED** head-to-head, iter_11 both sides, confirming the wave-1 screens on a clean baseline. Launcher `~/sweep_stageA_verdict.sh` (tracked `scripts/sweep_stageA_verdict.sh`), launcher PID was 900752, watcher task `b7dejx0a4`, out `/mnt/c/carc-shared/verdictA/<cell>/eval/iter_NN_vs_MM/`, logs `/tmp/verdictA*.log`. **To resume post-compact:** `kill -0 <pid>`/`pgrep -f sweep_stageA_verdict`; tally each cell dir for `s*.json` (n=400 or 200); read `grep VERDICT /tmp/verdictA.log`.
- **Verdicts so far (clean, paired, se≈2.5pp):** `self_c3` **49.5%** (z=−0.20) → **deck-pairing fix VALIDATED** (unpaired wave-1 self-cell was 42% = harness bias, now gone). `c15` (c=1.5) **+15.6 elo** (z=0.90, n.s.). `c20` (c=2.0) **−17.4 elo** (z=−1.0) → **the n=100 "+18pp c=2.0" screen was NOISE** (textbook lone-spike-is-noise). **Read: c_puct FLAT across 1.5–3.0; production c=3.0 STAYS.** Cap also flat (wave-1: cap=8/16 ≈ cap=12) → **cap=12 STAYS.**
- **Pending:** `c25` (c=2.5, running) + `fpu02`/`fpu04` (FPU 0.2/0.4 vs legacy, n=200 screens). Expect c25 flat; FPU is the only open question (and it's re-tuned at Stage B anyway — G-S4).

**✅ Eval-path fixes shipped (f2a64b7, synced to all 3 boxes):** **G-M2** `eval_iter_head_to_head --paired` (each deck both colors → cancels first-player advantage, ~halves variance). **G-M6** default `--seed-start`→1e9 (no self-play collision). **F-D-FPU** `NeuralMCTS(fpu_reduction=)` + per-side `--new-fpu/--old-fpu` (default None=legacy q=0). 342 tests pass.
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
1. **Finish the verdict run** (c25 + fpu02/fpu04, ~done 23:00–23:30). Record cap/c_puct/FPU verdicts → `results.csv` with manifests. Likely outcome: **no production change** (cap=12 + c=3.0 both stay; c_puct flat). Only FPU is open.
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

- **Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + **c_puct=3.0** (eval-validated) + sims=200 default. All production workers run `nice -n 19`. ⚠️ caps + c_puct **owed a re-sweep** post-Phase-0 (C1/C2 moved their optima).
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
