# F9 / D1 — JCloisterZone runtime replay oracle: validation

> **Status: BUILT + VALIDATED 2026-08-03.** This is stage **D1** of the oracle that
> [measurement/jcz_spike_20260803/SPIKE_REPORT.md](../jcz_spike_20260803/SPIKE_REPORT.md)
> GO'd at 1–1.5 agent-days (D0 — the tile-data pytest — merged earlier as
> `tests/test_jcz_tile_oracle.py`). The spike's one named unknown, the **meeple-slot
> (`location`) mapping**, is **resolved and verified**; see §3.
>
> Harness: [`scripts/jcz_oracle/`](../../scripts/jcz_oracle/) · CI:
> `tests/test_jcz_replay_oracle.py` · artifacts: the `*.json` beside this file.
> No cluster, no cloud spend; ~10 min wall-clock on the local box, niced.

---

## TL;DR

1. **The oracle works end to end.** Full 142-ply games replay through both engines in
   lockstep with the deck handed to JCZ verbatim (`ForcedDrawTilePack`), diffing the
   legal-move set, the running scores and the whole Field/City/Road partition at every
   ply. 128 games across 7 legs, **zero unclassified divergences in any of them**.
2. **The money number: 43 of 43.** Every game in which no *named* rules divergence
   intervened agrees with JCloisterZone on the **exact final scores** — 20/20 under
   `fixed_v1`+R9, and 43/43 counting the uncontaminated games of every leg. That
   includes a real human-vs-champion E4 game reproduced score-for-score, **111–113**.
3. **`fixed_v1` + R9 is clean outright** — not "explained", but *empty*: zero
   divergences of any class, 20/20 exact final scores (leg D). The audit's five named
   differences and R9 are, between them, a **complete** account of where our engine
   parts company with JCZ on the base game.
4. **R9 flips its class exactly as predicted, and the merge is real under champion
   play.** With R9 off, the champion corpus shows `FARM_ATOM_SET` on 2474 plies and —
   the one that actually moves points — **`FARM_PARTITION` 66 times**, i.e. two
   under-city field strips genuinely merged through a city. With R9 on, both are **0**.
   The spike measured the *configuration* rate at 3.3% of games under **random** play
   and warned champion play would be higher; it is.
5. **The three classes `fixed_v1`+R9 still cannot close are named and bounded** —
   the bounded board, the 25×25 action window, and garden semantics. §5.

---

## 1. What the harness does

`scripts/jcz_oracle/replay_diff.py` drives both engines from one recorded game:

| signal | ours | JCZ | compared as |
|---|---|---|---|
| legal tile placements | `get_valid_moves` → window cell × rotation | `action.items[].options` | set of `(x, y, degrees)` |
| legal meeple slots | 9 `Side` slots | `Meeple` action options | set of `(feature, location-token-set)` — see §3 |
| running scores | `state.scores` | `players[].points` | per seat, offset-corrected |
| feature partition | `CityUtil` / `RoadUtil` / `FarmUtil.find_all_farms` | `features[].places` | **set of atom-sets**, where an atom is `(x, y, edge-or-half-edge)` |

The partition comparison is the load-bearing one and is deliberately identity-free:
each feature becomes the set of `(tile, half-edge)` atoms it spans, so the diff is
independent of feature ordering, naming, and internal representation on both sides.
It also separates **data** divergence from **traversal** divergence — the atom *sets*
are compared first (`FARM_ATOM_SET`), then the partition *induced on the atoms both
sides agree exist* (`FARM_PARTITION`). That split is what lets the report say the R9
tile-data bug is present on 2474 plies but only *merges* two fields 66 times.

Three protocol footguns are absorbed in `jcz_driver.py` / `tile_map.py` and are worth
knowing before touching this code:

* `rotation` is an **int** inside `action.options` but the enum string `"R180"` inside a
  `PLACE_TILE` payload; an int silently no-ops the ply (the spike's A5).
* a `FeaturePointer` needs `position` **and** `location` **and** `feature`; omit one and
  the JVM throws a bare NPE to stderr and emits **no state line** at all. The driver
  therefore sends JCZ's own option dict back verbatim, and routes stderr to a file so a
  refusal surfaces as a `JczError` with the trace instead of a hang.
* JCZ names an edge-mask location by its **registered constant**, so a 3-edge city is
  `"_E"` ("everything but E") and a straight road is `"WE"` — neither is parseable by
  splitting characters. Half-edge names and edge names live in **different bit planes**
  of the same mask, so `N` is *not* `NL|NR`. `tile_map.JCZ_EDGE_LOCATIONS` is the table.

### The one methodological correction

A recorded `(deck_seed, actions)` pair is **rules-relative**. Under `fixed_v1` the same
action ints decode to a *different* — and generally illegal — game, because the retail
start tile, the redraw rule and the recentred grid all move the action space and the
turn parity (`game_wrapper` says as much at `DRAW_RULE_*`). Replaying a walled archive
under fixed rules measures our own mis-replay, not the two engines' rules.

So the fixed-rules legs keep the **deck** — the thing the oracle needs held constant —
and generate their own deterministic legal trajectory (`--policy seeded`, uniform over
the legal set from a dedicated `random.Random`; the engine touches the *global* stream
only in the deck shuffle, so the deck is unperturbed). The harness also refuses a
record that is illegal under the profile it was asked to replay (`RECORD_ILLEGAL`)
rather than playing it and blaming JCZ. Leg E (`walled` + `seeded`) exists so the
walled↔fixed comparison holds the policy fixed and varies only the rules.

---

## 2. Results — per-class divergence counts

Counts are **ply-level events**, not games: `FARM_ATOM_SET` recurs on every ply after
the offending tile is on the board, so its magnitude reflects board persistence, not
frequency of occurrence. `SCORE_FINAL_EXPLAINED` likewise absorbs the running-score
mismatch count of a game whose finals disagree.

| divergence class | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| `DESYNC_FALLOUT` | 273 | 140 | 42 | 0 | 352 | 0 | 18 |
| `FARM_ATOM_SET` | 2474 | 0 | 2840 | 0 | 0 | 0 | 178 |
| `FARM_PARTITION` | 66 | 0 | 0 | 0 | 0 | 0 | 30 |
| `MEEPLE_DEPLOY_UNMIRRORED` | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `R9_MEEPLE_FALLOUT` | 0 | 0 | 7 | 0 | 0 | 0 | 2 |
| `SCORE_FINAL_EXPLAINED` | 1365 | 1365 | 0 | 0 | 512 | 112 | 112 |
| `SEAT_DESYNC` | 2 | 2 | 0 | 0 | 1 | 0 | 0 |
| `START_TILE_MEEPLE` | 20 | 20 | 0 | 0 | 15 | 1 | 1 |
| `START_TILE_PLY` | 20 | 20 | 0 | 0 | 20 | 2 | 2 |
| `UNPLACEABLE_TURN_LOSS` | 3 | 3 | 0 | 0 | 2 | 0 | 0 |
| `WALL_LEGALITY` | 147 | 147 | 0 | 0 | 259 | 25 | 25 |
| **any REAL (unclassified)** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |

| leg | corpus | profile | policy | R9 | games | terminal scores agree | unclassified |
|---|---|---|---|---|---|---|---|
| A | champ ×20 | walled | record | off | 20 | 0/18 | none |
| B | champ ×20 | walled | record | **on** | 20 | 0/18 | none |
| C | champ decks ×20 | fixed_v1 | seeded | off | 20 | **20/20** | none |
| **D** | champ decks ×20 | **fixed_v1** | seeded | **on** | 20 | **20/20** | none |
| E | champ decks ×20 | walled | seeded | on | 20 | 7/19 | none |
| F | E4 ×2 | walled | record | on | 2 | 1/2 | none |
| G | E4 ×2 | walled | record | off | 2 | 1/2 | none |

*(the `agree/compared` denominator excludes games whose seats desynced, where per-seat
scores stop being comparable at all; ~142 plies were compared per game in every leg.)*

### The money number, stated precisely

**43 of 43.** Restricting to games in which **no contaminating event occurred** — no
start-tile meeple, no unplaceable-tile turn loss, no seat desync, no unmirrorable
deploy — the two engines agree on the **exact final scores** in every single game:

| leg | uncontaminated games | of which finals agree |
|---|---|---|
| C (`fixed_v1`, R9 off) | 18 | **18** |
| D (`fixed_v1`, R9 on) | **20** | **20** |
| E (`walled`, seeded) | 4 | **4** |
| F (E4, `walled`, recorded human games) | 1 | **1** |

Under `fixed_v1`+R9 *every* game is uncontaminated, which is the cleanest form of the
claim: **20/20 games, zero divergences of any class, exact final scores.**

### What each leg pair isolates

* **A vs B (R9 off → on, champion corpus, everything else held).** `FARM_ATOM_SET`
  2474 → 0 and `FARM_PARTITION` 66 → 0. The 66 is the spike's Finding 1 firing in
  production play: two `city_top_straight_road` cities meet, and our surplus `TLT`/`TRT`
  half-edges let `find_farm` walk a field **through** the city and merge two strips that
  JCZ keeps apart. Terminal-score agreement does **not** improve (0/18 either way)
  because it is dominated by a larger walled divergence — see A vs E.
* **C vs D (the same flip on the clean profile).** Same extinction. Note C still scores
  20/20: with R9 off the surplus half-edges are present on 2840 plies but `FARM_PARTITION`
  never fires in those 20 seeded games, so the data bug stays *latent*. **The atom-set
  divergence is the bug; the partition divergence is the bug doing damage** — which is
  exactly why the harness reports them as two classes and not one.
* **D vs E (same policy, walled vs fixed_v1).** 20/20 → 7/19. Everything lost is the
  audit's named set, led by `START_TILE_MEEPLE`: our engine lets player 0 put a meeple
  on the start tile, which JCZ has **no ply to express**, and from that moment the two
  boards hold different meeple supplies. In the champion archive it fires in **20 of 20**
  games — the champion always meeples the start tile — which is why leg B's terminal
  agreement is 0/18 with nothing else wrong. In every one of those 20 games **player 1's
  final score matches JCZ exactly** and only player 0's differs, which is the signature
  of a single extra meeple and a useful independent check that nothing else is adrift.
* **F / G (the E4 human-vs-champion archives).** Game `867966` — Joshua's 111–113 loss —
  carries **only** `START_TILE_PLY` and reproduces **111–113 exactly** on an independent
  implementation. Game `161583`, the known "invisible border" game, carries
  `WALL_LEGALITY` ×25 *and* `START_TILE_MEEPLE`; its 73→59 gap is therefore **explained
  but not attributable** to the wall alone by this harness, since the start-tile meeple
  contaminates it first. Do not quote the 14 points as a wall cost.

---

## 3. The meeple-slot mapping (the spike's named unknown)

Our action space offers 9 slots on the just-placed tile — NORMAL on
`{TOP, RIGHT, BOTTOM, LEFT, CENTER}`, FARMER on the four corners. JCZ instead points at
a **feature**: `{"position": [x,y], "location": …, "feature": …}`. The mapping is:

| our slot | resolved on the placed tile by | JCZ `feature` | JCZ `location` |
|---|---|---|---|
| NORMAL `TOP`/`RIGHT`/`BOTTOM`/`LEFT` | the `tile.city` group, or the `tile.road` `Connection`, containing that edge | `City` / `Road` | the **named edge mask** of the group's non-`CENTER` edges — `"N"`, `"WE"`, `"SW"`, `"NWSE"`, and `"_N".."_W"` for a 3-edge city |
| NORMAL `CENTER` | `tile.chapel` | `Monastery` | `"I"` (interior) |
| FARMER corner | the `FarmerConnection` whose `farmer_positions` contains that corner | `Field` | its `tile_connections` as JCZ half-edges, `.`-joined — `"EL.WR"` |

No rotation arithmetic is involved: the board holds `Tile.turn(t)`, whose `city`, `road`
and `farms` are already in board orientation, so the slot resolves directly.

Two structural facts the differ must respect:

* **Our slots are finer than JCZ's.** A city spanning TOP and RIGHT is two of our slots
  and one JCZ option; a 3-corner field is three slots and one option. Meeple legal-sets
  are therefore compared **canonicalised to the JCZ `(feature, location)` key**, never
  slot-for-slot. This is an encoding difference, not a rules difference.
* **Token order is not meaningful** — comparison is on parsed token *sets*, so `"WE"`
  and `"EW"` are the same thing and JCZ's shorthand naming is invisible to the diff.

### Verification — 121/121, semantically

`scripts/jcz_oracle/verify_meeple_map.py` does **not** stop at "JCZ accepted the
pointer". For every deployed meeple it re-derives, on **both engines independently**,
the entire feature the meeple landed on — ours via `CityUtil.find_city` /
`RoadUtil.find_road` / `FarmUtil.find_farm_by_coordinate`, JCZ's from the `features`
array — and compares their **multi-tile atom sets**. A label that happened to parse but
pointed at the wrong feature passes the first check and fails this one.

```
deploys=121  feature-verified=121  feature-MISMATCH=0  unmapped=0
distinct (kind, rotation, slot) rows: Field 38 · City 32 · Road 25 · Monastery 5
```

That is **100 distinct mapping rows across all four feature types**, well past the ≥5
hand-verification the charter asked for, and the farm rows are the demanding ones —
verified regions run up to **36 atoms across many tiles**, e.g.

| our tile kind | turns | our slot | JCZ feature | JCZ location | atoms verified |
|---|---|---|---|---|---|
| `bent_road` | 1 | `top_right` | `Field` | `NR.EL.ER.SL.SR.WL` | 36 |
| `city_top_right` | 3 | `bottom_left` | `Field` | `EL.ER.SL.SR` | 19 |
| `full_city_with_shield` | 3 | `left` | `City` | `NWSE` | 7 |
| `chapel_with_road` | 2 | `center` | `Monastery` | `I` | 1 |
| `city_top_straight_road` | 0 | `left` | `Road` | `WE` | 6 |

The full table is [`MEEPLE_MAPPING.tsv`](MEEPLE_MAPPING.tsv) (100 rows, regenerate with
`verify_meeple_map.py`). **Risk retired: the D1 unknown is closed.**

---

## 4. The divergence taxonomy

Expected divergence is **classified and counted**, never failed on — a harness that
aborted on the first known difference would be useless. Anything outside the classified
set is REAL and exits non-zero (`--fail-on-real`, which is what the pytest runs).

| class | what it is | closed by |
|---|---|---|
| `START_TILE_PLY` | our first tile is a *player move*; JCZ pre-places a fixed D tile | `fixed_v1` (A4) |
| `START_TILE_MEEPLE` | …and that player may meeple it, which JCZ cannot express | `fixed_v1` (A4) |
| `UNPLACEABLE_TURN_LOSS` | our TILES-phase Pass discards **and hands over the turn** | `fixed_v1` (A3 redraw) |
| `SEAT_DESYNC` | the two engines disagree about who is to move | `fixed_v1` |
| `SCORE_TIMING` | a running-score gap that reconciles by the terminal (A2 cloister scan drift) | `fixed_v1` (A2) |
| `WALL_LEGALITY` | JCZ offers a placement our bounded grid does not | **not fully** — §5 |
| `WINDOW_OVERFLOW` | a placement the 25×25 action space cannot encode | **not at all** — §5 |
| `FARM_ATOM_SET` / `FARM_PARTITION` | R9 — a field half-edge on a city edge, and the merge it causes | `CARCASSONNE_FIX_R9=1` |
| `R9_MEEPLE_FALLOUT` / `MEEPLE_DEPLOY_UNMIRRORED` | the same R9 half-edges arriving through the meeple legal-set | `CARCASSONNE_FIX_R9=1` |
| `DESYNC_FALLOUT` | any later diff downstream of a **contaminating** event | — |
| `SCORE_FINAL_EXPLAINED` | a final-score gap in a game that carries a score-moving class | — |

Two design decisions worth defending, because they are where a taxonomy like this
usually goes soft:

* **Contamination is flagged at the site where the two states actually part company,
  never inferred from the counter.** Once a meeple exists on one side only, or the turn
  order slips, every later legal-set or score difference is that one event's shadow.
  `WALL_LEGALITY` is deliberately **not** contaminating and **not** score-moving: it only
  ever *adds* options on JCZ's side, and our player picks from *our* set, so the boards
  stay identical — and the data agrees, since leg E contains games with `WALL_LEGALITY`
  and exact score agreement.
* **A final-score gap is only a finding when nothing classified could have caused it.**
  A game carrying a score-moving class gets `SCORE_FINAL_EXPLAINED` (classified); a game
  carrying none and still disagreeing gets `SCORE_FINAL` (REAL, exits 1). This is the
  assertion that will catch the *next* rules bug.

---

## 5. What `fixed_v1` + R9 still cannot match

Stated plainly, because "20/20" invites over-reading:

* **The board is bounded and JCZ's is not.** `fixed_v1` moves the start tile to row 18
  of the 35×35 grid, buying 18 rows of headroom instead of 6 and making the wall
  unreachable in practice — `WALL_LEGALITY` went 147 → 0 across legs B → D. It is
  **not closed by construction**: a game that pushed 18 tiles in one direction would
  still diverge. The class shrinks toward zero; it is not proved empty.
* **The 25×25 action window is untouched by any rules profile.** It is a
  *representation* cap that spec §A1 keeps as a separate decision (J4), so a placement
  outside it is unencodable — meaning our recorded games can never *contain* one, and it
  can only ever appear as a legal move JCZ offers and we cannot express. `WINDOW_OVERFLOW`
  fired 0 times here, which is evidence about these decks, not a guarantee.
* **Garden semantics.** The 8 "flowers" tiles' *geometry* is certified (spike Q2), but
  JCZ scores gardens via its own `GardenCapability` while we score them as cloisters
  (audit R7). Gardens are kept **off** in the JCZ setup so the comparison is like for
  like; garden semantics remain outside the oracle's reach.
* **Ownership and tie-breaks are not diffed at feature level** — only the feature
  *partitions* and the *scores* are. Two engines could in principle disagree about who
  owns a contested farm while agreeing on both partition and totals; that would be
  invisible here. (It would have to be a compensating pair of errors, so this is a
  small gap, but it is a gap.)
* **One reference implementation, one tile set.** JCZ `basic:2` only. Strong evidence of
  edition identity, not proof — the spike's caveat still stands.

---

## 6. Reproducing

```bash
# the jar (NOT vendored — 28 MB, shaded; the spike records the 2-minute build)
ls ~/jcz_spike/JCloisterZone/build/Engine.jar

# all seven legs (~10 min, local box, niced)
scripts/jcz_oracle/run_validation.sh

# one leg
.venv/bin/python scripts/jcz_oracle/replay_diff.py \
    --games measurement/champ_action_logs/champ_games.jsonl --limit 20 \
    --profile fixed_v1 --policy seeded --r9 --fail-on-real --out /tmp/D.json

# the meeple-mapping evidence
.venv/bin/python scripts/jcz_oracle/verify_meeple_map.py \
    --games measurement/champ_action_logs/champ_games.jsonl --limit 8 --r9

# the tables in this report
.venv/bin/python scripts/jcz_oracle/summarize.py measurement/jcz_oracle_20260803

# CI (skips cleanly when the jar is absent)
pytest tests/test_jcz_replay_oracle.py
```

`--r9` re-execs with `CARCASSONNE_FIX_R9=1` if it is not already set: `base_deck`
latches the flag at **import** time and there is no per-`Game` seam to thread it through.

## 7. Files

| file | what it is |
|---|---|
| `scripts/jcz_oracle/tile_map.py` | the representation map — half-edges, edges, coordinates, rotation, and the meeple-slot resolution. Reads the spike's `TILE_MAPPING.tsv`; vendors nothing new. |
| `scripts/jcz_oracle/jcz_driver.py` | subprocess driver over the line-JSON protocol, with the three footguns absorbed |
| `scripts/jcz_oracle/replay_diff.py` | the differ + the divergence taxonomy + the CLI |
| `scripts/jcz_oracle/verify_meeple_map.py` | the semantic meeple-mapping verification (§3) |
| `scripts/jcz_oracle/summarize.py` | renders §2's tables from the artifacts, so they cannot drift |
| `scripts/jcz_oracle/run_validation.sh` | the seven legs |
| `A_*.json … G_*.json` | per-leg artifacts: per-game counts, samples with the first 3 instances of each class, finals |
| `MEEPLE_MAPPING.tsv` | 100 verified `(kind, rotation, slot) → (feature, location)` rows |
| `tests/test_jcz_replay_oracle.py` | CI mode — clean-profile emptiness, walled-classification, and an R9-flip guard against the fix regressing to a no-op |
