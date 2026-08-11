# Window-overflow audit — REPORT (Phase 0.2, measurement-only)

Status: COMPLETE. Pre-registration: [PLAN.md](PLAN.md) (written before any number
existed). Single read-out at the pre-registered n; no threshold-moving.

## TL;DR

The `get_valid_moves` window-overflow bug (silent `continue` past legal actions
whose encoded index leaves the centered 25×25 window) and the `encode_board`
out-of-window placed-tile skip **never fire in strong play**. Across **2,096
games / 299,165 decisions** (696 real archived + 1,400 champion-leaf self-play),
with balanced opening/mid/endgame coverage, **zero** decisions dropped a legal
action and **zero** placed tiles fell outside the window. The instrumentation is
proven live by a positive control (a 5×5 window fires the counters). **The
pre-registered decision rule does NOT fire → the item closes with a measured
drop rate of 0%. No W=25-vs-W=31 A/B is warranted.**

## Instrumentation (shipped behind a flag, default OFF)

- `src/carcassonne_ai/game_wrapper.py`: `CARCASSONNE_WINDOW_AUDIT=1` (env, read
  at import). When set, `get_valid_moves` appends one per-decision record
  `{phase, n_total, n_overflow, k_remaining, n_oow_tiles, window_size}` to a
  module buffer, drained by `drain_window_audit()`. `n_oow_tiles` counts placed
  tiles outside the window — exactly what `encode_board`/`get_canonical_form`
  silently skip. `window_audit_enabled()` exposes the flag.
- **Bit-exact when off:** `scripts/window_audit/verify_bitexact.py` plays 20
  fixed seeded games; SHA256 over every returned mask is IDENTICAL flag-off
  (0 records) vs flag-on (2,878 records): `ad178797…`. The audit block never
  mutates the mask, the raise condition, or any leaf/eval semantics. (Re-checked
  after a concurrent Phase-0.3 edit to the same file — still bit-exact.)
- **Positive control:** at a deliberately tiny `window_size=5`, the counters fire
  correctly (17/47 decisions dropped ≥1 action, 219 dropped actions, 27 out-of-
  window tiles) — so the zeros at W=25 are a real null, not a dead counter.

## Data

Replayed losslessly from `(deck_seed, action_sequence)` via
`scripts/measurement_infra/root_replay.py` (each game stepped ply-by-ply with
`get_valid_moves` called at every decision, under the production leaf env).

| file | games | note |
|---|---|---|
| `measurement/post_search_residual/data/games_mcts.jsonl` | 400 | NeuralMCTS self-play, full games |
| `/mnt/c/carc-shared/l23_k4_expand.jsonl` | 200 | L2-3 K=4 games (legacy `seed`/`gen_id` schema) |
| `measurement/level2/l23_k4_multisource.jsonl` | 96 | 48 seeds × 2 source agents |
| **real subtotal** | **696** | 97,683 decisions, 0 replay failures |
| `measurement/window_audit/gen_games.jsonl` | 1,400 | champion-LEAF self-play top-up (see note) |
| **combined total** | **2,096** | 299,165 decisions, 0 replay failures |

The `.npz` self-play archives (≈6,000 games) store training tensors only (no
`deck_seed`+action list) — not replayable, so excluded. To reach the
pre-registered ≥2,000 games, real games are topped up with champion-**leaf**
self-play (`scripts/window_audit/gen_games.py`, HeuristicMCTS `heur_leaf=v2_7`
built from the CARCASSONNE_V25_*/V29_* env block = the champion leaf; verified at
runtime: 1,600 v2_7 leaf calls / 0 v1 calls per search). Rationale: net-on-CPU
generation of thousands of games with the actual net champion is hours-
infeasible, and the board GEOMETRY that drives window overflow is set by
placement-policy quality, which the v2.7-leaf MCTS captures (reference-ladder /
RoDv2-tier opponent). Real games are the primary evidence; generation is the
pre-registration top-up.

## Results

Real-only and combined agree exactly — every bucket is 0.

| metric | real (696) | combined (2,096) |
|---|---|---|
| decisions | 97,683 | 299,165 |
| % games with ANY overflow event | 0.000% (0/696) | 0.000% (0/2,096) |
| % games with ANY out-of-window placed tile | 0.000% | 0.000% |
| **% decisions dropping ≥1 legal action** | **0.0000% (0/97,683)** | **0.0000% (0/299,165)** |
| % decisions with ≥1 out-of-window placed tile | 0.0000% | 0.0000% |
| total dropped legal actions | 0 | 0 |
| total out-of-window placed tiles | 0 | 0 |
| all-overflow (raise) decisions | 0 | 0 |
| replay failures | 0 | 0 |

Distribution (combined; every bucket = 0 overflow):

- **Phase:** 149,680 TILES / 149,485 MEEPLES — 0 drops in either. (Overflow can
  only occur on TILE placements; MEEPLE/pass actions carry no window check.)
- **Game-stage (by k_remaining):** 98,690 opening / 100,619 mid / **99,856
  endgame** — 0 drops in any stage. Endgame boards are the most spread, and even
  they never overflow the 25×25 window.
- `n_overflow` histogram: `{0: 299165}`. `n_oow_tiles` histogram: `{0: 299165}`.

**Statistical power:** 0 events in 299,165 decisions → rule-of-three 95% upper
bound on the per-decision drop rate = **0.001003%** (≤ ~1 in 99,721), ~500× below
the 0.5% decision threshold. The threshold would require ≥1,496 dropped
decisions; observed 0. (Real-only UB alone was 0.00307%, already 163× below.)

## Deep-search preference check (h1600 @ W=31)

The combined replay produced **0 dropped-action decisions**, so there is no
dropped action to test — the "deep-search-preferred dropped move" clause is
vacuously not met. `scripts/window_audit/deep_search_check.py` ran and reported
**0/0** (`measurement/window_audit/deep_search_result.json`). The h1600@W31
machinery was validated on a real midgame position (0.89 s/decision; the v2.7
champion leaf confirmed running), so had any dropped decision existed it would
have been checked.

## Decision-rule outcome

Pre-registered rule (verbatim):

> If ≥0.5% of decisions drop a legal action OR any sampled dropped action is the
> deep-search (h1600@W31)-preferred move → escalate to a W=25 vs W=31 deck-paired
> game A/B at n=400. DO NOT launch that A/B — instead SURFACE its cost estimate
> to the lead as a go/no-go. Otherwise, close the item with the measured drop
> rate.

**Outcome: the rule does NOT fire.** Drop rate 0.0000% (95% UB 0.001003%) ≪ 0.5%,
and there are no dropped actions to be deep-search-preferred. **Recommendation:
CLOSE the item.** No A/B is warranted — the production 25×25 centered window
loses nothing in strong 2-player Base+Farmers play, at any game stage. (No cost
estimate is surfaced because the escalation condition was not met.)

## Files

- Instrumentation: `src/carcassonne_ai/game_wrapper.py` (`CARCASSONNE_WINDOW_AUDIT`, `drain_window_audit`, `window_audit_enabled`, `_count_out_of_window_tiles`)
- Scripts: `scripts/window_audit/{verify_bitexact,run_audit,gen_games,deep_search_check}.py`, `scripts/window_audit/orchestrate.sh`
- Pre-reg: `measurement/window_audit/PLAN.md`
- Results: `measurement/window_audit/{audit_real,audit_combined}.json` (+ `_dropped_refs`/`_dropped_sample` sidecars), `deep_search_result.json`, `gen_games.jsonl`
