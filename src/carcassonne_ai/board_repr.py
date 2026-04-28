"""Centered-window tensor encoding of a Carcassonne board state.

The wingedsheep engine stores tiles on an internal 35x35 grid offset by a
fixed `starting_position`. We re-center the placed tiles into a smaller
W x W window and encode them as a multi-channel tensor for the network.
W is configurable (see DEFAULT_WINDOW_SIZE in action_space).

Channel layout (current-player-relative; mine/opp swap is done in canonical_swap):

  Index range          | Channels | Description
  ---------------------+----------+--------------------------------------
  [ 0, 16)             |    16    | edge types: 4 sides x {city,road,field,none}
  [16, 17)             |     1    | tile-present binary
  [17, 18)             |     1    | shield-on-tile flag
  [18, 19)             |     1    | chapel-or-flowers flag
  [19, 25)             |     6    | internal road same-feature pairs:
                                    TR, TB, TL, RB, RL, BL — 1 if both sides
                                    are connected by a single road on this tile
  [25, 31)             |     6    | internal city same-feature pairs (same shape)
  [31, 41)             |    10    | NORMAL meeple slots: 5 sides x {mine, opp}
                                    side order: TOP, RIGHT, BOTTOM, LEFT, CENTER
                                    (mine[5] then opp[5])
  [41, 49)             |     8    | FARMER meeple slots: 4 corners x {mine, opp}
                                    corner order: TOP_LEFT, TOP_RIGHT,
                                    BOTTOM_LEFT, BOTTOM_RIGHT (mine[4] then opp[4])
  [49, 65)             |    16    | reference-tile broadcast: edge encoding
                                    of state.next_tile (TILES) or last placed
                                    tile (MEEPLES), broadcast to every cell
  [65, 77)             |    12    | reference-tile internal: same-pair indicators
                                    for road (6) + city (6), broadcast every cell
  [77, 78)             |     1    | last-placed-tile-position one-hot
                                    (1.0 at the just-placed tile during MEEPLES,
                                     all-zero during TILES)

Total: 78 channels.

Edge categorical encoding uses TerrainType:
  CITY, ROAD, GRASS (= field), then "other" (CHAPEL/FLOWERS/UNPLAYABLE) are
  bucketed as none. The engine reports CHAPEL/FLOWERS only for Side.CENTER.

Internal topology rationale: two tiles with identical outer-edge category
patterns can have different internal structures. E.g. a road-corner (TOP-RIGHT
joined into one road) vs a road-T (TOP-RIGHT-BOTTOM all joined), or a
city-corner (T+R same city) vs city-on-two-tiles (T and R are independent
cities). The internal pair-indicator channels distinguish these explicitly.

Per-side meeple rationale: a NORMAL meeple on the TOP edge claims the
city/road on that edge; a NORMAL meeple at CENTER claims a chapel. Pre-fix
all meeple positions on a tile collapsed to a single cell-level flag, hiding
which feature was actually claimed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import numpy as np

from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

from .action_space import DEFAULT_WINDOW_SIZE, WindowOffset

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.objects.connection import Connection
    from wingedsheep.carcassonne.objects.tile import Tile


SIDES_4: tuple[Side, ...] = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)
SIDES_5: tuple[Side, ...] = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT, Side.CENTER)
CORNERS_4: tuple[Side, ...] = (
    Side.TOP_LEFT,
    Side.TOP_RIGHT,
    Side.BOTTOM_LEFT,
    Side.BOTTOM_RIGHT,
)
EDGE_CATEGORIES = 4  # city / road / field / none
EDGE_BLOCK = len(SIDES_4) * EDGE_CATEGORIES  # 16

# Unordered pairs of the 4 outer sides (TR, TB, TL, RB, RL, BL).
SIDE_PAIRS: tuple[tuple[Side, Side], ...] = (
    (Side.TOP, Side.RIGHT),
    (Side.TOP, Side.BOTTOM),
    (Side.TOP, Side.LEFT),
    (Side.RIGHT, Side.BOTTOM),
    (Side.RIGHT, Side.LEFT),
    (Side.BOTTOM, Side.LEFT),
)
N_SIDE_PAIRS = len(SIDE_PAIRS)  # 6

CH_EDGES = 0
CH_TILE_PRESENT = 16
CH_SHIELD = 17
CH_CHAPEL = 18
CH_INTERNAL_ROAD = 19  # 6 channels
CH_INTERNAL_CITY = 25  # 6 channels
CH_NORMAL_MEEPLE_MINE = 31  # 5 channels (T, R, B, L, CENTER)
CH_NORMAL_MEEPLE_OPP = 36  # 5 channels
CH_FARMER_MEEPLE_MINE = 41  # 4 channels (TL, TR, BL, BR)
CH_FARMER_MEEPLE_OPP = 45  # 4 channels
CH_REF_TILE_EDGES = 49  # 16 channels
CH_REF_TILE_INTERNAL = 65  # 12 channels (6 road + 6 city)
CH_LAST_TILE_POS = 77
N_CHANNELS = 78


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


def _components_from_connections(
    connections: Iterable["Connection"], sides: tuple[Side, ...]
) -> dict[Side, int]:
    """Union-find on the connection graph; returns side -> component id."""
    parent: dict[Side, Side] = {s: s for s in sides}

    def find(x: Side) -> Side:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for conn in connections:
        if conn.a in parent and conn.b in parent:
            ra, rb = find(conn.a), find(conn.b)
            if ra != rb:
                parent[ra] = rb
    # Map each side to a stable integer id (component-canonical-side).
    canon: dict[Side, int] = {}
    next_id = 0
    out: dict[Side, int] = {}
    for s in sides:
        root = find(s)
        if root not in canon:
            canon[root] = next_id
            next_id += 1
        out[s] = canon[root]
    return out


def _encode_road_pairs(tile: "Tile") -> np.ndarray:
    """6-dim block: for each pair (a, b) in SIDE_PAIRS, 1.0 if both sides are
    joined by a single road feature on this tile.

    Only unions outer-side ↔ outer-side connections directly. The engine
    represents a 4-way crossroads as four separate Connection(outer, CENTER)
    entries; per Carcassonne rules these are four SEPARATE road features that
    happen to meet at the tile's center, NOT one big four-way road. Including
    CENTER in the union-find would incorrectly merge them.
    """
    out = np.zeros(N_SIDE_PAIRS, dtype=np.float32)
    if not tile.road:
        return out
    outer_only = [c for c in tile.road if c.a in SIDES_4 and c.b in SIDES_4]
    if not outer_only:
        return out
    comps = _components_from_connections(outer_only, SIDES_4)
    for i, (a, b) in enumerate(SIDE_PAIRS):
        if comps[a] == comps[b]:
            out[i] = 1.0
    return out


def _encode_city_pairs(tile: "Tile") -> np.ndarray:
    """6-dim block: for each pair (a, b) in SIDE_PAIRS, 1.0 if both sides are
    part of the same city feature on this tile. tile.city is a list of lists
    of sides; sides in the same inner list belong to the same city.
    """
    out = np.zeros(N_SIDE_PAIRS, dtype=np.float32)
    if not tile.city:
        return out
    side_to_group: dict[Side, int] = {}
    for gid, side_list in enumerate(tile.city):
        for s in side_list:
            side_to_group[s] = gid
    for i, (a, b) in enumerate(SIDE_PAIRS):
        if a in side_to_group and b in side_to_group and side_to_group[a] == side_to_group[b]:
            out[i] = 1.0
    return out


def _encode_tile_internal(tile: "Tile") -> np.ndarray:
    """12-dim block: 6 road-pair + 6 city-pair indicators."""
    out = np.zeros(2 * N_SIDE_PAIRS, dtype=np.float32)
    out[:N_SIDE_PAIRS] = _encode_road_pairs(tile)
    out[N_SIDE_PAIRS:] = _encode_city_pairs(tile)
    return out


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


# Side-to-channel-offset lookup tables for meeple slots.
_NORMAL_SIDE_TO_OFFSET: dict[Side, int] = {s: i for i, s in enumerate(SIDES_5)}
_FARMER_CORNER_TO_OFFSET: dict[Side, int] = {s: i for i, s in enumerate(CORNERS_4)}


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
            arr[CH_INTERNAL_ROAD:CH_INTERNAL_ROAD + N_SIDE_PAIRS, wr, wc] = (
                _encode_road_pairs(tile)
            )
            arr[CH_INTERNAL_CITY:CH_INTERNAL_CITY + N_SIDE_PAIRS, wr, wc] = (
                _encode_city_pairs(tile)
            )

    for owner in (player, opp):
        normal_base = CH_NORMAL_MEEPLE_MINE if owner == player else CH_NORMAL_MEEPLE_OPP
        farmer_base = CH_FARMER_MEEPLE_MINE if owner == player else CH_FARMER_MEEPLE_OPP
        for mp in state.placed_meeples[owner]:
            cws = mp.coordinate_with_side
            wr = cws.coordinate.row - off.origin_row
            wc = cws.coordinate.column - off.origin_col
            if not (0 <= wr < W and 0 <= wc < W):
                continue
            if mp.meeple_type == MeepleType.FARMER:
                offset = _FARMER_CORNER_TO_OFFSET.get(cws.side)
                if offset is None:
                    raise ValueError(
                        f"FARMER meeple on non-corner side {cws.side!r} at "
                        f"({cws.coordinate.row},{cws.coordinate.column}) — "
                        "engine should never place a farmer outside the 4 corners."
                    )
                arr[farmer_base + offset, wr, wc] = 1.0
            elif mp.meeple_type == MeepleType.NORMAL:
                offset = _NORMAL_SIDE_TO_OFFSET.get(cws.side)
                if offset is None:
                    raise ValueError(
                        f"NORMAL meeple on unexpected side {cws.side!r} at "
                        f"({cws.coordinate.row},{cws.coordinate.column}) — "
                        "engine should only emit T/R/B/L/CENTER."
                    )
                arr[normal_base + offset, wr, wc] = 1.0
            else:
                raise ValueError(
                    f"Unsupported meeple type {mp.meeple_type!r} — locked scope is "
                    "NORMAL + FARMER (no Abbots, no Big meeples). Did the engine "
                    "config drift?"
                )

    ref_tile: "Tile | None"
    if state.phase.value == "tiles":
        ref_tile = state.next_tile
    else:
        ref_tile = state.last_tile_action.tile if state.last_tile_action is not None else None
    if ref_tile is not None:
        edges = _encode_tile_edges(ref_tile)
        arr[CH_REF_TILE_EDGES:CH_REF_TILE_EDGES + EDGE_BLOCK, :, :] = edges[:, None, None]
        internal = _encode_tile_internal(ref_tile)
        arr[CH_REF_TILE_INTERNAL:CH_REF_TILE_INTERNAL + 2 * N_SIDE_PAIRS, :, :] = (
            internal[:, None, None]
        )

    if state.phase.value == "meeples" and state.last_tile_action is not None:
        coord = state.last_tile_action.coordinate
        wr, wc = coord.row - off.origin_row, coord.column - off.origin_col
        if 0 <= wr < W and 0 <= wc < W:
            arr[CH_LAST_TILE_POS, wr, wc] = 1.0

    return arr


def canonical_swap(arr: np.ndarray) -> np.ndarray:
    """Swap mine/opp meeple+farmer channel blocks. Idempotent of order 2."""
    out = arr.copy()
    n_normal = len(SIDES_5)  # 5
    n_farmer = len(CORNERS_4)  # 4
    out[CH_NORMAL_MEEPLE_MINE:CH_NORMAL_MEEPLE_MINE + n_normal] = (
        arr[CH_NORMAL_MEEPLE_OPP:CH_NORMAL_MEEPLE_OPP + n_normal]
    )
    out[CH_NORMAL_MEEPLE_OPP:CH_NORMAL_MEEPLE_OPP + n_normal] = (
        arr[CH_NORMAL_MEEPLE_MINE:CH_NORMAL_MEEPLE_MINE + n_normal]
    )
    out[CH_FARMER_MEEPLE_MINE:CH_FARMER_MEEPLE_MINE + n_farmer] = (
        arr[CH_FARMER_MEEPLE_OPP:CH_FARMER_MEEPLE_OPP + n_farmer]
    )
    out[CH_FARMER_MEEPLE_OPP:CH_FARMER_MEEPLE_OPP + n_farmer] = (
        arr[CH_FARMER_MEEPLE_MINE:CH_FARMER_MEEPLE_MINE + n_farmer]
    )
    return out


# ---------------------------------------------------------------------------
# Backwards-compat shims for legacy channel constants. Existing tests import
# CH_MEEPLE_MINE / CH_MEEPLE_OPP / CH_FARMER_MINE / CH_FARMER_OPP and treat
# them as a single channel each. After the per-side / per-corner expansion
# the "meeple at this cell" presence is the OR across the 5 normal-side or
# 4 farmer-corner channels — but for purposes of the legacy tests it's
# sufficient to point the old constant at the first slot in each block.
CH_MEEPLE_MINE = CH_NORMAL_MEEPLE_MINE
CH_MEEPLE_OPP = CH_NORMAL_MEEPLE_OPP
CH_FARMER_MINE = CH_FARMER_MEEPLE_MINE
CH_FARMER_OPP = CH_FARMER_MEEPLE_OPP
CH_REF_TILE = CH_REF_TILE_EDGES
