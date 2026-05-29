"""Scalar feature extraction for the Carcassonne game state.

Concatenated to the network's flat layer alongside the (channels, W, W) tensor
from board_repr.

Layout (current-player-relative, all values normalized to roughly [-1, 1]):

  0  meeples_remaining_mine     / 7      (max meeples per player in our scope)
  1  meeples_remaining_opp      / 7
  2  score_mine                 / 100    (typical end-of-game ~80-150)
  3  score_opp                  / 100
  4  score_diff_mine_minus_opp  / 50     (typical |diff| <= 50; saturation OK)
  5  tiles_remaining_in_deck    / 85     (total deck ~83 with BASE+THE_RIVER)
  6  current_player_flag        (already 0/1)
  7  phase_tiles                (already 0/1)
  8  phase_meeples              (already 0/1)
  9  game_progress              (already in [0, 1])

Length: 10. Normalization rationale: Phase 3 external review flagged that raw
scalars (scores up to 150, deck size up to 83) had vastly different magnitudes
than the binary phase one-hots, slowing learning by forcing the dense head to
absorb the scaling. Constants are deliberately conservative (rare saturation is
preferable to compressing the typical range).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState

N_SCALAR_FEATURES = 10

MEEPLE_NORM = 7.0
SCORE_NORM = 100.0
SCORE_DIFF_NORM = 50.0
DECK_NORM = 85.0


def encode_scalars(state: "CarcassonneGameState", player: int, total_tiles: int) -> np.ndarray:
    opp = 1 - player
    is_tiles = state.phase.value == "tiles"
    # D13 fix (2026-05-29): the engine doesn't clear state.next_tile after
    # play_tile — it still holds the just-placed tile through the MEEPLES phase
    # until draw_tile runs. So counting next_tile unconditionally overcounted the
    # deck by 1 on every MEEPLES-phase encode (~half of all evals), and `progress`
    # jumped by 1/total at each TILES->MEEPLES transition. Only count next_tile as
    # a future tile during the TILES phase. (Matches rule_based_player intent.)
    tiles_remaining = len(state.deck) + (1 if (is_tiles and state.next_tile is not None) else 0)
    progress = 1.0 - (tiles_remaining / max(total_tiles, 1))
    return np.array(
        [
            state.meeples[player] / MEEPLE_NORM,
            state.meeples[opp] / MEEPLE_NORM,
            float(state.scores[player]) / SCORE_NORM,
            float(state.scores[opp]) / SCORE_NORM,
            float(state.scores[player] - state.scores[opp]) / SCORE_DIFF_NORM,
            float(tiles_remaining) / DECK_NORM,
            1.0 if state.current_player == player else 0.0,
            1.0 if is_tiles else 0.0,
            0.0 if is_tiles else 1.0,
            float(progress),
        ],
        dtype=np.float32,
    )
