"""MCTS-vs-random tournament with per-game checkpointing.

Phase 2 acceptance criterion: MCTS at s=50 (or s=100) beats random in a
strong majority of games. The 2020 paper reports MCTS s=100 winning
~95-100% vs Star2.5; we expect even higher win rate vs uniform random.

The Pool worker creates a fresh Game and MCTS per game (process-isolated;
no shared state). Each worker picks one side as MCTS, the other as random,
alternating between games.

CHECKPOINTING: each completed game writes its result to
data/tournament/<sims>_<seed>_<mcts_player>.json. On rerun, finished
seeds are skipped. To clear and start over:
    python scripts/play_mcts_vs_random.py --reset

This makes the run resumable across kills, optimization swaps, machine
restarts. Stdout is unbuffered (-u recommended at the python level) so
progress prints flush immediately.

Run:
  python -u scripts/play_mcts_vs_random.py --n 100 --sims 50
  python -u scripts/play_mcts_vs_random.py --reset --n 100 --sims 50
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import MCTS


REPO_ROOT = Path(__file__).resolve().parent.parent
TOURNAMENT_DIR = REPO_ROOT / "data" / "tournament"


@dataclass
class GameResult:
    seed: int
    sims: int
    mcts_player: int
    score_p0: int
    score_p1: int
    diff_mcts_minus_random: int
    won_by_mcts: bool
    drew: bool
    elapsed_s: float
    moves: int


def _result_path(sims: int, seed: int, mcts_player: int) -> Path:
    return TOURNAMENT_DIR / f"s{sims:04d}_seed{seed:06d}_p{mcts_player}.json"


def _try_load(path: Path) -> GameResult | None:
    if not path.exists():
        return None
    try:
        with path.open() as fh:
            data = json.load(fh)
        return GameResult(**data)
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _save(result: GameResult) -> None:
    path = _result_path(result.sims, result.seed, result.mcts_player)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        json.dump(asdict(result), fh)
    tmp.replace(path)  # atomic on POSIX


def _play_one(args: tuple[int, int, int]) -> GameResult:
    """Play one game OR resume from cached result. seed used for both deck
    shuffle (deterministic) and rollout RNG."""
    seed, mcts_player, sims = args
    cached = _try_load(_result_path(sims, seed, mcts_player))
    if cached is not None:
        return cached

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
            mcts.clear()
            action = mcts.best_action(board)
        else:
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            action = int(rng.choice(legal))
        board, _ = game.get_next_state(board, action)
        moves += 1

    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if mcts_player == 0 else (s1 - s0)
    result = GameResult(
        seed=seed,
        sims=sims,
        mcts_player=mcts_player,
        score_p0=s0,
        score_p1=s1,
        diff_mcts_minus_random=diff,
        won_by_mcts=(diff > 0),
        drew=(diff == 0),
        elapsed_s=elapsed,
        moves=moves,
    )
    _save(result)
    return result


def _summary(results: list[GameResult], sims: int, n_workers: int) -> int:
    mcts_wins = sum(1 for r in results if r.won_by_mcts)
    draws = sum(1 for r in results if r.drew)
    losses = len(results) - mcts_wins - draws
    avg_diff = sum(r.diff_mcts_minus_random for r in results) / len(results)
    avg_moves = sum(r.moves for r in results) / len(results)
    avg_elapsed = sum(r.elapsed_s for r in results) / len(results)

    print()
    print(f"Tournament: MCTS(s={sims}) vs random, {len(results)} games, {n_workers} workers")
    print(f"  MCTS wins:   {mcts_wins}/{len(results)} ({mcts_wins / len(results):.1%})")
    print(f"  draws:       {draws}/{len(results)}")
    print(f"  MCTS losses: {losses}/{len(results)}")
    print(f"  avg score diff (MCTS − random): {avg_diff:+.1f}")
    print(f"  avg moves/game: {avg_moves:.0f}")
    print(f"  avg wall-clock per game: {avg_elapsed:.1f}s")

    if mcts_wins / len(results) >= 0.95:
        print("\n  PASS: MCTS wins ≥ 95% of games against random.")
        return 0
    print(f"\n  FAIL: MCTS wins {mcts_wins / len(results):.1%}, target ≥95%.")
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="play_mcts_vs_random")
    p.add_argument("--n", type=int, default=100, help="number of games")
    p.add_argument("--sims", type=int, default=50, help="MCTS simulations per move")
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--reset", action="store_true",
                   help="Wipe data/tournament/ before starting (full restart)")
    p.add_argument("--summary-only", action="store_true",
                   help="Don't run any games; just summarize what's already on disk for these (n, sims, seed-start)")
    args = p.parse_args(argv)

    if args.reset:
        if TOURNAMENT_DIR.exists():
            shutil.rmtree(TOURNAMENT_DIR)
        print(f"Wiped {TOURNAMENT_DIR}")

    pool_args = [(args.seed_start + i, i % 2, args.sims) for i in range(args.n)]

    # Probe checkpoint state up front.
    already_done = sum(1 for a in pool_args if _result_path(args.sims, a[0], a[1]).exists())
    n_remaining = args.n - already_done

    if args.summary_only:
        results = [r for r in (_try_load(_result_path(args.sims, a[0], a[1])) for a in pool_args) if r is not None]
        if not results:
            print("No saved games for these parameters.")
            return 0
        return _summary(results, args.sims, n_workers=0)

    n_workers = args.workers or min(os.cpu_count() or 1, max(n_remaining, 1))
    print(f"Tournament: MCTS(s={args.sims}) vs random, {args.n} games, {n_workers} workers")
    if already_done:
        print(f"  Resuming: {already_done}/{args.n} already on disk, {n_remaining} to play")
    else:
        print(f"  ETA firms up after the first game finishes.")

    results: list[GameResult] = []
    t0 = time.perf_counter()
    first_done_t: float | None = None
    if n_remaining > 0:
        with Pool(processes=n_workers) as pool:
            for r in pool.imap_unordered(_play_one, pool_args, chunksize=1):
                results.append(r)
                n = len(results)
                if first_done_t is None and n > already_done:
                    first_done_t = time.perf_counter()
                    first_s = first_done_t - t0
                    eta_remaining = (args.n - n) * first_s / n_workers
                    m, s = divmod(eta_remaining, 60)
                    print(f"  [ETA] first new game took {first_s:.0f}s; "
                          f"~{int(m)}m{int(s):02d}s for {args.n - n} more")
                    sys.stdout.flush()
                if n % 10 == 0 or n == args.n:
                    wins = sum(1 for x in results if x.won_by_mcts)
                    print(f"  ... {n}/{args.n} done, MCTS {wins}/{n} so far")
                    sys.stdout.flush()
    else:
        # Everything cached; just load.
        results = [_try_load(_result_path(args.sims, a[0], a[1])) for a in pool_args]
        results = [r for r in results if r is not None]

    return _summary(results, args.sims, n_workers)


if __name__ == "__main__":
    sys.exit(main())
