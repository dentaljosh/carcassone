"""Centered-window tensor encoding of a Carcassonne board state.

The wingedsheep engine stores tiles on an internal 35x35 grid offset by a
fixed `starting_position`. We re-center the placed tiles into a smaller
W x W window and encode them as a multi-channel tensor for the network.
W is configurable (see DEFAULT_WINDOW_SIZE in action_space).

Channel layout (current-player-relative; mine/opp swap is done in canonical_swap):

  Index range          | Channels | Description
  ---------------------+----------+------------------------------------
  [ 0, 16)             |    16    | edge types: 4 sides x {city,road,field,none}
  [16, 17)             |     1    | tile-present binary
  [17, 18)             |     1    | shield-on-tile flag
  [18, 19)             |     1    | chapel-or-flowers flag
  [19, 21)             |     2    | NORMAL meeple (mine, opp)
  [21, 23)             |     2    | FARMER meeple (mine, opp)
  [23, 39)             |    16    | reference-tile broadcast: edge encoding
                                    of state.next_tile (TILES) or last placed
                                    tile (MEEPLES), broadcast to every cell
  [39, 40)             |     1    | last-placed-tile-position one-hot
                                    (1.0 at the just-placed tile during MEEPLES,
                                     all-zero during TILES)

Total: 40 channels.

Edge categorical encoding uses TerrainType:
  CITY, ROAD, GRASS (= field), then "other" (CHAPEL/FLOWERS/UNPLAYABLE) are
  bucketed as none. The engine reports CHAPEL/FLOWERS only for Side.CENTER.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

from .action_space import DEFAULT_WINDOW_SIZE, WindowOffset

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.objects.tile import Tile


SIDES_4: tuple[Side, ...] = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)
EDGE_CATEGORIES = 4  # city / road / field / none
EDGE_BLOCK = len(SIDES_4) * EDGE_CATEGORIES  # 16

CH_EDGES = 0
CH_TILE_PRESENT = 16
CH_SHIELD = 17
CH_CHAPEL = 18
CH_MEEPLE_MINE = 19
CH_MEEPLE_OPP = 20
CH_FARMER_MINE = 21
CH_FARMER_OPP = 22
CH_REF_TILE = 23
CH_LAST_TILE_POS = 39
N_CHANNELS = 40


def _terrain_to_category(terrain: TerrainType) -> int:
    if terrain == TerrainType.CITY:
        return 0
    if terrain == TerrainType.ROAD:
        return 1
    if terrain == TerrainType.GRASS:
        return 2
    return 3  # CHAPEL/FLOWERS/UNPLAYABLE → "none" for edge purposes


def _encode_tile_edges(tile: "Tile") -> np.ndarray:
    """16-dim one-hot block: 4 sides x 4 edge categories."""
    block = np.zeros(EDGE_BLOCK, dtype=np.float32)
    for i, side in enumerate(SIDES_4):
        cat = _terrain_to_category(tile.get_type(side))
        block[i * EDGE_CATEGORIES + cat] = 1.0
    return block


def compute_window_offset(
    state: "CarcassonneGameState",
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> WindowOffset:
    """Center the window on the centroid of placed tiles, snapped to int.

    For an empty board (defensive — the first tile is auto-placed), center
    on the engine's starting_position.
    """
    rows: list[int] = []
    cols: list[int] = []
    for r, row in enumerate(state.board):
        for c, tile in enumerate(row):
            if tile is not None:
                rows.append(r)
                cols.append(c)
    if not rows:
        sp = state.starting_position
        center_r, center_c = sp.row, sp.column
    else:
        center_r = round(sum(rows) / len(rows))
        center_c = round(sum(cols) / len(cols))
    half = window_size // 2
    return WindowOffset(
        origin_row=center_r - half,
        origin_col=center_c - half,
        size=window_size,
    )


def board_overflows_window(state: "CarcassonneGameState", off: WindowOffset) -> bool:
    """True if any placed tile falls outside the centered window."""
    for r, row in enumerate(state.board):
        for c, tile in enumerate(row):
            if tile is None:
                continue
            wr, wc = r - off.origin_row, c - off.origin_col
            if not (0 <= wr < off.size and 0 <= wc < off.size):
                return True
    return False


def encode_board(
    state: "CarcassonneGameState",
    player: int,
    off: WindowOffset,
) -> np.ndarray:
    """Encode the placed board into a (N_CHANNELS, W, W) float32 tensor.

    `player` is the current-player perspective (mine = `player`, opp = the other).
    """
    W = off.size
    arr = np.zeros((N_CHANNELS, W, W), dtype=np.float32)
    opp = 1 - player

    for r, row in enumerate(state.board):
        for c, tile in enumerate(row):
            if tile is None:
                continue
            wr, wc = r - off.origin_row, c - off.origin_col
            if not (0 <= wr < W and 0 <= wc < W):
                continue
            edges = _encode_tile_edges(tile)
            arr[CH_EDGES:CH_EDGES + EDGE_BLOCK, wr, wc] = edges
            arr[CH_TILE_PRESENT, wr, wc] = 1.0
            if tile.shield:
                arr[CH_SHIELD, wr, wc] = 1.0
            if tile.chapel or tile.flowers:
                arr[CH_CHAPEL, wr, wc] = 1.0

    for owner in (player, opp):
        ch_meeple = CH_MEEPLE_MINE if owner == player else CH_MEEPLE_OPP
        ch_farmer = CH_FARMER_MINE if owner == player else CH_FARMER_OPP
        for mp in state.placed_meeples[owner]:
            cws = mp.coordinate_with_side
            wr, wc = cws.coordinate.row - off.origin_row, cws.coordinate.column - off.origin_col
            if not (0 <= wr < W and 0 <= wc < W):
                continue
            if mp.meeple_type == MeepleType.FARMER:
                arr[ch_farmer, wr, wc] = 1.0
            elif mp.meeple_type == MeepleType.NORMAL:
                arr[ch_meeple, wr, wc] = 1.0

    ref_tile: "Tile | None"
    if state.phase.value == "tiles":
        ref_tile = state.next_tile
    else:
        ref_tile = state.last_tile_action.tile if state.last_tile_action is not None else None
    if ref_tile is not None:
        edges = _encode_tile_edges(ref_tile)
        arr[CH_REF_TILE:CH_REF_TILE + EDGE_BLOCK, :, :] = edges[:, None, None]

    if state.phase.value == "meeples" and state.last_tile_action is not None:
        coord = state.last_tile_action.coordinate
        wr, wc = coord.row - off.origin_row, coord.column - off.origin_col
        if 0 <= wr < W and 0 <= wc < W:
            arr[CH_LAST_TILE_POS, wr, wc] = 1.0

    return arr


def canonical_swap(arr: np.ndarray) -> np.ndarray:
    """Swap mine/opp meeple+farmer channels. Idempotent of order 2."""
    out = arr.copy()
    out[CH_MEEPLE_MINE] = arr[CH_MEEPLE_OPP]
    out[CH_MEEPLE_OPP] = arr[CH_MEEPLE_MINE]
    out[CH_FARMER_MINE] = arr[CH_FARMER_OPP]
    out[CH_FARMER_OPP] = arr[CH_FARMER_MINE]
    return out
