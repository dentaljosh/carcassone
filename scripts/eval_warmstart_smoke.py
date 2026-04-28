"""Evaluate a trained warm-start network in a network-vs-random tournament.

Network plays argmax(policy * mask); no MCTS at inference.

Usage:
  # Serial (default, simplest):
  python -u scripts/eval_warmstart_smoke.py --checkpoint <path> --n 100

  # Parallel (faster for big N; per-game JSON checkpoints support resume):
  python -u scripts/eval_warmstart_smoke.py --checkpoint <path> --n 100 --workers 4

Each game alternates which side the network plays. With --workers > 1,
per-game JSON results are checkpointed under
data/tournament/eval_phase3_t1/ so reruns skip cached games. With
--workers 1 the script is purely in-memory.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
import multiprocessing as mp
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet


REPO_ROOT = Path(__file__).resolve().parent.parent
T1_DIR = REPO_ROOT / "data" / "tournament" / "eval_phase3_t1"


@dataclass
class GameResult:
    seed: int
    net_player: int
    score_p0: int
    score_p1: int
    diff: int
    won: bool
    drew: bool
    moves: int


def _result_path(seed: int, net_player: int) -> Path:
    return T1_DIR / f"seed{seed:06d}_p{net_player}.json"


def _try_load(path: Path) -> GameResult | None:
    if not path.exists():
        return None
    try:
        with path.open() as fh:
            return GameResult(**json.load(fh))
    except Exception:
        return None


def _save(result: GameResult) -> None:
    path = _result_path(result.seed, result.net_player)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial.json")
    with tmp.open("w") as fh:
        json.dump(asdict(result), fh)
    tmp.replace(path)


_worker_net: CarcassonneNet | None = None
_worker_device: torch.device | None = None


def _worker_init(checkpoint_path: str) -> None:
    """Initialize the network in each worker process exactly once."""
    global _worker_net, _worker_device
    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=_worker_device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net


def network_action(net: CarcassonneNet, game: Game, board, mask: np.ndarray, device: torch.device) -> int:
    """Take the network's argmax over valid moves. Reuses the caller's Game
    so we don't allocate a new wrapper per inference call."""
    obs, scalars = game.get_canonical_form(board, board.state.current_player)
    obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
    scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
    mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(device)
    with torch.no_grad():
        logits, _ = net(obs_t, scalars_t)
        masked = logits.masked_fill(~mask_t, float("-inf"))
        return int(masked.argmax(dim=-1).item())


def play_one_game(net: CarcassonneNet, net_player: int, seed: int, device: torch.device) -> GameResult:
    import random
    random.seed(seed)
    rng = random.Random(seed + 1)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if cur == net_player:
            action = network_action(net, game, board, mask, device)
            if not mask[action]:
                action = int(rng.choice(legal))
        else:
            action = int(rng.choice(legal))
        board, _ = game.get_next_state(board, action)
        moves += 1
    s0, s1 = board.state.scores
    diff = (s0 - s1) if net_player == 0 else (s1 - s0)
    return GameResult(
        seed=seed, net_player=net_player,
        score_p0=s0, score_p1=s1, diff=diff,
        won=(diff > 0), drew=(diff == 0), moves=moves,
    )


def _play_one_pool(args: tuple[int, int]) -> GameResult:
    """Worker entry: check disk cache, otherwise play and save."""
    seed, net_player = args
    cached = _try_load(_result_path(seed, net_player))
    if cached is not None:
        return cached
    result = play_one_game(_worker_net, net_player, seed, _worker_device)
    _save(result)
    return result


def _run_serial(checkpoint: Path, n: int, seed_start: int) -> list[GameResult]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading {checkpoint} on {device} (serial)...")
    ckpt = torch.load(checkpoint, map_location=device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    print(f"  params: {net.param_count():,}")
    results: list[GameResult] = []
    for i in range(n):
        seed = seed_start + i
        net_player = i % 2
        result = play_one_game(net, net_player, seed, device)
        results.append(result)
        wins = sum(1 for r in results if r.won)
        if (i + 1) % 5 == 0 or i == n - 1:
            print(f"  ... {i+1}/{n} done, net wins {wins}/{i+1}")
            sys.stdout.flush()
    return results


def _run_pool(checkpoint: Path, n: int, seed_start: int, n_workers: int) -> list[GameResult]:
    pool_args = [(seed_start + i, i % 2) for i in range(n)]
    print(f"Pool ({n_workers} workers), {n} games, checkpoints in {T1_DIR}")
    results: list[GameResult] = []
    # 'spawn' start method: CUDA cannot reinit in forked subprocesses.
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n_workers, initializer=_worker_init, initargs=(str(checkpoint),)) as pool:
        for done, result in enumerate(pool.imap_unordered(_play_one_pool, pool_args, chunksize=1), 1):
            results.append(result)
            wins = sum(1 for r in results if r.won)
            if done % 5 == 0 or done == n:
                print(f"  ... {done}/{n} done, net wins {wins}/{done}")
                sys.stdout.flush()
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval_warmstart_smoke")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed-start", type=int, default=10000)
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="1 = serial in-memory (no checkpoints); >1 = Pool with per-game JSON checkpoints. "
             "On CUDA, capped to 4 to avoid GPU thrash.",
    )
    args = p.parse_args(argv)

    n_workers = args.workers
    if torch.cuda.is_available() and n_workers > 4:
        print(f"  CUDA detected — capping workers from {n_workers} to 4 to avoid GPU thrash")
        n_workers = 4
    elif not torch.cuda.is_available() and n_workers > 1:
        n_workers = min(n_workers, os.cpu_count() or 1)

    t0 = time.perf_counter()
    if n_workers <= 1:
        results = _run_serial(args.checkpoint, args.n, args.seed_start)
    else:
        results = _run_pool(args.checkpoint, args.n, args.seed_start, n_workers)
    elapsed = time.perf_counter() - t0

    wins = sum(1 for r in results if r.won)
    draws = sum(1 for r in results if r.drew)
    losses = args.n - wins - draws
    avg_diff = sum(r.diff for r in results) / args.n
    avg_moves = sum(r.moves for r in results) / args.n

    print()
    print(f"Network vs random: {wins}/{args.n} wins ({wins/args.n:.1%})")
    print(f"  draws: {draws}, losses: {losses}")
    print(f"  avg score diff (net - random): {avg_diff:+.1f}")
    print(f"  avg moves/game: {avg_moves:.0f}")
    print(f"  total wallclock: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
