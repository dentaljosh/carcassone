#!/usr/bin/env python3
"""Verify the snapshot==standalone equivalence holds all the way up to h12800.

The pilot proved it at h200; this certifies the multi-depth snapshot infra for DEEP references
(h6400 / h12800). For a random sample of real MCTS-play roots, assert that one HeuristicMCTS(12800)
search snapshotted at {200,1600,6400,12800} reproduces a standalone L-sim search's root child
N-distribution, bit-for-bit, at EVERY level. Net-free, frozen v2.9 leaf.
"""
from __future__ import annotations
import os
for _k, _v in {"CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
               "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
               "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
               "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_USE_FLAT_LEAF": "1",
               "CARCASSONNE_USE_CY_REPR": "1", "CARCASSONNE_V25_VALUE_BLEND": "0",
               "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
    os.environ[_k] = _v

import argparse, json, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import snapshot as SNAP                       # noqa: E402
from root_replay import load_games            # noqa: E402

LEVELS = [200, 1600, 6400, 12800]
_W: dict = {}


def _worker_init(games):
    _W["cfg"] = SNAP.frozen_v29_cfg()
    _W["games"] = games


def _verify_one(root):
    from root_replay import replay_actions
    seed = int(root["deck_seed"]); ply = int(root["ply"]); gid = int(root["game_id"])
    _, board = replay_actions(seed, _W["games"][gid], ply)
    cfg = _W["cfg"]
    res = SNAP.verify_equivalence(
        make_agent=lambda sims, s: SNAP.make_heuristic_agent(sims, cfg, seed=s),
        board=board, levels=LEVELS, mcts_seed=(seed * 1_000_003 + ply) & 0x7fffffff)
    return {"game_id": gid, "ply": ply,
            "all_match": all(res[L]["match"] for L in LEVELS),
            "per_level": {L: bool(res[L]["match"]) for L in LEVELS}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", default=str(HERE.parents[1] / "measurement" /
                                           "post_search_residual" / "data" / "games_mcts.jsonl"))
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    t0 = time.time()

    games = load_games(args.games)
    games_dict = {g.game_id: g.actions for g in games}
    rng = np.random.default_rng(args.seed)
    roots = []
    for _ in range(args.n):
        g = games[rng.integers(len(games))]
        ply = int(rng.integers(4, g.n_plies - 3))
        roots.append({"game_id": g.game_id, "deck_seed": g.deck_seed, "ply": ply})
    print(f"[verify h12800] {len(roots)} random roots, levels={LEVELS}, {args.workers} workers")

    ctx = get_context("fork")
    out = []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=(games_dict,)) as pool:
        for r in pool.imap_unordered(_verify_one, roots):
            out.append(r)
            print(f"  game {r['game_id']} ply {r['ply']}: all_match={r['all_match']} {r['per_level']}")
    n_match = sum(r["all_match"] for r in out)
    dt = time.time() - t0
    print(f"\n[result] {n_match}/{len(out)} roots: snapshot == standalone at ALL of {LEVELS} "
          f"in {dt:.0f}s")
    verdict = "PASS" if n_match == len(out) else "FAIL"
    print(f"[verify h12800] {verdict}")
    res_path = HERE.parents[1] / "measurement" / "post_search_residual" / "h12800_verify.json"
    res_path.write_text(json.dumps({"levels": LEVELS, "n": len(out), "n_match": n_match,
                                    "verdict": verdict, "roots": out}, indent=2))
    print(f"[write] {res_path}")
    sys.exit(0 if verdict == "PASS" else 2)


if __name__ == "__main__":
    main()
