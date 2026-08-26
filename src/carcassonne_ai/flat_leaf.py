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
_CY_SUPPORTS_PHASE = False  # set from flat_leaf_cy.SUPPORTS_V29_PHASE at bind time (Part C phase multiplier)
_CY_BASE = None  # lazily bound flat_leaf_cy.flat_base_score_cy (exact terminal score)

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


def _final_scores(state: "CarcassonneGameState", decomp: Decomp,
                  farm_off: bool = False) -> list:
    """The per-player points `count_final_scores` would ADD (cities + roads +
    farms + cloisters that carry a meeple). Pure int; no mutation, no deepcopy.

    `farm_off` (F7b knockout, default False == unchanged): drop the farm award
    entirely — fields score 0 for everyone. Only the leaf's base term passes it;
    the exact solver's terminal `flat_base_score` never does.

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
    if not farm_off:
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


def flat_base_score(state: "CarcassonneGameState", player: int, decomp: Decomp | None = None,
                    farm_off: bool = False) -> int:
    """== virtual_score(state, player): the end-of-game score differential
    `scores[player] - scores[opp]`, computed flat (no deepcopy, no
    count_final_scores). Pure integer.

    `count_final_scores` ADDS to the running `state.scores`, so the differential
    is the running-score diff plus the diff of the points it would add.

    Under USE_CY_LEAF this redirects to the compiled `flat_base_score_cy`, which
    runs the SAME `_decompose_c` + `_final_scores_c` the Cython v2 leaf already
    uses (bit-exact gate: scripts/reconcile_cy_leaf.py check 2 — integer output,
    so the bar is plain ==). This is the exact endgame solver's terminal leaf and
    was measured at >=37% of an 11.9 s latch solve while still pure Python
    (measurement/ANDROID_WALLCLOCK_MEMO_20260728.md §3, lever #2).

    The redirect fires ONLY when `decomp is None`. A caller that passes a `decomp`
    has already paid for the decomposition and expects THAT one to be scored — the
    cy entry point takes only `(state, player)` and would both redo the work and
    silently ignore the argument. The v2 leaf's pure-Python fallback is such a
    caller, so its path is untouched.

    `farm_off` (F7b knockout, default False == unchanged) drops farm scoring from
    the base term. It ALSO suppresses the cy redirect: `flat_base_score_cy` does not
    implement the knockout (deliberately — see LeafConfig.farm_base_off) and would
    silently return the INTACT score. Callers that leave it False — every caller in
    the tree except the flat leaf's own base term, notably `endgame_solver`'s exact
    terminal — reach the identical code path they did before this argument existed."""
    if state.players != 2:
        raise ValueError(f"flat_base_score is 2-player only; got {state.players}")
    if decomp is None:
        if USE_CY_LEAF and not farm_off:
            global _CY_BASE  # noqa: PLW0603
            if _CY_BASE is None:
                try:
                    from . import flat_leaf_cy as _cy

                    # getattr, not attribute access: a STALE .so predating the export
                    # must degrade to pure Python, not crash (the _CY_FLAT_V2 pattern).
                    _CY_BASE = getattr(_cy, "flat_base_score_cy", None) or False
                except ImportError:
                    _CY_BASE = False  # .so missing on this box -> sentinel, no retry
            if _CY_BASE:
                return _CY_BASE(state, player)
        decomp = decompose(state)
    final = _final_scores(state, decomp, farm_off)
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
    # F7b `farm_growth_off` severs exactly this block (default False == unchanged);
    # `contribs` is fsum-reduced, so dropping members is order-independent.
    if not getattr(cfg, "farm_growth_off", False):
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


# --- Part C PHASE MULTIPLIER on the meeple curve ------------------------------ #
# K0 = 35 (mid-deck) — frozen by the prereg
# (measurement/curve_shape_scope_20260809/PREREG_DRAFT.md §4). Module constant, not a
# LeafConfig field, exactly like _FLIP_BETA/_FLIP_RAMP below.
_PHASE_K0 = 35.0


def _k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand. THE definition of record for the
    phase multiplier, byte-identical to `fair_agent.k_remaining` and to the Rust
    `state.deck_len() + state.next_tile.is_some() as usize`.

    ⚠️ NOT `state.remaining_deck()`, and NOT `_bag_stats`' notion: `_bag_stats`
    deliberately excludes `next_tile` in the MEEPLES phase (there it is a stale ref to
    the just-placed tile). This term counts it unconditionally, because it is a
    game-clock, not a placeability proxy — and because that is what `fair_agent` does,
    which is what the prereg pinned."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def _phase_mult(state, beta: float, norm: float) -> float:
    """`clip(1 + beta*(k - K0)/K0, 0.0, 2.0) / norm` — the mean-1-renormalized phase
    weight. `norm` is the run-level E[f] scalar (cfg.v29_phase_norm); computing it here
    would make the leaf state-history-dependent and break hashing / reconciliation."""
    f = 1.0 + beta * (_k_remaining(state) - _PHASE_K0) / _PHASE_K0
    if f < 0.0:
        f = 0.0
    elif f > 2.0:
        f = 2.0
    return f / norm


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


def flat_denial_term(state, player: int, decomp: Decomp, cfg) -> float:
    """TARGETED DENIAL on near-complete large opponent cities (BACKLOG 2026-05-16
    item 3; LEVER_INDEX "targeted denial"; v1 semantics, building 2026-08-11).

    Returns the RAW denial magnitude ``T >= 0`` from `player`'s POV; the leaf
    subtracts ``cfg.denial_dose * T`` from the evaluation. A city component
    qualifies iff ALL of:

      * OPPONENT STRICT MAJORITY — weighted meeple counts (big meeple = 2, the
        `_final_scores` semantics) with ``counts[opp] > counts[player]``. A TIED
        city never fires (both players majority-score it, so "denial" would also
        hurt the evaluating player); an OWN or unmeepled city never fires.
      * incomplete, and closable: ``0 < open_n`` (`city_root_open_n`, the same
        distinct-empty-adjacent-cell count the closure schedule keys on; the D16
        ``open_n == 0`` board-edge city can never close and never fires),
      * near-complete: ``open_n <= cfg.denial_open_max``,
      * large: anticipated completed value ``city_root_delta >= cfg.denial_size_min``
        (`city_root_delta` == count_city_points if it closed — the exact quantity
        the closure-anticipation bonus already prices).

    Each qualifying city contributes ``delta - denial_size_min + 1`` (linear
    escalation: 1 point of extra fear at the threshold, growing with size).
    Contributions are fsum-reduced (order-independent), mirrored bit-exactly by
    the Rust `carc_core::leaf::denial_term`.

    ⚠️ EXPLICITLY NOT SUBJECT TO `_OPP_BONUS_CAP` / `opp_bonus_cap`: the capped
    opponent-anticipation term can never express more than `opp_bonus_cap` points
    of fear, no matter how large the near-complete opponent city — ESCAPING THAT
    CAP for the (large AND near-complete) conjunction is the entire point of this
    term. It is applied as a separate uncapped subtraction on top of the existing
    (capped) anticipation."""
    opp = 1 - player
    board = state.board
    city_counts: dict = {}   # city root -> [w_p0, w_p1] weighted meeple counts
    for pl in (0, 1):
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            if board[r][c].get_type(side) != TerrainType.CITY:
                continue
            root = decomp.city_side_root.get((r, c, side))
            if root is None:
                continue
            ent = city_counts.get(root)
            if ent is None:
                ent = [0, 0]
                city_counts[root] = ent
            ent[pl] += _meeple_weight(mp.meeple_type)
    size_min = cfg.denial_size_min
    open_max = cfg.denial_open_max
    contribs: list = []
    for root, cnt in city_counts.items():
        if cnt[opp] <= cnt[player]:      # opponent STRICT majority only
            continue
        if decomp.city_root_finished[root]:
            continue
        open_n = decomp.city_root_open_n[root]
        if open_n <= 0 or open_n > open_max:   # unclosable, or not near-complete
            continue
        delta = decomp.city_root_delta[root]
        if delta < size_min:             # not large
            continue
        contribs.append(float(delta) - size_min + 1.0)
    return math.fsum(contribs)


def flat_opencity_term(state, player: int, decomp: Decomp, cfg) -> float:
    """OPEN-CITY DISCIPLINE — penalize LARGE cities that are still WIDE OPEN
    (BACKLOG 2026-05-16; LEVER_INDEX "penalize large open cities"; the flagged
    NEVER-TRIED leaf term, externally endorsed by
    docs/research/PRO_STRATEGY_SCAN_2026-08-12.md §F1; spec
    measurement/opencity_term_20260812/TERM_SPEC.md, building 2026-08-12).

    Returns the SIGNED differential ``T`` from `player`'s POV; the leaf subtracts
    ``cfg.opencity_dose * T``. ``T`` is ``pen(player) - pen(opp)`` when
    ``cfg.opencity_symmetric`` (the default — the leaf stays antisymmetric, so
    ``T`` may be NEGATIVE when the opponent is the more overextended builder), or
    ``pen(player)`` alone when it is False (own-side-only ablation, which breaks
    antisymmetry exactly the way ``denial_dose`` already does).

    ``pen(pl) >= 0`` sums, over every city component where ALL of:

      * ``pl`` HOLDS A STRICT MAJORITY — weighted meeple counts (big meeple = 2,
        the `_final_scores` semantics) with ``counts[pl] > counts[other]``. This
        is the builder-discipline scope: the term prices *the exploitable object
        you built*, never the opponent's (static opponent-side denial is the
        adjacent lever that measured harmful at the 2750 instrument and
        bounded-null at deploy — CL-079 — and the champion's SEARCH already
        finds denial emergently). A TIED city never fires (nobody "owns" the
        overextension); an unmeepled city never fires (no committed stake).
      * INCOMPLETE AND CLOSABLE: ``0 < open_n`` (`city_root_open_n`, the same
        distinct-empty-adjacent-cell count the closure schedule keys on; the D16
        ``open_n == 0`` board-edge city can never close, and a city you cannot
        finish is a *scoring* problem the base term already prices, not an
        exposure problem).
      * WIDE: ``open_n >= cfg.opencity_edge_min`` — the guides' converged rule
        ("prefer one open edge, tolerate two, avoid three") is the default 2.
      * LARGE: ``tiles >= cfg.opencity_size_min``, where ``tiles`` is the count of
        DISTINCT TILES the component spans (``len(city_root_coords[root])``).
        ⚠️ TILES, not points — deliberately NOT `city_root_delta` (denial's axis).
        The F1 mechanism is that the marginal tile earns the same 2 points in a
        big city as in a small one while adding all of the completion and
        steal/merge risk, so the exposure scales with the object's EXTENT.

    Each qualifying city contributes
    ``(tiles - opencity_size_min + 1) * (open_n - opencity_edge_min + 1)`` —
    linear escalation on both axes, exactly 1.0 at the joint threshold corner.
    Per-side contributions are fsum-reduced (order-independent), mirrored
    bit-exactly by the Rust `carc_core::leaf::opencity_term`.

    ``opencity_cap`` (added 2026-08-14, the round-2 falsifier of CL-080's
    uncapped-product form): when ``> 0.0``, each qualifying city's contribution
    is capped PER CITY at ``opencity_cap`` (in the term's own units, before the
    dose multiply) — ``min(raw, cap)``, applied before the fsum so the cap can
    never be reallocated across cities. ``0.0`` (default) == uncapped == the
    cap branch is NEVER taken, so the term is bit-exact with the CL-080-era
    build at the same dose. At cap 1.0 the term degenerates to a count of
    qualifying cities per side (TERM_SPEC §9 item 3's "all-or-nothing switch").

    ⚠️ The term ADJUSTS, it never REPLACES: the closure-anticipation credit the
    same city earns through `flat_closure_bonus` is untouched, and this
    subtraction is applied separately (and uncapped) on top of it — the two are
    deliberately independent so a dose sweep moves only the risk price."""
    board = state.board
    city_counts: dict = {}   # city root -> [w_p0, w_p1] weighted meeple counts
    for pl in (0, 1):
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            if board[r][c].get_type(side) != TerrainType.CITY:
                continue
            root = decomp.city_side_root.get((r, c, side))
            if root is None:
                continue
            ent = city_counts.get(root)
            if ent is None:
                ent = [0, 0]
                city_counts[root] = ent
            ent[pl] += _meeple_weight(mp.meeple_type)
    size_min = cfg.opencity_size_min
    edge_min = cfg.opencity_edge_min
    cap = getattr(cfg, "opencity_cap", 0.0)
    contribs: list = [[], []]            # per-player penalty contributions
    for root, cnt in city_counts.items():
        if cnt[0] > cnt[1]:
            owner = 0
        elif cnt[1] > cnt[0]:
            owner = 1
        else:
            continue                     # tied -> nobody owns the overextension
        if decomp.city_root_finished[root]:
            continue
        open_n = decomp.city_root_open_n[root]
        if open_n <= 0 or open_n < edge_min:   # unclosable, or not wide
            continue
        tiles = len(decomp.city_root_coords[root])
        if tiles < size_min:             # not large
            continue
        contrib = (float(tiles) - size_min + 1.0) * (float(open_n) - float(edge_min) + 1.0)
        if cap > 0.0 and contrib > cap:  # per-city cap (0.0 == uncapped: branch never taken)
            contrib = cap
        contribs[owner].append(contrib)
    pen_self = math.fsum(contribs[player])
    if not cfg.opencity_symmetric:
        return pen_self
    return pen_self - math.fsum(contribs[1 - player])


# --------------------------------------------------------------------------- #
# J-RULES ON SEARCH — the anchor's self-described strategy, as ONE leaf term    #
# (measurement/jrules_on_search_20260813/DESIGN.md, building 2026-08-13)        #
# --------------------------------------------------------------------------- #
#: `k_remaining` at the FIRST decision of a 2-player Base+Farmers game (71 undrawn
#: + 1 in hand; verified against `Game().get_init_board()`). ``joshua_bot`` latches
#: this per game (`Clock.k0`); the leaf MUST stay a pure function of (state, cfg)
#: for hashing and py/rust reconciliation, so it is FROZEN here instead.
_JR_K0 = 72.0

#: rule bits for ``LeafConfig.jrules_mask`` (ablation surface; the primary cell
#: runs JR_ALL). Kept as ints — the Rust mirror reads the same bit values.
JR_J1 = 1      # J1  large-open-city share premium ("sneak a meeple in")
JR_J2 = 2      # J2c farm value discipline (realized steal + low-value surrender)
JR_J5 = 4      # J5+J13 signed unclaimed-feature value
JR_J6 = 8      # J6  anchor structure + road policy
JR_J8 = 16     # J8  pivotal-feature overcommit
JR_ALL = JR_J1 | JR_J2 | JR_J5 | JR_J6 | JR_J8

# --- the FROZEN `current`-preset parameter block ---------------------------- #
# Every constant below is copied from ``joshua_bot.PRESETS["current"]`` (the epoch
# the 2026-08-12 tournament selected at z +3.68). They are deliberately NOT
# LeafConfig fields: 28 more knobs would be 28 more plumbing surfaces through the
# env, the Rust LeafConfigRs, the leaf hash and the reconcile gate, and this
# experiment's calibration axis is the single scalar `jrules_dose`, not a re-tune
# of the interview. `tests/test_jrules_term.py::test_constants_match_joshua_bot`
# pins them against the bot so the two encodings can never silently drift.
_JR_J1_MIN_CITY_TILES = 5
_JR_J1_MIN_OPEN_EDGES = 2
_JR_J1_JOIN_BONUS = 3.0
_JR_J1_LATE_EXTRA = 1.0
_JR_J4_MIN_URGENCY = 0.35
_JR_J4_FULL_RESERVE = 4
_JR_J2_STEAL_W = 1.0
_JR_J2_MIN_FARM_VALUE = 3.0
_JR_J2_LOW_FARM_PENALTY = 2.0
_JR_J2_UNFINISHED_CITY_W = 1.0
_JR_J2_CITY_COUNT_FROM_K = 36
_JR_J2_CITY_CLOSE_OPEN_MAX = 2
_JR_J5_WEIGHT = 0.5
_JR_J5_VALUE_FLOOR = 4.0
#: NEW (no bot counterpart): the reserve differential at which the J13 claim-edge
#: saturates. J5 and J13 are the two signs of ONE term (interview §2 row J13:
#: "credit unclaimed V(f) x (P_self(claim) - P_opp(claim))"); this is the cheapest
#: fair-information proxy for that probability differential.
_JR_J5_RESERVE_NORM = 2.0
_JR_J6_ANCHOR_BONUS = 2.0
_JR_J6_ANCHOR_CITY_MIN = 3
_JR_J6_ANCHOR_ROAD_MIN = 2
_JR_J6_ROAD_JOIN_MIN_LEN = 4
_JR_J6_ROAD_JOIN_BONUS = 2.0
_JR_J6_ROAD_SKEPTIC_MAX_LEN = 3
_JR_J6_ROAD_CLAIM_PENALTY = 1.5
_JR_J6_ROAD_ANCHOR_ALLOWANCE = 1
_JR_J8_PIVOTAL_SWING = 12.0
_JR_J8_OVERCOMMIT_BONUS = 3.0
_JR_J8_VALUE_NORM = 10.0
_JR_J8_MAX_CITY_MEEPLES = 2
_JR_J8_MAX_FARM_MEEPLES = 3

_JR_CLOISTER_TERRAIN = (TerrainType.CHAPEL, TerrainType.FLOWERS)


def _jr_counts(state, decomp):
    """Weighted meeple counts per component + the CLAIMED-cloister cell set.

    Attribution mirrors ``_final_scores`` exactly (terrain of the meeple's own
    side; FARMER/BIG_FARMER -> ``farm_pos0_root``), which is the same rule
    ``joshua_bot.analyze`` follows, so "who has the majority" here is the same
    question the scorer answers."""
    board = state.board
    city: dict = {}
    road: dict = {}
    farm: dict = {}
    cloister: set = set()
    for pl in (0, 1):
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            tile = board[r][c]
            if tile is None:
                continue
            terrain = tile.get_type(side)
            w = _meeple_weight(mp.meeple_type)
            if terrain == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    ent = city.get(root)
                    if ent is None:
                        ent = [0, 0]
                        city[root] = ent
                    ent[pl] += w
            elif terrain == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is not None:
                    ent = road.get(root)
                    if ent is None:
                        ent = [0, 0]
                        road[root] = ent
                    ent[pl] += w
            elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
                cloister.add((r, c))
            elif (mp.meeple_type == MeepleType.FARMER
                  or mp.meeple_type == MeepleType.BIG_FARMER):
                root = decomp.farm_pos0_root.get((r, c, side))
                if root is not None:
                    ent = farm.get(root)
                    if ent is None:
                        ent = [0, 0]
                        farm[root] = ent
                    ent[pl] += w
    return city, road, farm, cloister


def _jr_urgency(opp_reserve: int) -> float:
    """J4 — "if i see he is out of meeple, i am more okay with leaving something
    juicy unclaimed". A multiplier in ``[_JR_J4_MIN_URGENCY, 1.0]`` on every
    CONTEST/CLAIM sub-term (J1, J2c, J6-road-join, J8), exactly as
    ``joshua_bot.j4_urgency``. Note it reads the OTHER side's reserve, so under a
    seat swap the two multipliers exchange — which is what keeps the assembled
    differential antisymmetric."""
    frac = opp_reserve / float(_JR_J4_FULL_RESERVE)
    if frac > 1.0:
        frac = 1.0
    return _JR_J4_MIN_URGENCY + (1.0 - _JR_J4_MIN_URGENCY) * frac


def _jr_late_frac(k: int) -> float:
    """0.0 at the first decision, 1.0 at the last tile (``joshua_bot.Clock.late_frac``
    with the frozen ``_JR_K0`` standing in for the latched per-game ``k0``)."""
    f = 1.0 - (k / _JR_K0)
    if f < 0.0:
        return 0.0
    return 1.0 if f > 1.0 else f


def _jr_j1(decomp, city_counts, pl: int, other: int, late_frac: float) -> float:
    """J1 — "i notice he tends to build large cities that probably wont close. if
    they are getting on the bigger side, i will attempt to sneak a meeple in,
    sometimes late in hte game."

    ⚠️ DELIBERATE DEVIATION from ``joshua_bot.j1_majority_steal``, forced by
    symmetrization. The bot requires ``cnt[other] >= 1`` ("it must be a JOIN into
    HIS city"). In a SIGNED differential that predicate is self-cancelling: before
    the join (he alone) neither side fires; after the join (1-1 tie) BOTH sides
    fire and the difference is again zero, so the term would carry no gradient at
    all — it would never pay for the join it exists to buy. Dropping the
    opponent-presence requirement makes this "credit for HOLDING A SHARE of a large
    still-open city", whose differential across exactly that transition is
    ``0 - B -> B - B``, i.e. **+B for the sneak**, which is the rule's intent. The
    side effect is that it also credits owning a large open city outright — which
    is J6's anchor logic ("keep a big city as mine even if there is no plan to
    close it").

    ⚠️ **OPPOSITE SIGN TO ``opencity_dose`` ON THE SAME OBJECT, BY DECISION.** That
    term SUBTRACTS a penalty for a large open city you hold; this one ADDS a bonus.
    They are simultaneously loadable and would partially cancel — **never run both
    in one cell.** The opposition is not an oversight: the penalise direction went
    straight to the deploy budget and lost decisively (CL-080, arm A, band 1.27e11,
    n=800/cell: dose 0.5 margin z −5.863 / −53.8 elo, dose 2.0 z −19.384 / −190.3
    elo, both cost-neutral), so J1's direction is at least NOT CONTRADICTED. It is
    also NOT SUPPORTED — no cell has ever measured J1, and CL-080's scope limit is
    binding (arm A at two doses only; "the open-cities idea is dead" is a forbidden
    reading). ⚠️ CL-080's leading mechanism is the DOUBLE-COUNT hypothesis, which is
    about STATICNESS, not sign — it applies to a static bonus here just as much.
    Full treatment: measurement/jrules_on_search_20260813/DESIGN.md §3.6."""
    contribs: list = []
    bonus = _JR_J1_JOIN_BONUS * (1.0 + _JR_J1_LATE_EXTRA * late_frac)
    for root, cnt in city_counts.items():
        if decomp.city_root_finished[root]:
            continue
        if cnt[pl] < 1 or cnt[pl] < cnt[other]:
            continue                                   # no share of this city
        if len(decomp.city_root_coords[root]) < _JR_J1_MIN_CITY_TILES:
            continue                                   # not "on the bigger side"
        if decomp.city_root_open_n[root] < _JR_J1_MIN_OPEN_EDGES:
            continue                                   # not "probably wont close"
        contribs.append(bonus)
    return math.fsum(contribs)


def _jr_farm_potential(decomp, root, k: int) -> float:
    """== ``joshua_bot.farm_potential_value``: 3 points for each adjacent city that
    is not finished yet but is plausibly closable. The FINISHED adjacent cities are
    deliberately excluded — ``flat_base_score`` already pays those, and counting
    them here would double-count. J10's "current" epoch only counts the unclosed
    ones from ``_JR_J2_CITY_COUNT_FROM_K`` tiles remaining onward."""
    if k > _JR_J2_CITY_COUNT_FROM_K:
        return 0.0
    n = 0
    for croot in decomp.farm_root_adj_city_roots.get(root, ()):
        if decomp.city_root_finished[croot]:
            continue
        if decomp.city_root_open_n[croot] <= _JR_J2_CITY_CLOSE_OPEN_MAX:
            n += 1
    return 3.0 * n * _JR_J2_UNFINISHED_CITY_W


def _jr_j2(decomp, farm_counts, pl: int, other: int, k: int) -> float:
    """J2c (the value half of J2) — "if i see a farm is valuable, i will try to tie
    it or steal from him", plus J10-"current"'s surrender bar ("some games the
    farms really aren't worth much... so i started to count the cities, especially
    late in game, and surrender a farm").

    Two pieces, both pure state functions:
      * REALIZED STEAL: this side holds tie-or-better on a field that clears the
        value bar -> credit its UNFINISHED-city potential (the part the naive count
        cannot see; the FINISHED adjacent cities are already paid by
        ``flat_base_score``, so crediting them here would double-count).
        ⚠️ SAME SYMMETRIZATION DEVIATION AS J1: the bot additionally requires
        ``cnt[other] >= 1`` ("tie it or steal from HIM"). In a signed differential
        that predicate is inert — before the steal neither side fires (the thief has
        no farmer yet), after it both fire and cancel — so the term would never pay
        for the steal it exists to buy. Dropped, leaving "credit for holding
        tie-or-better on a valuable field", whose differential across exactly that
        transition is ``0 - pot -> pot - pot``, i.e. **+pot for the steal**.
      * SURRENDER CHARGE: a farmer sitting on a field worth less than the bar is
        charged, per weighted meeple.

    ⚠️ J2's APPROACH/REACH half ("planning 2-4 tiles in advance, so i look at
    remaining tiles") is NOT here and is not implemented anywhere — see DESIGN.md
    §"Rules we could not express": it needs bag composition and an entry-cell board
    scan outside the Decomp contract, and, more importantly, multi-tile planning is
    precisely what the 11008-sim search already does natively. Encoding it as a
    static leaf term would double-count depth — the exact confound this build
    exists to remove."""
    contribs: list = []
    for root, cnt in farm_counts.items():
        if cnt[pl] < 1:
            continue
        pot = _jr_farm_potential(decomp, root, k)
        value = 3.0 * decomp.farm_root_finished_cities.get(root, 0) + pot
        if cnt[pl] >= cnt[other] and value >= _JR_J2_MIN_FARM_VALUE:
            contribs.append(_JR_J2_STEAL_W * pot)
        if value < _JR_J2_MIN_FARM_VALUE:
            contribs.append(-_JR_J2_LOW_FARM_PENALTY * cnt[pl])
    return math.fsum(contribs)


def _jr_unclaimed_value(state, decomp, city_counts, road_counts, cloister_owned) -> float:
    """Total value sitting on features NOBODY has a meeple on, counting only the
    excess over ``_JR_J5_VALUE_FLOOR`` ("already worth more than a few points").
    Cities, roads and cloisters — seat-free by construction (this is a property of
    the BOARD, not of a player), which is what lets J5/J13 be expressed as one
    signed term."""
    contribs: list = []
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0
    for root, coords in decomp.city_root_coords.items():
        if root in city_counts:
            continue
        delta = float(decomp.city_root_delta[root])
        v = 2.0 * delta if decomp.city_root_finished[root] else delta
        if v > _JR_J5_VALUE_FLOOR:
            contribs.append(v - _JR_J5_VALUE_FLOOR)
    for root, coords in decomp.road_root_coords.items():
        if root in road_counts:
            continue
        v = float(len(coords))
        if v > _JR_J5_VALUE_FLOOR:
            contribs.append(v - _JR_J5_VALUE_FLOOR)
    # `placed_coords` is a set of engine Coordinate objects; only fsum-reduced
    # below, so its (hash) iteration order can never reach the leaf value.
    for coord in getattr(state, "placed_coords", ()):
        r = coord.row
        c = coord.column
        if (r, c) in cloister_owned:
            continue
        tile = board[r][c]
        if tile is None or tile.get_type(Side.CENTER) not in _JR_CLOISTER_TERRAIN:
            continue
        v = float(_cloister_points(r, c, board, H, W))
        if v > _JR_J5_VALUE_FLOOR:
            contribs.append(v - _JR_J5_VALUE_FLOOR)
    return math.fsum(contribs)


def _jr_claim_edge(state, player: int, opp: int) -> float:
    """J13's ``P_self(claim) - P_opp(claim)``, proxied by the meeple-reserve
    differential and clipped to [-1, 1]. Antisymmetric by construction."""
    e = (state.meeples[player] - state.meeples[opp]) / _JR_J5_RESERVE_NORM
    if e > 1.0:
        return 1.0
    return -1.0 if e < -1.0 else e


def _jr_j6_anchor(decomp, city_counts, road_counts, pl: int, other: int) -> float:
    """J6 (a) + (c) — "i learned from him to keep a big city and road as mine, even
    if there is no plan to close it... but i'm generally less bullish on roads than
    him." A bonus for holding one unfinished city anchor and one unfinished road
    anchor; a charge on every SOLO short road claim past the one anchor road.
    NOT urgency-multiplied (the bot doesn't multiply these either)."""
    has_city = False
    for root, cnt in city_counts.items():
        if decomp.city_root_finished[root] or cnt[pl] <= cnt[other]:
            continue
        if len(decomp.city_root_coords[root]) >= _JR_J6_ANCHOR_CITY_MIN:
            has_city = True
            break
    has_road = False
    n_short_solo = 0
    for root, cnt in road_counts.items():
        if decomp.road_root_finished[root]:
            continue
        length = len(decomp.road_root_coords[root])
        if cnt[pl] > cnt[other]:
            if length >= _JR_J6_ANCHOR_ROAD_MIN:
                has_road = True
            if cnt[other] == 0 and length <= _JR_J6_ROAD_SKEPTIC_MAX_LEN:
                n_short_solo += 1
    excess = n_short_solo - _JR_J6_ROAD_ANCHOR_ALLOWANCE
    if excess < 0:
        excess = 0
    return (_JR_J6_ANCHOR_BONUS * float(int(has_city) + int(has_road))
            - _JR_J6_ROAD_CLAIM_PENALTY * float(excess))


def _jr_j6_road_join(decomp, road_counts, pl: int, other: int) -> float:
    """J6 (b) — "sometimes i see his road is getting long and thats my signal to
    tie it up." Same symmetrization deviation as J1: the bot's ``cnt[other] >= 1``
    join requirement is dropped (it would self-cancel), leaving "credit for holding
    a share of a long unfinished road"."""
    contribs: list = []
    for root, cnt in road_counts.items():
        if decomp.road_root_finished[root]:
            continue
        if cnt[pl] < 1 or cnt[pl] < cnt[other]:
            continue
        if len(decomp.road_root_coords[root]) < _JR_J6_ROAD_JOIN_MIN_LEN:
            continue
        contribs.append(_JR_J6_ROAD_JOIN_BONUS)
    return math.fsum(contribs)


def _jr_j8(decomp, city_counts, farm_counts, pl: int, other: int, k: int,
           abs_margin: float) -> float:
    """J8 — "sometimes it takes 2 meeple to secure a city. sometimes 3 for a single
    farm... you can sometimes see that the game will turn on a single large
    feature, and in those cases, you have to take chances."

    A feature is PIVOTAL when its swing (2x its value) clears ``_JR_J8_PIVOTAL_SWING``
    AND is big enough to flip the current margin. On a pivotal, still-contestable
    feature the side is paid for holding a >=2-weighted-meeple lead, which the naive
    count values at exactly zero.

    ⚠️ TWO DELIBERATE DEVIATIONS from ``joshua_bot``:
      * the bot reads ``|margin|`` from the decision ROOT; a leaf has no root, so
        this reads the margin AT THE LEAF (``|flat_base_score|``). A potential
        cannot see a root, and the leaf's own margin is the natural analogue.
      * the bot gates the farm branch on ``farm_entry_cells >= 1`` ("he can still
        get in"); the Decomp has no farm-side analogue of ``city_root_open_n``, so
        the gate becomes ``k >= 1`` (tiles remain). Strictly more permissive.

    The 2026-08-12 tournament found J8-as-encoded INERT (it was a *filter
    exemption*, pre-empted by F-J3's skip-when-empty rule); `J8EX_INERT_FINDING.md`
    concluded "J8 should arguably be a SCORE term rather than a filter exemption".
    This is that score term."""
    contribs: list = []
    for root, cnt in city_counts.items():
        if decomp.city_root_finished[root]:
            continue
        if decomp.city_root_open_n[root] < 1:
            continue                                   # he can no longer get in
        value = float(decomp.city_root_delta[root])
        swing = 2.0 * value
        if swing < _JR_J8_PIVOTAL_SWING or swing < abs_margin:
            continue
        if cnt[pl] - cnt[other] < 2 or cnt[pl] > _JR_J8_MAX_CITY_MEEPLES:
            continue
        contribs.append(_JR_J8_OVERCOMMIT_BONUS * min(1.0, value / _JR_J8_VALUE_NORM))
    if k >= 1:
        for root, cnt in farm_counts.items():
            value = (3.0 * decomp.farm_root_finished_cities.get(root, 0)
                     + _jr_farm_potential(decomp, root, k))
            swing = 2.0 * value
            if swing < _JR_J8_PIVOTAL_SWING or swing < abs_margin:
                continue
            if cnt[pl] - cnt[other] < 2 or cnt[pl] > _JR_J8_MAX_FARM_MEEPLES:
                continue
            contribs.append(_JR_J8_OVERCOMMIT_BONUS * min(1.0, value / _JR_J8_VALUE_NORM))
    return math.fsum(contribs)


def flat_jrules_term(state, player: int, decomp: Decomp, cfg, base=None) -> float:
    """J-RULES ON SEARCH — the 2026-08-12 anchor interview's strategy expressed as a
    SIGNED leaf differential ``T`` from `player`'s POV; the leaf **ADDS**
    ``cfg.jrules_dose * T``.

    ⚠️ NOTE THE SIGN. ``denial_dose`` and ``opencity_dose`` are PENALTIES and the
    leaf SUBTRACTS them; this bundle is a BONUS potential (the J-rules say what to
    seek, not only what to fear) and the leaf ADDS it. The Rust mirror
    (`carc_core::leaf::jrules_term`) uses the same sign.

    WHY IT EXISTS. The 2026-08-13 Joshua-bot tournament measured these rules on a
    ONE-PLY GREEDY base and lost to the champion by -16.0 pts/deck (z -24.4),
    *weaker than JCloisterZone's shallow AI at -6.5*
    (`measurement/joshuabot_20260812/CONFIRM_VERDICT.md`). That result cannot
    separate STRATEGY from DEPTH and no amount of n fixes it. Putting the same
    rules on the champion's own leaf makes strategy the ONLY difference between the
    two arms.

    ANTISYMMETRY IS THE DESIGN CONSTRAINT. The Rust/Python search evaluates the leaf
    from the MOVER's POV at every node and negates on backup
    (`search/mod.rs`: `let mover = g.state.current_player`), so a term that is not
    antisymmetric is not a coherent zero-sum value function — the value backed up
    at a node stops being the negation of what the other seat sees. Every sub-rule
    is therefore assembled as ``urg(pl) * j(pl) - urg(other) * j(other)``, which
    negates exactly under a seat swap; ``T(s, p) == -T(s, 1-p)`` is pinned on a
    random-play corpus by `tests/test_jrules_term.py::test_antisymmetry_on_the_corpus`.
    THREE rules (J1, J2's realized steal, J6's road join) had to DROP the bot's "the
    opponent must already be there" predicate to survive symmetrization — see their
    docstrings; that is the single largest fidelity deviation in this encoding and
    DESIGN.md §3 states it in full.

    ⚠️ **THE SYMMETRIC FORM IS THE RULING OF RECORD (owner, 2026-08-13; DESIGN.md
    §12 Q1).** There is no ``jrules_symmetric`` knob and adding one is a NEW TERM, not
    a rung: because the leaf is evaluated from the MOVER's POV, an own-side-only
    variant would make the search's internal OPPONENT MODEL play the anchor's strategy
    too — opponent modelling rather than evaluation, a materially stronger and
    different claim that needs its own prereg, its own cell and its own fresh band at
    the deploy budget. ``denial_dose`` breaks antisymmetry today; that is a wart, not a
    precedent to copy.

    RULES COVERED: J1, J2c, J5+J13, J6, J8, with J4 as the urgency multiplier on
    J1/J2c/J6-road-join/J8. RULES NOT COVERED and why: J2-approach (subsumed by
    search depth), J3 (already in the champion leaf as ``v29_meeple_curve``), J7
    (tournament-calibrated best weight is 0.0 == the absent term), J9 (tournament:
    no conviction, negative point estimate), J10's early-farmer block and J3's hard
    floor (both POLICY filters, not value statements — a separate root-filter cell).
    Full table: measurement/jrules_on_search_20260813/DESIGN.md §2.

    ``base`` is ``flat_base_score(state, player, decomp)``; the leaf passes the value
    it already computed. Only J8 reads it (as ``|base|``, which is seat-free)."""
    mask = int(getattr(cfg, "jrules_mask", JR_ALL))
    opp = 1 - player
    city_counts, road_counts, farm_counts, cloister_owned = _jr_counts(state, decomp)
    k = _k_remaining(state)
    parts: list = []
    if mask & JR_J1:
        late = _jr_late_frac(k)
        u_self = _jr_urgency(state.meeples[opp])
        u_opp = _jr_urgency(state.meeples[player])
        parts.append(u_self * _jr_j1(decomp, city_counts, player, opp, late)
                     - u_opp * _jr_j1(decomp, city_counts, opp, player, late))
    if mask & JR_J2:
        u_self = _jr_urgency(state.meeples[opp])
        u_opp = _jr_urgency(state.meeples[player])
        parts.append(u_self * _jr_j2(decomp, farm_counts, player, opp, k)
                     - u_opp * _jr_j2(decomp, farm_counts, opp, player, k))
    if mask & JR_J5:
        # J5 + J13 are ONE signed term and are already a differential, so they are
        # NOT run through the per-side frame and are NOT urgency-multiplied — the
        # claim edge IS the reserve conditioning J4 would otherwise supply, and
        # applying both would price the same reserve fact twice.
        u = _jr_unclaimed_value(state, decomp, city_counts, road_counts, cloister_owned)
        parts.append(_JR_J5_WEIGHT * u * _jr_claim_edge(state, player, opp))
    if mask & JR_J6:
        u_self = _jr_urgency(state.meeples[opp])
        u_opp = _jr_urgency(state.meeples[player])
        parts.append(_jr_j6_anchor(decomp, city_counts, road_counts, player, opp)
                     - _jr_j6_anchor(decomp, city_counts, road_counts, opp, player))
        parts.append(u_self * _jr_j6_road_join(decomp, road_counts, player, opp)
                     - u_opp * _jr_j6_road_join(decomp, road_counts, opp, player))
    if mask & JR_J8:
        if base is None:
            base = flat_base_score(state, player, decomp)
        abs_margin = abs(float(base))
        u_self = _jr_urgency(state.meeples[opp])
        u_opp = _jr_urgency(state.meeples[player])
        parts.append(u_self * _jr_j8(decomp, city_counts, farm_counts, player, opp,
                                     k, abs_margin)
                     - u_opp * _jr_j8(decomp, city_counts, farm_counts, opp, player,
                                      k, abs_margin))
    return math.fsum(parts)


# --------------------------------------------------------------------------- #
# TILE-TIE TIE-BREAK — a bounded micro-term that discriminates only where the   #
# leaf is (near-)silent (measurement/tiletie_term_20260814/DESIGN.md,           #
# building 2026-08-14)                                                          #
# --------------------------------------------------------------------------- #

def _tiletie_wallin(state, decomp, side_root, root_positions, root_finished,
                    root_open_n, terrain) -> list:
    """Per-player closure-cell constrainedness of CLAIMED unfinished open
    components of one terrain (city or road).

    For each component with a strict weighted-meeple majority owner (BIG=2, the
    ``flat_opencity_term`` / ``_final_scores`` semantics), unfinished and
    closable (``open_n > 0``): sum over the component's distinct open cells e —
    the empty in-bounds cells across its open edges, the same derivation as
    ``decompose``'s ``*_root_emptyadj`` — of ``occ4(e) - 1``, where ``occ4`` is
    the count of occupied in-bounds orthogonal neighbours of e (>= 1 by
    construction, so a lone frontier cell contributes 0 and every additional
    wall around a closure cell contributes 1).

    Returns ``[wall_p0, wall_p1]`` as plain floats (ints promoted)."""
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0
    counts: dict = {}   # root -> [w_p0, w_p1]
    for pl in (0, 1):
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            if board[r][c].get_type(side) != terrain:
                continue
            root = side_root.get((r, c, side))
            if root is None:
                continue
            ent = counts.get(root)
            if ent is None:
                ent = [0, 0]
                counts[root] = ent
            ent[pl] += _meeple_weight(mp.meeple_type)
    wall = [0.0, 0.0]
    for root, cnt in counts.items():
        if cnt[0] > cnt[1]:
            owner = 0
        elif cnt[1] > cnt[0]:
            owner = 1
        else:
            continue                     # tied -> nobody owns the component
        if root_finished[root]:
            continue
        if root_open_n[root] <= 0:
            continue                     # unclosable (D16 board-edge object)
        open_cells: set = set()
        for (r, c, side) in root_positions[root]:
            step = _OPP.get(_SIDE_IX[side])
            if step is None:
                continue                 # CENTER etc. never crosses a border
            nr, nc = r + step[0], c + step[1]
            if 0 <= nr < H and 0 <= nc < W and board[nr][nc] is None:
                open_cells.add((nr, nc))
        total = 0
        for (er, ec) in open_cells:
            occ = 0
            if er > 0 and board[er - 1][ec] is not None:
                occ += 1
            if er + 1 < H and board[er + 1][ec] is not None:
                occ += 1
            if ec > 0 and board[er][ec - 1] is not None:
                occ += 1
            if ec + 1 < W and board[er][ec + 1] is not None:
                occ += 1
            total += occ - 1
        wall[owner] += float(total)
    return wall


def flat_tiletie_term(state, player: int, decomp: Decomp, cfg) -> float:
    """The tile-tie tie-break term T, bounded in (-1, 1). The leaf ADDS
    ``cfg.tiletie_dose * T`` (see flat_virtual_score_v2). Dose 0.0 == the term
    never runs (early branch in the callers — this function is not consulted).

    Motivation (measurement/tiletie_pricing_20260812, pooled n=733): the
    production leaf exactly ties the top TILE placement on ~66% of champion tile
    plies, the tied sets carry real value spread (S1a z +4.26), and the
    champion's 11008-sim search leaves +0.252 pts/tied ply of it on the table
    (z +3.43). CL-065 forbids a learned tie-breaker, so T is hand-crafted
    geometry:

        raw = w_city  * (wall_city(opp)  - wall_city(self))
            + w_road  * (wall_road(opp)  - wall_road(self))
            + w_perim * F_perim          # sum of occ4 over state.open_positions
            + w_lib   * F_lib            # len(state.open_positions)
        T   = t / (1 + |t|),  t = raw / tiletie_norm

    * ``wall_*`` — closure-geometry guard (see ``_tiletie_wallin``): don't brick
      up the cells your own claimed features still need to close; do constrain
      the opponent's. The leaf's ``closure_p[open_n]`` counts open cells but is
      blind to how fillable they are — inside an exact tie set every existing
      leaf term is equal across arms by definition, so this is new signal.
    * ``F_perim`` / ``F_lib`` — board-frontier shape terms. ⚠️ Both are
      PLAYER-INDEPENDENT, so a nonzero ``w_perim`` / ``w_lib`` breaks leaf
      antisymmetry (the ``denial_dose`` wart, disclosed the same way). The
      default weights (city 1, road 1, perim 0, lib 0) keep T antisymmetric.
    * The bounded map ``t/(1+|t|)`` is strictly monotone — within-tie ORDERING
      never depends on ``tiletie_norm`` or the dose — and uses only exactly-
      representable float ops (no libm tanh), for the future rust mirror.
    * |T| < 1 makes ``tiletie_dose`` a hard cap on the leaf perturbation: any
      dose below the leaf's own value-lattice step (census: non-tie top-2 gap
      p5 = 0.15) reorders exact and hairline ties ONLY.

    Determinism: contributions are ``fsum``-reduced; the wallin sets/dicts are
    iterated only through order-independent reductions (sums)."""
    parts: list = []
    w_city = getattr(cfg, "tiletie_w_city", 1.0)
    w_road = getattr(cfg, "tiletie_w_road", 1.0)
    if w_city != 0.0:
        wc = _tiletie_wallin(state, decomp, decomp.city_side_root,
                             decomp.city_root_positions, decomp.city_root_finished,
                             decomp.city_root_open_n, TerrainType.CITY)
        parts.append(w_city * (wc[1 - player] - wc[player]))
    if w_road != 0.0:
        wr = _tiletie_wallin(state, decomp, decomp.road_side_root,
                             decomp.road_root_positions, decomp.road_root_finished,
                             decomp.road_root_open_n, TerrainType.ROAD)
        parts.append(w_road * (wr[1 - player] - wr[player]))
    w_perim = getattr(cfg, "tiletie_w_perim", 0.0)
    w_lib = getattr(cfg, "tiletie_w_lib", 0.0)
    if w_perim != 0.0 or w_lib != 0.0:
        board = state.board
        H = len(board)
        W = len(board[0]) if H else 0
        perim = 0
        n_open = 0
        for pos in state.open_positions:
            er, ec = pos.row, pos.column
            n_open += 1
            if w_perim != 0.0:
                if er > 0 and board[er - 1][ec] is not None:
                    perim += 1
                if er + 1 < H and board[er + 1][ec] is not None:
                    perim += 1
                if ec > 0 and board[er][ec - 1] is not None:
                    perim += 1
                if ec + 1 < W and board[er][ec + 1] is not None:
                    perim += 1
        if w_perim != 0.0:
            parts.append(w_perim * float(perim))
        if w_lib != 0.0:
            parts.append(w_lib * float(n_open))
    t = math.fsum(parts) / getattr(cfg, "tiletie_norm", 8.0)
    return t / (1.0 + abs(t))


def _tiletie_off(cfg) -> bool:
    """True iff the tile-tie tie-break is OFF (dose 0.0) — then the cy route is
    bit-exact. Like the F7b knockouts, denial, open-city and jrules there is
    deliberately NO cy implementation, so a SET dose ALWAYS leaves the cy fast
    path for the pure-Python flat leaf. ⚠️ There is also NO rust implementation
    yet — a SET dose through rust_agent.leaf_config_rs raises TypeError
    (fail-closed) until the mirror lands."""
    return getattr(cfg, "tiletie_dose", 0.0) == 0.0


def _jrules_off(cfg) -> bool:
    """True iff the J-rules bundle is OFF (dose 0.0) — then the cy route is
    bit-exact. Like the F7b knockouts, the denial term and the open-city term there
    is deliberately NO cy implementation (candidate cells run `--backend rust`,
    where no Python leaf is computed at all), so a SET dose ALWAYS leaves the cy
    fast path for the pure-Python flat leaf: bit-exact
    (scripts/rustport/reconcile_leaf.py `--configs jrules` against Rust) but far
    slower per leaf."""
    return getattr(cfg, "jrules_dose", 0.0) == 0.0


def _opencity_off(cfg) -> bool:
    """True iff open-city discipline is OFF (dose 0.0) — then the cy route is
    bit-exact. Like the F7b knockouts and the denial term there is deliberately NO
    cy implementation (candidate cells run `--backend rust`, where no Python leaf
    is computed at all), so a SET dose ALWAYS leaves the cy fast path for the pure-
    Python flat leaf: bit-exact (scripts/rustport/reconcile_leaf.py `--configs
    opencity` against Rust) but far slower per leaf."""
    return getattr(cfg, "opencity_dose", 0.0) == 0.0


def _denial_off(cfg) -> bool:
    """True iff the targeted-denial term is OFF (dose 0.0) — then the cy route is
    bit-exact. Like the F7b knockouts there is deliberately NO cy implementation
    (candidate cells run `--backend rust`, where no Python leaf is computed at
    all), so a SET dose ALWAYS leaves the cy fast path for the pure-Python flat
    leaf: bit-exact (scripts/rustport/reconcile_leaf.py `--configs denial`
    against Rust) but far slower per leaf."""
    return getattr(cfg, "denial_dose", 0.0) == 0.0


def _invasion_off(cfg) -> bool:
    """True iff EVERY invasion-risk weight is OFF (0.0) — then this leaf is the
    champion's, bit-for-bit, and both the cy and the pure-Python flat routes are
    correct.

    ⚠️ THE SIDES ARE REVERSED HERE vs denial / open-city / jrules / tiletie. The
    invasion-risk family (LeafConfig.invasion_*, spec
    measurement/invasion_term_build/SHAPES.md) is implemented in the RUST leaf ONLY
    — by decision, there is no flat_leaf mirror and no cy mirror. So a SET weight
    does not "leave the fast path"; it makes BOTH Python leaves RAISE (see
    `_require_invasion_off`). Screening cells run `--backend rust`.

    The two inert shape-B knobs (`invasion_alpha_cap`, `invasion_stub_max_tiles`)
    are deliberately NOT consulted: they cannot move a leaf value while
    `invasion_alpha` is 0.0."""
    return (getattr(cfg, "invasion_beta", 0.0) == 0.0
            and getattr(cfg, "invasion_alpha", 0.0) == 0.0
            and getattr(cfg, "invasion_gamma", 0.0) == 0.0
            and getattr(cfg, "invasion_delta_farm", 0.0) == 0.0)


def _require_invasion_off(cfg) -> None:
    """Fail LOUD on a nonzero invasion-risk weight (see `_invasion_off`). Serving an
    invasion-blind Python leaf to an invasion cell would read as 'the term is worth
    nothing' instead of 'the term never ran' — precisely the misreading this build
    exists to prevent."""
    if not _invasion_off(cfg):
        raise NotImplementedError(
            "LeafConfig invasion-risk weights (invasion_beta / invasion_alpha / "
            "invasion_gamma / invasion_delta_farm) are implemented in the RUST leaf "
            "ONLY (carc_core::leaf::invasion; spec "
            "measurement/invasion_term_build/SHAPES.md). There is deliberately no "
            "flat_leaf and no Cython mirror — run the cell with `--backend rust`."
        )


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


def _farm_knockout_off(cfg) -> bool:
    """True iff both F7b farm knockouts are OFF — then the cy route is bit-exact.

    Unlike the other capability gates in this file there is no `SUPPORTS_*` flag to
    consult: `flat_leaf_cy.pyx` DELIBERATELY does not implement the knockouts (F7b
    decision — the ablation cells run `--backend rust`, where no Python leaf is
    computed at all, and the exact-K tail scores the TRUE final score with farms
    intact by design). So a SET knob ALWAYS leaves the cy fast path for the
    pure-Python flat leaf: bit-exact (gated by scripts/rustport/reconcile_leaf.py
    `--configs farmoff` against Rust) but ~12.5x slower per leaf."""
    return (not getattr(cfg, "farm_base_off", False)
            and not getattr(cfg, "farm_growth_off", False))


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
    # RUST-ONLY family — fail loud BEFORE any route is chosen (see _invasion_off).
    _require_invasion_off(cfg)
    # v2.9 meeple curve (Candidate B). The cy leaf implements it when the loaded .so
    # advertises SUPPORTS_V29_CURVE; a STALE .so (no curve support) would silently
    # DROP the curve, so for curve configs we fall back to the pure-Python curve path
    # below unless the build supports it. No curve -> cy as before. Same
    # capability-flag pattern for the v2.10 bag-close gate (SUPPORTS_V210_BAG_CLOSE).
    curve = cfg.v29_meeple_curve
    if USE_CY_LEAF:
        global _CY_FLAT_V2, _CY_FLAT_V2_FLOAT, _CY_SUPPORTS_CURVE, _CY_SUPPORTS_BAG_CLOSE, _CY_SUPPORTS_C7, _CY_SUPPORTS_SOFT_CAP, _CY_SUPPORTS_PHASE  # noqa: PLW0603
        if _CY_FLAT_V2 is None:
            try:
                from . import flat_leaf_cy as _cy
                _CY_FLAT_V2 = _cy.flat_virtual_score_v2_cy
                _CY_FLAT_V2_FLOAT = getattr(_cy, "flat_virtual_score_v2_cy_float", None) or False
                _CY_SUPPORTS_CURVE = bool(getattr(_cy, "SUPPORTS_V29_CURVE", False))
                _CY_SUPPORTS_BAG_CLOSE = bool(getattr(_cy, "SUPPORTS_V210_BAG_CLOSE", False))
                _CY_SUPPORTS_C7 = bool(getattr(_cy, "SUPPORTS_V29_C7_TERMS", False))
                _CY_SUPPORTS_SOFT_CAP = bool(getattr(_cy, "SUPPORTS_F6_SOFT_CAP", False))
                _CY_SUPPORTS_PHASE = bool(getattr(_cy, "SUPPORTS_V29_PHASE", False))
            except ImportError:
                _CY_FLAT_V2 = False  # .so missing on this box -> sentinel; fall through to pure-Python (no crash, no retry)
                _CY_FLAT_V2_FLOAT = False
                _CY_SUPPORTS_CURVE = False
                _CY_SUPPORTS_BAG_CLOSE = False
                _CY_SUPPORTS_C7 = False
                _CY_SUPPORTS_SOFT_CAP = False
                _CY_SUPPORTS_PHASE = False
        if (_CY_FLAT_V2 and (curve is None or _CY_SUPPORTS_CURVE)
                and (not bag_close or _CY_SUPPORTS_BAG_CLOSE)
                and (_c7_off(cfg) or _CY_SUPPORTS_C7)
                and (_soft_cap_off(cfg) or _CY_SUPPORTS_SOFT_CAP)
                and (cfg.v29_phase_beta == 0.0 or _CY_SUPPORTS_PHASE)
                and _farm_knockout_off(cfg)
                and _denial_off(cfg)
                and _opencity_off(cfg)
                and _jrules_off(cfg)
                and _tiletie_off(cfg)):
            return _CY_FLAT_V2(state, player, cfg, bag_close)
    if state.players != 2:
        raise ValueError(f"flat_virtual_score_v2 is 2-player only; got {state.players}")
    decomp = decompose(state)
    opp = 1 - player
    bag = _bag_stats(state) if bag_close else None
    base = flat_base_score(state, player, decomp, getattr(cfg, "farm_base_off", False))
    # F6 soft cap (slope 0.0 default -> hard `_capped`, bit-identical); per-side slopes.
    bonus_self = _soft_capped(flat_closure_bonus(state, player, decomp, cfg, bag),
                              cfg.bonus_cap, getattr(cfg, "soft_cap_slope", 0.0))
    bonus_opp = _soft_capped(flat_closure_bonus(state, opp, decomp, cfg, bag),
                             cfg.opp_bonus_cap, getattr(cfg, "opp_soft_cap_slope", 0.0))
    score = base + bonus_self - bonus_opp
    # Targeted denial: an UNCAPPED extra subtraction on top of the (capped)
    # opponent anticipation — deliberately NOT routed through `_soft_capped` /
    # `opp_bonus_cap`; escaping that cap for near-complete large opponent cities
    # is the point (see flat_denial_term). dose == 0.0 (default/champion) takes
    # an early branch — never a subtract of 0.0 — so default traffic is
    # byte-identical, not merely equal.
    if getattr(cfg, "denial_dose", 0.0) != 0.0:
        score -= cfg.denial_dose * flat_denial_term(state, player, decomp, cfg)
    # Open-city discipline: a SIGNED, uncapped subtraction applied AFTER denial (two
    # separate gated statements in this fixed order — float addition is
    # non-associative, so a fused expression would break 3-way bit-exactness). It
    # ADJUSTS the city terms, never replaces them. dose == 0.0 (default/champion)
    # takes an early branch — never a subtract of 0.0 — so default traffic is
    # byte-identical, not merely equal.
    if getattr(cfg, "opencity_dose", 0.0) != 0.0:
        score -= cfg.opencity_dose * flat_opencity_term(state, player, decomp, cfg)
    # J-rules on search: a SIGNED, uncapped **addition** (note the sign — this bundle
    # is a BONUS potential, not a penalty like denial/open-city), applied AFTER
    # open-city as a third separate gated statement in this fixed order (float
    # addition is non-associative, so a fused expression would break 3-way
    # bit-exactness). dose == 0.0 (default/champion) takes an early branch — never
    # an add of 0.0 — so default traffic is byte-identical, not merely equal.
    if getattr(cfg, "jrules_dose", 0.0) != 0.0:
        score += cfg.jrules_dose * flat_jrules_term(state, player, decomp, cfg, base)
    # Tile-tie tie-break: a SIGNED, bounded (|T| < 1) micro-**addition** applied
    # AFTER jrules as a fourth separate gated statement in this fixed order (float
    # addition is non-associative, so a fused expression would break bit-exactness
    # gating). dose == 0.0 (default/champion) takes an early branch — never an add
    # of 0.0 — so default traffic is byte-identical, not merely equal.
    if getattr(cfg, "tiletie_dose", 0.0) != 0.0:
        score += cfg.tiletie_dose * flat_tiletie_term(state, player, decomp, cfg)
    if curve is not None:
        # B: nonlinear meeple liquidity curve REPLACES the flat meeple_k term
        # (== leaf_v29._meeple_curve_term; the object path adds it in apply_v29).
        # Part C: beta == 0.0 (default/champion) takes the UNMODIFIED expression —
        # an early branch, never a multiply by 1.0, so default traffic is byte-identical.
        if cfg.v29_phase_beta == 0.0:
            score += _flat_curve_lookup(curve, state.meeples[player]) - _flat_curve_lookup(curve, state.meeples[opp])
        else:
            score += _phase_mult(state, cfg.v29_phase_beta, cfg.v29_phase_norm) * (
                _flat_curve_lookup(curve, state.meeples[player]) - _flat_curve_lookup(curve, state.meeples[opp]))
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
    # RUST-ONLY family — fail loud BEFORE any route is chosen (see _invasion_off).
    _require_invasion_off(cfg)
    curve = cfg.v29_meeple_curve
    if USE_CY_LEAF:
        global _CY_FLAT_V2, _CY_FLAT_V2_FLOAT, _CY_SUPPORTS_CURVE, _CY_SUPPORTS_BAG_CLOSE, _CY_SUPPORTS_C7, _CY_SUPPORTS_SOFT_CAP, _CY_SUPPORTS_PHASE  # noqa: PLW0603
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
                    _CY_SUPPORTS_PHASE = bool(getattr(_cy, "SUPPORTS_V29_PHASE", False))
                except ImportError:
                    _CY_FLAT_V2 = False
                    _CY_FLAT_V2_FLOAT = False
                    _CY_SUPPORTS_CURVE = False
                    _CY_SUPPORTS_BAG_CLOSE = False
                    _CY_SUPPORTS_C7 = False
                    _CY_SUPPORTS_SOFT_CAP = False
                    _CY_SUPPORTS_PHASE = False
        if (_CY_FLAT_V2_FLOAT and (curve is None or _CY_SUPPORTS_CURVE)
                and (not bag_close or _CY_SUPPORTS_BAG_CLOSE)
                and (_c7_off(cfg) or _CY_SUPPORTS_C7)
                and (_soft_cap_off(cfg) or _CY_SUPPORTS_SOFT_CAP)
                and (cfg.v29_phase_beta == 0.0 or _CY_SUPPORTS_PHASE)
                and _farm_knockout_off(cfg)
                and _denial_off(cfg)
                and _opencity_off(cfg)
                and _jrules_off(cfg)
                and _tiletie_off(cfg)):
            return float(_CY_FLAT_V2_FLOAT(state, player, cfg, bag_close))
    # pure-Python flat float fallback (== flat_virtual_score_v2 minus the round).
    if state.players != 2:
        raise ValueError(f"flat_virtual_score_v2 is 2-player only; got {state.players}")
    decomp = decompose(state)
    opp = 1 - player
    bag = _bag_stats(state) if bag_close else None
    base = flat_base_score(state, player, decomp, getattr(cfg, "farm_base_off", False))
    # F6 soft cap (slope 0.0 default -> hard `_capped`, bit-identical); per-side slopes.
    bonus_self = _soft_capped(flat_closure_bonus(state, player, decomp, cfg, bag),
                              cfg.bonus_cap, getattr(cfg, "soft_cap_slope", 0.0))
    bonus_opp = _soft_capped(flat_closure_bonus(state, opp, decomp, cfg, bag),
                             cfg.opp_bonus_cap, getattr(cfg, "opp_soft_cap_slope", 0.0))
    score = base + bonus_self - bonus_opp
    # Targeted denial — uncapped, dose-gated early branch (see the int sibling).
    if getattr(cfg, "denial_dose", 0.0) != 0.0:
        score -= cfg.denial_dose * flat_denial_term(state, player, decomp, cfg)
    # Open-city discipline — signed, uncapped, dose-gated early branch, applied
    # AFTER denial in this fixed order (see the int sibling).
    if getattr(cfg, "opencity_dose", 0.0) != 0.0:
        score -= cfg.opencity_dose * flat_opencity_term(state, player, decomp, cfg)
    # J-rules on search — signed, uncapped, dose-gated early branch, ADDED (not
    # subtracted) after open-city in this fixed order (see the int sibling).
    if getattr(cfg, "jrules_dose", 0.0) != 0.0:
        score += cfg.jrules_dose * flat_jrules_term(state, player, decomp, cfg, base)
    # Tile-tie tie-break — bounded, dose-gated early branch, ADDED after jrules
    # in this fixed order (see the int sibling).
    if getattr(cfg, "tiletie_dose", 0.0) != 0.0:
        score += cfg.tiletie_dose * flat_tiletie_term(state, player, decomp, cfg)
    if curve is not None:
        if cfg.v29_phase_beta == 0.0:   # Part C: early branch == byte-identical default
            score += _flat_curve_lookup(curve, state.meeples[player]) - _flat_curve_lookup(curve, state.meeples[opp])
        else:
            score += _phase_mult(state, cfg.v29_phase_beta, cfg.v29_phase_norm) * (
                _flat_curve_lookup(curve, state.meeples[player]) - _flat_curve_lookup(curve, state.meeples[opp]))
    elif cfg.meeple_k > 0.0:
        score += cfg.meeple_k * (state.meeples[player] - state.meeples[opp])
    # C7: Term R then Term F (two separate gated adds, fixed order — see the int sibling).
    if cfg.v29_meeple_return_k != 0.0:
        score += cfg.v29_meeple_return_k * flat_return_term(state, player, decomp, cfg)
    if cfg.v29_farm_flip_k != 0.0:
        score += cfg.v29_farm_flip_k * flat_farm_flip_term(state, player, decomp, cfg)
    return float(score)
