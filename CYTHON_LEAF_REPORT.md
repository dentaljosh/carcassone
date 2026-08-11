# Cython flat-leaf port — dev + validation report (2026-06-12)

**Status: DEV-ONLY, default OFF.** `CARCASSONNE_USE_CY_LEAF` is unset everywhere;
nothing imports the compiled module unless the flag is set. No production
behavior changed. Fold-to-production is a separate, later decision at a clean
boundary (see "Fold-to-production steps").

## What this is

A Cython port of the production leaf kernel
(`flat_leaf.flat_virtual_score_v2`, the v2.7 virtual-score under
`CARCASSONNE_USE_FLAT_LEAF=1`): `src/carcassonne_ai/flat_leaf_cy.pyx`.
The whole pipeline is ported — `decompose` (board walk → int union-find
components + per-root facts), `_label_components` (path-halving union-find),
`_final_scores`, the closure-anticipation bonus, and the final assembly through
`flat_virtual_score_v2_cy(state, player, cfg) -> int`.

Design (per the de-objectify plan's Stage-4 intent):

- The **boundary** (walking engine Tile/meeple Python objects) stays
  Python-object access inside Cython. Enum→small-int conversion happens once
  per distinct Tile via a feature cache (`_TILE_FEAT`, identity-keyed dict —
  tiles are canonical shared refs; the engine state `__deepcopy__` shares Tile
  objects, so the cache is bounded ~100 entries/process).
- **All interior bookkeeping is C**: node-id tables are flat `int` arrays
  indexed by `(r*W+c)*9 + side_ix` (memset −1 per call, no dict/tuple/enum
  hashing); union-find over C arrays; per-root facts (finished / open_n /
  tiles / shields / cathedral / adjacent-city dedup) via counting-sort
  bucketing + monotone stamp arrays — no per-leaf set/dict allocation. All
  buffers live in a reused module-singleton workspace (workers are separate
  processes; the leaf is not re-entrant).
- **Bit-exactness by construction**: node/edge enumeration and union order
  mirror `flat_leaf.decompose` exactly → component root ids are bit-identical
  ints (verified, not just assumed). The closure bonus accumulates the same
  multiset of float contributions (each a single IEEE-double product, identical
  to the Python float product) and reduces with `math.fsum` (correctly rounded,
  order-independent) — same canonical-sum semantics the flat leaf already
  adopted. Final rounding calls Python `round()` on a boxed float (banker's
  rounding), matching `int(round(score))`.

## Build

```bash
# fresh venv used for dev (DO NOT touch the production venv):
python3 -m venv .venv-cy && .venv-cy/bin/pip install cython setuptools numpy
# one-command build (any venv with cython+setuptools):
.venv-cy/bin/python setup_flat_leaf_cy.py build_ext --inplace
# -> src/carcassonne_ai/flat_leaf_cy.cpython-312-x86_64-linux-gnu.so
```

Compiles clean (gcc, `-O3`). The `.so` and `build/` are not committed; each box
builds locally.

## Flag / wiring (additive, default OFF)

`flat_leaf.py` gains `USE_CY_LEAF` (env `CARCASSONNE_USE_CY_LEAF=1`, read at
import like `USE_FLAT_LEAF` so spawned workers inherit it) and a 5-line lazy
redirect at the top of `flat_virtual_score_v2`. With the flag unset: one false
`if` per call, the compiled module is never imported, behavior byte-identical
(existing `tests/test_flat_leaf_edge_cases.py` + `tests/test_virtual_score_v2.py`
pass with the flag off — and also with it ON). Because the redirect sits inside
`flat_leaf.flat_virtual_score_v2`, the production dispatch chain
(`virtual_score_v2` → flat-leaf redirect → cy) needs no other edits, and the
deck-aware-config fall-through guard in `virtual_score_v2` still applies
upstream. The cy port itself raises `NotImplementedError` on
`tile_counting_closure` / `closure_continuous_slack` cfgs, mirroring
`flat_closure_bonus`.

## Validation (bit-exact gate)

Gate: `scripts/reconcile_cy_leaf.py` (modeled on
`scripts/reconcile_compact_leaf.py`; same seeded random-play state sampling at
every depth + terminal). Acceptance bar is **0 int mismatches — no float-order
escape hatch**, since the Python flat leaf is already fsum-canonical and the
port reproduces the same contribution multiset.

Verdict run (production knobs `CARCASSONNE_V25_CAP=12
CARCASSONNE_V25_DROP_THREE_OPEN=1`, seed 24680, snap-every 1):

| check | count | mismatches |
|---|---|---|
| leaf int, cfg prod-default (v2.7) | 115,126 | 0 |
| leaf int, cfg pre-v2.7 (3-open schedule, cap 5) | 115,126 | 0 |
| leaf int, cfg "weird" (one-open, caps 3/7.5, meeple_k=0.35) | 115,126 | 0 |
| base int (`flat_base_score`) | 115,126 | 0 |
| full Decomp structure compare (every 25th state) | 2,302 | 0 |
| runtime `USE_CY_LEAF` wiring | bound + routed | OK |

400 games / 57,563 states / **345,378 leaf-int checks total** (= 57,563×2
players×3 cfgs; the production-config cell alone is 115,126 position-player
evals, > the 100k target). Off-production **env** run (`CARCASSONNE_V25_CAP=5`,
no drop-3-open → DEFAULT_CONFIG carries the 3-open schedule): 25 games, 10,800
leaf checks + 3,600 base checks, 0 mismatches. Logs:
`/tmp/reconcile_cy_leaf_prod.log`, `/tmp/reconcile_cy_leaf_offprod.log`.
Existing `tests/test_flat_leaf_edge_cases.py` + `tests/test_virtual_score_v2.py`
also pass with `CARCASSONNE_USE_CY_LEAF=1`.

Structure compares check `decompose_export` (the boxed C decomposition) against
`flat_leaf.decompose` field-for-field with **exact root-id equality** (not just
up-to-relabeling) on: city_side_root / finished / open_n / delta,
road_side_root / finished, farm_pos0_root, farm_anypos_root,
farm_root_adj_city_roots, farm_root_finished_cities.

## Bench (interleaved A/B, busy box)

`scripts/bench_cy_leaf.py` — 360 random-play snapshots (30 games, production
knobs), 8 alternating full-pass block pairs, `nice -n 19`, on the 5900XT box
**while the production flywheel was running** (loadavg ~16/32) — absolute
numbers are load-contaminated; the interleaved ratio is the result:

| | median us/leaf | min |
|---|---|---|
| Python flat leaf | 484.5 | 389.3 |
| Cython port | 33.6 | 29.2 |

**Speedup: ~14.3x median-of-block ratios (range 8.7–20.3x across blocks).**
For calibration: the flat leaf itself was a ~2.26x win over the object leaf, so
cy is ~30x the original object path per leaf. Reminder from the flat-leaf
deploy: per-leaf speedup translated to ~+8% end-to-end self-play throughput at
that time (the leaf is one component of the move loop); expect the end-to-end
gain to be re-benched at fold time, not extrapolated.

## Files

- `src/carcassonne_ai/flat_leaf_cy.pyx` — the port (new)
- `setup_flat_leaf_cy.py` — one-command build (new)
- `src/carcassonne_ai/flat_leaf.py` — `USE_CY_LEAF` flag + lazy redirect (edit, default OFF)
- `scripts/reconcile_cy_leaf.py` — bit-exact differential gate (new)
- `scripts/bench_cy_leaf.py` — interleaved A/B bench (new)
- `CYTHON_LEAF_REPORT.md` — this file

Branch: `stage-b-wiring` (agent worktree).

## Known caveats

1. **`.so` is per-box / per-python.** Built for cpython-3.12 x86_64. Each box
   (5800x/xeon/laptop) must run the build once; the flag without the build
   raises `ModuleNotFoundError` at the first leaf call (loud, not silent).
2. **Tile feature cache holds strong refs** (plain dict, identity-keyed) vs the
   Python flat leaf's `WeakKeyDictionary`. Safe/bounded because the engine
   state deepcopy shares Tile refs (canonical tile population ~100/process). If
   anyone ever makes states deep-copy tiles, this becomes a slow leak — the
   Python version's WeakKey choice documents the same assumption.
3. **Workspace is a module singleton** — not thread-safe, not re-entrant. Fine
   for the production model (process-parallel workers, leaf called serially
   inside MCTS); do not call the leaf from threads.
4. **Capacity guards**: fixed small tables (32 meepled features, 16
   knight/farm/cloister entries per player) raise `RuntimeError` if exceeded —
   impossible under 7-meeples-per-player rules, loud if assumptions break.
5. Only the v2.7 schedule path is implemented (no `tile_counting_closure` /
   `closure_continuous_slack`) — same scope as the Python flat leaf, same
   `NotImplementedError`, and `virtual_score_v2` already falls through to the
   engine path for those configs.
6. Bench absolutes are contaminated by background load (production flywheel
   running); the interleaved ratio is robust but re-bench per box at fold time.

## Fold-to-production steps (later, at a clean boundary)

1. Merge the branch at an iteration boundary (no mid-generation code-era flip).
2. `git bundle` sync to xeon + laptop (no GitHub from remotes), then build the
   extension on each box **in its production venv** (needs `cython` +
   `setuptools` installed there, or ship the cythonized `.c` and compile
   without cython).
3. Re-run `scripts/reconcile_cy_leaf.py --n 400 --snap-every 1` on EACH box
   under production env (hash-seed/arch differences are exactly what the gate
   exists to catch). Require PASS on all 3.
4. Flip `CARCASSONNE_USE_CY_LEAF=1` in the gen/eval launchers next to
   `CARCASSONNE_USE_FLAT_LEAF=1`, at an iteration boundary; keep
   `USE_FLAT_LEAF=1` as the fallback path (unset cy-flag = instant rollback).
5. Re-bench end-to-end self-play g/min per box (per the re-bench-after-code-era
   rule) and re-tune W if the leaf is no longer the per-worker bottleneck.
6. Close out per the checklist (results.csv if a throughput claim is recorded,
   DECISIONS line, STATUS).

## CLEAN BENCH ADDENDUM (2026-06-12 14:05 EDT, idle box — iter5 train window)

Re-run on a CPU-idle box (iter5 gen done, train is GPU-bound → cores free), so the
ratio is no longer load-contaminated and absolutes are trustworthy.

- **Isolated leaf ratio: 12.5× median** (tight 11.5–13.4× over 10 interleaved blocks;
  the earlier 14.3× was load-inflated). Absolutes: py **345 µs** → cy **27.5 µs** per leaf.
- **Leaf fraction of a real HeuristicMCTS@800 search: 27.4%** (`flat_virtual_score_v2`
  cumtime / total, cProfile over 24 plies @ sims=800, v2.7 flat leaf). `decompose` alone
  is the largest single tottime (2.71s). The engine board ops dominate the REST:
  `get_next_state`/`apply_action`/`state_updater` ≈ 39% cumtime, move-gen ≈ 24%.

### End-to-end deploy ROI (measured Amdahl, not the isolated 12.5×)
- Heuristic@800 search: 1/(0.726 + 0.274/12.5) = **1.34×** (the leaf-heavy eval opponent).
  Ceiling with an infinitely-fast leaf = 1/0.726 = 1.38× → **Cython already captures ~97%
  of the achievable leaf win**; no further leaf optimization is worth it.
- Gen (NeuralMCTS@800, GPU/IPC-bound; leaf ≈13% of wall from the flat_leaf +8%@2.26×
  calibration): ≈ **1.14×**.
- Train: leaf-free (GPU) → **1.0×**.
- **Weighted cycle (~eval 70% / gen 18% / train 12%): ≈ 1.23×** — shave ~18–20% off each
  ~8h cycle (~1.5h/cycle). Real but modest; the isolated 12.5× collapses because the leaf
  is only ~27% of even the most leaf-heavy phase, and gen/train are GPU-bound.

### The bigger lever this surfaced
The leaf is NOT the search bottleneck — the **engine** (board mutation + move generation,
~40%+ of the heuristic search) is. A perfect leaf caps the heuristic search at 1.38×; the
de-objectified-engine BACKLOG item attacks the dominant 40%. Cython-leaf is the cheap,
correctness-safe win; the engine rewrite is the real (but much larger) throughput lever.
