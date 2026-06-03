# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-06-03 overnight) — 🟢 PHASE 0 + RE-BASELINE + ROUND-2 AUDIT + EVAL-PATH + WORK-STEALING + DASHBOARD + HOOKS + STAGE-A2 VERDICT + STAGE-B WIRING (branch) + TEST-GAP CLOSE all done. 🔵 high-sim ladder running. ⏭ NEXT = Joshua.

**⏭ NEXT — Stage B DECISIONS 1+2 LOCKED (Joshua, 2026-06-03):** (1) **success bar = ≥25 elo over iter_11 @ n=400 paired** (~1.5σ, the min that isn't noise); (2) **blend curve = `0,0,0.15,0.30,0.50,0.70,1.0`** (already what `blend_for_iter()` codes). Remaining pre-launch: train `warm.pt` from the corpus (~15 min), **Xeon OOM smoke** (blend>0 full-forward on 8GB), wire **G-S3** (gate→HeuristicMCTS + warm_from=best — **gate DESIGN still open, the last decision**). Full package + launch command: **`docs/STAGE_B_LAUNCH_READINESS.md`**.

**✅ STAGE-B WIRING DONE — branch `stage-b-wiring`** (off `gpu-orchestrator`@e595d6c; code-reviewed **"correct + safe to launch"**; merge is Joshua's call). Closes the F-B1 root cause (the learned value was never in the search loop):
- **G-S1** — `--value-blend` puts the NN value into the leaf `(1-λ)·v2.7 + λ·v_nn`; `blend_for_iter()` ramp in the loop, **DEFAULT OFF** (`STAGE_B_BLEND=1` enables; curve is a PROPOSAL). Smoke-verified blend changes the search; anchor stays blend=0 (pure v2.7). Commits **7fa696d** + **b2ba341** (anchor) + **bfbd47d** (review fix: anchor orch server always policy_only). Plan: `docs/STAGE_B_G-S1_PLAN_2026-06-03.md`.
- **G-T1/T2** — `LR_SCHEDULE`/`VALUE_LOSS_WEIGHT` env knobs into the loop train step (defaults = current behavior; Stage B sets cosine / ~3). Commit **8965852**.

**✅ TEST-GAP CLOSE (be46466) — top 3 regression holes now gate CI** (were script-only / absent): `tests/test_farm_dedup_c1.py` (C1 farm double-count), `test_mcts_transposition_c2.py` (C2 visit dedup), `test_value_in_loop_fb1.py` (F-B1: value_blend steers the search — guards the wiring). All pass w/ teeth-assertions. Gap analysis: `docs/TEST_SUITE_GAP_ANALYSIS_2026-06-03.md` (#4 cross-proc determinism + #5 tied-scoring still open).

**✅ DONE — high-sim reference rung (ladder), recorded:** iter_11 vs HeuristicMCTS @ **sims=800**, clean base-only game, n=1143 (3-box disjoint shards). **+56.7 elo ± 10.4 (5.5σ)** — 652W/24D/467L = 58.1%. `results.csv: ladder_iter11_vs_heuristic_baseonly_s800_n1143`. **KEY FINDING:** the SAME matchup at sims=200 was only +25.2/1.45σ (inconclusive) — so the **learned policy's edge over raw heuristic search GROWS with depth** (25→57 elo as sims 200→800). Refutes the pessimistic "iter_11 ≈ heuristic" read — that was sims=200-only; the policy is real strength that needs depth. (net = priors + v2.7 leaf value; the net VALUE head is still NOT in the loop — that's exactly what Stage B adds.)

**✅ Warmstart corpus (G-S2) DONE:** `data/warmstart/baseonly_v27cap12/` **300K** positions (base-only bug-fixed, 1ply heuristic, 12-scalar, cap=12). The Stage-B starting net (`warm.pt`) is NOT yet trained from it — that's a ~15-min pre-launch step (deliberately not run overnight to avoid GPU-contending the ladder).

**✅ FAILURE-MODE HOOKS LIVE (390b482):** `scripts/hooks/{pretooluse_lint,posttooluse_log}.py`, registered project-scoped in `.claude/settings.local.json` (gitignored; see `scripts/hooks/README.md`). PreToolUse blocks foreground `sleep≥10s` + CIFS mount-path mismatch (N1); PostToolUse logs failures → `.claude/tool_failures.jsonl`. Built from the 2026-06-02 transcript audit (BACKLOG entry).

**✅ STAGE A2 VERDICT DONE (paired n=400/200, work-stealing 3-box; `sweep_verdict_steal.sh`).** c_puct + cap FLAT (no prod change); FPU the one positive lever (both screens, confirm pending). Cluster idle except heartbeats + dashboard. Full numbers below + in `results.csv verdict_*`.
- **VERDICT — c_puct + cap are FLAT (paired n=400, se≈2.5pp):** `self_c3` **49.5%** (z=−0.20) → deck-pairing VALIDATED (unpaired self-cell was 42% harness bias, gone). `c15` **+15.6** (z=0.90 n.s.), `c20` **−17.4** (z=−1.0 n.s. — REVERSES the n=100 "+18pp c=2.0" screen = noise), `c25` **−15.6** (z=−0.90 n.s.). **→ c_puct flat across 1.5–3.0; production c=3.0 + cap=12 STAY.** Rows in `results.csv` (`verdict_*`).
- **FPU is the ONE live lever (sweep COMPLETE):** `fpu02` (reduction 0.2) = **+45.4 elo / z=+1.85**, `fpu04` (0.4) = **+31.4 elo / z=+1.28** — both positive vs legacy q=0, same direction. Neither clears 2σ alone, but **two independent positive cells corroborate** → FPU is a real modest lever (the only non-flat thing in the verdict). 0.2 screens slightly > 0.4 (within noise). **Still a SCREEN, not a verdict** → CONFIRM the better value at **n=400 paired** (or fold into the Stage-B G-S4 FPU sweep) before promoting `fpu_reduction` to the production NeuralMCTS config. Rows: `results.csv verdict_fpu0{2,4}_*`.

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

### NEXT ACTIONS — immediate sequence (updated 2026-06-03 overnight)
DONE this session: ~~verdict~~ ✅ (c_puct+cap FLAT, no prod change; FPU the lever) · ~~work-stealing default~~ ✅ · ~~dashboard~~ ✅ · ~~failure-mode hooks~~ ✅ · ~~G-S2 warmstart corpus (300K)~~ ✅ · ~~G-S1 value_blend wiring + anchor~~ ✅ · ~~G-T1/T2 knobs into loop~~ ✅ · ~~pre-Stage-B code review~~ ✅ ("safe to launch", 1 fix applied) · ~~test-gap close (C1/C2/F-B1)~~ ✅ — **all on branch `stage-b-wiring`**.
1. **Record the ladder elo verdict → `results.csv`** when the run finishes (watcher `b31dw5g1c`; tally via `--summary-only --seed-start 800000`). This calibrates the high-sim reference rung (where iter_11 sits vs HeuristicMCTS@800).
2. **⏭ NEEDS JOSHUA before Stage-B launch** (see `docs/STAGE_B_LAUNCH_READINESS.md`):
   - (a) pre-register the **success bar** (suggest ≥25 elo over iter_11 @ n=400 paired);
   - (b) pick the **blend ramp curve** (`blend_for_iter()` proposal: 0→0.15→0.30→0.50→0.70→1.0).
3. **Then the cheap pre-launch steps:** train `warm.pt` from `data/warmstart/baseonly_v27cap12/` (~15 min); **Xeon OOM smoke** (blend>0 full-forward on 8GB, W=18 sims=200, watch CUDA VRAM); wire **G-S3** (gate→HeuristicMCTS out-of-lineage + `warm_from=best_ckpt`, C7 — left for Joshua, gate-design judgment); merge `stage-b-wiring`; launch `STAGE_B_BLEND=1 VALUE_LOSS_WEIGHT=3 LR_SCHEDULE=cosine bash ~/run_pathb_cluster_loop.sh`.
4. **Optional:** confirm FPU at n=400 paired (or fold into the Stage-B G-S4 sweep — leaning fold); add test gaps #4 (cross-proc determinism) + #5 (tied-scoring).

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
