# Flat-leaf throughput bench + deploy — runbook (2026-06-09)

> **POST-COMPACTION: START HERE.** Self-contained; the executor has NO memory of
> the conversation that produced it. Read this, then `git log --oneline -8`, then
> proceed. The flat leaf is BUILT, VALIDATED bit-exact, and WIRED (default-OFF).
> The only remaining work is: **run the throughput bench → decide deploy.**

> ## ✅ VERDICT: DEPLOY (cross-box confirmed 2026-06-09) — Joshua approved for the rest of attempt-2
> Cross-box OFF-vs-FLAT, production W, **iter_11** checkpoint, fixed seed, back-to-back:
>
> | box | memory | W | OFF g/min | FLAT g/min | FLAT/OFF | clean? |
> |-----|--------|---|-----------|------------|----------|--------|
> | xeon   | DDR4 | 10 | 2.73 | 3.02 | **1.11×** | ✓ foreign 4% |
> | 5800x  | DDR4 | 16 | 6.65 | 7.35 | **1.10×** | throttle-floor |
> | laptop | DDR5 | 20 | 9.05 | 9.51 | **1.05×** | ✓ foreign 0% |
>
> **Cluster gen ≈ +8%** (sum 18.4→19.9 g/min) and flat helps the eval gauntlet too (same
> leaf) → ~+8–10% on 2 of the 3 phases (train is GPU, untouched). Worth deploying for the
> ~6 remaining attempt-2 iters, folded into the restart the paused flywheel needs anyway.
>
> **WHY the earlier "2% / DO NOT DEPLOY" was wrong — checkpoint dependence.** The first
> bench used **iter4** and got ~1.02×; iter_11 (closer to the real nets) gets ~1.10× on
> DDR4. The net's policy changes game dynamics → how big a share the leaf is of wall time.
> **The cross-box pattern confirms the mechanism:** flat's real win is cache-friendly int
> arrays vs pointer-chasing engine objects → it pays off most where the **DRAM bus is
> saturated** (both DDR4 boxes ~1.10×) and least where there's bandwidth headroom (DDR5
> laptop 1.05×). So flat partially *does* relieve the bandwidth wall — Joshua's hypothesis.
>
> **Throttle reconciliation (Joshua, HWiNFO):** the 5800x VRM-throttles ~8% of the time
> with clocks cratering to ~0.55 GHz transiently → ~10–15% real penalty (the WSL
> `% Processor Performance` gauge samples ~1/s and misses these cliffs — that's why last
> night's "no throttle" was wrong). This depresses ABSOLUTE g/min on both OFF and FLAT but
> the FLAT/OFF *ratio* is throttle-independent and biased AGAINST flat (FLAT runs hotter /
> second + draws more watts) → **the ~1.10× is a conservative floor.** Higher wattage under
> flat = more compute/sec = direct evidence the DRAM relief is real (bandwidth wall → thermal
> wall). VRM fins (on order) recover the 10–15% for ALL work, both modes — orthogonal, bigger.
>
> FIRING PROVEN three ways: position divergence 3957→3956 (canonical-fsum signature), the
> 18% single-thread wall drop on byte-identical games, and a direct assertion
> (virtual_score_v2 routes to flat_leaf 0× OFF / 1× ON). Deployed flat is pure interpreted
> Python — NO compilation; numba (3.21× kernel) stays DEFERRED. Deploying adopts canonical
> (fsum) leaf semantics: ~7e-5 of evals by ±1, negligible (the leaf is already that
> nondeterministic across processes) — note the switch point in the experiment log.
> **DEPLOY STEPS: see "Deploy steps" below — already pinned exact (commit 60374bd).**

## TL;DR — what to do next
**Bench is DONE and the verdict is DEPLOY (see the ✅ block above). Joshua approved
turning flat ON for the rest of attempt-2, folded into the restart the paused flywheel
needs anyway. Implementation is owned by the flywheel thread — apply the "Deploy steps"
below.** The bench commands are retained at the bottom for the post-VRM-fin clean rerun.

### Deploy handoff (what the flywheel thread must do)
1. **Get the flat code onto all 3 boxes.** Merge `leaf-rewrite` → `stage-b-wiring` (clean —
   only docs diverged) OR cherry-pick; it's default-OFF so the merge is behaviorally inert.
   Then bundle-refresh the remotes (offline-git-bundle-sync: bundle on the share +
   `git fetch <bundle>` + `git reset --hard` on xeon & laptop). **The flag does nothing
   without this code** (the boxes' current `virtual_score_v2.py` has no redirect / no `flat_leaf.py`).
2. **Set the flag in TWO places:**
   - `/mnt/c/carc-shared/code_sync/gen_flywheel.sh:28` (xeon+laptop gen — all boxes read this
     share copy, so NO per-box edit needed for the flag) → add `CARCASSONNE_USE_FLAT_LEAF=1`.
   - `scripts/run_residual_flywheel_v2.sh:40` `ENVV=...` (5800x gen + eval, lines 137/141/142) → add `CARCASSONNE_USE_FLAT_LEAF=1`.
3. **Deck-aware guard is clear** — neither `CARCASSONNE_V25_TILE_COUNTING` nor `_CLOSURE_SLACK`
   is set anywhere in the flywheel path, so the flat path's `NotImplementedError` can't fire.
4. **Restart at a clean iter boundary** via `--shared-claim`. Pure-Python flat only (no numba).
5. **Log the switch point** — deploying adopts canonical (fsum) leaf semantics (~7e-5 ±1, negligible).

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
