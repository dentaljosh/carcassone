# JCloisterZone differential-oracle — feasibility spike

> **Status: COMPLETE 2026-08-03. Verdict = GO, with a scope correction.** This is the ~half-day
> go/no-go that [docs/F9_BUILD_SPEC_20260802.md](../../docs/F9_BUILD_SPEC_20260802.md) §4 (Phase D)
> and §7 J6 gate the 1–2 agent-day build behind. Both unpriced risks are **retired**. The spike also
> **already found the bug the oracle was built to look for** — see [Finding 1](#finding-1).

| | |
|---|---|
| Spike cost | ~2 h, one box (local), no cloud spend |
| Downloads | `~/jcz_spike/` (JCZ git clone 3.2 MB, Maven 3.9.9, ~28 MB shaded jar) — nothing in the repo tree except `jcz_basic_5x.xml` |
| Repo changes | this directory only; **no engine edits** |
| Blockers found | none |

---

## TL;DR

1. **The data-file route works and needs no Java at all.** JCZ ships its tile definitions as a
   declarative XML file whose farm model is *the same shape as ours* (8 named half-edges + adjacent
   cities). The whole priority-1 check — farm/city adjacency for all 32 tile kinds — is a **~250-line
   Python parser**, already written and run in this spike.
2. **It found a real bug on the first run.** Exactly **1 of our 32 tile kinds** disagrees with JCZ:
   `city_top_straight_road` (JCZ `BA/RCr`, **4 copies in the deck**) declares two half-edges that lie
   *on its own city edge*, which makes `FarmUtil.find_farm` **merge two fields through a city**.
   Reproduced end-to-end. The other 31 kinds are **byte-for-byte equivalent** to JCZ.
3. **The runtime route also works** — and was cheaper than feared. JCZ 5.x *is* a headless engine
   (`com.jcloisterzone.engine.Engine`) with a **line-delimited JSON stdin/stdout protocol**. It built
   clean in ~2 min on the JDK 17 already installed, and it emits per-ply **legal-move sets, running
   scores, and every Field/City/Road feature with its exact tile-places**. Risk J6-1 ("no scriptable
   API → reprices to a week") is **refuted**.
4. **The edition mismatch (risk J6-2) does not exist.** JCZ's tile-set `basic:2` **is** the C3 base
   game with the 8 garden ("flowers") variants substituted in place — the exact edition we model. The
   deck-count multiset matches ours **32/32 kinds, 72/72 tiles**. The spec's planned workaround
   (map each garden tile to its plain counterpart, treat as an assumption test) is **unnecessary**;
   the 8 garden tiles are directly present and their geometry now **checks clean**, closing the
   audit's "*the 8 flowers tiles' non-garden geometry was assumed, not checked*" gap outright.

---

## Q1 — Can JCZ be driven headlessly on this box?

**Yes, both ways. And the data-file route alone answers the priority-1 question, so the runtime is a
bonus, not a dependency.**

### Route A (the collapse) — data files only, no Java

The engine repo (`farin/JCloisterZone`, master = v5, HEAD `29a1561` 2023-03-27) does **not** contain
tile definitions; `TilePackBuilder.createTilePack(List<String> definitions)` reads XML from
caller-supplied file paths. They ship in the **client** repo:

```
https://raw.githubusercontent.com/farin/JCloisterZone-Client/master/src/extraResources/expansions/basic.xml
```

(vendored here as `jcz_basic_5x.xml`, 243 lines). The README's link to
`JCloisterZone/master/src/main/resources/tile-definitions/` is **stale — it 404s**; the 4.x branch
still has an older copy (`<pack>`/`<farm>` schema, pre-garden) if a second opinion is ever wanted.

The schema is exactly the model we need:

```xml
<tile id="BA/RCr">
  <road>W E</road>
  <city>N</city>
  <field city="N">EL WR</field>      <!-- farm region + which cities it touches -->
  <field>ER SL SR WL</field>
</tile>
```

`<field>` = a farm region as a set of the 8 half-edges; `city="…"` = the cities that region scores
from. That is a direct structural analogue of our `FarmerConnection(tile_connections=…, city_sides=…)`.
**No runtime is needed to diff it.**

### Route B — the headless engine

- **JDK 17.0.19 was already installed** (`/usr/lib/jvm/java-17-openjdk-amd64`). No system packages
  needed. Maven is not installed; the 3.9.9 binary tarball dropped into `~/jcz_spike/` works fine
  (note: `dlcdn.apache.org` served an HTML redirect stub — use `archive.apache.org`).
- **Build:** `mvn -q -B -DskipTests package` → **clean, ~2 min**, producing a self-contained
  `build/Engine.jar` (28 MB, shaded, `Main-Class: com.jcloisterzone.engine.Engine`).
  *(The `target/engine-5-SNAPSHOT.jar` beside it is the thin jar and has no manifest — use `build/Engine.jar`.)*
- **Protocol** (`Engine.run()`): directives (`%load <tiles.xml>`, `%bulk on|off`, `%state`), then one
  `GAME_SETUP` JSON line, then one `{"type":…,"payload":…}` line per ply
  (`PLACE_TILE` / `DEPLOY_MEEPLE` / `PASS` / `COMMIT`). After **every** message it prints one line of
  JSON containing the whole game state.
- **Deterministic deck replay is a first-class feature.** `gameAnnotations.tilePack` can select
  `com.jcloisterzone.debug.ForcedDrawTilePack` with an explicit `drawOrder` list. **We never have to
  match JCZ's RNG** — we hand it our deck order directly. This was the single biggest unpriced risk
  in the action-translation work and it is gone.

Verified live (`jcz_headless_smoke.py`) — the emitted state carries all three oracle signals:

```
legal action : {"player":0,"canPass":false,"items":[{"type":"TilePlacement","tileId":"BA/RCr",
                "options":[{"position":[1,0],"rotations":[0,180]}, …]}]}     <- legality (priority 2)
players      : [{"points":0,…},{"points":0,…}]                              <- scoring  (priority 3)
features     : {"type":"Field","places":[[0,0,"EL.WR"]],"owners":[],"cities":1}   <- farms (priority 1)
```

Top-level state keys: `action, deployedMeeples, discardedTiles, features, flags, history,
neutralFigures, phase, placedTiles, players, tilePack, tokens, turnPlayer, undo`.
`history` carries the scoring events; `features[].places` gives farm-region equality directly.

---

## Q2 — Mapping JCZ's representation to ours

### The half-edge convention (the load-bearing piece)

Both engines name the same 8 half-edges; they are both **clockwise from the NW corner**, so the map
is a straight relabelling with **no reflection and no offset**:

| clockwise idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| **JCZ** | `NL` | `NR` | `EL` | `ER` | `SL` | `SR` | `WL` | `WR` |
| **ours** (`FarmerSide`) | `TLT` | `TRT` | `TRR` | `BRR` | `BRB` | `BLB` | `BLL` | `TLL` |
| edge | N/`TOP` | N | E/`RIGHT` | E | S/`BOTTOM` | S | W/`LEFT` | W |

Read it as: our names are `<corner><edge>` in screen coordinates (`TRR` = top-right corner, Right
edge = the north half of the east edge); JCZ's are `<edge><first-or-second going clockwise>`
(`EL` = east edge, first half clockwise = the north half). **They agree.**

Two independent confirmations that the convention is right, not just self-consistent:

- Our patched involution pairs `{TLT,BLB} {TRT,BRB} {TLL,TRR} {BLL,BRR}`
  (`side_modification_util.opposite_farmer_side`, the 2026-05-29 `TRT→BRB` fix) map under the table
  to `{NL,SR} {NR,SL} {WR,EL} {WL,ER}` — precisely mirror-across-the-shared-border in JCZ's naming.
- 31 of 32 tile kinds then match **field-for-field with zero residual**, which a wrong convention
  could not produce.

Rotation: 90° clockwise maps half-edge `i → (i+2) mod 8` and edge `e → (e+1) mod 4`, identically on
both sides. Base orientations differ per tile, so the differ searches all 4 rotations; the resolved
rotation is the `rot` column of `TILE_MAPPING.tsv`.

### Hand-verified end to end

**(a) `city_top_crossroads` ↔ `BA/CRRR`** — unaudited kind, ×3, 3-way field split, rot 0.

| | |
|---|---|
| ours | city `[TOP]`; roads `S–C`, `W–C`, `E–C`; farms `{TLL,TRR}`+city`[TOP]` · `{BLL,BLB}` · `{BRB,BRR}` |
| ours → JCZ labels | `{WR,EL}`+city`{N}` · `{WL,SR}` · `{SL,ER}` |
| JCZ | `<field city="N">WR EL</field>` · `<field>WL SR</field>` · `<field>ER SL</field>` |
| verdict | **identical** (3/3 regions, city adjacency matches) |

**(b) `city_top_right` ↔ `BA/CC.2`** — unaudited kind, ×1, **two separate cities**, rot 3.
This one exercises both the rotation convention and the multi-city `city="N W"` attribute.

| | |
|---|---|
| ours (base) | cities `[[TOP]]`, `[[RIGHT]]` (two distinct features); farm `{TLL,BRB,BLB,BLL}` + city_sides `[TOP,RIGHT]` |
| ours → JCZ labels, base | `{WR,SL,SR,WL}` adjacent to cities `{N}` and `{E}` |
| rotate 3×90° CW (`i→i+6 mod 8`) | `{EL,NR,NL,ER}` adjacent to cities `{W}` and `{N}` |
| JCZ | `<city>N</city><city>W</city>` · `<field city="N W">EL ER SL SR</field>` |
| verdict | **identical** — JCZ's `city="N W"` resolves to the same two city features |

**(c) `city_top_straight_road` ↔ `BA/RCr`** — ×4, rot 0. **The one divergence** — see below.

### Ambiguities found (all resolved; record them in the adapter)

| # | ambiguity | resolution |
|---|---|---|
| A1 | JCZ names a *city* in a `field city="…"` attribute by **one representative edge label**, not by all its edges (`BA/Ccc` has `<city>N E W</city>` but `<field city="N">`). | Resolve each label to the **city feature** (frozenset of its edges) containing it, then compare feature sets. Done in `jcz_tile_diff.py`. Comparing raw labels would false-positive. |
| A2 | A **road edge still carries field on both halves** (a road is a line, not a band), but a **city edge carries none**. A naive "is this half-edge on a non-field edge" check flags legitimate road-edge halves. | Only flag half-edges on **city** edges. This distinction *is* the bug detector — see Finding 1. |
| A3 | Base orientations differ per tile between the two decks. | Match up to rotation; record the resolved rotation. 32/32 resolved uniquely by (deck count × rotation-invariant skeleton), with a field-signature tiebreak for the two chiral pairs (`CRr`/`RrC`). |
| A4 | Tile-**id** granularity: JCZ splits by pennant *and* garden (`Cc.1`/`Cc+`/`CcG`/`Cc+G`), we split the same way (`city_diagonal_top_right{,_shield,_flowers,_shield_flowers}`). | 1:1. No aliasing needed. (Note JCZ writes ids `BA/Rr` in XML but `BA.Rr` in 4.x saved games — pick one and normalise.) |
| A5 | JCZ positions are `[x, y]` with **y increasing downward/north-negative**; our coordinates are `(row, column)`. | `x = column − col0`, `y = row − row0`. Confirmed live: from a start tile at `[0,0]`, the northern neighbour is `[0,-1]`. Also `rotation` is serialised as an **int** in `action.options` but as the **enum string `"R180"`** in `PLACE_TILE` payloads — a real footgun; a plain int silently no-ops the ply. |

---

## Finding 1 — the oracle's first bug, found by the data diff alone

**All 32 kinds compared; 31 MATCH; 1 FIELD DIFF.**

```
--- city_top_straight_road  <->  BA/RCr   (x4 in deck, rot 0)
    edges (N E S W)  : C R F R
    JCZ  fields      : [EL WR] + city{N}      [ER SL SR WL]
    ours fields      : [NL NR EL WR] + city{N}      [ER SL SR WL]
    >>> ours claims half-edges lying ON A CITY EDGE: NL NR

GLOBAL SWEEP: field regions claiming a half-edge that lies on a CITY edge
  ours: 1 kind(s) — city_top_straight_road: NL NR
  JCZ : 0 kind(s)  -- clean
```

The tile is base-game **A/RCr**: city on the north edge, road running west–east, a thin field strip
between them. Our `FarmerConnection` for that strip lists
`tile_connections = [TLL, TLT, TRT, TRR]`, but **`TLT` and `TRT` are the two halves of the north
edge — and the north edge is a city.** JCZ lists `EL WR` (= our `TRR`, `TLL`) only. It is the **only**
kind in our deck that claims a field half-edge on a city edge; JCZ's whole base set is clean.

### Why it is not cosmetic

`FarmUtil.find_farm` crosses a `tile_connection` **unconditionally** — there is no grass/city gate
anywhere on the traversal (by design: the data is supposed to encode that). So the surplus
`TLT`/`TRT` let the field walk **straight through the city**.

`rcr_merge_probe.py` builds the two-tile board and asks:

```
two RCr tiles, cities joined across the shared N/S border
  lower tile (0,0) north field  -> region cells: [(-1, 0), (0, 0)]
  upper tile (-1,0) south field -> region cells: [(-1, 0), (0, 0)]
  RESULT: MERGED  ***  the two under-city field strips are ONE farm.

control -- same board with the surplus TLT/TRT removed:
  region cells: [(0, 0)]   -> separate
```

The control isolates the cause to those two entries and nothing else. JCZ, driven headlessly on the
identical board, keeps them apart — four distinct `Field` features, the two under-city strips scoring
independently:

```
{"type":"Field","places":[[0, 0,"EL.WR"]],"cities":1}
{"type":"Field","places":[[0,-1,"ER.WL"]],"cities":1}
```

### Consequences (all four matter)

1. **Farm scoring.** Two fields that should be separate become one, so a farmer on either collects
   the completed cities adjacent to **both** — and two farmers who should each own a field instead
   contest one. Worth ±3 points per affected city, exactly the audit's predicted failure mode.
2. **Meeple legality/valuation.** The merged region changes which fields already have a farmer,
   i.e. it changes the *legal-looking* and *valuable-looking* farmer placements the leaf sees.
3. **It is in the leaf.** `flat_leaf.py` is a de-objectified rewrite of the same decomposition over
   the same `base_deck` data, so the divergence is in the **production hot path**, not only the
   object scorer. *(The spike did not separately re-derive it there — see "not done" below.)*
4. **Symmetric.** Like every divergence in the 2026-08-02 audit, it hits both seats identically, so
   **no historical A/B ordering is invalidated**. It is a transfer-error term, not a re-baseline of
   past results.

### How often does it fire?

`rcr_frequency.py`, 300 random games (43,166 plies), counting boards where two `RCr` tiles end up
with their cities meeting:

```
games with >=1 trigger  : 10  (3.3%)
trigger pairs total     : 10  (0.033 per game)
```

**Read this as an order-of-magnitude ceiling, not a verdict**, for three reasons:
(a) it is the *configuration* rate — the score only actually moves if a farmer sits on one of the
merged strips and the merged city sets differ, so the score-changing rate is **strictly lower**;
(b) **random play is not champion play**, and champion play packs cities much harder, so the true
rate under production play is likely **higher** — this is the same caveat that makes audit item **R1**
(re-run `rf_cloister_rate.py` under champion play) a prerequisite, and the same script pattern applies;
(c) n=300 on a ~3% event is ±1.0pp (1σ).

**Recommended fix (one line of data, not code):** drop `FarmerSide.TLT, FarmerSide.TRT` from the
north `FarmerConnection` of `city_top_straight_road` in `base_deck.py`. It belongs in the **F9
remediation set behind a default-off flag** with the same gating as R2/R4 — it changes results, and
`feedback_bug_fix_shifts_optima` applies (this one perturbs *farm* scoring, which is exactly what the
v2.7 leaf's farm caps were tuned against). **Suggest a new remediation id `R9`.** It is cheaper than
R2 and strictly better evidenced.

---

## Q3 — Scoring cross-check: is the tile-data diff the valuable 80%?

**The data diff was the valuable 80%** — it is done, it cost ~2 h, and it closed the audit's
"single largest unaudited surface" with a live bug in hand. **But the runtime half is no longer the
expensive part it was priced as, so the answer is "both", in that order.**

Against the audit's own risk model:

| oracle priority | what closes it | status after this spike |
|---|---|---|
| **1. farm `city_sides` for the 25 unaudited kinds** — "*the single largest unaudited surface left*" | data-file diff | ✅ **CLOSED.** All 32 kinds diffed (not 25 — the 7 spot-checked came free). 31 clean, 1 bug found and reproduced. Also closes the separate "*8 flowers tiles' non-garden geometry assumed, not checked*" gap: `basic:2` contains all 8, all clean. |
| **2. legality / the per-ply legal-placement set** (certifies A1, the wall) | runtime replay | ⏳ needs the driver, but the protocol emits it directly (`action.items[].options`) and `ForcedDrawTilePack` removes the RNG problem. **De-risked, not done.** |
| **3. scoring cross-check** (mechanise "zero scoring-amount errors") | runtime replay | ⏳ same driver; `players[].points` + `history` give during-game events and finals. **De-risked, not done.** |

Two things only the runtime can do, which is why it should still be funded:

- **It is the permanent CI referee.** The data diff is a one-shot certificate that goes stale the
  moment anyone edits `base_deck.py` — cheap to re-run, but it only guards *data*. The replay
  harness guards *traversal + scoring + legality* on every commit touching `engine/` or the Rust core.
- **Legality is the check that would have caught the wall**, and it is the one that certifies A1. No
  amount of tile-data diffing reaches it.

Honest limits of the data-only route, stated plainly:

- It certifies **tile data**, not the **traversal** that consumes it. (Our traversal has its own
  history — the 2026-05-29 `TRT→BRB` non-bijection.) Finding 1 was found *because* the data encodes
  a geometric fact; a traversal bug with clean data would be invisible to it.
- It says nothing about the five **structural** divergences the audit already names (walled board,
  cloister scan drift, unplaceable-tile turn loss, random start tile, WC tie-break). Those are ours
  by construction and are the F9 Phase-A work.
- **`basic:2` matching our deck is strong evidence, not proof, of edition identity.** It is a 32-kind,
  72-tile count-multiset match plus 31/32 field-exact agreement, which is about as good as this gets
  without a physical rulebook — but it is still one source.

---

## Verdict — **GO**, with a scope correction

The 1–2 agent-day build is de-risked: **both J6 risks are retired**, the JDK was free, the build is
2 minutes, the protocol is documented above, and the RNG-matching problem — which was the real cost
driver behind "the tile-id mapping and the action translation are the work" — **does not exist**
because `ForcedDrawTilePack` takes our deck order verbatim.

**Scope correction:** the spec sequenced the oracle as *one* deliverable gated on a spike. It should
be **two**, because half of it is already finished and its verdict should not wait for the other half:

### Stage D0 — land now (~0, already built)

`jcz_tile_diff.py` + `jcz_basic_5x.xml` in this directory, promoted to `tests/` as a **pytest that
fails on any `base_deck.py` field-data divergence from JCZ**. It runs in well under a second, needs
no Java, and would have caught Finding 1 the day the data was typed. Do this **before** Phase A, so
the R9 fix lands against a green oracle.

### Stage D1 — the replay harness (1–1.5 agent-days, revised down)

Build order, cheapest-informative-first:

1. **`scripts/rules_oracle/jcz_driver.py`** — subprocess wrapper over `build/Engine.jar`:
   `%load` → `GAME_SETUP` (with `ForcedDrawTilePack` = our deck order) → one message per ply,
   parse one state line back. `%bulk on` for speed; drop to `%bulk off` only when diffing per-ply.
   *(The spike's `jcz_headless_smoke.py` is this file's skeleton.)*
2. **`scripts/rules_oracle/tile_map.py`** — `TILE_MAPPING.tsv` promoted to a checked-in constant,
   plus the half-edge table and the `(row,col)↔[x,y]` / `R{n}` rotation conversions from Q2/A5.
3. **Action translation** — our action index → `PLACE_TILE{tileId,rotation:"R…",position:[x,y]}`
   + `DEPLOY_MEEPLE{pointer:{position,location},meepleId}` / `PASS`. **This is the remaining real
   work**: the meeple-slot mapping (our `Side`/`FarmerSide` slot → JCZ `location` like `NW`,`CITY`,`N`)
   is the one piece the spike did **not** verify. Budget most of the day here.
4. **The differ** — per ply compare: legal-set digest, `players[].points`, `features` partition
   (Field regions especially), free-meeple counts. Emit first-divergence ply + a minimal repro board.
5. **CI mode** — N golden games replayed on commits touching `engine/` or the Rust core.

### Two riders

- **A per-ply legality diff will light up immediately and that is expected, not a harness bug.** We
  knowingly diverge on the walled board, the random start tile, and the unplaceable-tile rule. Run
  the oracle against the **A-phase fixed-rules build** (or with those flags on), or the signal drowns.
  This should be stated in the spec: **D1 is gated on Phase A, D0 is not.**
- The **8 garden tiles**: geometry is now certified, but JCZ scores gardens via its own
  `GardenCapability`, and we deliberately do not model garden *semantics* (audit R7 notes we currently
  score gardens as cloisters). Keep `garden` **off** in the JCZ setup so the scoring diff compares
  like with like, and keep treating garden semantics as out of the oracle's reach — the spec's
  honesty caveat still stands, just for a smaller set of reasons.

### Not done here (so nobody assumes it was)

- No check that `flat_leaf.py` / the Rust core reproduce the merge (argued from shared data, not measured).
- No score-delta measurement for Finding 1 — only the configuration rate, under **random** play.
- No meeple-slot (`location`) mapping verified — the main remaining unknown in D1.
- Only `basic:2` compared; no other tile set, and no second independent implementation consulted.

### Alternative reference implementations (checked, per the NO-GO/PIVOT branch)

Not needed — but for the record, JCZ is the right pick and no pivot is warranted. Its tile data is
**declarative XML** (parseable with zero runtime), it is the only mature open implementation that
ships the **C3 garden edition** as a first-class tile set, and its engine is **already headless with a
documented replay path**. Anything else would trade all three away.

---

## Files in this directory

| file | what it is |
|---|---|
| `SPIKE_REPORT.md` | this report |
| `jcz_basic_5x.xml` | JCZ's base-game tile definitions, vendored from `farin/JCloisterZone-Client@master:src/extraResources/expansions/basic.xml` |
| `jcz_tile_diff.py` | the differ — parses both decks, resolves the 32-kind mapping up to rotation, diffs field data. **Exit 1 on any diff** (ready to promote to a pytest) |
| `TILE_MAPPING.tsv` | the 32-row mapping table: our kind ↔ JCZ id ↔ deck count ↔ rotation ↔ both sides' field data ↔ verdict |
| `TILE_DIFF_OUTPUT.txt` | captured run of the differ (the evidence for Finding 1) |
| `rcr_merge_probe.py` | two-tile board proving the merge, with a control that isolates the cause |
| `rcr_frequency.py` | trigger-rate measurement over random games |
| `jcz_headless_smoke.py` | drives `build/Engine.jar` over the JSON protocol; the D1 driver skeleton |

### Reproducing

```bash
# data-only route (no Java)
.venv/bin/python measurement/jcz_spike_20260803/jcz_tile_diff.py
.venv/bin/python measurement/jcz_spike_20260803/rcr_merge_probe.py

# runtime route
mkdir -p ~/jcz_spike && cd ~/jcz_spike
git clone --depth 1 https://github.com/farin/JCloisterZone.git
curl -sLO https://archive.apache.org/dist/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz
tar xzf apache-maven-3.9.9-bin.tar.gz
~/jcz_spike/apache-maven-3.9.9/bin/mvn -q -B -DskipTests package \
    -f ~/jcz_spike/JCloisterZone/pom.xml          # -> build/Engine.jar, ~2 min
.venv/bin/python measurement/jcz_spike_20260803/jcz_headless_smoke.py
```
