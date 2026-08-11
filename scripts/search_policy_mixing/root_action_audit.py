#!/usr/bin/env python3
"""Phase 2 — Root-action audit for the search/policy mixing study.

Adds, per midgame position (the 1000-position bank from measurement/midgame_reference),
the ROOT actions + routing signals NOT already in MIDGAME_REFERENCE_LABELS.jsonl. Joined by
`position_id` in the analysis step. Reuses label_midgame.py's _replay/_mover_child_stats and the
production leaf env.

NEW per-position outputs:
  - heur200_choice            : HeuristicMCTS@200 v2.7 (missing budget rung; equal-sims vs iter8@200)
  - iter8_noresid_choice      : NeuralMCTS@200, net policy prior + PURE v2.7 leaf (residual_scale=0).
                                == ITER8_POLICY_ONLY_LEAF_V27 == ITER8_NO_RESIDUAL (collapse: the
                                v2.7 wrapper discards v_nn when residual_scale=0).
  - iter8_noresid_topvisit_frac : top-child visit fraction of that search (decisiveness/sharpness)
  - iter8_noresid_n_children    : #root children (dedup)
  - policy_entropy            : Shannon entropy (nats) of masked iter8 policy over legal actions
  - policy_top1_prob          : max policy prob over legal actions
  - v27_gap                   : best - 2nd-best static virtual_score_v2 over legal afterstates (sharpness)
  - v27_recheck_choice        : re-derived v2.7 argmax (sanity vs labelled v27_static_choice)

Same seed convention as label_midgame.py, so iter8_noresid is the PAIRED counterpart of the
labelled iter8_choice (same seed → only residual_scale differs).

Measurement only. No training / flywheel / promotion. Champion unchanged.

In : measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl
Out: measurement/search_policy_mixing/ROOT_ACTION_AUDIT.jsonl
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")   # net on CPU; throughput scales with workers
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import dataclasses as dc
import json
import math
import random
import sys
import time
from multiprocessing import get_context

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))

from carcassonne_ai.game_wrapper import Game                          # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS             # noqa: E402
from carcassonne_ai.virtual_score_v2 import virtual_score_v2, DEFAULT_CONFIG  # noqa: E402

CKPT = "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt"
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
    _W["net"], _W["dev"], _W["ns"] = net, dev, ns
    game_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
    _W["base"] = make_single_evaluator(net, dev, game_farm)
    # residual_scale=0.0 -> the wrapper returns (priors, h): net policy prior + PURE v2.7 leaf.
    _W["leaf_noresid"] = make_v25_value_wrapper(_W["base"], dc.replace(DEFAULT_CONFIG, residual_scale=0.0))


def _replay(seed, prefix, include_farm):
    random.seed(seed)
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    b = g.get_init_board()
    for a in prefix:
        b, _ = g.get_next_state(b, int(a))
    return g, b


def _topvisit_frac(mcts, board):
    """top child visit fraction + #children (dedup transposition collisions)."""
    root = mcts._nodes.get(mcts.game.string_representation(board))
    if root is None:
        return None, 0
    seen, counts = set(), []
    for a in sorted(root.children):
        c = root.children[a]
        if id(c) in seen:
            continue
        seen.add(id(c))
        counts.append(int(c.N))
    tot = sum(counts)
    if tot <= 0 or not counts:
        return None, len(counts)
    return round(max(counts) / tot, 5), len(counts)


def _process(pos):
    try:
        seed = (pos["source_game_seed"] * 131 + pos["ply"]) & 0x7FFFFFFF
        ns = _W["ns"]
        game, board = _replay(pos["source_game_seed"], pos["prefix"], include_farm=(ns > 10))
        mover = board.state.current_player
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)

        # ---- HEUR@200 (the missing budget rung) ----
        hm = HeuristicMCTS(game=game, simulations=200, seed=seed, heur_leaf="v2_7")
        heur200 = int(hm.best_action(board))

        # ---- iter8 net policy prior: entropy + top1 over LEGAL (masked-softmax already normalizes) ----
        prior, _val = _W["base"](board)
        pl = np.array([float(prior[a]) for a in legal], dtype=np.float64)
        s = pl.sum()
        if s > 0:
            pl = pl / s
        nz = pl[pl > 0]
        policy_entropy = float(-(nz * np.log(nz)).sum()) if nz.size else 0.0
        policy_top1 = float(pl.max()) if pl.size else None

        # ---- iter8 policy + PURE v2.7 leaf (residual 0) @200 -- the collapsed decomposition variant ----
        nm = NeuralMCTS(game=game, evaluator=_W["leaf_noresid"], simulations=200, seed=seed, c_puct=3.0)
        iter8_noresid = int(nm.best_action(board))
        tv_frac, n_child = _topvisit_frac(nm, board)

        # ---- static v2.7-depth-0: best, 2nd-best, gap, argmax (sanity) ----
        best_v, second_v, v27_arg = None, None, None
        for a in legal:
            child, _ = game.get_next_state(board, int(a))
            v = virtual_score_v2(child.state, mover, DEFAULT_CONFIG)
            if best_v is None or v > best_v:
                second_v, best_v, v27_arg = best_v, v, int(a)
            elif second_v is None or v > second_v:
                second_v = v
        v27_gap = round(best_v - second_v, 5) if (best_v is not None and second_v is not None) else None

        return {
            "position_id": pos["position_id"], "source_bucket": pos["source_bucket"],
            "band": pos["band"], "k_remaining": pos["k_remaining"], "n_legal": int(len(legal)),
            "heur200_choice": heur200,
            "iter8_noresid_choice": iter8_noresid,
            "iter8_noresid_topvisit_frac": tv_frac,
            "iter8_noresid_n_children": n_child,
            "policy_entropy": round(policy_entropy, 5),
            "policy_top1_prob": round(policy_top1, 5) if policy_top1 is not None else None,
            "v27_gap": v27_gap,
            "v27_recheck_choice": v27_arg,
        }
    except Exception as e:
        return {"_error": f"{pos['position_id']}: {type(e).__name__}: {e}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default=os.path.join(REPO, "measurement", "midgame_reference", "MIDGAME_POSITION_SAMPLE.jsonl"))
    ap.add_argument("--out", default=os.path.join(REPO, "measurement", "search_policy_mixing", "ROOT_ACTION_AUDIT.jsonl"))
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0, help="0=all; else first N (smoke)")
    args = ap.parse_args(argv)

    positions = [json.loads(l) for l in open(args.sample)]
    if args.limit:
        positions = positions[:args.limit]
    print(f"[spm-phase2] {len(positions)} positions, W={args.workers}, ckpt={args.ckpt}", flush=True)

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
    with open(args.out, "w") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")

    el = time.perf_counter() - t0
    print(f"[spm-phase2] wrote {len(lines)} rows -> {args.out} ({el/60:.2f} min @ W={args.workers}); errors={len(errors)}", flush=True)
    if errors:
        print(f"[spm-phase2] ERRORS ({len(errors)}): {[e['_error'] for e in errors[:5]]}", flush=True)


if __name__ == "__main__":
    main()
