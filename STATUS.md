# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-06-02) — 🟢 PHASE 0 DONE + RIVER DROPPED + SYMMETRY-AUG built. 🔵 RE-BASELINE RUNNING. Plan staged A→B→C.

**READ FIRST:** [docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) (the path forward) + [docs/PHASE1_BUILD_SPEC_2026-06-02.md](docs/PHASE1_BUILD_SPEC_2026-06-02.md) (the concrete build) + [docs/research/foundational_audit_2026-06-02.md](docs/research/foundational_audit_2026-06-02.md) (the evidence). These SUPERSEDE the old leaf-gate / afterstate / residual-leaf / anchor-fraction plan (now history in DECISIONS + git).

**🔵 IN FLIGHT — re-baseline:** n=400 of iter_11 (NeuralMCTS) vs HeuristicMCTS on the NEW base-only bug-fixed game, 3-box (`/home/doctor/run_rebaseline.sh` → `/mnt/c/carc-shared/rebaseline/iter_11_s200_h200_c30`; live summary `/tmp/rebaseline.log`). n=8 smoke = 3W/5L = 0.375 (screen only — do not bank). ⚠️ The pre-2026-06-02 **"+181.7 elo / 74% vs HeuristicMCTS"** was measured on the OLD River+buggy game — being re-measured now. iter_11 may NOT be champion on the real game (expected after the foundation fixes; it trained on the old game). Verdict → `experiments/results.csv` when it lands.

**The reframe (2026-06-02 foundational audit — `docs/research/foundational_audit_2026-06-02.md`):** 6 weeks of leaf-tuning treated a symptom. The learned value can't beat the v2.7 heuristic because it was (1) **never in the search loop** (prod self-play passes `--leaf-eval v2_5` → the net value never drives a move; F-B1 confirmed in `run_pathb_cluster_loop.sh`), (2) taught by a **clairvoyant teacher**, (3) on a **corrupted reward** (farm double-count) + **corrupted policy targets** (MCTS transposition), (4) through a representation **blind to farm connectivity + the bag**, (5) on un-augmented saturated-target (`tanh(diff/15)`) data, (6) in a loop whose gate is **advisory**. **Clairvoyance is NOT a strength lever** (n=76 screen, 0.474 = dead even) → the exact-chance-node rebuild is demoted.

**✅ Phase 0 complete (committed + pushed, verified without retrain):**
- **C1 farm double-count** — `count_farm_points` dedups touched cities by `frozenset(city_positions)`; `City` got `__eq__/__hash__`. `scripts/verify_farm_dedup_fix.py` (n=150, 876 farms): fixed == independent correct ref on ALL; 16.3% over-scored pre-fix (audit ~17%), 633 spurious pts removed.
- **C2 MCTS visit double-count** — `NeuralMCTS._deduped_children` (policy target + best_action) + `_link_child`/alias structure (PUCT selection); base `MCTS` selection LEFT unchanged (it's the reference ladder — changing it breaks comparability). `scripts/verify_mcts_transposition_fix.py`: collision-free vector, mass == unique-child sum.
- **RIVER DROPPED** — `Game` default `tile_sets=(BASE,)`, `DECK_NORM 85→72` (base deck = 72 tiles). Suite green (323 passed, 1 skip). Old river-trained checkpoints now off-distribution (expected — Stage B warmstarts from scratch).
- ⚠️ **Owed (do with the re-baseline, Stage A):** re-sweep v2.7 caps (C1 shifts scoring optima) + c_puct/FPU (C2 changed the visit distribution the old c-sweep tuned against).

**Stage-A progress (no-retrain, committed + pushed):** symmetry aug (C5) **COMPLETE end-to-end** — board/action/policy-vector rotation + dataset augment + streaming-loader flag `train_iter.py --augment-rotations` (default OFF, zero behavior change), 16 tests (`tests/test_symmetry_aug.py`); flip the flag at Stage B. Loop orchestrator version-controlled (`scripts/run_pathb_cluster_loop.sh`; the running copy stays in `~/` per the share chicken-egg). 3 boxes synced to HEAD via an offline git **bundle** (remotes have no github DNS — see DECISIONS 2026-06-02 + memory).

### NEXT ACTIONS — staged A→B→C (Joshua-approved; NOT "one batched retrain")
1. **Finish Stage A:** the re-baseline (in flight) → then re-sweep v2.7 caps + c_puct/FPU on the new game (eval runs; need box + ETA). Optional: de-saturated value-target mode (C6) + exploration knobs (C8) — but those are tested only when Stage B runs.
2. **Stage B — the cheap root-cause retrain (one question):** does the value head IN the search loop (C3, the F-B1 root cause) beat the v2.7 ceiling with NO new planes? `--leaf-eval nn` (or `value_blend` ramp) + de-saturated target + conditional gate (C7) + exploration (C8) + symmetry aug ON. Short loop, base-only, from-scratch warmstart at current width. Evaluate on the INDEPENDENT HeuristicMCTS ladder at n=400. **Gate Stage C on it.**
3. **Stage C — the expensive representation retrain (C4):** live farm-connectivity input planes + bag histogram + open-feature planes + farm scalars ON. Only if Stage B breaks upward. Fresh warmstart at the new input width.

---

## Reference (stable)

- **Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + **c_puct=3.0** (eval-validated) + sims=200 default. All production workers run `nice -n 19`. ⚠️ caps + c_puct **owed a re-sweep** post-Phase-0 (C1/C2 moved their optima).
- **Active branch:** `gpu-orchestrator` (pushed to origin; not merged to `main`/`phase-4-selfplay`). Parked side branches (safe to ignore): `leaf-memoization` (3db30f1 — ~6% memo, not worth merge-risk), `play-vs-mcts` (04e4330 — stale UI, needs forward-port).
- **Cluster (W defaults, orchestrator self-play):** 5800x **W=14** · xeon (`ssh xeon`) **W=18** · laptop (`ssh laptop`) **W=24**. Per-box hardware + launch patterns in [CLAUDE.md](CLAUDE.md); bench-sweep throughput numbers in [DECISIONS.md](DECISIONS.md) 2026-06-01 (mixed-mode self-play = +87% cluster, locked).
- **Checkpoints:** **iter_11** (`/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt`) was strongest on the OLD game (+181.7 elo) — **status on the new base-only game is being re-baselined** (likely no longer champion). 12 screening ckpts in `pathb_loop/ckpt/`.

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
