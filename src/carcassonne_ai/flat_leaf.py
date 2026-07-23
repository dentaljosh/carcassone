"""De-objectified flat leaf (DEOBJECTIFY_LEAF_PLAN_2026-06-09).

Computes the v2.7 leaf value DIRECTLY from a flat int-ish decomposition of the
board, with **NO `copy.deepcopy`, NO engine `Farm`/`City`/`Road` objects, NO
`count_final_scores`, NO enum-keyed object graphs**. The compact-leaf attempt
(`compact_leaf.py`) kept all three and was a 10% regression; Stage 0 of the plan
showed `count_final_scores` (the flood-fill scoring) is ~90% of the leaf — that
is what this module replaces.

Pipeline:
    decompose(state)            # one board pass -> int union-find components
      -> Decomp                 #   per-component facts + node->root maps
    flat_base_score(state, p)   # Stage 2: scores[p]-scores[opp], no deepcopy
    flat_virtual_score_v2(...)  # Stage 3 (TODO): + closure-anticipation bonus

Correctness is MANDATORY and gated bit-exactly by
`scripts/reconcile_flat_leaf.py` against the engine ground truth
(`FarmUtil.find_farm`, `CityUtil._compute_city`, `RoadUtil.find_road`,
`PointsCollector.count_final_scores`). The base score is pure integer, so the
Stage-2 gate is exact integer equality.

The connected-component kernel (`_label_components`) and the scoring arithmetic
are deliberately pure-int over plain lists/dicts so Stage 4 can numba/Cython them.
Default OFF (`USE_FLAT_LEAF`); wired into the production leaf only after the gate.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from wingedsheep.carcassonne.objects.farmer_side import FarmerSide
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.utils.side_modification_util import SideModificationUtil

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState

# Flat-leaf toggle (2026-06-09, leaf-rewrite branch). When True, virtual_score_v2
# redirects to the de-objectified flat path (bit-exact under canonical sum, ~2.26x
# faster per leaf). Default OFF — bit-exact-validated by
# scripts/reconcile_flat_leaf.py (incl. the make_v25_value_wrapper firing check).
# Read CARCASSONNE_USE_FLAT_LEAF at import so SPAWNED self-play/eval workers (which
# don't inherit a runtime flip of this module attr) pick it up — this is also how a
# deploy launcher flips it. A runtime `flat_leaf.USE_FLAT_LEAF = ...` still works in
# the main process (the gate uses that). Adopting it == adopting CANONICAL leaf
# semantics (the flat path is fsum-canonical), a deliberate, gated decision.
USE_FLAT_LEAF = os.environ.get("CARCASSONNE_USE_FLAT_LEAF") == "1"

# Cython flat-leaf toggle (2026-06-12, dev/validation only — DEFAULT OFF and not
# yet folded into production). When set, flat_virtual_score_v2 redirects to the
# compiled `flat_leaf_cy` port (bit-exact gate: scripts/reconcile_cy_leaf.py;
# build: `python setup_flat_leaf_cy.py build_ext --inplace`). With the flag
# unset, the compiled module is NEVER imported — zero behavioral change. Same
# read-at-import pattern as USE_FLAT_LEAF so spawned workers inherit the env
# flip; a runtime flip needs `flat_leaf.USE_CY_LEAF = True` (lazy import fires
# on the next leaf call).
USE_CY_LEAF = os.environ.get("CARCASSONNE_USE_CY_LEAF", "1") != "0"  # FOLDED 2026-06-17: default ON (all 3 boxes built+reconciled bit-exact); set =0 to force the Python path
_CY_FLAT_V2 = None  # lazily bound flat_leaf_cy.flat_virtual_score_v2_cy
_CY_FLAT_V2_FLOAT = None  # lazily bound flat_leaf_cy.flat_virtual_score_v2_cy_float (pre-round)
_CY_SUPPORTS_CURVE = False  # set from flat_leaf_cy.SUPPORTS_V29_CURVE at bind time
_CY_SUPPORTS_BAG_CLOSE = False  # set from flat_leaf_cy.SUPPORTS_V210_BAG_CLOSE at bind time
_CY_SUPPORTS_C7 = False  # set from flat_leaf_cy.SUPPORTS_V29_C7_TERMS at bind time (Term R + Term F)
_CY_SUPPORTS_SOFT_CAP = False  # set from flat_leaf_cy.SUPPORTS_F6_SOFT_CAP at bind time (F6 soft cap)

# v2.10 bag-aware closure gate (2026-07-04, docs/V210_LEAF_SPEC_2026-07-04.md Track B;
# BACKLOG 2026-05-16 item 1). When ON, the closure-anticipation bonus consults the
# REMAINING-TILE MULTISET (state.deck, + the in-hand next_tile in the TILES phase):
# a feature the bag can no longer complete gets P(closure)=0 EXACTLY (stuck meeple) —
# cities via a per-open-cell city-edge-supply feasibility check (Hall's condition on
# the nested >=k-city-edge tile classes), cloisters via remaining-tile count. Default
# OFF == bit-identical production v2.9 flat leaf (gate-tested). Deliberately a MODULE
# flag, not a LeafConfig field: the frozen v2.9 substrate config-hash guards
# (governance/LEAF_SUBSTRATES.yaml, snapshot.frozen_v29_cfg, step2 provenance) pin the
# LeafConfig dataclass schema — adding a field would flip every asdict-hash. Same
# read-at-import pattern as USE_FLAT_LEAF so spawned workers inherit the env flip;
# explicit per-call override via flat_virtual_score_v2(..., bag_close=...) (the
# solver-screen A/B path — no env/global mutation).
V210_BAG_CLOSE = os.environ.get("CARCASSONNE_V210_BAG_CLOSE") == "1"

# --- geometry (gate-validated against the engine) ----------------------------
# Stage 4a: the decomposition hot path int-encodes sides. Enum dict keys cost a
# Python-level Enum.__hash__ (the dominant cost once the leaf is de-objectified —
# ~0.95s of decompose's 1.84s in the Stage-3 profile); int-tuple keys hash at C
# speed. _SIDE_IX / _FS_IX map the engine enums -> small ints; _IX_SIDE maps back
# for the (enum-keyed, gate-facing) public Decomp fields, which are touched only
# O(nodes) at build + ~O(meeples) at read, so they stay enum-keyed for clarity.
_SIDE_IX: dict = {s: i for i, s in enumerate(Side)}  # TOP0 RIGHT1 BOTTOM2 LEFT3 CENTER4 TL5 TR6 BL7 BR8
_IX_SIDE: list = list(Side)                          # ix -> Side
_FS_IX: dict = {fs: i for i, fs in enumerate(FarmerSide)}  # TLL0 TLT1 TRT2 TRR3 BLL4 BLB5 BRB6 BRR7

# Cross a tile border on a CITY or ROAD edge, by cardinal side ix:
# (d_row, d_col, neighbour_side_ix). Mirrors CityUtil/RoadUtil.opposite_edge.
_OPP: dict = {
    _SIDE_IX[Side.TOP]: (-1, 0, _SIDE_IX[Side.BOTTOM]),
    _SIDE_IX[Side.RIGHT]: (0, 1, _SIDE_IX[Side.LEFT]),
    _SIDE_IX[Side.BOTTOM]: (1, 0, _SIDE_IX[Side.TOP]),
    _SIDE_IX[Side.LEFT]: (0, -1, _SIDE_IX[Side.RIGHT]),
}

# Farmer half-side adjacency, by farmer-side ix: step (d_row, d_col) from its
# cardinal Side, and the neighbour half-side ix (opposite_farmer_side involution
# — taken straight from the engine to avoid transcription risk).
_FS_STEP: dict = {}
_FS_OPP: dict = {}
_card_step = {Side.TOP: (-1, 0), Side.RIGHT: (0, 1), Side.BOTTOM: (1, 0), Side.LEFT: (0, -1)}
for _fs in FarmerSide:
    _FS_STEP[_FS_IX[_fs]] = _card_step[_fs.get_side()]
    _FS_OPP[_FS_IX[_fs]] = _FS_IX[SideModificationUtil.opposite_farmer_side(_fs)]
del _fs, _card_step


# --- per-tile int-feature cache (Stage 4b) ----------------------------------
# Tiles are immutable and shared via canonical refs (engine base_tiles +
# Tile._turn_cache), so a game touches only ~80 distinct rotated Tile objects.
# Memoising the enum->int conversion per Tile hoists it out of the per-leaf hot
# path (the remaining post-4a cost). WeakKeyDictionary keyed by the Tile object:
# Tile has no __eq__/__hash__ override -> identity hash (fast, C-level) and entries
# auto-drop if a tile is ever GC'd (no id-reuse hazard). Returns, per tile:
#   city_groups_ix : tuple(tuple(side_ix))      -- intra-tile city groups
#   road_conns_ix  : tuple((a_ix|None, b_ix|None))  -- None == CENTER (dead end)
#   farms_tc_ix    : tuple(tuple(farmer_side_ix)) aligned with tile.farms order
_TILE_FEAT: "WeakKeyDictionary" = WeakKeyDictionary()


def _tile_features(tile):
    feat = _TILE_FEAT.get(tile)
    if feat is None:
        city_groups_ix = tuple(tuple(_SIDE_IX[s] for s in g) for g in tile.city)
        road_conns_ix = tuple(
            (None if conn.a == Side.CENTER else _SIDE_IX[conn.a],
             None if conn.b == Side.CENTER else _SIDE_IX[conn.b])
            for conn in tile.road
        )
        farms_tc_ix = tuple(
            tuple(_FS_IX[fs] for fs in fc.tile_connections) for fc in tile.farms
        )
        feat = (city_groups_ix, road_conns_ix, farms_tc_ix)
        _TILE_FEAT[tile] = feat
    return feat


def _label_components(n: int, edges_u: list, edges_v: list) -> list:
    """Union-find connected components (path-halving). Pure-int over parallel
    arrays — the numba/Cython target. Returns node id -> canonical root id."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(edges_u)):
        a = find(edges_u[i])
        b = find(edges_v[i])
        if a != b:
            parent[a] = b
    return [find(x) for x in range(n)]


@dataclass
class Decomp:
    """Whole-board structural decomposition. Pure data (ints, tuples, sets) —
    no engine objects. Built by `decompose`; consumed by the flat scorers and
    by the equivalence gate (the *_positions / *_keys fields are for the gate's
    partition checks)."""
    # CITY
    city_side_root: dict          # (r, c, Side) -> component root id
    city_root_positions: dict     # root -> frozenset((r, c, Side))
    city_root_coords: dict        # root -> set((r, c))  (distinct tiles)
    city_root_finished: dict      # root -> bool
    city_root_open_n: dict        # root -> #distinct empty adjacent cells (closure proximity)
    city_root_delta: dict         # root -> closure score delta (== count_city_points if it closed)
    # ROAD
    road_side_root: dict          # (r, c, Side) -> root
    road_root_positions: dict     # root -> frozenset((r, c, Side))
    road_root_coords: dict        # root -> set((r, c))
    road_root_finished: dict      # root -> bool
    road_root_open_n: dict        # root -> #distinct empty adjacent cells (C7 Term R; == _open_road_positions)
    # FARM
    farm_pos0_root: dict          # (r, c, farmer_positions[0]) -> root  (base meeple match: find_meeples)
    farm_anypos_root: dict        # (r, c, any farmer_position) -> root  (bonus match: find_farm_by_coordinate)
    farm_root_keys: dict          # root -> frozenset((r, c, id(FarmerConnection)))
    farm_root_adj_city_roots: dict   # root -> frozenset(adjacent city roots)
    farm_root_finished_cities: dict  # root -> #distinct finished adjacent cities


def decompose(state: "CarcassonneGameState") -> Decomp:
    """One board pass -> int union-find components for cities, roads, farms, plus
    the per-component facts the flat scorer needs. No engine Farm/City objects."""
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0

    # ---- enumerate nodes + intra-tile edges -------------------------------- #
    # CITY: one node per (tile, city side); sides of one tile.city group are
    # connected (== CityUtil.cities_for_position).
    city_node_id: dict = {}
    city_nodes: list = []         # nid -> (r, c, side_ix)
    city_eu: list = []
    city_ev: list = []
    # ROAD: one node per non-CENTER road side; the two non-CENTER ends of a
    # Connection are connected (== RoadUtil.outgoing_roads_for_position).
    road_node_id: dict = {}
    road_nodes: list = []         # nid -> (r, c, side_ix)
    road_eu: list = []
    road_ev: list = []
    # FARM: one node per FarmerConnection; tile_connections give adjacency.
    farm_node_rc: list = []       # nid -> (r, c)
    farm_node_fc: list = []       # nid -> FarmerConnection
    farm_node_tc_ix: list = []    # nid -> tuple(farmer_side_ix) (cached tile_connections)
    farm_side_to_node: dict = {}  # (r, c, farmer_side_ix) -> nid

    def _city_nid(key):
        nid = city_node_id.get(key)
        if nid is None:
            nid = len(city_nodes)
            city_node_id[key] = nid
            city_nodes.append(key)
        return nid

    def _road_nid(key):
        nid = road_node_id.get(key)
        if nid is None:
            nid = len(road_nodes)
            road_node_id[key] = nid
            road_nodes.append(key)
        return nid

    for r in range(H):
        brow = board[r]
        for c in range(W):
            tile = brow[c]
            if tile is None:
                continue
            city_groups_ix, road_conns_ix, farms_tc_ix = _tile_features(tile)
            # cities  (nodes keyed by int side ix: (r, c, side_ix))
            for group_ix in city_groups_ix:
                gids = [_city_nid((r, c, six)) for six in group_ix]
                first = gids[0]
                for other in gids[1:]:
                    city_eu.append(first)
                    city_ev.append(other)
            # roads  (non-CENTER ends only; both-non-CENTER ends of a Connection union)
            for a_ix, b_ix in road_conns_ix:
                ida = _road_nid((r, c, a_ix)) if a_ix is not None else None
                idb = _road_nid((r, c, b_ix)) if b_ix is not None else None
                if a_ix is not None and b_ix is not None:
                    road_eu.append(ida)
                    road_ev.append(idb)
            # farms  (side_to_node keyed by int farmer-side ix)
            farms = tile.farms
            for k in range(len(farms)):
                nid = len(farm_node_rc)
                farm_node_rc.append((r, c))
                farm_node_fc.append(farms[k])
                tc_ix = farms_tc_ix[k]
                farm_node_tc_ix.append(tc_ix)
                for fs_ix in tc_ix:
                    farm_side_to_node[(r, c, fs_ix)] = nid

    # ---- cross-tile edges + open detection --------------------------------- #
    city_open = [False] * len(city_nodes)
    for nid in range(len(city_nodes)):
        r, c, ix = city_nodes[nid]
        dr, dc, o_ix = _OPP[ix]
        onid = city_node_id.get((r + dr, c + dc, o_ix))
        if onid is not None:
            city_eu.append(nid)
            city_ev.append(onid)
        else:
            city_open[nid] = True

    road_open = [False] * len(road_nodes)
    for nid in range(len(road_nodes)):
        r, c, ix = road_nodes[nid]
        dr, dc, o_ix = _OPP[ix]
        onid = road_node_id.get((r + dr, c + dc, o_ix))
        if onid is not None:
            road_eu.append(nid)
            road_ev.append(onid)
        else:
            road_open[nid] = True

    farm_eu: list = []
    farm_ev: list = []
    for nid in range(len(farm_node_rc)):
        r, c = farm_node_rc[nid]
        for fs_ix in farm_node_tc_ix[nid]:
            step = _FS_STEP[fs_ix]
            neighbor = farm_side_to_node.get((r + step[0], c + step[1], _FS_OPP[fs_ix]))
            if neighbor is not None:
                farm_eu.append(nid)
                farm_ev.append(neighbor)

    # ---- label components -------------------------------------------------- #
    city_labels = _label_components(len(city_nodes), city_eu, city_ev)
    road_labels = _label_components(len(road_nodes), road_eu, road_ev)
    farm_labels = _label_components(len(farm_node_rc), farm_eu, farm_ev)

    # ---- city facts -------------------------------------------------------- #
    city_side_root: dict = {}
    city_root_positions: dict = {}
    city_root_coords: dict = {}
    city_root_open: set = set()
    city_root_emptyadj: dict = {}   # root -> set of distinct empty neighbour cells
    for nid in range(len(city_nodes)):
        r, c, ix = city_nodes[nid]
        root = city_labels[nid]
        side = _IX_SIDE[ix]  # back to enum for the public, gate-facing dicts
        city_side_root[(r, c, side)] = root
        city_root_positions.setdefault(root, set()).add((r, c, side))
        city_root_coords.setdefault(root, set()).add((r, c))
        if city_open[nid]:
            city_root_open.add(root)
        # closure-proximity: count distinct empty cells across the outward
        # neighbours of the component's city edges (== _open_city_positions).
        dr, dc, _o = _OPP[ix]
        nr, nc = r + dr, c + dc
        if 0 <= nr < H and 0 <= nc < W and board[nr][nc] is None:
            city_root_emptyadj.setdefault(root, set()).add((nr, nc))
    city_root_finished = {root: root not in city_root_open for root in city_root_positions}
    city_root_open_n = {root: len(city_root_emptyadj.get(root, ())) for root in city_root_positions}
    # closure delta == count_city_points if the city closed (full credit): for an
    # incomplete city, T tiles + S shield-tiles (+ cathedral 3x). Computed for
    # every component; the closure bonus only consults it for unfinished ones.
    city_root_delta: dict = {}
    for root, coords in city_root_coords.items():
        shields = 0
        cathedral = False
        total = 0
        for (r, c) in coords:
            tile = board[r][c]
            if tile.inn:
                cathedral = True
            if tile.shield:
                shields += 1
            total += 1
        city_root_delta[root] = (3 * total + 3 * shields) if cathedral else (total + shields)
    city_root_positions = {root: frozenset(s) for root, s in city_root_positions.items()}

    # ---- road facts -------------------------------------------------------- #
    road_side_root: dict = {}
    road_root_positions: dict = {}
    road_root_coords: dict = {}
    road_root_open: set = set()
    road_root_emptyadj: dict = {}   # root -> set of distinct empty neighbour cells (C7 Term R)
    for nid in range(len(road_nodes)):
        r, c, ix = road_nodes[nid]
        root = road_labels[nid]
        side = _IX_SIDE[ix]  # back to enum for the public, gate-facing dicts
        road_side_root[(r, c, side)] = root
        road_root_positions.setdefault(root, set()).add((r, c, side))
        road_root_coords.setdefault(root, set()).add((r, c))
        if road_open[nid]:
            road_root_open.add(root)
        # closure-proximity: distinct empty cells across the outward neighbours of
        # the component's road edges (== _open_road_positions; same stamp/dedup
        # pattern as the city one). Empty (None) neighbours only -> can't collide
        # with an occupied tile cell of the same component.
        dr, dc, _o = _OPP[ix]
        nr, nc = r + dr, c + dc
        if 0 <= nr < H and 0 <= nc < W and board[nr][nc] is None:
            road_root_emptyadj.setdefault(root, set()).add((nr, nc))
    road_root_finished = {root: root not in road_root_open for root in road_root_positions}
    road_root_open_n = {root: len(road_root_emptyadj.get(root, ())) for root in road_root_positions}
    road_root_positions = {root: frozenset(s) for root, s in road_root_positions.items()}

    # ---- farm facts -------------------------------------------------------- #
    farm_pos0_root: dict = {}      # base: find_meeples matches farmer_positions[0]
    farm_anypos_root: dict = {}    # bonus: find_farm_by_coordinate matches any farmer_position
    farm_root_keys: dict = {}
    farm_root_members: dict = {}
    for nid in range(len(farm_node_rc)):
        root = farm_labels[nid]
        r, c = farm_node_rc[nid]
        fc = farm_node_fc[nid]
        farm_root_keys.setdefault(root, set()).add((r, c, id(fc)))
        farm_root_members.setdefault(root, []).append(nid)
        fp = fc.farmer_positions
        if fp:
            farm_pos0_root[(r, c, fp[0])] = root
            for pos in fp:
                farm_anypos_root[(r, c, pos)] = root
    farm_root_keys = {root: frozenset(s) for root, s in farm_root_keys.items()}

    # Distinct city components adjacent to the whole field (count_farm_points and
    # the farm-growth bonus both dedup by city component == city root). Base needs
    # the FINISHED count; the bonus needs the full set (it scores the INCOMPLETE
    # ones). find_cities is called per connection over fc.city_sides.
    farm_root_adj_city_roots: dict = {}
    farm_root_finished_cities: dict = {}
    for root, member_ids in farm_root_members.items():
        adj_city_roots: set = set()
        for nid in member_ids:
            r, c = farm_node_rc[nid]
            for cs in farm_node_fc[nid].city_sides:
                croot = city_side_root.get((r, c, cs))
                if croot is not None:
                    adj_city_roots.add(croot)
        farm_root_adj_city_roots[root] = frozenset(adj_city_roots)
        farm_root_finished_cities[root] = sum(
            1 for croot in adj_city_roots if city_root_finished.get(croot, False)
        )

    return Decomp(
        city_side_root=city_side_root,
        city_root_positions=city_root_positions,
        city_root_coords=city_root_coords,
        city_root_finished=city_root_finished,
        city_root_open_n=city_root_open_n,
        city_root_delta=city_root_delta,
        road_side_root=road_side_root,
        road_root_positions=road_root_positions,
        road_root_coords=road_root_coords,
        road_root_finished=road_root_finished,
        road_root_open_n=road_root_open_n,
        farm_pos0_root=farm_pos0_root,
        farm_anypos_root=farm_anypos_root,
        farm_root_keys=farm_root_keys,
        farm_root_adj_city_roots=farm_root_adj_city_roots,
        farm_root_finished_cities=farm_root_finished_cities,
    )


# --- scoring (Stage 2) ------------------------------------------------------- #
def _meeple_weight(meeple_type) -> int:
    """Big meeples count 2 (mirrors get_meeple_counts_per_player). Our locked
    scope has no big meeples, but reproduce the engine exactly."""
    if meeple_type == MeepleType.BIG or meeple_type == MeepleType.BIG_FARMER:
        return 2
    return 1


def _winners(counts) -> list:
    """Player indices tied for max meeple count; [] if none (mirrors
    PointsCollector.get_winning_players)."""
    m = max(counts)
    if m == 0:
        return []
    return [i for i, v in enumerate(counts) if v == m]


def _city_points(coords, finished: bool, board) -> int:
    """== PointsCollector.count_city_points over the component's distinct tiles."""
    shields = 0
    cathedral = False
    total = 0
    for (r, c) in coords:
        tile = board[r][c]
        if tile.inn:  # engine reuses .inn as the cathedral flag on city tiles
            cathedral = True
        if tile.shield:
            shields += 1
        total += 1
    if not finished and cathedral:
        return 0
    if cathedral:  # cathedral + finished
        return 6 * shields + 3 * (total - shields)
    if finished:
        return 4 * shields + 2 * (total - shields)
    return 2 * shields + 1 * (total - shields)


def _road_points(coords, finished: bool, board) -> int:
    """== PointsCollector.count_road_points over the component's distinct tiles."""
    inn = False
    total = 0
    for (r, c) in coords:
        if board[r][c].inn:
            inn = True
        total += 1
    if not finished and inn:
        return 0
    return (2 if inn else 1) * total


def _cloister_points(r: int, c: int, board, H: int, W: int) -> int:
    """== PointsCollector.chapel_or_flowers_points: placed tiles in the 3x3
    (including the centre cloister tile itself)."""
    pts = 0
    for rr in range(r - 1, r + 2):
        if rr < 0 or rr >= H:
            continue
        for cc in range(c - 1, c + 2):
            if cc < 0 or cc >= W:
                continue
            if board[rr][cc] is not None:
                pts += 1
    return pts


def _final_scores(state: "CarcassonneGameState", decomp: Decomp) -> list:
    """The per-player points `count_final_scores` would ADD (cities + roads +
    farms + cloisters that carry a meeple). Pure int; no mutation, no deepcopy.

    Mirrors count_final_scores: it iterates placed MEEPLES, so an unmeepled
    feature scores nothing — equivalent to iterating components and awarding only
    when a component has >=1 meeple (winners non-empty)."""
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0
    nplayers = state.players

    city_counts: dict = {}   # root -> [per-player weighted meeples]
    road_counts: dict = {}
    farm_counts: dict = {}
    cloister_awards: list = []  # (player, points)

    for player in range(nplayers):
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            tile = board[r][c]
            terrain = tile.get_type(side)
            w = _meeple_weight(mp.meeple_type)
            if terrain == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    cnt = city_counts.get(root)
                    if cnt is None:
                        cnt = [0] * nplayers
                        city_counts[root] = cnt
                    cnt[player] += w
            elif terrain == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is not None:
                    cnt = road_counts.get(root)
                    if cnt is None:
                        cnt = [0] * nplayers
                        road_counts[root] = cnt
                    cnt[player] += w
            elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
                cloister_awards.append((player, _cloister_points(r, c, board, H, W)))
            elif mp.meeple_type == MeepleType.FARMER or mp.meeple_type == MeepleType.BIG_FARMER:
                root = decomp.farm_pos0_root.get((r, c, side))
                if root is not None:
                    cnt = farm_counts.get(root)
                    if cnt is None:
                        cnt = [0] * nplayers
                        farm_counts[root] = cnt
                    cnt[player] += w

    final = [0] * nplayers
    for root, counts in city_counts.items():
        winners = _winners(counts)
        if not winners:
            continue
        pts = _city_points(decomp.city_root_coords[root], decomp.city_root_finished[root], board)
        for wpl in winners:
            final[wpl] += pts
    for root, counts in road_counts.items():
        winners = _winners(counts)
        if not winners:
            continue
        pts = _road_points(decomp.road_root_coords[root], decomp.road_root_finished[root], board)
        for wpl in winners:
            final[wpl] += pts
    for root, counts in farm_counts.items():
        winners = _winners(counts)
        if not winners:
            continue
        pts = 3 * decomp.farm_root_finished_cities[root]
        for wpl in winners:
            final[wpl] += pts
    for (player, pts) in cloister_awards:
        final[player] += pts
    return final


def flat_base_score(state: "CarcassonneGameState", player: int, decomp: Decomp | None = None) -> int:
    """== virtual_score(state, player): the end-of-game score differential
    `scores[player] - scores[opp]`, computed flat (no deepcopy, no
    count_final_scores). Pure integer.

    `count_final_scores` ADDS to the running `state.scores`, so the differential
    is the running-score diff plus the diff of the points it would add."""
    if state.players != 2:
        raise ValueError(f"flat_base_score is 2-player only; got {state.players}")
    if decomp is None:
        decomp = decompose(state)
    final = _final_scores(state, decomp)
    opp = 1 - player
    running = int(state.scores[player]) - int(state.scores[opp])
    return running + (final[player] - final[opp])


# --- v2.10 bag-aware closure gate helpers ------------------------------------ #
def _bag_stats(state) -> tuple:
    """Remaining-tile-multiset stats for the bag-aware closure gate:
    ``(n_tiles, ge1, ge2, ge3, ge4)`` where ge_k = #remaining tiles with >= k
    cardinal CITY edges (rotation is free, so edge COUNT is the placeability
    proxy — deliberately permissive, same spirit as the old _deck_city_supply).

    Remaining = ``state.deck`` plus the in-hand ``next_tile`` iff the state is in
    the TILES phase (the tile is drawn but not yet placed — it can still close a
    feature). In the MEEPLES phase ``next_tile`` is a stale ref to the
    just-placed tile (StateUpdater only pops the next draw at turn end), so it
    must NOT be counted."""
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    n = 0
    ge1 = ge2 = ge3 = ge4 = 0
    deck = state.deck
    nt = state.next_tile
    extra = (nt,) if (nt is not None and state.phase == GamePhase.TILES) else ()
    for tile in (*deck, *extra):
        n += 1
        city_groups_ix = _tile_features(tile)[0]
        ne = 0
        for g in city_groups_ix:
            ne += len(g)
        if ne >= 1:
            ge1 += 1
            if ne >= 2:
                ge2 += 1
                if ne >= 3:
                    ge3 += 1
                    if ne >= 4:
                        ge4 += 1
    return (n, ge1, ge2, ge3, ge4)


def _city_faces_ge(decomp: Decomp, board, H: int, W: int, root) -> tuple:
    """Per-open-cell face requirements of one city component: how many of the
    component's open city edges point INTO each empty adjacent cell (a filling
    tile must present that many city edges). Returns ``(ge2, ge3, ge4)`` = the
    number of open cells needing >= 2/3/4 city faces (ge1 == the component's
    ``city_root_open_n``). Recomputed lazily (only when the bag gate is ON and
    the component is a candidate) so the OFF path does zero extra work."""
    faces: dict = {}
    for (r, c, side) in decomp.city_root_positions[root]:
        dr, dc, _o = _OPP[_SIDE_IX[side]]
        nr, nc = r + dr, c + dc
        if 0 <= nr < H and 0 <= nc < W and board[nr][nc] is None:
            key = nr * W + nc
            faces[key] = faces.get(key, 0) + 1
    ge2 = ge3 = ge4 = 0
    for v in faces.values():
        if v >= 2:
            ge2 += 1
            if v >= 3:
                ge3 += 1
                if v >= 4:
                    ge4 += 1
    return (ge2, ge3, ge4)


def _bag_city_ok(open_n: int, faces_ge: tuple, bag: tuple) -> bool:
    """Can the bag still close this city? Each open cell with k faces needs a
    distinct tile with >= k city edges; the >=k tile classes are NESTED, so a
    perfect matching exists iff Hall's condition holds on each class:
    #cells needing >= k  <=  #tiles with >= k city edges, for k = 1..4."""
    return (open_n <= bag[1] and faces_ge[0] <= bag[2]
            and faces_ge[1] <= bag[3] and faces_ge[2] <= bag[4])


# --- closure-anticipation bonus (Stage 3) ----------------------------------- #
def _surrounding_count(state, r: int, c: int, H: int, W: int) -> int:
    """Placed tiles among the 8 cells around (r, c), excluding the centre
    (== virtual_score_v2._surrounding_count)."""
    n = 0
    board = state.board
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < H and 0 <= cc < W and board[rr][cc] is not None:
                n += 1
    return n


def flat_closure_bonus(state, player: int, decomp: Decomp, cfg, bag: tuple | None = None) -> float:
    """== virtual_score_v2._closure_anticipation_bonus(state, player, cfg), UNCAPPED.

    Mirrors the engine pass but works off the flat decomposition: it iterates the
    player's meeples, dedups features by component (== the engine's
    frozenset(positions) / frozenset(connections) keys, bijective with our roots),
    and accumulates the same multiset of contributions. Summed with math.fsum
    (order-independent / correctly-rounded) — i.e. the CANONICAL_BONUS_SUM
    semantics, which the flat leaf targets from the start so it is a well-defined
    function of the board (the naive set-iteration sum is hash-seed dependent).

    `bag` (v2.10 Track B): pass `_bag_stats(state)` to apply the bag-aware closure
    gate — a city/cloister the remaining-tile multiset can no longer complete
    contributes NOTHING (P=0 exactly, the stuck-meeple case). None == gate off ==
    bit-identical v2.9 behaviour.

    Only the v2.7 schedule path is implemented (closure_p lookup, no deck-aware
    gate/continuous ramp); a cfg requesting those raises rather than silently
    diverging."""
    if cfg.tile_counting_closure or cfg.closure_continuous_slack > 0.0:
        raise NotImplementedError(
            "flat_closure_bonus implements only the v2.7 schedule path "
            "(no tile_counting_closure / closure_continuous_slack)"
        )
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0
    closure_p = cfg.closure_p
    _faces_memo: dict = {}  # city root -> (ge2, ge3, ge4), bag-gate only

    def _bag_ok(croot) -> bool:
        fg = _faces_memo.get(croot)
        if fg is None:
            fg = _faces_memo[croot] = _city_faces_ge(decomp, board, H, W, croot)
        return _bag_city_ok(decomp.city_root_open_n[croot], fg, bag)

    # Partition the player's meeples into the three feature kinds (same
    # discrimination as count_final_scores / the engine bonus).
    knight_roots: set = set()       # city components with the player's knight
    cloister_tiles: list = []       # (r, c) cloister tiles with the player's meeple
    farm_roots: set = set()         # farm components with the player's farmer
    for mp in state.placed_meeples[player]:
        cws = mp.coordinate_with_side
        r = cws.coordinate.row
        c = cws.coordinate.column
        side = cws.side
        terrain = board[r][c].get_type(side)
        if terrain == TerrainType.CITY:
            root = decomp.city_side_root.get((r, c, side))
            if root is not None:
                knight_roots.add(root)
        elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
            cloister_tiles.append((r, c))
        elif mp.meeple_type == MeepleType.FARMER or mp.meeple_type == MeepleType.BIG_FARMER:
            root = decomp.farm_anypos_root.get((r, c, side))
            if root is not None:
                farm_roots.add(root)

    contribs: list = []

    # City closures (knight on an incomplete city near closing).
    for root in knight_roots:
        if decomp.city_root_finished[root]:
            continue
        open_n = decomp.city_root_open_n[root]
        if open_n <= 0:  # D16: unclosable board-edge city
            continue
        p = closure_p.get(open_n, 0.0)
        if p > 0 and (bag is None or _bag_ok(root)):
            contribs.append(p * decomp.city_root_delta[root])

    # Cloister completion.
    for (r, c) in cloister_tiles:
        n_surround = _surrounding_count(state, r, c, H, W)
        needed = 8 - n_surround
        if needed > 0:
            p = closure_p.get(needed, 0.0)
            # bag gate: any tile can neighbour a cloister — feasible iff enough
            # tiles remain to fill the needed cells.
            if p > 0 and (bag is None or needed <= bag[0]):
                contribs.append(p * needed)

    # Farm growth: incomplete cities adjacent to the player's fields, deduped
    # across all the player's farms by city component (== counted_growth_cities).
    growth_roots: set = set()
    for froot in farm_roots:
        growth_roots |= decomp.farm_root_adj_city_roots[froot]
    for croot in growth_roots:
        if decomp.city_root_finished[croot]:
            continue
        open_n = decomp.city_root_open_n[croot]
        if open_n <= 0:
            continue
        p = closure_p.get(open_n, 0.0)
        if p > 0 and (bag is None or _bag_ok(croot)):
            contribs.append(p * 3)

    return math.fsum(contribs)


def _capped(bonus: float, cap: float) -> float:
    """== virtual_score_v2._capped."""
    return cap if bonus > cap else bonus


def _soft_capped(bonus: float, cap: float, slope: float) -> float:
    """== virtual_score_v2._soft_capped. F6 soft cap (CL-063): linear credit `slope`
    to the closure bonus ABOVE `cap` instead of a hard clamp. slope==0.0 delegates to
    the UNCHANGED hard `_capped` (BIT-EXACT default path); slope==1.0 == identity."""
    if slope == 0.0:
        return _capped(bonus, cap)
    return cap + slope * (bonus - cap) if bonus > cap else bonus


def _flat_curve_lookup(curve, n: int) -> float:
    """== leaf_v29._curve_lookup. Value of holding `n` free meeples, clamped into
    [0, len-1] (free-meeple count is 0..7 in base+farmers)."""
    if n < 0:
        n = 0
    elif n >= len(curve):
        n = len(curve) - 1
    return float(curve[n])


# --- C7 wave-2 leaf terms (opt-in; default-OFF == bit-identical champion) ------ #
# Pre-registered module constants (NOT LeafConfig fields — fewer hash-churn keys);
# a β/ramp sweep is a possible wave-3 only if Term F fires.
_FLIP_BETA = 0.5
_FLIP_RAMP = 2.0


def _flat_dcurve(curve, n: int) -> float:
    """Marginal curve value of recovering ONE meeple at current free count `n`:
    ``curve[min(n+1, L-1)] - curve[min(max(n,0), L-1)]`` (0 at n == L-1). == the
    object-path _dcurve and the cy _dcurve_c."""
    L = len(curve)
    hi = n + 1
    if hi > L - 1:
        hi = L - 1
    lo = n
    if lo < 0:
        lo = 0
    if lo > L - 1:
        lo = L - 1
    return float(curve[hi]) - float(curve[lo])


def flat_return_term(state, player: int, decomp: Decomp, cfg) -> float:
    """C7 Term R — meeple-return liquidity, UNCAPPED differential ``ret(player) -
    ret(opp)`` (§1 of C7_LEAF_TERMS_DESIGN.md). PER-MEEPLE (no feature dedup): every
    committed, returnable meeple credits P(feature closes) from the closure schedule,
    the whole ΣP scaled by ``dcurve(free-meeple-count)`` (marginal value of one more
    free meeple). Farmers never return (skipped). Requires a curve."""
    curve = cfg.v29_meeple_curve
    if curve is None:
        raise ValueError(
            "v29_meeple_return_k requires v29_meeple_curve (Term R prices the "
            "marginal step of the liquidity curve)"
        )
    closure_p = cfg.closure_p
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0

    def _ret(p: int) -> float:
        plist: list = []
        for mp in state.placed_meeples[p]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            terrain = board[r][c].get_type(side)
            if terrain == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is None or decomp.city_root_finished[root]:
                    continue
                open_n = decomp.city_root_open_n[root]
                if open_n <= 0:
                    continue
                pr = closure_p.get(open_n, 0.0)
                if pr > 0:
                    plist.append(pr)
            elif terrain == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is None or decomp.road_root_finished[root]:
                    continue
                open_n = decomp.road_root_open_n[root]
                if open_n <= 0:
                    continue
                pr = closure_p.get(open_n, 0.0)
                if pr > 0:
                    plist.append(pr)
            elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
                n_surround = _surrounding_count(state, r, c, H, W)
                needed = 8 - n_surround
                if needed <= 0:
                    continue
                pr = closure_p.get(needed, 0.0)
                if pr > 0:
                    plist.append(pr)
            # FARMER / BIG_FARMER: terrain is not city/road/cloister -> skip (never returns)
        return _flat_dcurve(curve, state.meeples[p]) * math.fsum(plist)

    opp = 1 - player
    return _ret(player) - _ret(opp)


def flat_farm_flip_term(state, player: int, decomp: Decomp, cfg) -> float:
    """C7 Term F — farm majority-flip anticipation, player-POV antisymmetric fsum of
    per-contested-field contributions (§2 of C7_LEAF_TERMS_DESIGN.md). Field
    membership + weights use base-scoring (pos0) semantics — F adjusts base's award,
    so it must see exactly base's fields. Smooths base's hard ``sign(margin)·V`` step
    by weighted margin AND free-meeple liquidity; contested fields only."""
    opp = 1 - player
    field_counts: dict = {}   # pos0 root -> [w_p0, w_p1]  (big farmer = 2)
    for pl in (0, 1):
        for mp in state.placed_meeples[pl]:
            mt = mp.meeple_type
            if mt != MeepleType.FARMER and mt != MeepleType.BIG_FARMER:
                continue
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            root = decomp.farm_pos0_root.get((r, c, side))
            if root is None:
                continue
            ent = field_counts.get(root)
            if ent is None:
                ent = [0, 0]
                field_counts[root] = ent
            ent[pl] += 2 if mt == MeepleType.BIG_FARMER else 1
    free_d = state.meeples[player] - state.meeples[opp]
    if free_d > 1:
        free_d = 1
    elif free_d < -1:
        free_d = -1
    contribs: list = []
    for root, cnt in field_counts.items():
        w_me = cnt[player]
        w_opp = cnt[opp]
        if w_me >= 1 and w_opp >= 1:   # contested only
            V = float(3 * decomp.farm_root_finished_cities[root])
            m = w_me - w_opp
            step = 1.0 if m > 0 else (-1.0 if m < 0 else 0.0)
            m_eff = m + _FLIP_BETA * free_d
            ramp = m_eff / _FLIP_RAMP
            if ramp > 1.0:
                ramp = 1.0
            elif ramp < -1.0:
                ramp = -1.0
            contribs.append(V * (ramp - step))
    return math.fsum(contribs)


def _c7_off(cfg) -> bool:
    """True iff both C7 term knobs are OFF — then the cy route need not advertise
    SUPPORTS_V29_C7_TERMS (a stale .so still runs the champion leaf bit-exactly)."""
    return cfg.v29_meeple_return_k == 0.0 and cfg.v29_farm_flip_k == 0.0


def _soft_cap_off(cfg) -> bool:
    """True iff both F6 soft-cap slopes are OFF (0.0) — then the cy route need not
    advertise SUPPORTS_F6_SOFT_CAP (a stale .so hard-clamps, which is bit-exact for
    slope 0.0). A SET slope must not silently route to a soft-cap-blind .so."""
    return (getattr(cfg, "soft_cap_slope", 0.0) == 0.0
            and getattr(cfg, "opp_soft_cap_slope", 0.0) == 0.0)


def flat_virtual_score_v2(state, player: int, cfg=None, bag_close=None) -> int:
    """== virtual_score_v2(state, player, cfg) under CANONICAL_BONUS_SUM, computed
    entirely flat (no deepcopy, no count_final_scores, no engine Farm/City BFS).

    Bit-exact to the engine leaf when the engine runs with CANONICAL_BONUS_SUM=True
    (order-independent fsum); against the naive-sum production path it differs only
    by the known ~1e-4 ±1 hash-seed reorder flips (DECISIONS 2026-06-09).

    `bag_close` (v2.10 Track B): explicit True/False overrides everything (the
    in-process A/B path — no env/global mutation). None -> resolve from
    `cfg.bag_close` when a cfg was passed (the per-side game-gate harness path),
    else the module/env flag V210_BAG_CLOSE (back-compat, cfg is None).
    DEFAULT_CONFIG.bag_close mirrors the env flag, so the env-global gate also
    survives the always-forward-cfg dispatch in virtual_score_v2. OFF is
    bit-identical v2.9."""
    cfg_was_none = cfg is None
    if cfg is None:
        from .virtual_score_v2 import DEFAULT_CONFIG
        cfg = DEFAULT_CONFIG
    if bag_close is None:
        bag_close = V210_BAG_CLOSE if cfg_was_none else bool(getattr(cfg, "bag_close", False))
    # v2.9 meeple curve (Candidate B). The cy leaf implements it when the loaded .so
    # advertises SUPPORTS_V29_CURVE; a STALE .so (no curve support) would silently
    # DROP the curve, so for curve configs we fall back to the pure-Python curve path
    # below unless the build supports it. No curve -> cy as before. Same
    # capability-flag pattern for the v2.10 bag-close gate (SUPPORTS_V210_BAG_CLOSE).
    curve = cfg.v29_meeple_curve
    if USE_CY_LEAF:
        global _CY_FLAT_V2, _CY_FLAT_V2_FLOAT, _CY_SUPPORTS_CURVE, _CY_SUPPORTS_BAG_CLOSE, _CY_SUPPORTS_C7, _CY_SUPPORTS_SOFT_CAP  # noqa: PLW0603
        if _CY_FLAT_V2 is None:
            try:
                from . import flat_leaf_cy as _cy
                _CY_FLAT_V2 = _cy.flat_virtual_score_v2_cy
                _CY_FLAT_V2_FLOAT = getattr(_cy, "flat_virtual_score_v2_cy_float", None) or False
                _CY_SUPPORTS_CURVE = bool(getattr(_cy, "SUPPORTS_V29_CURVE", False))
                _CY_SUPPORTS_BAG_CLOSE = bool(getattr(_cy, "SUPPORTS_V210_BAG_CLOSE", False))
                _CY_SUPPORTS_C7 = bool(getattr(_cy, "SUPPORTS_V29_C7_TERMS", False))
                _CY_SUPPORTS_SOFT_CAP = bool(getattr(_cy, "SUPPORTS_F6_SOFT_CAP", False))
            except ImportError:
                _CY_FLAT_V2 = False  # .so missing on this box -> sentinel; fall through to pure-Python (no crash, no retry)
                _CY_FLAT_V2_FLOAT = False
                _CY_SUPPORTS_CURVE = False
                _CY_SUPPORTS_BAG_CLOSE = False
                _CY_SUPPORTS_C7 = False
                _CY_SUPPORTS_SOFT_CAP = False
        if (_CY_FLAT_V2 and (curve is None or _CY_SUPPORTS_CURVE)
                and (not bag_close or _CY_SUPPORTS_BAG_CLOSE)
                and (_c7_off(cfg) or _CY_SUPPORTS_C7)
                and (_soft_cap_off(cfg) or _CY_SUPPORTS_SOFT_CAP)):
            return _CY_FLAT_V2(state, player, cfg, bag_close)
    if state.players != 2:
        raise ValueError(f"flat_virtual_score_v2 is 2-player only; got {state.players}")
    decomp = decompose(state)
    opp = 1 - player
    bag = _bag_stats(state) if bag_close else None
    base = flat_base_score(state, player, decomp)
    # F6 soft cap (slope 0.0 default -> hard `_capped`, bit-identical); per-side slopes.
    bonus_self = _soft_capped(flat_closure_bonus(state, player, decomp, cfg, bag),
                              cfg.bonus_cap, getattr(cfg, "soft_cap_slope", 0.0))
    bonus_opp = _soft_capped(flat_closure_bonus(state, opp, decomp, cfg, bag),
                             cfg.opp_bonus_cap, getattr(cfg, "opp_soft_cap_slope", 0.0))
    score = base + bonus_self - bonus_opp
    if curve is not None:
        # B: nonlinear meeple liquidity curve REPLACES the flat meeple_k term
        # (== leaf_v29._meeple_curve_term; the object path adds it in apply_v29).
        score += _flat_curve_lookup(curve, state.meeples[player]) - _flat_curve_lookup(curve, state.meeples[opp])
    elif cfg.meeple_k > 0.0:
        score += cfg.meeple_k * (state.meeples[player] - state.meeples[opp])
    # C7: Term R then Term F, two SEPARATE gated adds in this fixed order (float
    # addition is non-associative — a fused add would break 3-way bit-exactness).
    if cfg.v29_meeple_return_k != 0.0:
        score += cfg.v29_meeple_return_k * flat_return_term(state, player, decomp, cfg)
    if cfg.v29_farm_flip_k != 0.0:
        score += cfg.v29_farm_flip_k * flat_farm_flip_term(state, player, decomp, cfg)
    return int(round(score))


def flat_virtual_score_v2_float(state, player: int, cfg=None, bag_close=None) -> float:
    """PRE-ROUND float variant of flat_virtual_score_v2: IDENTICAL computation,
    returns the raw float score BEFORE the terminal ``int(round(...))``.

    Motivation: the PUCT heuristic-prior candidate (heuristic_prior_mcts.py)
    builds priors from ``softmax(Δleaf / τ)`` over per-child afterstates —
    int-rounding the leaf merges close siblings and throws away sub-integer prior
    resolution. This exposes the SAME v2.9 leaf at full float resolution via the
    Cython flat leaf (or the pure-Python flat float when the .so is absent), so
    the candidate leaf runs at Cython speed instead of the ~30× slower pure-Python
    reproduction (``heuristic_prior_mcts.leaf_score_float``).

    ``int(round(flat_virtual_score_v2_float(...)))`` == ``flat_virtual_score_v2(...)``
    by construction (same operations, same order). `bag_close` resolves exactly as
    in flat_virtual_score_v2 (None -> cfg.bag_close if a cfg was passed, else the
    env/module V210_BAG_CLOSE flag)."""
    cfg_was_none = cfg is None
    if cfg is None:
        from .virtual_score_v2 import DEFAULT_CONFIG
        cfg = DEFAULT_CONFIG
    if bag_close is None:
        bag_close = V210_BAG_CLOSE if cfg_was_none else bool(getattr(cfg, "bag_close", False))
    curve = cfg.v29_meeple_curve
    if USE_CY_LEAF:
        global _CY_FLAT_V2, _CY_FLAT_V2_FLOAT, _CY_SUPPORTS_CURVE, _CY_SUPPORTS_BAG_CLOSE, _CY_SUPPORTS_C7, _CY_SUPPORTS_SOFT_CAP  # noqa: PLW0603
        if _CY_FLAT_V2_FLOAT is None:
            if _CY_FLAT_V2 is False:
                _CY_FLAT_V2_FLOAT = False  # .so already known-missing; don't retry
            else:
                try:
                    from . import flat_leaf_cy as _cy
                    _CY_FLAT_V2 = _cy.flat_virtual_score_v2_cy
                    _CY_FLAT_V2_FLOAT = getattr(_cy, "flat_virtual_score_v2_cy_float", None) or False
                    _CY_SUPPORTS_CURVE = bool(getattr(_cy, "SUPPORTS_V29_CURVE", False))
                    _CY_SUPPORTS_BAG_CLOSE = bool(getattr(_cy, "SUPPORTS_V210_BAG_CLOSE", False))
                    _CY_SUPPORTS_C7 = bool(getattr(_cy, "SUPPORTS_V29_C7_TERMS", False))
                    _CY_SUPPORTS_SOFT_CAP = bool(getattr(_cy, "SUPPORTS_F6_SOFT_CAP", False))
                except ImportError:
                    _CY_FLAT_V2 = False
                    _CY_FLAT_V2_FLOAT = False
                    _CY_SUPPORTS_CURVE = False
                    _CY_SUPPORTS_BAG_CLOSE = False
                    _CY_SUPPORTS_C7 = False
                    _CY_SUPPORTS_SOFT_CAP = False
        if (_CY_FLAT_V2_FLOAT and (curve is None or _CY_SUPPORTS_CURVE)
                and (not bag_close or _CY_SUPPORTS_BAG_CLOSE)
                and (_c7_off(cfg) or _CY_SUPPORTS_C7)
                and (_soft_cap_off(cfg) or _CY_SUPPORTS_SOFT_CAP)):
            return float(_CY_FLAT_V2_FLOAT(state, player, cfg, bag_close))
    # pure-Python flat float fallback (== flat_virtual_score_v2 minus the round).
    if state.players != 2:
        raise ValueError(f"flat_virtual_score_v2 is 2-player only; got {state.players}")
    decomp = decompose(state)
    opp = 1 - player
    bag = _bag_stats(state) if bag_close else None
    base = flat_base_score(state, player, decomp)
    # F6 soft cap (slope 0.0 default -> hard `_capped`, bit-identical); per-side slopes.
    bonus_self = _soft_capped(flat_closure_bonus(state, player, decomp, cfg, bag),
                              cfg.bonus_cap, getattr(cfg, "soft_cap_slope", 0.0))
    bonus_opp = _soft_capped(flat_closure_bonus(state, opp, decomp, cfg, bag),
                             cfg.opp_bonus_cap, getattr(cfg, "opp_soft_cap_slope", 0.0))
    score = base + bonus_self - bonus_opp
    if curve is not None:
        score += _flat_curve_lookup(curve, state.meeples[player]) - _flat_curve_lookup(curve, state.meeples[opp])
    elif cfg.meeple_k > 0.0:
        score += cfg.meeple_k * (state.meeples[player] - state.meeples[opp])
    # C7: Term R then Term F (two separate gated adds, fixed order — see the int sibling).
    if cfg.v29_meeple_return_k != 0.0:
        score += cfg.v29_meeple_return_k * flat_return_term(state, player, decomp, cfg)
    if cfg.v29_farm_flip_k != 0.0:
        score += cfg.v29_farm_flip_k * flat_farm_flip_term(state, player, decomp, cfg)
    return float(score)
