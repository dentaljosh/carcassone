"""L2-3 endgame-regret harness.

For each position in the fixed suite: reconstruct the Board (replay), solve the
GROUND TRUTH in both modes (marginalized = preferred, clairvoyant = fallback;
node-budget skips intractable ones), query each agent's move, and record
regret (points lost vs optimal) + top-1 agreement. Pure CPU, parallel over
positions (each independent), per-position checkpoint = resumable + cluster-able.

Agents: iter8 (production NeuralMCTS@200), heur@{800,1600,3200} (v2.7 leaf),
greedy (1-ply), heur_v1@200. Each agent's move = best_action(board) at its
normal (clairvoyant) settings — we score THEIR move with the solver.

Usage:
  python scripts/level2/endgame_regret.py --suite measurement/level2/l23_positions.jsonl \
      --out-root /mnt/c/carc-shared/l23_regret --ckpt <iter8.pt> --workers 14 \
      --budget 150000 --modes marginalized clairvoyant [--agents iter8 heur@800 ...]
      [--shared-claim --claim-host 5800x]
"""
from __future__ import annotations

import os
# v2.7 production leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Matches the L1 ladder / production.
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import dataclasses
import json
import math
import socket
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import torch

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
import endgame_solver as S
from gen_endgame_positions import replay_to

# default agent set
ALL_AGENTS = ["iter8", "heur@800", "heur@1600", "heur@3200", "greedy", "heur_v1@200"]

_W: dict = {}  # per-worker state (net, agents)


def _heur_sims(name: str) -> int:
    return int(name.split("@")[1])


def _worker_init(ckpt: str, agents: list[str], device_str: str):
    torch.set_num_threads(1)
    dev = torch.device(device_str)
    _W["dev"] = dev
    _W["agents"] = agents
    _W["ckpt"] = ckpt
    if "iter8" in agents:
        ck = torch.load(ckpt, map_location=dev, weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
        net.load_state_dict(ck["model_state"])
        net.train(False)
        _W["net"] = net
        _W["ns"] = ns


def _agent_move(name: str, game_farm: Game, game_plain: Game, board, seed: int) -> int:
    """The agent's chosen action_idx at `board` (production/clairvoyant settings)."""
    if name == "greedy":
        rb = RuleBasedPlayer(seed=seed)
        return int(rb.choose_action(game_plain, board, game_plain.get_valid_moves(board)))
    if name == "iter8":
        base = make_single_evaluator(_W["net"], _W["dev"], game_farm)
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=0.25)
        leaf = make_v25_value_wrapper(base, cfg)
        mcts = NeuralMCTS(game=game_farm, evaluator=leaf, simulations=200, seed=seed, c_puct=3.0)
        return int(mcts.best_action(board))
    # heuristic rungs
    leaf = "v1" if name.startswith("heur_v1") else "v2_7"
    mcts = HeuristicMCTS(game=game_plain, simulations=_heur_sims(name), seed=seed, heur_leaf=leaf)
    return int(mcts.best_action(board))


def _eval_one(rec: dict, modes: list[str], budget: int, agents: list[str]) -> dict:
    seed, ply = rec["seed"], rec["ply"]
    game, board = replay_to(seed, ply)                 # plain game (include_farm=False)
    game_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=(_W.get("ns", 10) > 10))
    move_seed = (seed * 131 + ply) & 0x7FFFFFFF

    # ground truth per mode
    gt = {}
    for mode in modes:
        t0 = time.perf_counter()
        try:
            res = S.solve(game, board, mode=mode, budget=budget)
            gt[mode] = {"value": res.value, "optimal": res.optimal_actions,
                        "child_values": {int(a): v for a, v in res.child_values.items()},
                        "to_move": res.to_move, "nodes": res.nodes,
                        "secs": round(time.perf_counter() - t0, 2), "solved": True}
        except S.BudgetExceeded:
            gt[mode] = {"solved": False, "nodes": budget, "secs": round(time.perf_counter() - t0, 2)}

    # agent moves (once per position; scored under each solved mode)
    moves = {}
    for a in agents:
        try:
            moves[a] = _agent_move(a, game_farm, game, board, move_seed)
        except Exception as e:  # noqa
            moves[a] = -1
            moves[a + "_err"] = str(e)[:80]

    out = {**{k: rec[k] for k in ("gen_id", "seed", "ply", "k_remaining", "to_move",
                                  "scores", "legal_n", "in_hand_tile", "bag_size")},
           "moves": moves, "gt": {}}
    for mode in modes:
        g = gt[mode]
        if not g["solved"]:
            out["gt"][mode] = {"solved": False, "nodes": g["nodes"], "secs": g["secs"]}
            continue
        cv = g["child_values"]
        per_agent = {}
        for a in agents:
            mv = moves.get(a, -1)
            if mv in cv:
                v = cv[mv]
                reg = (g["value"] - v) if g["to_move"] == 0 else (v - g["value"])
                per_agent[a] = {"move": mv, "regret": round(float(reg), 4),
                                "match": mv in g["optimal"]}
            else:
                per_agent[a] = {"move": mv, "regret": None, "match": False, "illegal": True}
        out["gt"][mode] = {"solved": True, "value": g["value"], "n_optimal": len(g["optimal"]),
                           "n_legal": len(cv), "nodes": g["nodes"], "secs": g["secs"],
                           "per_agent": per_agent}
    return out


# module-level pool target ------------------------------------------------- #
_CFG: dict = {}


def _task(rec):
    out = _CFG["out"]
    fp = out / f"{rec['gen_id']}_k{rec['k_remaining']}.json"
    if fp.exists():
        return ("cached", str(fp))
    if _CFG["shared_claim"]:
        if not _try_claim(fp.with_suffix(".claim"), _CFG["claim_host"], 5400):
            return ("claimed", None)
    res = _eval_one(rec, _CFG["modes"], _CFG["budget"], _CFG["agents"])
    tmp = fp.with_suffix(".tmp")
    json.dump(res, open(tmp, "w"))
    tmp.replace(fp)
    return ("done", str(fp))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="measurement/level2/l23_positions.jsonl")
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--budget", type=int, default=150_000)
    ap.add_argument("--modes", nargs="+", default=["marginalized", "clairvoyant"])
    ap.add_argument("--agents", nargs="+", default=ALL_AGENTS)
    ap.add_argument("--ks", type=int, nargs="+", default=None, help="restrict to these K")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-host", default=socket.gethostname())
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    recs = [json.loads(l) for l in open(args.suite)]
    if args.ks:
        recs = [r for r in recs if r["k_remaining"] in set(args.ks)]
    if args.limit:
        recs = recs[:args.limit]
    out = Path(args.out_root)
    out.mkdir(parents=True, exist_ok=True)

    _CFG.update(out=out, modes=args.modes, budget=args.budget, agents=args.agents,
                shared_claim=args.shared_claim, claim_host=args.claim_host)
    print(f"L2-3 regret: {len(recs)} positions, agents={args.agents}, modes={args.modes}, "
          f"budget={args.budget}, W={args.workers}, out={out}", flush=True)

    from multiprocessing import get_context
    ctx = get_context("fork")
    t0 = time.perf_counter()
    done = 0
    with ctx.Pool(args.workers, initializer=_worker_init,
                  initargs=(args.ckpt, args.agents, args.device)) as pool:
        for status, _ in pool.imap_unordered(_task, recs, chunksize=1):
            done += 1
            if done % 10 == 0:
                el = time.perf_counter() - t0
                print(f"  {done}/{len(recs)} ({el/done:.1f}s/pos, ~{(len(recs)-done)*el/done/60:.0f} min left)", flush=True)
    print(f"done {done} positions in {(time.perf_counter()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
