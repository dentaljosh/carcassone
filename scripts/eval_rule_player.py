"""Head-to-head harness for the rule-based Tier-1 baseline.

Plays N games of (rule_player vs opponent), alternating sides each game.
Opponent can be:
  - 'random'     — uniform random over legal actions
  - 'mcts'       — vanilla MCTS at --sims simulations (random rollouts)
  - 'checkpoint' — NeuralMCTS driven by a trained network checkpoint

For 'checkpoint' the harness uses a multiprocessing pool ('spawn' context) so
each worker holds its own CUDA context. Per-game results are NOT cached on
disk — this script is meant for one-off bench runs, not large tournaments.

Usage:
    # Sanity vs random
    python scripts/eval_rule_player.py --n 50 --opponent random
    # Vanilla-MCTS opponent
    python scripts/eval_rule_player.py --n 50 --opponent mcts --sims 100
    # NN-checkpoint opponent (Tier-1 vs warmstart_canonical)
    python scripts/eval_rule_player.py --n 50 --opponent checkpoint \\
        --checkpoint checkpoints/warmstart_canonical.pt --sims 100

Reports W/D/L from rule-player's perspective and approximate ELO delta.
"""
from __future__ import annotations

import argparse
import math
import multiprocessing as mp
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import MCTS, NeuralMCTS
from carcassonne_ai.rule_based_player import RuleBasedPlayer


# Worker-side state for checkpoint mode — initialized once per process.
_worker_net = None
_worker_device = None


def _worker_init(checkpoint_path: str) -> None:
    """Initialize the network in each worker process exactly once."""
    global _worker_net, _worker_device
    import torch
    from carcassonne_ai.network import CarcassonneNet

    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=_worker_device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net


def _network_evaluator(game: Game):
    """Returns a Callable[[Board], (priors, value)] using the worker's net."""
    import torch

    def evaluator(board):
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(_worker_device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(_worker_device)
        with torch.no_grad():
            logits, value = _worker_net(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(_worker_device)
            probs = _worker_net.policy_softmax_with_mask(logits, mask_t)
        return probs[0].cpu().numpy(), float(value.item())

    return evaluator


def play_one(args: tuple) -> dict:
    seed, rule_player_idx, opponent, sims = args
    rng = random.Random(seed)
    rule = RuleBasedPlayer(seed=seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    opp = None
    if opponent == "mcts":
        opp = MCTS(game=Game(enable_legal_moves_cache=True), simulations=sims, seed=seed + 1)
    elif opponent == "checkpoint":
        evaluator = _network_evaluator(game)
        opp = NeuralMCTS(
            game=game,
            evaluator=evaluator,
            simulations=sims,
            seed=seed + 1,
        )

    moves = 0
    t0 = time.perf_counter()
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if cur == rule_player_idx:
            action = rule.choose_action(game, board, mask)
        elif opponent == "random":
            action = int(rng.choice(legal.tolist()))
        elif opponent == "mcts":
            opp.clear()  # type: ignore[union-attr]
            action = opp.best_action(board)  # type: ignore[union-attr]
        elif opponent == "checkpoint":
            opp.clear()  # type: ignore[union-attr]
            action = opp.best_action(board)  # type: ignore[union-attr]
        else:
            raise ValueError(f"unknown opponent: {opponent}")
        if not mask[action]:
            raise RuntimeError(f"player {cur} returned illegal action {action}")
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if rule_player_idx == 0 else (s1 - s0)
    return {
        "seed": seed,
        "rule_player_idx": rule_player_idx,
        "score_p0": s0,
        "score_p1": s1,
        "diff_rule_minus_opp": diff,
        "won_by_rule": diff > 0,
        "drew": diff == 0,
        "moves": moves,
        "elapsed_s": elapsed,
    }


def elo_delta(wr: float, eps: float = 1e-9) -> float:
    wr = min(max(wr, eps), 1 - eps)
    return -400.0 * math.log10(1.0 / wr - 1.0)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=20)
    p.add_argument(
        "--opponent",
        choices=["random", "mcts", "checkpoint"],
        default="random",
    )
    p.add_argument(
        "--sims",
        type=int,
        default=50,
        help="for --opponent=mcts (vanilla rollouts) or =checkpoint (NeuralMCTS sims)",
    )
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="required when --opponent=checkpoint",
    )
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="parallel workers; default 2 if CUDA-checkpoint, else os.cpu_count()",
    )
    args = p.parse_args()

    if args.opponent == "checkpoint" and args.checkpoint is None:
        p.error("--checkpoint required when --opponent=checkpoint")

    pool_args = [
        (args.seed_start + i, i % 2, args.opponent, args.sims) for i in range(args.n)
    ]

    label = (
        f"checkpoint={args.checkpoint.name}"
        if args.opponent == "checkpoint"
        else args.opponent
    )
    print(f"=== rule-player vs {label} — n={args.n} sims={args.sims} ===")
    t0 = time.perf_counter()

    if args.opponent == "checkpoint":
        try:
            import torch
        except ImportError:
            p.error("--opponent=checkpoint requires torch installed")
        if args.workers is not None:
            n_workers = args.workers
        elif torch.cuda.is_available():
            n_workers = min(2, args.n)
            print(
                f"  CUDA detected — defaulting to {n_workers} workers to "
                f"avoid GPU thrash. Use --workers N to override."
            )
        else:
            n_workers = min(os.cpu_count() or 1, args.n)
        ctx = mp.get_context("spawn")
        with ctx.Pool(
            processes=n_workers,
            initializer=_worker_init,
            initargs=(str(args.checkpoint.resolve()),),
        ) as pool:
            results = []
            for r in pool.imap_unordered(play_one, pool_args, chunksize=1):
                results.append(r)
                wins = sum(1 for x in results if x["won_by_rule"])
                drew = sum(1 for x in results if x["drew"])
                losses = len(results) - wins - drew
                if len(results) % 5 == 0 or len(results) == args.n:
                    print(
                        f"  ... {len(results)}/{args.n}  W={wins} D={drew} L={losses}"
                    )
                    sys.stdout.flush()
    elif args.opponent == "mcts":
        # Vanilla MCTS is CPU-bound — serial keeps it simple, parallelize if needed.
        results = [play_one(a) for a in pool_args]
        for r in results:
            print(
                f"  seed={r['seed']:>4}  scores={r['score_p0']}-{r['score_p1']}  "
                f"diff={r['diff_rule_minus_opp']:+}  "
                f"{'W' if r['won_by_rule'] else 'D' if r['drew'] else 'L'}  "
                f"{r['moves']} moves  {r['elapsed_s']:.1f}s"
            )
    else:  # random
        results = [play_one(a) for a in pool_args]
        for r in results:
            print(
                f"  seed={r['seed']:>4}  scores={r['score_p0']}-{r['score_p1']}  "
                f"diff={r['diff_rule_minus_opp']:+}  "
                f"{'W' if r['won_by_rule'] else 'D' if r['drew'] else 'L'}  "
                f"{r['moves']} moves  {r['elapsed_s']:.1f}s"
            )

    elapsed = time.perf_counter() - t0
    wins = sum(1 for r in results if r["won_by_rule"])
    draws = sum(1 for r in results if r["drew"])
    losses = len(results) - wins - draws
    wr = (wins + 0.5 * draws) / len(results)
    avg_diff = sum(r["diff_rule_minus_opp"] for r in results) / len(results)

    print()
    print(f"=== rule-player vs {label}: {wins}W / {draws}D / {losses}L ===")
    print(f"  winrate (W + 0.5D)/N = {wr:.3f}")
    print(f"  ELO delta            ≈ {elo_delta(wr):+.0f}")
    print(f"  avg score diff       = {avg_diff:+.1f}")
    print(f"  wallclock total      = {elapsed:.1f}s ({elapsed/args.n:.1f}s/game)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
