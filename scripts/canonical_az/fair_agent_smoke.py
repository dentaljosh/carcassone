#!/usr/bin/env python3
"""Legality smoke for the production fair mode (src/carcassonne_ai/fair_agent.py).

Plays N complete games of FairHeuristicMCTSAgent(sims, K, pooled-Q, marginalized
K<=2 exact handoff) vs the CLAIRVOYANT champion search (HeuristicMCTS at the same
sims), asserting every returned action is legal, and reports scores + handoff
instrumentation.

⚠️ THIS IS A PLUMBING/LEGALITY PROOF, **NOT A STRENGTH CLAIM** — at n=5 the
result is pure noise (n=100 is only a coarse screen at ±35 elo 1σ; see CLAUDE.md
n-thresholds). The K×depth fair-vs-clair sweep is a separate, queued run.

Usage:
  nice -n 19 python scripts/canonical_az/fair_agent_smoke.py \
      --games 5 --sims 400 --k 4 --workers 5
"""
from __future__ import annotations

import os
# v2.9 Bmild_cap8 champion leaf env — MUST precede the carcassonne_ai imports
# (DEFAULT_CONFIG reads these at import). Matches fairness_decision_probe.py.
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent   # noqa: E402
from carcassonne_ai.game_wrapper import Game                   # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS                  # noqa: E402

_CTX: dict = {}


def play_one(args_tuple):
    seed, fair_seat = args_tuple
    sims, K = _CTX["sims"], _CTX["k"]
    random.seed(seed)                      # engine deck shuffle
    game = Game(enable_legal_moves_cache=True)   # referee
    board = game.get_init_board()

    fair = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                  sims=sims, k_dets=K, c_puct=3.0, seed=seed,
                                  heur_leaf="v2_7", exact_endgame=True)
    clair = HeuristicMCTS(game=Game(enable_legal_moves_cache=True),
                          simulations=sims, c=3.0, seed=seed + 1,
                          heur_leaf="v2_7")
    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        if cur == fair_seat:
            a = fair.choose_action(board)
        else:
            clair.clear()
            a = int(clair.best_action(board))
        assert mask[a], f"ILLEGAL action {a} (seed={seed}, mover={cur}, ply={moves})"
        board, _ = game.get_next_state(board, a)
        moves += 1
    s0, s1 = board.state.scores
    diff = (s0 - s1) if fair_seat == 0 else (s1 - s0)   # fair-agent perspective
    return {
        "seed": seed, "fair_seat": fair_seat, "scores": (int(s0), int(s1)),
        "fair_diff": int(diff), "moves": moves,
        "secs": round(time.perf_counter() - t0, 1),
        "fair_pimc_moves": fair.heur_moves, "fair_exact_moves": fair.exact_moves,
        "latch_k": fair.latch_k, "timeouts": fair.n_timeouts,
        "solver_secs": round(fair.solver_secs, 2),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--sims", type=int, default=400)
    ap.add_argument("--k", type=int, default=4, help="PIMC determinizations")
    ap.add_argument("--seed-start", type=int, default=77_000_000)
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args(argv)

    _CTX.update(sims=args.sims, k=args.k)
    work = [(args.seed_start + i, i % 2) for i in range(args.games)]
    print(f"[smoke] {args.games} games: FairAgent(sims={args.sims},K={args.k},"
          f"pooled-Q,exact<=2) vs clairvoyant heur@{args.sims} | W{args.workers}",
          flush=True)
    t0 = time.time()
    if args.workers <= 1:
        results = [play_one(w) for w in work]
    else:
        from multiprocessing import get_context
        with get_context("fork").Pool(min(args.workers, len(work))) as pool:
            results = list(pool.imap_unordered(play_one, work))
    results.sort(key=lambda r: r["seed"])
    for r in results:
        print(f"  seed={r['seed']} fair_seat={r['fair_seat']} "
              f"scores={r['scores'][0]}-{r['scores'][1]} fair_diff={r['fair_diff']:+d} "
              f"moves={r['moves']} | pimc={r['fair_pimc_moves']} "
              f"exact={r['fair_exact_moves']} latch_k={r['latch_k']} "
              f"timeouts={r['timeouts']} solver={r['solver_secs']}s | {r['secs']}s",
              flush=True)
    w = sum(1 for r in results if r["fair_diff"] > 0)
    d = sum(1 for r in results if r["fair_diff"] == 0)
    print(f"[smoke] ALL {len(results)} GAMES LEGAL+COMPLETE in "
          f"{(time.time() - t0) / 60:.1f} min | fair {w}W/{d}D/"
          f"{len(results) - w - d}L, mean diff "
          f"{sum(r['fair_diff'] for r in results) / len(results):+.1f}")
    print("[smoke] NOT A STRENGTH CLAIM — n=%d is pure noise; the K×depth sweep "
          "is the queued strength measurement." % len(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
