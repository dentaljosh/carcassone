"""Regression tests for `RiverRotationUtil` (engine river-segment rotation).

`RiverRotationUtil.get_river_rotation` decides how the next river tile must
be rotated so its river edge meets the previous tile's. Coverage of the
engine's river path was thin (BACKLOG 2026-04-28), and the function has two
easy-to-miss behaviors these tests pin:

  - it *implicitly returns `None`* (not `Rotation.NONE`) whenever the tile has
    no river, or there is no previous tile — the river-start case;
  - a straight river segment (`get_river_rotation_tile` -> `Rotation.NONE`)
    carries the *previous* rotation forward rather than reporting "no turn".

Most assertions are pure-geometry unit tests of `RiverRotationUtil`'s
classmethods plus checks against the real `the_river_tiles` data, so they do
not depend on driving a full game. `state_updater` is what tracks the result
across placements (it assigns `get_river_rotation`'s return into
`last_river_rotation` on every tile action).

`turn_side(s, 1)` rotates a side one step clockwise (TOP->RIGHT->BOTTOM->LEFT).
"""
from __future__ import annotations

import types

from wingedsheep.carcassonne.objects.rotation import Rotation
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.tile import Tile
from wingedsheep.carcassonne.tile_sets.the_river_deck import the_river_tiles
from wingedsheep.carcassonne.utils.river_rotation_util import RiverRotationUtil


def _game_state(last_tile_action, last_river_rotation=Rotation.NONE):
    """Minimal stand-in: `get_river_rotation` only reads these two attrs."""
    return types.SimpleNamespace(
        last_tile_action=last_tile_action,
        last_river_rotation=last_river_rotation,
    )


def _last_tile(tile):
    """Stand-in for a TileAction — only `.tile` is read."""
    return types.SimpleNamespace(tile=tile)


# --- tile-data assumptions the rotation logic relies on ---------------------

def test_river_terminus_tiles_carry_a_center_end():
    # river_start / river_end each have one board-edge end plus a CENTER end
    # (the spring / mouth). get_river_rotation_ends pops the non-connecting
    # end, so a terminus tile must still expose two ends or that pop raises.
    assert the_river_tiles["river_start"].get_river_ends() == {
        Side.CENTER, Side.BOTTOM
    }
    assert the_river_tiles["river_end"].get_river_ends() == {
        Side.TOP, Side.CENTER
    }


# --- get_connecting_side ----------------------------------------------------

def test_get_connecting_side_finds_the_matching_edge():
    # The new tile's TOP end meets a previous tile whose river exits BOTTOM.
    side = RiverRotationUtil.get_connecting_side(
        previous_river_sides={Side.TOP, Side.BOTTOM},
        river_sides={Side.TOP, Side.RIGHT},
    )
    assert side == Side.TOP


def test_get_connecting_side_returns_none_when_unconnected():
    # No end of the new tile has its opposite among the previous tile's ends.
    side = RiverRotationUtil.get_connecting_side(
        previous_river_sides={Side.TOP},
        river_sides={Side.TOP},
    )
    assert side is None


# --- get_river_rotation_ends: the pure rotation geometry --------------------

def test_straight_river_segment_yields_no_rotation():
    # Ends are opposite (connect via TOP, exit via BOTTOM) -> straight -> NONE.
    rotation = RiverRotationUtil.get_river_rotation_ends(
        previous_river_ends={Side.LEFT, Side.BOTTOM},
        river_ends={Side.TOP, Side.BOTTOM},
    )
    assert rotation == Rotation.NONE


def test_clockwise_bend():
    # Connect via RIGHT, exit via TOP; turn_side(TOP, 1) == RIGHT -> CW.
    rotation = RiverRotationUtil.get_river_rotation_ends(
        previous_river_ends={Side.LEFT, Side.TOP},
        river_ends={Side.TOP, Side.RIGHT},
    )
    assert rotation == Rotation.CLOCKWISE


def test_counter_clockwise_bend():
    # Connect via TOP, exit via RIGHT; turn_side(RIGHT, 3) == TOP -> CCW.
    rotation = RiverRotationUtil.get_river_rotation_ends(
        previous_river_ends={Side.BOTTOM, Side.RIGHT},
        river_ends={Side.TOP, Side.RIGHT},
    )
    assert rotation == Rotation.COUNTER_CLOCKWISE


# --- get_river_rotation_tile against the real river tiles -------------------

def test_straight_after_straight_is_none():
    rotation = RiverRotationUtil.get_river_rotation_tile(
        previous_tile=the_river_tiles["river_straight"],
        new_tile=the_river_tiles["river_straight"],
    )
    assert rotation == Rotation.NONE


def test_bend_after_straight_is_a_turn():
    # river_straight ends {TOP, BOTTOM}; river_bend ends {TOP, LEFT}.
    rotation = RiverRotationUtil.get_river_rotation_tile(
        previous_tile=the_river_tiles["river_straight"],
        new_tile=the_river_tiles["river_bend"],
    )
    assert rotation == Rotation.CLOCKWISE


def test_river_end_after_straight_does_not_crash():
    # river_end's CENTER end must not break the non-connecting-side pop.
    rotation = RiverRotationUtil.get_river_rotation_tile(
        previous_tile=the_river_tiles["river_straight"],
        new_tile=the_river_tiles["river_end"],
    )
    assert rotation == Rotation.NONE


# --- get_river_rotation: the implicit-None branches + carry-forward ---------

def test_get_river_rotation_is_none_at_river_start():
    # First tile of the game: no previous tile -> implicit None (NOT
    # Rotation.NONE). Pins the documented behavior.
    result = RiverRotationUtil.get_river_rotation(
        _game_state(last_tile_action=None),
        the_river_tiles["river_straight"],
    )
    assert result is None


def test_get_river_rotation_is_none_for_a_non_river_tile():
    # A base (non-river) tile -> has_river() False -> implicit None.
    result = RiverRotationUtil.get_river_rotation(
        _game_state(_last_tile(the_river_tiles["river_straight"])),
        Tile(description="plain_non_river"),
    )
    assert result is None


def test_get_river_rotation_straight_carries_forward_last_rotation():
    # A straight segment reports the *previous* rotation, not Rotation.NONE.
    result = RiverRotationUtil.get_river_rotation(
        _game_state(
            _last_tile(the_river_tiles["river_straight"]),
            last_river_rotation=Rotation.CLOCKWISE,
        ),
        the_river_tiles["river_straight"],
    )
    assert result == Rotation.CLOCKWISE


def test_get_river_rotation_bend_returns_the_computed_rotation():
    # A real bend overrides the carried-forward value with its own rotation.
    gs = _game_state(
        _last_tile(the_river_tiles["river_straight"]),
        last_river_rotation=Rotation.COUNTER_CLOCKWISE,
    )
    result = RiverRotationUtil.get_river_rotation(
        gs, the_river_tiles["river_bend"]
    )
    assert result == Rotation.CLOCKWISE
    assert result != gs.last_river_rotation
