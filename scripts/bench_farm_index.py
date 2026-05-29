"""Throughput bench for the find_all_farms speedup (2026-05-29). Measure, don't
extrapolate (CLAUDE.md). Two levels:

  1. LEAF microbench — wall-clock of `virtual_score_v2` over a fixed set of
     representative mid/late-game states, index path ON vs OFF. Isolates the
     per-leaf speedup the v2.7 evaluator gets.

  2. SEARCH bench (optional, --search) — a real NeuralMCTS search at production
     sims with the v2.7 leaf wrapper but a uniform-prior CPU evaluator (no net /
     no GPU, so the leaf is the only nontrivial cost), index ON vs OFF. Shows
     the speedup's effect on actual MCTS wall-clock, where the leaf is one of
     several costs (priors, tree ops, get_next_state deepcopy).

The OFF path stubs `FarmUtil.find_all_farms -> {}` so every find_farm_by_
coordinate falls back to the original flood-fill — an honest A/B of the same
code with only the index disabled.

Usage:
  python scripts/bench_farm_index.py --games 8 --snap-every 6 --repeats 5
  python scripts/bench_farm_index.py --search --sims 200 --moves 6
"""
from __future__ import annotations

import argparse
import copy
import random
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from carcassonne_ai import virtual_score as _vs  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2  # noqa: E402


def collect_states(games, snap_every, seed_start, max_plies=400):
    game = Game()
    states = []
    for g in range(games):
        random.seed(seed_start + g)
        board = game.get_init_board()
        plies = 0
        while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
            plies += 1
            if plies % snap_every == 0 and game.get_game_ended(board, 0) == 0.0:
                states.append(copy.deepcopy(board.state))
    return states


def _time_leaf(states, repeats):
    t0 = time.perf_counter()
    for _ in range(repeats):
        for st in states:
            virtual_score_v2(st, 0, DEFAULT_CONFIG)
    return time.perf_counter() - t0


def bench_leaf(args):
    print(f"collecting states: {args.games} games, snap every {args.snap_every} ...")
    states = collect_states(args.games, args.snap_every, args.seed_start)
    print(f"collected {len(states)} states; {args.repeats} repeats each\n")
    n_evals = len(states) * args.repeats

    # warm caches / JIT-free Python; one untimed pass
    for st in states:
        virtual_score_v2(st, 0, DEFAULT_CONFIG)

    def timed(farm, city):
        _vs.USE_FARM_CACHE, _vs.USE_CITY_CACHE = farm, city
        return _time_leaf(states, args.repeats)

    try:
        off = timed(False, False)        # legacy: no memo
        farm_only = timed(True, False)   # farm memo only
        both = timed(True, True)         # farm + city memo (production)
    finally:
        _vs.USE_FARM_CACHE = _vs.USE_CITY_CACHE = True

    print("===== LEAF microbench (virtual_score_v2) =====")
    print(f"both OFF (legacy flood-fills):  {off:.3f}s  ({1e3*off/n_evals:.3f} ms/leaf)")
    print(f"farm memo only:                 {farm_only:.3f}s  ({1e3*farm_only/n_evals:.3f} ms/leaf)  {off/farm_only:.2f}x")
    print(f"farm + city memo (production):  {both:.3f}s  ({1e3*both/n_evals:.3f} ms/leaf)  {off/both:.2f}x")
    print(f"  -> city increment over farm-only: {farm_only/both:.2f}x ({100*(farm_only-both)/farm_only:.1f}% faster)")
    print(f"  -> total speedup:                 {off/both:.2f}x ({100*(off-both)/off:.1f}% faster)")


def bench_search(args):
    """NeuralMCTS at production sims with the v2.7 leaf + uniform-prior CPU
    evaluator (no net), index ON vs OFF."""
    from carcassonne_ai.mcts import NeuralMCTS
    from carcassonne_ai.evaluators import make_v25_value_wrapper

    game = Game()

    def uniform_eval(board):
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        priors = np.zeros(mask.shape, dtype=np.float32)
        if legal.size:
            priors[legal] = 1.0 / legal.size
        return priors, 0.0

    leaf_eval = make_v25_value_wrapper(uniform_eval, DEFAULT_CONFIG)

    def run_moves(seed):
        random.seed(seed)
        board = game.get_init_board()
        # advance to a mid-game position so farms exist
        for _ in range(80):
            if game.get_game_ended(board, 0) != 0.0:
                break
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        mcts = NeuralMCTS(game, evaluator=leaf_eval, simulations=args.sims, seed=seed)
        t0 = time.perf_counter()
        moves = 0
        b = board
        while moves < args.moves and game.get_game_ended(b, 0) == 0.0:
            mcts.clear()
            mcts.search(b)
            a = mcts.best_action(b)
            b, _ = game.get_next_state(b, a)
            moves += 1
        return time.perf_counter() - t0

    run_moves(args.seed_start)  # warm

    _vs.USE_FARM_CACHE = _vs.USE_CITY_CACHE = True
    on = sum(run_moves(args.seed_start + i) for i in range(args.bench_games))

    _vs.USE_FARM_CACHE = _vs.USE_CITY_CACHE = False
    try:
        off = sum(run_moves(args.seed_start + i) for i in range(args.bench_games))
    finally:
        _vs.USE_FARM_CACHE = _vs.USE_CITY_CACHE = True

    print(f"\n===== SEARCH bench (NeuralMCTS sims={args.sims}, v2.7 leaf, uniform prior) =====")
    print(f"{args.bench_games} games x {args.moves} moves each")
    print(f"caches OFF (legacy):        {off:.2f}s")
    print(f"caches ON  (farm + city):   {on:.2f}s")
    print(f"speedup:                    {off/on:.2f}x   ({100*(off-on)/off:.1f}% faster)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("--snap-every", type=int, default=6)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--seed-start", type=int, default=20000)
    ap.add_argument("--search", action="store_true", help="also run the NeuralMCTS search bench")
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--moves", type=int, default=6)
    ap.add_argument("--bench-games", type=int, default=3)
    args = ap.parse_args(argv)
    bench_leaf(args)
    if args.search:
        bench_search(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
