"""Phase 4A — value-ranking LABEL-RELIABILITY ceiling (2026-06-17).

Before training any candidate value head against the deep-oracle sibling
ranking (Phase 4C), we must know how reliable that RANKING TARGET is. A model's
Kendall-tau vs "the oracle" is meaningless without the oracle's self-agreement:
if two independent 400-sim oracle runs only agree at tau=0.6, then 0.6 is the
empirical CEILING and a model tau of 0.5 is near-perfect, not a failure.

This probe, for a set of on-distribution decision nodes:
  - scores each child with the 400-sim v2.7-leaf oracle TWICE (independent search
    seeds) -> tau(A,B), top-1 agreement, pairwise agreement, cross-regret.
  - on a subset, also runs a DEEPER oracle (--deep-sims, e.g. 1600) -> measures
    whether 400 sims approximates the deeper ranking (tau(400, deep), top-1).

Outputs the empirical label ceiling consumed by VALUE_RANKING_LABEL_RELIABILITY.md.
Decision (Phase 4E): if model arms fail BUT oracle self-agreement is also low,
the probe/target is the bottleneck — do NOT declare learned value dead. If oracle
self-agreement is HIGH and arms still fail, the learned-ranking formulation is
disfavored.

Self-contained (copies the harvest/oracle machinery from probe_decision_ranking.py
so the deliverable runs standalone). CPU multiprocessing; net on CPU in workers.

Usage:
  python -u scripts/value_ranking_label_reliability.py \
      --checkpoint /mnt/c/carc-shared/searchval_tree/ckpt/iter_00.pt \
      --n-positions 200 --oracle-sims 400 --deep-sims 1600 --deep-frac 0.3 \
      --play-sims 60 --max-children 16 --workers 14 \
      --out /mnt/c/carc-shared/value_ranking/label_reliability
"""
from __future__ import annotations

import os

os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")

import argparse
import copy
import dataclasses
import json
import math
import multiprocessing as mp
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.evaluators import (
    make_single_evaluator_policy_only,
    make_v25_value_wrapper,
)
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.game_wrapper import Board, Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG


def kendall_tau_b(x: np.ndarray, y: np.ndarray) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    c = d = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = float(x[i] - x[j]); dy = float(y[i] - y[j])
            sx = (dx > 0) - (dx < 0); sy = (dy > 0) - (dy < 0)
            if sx == 0 and sy == 0:
                continue
            if sx == 0:
                ty += 1; continue
            if sy == 0:
                tx += 1; continue
            if sx == sy:
                c += 1
            else:
                d += 1
    denom = math.sqrt((c + d + tx) * (c + d + ty))
    return (c - d) / denom if denom else float("nan")


def pairwise_agreement(x: np.ndarray, y: np.ndarray) -> float:
    """Fraction of strictly-ordered child pairs that agree in direction
    (ties on either side excluded from both numerator and denominator)."""
    n = len(x); agree = tot = 0
    for i in range(n):
        for j in range(i + 1, n):
            sx = int(x[i] > x[j]) - int(x[i] < x[j]); sy = int(y[i] > y[j]) - int(y[i] < y[j])
            if sx == 0 or sy == 0:
                continue
            tot += 1; agree += int(sx == sy)
    return agree / tot if tot else float("nan")


_W: dict = {}


def _worker_init(checkpoint, play_sims, oracle_sims, deep_sims, c_puct,
                 max_children, min_children, stride, temp_threshold):
    os.environ["OMP_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    device = torch.device("cpu")
    ck = torch.load(checkpoint, map_location=device, weights_only=False)
    n_scalar = int(ck.get("n_scalar_features", N_SCALAR_FEATURES))
    net = CarcassonneNet(
        n_filters=int(ck["n_filters"]), n_blocks=int(ck["n_blocks"]),
        n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"]); net.train(False)
    include_farm = (n_scalar == N_SCALAR_FEATURES + 2)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    _W.update(net=net, device=device, game=game, play_sims=play_sims,
              oracle_sims=oracle_sims, deep_sims=deep_sims, c_puct=c_puct,
              max_children=max_children, min_children=min_children, stride=stride,
              temp_threshold=temp_threshold,
              cfg0=dataclasses.replace(DEFAULT_CONFIG, value_blend=0.0))


def _make_search(sims, seed):
    base = make_single_evaluator_policy_only(_W["net"], _W["device"], _W["game"])
    leaf = make_v25_value_wrapper(base, cfg=_W["cfg0"])
    return NeuralMCTS(game=_W["game"], evaluator=leaf, simulations=sims,
                      c_puct=_W["c_puct"], seed=seed, batch_size=1)


def _unique_children(board, rng):
    game, max_children = _W["game"], _W["max_children"]
    legal = list(map(int, np.flatnonzero(game.get_valid_moves(board))))
    rng.shuffle(legal)
    out, seen = [], set()
    for a in legal:
        child, _ = game.get_next_state(board, a)
        key = game.string_representation(child)
        if key in seen:
            continue
        seen.add(key); out.append(child)
        if len(out) >= max_children:
            break
    return out


def _oracle_rank(children, parent_player, sims, seed):
    oracle = _make_search(sims, seed)
    q = np.empty(len(children), dtype=np.float64)
    for i, cb in enumerate(children):
        oracle.clear(); oracle.search(cb)
        flip = 1.0 if cb.state.current_player == parent_player else -1.0
        q[i] = flip * oracle.root_value(cb)
    return q


def harvest_game(seed):
    import pickle
    game = _W["game"]; random.seed(seed)
    search = _make_search(_W["play_sims"], seed)
    board = game.get_init_board(); out = []; ply = 0
    while game.get_game_ended(board, 0) == 0.0:
        legal = np.flatnonzero(game.get_valid_moves(board))
        if legal.size == 0:
            break
        search.clear(); search.search(board)
        if (ply % _W["stride"] == 0) and legal.size >= _W["min_children"]:
            out.append(pickle.dumps((seed, ply, copy.deepcopy(board))))
        temp = 1.0 if ply < _W["temp_threshold"] else 0.0
        action = search.select_for_training(board, temperature=temp)
        board, _ = game.get_next_state(board, action); ply += 1
    return out


def probe_one(args):
    import pickle
    idx, payload, do_deep = args
    game_seed, ply, board = pickle.loads(payload)
    game = _W["game"]
    rng = random.Random(0xC0FFEE ^ (idx * 2654435761))
    parent_player = board.state.current_player
    children = _unique_children(board, rng)
    if len(children) < 2:
        return None
    qa = _oracle_rank(children, parent_player, _W["oracle_sims"], 0x5A5A ^ idx)
    qb = _oracle_rank(children, parent_player, _W["oracle_sims"], 0xA5A5 ^ (idx * 7 + 1))
    best_a, best_b = int(np.argmax(qa)), int(np.argmax(qb))
    # cross-regret: trust A's pick, measure loss under B's "ground truth" (and vice versa)
    regret_ab = float(qb[best_b] - qb[best_a])
    regret_ba = float(qa[best_a] - qa[best_b])
    row = {
        "game_seed": int(game_seed), "ply": int(ply), "k": len(children),
        "tau_ab": kendall_tau_b(qa, qb),
        "top1_ab": int(best_a == best_b),
        "pair_ab": pairwise_agreement(qa, qb),
        "cross_regret": 0.5 * (abs(regret_ab) + abs(regret_ba)),
        "spread_a": float(qa.max() - qa.min()),
        "phase": ("open" if ply < 24 else "mid" if ply < 48 else "end"),
    }
    if do_deep:
        qd = _oracle_rank(children, parent_player, _W["deep_sims"], 0xDEEF ^ idx)
        row["tau_400_deep"] = kendall_tau_b(qa, qd)
        row["top1_400_deep"] = int(best_a == int(np.argmax(qd)))
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(prog="value_ranking_label_reliability")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--n-positions", type=int, default=200)
    ap.add_argument("--oracle-sims", type=int, default=400)
    ap.add_argument("--deep-sims", type=int, default=1600)
    ap.add_argument("--deep-frac", type=float, default=0.3)
    ap.add_argument("--play-sims", type=int, default=60)
    ap.add_argument("--max-children", type=int, default=16)
    ap.add_argument("--min-children", type=int, default=3)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--temp-threshold", type=int, default=20)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--out", type=Path, default=Path("/tmp/value_ranking_label_reliability"))
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    per_game = max(4, (2 * 70) // args.stride // 2)
    n_games = math.ceil(args.n_positions / per_game) + 3
    init_args = (str(args.checkpoint), args.play_sims, args.oracle_sims, args.deep_sims,
                 args.c_puct, args.max_children, args.min_children, args.stride,
                 args.temp_threshold)
    ctx = mp.get_context("fork")
    t0 = time.perf_counter()
    print(f"label-reliability: ckpt={args.checkpoint} n={args.n_positions} "
          f"oracle_sims={args.oracle_sims} deep_sims={args.deep_sims} "
          f"deep_frac={args.deep_frac} workers={args.workers}", flush=True)

    boards = []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=init_args) as pool:
        for gi, blist in enumerate(pool.imap_unordered(
                harvest_game, [args.seed + i for i in range(n_games)])):
            boards.extend(blist)
            print(f"  harvest: {len(boards)} positions ({gi+1} games)", flush=True)
            if len(boards) >= args.n_positions:
                break
        pool.terminate()
    boards = boards[:args.n_positions]
    print(f"  harvested {len(boards)} positions in {time.perf_counter()-t0:.1f}s", flush=True)

    drng = random.Random(args.seed)
    tasks = [(i, b, drng.random() < args.deep_frac) for i, b in enumerate(boards)]
    rows = []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=init_args) as pool:
        for done, r in enumerate(pool.imap_unordered(probe_one, tasks)):
            if r is not None:
                rows.append(r)
            if (done + 1) % 25 == 0:
                print(f"  {done+1}/{len(tasks)} probed", flush=True)
    if not rows:
        print("ERROR: no usable nodes", file=sys.stderr); return 1

    def agg(key):
        vals = np.array([r[key] for r in rows if key in r and not
                         (isinstance(r[key], float) and math.isnan(r[key]))], dtype=np.float64)
        if len(vals) == 0:
            return None
        return {"mean": float(vals.mean()),
                "se": float(vals.std() / math.sqrt(max(len(vals), 1))), "n": int(len(vals))}

    summary = {
        "checkpoint": str(args.checkpoint), "n_nodes": len(rows),
        "mean_k": float(np.mean([r["k"] for r in rows])),
        "config": {"oracle_sims": args.oracle_sims, "deep_sims": args.deep_sims,
                   "play_sims": args.play_sims, "max_children": args.max_children,
                   "c_puct": args.c_puct, "stride": args.stride, "seed": args.seed},
        "ceiling": {k: agg(k) for k in
                    ("tau_ab", "top1_ab", "pair_ab", "cross_regret",
                     "tau_400_deep", "top1_400_deep", "spread_a")},
        "by_phase": {ph: {"n": sum(r["phase"] == ph for r in rows),
                          "tau_ab": agg_phase(rows, ph, "tau_ab")}
                     for ph in ("open", "mid", "end")},
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.out / "rows.json").write_text(json.dumps(rows))
    c = summary["ceiling"]
    print("\n" + "=" * 60)
    print(f"LABEL-RELIABILITY CEILING ({len(rows)} nodes, {time.perf_counter()-t0:.0f}s)")
    print("=" * 60)
    print(f"  oracle self-agreement tau(400_A, 400_B) : {c['tau_ab']['mean']:+.3f} +- {c['tau_ab']['se']:.3f}")
    print(f"  oracle top-1 agreement                  : {c['top1_ab']['mean']:.3f}")
    print(f"  oracle pairwise agreement               : {c['pair_ab']['mean']:.3f}")
    print(f"  cross-regret (oracle noise, tanh)       : {c['cross_regret']['mean']:.4f}")
    if c.get("tau_400_deep"):
        print(f"  tau(400, {args.deep_sims}) [deeper agreement]   : {c['tau_400_deep']['mean']:+.3f} +- {c['tau_400_deep']['se']:.3f}")
        print(f"  top-1(400 vs {args.deep_sims})                  : {c['top1_400_deep']['mean']:.3f}")
    print(f"\n  -> model tau vs oracle is CAPPED near {c['tau_ab']['mean']:.2f}; interpret arm results against this.")
    print(f"  -> wrote {args.out}/summary.json")
    return 0


def agg_phase(rows, ph, key):
    vals = [r[key] for r in rows if r.get("phase") == ph and key in r
            and not (isinstance(r[key], float) and math.isnan(r[key]))]
    return float(np.mean(vals)) if vals else None


if __name__ == "__main__":
    sys.exit(main())
