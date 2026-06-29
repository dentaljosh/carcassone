#!/usr/bin/env python3
"""FGSR graph extractor — typed feature-graph + action-node extraction from a root.

MEASUREMENT / OFFLINE PILOT (Feature-Graph Search-Residual, FGSR_PLAN.md).
NET-FREE, CPU-only. Reads off `flat_leaf.decompose(state)` + `state` + the stored
multi-depth search snapshot. Does NOT run any search and does NOT touch the
v2.9 evaluator / PRODUCTION.yaml. The frozen v2.9 leaf env must already be set by
the caller BEFORE importing engine modules (use measurement_infra.set_frozen_v29_env()).

Two public entry points (both per ROOT):

  extract_graph(state, decomp, root_player) -> dict
      Typed nodes (tile / city_feature / road_feature / farm_feature /
      monastery_feature / player / meeple / deck_bucket) + edges, per
      measurement/feature_graph_search_residual/FGSR_SCHEMA.md. open_boundary is
      FOLDED into feature attrs (open_edges count) for now (schema §open_questions,
      "fold first") — noted in the returned graph["_notes"].

  extract_action_nodes(game, state, board, decomp, root_player, root_record) -> list[dict]
      One node per legal action (== deduped canonical child, matching the stored
      level-map action ids). Attributes = the comparator pilot's 50 per-child
      scalars (build_feat_dataset.py, state-agnostic, reused verbatim) + the stored
      h200/h6400 child (N, Q_rootpov) joined from root_record["levels"].

Design choices baked in (documented so this is a read-off, not new physics):
  * Extract ONCE per root. decompose(state) is memoized by board id within a root
    (and children are decomposed once each in the action pass — the comparator's
    existing per-child decomp).
  * Root-POV sign convention: self = root_player, opp = 1 - root_player. Q values
    in the level-map are already Q_rootpov (snapshot.read_children sign).
  * Meeple->root ownership uses the SAME mapping flat_leaf._final_scores uses
    (city_side_root / road_side_root / farm_pos0_root) so owner/contested are
    bit-consistent with the production leaf scorer.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

# --- repo wiring -------------------------------------------------------------
_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "src", _REPO / "scripts" / "level2",
           _REPO / "scripts" / "feature_graph", _REPO / "scripts" / "measurement_infra"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from carcassonne_ai.flat_leaf import decompose, _winners, _city_points, _road_points

# Reuse the comparator pilot's state-agnostic per-child scalar machinery VERBATIM.
# build_feat_dataset.py sets the v2.9 leaf env at import time (same frozen block),
# so importing it is safe and keeps the leaf pinned. FEAT_NAMES is the canonical
# 50-scalar order; _struct_summary / _completed_value / _opp_feature_touched are
# the exact functions the comparator used.
import build_feat_dataset as BFD
from build_feat_dataset import (
    _struct_summary, _completed_value, _opp_feature_touched, FEAT_NAMES, PHASES,
)
from carcassonne_ai.virtual_score_v2 import virtual_score_v2
from carcassonne_ai.leaf_v29 import decompose_v29

_FARMER_TYPES = (MeepleType.FARMER, MeepleType.BIG_FARMER)
BOARD_CENTER = 17  # 35x35 board, center cell index (for (r,c) normalization)


# ============================================================================ #
# decompose memo (by board object id within one root extraction)
# ============================================================================ #
class _DecompMemo:
    """Memoize decompose(state) by id(state.board). A board within a single root
    extraction is never mutated in place (children are fresh states), so id keying
    is safe for the lifetime of one extract call chain."""
    def __init__(self):
        self._d = {}

    def get(self, state):
        k = id(state.board)
        v = self._d.get(k)
        if v is None:
            v = decompose(state)
            self._d[k] = v
        return v


# ============================================================================ #
# meeple -> feature-root ownership (mirrors flat_leaf._final_scores mapping)
# ============================================================================ #
def _owner_maps(state, decomp):
    """Return per-root weighted meeple counts for city/road/farm + per-meeple
    placement records. counts[root] = [w_p0, w_p1]. Mirrors _final_scores exactly
    (city_side_root / road_side_root / farm_pos0_root)."""
    nplayers = state.players
    board = state.board
    city_counts: dict = {}
    road_counts: dict = {}
    farm_counts: dict = {}
    monastery: list = []   # (player, r, c, surrounding_count)
    meeple_records: list = []  # (player, r, c, side, feat_type, root_or_None)

    for player in range(nplayers):
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            tile = board[r][c]
            terrain = tile.get_type(side)
            w = 2 if mp.meeple_type in (MeepleType.BIG, MeepleType.BIG_FARMER) else 1
            if terrain == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    cnt = city_counts.setdefault(root, [0] * nplayers)
                    cnt[player] += w
                meeple_records.append((player, r, c, side, "city", root))
            elif terrain == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is not None:
                    cnt = road_counts.setdefault(root, [0] * nplayers)
                    cnt[player] += w
                meeple_records.append((player, r, c, side, "road", root))
            elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                sc = _surrounding_count(board, r, c)
                monastery.append((player, r, c, sc))
                meeple_records.append((player, r, c, side, "monastery", None))
            elif mp.meeple_type in _FARMER_TYPES:
                root = decomp.farm_pos0_root.get((r, c, side))
                if root is not None:
                    cnt = farm_counts.setdefault(root, [0] * nplayers)
                    cnt[player] += w
                meeple_records.append((player, r, c, side, "farm", root))
    return city_counts, road_counts, farm_counts, monastery, meeple_records


def _surrounding_count(board, r, c):
    H = len(board)
    W = len(board[0]) if H else 0
    n = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < H and 0 <= cc < W and board[rr][cc] is not None:
                n += 1
    return n


def _owner_status(counts, root_player):
    """('p0'|'p1'|'contested'|'none', contested_flag, m_p0, m_p1)."""
    if counts is None:
        return "none", 0, 0, 0
    m0 = counts[0]
    m1 = counts[1] if len(counts) > 1 else 0
    winners = _winners(counts)
    opp = 1 - root_player
    if not winners:
        status = "none"
    elif len(winners) >= 2:
        status = "contested"
    elif winners[0] == root_player:
        status = "self"
    elif winners[0] == opp:
        status = "opp"
    else:
        status = "none"
    contested = 1 if status == "contested" else 0
    # report meeples in root-POV order (self, opp)
    m_self = counts[root_player]
    m_opp = counts[opp] if len(counts) > opp else 0
    return status, contested, m_self, m_opp


# ============================================================================ #
# extract_graph — typed nodes + edges
# ============================================================================ #
def extract_graph(state, decomp, root_player, k_remaining=None, phase=None):
    """Typed feature graph for one root. Returns a dict:

      nodes: {node_type: [attr_dict, ...]}  with a stable per-type local index
      edges: {edge_type: [(src_type, src_idx, dst_type, dst_idx), ...]}
      meta : {root_player, n_nodes, n_edges, _notes}

    All value-like city/road attrs are reported raw AND phase-normalized
    (/k_remaining) where cheap. open_boundary is folded into feature `open_edges`.
    """
    opp = 1 - root_player
    board = state.board
    k_rem = float(len(state.deck)) if k_remaining is None else float(k_remaining)
    k_norm = max(k_rem, 1.0)

    city_counts, road_counts, farm_counts, monastery, meeple_records = _owner_maps(state, decomp)

    nodes: dict = {t: [] for t in
                   ("tile", "city_feature", "road_feature", "farm_feature",
                    "monastery_feature", "player", "meeple", "deck_bucket")}
    edges: dict = {}

    def add_edge(etype, st, si, dt, di):
        edges.setdefault(etype, []).append((st, si, dt, di))

    # ---- tiles ------------------------------------------------------------- #
    # local index by (r,c). recency from placement order is not stored on state,
    # so ply-placed recency is left None here (the action pass carries move recency).
    tile_idx: dict = {}
    for co in state.placed_coords:
        r, c = co.row, co.column
        tile = board[r][c]
        has_city = bool(tile.city)
        has_road = bool(tile.road)
        has_farm = bool(tile.farms)
        has_monastery = bool(tile.chapel or tile.flowers)
        idx = len(nodes["tile"])
        tile_idx[(r, c)] = idx
        nodes["tile"].append({
            "r_norm": (r - BOARD_CENTER) / 17.0,
            "c_norm": (c - BOARD_CENTER) / 17.0,
            "has_city": int(has_city), "has_road": int(has_road),
            "has_farm": int(has_farm), "has_monastery": int(has_monastery),
            "shield": int(bool(tile.shield)), "inn": int(bool(tile.inn)),
        })

    # ---- city features ----------------------------------------------------- #
    city_idx: dict = {}  # root -> local idx
    for root in decomp.city_root_finished:
        finished = decomp.city_root_finished[root]
        open_n = decomp.city_root_open_n.get(root, 0)
        coords = decomp.city_root_coords[root]
        tile_count = len(coords)
        closure_delta = decomp.city_root_delta.get(root, 0)
        cur_val = _city_points(coords, finished, board)
        comp_val = _city_points(coords, True, board)  # value if completed
        status, contested, m_self, m_opp = _owner_status(city_counts.get(root), root_player)
        idx = len(nodes["city_feature"])
        city_idx[root] = idx
        nodes["city_feature"].append({
            "completed": int(finished), "open_edges": int(open_n),
            "tile_count": tile_count, "closure_delta": closure_delta,
            "current_value": cur_val, "completed_value": comp_val,
            "meeples_self": m_self, "meeples_opp": m_opp,
            "owner_status": status, "contested_flag": contested,
            "phase_norm_value": comp_val / k_norm,
        })
        # tile_belongs_to_feature
        for (r, c) in coords:
            ti = tile_idx.get((r, c))
            if ti is not None:
                add_edge("tile_belongs_to_feature", "tile", ti, "city_feature", idx)

    # ---- road features ----------------------------------------------------- #
    road_idx: dict = {}
    for root in decomp.road_root_finished:
        finished = decomp.road_root_finished[root]
        coords = decomp.road_root_coords[root]
        tile_count = len(coords)
        inn_flag = any(board[r][c].inn for (r, c) in coords)
        # open_ends: a road component is "open" if not finished; count = #open road
        # endpoint sides == positions minus internal connections. Cheap proxy:
        # 0 if finished else (# road positions that are open). We expose finished +
        # a binary has_open since precise endpoint scan needs node-side data.
        status, contested, m_self, m_opp = _owner_status(road_counts.get(root), root_player)
        idx = len(nodes["road_feature"])
        road_idx[root] = idx
        nodes["road_feature"].append({
            "completed": int(finished), "tile_count": tile_count,
            "open_ends": 0 if finished else 1,  # folded: has-open-boundary flag
            "inn_flag": int(inn_flag),
            "meeples_self": m_self, "meeples_opp": m_opp,
            "owner_status": status, "contested_flag": contested,
        })
        for (r, c) in coords:
            ti = tile_idx.get((r, c))
            if ti is not None:
                add_edge("tile_belongs_to_feature", "tile", ti, "road_feature", idx)

    # ---- farm features ----------------------------------------------------- #
    farm_idx: dict = {}
    for root in decomp.farm_root_keys:
        adj_city_roots = decomp.farm_root_adj_city_roots.get(root, frozenset())
        fin_cities = decomp.farm_root_finished_cities.get(root, 0)
        tile_count = len({(r, c) for (r, c, _fc) in decomp.farm_root_keys[root]})
        status, contested, m_self, m_opp = _owner_status(farm_counts.get(root), root_player)
        volatility = len(adj_city_roots) - fin_cities  # cities that could still complete
        idx = len(nodes["farm_feature"])
        farm_idx[root] = idx
        nodes["farm_feature"].append({
            "adjacent_finished_cities": fin_cities,
            "adjacent_city_roots": len(adj_city_roots),
            "tile_count": tile_count,
            "meeples_self": m_self, "meeples_opp": m_opp,
            "owner_status": status, "contested_flag": contested,
            "volatility": volatility,
            "potential_value": 3 * len(adj_city_roots),  # 3pt/completed adjacent city
            "phase_norm_potential": (3 * len(adj_city_roots)) / k_norm,
        })
        # city_touches_farm (reversed adjacency)
        for croot in adj_city_roots:
            ci = city_idx.get(croot)
            if ci is not None:
                add_edge("city_touches_farm", "city_feature", ci, "farm_feature", idx)
                add_edge("feature_touches_feature", "city_feature", ci, "farm_feature", idx)

    # ---- monastery features ------------------------------------------------ #
    # placed-meeple monasteries from _owner_maps + any unmeepled chapel/flowers tiles
    mon_seen = set()
    for (player, r, c, sc) in monastery:
        idx = len(nodes["monastery_feature"])
        mon_seen.add((r, c))
        owner = "self" if player == root_player else "opp"
        nodes["monastery_feature"].append({
            "surrounding_count": sc, "completed": int(sc == 8),
            "owner": owner, "score_if_now": sc + 1,
        })
        ti = tile_idx.get((r, c))
        if ti is not None:
            add_edge("tile_belongs_to_feature", "tile", ti, "monastery_feature", idx)
    # unmeepled monastery tiles (still structural)
    for (r, c), ti in tile_idx.items():
        tile = board[r][c]
        if (tile.chapel or tile.flowers) and (r, c) not in mon_seen:
            sc = _surrounding_count(board, r, c)
            idx = len(nodes["monastery_feature"])
            nodes["monastery_feature"].append({
                "surrounding_count": sc, "completed": int(sc == 8),
                "owner": "none", "score_if_now": sc + 1,
            })
            add_edge("tile_belongs_to_feature", "tile", ti, "monastery_feature", idx)

    # ---- players ----------------------------------------------------------- #
    for p in range(state.players):
        free = int(state.meeples[p])
        nodes["player"].append({
            "player_local": 0 if p == root_player else 1,  # 0 = self, 1 = opp
            "is_root_player": int(p == root_player),
            "is_current_player": int(p == state.current_player),
            "score": int(state.scores[p]),
            "meeples_free": free,
            "meeples_locked": 7 - free,
            "score_margin_signed": int(state.scores[p] - state.scores[1 - p]),
        })

    self_pi = 0 if root_player == 0 else 1  # player node index for root_player

    # ---- meeples ----------------------------------------------------------- #
    for (player, r, c, side, feat_type, root) in meeple_records:
        # near-completion / returnable_soon
        returnable = 0
        feat_t, feat_i = None, None
        if feat_type == "city" and root in city_idx:
            feat_t, feat_i = "city_feature", city_idx[root]
            returnable = int(decomp.city_root_open_n.get(root, 99) <= 1 and not decomp.city_root_finished.get(root, False))
        elif feat_type == "road" and root in road_idx:
            feat_t, feat_i = "road_feature", road_idx[root]
        elif feat_type == "farm" and root in farm_idx:
            feat_t, feat_i = "farm_feature", farm_idx[root]
        mi = len(nodes["meeple"])
        nodes["meeple"].append({
            "player_local": 0 if player == root_player else 1,
            "feature_type": feat_type,
            "returnable_soon": returnable,
        })
        if feat_t is not None:
            add_edge("meeple_on_feature", "meeple", mi, feat_t, feat_i)
        # player_owns / player_contests edges from owner status
        pi = (0 if player == 0 else 1)
        add_edge("meeple_belongs_to_player", "player", pi, "meeple", mi)

    # player_owns_feature / player_contests_feature (from owner_status)
    for (idx_map, ntype, counts_map) in (
        (city_idx, "city_feature", city_counts),
        (road_idx, "road_feature", road_counts),
        (farm_idx, "farm_feature", farm_counts),
    ):
        for root, idx in idx_map.items():
            counts = counts_map.get(root)
            status, contested, _, _ = _owner_status(counts, root_player)
            if status == "contested":
                for pi in (0, 1):
                    add_edge("player_contests_feature", "player", pi, ntype, idx)
            elif status == "self":
                add_edge("player_owns_feature", "player", self_pi, ntype, idx)
            elif status == "opp":
                add_edge("player_owns_feature", "player", 1 - self_pi, ntype, idx)
            # feature_has_open_boundary (folded: emit if not finished / has open edges)
            has_open = False
            if ntype == "city_feature":
                has_open = decomp.city_root_open_n.get(root, 0) > 0
            elif ntype == "road_feature":
                has_open = not decomp.road_root_finished.get(root, True)
            if has_open:
                add_edge("feature_has_open_boundary", ntype, idx, "_open", 0)

    # ---- deck_bucket (1 aggregate node) ------------------------------------ #
    from collections import Counter
    deck_types = Counter()
    for t in state.deck:
        # type signature: (has_city, has_road, has_monastery, shield)
        sig = (bool(t.city), bool(t.road), bool(t.chapel or t.flowers), bool(t.shield))
        deck_types[sig] += 1
    nodes["deck_bucket"].append({
        "k_remaining": int(len(state.deck)),
        "n_city_tiles": sum(v for s, v in deck_types.items() if s[0]),
        "n_road_tiles": sum(v for s, v in deck_types.items() if s[1]),
        "n_monastery_tiles": sum(v for s, v in deck_types.items() if s[2]),
        "n_shield_tiles": sum(v for s, v in deck_types.items() if s[3]),
        "n_distinct_types": len(deck_types),
    })

    n_nodes = sum(len(v) for v in nodes.values())
    n_edges = sum(len(v) for v in edges.values())
    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "root_player": int(root_player),
            "phase": phase,
            "k_remaining": k_rem,
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "node_counts": {t: len(v) for t, v in nodes.items()},
            "edge_counts": {t: len(v) for t, v in edges.items()},
            "_notes": [
                "open_boundary FOLDED into feature open_edges/open_ends + "
                "feature_has_open_boundary edges to a singleton '_open' sentinel",
                "tile recency (ply-placed) not stored on state -> omitted on tile "
                "nodes; move recency carried by action nodes instead",
                "road open_ends reduced to a has-open binary (precise endpoint scan "
                "needs node-side data, deferred per schema 'fold first')",
            ],
        },
    }


# ============================================================================ #
# extract_action_nodes — one node per legal action (comparator 50 scalars + Q)
# ============================================================================ #
def extract_action_nodes(game, state, board, decomp, root_player, root_record, memo=None):
    """One action node per deduped canonical child (matching the stored level-map
    action ids). Attributes = the comparator pilot's 50 per-child scalars +
    stored h200 & h6400 (N, Q_rootpov). Returns list[dict].

    root_record: the roots_mcts.jsonl record (has ["levels"][str(L)][str(action)] =
    [N, Q_rootpov]). decomp: parent Decomp (memoized). memo: optional _DecompMemo
    for child decomposes.
    """
    cfg = BFD.EH._heur_leaf_cfg(2.0)
    opp = 1 - root_player
    levels = root_record["levels"]
    lv200 = {int(a): v for a, v in levels.get("200", {}).items()}
    lv800 = {int(a): v for a, v in levels.get("800", {}).items()}
    lv6400 = {int(a): v for a, v in levels.get("6400", {}).items()}

    # parent decompositions + struct (ONCE)
    pdec = decomp
    pv29 = decompose_v29(state, root_player, cfg)
    pstruct = _struct_summary(state, pdec, root_player)
    p_scores = state.scores
    p_meeples_free = state.meeples
    p_meeple_contrib = pv29["meeple_flat"] + pv29["meeple_curve_delta"]

    phase = root_record.get("phase", "?")
    k_remaining = float(len(state.deck))
    score_margin_signed = float(p_scores[root_player] - p_scores[opp])
    ph_onehot = [1.0 if phase == p else 0.0 for p in PHASES]
    F = ph_onehot + [
        k_remaining / 10.0,
        score_margin_signed / 10.0,
        float(p_meeples_free[root_player]),
        float(p_meeples_free[opp]),
    ]

    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
    out = []
    seen = set()
    for a in legal:
        a = int(a)
        child, _ = game.get_next_state(board, a)
        cs = game.string_representation(child)
        if cs in seen:
            continue
        seen.add(cs)
        cstate = child.state

        ended = game.get_game_ended(child, root_player)
        terminal = 1.0 if ended != 0 else 0.0
        if ended != 0:
            leaf_total_raw = None
            leaf_q = max(-1.0, min(1.0, float(ended)))
        else:
            vs = float(virtual_score_v2(cstate, root_player, cfg))
            leaf_total_raw = vs
            leaf_q = math.tanh(vs / 15.0)

        cv29 = decompose_v29(cstate, root_player, cfg)
        cdec = decompose(cstate)
        cstruct = _struct_summary(cstate, cdec, root_player)
        c_meeple_contrib = cv29["meeple_flat"] + cv29["meeple_curve_delta"]
        leaf_total_div15 = (leaf_total_raw / 15.0) if leaf_total_raw is not None else leaf_q

        net_meeple_delta_self = float(cstate.meeples[root_player] - p_meeples_free[root_player])
        imm_score_delta_self = float(cstate.scores[root_player] - p_scores[root_player])
        imm_score_delta_opp = float(cstate.scores[opp] - p_scores[opp])
        n_placed_parent = len(state.placed_meeples[root_player])
        n_placed_child = len(cstate.placed_meeples[root_player])
        meeple_placed = 1.0 if n_placed_child > n_placed_parent else 0.0
        mtype_city = mtype_road = mtype_farm = mtype_monastery = 0.0
        if meeple_placed:
            pset = set((mp.coordinate_with_side.coordinate.row,
                        mp.coordinate_with_side.coordinate.column,
                        mp.coordinate_with_side.side, mp.meeple_type)
                       for mp in state.placed_meeples[root_player])
            newmp = None
            for mp in cstate.placed_meeples[root_player]:
                key = (mp.coordinate_with_side.coordinate.row,
                       mp.coordinate_with_side.coordinate.column,
                       mp.coordinate_with_side.side, mp.meeple_type)
                if key not in pset:
                    newmp = mp
                    break
            if newmp is not None:
                cws = newmp.coordinate_with_side
                terr = cstate.board[cws.coordinate.row][cws.coordinate.column].get_type(cws.side)
                if newmp.meeple_type in _FARMER_TYPES:
                    mtype_farm = 1.0
                elif terr == TerrainType.CITY:
                    mtype_city = 1.0
                elif terr == TerrainType.ROAD:
                    mtype_road = 1.0
                elif terr in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                    mtype_monastery = 1.0

        d_total_city_open_edges = float(cstruct["total_city_open_edges"] - pstruct["total_city_open_edges"])
        d_n_open_cities = float(cstruct["n_open_cities"] - pstruct["n_open_cities"])
        d_meeples_locked_self = float(cstruct["n_meeples_locked_self"] - pstruct["n_meeples_locked_self"])
        d_n_contested = float(cstruct["n_cities_contested"] - pstruct["n_cities_contested"])
        opp_touched = float(_opp_feature_touched(pstruct, cstruct, root_player))
        csv, cov, feat_completed = _completed_value(pstruct, cdec, cstruct, cstate, root_player)

        row = list(F) + [
            leaf_total_div15, leaf_q,
            cv29["base"] / 15.0, cv29["closure_self"] / 8.0, cv29["closure_opp"] / 8.0,
            c_meeple_contrib, cv29["pretransform_total"] / 15.0, terminal,
            (cv29["base"] - pv29["base"]),
            (cv29["closure_self"] - pv29["closure_self"]),
            (cv29["closure_opp"] - pv29["closure_opp"]),
            (c_meeple_contrib - p_meeple_contrib),
            (cv29["pretransform_total"] - pv29["pretransform_total"]),
            meeple_placed, mtype_city, mtype_road, mtype_farm, mtype_monastery,
            net_meeple_delta_self, imm_score_delta_self, imm_score_delta_opp,
            float(cstruct["n_open_cities"]), float(cstruct["n_open_roads"]),
            float(cstruct["n_open_farms"]), float(cstruct["total_city_open_edges"]),
            float(cstruct["n_cities_self"]), float(cstruct["n_cities_opp"]),
            float(cstruct["n_cities_contested"]), float(cstruct["n_meeples_locked_self"]),
            float(cstruct["n_meeples_locked_opp"]),
            float(cstruct["max_open_city_value_self"]) / 8.0,
            float(cstruct["n_farms_self"]), float(cstruct["n_farms_contested"]),
            d_total_city_open_edges, d_n_open_cities, d_meeples_locked_self,
            d_n_contested, opp_touched, float(feat_completed),
            csv / 8.0, cov / 8.0,
        ]
        feat = np.asarray(row, dtype=np.float32)

        n200, q200 = (lv200.get(a, [0, float("nan")]))[0], (lv200.get(a, [0, float("nan")]))[1]
        n800, q800 = (lv800.get(a, [0, float("nan")]))[0], (lv800.get(a, [0, float("nan")]))[1]
        n6400, q6400 = (lv6400.get(a, [0, float("nan")]))[0], (lv6400.get(a, [0, float("nan")]))[1]

        out.append({
            "action_id": a,
            "feat": feat,            # the 50 comparator scalars (FEAT_NAMES order)
            "n200": int(n200), "q200_rootpov": float(q200),
            "n800": int(n800), "q800_rootpov": float(q800),
            "n6400": int(n6400), "q6400_rootpov": float(q6400),
            "in_h200": a in lv200,   # was this child explored by h200?
            "leaf_q": float(leaf_q),
        })
    return out, FEAT_NAMES


# convenience: full per-root extraction (graph + action nodes) from a record
def extract_root(game, board, root_record, root_player=None):
    state = board.state
    rp = state.current_player if root_player is None else int(root_player)
    decomp = decompose(state)
    graph = extract_graph(state, decomp, rp,
                          k_remaining=len(state.deck), phase=root_record.get("phase"))
    action_nodes, feat_names = extract_action_nodes(
        game, state, board, decomp, rp, root_record)
    return graph, action_nodes, feat_names
