#!/usr/bin/env python3
"""Value/Search Conversion Autopsy — the universal NMCTS intervention harness.

Given h6400-labeled roots (Path-3 probe.jsonl: per-action adjusted Q + teacher_best),
run a CONFIGURABLE NeuralMCTS variant per root and record, per checkpoint, the searched
move + visit share on the h6400 top move + adjusted search-Q + h6400-Q regret. One row
per (root, checkpoint). A single script covers every root-level intervention by config:

  I0/I1  --sims {200,400,800,1600}        search-budget axis
  I4     --residual-scale {0.0,0.25,0.5}  neural-value/residual axis  (0 = pure v2.9 leaf)
  I3     --prior {net,flat}               prior ablation (flat = uniform-over-legal)
  I2     --prior teacher --prior-temp T   teacher-prior injection at the ROOT only
                                          (softmax(h6400 Q / T) over legal; T→0 ≈ one-hot)

Net-on-CPU, fork-pool parallel, v2.9 leaf hard-set (identical substrate to Path-3 /
highgap_nmcts_eval / stage_a_lite). Output: one jsonl row per (root, ckpt) with full
provenance so agg_miss.py can bucket misses and A/B interventions post-hoc.
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

import argparse, dataclasses, json, sys, time
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
    dev = torch.device("cpu")
    _W["nets"] = {}
    for name, path in _CFG["ckpts"].items():
        ck = torch.load(path, map_location=dev, weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
        net.load_state_dict(ck["model_state"]); net.train(False)
        gf = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
        _W["nets"][name] = {"base": make_single_evaluator(net, dev, gf), "game": gf}


def _build_mcts(base_eval, gf, seed, root_key=None, action_q=None):
    """Construct a NeuralMCTS with the configured sims/residual/c_puct/prior.

    The v2.5 leaf wrapper keeps the NET priors and replaces the value with
    tanh(vs2/15) + resid*v_nn. We optionally wrap that to flatten the prior or
    inject an h6400-derived teacher prior at the ROOT board only.
    """
    from carcassonne_ai.evaluators import make_v25_value_wrapper
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    from carcassonne_ai.mcts import NeuralMCTS

    sims = _CFG["sims"]; resid = _CFG["resid"]; cpuct = _CFG["cpuct"]
    prior = _CFG["prior"]; temp = _CFG["prior_temp"]
    cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=resid, meeple_k=2.0)
    leaf = make_v25_value_wrapper(base_eval, cfg)

    if prior == "net":
        ev = leaf
    elif prior == "flat":
        def ev(board):
            p, v = leaf(board)
            mask = gf.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            up = np.zeros_like(np.asarray(p, dtype=np.float32))
            up[legal] = 1.0 / max(legal.size, 1)
            return up, v
    elif prior == "teacher":
        # Peaked softmax(h6400 Q / temp) over the deduped legal set, injected at
        # the root board only; net priors elsewhere in the tree. action_q keys are
        # the deduped lowest-index legal actions (same dedup the tree uses).
        qa = {int(k): float(val) for k, val in (action_q or {}).items()}
        if qa:
            acts = np.array(list(qa.keys()))
            qv = np.array([qa[a] for a in acts], dtype=np.float64)
            w = np.exp((qv - qv.max()) / max(temp, 1e-6)); w /= w.sum()
        else:
            acts, w = np.array([], dtype=int), np.array([])

        def ev(board):
            p, v = leaf(board)
            if root_key is not None and gf.string_representation(board) == root_key and acts.size:
                tp = np.zeros_like(np.asarray(p, dtype=np.float32))
                tp[acts] = w.astype(np.float32)
                return tp, v
            return p, v
    else:
        raise ValueError(f"bad prior {prior!r}")

    return NeuralMCTS(game=gf, evaluator=ev, simulations=sims, seed=seed, c_puct=cpuct)


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
        seed = int(rec["seed"])
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        teacher_best = int(rec["teacher_best"])
        q_best = float(rec["q_best"])
        base_out = {
            "gen_id": rec.get("gen_id"), "seed": seed, "ply": rec.get("ply"),
            "phase": rec.get("phase"), "k_remaining": rec.get("k_remaining"),
            "score_margin_abs": rec.get("score_margin_abs"), "legal_n": rec.get("legal_n"),
            "teacher_best": teacher_best, "q_best": round(q_best, 6),
            "q_gap_1_2": rec.get("q_gap_1_2"), "q_second": rec.get("q_second"),
            "sims": _CFG["sims"], "resid": _CFG["resid"], "cpuct": _CFG["cpuct"],
            "prior": _CFG["prior"], "tag": _CFG["tag"],
        }
        rows = []
        for name, w in _W["nets"].items():
            gf = w["game"]
            _, board = replay_to(seed, rec["ply"])
            root_key = gf.string_representation(board)
            nm = _build_mcts(w["base"], gf, seed * 13 + 1, root_key=root_key, action_q=aq)
            nm.clear()
            visits = nm.search(board)
            nmcts_top = int(nm.best_action(board))
            root = nm._nodes[root_key]
            ded = _deduped(root)
            # adjusted search-Q + visits keyed by deduped lowest-index action
            sq, sn = {}, {}
            for a, c in ded:
                q = c.Q if c.player_to_move == root.player_to_move else -c.Q
                sq[int(a)] = float(q); sn[int(a)] = int(c.N)
            tot = sum(sn.values()) or 1
            t_N = sn.get(teacher_best, 0)
            top_N = sn.get(nmcts_top, 0)
            # top3 by visits
            top3 = [int(a) for a, _ in sorted(sn.items(), key=lambda kv: kv[1], reverse=True)[:3]]
            regret = q_best - aq.get(nmcts_top, min(aq.values()))
            r = dict(base_out)
            r.update({
                "ckpt": name,
                "nmcts_top": nmcts_top,
                "nmcts_top_eq_teacher": (nmcts_top == teacher_best),
                "teacher_best_N": t_N,
                "nmcts_top_N": top_N,
                "total_N": tot,
                "teacher_best_visit_share": round(t_N / tot, 5),
                "nmcts_top_visit_share": round(top_N / tot, 5),
                "search_q_teacher_best": (round(sq[teacher_best], 6) if teacher_best in sq else None),
                "search_q_nmcts_top": (round(sq[nmcts_top], 6) if nmcts_top in sq else None),
                "regret": round(regret, 6),
                "top3_actions": top3,
                "teacher_in_top3": (teacher_best in top3),
            })
            rows.append(r)
        return rows
    except Exception as e:
        return [{"_error": f"{rec.get('gen_id', rec.get('seed'))}: {type(e).__name__}: {e}"}]


def _load_probes(paths, gap_min, limit, phase=None):
    recs = []
    for p in paths:
        for line in open(p):
            d = json.loads(line)
            if gap_min and float(d.get("q_gap_1_2", 0.0)) < gap_min:
                continue
            if phase and d.get("phase") != phase:
                continue
            recs.append(d)
    if limit:
        recs = recs[:limit]
    return recs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True, help="comma-list of probe.jsonl")
    ap.add_argument("--checkpoints", required=True, help="name=path,name=path")
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--residual-scale", type=float, default=0.25)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--prior", choices=["net", "flat", "teacher"], default="net")
    ap.add_argument("--prior-temp", type=float, default=0.03)
    ap.add_argument("--gap-min", type=float, default=0.0, help="prefilter q_gap_1_2 >= this")
    ap.add_argument("--phase", default=None, help="restrict to one phase (I7 endgame slice)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default=None, help="i/n e.g. 0/2 for multi-box split")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--tag", default="I0")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    for tok in args.checkpoints.split(","):
        n, p = tok.split("=", 1); _CFG.setdefault("ckpts", {})[n.strip()] = p.strip()
    _CFG.update(sims=args.sims, resid=args.residual_scale, cpuct=args.c_puct,
                prior=args.prior, prior_temp=args.prior_temp, tag=args.tag)

    recs = _load_probes(args.probe.split(","), args.gap_min, args.limit, args.phase)
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        recs = [r for k, r in enumerate(recs) if k % n == i]
    print(f"[miss] tag={args.tag} {len(recs)} roots x sims={args.sims} rs={args.residual_scale} "
          f"prior={args.prior} x {len(_CFG['ckpts'])} nets W={args.workers}", flush=True)

    t0 = time.perf_counter()
    out = open(args.out, "w")
    nrow = nerr = done = 0
    with get_context("fork").Pool(args.workers, initializer=_worker_init) as pool:
        for batch in pool.imap_unordered(_process, recs, chunksize=1):
            done += 1
            for r in batch:
                if "_error" in r:
                    nerr += 1
                else:
                    out.write(json.dumps(r) + "\n"); nrow += 1
            if done % 100 == 0:
                el = time.perf_counter() - t0
                print(f"  {done}/{len(recs)} ({el/done:.2f}s/root, "
                      f"~{(len(recs)-done)*el/max(done,1)/60:.1f} min left)", flush=True)
    out.close()
    print(f"[miss] {nrow} rows, {nerr} err, {(time.perf_counter()-t0)/60:.1f} min -> {args.out}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
