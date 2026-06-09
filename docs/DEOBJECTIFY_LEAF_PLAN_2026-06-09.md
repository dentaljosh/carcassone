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

## As-built (executed 2026-06-09, worktree `carc-leafdev` @ leaf-rewrite)

Module: `src/carcassonne_ai/flat_leaf.py` (default-OFF `USE_FLAT_LEAF`). Gate:
`scripts/reconcile_flat_leaf.py`. Benches: `scripts/stage0_leaf_breakdown.py`,
`scripts/microbench_flat_leaf.py`. All run with the flywheel live (worktree
isolation, `nice -n 19`, no live-tree edits, no bench on the busy box — only
relative/min-of-reps micro-benches + the CPU-light gate).

- **Stage 0 leaf-OFF breakdown — OVERTURNED THE PLAN'S PREMISE.** Per-leaf split
  (compact OFF = production, n=1160 states): **deepcopy = 0.9%**, **count_final_scores
  = ~90%**, **closure bonus = ~12%**. The plan assumed deepcopy was ~75%; the
  custom `__deepcopy__` (shares Tile/FarmerConnection refs) already made it ~free
  (0.008 ms/leaf). The real lever is `count_final_scores` (the flood-fill
  scoring), NOT the deepcopy. cProfile of count_final_scores: `find_farm`
  (~1.6–1.8s), city flood (~1.2s), `find_road` (~0.3s), `get_winning_players`
  (~0.65s), pervasive `hash`/Coordinate churn — exactly what flat int arrays kill.
- **Stage 1 flat components — BIT-EXACT.** One board pass → int union-find for
  city/road/farm. Gate vs engine `find_farm` / `_compute_city` / `find_road`:
  **935,018 farm + 579,575 city + 700,424 road partition checks, 0 mismatches**
  (n=400). Road geometry mirrors city `opposite_edge`; intra-tile road union =
  both non-CENTER ends of a `Connection`.
- **Stage 2 flat base score — BIT-EXACT (pure int).** `flat_base_score` replaces
  deepcopy + count_final_scores. Gate: **28,800 base evals + 14,400 final-addition
  checks, 0 mismatches** (n=400). Key correctness details reproduced: farm meeple
  count via `farmer_positions[0]` (find_meeples), unmeepled features score 0,
  tied-feature → all winners, farm pts = 3×distinct finished adjacent city
  components, cathedral/inn variants, base diff = running-score diff + final-add diff.
- **Stage 3 flat closure bonus + full flat v2 — BIT-EXACT (canonical sum).**
  `flat_closure_bonus` + `flat_virtual_score_v2`, summed with `math.fsum`
  (CANONICAL_BONUS_SUM semantics — well-defined, hash-seed-independent). Gate vs
  engine under CANONICAL_BONUS_SUM=True: closure-bonus float + full v2 int both
  **0 mismatches** (n=20 smoke: 1440 each; full n=400 in flight, clean at 160/400).
  Bonus uses `find_farm_by_coordinate` semantics (membership by ANY
  `farmer_positions`, not just [0]) — separate map from base. Only the v2.7
  schedule path is implemented; a cfg requesting tile-counting/continuous raises.
- **Per-leaf speed (relative micro-bench, min-of-reps, n=1160 states):**
  **FLAT 0.547 ms/leaf vs OFF 1.021 ms/leaf = 1.87× faster, INTERPRETED** (pure
  Python, no compile). Compare: the compact attempt was 1.10× SLOWER. The
  de-objectification worked. Remaining cost is dominated by **enum hashing**
  (`enum.__hash__` + `hash` ≈ 0.95s of `decompose`'s 1.84s self-time) from
  `(r,c,Side)` tuple dict keys → Stage 4's first lever is INT-ENCODING the sides
  (Side 0–4, FarmerSide 0–7, pack `(r,c,side)` to one int), THEN numba on the
  now-pure-int `_label_components` + decompose.
- **Stage 4a int-encode (pure Python, no deps) — BIT-EXACT, 2.04×.** Replaced the
  hot internal dict keys + geometry (`_OPP`/`_FS_STEP`/`_FS_OPP`) with int side
  codes (`_SIDE_IX`/`_FS_IX`/`_IX_SIDE`); public Decomp dicts stay enum-keyed
  (touched O(nodes)+O(meeples) only). Enum hashes 4.1M→2.3M; 0.547→0.451 ms/leaf.
- **Stage 4b per-tile feature cache (pure Python, no deps) — BIT-EXACT, 2.26×.**
  `_tile_features` memoises the enum→int conversion per unique Tile
  (WeakKeyDictionary; ~80 distinct rotated tiles/game) so it's out of the per-leaf
  hot path. Enum hashes 2.3M→1.1M; 0.451→**0.400 ms/leaf vs OFF 0.903 = 2.26×**,
  all in pure Python. Profile is now an even spread (dict.get/append/_label_components/
  set.add); no single dominant cost. Committed.
- **Stage 4c compile (numba, isolated venv) — PROVEN, DEPLOYMENT DEFERRED.**
  Isolated venv `/tmp/numba_proto_venv` (numba 0.65.1 / numpy 2.4.6; shared venv +
  flywheel untouched). `scripts/prototype_numba_labels.py` captured 2610 real
  union-find calls (mean n=52 nodes / 68 edges) and benched `@njit`
  `_label_components` vs pure-Python: **0 label mismatches**, numba **3.21× faster
  WITH list→ndarray conversion** (14.5→4.5 µs/call), **10.7× kernel-only** (1.35
  µs/call). So numba-the-core is a bit-exact drop-in win. BUT `_label_components`
  is only ~10% of the leaf → numba-core alone moves it ~2.26×→~2.45×; and
  **`flat_leaf.py` is kept pure-Python** (no `import numba`) because the shared
  venv has no numba and installing it bumps numpy 2.4.4→2.4.6, which would
  contaminate the running strength experiment. DEPLOY decision (post-flywheel):
  either pin numpy when adding numba, or AOT-Cython the kernel (gcc present, no
  numpy-version risk). The BIG numba payoff (the bandwidth wall) is the full
  array-based decompose rewrite — pairs with Stage 5 on a quiet box.
- **Stage 5 throughput / bandwidth-wall verdict:** DEFERRED to a quiet box (see
  above). Success = moves the per-worker erosion curve / raises saturation-W.

### Net result (interpreted, shared-venv-deployable TODAY): 2.26× faster per leaf, bit-exact (n=400 gate). numba adds a further proven ~1.4× on the core when deployable.

## Adversarial code-review audit (2026-06-09, 18 agents)

Multi-agent review (5 dimensions → per-finding adversarial verify → synthesis).
**Verdict: the bit-exact claim HOLDS in production (2p Base+Farmers, v2.7,
DEFAULT_CONFIG, canonical sum) — ZERO reachable flat≠engine bugs.** The 2.26×
speedup is sound and *conservative* (the microbench times flat's `math.fsum`
against OFF's cheaper running-sum, which only biases against flat). 8 findings,
all reproduced; the cluster was gate *over-certification*, not leaf correctness.

Fixes applied (commit after the hardened n=400 re-gate):
- **[HIGH] gate exit-0 on undersampled runs** → `reconcile_flat_leaf` now reserves
  exit 0 for a full acceptance pass: undersampled (`< --min-evals`, default 10k) →
  **exit 3**, values-only → **exit 4**, never prints "BIT-EXACT" for either.
- **[MED] config corners never tested** (DEFAULT_CONFIG has meeple_k=0, equal caps)
  → added **check 8: full v2 under ALT_CONFIG** (meeple_k=0.5, caps 8/4) so the
  economy term + asymmetric cap clamp are exercised. Passes 0-mismatch.
- **[MED] `--values-only` over-certified** → distinct banner + exit 4 (above).
- **[LOW] farm check-1 fallback masked a missing `pos0` entry** → removed the
  fallback (missing entry now FAILS) and added an explicit `farm_anypos_root`
  (bonus-membership) check per farmer_position.
- **[LOW] cathedral/inn/big-meeple gate-unreachable** → already covered by
  `tests/test_flat_leaf_edge_cases.py` (the audit ran it, 2/2 pass); PASS banner
  now cross-references it.
- **[LOW] stage0 "overhead" bucket** → relabelled "residual (timing noise)", no
  longer clamped to 0 (it's a 3-timing residual, ~±few %, not a real cost).

Remaining (latent, non-production): `flat_closure_bonus` raises
`NotImplementedError` for the deck-aware closure configs (`tile_counting_closure`
/ `closure_continuous_slack`), where the engine returns a valid (different) value.
Fail-loud, v2.7 has both OFF, and `USE_FLAT_LEAF` has no callers — so unreachable
today. **WIRING-TIME REQUIREMENT:** when `USE_FLAT_LEAF` is wired into production,
assert both deck-aware flags are OFF at the wiring point (or implement those paths)
so a config combo can't crash every leaf eval.
