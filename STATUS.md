# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A fresh Claude thread reading [CLAUDE.md](CLAUDE.md) → here should take over without missing a beat. **Current state only.** Historical narrative lives in [DECISIONS.md](DECISIONS.md) (dated entries) + git log — do NOT re-stack old "Right now" blocks here; that's what DECISIONS is for.

## Right now (2026-06-01) — 🔵 strength-push DONE: iter_4 = new best, +39 elo over iter_11 (n=400 verdict)

**Strongest checkpoint = iter_4 (`pathb_anchor/ckpt/iter_04.pt`), +39.3 elo / 2.25σ over iter_11 at n=400 (c=1.5, sims=200).** The anchor-fraction strength push (`RUN=pathb_anchor`, warm=iter_11, anchor_fraction=0.3, all 3 boxes) ran iters 0–6 then self-stopped via confirm-before-kill (plateau confirmed). **Real, modest gain — the v2.7 leaf ceiling is NOT absolute.** (Caveat: measured at the loop-gate's c=1.5, not the ladder's c=3.0; iter_4's *absolute* strength vs HeuristicMCTS not yet re-laddered.) Loop done; boxes free.

**The verdict (all in `results.csv`, `anchor_*_n400`):**
- **iter_4 vs iter_11 (n=400): 55.6% = +39.3 elo / 2.25σ — REAL.** iter_4 is the new best. ← headline
- iter_6 vs iter_4 (n=400): 49.1% = EQUAL → the two best ckpts are same strength despite n=40 iter_11 gates of 57.5 vs 68.8 ⇒ those swings were **noise**.
- iter_0 vs iter_5 (n=100): 46.5% ≈ equal → chain is NOT monotonic; checkpoints **bounce** (iter_4/iter_6 ~+39 over iter_11; iter_0/iter_5 ~iter_11 level). Pipeline healthy (val-corr 0.18→0.81), gain is real-but-noisy.
- **Lesson (logged hard): per-iter n=40 gates are screens, not verdicts** — the +39 real signal was invisible/misleading at n=40 (gates swung 37.5–68.8%); only n=400 resolved it. Per-iter timing/gate/corr in `experiments/iter_timings.csv`.

**Open decision (NEXT):** we have a real +39 → re-anchor on iter_4 and run more (try to stack), and/or re-ladder iter_4 vs HeuristicMCTS for the absolute read, vs. pivot to the leaf for a bigger lever. See NEXT.

### What we know (recorded in DECISIONS.md 2026-05-31)
- **iter_11 is the confirmed-strongest checkpoint — first trustworthy ABSOLUTE-strength signal.** Ladder gauntlet vs **HeuristicMCTS** (a strong NON-saturated reference: v2.7 leaf + UCT, no learned policy) at matched sims=200/c=3: **n=400 → 293W/6D/101L = 74.0%, +181.7 elo / 9.2σ.** The learned policy beats strong heuristic-search at equal compute → the +190 self-anchored gain was real strength. Clears ladder rung 1; **NOT yet superhuman** (HeuristicMCTS ≈ strong-amateur). `results.csv: ladder_iter11_vs_heuristic_n400`.
- **Value-as-leaf is CLOSED (calibration cliff).** Pure NN-value leaf −800; graceful only at λ≤0.1. Ceiling-probe (n=400): even λ=0.1 hurts (iter_01 −27.9 / iter_11 −35.7 elo) and a *better*-calibrated head hurts *more* → the v2.7 leaf ceiling is NOT liftable by value-head blending. Lifting it needs a genuinely stronger **learned** signal (what anchor-fraction self-play is meant to produce). **Don't switch the production leaf.**

### Bench sweep — DONE + CONFIRMED (3-rep verdict); mixed-mode self-play locked (+87% cluster)
Per-box per-lever throughput+telemetry sweep + 3-rep confirm + deploy pass. **Full record + all numbers: [DECISIONS.md](DECISIONS.md) 2026-06-01.** Data: `/mnt/c/carc-shared/bench/sweep_*.csv` (+ `sweep_confirm_*` / `sweep_deploy_*`). Headline: the orchestrator's **single GIL-bound dispatch thread is the limiter** for the CPU v2.7 leaf (GPU idle 28W) → **W is flat; orchestrator OFF wins where VRAM fits.** Per-box self-play optimum (3-rep, CV ≤2%): **5800x orch-off W=16 (no fp16) = 14.70 mv/s (+99%) · xeon orch_shards=2 = 6.99 (+30%) · laptop orch-off W=10 = 19.26 (+110%)** → cluster 21.9→41.0 = **+87%**. fp16 is **batch-conditional** (helps under orchestrator on Blackwell/Ada +24/31%, HURTS under orch-off −6%). Cloud-era doctrines **superseded**: the "W≈48 GIL" + "fp16 always slower" claims were vast.ai-48-core numbers. Harness now has `--repeats`, comma-`--only`, a `deploy` cell, and `--mode eval` (Phase-3 eval W-sweep — done, see DECISIONS addendum). **NOT yet wired into the loop — gated on a Pass-3 strength/correctness check** that orch-off (per-worker prior-batching) is strength-neutral.

### NEXT — decision point (anchor-fraction gave a real +39; pick the next lever)
The strength loop + confirm-before-kill + iter-timing recorder are all done and committed (DECISIONS 2026-06-01). iter_4 is the new best (+39 elo / 2.25σ over iter_11, n=400). Open options:
1. **Re-ladder iter_4 vs HeuristicMCTS @ c=3.0** (n=400) — get iter_4's ABSOLUTE strength on the same ruler as `ladder_iter11_vs_heuristic_n400`, and reconcile the c=1.5 (loop gate) vs c=3.0 (ladder) operating point. Cheap (~90 min, boxes free), and it's the clean way to say "iter_4 = iter_11's +181.7 elo **+ 39 more**" on one scale. **Recommended first.**
2. **Re-anchor + run more:** `RUN=pathb_anchor2 WARM_SRC=…/pathb_anchor/ckpt/iter_04.pt` with anchor=iter_4 — try to stack another increment on the new best. Gain is real but noisy/non-monotonic, so weigh ROI; consider bumping `ANCHOR_GAMES=100` (stabilizes the plateau ratchet) and benching a cheaper self-play config first.
3. **Pivot to the leaf rework** — +39 is modest; the v2.7 leaf is still the bigger lever for superhuman. The dent (iter_4 > iter_11) shows learned signal *can* exceed it; a learnable/better leaf is the path to a *large* gain.
4. **Joshua plays iter_4** @ sims=800: `python scripts/play_vs_net.py --checkpoint /mnt/c/carc-shared/pathb_anchor/ckpt/iter_04.pt --sims 800 --human 0`.

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
