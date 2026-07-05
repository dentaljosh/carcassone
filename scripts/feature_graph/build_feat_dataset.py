#!/usr/bin/env python3
"""Feature-Graph Action Comparator Pilot — Stage 1 dataset builder (Level A).

Fork of scripts/rod_v2/value_resurrection/dump_dataset.py.  For each
TEACHER-VISITED canonical child of each root (the SAME id-deduped enumeration the
leaf-audit / value-resurrection dumps used), computes the Level-A tabular
feature vector defined in
  measurement/feature_graph_comparator/FEATURE_GRAPH_SCHEMA.md
(Group F context · Tier-1 leaf-components · Tier-2 structural+action), in the
SCHEMA's fixed order, scaled (/10, /15, /8) so a linear model is well-conditioned.

The enumeration is bit-identical to dump_dataset.py / leaf_audit.py (same env, same
EH._heur_leaf_cfg(2.0) cfg, same canonical-child set keyed by string_representation,
teacher-visited only) so the labels align AND the built-in leaf-audit gate below
reproduces measurement/value_resurrection_pilot/data/leaf_audit_summary.json.

Parent decompose / decompose_v29 are computed ONCE per root and reused across
siblings; the per-child marginal cost is one child decompose pair + a leaf eval.

NET-FREE, CPU-parallel.  Writes <out>/rows_feat.npz + meta.json.

The built-in CORRECTNESS GATE (validate_dataset.py, also runnable standalone)
re-derives the leaf-audit aggregate from the BUILT rows and asserts it reproduces
the reference (top1 0.455 / tau 0.895 / n_gap002_and_regret002 1197).
"""
from __future__ import annotations
import os
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

import argparse, dataclasses as dc, hashlib, json, math, random, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.virtual_score_v2 import virtual_score_v2
from carcassonne_ai.flat_leaf import decompose
from carcassonne_ai.leaf_v29 import decompose_v29
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.meeple_type import MeepleType

HG = REPO / "measurement" / "high_gap_distillation"
FROZEN_V29_HASH = "7fc930b82801cb43"
_FARMER_TYPES = (MeepleType.FARMER, MeepleType.BIG_FARMER)
_W: dict = {}

# ---------------------------------------------------------------------------- #
# Feature ordering (THE canonical fixed order; SCHEMA Level A).  Stored in npz.
# ---------------------------------------------------------------------------- #
PHASES = ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]
FEAT_NAMES = [
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
N_FEAT = len(FEAT_NAMES)


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


# ---------------------------------------------------------------------------- #
# Structural summary of a board from its Decomp + placed meeples (root-POV).
# self = root_player, opp = 1-root_player.
# ---------------------------------------------------------------------------- #
def _struct_summary(state, decomp, root_player):
    """Returns a dict of structural facts used by Tier-2 (child or parent)."""
    opp = 1 - root_player
    # ---- city / road / farm open counts -----------------------------------
    n_open_cities = sum(1 for fin in decomp.city_root_finished.values() if not fin)
    n_open_roads = sum(1 for fin in decomp.road_root_finished.values() if not fin)
    n_open_farms = len(decomp.farm_root_keys)
    total_city_open_edges = sum(decomp.city_root_open_n.values())

    # ---- meeple ownership maps --------------------------------------------
    # per city root -> {player: weighted meeple count}
    city_owner: dict = {}
    road_owner: dict = {}
    farm_owner: dict = {}
    locked_self = 0   # meeples (weight) on UNFINISHED city/road/farm/cloister, self
    locked_opp = 0
    board = state.board
    for pl in range(state.players):
        slot = pl
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
                # cloister: locked while the 3x3 is not full (open). Approx: count
                # as locked self/opp (cloisters resolve at end; treat as locked).
                if pl == root_player: locked_self += w
                else: locked_opp += w
            elif mp.meeple_type in _FARMER_TYPES:
                root = decomp.farm_pos0_root.get((r, c, side))
                if root is not None:
                    farm_owner.setdefault(root, {})[pl] = farm_owner.get(root, {}).get(pl, 0) + w
                    # farms are never "finished"/returned -> always locked
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

    # max open city value self: largest city_root_delta over OPEN cities the root
    # player owns (>=1 self meeple).
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
        # auxiliary sets for delta features
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
    """Points to self/opp from features NEWLY finished by this move.
    A move can close at most one city/road (the placed tile completes it). We
    detect newly-finished city/road roots in the CHILD whose component coords did
    NOT form a finished component in the parent, and award their points to the
    meeple-winner on the child component."""
    opp = 1 - root_player
    pd = parent_struct["_decomp"]
    cd = child_decomp
    board = state_child.board
    cself = copp = 0
    feature_completed = 0
    # cities newly finished in child
    # represent parent finished cities by a set of frozenset(coords)
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
        pts = cd.city_root_delta.get(root, 0)  # finished -> delta == full city points
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
        # road points: 1 per tile (or 2 if inn); use _road_points via coords
        from carcassonne_ai.flat_leaf import _road_points
        pts = _road_points(cd.road_root_coords[root], True, board)
        if root_player in winners: cself += pts
        if opp in winners: copp += pts
    return cself, copp, feature_completed


def _opp_feature_touched(parent_struct, child_struct, root_player):
    """1 if the move modified (extended/blocked) a feature the OPP owned in the
    parent — detected by an opp-owned city/road/farm component whose member set
    differs between parent and child (coords grew) or whose closure changed."""
    # compare opp-owned city/road open_n & coords between parent and child decomp.
    pd = parent_struct["_decomp"]; cd = child_struct["_decomp"]
    opp = 1 - root_player
    # opp-owned city roots in parent: map coords->open_n
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
    # if any parent opp-city coords-set is no longer present unchanged in child -> touched
    for coords, st in pc.items():
        if coords not in cc:        # grew/merged -> touched
            return 1
        if cc[coords] != st:        # closure/open_n changed -> touched
            return 1
    pr = _opp_road_state(parent_struct, pd)
    cr = _opp_road_state(child_struct, cd)
    for coords, st in pr.items():
        if coords not in cr or cr[coords] != st:
            return 1
    return 0


def _kendall_tau(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    c = d = 0
    for i in range(n):
        xi, yi = xs[i], ys[i]
        for j in range(i + 1, n):
            s = (xi - xs[j]) * (yi - ys[j])
            if s > 0: c += 1
            elif s < 0: d += 1
    tot = c + d
    return (c - d) / tot if tot else None


def _process(rec):
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game, board = replay_to(seed, ply)
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        cfg = _W["cfg"]; gf = _W["game"]
        pstate = board.state
        root_player = pstate.current_player
        opp = 1 - root_player
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}

        # ---- parent decompositions (ONCE per root) -------------------------
        pdec = decompose(pstate)
        pv29 = decompose_v29(pstate, root_player, cfg)
        pstruct = _struct_summary(pstate, pdec, root_player)
        p_scores = pstate.scores
        p_meeples_free = pstate.meeples
        p_meeple_contrib = pv29["meeple_flat"] + pv29["meeple_curve_delta"]

        # ---- context (Group F, constant across siblings) -------------------
        phase = rec.get("phase", "?")
        k_remaining = float(rec.get("k_remaining", 0))
        score_margin_signed = float(p_scores[root_player] - p_scores[opp])
        ph_onehot = [1.0 if phase == p else 0.0 for p in PHASES]
        F = ph_onehot + [
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

            # leaf_total feature: for terminal use leaf_q*15 stand-in -> keep
            # leaf_total_div15 == leaf_q at terminal (tanh saturated); use vs/15 else.
            leaf_total_div15 = (leaf_total_raw / 15.0) if leaf_total_raw is not None else leaf_q

            # ---- Tier-2 action/move semantics ------------------------------
            net_meeple_delta_self = float(cstate.meeples[root_player] - p_meeples_free[root_player])
            imm_score_delta_self = float(cstate.scores[root_player] - p_scores[root_player])
            imm_score_delta_opp = float(cstate.scores[opp] - p_scores[opp])
            # meeple placed this move? compare placed_meeples count for the MOVER
            # (mover == root_player in this engine, verified leaf_audit).
            n_placed_parent = len(pstate.placed_meeples[root_player])
            n_placed_child = len(cstate.placed_meeples[root_player])
            meeple_placed = 1.0 if n_placed_child > n_placed_parent else 0.0
            mtype_city = mtype_road = mtype_farm = mtype_monastery = 0.0
            if meeple_placed:
                # the newly-placed meeple is the one in child not in parent
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

            # ---- Tier-2 structural deltas ----------------------------------
            d_total_city_open_edges = float(cstruct["total_city_open_edges"] - pstruct["total_city_open_edges"])
            d_n_open_cities = float(cstruct["n_open_cities"] - pstruct["n_open_cities"])
            d_meeples_locked_self = float(cstruct["n_meeples_locked_self"] - pstruct["n_meeples_locked_self"])
            d_n_contested = float(cstruct["n_cities_contested"] - pstruct["n_cities_contested"])
            opp_touched = float(_opp_feature_touched(pstruct, cstruct, root_player))
            csv, cov, feat_completed = _completed_value(pstruct, cdec, cstruct, cstate, root_player)

            row = list(F) + [
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
    ap.add_argument("--qprobe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--out", default=str(REPO / "measurement" / "feature_graph_comparator" / "data"))
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfg = _provenance_guard()

    checks = {}
    for line in open(args.pool):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.qprobe):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]; recs.append(r)
    n_avail = len(recs)
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)}/{n_avail} sibling sets  workers={args.workers}  n_feat={N_FEAT}")

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
    feat = np.concatenate(FEAT)
    gs = np.concatenate(GS)
    np.savez_compressed(
        outd / "rows_feat.npz",
        feat=feat,
        oracle_q=np.concatenate(OQ), leaf_q=np.concatenate(LQ),
        group_id=np.concatenate(GID), action_id=np.concatenate(AID),
        game_seed=gs, ply=np.concatenate(PLY), phase=np.concatenate(PH),
        q_gap=np.concatenate(GAP), legal_n=np.concatenate(LEGN),
        is_teacher_best=np.concatenate(ISBEST),
        feat_names=np.array(FEAT_NAMES, dtype="<U40"),
    )
    meta = {
        "n_rows": int(nrow), "n_groups": int(gid), "n_groups_avail": int(n_avail),
        "n_feat": int(N_FEAT),
        "n_games": int(len(set(gs.tolist()))),
        "feat_names": FEAT_NAMES,
        "teacher": "h6400_v2.9", "leaf": "v2.9_bmild_cap8", "v29_hash": FROZEN_V29_HASH,
        "leaf_config_hash": _cfg_hash(cfg),
        "source": args.qprobe, "pool": args.pool, "n_err": int(nerr),
        "scalers": {"score_div": 10, "k_div": 10, "leaf_div": 15, "closure_div": 8,
                    "city_value_div": 8},
        "schema": "FEATURE_GRAPH_SCHEMA.md Level A",
    }
    (outd / "meta.json").write_text(json.dumps(meta, indent=2))
    print("meta:", {k: v for k, v in meta.items() if k != "feat_names"})
    print(f"[out] {outd/'rows_feat.npz'}  shape={feat.shape}")


if __name__ == "__main__":
    main()
