# Compact-leaf rewrite — AS-BUILT + validation report (2026-06-09)

Branch: `leaf-rewrite` (isolated worktree `/home/doctor/projects/carc-leafdev`).
Executed per [COMPACT_LEAF_REWRITE_PLAN_2026-06-09.md](COMPACT_LEAF_REWRITE_PLAN_2026-06-09.md).
**No benchmarking** (attempt-2 flywheel was live on the cluster). Correctness only.

## TL;DR

- The compact leaf is **logic-exact**: farm partitions, city partitions,
  `count_final_scores` `scores[]`, and the base `virtual_score` are **bit-identical**
  to production across **935,018 farm + 579,575 city partition checks + 14,400
  score checks + 28,800 base-value checks — 0 mismatches.**
- It is **not** automatically int-bit-exact at the `virtual_score_v2` boundary:
  **~2–12 / 28,800** leaf ints differ by **±1** (the exact count is itself
  hash-seed-dependent — see below). Root cause is **not** the compact logic — it
  is a **pre-existing float-order sensitivity in the v2.7 leaf**: the
  closure-anticipation bonus sums non-associative floats (0.2-multiples) in
  *set-iteration order*, which is arbitrary. Compact realizes a different valid
  order; max pre-round score drift = **~1.8e-15–3.6e-15** (≈1 ULP), which flips
  `int(round())` only where a score lands *exactly* on a `.5` boundary
  (min margin observed = 0.0, banker's-rounding tip).

- **⚠️ The production leaf is ALREADY non-deterministic across processes.** The
  bonus set order is keyed on enum hashes, and CPython randomizes enum/str
  hashing per process via `PYTHONHASHSEED`. So two self-play workers (different
  seeds) already compute different `virtual_score_v2` ints for the **same
  position** in ~1e-4 of evals — independent of compact. Evidence: identical
  gate config gave 2 flips in one process and 12 in another. The 2026-05-29 fix
  made `find_farm` start-independent but left this bonus-summation order
  hash-dependent. `CANONICAL_BONUS_SUM` (fsum) removes it → the leaf becomes a
  deterministic, well-defined function of the position. This is a genuine
  ruler-integrity improvement, not just a compact enabler.
- The clean closer is order-independent summation (`math.fsum`), added behind a
  default-OFF toggle `CANONICAL_BONUS_SUM`. With it on for both paths, compact is
  a **true bit-exact** drop-in (gate `--canonical`: 0 flips).
- All work is behind default-OFF toggles; production behavior is byte-identical
  when both toggles are OFF (full pytest suite green, OFF and ON).

## What was built (files, all on `leaf-rewrite`)

- **`src/carcassonne_ai/compact_leaf.py`** (new) — flat union-find decomposition.
  `build_farm_cache` / `build_city_cache` return fully-populated `_farm_cache` /
  `_city_cache` dicts in the EXACT format the engine already reads
  (`(row,col,id(FarmerConnection)) -> Farm` and `CoordinateWithSide ->
  (positions, finished)`). Enumerate nodes → flat int ids → edge lists →
  `_label_components` union-find (path-halving) → reconstruct the engine
  `Farm`/`City` objects. **Zero engine edits**: pre-populating those dicts means
  `FarmUtil.find_farm_by_coordinate` / `CityUtil.find_city` resolve every query
  as a hit, so the object-graph BFS never runs.
- **`src/carcassonne_ai/virtual_score.py`** — added `USE_COMPACT_LEAF = False`;
  `virtual_score` / `virtual_score_inplace` build the compact caches when on.
- **`src/carcassonne_ai/virtual_score_v2.py`** — `virtual_score_v2` pre-populates
  the shared caches via compact when on (shared into `virtual_score`'s snapshot —
  valid because the state's deepcopy shares Tile/FarmerConnection refs). Added
  `CANONICAL_BONUS_SUM = False` + order-independent `math.fsum` accumulation in
  `_closure_anticipation_bonus` (OFF path byte-identical).
- **`scripts/reconcile_compact_leaf.py`** (new) — the equivalence gate. Checks
  farm/city partitions vs the object BFS, `scores[]`, base `virtual_score`, and
  `virtual_score_v2` ints; audits closure-bonus float drift and the min rounding
  margin; classifies LOGIC mismatch (exit 1) vs ULP reorder (exit 3) vs bit-exact
  (exit 0). Flags: `--values-only`, `--canonical`.
- **`tests/test_compact_leaf.py`** (new) + **`tests/conftest.py`** (new, test-infra;
  `CARC_TEST_COMPACT_LEAF=1` runs the whole suite under the toggle ON).

## Validation results

Run from the worktree with `PYTHONPATH` forcing worktree imports (editable
installs point at the live tree), under the production v2.7 env
(`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`), `nice -n 19`.

| check | n | mismatches |
|---|---|---|
| farm partition (compact build == `find_farm`) | 935,018 | **0** |
| city partition (compact build == `_compute_city`) | 579,575 | **0** |
| `count_final_scores` `scores[]` | 14,400 | **0** |
| base `virtual_score` int | 28,800 | **0** |
| `virtual_score_v2` int (naive sum) | 28,800 | **2–12** (±1, ULP reorder; hash-seed-dependent) |
| `virtual_score_v2` int (`--canonical` fsum) | 28,800 | **0** (confirmed; drift 0.0, exit 0) |

- closure-bonus float drift: max **~1.8e-15–3.6e-15** (≈1 ULP), min `.5`-margin
  **0.0** → the flips are banker's-rounding tips at exact-half boundaries, not a
  logic error. Gate exit codes: naive → **3** (logic-equiv, reorder);
  `--canonical` → **0** (bit-exact).
- pytest: full suite green with toggle **OFF** (no regression); leaf-touching
  suite green with toggle **ON**; `tests/test_compact_leaf.py` green.

## Phase-0 findings (the traversal replaced)

The v2.7 leaf cost is dominated by two object-graph flood-fills:
`FarmUtil.find_farm` (connected components over `tile.farms` FarmerConnections
via `opposite_edge`/`opposite_farmer_side`, the 2026-05-29 start-independent
version) and `CityUtil._compute_city` (BFS over city edges via `opposite_edge`).
Both are already memoized per-component within a leaf eval by the lazy
`_farm_cache`/`_city_cache`; the compact path replaces the *per-component BFS +
temporary-object churn* with one whole-board flat union-find that fills those
same caches. Representation chosen: small int node ids + two parallel edge
arrays + a `parent[]` union-find, reconstructed into the engine's own
`Farm`/`City` value objects (so all downstream scoring is untouched).

## numba vs Cython

Neither applied yet — numba is **not installed** in the venv, and installing into
the shared `.venv` could perturb the live flywheel, so it was deliberately
deferred. The union-find core (`_label_components`) is written as a pure-int
kernel over parallel arrays specifically so it can be `@njit`-compiled (numba
`cache=True` to dodge per-worker warmup) or Cython-AOT'd in Phase 4 without
touching the enumeration/reconstruction. **The current pure-Python version is
correctness-complete but is NOT a measured speedup** — see below.

## ⚠️ Honest caveat: this is not yet a proven speedup

The whole point of the rewrite is to move the RAM-bandwidth wall. The current
pure-Python flat union-find still allocates the same engine wrapper objects
during enumeration/reconstruction and runs the union-find in interpreted Python,
so it may not beat the existing C-level set-based BFS until the core is compiled
(numba/Cython) and the enumeration is de-objectified. Whether it actually helps
throughput is a **Phase-4 benchmark question** (deferred: the box was busy and
benchmarking was explicitly out of scope). Do not assume a win from "logic-exact".

## Recommendation / open decision for Joshua

1. **Logic is proven equivalent** — safe to keep developing on this branch.
2. For a **true bit-exact** drop-in, adopt `CANONICAL_BONUS_SUM` (fsum). It also
   removes a latent ULP nondeterminism already in the v2.7 leaf (the bonus value
   currently depends on arbitrary cache-population order). BUT turning it on
   changes production's exact output vs the **currently-running** flywheel by the
   same ~7e-5 ±1 flips, so it must be a **deliberate, gated decision bundled with
   the compact merge (Phase 4)** — never flipped mid-flywheel.
3. **Phase 4 (after the flywheel, quiet box):** compile the union-find core,
   benchmark with `sweep_w_thermal.sh` / `scan_loww.sh` — success = the
   per-worker erosion curve flattens and saturation-W rises above 16, not merely
   "faster". Only then propose merge + bundle refresh.
