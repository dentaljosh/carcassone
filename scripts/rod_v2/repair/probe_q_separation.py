#!/usr/bin/env python3
"""Pivot diagnostic: on DISAGREEMENT (hard) states, how separated are h6400's root
child Q-values? best_action ranks by Q (visits flat), so the learnable signal — if
any — is the Q gap between the best move and the rest. If Q(1st)-Q(2nd) is tiny, the
argmax is a near-tie (noise); the 'hard = h3200≠h6400' filter selects LOW-signal
states, not deep-distinctive ones. Also: does Q-best == most-visited? (visits flat =>
often no)."""
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
import sys, json, argparse
from pathlib import Path
from multiprocessing import get_context
import numpy as np
REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.mcts import HeuristicMCTS
_W = {}

def _init():
    _W["cfg"] = EH._heur_leaf_cfg(2.0)

def _probe(rec):
    try:
        game, board = replay_to(rec["seed"], rec["ply"])
        m = HeuristicMCTS(game=game, simulations=rec.get("_sims", 6400),
                          seed=rec["seed"]*13+6400, heur_leaf="v2_7", leaf_cfg=_W["cfg"])
        m.clear(); m.search(board)
        rk = game.string_representation(board)
        root = m._nodes[rk]
        rows = []
        _seen = set()
        for a in sorted(root.children):
            c = root.children[a]
            if c.N <= 0 or id(c) in _seen:
                continue
            _seen.add(id(c))
            q = c.Q if c.player_to_move == root.player_to_move else -c.Q
            rows.append((int(a), float(q), int(c.N)))
        if len(rows) < 2:
            return None
        rows.sort(key=lambda t: (-t[1], -t[2]))           # by adjusted Q
        qs = np.array([r[1] for r in rows]); ns = np.array([r[2] for r in rows])
        qbest_a = rows[0][0]
        mostvis_a = max(rows, key=lambda t: t[2])[0]
        return {
            "phase": rec.get("phase"), "legal_n": rec.get("legal_n"),
            "nchild": len(rows),
            "q_gap_1_2": float(qs[0]-qs[1]),
            "q_gap_1_med": float(qs[0]-np.median(qs)),
            "q_std": float(qs.std()), "q_range": float(qs[0]-qs[-1]),
            "qbest_eq_mostvisited": int(qbest_a == mostvis_a),
            "topN_share": float(ns.max()/ns.sum()),
        }
    except Exception as e:
        return {"_error": f"{rec.get('gen_id')}: {type(e).__name__}: {e}"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(REPO/"measurement/hard_policy_repair/manifest_test.jsonl"))
    ap.add_argument("--ordinary", default=str(REPO/"measurement/hard_policy_repair/manifest_ordinary.jsonl"))
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    _init.__call__ if False else None
    def run(path, label, n):
        recs = [json.loads(l) for l in open(path)][:n]
        ctx = get_context("fork")
        out = []
        with ctx.Pool(args.workers, initializer=_init) as pool:
            for r in pool.imap_unordered(_probe, recs):
                if r and "_error" not in r:
                    out.append(r)
        if not out:
            print(f"{label}: no rows"); return
        def col(k): return np.array([r[k] for r in out], float)
        print(f"\n== {label} (n={len(out)}) ==")
        print(f"  Q gap best-2nd:   mean {col('q_gap_1_2').mean():.4f}  median {np.median(col('q_gap_1_2')):.4f}")
        print(f"  Q gap best-median:mean {col('q_gap_1_med').mean():.4f}  median {np.median(col('q_gap_1_med')):.4f}")
        print(f"  Q std over children: mean {col('q_std').mean():.4f}")
        print(f"  Q range best-worst:  mean {col('q_range').mean():.4f}")
        print(f"  best_action == most_visited: {col('qbest_eq_mostvisited').mean():.2f} (1.0=visits track Q)")
        print(f"  top visit share: mean {col('topN_share').mean():.3f}")
    run(args.manifest, "HARD (h3200!=h6400) test states", args.n)
    run(args.ordinary, "ORDINARY (agreement) states", args.n)

if __name__ == "__main__":
    raise SystemExit(main())
