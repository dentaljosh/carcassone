# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-06-02) — 🔴 FOUNDATIONAL AUDIT done; the leaf was a symptom. Correction plan written → fix 2 live bugs, then ONE batched retrain. **NEXT ACTION: Phase-0 bug fixes (C1, C2).**

**READ FIRST:** [docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) (the path forward) + [docs/research/foundational_audit_2026-06-02.md](docs/research/foundational_audit_2026-06-02.md) (the evidence). These supersede the old leaf/afterstate/pivot plan.

**The reframe:** 6 weeks of leaf-tuning treated a symptom. A 6-agent audit found why the learned value can't beat the v2.7 heuristic: it was (1) **never in the search loop** (prod uses the v2.7 leaf; the net value is a side-regression that never drives a move), (2) taught by a **clairvoyant teacher**, (3) on a **corrupted reward** (farm scoring double-counts cities — `count_farm_points` sets `City` objects with no `__eq__/__hash__` → identity dedup → ~17% of farms over-scored, up to +69pts, asymmetric) and **corrupted policy targets** (MCTS keys children by action → rotationally-symmetric tiles share a node → ~20% of nodes double-count visits), (4) through a representation **blind to farm connectivity AND bag composition**, (5) on un-augmented, saturated-target (`tanh(diff/15)`) data, (6) in a loop whose gate is **advisory** (never rejects a regressing iter → chain random-walks). The v2.7 leaf masked all six at strong-amateur.

**Clairvoyance is NOT a strength lever** (screen n=76, iter_11, sims=200/c=3: clairvoyant vs fair = 36W/40L = 0.474, −0.5σ = dead even). Good news: our +180 numbers are NOT future-sight-inflated (validity intact). Consequence: the exact-chance-node rebuild is **demoted** — the chance gap bites VALUE-LEARNING (single-future high-variance targets), not search strength. `scripts/diag_clairvoyance.py` + `NeuralMCTS(fair_chance=…)` built (commit e88d82b).

### NEXT ACTIONS (from the correction plan; bugs first, no retrain to verify)
1. **C1 — farm scoring double-count** (`engine/.../points_collector.py:284-299` + City `__eq__/__hash__`). Verify: farm-discrepancy check → 0 mismatches. Then RE-SWEEP v2.7 caps (scoring fix shifts optima).
2. **C2 — MCTS transposition visit double-count** (`src/carcassonne_ai/mcts.py`; edge/node split or dedup same-child actions in the visit distribution). Verify: collision check. Then re-sweep c_puct/FPU.
3. **Then ONE batched retrain** (Phase 1): value head in the loop (`leaf_eval=nn`/deep-search targets) + representation planes (farm connectivity + bag histogram + open-feature progress; turn on farm scalars) + **DROP RIVER** (Joshua confirm — C4 forces a retrain anyway, the moment to do it) + symmetry aug + de-saturated value target + conditional gate + exploration A/B. Evaluate on the INDEPENDENT HeuristicMCTS ladder at n=400.

### Superseded this session (kept for context, detail in git log / docs)
- **Leaf gate** (sims=800, n=40, commit 870b08d) = MIXED, then **luck-adjusted re-gate** (`--with-luck`, commit 7e7ebf1, n=40) = SOFT NO on the learned-residual leaf (adjusted margin +0.012, shrank under de-noising). Draw-luck control variate works as a measurement tool (×1.21, modest, keep). Both now subsumed by the audit: the residual idea was one symptom-fix among six root causes.
- Anchor-fraction push = ladder-confirmed null (the +39 was anchor-overfitting; see verdict arc below).

**The verdict arc (all in `results.csv`):**
- `anchor_iter4_vs_iter11_n400` (c=1.5): iter_4 vs iter_11 = 55.6% = +39.3 elo / 2.25σ. **Looked like a real gain — it was NOT (see ladder).**
- `ladder_iter4_vs_heuristic_n400` (c=3.0): iter_4 vs HeuristicMCTS = 72.1% = **+165.1 elo** vs iter_11's **+181.7** → diff −16.6 ±27.7 = **0.6σ = TIED** (iter_4 nominally *lower*). **On the absolute anchor at production c=3.0, iter_4 is NOT stronger than iter_11.**
- **Reconciliation:** the +39 head-to-head was **anchor-overfitting** (iter_4 trained 30% vs iter_11 → learned to beat *it specifically*, not generally) ± a c=1.5 artifact. **`anchor_before_scaling` in the flesh: relative-vs-lineage-anchor ≠ absolute strength.** The ladder (independent reference) caught a false positive the head-to-head shipped.
- Supporting: iter_6 ≈ iter_4 (49.1%), iter_0 ≈ iter_5 (floor check) — chain bounces, no monotonic gain. Pipeline healthy (val-corr 0.18→0.81) but it doesn't convert to absolute play strength = **the v2.7 leaf ceiling, intact**.
- **Lessons logged:** (1) n=40 gates are screens not verdicts (swings 37.5–68.8% hid the truth); (2) **always anchor against an INDEPENDENT reference, not a same-lineage one** — head-to-head vs iter_11 overfits.

**The verdict arc (anchor-fraction null) — full detail in `results.csv` + DECISIONS 2026-06-01:** `anchor_iter4_vs_iter11_n400` (c=1.5) = 55.6%/+39 looked real; `ladder_iter4_vs_heuristic_n400` (c=3.0) = +165.1 vs iter_11's +181.7 = 0.6σ TIED → the +39 was anchor-overfitting (`anchor_before_scaling`: relative-vs-lineage-anchor ≠ absolute). Leaf ceiling intact.

### What we know (recorded in DECISIONS.md 2026-05-31)
- **iter_11 is the confirmed-strongest checkpoint — first trustworthy ABSOLUTE-strength signal.** Ladder gauntlet vs **HeuristicMCTS** (a strong NON-saturated reference: v2.7 leaf + UCT, no learned policy) at matched sims=200/c=3: **n=400 → 293W/6D/101L = 74.0%, +181.7 elo / 9.2σ.** The learned policy beats strong heuristic-search at equal compute → the +190 self-anchored gain was real strength. Clears ladder rung 1; **NOT yet superhuman** (HeuristicMCTS ≈ strong-amateur). `results.csv: ladder_iter11_vs_heuristic_n400`.
- **Value-as-leaf is CLOSED (calibration cliff).** Pure NN-value leaf −800; graceful only at λ≤0.1. Ceiling-probe (n=400): even λ=0.1 hurts (iter_01 −27.9 / iter_11 −35.7 elo) and a *better*-calibrated head hurts *more* → the v2.7 leaf ceiling is NOT liftable by value-head blending. Lifting it needs a genuinely stronger **learned** signal (what anchor-fraction self-play is meant to produce). **Don't switch the production leaf.**

### Bench sweep — DONE + CONFIRMED (3-rep verdict); mixed-mode self-play locked (+87% cluster)
Per-box per-lever throughput+telemetry sweep + 3-rep confirm + deploy pass. **Full record + all numbers: [DECISIONS.md](DECISIONS.md) 2026-06-01.** Data: `/mnt/c/carc-shared/bench/sweep_*.csv` (+ `sweep_confirm_*` / `sweep_deploy_*`). Headline: the orchestrator's **single GIL-bound dispatch thread is the limiter** for the CPU v2.7 leaf (GPU idle 28W) → **W is flat; orchestrator OFF wins where VRAM fits.** Per-box self-play optimum (3-rep, CV ≤2%): **5800x orch-off W=16 (no fp16) = 14.70 mv/s (+99%) · xeon orch_shards=2 = 6.99 (+30%) · laptop orch-off W=10 = 19.26 (+110%)** → cluster 21.9→41.0 = **+87%**. fp16 is **batch-conditional** (helps under orchestrator on Blackwell/Ada +24/31%, HURTS under orch-off −6%). Cloud-era doctrines **superseded**: the "W≈48 GIL" + "fp16 always slower" claims were vast.ai-48-core numbers. Harness now has `--repeats`, comma-`--only`, a `deploy` cell, and `--mode eval` (Phase-3 eval W-sweep — done, see DECISIONS addendum). **NOT yet wired into the loop — gated on a Pass-3 strength/correctness check** that orch-off (per-worker prior-batching) is strength-neutral.

### NEXT — gated on the LEAF GATE result (see "IN FLIGHT" above)
**Leaf research is DONE** (5-agent sweep, committed): `docs/research/leaf_eval_research_2026-06-01.md`. Convergent finding: the lever is **afterstate value + EXACT chance nodes** (our known tile bag → exact weighted expectimax, better-positioned than backgammon/MuZero). Cheap-first ladder, each rung early-abandon-gated.

1. **When the leaf gate lands** (IN FLIGHT #2): if **green** → build the **learned-residual leaf** (`leaf = v2.7 + ε·tanh(residual)`, residual trained on `V_deepsearch − v2.7` from the sims=800 deepsearch teacher — NOT outcomes; sidesteps the calibration cliff). The NNUE precedent says the *training target* is load-bearing. If **null** → deep search doesn't correct v2.7; pivot to the afterstate/chance-node route (rung 2 below) or reconsider appetite (strong-amateur may be the practical ceiling).
2. **The full leaf ladder (cheap-signal-first)** from the research doc: (a) **draw-luck control variate** for MEASUREMENT (bag known → exact; turns n=100 into near-verdicts — fixes our chronic gate noise, independent of the leaf); (b) **exact chance-node expectation around the v2.7 leaf** (no training — does putting the draw-expectation in the tree help win-rate?); (c) **afterstate value targets**; (d) **learned-residual leaf** (gated by #1). Each: implement → re-tune caps/weights → measure vs v2.7 at **n=400**.
3. **Honest ceiling:** a residual trained on deep-search-over-v2.7 is bounded by v2.7's worldview — likely clears strong-human, probably not superhuman alone (needs the NNUE-style bootstrap flywheel). This is the research frontier the prompt scoped out; appetite/ROI is a real open question.
4. **If revisiting self-play:** anchor vs an INDEPENDENT/diverse opponent set (population/league), NOT same-lineage (iter_11 overfit). Lower priority than the leaf.
5. **Joshua plays iter_4 ≈ iter_11** @ sims=800: `python scripts/play_vs_net.py --checkpoint /mnt/c/carc-shared/pathb_anchor/ckpt/iter_04.pt --sims 800 --human 0`.

### Tooling built this session (all committed unless noted)
- `scripts/diag_leaf_gate.py` (870b08d) — the leaf gate; `scripts/parse_iter_timings.py` + `experiments/iter_timings.csv` — per-iter wall-clock/gate/corr recorder.
- `run_pathb_cluster_loop.sh` (untracked ~/, in `code_sync/`) — strength loop, now with: mixed-mode self-play, anchor-fraction, **confirm-before-kill** (n=400 verify before a plateau-stop), **VERIFY one-shot mode** (head-to-head gates on existing ckpts, env `VERIFY=`/`VCPUCT=`/`VSENT0=`), iter-timing.
- `run_leaf_gate.sh` (untracked ~/, in `code_sync/`) — the chained leaf-gate auto-launcher (IN FLIGHT #2).

### Killed/paused
The extended self-play loop (driver 29976) was KILLED during the pivot to free boxes — iter_12 has ~429 banked seeds in `pathb_loop/iter_12/` if we resume (`START=12 ITERS=24`). 12 screening checkpoints safe in `pathb_loop/ckpt/`.

### Open gaps (if we return to scaling)
Loop now gates vs the fixed iter_11 ref with a plateau-stop + **confirm-before-kill** (n=400 latest-vs-best before stopping) — still n=40 per-iter screens so individual gates are noisy by design; self-play throughput lever is **orch-off (not the multi-shard eval-server)** for the CPU v2.7 leaf — the orchestrator's GIL-bound dispatcher was the limiter, now bypassed (DECISIONS 2026-06-01); the leaf ceiling + an external/absolute reference (Joshua → pros) still gate true superhuman.

---

## Reference (stable)

- **Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + **c_puct=3.0** (eval-side validated; self-play-side is hypothesis-only — DECISIONS 2026-05-28) + sims=200 default. All production workers run `nice -n 19`.
- **Active branch:** `gpu-orchestrator` (not merged to `main`/`phase-4-selfplay`). Unmerged side branches (no worktrees): `leaf-memoization` (3db30f1 — parked find_city/road memo, ~6%, not worth merge-risk) and `play-vs-mcts` (04e4330 — stale play UI, needs a forward-port).
- **Cluster (W defaults, orchestrator self-play):** 5800x **W=14** · xeon (`ssh xeon`) **W=18** · laptop (`ssh laptop`) **W=24**. Full per-box hardware + launch-pattern detail in [CLAUDE.md](CLAUDE.md); live throughput numbers come from the bench sweep above.
- **Checkpoints:** strongest = **iter_11** (`/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt`); 12 screening ckpts in `pathb_loop/ckpt/`. Bridge infra (`remote_eval_bridge.py` + `remote_socket_handles.py` + `--serve-on`/`--remote-eval-server`) stays committed but unused (Zenbook called a dead-end 2026-05-21).

## Key contact files for a fresh thread
1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec (win-condition framing superseded — see CLAUDE.md)
3. [DECISIONS.md](DECISIONS.md) — every non-trivial decision + why; supersedes the original prompt
4. [EXPERIMENTS.md](EXPERIMENTS.md) — open ablation roadmap + findings ledger
5. [BACKLOG.md](BACKLOG.md) — deferred ideas (don't action without Joshua's OK)
6. [REVIEW_LOG.md](REVIEW_LOG.md) — code-review fixes (F-numbers) + deferred items (D-numbers)

## Hooks active
- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks; if elapsed >5min, instructs Claude to actively check status rather than idle. Registered in `~/.claude/settings.json`.

## History
All prior "Right now" states — **2026-05-29** (Path B Steps 6-8, the Shabbos 3-box screening run that produced iter_11), **2026-05-28** (strategic regroup; goal → superhuman; Optuna eval-search), **2026-05-20** (retroactive-validation pipeline; iter_B1 recovered), **2026-05-18** (Option-2 closed; sims-ladder +200 elo), and earlier — are recorded as dated entries in [DECISIONS.md](DECISIONS.md) and in git log. Not duplicated here.
