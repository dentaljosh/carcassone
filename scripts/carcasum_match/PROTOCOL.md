# `carcasum_driver` — the stdin/stdout protocol

**Status:** current — the contract between `vendor/carcasum/Carcasum/driver/main.cpp`
(the C++ side) and `scripts/carcasum_match/match.py` (the Python side). Written
before either existed, so that neither gets to define the interface by accident.

This is the Carcasum analogue of `scripts/jcz_match/ai_engine.py`'s `%ai` / `aiMessage`
protocol. It is deliberately **simpler** than the JCZ one, because Carcasum has no
message chain, no `Confirm`, and no stateful AI-turn plumbing: `Game::step()` drives
both seats itself, so lockstep is a property of the loop rather than something the
driver has to maintain.

---

## 0. Who is the game of record

**Our engine is** — exactly as in `scripts/jcz_match/match.py`. Carcasum's `Game`
is a mirror that happens to also own the turn loop:

* the champion is seated inside Carcasum as an `ExternalPlayer`; when Carcasum asks
  it for a move, the driver blocks on stdin, Python asks the real champion on OUR
  board, forward-maps our action into Carcasum's coordinates, and answers;
* Carcasum's own player (`MCTSPlayer`) moves on its own; the driver reports the move,
  and Python **inverts it onto our action space by enumerating OUR legal actions and
  forward-mapping each one** until one matches. There is no inverse map anywhere —
  same discipline, same reason.
* if no legal action of ours matches, the game is `VOID_UNMAPPABLE` and the offered
  move plus our full legal set are recorded verbatim.

## 1. Framing

One JSON object per line, UTF-8, `\n`-terminated, on stdout. One JSON object per line
on stdin. The driver **must** `flush` after every line it writes, and must never write
anything to stdout that is not a protocol line — all logging goes to stderr. (The JCZ
harness lost time to exactly this: JCZ logs to stdout mid-protocol, and
`JczAiEngine._recv` has to sieve the stream. We do not repeat that mistake; stdout is
protocol-only by construction.)

Every line carries a `"t"` key naming its type.

## 2. Coordinates, rotation, node indices

| thing | Carcasum | ours |
|---|---|---|
| board | `size × size` with `size = 72`, `offset = size/2 = 36`; start tile at `(36, 36)` | 35×35, start at `(game.start_row, game.start_col)`, 25×25 action window |
| axes | `x` → east (`Tile::right`), `y` → **south** (`Tile::down`) | `row` → south, `column` → east |
| rotation | `TileMove::orientation ∈ {left=0, up=1, right=2, down=3}` = **quarter turns clockwise** from the tile template's base orientation. Proof: `getEdge(side, o) = edges[(4 + side - o) % 4]`, so at `o=1` the base `left`(W) edge answers for absolute `up`(N), i.e. W→N, a CW quarter turn. | `rot ∈ 0..3`, CW quarter turns of our tile representation |
| meeple | `MeepleMove::nodeIndex` — an index into `Tile::nodes[]`, i.e. **tile-local and rotation-invariant** | `(feature, side)` slot in `action_space` |

**Position map (Python side):** reuse `scripts/jcz_oracle/tile_map.to_jcz_position` —
JCZ's `(x, y)` convention is the same handedness as Carcasum's — then add the offset:
`carcasum_xy = (jcz_x + 36, jcz_y + 36)` relative to whatever origin
`to_jcz_position` was given. Do **not** hand-roll a second coordinate transform.

**Rotation map (Python side):** reuse `tile_map.jcz_rotation_quarters(rot, rot_cw90)`
where `rot_cw90` is the per-kind column of `tests/data/carcasum/TILE_MAPPING.tsv`.
The result *is* Carcasum's `orientation` (no `×90`, no degree string).

**Meeple map (Python side):** the driver's `dump_tiles` mode (§4) exports, for every
`tile_type`, every node index with its terrain and its **tile-local** half-edge label
set in JCZ vocabulary (`NL NR EL ER SL SR WL WR`, plus `CLOISTER`). Rotate those
labels by the placed tile's `orientation` (CW: `N→E→S→W→N`, `L`/`R` preserved) to get
board-absolute labels, then match against `tile_map.jcz_location_for(tile, side)` for
each of our legal meeple slots — the same forward-map-and-match the JCZ driver uses,
and with the same known multiplicity caveat (our slots are finer than theirs; a city
spanning two edges is one of their nodes and two of our slots — take the first in
canonical slot order and record `n_matching_slots`).

## 3. Session: `play` mode

### 3.1 Setup — Python → driver, first line

```json
{"t":"new_game",
 "deck":[2,0,0,23,...],          // 71 ints: Carcasum tileTypes, in OUR draw order
 "external_seat":0,               // seat the champion occupies (0 or 1)
 "opponent":{"kind":"mcts",       // "mcts" | "montecarlo" | "montecarlo2" | "uct" | "simple3" | "jcz" | "random"
             "budget_ms":5000,    // MCTSPlayer m, with mIsTimeout=true
             "playouts":null,     // if set, m = playouts and mIsTimeout=false
             "cp":0.5,
             "reuse_tree":false,
             "node_priors":false,
             "progressive_widening":false,
             "progressive_bias":false,
             "utility":"portion",  // Utilities::PortionUtility (the thesis 84% config)
             "playout":"random"},  // Playouts::RandomPlayout   (ditto)
 "seed":12345}                     // seeds Carcasum's DefaultRandom / RandomTable
```

The driver replies:

```json
{"t":"ready","start_tile_type":2,"start_xy":[36,36],"board_size":72,
 "deck_len":71,"players":["external","MCTSPlayer<PortionUtility,RandomPlayout>"],
 "revision":"5f5e365...","patches":["tiny_city_modern","upper_bound_modern"]}
```

⚠️ `deck` is **71** entries, not 72: Carcasum's `TileFactory::createPack` *prepends*
the positioned `RCr` tile and `Game::newGame` immediately does
`board->setStartTile(tiles.takeFirst())`, so the start tile is consumed before any
ply. `deck` therefore lists exactly what our `[next_tile] + deck` lists — the same
construction `jcz_match.draw_order_for` already uses.

The forced draw is implemented by a `ForcedTileProvider : public NextTileProvider`
whose `nextTile(game)` returns `game->getTileIndexByType(deck[i++])`. If the driver's
cursor runs past the end, or `getTileIndexByType` finds no tile of that type
remaining, it must emit `{"t":"fault","why":"deck_desync",...}` and stop — never fall
back to random.

### 3.2 The loop

The driver runs `while (game.step())`. Four line types can come out of it.

**(a) The driver needs the champion's tile move:**

```json
{"t":"req_tile","ply":0,"player":0,"tile_type":23,
 "placements":[[35,36,0],[35,36,1],...]}     // [x, y, orientation]
```

Python answers:

```json
{"t":"tile","x":35,"y":36,"o":0}
```

**(b) The driver needs the champion's meeple move:**

```json
{"t":"req_meeple","ply":0,"player":0,"tile_type":23,
 "placed":[35,36,0],
 "nodes":[{"i":0,"terrain":"field","labels":["NL","NR","EL","ER","SL","SR","WL","WR"]},
          {"i":1,"terrain":"road","labels":["W","E"]}]}
```

`nodes` lists **only the currently legal** node indices (i.e. what
`Game::getPossibleMeeplePlacements` offered, minus the null entry), with labels
already rotated to board-absolute by the driver. Python answers with a node index, or
`null` for "no meeple":

```json
{"t":"meeple","i":1}
{"t":"meeple","i":null}
```

Carcasum only *asks* when the player has a meeple in hand **and**
`possibleMeeples.size() > 1`. When it does not ask, no `req_meeple` is emitted and
Python must apply its own meeple-phase pass (see `ev_move.meeple: null` below).

**(c) A ply happened** (either side; emitted after every `step()` that placed a tile):

```json
{"t":"ev_move","ply":0,"player":1,"tile_type":23,
 "x":35,"y":36,"o":0,"meeple":null,
 "scores":[0,0],
 "score_detail":{"field":[0,0],"city":[0,0],"road":[0,0],"cloister":[0,0]},
 "meeples_left":[7,7],"discarded":0,"tiles_left":70,
 "ms":4998,"playouts":42879}
```

`score_detail` is `Game::playerScoresDetail[terrain][player]` — it is the whole reason
the audit can say *farm scoring specifically agreed* rather than *the totals happened
to agree*. `ms` / `playouts` are per-move and only meaningful for a search player
(`ms` for the external seat is the driver-side round-trip and should be ignored;
Python times the champion itself).

**(d) A tile was unplaceable and discarded** (no player was asked; the SAME player
keeps the turn — `Game::step()` does not call `setNextPlayer()` on this branch):

```json
{"t":"ev_discard","ply":0,"player":0,"tile_type":9,"discarded":1,"tiles_left":70}
```

Python must apply our TILES-phase pass here. Our `fixed_v1` redraw fix must produce
exactly this shape; a mismatch is the `UNPLACEABLE_TURN_LOSS` class.

**(e) End:**

```json
{"t":"game_over","scores":[71,68],
 "score_detail":{...},"plies":71,"discarded":0,
 "history":[{"tile_index":6,"tile_type":2,"x":35,"y":36,"o":0,"meeple":1}, ...]}
```

`history` is `Game::getMoveHistory()` verbatim, so it can be fed back through
`Game::newGame(..., history)` (or `storeToFile`) to reproduce the game exactly — that
is the replay oracle the divergence audit leans on.

**(f) Anything wrong:**

```json
{"t":"fault","why":"deck_desync|invalid_move|internal","detail":{...}}
```

After a `fault` the driver exits non-zero. Python turns that into `VOID_ERROR`.

### 3.3 Shutdown

`{"t":"quit"}` on stdin, or EOF, makes the driver exit 0. Python must always close
stdin and reap the child, and must kill it on timeout — an orphaned 5-s/move MCTS
process is a silent 100 %-of-a-core leak across a 400-game match.

## 4. `dump_tiles` mode

`carcasum_driver --dump-tiles` writes ONE json object and exits, with no game:

```json
{"t":"tiles","revision":"5f5e365...","count":24,
 "tiles":[{"tile_type":0,"id":"L","deck_count":4,
           "edges":["F","F","F","F"],          // base orientation, [left,up,right,down] = W,N,E,S
           "has_position":false,
           "nodes":[{"i":0,"terrain":"cloister","labels":["CLOISTER"],"pennant":0},
                    {"i":1,"terrain":"field","labels":["NL","NR",...],"pennant":0}]}, ...]}
```

This is the machine-checkable half of `tests/data/carcasum/TILE_MAPPING.tsv`: the TSV
is derived from *their XML*, this dump is derived from *their loader*, and the test
asserts the two agree. A hand-read XML that disagrees with the code that reads it is
exactly the failure the JCZ oracle's `verify_meeple_map.py` exists to catch.

Label vocabulary, derived from `TileFactory::readXMLTile`'s
`setEdgeNode(side, index, node)` calls:

* a **Field** edge fills slot 1 only → the whole edge is one field node;
* a **City** edge fills slot 1 only → **no field half-edges on a city edge**, which is
  precisely the R9 convention (our engine matches it under `CARCASSONNE_FIX_R9=1`);
* a **Road** edge fills slots 0, 1, 2 → field-left, road, field-right.

So a node's label set is recoverable from which `(side, slot)` pairs point at it. The
driver must emit it, not have Python guess it.

## 5. What the driver may NOT do

* No RNG fallback in the tile provider (see §3.1).
* No writing to stdout outside the protocol.
* No touching `Carcasum/player/**` — the search is the thing being measured.
* No silent clamping of an out-of-range move: an `x`/`y` outside the board is a
  `fault`, not a clamp.
