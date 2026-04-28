"""MCTS-vs-random tournament.

Phase 2 acceptance criterion: MCTS at s=50 (or s=100) beats random in a
strong majority of games. The 2020 paper reports MCTS s=100 winning ~95-100%
vs Star2.5; we expect even higher win rate vs uniform random play.

The Pool worker creates a fresh Game and MCTS per game (process-isolated; no
shared state). Each worker picks one side as MCTS, the other as random,
alternating between games.

Run:
  python scripts/play_mcts_vs_random.py --n 100 --sims 50
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from dataclasses import dataclass
from multiprocessing import Pool

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import MCTS


@dataclass
class GameResult:
    seed: int
    mcts_player: int
    score_p0: int
    score_p1: int
    diff_mcts_minus_random: int
    won_by_mcts: bool
    drew: bool
    elapsed_s: float
    moves: int


def _play_one(args: tuple[int, int, int]) -> GameResult:
    """Play one game. seed used for both deck shuffle (deterministic) and
    rollout RNG. mcts_player is 0 or 1 — whichever side MCTS plays."""
    seed, mcts_player, sims = args
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    mcts = MCTS(game=game, simulations=sims, seed=seed)
    rng = random.Random(seed + 1)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == mcts_player:
            mcts.clear()  # reset tree per move (per-search cache)
            action = mcts.best_action(board)
        else:
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            action = int(rng.choice(legal))
        board, _ = game.get_next_state(board, action)
        moves += 1

    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    if mcts_player == 0:
        diff = s0 - s1
    else:
        diff = s1 - s0
    won = diff > 0
    drew = diff == 0
    return GameResult(
        seed=seed,
        mcts_player=mcts_player,
        score_p0=s0,
        score_p1=s1,
        diff_mcts_minus_random=diff,
        won_by_mcts=won,
        drew=drew,
        elapsed_s=elapsed,
        moves=moves,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="play_mcts_vs_random")
    p.add_argument("--n", type=int, default=100, help="number of games")
    p.add_argument("--sims", type=int, default=50, help="MCTS simulations per move")
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--workers", type=int, default=None)
    args = p.parse_args(argv)

    n_workers = args.workers or min(os.cpu_count() or 1, args.n)

    # Build the work list. Alternate which player MCTS controls so we don't
    # bias by who-moves-first effects.
    pool_args = [(args.seed_start + i, i % 2, args.sims) for i in range(args.n)]

    # Skip the sample-game ETA: at s=10+ the sample alone takes minutes and
    # would block Pool startup. Print a coarse estimate based on quick-bench
    # numbers and let the user watch the progress bar.
    print(f"Tournament: MCTS(s={args.sims}) vs random, {args.n} games, {n_workers} workers")
    print(f"  ETA will firm up after the first game finishes.")

    results: list[GameResult] = []
    t0 = time.perf_counter()
    first_done_t: float | None = None
    with Pool(processes=n_workers) as pool:
        for r in pool.imap_unordered(_play_one, pool_args, chunksize=1):
            results.append(r)
            n = len(results)
            if first_done_t is None:
                first_done_t = time.perf_counter()
                first_s = first_done_t - t0
                # Once worker pipeline is full (n_workers games done in parallel),
                # remaining = (n_games - n_workers) / n_workers * per-game.
                # First-done time ≈ per-game time for one worker.
                eta_remaining = (args.n - n) * first_s / n_workers
                m, s = divmod(eta_remaining, 60)
                print(f"  [ETA] first game took {first_s:.0f}s; "
                      f"~{int(m)}m{int(s):02d}s remaining for {args.n - n} more")
            if n % 10 == 0 or n == args.n:
                wins = sum(1 for x in results if x.won_by_mcts)
                print(f"  ... {n}/{args.n} done, MCTS {wins}/{n} so far")

    # Summary
    mcts_wins = sum(1 for r in results if r.won_by_mcts)
    draws = sum(1 for r in results if r.drew)
    losses = len(results) - mcts_wins - draws
    avg_diff = sum(r.diff_mcts_minus_random for r in results) / len(results)
    avg_moves = sum(r.moves for r in results) / len(results)
    avg_elapsed = sum(r.elapsed_s for r in results) / len(results)

    print()
    print(f"Tournament: MCTS(s={args.sims}) vs random, {args.n} games, {n_workers} workers")
    print(f"  MCTS wins:   {mcts_wins}/{len(results)} ({mcts_wins / len(results):.1%})")
    print(f"  draws:       {draws}/{len(results)}")
    print(f"  MCTS losses: {losses}/{len(results)}")
    print(f"  avg score diff (MCTS − random): {avg_diff:+.1f}")
    print(f"  avg moves/game: {avg_moves:.0f}")
    print(f"  avg wall-clock per game: {avg_elapsed:.1f}s")

    # Acceptance: MCTS should win >= 95% to satisfy the Phase 2 criterion.
    if mcts_wins / len(results) >= 0.95:
        print("\n  PASS: MCTS wins ≥ 95% of games against random.")
        return 0
    print(f"\n  FAIL: MCTS wins {mcts_wins / len(results):.1%}, target ≥95%.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
