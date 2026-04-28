"""Evaluate a trained warm-start network in a simple network-vs-random
tournament. Network plays argmax(policy * mask); no MCTS at inference.

Usage:
  python -u scripts/eval_warmstart_smoke.py --checkpoint checkpoints/warmstart_mcts_smoke.best.pt --n 50
  python -u scripts/eval_warmstart_smoke.py --checkpoint checkpoints/warmstart_heuristic_smoke.best.pt --n 50

Each game alternates which side the network plays. Progress prints flush
on completion of each game (small N, no Pool — keeps it simple).
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet


def network_action(net: CarcassonneNet, game: Game, board, mask: np.ndarray, device: torch.device) -> int:
    """Take the network's argmax over valid moves. Reuses the caller's Game
    so we don't allocate a new wrapper per inference call."""
    obs, scalars = game.get_canonical_form(board, board.state.current_player)
    obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
    scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
    # Cached masks from get_valid_moves are non-writable (read-only protection
    # against accidental cache corruption). Copy before tensor conversion.
    mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(device)
    with torch.no_grad():
        logits, _ = net(obs_t, scalars_t)
        masked = logits.masked_fill(~mask_t, float("-inf"))
        return int(masked.argmax(dim=-1).item())


def play_one_game(net: CarcassonneNet, net_player: int, seed: int, device: torch.device) -> dict:
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
            # Defensive: if the network somehow picked an invalid action, fall
            # back to argmax over visible-from-mask. Shouldn't happen with the
            # masked_fill above.
            if not mask[action]:
                action = int(rng.choice(legal))
        else:
            action = int(rng.choice(legal))
        board, _ = game.get_next_state(board, action)
        moves += 1
    s0, s1 = board.state.scores
    diff = (s0 - s1) if net_player == 0 else (s1 - s0)
    return {
        "seed": seed,
        "net_player": net_player,
        "score_p0": s0,
        "score_p1": s1,
        "diff": diff,
        "won": diff > 0,
        "drew": diff == 0,
        "moves": moves,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval_warmstart_smoke")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed-start", type=int, default=10000)
    args = p.parse_args(argv)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading {args.checkpoint} on {device}...")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    print(f"  strategy: {ckpt.get('strategy', '?')}, params: {net.param_count():,}")

    t0 = time.perf_counter()
    results = []
    for i in range(args.n):
        seed = args.seed_start + i
        net_player = i % 2
        result = play_one_game(net, net_player, seed, device)
        results.append(result)
        wins = sum(1 for r in results if r["won"])
        if (i + 1) % 5 == 0 or i == args.n - 1:
            print(f"  ... {i+1}/{args.n} done, net wins {wins}/{i+1}")
            sys.stdout.flush()

    elapsed = time.perf_counter() - t0
    wins = sum(1 for r in results if r["won"])
    draws = sum(1 for r in results if r["drew"])
    losses = args.n - wins - draws
    avg_diff = sum(r["diff"] for r in results) / args.n
    avg_moves = sum(r["moves"] for r in results) / args.n

    print()
    print(f"Network({ckpt.get('strategy', '?')}) vs random: {wins}/{args.n} wins ({wins/args.n:.1%})")
    print(f"  draws: {draws}, losses: {losses}")
    print(f"  avg score diff (net - random): {avg_diff:+.1f}")
    print(f"  avg moves/game: {avg_moves:.0f}")
    print(f"  total wallclock: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
