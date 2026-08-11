# Window-offset incremental tracking — report

**Branch:** `worktree-agent-aedf22c2f3ce51fd9`
**Status:** DONE — bit-identical, reconcile gate green (0 mismatches), tests green.
**Deploy:** correctness-safe (bit-identical) but it edits the LIVE working tree;
fold only at a clean boundary, re-running the reconcile gate on each box's code.

## The change

`board_repr.compute_window_offset(state, window_size)` centers the W×W window on
the centroid of placed tiles, computed by scanning the entire 35×35 board every
call. It was called on **every state transition** in `Game.get_next_state` (via
`Board.from_state`) and `Game.apply_action_inplace` — including every MCTS
rollout state — making it 8.6% of self-time in a heur@800 search (both gen and
eval paths).

Replaced the per-transition full scan with an **O(1) incremental centroid
tracker** on `Board`:

- New `Board` fields `sum_row`, `sum_col`, `tile_count` — the running sums of
  placed-tile coordinates. The offset is derived from them with the *exact* same
  rounding/centering math as the old scan.
- Key insight exploited: the centroid only moves when a **tile** is placed.
  Meeple actions and passes place no tile (engine: `StateUpdater.play_tile` is
  the sole writer of `placed_coords`), so on those plies the sums — and the
  offset — are unchanged. The decoded action is a `TileAction` iff a tile is
  placed; `Game._next_centroid_sums` adds `(row, col)` and `+1` only then.
- Seeded once by `Board.from_state` (a one-time scan via `centroid_sums`, which
  reads the engine-maintained `placed_coords` set — equivalent to the dense
  scan but cheaper, with a dense fallback for non-engine states).
- The math lives in ONE pure function, `board_repr.offset_from_centroid_sums`,
  which both the legacy `compute_window_offset` (now a thin scan→delegate) and
  the incremental path call — so the two can never drift.

### Correctness subtleties handled
- **Meeple-vs-tile:** only `TileAction` updates the sums; verified the engine
  adds to `placed_coords` exclusively in `play_tile`. Tile-phase **PassAction**
  (unplaceable tile discarded) places no tile and is correctly a no-op for the
  centroid.
- **Empty board:** the constructor places NO starting tile (board all-`None`,
  `placed_coords` empty); the first move is a `TileAction` placing `next_tile` at
  `starting_position`. `tile_count == 0` takes the `starting_position`-centered
  branch — matches the old scan's empty-board branch exactly.
- **Deepcopy / rollout:** `Board` is a plain dataclass with no custom
  `__deepcopy__`, so `copy.deepcopy(board)` (NeuralMCTS `_reshuffled_root`)
  copies the int sums trivially. The manual `Board(...)` build in
  `mcts._rollout` now forwards `sum_row/sum_col/tile_count`, so
  `apply_action_inplace` stays O(1)-correct down the rollout (else it would
  start from 0 and diverge after the first tile placed in the rollout).
- **External contract preserved:** `board.offset` is byte-for-byte the value the
  scan produced at every ply — it feeds action encode/decode, where a wrong
  offset would silently shift the action space.

## Reconcile gate (the proof)

`scripts/reconcile_window_offset.py` plays N seeded random games to the end; at
**every ply**, along BOTH `get_next_state` (new-Board) and `apply_action_inplace`
(rollout) paths, it asserts the incremental `board.offset` AND the underlying
`(sum_row, sum_col, tile_count)` are exactly equal to a fresh full-scan
`compute_window_offset` / `centroid_sums`.

| run                       | games | plies (tile / meeple)   | inplace steps | checks | mismatches |
|---------------------------|-------|-------------------------|---------------|--------|------------|
| `--n 40 --seed 0`         | 40    | 5758 (2880 / 2878)      | 5718          | 23032  | **0**      |
| `--n 100 --seed 1000`     | 100   | 14385 (7200 / 7185)     | 14285         | 57540  | **0**      |
| **total**                 | 140   | 20143 (10080 / 10063)   | 20003         | 80572  | **0**      |

**0 mismatches** across 140 games / ~80.6K offset+sums comparisons, full games to
completion (tile AND meeple plies, multiple seed bases, the late-game tail).

### Existing tests
- `pytest tests/ -k "offset or board_repr or wrapper or window"` → **43 passed**.
- `pytest tests/ -k "mcts or rollout or selfplay"` → **93 passed** (covers the
  rollout Board-construction change).

## Bench (interleaved A/B; absolute ns are flywheel-contaminated, ratios are not)

`scripts/bench_window_offset.py --games 6 --reps 4`:

**[1] per-call offset computation** (realistic mid/late-game state distribution):
- incremental: **0.76 us/call**
- full scan:   **3.25 us/call**
- **speedup: 4.27×**

**[2] whole `get_next_state`** (same action sequences):
- incremental: 34.7 us/transition
- full scan:   36.2 us/transition
- **speedup: 1.04×** — the offset is a small slice of the safe-path transition
  (dominated by `apply_action`'s deepcopy). The win concentrates on the
  **inplace rollout path** (no deepcopy), which is where the 8.6%-self-time
  measurement was taken.

**Offset cost vs board size** (the scan grows, incremental is flat):

| placed tiles | incremental | full scan | speedup |
|--------------|-------------|-----------|---------|
| 0–9          | 0.82 us     | 1.53 us   | 1.87×   |
| 20–29        | 0.81 us     | 2.35 us   | 2.91×   |
| 40–49        | 0.82 us     | 3.32 us   | 4.07×   |
| 60–69        | 0.82 us     | 4.23 us   | 5.19×   |
| 70–79        | 0.84 us     | 4.53 us   | 5.42×   |

Incremental is O(1)-flat (~0.8 us); the scan is O(board area), so the win climbs
to **5.4× late-game**, exactly where MCTS rollout traffic and leaf evals
concentrate.

## Files changed

- `src/carcassonne_ai/board_repr.py` — added `offset_from_centroid_sums` (pure
  offset math) + `centroid_sums` (seed scan, `placed_coords`-based with dense
  fallback); `compute_window_offset` now delegates to them (single source of
  truth).
- `src/carcassonne_ai/game_wrapper.py` — `Board` gains `sum_row/sum_col/
  tile_count`; `from_state` seeds them; `get_next_state` + `apply_action_inplace`
  carry them forward O(1) via the new `_next_centroid_sums`; imports `TileAction`.
- `src/carcassonne_ai/mcts.py` — `_rollout` scratch `Board(...)` forwards the
  centroid sums.
- `scripts/diag_value_leaf.py` — diag now builds its scratch board via
  `Board.from_state` (seeds sums; a bare `Board(...)` would have left them 0 and
  diverged the offset). Diagnostic-only; not a production path.
- `scripts/reconcile_window_offset.py` — **new**, the validation gate.
- `scripts/bench_window_offset.py` — **new**, the interleaved A/B bench.

## Fold note

Bit-identical → correctness-safe; no retrain/re-eval needed (offsets, action
encode/decode, board tensors all unchanged). BUT it edits the live working tree
the flywheel reads, so:
1. fold only at a **clean boundary** (no self-play/eval mid-iteration reading the
   changed files),
2. re-run `scripts/reconcile_window_offset.py` on **each of the 3 boxes' code**
   after the bundle-sync (the standard offline sync), confirming 0 mismatches
   before relying on it,
3. re-bench W after deploy if desired (per the flat-leaf-era note in CLAUDE.md;
   this is a pure speedup and doesn't change the W bottleneck shape).
