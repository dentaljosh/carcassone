# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False, cdivision=True
# Capability flag: this build implements the v2.9 meeple curve (Candidate B). The
# Python wrapper (flat_leaf.py) checks it before routing a curve config here, so a
# STALE .so (no curve support) can never silently drop the curve — it falls back to
# the pure-Python flat path instead. Bump/rename if the curve semantics ever change.
SUPPORTS_V29_CURVE = True
"""Cython port of the production flat leaf (`flat_leaf.flat_virtual_score_v2`).

DEV-ONLY (2026-06-12, stage-b-wiring worktree). Default OFF — nothing imports
this module unless `CARCASSONNE_USE_CY_LEAF=1` (see `flat_leaf.USE_CY_LEAF`).

Design: bit-exact mirror of `flat_leaf.py`. The boundary (walking engine
tile/meeple Python objects) stays Python-object access; ALL interior
bookkeeping is int-keyed C arrays:

  * enum -> small-int conversion happens ONCE per distinct Tile object via the
    `_TILE_FEAT` cache (tiles are canonical shared refs — the engine state
    `__deepcopy__` shares Tile objects, so the cache is bounded by the global
    rotated-tile population, ~100 entries per process).
  * node-id tables are flat C int arrays indexed by `(r*W + c)*9 + side_ix`
    (memset to -1 per call) — no dict, no tuple, no enum hashing.
  * union-find (`_label_components`) is path-halving over C int arrays with the
    IDENTICAL edge order as the Python version, so component root ids are
    bit-identical to `flat_leaf.decompose` (checked by `decompose_export`).
  * per-root facts (finished / open_n / tiles / shields / cathedral / inn /
    adjacent-city dedup) are computed by counting-sort bucketing + monotone
    stamp arrays — no per-leaf set/dict allocation.

Float semantics: the closure bonus accumulates the SAME multiset of float
contributions as `flat_leaf.flat_closure_bonus` (each contribution is a single
IEEE double product, identical to the Python float product) and reduces it with
`math.fsum`, which is correctly rounded and order-independent — so the bonus,
the capped sum, and the final `int(round(score))` (Python-semantics round, on a
boxed float) are bit-identical to the Python flat leaf by construction. Gated
by `scripts/reconcile_cy_leaf.py` (0 mismatches required).
"""

from libc.stdlib cimport malloc, free
from libc.string cimport memset

import math

from wingedsheep.carcassonne.objects.farmer_side import FarmerSide
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.utils.side_modification_util import SideModificationUtil

_fsum = math.fsum

# --- boundary enum tables (mirror flat_leaf._SIDE_IX / _FS_IX / _OPP / _FS_*) --
_SIDE_IX = {s: i for i, s in enumerate(Side)}   # TOP0 RIGHT1 BOTTOM2 LEFT3 CENTER4 TL5 TR6 BL7 BR8
_IX_SIDE = list(Side)
_FS_IX = {fs: i for i, fs in enumerate(FarmerSide)}

# Terrain / meeple-type singletons (enum identity compare is what Python's ==
# resolves to for Enum, so `is` is exact here; we still use == via richcompare
# where flat_leaf does — both are identity for these enums).
_T_CITY = TerrainType.CITY
_T_ROAD = TerrainType.ROAD
_T_CHAPEL = TerrainType.CHAPEL
_T_FLOWERS = TerrainType.FLOWERS
_M_BIG = MeepleType.BIG
_M_BIG_FARMER = MeepleType.BIG_FARMER
_M_FARMER = MeepleType.FARMER

# Cardinal-side crossing tables (== flat_leaf._OPP), C-array form.
cdef int _OPP_DR[4]
cdef int _OPP_DC[4]
cdef int _OPP_IX[4]
_card = {Side.TOP: (-1, 0, Side.BOTTOM), Side.RIGHT: (0, 1, Side.LEFT),
         Side.BOTTOM: (1, 0, Side.TOP), Side.LEFT: (0, -1, Side.RIGHT)}
for _s, (_dr, _dc, _o) in _card.items():
    _OPP_DR[_SIDE_IX[_s]] = _dr
    _OPP_DC[_SIDE_IX[_s]] = _dc
    _OPP_IX[_SIDE_IX[_s]] = _SIDE_IX[_o]
del _card, _s, _dr, _dc, _o

# Farmer half-side step + opposite (== flat_leaf._FS_STEP / _FS_OPP, built from
# the engine helpers to avoid transcription risk).
cdef int _FS_DR[8]
cdef int _FS_DC[8]
cdef int _FS_OPPC[8]
_cstep = {Side.TOP: (-1, 0), Side.RIGHT: (0, 1), Side.BOTTOM: (1, 0), Side.LEFT: (0, -1)}
for _fs in FarmerSide:
    _i = _FS_IX[_fs]
    _FS_DR[_i], _FS_DC[_i] = _cstep[_fs.get_side()]
    _FS_OPPC[_i] = _FS_IX[SideModificationUtil.opposite_farmer_side(_fs)]
del _cstep, _fs, _i


# --- per-tile int-feature cache ----------------------------------------------
# Plain dict keyed by the Tile OBJECT (identity hash — Tile has no __eq__/
# __hash__ override). Strong refs are safe/bounded: the engine state deepcopy
# shares tile refs (carcassonne_game_state.__deepcopy__ does `row[:]`), so the
# process only ever sees the canonical base tiles + their Tile._turn_cache
# rotations (~100 objects). Per tile we store:
#   (city_groups_ix, road_conns_ix(-1==CENTER), farms_tc_ix, farms_fp_ix,
#    farms_cs_ix, inn, shield)
_TILE_FEAT: dict = {}


cdef tuple _tile_features(object tile):
    feat = _TILE_FEAT.get(tile)
    if feat is None:
        side_ix = _SIDE_IX
        fs_ix = _FS_IX
        CENTER = Side.CENTER
        cg = tuple(tuple(side_ix[s] for s in g) for g in tile.city)
        rd = tuple(
            (-1 if conn.a is CENTER else side_ix[conn.a],
             -1 if conn.b is CENTER else side_ix[conn.b])
            for conn in tile.road
        )
        farms = tile.farms
        ftc = tuple(tuple(fs_ix[fs] for fs in fc.tile_connections) for fc in farms)
        ffp = tuple(tuple(side_ix[s] for s in fc.farmer_positions) for fc in farms)
        fcs = tuple(tuple(side_ix[s] for s in fc.city_sides) for fc in farms)
        feat = (cg, rd, ftc, ffp, fcs,
                1 if tile.inn else 0, 1 if tile.shield else 0)
        _TILE_FEAT[tile] = feat
    return <tuple>feat


# --- reusable workspace -------------------------------------------------------
cdef class _WS:
    """All per-leaf C buffers, allocated once and reused (module singleton).
    Workers are separate processes and the leaf is not re-entrant, so a module
    singleton is safe (same assumption as flat_leaf's module caches)."""
    cdef int cap_cells          # allocated H*W capacity
    cdef int H, W, ncells
    # boundary tables (memset -1 per call)
    cdef int *city_tab          # (rc*9+six) -> city node id
    cdef int *road_tab          # (rc*9+six) -> road node id
    cdef int *farm_tab          # (rc*8+fsix) -> farm node id
    cdef int *pos0_tab          # (rc*9+six)  -> farm node id (farmer_positions[0])
    cdef int *anypos_tab        # (rc*9+six)  -> farm node id (any farmer_position)
    # per-cell facts (memset 0 per call)
    cdef char *cell_occ
    cdef char *cell_inn
    cdef char *cell_shield
    # city nodes/edges
    cdef int n_city
    cdef int *city_nr
    cdef int *city_nc
    cdef int *city_nix
    cdef char *city_openb
    cdef int n_city_e
    cdef int *city_eu
    cdef int *city_ev
    cdef int *city_lab
    # road nodes/edges
    cdef int n_road
    cdef int *road_nr
    cdef int *road_nc
    cdef int *road_nix
    cdef char *road_openb
    cdef int n_road_e
    cdef int *road_eu
    cdef int *road_ev
    cdef int *road_lab
    # farm nodes/edges
    cdef int n_farm
    cdef int *farm_nr
    cdef int *farm_nc
    cdef int n_farm_e
    cdef int *farm_eu
    cdef int *farm_ev
    cdef int *farm_lab
    cdef int *farm_tc           # concatenated tile_connections ixs
    cdef int *farm_tc_start     # n_farm+1
    cdef int *farm_cs           # concatenated city_sides ixs
    cdef int *farm_cs_start     # n_farm+1
    cdef int farm_tc_n, farm_cs_n
    # union-find / sort scratch
    cdef int *parent            # max(cap city, cap farm)
    cdef int *order
    cdef int *bstart            # bucket starts (n+1)
    # per-root facts (indexed by root node id)
    cdef char *city_fin
    cdef int *city_open_n
    cdef int *city_total
    cdef int *city_shieldn
    cdef char *city_cath
    cdef int *city_delta
    cdef char *road_fin
    cdef int *road_total
    cdef char *road_inn
    cdef int *farm_fincities
    cdef int *farm_adj          # concatenated deduped adjacent city roots
    cdef int *farm_adj_lo
    cdef int *farm_adj_hi
    # stamps (monotone counters; never cleared)
    cdef long *stamp_cell
    cdef long *stamp_city
    cdef long *stamp_farm
    cdef long counter

    def __cinit__(self):
        self.cap_cells = 0

    cdef int ensure(self, int H, int W) except -1:
        cdef int nc = H * W
        self.H = H
        self.W = W
        self.ncells = nc
        if nc <= self.cap_cells:
            return 0
        self._free_all()
        cdef int c4 = 4 * nc, c8 = 8 * nc, c9 = 9 * nc, e = 2 * c4
        self.city_tab = <int *>malloc(c9 * sizeof(int))
        self.road_tab = <int *>malloc(c9 * sizeof(int))
        self.farm_tab = <int *>malloc(c8 * sizeof(int))
        self.pos0_tab = <int *>malloc(c9 * sizeof(int))
        self.anypos_tab = <int *>malloc(c9 * sizeof(int))
        self.cell_occ = <char *>malloc(nc)
        self.cell_inn = <char *>malloc(nc)
        self.cell_shield = <char *>malloc(nc)
        self.city_nr = <int *>malloc(c4 * sizeof(int))
        self.city_nc = <int *>malloc(c4 * sizeof(int))
        self.city_nix = <int *>malloc(c4 * sizeof(int))
        self.city_openb = <char *>malloc(c4)
        self.city_eu = <int *>malloc(e * sizeof(int))
        self.city_ev = <int *>malloc(e * sizeof(int))
        self.city_lab = <int *>malloc(c4 * sizeof(int))
        self.road_nr = <int *>malloc(c4 * sizeof(int))
        self.road_nc = <int *>malloc(c4 * sizeof(int))
        self.road_nix = <int *>malloc(c4 * sizeof(int))
        self.road_openb = <char *>malloc(c4)
        self.road_eu = <int *>malloc(e * sizeof(int))
        self.road_ev = <int *>malloc(e * sizeof(int))
        self.road_lab = <int *>malloc(c4 * sizeof(int))
        self.farm_nr = <int *>malloc(c8 * sizeof(int))
        self.farm_nc = <int *>malloc(c8 * sizeof(int))
        self.farm_eu = <int *>malloc(c8 * 2 * sizeof(int))
        self.farm_ev = <int *>malloc(c8 * 2 * sizeof(int))
        self.farm_lab = <int *>malloc(c8 * sizeof(int))
        self.farm_tc = <int *>malloc(c8 * sizeof(int))
        self.farm_tc_start = <int *>malloc((c8 + 1) * sizeof(int))
        self.farm_cs = <int *>malloc(c8 * sizeof(int))
        self.farm_cs_start = <int *>malloc((c8 + 1) * sizeof(int))
        self.parent = <int *>malloc(c8 * sizeof(int))
        self.order = <int *>malloc(c8 * sizeof(int))
        self.bstart = <int *>malloc((c8 + 1) * sizeof(int))
        self.city_fin = <char *>malloc(c4)
        self.city_open_n = <int *>malloc(c4 * sizeof(int))
        self.city_total = <int *>malloc(c4 * sizeof(int))
        self.city_shieldn = <int *>malloc(c4 * sizeof(int))
        self.city_cath = <char *>malloc(c4)
        self.city_delta = <int *>malloc(c4 * sizeof(int))
        self.road_fin = <char *>malloc(c4)
        self.road_total = <int *>malloc(c4 * sizeof(int))
        self.road_inn = <char *>malloc(c4)
        self.farm_fincities = <int *>malloc(c8 * sizeof(int))
        self.farm_adj = <int *>malloc(c8 * sizeof(int))
        self.farm_adj_lo = <int *>malloc(c8 * sizeof(int))
        self.farm_adj_hi = <int *>malloc(c8 * sizeof(int))
        self.stamp_cell = <long *>malloc(nc * sizeof(long))
        self.stamp_city = <long *>malloc(c4 * sizeof(long))
        self.stamp_farm = <long *>malloc(c8 * sizeof(long))
        if (self.city_tab == NULL or self.farm_tab == NULL or self.pos0_tab == NULL
                or self.anypos_tab == NULL or self.cell_occ == NULL
                or self.stamp_farm == NULL or self.farm_adj_hi == NULL):
            raise MemoryError("flat_leaf_cy workspace allocation failed")
        memset(self.stamp_cell, 0, nc * sizeof(long))
        memset(self.stamp_city, 0, c4 * sizeof(long))
        memset(self.stamp_farm, 0, c8 * sizeof(long))
        self.counter = 0
        self.cap_cells = nc
        return 0

    cdef void _free_all(self):
        if self.cap_cells == 0:
            return
        free(self.city_tab); free(self.road_tab); free(self.farm_tab)
        free(self.pos0_tab)
        free(self.anypos_tab)
        free(self.cell_occ)
        free(self.cell_inn); free(self.cell_shield)
        free(self.city_nr); free(self.city_nc); free(self.city_nix)
        free(self.city_openb); free(self.city_eu); free(self.city_ev)
        free(self.city_lab)
        free(self.road_nr); free(self.road_nc); free(self.road_nix)
        free(self.road_openb); free(self.road_eu); free(self.road_ev)
        free(self.road_lab)
        free(self.farm_nr); free(self.farm_nc); free(self.farm_eu)
        free(self.farm_ev); free(self.farm_lab)
        free(self.farm_tc); free(self.farm_tc_start)
        free(self.farm_cs); free(self.farm_cs_start)
        free(self.parent); free(self.order); free(self.bstart)
        free(self.city_fin); free(self.city_open_n); free(self.city_total)
        free(self.city_shieldn); free(self.city_cath); free(self.city_delta)
        free(self.road_fin); free(self.road_total); free(self.road_inn)
        free(self.farm_fincities); free(self.farm_adj)
        free(self.farm_adj_lo); free(self.farm_adj_hi)
        free(self.stamp_cell); free(self.stamp_city); free(self.stamp_farm)
        self.cap_cells = 0

    def __dealloc__(self):
        self._free_all()


cdef _WS _ws = _WS()


cdef inline void _uf_label(int n, int ne, int *eu, int *ev, int *parent, int *lab) noexcept:
    """== flat_leaf._label_components: path-halving find, parent[a]=b unions in
    edge order, then final find per node. Bit-identical labels for identical
    node/edge order."""
    cdef int i, a, b, x
    for i in range(n):
        parent[i] = i
    for i in range(ne):
        # find(eu[i])
        x = eu[i]
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        a = x
        # find(ev[i])
        x = ev[i]
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        b = x
        if a != b:
            parent[a] = b
    for i in range(n):
        x = i
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        lab[i] = x


cdef inline void _bucket_by_root(int n, int *lab, int *bstart, int *order) noexcept:
    """Counting sort node ids by root label. bstart has n+1 entries; after the
    call, members of root r are order[bstart[r] : bstart[r+1]] (bstart is the
    standard shifted prefix array)."""
    cdef int i, r, acc, t
    for i in range(n + 1):
        bstart[i] = 0
    for i in range(n):
        bstart[lab[i] + 1] += 1
    acc = 0
    for i in range(1, n + 1):
        bstart[i] += bstart[i - 1]
    # stable fill using a moving cursor (reuse a second pass over bstart copy
    # is avoided by filling into order with per-root cursors kept in bstart's
    # own slots — restore after)
    # simple approach: temporary cursor array not needed; iterate nodes and
    # place at bstart[lab[i]]++, then shift back.
    for i in range(n):
        r = lab[i]
        order[bstart[r]] = i
        bstart[r] += 1
    # shift bstart back (bstart[r] now == end of bucket r == start of r+1)
    t = 0
    for i in range(n):
        r = bstart[i]
        bstart[i] = t
        t = r


cdef int _decompose_c(object state, _WS ws) except -1:
    """Build the full flat decomposition into ws. Node/edge enumeration order
    mirrors flat_leaf.decompose exactly -> identical component root ids."""
    cdef list board = <list>state.board
    cdef int H = len(board)
    cdef int W = len(<list>board[0]) if H else 0
    ws.ensure(H, W)
    cdef int nc = ws.ncells
    memset(ws.city_tab, 0xFF, 9 * nc * sizeof(int))
    memset(ws.road_tab, 0xFF, 9 * nc * sizeof(int))
    memset(ws.farm_tab, 0xFF, 8 * nc * sizeof(int))
    memset(ws.pos0_tab, 0xFF, 9 * nc * sizeof(int))
    memset(ws.anypos_tab, 0xFF, 9 * nc * sizeof(int))
    memset(ws.cell_occ, 0, nc)
    memset(ws.cell_inn, 0, nc)
    memset(ws.cell_shield, 0, nc)

    cdef int cap4 = 4 * nc, cap8 = 8 * nc, cape = 8 * nc
    cdef int n_city = 0, n_road = 0, n_farm = 0
    cdef int ne_city = 0, ne_road = 0, ne_farm = 0
    cdef int tc_n = 0, cs_n = 0
    cdef int r, c, rc, j, k, six, a_ix, b_ix, nid, first, ida, idb
    cdef int dr, dc, oix, nr2, nc2, onid, fsix, t
    cdef list brow
    cdef object tile
    cdef tuple feat, cg, rdc, ftc, ffp, fcs, group, fp

    for r in range(H):
        brow = <list>board[r]
        for c in range(W):
            tile = brow[c]
            if tile is None:
                continue
            rc = r * W + c
            ws.cell_occ[rc] = 1
            feat = _tile_features(tile)
            cg = <tuple>feat[0]
            rdc = <tuple>feat[1]
            ftc = <tuple>feat[2]
            ffp = <tuple>feat[3]
            fcs = <tuple>feat[4]
            ws.cell_inn[rc] = <char><int>feat[5]
            ws.cell_shield[rc] = <char><int>feat[6]
            # --- cities: nodes per (tile, city side); group members union ---
            for group in cg:
                first = -1
                for j in range(len(group)):
                    six = <int>group[j]
                    nid = ws.city_tab[rc * 9 + six]
                    if nid < 0:
                        if n_city >= cap4:
                            raise RuntimeError("flat_leaf_cy: city node capacity")
                        nid = n_city
                        ws.city_tab[rc * 9 + six] = nid
                        ws.city_nr[nid] = r
                        ws.city_nc[nid] = c
                        ws.city_nix[nid] = six
                        n_city += 1
                    if j == 0:
                        first = nid
                    else:
                        if ne_city >= cape:
                            raise RuntimeError("flat_leaf_cy: city edge capacity")
                        ws.city_eu[ne_city] = first
                        ws.city_ev[ne_city] = nid
                        ne_city += 1
            # --- roads: non-CENTER ends; both-non-CENTER connections union ---
            for group in rdc:          # (a_ix, b_ix), -1 == CENTER
                a_ix = <int>group[0]
                b_ix = <int>group[1]
                ida = -1
                idb = -1
                # get-or-create a-then-b (creation order mirrors Python)
                if a_ix >= 0:
                    ida = _road_nid(ws, rc, r, c, a_ix, &n_road, cap4)
                if b_ix >= 0:
                    idb = _road_nid(ws, rc, r, c, b_ix, &n_road, cap4)
                if a_ix >= 0 and b_ix >= 0:
                    if ne_road >= cape:
                        raise RuntimeError("flat_leaf_cy: road edge capacity")
                    ws.road_eu[ne_road] = ida
                    ws.road_ev[ne_road] = idb
                    ne_road += 1
            # --- farms: one node per FarmerConnection -----------------------
            for k in range(len(ftc)):
                if n_farm >= cap8:
                    raise RuntimeError("flat_leaf_cy: farm node capacity")
                nid = n_farm
                ws.farm_nr[nid] = r
                ws.farm_nc[nid] = c
                ws.farm_tc_start[nid] = tc_n
                group = <tuple>ftc[k]
                for j in range(len(group)):
                    fsix = <int>group[j]
                    if tc_n >= cap8:
                        raise RuntimeError("flat_leaf_cy: farm tc capacity")
                    ws.farm_tc[tc_n] = fsix
                    tc_n += 1
                    ws.farm_tab[rc * 8 + fsix] = nid
                ws.farm_cs_start[nid] = cs_n
                group = <tuple>fcs[k]
                for j in range(len(group)):
                    if cs_n >= cap8:
                        raise RuntimeError("flat_leaf_cy: farm cs capacity")
                    ws.farm_cs[cs_n] = <int>group[j]
                    cs_n += 1
                fp = <tuple>ffp[k]
                if len(fp) > 0:
                    ws.pos0_tab[rc * 9 + <int>fp[0]] = nid
                    for j in range(len(fp)):
                        ws.anypos_tab[rc * 9 + <int>fp[j]] = nid
                n_farm += 1
    ws.farm_tc_start[n_farm] = tc_n
    ws.farm_cs_start[n_farm] = cs_n
    ws.farm_tc_n = tc_n
    ws.farm_cs_n = cs_n

    # ---- cross-tile edges + open detection (node-id order, like Python) ----
    for nid in range(n_city):
        r = ws.city_nr[nid]; c = ws.city_nc[nid]; six = ws.city_nix[nid]
        dr = _OPP_DR[six]; dc = _OPP_DC[six]; oix = _OPP_IX[six]
        nr2 = r + dr; nc2 = c + dc
        onid = -1
        if 0 <= nr2 < H and 0 <= nc2 < W:
            onid = ws.city_tab[(nr2 * W + nc2) * 9 + oix]
        if onid >= 0:
            if ne_city >= cape:
                raise RuntimeError("flat_leaf_cy: city edge capacity")
            ws.city_eu[ne_city] = nid
            ws.city_ev[ne_city] = onid
            ne_city += 1
            ws.city_openb[nid] = 0
        else:
            ws.city_openb[nid] = 1
    for nid in range(n_road):
        r = ws.road_nr[nid]; c = ws.road_nc[nid]; six = ws.road_nix[nid]
        dr = _OPP_DR[six]; dc = _OPP_DC[six]; oix = _OPP_IX[six]
        nr2 = r + dr; nc2 = c + dc
        onid = -1
        if 0 <= nr2 < H and 0 <= nc2 < W:
            onid = ws.road_tab[(nr2 * W + nc2) * 9 + oix]
        if onid >= 0:
            if ne_road >= cape:
                raise RuntimeError("flat_leaf_cy: road edge capacity")
            ws.road_eu[ne_road] = nid
            ws.road_ev[ne_road] = onid
            ne_road += 1
            ws.road_openb[nid] = 0
        else:
            ws.road_openb[nid] = 1
    for nid in range(n_farm):
        r = ws.farm_nr[nid]; c = ws.farm_nc[nid]
        for t in range(ws.farm_tc_start[nid], ws.farm_tc_start[nid + 1]):
            fsix = ws.farm_tc[t]
            nr2 = r + _FS_DR[fsix]; nc2 = c + _FS_DC[fsix]
            onid = -1
            if 0 <= nr2 < H and 0 <= nc2 < W:
                onid = ws.farm_tab[(nr2 * W + nc2) * 8 + _FS_OPPC[fsix]]
            if onid >= 0:
                if ne_farm >= 2 * cap8:
                    raise RuntimeError("flat_leaf_cy: farm edge capacity")
                ws.farm_eu[ne_farm] = nid
                ws.farm_ev[ne_farm] = onid
                ne_farm += 1

    ws.n_city = n_city; ws.n_city_e = ne_city
    ws.n_road = n_road; ws.n_road_e = ne_road
    ws.n_farm = n_farm; ws.n_farm_e = ne_farm

    # ---- label components ---------------------------------------------------
    _uf_label(n_city, ne_city, ws.city_eu, ws.city_ev, ws.parent, ws.city_lab)
    _uf_label(n_road, ne_road, ws.road_eu, ws.road_ev, ws.parent, ws.road_lab)
    _uf_label(n_farm, ne_farm, ws.farm_eu, ws.farm_ev, ws.parent, ws.farm_lab)

    # ---- city facts -----------------------------------------------------------
    _bucket_by_root(n_city, ws.city_lab, ws.bstart, ws.order)
    cdef int root, m, i0, i1, total, shn, open_n
    cdef char fin, cath
    cdef long stamp
    root = 0
    while root < n_city:
        i0 = ws.bstart[root]; i1 = ws.bstart[root + 1]
        if i1 > i0:
            ws.counter += 1
            stamp = ws.counter
            fin = 1; total = 0; shn = 0; cath = 0; open_n = 0
            for m in range(i0, i1):
                nid = ws.order[m]
                if ws.city_openb[nid]:
                    fin = 0
                r = ws.city_nr[nid]; c = ws.city_nc[nid]; six = ws.city_nix[nid]
                rc = r * W + c
                if ws.stamp_cell[rc] != stamp:
                    ws.stamp_cell[rc] = stamp
                    total += 1
                    shn += ws.cell_shield[rc]
                    if ws.cell_inn[rc]:
                        cath = 1
                # closure proximity: distinct EMPTY outward neighbours
                nr2 = r + _OPP_DR[six]; nc2 = c + _OPP_DC[six]
                if 0 <= nr2 < H and 0 <= nc2 < W:
                    rc = nr2 * W + nc2
                    if not ws.cell_occ[rc] and ws.stamp_cell[rc] != stamp:
                        ws.stamp_cell[rc] = stamp
                        open_n += 1
            ws.city_fin[root] = fin
            ws.city_open_n[root] = open_n
            ws.city_total[root] = total
            ws.city_shieldn[root] = shn
            ws.city_cath[root] = cath
            ws.city_delta[root] = (3 * total + 3 * shn) if cath else (total + shn)
        root += 1

    # ---- road facts -----------------------------------------------------------
    _bucket_by_root(n_road, ws.road_lab, ws.bstart, ws.order)
    cdef char rinn
    root = 0
    while root < n_road:
        i0 = ws.bstart[root]; i1 = ws.bstart[root + 1]
        if i1 > i0:
            ws.counter += 1
            stamp = ws.counter
            fin = 1; total = 0; rinn = 0
            for m in range(i0, i1):
                nid = ws.order[m]
                if ws.road_openb[nid]:
                    fin = 0
                rc = ws.road_nr[nid] * W + ws.road_nc[nid]
                if ws.stamp_cell[rc] != stamp:
                    ws.stamp_cell[rc] = stamp
                    total += 1
                    if ws.cell_inn[rc]:
                        rinn = 1
            ws.road_fin[root] = fin
            ws.road_total[root] = total
            ws.road_inn[root] = rinn
        root += 1

    # ---- farm facts (adjacent city components, deduped by city root) ---------
    _bucket_by_root(n_farm, ws.farm_lab, ws.bstart, ws.order)
    cdef int adj_pos = 0, cnid, croot, fincnt
    root = 0
    while root < n_farm:
        i0 = ws.bstart[root]; i1 = ws.bstart[root + 1]
        if i1 > i0:
            ws.counter += 1
            stamp = ws.counter
            ws.farm_adj_lo[root] = adj_pos
            fincnt = 0
            for m in range(i0, i1):
                nid = ws.order[m]
                rc = ws.farm_nr[nid] * W + ws.farm_nc[nid]
                for t in range(ws.farm_cs_start[nid], ws.farm_cs_start[nid + 1]):
                    cnid = ws.city_tab[rc * 9 + ws.farm_cs[t]]
                    if cnid >= 0:
                        croot = ws.city_lab[cnid]
                        if ws.stamp_city[croot] != stamp:
                            ws.stamp_city[croot] = stamp
                            if adj_pos >= cap8:
                                raise RuntimeError("flat_leaf_cy: farm adj capacity")
                            ws.farm_adj[adj_pos] = croot
                            adj_pos += 1
                            if ws.city_fin[croot]:
                                fincnt += 1
            ws.farm_adj_hi[root] = adj_pos
            ws.farm_fincities[root] = fincnt
        root += 1
    return 0


cdef inline int _road_nid(_WS ws, int rc, int r, int c, int ix, int *n_road, int cap4) except -1:
    cdef int nid = ws.road_tab[rc * 9 + ix]
    if nid < 0:
        if n_road[0] >= cap4:
            raise RuntimeError("flat_leaf_cy: road node capacity")
        nid = n_road[0]
        ws.road_tab[rc * 9 + ix] = nid
        ws.road_nr[nid] = r
        ws.road_nc[nid] = c
        ws.road_nix[nid] = ix
        n_road[0] += 1
    return nid


# --- scoring ------------------------------------------------------------------
cdef inline int _city_points_c(_WS ws, int root) noexcept:
    """== flat_leaf._city_points from the per-root facts."""
    cdef int total = ws.city_total[root]
    cdef int shn = ws.city_shieldn[root]
    if not ws.city_fin[root] and ws.city_cath[root]:
        return 0
    if ws.city_cath[root]:
        return 6 * shn + 3 * (total - shn)
    if ws.city_fin[root]:
        return 4 * shn + 2 * (total - shn)
    return 2 * shn + (total - shn)


cdef inline int _road_points_c(_WS ws, int root) noexcept:
    if not ws.road_fin[root] and ws.road_inn[root]:
        return 0
    return (2 if ws.road_inn[root] else 1) * ws.road_total[root]


cdef inline int _cloister_points_c(_WS ws, int r, int c) noexcept:
    cdef int pts = 0, rr, cc
    for rr in range(r - 1, r + 2):
        if rr < 0 or rr >= ws.H:
            continue
        for cc in range(c - 1, c + 2):
            if cc < 0 or cc >= ws.W:
                continue
            if ws.cell_occ[rr * ws.W + cc]:
                pts += 1
    return pts


cdef inline int _feat_add(int *roots, int *w0, int *w1, int *n, int root, int player, int w) except -1:
    """find-or-add (root) in the tiny meepled-feature table; add weight."""
    cdef int i
    for i in range(n[0]):
        if roots[i] == root:
            if player == 0:
                w0[i] += w
            else:
                w1[i] += w
            return 0
    if n[0] >= 32:
        raise RuntimeError("flat_leaf_cy: meepled-feature table overflow")
    roots[n[0]] = root
    w0[n[0]] = w if player == 0 else 0
    w1[n[0]] = w if player == 1 else 0
    n[0] += 1
    return 0


cdef int _final_scores_c(object state, _WS ws, long *out) except -1:
    """== flat_leaf._final_scores for 2 players (points count_final_scores would ADD)."""
    cdef list board = <list>state.board
    cdef int W = ws.W
    cdef int croots[32]
    cdef int cw0[32]
    cdef int cw1[32]
    cdef int rroots[32]
    cdef int rw0[32]
    cdef int rw1[32]
    cdef int froots[32]
    cdef int fw0[32]
    cdef int fw1[32]
    cdef int ncr = 0, nrr = 0, nfr = 0
    cdef long clo0 = 0, clo1 = 0
    cdef int player, r, c, w, six, nid, root, i, m0, m1, pts
    cdef object mp, cws, coord, side, tile, terrain, mtype
    cdef list pm
    side_ix = _SIDE_IX

    for player in range(2):
        pm = <list>state.placed_meeples[player]
        for mp in pm:
            cws = mp.coordinate_with_side
            coord = cws.coordinate
            r = <int>coord.row
            c = <int>coord.column
            side = cws.side
            tile = (<list>board[r])[c]
            terrain = tile.get_type(side)
            mtype = mp.meeple_type
            w = 2 if (mtype is _M_BIG or mtype is _M_BIG_FARMER) else 1
            six = <int>side_ix[side]
            if terrain is _T_CITY:
                nid = ws.city_tab[(r * W + c) * 9 + six]
                if nid >= 0:
                    _feat_add(croots, cw0, cw1, &ncr, ws.city_lab[nid], player, w)
            elif terrain is _T_ROAD:
                nid = ws.road_tab[(r * W + c) * 9 + six]
                if nid >= 0:
                    _feat_add(rroots, rw0, rw1, &nrr, ws.road_lab[nid], player, w)
            elif terrain is _T_CHAPEL or terrain is _T_FLOWERS:
                pts = _cloister_points_c(ws, r, c)
                if player == 0:
                    clo0 += pts
                else:
                    clo1 += pts
            elif mtype is _M_FARMER or mtype is _M_BIG_FARMER:
                nid = ws.pos0_tab[(r * W + c) * 9 + six]
                if nid >= 0:
                    _feat_add(froots, fw0, fw1, &nfr, ws.farm_lab[nid], player, w)

    out[0] = clo0
    out[1] = clo1
    for i in range(ncr):
        m0 = cw0[i]; m1 = cw1[i]
        if m0 == 0 and m1 == 0:
            continue
        pts = _city_points_c(ws, croots[i])
        if m0 >= m1 and m0 > 0:
            out[0] += pts
        if m1 >= m0 and m1 > 0:
            out[1] += pts
    for i in range(nrr):
        m0 = rw0[i]; m1 = rw1[i]
        if m0 == 0 and m1 == 0:
            continue
        pts = _road_points_c(ws, rroots[i])
        if m0 >= m1 and m0 > 0:
            out[0] += pts
        if m1 >= m0 and m1 > 0:
            out[1] += pts
    for i in range(nfr):
        m0 = fw0[i]; m1 = fw1[i]
        if m0 == 0 and m1 == 0:
            continue
        pts = 3 * ws.farm_fincities[froots[i]]
        if m0 >= m1 and m0 > 0:
            out[0] += pts
        if m1 >= m0 and m1 > 0:
            out[1] += pts
    return 0


cdef double _closure_bonus_c(object state, int player, _WS ws, object closure_p) except? -12345.0:
    """== flat_leaf.flat_closure_bonus (UNCAPPED): same multiset of float
    contributions, reduced with math.fsum (order-independent)."""
    cdef list board = <list>state.board
    cdef int W = ws.W
    cdef int knroots[16]
    cdef int frroots[16]
    cdef int clr[16]
    cdef int clc[16]
    cdef int nkn = 0, nfr = 0, ncl = 0
    cdef int r, c, six, nid, root, i, t, open_n, needed, n_sur
    cdef object mp, cws, coord, side, tile, terrain, mtype, pobj
    cdef double pd
    cdef list contribs = []
    cdef long stamp
    side_ix = _SIDE_IX

    for mp in <list>state.placed_meeples[player]:
        cws = mp.coordinate_with_side
        coord = cws.coordinate
        r = <int>coord.row
        c = <int>coord.column
        side = cws.side
        tile = (<list>board[r])[c]
        terrain = tile.get_type(side)
        mtype = mp.meeple_type
        six = <int>side_ix[side]
        if terrain is _T_CITY:
            nid = ws.city_tab[(r * W + c) * 9 + six]
            if nid >= 0:
                root = ws.city_lab[nid]
                for i in range(nkn):
                    if knroots[i] == root:
                        break
                else:
                    if nkn >= 16:
                        raise RuntimeError("flat_leaf_cy: knight roots overflow")
                    knroots[nkn] = root
                    nkn += 1
        elif terrain is _T_CHAPEL or terrain is _T_FLOWERS:
            if ncl >= 16:
                raise RuntimeError("flat_leaf_cy: cloister list overflow")
            clr[ncl] = r
            clc[ncl] = c
            ncl += 1
        elif mtype is _M_FARMER or mtype is _M_BIG_FARMER:
            nid = ws.anypos_tab[(r * W + c) * 9 + six]
            if nid >= 0:
                root = ws.farm_lab[nid]
                for i in range(nfr):
                    if frroots[i] == root:
                        break
                else:
                    if nfr >= 16:
                        raise RuntimeError("flat_leaf_cy: farm roots overflow")
                    frroots[nfr] = root
                    nfr += 1

    # city closures
    for i in range(nkn):
        root = knroots[i]
        if ws.city_fin[root]:
            continue
        open_n = ws.city_open_n[root]
        if open_n <= 0:
            continue
        pobj = closure_p.get(open_n)
        if pobj is None:
            continue
        pd = <double>pobj
        if pd > 0:
            contribs.append(pd * ws.city_delta[root])

    # cloisters
    for i in range(ncl):
        n_sur = _cloister_points_c(ws, clr[i], clc[i]) - 1  # exclude centre (occupied)
        needed = 8 - n_sur
        if needed > 0:
            pobj = closure_p.get(needed)
            if pobj is not None:
                pd = <double>pobj
                if pd > 0:
                    contribs.append(pd * needed)

    # farm growth (incomplete adjacent cities, deduped across the player's farms)
    ws.counter += 1
    stamp = ws.counter
    for i in range(nfr):
        root = frroots[i]
        for t in range(ws.farm_adj_lo[root], ws.farm_adj_hi[root]):
            nid = ws.farm_adj[t]          # a city root
            if ws.stamp_city[nid] == stamp:
                continue
            ws.stamp_city[nid] = stamp
            if ws.city_fin[nid]:
                continue
            open_n = ws.city_open_n[nid]
            if open_n <= 0:
                continue
            pobj = closure_p.get(open_n)
            if pobj is None:
                continue
            pd = <double>pobj
            if pd > 0:
                contribs.append(pd * 3.0)

    return <double>_fsum(contribs)


cdef inline double _curve_lookup_c(object curve, long n):
    """== flat_leaf._flat_curve_lookup / leaf_v29._curve_lookup. Value of holding `n`
    free meeples, clamped into [0, len-1]."""
    cdef Py_ssize_t L = len(curve)
    if n < 0:
        n = 0
    elif n >= L:
        n = L - 1
    return <double>curve[n]


def flat_virtual_score_v2_cy(state, int player, cfg=None):
    """Cython drop-in for flat_leaf.flat_virtual_score_v2 (bit-exact)."""
    if state.players != 2:
        raise ValueError(f"flat_virtual_score_v2 is 2-player only; got {state.players}")
    if cfg is None:
        from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
        cfg = DEFAULT_CONFIG
    if cfg.tile_counting_closure or cfg.closure_continuous_slack > 0.0:
        raise NotImplementedError(
            "flat_closure_bonus implements only the v2.7 schedule path "
            "(no tile_counting_closure / closure_continuous_slack)"
        )
    cdef _WS ws = _ws
    _decompose_c(state, ws)
    cdef int opp = 1 - player
    cdef long final[2]
    _final_scores_c(state, ws, final)
    scores = state.scores
    cdef long running = <long>int(scores[player]) - <long>int(scores[opp])
    cdef long base = running + (final[player] - final[opp])

    closure_p = cfg.closure_p
    cdef double bonus_self = _closure_bonus_c(state, player, ws, closure_p)
    cdef double bonus_opp = _closure_bonus_c(state, opp, ws, closure_p)
    cdef double cap = <double>cfg.bonus_cap
    cdef double opp_cap = <double>cfg.opp_bonus_cap
    if bonus_self > cap:
        bonus_self = cap
    if bonus_opp > opp_cap:
        bonus_opp = opp_cap
    cdef double score = base + bonus_self - bonus_opp
    cdef double meeple_k = <double>cfg.meeple_k
    cdef object curve = cfg.v29_meeple_curve
    if curve is not None:
        # v2.9 Candidate B: nonlinear meeple liquidity curve REPLACES the flat
        # meeple_k term (== flat_leaf._flat_curve_lookup / leaf_v29._meeple_curve_term).
        meeples = state.meeples
        score += _curve_lookup_c(curve, <long>int(meeples[player])) - _curve_lookup_c(curve, <long>int(meeples[opp]))
    elif meeple_k > 0.0:
        meeples = state.meeples
        score += meeple_k * (<long>int(meeples[player]) - <long>int(meeples[opp]))
    # Python round semantics (banker's rounding) on a boxed float — exact match
    # with flat_leaf's `int(round(score))`.
    score_obj = score
    return int(round(score_obj))


def flat_base_score_cy(state, int player):
    """== flat_leaf.flat_base_score (pure-int base differential)."""
    if state.players != 2:
        raise ValueError(f"flat_base_score is 2-player only; got {state.players}")
    cdef _WS ws = _ws
    _decompose_c(state, ws)
    cdef int opp = 1 - player
    cdef long final[2]
    _final_scores_c(state, ws, final)
    scores = state.scores
    cdef long running = <long>int(scores[player]) - <long>int(scores[opp])
    return running + (final[player] - final[opp])


# ============================================================================ #
# PROBE A — per-component feature emit (docs/PROBE_A_STRUCTURED_VALUE_SPEC.md).
#
# Emits the (n_comp, FEAT_DIM) feature matrix defined by
# scripts/probe_a/component_features.py (the FROZEN A1<->A2 contract) from the
# SAME C decomposition the scalar leaf computes — NO second decompose. Bit-exact
# to that Python reference (gated by tests/test_probe_a_feature_emit.py).
#
# Row order (must match the reference): cities asc root id, roads asc root id,
# farms asc root id, then ONE meeple-economy pseudo-row. See the reference module
# docstring for the column semantics; the C indices below mirror its C_* consts.
# ADDITIVE: does not touch flat_virtual_score_v2_cy.
# ============================================================================ #
PROBE_A_FEAT_DIM = 24

# Column indices — keep in lockstep with component_features.py C_* constants.
cdef enum:
    _C_IS_CITY = 0
    _C_IS_ROAD = 1
    _C_IS_FARM = 2
    _C_IS_ECON = 3
    _C_N_TILES = 4
    _C_N_SHIELDS = 5
    _C_IS_CATHEDRAL = 6
    _C_FINISHED = 7
    _C_OPEN_N = 8
    _C_CLOSURE_DELTA = 9
    _C_SELF_MEEPLE_W = 10
    _C_OPP_MEEPLE_W = 11
    _C_FARM_FIN_CITIES = 12
    _C_FARM_POTENTIAL3 = 13
    _C_SELF_GROWTH_P_SUM = 14
    _C_SELF_CITY_CLOSE_P = 15
    _C_ECON_SELF_FREE = 16
    _C_ECON_OPP_FREE = 17
    _C_ECON_K_REMAINING = 18
    _C_CLOISTER_IS = 19
    _C_CLOISTER_NEEDED = 20
    _C_CLOISTER_SELF = 21
    _C_CLOISTER_OPP = 22
    _C_BIAS = 23


cdef int _k_remaining_c(state) except -12345:
    """== component_features._k_remaining: len(deck) [+1 if a tile is drawn but
    unplaced in the TILES phase]. Uses the engine GamePhase enum by identity."""
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    cdef int k = len(<list>state.deck)
    nt = getattr(state, "next_tile", None)
    if nt is not None and state.phase is GamePhase.TILES:
        k += 1
    return k


def component_features_cy(state, int root_player=0, closure_p=None):
    """Emit the Probe-A per-component feature matrix (n_comp, FEAT_DIM) float32.

    Bit-exact to scripts/probe_a/component_features.component_features. Reuses the
    scalar leaf's C decomposition (`_decompose_c`) so there is NO second decompose.
    `closure_p` defaults to DEFAULT_CONFIG.closure_p (production v2.9 schedule).
    """
    import numpy as np
    if state.players != 2:
        raise ValueError(f"component_features_cy is 2-player only; got {state.players}")
    if closure_p is None:
        from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
        closure_p = DEFAULT_CONFIG.closure_p

    cdef _WS ws = _ws
    _decompose_c(state, ws)
    cdef int W = ws.W, H = ws.H
    cdef int opp = 1 - root_player

    # ---- distinct roots per kind, ascending (== sorted(...keys())) --------- #
    # A root id equals its own label (a root labels itself), and every root has
    # >=1 member node; collect distinct labels via a membership pass over nodes.
    # We reuse ws.bstart as a "seen" stamp keyed by root id (bounded by n_*).
    # Distinct root ids per kind, ascending (== Python sorted(...keys())). A root
    # labels itself, so the distinct labels ARE the roots; collect + sort. Local
    # sets keep this independent of the leaf's monotone stamp arrays (no fiddling
    # with ws state that the scalar leaf relies on).
    cdef int nid, root, i, j, t
    cdef int n_city = ws.n_city
    cdef int n_road = ws.n_road
    cdef int n_farm = ws.n_farm
    cdef set cseen = set()
    for nid in range(n_city):
        cseen.add(ws.city_lab[nid])
    cdef list city_roots = sorted(cseen)
    cdef set rseen = set()
    for nid in range(n_road):
        rseen.add(ws.road_lab[nid])
    cdef list road_roots = sorted(rseen)
    cdef set fseen = set()
    for nid in range(n_farm):
        fseen.add(ws.farm_lab[nid])
    cdef list farm_roots = sorted(fseen)

    cdef int n_city_c = len(city_roots)
    cdef int n_road_c = len(road_roots)
    cdef int n_farm_c = len(farm_roots)
    cdef int n_rows = n_city_c + n_road_c + n_farm_c + 1  # + meeple-econ row

    out = np.zeros((n_rows, PROBE_A_FEAT_DIM), dtype=np.float32)
    cdef float[:, ::1] X = out

    # ---- per-component self/opp weighted meeple counts --------------------- #
    # One pass over BOTH players' placed meeples, routed to root ids exactly like
    # _final_scores_c (city_side->city_lab, road_side->road_lab, farm pos0->farm_lab).
    # Keyed dicts root->[self_w, opp_w].
    cdef dict city_own = {}
    cdef dict road_own = {}
    cdef dict farm_own = {}
    cdef object mp, cws, coord, side, tile, terrain, mtype
    cdef int r, c, six, w, is_self
    side_ix = _SIDE_IX
    cdef list pm
    for pl in range(2):
        is_self = 1 if pl == root_player else 0
        pm = <list>state.placed_meeples[pl]
        for mp in pm:
            cws = mp.coordinate_with_side
            coord = cws.coordinate
            r = <int>coord.row
            c = <int>coord.column
            side = cws.side
            tile = (<list>state.board[r])[c]
            terrain = tile.get_type(side)
            mtype = mp.meeple_type
            w = 2 if (mtype is _M_BIG or mtype is _M_BIG_FARMER) else 1
            six = <int>side_ix[side]
            if terrain is _T_CITY:
                nid = ws.city_tab[(r * W + c) * 9 + six]
                if nid >= 0:
                    root = ws.city_lab[nid]
                    e = city_own.get(root)
                    if e is None:
                        e = [0, 0]; city_own[root] = e
                    e[0 if is_self else 1] += w
            elif terrain is _T_ROAD:
                nid = ws.road_tab[(r * W + c) * 9 + six]
                if nid >= 0:
                    root = ws.road_lab[nid]
                    e = road_own.get(root)
                    if e is None:
                        e = [0, 0]; road_own[root] = e
                    e[0 if is_self else 1] += w
            elif mtype is _M_FARMER or mtype is _M_BIG_FARMER:
                nid = ws.pos0_tab[(r * W + c) * 9 + six]
                if nid >= 0:
                    root = ws.farm_lab[nid]
                    e = farm_own.get(root)
                    if e is None:
                        e = [0, 0]; farm_own[root] = e
                    e[0 if is_self else 1] += w

    # ---- fill city rows ---------------------------------------------------- #
    cdef int rowi = 0
    cdef int open_n, croot, c_open_n
    cdef double pp
    cdef object pobj
    for i in range(n_city_c):
        root = <int>city_roots[i]
        X[rowi, _C_IS_CITY] = 1.0
        X[rowi, _C_N_TILES] = <float>ws.city_total[root]
        X[rowi, _C_N_SHIELDS] = <float>ws.city_shieldn[root]
        X[rowi, _C_IS_CATHEDRAL] = 1.0 if ws.city_cath[root] else 0.0
        X[rowi, _C_FINISHED] = 1.0 if ws.city_fin[root] else 0.0
        open_n = ws.city_open_n[root]
        X[rowi, _C_OPEN_N] = <float>open_n
        X[rowi, _C_CLOSURE_DELTA] = <float>ws.city_delta[root]
        e = city_own.get(root)
        if e is not None:
            X[rowi, _C_SELF_MEEPLE_W] = <float><int>e[0]
            X[rowi, _C_OPP_MEEPLE_W] = <float><int>e[1]
        if (not ws.city_fin[root]) and open_n > 0:
            pobj = closure_p.get(open_n)
            if pobj is not None:
                X[rowi, _C_SELF_CITY_CLOSE_P] = <float><double>pobj
        X[rowi, _C_BIAS] = 1.0
        rowi += 1

    # ---- fill road rows ---------------------------------------------------- #
    for i in range(n_road_c):
        root = <int>road_roots[i]
        X[rowi, _C_IS_ROAD] = 1.0
        X[rowi, _C_N_TILES] = <float>ws.road_total[root]
        X[rowi, _C_FINISHED] = 1.0 if ws.road_fin[root] else 0.0
        e = road_own.get(root)
        if e is not None:
            X[rowi, _C_SELF_MEEPLE_W] = <float><int>e[0]
            X[rowi, _C_OPP_MEEPLE_W] = <float><int>e[1]
        X[rowi, _C_BIAS] = 1.0
        rowi += 1

    # ---- fill farm rows ---------------------------------------------------- #
    for i in range(n_farm_c):
        root = <int>farm_roots[i]
        X[rowi, _C_IS_FARM] = 1.0
        X[rowi, _C_FARM_FIN_CITIES] = <float>ws.farm_fincities[root]
        # potential3 = 3 * #distinct adjacent city roots (farm_adj_lo:hi, deduped).
        X[rowi, _C_FARM_POTENTIAL3] = <float>(3 * (ws.farm_adj_hi[root] - ws.farm_adj_lo[root]))
        # growth_p_sum = sum over INCOMPLETE adjacent cities of closure_p[open_n].
        pp = 0.0
        for t in range(ws.farm_adj_lo[root], ws.farm_adj_hi[root]):
            croot = ws.farm_adj[t]
            if ws.city_fin[croot]:
                continue
            c_open_n = ws.city_open_n[croot]
            if c_open_n <= 0:
                continue
            pobj = closure_p.get(c_open_n)
            if pobj is not None:
                pp += <double>pobj
        X[rowi, _C_SELF_GROWTH_P_SUM] = <float>pp
        e = farm_own.get(root)
        if e is not None:
            X[rowi, _C_SELF_MEEPLE_W] = <float><int>e[0]
            X[rowi, _C_OPP_MEEPLE_W] = <float><int>e[1]
        X[rowi, _C_BIAS] = 1.0
        rowi += 1

    # ---- meeple-economy pseudo-row (last) ---------------------------------- #
    meeples = state.meeples
    X[rowi, _C_IS_ECON] = 1.0
    X[rowi, _C_ECON_SELF_FREE] = <float><int>meeples[root_player]
    X[rowi, _C_ECON_OPP_FREE] = <float><int>meeples[opp]
    X[rowi, _C_ECON_K_REMAINING] = <float>_k_remaining_c(state)
    X[rowi, _C_BIAS] = 1.0

    return out


def decompose_export(state):
    """Diagnostic: box the C decomposition into Python dicts comparable 1:1
    with flat_leaf.decompose's Decomp (same root ids — enumeration and
    union order are mirrored exactly). NOT a hot path."""
    cdef _WS ws = _ws
    _decompose_c(state, ws)
    cdef int W = ws.W, H = ws.H
    cdef int nid, rc, ix, root
    ix_side = _IX_SIDE

    city_side_root = {}
    for nid in range(ws.n_city):
        city_side_root[(ws.city_nr[nid], ws.city_nc[nid], ix_side[ws.city_nix[nid]])] = ws.city_lab[nid]
    roots = sorted(set(city_side_root.values()))
    city_root_finished = {r: bool(ws.city_fin[r]) for r in roots}
    city_root_open_n = {r: ws.city_open_n[r] for r in roots}
    city_root_delta = {r: ws.city_delta[r] for r in roots}

    road_side_root = {}
    for nid in range(ws.n_road):
        road_side_root[(ws.road_nr[nid], ws.road_nc[nid], ix_side[ws.road_nix[nid]])] = ws.road_lab[nid]
    rroots = sorted(set(road_side_root.values()))
    road_root_finished = {r: bool(ws.road_fin[r]) for r in rroots}

    farm_pos0_root = {}
    farm_anypos_root = {}
    for rc in range(ws.ncells):
        for ix in range(9):
            nid = ws.pos0_tab[rc * 9 + ix]
            if nid >= 0:
                farm_pos0_root[(rc // W, rc % W, ix_side[ix])] = ws.farm_lab[nid]
            nid = ws.anypos_tab[rc * 9 + ix]
            if nid >= 0:
                farm_anypos_root[(rc // W, rc % W, ix_side[ix])] = ws.farm_lab[nid]
    froots = sorted({ws.farm_lab[n] for n in range(ws.n_farm)})
    farm_root_adj_city_roots = {
        r: frozenset(ws.farm_adj[t] for t in range(ws.farm_adj_lo[r], ws.farm_adj_hi[r]))
        for r in froots
    }
    farm_root_finished_cities = {r: ws.farm_fincities[r] for r in froots}

    return {
        "city_side_root": city_side_root,
        "city_root_finished": city_root_finished,
        "city_root_open_n": city_root_open_n,
        "city_root_delta": city_root_delta,
        "road_side_root": road_side_root,
        "road_root_finished": road_root_finished,
        "farm_pos0_root": farm_pos0_root,
        "farm_anypos_root": farm_anypos_root,
        "farm_root_adj_city_roots": farm_root_adj_city_roots,
        "farm_root_finished_cities": farm_root_finished_cities,
    }
