#!/usr/bin/env python3
"""Gate G-CACHE: the injective key must not silently disable memoization.

The key got LONGER (a farm-slot tuple per placed tile, plus next_tile's
signature and the big-meeple/abbot supplies). Two things could go wrong and
both are invisible to a correctness test:
  1. the hit RATE collapses because keys that used to coincide no longer do
     (the collisions were "hits"), i.e. the fix pays for correctness in
     memoization; and
  2. the per-key COST rises enough to make the memo net-negative.

This replays ONE game — a real `NeuralMCTS` search per ply against the
heuristic-prior evaluator, which is the shape the memo was built for (~22K
`string_representation` calls per game folded onto the unique states visited)
— and reports hits / misses / entries / wall-clock. Run it once per key mode
and diff. It asserts nothing: the numbers are the gate evidence.

Usage: CARCASSONNE_FIX_LEGAL_CACHE_KEY=0|1 cache_effectiveness.py --out F
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=880777001)
    ap.add_argument("--sims", type=int, default=32)
    ap.add_argument("--plies", type=int, default=40)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import carcassonne_ai.game_wrapper as gw
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.heuristic_prior_mcts import (
        HeuristicPriorConfig,
        make_heuristic_prior_evaluator,
    )
    from carcassonne_ai.mcts import NeuralMCTS

    random.seed(a.seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    cfg = HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                               final_select="visits")
    ev = make_heuristic_prior_evaluator(game, cfg)
    rng = random.Random(a.seed ^ 0xBEEF)

    t0 = time.time()
    played = 0
    for _ in range(a.plies):
        if game.get_game_ended(board, 0) != 0.0:
            break
        m = NeuralMCTS(game=game, evaluator=ev, simulations=a.sims,
                       c_puct=cfg.c_puct, seed=17)
        m.search(board)
        act = int(m.best_action(board))
        legal = np.flatnonzero(game.get_valid_moves(board))
        if act not in legal:            # defensive; never expected
            act = int(rng.choice(legal))
        board, _ = game.get_next_state(board, act)
        played += 1

    st = game.cache_stats()
    out = {
        "fix_legal_cache_key": gw._FIX_LEGAL_CACHE_KEY,
        "seed": a.seed, "sims": a.sims, "plies_played": played,
        "secs": round(time.time() - t0, 2),
        "hits": st["hits"], "misses": st["misses"], "entries": st["size"],
        "hit_rate": round(st["hit_rate"], 6),
        "mean_key_bytes": round(
            len(game.string_representation(board).encode()), 1),
    }
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
