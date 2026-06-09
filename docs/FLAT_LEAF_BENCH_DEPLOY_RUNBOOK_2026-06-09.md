# Flat-leaf throughput bench + deploy — runbook (2026-06-09)

> **POST-COMPACTION: START HERE.** Self-contained; the executor has NO memory of
> the conversation that produced it. Read this, then `git log --oneline -8`, then
> proceed. The flat leaf is BUILT, VALIDATED bit-exact, and WIRED (default-OFF).
> The only remaining work is: **run the throughput bench → decide deploy.**

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
2. **Flip the toggle via env in the flywheel launchers:** add `CARCASSONNE_USE_FLAT_LEAF=1`
   to the `ENVV`/`COMMON_ENV` of `run_residual_flywheel_v2.sh` (5800x train + local
   gen), `gen_flywheel.sh` (xeon/laptop gen), and the eval launches. (It already
   carries `CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`.)
3. **WIRING-TIME GUARD (audit):** the flat path raises `NotImplementedError` on the
   deck-aware closure configs (`CARCASSONNE_V25_TILE_COUNTING` / `_CLOSURE_SLACK`).
   v2.7 has both OFF, so safe — but assert/verify they're off wherever flat is enabled.
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
