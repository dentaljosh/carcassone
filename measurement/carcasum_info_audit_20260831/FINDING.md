# Carcasum information audit — is `MCTSPlayer` clairvoyant?

**Status: COMPLETE (2026-08-30). Verdict: FAIR — not clairvoyant, in the engine and
across our bridge. No caveat is owed to T-TRANSFER, the rung interpretations, or the
E-5 protocol on information-hygiene grounds.**

Read-only source audit. Nothing was edited, built, or run against compute. Every claim
below is a `file:line` cite into `vendor/carcasum/` (upstream
`TripleWhy/Carcasum @ 5f5e365`, patch list in `vendor/carcasum/CARCASUM_PATCHES.md`) or
into our bridge.

---

## 1. Verdict

**FAIR.** Carcasum's `MCTSPlayer` re-randomizes the hidden bag at every chance
decision. It is not clairvoyant, and it cannot be — there is *no future to be
clairvoyant about* inside its own model of the game.

The mechanism, exactly:

1. **Carcasum's `Game` has no tile stack.** `Game::tiles` is a `QList<Tile *>` of the
   tiles *still to come*, i.e. an unordered **bag**, created in canonical pack order by
   `tileFactory->createPack()` and never shuffled
   (`Carcasum/core/game.h:89`; `Carcasum/core/game.cpp:38-84`, esp. `tiles = tileFactory->createPack(...)`
   and `board->setStartTile(tiles.takeFirst())`). The draw order of a real game is
   produced **just in time**, one tile per ply, by a `NextTileProvider`
   (`Carcasum/core/nexttileprovider.h:27-39`). There is no pre-dealt sequence stored on
   the `Game` object for a search to read.

2. **The search draws from the bag with its own RNG, never from the provider.**
   `Game` exposes two distinct draw paths (`Carcasum/core/game.h:236-237`):

   ```c
   inline int simNextTile() { return r.nextInt(tiles.size()); }   // search / rollouts
   inline int nextTile()    { return ntp->nextTile(this); }       // the REAL game only
   ```

   `nextTile()` has exactly one caller in the whole tree — `Game::step()`,
   `Carcasum/core/game.cpp:232` — which is the driver's real-game advance.
   `simNextTile()` has exactly one caller — `Game::simStep()`,
   `Carcasum/core/game.cpp:373` — which is the rollout advance. Grepping the tree for
   `getNextTileProvider` / `setNextTileProvider` finds **zero live callers**: the only
   hits are the accessor definitions (`core/game.h:193-194`) and a commented-out GUI
   line (`gui/mainwindow.cpp:387-388`). Nothing under `Carcasum/player/**` touches
   `ntp` at all.

3. **The MCTS chance node is a re-sample of the remaining multiset.** In
   `MCTSPlayer::treePolicy` (`Carcasum/player/mctsplayer.tpp:194-209`):

   ```c
   auto const & tiles = simGame.getTiles();
   int tileIndex = r.nextInt(tiles.size());
   Tile const * t = tiles[tileIndex];
   int const a = t->tileType;
   ```

   Uniform over the remaining **tile instances**, so the probability of a type is
   exactly its remaining multiplicity / remaining count — which is precisely the true
   posterior of the next draw under a uniformly shuffled bag. This is a *correct* fair
   chance model, not merely a fair-ish approximation, and it is re-sampled on **every
   visit** to that chance node (open-loop chance sampling), not fixed once per
   determinization.

4. **Chance expansion enumerates types, not the true tile.** `MCTSChanceNode` stores
   `TileCountType tileCounts` — the per-type remaining counts, taken from
   `g.getTileCounts()` at node creation (`mctsplayer.h:150`, `mctsplayer.tpp:639-644`).
   Its children vector is indexed by `tileType`, and a child is created only when that
   type is actually sampled (`expandChance`, `mctsplayer.tpp:283-289`). Applying a
   chance action removes an arbitrary instance of that *type* from the bag
   (`applyChance` → `g.simPartStepChance(g.getTileIndexByType(action))`,
   `mctsplayer.tpp:663-666`). No branch is keyed to "the tile that is actually next".

5. **Rollouts are equally blind.** `Playouts::RandomPlayout::playout` loops
   `simGame.simStep(&RandomPlayer::instance)` (`Carcasum/player/playouts.h:44-54`) →
   `simNextTile()` → uniform-from-bag. Same for `EarlyCutoff` and `EGreedy`
   (`playouts.h:69-92`, `133-...`).

6. **The search's copy of the game is built from the PAST only.** `MCTSPlayer` holds
   `Game const * game` (the real game) and a private `Game simGame = Game(0)` — an ntp
   of `nullptr` (`mctsplayer.h:188-189`), so `simGame` *cannot* call `nextTile()` at
   all. It is brought up to date by replaying the real game's **move history**:
   `Util::syncGamesFast` (`Carcasum/core/util.cpp:25-30`) replays
   `from.getMoveHistory()[i]` into `to.simStep(...)`, and `MCTSPlayer::newGame` does the
   same at game start (`mctsplayer.tpp:736-746`). `Game::moveHistory` is append-only,
   written *after* each move is played (`game.cpp:246`, and the `simStep` analogue), so
   it contains only played plies. The `reuseTree` path does the same, one history entry
   at a time (`mctsplayer.tpp:456-520`).

   Copying the *remaining bag* is legitimate public information — a Carcassonne player
   is entitled to know the tile distribution and what has been placed. It reveals
   nothing about order.

The same is true of the other wired opponents: `MonteCarloPlayer`,
`MonteCarloPlayer2`, `MonteCarloPlayerUCT` all advance their sims via
`simStep`/`simPartStepChance` on the already-revealed entry
(`montecarloplayer.tpp:81,87,158,164,168`; `montecarloplayer2.tpp:71,115`;
`montecarloplayeruct.tpp:76,127`) — never through `ntp`.

For completeness, the **GUI** build (the one `measurement/carcasum_owner_session_prep/`
sets up) is fair the same way: with `Game ▸ Random Tiles` ticked it calls
`rntp.nextTile(game)` = `r.nextInt(game->getTileCount())`
(`gui/mainwindow.cpp:340-352`; `core/nexttileprovider.cpp:21-24`) — a just-in-time
uniform draw from the remaining bag, with no stack to peek at. (Un-ticking it hands the
draw to the human's `Choose Tiles` picker, which the session protocol already names a
cheat switch — `measurement/carcasum_owner_session_prep/PROTOCOL.md:51`.)

---

## 2. The bridge: do WE hand Carcasum the future?

**We hand the future to the *process*, and it is structurally unreachable by the
search.** This is the part that deserved checking, and it is clean.

- `scripts/carcasum_match/match.py:1416-1417` sends
  `{"t":"new_game","deck": draw_order, "external_seat":…, "opponent":…, "seed":…}` where
  `draw_order` is **our full dealt deck in true draw order**, all 71 upcoming tiles
  (`draw_order_for`, `match.py:725-732`; contract in
  `scripts/carcasum_match/PROTOCOL.md:109-126` §3.1).
- The driver consumes it into a private `ForcedTileProvider`
  (`Carcasum/driver/main.cpp:245-271`), installed as the `Game`'s ntp
  (`driver/main.cpp:634-635` — `ForcedTileProvider * ftp = new ForcedTileProvider(deck); Game game(ftp);`).
- **That object is reachable only from `Game::step()`.** The opponent player is
  constructed from `tileFactory` + hyperparameters alone
  (`driver/main.cpp:439-457`) and is never handed the deck. `MCTSPlayer` holds the game
  as `Game const *`; `getNextTileProvider()` is a **non-const** member
  (`core/game.h:194`), so a `Game const *` could not call it even if any player wanted
  to — and none does (§1 item 2).
- **Empirical tripwire, already banked.** `ForcedTileProvider::nextTile` advances a
  cursor and `faultExit`s on overrun or on a type with no remaining instances — no RNG
  fallback, ever (`driver/main.cpp:254-271`). If the search consumed draws through the
  provider, the cursor would race ahead and every game would die of `deck_desync` within
  a few plies. The 400-game T-TRANSFER match banked **0 voids / 400 games, `voids` map
  empty, zero REAL divergences, 100% final-score/farm/replay agreement**
  (`measurement/carcasum_match_20260823/READOUT.md:45-59, 162-163`). Each game consumed
  exactly its 71 deck entries. That is a behavioural confirmation of the static read.

So: fair engine, and the bridge does **not** convert it into a clairvoyant one.

The E-5 / phone path is the *same* path, not a second one:
`scripts/carcasum_remote/server.py` delegates the whole game to
`match.play_one_match(...)` on its own thread with only `agent=`/`on_apply=` hooks added
(`server.py:380-397`, and the module docstring at `server.py:20-23` says a second
inverter is deliberately refused). The deck the phone plays against is a function of
`deck_seed` alone, seat-independent (`match.py:1324` `random.seed(int(deck_seed))`
before the deal), and the client replays the same `(deck_seed, actions)` pair — so both
sides face the identical tile order. There is no draw asymmetry to be "lucky" about.

---

## 3. Prior art: had anyone answered this?

**No.** Nothing in the Carcasum corpus poses or answers the clairvoyance question.
Greps for `clairvoy|determiniz|perfect.information|re-?shuffl|hidden|foresee|future tile|knows the deck|cheat`
across `measurement/carcasum_*/`, `scripts/carcasum_match/PROTOCOL.md`,
`scripts/carcasum_remote/README.md`, `docs/LEVER_INDEX.md` and
`vendor/carcasum/CARCASUM_PATCHES.md` return only:

- three hits on the **GUI `Choose Tiles`** cheat switch, in the owner-session prep
  (`carcasum_owner_session_prep/PROTOCOL.md:51`, `RULES_DELTA.md:139`, `SETUP.md:210`) —
  a *human*-side switch, not a search-side one;
- `determinization` hits that refer to **our own champion's** PIMC seed
  (`carcasum_rung2_prep/DESIGN.md:170`, `READ_RULE.md:85`), not to Carcasum.

The nearest thing to a prior statement is `PROTOCOL.md:128-134`, which notes the forced
deck "never touches their RNG" — true, and this audit is the reason why that is
load-bearing rather than incidental. The audit plan
(`measurement/carcasum_match_prep/AUDIT_PLAN.md`) gated rules fidelity, not information
hygiene. **This finding closes that gap.**

---

## 4. Caveats owed (none) — and the one honest asymmetry

**T-TRANSFER, the rung interpretations, and the E-5 protocol need no
information-hygiene caveat.** The +4.08 points/deck (paired, z=4.18, n=400) result and
every rung graded against this opponent are strength results against a fair
imperfect-information searcher. Do **not** edit those documents on the strength of this
finding; there is nothing to correct.

Two things are worth *stating* in E-5's readout, neither of which is a defect:

1. **Carcasum tracks the remaining bag exactly.** `getTileCounts()` is maintained
   perfectly (`game.cpp:38-84` and the per-step decrements), so its chance model is the
   true posterior at every ply. A strong human does not track 71 tiles that precisely.
   This is legitimate public information — every physical Carcassonne player may count
   the bag — but it is a real capability gap that can *read* as "it always seems to know
   what's coming", and it is the most likely honest source of the owner's
   lucky-draw impression. It is a knowledge asymmetry, not a foresight one.
2. **Chance is re-sampled per visit, not per determinization.** Carcasum is not a PIMC
   agent with a fixed world per rollout; it is open-loop over the bag. When comparing
   its behavioural signature against our champion's (which *is* determinized —
   `agent_seed`, `carcasum_rung2_prep/DESIGN.md:170`), that difference in chance
   handling is the relevant one, not a difference in what either side can see.

Also inherited unchanged, and already documented: a Carcasum game **cannot be
reconstructed** from `(deck_seed, actions)` because its RNG seed is compile-time only
(`static.h RANDOM_SEED`; `PROTOCOL.md:128-134`; `server.py:35-47`). That limits replay,
not fairness.

---

## 5. If it had been clairvoyant (it is not) — the fix, unimplemented

Not applicable: there is no clairvoyance switch to turn off, because the search never
consults `ntp` and `simGame`'s ntp is `nullptr`.

The only thing that could ever *introduce* clairvoyance here is a future change that
hands the search a provider. The one-line guard that would make that structurally
impossible — **NOT implemented, and deliberately not, because it touches
`Carcasum/core/**` and would change the `G-BINARY` anchor sha
(`scripts/carcasum_remote/server.py:107` `ANCHOR_SHA256`), which is the identity every
banked rung is graded against** — is:

```c
// Carcasum/core/game.h:236 — would pin the search to the bag by construction
inline int simNextTile() { Q_ASSERT(ntp == nullptr || !inSearch); return r.nextInt(tiles.size()); }
```

The cheap, zero-binary-change equivalent is a repo-side regression test asserting that
`grep -rn 'ntp\|NextTileProvider' vendor/carcasum/Carcasum/player/` stays empty. Also
not implemented; noted here so the next reader can add it deliberately.

---

## 6. Cites, one table

| Claim | Cite |
|---|---|
| No tile stack; `tiles` is the remaining bag, unshuffled | `vendor/carcasum/Carcasum/core/game.h:89`; `core/game.cpp:38-84` |
| Two draw paths, one for the real game and one for search | `core/game.h:236-237` |
| `nextTile()` (provider) called only by `Game::step()` | `core/game.cpp:232` |
| `simNextTile()` (uniform-from-bag) called only by `Game::simStep()` | `core/game.cpp:373` |
| MCTS chance node re-samples the bag every visit | `player/mctsplayer.tpp:194-209` |
| Chance node stores per-type remaining counts only | `player/mctsplayer.h:150`; `player/mctsplayer.tpp:639-644` |
| Chance action = remove an instance of that type | `player/mctsplayer.tpp:663-666` |
| `simGame` has a null provider | `player/mctsplayer.h:189` |
| Sim state built by replaying past history only | `core/util.cpp:25-30`; `player/mctsplayer.tpp:456-520, 736-746` |
| Rollouts blind (`simStep` loop) | `player/playouts.h:44-54` |
| Other MC players equally blind | `player/montecarloplayer.tpp:81,87`; `montecarloplayer2.tpp:71,115`; `montecarloplayeruct.tpp:76,127` |
| No live caller of `get/setNextTileProvider` | `core/game.h:193-194` (defs); `gui/mainwindow.cpp:387-388` (commented out) |
| GUI random draw is just-in-time uniform | `gui/mainwindow.cpp:340-352`; `core/nexttileprovider.cpp:21-24` |
| We send the full deck order in `new_game` | `scripts/carcasum_match/match.py:1416-1417, 725-732`; `scripts/carcasum_match/PROTOCOL.md:109-126` |
| Deck is held privately by `ForcedTileProvider` | `vendor/carcasum/Carcasum/driver/main.cpp:245-271, 634-635` |
| Opponent constructed with no deck access | `driver/main.cpp:439-457` |
| Desync would fault, not fall back to RNG | `driver/main.cpp:254-271` |
| 0 voids / 400 games — cursor never raced | `measurement/carcasum_match_20260823/READOUT.md:45-59, 162-163` |
| E-5 phone path reuses `play_one_match` verbatim | `scripts/carcasum_remote/server.py:20-23, 380-397` |
| Carcasum RNG is compile-time-seeded only | `scripts/carcasum_match/PROTOCOL.md:128-134`; `scripts/carcasum_remote/server.py:35-47` |
