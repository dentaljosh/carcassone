#!/usr/bin/env python3
"""Step-2 "PeNS" SCALAR dataset builder (MEASUREMENT ONLY).

Builds the full ~89-scalar PeNS feature row for each canonical teacher-Q'd child
of each of the 10,067 h6400_v2.9 sibling sets, in ONE consistent per-child loop.
The row is, in fixed order:

  * CL-034's 50 handcrafted scalars (Group A/B/C/D/E of PeNS_SCHEMA.md)
      — the EXACT computation from scripts/feature_graph/build_feat_dataset._process
      (FEAT_NAMES order preserved; the _struct_summary / _completed_value /
      _opp_feature_touched helpers are copied verbatim so the labels + leaf_q stay
      bit-identical to CL-034 / Step-1 / the value-resurrection enumeration).
  * + the 32-type bag/deck-composition histogram (step1_planes.bag_histogram),
      the Step-1 sighted axis (the cleanest "net sees what the leaf can't").
  * + 7 NEW DECK-ONLY deck-odds scalars (Group F #48-54 of PeNS_SCHEMA.md), the
      only genuinely new logic (see `_deck_odds` below + its docstring for the
      completer-matching approximation + the deck-only doctrine line).

Total feature width D = 50 + 32 + 7 = 89.

Enumeration is bit-identical to build_feat_dataset.py / step1_dump.py: same env,
same EH._heur_leaf_cfg(2.0) cfg (hash 7fc930b82801cb43), same canonical-child set
keyed by game.string_representation (teacher-Q'd, id-deduped), determinism via
checksum match (mismatches skipped). Root-POV throughout (self = root_player,
opp = 1-root_player; never p0/p1).

NET-FREE, CPU-parallel. Writes <out>/aux_step2.npz + <out>/meta.json.

  python -u scripts/step2_pens/build_dataset.py \
      --out /home/doctor/carc_step2_pens/dataset --workers 30           # full
  python -u scripts/step2_pens/build_dataset.py --limit 50 --workers 8 \
      --out /home/doctor/carc_step2_pens/dataset_smoke                  # smoke
"""
from __future__ import annotations
import os
# --- GUARD env (copied VERBATIM from build_feat_dataset.py lines ~28-38) ------ #
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, dataclasses as dc, hashlib, json, math, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.virtual_score_v2 import virtual_score_v2
from carcassonne_ai.flat_leaf import decompose, _road_points
from carcassonne_ai.leaf_v29 import decompose_v29
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.game_phase import GamePhase
# the frozen 32-type bag histogram (Step-1, asserts 32 types / 72 tiles at import)
from step1_planes import bag_histogram, BAG_ORDER, N_BAG  # noqa: E402

HG = REPO / "measurement" / "high_gap_distillation"
FROZEN_V29_HASH = "7fc930b82801cb43"
_FARMER_TYPES = (MeepleType.FARMER, MeepleType.BIG_FARMER)
_CARDINAL_SIDES = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)
_W: dict = {}

# ---------------------------------------------------------------------------- #
# Feature ordering.  D = 50 (CL-034) + 32 (bag) + 7 (deck-odds) = 89.
# CL-034's 50 are copied VERBATIM from build_feat_dataset.FEAT_NAMES (same order).
# ---------------------------------------------------------------------------- #
PHASES = ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]
CL034_FEAT_NAMES = [
    # Group F — context (9)
    "F_phase_opening", "F_phase_midgame", "F_phase_late_mid",
    "F_phase_pre_endgame", "F_phase_endgame",
    "F_k_remaining_div10", "F_score_margin_signed_div10",
    "F_meeples_free_self", "F_meeples_free_opp",
    # Tier-1 — leaf components (13)
    "T1_leaf_total_div15", "T1_leaf_q_tanh",
    "T1_base_div15", "T1_closure_self_div8", "T1_closure_opp_div8",
    "T1_meeple_contribution", "T1_pretransform_div15", "T1_terminal_flag",
    "T1_d_base", "T1_d_closure_self", "T1_d_closure_opp",
    "T1_d_meeple", "T1_d_pretransform",
    # Tier-2 — action/move semantics (8)
    "T2_meeple_placed", "T2_mtype_city", "T2_mtype_road",
    "T2_mtype_farm", "T2_mtype_monastery",
    "T2_net_meeple_delta_self", "T2_imm_score_delta_self", "T2_imm_score_delta_opp",
    # Tier-2 — child structural state (12)
    "T2_n_open_cities", "T2_n_open_roads", "T2_n_open_farms",
    "T2_total_city_open_edges", "T2_n_cities_self", "T2_n_cities_opp",
    "T2_n_cities_contested", "T2_n_meeples_locked_self", "T2_n_meeples_locked_opp",
    "T2_max_open_city_value_self_div8", "T2_n_farms_self", "T2_n_farms_contested",
    # Tier-2 — parent->child structural deltas (8)
    "T2_d_total_city_open_edges", "T2_d_n_open_cities", "T2_d_meeples_locked_self",
    "T2_d_n_contested", "T2_opp_feature_touched", "T2_feature_completed_by_move",
    "T2_completed_value_self_div8", "T2_completed_value_opp_div8",
]
assert len(CL034_FEAT_NAMES) == 50, len(CL034_FEAT_NAMES)

BAG_FEAT_NAMES = [f"BAG_{d}" for d in BAG_ORDER]  # 32, fraction-of-type-remaining in [0,1]
assert len(BAG_FEAT_NAMES) == 32

# --- the 7 NEW deck-odds features (Group F #48-54), DECK-ONLY, log-space ---- #
DECKODDS_FEAT_NAMES = [
    "DO_completer_copies_my_open_cities_sum_log1p",     # #48
    "DO_completer_copies_my_open_cities_max_log1p",     # #49
    "DO_completer_copies_opp_open_cities_sum_log1p",    # #50
    "DO_n_dead_features_self",                          # #51 (raw count)
    "DO_n_dead_features_opp",                           # #52 (raw count)
    "DO_P_ge1_completer_my_closable_sum_log1p",         # #53 (sum of hypergeo P, log1p)
    "DO_placed_tile_remaining_count_log1p",             # #54
]
assert len(DECKODDS_FEAT_NAMES) == 7

FEAT_NAMES = CL034_FEAT_NAMES + BAG_FEAT_NAMES + DECKODDS_FEAT_NAMES
N_FEAT = len(FEAT_NAMES)  # 89
assert N_FEAT == 89, N_FEAT


def _cfg_hash(cfg):
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()
         if not (k == "bag_close" and v is False)}  # v2.10 bag_close default-off == frozen v2.9 substrate
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _provenance_guard():
    cfg = EH._heur_leaf_cfg(2.0)
    h = _cfg_hash(cfg)
    print(f"[provenance] v2.9 leaf config_hash = {h}  (frozen v2.9 = {FROZEN_V29_HASH})")
    assert h == FROZEN_V29_HASH, f"LEAF NOT v2.9 bmild_cap8 (got {h})"
    return cfg


def _worker_init():
    _W["cfg"] = EH._heur_leaf_cfg(2.0)
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)


# ============================================================================ #
# CL-034 structural helpers — COPIED VERBATIM from
# scripts/feature_graph/build_feat_dataset.py so the 50 scalars are bit-identical.
# ============================================================================ #
def _struct_summary(state, decomp, root_player):
    """Returns a dict of structural facts used by Tier-2 (child or parent)."""
    opp = 1 - root_player
    n_open_cities = sum(1 for fin in decomp.city_root_finished.values() if not fin)
    n_open_roads = sum(1 for fin in decomp.road_root_finished.values() if not fin)
    n_open_farms = len(decomp.farm_root_keys)
    total_city_open_edges = sum(decomp.city_root_open_n.values())

    city_owner: dict = {}
    road_owner: dict = {}
    farm_owner: dict = {}
    locked_self = 0
    locked_opp = 0
    board = state.board
    for pl in range(state.players):
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row; c = cws.coordinate.column; side = cws.side
            terr = board[r][c].get_type(side)
            w = 2 if mp.meeple_type in (MeepleType.BIG, MeepleType.BIG_FARMER) else 1
            if terr == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    city_owner.setdefault(root, {}).update()
                    city_owner.setdefault(root, {})[pl] = city_owner.get(root, {}).get(pl, 0) + w
                    if not decomp.city_root_finished.get(root, False):
                        if pl == root_player: locked_self += w
                        else: locked_opp += w
            elif terr == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is not None:
                    road_owner.setdefault(root, {})[pl] = road_owner.get(root, {}).get(pl, 0) + w
                    if not decomp.road_root_finished.get(root, False):
                        if pl == root_player: locked_self += w
                        else: locked_opp += w
            elif terr in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                if pl == root_player: locked_self += w
                else: locked_opp += w
            elif mp.meeple_type in _FARMER_TYPES:
                root = decomp.farm_pos0_root.get((r, c, side))
                if root is not None:
                    farm_owner.setdefault(root, {})[pl] = farm_owner.get(root, {}).get(pl, 0) + w
                    if pl == root_player: locked_self += w
                    else: locked_opp += w

    def _classify(owner_map):
        nself = nopp = ncon = 0
        for root, pm in owner_map.items():
            s = pm.get(root_player, 0); o = pm.get(opp, 0)
            if s > 0 and o > 0: ncon += 1
            elif s > 0: nself += 1
            elif o > 0: nopp += 1
        return nself, nopp, ncon

    n_cities_self, n_cities_opp, n_cities_contested = _classify(city_owner)
    n_farms_self, n_farms_opp, n_farms_contested = _classify(farm_owner)

    max_open_city_value_self = 0
    for root, pm in city_owner.items():
        if pm.get(root_player, 0) > 0 and not decomp.city_root_finished.get(root, False):
            v = decomp.city_root_delta.get(root, 0)
            if v > max_open_city_value_self:
                max_open_city_value_self = v

    return {
        "n_open_cities": n_open_cities,
        "n_open_roads": n_open_roads,
        "n_open_farms": n_open_farms,
        "total_city_open_edges": total_city_open_edges,
        "n_cities_self": n_cities_self,
        "n_cities_opp": n_cities_opp,
        "n_cities_contested": n_cities_contested,
        "n_meeples_locked_self": locked_self,
        "n_meeples_locked_opp": locked_opp,
        "max_open_city_value_self": max_open_city_value_self,
        "n_farms_self": n_farms_self,
        "n_farms_contested": n_farms_contested,
        "_finished_city_roots": frozenset(
            decomp.city_root_positions[root] for root, fin in decomp.city_root_finished.items() if fin
        ),
        "_owner_roots_opp": frozenset(
            r for r, pm in city_owner.items() if pm.get(opp, 0) > 0
        ) | frozenset(
            r for r, pm in road_owner.items() if pm.get(opp, 0) > 0
        ) | frozenset(
            r for r, pm in farm_owner.items() if pm.get(opp, 0) > 0
        ),
        "_city_owner": city_owner,
        "_road_owner": road_owner,
        "_decomp": decomp,
    }


def _completed_value(parent_struct, child_decomp, child_struct, state_child, root_player):
    """Points to self/opp from features NEWLY finished by this move."""
    opp = 1 - root_player
    pd = parent_struct["_decomp"]
    cd = child_decomp
    board = state_child.board
    cself = copp = 0
    feature_completed = 0
    parent_fin_city = {frozenset(coords)
                       for root, coords in pd.city_root_coords.items()
                       if pd.city_root_finished.get(root, False)}
    for root, fin in cd.city_root_finished.items():
        if not fin:
            continue
        coords = frozenset(cd.city_root_coords[root])
        if coords in parent_fin_city:
            continue
        feature_completed = 1
        pm = child_struct["_city_owner"].get(root, {})
        if not pm:
            continue
        m = max(pm.values())
        winners = [p for p, v in pm.items() if v == m]
        pts = cd.city_root_delta.get(root, 0)
        if root_player in winners: cself += pts
        if opp in winners: copp += pts
    parent_fin_road = {frozenset(coords)
                       for root, coords in pd.road_root_coords.items()
                       if pd.road_root_finished.get(root, False)}
    for root, fin in cd.road_root_finished.items():
        if not fin:
            continue
        coords = frozenset(cd.road_root_coords[root])
        if coords in parent_fin_road:
            continue
        feature_completed = 1
        pm = child_struct["_road_owner"].get(root, {})
        if not pm:
            continue
        m = max(pm.values())
        winners = [p for p, v in pm.items() if v == m]
        pts = _road_points(cd.road_root_coords[root], True, board)
        if root_player in winners: cself += pts
        if opp in winners: copp += pts
    return cself, copp, feature_completed


def _opp_feature_touched(parent_struct, child_struct, root_player):
    """1 if the move modified an opp-owned feature."""
    pd = parent_struct["_decomp"]; cd = child_struct["_decomp"]
    opp = 1 - root_player

    def _opp_city_state(struct, decomp):
        out = {}
        for root, pm in struct["_city_owner"].items():
            if pm.get(opp, 0) > 0:
                out[frozenset(decomp.city_root_coords[root])] = (
                    decomp.city_root_open_n.get(root, 0),
                    decomp.city_root_finished.get(root, False),
                )
        return out

    def _opp_road_state(struct, decomp):
        out = {}
        for root, pm in struct["_road_owner"].items():
            if pm.get(opp, 0) > 0:
                out[frozenset(decomp.road_root_coords[root])] = decomp.road_root_finished.get(root, False)
        return out

    pc = _opp_city_state(parent_struct, pd)
    cc = _opp_city_state(child_struct, cd)
    for coords, st in pc.items():
        if coords not in cc:
            return 1
        if cc[coords] != st:
            return 1
    pr = _opp_road_state(parent_struct, pd)
    cr = _opp_road_state(child_struct, cd)
    for coords, st in pr.items():
        if coords not in cr or cr[coords] != st:
            return 1
    return 0


# ============================================================================ #
# FILE 1b — the 7 NEW DECK-ONLY deck-odds features (Group F #48-54).
# ============================================================================ #
def _remaining_tile_counts(state):
    """The remaining-tile multiset, per the Step-1 bag rule: state.deck + the
    state.next_tile IFF phase == TILES (the drawn-but-unplaced tile is still
    'remaining' from the decision's POV). Returns a list of Tile objects (so the
    caller can inspect edges) AND the total count tiles_left.

    DECK-ONLY: this is purely the multiset of what is left to draw; no model of
    future play, no opponent policy."""
    tiles = list(state.deck)
    nt = getattr(state, "next_tile", None)
    if nt is not None and state.phase == GamePhase.TILES:
        tiles.append(nt)
    return tiles


def _tile_has_terrain_edge(tile, terr):
    """True if `tile` carries at least one CARDINAL edge of TerrainType `terr`
    (city or road). A tile is rotated freely on placement, so any cardinal edge
    of the right terrain means the tile COULD extend such a feature — the same
    permissive over-count the leaf's own `_deck_city_supply` uses (it does not do
    the full geometric adjacency search; neither do we). This is a DECK-ONLY fact
    (a property of the remaining-tile multiset + terrain), never of future play."""
    return any(tile.get_type(s) == terr for s in _CARDINAL_SIDES)


def _hypergeom_p_ge1(supply, bag_size, draws):
    """EXACT deck-only P(at least one of `supply` 'completer' tiles appears in the
    next `draws` tiles drawn without replacement from a bag of `bag_size`).

      P(>=1) = 1 - C(bag_size - supply, draws) / C(bag_size, draws)
             = 1 - prod_{i=0..draws-1} (bag_size - supply - i)/(bag_size - i)

    Depends ONLY on (supply, bag_size, draws) = (#completer copies, tiles-left,
    #tiles that will still be drawn). NO model of future play / who draws / where
    it lands — a pure combinatorial fact about the remaining multiset. This is the
    'calculator's answer' (#53); F#48-50/#54 are the raw inputs the net can also
    combine itself in log-space (see PeNS_SCHEMA.md §3b)."""
    if supply <= 0 or bag_size <= 0 or draws <= 0:
        return 0.0
    if supply >= bag_size:
        return 1.0
    draws = min(draws, bag_size)
    p_none = 1.0
    for i in range(draws):
        num = bag_size - supply - i
        den = bag_size - i
        if num <= 0:
            return 1.0
        p_none *= num / den
    return 1.0 - p_none


def _deck_odds(child_state, child_decomp, child_struct, root_player, placed_tile):
    """The 7 deck-only deck-odds scalars (Group F #48-54).

    APPROXIMATION (documented, deck-only-doctrine-preserving):
      "completer copies for an open city/road component" is approximated as the
      number of REMAINING tile-copies that carry >=1 cardinal edge of that
      terrain (city for cities, road for roads). This is the leaf's own
      `_deck_city_supply` permissive proxy (virtual_score_v2.py) applied
      PER-FEATURE: a freely-rotated tile with a matching edge COULD extend the
      component. We do NOT run the exact geometric adjacency search (which open
      cell, which rotation actually mates the open edges) — too expensive for a
      per-leaf feature, and the leaf itself never does it. This OVER-counts (some
      matching tiles can't physically mate every open edge) but it is a function
      ONLY of the remaining multiset + the component's terrain + open-edge state
      — it never consults a model of future play, who draws, or where a tile
      lands, so it stays strictly on the DECK-ONLY side of the doctrine line.
      P(I actually complete this) / expected-final-score is excluded (projection).

      A "completer copy" for the #48-50 SUMS/MAX is attributed to each of my/opp
      OPEN city components. Because the matching set is a deck property (not
      per-cell), every open city of a player gets the same per-feature count =
      `city_copies`; the SUM thus scales with #open cities (more open cities =
      more places that supply could land = more completion exposure), the MAX is
      `city_copies` when any open city exists. This is the schema's
      sum/max-over-my-open-features-of-#completer-copies (#48/#49), and the
      log1p keeps the heavy-tailed counts linear-in-ratio (§3).

      `n_dead_features` (#51/#52): an open city/road owned by the player is DEAD
      iff there are ZERO remaining copies of its terrain (it can never close).
      This is the exact deck-only dead flag (no completer remains).

      #53 P(>=1 completer drawn): over my CLOSABLE-SOON features — open cities/
      roads with open_n (distinct empty adjacent cells) <= 1, i.e. one tile from
      closing — the EXACT hypergeometric P(>=1 completer in the remaining draws).
      draws = tiles_left (every remaining tile is a future draw; this is the
      deck-only ceiling, no turn-order model). Summed over such features, log1p.
      For roads we treat open_n via road open-end count (<=1 closable-soon too;
      see below). NOTE roads have no open_n in Decomp, so for the closable-soon
      road set we count open road ends == 1 from road_root_positions vs finished.

      #54 placed_tile_remaining_count: #remaining copies (in the bag multiset) of
      THIS move's placed tile-DESCRIPTION (consumes-rare-tile). DECK-ONLY count
      of `placed_tile.description` in the remaining multiset. log1p.
    """
    opp = 1 - root_player
    tiles = _remaining_tile_counts(child_state)
    bag_size = len(tiles)

    # deck supply by terrain (permissive, leaf-style) ----------------------- #
    city_copies = 0
    road_copies = 0
    for t in tiles:
        if _tile_has_terrain_edge(t, TerrainType.CITY):
            city_copies += 1
        if _tile_has_terrain_edge(t, TerrainType.ROAD):
            road_copies += 1

    cd = child_decomp
    city_owner = child_struct["_city_owner"]
    road_owner = child_struct["_road_owner"]

    # open city roots owned by self / opp (>=1 meeple, not finished) --------- #
    def _open_owned(owner_map, finished_map, owner_pl):
        roots = []
        for root, pm in owner_map.items():
            if pm.get(owner_pl, 0) > 0 and not finished_map.get(root, False):
                roots.append(root)
        return roots

    my_open_city_roots = _open_owned(city_owner, cd.city_root_finished, root_player)
    opp_open_city_roots = _open_owned(city_owner, cd.city_root_finished, opp)
    my_open_road_roots = _open_owned(road_owner, cd.road_root_finished, root_player)
    opp_open_road_roots = _open_owned(road_owner, cd.road_root_finished, opp)

    # #48/#49: completer copies for my open cities (sum / max), log-space.
    # per-open-city completer count == city_copies (deck property); sum over
    # the player's open cities, max == city_copies if any open city.
    n_my_open_cities = len(my_open_city_roots)
    completer_sum_my = city_copies * n_my_open_cities
    completer_max_my = city_copies if n_my_open_cities > 0 else 0
    # #50: same SUM for opp open cities.
    completer_sum_opp = city_copies * len(opp_open_city_roots)

    # #51/#52: dead features (no remaining closer). An open city is dead iff
    # city_copies == 0; an open road dead iff road_copies == 0. Count self/opp
    # open city+road features that are dead.
    def _dead_count(open_city_roots, open_road_roots):
        d = 0
        if city_copies == 0:
            d += len(open_city_roots)
        if road_copies == 0:
            d += len(open_road_roots)
        return d

    n_dead_self = _dead_count(my_open_city_roots, my_open_road_roots)
    n_dead_opp = _dead_count(opp_open_city_roots, opp_open_road_roots)

    # #53: P(>=1 completer drawn) over my closable-soon features, sum, log1p.
    # closable-soon CITY: city_root_open_n <= 1 (one empty adjacent cell -> one
    # tile from closing). closable-soon ROAD: exactly one open road end.
    p_sum = 0.0
    for root in my_open_city_roots:
        if cd.city_root_open_n.get(root, 99) <= 1:
            p_sum += _hypergeom_p_ge1(city_copies, bag_size, bag_size)
    # road open-end count: #distinct (r,c,side) that are open. Decomp does not
    # expose road_root_open_n, so derive from positions that lack a finished
    # neighbour: a road is closable-soon iff it has exactly 1 open end. We
    # approximate via: open road (not finished) with <=2 tiles is one-end-from-
    # close in the common case; conservatively use the not-finished flag and a
    # single-end assumption (open roads typically have 1-2 open ends). To stay
    # deck-only + cheap we treat every not-finished owned road as closable-soon
    # at most one tile away when road has a single open end. Decomp gives only
    # finished/positions; we approximate closable-soon-road := not finished.
    for root in my_open_road_roots:
        p_sum += _hypergeom_p_ge1(road_copies, bag_size, bag_size)

    # #54: placed-tile remaining count (consumes-rare-tile), log1p.
    placed_remaining = 0
    if placed_tile is not None:
        desc = getattr(placed_tile, "description", None)
        if desc is not None:
            for t in tiles:
                if getattr(t, "description", None) == desc:
                    placed_remaining += 1

    return [
        math.log1p(completer_sum_my),
        math.log1p(completer_max_my),
        math.log1p(completer_sum_opp),
        float(n_dead_self),
        float(n_dead_opp),
        math.log1p(p_sum),
        math.log1p(placed_remaining),
    ]


def _placed_tile(parent_state, child_state):
    """The Tile object placed by the move = the tile present in child_state.board
    at a cell that was empty in parent_state.board (deck-only: identifies the
    physical tile-type consumed, for #54). Returns the Tile or None."""
    pb = parent_state.board
    cb = child_state.board
    H = len(cb); Wd = len(cb[0]) if H else 0
    for r in range(H):
        for c in range(Wd):
            if cb[r][c] is not None and pb[r][c] is None:
                return cb[r][c]
    return None


def _process(rec):
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game, board = replay_to(seed, ply)
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        cfg = _W["cfg"]
        pstate = board.state
        root_player = pstate.current_player
        opp = 1 - root_player
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}

        # parent decompositions (ONCE per root) ------------------------------ #
        pdec = decompose(pstate)
        pv29 = decompose_v29(pstate, root_player, cfg)
        pstruct = _struct_summary(pstate, pdec, root_player)
        p_scores = pstate.scores
        p_meeples_free = pstate.meeples
        p_meeple_contrib = pv29["meeple_flat"] + pv29["meeple_curve_delta"]

        phase = rec.get("phase", "?")
        k_remaining = float(rec.get("k_remaining", 0))
        score_margin_signed = float(p_scores[root_player] - p_scores[opp])
        ph_onehot = [1.0 if phase == p else 0.0 for p in PHASES]
        Fctx = ph_onehot + [
            k_remaining / 10.0,
            score_margin_signed / 10.0,
            float(p_meeples_free[root_player]),
            float(p_meeples_free[opp]),
        ]

        teacher_best = max(aq, key=lambda k: aq[k]) if aq else -1

        seen = set()
        feats, oqs, lqs, aids = [], [], [], []
        for a in legal:
            a = int(a)
            if a not in aq:
                continue
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

            # Tier-2 action/move semantics ----------------------------------- #
            net_meeple_delta_self = float(cstate.meeples[root_player] - p_meeples_free[root_player])
            imm_score_delta_self = float(cstate.scores[root_player] - p_scores[root_player])
            imm_score_delta_opp = float(cstate.scores[opp] - p_scores[opp])
            n_placed_parent = len(pstate.placed_meeples[root_player])
            n_placed_child = len(cstate.placed_meeples[root_player])
            meeple_placed = 1.0 if n_placed_child > n_placed_parent else 0.0
            mtype_city = mtype_road = mtype_farm = mtype_monastery = 0.0
            if meeple_placed:
                pset = set((mp.coordinate_with_side.coordinate.row,
                            mp.coordinate_with_side.coordinate.column,
                            mp.coordinate_with_side.side, mp.meeple_type)
                           for mp in pstate.placed_meeples[root_player])
                newmp = None
                for mp in cstate.placed_meeples[root_player]:
                    key = (mp.coordinate_with_side.coordinate.row,
                           mp.coordinate_with_side.coordinate.column,
                           mp.coordinate_with_side.side, mp.meeple_type)
                    if key not in pset:
                        newmp = mp; break
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

            # Tier-2 structural deltas --------------------------------------- #
            d_total_city_open_edges = float(cstruct["total_city_open_edges"] - pstruct["total_city_open_edges"])
            d_n_open_cities = float(cstruct["n_open_cities"] - pstruct["n_open_cities"])
            d_meeples_locked_self = float(cstruct["n_meeples_locked_self"] - pstruct["n_meeples_locked_self"])
            d_n_contested = float(cstruct["n_cities_contested"] - pstruct["n_cities_contested"])
            opp_touched = float(_opp_feature_touched(pstruct, cstruct, root_player))
            csv, cov, feat_completed = _completed_value(pstruct, cdec, cstruct, cstate, root_player)

            cl034_row = list(Fctx) + [
                # Tier-1 (13)
                leaf_total_div15,
                leaf_q,
                cv29["base"] / 15.0,
                cv29["closure_self"] / 8.0,
                cv29["closure_opp"] / 8.0,
                c_meeple_contrib,
                cv29["pretransform_total"] / 15.0,
                terminal,
                (cv29["base"] - pv29["base"]),
                (cv29["closure_self"] - pv29["closure_self"]),
                (cv29["closure_opp"] - pv29["closure_opp"]),
                (c_meeple_contrib - p_meeple_contrib),
                (cv29["pretransform_total"] - pv29["pretransform_total"]),
                # Tier-2 action/move (8)
                meeple_placed, mtype_city, mtype_road, mtype_farm, mtype_monastery,
                net_meeple_delta_self, imm_score_delta_self, imm_score_delta_opp,
                # Tier-2 child structural (12)
                float(cstruct["n_open_cities"]),
                float(cstruct["n_open_roads"]),
                float(cstruct["n_open_farms"]),
                float(cstruct["total_city_open_edges"]),
                float(cstruct["n_cities_self"]),
                float(cstruct["n_cities_opp"]),
                float(cstruct["n_cities_contested"]),
                float(cstruct["n_meeples_locked_self"]),
                float(cstruct["n_meeples_locked_opp"]),
                float(cstruct["max_open_city_value_self"]) / 8.0,
                float(cstruct["n_farms_self"]),
                float(cstruct["n_farms_contested"]),
                # Tier-2 structural deltas (8)
                d_total_city_open_edges, d_n_open_cities, d_meeples_locked_self,
                d_n_contested, opp_touched, float(feat_completed),
                csv / 8.0, cov / 8.0,
            ]
            assert len(cl034_row) == 50

            # --- bag histogram (32) ----------------------------------------- #
            bag = bag_histogram(cstate).astype(np.float32).tolist()

            # --- deck-odds (7) ---------------------------------------------- #
            placed_tile = _placed_tile(pstate, cstate)
            do_row = _deck_odds(cstate, cdec, cstruct, root_player, placed_tile)

            row = cl034_row + bag + do_row
            assert len(row) == N_FEAT
            feats.append(np.asarray(row, dtype=np.float32))
            oqs.append(aq[a])
            lqs.append(float(leaf_q))
            aids.append(a)

        if len(oqs) < 2:
            return {"_error": f"{seed}:{ply} <2 mapped children"}
        feats = np.stack(feats)
        if not np.isfinite(feats).all():
            return {"_error": f"{seed}:{ply} non-finite feat"}
        return {
            "seed": seed, "ply": ply, "phase": phase,
            "q_gap": float(rec.get("q_gap_1_2", 0.0)),
            "legal_n": int(rec.get("legal_n", legal.size)),
            "feat": feats,
            "oracle_q": np.asarray(oqs, dtype=np.float32),
            "leaf_q": np.asarray(lqs, dtype=np.float32),
            "action_id": np.asarray(aids, dtype=np.int32),
            "teacher_best": int(teacher_best),
        }
    except Exception as e:
        import traceback
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}",
                "_tb": traceback.format_exc()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--out", default="/home/doctor/carc_step2_pens/dataset")
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfg = _provenance_guard()
    print(f"[schema] D={N_FEAT} = 50 CL-034 + 32 bag + 7 deck-odds")
    print("[deck-odds names]", DECKODDS_FEAT_NAMES)

    checks = {}
    for line in open(args.pool):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.probe):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]; recs.append(r)
    n_avail = len(recs)
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)}/{n_avail} sibling sets  workers={args.workers}  D={N_FEAT}")

    t0 = time.time()
    FEAT, OQ, LQ, AID, GID, GS, PLY, PH, GAP, LEGN, ISBEST = [], [], [], [], [], [], [], [], [], [], []
    gid = 0; nerr = 0; nrow = 0; sample_errs = []
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for i, out in enumerate(pool.imap_unordered(_process, recs, chunksize=8)):
            if "_error" in out:
                nerr += 1
                if len(sample_errs) < 8:
                    sample_errs.append(out["_error"])
                    if "_tb" in out and len(sample_errs) <= 2:
                        print(out["_tb"])
                continue
            m = out["feat"].shape[0]
            FEAT.append(out["feat"]); OQ.append(out["oracle_q"]); LQ.append(out["leaf_q"])
            AID.append(out["action_id"])
            is_best = (out["action_id"] == out["teacher_best"]).astype(np.int8)
            ISBEST.append(is_best)
            GID.append(np.full(m, gid, np.int32)); GS.append(np.full(m, out["seed"], np.int64))
            PLY.append(np.full(m, out["ply"], np.int16)); GAP.append(np.full(m, out["q_gap"], np.float32))
            LEGN.append(np.full(m, out["legal_n"], np.int16))
            PH.append(np.array([out["phase"]] * m, dtype="<U12"))
            gid += 1; nrow += m
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)} groups={gid} rows={nrow} err={nerr} {time.time()-t0:.0f}s")
    dt = time.time() - t0
    print(f"[done] groups={gid} rows={nrow} err={nerr} in {dt:.0f}s ({len(recs)/max(dt,1):.0f}/s)")
    if sample_errs:
        print("  sample errors:", sample_errs)

    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)
    feat = np.concatenate(FEAT).astype(np.float16)   # f16 per spec (big-ish dataset)
    gs = np.concatenate(GS)
    oracle_q = np.concatenate(OQ).astype(np.float32)
    leaf_q = np.concatenate(LQ).astype(np.float32)
    group_id = np.concatenate(GID).astype(np.int32)
    phase = np.concatenate(PH)

    # per-column normalization (mean/std over the BUILT rows, computed in f32).
    feat32 = feat.astype(np.float32)
    col_mean = feat32.mean(axis=0)
    col_std = feat32.std(axis=0)
    col_std[col_std < 1e-6] = 1.0  # guard constant columns (one-hots etc.)

    np.savez_compressed(
        outd / "aux_step2.npz",
        child_scalars=feat,                          # (n, D) f16
        oracle_q=oracle_q, leaf_q=leaf_q,            # (n,) f32
        group_id=group_id,                           # (n,) i32
        game_seed=gs.astype(np.int64),               # (n,) i64
        phase=phase.astype("<U12"),                  # (n,) <U12
        action_id=np.concatenate(AID).astype(np.int32),
        ply=np.concatenate(PLY).astype(np.int16),
        q_gap=np.concatenate(GAP).astype(np.float32),
        legal_n=np.concatenate(LEGN).astype(np.int16),
        is_teacher_best=np.concatenate(ISBEST).astype(np.int8),
        feat_names=np.array(FEAT_NAMES, dtype="<U64"),
        col_mean=col_mean.astype(np.float32), col_std=col_std.astype(np.float32),
    )
    meta = {
        "n_rows": int(nrow), "n_groups": int(gid), "n_groups_avail": int(n_avail),
        "D": int(N_FEAT),
        "n_games": int(len(set(gs.tolist()))),
        "feat_names": FEAT_NAMES,
        "n_cl034": 50, "n_bag": 32, "n_deck_odds": 7,
        "deck_odds_names": DECKODDS_FEAT_NAMES,
        "teacher": "h6400_v2.9", "leaf": "v2.9_bmild_cap8", "v29_hash": FROZEN_V29_HASH,
        "leaf_config_hash": _cfg_hash(cfg),
        "source": args.probe, "pool": args.pool, "n_err": int(nerr),
        "normalization": {"scheme": "per-column z-score (mean/std over built rows)",
                          "stored_in_npz": ["col_mean", "col_std"]},
        "deck_odds_approx": ("completer copies = #remaining tiles with >=1 cardinal "
                             "edge of the terrain (leaf _deck_city_supply permissive "
                             "proxy, per-feature); DECK-ONLY (remaining multiset + "
                             "open-edge terrain), no future-play projection. #53 is "
                             "exact hypergeometric P(>=1 completer in remaining draws)."),
        "schema": "PeNS_SCHEMA.md group F #48-54",
    }
    (outd / "meta.json").write_text(json.dumps(meta, indent=2))
    print("meta:", {k: v for k, v in meta.items() if k not in ("feat_names",)})
    print(f"[out] {outd/'aux_step2.npz'}  child_scalars.shape={feat.shape}")
    print("[feature manifest]")
    for i, nm in enumerate(FEAT_NAMES):
        print(f"  {i:2d} {nm}")


if __name__ == "__main__":
    main()
