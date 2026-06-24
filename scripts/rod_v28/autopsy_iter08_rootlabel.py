#!/usr/bin/env python3
"""
Autopsy Part B/C — label rod_ov_iter_08's ROOT choice on the 1000 fixed midgame
positions, comparably to the cached rod_choice/parent_choice/heur3200_v28_choice
in ROOT_AUDIT_V28.jsonl.

FAITHFUL + COMPARABLE to the cached labels:
  - same env as the v2.8 rod/parent label runs: MEEPLE_K=2.0 (=> v2.8 leaf), FLAT, cap12, drop3
  - same per-position seed: seed = (source_game_seed*131 + ply) & 0x7FFFFFFF
  - same agent: NeuralMCTS@200, c_puct=3.0, residual_scale=0.25, net-on-CPU (label_midgame path)
  - same selector: best_action() (NOT argmax-visits) — exactly how rod/parent `iter8_choice` was made
Skips the heur@800/1600/3200 ladder (already cached) -> far cheaper; ADDS root value + top-1
visit share for Part C. Writes to a FRESH path (does NOT touch the canonical reference labels).
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"          # v2.8 leaf (the matchplay leaf)
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")       # net on CPU; throughput scales with workers
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, dataclasses as dc, json, random, sys, time
from multiprocessing import get_context
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
from carcassonne_ai.game_wrapper import Game                          # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS                            # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG            # noqa: E402

CKPT = "/mnt/c/carc-shared/rod_v28_overnight_flywheel/ckpt/iter_08.pt"
SAMPLE = os.path.join(REPO, "measurement", "midgame_reference", "MIDGAME_POSITION_SAMPLE.jsonl")
OUT = os.path.join(REPO, "measurement", "rod_v28_overnight_flywheel", "autopsy", "iter08_root_labels.jsonl")
_W: dict = {}


def _worker_init(ckpt):
    import torch
    torch.set_num_threads(1)
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
    dev = torch.device("cpu")
    ck = torch.load(ckpt, map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"], n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"]); net.train(False)
    _W["ns"] = ns
    game_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
    _W["base"] = make_single_evaluator(net, dev, game_farm)
    _W["leaf"] = make_v25_value_wrapper(_W["base"], dc.replace(DEFAULT_CONFIG, residual_scale=0.25))


def _replay(seed, prefix, include_farm):
    random.seed(seed)
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    b = g.get_init_board()
    for a in prefix:
        b, _ = g.get_next_state(b, int(a))
    return g, b


def _process(pos):
    try:
        seed = (pos["source_game_seed"] * 131 + pos["ply"]) & 0x7FFFFFFF
        ns = _W["ns"]
        game, board = _replay(pos["source_game_seed"], pos["prefix"], include_farm=(ns > 10))
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        prior, _val = _W["base"](board)
        prior_arg = int(legal[int(np.argmax([prior[a] for a in legal]))])
        nm = NeuralMCTS(game=game, evaluator=_W["leaf"], simulations=200, seed=seed, c_puct=3.0)
        choice = int(nm.best_action(board))                 # SAME selector as cached rod/parent labels
        counts, actions = nm.root_visit_distribution(board)
        tot = float(counts.sum()) or 1.0
        top1_share = float(counts.max() / tot) if len(counts) else None
        rootv = float(nm.root_value(board))
        return {
            "position_id": pos["position_id"], "band": pos["band"],
            "source_bucket": pos["source_bucket"], "k_remaining": pos["k_remaining"],
            "n_legal": int(len(legal)),
            "iter08ov_choice": choice,
            "iter08ov_prior_argmax": prior_arg,
            "iter08ov_root_value": round(rootv, 5),
            "iter08ov_top1_visit_share": round(top1_share, 4) if top1_share is not None else None,
        }
    except Exception as e:
        return {"_error": f"{pos['position_id']}: {type(e).__name__}: {e}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    positions = [json.loads(l) for l in open(SAMPLE)]
    if args.limit:
        positions = positions[:args.limit]
    print(f"[iter08-rootlabel] {len(positions)} positions, W={args.workers}, ckpt={args.ckpt}", flush=True)
    t0 = time.perf_counter()
    ctx = get_context("fork")
    results = []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=(args.ckpt,)) as pool:
        done = 0
        for r in pool.imap_unordered(_process, positions, chunksize=4):
            results.append(r); done += 1
            if done % 100 == 0:
                el = time.perf_counter() - t0
                print(f"  {done}/{len(positions)} ({el/done:.2f}s/pos, ~{(len(positions)-done)*el/done/60:.1f} min left)", flush=True)
    errors = [r for r in results if "_error" in r]
    lines = [r for r in results if "_error" not in r]
    lines.sort(key=lambda x: (-x["k_remaining"], x["source_bucket"], x["position_id"]))
    with open(OUT, "w") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    el = time.perf_counter() - t0
    print(f"[iter08-rootlabel] wrote {len(lines)} -> {OUT} ({el/60:.1f} min); errors={len(errors)}", flush=True)
    if errors:
        print(f"[iter08-rootlabel] ERRORS: {[e['_error'] for e in errors[:5]]}", flush=True)


if __name__ == "__main__":
    main()
