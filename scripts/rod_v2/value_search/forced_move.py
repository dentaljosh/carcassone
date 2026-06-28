#!/usr/bin/env python3
"""Value/Search Autopsy — I6: forced-move child evaluation (the value/horizon probe).

For each high-gap MISS (baseline NMCTS@200 picked nmcts_top != teacher_best), force the
first move to teacher_best vs nmcts_top and ask what the STATIC v2.9 leaf — the value
NMCTS bottoms out on — says about the two resulting children, vs what h6400 deep search
says (already stored as action_q, free).

Per miss, root-player POV (child is the OPPONENT to move, so root-POV value = -child value):
  Q_T = action_q[teacher_best] = q_best        h6400 deep, root POV   (the "truth")
  Q_N = action_q[nmcts_top]                     h6400 deep, root POV
  L0_T = -tanh(vs2(child_T)/15)                 STATIC v2.9 leaf,  rs=0     root POV
  L0_N = -tanh(vs2(child_N)/15)
  Lr_T = -(tanh(vs2/15) + 0.25*v_nn(child_T))   leaf + iter04 residual, rs=0.25, clipped
  Lr_N = ...

Interpretation:
  * leaf0_picks_teacher = L0_T > L0_N. If the static leaf already ranks the teacher child
    ABOVE the nmcts child, yet NMCTS missed -> the leaf is fine, the miss is exploration/
    search budget (not value). If the leaf ranks them WRONG (L0_T <= L0_N) on a state where
    h6400 says teacher is better -> the v2.9 LEAF cannot see it: value/horizon bottleneck.
  * leafR_picks_teacher = Lr_T > Lr_N. Does adding the 0.25 neural residual fix the ranking?
    (ties I6 to the I4 residual ablation.)

Net-free for rs=0; needs iter04's value head for the residual term. 1 forward per child,
no search -> very cheap. Reads I0 baseline rows to know nmcts_top.
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

import argparse, dataclasses, json, math, sys, time
from pathlib import Path
from multiprocessing import get_context
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to

_CFG: dict = {}
_W: dict = {}


def _worker_init():
    import torch
    torch.set_num_threads(1)
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.evaluators import make_single_evaluator
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    dev = torch.device("cpu")
    ck = torch.load(_CFG["ckpt"], map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"]); net.train(False)
    gf = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
    _W["game"] = gf
    _W["eval"] = make_single_evaluator(net, dev, gf)
    _W["cfg"] = dataclasses.replace(DEFAULT_CONFIG, meeple_k=2.0)


def _child_root_pov(gf, board, action, want_resid):
    """Return (L0, Lr) = root-POV static-leaf values of the child after `action`.
    L0 = pure v2.9 leaf (rs=0); Lr = leaf + 0.25*v_nn (rs=0.25). Child is the
    opponent-to-move, so root-POV value = -(child-mover-POV leaf)."""
    from carcassonne_ai.virtual_score_v2 import virtual_score_v2
    child, _ = gf.get_next_state(board, int(action))
    st = child.state
    # terminal child: use the true terminal score sign (leaf-independent)
    ended = gf.get_game_ended(child, st.current_player)
    if ended != 0:
        h = max(-1.0, min(1.0, float(ended)))
        return -h, -h
    h = math.tanh(virtual_score_v2(st, st.current_player, _W["cfg"]) / 15.0)
    L0 = -h
    Lr = L0
    if want_resid:
        priors, v_nn = _W["eval"](child)
        leaf = max(-1.0, min(1.0, h + 0.25 * float(v_nn)))
        Lr = -leaf
    return L0, Lr


def _process(rec):
    try:
        gf = _W["game"]
        seed = int(rec["seed"])
        _, board = replay_to(seed, rec["ply"])
        tb = int(rec["teacher_best"]); nm = int(rec["nmcts_top"])
        # Q_T = q_best (h6400 deep, root POV); Q_N = q_best - regret (regret is
        # defined exactly as q_best - action_q[nmcts_top] in miss_harness).
        q_best = float(rec["q_best"]); regret = float(rec["regret"])
        Q_T, Q_N = q_best, q_best - regret
        L0_T, Lr_T = _child_root_pov(gf, board, tb, _CFG["resid"])
        L0_N, Lr_N = _child_root_pov(gf, board, nm, _CFG["resid"])
        return {
            "seed": seed, "phase": rec.get("phase"), "k_remaining": rec.get("k_remaining"),
            "q_gap_1_2": rec.get("q_gap_1_2"),
            "teacher_best": tb, "nmcts_top": nm,
            "Q_T": round(Q_T, 6), "Q_N": round(Q_N, 6),
            "L0_T": round(L0_T, 6), "L0_N": round(L0_N, 6),
            "Lr_T": round(Lr_T, 6), "Lr_N": round(Lr_N, 6),
            "leaf0_picks_teacher": bool(L0_T > L0_N),
            "leafR_picks_teacher": bool(Lr_T > Lr_N),
        }
    except Exception as e:
        return {"_error": f"{rec.get('seed')}: {type(e).__name__}: {e}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--misses", required=True, help="jsonl of iter04 I0 MISS rows (has nmcts_top + action_q)")
    ap.add_argument("--checkpoint", required=True, help="path to iter04 (for the residual value head)")
    ap.add_argument("--no-residual", action="store_true", help="skip the residual term (pure leaf only)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    _CFG["ckpt"] = args.checkpoint
    _CFG["resid"] = not args.no_residual
    recs = [json.loads(l) for l in open(args.misses)]
    # only argmax-misses (nmcts_top != teacher_best); needs q_best + regret on the row
    recs = [r for r in recs if r.get("nmcts_top") != r.get("teacher_best")
            and "q_best" in r and "regret" in r]
    print(f"[forced] {len(recs)} misses x (teacher_best, nmcts_top) children W={args.workers}", flush=True)
    t0 = time.perf_counter()
    rows = []
    with get_context("fork").Pool(args.workers, initializer=_worker_init) as pool:
        for i, r in enumerate(pool.imap_unordered(_process, recs, chunksize=4)):
            rows.append(r)
    good = [r for r in rows if "_error" not in r]
    with open(args.out, "w") as fh:
        for r in good:
            fh.write(json.dumps(r) + "\n")
    print(f"[forced] {len(good)} ok, {len(rows)-len(good)} err, "
          f"{(time.perf_counter()-t0)/60:.1f} min -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
