"""Phase 4B — leakage-safe per-child ranking dataset (2026-06-17).

Dumps the training/eval rows for the value-ranking kill-test (Phase 4C arms):
for a set of on-distribution DECISION nodes, every unique child board is one row
with the deep-oracle sibling-value as the RANKING TARGET, tagged with a
group_id (the parent decision node) and the game_seed (for leakage-safe splits).

Leakage discipline (4B):
  - group_id = parent node: ALL children of a parent stay in one split (the
    training script must split by game_seed, never by row).
  - game_seed recorded per row: games never cross train/val/test.
  - phase (open/mid/end) recorded for phase break-outs.
  - sibling count k and oracle spread recorded per group.
  - NO random child-row split is valid; the consumer splits by game_seed.

Row arrays (single .npz):
  child_obs    (M, C, W, W) float16   canonical board planes (decision-maker POV)
  child_scalars(M, S)        float16
  oracle_q     (M,)          float32   parent-POV deep-oracle value  [the target]
  group_id     (M,)          int32     parent decision-node index
  game_seed    (M,)          int64
  ply          (M,)          int16
  k            (M,)          int16      sibling count of this row's group
Plus meta.json: config, checkpoint sha, n_groups, n_games, per-phase counts.

Self-contained; CPU multiprocessing (net on CPU in workers).

Usage:
  python -u scripts/value_ranking_dump_dataset.py \
      --checkpoint /mnt/c/carc-shared/searchval_tree/ckpt/iter_00.pt \
      --n-positions 1200 --oracle-sims 400 --play-sims 60 --max-children 16 \
      --workers 14 --out /mnt/c/carc-shared/value_ranking/dataset
"""
from __future__ import annotations

import os

os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")

import argparse
import copy
import dataclasses
import hashlib
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

_W: dict = {}


def _worker_init(checkpoint, play_sims, oracle_sims, c_puct,
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
              oracle_sims=oracle_sims, c_puct=c_puct, max_children=max_children,
              min_children=min_children, stride=stride, temp_threshold=temp_threshold,
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


def dump_one(args):
    """Return per-child rows for one decision node, or None."""
    import pickle
    idx, payload = args
    game_seed, ply, board = pickle.loads(payload)
    game = _W["game"]
    rng = random.Random(0xC0FFEE ^ (idx * 2654435761))
    parent_player = board.state.current_player
    children = _unique_children(board, rng)
    if len(children) < 2:
        return None
    oracle = _make_search(_W["oracle_sims"], 0x5A5A ^ idx)
    obs_l, sca_l, q_l = [], [], []
    for cb in children:
        oracle.clear(); oracle.search(cb)
        flip = 1.0 if cb.state.current_player == parent_player else -1.0
        q_l.append(flip * oracle.root_value(cb))
        obs, sca = game.get_canonical_form(cb, cb.state.current_player)
        # store from the DECISION-MAKER's POV: if child flips player, negate is
        # handled on the target (oracle_q already parent-POV); obs stays the
        # child's own canonical form (the head sees the child as-is).
        obs_l.append(obs.astype(np.float16))
        sca_l.append(np.asarray(sca, dtype=np.float16))
    k = len(children)
    return {
        "obs": np.stack(obs_l), "sca": np.stack(sca_l),
        "q": np.asarray(q_l, dtype=np.float32),
        "game_seed": int(game_seed), "ply": int(ply), "k": k,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="value_ranking_dump_dataset")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--n-positions", type=int, default=1200)
    ap.add_argument("--oracle-sims", type=int, default=400)
    ap.add_argument("--play-sims", type=int, default=60)
    ap.add_argument("--max-children", type=int, default=16)
    ap.add_argument("--min-children", type=int, default=3)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--temp-threshold", type=int, default=20)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed", type=int, default=2024)
    ap.add_argument("--out", type=Path, default=Path("/tmp/value_ranking_dataset"))
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    per_game = max(4, (2 * 70) // args.stride // 2)
    n_games = math.ceil(args.n_positions / per_game) + 3
    init_args = (str(args.checkpoint), args.play_sims, args.oracle_sims, args.c_puct,
                 args.max_children, args.min_children, args.stride, args.temp_threshold)
    ctx = mp.get_context("fork")
    t0 = time.perf_counter()
    print(f"dump: ckpt={args.checkpoint} sha={sha[:12]} n={args.n_positions} "
          f"oracle_sims={args.oracle_sims} workers={args.workers}", flush=True)

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
    print(f"  harvested {len(boards)} in {time.perf_counter()-t0:.1f}s", flush=True)

    obs_a, sca_a, q_a, grp_a, gs_a, ply_a, k_a = [], [], [], [], [], [], []
    gid = 0; phase_counts = {"open": 0, "mid": 0, "end": 0}
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=init_args) as pool:
        for done, r in enumerate(pool.imap_unordered(
                dump_one, list(enumerate(boards)))):
            if r is None:
                continue
            m = r["q"].shape[0]
            obs_a.append(r["obs"]); sca_a.append(r["sca"]); q_a.append(r["q"])
            grp_a.append(np.full(m, gid, dtype=np.int32))
            gs_a.append(np.full(m, r["game_seed"], dtype=np.int64))
            ply_a.append(np.full(m, r["ply"], dtype=np.int16))
            k_a.append(np.full(m, r["k"], dtype=np.int16))
            ph = "open" if r["ply"] < 24 else "mid" if r["ply"] < 48 else "end"
            phase_counts[ph] += 1
            gid += 1
            if (done + 1) % 50 == 0:
                print(f"  {done+1}/{len(boards)} nodes, {gid} groups", flush=True)

    if not q_a:
        print("ERROR: no usable nodes", file=sys.stderr); return 1
    obs = np.concatenate(obs_a); sca = np.concatenate(sca_a); q = np.concatenate(q_a)
    grp = np.concatenate(grp_a); gs = np.concatenate(gs_a)
    ply = np.concatenate(ply_a); k = np.concatenate(k_a)
    np.savez_compressed(args.out / "rows.npz", child_obs=obs, child_scalars=sca,
                        oracle_q=q, group_id=grp, game_seed=gs, ply=ply, k=k)
    meta = {
        "checkpoint": str(args.checkpoint), "checkpoint_sha256": sha,
        "n_rows": int(q.shape[0]), "n_groups": int(gid),
        "n_games": int(len(np.unique(gs))),
        "obs_shape": list(obs.shape[1:]), "n_scalar": int(sca.shape[1]),
        "phase_counts": phase_counts,
        "config": {"n_positions": args.n_positions, "oracle_sims": args.oracle_sims,
                   "play_sims": args.play_sims, "max_children": args.max_children,
                   "c_puct": args.c_puct, "stride": args.stride, "seed": args.seed,
                   "v25_cap": os.environ["CARCASSONNE_V25_CAP"],
                   "v25_drop_three_open": os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"]},
        "leakage_policy": "split by game_seed; all children of a group stay together",
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\n  dumped {q.shape[0]} rows / {gid} groups / {meta['n_games']} games "
          f"({time.perf_counter()-t0:.0f}s)")
    print(f"  obs {obs.shape} {obs.dtype}  -> {args.out}/rows.npz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
