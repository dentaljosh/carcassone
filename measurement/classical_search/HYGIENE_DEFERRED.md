# Hygiene items DEFERRED — touch a LIVE eval-screen code path (apply after the screen)

**Date:** 2026-07-14 · **Status:** PREPARED, NOT APPLIED · **Source:** BACKLOG re-audit T4 (items c + d).

Context: a CLAIRVOYANT PUCT eval screen (C7 Term-R) was RUNNING on both boxes when this
bundle was done. Its workers re-spawn per launcher retry-iter and load code fresh from disk,
so editing any file on `scripts/classical_search/eval_puct_priors.py`'s import graph would
contaminate a live measurement. Both items below land in exactly such a file, so they were
NOT applied. The other two T4 code items (T4d PIMC deck-sort → `fair_agent.py`; T4e npz
value_target stamp → `gen_fair_selfplay.py`) are OFF the eval path and were applied +
committed.

**Apply these two after the screen finishes** (verify no `eval_puct_priors` run is active:
`pgrep -af eval_puct_priors || echo clear`), each with its own test + commit.

---

## (c) `deck_hash` omits the first drawn tile — in `eval_provenance.py` (ON the eval path)

**Why deferred:** the omission lives in `src/carcassonne_ai/eval_provenance.py::deck_hash`,
which is imported by the running screen (`eval_puct_priors.py:112
from carcassonne_ai.eval_provenance import deck_hash`). Editing it mid-run would make the
recorded `deck_hash` provenance column inconsistent across worker generations of the same
measurement. → DEFERRED.

**Note:** the *other* `deck_hash` (in `scripts/human_anchor/play_harness.py:56`, the human
harness — off the eval path) ALREADY includes the first tile (`[next_tile] + deck`). It needs
no change. Only the eval_provenance copy has the blind spot.

**The bug:** the engine draws the FIRST tile into `state.next_tile` at init
(`engine/wingedsheep/carcassonne/carcassonne_game_state.py:31` `self.next_tile =
self.deck.pop(0)`; `game_wrapper.get_init_board` comments "+1 for the first tile already
drawn into next_tile"). So `board.state.deck` at init is MISSING that first tile — two decks
differing only in the first drawn tile hash-collide.

**Proposed diff (`src/carcassonne_ai/eval_provenance.py`):**
```python
 def deck_hash(board) -> str:
     """Stable 16-hex identity of a game's shuffled deck, computed at init (before
     any tile is drawn). Lets a results row prove which deck it played and lets us
     detect overlap with trained-on self-play decks (outside-review A9)."""
-    descs = tuple(t.description for t in board.state.deck)
+    st = board.state
+    # The engine draws the FIRST tile into `next_tile` at init (deck.pop(0)), so
+    # `state.deck` alone omits it — two decks differing only in that first tile
+    # would collide. Hash the FULL initial deck: [next_tile] + deck.
+    tiles = ([st.next_tile] if st.next_tile is not None else []) + list(st.deck)
+    descs = tuple(t.description for t in tiles)
     return hashlib.sha256(repr(descs).encode()).hexdigest()[:16]
```

**Test impact:** no test pins a LITERAL deck_hash value — `tests/test_eval_provenance.py::
test_deck_hash_deterministic_and_seed_sensitive` checks only determinism + seed-sensitivity
+ 16-char length (all still hold); `test_c5_leaf_ab.py` / `test_c5_fair_leaf_ab.py` /
`test_rr_roundrobin_harness.py` compare deck_hash between two runs for equality, not against
a literal. So no test needs a value update; optionally ADD a regression test that two decks
differing only in `next_tile` now produce different hashes.

**Migration caveat to note when applying:** this changes the hash *value* for every deck, so
new eval rows' `deck_hash` become incomparable to OLD rows' `deck_hash` (cross-epoch
deck-overlap detection). That is acceptable (the old hash was defective) but worth a
one-line DECISIONS stamp so a future overlap check does not silently compare across the
format change.

---

## (d) Abbots defensive assert — appropriate spot is `game_wrapper.py` (ON the eval path)

**Why deferred:** the natural, central scope-guard spot is in
`src/carcassonne_ai/game_wrapper.py` (the `Game` wrapper already enforces scope there — the
`INNS_AND_CATHEDRALS` / `ABBOTS` `NotImplementedError` guards in `Game.__init__`, lines
281-290). `game_wrapper.py` is imported by the running screen (`eval_puct_priors.py:113`)
and is explicitly on the do-not-edit list. A consumer-local assert (e.g. in the gen or fair
path) would not be a *central* scope guard, so this belongs in the wrapper. → DEFERRED.

**Invariant:** locked scope is 2p Base+Farmers, NO Abbots. With FARMERS-only rules the engine
sets `state.abbots = [0, 0]` (`carcassonne_game_state.py:34`) and no `ABBOT` meeple can ever
be placed, so `any(state.abbots)` is always False. The assert is a strict no-op in every
valid game and fires loud only if an out-of-scope ABBOTS state slipped past the `__init__`
guard (which would otherwise silently mis-score gardens/abbots).

**Proposed diff (`src/carcassonne_ai/game_wrapper.py`, in `get_init_board`):**
```python
     def get_init_board(self) -> Board:
         state = CarcassonneGameState(
             players=self.players,
             tile_sets=list(self.tile_sets),
             supplementary_rules=list(self.supplementary_rules),
         )
+        # Scope guard (locked scope = 2p Base+Farmers, NO Abbots): a base+farmers
+        # state has abbots == [0, 0] and no ABBOT meeple can ever be placed. If this
+        # fires, an out-of-scope ABBOTS state slipped past the __init__ guard and
+        # would silently mis-score — fail loud instead of scoring the wrong game.
+        assert not any(state.abbots), (
+            f"scope violation: abbots enabled ({state.abbots}); locked scope is "
+            "2p Base+Farmers, no Abbots")
         # +1 for the first tile already drawn into next_tile.
         total_tiles = len(state.deck) + 1
         return Board.from_state(state, total_tiles, self.window_size)
```

**Test when applying:** add `test_get_init_board_asserts_no_abbots` — a default
`Game()` init board passes (no raise); constructing a `CarcassonneGameState` with
`SupplementaryRule.ABBOTS` and feeding it through a path that reaches the assert raises
`AssertionError`. (The `Game.__init__` ABBOTS guard already blocks the wrapper-level
construction, so the direct-state test is the one that exercises the new assert.)

---

*Both prepared; apply after the C7 screen concludes, one commit each, tests included, per the
CLAUDE.md operating norms.*
