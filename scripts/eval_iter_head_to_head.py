"""Phase 4 head-to-head: iter_N vs iter_(N-1) with NeuralMCTS each side.

Both checkpoints run NeuralMCTS at the same simulation budget (eval-only,
no Dirichlet noise). Alternates which side plays first; per-game JSON
checkpointing so reruns skip cached games.

Output: writes a single ELO-log entry to `<output-root>/elo_log.json`
(appends if the file already exists). Per-game results live under
`<output-root>/eval/iter_<NN>_vs_<MM>/`.

Usage:
  python -u scripts/eval_iter_head_to_head.py \\
      --new-checkpoint checkpoints/selfplay/iter_01.pt \\
      --old-checkpoint checkpoints/selfplay/iter_00.pt \\
      --output-root data/selfplay/calibration \\
      --iter 1 --vs-iter 0 --games 10 --sims 50 --workers 4
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.elo import update_pair
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class GameResult:
    seed: int
    new_player: int
    sims: int
    score_p0: int
    score_p1: int
    diff: int  # new - old
    won_by_new: bool
    drew: bool
    elapsed_s: float
    moves: int


# Per-worker globals — both checkpoints loaded once per process.
_worker_new: CarcassonneNet | None = None
_worker_old: CarcassonneNet | None = None
_worker_device: torch.device | None = None
_worker_sims: int = 0
_worker_c_puct: float = 1.5
_worker_eval_dir: str = ""
_worker_batch_size: int = 1
_worker_virtual_loss: float = 1.0


def _result_path(eval_dir: str, sims: int, seed: int, new_player: int) -> Path:
    return Path(eval_dir) / f"s{sims:04d}_seed{seed:06d}_p{new_player}.json"


def _try_load(path: Path) -> GameResult | None:
    if not path.exists():
        return None
    try:
        with path.open() as fh:
            return GameResult(**json.load(fh))
    except Exception:
        return None


def _save(eval_dir: str, result: GameResult) -> None:
    path = _result_path(eval_dir, result.sims, result.seed, result.new_player)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial.json")
    with tmp.open("w") as fh:
        json.dump(asdict(result), fh)
    tmp.replace(path)


def _load_net(path: str, device: torch.device) -> CarcassonneNet:
    ckpt = torch.load(path, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net


def _worker_init(
    new_path: str, old_path: str, sims: int, c_puct: float, eval_dir: str,
    batch_size: int, virtual_loss: float,
) -> None:
    global _worker_new, _worker_old, _worker_device, _worker_sims, _worker_c_puct, _worker_eval_dir
    global _worker_batch_size, _worker_virtual_loss
    _worker_device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    _worker_new = _load_net(new_path, _worker_device)
    _worker_old = _load_net(old_path, _worker_device)
    _worker_sims = sims
    _worker_c_puct = c_puct
    _worker_eval_dir = eval_dir
    _worker_batch_size = batch_size
    _worker_virtual_loss = virtual_loss


def _make_evaluator(net: CarcassonneNet, game: Game, device: torch.device):
    def evaluator(board):
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
        with torch.no_grad():
            logits, value = net(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(device)
            probs = net.policy_softmax_with_mask(logits, mask_t)
        return probs[0].cpu().numpy(), float(value.item())
    return evaluator


def _make_batch_evaluator(net: CarcassonneNet, game: Game, device: torch.device):
    def batch_evaluator(boards):
        if not boards:
            return np.empty((0,), dtype=np.float32), np.empty((0,), dtype=np.float32)
        obs_list = []
        scalars_list = []
        masks_list = []
        for b in boards:
            obs, scalars = game.get_canonical_form(b, b.state.current_player)
            obs_list.append(obs)
            scalars_list.append(scalars)
            masks_list.append(game.get_valid_moves(b))
        obs_t = torch.from_numpy(np.stack(obs_list)).float().to(device)
        scalars_t = torch.from_numpy(np.stack(scalars_list)).float().to(device)
        masks_t = torch.from_numpy(np.stack(masks_list).copy()).bool().to(device)
        with torch.no_grad():
            logits, values = net(obs_t, scalars_t)
            probs = net.policy_softmax_with_mask(logits, masks_t)
        return probs.cpu().numpy(), values.cpu().numpy()
    return batch_evaluator


def _play_one(args: tuple[int, int]) -> GameResult:
    seed, new_player = args
    cached = _try_load(_result_path(_worker_eval_dir, _worker_sims, seed, new_player))
    if cached is not None:
        return cached

    import random
    random.seed(seed)

    game_new = Game(enable_legal_moves_cache=True)
    game_old = Game(enable_legal_moves_cache=True)
    new_eval = _make_evaluator(_worker_new, game_new, _worker_device)
    old_eval = _make_evaluator(_worker_old, game_old, _worker_device)
    new_batch_eval = None
    old_batch_eval = None
    if _worker_batch_size > 1:
        new_batch_eval = _make_batch_evaluator(
            _worker_new, game_new, _worker_device
        )
        old_batch_eval = _make_batch_evaluator(
            _worker_old, game_old, _worker_device
        )
    new_mcts = NeuralMCTS(
        game=game_new, evaluator=new_eval, simulations=_worker_sims,
        seed=seed, c_puct=_worker_c_puct,
        batch_size=_worker_batch_size, batch_evaluator=new_batch_eval,
        virtual_loss=_worker_virtual_loss,
    )
    old_mcts = NeuralMCTS(
        game=game_old, evaluator=old_eval, simulations=_worker_sims,
        seed=seed + 1, c_puct=_worker_c_puct,
        batch_size=_worker_batch_size, batch_evaluator=old_batch_eval,
        virtual_loss=_worker_virtual_loss,
    )

    board = game_new.get_init_board()
    moves = 0
    t0 = time.perf_counter()
    while game_new.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == new_player:
            new_mcts.clear()
            action = new_mcts.best_action(board)
        else:
            old_mcts.clear()
            action = old_mcts.best_action(board)
        board, _ = game_new.get_next_state(board, action)
        moves += 1

    s0, s1 = board.state.scores
    diff = (s0 - s1) if new_player == 0 else (s1 - s0)
    result = GameResult(
        seed=seed, new_player=new_player, sims=_worker_sims,
        score_p0=s0, score_p1=s1, diff=diff,
        won_by_new=(diff > 0), drew=(diff == 0),
        elapsed_s=time.perf_counter() - t0, moves=moves,
    )
    _save(_worker_eval_dir, result)
    return result


def _append_elo_log(
    output_root: Path, iter_n: int, iter_prev: int,
    wins: int, losses: int, draws: int,
) -> dict:
    log_path = output_root / "elo_log.json"
    entries: list[dict]
    if log_path.exists():
        with log_path.open() as fh:
            entries = json.load(fh)
    else:
        entries = []

    # Anchor: previous iter's ELO is whatever the latest log entry recorded
    # for it. iter_-1 baseline is 0.
    prev_elo = 0.0
    for e in entries:
        if e["iter"] == iter_prev:
            prev_elo = float(e["elo_estimate"])
    new_elo, delta = update_pair(
        iter_n_elo_estimate=0.0,
        iter_prev_elo=prev_elo,
        wins=wins, losses=losses, draws=draws,
    )
    entry = {
        "iter": iter_n,
        "vs_iter": iter_prev,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "elo_delta": round(delta, 1),
        "elo_estimate": round(new_elo, 1),
    }
    entries.append(entry)
    with log_path.open("w") as fh:
        json.dump(entries, fh, indent=2)
    return entry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval_iter_head_to_head")
    p.add_argument("--new-checkpoint", type=Path, required=True)
    p.add_argument("--old-checkpoint", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--iter", type=int, required=True, dest="iter_idx")
    p.add_argument("--vs-iter", type=int, required=True)
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--sims", type=int, default=50)
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--workers", type=int, default=4,
                   help="Pool workers (CUDA caps to 4 internally unless "
                        "--no-cuda-cap is set).")
    p.add_argument(
        "--no-cuda-cap", action="store_true",
        help="Skip the 4-worker CUDA cap for head-to-head. Each game runs "
             "two networks per worker (2× the per-worker GPU memory), so "
             "be a bit more careful here than in self-play.",
    )
    p.add_argument("--seed-start", type=int, default=900_000,
                   help="Eval seed base (kept high so it doesn't collide with "
                        "self-play seeds, which use iter * 10_000 + game_idx).")
    p.add_argument(
        "--batch-size", type=int, default=1,
        help="NeuralMCTS batch size for virtual-loss / batched-eval mode "
             "during head-to-head. 1 (default) = serial.",
    )
    p.add_argument(
        "--virtual-loss", type=float, default=1.0,
        help="W-penalty for in-flight nodes; only matters when --batch-size > 1.",
    )
    args = p.parse_args(argv)

    eval_dir = (
        args.output_root / "eval" /
        f"iter_{args.iter_idx:02d}_vs_{args.vs_iter:02d}"
    )
    eval_dir.mkdir(parents=True, exist_ok=True)

    n_workers = args.workers
    if torch.cuda.is_available() and n_workers > 4 and not args.no_cuda_cap:
        print(f"  CUDA detected — capping workers from {n_workers} to 4 "
              "(use --no-cuda-cap to lift)")
        n_workers = 4
    n_workers = min(n_workers, args.games)

    pool_args = [
        (args.seed_start + i, i % 2) for i in range(args.games)
    ]
    print(
        f"head-to-head: iter_{args.iter_idx:02d} vs iter_{args.vs_iter:02d}, "
        f"{args.games} games at sims={args.sims}, c_puct={args.c_puct}, "
        f"{n_workers} workers, eval_dir={eval_dir}"
    )
    sys.stdout.flush()

    t0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    results: list[GameResult] = []
    with ctx.Pool(
        processes=n_workers,
        initializer=_worker_init,
        initargs=(
            str(args.new_checkpoint), str(args.old_checkpoint),
            args.sims, args.c_puct, str(eval_dir),
            args.batch_size, args.virtual_loss,
        ),
    ) as pool:
        for done, r in enumerate(
            pool.imap_unordered(_play_one, pool_args, chunksize=1), 1
        ):
            results.append(r)
            wins_so_far = sum(1 for x in results if x.won_by_new)
            if done % max(1, args.games // 5) == 0 or done == args.games:
                print(f"  ... {done}/{args.games}, new wins {wins_so_far}/{done}")
                sys.stdout.flush()
    elapsed = time.perf_counter() - t0

    wins = sum(1 for r in results if r.won_by_new)
    draws = sum(1 for r in results if r.drew)
    losses = args.games - wins - draws
    avg_diff = sum(r.diff for r in results) / args.games

    entry = _append_elo_log(
        args.output_root, args.iter_idx, args.vs_iter, wins, losses, draws
    )
    print(
        f"\niter_{args.iter_idx:02d} vs iter_{args.vs_iter:02d}: "
        f"{wins}W/{draws}D/{losses}L, avg diff {avg_diff:+.1f}, "
        f"elo_delta {entry['elo_delta']:+.1f} → elo_estimate {entry['elo_estimate']:+.1f}, "
        f"wallclock {elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
