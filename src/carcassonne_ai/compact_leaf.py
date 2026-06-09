"""Compact leaf decomposition — flat union-find replacement for the engine's
object-graph farm/city flood-fills (the v2.7 leaf hot path).

Why this exists (DECISIONS.md 2026-06-09): self-play throughput is
RAM-bandwidth-bound. The dominant cost is the v2.7 CPU leaf, whose
`FarmUtil.find_farm` / `CityUtil.find_city` flood-fills chase Python object
graphs (Tile -> FarmerConnection -> ... ) and allocate a swarm of temporary
`Coordinate` / `CoordinateWithSide` / `CoordinateWithFarmerSide` wrappers per
expansion step — near-zero cache locality, so every traversal step is a DRAM
fetch using a fraction of each cache line.

This module computes the SAME connected-component partition with a flat
union-find over small int ids:

    enumerate nodes -> flat int ids
      -> build edge list (two parallel int arrays)
      -> union-find with path-halving on a flat parent[] (the numba/Cython seam)
      -> reconstruct the exact engine Farm / City objects per component.

The output is drop-in for the engine's existing lazy memo dicts: a fully
populated `_farm_cache` (`(row, col, id(FarmerConnection)) -> Farm`) and
`_city_cache` (`CoordinateWithSide -> (positions_set, finished)`). Attach them
to a state and `FarmUtil.find_farm_by_coordinate` / `CityUtil.find_city`
resolve every query as a cache hit, so the object-graph BFS never runs — with
ZERO engine edits. See `virtual_score.USE_COMPACT_LEAF`.

Equivalence is mandatory and gated bit-exactly by
`scripts/reconcile_compact_leaf.py`. The geometry below intentionally mirrors
`FarmUtil.opposite_edge` + `SideModificationUtil.opposite_farmer_side` and
`CityUtil.opposite_edge`; any transcription error surfaces as a partition
mismatch -> score mismatch -> gate failure.

STATUS: correctness-complete, default OFF. The union-find CORE
(`_label_components`) is written as a pure-int kernel over parallel arrays so it
can be `@njit`-compiled (numba) or Cython-AOT'd later for the actual bandwidth
win; that is a deferred Phase-4 perf step (see the rewrite plan). This pure
-Python version proves equivalence; it is NOT yet a measured speedup.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.farm import Farm
from wingedsheep.carcassonne.objects.farmer_connection_with_coordinate import (
    FarmerConnectionWithCoordinate,
)
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.utils.side_modification_util import SideModificationUtil

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState


# --- geometry, mirrored from the engine (cross-checked by the gate) ----------
# Cross a tile border on a *city* edge: (d_row, d_col, side_on_neighbour).
# Mirrors CityUtil.opposite_edge.
_CITY_OPP: dict = {
    Side.TOP: (-1, 0, Side.BOTTOM),
    Side.RIGHT: (0, 1, Side.LEFT),
    Side.BOTTOM: (1, 0, Side.TOP),
    Side.LEFT: (0, -1, Side.RIGHT),
}

# Step direction for a farmer half-side, by its cardinal Side. Mirrors the
# Side branch in FarmUtil.opposite_edge; the neighbour's farmer half-side is
# SideModificationUtil.opposite_farmer_side(fs).
_FARMER_STEP: dict = {
    Side.TOP: (-1, 0),
    Side.RIGHT: (0, 1),
    Side.BOTTOM: (1, 0),
    Side.LEFT: (0, -1),
}


def _label_components(n: int, edges_u: list, edges_v: list) -> list:
    """Union-find connected-components kernel.

    Pure-int over parallel arrays (the numba/Cython target). Returns a
    `labels` list mapping node id -> canonical root id. Path-halving keeps
    `find` near-O(1); union-by-attach is enough at these sizes.
    """
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


def build_farm_cache(game_state: "CarcassonneGameState") -> dict:
    """Whole-board farm decomposition as a fully-populated `_farm_cache`.

    Returns `{(row, col, id(FarmerConnection)) -> Farm}` for every farmer
    connection on the board — exactly the keys/values
    `FarmUtil.find_farm_by_coordinate` would memoize lazily, so every query is
    a hit and `FarmUtil.find_farm` (the object BFS) never runs.

    Equivalent to calling `find_farm` from every farmer connection: the
    component a node lands in is a board function (start-independent since the
    2026-05-29 fix), so partitioning once gives each node exactly its
    `find_farm` region.
    """
    board = game_state.board
    height = len(board)
    width = len(board[0]) if height else 0

    # Enumerate farm nodes: one per FarmerConnection on each placed tile.
    node_rc: list = []          # node id -> (row, col)
    node_fc: list = []          # node id -> FarmerConnection object (shared ref)
    side_to_node: dict = {}     # (row, col, FarmerSide) -> node id
    for row in range(height):
        board_row = board[row]
        for col in range(width):
            tile = board_row[col]
            if tile is None:
                continue
            for fc in tile.farms:
                nid = len(node_rc)
                node_rc.append((row, col))
                node_fc.append(fc)
                for fs in fc.tile_connections:
                    side_to_node[(row, col, fs)] = nid

    # Build edges: a node connects to the neighbour across each of its
    # tile_connections (mirrors find_farm's farm_for_position adjacency).
    edges_u: list = []
    edges_v: list = []
    for nid in range(len(node_rc)):
        row, col = node_rc[nid]
        for fs in node_fc[nid].tile_connections:
            d = _FARMER_STEP.get(fs.get_side())
            if d is None:
                continue
            opp_fs = SideModificationUtil.opposite_farmer_side(fs)
            neighbor = side_to_node.get((row + d[0], col + d[1], opp_fs))
            if neighbor is not None:
                edges_u.append(nid)
                edges_v.append(neighbor)

    n = len(node_rc)
    labels = _label_components(n, edges_u, edges_v)

    # Group node ids by component root.
    members: dict = {}
    for nid in range(n):
        members.setdefault(labels[nid], []).append(nid)

    # Reconstruct one Farm per component, then map every node key -> that Farm.
    cache: dict = {}
    for member_ids in members.values():
        fccs = {
            FarmerConnectionWithCoordinate(
                node_fc[nid], Coordinate(node_rc[nid][0], node_rc[nid][1])
            )
            for nid in member_ids
        }
        farm = Farm(fccs)
        for nid in member_ids:
            row, col = node_rc[nid]
            cache[(row, col, id(node_fc[nid]))] = farm
    return cache


def build_city_cache(game_state: "CarcassonneGameState") -> dict:
    """Whole-board city decomposition as a fully-populated `_city_cache`.

    Returns `{CoordinateWithSide -> (positions_set, finished)}` for every city
    edge on the board — exactly what `CityUtil.find_city` memoizes lazily, so
    every query is a hit and `CityUtil._compute_city` (the object BFS) never
    runs.

    `positions` is the set of `CoordinateWithSide` city edges in the component
    (== `_compute_city`'s `cities`). `finished` is True iff no edge in the
    component is open — i.e. every edge's opposite is itself a placed city edge
    (== `_compute_city`'s `len(explored) == len(cities)`).
    """
    board = game_state.board
    height = len(board)
    width = len(board[0]) if height else 0

    # Enumerate city nodes: one per (tile, city-side). Intra-tile, the sides of
    # one `tile.city` group are connected (== CityUtil.cities_for_position).
    node_rcs: list = []         # node id -> (row, col, Side)
    node_id: dict = {}          # (row, col, Side) -> node id
    intra_groups: list = []     # list of [node ids in the same tile city group]
    for row in range(height):
        board_row = board[row]
        for col in range(width):
            tile = board_row[col]
            if tile is None:
                continue
            for city_group in tile.city:
                group_ids = []
                for side in city_group:
                    key = (row, col, side)
                    nid = node_id.get(key)
                    if nid is None:
                        nid = len(node_rcs)
                        node_id[key] = nid
                        node_rcs.append(key)
                    group_ids.append(nid)
                if group_ids:
                    intra_groups.append(group_ids)

    edges_u: list = []
    edges_v: list = []
    # Intra-tile: connect all sides within one city group.
    for group_ids in intra_groups:
        first = group_ids[0]
        for other in group_ids[1:]:
            edges_u.append(first)
            edges_v.append(other)

    # Cross-tile: connect a city edge to its opposite across the border when
    # the opposite is also a placed city edge; otherwise the edge is OPEN.
    open_node: list = [False] * len(node_rcs)
    for nid in range(len(node_rcs)):
        row, col, side = node_rcs[nid]
        dr, dc, oside = _CITY_OPP[side]
        onid = node_id.get((row + dr, col + dc, oside))
        if onid is not None:
            edges_u.append(nid)
            edges_v.append(onid)
        else:
            open_node[nid] = True

    n = len(node_rcs)
    labels = _label_components(n, edges_u, edges_v)

    # Group node ids by component; a component is finished iff none of its
    # edges is open.
    members: dict = {}
    comp_open: dict = {}
    for nid in range(n):
        root = labels[nid]
        members.setdefault(root, []).append(nid)
        if open_node[nid]:
            comp_open[root] = True

    cache: dict = {}
    for root, member_ids in members.items():
        positions = {
            CoordinateWithSide(Coordinate(node_rcs[nid][0], node_rcs[nid][1]), node_rcs[nid][2])
            for nid in member_ids
        }
        finished = root not in comp_open
        entry = (positions, finished)
        for cws in positions:
            cache[cws] = entry
    return cache
