# Flat-leaf throughput bench + deploy — runbook (2026-06-09)

> **POST-COMPACTION: START HERE.** Self-contained; the executor has NO memory of
> the conversation that produced it. Read this, then `git log --oneline -8`, then
> proceed. The flat leaf is BUILT, VALIDATED bit-exact, and WIRED (default-OFF).
> The only remaining work is: **run the throughput bench → decide deploy.**

> ## ⛔ BENCH DONE — VERDICT: DO NOT DEPLOY (2026-06-09)
> Ran on a quiet 5800x, G=32, sims=200, fixed seed, OFF vs FLAT back-to-back, swept W.
>
> | W  | regime           | OFF g/min | FLAT g/min | FLAT/OFF |
> |----|------------------|-----------|------------|----------|
> | 1  | contention-free  | 0.94      | 1.15       | **1.22×** |
> | 14 | production       | 6.64      | 6.79       | **1.02×** |
> | 20 | oversubscribed   | 7.14      | 7.42       | **1.04×** |
>
> **At production-scale W the gain is ~2–4% ≪ the 1.3× deploy floor → NOT deployed.**
> WHY (decomposed by the W=1 probe + reconciled with the 2026-06-09 DRAM-bandwidth
> DECISIONS entry): the leaf speedup is real and large single-thread (+22% → the leaf is
> ~⅓ of single-thread self-play wall, NOT an Amdahl sliver), but it collapses at W≥14
> because production self-play is **RAM-BANDWIDTH-bound** (rigorously established last
> night: `bw_scaling.py` saturates at 2–4 threads ≈40 GB/s; per-worker throughput erodes
> smoothly from W=4; clock held → not thermal; GPU mostly idle during gen → not GPU).
> **The leaf rewrite's STATED goal (BACKLOG #322 / the DRAM entry) was "cut bytes/sim →
> raise the saturation point."** We instead built+validated a COMPUTE win (2.26× per-leaf
> CPU, +22% single-thread) and never measured bytes/sim. The at-scale bench is that
> measurement: ~no gain ⇒ the flat leaf does NOT meaningfully cut DRAM traffic at the
> operating point (the dominant traffic is the MCTS tree + state/feature memory, not the
> leaf's allocations — OR the flat leaf's own per-eval arrays/dicts move similar bytes).
> Optimized the right hot-path for the WRONG resource. Process was sound: gating on the
> at-scale number (not the 2.26× microbench) caught it cheaply, before any deploy.
> FIRING PROVEN three ways: position divergence 3956→3955 at W=14 & W=20 (canonical-fsum
> signature), the 18% single-thread wall drop on byte-identical games, and a direct
> assertion (virtual_score_v2 routes to flat_leaf 0× when OFF / 1× when ON). NB: deployed
> flat is pure interpreted Python — NO compilation; numba (the 3.21× compiled kernel) is
> a separate DEFERRED path, not in this bench.
> ⚠️ RETRACTED (was wrong): an earlier note here claimed "W=20 out-throughputs W=14 by
> ~8% → possible worker-count lever." That compared TWO separate G=32 runs at different
> thermal states and is **inside the ±15–20% run-to-run noise** the DRAM DECISIONS entry
> explicitly flags. Last night's CONTROLLED single-session W=1..30 scan (G=48,
> thermal-instrumented) shows **W=16 is the peak (7.73 g/min) and W=20 is BELOW it
> (6.71)**. The W=14–18 plateau + production W=14 STAND. No worker-count change.
> The flat leaf stays a validated bit-exact branch (`leaf-rewrite`) for a FUTURE
> leaf-bound / low-contention context (low-W, the numba path, a higher-bandwidth box like
> the DDR5 laptop, or a leaf-dominated pipeline). Deploy steps below retained for that
> future use — DO NOT run them here.

## TL;DR — what to do next
1. **Confirm the flywheel is paused** (Joshua is pausing it from another thread so
   the 5800x is quiet). Verify: `pgrep -f 'run_selfplay_iter|eval_net_vs_heuristic|train_iter' | wc -l` should be ~0 on the 5800x. Do NOT resume the flywheel — Joshua's other thread owns it.
2. **Run the headline bench** (on the 5800x, where the worktree lives):
   ```
   cd /home/doctor/projects/carc-leafdev
   WS="16" G=32 bash scripts/bench_flat_throughput.sh
   ```
   ETA ~12–15 min (warmup + OFF + FLAT at W=16). Reads the FLAT/OFF games/min ratio.
3. **Decide** per the decision tree below. If promising, run the saturation sweep
   `WS="8 12 16 20" G=48 bash scripts/bench_flat_throughput.sh` (~45 min) for
   deploy-grade evidence.

## Where things stand (all committed on branch `leaf-rewrite`, worktree `/home/doctor/projects/carc-leafdev`)
The de-objectified flat leaf (`src/carcassonne_ai/flat_leaf.py`) computes the full
v2.7 leaf directly from an int union-find decomposition — no deepcopy, no
count_final_scores, no engine Farm/City objects.
- **Bit-exact** to the engine under canonical sum: `scripts/reconcile_flat_leaf.py`
  n=400 PASS (935k+580k+700k partition checks + 28.8k each base/closure/v2/ALT-cfg,
  0 mismatches) + edge-case test `tests/test_flat_leaf_edge_cases.py` (inn/cathedral/
  shield + BIG meeples, the branches random play can't reach).
- **2.26× faster per leaf** in pure Python (micro-bench); numba on `_label_components`
  proven 3.21× drop-in but DEFERRED (needs an isolated/Cython build — shared venv
  has no numba; installing bumps numpy). **Deploy the pure-Python flat only.**
- **Wired, default-OFF:** `virtual_score_v2` redirects to `flat_virtual_score_v2`
  when `flat_leaf.USE_FLAT_LEAF` is on. The toggle also reads env
  `CARCASSONNE_USE_FLAT_LEAF=1` at import (so spawned workers + a deploy launcher
  pick it up). Wrapper-path gate confirms it FIRES through `make_v25_value_wrapper`
  (144/144, 0 mismatches) — not silently bypassed.
- **Audit:** 18-agent adversarial review — verdict "bit-exact HOLDS, 0 reachable
  bugs"; all findings were gate over-certification (since hardened). See
  `docs/DEOBJECTIFY_LEAF_PLAN_2026-06-09.md` "Adversarial code-review audit".

## The bench — what it measures + why
`scripts/bench_flat_throughput.sh`: real production-knob self-play (sims=200,
v2.7 CPU leaf, orch-off, batch=8, anchor 0.3, FIXED seed → identical games), npz to
local /tmp (no CIFS confound), each W run twice — OFF vs `CARCASSONNE_USE_FLAT_LEAF=1`
— against the worktree code. Prints games/min per (mode,W) + the FLAT/OFF ratio.

**Why this number, not the 2.26×:** self-play is RAM-bandwidth-bound at production W,
so the per-leaf 2.26× is an UPPER BOUND. The at-scale games/min gain at W=16 is the
real deploy-decision number (likely lower — anywhere ~1.2×–2×). Deploying on the
2.26× would be the "extrapolate from one good run" trap.

Checkpoint: defaults to `/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter4.pt`
(or pass `CKPT=...`). Any valid ckpt works (throughput, not strength). It's copied
to /tmp so the share isn't in the hot path.

## Deploy decision tree (after the bench)
- **at-scale gain < ~1.3×** → NOT worth the deploy disruption for ~8 iters. Skip
  deploy; merge the leaf for the NEXT experiment instead.
- **~1.3×–1.5×** → marginal; only deploy if many iters remain. Judgement call.
- **≥ ~1.5×** → worth it. Deploy for the remaining flywheel iters (could save hours).

Deploying flat == **adopting CANONICAL leaf semantics** (the flat path is
fsum-canonical; production runs naive sum). The difference is ~7e-5 of leaf evals by
±1 — negligible (the naive leaf is ALREADY non-deterministic across processes by the
same magnitude), but it IS a deliberate, documented ruler change. Note the switch
point in the experiment log.

## Deploy steps (ONLY if the bench says go — coordinate with Joshua; it touches the running experiment)
1. **Merge `leaf-rewrite` → `stage-b-wiring`** (the flywheel's branch), OR cherry-pick
   the flat-leaf commits. The flat code is default-OFF, so the merge itself is inert.
2. **Flip the toggle via env — EXACT diff (verified against live tree 2026-06-09).**
   Gen workers do NOT inherit `$ENVV`; they get env via an explicit var list. So the
   toggle goes in TWO places:
   - **`/mnt/c/carc-shared/code_sync/gen_flywheel.sh:28`** — the line is
     `env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \` right before the
     `run_selfplay_iter.py` call. Add `CARCASSONNE_USE_FLAT_LEAF=1`. **This is the
     throughput win** (covers gen on all 3 boxes — it's ONE share file, every box
     reads `$SHARE/code_sync/gen_flywheel.sh`, so no per-box sync for this edit).
     ⚠️ This file is share-resident, NOT git-tracked — it will NOT come through the
     bundle; edit the share copy directly.
   - **`scripts/run_residual_flywheel_v2.sh:40`** — `ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"`.
     Add `CARCASSONNE_USE_FLAT_LEAF=1`. `$ENVV` flows to eval (lines 137/141/142, all
     3 boxes, also leaf-bound → also benefits) and train (line 243, ignores it
     harmlessly — train consumes .npz, never calls the leaf). This IS git-tracked →
     comes through the bundle.
3. **WIRING-TIME GUARD (audit) — VERIFIED CLEAR 2026-06-09:** the flat path raises
   `NotImplementedError` on deck-aware closure (`CARCASSONNE_V25_TILE_COUNTING` /
   `_CLOSURE_SLACK`). Grepped the live flywheel path (run_residual_flywheel_v2.sh,
   gen_flywheel.sh, pathb): **neither var is set anywhere** → flat guard cannot fire.
   Re-verify if the leaf config ever changes.
4. **3-box git-bundle refresh + worker restart** (the flywheel is multi-box; remotes
   sync via `git bundle` on the share — see the offline-git-bundle-sync memory). Do
   this at a clean iter boundary, restart workers via `--shared-claim`.
5. Pure-Python flat ONLY (no numba → no numpy/venv risk).

## Flywheel architecture facts (for safety — verified from `run_residual_flywheel_v2.sh`)
- **Train is 5800x-ONLY** (`train_iter.py` runs locally, no ssh). gen + eval fan out
  to xeon+laptop via `--shared-claim`.
- Loop per iter: gen (3-box) → **train (5800x-only)** → telemetry gate → external
  keep-best eval. Resumable: per-phase `done/gen$it` markers + per-game `.npz` +
  ckpt files; re-running the launcher skips completed phases.
- attempt-2 = 12 iters; as of 2026-06-09 ~iter5 done (so ~6–7 iters / many hours left).
- Killing a `--shared-claim` worker strands `.claim` files → a ~6-min stall-heal
  RELAUNCHES workers (incl. on the 5800x). This is why a "5800x-only" pause is
  fragile and a clean WHOLE-flywheel pause was chosen instead.

## Hard constraints (unchanged)
- Work in the `leaf-rewrite` worktree; do NOT edit the live tree
  `/home/doctor/projects/carcassone` casually. Do NOT resume Joshua's flywheel
  (his other thread owns it).
- Do NOT `pip install` into the shared `.venv` (numpy bump contaminates experiments).
- The bench needs a genuinely quiet 5800x (flywheel paused) for a clean number.
- `nice -n 19` on everything.

## Git state (branch `leaf-rewrite`)
```
feat(leaf): wire USE_FLAT_LEAF into virtual_score_v2 + throughput bench (default OFF)  [02e7bad]
test(leaf): harden the equivalence gate per the adversarial audit (18-agent review)   [9c1e6f9]
test(leaf): edge-case equivalence for inn/cathedral/shield + BIG meeples              [0e0d39b]
perf(leaf): Stage 4c — numba prototype proves _label_components 3.21x (deferred)      [cab569e]
perf(leaf): Stage 4a/4b — int-encode sides + per-tile feature cache (2.26x)           [7aad044]
perf(leaf): de-objectified flat leaf — bit-exact, 1.87x faster interpreted            [9e57ff5]
```
(+ this runbook + the bench-warmup fix to commit.)
