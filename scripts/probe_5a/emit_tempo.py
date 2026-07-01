#!/usr/bin/env python3
"""Probe §5A — tempo/timing feature emitter (gate-zero + arm inputs).

Emits a per-child TEMPO feature block aligned to the CL-037 dataset
(/home/doctor/carc_step1_gate/dataset_both). Reuses step1_dump.py's EXACT child
enumeration (same replay_to / legal order / `a in aq` teacher-Q filter / `seen`
dedup) so rows align 1:1 by (game_seed, ply, within-root order). Recomputes `leaf`
(== dataset leaf_q) so the align step can PROVE the join bit-exactly.

Design note (why these features, not raw counts): the CL-037 base 12 aux scalars
ALREADY include free-meeple counts (cols 0,1) and tiles-remaining (col 5), and the
blind "none" arm carrying them was INERT (+1.9%). Finished city/road features also
auto-return their meeples, so raw "committed" count is ~a linear function of col 0.
The genuinely-novel tempo axis is therefore the DEPTH-weighted lockup (how far each
locked meeple is from freeing, Σ open_n) + the contested closure-race, none of which
cols 0-11 can express. We emit those; gate-zero (gate_zero.py) residualizes against
the already-present representation and decides PASS/PARTIAL/FAIL.

NET-FREE, CPU-parallel. Writes <out>/tempo.npz.
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

import argparse, json, math, sys, time
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
from carcassonne_ai.flat_leaf import decompose
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

HG = REPO / "measurement" / "high_gap_distillation"

TEMPO_NAMES = [
    "lockup_self", "lockup_opp", "lockup_diff",
    "lockup_depth_self", "lockup_depth_opp", "lockup_depth_diff",
    "open_city_count", "open_road_count",
    "open_city_delta_self", "open_city_delta_opp",
    "contested_open_count", "closure_race_diff",
    "farmers_self", "farmers_opp",
]
FARMSUM_NAMES = ["n_farm_comp", "total_farm_tiles", "farm_city_adj", "farm_finished_cities"]

_W: dict = {}


def _worker_init():
    _W["cfg"] = EH._heur_leaf_cfg(2.0)
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)


def _tempo_features(state, root_player):
    """Novel structural-tempo scalars (POV = root_player). See module docstring."""
    d = decompose(state)
    board = state.board
    opp = 1 - root_player
    # --- meeple ownership walk (mirrors flat_leaf._final_scores, no big meeples) ---
    city_counts: dict = {}   # root -> [n_self, n_opp]
    road_counts: dict = {}
    farm_counts: dict = {}
    for player in range(2):
        slot = 0 if player == root_player else 1
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row; c = cws.coordinate.column; side = cws.side
            terrain = board[r][c].get_type(side)
            if terrain == TerrainType.CITY:
                root = d.city_side_root.get((r, c, side))
                if root is not None:
                    city_counts.setdefault(root, [0, 0])[slot] += 1
            elif terrain == TerrainType.ROAD:
                root = d.road_side_root.get((r, c, side))
                if root is not None:
                    road_counts.setdefault(root, [0, 0])[slot] += 1
            elif mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                root = d.farm_pos0_root.get((r, c, side))
                if root is not None:
                    farm_counts.setdefault(root, [0, 0])[slot] += 1

    lockup_s = lockup_o = 0
    depth_s = depth_o = 0
    delta_s = delta_o = 0.0
    contested = 0
    race = 0.0
    open_city = sum(1 for root, fin in d.city_root_finished.items() if not fin)
    open_road = sum(1 for root, fin in d.road_root_finished.items() if not fin)

    for root, (ns, no) in city_counts.items():
        if d.city_root_finished.get(root, False):
            continue  # finished cities keep no meeples in practice; skip defensively
        lockup_s += ns; lockup_o += no
        open_n = int(d.city_root_open_n.get(root, 0))
        delta = float(d.city_root_delta.get(root, 0))
        if ns > 0:
            depth_s += open_n
        if no > 0:
            depth_o += open_n
        if ns > no:
            delta_s += delta
        elif no > ns:
            delta_o += delta
        if ns > 0 and no > 0:
            contested += 1
        # closure-race: value at stake, signed by who leads, weighted by proximity
        lead = (1 if ns > no else -1 if no > ns else 0)
        race += lead * delta / max(1, open_n)

    for root, (ns, no) in road_counts.items():
        if d.road_root_finished.get(root, False):
            continue
        lockup_s += ns; lockup_o += no
        if ns > 0 and no > 0:
            contested += 1

    farmers_s = sum(v[0] for v in farm_counts.values())
    farmers_o = sum(v[1] for v in farm_counts.values())

    tempo = [
        float(lockup_s), float(lockup_o), float(lockup_s - lockup_o),
        float(depth_s), float(depth_o), float(depth_s - depth_o),
        float(open_city), float(open_road),
        float(delta_s), float(delta_o),
        float(contested), float(race),
        float(farmers_s), float(farmers_o),
    ]
    # farm-summary scalars (reduce the farm axis to scalars for gate-zero's FB block)
    n_farm = len(d.farm_root_keys)
    total_farm_tiles = sum(len({(r, c) for (r, c, _fc) in keys})
                           for keys in d.farm_root_keys.values())
    farm_city_adj = sum(len(v) for v in d.farm_root_adj_city_roots.values())
    farm_fin_cities = sum(int(v) for v in d.farm_root_finished_cities.values())
    farmsum = [float(n_farm), float(total_farm_tiles), float(farm_city_adj), float(farm_fin_cities)]
    return tempo, farmsum


def _process(rec):
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game, board = replay_to(seed, ply)
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        cfg = _W["cfg"]
        root_player = board.state.current_player
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}
        seen = set()
        tempo_l, farm_l, leaf_l = [], [], []
        for a in legal:
            a = int(a)
            if a not in aq:
                continue
            child, _ = game.get_next_state(board, a)
            cs = game.string_representation(child)
            if cs in seen:
                continue
            seen.add(cs)
            ended = game.get_game_ended(child, root_player)
            if ended != 0:
                leaf = max(-1.0, min(1.0, float(ended)))
            else:
                leaf = math.tanh(virtual_score_v2(child.state, root_player, cfg) / 15.0)
            tempo, farmsum = _tempo_features(child.state, root_player)
            tempo_l.append(tempo); farm_l.append(farmsum); leaf_l.append(float(leaf))
        if len(leaf_l) < 2:
            return {"_error": f"{seed}:{ply} <2 mapped children"}
        return {
            "seed": seed, "ply": ply,
            "tempo": np.asarray(tempo_l, dtype=np.float32),
            "farm": np.asarray(farm_l, dtype=np.float32),
            "leaf": np.asarray(leaf_l, dtype=np.float32),
        }
    except Exception as e:
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qprobe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--out", default="/home/doctor/carc_step1_gate/tempo_5a")
    ap.add_argument("--workers", type=int, default=28)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)

    checks = {}
    for line in open(args.pool):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.qprobe):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]; recs.append(r)
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)} sibling sets workers={args.workers} -> {outd}", flush=True)

    TEMPO, FARM, LEAF, GS, PLY, CIDX = [], [], [], [], [], []
    nerr = nrow = 0
    t0 = time.time()
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for i, rec in enumerate(pool.imap_unordered(_process, recs, chunksize=8)):
            if "_error" in rec:
                nerr += 1
                continue
            m = rec["tempo"].shape[0]
            TEMPO.append(rec["tempo"]); FARM.append(rec["farm"]); LEAF.append(rec["leaf"])
            GS.append(np.full(m, rec["seed"], np.int64))
            PLY.append(np.full(m, rec["ply"], np.int16))
            CIDX.append(np.arange(m, dtype=np.int32))   # within-root order index
            nrow += m
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)} rows={nrow} err={nerr} {time.time()-t0:.0f}s", flush=True)
    dt = time.time() - t0
    print(f"[done] rows={nrow} err={nerr} in {dt:.0f}s", flush=True)

    np.savez(
        outd / "tempo.npz",
        tempo=np.concatenate(TEMPO), farm_summary=np.concatenate(FARM),
        leaf=np.concatenate(LEAF), game_seed=np.concatenate(GS),
        ply=np.concatenate(PLY), child_index=np.concatenate(CIDX),
        tempo_names=np.array(TEMPO_NAMES), farmsum_names=np.array(FARMSUM_NAMES),
    )
    print(f"[saved] {outd/'tempo.npz'} rows={nrow}", flush=True)


if __name__ == "__main__":
    main()
