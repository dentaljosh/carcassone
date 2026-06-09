# De-objectified flat leaf — build + validation plan (2026-06-09)

> **POST-COMPACTION: START HERE.** Self-contained; the executor has NO memory of
> the conversation that produced it. Read this whole file, then `git log`, then
> the as-built ([COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md](COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md)),
> then the leaf source, before writing any code.

## Where things stand (read first)

- You are in the **worktree `/home/doctor/projects/carc-leafdev`, branch
  `leaf-rewrite`** (HEAD ≈ `156a5f1`). The live tree `/home/doctor/projects/carcassone`
  is on `stage-b-wiring` and a multi-hour **attempt-2 flywheel is RUNNING** on the
  cluster. Same hard constraints as before (below).
- The previous attempt (the "compact" flat union-find, `src/carcassonne_ai/compact_leaf.py`,
  behind `USE_COMPACT_LEAF`) is **logic-exact but a ~10% per-leaf REGRESSION** —
  proven dead by `scripts/microbench_compact_leaf.py`:
  `OFF 0.992 ms/leaf vs compact-ON 1.088 ms/leaf`. cProfile of the build: the cost
  is **Python `dict.get` + enum hashing + Coordinate/CoordinateWithSide/
  FarmerConnectionWithCoordinate construction** — the `(row,col,FarmerSide)`-keyed
  enumeration dicts and the engine-object reconstruction. The union-find core
  `_label_components` is only **4.6%** of build self-time, so numba-on-the-core is
  worthless. Compact still (a) reconstructs engine `Farm`/`City` objects and (b)
  leaves `virtual_score`'s per-leaf `copy.deepcopy` + `count_final_scores`
  mutation in place — it never attacked the two biggest costs.

## The goal of THIS project (why it can win where compact couldn't)

Build a **flat-array leaf** that computes `virtual_score_v2(state, player, cfg)`
**directly from a compact int encoding of the board**, with:
1. **NO `copy.deepcopy`** — `count_final_scores` deepcopies because it MUTATES
   (removes meeples, adds scores). A flat scorer computes the score differential
   without mutating → the per-leaf deepcopy disappears. (Deepcopy was historically
   ~75% of self-play wallclock pre-patch; even patched it's a real per-leaf slice
   — Stage 0 measures exactly how much.)
2. **NO engine `Farm`/`City`/`FarmerConnectionWithCoordinate`/`CoordinateWithSide`
   objects and NO enum-keyed dicts** — flat int ids + contiguous arrays end to
   end (this is what compact failed to do; it's where the time goes).
3. **Bit-exact / logic-exact to the current engine leaf** — gated, mandatory.

If done, the kernels become pure-int over arrays, so Stage 4 (numba/Cython) FINALLY
helps, and the whole thing is cache-friendly → actually moves the RAM-bandwidth
wall (the original motivation, DECISIONS 2026-06-09 bandwidth entry).

This is a **substantial, multi-stage rewrite, not a compile step.** It is a
self-play/eval THROUGHPUT lever only (training is GPU-bound; the leaf also caps
*strength* near strong-human by construction — orthogonal). Stage-gate it and
bail at the first stage whose measured payoff doesn't justify the next.

## ⚠️ HARD SAFETY CONSTRAINTS (unchanged — a flywheel is live)

1. **Work ONLY in this worktree on `leaf-rewrite`.** Never edit the live tree
   `/home/doctor/projects/carcassone` (the flywheel re-imports the leaf from it).
2. **No commits to `stage-b-wiring`, no git-bundle refresh** while the flywheel runs.
3. **No throughput benchmarking until a quiet box** (a busy box gives contended
   garbage AND competes for the bandwidth under study). DEV + the equivalence gate
   are CPU-light and coexist fine at `nice -n 19`. The throughput bench (Stage 5)
   waits for the flywheel to finish or a deliberate iter-boundary pause.
4. **Do NOT `pip install` into the shared `.venv`** (numpy bump would contaminate
   the running strength experiment when its next phase spawns fresh Python). For
   numba/Cython in Stage 4, use an **isolated venv** (`python -m venv` with
   numpy+numba, run via PYTHONPATH to the worktree) or Cython AOT (build tool, no
   numpy-version risk). The equivalence gate + Stages 0-3 need NO new packages.
5. **The leaf IS the measurement ruler.** Bit-exact equivalence gate is MANDATORY
   and gates everything. New code lives behind a default-OFF toggle until validated.

## Assets you already have (don't rebuild)

- **Equivalence gate harness:** `scripts/reconcile_compact_leaf.py` — drives
  diverse seeded real positions, compares a candidate leaf path vs the engine
  ground truth (`FarmUtil.find_farm`, `CityUtil._compute_city`,
  `PointsCollector.count_final_scores`), audits float drift, classifies
  logic-mismatch vs ULP-reorder, and (review fix) checks the production wrapper
  path via `check_wrapper_path`. **Extend it (or clone its harness) to validate the
  flat leaf** — reuse `collect_states`, the coverage assertions, the wrapper check.
- **Geometry, validated:** `compact_leaf.py` `_CITY_OPP` / `_FARMER_STEP` +
  `SideModificationUtil.opposite_farmer_side` reproduce the engine opposite-edge
  exactly (gate-proven). Reuse the geometry; replace the dict/object machinery.
- **Micro-bench:** `scripts/microbench_compact_leaf.py` (relative per-leaf, no
  pause). Adapt for the flat leaf to track progress without a quiet box.
- **Toggle pattern:** `virtual_score.USE_COMPACT_LEAF` / `virtual_score_v2.
  CANONICAL_BONUS_SUM` + the wrapper wiring in `evaluators.py` /
  `features.encode_farm_scalars` (review-fixed to thread the toggle through).
  Add a NEW default-OFF toggle `USE_FLAT_LEAF`; thread it the same way (and the
  gate's `check_wrapper_path` already guards the wrapper path — extend it).
- **Engine ground truth + equality semantics** (from the compact Phase-0):
  `engine/wingedsheep/carcassonne/utils/{farm_util,city_util,road_util,points_collector,
  side_modification_util}.py`, `objects/*.py`. Key facts: City/Farm scoring lives
  in `PointsCollector.count_final_scores` (cities/roads via `remove...`/per-meeple,
  farms, cloisters); tied features score full to ALL tied players (vendored patch);
  farm cities deduped by `frozenset(city_positions)`; `find_farm` start-independent
  (TRT→BRB involution); D16 = board-edge city with 0 in-bounds open positions earns
  no closure bonus; closure_p = {1:0.5, 2:0.2} at v2.7 (CAP=12, DROP_THREE_OPEN).

## How to run code (worktree imports + production env)

Editable installs point at the LIVE tree — force the worktree:
```
PYTHONPATH=/home/doctor/projects/carc-leafdev/src:/home/doctor/projects/carc-leafdev/engine \
CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \
nice -n 19 /home/doctor/projects/carcassone/.venv/bin/python <script>
```
Verify at runtime that `carcassonne_ai.__file__` and `wingedsheep.__file__` contain
`/carc-leafdev/`.

## Staged build (cheapest-informative-first; bail at any stage that doesn't pay)

### Stage 0 — MEASURE the leaf-OFF cost breakdown (do FIRST, no code change)
Profile the PRODUCTION leaf path (`virtual_score_v2`, compact OFF) to split the
per-leaf budget across: (a) `copy.deepcopy`, (b) `count_final_scores` flood-fills +
scoring, (c) the two `_closure_anticipation_bonus` passes. cProfile + a timed
harness over diverse states (extend `microbench_compact_leaf.py`). **This decides
where to invest.** Likely outcome: deepcopy + count_final_scores dominate → Stage 2
(flat base score, no deepcopy) is the big lever; the closure bonus (Stage 3) is
secondary. If deepcopy is small, re-think scope. Write the numbers into this doc's
"As-built".

### Stage 1 — flat board encoding + flat connected components (no objects)
One pass over the board → flat int arrays: per (row,col) tile features encoded as
small ints (city groups, road groups, farm connections, cloister flag, shield/inn,
meeple owner+type per side). Build farm/city/road components with int union-find
(reuse `compact_leaf._label_components`; key adjacency by **int** ids, NOT
enum-tuple dicts — index a flat `(row*W+col)*NSIDES+side` array). Output: per-component
membership + per-component facts (size, shields, finished, meeple counts per player,
adjacent-finished-cities for farms). Gate: these flat facts must match the engine's
per-feature facts on every component (extend the reconcile gate's partition checks).

### Stage 2 — flat BASE score (replace deepcopy + count_final_scores)
From the Stage-1 flat facts, compute `scores[player] - scores[opp]` exactly as
`count_final_scores` would — cities (2/tile+2/shield finished, 1+1 unfinished;
cathedral 3/6; tied→all tied players), roads (1/tile, inn 2/tile), farms (3 per
distinct finished adjacent city, deduped), cloisters (1+surround, 9 finished),
meeple-majority per feature. **No mutation, no deepcopy.** Gate: `base_flat ==
virtual_score(state, p)` bit-exact over ≥10k positions incl. all edge cases.
Re-bench (Stage 0 harness) — this is where the deepcopy win shows up.

### Stage 3 — flat CLOSURE bonus (replace `_closure_anticipation_bonus`)
Flat version of the self/opp closure-anticipation bonus from Stage-1 facts
(open-position counts per incomplete city/cloister, farm-growth cities, dedup by
component, caps). Use order-independent accumulation (the `CANONICAL_BONUS_SUM`
fsum lesson) so it's deterministic. Gate: full `virtual_score_v2` (flat) ==
engine v2 — bit-exact under canonical sum (the naive-sum path has the known
hash-seed ULP reorder; target canonical for the flat leaf from the start).

### Stage 4 — compile the pure-int kernels (isolated venv / Cython)
Only NOW does compilation help (everything is flat int). numba `@njit cache=True`
(warm-once at import to dodge per-worker JIT) or Cython AOT. Isolated venv per
constraint #4. Re-gate (compiled == interpreted == engine).

### Stage 5 — throughput bench (DEFERRED to a quiet box)
`sweep_w_thermal.sh` + `scan_loww.sh`, flat-leaf ON vs OFF. **Success = it MOVES
the bandwidth wall** (per-worker erosion curve flattens, saturation-W rises above
16), not merely "faster". If yes AND bit-exact → propose merge to `stage-b-wiring`
+ bundle refresh + `eval_provenance.py` wiring as a SEPARATE decision.

## Risks / kill-criteria
- **Reimplementing engine scoring exactly is the hard part** (tied-feature rule,
  farm dedup, D16, cathedral/inn, cloister, meeple majority incl. big-meeple=2).
  The existing gate de-risks it — drive ≥10k diverse positions + all edge cases
  before trusting a stage. Bit-exact or it doesn't ship.
- **Payoff capped by what's left.** If Stage 0 shows deepcopy+flood-fills are a
  small fraction, the whole project's ceiling is low — bail. Don't sink days into
  a 5% win.
- **Float order:** target `CANONICAL_BONUS_SUM` semantics (fsum / fixed order)
  for the flat closure bonus so it's deterministic and bit-exact.
- **Scope creep into the engine:** keep the flat leaf as an ADDITIVE module
  (`src/carcassonne_ai/flat_leaf.py`) behind `USE_FLAT_LEAF`; do not modify engine
  scoring — reproduce it. The engine stays the ground-truth oracle for the gate.

## As-built (fill in during execution)
- _Stage 0 leaf-OFF breakdown (deepcopy / count_final_scores / closure):_ TBD
- _Stage 1 flat encoding + component facts gate:_ TBD
- _Stage 2 flat base score gate + bench delta:_ TBD
- _Stage 3 flat closure bonus gate:_ TBD
- _Stage 4 compile (numba/Cython) result:_ TBD
- _Stage 5 throughput / bandwidth-wall verdict:_ TBD
