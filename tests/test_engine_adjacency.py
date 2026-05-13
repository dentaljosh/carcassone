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


def test_placed_coords_starts_empty() -> None:
    g = Game()
    board = g.get_init_board()
    assert board.state.placed_coords == set()


def test_placed_coords_stays_consistent_through_a_random_game() -> None:
    """Mirror of test_open_positions_*: placed_coords must always equal the
    set of (row, col) cells with a non-None tile. Required for
    string_representation to iterate placed tiles fast (loop-4 patch,
    2026-05-13)."""
    g = Game()
    random.seed(42)
    board = g.get_init_board()
    steps = 0
    while g.get_game_ended(board, 0) == 0.0 and steps < 60:
        actual = board.state.placed_coords
        expected = set()
        for r, row in enumerate(board.state.board):
            for c, t in enumerate(row):
                if t is not None:
                    expected.add(Coordinate(row=r, column=c))
        assert actual == expected, (
            f"step {steps}: placed_coords out of sync. "
            f"actual={len(actual)} expected={len(expected)}"
        )
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))
        steps += 1


def test_tile_phase_pass_does_not_leak_meeples() -> None:
    """Regression for the engine bug found in external review pass 4 (2026-04-28):
    if the current tile is unplaceable, the engine emits a TILES-phase
    PassAction. Pre-fix, that switched phase to MEEPLES with a stale
    last_tile_action — letting the agent place a meeple on the PREVIOUS
    turn's tile.

    Post-fix: tile-phase pass should clear last_tile_action, draw a new
    next_tile, and hand off directly to the next player (no MEEPLES decision).
    """
    from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
    from wingedsheep.carcassonne.objects.coordinate import Coordinate
    from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    g = Game()
    board = g.get_init_board()

    # Step into a state where last_tile_action is set (after the first
    # placement). Use the first legal action.
    legal = np.flatnonzero(g.get_valid_moves(board))
    board, _ = g.get_next_state(board, int(legal[0]))
    # We're now in MEEPLES phase with last_tile_action set to the river_start
    # placement. Skip the meeple decision so we get to the next TILES phase.
    legal = np.flatnonzero(g.get_valid_moves(board))
    # Find the meeple-pass index (last index in our action space).
    pass_idx = g.get_action_size() - 1
    assert pass_idx in legal
    board, _ = g.get_next_state(board, pass_idx)
    # Now in TILES phase, but last_tile_action still references the river_start.
    assert board.state.phase == GamePhase.TILES
    prior_last_tile_action = board.state.last_tile_action
    assert prior_last_tile_action is not None

    # Construct a TILES-phase PassAction directly and apply it. The engine
    # should: draw a new next_tile, advance to next player, clear or skip
    # last_tile_action handling, and STAY in TILES phase (no meeple decision).
    new_state = StateUpdater.apply_action(
        game_state=board.state, action=PassAction()
    )
    # last_tile_action must be cleared (or otherwise unusable) so that
    # the next decision can't claim a feature on the previous tile.
    assert new_state.last_tile_action is None, (
        "tile-phase pass left last_tile_action stale — meeple-leak bug"
    )
    # Phase should be TILES: no meeple decision is owed for a pass.
    assert new_state.phase == GamePhase.TILES
    # The current player should have advanced.
    assert new_state.current_player != board.state.current_player


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
