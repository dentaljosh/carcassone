"""Head-to-head harness for the rule-based player.

Plays N games of (rule_player vs opponent), alternating sides each game.
Opponent can be 'random' (default) or 'mcts' (sims-configurable).

Usage:
    python scripts/eval_rule_player.py --n 50 --opponent random
    python scripts/eval_rule_player.py --n 50 --opponent mcts --sims 100

Reports W/D/L from rule-player's perspective and approximate ELO delta.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer


def play_one(seed: int, rule_player_idx: int, opponent: str, sims: int) -> dict:
    rng = random.Random(seed)
    rule = RuleBasedPlayer(seed=seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    moves = 0
    t0 = time.perf_counter()
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if cur == rule_player_idx:
            action = rule.choose_action(game, board, mask)
        elif opponent == "random":
            action = int(rng.choice(legal))
        elif opponent == "mcts":
            raise NotImplementedError("MCTS opponent: future work")
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
    p.add_argument("--opponent", choices=["random", "mcts"], default="random")
    p.add_argument("--sims", type=int, default=50, help="only used for --opponent=mcts")
    p.add_argument("--seed-start", type=int, default=0)
    args = p.parse_args()

    print(f"=== rule-player vs {args.opponent} — n={args.n} ===")
    t0 = time.perf_counter()
    results = []
    for i in range(args.n):
        seed = args.seed_start + i
        # Alternate sides: rule player is p0 on even seeds, p1 on odd.
        rule_idx = i % 2
        r = play_one(seed, rule_idx, args.opponent, args.sims)
        results.append(r)
        print(
            f"  seed={seed:>4}  rule={'p0' if rule_idx == 0 else 'p1'}  "
            f"scores={r['score_p0']}-{r['score_p1']}  diff={r['diff_rule_minus_opp']:+}  "
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
    print(f"=== rule-player vs {args.opponent}: {wins}W / {draws}D / {losses}L ===")
    print(f"  winrate (W + 0.5D)/N = {wr:.3f}")
    print(f"  ELO delta            ≈ {elo_delta(wr):+.0f}")
    print(f"  avg score diff       = {avg_diff:+.1f}")
    print(f"  wallclock total      = {elapsed:.1f}s ({elapsed/args.n:.1f}s/game)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
