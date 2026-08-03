# F9 / A3 — unplaceable-tile → REDRAW: build + gate verdict

> **STATUS 2026-08-03 — BUILT, GATED, DEFAULT OFF, NOT ADOPTED.** The flag exists in both
> engines and every gate below is green. **Nothing is adopted**: `draw_rule="engine"` is the
> default everywhere including the Android app, `governance/PRODUCTION.yaml` is untouched, no
> `experiments/results.csv` row was written and no band was claimed. Adoption is spec §7 **J5**.

Spec: [docs/F9_BUILD_SPEC_20260802.md](../../docs/F9_BUILD_SPEC_20260802.md) §A3.
Dossier: [docs/RULES_FIDELITY_AUDIT_20260802.md](../../docs/RULES_FIDELITY_AUDIT_20260802.md) **RF-D-2**.

## The rule, and the two sub-decisions the spec required pre-registering

Audit clause **P4**: *"In the rare circumstances where a drawn tile cannot be placed, the player
returns the tile to the box and **draws another tile**"* — the tile is **removed from the game**
and the **same player continues their turn**. The vendored engine instead discards, draws, **and
calls `next_player`**, so the drawer forfeits a whole placement.

**Sub-decision 1 — RECURSION.** The redrawn tile may itself be unplaceable and the clause is
per-draw, so it re-applies. Realized as a **sequence of forced `PassAction`s** (one set-aside +
one draw each, phase left at TILES with the drawer still to move), not a `while` loop inside the
transition. Behaviourally identical — a redrawn-and-still-unplaceable state has `PassAction` as
its only legal move, so no agent decision is invented — and it buys two things a loop cannot:
each draw stays a **separate chance event** the marginalized solver can price (sub-decision 2),
and the engine diff is the removal of one call. **Termination is structural, not a guard:** the
bag strictly shrinks by one tile per pass because a set-aside tile leaves the game rather than
returning to it. Deck exhausted mid-redraw resolves through the same
`is_terminated()` / `count_final_scores` block as the normal path (audit **E7**).

**Sub-decision 2 — THE BAG / THE EXACT SOLVER'S HISTOGRAM.** A set-aside tile is removed
**permanently**: not returned, not reshuffled, never redrawn, and absent from every later
determinization and chance node. This needs no new bookkeeping — `state.deck` **is** the bag in
both engines (there is no separate histogram anywhere in the hot path) and `draw_tile`'s `pop(0)`
already removes it — but the flag owes the bag two consequences, both gated on it:

1. **`total_tiles` is decremented** per set-aside, so the two live definitions of "tiles left" stay
   equal: `len(deck) + has_next` (the fair agent's latch band) and `total_tiles - tile_count`
   (the window audit, `clip_trace`, `features.progress`).
2. **The marginalized exact solver re-marginalizes the replacement draw.** *Required, not
   cosmetic:* the solver's TT key hashes the **sorted** bag (the multiset is the information set),
   so a redraw value that depended on which tile happened to sit at the front of `state.deck`
   would return one deck order's answer for another's. The same unsoundness is latent on the
   flag-**off** discard path and is deliberately **not** fixed there — flags-off must stay
   byte-identical.

## Gate table

| # | gate | instrument | result |
|---|---|---|---|
| 1a | **flags-off REPLAY regate** (zero tolerance) | `reconcile_engine.py --corpus champ --limit 60` | **PASS** — 60 games, 8,633 plies, **8,693 positions × 6 checks, 0 mismatches** |
| 1b | **flags-off SEARCH regate** (G3 pattern) | `reconcile_search.py --limit 12 --stride 24 --per-game 4` | **PASS** — **96 searches / 82,560 sims / 768 field checks, 0 mismatches** |
| 2 | **flags-ON python↔Rust lockstep, ≥1000 games** | `lockstep_fuzz.py --games 1000 --draw-rule redraw` | **PASS** — **144,922 positions × 15 checks, 0 mismatches**; 78 redraw events over 1,000 games |
| 3 | **flags-OFF lockstep control** (same instrument) | `lockstep_fuzz.py --games 1000` | **PASS** — 144,922 positions × 15 checks, 0 mismatches |
| 4 | **compose-with-P5 leg** | `--draw-rule redraw --start-rule retail --start-row 18` | **PASS** — **142,986 positions × 15 checks, 0 mismatches** |
| 5 | **grid disentangler** | `--draw-rule redraw --start-row 18` | **PASS** — 144,922 positions, 0 mismatches (and see the finding below) |
| 6 | **mutation probe** ("is 0 mismatches informative?") | `probe_a3_mutations.py` | **PASS — 5/5 mutations discriminated**, control clean on all 5 gates |
| 7 | **deterministic reproducer** | pinned seeds in `tests/test_unplaceable_redraw.py` | **PASS** — flag-on replay byte-stable; flag-off identical to a default `Game()` |
| 8 | **manifest counter** | `redraw_events` / `games_with_a_redraw` / `tiles_by_seat` / `seat_imbalance_games`, per mode | **PRESENT** in every fuzz manifest |
| 9 | **unit suites** | `test_unplaceable_redraw.py` (20) · `test_bridge.py` (107) · `test_p5_flags.py` (44) · Rust `cargo test` (84) | **PASS** |

**Mutation probe detail** (`A3_mutation_probe.json`), gates × regressions:

| mutation | went RED on |
|---|---|
| `ignore_the_flag` (pass still hands the turn over) | parity, lockstep |
| `no_remarginalize` (solver stops re-pricing the redraw) | solver_order |
| `no_total_tiles_decr` | bag, lockstep |
| `tile_returns_to_bag` | bag, conservation, solver_order, lockstep |
| `no_recursion` (only the first redraw keeps the turn) | lockstep |

## Event rate observed — and a finding that resizes A3

Per 1,000 fuzz games (uniform + wall-seeking policy mix), engine start rule, walled row 6:

* **7.8 redraw events / 100 games**, **6.7% of games affected** — the audit's independent
  random-play figure is 8.5/100 and 7.0% ± 3.6%, so the instruments agree.
* **0 seat-imbalance games** out of 1,000 under `redraw`: with T tiles actually placed the seats
  split ⌈T/2⌉ / ⌊T/2⌋ in every game. Under `engine` a discard hands the opponent an extra
  placement. That is the direct observable of what this flag changes.

**⚠️ FINDING — the event rate is governed by the START TILE, not by the grid.** Three matched
1,000-game legs:

| condition | events / 100 games | games affected |
|---|---|---|
| engine start rule, walled row 6 | 7.8 | 6.7% |
| engine start rule, **row 18** | **7.8** | **6.7%** |
| **retail** start rule, row 18 | **1.4** | **1.4%** |

Recentring changes the rate by **nothing**; the retail fixed "D" start tile cuts it **5.6×**.
The mechanism is visible in the positions themselves: probing 60 seeded games, **every**
naturally-occurring forced pass happened at **k = 71** — the very first decision, when only the
start tile is down and its four open cells admit few tile kinds. By the endgame the open perimeter
is wide and every kind fits somewhere. So an unplaceable tile is almost entirely a *first-move*
event, and which tile starts the board decides it: the engine rule auto-places a **random** tile
(sometimes highly edge-constrained), retail always places the edge-permissive city+road D.

Consequences for the program, none of them decided here:

* **RF-D-2's blast radius is conditional on A4.** If retail is in the fixed-rules bundle, A3
  affects ~1.4% of games rather than ~7%. That is a live input to spec §7 **J3** (is A4 in the
  bundle) and it means A3 and A4 are **not independent** — the single-flag attribution ladder of
  §6 T1 would need the A3 cell run at a *stated* start rule.
* It also means the audit's "7.0% of games" headline is an **engine-start-rule** number, and
  should be cited as such rather than as a property of the rules fix.

## Deliberate non-fixes (flags-off must stay byte-identical)

* The flag-off discard path still leaves `total_tiles` un-decremented (a pre-existing latent drift
  between the two "tiles left" definitions).
* The marginalized solver still does not re-marginalize the flag-off discard's replacement draw,
  so its sorted-bag TT key is latently unsound on that path. Both are documented at the code and
  both are gated on the flag so gate 1a/1b/3 stay clean.

## ⚠️ One default-path bug FIXED, deliberately

`android_bridge.get_bag` reconstructs the bag as *distribution − board − hand* and never reads
`state.deck`. A tile that was drawn and could not be placed is **neither on the board nor in
hand** — so under the **existing engine rule** the app has been reporting a discarded face as
still-unseen forever, breaking `total_remaining == deck_remaining` for the rest of any game
containing a discard. Now fixed by subtracting the set-aside faces. This changes the app's bag
**display** on the default path; it changes no rule, no move, and no measured number.

## Artefacts

`A3_regate_engine.json` · `A3_fuzz_redraw.json` · `A3_fuzz_control.json` · `A3_fuzz_compose.json` ·
`A3_fuzz_redraw_row18.json` · `A3_mutation_probe.json` ·
[`measurement/rustport_p3/G3_search_a3_regate.json`](../rustport_p3/G3_search_a3_regate.json).
Reproduce with `bash scripts/rustport/run_a3_gates.sh` and `run_a3_gates2.sh`.
