"""STEP A — offline decision-RANKING probe (the value-loss gate, 2026-06-05).

The triply-confirmed verdict: a learned value head with outcome-corr 0.84 is
NOT a usable MCTS leaf — blending it in degrades strength monotonically, and
neither more data (step 1) nor architecture (step 2) fixed it. The hypothesis
(docs/VALUE_LOSS_ATTACK_2026-06-05.md): a leaf must RANK sibling moves
correctly (local discrimination), not predict the absolute outcome (global
calibration). Outcome/Q-MSE optimizes the wrong objective.

This probe tests that hypothesis CHEAPLY, before any retrain:

  For a set of on-distribution decision positions, take each legal move's
  resulting child board and score it three ways, all from the DECISION-MAKER's
  POV:
    - ORACLE   : a deep v2.7-leaf search from the child (= our best proxy for
                 the move's true value; the production lambda=0 search, +56 elo).
    - v2.7     : the 1-ply v2.7 heuristic leaf value of the child.
    - value-net: the learned value head on the child.
  Then rank the moves by each and compare v2.7 / value-net rankings to the
  ORACLE via Kendall-tau, top-1 agreement, and ORACLE REGRET (how much oracle
  value you give up by trusting that ranker to pick the move).

PREDICTION (confirms "the loss is the problem"): value-net tau LOW + regret
HIGH despite corr 0.84, while v2.7 tau HIGH + regret LOW. If instead the
value-net ranks WELL, the leaf failure is elsewhere -> rethink before STEP B.

Notes on fairness / circularity:
  - The oracle uses the v2.7 leaf (our strongest eval), so v2.7's tau is mildly
    inflated by construction (deep-v2.7 vs 1-ply-v2.7). The DECISIVE, less
    circular outputs are (a) the value-net's ABSOLUTE regret (points of oracle
    value lost) and (b) value-net-vs-v2.7 contrast. The oracle Q is also
    literally what search_value_tree TRAINED the head to predict -> a low
    value-net tau is damning regardless. Oracle DEPTH matters: a shallow oracle
    ~ 1-ply v2.7 (circular); use --oracle-sims >= 400.
  - Children are deduped by board (symmetric rotations collapse) and, when a
    node has more legal moves than --max-children, a UNIFORM random subset is
    taken (unbiased w.r.t. both rankers) so neither ranker picks the candidates.

Parallel: positions are harvested (one game per worker) and probed (one node
per worker) across a CPU multiprocessing Pool — the net runs on CPU in each
worker (no CUDA in workers -> sidesteps the fork+CUDA crash; the net is tiny so
CPU forward is cheap, and the v2.7 leaf is the CPU bottleneck anyway).

Usage:
  python -u scripts/probe_decision_ranking.py \
      --checkpoint /mnt/c/carc-shared/searchval_tree/ckpt/iter_00.pt \
      --n-positions 250 --oracle-sims 400 --play-sims 60 \
      --max-children 16 --workers 14 --out /tmp/decision_ranking
"""
from __future__ import annotations

import os

# Production v2.7 leaf config MUST be set before importing carcassonne_ai
# (virtual_score_v2.DEFAULT_CONFIG is built from these at import time).
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
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2


# --------------------------------------------------------------------------
# Kendall tau-b (no scipy in the venv).
# --------------------------------------------------------------------------
def kendall_tau_b(x: np.ndarray, y: np.ndarray) -> float:
    """Kendall tau-b correlation between two score vectors (ties handled).
    +1 = identical ordering, -1 = reversed, 0 = independent. O(k^2); k is tiny."""
    n = len(x)
    if n < 2:
        return float("nan")
    c = d = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = float(x[i] - x[j])
            dy = float(y[i] - y[j])
            sx = (dx > 0) - (dx < 0)
            sy = (dy > 0) - (dy < 0)
            if sx == 0 and sy == 0:
                continue
            if sx == 0:
                ty += 1
                continue
            if sy == 0:
                tx += 1
                continue
            if sx == sy:
                c += 1
            else:
                d += 1
    denom = math.sqrt((c + d + tx) * (c + d + ty))
    if denom == 0:
        return float("nan")
    return (c - d) / denom


def _to_margin(v: float) -> float:
    """tanh value (parent POV) -> approx margin in points: 15*atanh(v)."""
    return 15.0 * math.atanh(max(-0.9999, min(0.9999, v)))


# --------------------------------------------------------------------------
# Per-worker globals (set in initializer; CPU only).
# --------------------------------------------------------------------------
_W: dict = {}


def _worker_init(checkpoint: str, play_sims: int, oracle_sims: int,
                 c_puct: float, max_children: int, min_children: int,
                 stride: int, temp_threshold: int) -> None:
    # One thread per worker process so N workers don't each spawn N threads.
    os.environ["OMP_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    device = torch.device("cpu")
    ck = torch.load(checkpoint, map_location=device, weights_only=False)
    n_scalar = int(ck.get("n_scalar_features", N_SCALAR_FEATURES))
    net = CarcassonneNet(
        n_filters=int(ck["n_filters"]),
        n_blocks=int(ck["n_blocks"]),
        n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    include_farm = (n_scalar == N_SCALAR_FEATURES + 2)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    _W.update(
        net=net, device=device, game=game,
        play_sims=play_sims, oracle_sims=oracle_sims, c_puct=c_puct,
        max_children=max_children, min_children=min_children,
        stride=stride, temp_threshold=temp_threshold,
        cfg0=dataclasses.replace(DEFAULT_CONFIG, value_blend=0.0),
    )


def _make_search(sims: int, seed: int) -> NeuralMCTS:
    base = make_single_evaluator_policy_only(_W["net"], _W["device"], _W["game"])
    leaf = make_v25_value_wrapper(base, cfg=_W["cfg0"])  # net priors + pure v2.7 leaf
    return NeuralMCTS(game=_W["game"], evaluator=leaf, simulations=sims,
                      c_puct=_W["c_puct"], seed=seed, batch_size=1)


def _net_values(boards: list[Board]) -> np.ndarray:
    game, net, device = _W["game"], _W["net"], _W["device"]
    obs_list, sca_list = [], []
    for b in boards:
        obs, sca = game.get_canonical_form(b, b.state.current_player)
        obs_list.append(obs)
        sca_list.append(sca)
    obs_t = torch.from_numpy(np.stack(obs_list)).float().to(device)
    sca_t = torch.from_numpy(np.stack(sca_list)).float().to(device)
    with torch.no_grad():
        _, v = net(obs_t, sca_t)
    return v.float().cpu().numpy().reshape(-1)


def _unique_children(board: Board, rng: random.Random):
    game, max_children = _W["game"], _W["max_children"]
    mask = game.get_valid_moves(board)
    legal = list(map(int, np.flatnonzero(mask)))
    rng.shuffle(legal)
    out, seen = [], set()
    for a in legal:
        child, _ = game.get_next_state(board, a)
        key = game.string_representation(child)
        if key in seen:
            continue
        seen.add(key)
        out.append(child)
        if len(out) >= max_children:
            break
    return out


# --------------------------------------------------------------------------
# Worker tasks.
# --------------------------------------------------------------------------
def harvest_game(seed: int) -> list[bytes]:
    """Play one self-play game (net priors + v2.7 leaf); return pickled
    decision boards snapshotted at the ply stride."""
    import pickle
    game = _W["game"]
    random.seed(seed)
    search = _make_search(_W["play_sims"], seed)
    board = game.get_init_board()
    out: list[bytes] = []
    ply = 0
    while game.get_game_ended(board, 0) == 0.0:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        search.clear()
        search.search(board)
        if (ply % _W["stride"] == 0) and legal.size >= _W["min_children"]:
            out.append(pickle.dumps(copy.deepcopy(board)))
        temperature = 1.0 if ply < _W["temp_threshold"] else 0.0
        action = search.select_for_training(board, temperature=temperature)
        board, _ = game.get_next_state(board, action)
        ply += 1
    return out


def probe_one(args) -> dict | None:
    import pickle
    idx, board_bytes = args
    board: Board = pickle.loads(board_bytes)
    game = _W["game"]
    rng = random.Random(0xC0FFEE ^ (idx * 2654435761))
    parent_player = board.state.current_player
    children = _unique_children(board, rng)
    if len(children) < 2:
        return None

    oracle = _make_search(_W["oracle_sims"], 0x5A5A ^ idx)
    oracle_q = np.empty(len(children), dtype=np.float64)
    for i, cb in enumerate(children):
        oracle.clear()
        oracle.search(cb)
        q = oracle.root_value(cb)
        flip = 1.0 if cb.state.current_player == parent_player else -1.0
        oracle_q[i] = flip * q

    v27 = np.array(
        [math.tanh(virtual_score_v2(cb.state, parent_player, DEFAULT_CONFIG) / 15.0)
         for cb in children],
        dtype=np.float64,
    )
    nv = _net_values(children)
    netv = np.array(
        [(nv[i] if children[i].state.current_player == parent_player else -nv[i])
         for i in range(len(children))],
        dtype=np.float64,
    )

    best = int(np.argmax(oracle_q))
    oq_best = float(oracle_q[best])

    def regret(scores):
        pick = int(np.argmax(scores))
        return float(oq_best - oracle_q[pick]), pick

    r_v27, pick_v27 = regret(v27)
    r_net, pick_net = regret(netv)
    return {
        "k": len(children),
        "tau_v27": kendall_tau_b(v27, oracle_q),
        "tau_net": kendall_tau_b(netv, oracle_q),
        "tau_net_v27": kendall_tau_b(netv, v27),
        "top1_v27": int(pick_v27 == best),
        "top1_net": int(pick_net == best),
        "regret_v27": r_v27,
        "regret_net": r_net,
        "regret_rand": float(oq_best - oracle_q.mean()),
        "regret_v27_pts": _to_margin(oq_best) - _to_margin(float(oracle_q[pick_v27])),
        "regret_net_pts": _to_margin(oq_best) - _to_margin(float(oracle_q[pick_net])),
        "oracle_spread": float(oracle_q.max() - oracle_q.min()),
    }


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="probe_decision_ranking")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--n-positions", type=int, default=250)
    ap.add_argument("--oracle-sims", type=int, default=400)
    ap.add_argument("--play-sims", type=int, default=60)
    ap.add_argument("--max-children", type=int, default=16)
    ap.add_argument("--min-children", type=int, default=3)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--temp-threshold", type=int, default=20)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out", type=Path, default=Path("/tmp/decision_ranking"))
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    # Empirically ~25-35 decision positions per full game at stride 4-6; launch
    # just enough games (+margin). The harvest pool is terminated as soon as we
    # have n_positions, so a small over-launch only wastes in-flight games.
    per_game = max(4, (2 * 70) // args.stride // 2)
    n_games = math.ceil(args.n_positions / per_game) + 3

    print(f"probe: ckpt={args.checkpoint}")
    print(f"  n_positions={args.n_positions} oracle_sims={args.oracle_sims} "
          f"play_sims={args.play_sims} max_children={args.max_children} "
          f"c_puct={args.c_puct} workers={args.workers}")
    print(f"  v2.7 leaf: DROP_THREE_OPEN={os.environ['CARCASSONNE_V25_DROP_THREE_OPEN']} "
          f"CAP={os.environ['CARCASSONNE_V25_CAP']}")

    init_args = (str(args.checkpoint), args.play_sims, args.oracle_sims,
                 args.c_puct, args.max_children, args.min_children,
                 args.stride, args.temp_threshold)
    ctx = mp.get_context("fork")  # CPU-only workers; no CUDA -> fork is safe
    t0 = time.perf_counter()

    print(f"[1/2] harvesting positions (<= {n_games} games across {args.workers} workers)...",
          flush=True)
    # Harvest pool: terminated (via `with` exit) as soon as we have enough, so
    # leftover in-flight games don't contend with the probe phase.
    boards: list[bytes] = []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=init_args) as pool:
        game_seeds = [args.seed + i for i in range(n_games)]
        for gi, blist in enumerate(pool.imap_unordered(harvest_game, game_seeds)):
            boards.extend(blist)
            print(f"  harvest: {len(boards)} positions ({gi + 1} games done)",
                  flush=True)
            if len(boards) >= args.n_positions:
                break
        pool.terminate()
    boards = boards[:args.n_positions]
    t_harvest = time.perf_counter() - t0
    print(f"  harvested {len(boards)} positions in {t_harvest:.1f}s", flush=True)

    print("[2/2] probing each position (deep oracle per child)...", flush=True)
    rows: list[dict] = []
    t1 = time.perf_counter()
    tasks = list(enumerate(boards))
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=init_args) as pool:
        for done, r in enumerate(pool.imap_unordered(probe_one, tasks)):
            if r is not None:
                rows.append(r)
            if (done + 1) % 25 == 0:
                el = time.perf_counter() - t1
                print(f"  {done + 1}/{len(tasks)} probed ({el / (done + 1):.2f}s/pos)",
                      flush=True)

    if not rows:
        print("ERROR: no usable decision nodes harvested.", file=sys.stderr)
        return 1

    def agg(key):
        vals = np.array([r[key] for r in rows
                         if not (isinstance(r[key], float) and math.isnan(r[key]))],
                        dtype=np.float64)
        return float(vals.mean()), float(vals.std() / math.sqrt(max(len(vals), 1)))

    n = len(rows)
    summary = {
        "checkpoint": str(args.checkpoint),
        "n_nodes": n,
        "mean_k": float(np.mean([r["k"] for r in rows])),
        "config": {
            "n_positions": args.n_positions, "oracle_sims": args.oracle_sims,
            "play_sims": args.play_sims, "max_children": args.max_children,
            "c_puct": args.c_puct, "stride": args.stride, "seed": args.seed,
            "v25_cap": os.environ["CARCASSONNE_V25_CAP"],
            "v25_drop_three_open": os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"],
        },
    }
    for key in ("tau_v27", "tau_net", "tau_net_v27", "top1_v27", "top1_net",
                "regret_v27", "regret_net", "regret_rand",
                "regret_v27_pts", "regret_net_pts", "oracle_spread"):
        m, se = agg(key)
        summary[key] = {"mean": m, "se": se}

    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.out / "rows.json").write_text(json.dumps(rows))

    el = time.perf_counter() - t0
    print()
    print("=" * 64)
    print(f"DECISION-RANKING PROBE  ({n} nodes, mean k={summary['mean_k']:.1f}, "
          f"oracle_sims={args.oracle_sims}, {el:.0f}s)")
    print("=" * 64)
    print(f"  {'metric':<22} {'value-net':>16} {'v2.7':>16}")
    print(f"  {'-'*22} {'-'*16} {'-'*16}")
    print(f"  {'Kendall-tau vs oracle':<22} "
          f"{summary['tau_net']['mean']:>+10.3f}+-{summary['tau_net']['se']:.3f} "
          f"{summary['tau_v27']['mean']:>+10.3f}+-{summary['tau_v27']['se']:.3f}")
    print(f"  {'top-1 == oracle best':<22} "
          f"{summary['top1_net']['mean']:>16.3f} "
          f"{summary['top1_v27']['mean']:>16.3f}")
    print(f"  {'oracle regret (tanh)':<22} "
          f"{summary['regret_net']['mean']:>16.4f} "
          f"{summary['regret_v27']['mean']:>16.4f}")
    print(f"  {'oracle regret (pts)':<22} "
          f"{summary['regret_net_pts']['mean']:>16.3f} "
          f"{summary['regret_v27_pts']['mean']:>16.3f}")
    print()
    print(f"  random-pick regret (tanh) : {summary['regret_rand']['mean']:.4f}  "
          f"(scale: oracle spread {summary['oracle_spread']['mean']:.3f})")
    print(f"  tau(value-net, v2.7)      : {summary['tau_net_v27']['mean']:+.3f}  "
          f"(do the two rankers even agree?)")
    print()
    print("  PREDICTION: value-net tau LOW + regret HIGH despite corr 0.84,")
    print("  v2.7 tau HIGH + regret LOW -> confirms the LOSS is the problem.")
    print(f"  -> wrote {args.out}/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
