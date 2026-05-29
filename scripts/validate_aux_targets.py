"""Validate the Path B aux-target ownership extractor against the engine scorer.

Step 1 linchpin gate (docs/PATH_B.md): a wrong ownership label teaches the aux
head garbage, and farm ownership is the engine's riskiest area (long-range
flood-fill). This script plays many games to terminal and asserts, per game, that
the per-feature ownership points from `extract_terminal_ownership` reconcile
EXACTLY with the engine's own `count_final_scores`. It exits non-zero on any
mismatch, and FAILS if no scored farms were exercised (so a farmless sample can't
trivially "pass").

Method. The engine consumes meeples at termination (state_updater.py calls
count_final_scores on the live state). So we monkeypatch count_final_scores to a
no-op DURING play, leaving the terminal state meeple-intact:
  - mid-game scoring (completed features) still runs normally;
  - at terminal, run the extractor on the meeple-intact state -> end-game records;
  - ground truth = the real count_final_scores on a deepcopy;
  - assert  pre_endgame_scores + ownership_points == truth, per player.

Usage:  python scripts/validate_aux_targets.py --n 400
"""
from __future__ import annotations

import argparse
import copy
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from carcassonne_ai.aux_targets import (  # noqa: E402
    extract_terminal_ownership,
    scores_from_records,
)
from carcassonne_ai.game_wrapper import Game  # noqa: E402


def _play_to_terminal(game: Game, seed: int, max_plies: int = 400):
    """Random-legal play to terminal. With count_final_scores stubbed by the
    caller, the returned Board's state keeps its meeples at game end.

    The engine shuffles the tile deck with the *global* `random` module
    (carcassonne_game_state.py), so we seed global RNG per game to make both the
    deck AND our move selection reproducible from `seed`."""
    random.seed(seed)
    board = game.get_init_board()
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        action = int(random.choice(legal.tolist()))
        board, _ = game.get_next_state(board, action)
        plies += 1
    return board


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="games to validate")
    ap.add_argument("--seed-start", type=int, default=0)
    args = ap.parse_args(argv)

    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    game = Game()  # default = 2p Base + River + Farmers (locked project scope)

    n_terminal = 0
    n_fail = 0
    farm_games = 0
    contested_farm_games = 0
    total_farm_records = 0
    total_records = 0
    mismatches: list[tuple] = []

    orig = PointsCollector.count_final_scores  # original bound classmethod
    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
    try:
        for i in range(args.n):
            seed = args.seed_start + i
            board = _play_to_terminal(game, seed)
            if not board.state.is_terminated():
                continue  # hit max_plies without terminating — skip
            n_terminal += 1
            state = board.state

            pre = list(state.scores)  # mid-game points (end-game stubbed out)
            records = extract_terminal_ownership(state)
            own_pts = scores_from_records(records, state.players)
            mine = [pre[p] + own_pts[p] for p in range(state.players)]

            truth_state = copy.deepcopy(state)
            orig(game_state=truth_state)  # real end-game scoring on the copy
            truth = list(truth_state.scores)

            if mine != truth:
                n_fail += 1
                if len(mismatches) < 10:
                    mismatches.append((seed, mine, truth, pre, own_pts))

            total_records += len(records)
            farm_recs = [r for r in records if r.terrain == "farm"]
            if farm_recs:
                farm_games += 1
                total_farm_records += len(farm_recs)
                if any(len(r.winners) > 1 for r in farm_recs):
                    contested_farm_games += 1
    finally:
        PointsCollector.count_final_scores = orig

    print(f"games requested:       {args.n}")
    print(f"reached terminal:      {n_terminal}")
    print(f"reconciliation FAILS:  {n_fail}")
    print(f"total feature records: {total_records}")
    print(f"games with farms:      {farm_games}  (contested: {contested_farm_games})")
    print(f"total farm records:    {total_farm_records}")
    if mismatches:
        print("\nfirst mismatches (seed, mine, truth, pre, own_pts):")
        for m in mismatches:
            print("  ", m)

    ok = n_fail == 0 and n_terminal > 0 and farm_games > 0
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
