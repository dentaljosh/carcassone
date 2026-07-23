#!/usr/bin/env python3
"""Gate C0 per-component feature emitter.

From `flat_leaf.decompose(child.state)` (the union-find decomposition the
production leaf already builds per leaf), emit a FIXED-LENGTH per-child feature
vector at component-term granularity, oriented to the MOVER (root_player) POV.

Design (see PREREG.md):
  * LEAF-OWN TERMS (guarantee the leaf is the learnable floor):
      lt_base, lt_bonus_self, lt_bonus_opp, lt_meeple_curve, lt_leaf_score.
    lt_base + lt_bonus_self - lt_bonus_opp + lt_meeple_curve == the pre-round
    virtual_score_v2 float; int(round(.)) == lt_leaf_score == the v29_leaf ranker
    input.  An OLS on lt_leaf_score alone reproduces the leaf ordering exactly.
  * RAW POOLED COMPONENT FEATURES: per component type (city/road/farm/cloister),
    pooled by OWNER (me/opp/tie/none) via counts + sums + maxes of raw component
    attributes (size, open-edge count, shields, closure delta, finished points,
    farm->city adjacency & finished-city counts, cloister completion-needed &
    current points).
  * GLOBAL / MEEPLE ECONOMY: running score diff, free-meeple counts & diff,
    placed-meeple counts, bag statistics, deck size.

The emitter is a PURE function of (child_state, root_player, cfg): no env
mutation, no global state.  The caller (c0_export.py) sets the v2.9 leaf env
BEFORE importing carcassonne_ai, exactly like solver_score.py.

NOTE: this module scores an OFFLINE ranker against the exact solver.  It NEVER
touches the champion, the production leaf, or PRODUCTION.yaml.
"""
from __future__ import annotations

import math
from collections import OrderedDict

from carcassonne_ai import flat_leaf as FL
from carcassonne_ai.virtual_score_v2 import virtual_score_v2

from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

_FARMER_TYPES = (MeepleType.FARMER, MeepleType.BIG_FARMER)
_OWNER_BUCKETS = ("me", "opp", "tie", "none")


def _owner_label(counts, me: int, opp: int):
    """Map a component's per-player meeple counts -> owner bucket label.
    Mirrors flat_leaf._winners (ties score for BOTH players)."""
    winners = FL._winners(counts)
    if not winners:
        return "none"
    if len(winners) >= 2:
        return "tie"
    return "me" if winners[0] == me else "opp"


def _component_owner_counts(state, decomp):
    """Per-component [p0_weight, p1_weight] meeple counts for city / road / farm
    components, mirroring flat_leaf._final_scores' meeple-iteration.  Cloisters
    are handled separately (single-owner, per-tile)."""
    board = state.board
    city_cnt: dict = {}
    road_cnt: dict = {}
    farm_cnt: dict = {}
    nplayers = state.players
    for pl in range(nplayers):
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            terrain = board[r][c].get_type(side)
            w = FL._meeple_weight(mp.meeple_type)
            if terrain == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    cnt = city_cnt.get(root)
                    if cnt is None:
                        cnt = [0, 0]
                        city_cnt[root] = cnt
                    cnt[pl] += w
            elif terrain == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is not None:
                    cnt = road_cnt.get(root)
                    if cnt is None:
                        cnt = [0, 0]
                        road_cnt[root] = cnt
                    cnt[pl] += w
            elif mp.meeple_type in _FARMER_TYPES:
                root = decomp.farm_pos0_root.get((r, c, side))
                if root is not None:
                    cnt = farm_cnt.get(root)
                    if cnt is None:
                        cnt = [0, 0]
                        farm_cnt[root] = cnt
                    cnt[pl] += w
    return city_cnt, road_cnt, farm_cnt


def _pool_init(prefix: str, attrs: tuple) -> "OrderedDict":
    """Fixed-length pool skeleton: count per owner bucket + sum/max of each attr
    for the me/opp buckets."""
    d: OrderedDict = OrderedDict()
    for b in _OWNER_BUCKETS:
        d[f"{prefix}_n_{b}"] = 0.0
    for b in ("me", "opp"):
        for a in attrs:
            d[f"{prefix}_{a}_sum_{b}"] = 0.0
            d[f"{prefix}_{a}_max_{b}"] = 0.0
    return d


def _pool_add(d: "OrderedDict", prefix: str, owner: str, attrs_vals: dict):
    d[f"{prefix}_n_{owner}"] += 1.0
    if owner in ("me", "opp"):
        for a, v in attrs_vals.items():
            fv = float(v)
            d[f"{prefix}_{a}_sum_{owner}"] += fv
            k = f"{prefix}_{a}_max_{owner}"
            if fv > d[k]:
                d[k] = fv


# attribute names pooled per type (keep in sync with the _pool_add calls below)
_CITY_ATTRS = ("size", "openn", "shields", "delta", "finpts")
_ROAD_ATTRS = ("size", "openn", "finpts")
_FARM_ATTRS = ("fincities", "adjcities")
_CLOISTER_ATTRS = ("needed", "curpts")


def emit_features_dict(state, root_player: int, cfg) -> "OrderedDict":
    """The per-child feature dict (fixed keys, insertion-ordered).  `state` is a
    CarcassonneGameState (child.state); `root_player` is the mover; `cfg` is the
    v2.9 LeafConfig (== eval_hybrid_handoff._heur_leaf_cfg(2.0))."""
    me = root_player
    opp = 1 - me
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0

    decomp = FL.decompose(state)

    feat: OrderedDict = OrderedDict()

    # --- LEAF-OWN TERMS (the guaranteed floor) ------------------------------- #
    base = FL.flat_base_score(state, me, decomp)
    bonus_self_raw = FL.flat_closure_bonus(state, me, decomp, cfg, None)
    bonus_opp_raw = FL.flat_closure_bonus(state, opp, decomp, cfg, None)
    bonus_self = FL._capped(bonus_self_raw, cfg.bonus_cap)
    bonus_opp = FL._capped(bonus_opp_raw, cfg.opp_bonus_cap)
    curve = cfg.v29_meeple_curve
    if curve is not None:
        mc = (FL._flat_curve_lookup(curve, state.meeples[me])
              - FL._flat_curve_lookup(curve, state.meeples[opp]))
    else:
        mc = cfg.meeple_k * (state.meeples[me] - state.meeples[opp])
    feat["lt_base"] = float(base)
    feat["lt_bonus_self"] = float(bonus_self)
    feat["lt_bonus_opp"] = float(bonus_opp)
    feat["lt_meeple_curve"] = float(mc)
    # the full production leaf (== virtual_score_v2 dispatch under USE_FLAT_LEAF=1,
    # the exact input to the v29_leaf ranker); authoritative, so the ironclad
    # single-feature sanity == the harness 0.6153.
    feat["lt_leaf_score"] = float(virtual_score_v2(state, me, cfg))
    # uncapped bonuses too (extra signal the cap throws away)
    feat["lt_bonus_self_uncapped"] = float(bonus_self_raw)
    feat["lt_bonus_opp_uncapped"] = float(bonus_opp_raw)

    # --- CITY pool ----------------------------------------------------------- #
    city_cnt, road_cnt, farm_cnt = _component_owner_counts(state, decomp)
    cpool = _pool_init("city", _CITY_ATTRS)
    for root, coords in decomp.city_root_coords.items():
        finished = decomp.city_root_finished[root]
        size = len(coords)
        shields = sum(1 for (r, c) in coords if board[r][c].shield)
        openn = decomp.city_root_open_n[root]
        delta = decomp.city_root_delta[root]
        cnt = city_cnt.get(root)
        owner = _owner_label(cnt, me, opp) if cnt is not None else "none"
        finpts = FL._city_points(coords, finished, board) if finished else 0
        _pool_add(cpool, "city", owner, {
            "size": size, "openn": openn, "shields": shields,
            "delta": delta, "finpts": finpts,
        })
    feat.update(cpool)

    # --- ROAD pool ----------------------------------------------------------- #
    rpool = _pool_init("road", _ROAD_ATTRS)
    for root, coords in decomp.road_root_coords.items():
        finished = decomp.road_root_finished[root]
        size = len(coords)
        openn = decomp.road_root_open_n[root]
        cnt = road_cnt.get(root)
        owner = _owner_label(cnt, me, opp) if cnt is not None else "none"
        finpts = FL._road_points(coords, finished, board) if finished else 0
        _pool_add(rpool, "road", owner, {
            "size": size, "openn": openn, "finpts": finpts,
        })
    feat.update(rpool)

    # --- FARM pool ----------------------------------------------------------- #
    fpool = _pool_init("farm", _FARM_ATTRS)
    n_farm_contested = 0
    # iterate ALL farm components (keys), owner via pos0 majority counts
    for root in decomp.farm_root_keys.keys():
        fincities = decomp.farm_root_finished_cities[root]
        adjcities = len(decomp.farm_root_adj_city_roots[root])
        cnt = farm_cnt.get(root)
        owner = _owner_label(cnt, me, opp) if cnt is not None else "none"
        if cnt is not None and cnt[0] >= 1 and cnt[1] >= 1:
            n_farm_contested += 1
        _pool_add(fpool, "farm", owner, {
            "fincities": fincities, "adjcities": adjcities,
        })
    feat.update(fpool)
    feat["farm_n_contested"] = float(n_farm_contested)

    # --- CLOISTER pool (single-owner, per meeple tile) ----------------------- #
    clpool = _pool_init("cloister", _CLOISTER_ATTRS)
    for pl in range(state.players):
        owner = "me" if pl == me else "opp"
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            terrain = board[r][c].get_type(side)
            if terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
                n_sur = FL._surrounding_count(state, r, c, H, W)
                needed = 8 - n_sur
                if needed < 0:
                    needed = 0
                curpts = FL._cloister_points(r, c, board, H, W)
                _pool_add(clpool, "cloister", owner, {
                    "needed": needed, "curpts": curpts,
                })
    feat.update(clpool)

    # --- GLOBAL / MEEPLE ECONOMY --------------------------------------------- #
    feat["g_score_diff"] = float(int(state.scores[me]) - int(state.scores[opp]))
    feat["g_meeple_me"] = float(state.meeples[me])
    feat["g_meeple_opp"] = float(state.meeples[opp])
    feat["g_meeple_diff"] = float(state.meeples[me] - state.meeples[opp])
    feat["g_placed_me"] = float(len(state.placed_meeples[me]))
    feat["g_placed_opp"] = float(len(state.placed_meeples[opp]))
    feat["g_deck_n"] = float(len(state.deck))
    bag = FL._bag_stats(state)  # (n, ge1, ge2, ge3, ge4)
    feat["g_bag_n"] = float(bag[0])
    feat["g_bag_ge1"] = float(bag[1])
    feat["g_bag_ge2"] = float(bag[2])
    feat["g_bag_ge3"] = float(bag[3])
    feat["g_bag_ge4"] = float(bag[4])

    return feat


# leaf-term feature keys (the guaranteed-floor subset) and the ironclad key.
LEAF_TERM_KEYS = ("lt_base", "lt_bonus_self", "lt_bonus_opp", "lt_meeple_curve")
LEAF_SCORE_KEY = "lt_leaf_score"


def feature_order(cfg) -> list:
    """Canonical feature column order, derived from a fresh empty-ish emission.
    Deterministic because emit_features_dict always builds the same keys in the
    same order regardless of board content."""
    # build against a trivial 2-player init state so all pooled keys exist
    from carcassonne_ai.game_wrapper import Game
    g = Game()
    b = g.get_init_board()
    d = emit_features_dict(b.state, 0, cfg)
    return list(d.keys())
