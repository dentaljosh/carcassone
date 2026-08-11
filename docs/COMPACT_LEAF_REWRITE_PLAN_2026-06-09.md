# Compact-leaf rewrite — build + validation plan (2026-06-09)

> ⚠️ **EXECUTED 2026-06-09 → then SUPERSEDED.** Execution record:
> [COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md](COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md)
> (logic-exact but ~10% per-leaf regression). The compact approach lost to the de-objectified
> **flat_leaf** ([DEOBJECTIFY_LEAF_PLAN_2026-06-09.md](DEOBJECTIFY_LEAF_PLAN_2026-06-09.md),
> deployed 2026-06-09); the Phase-2 "prototype with numba" recommendation was KILLED 2026-06-11
> (core ~4.7% of build self-time). Kept for the safety constraints + acceptance criteria record.

> **POST-COMPACTION: START HERE.** This is a self-contained plan. The executor is assumed to
> have NO memory of the conversation that produced it. Read this whole file, then `git log`,
> then the leaf source, before writing any code.

## Context — why this exists

Self-play throughput on the 5900XT is **RAM-bandwidth-bound**, not core/thermal/OOM-bound
(full evidence: DECISIONS.md entry **2026-06-09**). The bottleneck is the v2.7 CPU leaf, which
is Python-object **pointer-chasing** (board/farm/city graph traversal over heap-scattered
objects) → near-zero cache locality → every traversal step is a DRAM fetch using a fraction of
each 64-byte line. With ~16 workers their combined cache-miss traffic saturates the dual-channel
DDR4 bus (~40 GB/s, measured), so per-worker throughput erodes from W=4 onward and aggregate
peaks at W≈16. The cores are NOT the limit (a clean in-cache SIMD bench scaled +40% to 32 threads).

**The rewrite goal:** replace the hot leaf's pointer-chasing with a **compact, contiguous
(flat-array) representation** so it moves far less DRAM traffic per evaluation. Expected payoff:
(a) each worker faster, AND (b) the bandwidth-saturation point moves above W=16 → the idle cores
finally help self-play. This is the one box-agnostic perf lever (helps the whole cluster) and it
dominates buying X3D / faster RAM. Governs the two CPU-MCTS phases (self-play gen + eval); training
is GPU-bound and unaffected.

## ⚠️ HARD SAFETY CONSTRAINTS (a flywheel run, "attempt-2", may be live on this cluster)

1. **Work ONLY in an isolated git worktree.** NEVER edit the leaf in the live working tree
   `/home/doctor/projects/carcassone` — the running flywheel spawns fresh Python every phase and
   re-imports the leaf from the local tree (`gen_flywheel.sh` skips the git-reset for HOST=5800x),
   so a live edit would silently corrupt the strength experiment or crash a phase.
   Create: `git worktree add /home/doctor/projects/carc-leafdev -b leaf-rewrite HEAD`
2. **Do NOT commit to `stage-b-wiring` and do NOT refresh the git bundle** while the flywheel runs
   — its code-sync depends on that branch state. All work stays on the `leaf-rewrite` branch.
3. **Do NOT benchmark throughput.** The box is a busy cluster worker → any number is contended
   garbage AND competes for the bandwidth under study. Validation here is **correctness only**.
   Benchmarking is DEFERRED to a quiet box after the flywheel finishes (Phase 4).
4. Keep any test/validation execution `nice -n 19` and modest (a gate run, not 16×N workers).
5. **The leaf IS the measurement ruler.** This repo spent a major effort making strength evals
   trustworthy (clean-eval provenance, farm-dedup fix). A subtle behavior drift silently corrupts
   every downstream strength number. A **bit-exact equivalence gate is MANDATORY** (Phase 1) and
   gates everything. New code lives behind a default-OFF toggle until validated.

## Phase 0 — understand the code (read-only; trust the documented profile, don't re-bench)

Read and map, in the worktree:
- `src/carcassonne_ai/virtual_score.py` — `virtual_score`, `virtual_score_v2`, the
  `_farm_cache`/`_city_cache` lazy-memo mechanism (`USE_FARM_CACHE`/`USE_CITY_CACHE`), and how
  `count_final_scores` / the 12 scalars are computed.
- `engine/.../farm_util.py` — `find_farm` / `find_all_farms` (the connected-component traversal;
  **#1 hot path, ~58% of leaf cost** per the 2026-05-17 profile — trust it, don't re-profile on
  the busy box). Note the C1 dedup: touched cities deduped by `frozenset(city_positions)`.
- `engine/.../city_util.py` — `find_city` (same traversal pattern, has `_city_cache`).
- `src/carcassonne_ai/board_repr.py` / `features.py` — how the board is already encoded to arrays
  (possible reuse for the flat representation).
- The known edge cases to preserve exactly: **D16** (board-edge unfinished city with 0 in-bounds
  open positions → no 100% closure bonus), tied-feature scoring, the farmer-adjacency involution
  (`opposite_farmer_side` TRT→BRB), River dropped (base-only, DECK_NORM 72).

Output of Phase 0: a 1-paragraph note in this doc's "As-built" section on the exact traversal to
replace and the representation chosen.

## Phase 1 — the equivalence gate FIRST (the long pole; build before rewriting)

This is the de-risking deliverable. Build `scripts/reconcile_compact_leaf.py` (model it on the
existing `scripts/reconcile_farm_index.py` + `scripts/verify_farm_dedup_fix.py`, which already do
exactly this pattern for the farm-cache work):
- **Drive diverse real positions:** play K seeded base-only games (reuse the harness in
  `verify_farm_dedup_fix.py`, which generated 876 farms over n=150 games), snapshotting states
  across early/mid/late game. Ensure coverage of: large multi-tile farms, contested fields,
  completed vs open cities, **board-edge cities (D16)**, tied features, empty-feature boards.
- **Compare OLD vs NEW leaf** on every position, asserting equality of:
  - `virtual_score` AND `virtual_score_v2` final scalars (both code paths),
  - and, for stronger coverage, the **sub-quantities** (per-player farm score, city score, the
    12 scalars) — a final-scalar match can hide compensating errors.
- **Acceptance:** **bit-exact** on ≥10k positions incl. all edge cases. If operation-reorder makes
  bit-exact impossible, fall back to `|Δ| < 1e-9` AND additionally prove strength evals are
  unaffected (a much higher bar — prefer to engineer for bit-exact: same summation order, same
  float ops). Toggle `USE_COMPACT_LEAF` selects the path; the gate runs both.

## Phase 2 — the rewrite (behind a default-OFF toggle `USE_COMPACT_LEAF`)

Approach (refine after Phase 0):
- Replace the object-graph traversal in `find_farm`/`find_city` with a **flat-array
  connected-components / union-find**: assign each (tile-position, segment) a small int id; build
  adjacency as contiguous int arrays (CSR-style neighbor lists, or a fixed (row,col,segment)
  index); run **union-find with path compression on a flat `parent[]` int array** (extremely
  cache-friendly) instead of dict/set/object hopping. Preserve the C1 dedup logic exactly on the
  compact rep.
- **Implementation choice:** prototype with **numba `@njit`** on numpy int arrays (no build step,
  fastest to a passing gate). For production, evaluate **Cython AOT** to avoid per-worker JIT
  warmup (16 workers each JIT-compiling on first call would hurt; mitigate via numba cache=True,
  a warm-once-at-import call, or Cython). Note the tradeoff in As-built.
- Keep it **additive and reversible**, behind `USE_COMPACT_LEAF` (default **False**), exactly like
  `USE_FARM_CACHE`. Composes with the existing caches (or replaces them — decide in Phase 0).

## Phase 3 — validate (NO benchmark)

- Run `scripts/reconcile_compact_leaf.py` with the toggle ON → must pass (Phase 1 acceptance).
- Run the existing pytest suite in the worktree (`tests/test_farm_dedup_c1.py`,
  `test_mcts_transposition_c2.py`, `test_semantic_eval_contracts.py`, `test_eval_provenance.py`,
  the symmetry/aug tests) → all green with the toggle both OFF (no regression) and ON.
- Run `scripts/verify_evaluator_provenance.py` if the leaf path is provenance-tracked.
- **STOP HERE.** Do not measure throughput. Report: gate result, suite result, lines changed,
  and the As-built note. Leave everything on the `leaf-rewrite` branch, uncommitted-to-mainline.

## Phase 4 — DEFERRED to after the flywheel (Joshua's call, quiet box)

Only once the cluster is free:
1. Benchmark with the existing tooling: `scripts/sweep_w_thermal.sh` + `scripts/bw_scaling.py`
   (the arithmetic-intensity check). **Success criterion is not just "faster"** — confirm it
   **moves the bandwidth wall**: the per-worker erosion curve should flatten and the saturation W
   should rise above 16 (re-run `scripts/scan_loww.sh`).
2. If it's BOTH provably-equivalent AND meaningfully faster → propose merge to `stage-b-wiring` +
   bundle refresh as a SEPARATE decision. Wire into `eval_provenance.py` if it becomes production.

## Risks / open questions
- The leaf may be deeply entangled with engine `Tile` objects → a full de-objectify could be large.
  Pragmatic 80/20: rewrite only the `find_farm`/`find_city` traversal on a flat adjacency array,
  leave the surrounding scoring in Python.
- numba per-worker JIT warmup could erase gains at sims=200 → measure warmup, prefer Cython AOT or
  numba cache if so (Phase 4 question).
- Float exactness under op-reorder (see Phase 1 acceptance) — engineer for bit-exact.
- Equivalence ≠ correct production wiring — provenance integration is a Phase 4 item.

## As-built (fill in during execution)
- _Phase 0 findings:_ TBD
- _Representation chosen:_ TBD
- _numba vs Cython:_ TBD
- _Gate result (positions, pass/fail, exact vs epsilon):_ TBD
