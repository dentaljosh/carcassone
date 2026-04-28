"""Phase-aware action-space encoding for the wingedsheep engine.

The engine emits one of three Action types per decision, governed by
`state.phase`:

  GamePhase.TILES   -> TileAction(tile, coordinate, tile_rotations)
                       OR PassAction()  (no legal placement exists)
  GamePhase.MEEPLES -> MeepleAction(meeple_type, coordinate_with_side)
                       OR PassAction()  (skip placement)

We never see all three (position, rotation, meeple) jointly. This module
encodes/decodes via a phase-aware flat index parameterized by window size.

Index layout for window size W:

  0 .. W*W*4 - 1     TileAction.  index = (row * W + col) * 4 + rotation
  W*W*4              tile-phase Pass
  W*W*4 + 1 ..  + 5  MeepleAction NORMAL on {TOP, RIGHT, BOTTOM, LEFT, CENTER}
                                  of the just-placed tile
  W*W*4 + 6 ..  + 9  MeepleAction FARMER on
                                  {TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT}
  W*W*4 + 10         meeple-phase Pass

Total size: W*W*4 + 11 (= 2511 for W=25).

Window size is configured per-Game (see game_wrapper.Game) so we can retrain
at a different size without code changes if Phase 4 reveals 25 is wrong.
"""
from __future__ import annotations

from dataclasses import dataclass

from wingedsheep.carcassonne.objects.actions.action import Action
from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side


DEFAULT_WINDOW_SIZE = 25
N_ROTATIONS = 4

NORMAL_SIDES: tuple[Side, ...] = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT, Side.CENTER)
FARMER_SIDES: tuple[Side, ...] = (Side.TOP_LEFT, Side.TOP_RIGHT, Side.BOTTOM_LEFT, Side.BOTTOM_RIGHT)
N_MEEPLE_SLOTS = len(NORMAL_SIDES) + len(FARMER_SIDES) + 1  # +1 for meeple-phase pass


def tile_action_count(window_size: int) -> int:
    return window_size * window_size * N_ROTATIONS


def tile_pass_index(window_size: int) -> int:
    return tile_action_count(window_size)


def meeple_normal_base(window_size: int) -> int:
    return tile_pass_index(window_size) + 1


def meeple_farmer_base(window_size: int) -> int:
    return meeple_normal_base(window_size) + len(NORMAL_SIDES)


def meeple_pass_index(window_size: int) -> int:
    return meeple_farmer_base(window_size) + len(FARMER_SIDES)


def action_size(window_size: int) -> int:
    return meeple_pass_index(window_size) + 1


@dataclass(frozen=True)
class WindowOffset:
    """Translation + size for the centered window over the engine board.

    A tile at engine `Coordinate(r, c)` lives at window
    `(r - origin_row, c - origin_col)`. Window is `size x size`.
    """

    origin_row: int
    origin_col: int
    size: int

    def to_window(self, c: Coordinate) -> tuple[int, int] | None:
        wr, wc = c.row - self.origin_row, c.column - self.origin_col
        if 0 <= wr < self.size and 0 <= wc < self.size:
            return wr, wc
        return None

    def to_engine(self, wr: int, wc: int) -> Coordinate:
        return Coordinate(row=wr + self.origin_row, column=wc + self.origin_col)


class WindowOverflowError(Exception):
    """A tile placement falls outside the centered window."""


def encode_tile_action(action: TileAction, off: WindowOffset) -> int:
    win = off.to_window(action.coordinate)
    if win is None:
        raise WindowOverflowError(
            f"tile placement {action.coordinate} outside {off.size}x{off.size} window "
            f"centered at ({off.origin_row}, {off.origin_col})"
        )
    wr, wc = win
    return (wr * off.size + wc) * N_ROTATIONS + action.tile_rotations


def encode_meeple_action(action: MeepleAction, off: WindowOffset) -> int:
    if action.meeple_type == MeepleType.NORMAL:
        return meeple_normal_base(off.size) + NORMAL_SIDES.index(action.coordinate_with_side.side)
    if action.meeple_type == MeepleType.FARMER:
        return meeple_farmer_base(off.size) + FARMER_SIDES.index(action.coordinate_with_side.side)
    raise ValueError(
        f"unsupported MeepleType {action.meeple_type} (scope is NORMAL + FARMER only)"
    )


def encode(action: Action, off: WindowOffset, phase: str) -> int:
    """Encode any engine Action to a flat index. `phase` is "tiles" or "meeples"."""
    if isinstance(action, TileAction):
        return encode_tile_action(action, off)
    if isinstance(action, MeepleAction):
        return encode_meeple_action(action, off)
    if isinstance(action, PassAction):
        return tile_pass_index(off.size) if phase == "tiles" else meeple_pass_index(off.size)
    raise TypeError(f"unknown Action subtype: {type(action).__name__}")


def decode(
    idx: int,
    *,
    off: WindowOffset,
    phase: str,
    next_tile=None,
    last_tile_coord: Coordinate | None = None,
) -> Action:
    """Decode a flat index back to an engine Action.

    Phase determines whether we decode tile-half or meeple-half indices.
    `next_tile` is the engine tile being placed (TILES phase); the returned
    TileAction holds the tile rotated to the chosen rotation.
    `last_tile_coord` is the just-placed tile coordinate (MEEPLES phase).
    """
    total = action_size(off.size)
    if not (0 <= idx < total):
        raise ValueError(f"action index {idx} out of range [0, {total})")

    a_tile = tile_action_count(off.size)
    tile_pass = tile_pass_index(off.size)
    norm_base = meeple_normal_base(off.size)
    farm_base = meeple_farmer_base(off.size)
    meeple_pass = meeple_pass_index(off.size)

    if phase == "tiles":
        if idx == tile_pass:
            return PassAction()
        if idx >= a_tile:
            raise ValueError(f"index {idx} is meeple-phase but phase=tiles")
        if next_tile is None:
            raise ValueError("decoding a TileAction requires next_tile")
        cell, rot = divmod(idx, N_ROTATIONS)
        wr, wc = divmod(cell, off.size)
        coord = off.to_engine(wr, wc)
        return TileAction(tile=next_tile.turn(rot), coordinate=coord, tile_rotations=rot)

    if phase == "meeples":
        if idx < a_tile:
            raise ValueError(f"index {idx} is tile-phase but phase=meeples")
        if idx == tile_pass:
            raise ValueError(
                f"index {tile_pass} is tile-phase pass; meeple-phase pass is {meeple_pass}"
            )
        if idx == meeple_pass:
            return PassAction()
        if last_tile_coord is None:
            raise ValueError("decoding a MeepleAction requires last_tile_coord")
        if norm_base <= idx < norm_base + len(NORMAL_SIDES):
            side = NORMAL_SIDES[idx - norm_base]
            return MeepleAction(
                meeple_type=MeepleType.NORMAL,
                coordinate_with_side=CoordinateWithSide(coordinate=last_tile_coord, side=side),
            )
        if farm_base <= idx < farm_base + len(FARMER_SIDES):
            side = FARMER_SIDES[idx - farm_base]
            return MeepleAction(
                meeple_type=MeepleType.FARMER,
                coordinate_with_side=CoordinateWithSide(coordinate=last_tile_coord, side=side),
            )
        raise ValueError(f"index {idx} not assigned to any meeple action")

    raise ValueError(f"unknown phase: {phase!r} (expected 'tiles' or 'meeples')")
