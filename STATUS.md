# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-06-01) — 🟢 strength-push loop LIVE (3 boxes, RUN=pathb_anchor, at iter 3)

**Strongest checkpoint = iter_11 (absolute-strength-confirmed).** The anchor-fraction strength push is RUNNING (`RUN=pathb_anchor`, warm=iter_11, anchor_fraction=0.3, all 3 boxes, +87% mixed-mode throughput). Resumed at `START=3` after a 5800x reboot (iter 0–2 done; iter-3 self-play had 486/600 banked, resumed cheap after clearing 43 orphan claims). Driver on 5800x, logs `/tmp/pathb_anchor.log`.

**Early trend: AMBIGUOUS, mildly encouraging — too noisy to call at n=40.** Gates vs iter_11 (n=40): **iter0 47.5% · iter1 55.0% · iter2 37.5% · iter3 58.8%** — high variance (1σ≈±8%), mean ~50%, but iters 1 & 3 are both >55% and **iter 3 is the new high**. Value↔outcome corr climbs **monotonically 0.18→0.58→0.67→0.75** (now well above heuristic 0.61) — the learned value head is clearly improving. NOT the clean-null the leaf-ceiling hypothesis predicted, but NOT a verdict-grade win either. **The loop continues (iter 3 set a new best → no plateau, iter 4 running).** Watch whether the gate holds >55% / keeps climbing (→ anchor-fraction working, then verify the best at n=400 + consider sims=800) or regresses into a plateau (→ confirm-before-kill at n=400 → leaf rework). Per-iter wall-clock now logged to `experiments/iter_timings.csv` (iters 0–2 ~58–63 min; train time rising as the replay buffer fills — 321K positions by iter 3).

### What we know (recorded in DECISIONS.md 2026-05-31)
- **iter_11 is the confirmed-strongest checkpoint — first trustworthy ABSOLUTE-strength signal.** Ladder gauntlet vs **HeuristicMCTS** (a strong NON-saturated reference: v2.7 leaf + UCT, no learned policy) at matched sims=200/c=3: **n=400 → 293W/6D/101L = 74.0%, +181.7 elo / 9.2σ.** The learned policy beats strong heuristic-search at equal compute → the +190 self-anchored gain was real strength. Clears ladder rung 1; **NOT yet superhuman** (HeuristicMCTS ≈ strong-amateur). `results.csv: ladder_iter11_vs_heuristic_n400`.
- **Value-as-leaf is CLOSED (calibration cliff).** Pure NN-value leaf −800; graceful only at λ≤0.1. Ceiling-probe (n=400): even λ=0.1 hurts (iter_01 −27.9 / iter_11 −35.7 elo) and a *better*-calibrated head hurts *more* → the v2.7 leaf ceiling is NOT liftable by value-head blending. Lifting it needs a genuinely stronger **learned** signal (what anchor-fraction self-play is meant to produce). **Don't switch the production leaf.**

### Bench sweep — DONE + CONFIRMED (3-rep verdict); mixed-mode self-play locked (+87% cluster)
Per-box per-lever throughput+telemetry sweep + 3-rep confirm + deploy pass. **Full record + all numbers: [DECISIONS.md](DECISIONS.md) 2026-06-01.** Data: `/mnt/c/carc-shared/bench/sweep_*.csv` (+ `sweep_confirm_*` / `sweep_deploy_*`). Headline: the orchestrator's **single GIL-bound dispatch thread is the limiter** for the CPU v2.7 leaf (GPU idle 28W) → **W is flat; orchestrator OFF wins where VRAM fits.** Per-box self-play optimum (3-rep, CV ≤2%): **5800x orch-off W=16 (no fp16) = 14.70 mv/s (+99%) · xeon orch_shards=2 = 6.99 (+30%) · laptop orch-off W=10 = 19.26 (+110%)** → cluster 21.9→41.0 = **+87%**. fp16 is **batch-conditional** (helps under orchestrator on Blackwell/Ada +24/31%, HURTS under orch-off −6%). Cloud-era doctrines **superseded**: the "W≈48 GIL" + "fp16 always slower" claims were vast.ai-48-core numbers. Harness now has `--repeats`, comma-`--only`, a `deploy` cell, and `--mode eval` (Phase-3 eval W-sweep — done, see DECISIONS addendum). **NOT yet wired into the loop — gated on a Pass-3 strength/correctness check** that orch-off (per-worker prior-batching) is strength-neutral.

### NEXT
1. ✅ **DONE (2026-06-01): strength-push loop FULLY wired + smoke-passed.** `run_pathb_cluster_loop.sh` now has all of: (a) **mixed-mode self-play** (`selfplay_mode()`: 5800x orch-off W=16, xeon `--orch-shards 2` W=18, laptop orch-off W=10 — +87% cluster); (b) **3-box anchor-gate fan-out** (`--shared-claim` + consolidated tally, gate fastest on laptop); (c) **WARM/anchor/gate-ref = iter_11** (default `WARM_SRC`); (d) **`--anchor-fraction 0.3 --anchor-checkpoint iter_11`** on the self-play cmd; (e) **stop-after-`MAX_FLAT`(=2) plateau guard** vs the fixed iter_11 gate (n=40 → coarse; raise ANCHOR_GAMES/MAX_FLAT to tighten); (f) **clobber guard** + default `RUN=pathb_anchor` (fresh dir, won't touch pathb_loop screening ckpts). Pass-3 neutrality proven by `tests/test_eval_server.py` (orch == inline <1e-5). Two smokes clean (mixed-mode + anchor-fraction). Launcher (untracked ~/) backed up to `code_sync/`.
2. ✅ **LAUNCHED + running** (see "Right now"). Measured iter cadence ~58 min (full iter). **CONFIRM-BEFORE-KILL added 2026-06-01:** the bare n=40 plateau guard was asymmetric (killed on screen-grade evidence while a positive needs verdict-grade) and ratchet-biased; now when MAX_FLAT flat gates accumulate it runs ONE n=CONFIRM_GAMES(400) head-to-head of latest-vs-best and only stops if latest fails CONFIRM_THRESH(0.54) — symmetric, ratchet-immune, reversible. Knobs env-overridable. Launcher re-backed-up to `code_sync/`.
   - **WATCH:** iters 0–3 gates = 47.5/55.0/37.5/**58.8** (new high) — ambiguous at n=40. iter 4 running. If gates hold >55% / keep climbing → anchor-fraction is working → verify the best ckpt vs iter_11 at n=400, then consider sims=800. If they regress into a plateau → confirm-before-kill fires (n=400 latest-vs-best) → likely leaf rework.
3. **Joshua plays iter_11** @ sims=800 anytime: `python scripts/play_vs_net.py --checkpoint /mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt --sims 800 --human 0`.

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
