#!/usr/bin/env python3
"""Value/Search Autopsy — I5: classical HeuristicMCTS@N on the v2.9 leaf (NET-FREE).

Runs HeuristicMCTS at a chosen sim budget on the SAME v2.9 leaf the teacher uses, over
the miss-probe roots, and records the same row schema as miss_harness (searched move,
visit share on h6400 top, h6400-Q regret). The teacher itself is HeuristicMCTS@6400, so
this isolates: at matched budget (h@200), does CLASSICAL search alone match the neural
NMCTS@200? And does classical SEARCH BUDGET (h@200 -> h@800 -> h@6400) recover h6400's
move? If classical@200 ≈ neural@200, the net adds nothing over the leaf+search
(Decision D/F); if classical budget recovers the move that neural sims do not, the edge
is deeper classical search, not neural guidance (Decision F).

ckpt name is 'h{sims}' so agg_miss compare/classify treat it like any other leg.
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
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.mcts import HeuristicMCTS

_CFG: dict = {}
_W: dict = {}


def _worker_init():
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    _W["cfg"] = EH._heur_leaf_cfg(2.0)


def _deduped(root):
    out, seen = [], set()
    for a in sorted(root.children):
        c = root.children[a]
        if id(c) in seen:
            continue
        seen.add(id(c))
        out.append((a, c))
    return out


def _process(rec):
    try:
        seed = int(rec["seed"]); sims = _CFG["sims"]
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        teacher_best = int(rec["teacher_best"]); q_best = float(rec["q_best"])
        game, board = replay_to(seed, rec["ply"])
        m = HeuristicMCTS(game=game, simulations=sims, seed=seed * 13 + 1,
                          heur_leaf="v2_7", leaf_cfg=_W["cfg"])
        m.clear(); m.search(board)
        top = int(m.best_action(board))
        rk = game.string_representation(board)
        root = m._nodes[rk]
        sn = {}
        for a, c in _deduped(root):
            sn[int(a)] = int(c.N)
        tot = sum(sn.values()) or 1
        regret = q_best - aq.get(top, min(aq.values()))
        return {
            "ckpt": f"h{sims}", "seed": seed, "ply": rec.get("ply"),
            "phase": rec.get("phase"), "k_remaining": rec.get("k_remaining"),
            "score_margin_abs": rec.get("score_margin_abs"), "legal_n": rec.get("legal_n"),
            "teacher_best": teacher_best, "q_best": round(q_best, 6),
            "q_gap_1_2": rec.get("q_gap_1_2"), "sims": sims, "prior": "classical",
            "nmcts_top": top, "nmcts_top_eq_teacher": (top == teacher_best),
            "teacher_best_N": sn.get(teacher_best, 0), "nmcts_top_N": sn.get(top, 0),
            "total_N": tot,
            "teacher_best_visit_share": round(sn.get(teacher_best, 0) / tot, 5),
            "nmcts_top_visit_share": round(sn.get(top, 0) / tot, 5),
            "regret": round(regret, 6),
        }
    except Exception as e:
        return {"_error": f"{rec.get('seed')}: {type(e).__name__}: {e}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True, help="comma-list of probe.jsonl")
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--gap-min", type=float, default=0.0, help="prefilter q_gap_1_2 >= this")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    _CFG["sims"] = args.sims
    recs = []
    for p in args.probe.split(","):
        for line in open(p):
            d = json.loads(line)
            if args.gap_min and float(d.get("q_gap_1_2", 0.0)) < args.gap_min:
                continue
            recs.append(d)
    print(f"[classical] h{args.sims}_v2.9 x {len(recs)} roots W={args.workers}", flush=True)
    t0 = time.perf_counter()
    out = open(args.out, "w"); nrow = nerr = 0
    with get_context("fork").Pool(args.workers, initializer=_worker_init) as pool:
        for i, r in enumerate(pool.imap_unordered(_process, recs, chunksize=1)):
            if "_error" in r:
                nerr += 1
            else:
                out.write(json.dumps(r) + "\n"); nrow += 1
            if (i + 1) % 200 == 0:
                el = time.perf_counter() - t0
                print(f"  {i+1}/{len(recs)} ({el/(i+1):.2f}s/root)", flush=True)
    out.close()
    print(f"[classical] {nrow} rows, {nerr} err, {(time.perf_counter()-t0)/60:.1f} min -> {args.out}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
