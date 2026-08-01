"""Retail/tournament fixed start tile — OPT-IN, default OFF.

Retail Carcassonne pre-places a fixed "D" start tile (a city on one edge with a
road running straight through) before anyone draws. The vendored engine instead
has the first player DRAW a random tile which is auto-placed at
``starting_position`` — costing that player a turn and handing them a free meeple
opportunity on it. Joshua approved the retail convention **for the Android app
only** (2026-07-30); every training run, eval and solver measurement to date used
the engine convention, so it remains the library default and flipping it is a
separate re-baselining decision (BACKLOG "Fixed start tile", bundle with G1).

The two contracts that matter:
  * ``test_default_is_bit_identical`` — a default ``Game()`` is byte-for-byte the
    game it has always been. This is the one that protects every existing baseline.
  * ``test_retail_start_places_the_D_tile`` — opted in, the correct tile is on the
    board at the start position, unrotated, and it is nobody's move.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import RETAIL_START_TILE, Game
from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts
from wingedsheep.carcassonne.utils.action_util import ActionUtil

SEED = 20260730


def _init(seed: int, **kw) -> "object":
    random.seed(seed)
    return Game(**kw).get_init_board()


def test_default_is_bit_identical() -> None:
    """Default OFF must reproduce the historical game exactly — same deck, same
    empty board, same first-move contract. Guards every existing baseline."""
    a = _init(SEED)
    b = _init(SEED, fixed_start_tile=False)

    assert a.state.placed_coords == set() == b.state.placed_coords
    assert a.state.next_tile.description == b.state.next_tile.description
    assert [t.description for t in a.state.deck] == [t.description for t in b.state.deck]
    assert a.total_tiles == b.total_tiles == 72
    assert a.offset == b.offset
    assert a.state.current_player == b.state.current_player == 0
    assert a.state.phase == b.state.phase == GamePhase.TILES

    # The historical first-move contract: exactly one placement, forced onto the
    # start position at rotation 0, and the drawn tile is whatever the shuffle gave.
    g = Game()
    acts = ActionUtil.get_possible_actions(a.state)
    assert len(acts) == 1
    assert acts[0].coordinate == a.state.starting_position
    assert acts[0].tile_rotations == 0
    assert g.get_action_size() == Game(fixed_start_tile=True).get_action_size()


def test_retail_start_places_the_D_tile() -> None:
    board = _init(SEED, fixed_start_tile=True)
    st = board.state
    coord = st.starting_position
    tile = st.board[coord.row][coord.column]

    assert tile is not None, "retail start tile must already be on the board"
    assert tile.description == RETAIL_START_TILE
    # The retail "D" orientation, unrotated: city on top, road straight through.
    assert tile.get_type(Side.TOP).name.lower() == "city"
    assert tile.get_type(Side.LEFT).name.lower() == "road"
    assert tile.get_type(Side.RIGHT).name.lower() == "road"
    assert tile.get_type(Side.BOTTOM).name.lower() == "grass"

    # Nobody played it: it is still player 0's turn, in the TILES phase, with no
    # meeple phase pending and no meeples spent.
    assert st.current_player == 0
    assert st.phase == GamePhase.TILES
    assert st.last_tile_action is None
    assert st.placed_meeples == [[], []]
    assert st.meeples == [7, 7]

    # Bookkeeping the fast paths rely on.
    assert st.placed_coords == {coord}
    assert coord not in st.open_positions
    assert len(st.open_positions) == 4
    assert board.tile_count == 1


def test_retail_deck_is_the_remaining_71() -> None:
    """One D comes out of the pool — total tiles placed is still 72."""
    board = _init(SEED, fixed_start_tile=True)
    st = board.state
    assert len(st.deck) + 1 == 71, "71 tiles remain to be drawn"
    assert board.total_tiles == 72

    pool = [st.next_tile] + list(st.deck)
    n_d = sum(1 for t in pool if t.description == RETAIL_START_TILE)
    assert n_d == base_tile_counts[RETAIL_START_TILE] - 1 == 3

    all_tiles = [t.description for t in pool] + [RETAIL_START_TILE]
    assert len(all_tiles) == 72
    for name, count in base_tile_counts.items():
        assert all_tiles.count(name) == count, f"{name} miscounted"


def test_retail_first_move_is_a_real_choice() -> None:
    """Under the engine rule the first move is forced (one option). Under retail
    the start tile is already down, so player 0 faces a genuine placement."""
    engine_board = _init(SEED)
    retail_board = _init(SEED, fixed_start_tile=True)

    assert len(ActionUtil.get_possible_actions(engine_board.state)) == 1
    assert len(ActionUtil.get_possible_actions(retail_board.state)) > 1


def test_retail_game_plays_to_a_legal_finish() -> None:
    """End-to-end: the representation and action space are untouched by the rule,
    so a retail game runs through the ordinary wrapper to a scored terminal."""
    g = Game(fixed_start_tile=True)
    random.seed(SEED)
    board = g.get_init_board()
    rng = random.Random(3)
    placed = 1
    while not board.state.is_terminated():
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        assert len(legal) > 0
        # shape contract holds throughout
        assert g.get_canonical_form(board, 1)[0].shape == (
            g.get_input_channels(), g.window_size, g.window_size)
        if board.state.phase == GamePhase.TILES:
            placed += 1
        board = g.get_next_state(board, int(rng.choice(list(legal))))[0]
    assert len(board.state.placed_coords) == 72
    assert sum(board.state.scores) > 0


@pytest.mark.parametrize("flag", [False, True])
def test_window_offset_starts_on_the_start_tile(flag: bool) -> None:
    """Either rule centres the window on the start position, so the encoding is
    the same object in both worlds (only the game setup differs)."""
    board = _init(SEED, fixed_start_tile=flag)
    sp = board.state.starting_position
    half = board.offset.size // 2
    assert board.offset.origin_row == sp.row - half
    assert board.offset.origin_col == sp.column - half
