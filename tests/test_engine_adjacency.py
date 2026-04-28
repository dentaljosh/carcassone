"""Verify engine adjacency tracking (state.open_positions) stays in sync.

The patched engine maintains an `open_positions: set[Coordinate]` of empty
cells adjacent to placed tiles. TilePositionFinder iterates this instead of
the full 35x35 grid. Two invariants must hold:

  1. open_positions equals the set of empty cells adjacent to >=1 placed tile.
  2. Legal moves returned by ActionUtil.get_possible_actions match the
     pre-patch behavior — same as iterating the whole board.
"""
from __future__ import annotations

import random

import numpy as np

from wingedsheep.carcassonne.objects.coordinate import Coordinate

from carcassonne_ai.game_wrapper import Game


def _expected_open_positions(state) -> set:
    """Recompute open_positions from scratch (slow but obviously correct)."""
    expected = set()
    n_rows = len(state.board)
    n_cols = len(state.board[0])
    for r in range(n_rows):
        for c in range(n_cols):
            if state.board[r][c] is not None:
                continue
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= nr < n_rows and 0 <= nc < n_cols:
                    if state.board[nr][nc] is not None:
                        expected.add(Coordinate(row=r, column=c))
                        break
    return expected


def test_open_positions_starts_empty() -> None:
    g = Game()
    board = g.get_init_board()
    # Init has no placed tiles; open_positions is empty.
    assert board.state.open_positions == set()


def test_open_positions_stays_consistent_through_a_random_game() -> None:
    """At every step of a random game, state.open_positions must equal the
    brute-force recomputation from the placed-tile grid."""
    g = Game()
    random.seed(42)
    board = g.get_init_board()
    steps = 0
    while g.get_game_ended(board, 0) == 0.0 and steps < 60:
        actual = board.state.open_positions
        expected = _expected_open_positions(board.state)
        assert actual == expected, (
            f"step {steps}: open_positions out of sync\n"
            f"  actual (size {len(actual)}): {sorted((c.row, c.column) for c in actual)[:10]}...\n"
            f"  expected (size {len(expected)}): {sorted((c.row, c.column) for c in expected)[:10]}..."
        )
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))
        steps += 1


def test_open_positions_survives_deepcopy() -> None:
    """Game.get_next_state internally deepcopies state via the engine's
    apply_action. The open_positions set must round-trip cleanly."""
    g = Game()
    random.seed(7)
    board = g.get_init_board()
    legal = np.flatnonzero(g.get_valid_moves(board))
    board, _ = g.get_next_state(board, int(legal[0]))
    # First placement: river_start at starting_position. Open positions are its
    # 4 in-bounds empty neighbors.
    sp = board.state.starting_position
    expected_neighbors = {
        Coordinate(row=sp.row - 1, column=sp.column),
        Coordinate(row=sp.row + 1, column=sp.column),
        Coordinate(row=sp.row, column=sp.column - 1),
        Coordinate(row=sp.row, column=sp.column + 1),
    }
    assert board.state.open_positions == expected_neighbors
