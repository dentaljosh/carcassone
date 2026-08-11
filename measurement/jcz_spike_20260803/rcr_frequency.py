#!/usr/bin/env python3
"""How often does the RCr|RCr city-to-city adjacency (the divergence trigger) occur?

The tile-data diff found exactly one divergent kind, `city_top_straight_road`
(JCZ BA/RCr, 4 copies). It is also the ONLY kind whose field data claims a
half-edge on a city edge, so the spurious farm merge can only fire when two RCr
tiles are placed with their cities meeting across the shared border.

This plays random games and counts the trigger.

Usage: .venv/bin/python measurement/jcz_spike_20260803/rcr_frequency.py [n_games]
"""
import random
import sys

import numpy as np

from carcassonne_ai.game_wrapper import Game

KIND = "city_top_straight_road"
# (dr, dc) -> (side on the tile at the anchor cell, side on the neighbour)
NEIGHBOURS = ((-1, 0, "top", "bottom"), (0, 1, "right", "left"))


def city_edges(tile):
    out = set()
    for comp in (tile.city or []):
        for s in comp:
            out.add(str(s))
    return out


def count_triggers(state):
    board = state.board
    n = 0
    for r in range(len(board)):
        for c in range(len(board[r])):
            t = board[r][c]
            if t is None or getattr(t, "description", None) != KIND:
                continue
            for dr, dc, my_side, their_side in NEIGHBOURS:
                rr, cc = r + dr, c + dc
                if not (0 <= rr < len(board) and 0 <= cc < len(board[rr])):
                    continue
                u = board[rr][cc]
                if u is None or getattr(u, "description", None) != KIND:
                    continue
                if my_side in city_edges(t) and their_side in city_edges(u):
                    n += 1
    return n


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    g = Game()
    rng = random.Random(20260803)
    affected, total_triggers, plies = 0, 0, 0
    for i in range(n_games):
        board = g.get_init_board()
        while g.get_game_ended(board, 0) == 0.0:
            valid = g.get_valid_moves(board)
            idx = np.flatnonzero(valid)
            if len(idx) == 0:
                break
            board, _ = g.get_next_state(board, int(rng.choice(idx)))
            plies += 1
        k = count_triggers(board.state)
        total_triggers += k
        affected += 1 if k else 0
    print(f"random games            : {n_games}  ({plies} plies)")
    print(f"games with >=1 trigger  : {affected}  ({100.0 * affected / n_games:.1f}%)")
    print(f"trigger pairs total     : {total_triggers}"
          f"  ({total_triggers / n_games:.3f} per game)")
    print()
    print("A trigger = two `city_top_straight_road` tiles placed with their cities")
    print("meeting across the shared border. Each one merges two field regions that")
    print("canonical rules (and JCZ's tile data) keep separate.")


if __name__ == "__main__":
    main()
