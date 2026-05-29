"""Tests for the base scalar features (features.encode_scalars).

D13 regression: the engine does not clear state.next_tile after play_tile — it
still holds the just-placed tile through the MEEPLES phase until draw_tile runs.
So tiles_remaining (scalar 5) must count next_tile as a future tile ONLY during
the TILES phase; counting it in MEEPLES overcounts the deck by 1 on ~half of all
evaluations (and makes `progress` jump 1/total at every TILES->MEEPLES step).
"""
from __future__ import annotations

import random

import numpy as np

from carcassonne_ai.features import DECK_NORM, encode_scalars
from carcassonne_ai.game_wrapper import Game


def test_d13_tiles_remaining_counts_next_tile_only_in_tiles_phase():
    """Drive a random game through many TILES/MEEPLES transitions and assert the
    deck count is consistent with the D13 fix in BOTH phases."""
    game = Game()
    random.seed(7)
    board = game.get_init_board()
    saw_tiles = saw_meeples = False
    n = 0
    while game.get_game_ended(board, 0) == 0.0 and n < 300:
        st = board.state
        is_tiles = st.phase.value == "tiles"
        feats = encode_scalars(st, st.current_player, total_tiles=83)
        tiles_remaining = round(float(feats[5]) * DECK_NORM)
        if is_tiles:
            # The drawn-but-unplaced tile is a genuine future placement.
            expected = len(st.deck) + (1 if st.next_tile is not None else 0)
            assert tiles_remaining == expected, f"TILES phase: {tiles_remaining} != {expected}"
            saw_tiles = True
        else:
            # MEEPLES phase: state.next_tile still holds the just-PLACED tile —
            # it is NOT a future tile and must not be counted.
            assert tiles_remaining == len(st.deck), (
                f"MEEPLES phase counted the placed tile: {tiles_remaining} != {len(st.deck)} "
                f"(next_tile set={st.next_tile is not None})"
            )
            saw_meeples = True
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        n += 1
    assert saw_tiles and saw_meeples, "test must exercise both phases"
