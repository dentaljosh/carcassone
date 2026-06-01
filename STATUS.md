# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-05-31, eve) — 🟢 boxes FREE, nothing running

**Strongest checkpoint = iter_11 (absolute-strength-confirmed).** Bench-sweep metric is fixed and 3-box-smoke-passed; the full sweep is launch-ready and **HELD for Joshua's go**.

### What we know (recorded in DECISIONS.md 2026-05-31)
- **iter_11 is the confirmed-strongest checkpoint — first trustworthy ABSOLUTE-strength signal.** Ladder gauntlet vs **HeuristicMCTS** (a strong NON-saturated reference: v2.7 leaf + UCT, no learned policy) at matched sims=200/c=3: **n=400 → 293W/6D/101L = 74.0%, +181.7 elo / 9.2σ.** The learned policy beats strong heuristic-search at equal compute → the +190 self-anchored gain was real strength. Clears ladder rung 1; **NOT yet superhuman** (HeuristicMCTS ≈ strong-amateur). `results.csv: ladder_iter11_vs_heuristic_n400`.
- **Value-as-leaf is CLOSED (calibration cliff).** Pure NN-value leaf −800; graceful only at λ≤0.1. Ceiling-probe (n=400): even λ=0.1 hurts (iter_01 −27.9 / iter_11 −35.7 elo) and a *better*-calibrated head hurts *more* → the v2.7 leaf ceiling is NOT liftable by value-head blending. Lifting it needs a genuinely stronger **learned** signal (what anchor-fraction self-play is meant to produce). **Don't switch the production leaf.**

### Bench sweep — metric FIXED + 3-box smoke PASSED; full sweep HELD
Per-box per-lever throughput+telemetry sweep (`scripts/bench_pipeline_sweep.py`; 3-box launcher `/home/doctor/run_bench_sweep.sh`). **Was broken** (counted completed GAMES per 240s window, but one sims=200 game takes ~300-400s → ~0 g/min/cell). **Fixed (commit 338d4b9):** harness parses `selfplay.py`'s env-gated `BENCHTP pid=… t=… moves=<cum>` lines (emitted ~every 3s/worker under `CARC_BENCH_TP`, zero-cost off), tracks each pid's monotonic count and **deltas the sum across the window** → moves/sec. Parser unit-tested + **validated on REAL output on all 3 boxes**: 5800x W=14 → **8.35 mv/s** (gpu 35W/25%, cpu 40%), xeon W=18 → **6.09** (51W/36%, cpu 40%), laptop W=24 → **9.5** (27W/65%, cpu 16%); all `status=ok`, 15 telemetry samples each. (Smoke window is short → all read `ipc_latency`; the production 240s window on the 5800x read `cpu_bound` — the v2.7 CPU leaf is the limiter, GPU only 35-70W of 180.) **Launcher bug also fixed:** `run_bench_sweep.sh` now syncs `selfplay.py` (the emitter) to the remote boxes alongside the harness — before, a fresh/re-synced box would silently read 0 mv/s. Levers known-marginal from BACKLOG/DECISIONS (do NOT re-chase blind): fp16 (slower on 3 GPU gens), orch-shards (GIL only bites at W≈48), batch_timeout (dispatch-bound), production already `--batch-size 8`.

### NEXT (boxes are free)
1. **Bench sweep** (held): `nohup nice -n 19 bash /home/doctor/run_bench_sweep.sh > /tmp/bench_sweep.log 2>&1 & disown` — each box runs its own full matrix → `bench/sweep_<box>.csv` + `samples_<box>.csv`; ~1h wall parallel; merge after. OR decide the W=14/18/24 + cpu_bound datapoint is enough and skip.
2. **Wire the 3-box anchor-fraction self-play launcher** (the strength push — extend iter_11). Pre-launch review loop CONVERGED (REVIEW_LOG iters 5-8). **Corrected config:** all-12-scalar, warm-from **and** anchor = **iter_11** (NOT iter_B1/deepsearch), sims=200 first (escalate to 800 only if it gates positive), gate each iter vs iter_11 (fixed ref) + stop-after-2-flat, `anchor_fraction=0.3`. Base = `run_pathb_cluster_loop.sh` (set `WARM=iter_11`, add anchor flags + stop-after-2-flat) + a 4-game smoke. **Ask which box(es) before launching.**
3. **Joshua plays iter_11** @ sims=800 anytime: `python scripts/play_vs_net.py --checkpoint /mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt --sims 800 --human 0`.

### Killed/paused
The extended self-play loop (driver 29976) was KILLED during the pivot to free boxes — iter_12 has ~429 banked seeds in `pathb_loop/iter_12/` if we resume (`START=12 ITERS=24`). 12 screening checkpoints safe in `pathb_loop/ckpt/`.

### Open gaps (if we return to scaling)
Loop gates only vs WARM (no marginal-strength read → gate vs running-best + plateau-stop); post-speedup self-play is GPU/eval-bound (multi-shard eval-server is the throughput lever); the leaf ceiling + an external/absolute reference (Joshua → pros) still gate true superhuman.

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
