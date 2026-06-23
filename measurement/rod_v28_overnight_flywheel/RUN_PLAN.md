# RoD v2.8 Overnight Flywheel — RUN PLAN

**Branch:** `rod_v28_overnight_flywheel` (from `rod_v28_overnight_flywheel` @ branch tip of the batch-512 line)
**Date:** 2026-06-23 · **Status banner:** ⏳ SET UP — launching overnight
**Scope:** MEASUREMENT / EXPLORATION ONLY. **No promotion. `PRODUCTION.yaml` untouched. Champion (`flywheel2_champion_iter8`) unchanged. v2.7 frozen. v2.8 opt-in. No batch-512. No batch/LR/epoch/arch/c_puct/residual/sims change.**

---

## The one question

`RoD_iter_01` (one v2.8 continuation iter, warm-from `iter8`) **beat its frozen parent by +53.4 Elo** and **closed the equal-leaf gap to deep heuristic search to parity** — the first continuation the v2.7 substrate could never produce. **Does that gain COMPOUND across a multi-iteration latest-chain flywheel, or saturate** (as every v2.7-substrate flywheel did by ~iter5)? This overnight run generates the chain so tomorrow's binding evals can answer it.

This is **exploratory**, not promotion-grade. Overnight we run only **cheap catastrophe screens**; the real strength verdicts are **deferred to tomorrow** (cost discipline).

## Lineage — latest-chain

```
RoD_iter_01  →  RoD_iter_02  →  RoD_iter_03  →  …  →  RoD_iter_NN
   (seed)        (warm-from prev)   (warm-from prev)
```

- **Warm-from = the previous iter every time** (latest-chain), starting from `RoD_iter_01` (sha `a8b824df…`).
- **ALL checkpoints retained** (`/mnt/c/carc-shared/rod_v28_overnight_flywheel/ckpt/iter_*.pt`) → tomorrow we do after-the-fact **keep-best**, not a live keep-best gate (which would need expensive evals).
- **Catastrophe → STOP** at the last-sane checkpoint (no auto-revert-and-continue; safer unattended), preserving every artifact.

## The recipe (FROZEN — identical to RoD_iter_01)

| axis | value | in user's frozen list? |
|---|---|---|
| leaf | **v2.8** = v2.7 + `meeple_k=2.0` (`CARCASSONNE_V25_MEEPLE_K=2.0`, flat fast path) | ✅ |
| batch size | **256** | ✅ |
| epochs | **3** | ✅ |
| value-loss-weight | **1.5** | (recipe) |
| lr / wd / optimizer | **1e-3 / 1e-4 / AdamW** | ✅ |
| residual_scale | **0.25** | ✅ |
| sims / c_puct | **200 / 3.0** | ✅ |
| architecture | **96×6 ResNet, n_scalar=12** | ✅ |
| value target | **residual** | (recipe) |
| **games / iter** | **400** (see below) | ❌ *not in the frozen list* |

### The one deliberate parameter choice: games/iter = 400 (not 1000)

`games/iter` is **not** among the axes the user froze (batch/LR/epochs/arch/c_puct/residual/sims). **400 is the *validated* attempt-2 flywheel cadence** — the residual flywheel ran **400 games/iter × 8 iters → champion `iter8`, +67 Elo compounding**. The continuation's **1000** was a *one-shot probe boost* (a single iter, maximizing signal), **not** the flywheel cadence. Using 400:

- keeps **every frozen axis identical** to RoD_iter_01,
- makes the user's **10–15-iter target feasible overnight** (1000 games → train ≈ 76 min/iter → only ~4–5 iters fit; 400 games → train ≈ 30 min/iter → ~9–10 iters),
- does **not** reintroduce the batch-512 under-training failure: that was a *single* train with halved optimizer steps. In a **warm-from chain** each iter fine-tunes an already-converged policy and the chain **accumulates** steps across iters — exactly how attempt-2 compounded at 400/iter.

Reversible: `GAMES=1000 bash scripts/rod_v28/run_overnight_flywheel.sh` runs the exact continuation data volume (fewer iters).

## Per-iteration sequence

1. **Self-play gen** — 400 games, 2-box **work-stealing** (carc-orch SHM, `--shared-claim`), v2.8 leaf via `CARCASSONNE_V25_MEEPLE_K=2.0` in the gen env (reaches the MCTS search leaf — verified for RoD_iter_01, `run_selfplay_iter.py:354`). Local W48 + laptop W26.
2. **Train** — LOCAL only (5900XT), batch 256 / 3 epochs / VLW 1.5, warm-from prev. Writes `iter_NN.pt` + `.metrics.json`.
3. **Cheap screens** (catastrophe detectors, **NOT verdicts**):
   - training-loss sanity (monotone train_pol, flat val_pol),
   - **policy-entropy / collapse** check (floor = 0.5 × baseline),
   - **tiny n=40 paired smoke vs the previous iter** (local two-context net-vs-net, same v2.8 leaf) — flags only a *catastrophic* play regression (wr < 0.25).
   - *(root-action audit on the fixed 1000-pos v2.8 midgame sample is deferred to tomorrow — not cheap enough for every iter.)*
4. **Manifest / log / csv append** — `overnight_iter_screen.py` writes one row each to `CHECKPOINT_MANIFEST.json`, `TRAINING_LOG_SUMMARY.md`, `CHEAP_SCREEN_RESULTS.csv` (idempotent on iter).

**No expensive evals overnight** (`heur@3200`, n=400 binding matchups) — deferred per the user's "Full eval deferral".

## Cost / ETA

| stage | ~time @ 400 games |
|---|---|
| gen (local W48 + laptop W26, orch) | ~18–25 min |
| train (5900XT, ~0.83M positions, 3 ep) | ~30–35 min |
| smoke (n=40 paired, local two-context) | ~6–10 min |
| **per iter** | **~55–70 min** |

→ in a **10 h** window, **~9–10 iterations** (capped at 14; stops cleanly at the deadline or on catastrophe). Owned hardware, **no cloud $**.

## Self-healing & robustness

- gen no-progress for 15 min → kill pools + orch on both boxes, clean stranded `.claim` files, relaunch (≤ 8 heals, then abort loudly).
- detached launch (`nohup … & disown`) survives the Mac→Windows→WSL SIGHUP path; `nice -n 19` yields to interactive use.
- laptop sync failure → auto **local-only** (night not wasted on stale code).
- any exit (signal / deadline / catastrophe / done) → kill orphans on both boxes + write a clean `OVERNIGHT_STATUS.md`.
- resume-safe: `done/gen$it` and existing `iter_NN.pt` skip already-done work.

## Deferred to tomorrow (the binding evals)

On selected checkpoints (latest + best-cheap-diagnostic + maybe every 2nd):
1. candidate **vs `RoD_iter_01`** (n=400 paired, v2.8, net-vs-net),
2. candidate **vs frozen `ITER8_V28_PARENT`** (n=400 paired),
3. candidate **vs `heur@3200_v2.8`** ruler — *only if* it beats / plausibly beats `RoD_iter_01` (the first "learned > deep heuristic at equal leaf" would be the breakthrough).

## Deliverables (this dir)

| file | content |
|---|---|
| `RUN_PLAN.md` | this plan |
| `OVERNIGHT_CONFIGS.json` | fully-resolved machine-readable config |
| `CHECKPOINT_MANIFEST.json` | per-iter: ckpt/parent hashes, gen+train config, losses, steps, wall-clock, crashes, screen verdict, smoke (appended live) |
| `TRAINING_LOG_SUMMARY.md` | per-iter human summary (appended live) |
| `CHEAP_SCREEN_RESULTS.csv` | per-iter screen table (appended live) |
| `OVERNIGHT_STATUS.md` | live status (overwritten each stage) — read this first in the morning |

## Hard constraints (held)

No `PRODUCTION.yaml` edit · no promotion · no v2.7 change · no batch/LR/epoch/arch/c_puct/residual/sims change · no batch-512 · every checkpoint+manifest saved · reproducible from configs · partial artifacts preserved on crash.
