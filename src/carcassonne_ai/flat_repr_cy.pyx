# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False, cdivision=True
"""Cython port of the board feature encoder (`board_repr.encode_board`).

DEV/VALIDATION (2026-06-17, stage-b-wiring). Default OFF — nothing imports this
module unless `CARCASSONNE_USE_CY_REPR=1` (see `board_repr.USE_CY_REPR`).

Why: after the v2.7 leaf was Cython-ported (`flat_leaf_cy`), `encode_board`
became the largest pure-Python cost on the self-play/eval hot path (profile
2026-06-17: ~15% self / ~25% cumulative, called once per leaf eval). It has the
SAME shape that made the leaf port win — a union-find over a handful of sides +
direct numpy plane fills — but the original pays for it in:
  * a fresh `np.zeros(16)` / `np.zeros(6)` per tile (millions of tiny allocs),
  * dict-based union-find keyed by `Side` ENUM members (each lookup is an
    `Enum.__hash__` = `hash(name_str)`; ~16s of the profile is enum/builtin hash),
  * Python slice-assignment views into the output for every channel block.

This port keeps the boundary (reading engine `Tile`/meeple Python objects) but
moves ALL interior bookkeeping to C:
  * enum -> small-int via IDENTITY compare (`is`) — enum singletons, zero hashing.
  * each distinct `Tile` object is decoded ONCE into an 18-byte feature record
    (`_TILE_REPR_CACHE`, identity-keyed; tiles are canonical shared refs, ~100
    rotated tiles/process — same caching rationale as `flat_leaf_cy._TILE_FEAT`),
  * the output is filled through a typed `float[:, :, ::1]` memoryview — no
    per-tile allocation, no slice views.
  * placed tiles are walked via `state.placed_coords` (~80) instead of the full
    35x35 grid scan, with a defensive full-board fallback.

Bit-exactness is MANDATORY and gated by `scripts/reconcile_repr_cy.py` against
`board_repr.encode_board` (the output is a 0/1 float32 tensor, so the bar is
exact `np.array_equal`, full stop).

Layout (mirrors board_repr; 78 channels):
  edges[0,16) tile_present[16] shield[17] chapel[18] int_road[19,25) int_city[25,31)
  normal_mine[31,36) normal_opp[36,41) farmer_mine[41,45) farmer_opp[45,49)
  ref_edges[49,65) ref_internal[65,77) last_tile_pos[77]
"""

import numpy as np

from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

# --- channel offsets (== board_repr) -----------------------------------------
DEF CH_EDGES = 0
DEF EDGE_BLOCK = 16
DEF CH_TILE_PRESENT = 16
DEF CH_SHIELD = 17
DEF CH_CHAPEL = 18
DEF CH_INTERNAL_ROAD = 19
DEF CH_INTERNAL_CITY = 25
DEF CH_NORMAL_MINE = 31
DEF CH_NORMAL_OPP = 36
DEF CH_FARMER_MINE = 41
DEF CH_FARMER_OPP = 45
DEF CH_REF_EDGES = 49
DEF CH_REF_INTERNAL = 65
DEF CH_LAST_TILE_POS = 77
DEF N_CHANNELS = 78

# --- enum singletons (identity dispatch — no hashing) ------------------------
cdef object _S_TOP = Side.TOP
cdef object _S_RIGHT = Side.RIGHT
cdef object _S_BOTTOM = Side.BOTTOM
cdef object _S_LEFT = Side.LEFT
cdef object _S_CENTER = Side.CENTER
cdef object _S_TL = Side.TOP_LEFT
cdef object _S_TR = Side.TOP_RIGHT
cdef object _S_BL = Side.BOTTOM_LEFT
cdef object _S_BR = Side.BOTTOM_RIGHT

cdef object _T_CITY = TerrainType.CITY
cdef object _T_ROAD = TerrainType.ROAD
cdef object _T_GRASS = TerrainType.GRASS

cdef object _M_FARMER = MeepleType.FARMER
cdef object _M_NORMAL = MeepleType.NORMAL

cdef object _PHASE_TILES = GamePhase.TILES
cdef object _PHASE_MEEPLES = GamePhase.MEEPLES

# Python-side tuple of the 4 outer sides for tile.get_type(side) calls.
_SIDES4 = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)

# Per-tile 18-byte feature cache, identity-keyed (Tile has no __hash__/__eq__
# override -> id-based; strong refs bounded by the ~100 rotated tiles/process).
_TILE_REPR_CACHE = {}


cdef inline int _side4(object s):
    """Outer side -> 0..3 (T,R,B,L); CENTER/corners/None -> -1."""
    if s is _S_TOP:
        return 0
    elif s is _S_RIGHT:
        return 1
    elif s is _S_BOTTOM:
        return 2
    elif s is _S_LEFT:
        return 3
    return -1


cdef inline int _side5(object s):
    """Normal-meeple side -> 0..4 (T,R,B,L,CENTER); else -1."""
    if s is _S_TOP:
        return 0
    elif s is _S_RIGHT:
        return 1
    elif s is _S_BOTTOM:
        return 2
    elif s is _S_LEFT:
        return 3
    elif s is _S_CENTER:
        return 4
    return -1


cdef inline int _corner(object s):
    """Farmer corner -> 0..3 (TL,TR,BL,BR); else -1."""
    if s is _S_TL:
        return 0
    elif s is _S_TR:
        return 1
    elif s is _S_BL:
        return 2
    elif s is _S_BR:
        return 3
    return -1


cdef inline int _terr_cat(object t):
    """TerrainType -> edge category 0..3 (city/road/grass/none)."""
    if t is _T_CITY:
        return 0
    elif t is _T_ROAD:
        return 1
    elif t is _T_GRASS:
        return 2
    return 3


cdef inline int _find4(int* parent, int x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


cdef bytes _build_tile_repr(object tile):
    """Decode a Tile into 18 bytes:
      [0:4]   edge category per side (T,R,B,L)
      [4]     shield
      [5]     chapel-or-flowers
      [6:12]  internal road pairs (TR,TB,TL,RB,RL,BL)
      [12:18] internal city pairs (same order)
    Pure function of the (immutable) Tile -> cached by identity.
    """
    cdef unsigned char buf[18]
    cdef int i, ai, bi, ra, rb, gid, si
    cdef int parent[4]
    cdef int grp[4]

    # edges
    for i in range(4):
        buf[i] = <unsigned char>_terr_cat(tile.get_type(_SIDES4[i]))
    buf[4] = 1 if tile.shield else 0
    buf[5] = 1 if (tile.chapel or tile.flowers) else 0

    # internal road pairs: union-find over outer-outer connections only.
    for i in range(4):
        parent[i] = i
    if tile.road:
        for conn in tile.road:
            ai = _side4(conn.a)
            bi = _side4(conn.b)
            if ai >= 0 and bi >= 0:
                ra = _find4(parent, ai)
                rb = _find4(parent, bi)
                if ra != rb:
                    parent[ra] = rb
    buf[6] = 1 if _find4(parent, 0) == _find4(parent, 1) else 0   # T,R
    buf[7] = 1 if _find4(parent, 0) == _find4(parent, 2) else 0   # T,B
    buf[8] = 1 if _find4(parent, 0) == _find4(parent, 3) else 0   # T,L
    buf[9] = 1 if _find4(parent, 1) == _find4(parent, 2) else 0   # R,B
    buf[10] = 1 if _find4(parent, 1) == _find4(parent, 3) else 0  # R,L
    buf[11] = 1 if _find4(parent, 2) == _find4(parent, 3) else 0  # B,L

    # internal city pairs: same-inner-list grouping.
    for i in range(4):
        grp[i] = -1
    if tile.city:
        gid = 0
        for side_list in tile.city:
            for s in side_list:
                si = _side4(s)
                if si >= 0:
                    grp[si] = gid
            gid += 1
    buf[12] = 1 if (grp[0] >= 0 and grp[0] == grp[1]) else 0  # T,R
    buf[13] = 1 if (grp[0] >= 0 and grp[0] == grp[2]) else 0  # T,B
    buf[14] = 1 if (grp[0] >= 0 and grp[0] == grp[3]) else 0  # T,L
    buf[15] = 1 if (grp[1] >= 0 and grp[1] == grp[2]) else 0  # R,B
    buf[16] = 1 if (grp[1] >= 0 and grp[1] == grp[3]) else 0  # R,L
    buf[17] = 1 if (grp[2] >= 0 and grp[2] == grp[3]) else 0  # B,L

    return bytes(buf[:18])


cdef inline bytes _tile_repr(object tile):
    cached = _TILE_REPR_CACHE.get(tile)
    if cached is not None:
        return <bytes>cached
    cdef bytes rep = _build_tile_repr(tile)
    _TILE_REPR_CACHE[tile] = rep
    return rep


def encode_board_cy(object state, int player, object off):
    """Bit-exact Cython equivalent of board_repr.encode_board(state, player, off).

    Returns a C-contiguous (78, W, W) float32 numpy array.
    """
    cdef int W = off.size
    cdef int orow = off.origin_row
    cdef int ocol = off.origin_col
    cdef int opp = 1 - player

    arr = np.zeros((N_CHANNELS, W, W), dtype=np.float32)
    cdef float[:, :, ::1] a = arr

    cdef const unsigned char[::1] rep
    cdef int wr, wc, i, k, cat, off_idx
    cdef int normal_base, farmer_base, owner

    # --- placed tiles ---------------------------------------------------------
    placed = getattr(state, "placed_coords", None)
    board = state.board
    if placed is None:
        # defensive full-board scan (placed_coords not maintained on this state)
        coords_iter = _scan_coords(board)
    else:
        coords_iter = placed

    for coord in coords_iter:
        r = coord.row
        c = coord.column
        wr = r - orow
        wc = c - ocol
        if wr < 0 or wr >= W or wc < 0 or wc >= W:
            continue
        tile = board[r][c]
        if tile is None:
            continue
        rep = _tile_repr(tile)
        # edges (one-hot per side)
        for i in range(4):
            cat = rep[i]
            a[CH_EDGES + i * 4 + cat, wr, wc] = 1.0
        a[CH_TILE_PRESENT, wr, wc] = 1.0
        if rep[4]:
            a[CH_SHIELD, wr, wc] = 1.0
        if rep[5]:
            a[CH_CHAPEL, wr, wc] = 1.0
        for k in range(6):
            if rep[6 + k]:
                a[CH_INTERNAL_ROAD + k, wr, wc] = 1.0
            if rep[12 + k]:
                a[CH_INTERNAL_CITY + k, wr, wc] = 1.0

    # --- meeples --------------------------------------------------------------
    placed_meeples = state.placed_meeples
    for owner in (player, opp):
        if owner == player:
            normal_base = CH_NORMAL_MINE
            farmer_base = CH_FARMER_MINE
        else:
            normal_base = CH_NORMAL_OPP
            farmer_base = CH_FARMER_OPP
        for mp in placed_meeples[owner]:
            cws = mp.coordinate_with_side
            wr = cws.coordinate.row - orow
            wc = cws.coordinate.column - ocol
            if wr < 0 or wr >= W or wc < 0 or wc >= W:
                continue
            mt = mp.meeple_type
            if mt is _M_FARMER:
                off_idx = _corner(cws.side)
                if off_idx < 0:
                    raise ValueError(
                        "FARMER meeple on non-corner side %r at (%d,%d)"
                        % (cws.side, cws.coordinate.row, cws.coordinate.column)
                    )
                a[farmer_base + off_idx, wr, wc] = 1.0
            elif mt is _M_NORMAL:
                off_idx = _side5(cws.side)
                if off_idx < 0:
                    raise ValueError(
                        "NORMAL meeple on unexpected side %r at (%d,%d)"
                        % (cws.side, cws.coordinate.row, cws.coordinate.column)
                    )
                a[normal_base + off_idx, wr, wc] = 1.0
            else:
                raise ValueError(
                    "Unsupported meeple type %r (locked scope NORMAL+FARMER)" % (mt,)
                )

    # --- reference tile (phase-dependent), broadcast to every cell ------------
    if state.phase is _PHASE_TILES:
        ref_tile = state.next_tile
    else:
        ref_tile = state.last_tile_action.tile if state.last_tile_action is not None else None
    if ref_tile is not None:
        rep = _tile_repr(ref_tile)
        for i in range(4):
            cat = rep[i]
            _fill_plane(a, CH_REF_EDGES + i * 4 + cat, W)
        for k in range(6):
            if rep[6 + k]:
                _fill_plane(a, CH_REF_INTERNAL + k, W)
            if rep[12 + k]:
                _fill_plane(a, CH_REF_INTERNAL + 6 + k, W)

    # --- last-placed-tile one-hot (MEEPLES phase) -----------------------------
    if state.phase is _PHASE_MEEPLES and state.last_tile_action is not None:
        coord = state.last_tile_action.coordinate
        wr = coord.row - orow
        wc = coord.column - ocol
        if 0 <= wr < W and 0 <= wc < W:
            a[CH_LAST_TILE_POS, wr, wc] = 1.0

    return arr


cdef inline void _fill_plane(float[:, :, ::1] a, int ch, int W):
    cdef int wr, wc
    for wr in range(W):
        for wc in range(W):
            a[ch, wr, wc] = 1.0


def _scan_coords(board):
    """Defensive fallback: yield objects with .row/.column for every placed
    cell (only used when state.placed_coords is absent)."""
    out = []
    for r in range(len(board)):
        row = board[r]
        for c in range(len(row)):
            if row[c] is not None:
                out.append(_RC(r, c))
    return out


cdef class _RC:
    cdef public int row
    cdef public int column
    def __cinit__(self, int row, int column):
        self.row = row
        self.column = column
