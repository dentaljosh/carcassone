"""The parked `_legal_cache` non-injective rotation-signature fix.

Background: `game_wrapper.Game._legal_cache` (and the MCTS transposition
table, which reuses the same key) is keyed on `Game.string_representation`,
whose per-tile component -- `_tile_rotation_signature` = `(4 outer edges,
shield, chapel, flowers)` -- cannot distinguish rotation 0 from rotation 2 of
a 180-degree-rotationally-symmetric tile. The witness is `city_left_right`:
its 4 outer edges read `('grass', 'city', 'grass', 'city')` at BOTH
rotations, even though the tile's FARM SLOTS rotate (`farmer_positions` /
`tile_connections` / `city_sides` are permuted -- which absolute Side each
farm-slot ends up exposed on changes with rotation, and that is exactly what
cross-tile farm connectivity keys off of). Two genuinely different boards can
therefore collide on one cache key, and the second board to ask is served the
FIRST board's mask.

Localised 2026-08-17 by tiearb2 Stage-2's `G-BITEXACT` (moved 57/15,360
banked playout values -- 0.371%); parked as commit `05ed019c`. See
docs/PROGRAM_ROADMAP_2026-07-07.md's 2026-08-17 "by-catch" entry,
rust/carc/carc-core/src/tier1.rs's `LegalMaskCache` module docs, and
tests/test_tier1_rust.py::test_the_memo_collision_is_real_and_is_what_the_bank_carries
(the banked-replay contract test that certifies the tiearb2 rust port
reproduces this defect BIT-FOR-BIT, because it is what produced the banked
corpus).

`CARCASSONNE_FIX_LEGAL_CACHE_KEY` (module global `game_wrapper.
_FIX_LEGAL_CACHE_KEY`) makes the key injective on rotation by folding the
rotating farm-slot geometry (`_farm_slot_signature`) into the per-tile
signature. DEFAULT OFF -- see the flag's comment in game_wrapper.py for the
full reasoning; in short, the historical (colliding) signature is what the
banked Stage-1b corpus and its rust port are graded against, and that corpus
is BURNED (cannot be regenerated), so flipping the default would silently
invalidate every existing replay/analysis path with no way to re-verify.
"""
from __future__ import annotations

import numpy as np
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

import carcassonne_ai.game_wrapper as gw
from carcassonne_ai.game_wrapper import ENGINE_START_COL, ENGINE_START_ROW, Game

# An adjacent, always-empty cell in a freshly-initialised board -- used to
# hand-place a `city_left_right` tile without going through ActionUtil
# legality (this is white-box testing of the caching layer, not of tile
# placement rules).
_COORD = Coordinate(ENGINE_START_ROW, ENGINE_START_COL + 1)


def _reset_rot_sig_cache(*tiles) -> None:
    """`_tile_rotation_signature` memoizes on the (canonically-shared,
    process-lifetime) Tile instance itself, keyed by nothing but presence --
    it has no notion of `_FIX_LEGAL_CACHE_KEY`. Toggling the flag mid-session
    (as these tests do) would silently read a stale pre-toggle signature back
    off the shared singleton `Tile.turn(...)` object without this reset."""
    for t in tiles:
        t._rot_sig_cache = None


def _board_with_city_left_right(g: Game, *, seed: int, rotation: int):
    """A fresh init board (deterministic via `seed`) with a real,
    hand-placed `city_left_right` tile at `rotation` sitting at `_COORD`.
    Returns `(board, tile)`."""
    import random

    random.seed(seed)
    board = g.get_init_board()
    tile = base_tiles["city_left_right"].turn(rotation)
    _reset_rot_sig_cache(tile)
    board.state.board[_COORD.row][_COORD.column] = tile
    board.state.placed_coords.add(_COORD)
    return board, tile


def test_city_left_right_is_edge_symmetric_but_its_farm_slots_rotate() -> None:
    """Precondition check, not the bug itself: confirms the witness tile
    actually has the property the whole fix rests on, so the rest of this
    file isn't quietly testing a tile that doesn't exhibit it."""
    tile0 = base_tiles["city_left_right"].turn(0)
    tile2 = base_tiles["city_left_right"].turn(2)

    edges0 = tuple(tile0.get_type(s).value
                   for s in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT))
    edges2 = tuple(tile2.get_type(s).value
                   for s in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT))
    assert edges0 == edges2, "witness precondition: 4 outer edges must tie across rot 0/2"

    farm0 = gw._farm_slot_signature(tile0)
    farm2 = gw._farm_slot_signature(tile2)
    assert farm0 != farm2, (
        "witness precondition: farm-slot geometry must actually differ by "
        "rotation, or this tile can't demonstrate the defect")


def test_tile_rotation_signature_collision_and_fix(monkeypatch) -> None:
    """The root cause, directly: `_tile_rotation_signature` collides for
    city_left_right rot 0 vs rot 2 with the fix OFF (the historical,
    documented, DEFAULT behaviour -- asserted explicitly here so it stays a
    tracked contract, not an accident), and is injective with the fix ON."""
    tile0 = base_tiles["city_left_right"].turn(0)
    tile2 = base_tiles["city_left_right"].turn(2)

    monkeypatch.setattr(gw, "_FIX_LEGAL_CACHE_KEY", False)
    _reset_rot_sig_cache(tile0, tile2)
    sig0_off = gw._tile_rotation_signature(tile0)
    sig2_off = gw._tile_rotation_signature(tile2)
    assert sig0_off == sig2_off, (
        "FIX OFF (default/historical): the 180-symmetric-tile collision is "
        "real and reproduced -- this IS the documented defect, not a bug in "
        "this test")

    monkeypatch.setattr(gw, "_FIX_LEGAL_CACHE_KEY", True)
    _reset_rot_sig_cache(tile0, tile2)
    sig0_on = gw._tile_rotation_signature(tile0)
    sig2_on = gw._tile_rotation_signature(tile2)
    assert sig0_on != sig2_on, "FIX ON: the key must now be injective on rotation"


def test_legal_cache_wrong_mask_on_collision_then_correct_with_fix(monkeypatch) -> None:
    """End-to-end through `Game.get_valid_moves`'s `_legal_cache`.

    Two Boards place a REAL `city_left_right` tile at rotation 0 (board_a)
    and rotation 2 (board_b) at the same coordinate, with an otherwise
    identical init state (same seed -> same deck/next_tile/scores/etc, so
    every OTHER component of `string_representation` matches too) -- so with
    the fix OFF their `_legal_cache` keys collide for real, unmocked, engine
    reasons (proven directly above).

    `Game._compute_mask` is monkeypatched to a trivial per-board-identity
    function so the "true" mask each board should get is deterministically
    distinguishable, without needing to reproduce a real cross-trajectory
    farm-adjacency divergence in a unit test (that IS the real production
    mechanism -- see scripts/tiletie/diagnose_tier1_cache_collision.py, which
    found 57/15,360 actual divergent masks this way, across independent
    playout trajectories sharing one `Game` object's cache -- just too
    coincidence-dependent to construct deterministically here). The cache
    KEY LOGIC under test is 100% real and unmocked.
    """
    for fix_on in (False, True):
        monkeypatch.setattr(gw, "_FIX_LEGAL_CACHE_KEY", fix_on)
        g = Game(enable_legal_moves_cache=True)

        board_a, tile_a = _board_with_city_left_right(g, seed=424242, rotation=0)
        board_b, tile_b = _board_with_city_left_right(g, seed=424242, rotation=2)
        assert tile_a is not tile_b

        mask_a = np.zeros(g.get_action_size(), dtype=bool)
        mask_a[100] = True
        mask_b = np.zeros(g.get_action_size(), dtype=bool)
        mask_b[200] = True
        board_a._probe_tag = "A"
        board_b._probe_tag = "B"

        def fake_compute_mask(self, board, _a=mask_a, _b=mask_b):
            return _a if getattr(board, "_probe_tag", None) == "A" else _b

        monkeypatch.setattr(Game, "_compute_mask", fake_compute_mask)

        key_a = g.string_representation(board_a)
        key_b = g.string_representation(board_b)

        got_a = g.get_valid_moves(board_a)  # populates the cache under key_a
        np.testing.assert_array_equal(got_a, mask_a)
        got_b = g.get_valid_moves(board_b)

        if fix_on:
            assert key_a != key_b, "FIX ON: the injective key must not collide"
            np.testing.assert_array_equal(
                got_b, mask_b,
                "FIX ON: board_b must get its OWN (correct) mask")
        else:
            assert key_a == key_b, (
                "FIX OFF: this IS the documented historical collision -- "
                "city_left_right rot 0/rot 2 share one string_representation key")
            np.testing.assert_array_equal(
                got_b, mask_a,
                "FIX OFF: board_b is WRONGLY served board_a's cached mask "
                "(the historical, default, documented behaviour)")
