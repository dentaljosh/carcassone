#!/usr/bin/env python3
"""Post-Search Residual — Tier-B structural feature extraction (for Stage 3, if Tier-A fails).

For each MCTS-play root (group_id, game_id, seed, ply) in roots_mcts.jsonl, reconstruct the board
losslessly (replay_actions) and compute ROOT-LEVEL structural features from flat_leaf.decompose +
leaf_v29.decompose_v29 — board-complexity signal (open cities/roads/farms, closure proximity,
farm-city adjacency, the v2.9 value breakdown, score/meeple/tiles context) that the h200-diagnostic
heuristics do NOT have. All state-derived (NO h6400 leakage). Writes features_mcts.jsonl
{group_id, features:{...}}. Net-free, fast (no search).
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

import argparse, json, sys, time
from pathlib import Path
from multiprocessing import get_context

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "post_search_residual"))

import eval_hybrid_handoff as EH                          # noqa: E402
from gen_mcts_selfplay import replay_actions              # noqa: E402
from carcassonne_ai.flat_leaf import decompose            # noqa: E402
from carcassonne_ai.leaf_v29 import decompose_v29         # noqa: E402

DATA = REPO / "measurement" / "post_search_residual" / "data"
_W: dict = {}


def _k_remaining(state):
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def _root_features(state, player):
    opp = 1 - player
    dc = decompose(state)
    # cities
    cfin = dc.city_root_finished
    n_city = len(cfin)
    n_city_open = sum(1 for f in cfin.values() if not f)
    city_open_n_sum = float(sum(dc.city_root_open_n.values()))
    n_city_finished = sum(1 for f in cfin.values() if f)
    # roads
    rfin = dc.road_root_finished
    n_road = len(rfin)
    n_road_open = sum(1 for f in rfin.values() if not f)
    # farms
    n_farm = len(dc.farm_root_keys)
    farm_adj_city_sum = float(sum(len(s) for s in dc.farm_root_adj_city_roots.values()))
    farm_fin_city_sum = float(sum(dc.farm_root_finished_cities.values()))
    # v2.9 value breakdown (root-player POV)
    cfg = _W["cfg"]
    v = decompose_v29(state, player, cfg)
    # context
    k = _k_remaining(state)
    margin = float(state.scores[player] - state.scores[opp])
    m_self = float(state.meeples[player]); m_opp = float(state.meeples[opp])
    return {
        "k_remaining": float(k),
        "score_margin": margin,
        "meeples_free_self": m_self,
        "meeples_free_opp": m_opp,
        "meeples_free_diff": m_self - m_opp,
        "n_city": float(n_city),
        "n_city_open": float(n_city_open),
        "city_open_n_sum": city_open_n_sum,
        "n_city_finished": float(n_city_finished),
        "n_road": float(n_road),
        "n_road_open": float(n_road_open),
        "n_farm": float(n_farm),
        "farm_adj_city_sum": farm_adj_city_sum,
        "farm_fin_city_sum": farm_fin_city_sum,
        "open_structures": float(n_city_open + n_road_open),
        "v29_base": float(v["base"]),
        "v29_closure_self": float(v["closure_self"]),
        "v29_closure_opp": float(v["closure_opp"]),
        "v29_meeple_flat": float(v["meeple_flat"]),
        "v29_meeple_curve_delta": float(v["meeple_curve_delta"]),
        "v29_pretransform": float(v["pretransform_total"]),
    }


def _worker_init(cfg_norm, games):
    _W["cfg"] = EH._heur_leaf_cfg(cfg_norm)
    _W["games"] = games


def _process(root):
    try:
        gid = int(root["group_id"]); seed = int(root["seed"]); ply = int(root["ply"])
        game_id = int(root["game_id"])
        _, board = replay_actions(seed, _W["games"][game_id], ply)
        feats = _root_features(board.state, int(board.state.current_player))
        return {"group_id": gid, "features": feats}
    except Exception as e:
        import traceback
        return {"_error": f"{root.get('group_id')}: {type(e).__name__}: {e}",
                "_tb": traceback.format_exc().splitlines()[-3:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", default=str(DATA / "roots_mcts.jsonl"))
    ap.add_argument("--games-jsonl", default=str(DATA / "games_mcts.jsonl"))
    ap.add_argument("--out", default=str(DATA / "features_mcts.jsonl"))
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    t0 = time.time()

    games = {}
    for line in Path(args.games_jsonl).read_text().splitlines():
        if line.strip():
            g = json.loads(line); games[int(g["game_id"])] = [int(a) for a in g["actions"]]
    roots = []
    for line in Path(args.roots).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("game_id") is None:
                continue
            roots.append({"group_id": int(r["group_id"]), "seed": int(r["seed"]),
                          "ply": int(r["ply"]), "game_id": int(r["game_id"])})
    print(f"[extract] {len(roots)} roots, {len(games)} games, {args.workers} workers")

    ctx = get_context("fork")
    out_path = Path(args.out)
    ok, errs = 0, []
    with out_path.open("w") as fh:
        with ctx.Pool(args.workers, initializer=_worker_init, initargs=(2.0, games)) as pool:
            for i, o in enumerate(pool.imap_unordered(_process, roots, chunksize=16)):
                if "_error" in o:
                    errs.append(o["_error"])
                    if len(errs) <= 3:
                        print("  ERR", o["_error"], o.get("_tb"))
                else:
                    fh.write(json.dumps(o) + "\n"); ok += 1
    print(f"[done] ok={ok} err={len(errs)} in {time.time()-t0:.0f}s -> {out_path}")
    if errs[:3]:
        print("  sample errors:", errs[:3])


if __name__ == "__main__":
    main()
