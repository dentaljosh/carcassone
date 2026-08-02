# Rules-fidelity audit — our engine vs published Carcassonne (2026-08-02)

> **⚠️ STATUS 2026-08-02 — COMPLETE (read-only audit; no code changed).** The cheap sweep half of the
> rules-fidelity instrument named in [BACKLOG.md](../BACKLOG.md) (2026-08-02 entry). The machine-checkable
> half — the JCloisterZone differential oracle — is still unbuilt; this document is a *clause-by-clause
> human read*, not a mechanical proof, and its "CORRECT" verdicts carry the confidence of a careful
> reading plus targeted probes, not of an external referee. Remediation list is input to **F9** in
> [docs/PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md).

## Why this exists

The invisible-border and cloister-rebinding bugs are a *class*: places where the engine silently
implements a different game than published Carcassonne. That class is invisible to every
self-consistency gate we own **by construction** — both sides of every A/B play the same wrong rule, the
Rust port certifies the wrongness bit-exactly, and elo is measured against ourselves. Only an external
reference can see them. This audit is that reference, done by hand against the rules.

## Method + its limits

Rules source: WikiCarpedia (the community-maintained rules wiki that carries the official Base Game +
Farmers text for C1/C2/C3), plus UltraBoardGames' rules transcription and the
Carcassonne-Meisterschaft tournament rules for World-Championship conventions.

⚠️ **Sourcing caveat, stated up front.** wikicarpedia.com is behind an Anubis anti-scraping challenge
and returned "Access Denied" to every direct fetch. The content below was obtained through a
text-extraction proxy and through search-result excerpts, so **the rule text quoted here is
paraphrase-grade, not verbatim rulebook wording**. Every *number* was cross-confirmed on at least two
independent sources. Anything that turned on exact wording is flagged as ambiguous rather than decided.

Engine sources audited: `engine/wingedsheep/carcassonne/` (placement, legality, scoring, farm utils),
`src/carcassonne_ai/game_wrapper.py`, and `src/carcassonne_ai/flat_leaf.py` (`flat_base_score` — the
scoring of record for the solver).

Three probes were run (random self-play, 2p, BASE + FARMERS, engine only, nothing in the repo touched):

| probe | what it measures | n |
|---|---|---|
| `rf_audit_probe.py` | live cloister misses; unplaceable-tile discards | 200 games |
| `rf_cloister_repro.py` | deterministic control/trigger pair for the rebinding | 2 states |
| `rf_cloister_rate.py` | *geometric* cloister-scan miss rate (decoupled from whether a monk happens to be there) | 1500 games / 107,909 placements |

Plus one exhaustive static check: all 32 base tile kinds × 4 rotations × 32 × 4 = **16,384 ordered
neighbour pairs** run through `TileFitter.fits` and compared against ground-truth edge-type equality.

---

## Verdict — what edition of Carcassonne do we actually play?

**We play the 3rd edition (C3, 2021) Base game + Farmers, with World-Championship scoring conventions —
correctly, in every scoring amount — but on a walled 35×35 board with an off-centre start, with a random
rather than fixed start tile, with an unplaceable tile costing the drawer their whole turn, with no
WC tie-break, and with a cloister-completion scan that silently skips roughly one completed cloister in
ten.** The tile distribution is the official 72-tile base set including the C3 garden variants; every
during-game and end-game scoring amount matches C3/WC exactly (city 2/tile + 2/pennant, two-tile city =
4 not 2, road 1/tile, cloister 9, incomplete city 1/tile + 1/pennant, farm 3 per completed adjacent
city, all tied majorities score full). **There is not a single live scoring-amount error.** Every
divergence we found is structural — board geometry, turn sequencing, feature-completion *detection*, and
one missing tournament tie-break convention. All of them are symmetric: both agents in every comparison
we have ever run played the same wrong rule, so relative orderings survive; what is unmeasured is the
transfer error to canonical rules, which is exactly what F9 exists to bound.

---

## Divergence classes — counts

| class | meaning | live | latent (out of scope, inert) |
|---|---|---|---|
| **RF-A** | scoring amount wrong vs *every* official edition | **0** | 2 |
| **RF-B** | matches one edition but not the WC/current one | **1** | 0 |
| **RF-C** | legality divergence (the border class) | **2** | 0 |
| **RF-D** | timing / meeple-return divergence | **2** | 0 |
| **RF-E** | already known and already fixed | **3** | — |

Live total: **5 divergences** (2 of them newly characterized here), plus 2 latent code defects that are
provably inert under the locked scope, plus 3 historical fixes re-verified.

---

## Top 5 by impact

1. **RF-C-1 — walled 35×35 board, start at row 6.** Rule-legal placements are silently unavailable at the
   wall (67.8% of games hit ≥1 denial), and three of the four wall faces are outright fatal or
   memory-unsafe. Known, root-caused, app-only fix landed.
2. **RF-D-1 — the cloister-completion scan drifts and misses completions.** Newly characterized here with
   a deterministic reproducer: **9.55% (15/157, 95% CI ≈ [5%, 15%]) of cloister completions fall outside
   the scan window**. The 9 points are not lost (they arrive at final scoring) but the **monk is pinned
   on the board for the rest of the game** — a permanent −1 to that player's follower supply.
3. **RF-D-2 — an unplaceable tile costs the drawer their entire turn.** New. The rules say the player
   discards and *draws again*; the engine discards and passes the turn. Measured **8.5 discards per 100
   games, 7.0% of games affected**.
4. **RF-C-2 — random start tile, and placing it costs player 0 a turn.** Retail/WC pre-places a fixed "D"
   tile that nobody plays; the engine shuffles all 72 and auto-places the first draw. Known; fixed for
   the app only, library default unchanged.
5. **RF-B-1 — no WC tie-break.** WC resolves a tied final score against the starting player; we return a
   symmetric draw. Known, parked. ~1–2.5% of games.

---

## Clause-by-clause table

Legend: ✅ correct · ⚠️ divergence · 💤 latent defect, inert under the locked scope.

### Tile placement

| # | Rule clause | Engine behaviour | Verdict |
|---|---|---|---|
| P1 | "The new tile must be placed so that all road, city and field segments match on all abutting edges." | `TileFitter.grass_fits` / `cities_fit` / `roads_fit`, `tile_fitter.py:12-50`, combined in `fits` `tile_fitter.py:104-113`. **Exhaustively verified: 16,384 ordered tile-pairs, 0 disagreements with ground-truth edge-type equality.** Road edges are correctly *not* also listed in `Tile.grass`, so the grass check cannot mask a road/field mismatch. | ✅ |
| P2 | "…with at least one edge abutting one previously placed tile." | `tile_fitter.py:107-108` returns False when all four neighbours are None. | ✅ |
| P3 | The playing area is unbounded. | `carcassonne_game_state.py:24-25`: `board_size=(35,35)`, `starting_position=Coordinate(6,15)` — 6 rows of headroom above, 28 below. `state_updater.py:41-43` bounds-checks before adding to `open_positions`, so off-grid cells never enter the candidate set. Four distinct faces (silent denial · negative-index wrap · col-34 `IndexError` · last-row fatal in `count_final_scores`). | ⚠️ **RF-C-1** (known — BACKLOG 2026-07-30; DECISIONS 2026-07-31 / 2026-08-01) |
| P4 | "In the rare circumstances where a drawn tile cannot be placed, the player returns the tile to the box and **draws another tile**" — i.e. the same player continues their turn. | `state_updater.py:126-138`: a TILES-phase `PassAction` discards the tile, draws the next, **and calls `next_player`** (line 135). The drawer forfeits the turn; the opponent gets the extra placement. `action_util.py:19-24` correctly emits the Pass only when there is genuinely no legal placement (the must-place-if-possible rule is honoured). | ⚠️ **RF-D-2** (NEW) |
| P5 | Retail/tournament pre-places a fixed start tile ("D": city on one edge, road straight through); the remaining 71 are shuffled. Nobody spends a turn on it; no meeple may go on it. | `carcassonne_game_state.py:112-151` shuffles all 72; `tile_position_finder.py:12-13` auto-routes the first draw to `starting_position`, where it *is* a player move with a meeple phase. `game_wrapper.py:279-329` implements the retail behaviour but `fixed_start_tile` defaults **False** (`game_wrapper.py:344`). | ⚠️ **RF-C-2** (known — BACKLOG 2026-07-28; app-only fix 2026-08-01) |
| P6 | 72 base tiles, official distribution. | 32 kinds summing to 72; matches the official base distribution (8 straight road, 9 curved, 4 T, 1 crossroads, 4 cloister, 2 cloister+road, 5 single-edge city, 1 four-sided city with pennant, …), with the C3 garden ("flowers") variants substituted in-place. | ✅ (C3) |

### Meeple placement

| # | Rule clause | Engine behaviour | Verdict |
|---|---|---|---|
| M1 | One follower per turn, on the tile just placed, and placement is optional. | `possible_move_finder.py:67-102` offers positions only on `last_tile_action`; `action_util.py:31` always appends a `PassAction` in the meeple phase. | ✅ |
| M2 | "You may not place a follower on a road, in a city or in a field if that section is connected to another tile where there already is a follower" — evaluated *after* the new tile has merged the features. | City: `CityUtil.city_contains_meeples` over the merged component. Road: `RoadUtil.road_contains_meeples`. Field: `FarmUtil.has_meeples` over the merged farm (`possible_move_finder.py:104-123`). All run post-placement. | ✅ |
| M3 | Each player has 7 followers (8 wooden figures, one used as the score marker) in C2/C3. | `carcassonne_game_state.py:33`: `self.meeples = [7 for _ in range(players)]`. | ✅ (C2/C3) |
| M4 | A field occupying several half-edges of one tile is one placement option. | `possible_move_finder.py:120` canonicalises to `farmer_connection.farmer_positions[0]`; `FarmUtil.find_meeples` (`farm_util.py:215`) reads the same index. Consistent. | ✅ |

### Feature completion

| # | Rule clause | Engine behaviour | Verdict |
|---|---|---|---|
| C1 | A city is complete when it is fully enclosed by wall with no gaps. | `city_util.py:71` — `finished = len(explored) == len(cities)`; an edge opening onto an empty cell stays in `explored` but never enters `cities`. | ✅ |
| C2 | A road is complete when both ends terminate (village/city/cloister/crossroad) **or it closes into a loop**. | `road_util.py:48`, same construction. Loops close correctly because every edge's opposite is itself in the component. | ✅ |
| C3 | A cloister is complete when all 8 surrounding spaces are filled. | The *definition* is right (`chapel_or_flowers_points` counts the filled 3×3 and the caller requires 9). The *detection scan* is not — see RF-D-1 below. | ⚠️ **RF-D-1** |

### Scoring during the game

| # | Rule clause | Engine behaviour | Verdict |
|---|---|---|---|
| S1 | Completed city: 2 points per tile, plus 2 per coat of arms. | `points_collector.py:147` (`4` for a shielded tile = 2 tile + 2 pennant) and `:152` (`2`). Mirrored in `flat_leaf.py:467`. | ✅ |
| S2 | **Two-tile completed city.** C1/C2: 2 points total + 1 per pennant. C3 **and the official WC tournament rules**: the normal 2/tile, i.e. 4 points. | No special case; a 2-tile city scores 4 (+2/pennant). | ✅ **as C3/WC** (would be RF-B against C1/C2) |
| S3 | Completed road: 1 point per tile. | `points_collector.py:180`; `flat_leaf.py:481`. | ✅ |
| S4 | Completed cloister: 9 points (itself + 8). | `points_collector.py:90` awards when `points == 9`. | ✅ |
| S5 | Majority: most followers takes all; **on a tie, every tied player scores full points**. | `get_winning_players` (`points_collector.py:105-120`) returns the full argmax list. This is a vendored patch — upstream returned a sole winner or None. Mirrored by `flat_leaf._winners` (`flat_leaf.py:441-447`). | ✅ **RF-E** (fixed; CLAUDE.md engine notes) |
| S6 | Followers return to supply the moment their feature scores. | Correct for cities and roads (`MeepleUtil.remove_meeples`). **Not** correct for cloisters missed by the drifting scan. | ⚠️ **RF-D-1** |

### Scoring at the end of the game

| # | Rule clause | Engine behaviour | Verdict |
|---|---|---|---|
| E1 | Incomplete city: 1 point per tile + 1 per coat of arms. | `points_collector.py:147/152` with `finished=False` → 2 for a shielded tile (1+1), 1 otherwise; `flat_leaf.py:468`. | ✅ |
| E2 | Incomplete road: 1 point per tile. | `points_collector.py:180`. | ✅ |
| E3 | Incomplete cloister: 1 + 1 per adjacent tile. | `chapel_or_flowers_points` (`points_collector.py:185-192`) counts placed tiles in the 3×3, awarded unconditionally at `:240-245`. | ✅ |
| E4 | Fields: **3 points for each completed city the field touches**; each city counted once however many farmer-connections touch it; tied farmer majorities all score. | `count_farm_points` (`points_collector.py:284-307`), `points += 3` at `:305`, dedup by `frozenset(city.city_positions)` at `:292-303` (the 2026-06-02 fix). `flat_leaf.py:571` = `3 * farm_root_finished_cities[root]`. | ✅ (C2/C3) **RF-E** (dedup fixed) |
| E5 | Fields connect across tile edges by half-edge; roads and cities split them; a road dead-ending at a cloister does **not** split the field. | `FarmUtil.find_farm` (`farm_util.py:53-91`) is a complete, start-independent connected-component traversal; `opposite_farmer_side` (`side_modification_util.py:81-108`) is now a clean involution on 4 pairs `{TLL,TRR} {TLT,BLB} {TRT,BRB} {BRR,BLL}`. Spot-checked 7 of 32 tile kinds' farm data against the physical tiles (two-opposite-cities splitting vs not splitting, crossroads → 4 fields, cloister+road → 1 field, city-corner tiles) — all correct. | ✅ **RF-E** (involution fixed 2026-05-29) — but see *Not verified* below |
| E6 | No official tie-break in the retail rules; **WC/tournament: a tied 2-player game is lost by the starting player.** | `game_wrapper.get_game_ended` (`game_wrapper.py:646-665`) returns a symmetric ±1e-6 draw. | ⚠️ **RF-B-1** (known — BACKLOG 2026-07-28) |
| E7 | Game ends when the last tile has been placed. | `is_terminated()` = deck exhausted (`carcassonne_game_state.py:109-110`); `count_final_scores` fires from `state_updater.py:136-137` and `:147-148`. Both the normal path and the discard path are covered. | ✅ |
| E8 | Final scoring must not double-award a feature carrying two of one player's followers. | `count_final_scores` iterates a *snapshot* set of meeples but `find_meeples` re-reads live state, so the second visit sees zero counts and `get_winning_players` returns `[]`. Verified safe despite the `TODO` at `points_collector.py:198`. | ✅ |

---

## RF-D-1 in full — the cloister-completion scan drift ("cloister rebinding")

This was on record as an "undocumented cloister-rebinding quirk", mutation-proven load-bearing by the
Rust port's G1 gate but never characterized against the rulebook. Here is the mechanism, the
consequence, and the rate.

**The code** (`engine/wingedsheep/carcassonne/utils/points_collector.py:77-103`):

```python
for row in range(coordinate.row - 1, coordinate.row + 2):
    for column in range(coordinate.column - 1, coordinate.column + 2):
        tile: Tile = game_state.get_tile(row, column)
        if tile is None:
            continue
        coordinate = Coordinate(row=row, column=column)   # <-- rebinds the loop's own bound
```

The **outer** `range` is evaluated once, from the true placement coordinate. The **inner** `range` is
re-evaluated at the top of every outer iteration — using the *rebound* `coordinate`. So the column
window of scan rows 2 and 3 drifts to wherever the last non-empty cell of the previous row happened to
be. The rebinding is deliberate (the rebound value is what gets passed to `chapel_or_flowers_points` at
`:89`); the bug is that it is the same name as the loop bound.

**Consequence.** A cloister completed by this placement can fall outside the drifted window, in which
case it is not scored and its monk is not returned. Because a completed cloister's 3×3 is by definition
full, no later placement can ever be within Chebyshev distance 1 of it — **the miss is permanent for the
rest of the game.** Two distinct effects, which must not be conflated:

- **Points: deferred, not lost.** `count_final_scores` (`points_collector.py:240-245`) awards
  `chapel_or_flowers_points` = 9 for any monk still sitting on a cloister at the end. Final scores are
  therefore *unchanged* by this bug.
- **Meeple: lost.** The monk is pinned for the remainder of the game — a permanent −1 on a supply of 7.
  This is the real cost, and it is invisible to any score-based check.

The drift also makes the scan visit cells *outside* the true 3×3 (0.357 per placement), which can
belatedly re-score a cloister missed earlier — a partial, unreliable self-heal.

**Deterministic reproducer** (`rf_cloister_repro.py`, scratchpad): cloister with a monk at (10,10),
completed by a placement at (9,10).

| case | board | result |
|---|---|---|
| control — nothing to the right of the block | rows 9–11 × cols 9–11 | scores `[9, 0]`, free meeples `[6,7] → [7,7]`, monk returned |
| trigger — tiles also at (8,11) and (9,12) | scan row 9 drifts to cols 10–12, row 10 drifts to cols 11–13 | scores `[0, 0]`, free meeples stay `[6,7]`, **monk still on the completed cloister** |

**Rate** (`rf_cloister_rate.py`, 1500 random games, 107,909 placements — geometric, so independent of
whether a monk happens to be present):

| quantity | value |
|---|---|
| placements whose scan window drifts at all | **51.2%** (55,253 / 107,909) |
| cloister tiles that became fully surrounded | 157 (0.105 / game under random play) |
| …of those, outside the drifted window ⇒ would be missed | **15 = 9.55%**, 95% CI ≈ [5%, 15%] |
| cells visited outside the true 3×3 | 0.357 per placement |

⚠️ **Frequency caveat.** Random play completes only ~0.1 cloisters per game and almost never has a monk
on one (the 200-game live probe saw just 2 monk-bearing completions and 0 misses). Under strong play,
monks on cloisters are routine and completions are engineered, so the *event* rate is much higher than
0.1/game while the *conditional* miss rate (~9.6%) should carry over, since it is a pure board-geometry
property. A real impact number needs the probe re-run under champion play — that is cheap and is listed
as R1 below.

---

## RF-D-2 in full — an unplaceable tile costs the drawer their turn

`state_updater.py:126-138`. The rule: discard the unplaceable tile and **draw another**, continuing your
turn. The engine: discard, draw, and hand off to the opponent. The player who drew the dud loses a whole
placement; the opponent gains one, and every turn parity after that point is flipped.

Measured (200 random games): **17 discards, 0.085 per game, 14/200 = 7.0% of games affected** (±3.6% at
n=200). Symmetric in expectation — which player draws a dud is a deck accident — but it is not
score-neutral within a game, and it shifts the tile-count-per-player balance that farm and endgame play
depend on.

The comment at `state_updater.py:107-118` shows this path was deliberately rewritten (2026-04-28) to fix
a *different* bug (a stale `last_tile_action` leaking a meeple onto a previous turn's tile). That fix is
correct; the `next_player` call it introduced is the divergence.

---

## Latent defects — real code errors, provably inert under the locked scope

| # | Defect | Why inert |
|---|---|---|
| 💤 L1 | `tile.inn` drives **both** the road inn bonus **and** the city cathedral flag (`points_collector.py:132` `if tile.inn: has_cathedral = True`, and `:159-160`; mirrored in `flat_leaf.py:457` and `:476`, whose comment even names it: *"engine reuses .inn as the cathedral flag"*). `Tile.cathedral` exists (`tile.py:42`) and is never read. If Inns & Cathedrals were enabled, every inn tile in a city would trigger cathedral scoring (3/tile, 0 if unfinished). | Verified across all 32 base tile kinds: **no base tile sets `inn` or `cathedral`**. Inns & Cathedrals is rejected at `game_wrapper.py:352-356`. |
| 💤 L2 | `tile.flowers` (the C3 **garden**) is treated as a cloister worth 9 points wherever `chapel` is (`points_collector.py:88`, `:240`; `flat_leaf.py:541`). A garden is not a cloister and never scores 9 for a follower. | A meeple can only reach a garden's CENTER via `MeepleType.ABBOT` or the `NORMAL_MEEPLES_CAN_USE_FLOWERS` supplementary rule (`possible_move_finder.py:52-56`, `:77-79`). `Game.__init__` defaults to `(SupplementaryRule.FARMERS,)` (`game_wrapper.py:339`) and hard-rejects ABBOTS (`:357-361`). |

Both would become live RF-A (wrong amount vs every edition) the moment the scope widened. Neither should
be "fixed" casually — either fix changes nothing today and would need the same flag-and-regate treatment
as the recentring switch.

---

## Python-internal inconsistency worth naming

`PointsCollector.chapel_or_flowers_points` indexes `game_state.board[row][column]` **unguarded**
(`points_collector.py:189`), while its flat twin `flat_leaf._cloister_points` **is** bounds-guarded
(`flat_leaf.py:489-493`). At the board edge the object scorer wraps or raises where the flat scorer
returns a clean number. This is the fourth border face, already on record from P5; it is repeated here
because it is the one place where our *two* scorers disagree with *each other*, which makes it the
cheapest possible detector for the whole border class.

---

## Where the rulebook itself is ambiguous — not forced

1. **"All players must agree"** the tile is unplaceable, in some printings, before it may be discarded.
   There is no engine analogue and none is needed for 2-player self-play, but it means the discard rule
   has a procedural component we cannot claim to implement.
2. **Which edition the World Championship plays in full.** The WC tournament rules explicitly confirm the
   C3 two-tile-city convention (4 points), which is what we implement. Whether every other C3 wording
   change applies at WC — and whether the C3 garden tiles are the ones used — was **not** established
   from any source I could reach. We are C3-shaped and WC-correct on the one clause that was checkable.
3. **The 2-player game has no special rules** in the base game beyond the tie-break convention. I found
   nothing suggesting otherwise, but absence of evidence in paraphrase-grade sources is weak.
4. **Fields touching an *incomplete* city** score nothing — every source agrees, and the engine agrees
   (`points_collector.py:304`) — but UltraBoardGames' transcription drops the word "completed", so at
   least one widely-read secondary source states the rule wrongly. Noting it so a future reader does not
   "fix" us toward the error.

## Not verified — honest gaps

- **Farm/city adjacency data for 25 of the 32 tile kinds.** `FarmerConnection.city_sides` is hand-authored
  per tile in `base_deck.py`; the *traversal* is now provably correct but the *data* is only as good as
  whoever typed it. 7 kinds spot-checked and correct. A wrong `city_sides` on one tile would be worth 3
  points per farm, per game, systematically. **This is the single largest unaudited surface left** and it
  is exactly what the JCloisterZone oracle would settle mechanically.
- **The 8 `flowers` tiles' non-garden geometry** (roads/cities/fields) was assumed identical to their
  plain counterparts, not checked.
- Verbatim rulebook wording, per the sourcing caveat.

---

## Remediation list for F9

Ordered by (impact × cheapness). **Every one of these changes results — none is a free bug-fix.** They
must land behind flags with the same gating the recentring switch got, and
`feedback_bug_fix_shifts_optima` applies to the whole set: if any is globally adopted, the leaf
caps/curve want a re-sweep before old optima are trusted.

| id | action | cost | note |
|---|---|---|---|
| **R1** | Re-run `rf_cloister_rate.py` under champion play instead of random play, to turn "9.6% of completions" into "N events per game". | ~1 box-hour | Pure measurement, no code change. Do this **first** — it sizes R2. |
| **R2** | Fix the cloister scan (rename the rebound variable). One line. | trivial + regate | Changes meeple economy, not final scores. Cheapest real rules fix we have. |
| **R3** | Fold the board fix (centred start / larger grid) into the library default, not just the app. | already built (P5 flags) | The F9 transfer-bound cell already needs this. |
| **R4** | Make the unplaceable-tile discard keep the turn with the drawer. | small | Changes turn parity ⇒ a genuine re-baseline trigger; 7% of games. |
| **R5** | Make the retail fixed start tile the library default. | already built | `game_wrapper.py:344`, flip `fixed_start_tile` and re-gate. |
| **R6** | Add the WC tie-break as an option on `get_game_ended`. | small | Also makes seat asymmetry modellable, which it currently is not. |
| **R7** | Separate `cathedral` from `inn`; stop scoring gardens as cloisters. | small | Inert today; do it while the file is open, or leave it and record it. |
| **R8** | Build the JCloisterZone differential oracle ([BACKLOG.md](../BACKLOG.md) 2026-08-02) and point it at the farm `city_sides` data. | ~an agent-day | The only thing that closes the "25 unaudited tile kinds" gap and the only permanent guard against this whole class. |

**Symmetry statement, for the record.** Every divergence above is symmetric between the two seats and
identical for both sides of every A/B we have ever run, so no historical relative ordering is
invalidated by this audit. What is *not* established is the transfer error from walled-C3-with-a-drifting-
cloister-scan to canonical C3 — and that is precisely the F9 question, unchanged.
