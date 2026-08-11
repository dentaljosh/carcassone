# Window-overflow audit — PRE-REGISTRATION (Phase 0.2, measurement-only)

Status: PRE-REGISTERED 2026-07-05, BEFORE any number was measured. Single
read-out at the pre-registered n. No threshold-moving after seeing data.

## The bug class being measured

`src/carcassonne_ai/game_wrapper.py::get_valid_moves` builds the legal-action
mask by encoding each engine action into a centered `window_size × window_size`
grid (production `window_size = 25`). Any legal action whose encoded index
overflows the window is **silently dropped** (`except WindowOverflowError:
n_overflow += 1; continue`). It only RAISES if **every** legal action overflows
(`n_overflow == n_total`); a partial drop is invisible. Separately,
`board_repr.encode_board` / `get_canonical_form` silently skip any *placed tile*
that falls outside the window (the position simply isn't encoded into the board
tensor the net sees). Neither effect has ever been measured.

## Instrumentation (shipped, flag-gated, default OFF)

- `CARCASSONNE_WINDOW_AUDIT=1` (env, read at import; default off). When set,
  `get_valid_moves` appends one per-decision record to a module buffer:
  `{phase, n_total, n_overflow, k_remaining, n_oow_tiles, window_size}`.
  `n_oow_tiles` = placed tiles outside the window (what `encode_board` skips),
  computed by a read-only helper that mirrors `board_overflows_window`.
- When the flag is unset the audit block is skipped entirely. Verified
  bit-exact: `scripts/window_audit/verify_bitexact.py` plays a fixed seeded set
  of games and the SHA256 over every returned mask is IDENTICAL with the flag
  off (0 records) vs on. The instrumentation never mutates the returned mask.

## Data source

Real archived production/eval games with full `(deck_seed, action_sequence)`,
replayed losslessly via `scripts/measurement_infra/root_replay.py`. Preferred
over synthetic: they carry the true spatial spread of strong play. If < 2000
usable full games are found archived, top up by generating champion-config
self-play games (leaf env below) and replaying those. Target **≥ 2000 games**.

For each game we step ply-by-ply with `get_next_state` and call
`get_valid_moves` at every decision (both TILES and MEEPLES phases), draining
the audit buffer per game. Production leaf env is set before import:

```
CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0
CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
```

The audit runs at the production `window_size = 25` (`DEFAULT_WINDOW_SIZE`).

## Metrics reported

1. **% of games** with ANY overflow event (≥1 dropped legal action at any
   decision) and % with any out-of-window placed tile.
2. **% of DECISIONS** with ≥1 dropped legal action (the headline rate). Also the
   per-decision distribution of `n_overflow` and `n_oow_tiles`.
3. **Phase distribution** (TILES vs MEEPLES) of overflow events.
4. **Game-stage distribution** by `k_remaining` (tiles left to place, 72→0):
   - opening: `k_remaining ≥ 49` (first ~24 tiles)
   - mid: `25 ≤ k_remaining ≤ 48`
   - endgame: `k_remaining ≤ 24` (last ~24 tiles)
5. **Deep-search preference check.** Sample ~20 decisions that dropped ≥1 legal
   action. For each, reconstruct the SAME position with a `window_size = 31`
   Game (wide enough to include the dropped moves) and run **HeuristicMCTS at
   h1600** (`heur_leaf="v2_7"`, DEFAULT_CONFIG from the champion leaf env). Ask:
   does the h1600@W31 top action equal one of the moves that W25 dropped
   (i.e. would the deep search have chosen a move the production window hid)?
   Report the fraction of sampled decisions where a dropped move is the
   deep-search-preferred move.

## Pre-registered n

- Games: ≥ 2000. Decisions: expected ~250k+ (≈144 decisions/game).
- Deep-search check: ~20 sampled dropped-action decisions.

## DECISION RULE (verbatim, fixed before data)

> If ≥0.5% of decisions drop a legal action OR any sampled dropped action is the
> deep-search (h1600@W31)-preferred move → escalate to a W=25 vs W=31
> deck-paired game A/B at n=400. DO NOT launch that A/B — instead SURFACE its
> cost estimate to the lead as a go/no-go. Otherwise, close the item with the
> measured drop rate.

Single read-out at the pre-registered n; no threshold-moving.
