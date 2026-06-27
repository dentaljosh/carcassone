#!/usr/bin/env python3
"""High-gap distillation — Stage 5b: does the repaired POLICY change SEARCH output?

On held-out hard TEST states, run the production NeuralMCTS@200 (rs=0.25, v2.9 leaf —
EH._make_iter8_mcts) with each checkpoint and compare the SEARCHED move to the h6400
deep teacher: NMCTS top1 agreement + NMCTS regret = Q(teacher_best) − Q(nmcts_move),
using the per-action Q stored in the manifest. Baseline iter04 vs repaired R1/R2.

Interpretation: policy ↑ but NMCTS flat ⇒ value/search bottleneck (outcome B); both ↑ ⇒
game screen justified. Net-on-CPU, parallel (v2.9 leaf hard-set, like stage_a_lite).
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

_W: dict = {}
_CKPTS: dict = {}


def _worker_init():
    import torch
    torch.set_num_threads(1)
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.evaluators import make_single_evaluator
    dev = torch.device("cpu")
    _W["nets"] = {}
    for name, path in _CKPTS.items():
        ck = torch.load(path, map_location=dev, weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
        net.load_state_dict(ck["model_state"]); net.train(False)
        gf = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
        _W["nets"][name] = {"base": make_single_evaluator(net, dev, gf), "game": gf}


def _process(rec):
    try:
        seed = rec["seed"]
        out = {"phase": rec.get("phase"), "q_gap": rec.get("q_gap_1_2"),
               "teacher_best": rec["teacher_best"], "q_best": rec["q_best"],
               "action_q": rec["action_q"]}
        for name, w in _W["nets"].items():
            gf = w["game"]
            _, board = replay_to(seed, rec["ply"])
            nm = EH._make_iter8_mcts(w["base"], gf, seed * 13 + 1, 2.0)
            nm.clear(); nm.search(board)
            out[f"{name}_nm"] = int(nm.best_action(board))
        return out
    except Exception as e:
        return {"_error": f"{rec.get('gen_id', rec.get('seed'))}: {type(e).__name__}: {e}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--checkpoints", required=True, help="name=path,name=path")
    ap.add_argument("--limit", type=int, default=400, help="subset size (NMCTS is costly)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    for tok in args.checkpoints.split(","):
        n, p = tok.split("=", 1); _CKPTS[n.strip()] = p.strip()
    recs = [json.loads(l) for l in open(args.manifest)][:args.limit]
    print(f"[nmcts] {len(recs)} held-out states x NMCTS@200 x {len(_CKPTS)} nets W={args.workers}", flush=True)
    t0 = time.perf_counter()
    rows = []
    with get_context("fork").Pool(args.workers, initializer=_worker_init) as pool:
        for i, r in enumerate(pool.imap_unordered(_process, recs, chunksize=1)):
            rows.append(r)
            if (i + 1) % 50 == 0:
                el = time.perf_counter() - t0
                print(f"  {i+1}/{len(recs)} ({el/(i+1):.2f}s/pos)", flush=True)
    good = [r for r in rows if "_error" not in r]
    print(f"[nmcts] {len(good)} ok, {len(rows)-len(good)} err, {(time.perf_counter()-t0)/60:.1f} min", flush=True)

    names = list(_CKPTS)
    L = [f"\n## Stage 5b — NMCTS@200 on held-out hard TEST (n={len(good)})\n",
         "| net | NMCTS top1 (=h6400) | NMCTS regret | eg n | eg top1 | eg regret |",
         "|---|--:|--:|--:|--:|--:|"]
    for n in names:
        t1 = reg = 0.0; egn = egt1 = egreg = 0
        for r in good:
            aq = {int(k): v for k, v in r["action_q"].items()}
            mv = r.get(f"{n}_nm")
            hit = (mv == r["teacher_best"])
            rg = r["q_best"] - aq.get(mv, min(aq.values()))
            t1 += hit; reg += rg
            if r["phase"] == "endgame":
                egn += 1; egt1 += hit; egreg += rg
        nn = max(len(good), 1)
        L.append(f"| {n} | {t1/nn:.3f} | {reg/nn:.4f} | {egn} | "
                 f"{egt1/max(egn,1):.3f} | {egreg/max(egn,1):.4f} |")
    txt = "\n".join(L) + "\n"
    print(txt)
    if args.out:
        with open(args.out, "a") as fh:
            fh.write(txt)
        print(f"[nmcts] appended to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
