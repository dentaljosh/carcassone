"""Scalar feature extraction for the Carcassonne game state.

Concatenated to the network's flat layer alongside the (channels, W, W) tensor
from board_repr.

Layout (current-player-relative):

  0  meeples_remaining_mine     (raw count, divide by 7 to normalize)
  1  meeples_remaining_opp
  2  score_mine                 (raw)
  3  score_opp
  4  score_diff_mine_minus_opp
  5  tiles_remaining_in_deck
  6  current_player_flag        (1.0 if mine == player 0 else 0.0;
                                 redundant under canonical form but useful
                                 for debugging)
  7  phase_tiles                (1.0 if state.phase == TILES else 0.0)
  8  phase_meeples              (1.0 if state.phase == MEEPLES else 0.0)
  9  game_progress              (1 - tiles_remaining / total_tiles)

Length: 10.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState

N_SCALAR_FEATURES = 10


def encode_scalars(state: "CarcassonneGameState", player: int, total_tiles: int) -> np.ndarray:
    opp = 1 - player
    tiles_remaining = len(state.deck) + (1 if state.next_tile is not None else 0)
    progress = 1.0 - (tiles_remaining / max(total_tiles, 1))
    is_tiles = state.phase.value == "tiles"
    return np.array(
        [
            state.meeples[player],
            state.meeples[opp],
            float(state.scores[player]),
            float(state.scores[opp]),
            float(state.scores[player] - state.scores[opp]),
            float(tiles_remaining),
            1.0 if state.current_player == player else 0.0,
            1.0 if is_tiles else 0.0,
            0.0 if is_tiles else 1.0,
            float(progress),
        ],
        dtype=np.float32,
    )
