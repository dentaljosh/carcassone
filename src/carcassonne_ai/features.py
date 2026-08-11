"""Scalar feature extraction for the Carcassonne game state.

Concatenated to the network's flat layer alongside the (channels, W, W) tensor
from board_repr.

Layout (current-player-relative, all values normalized to roughly [-1, 1]):

  0  meeples_remaining_mine     / 7      (max meeples per player in our scope)
  1  meeples_remaining_opp      / 7
  2  score_mine                 / 100    (typical end-of-game ~80-150)
  3  score_opp                  / 100
  4  score_diff_mine_minus_opp  / 50     (typical |diff| <= 50; saturation OK)
  5  tiles_remaining_in_deck    / 72     (base-only deck = 72 tiles; River dropped 2026-06-02)
  6  current_player_flag        (already 0/1)
  7  phase_tiles                (already 0/1)
  8  phase_meeples              (already 0/1)
  9  game_progress              (already in [0, 1])

Length: 10. Normalization rationale: Phase 3 external review flagged that raw
scalars (scores up to 150, deck size up to 72) had vastly different magnitudes
than the binary phase one-hots, slowing learning by forcing the dense head to
absorb the scaling. Constants are deliberately conservative (rare saturation is
preferable to compressing the typical range).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

# D2: a trivial zero-dependency enum (the engine's state.phase) — lets us compare by
# enum identity instead of a hardcoded "tiles"/"meeples" string literal.
from wingedsheep.carcassonne.objects.game_phase import GamePhase

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState

N_SCALAR_FEATURES = 10
N_FARM_SCALARS = 2  # optional farm-control scalars, appended when include_farm=True

MEEPLE_NORM = 7.0
SCORE_NORM = 100.0
SCORE_DIFF_NORM = 50.0
DECK_NORM = 72.0  # base-only deck = 72 tiles (River dropped 2026-06-02)
FARM_SCALAR_NORM = 4.0  # typical |contested|, |balance| <= ~4 (saturation OK)


def farm_control_scalars(state: "CarcassonneGameState", player: int) -> tuple[int, int]:
    """Raw (contested_field_count, farm_control_balance) for the live board,
    from `player`'s perspective (Path B Step E, 2026-05-29):

      contested_field_count: # distinct fields where BOTH players have >=1 farmer.
      farm_control_balance:  (# fields where `player` has strictly more farmers)
                             - (# fields where the opponent has strictly more).
                             Tied fields count toward `contested`, 0 toward balance.

    Groups farmers into fields by flooding ONLY the farmer-occupied fields (via
    the lazy find_farm_by_coordinate + a `_farm_cache`), not the whole board —
    so cost scales with #farmers (<=14), not #fields. If the caller already has a
    `_farm_cache` attached (e.g. inside a leaf eval), it's reused, sharing the
    flood with the leaf-value pass. Big farmers count as 1 (our scope has no big
    meeples). RAW values; encode_scalars normalizes by FARM_SCALAR_NORM.

    Deliberately raw counts, NOT value-weighted by adjacent cities: value
    weighting would re-encode the v2.7 heuristic's evaluation and contaminate the
    Path-B go/no-go probe. These are STRUCTURAL facts (field connectivity +
    farmer counts) the conv can't derive from the raw farmer-meeple channels."""
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.utils.farm_util import FarmUtil

    opp = 1 - player
    # Attach a lazy farm-region memo (reuse the caller's if present) so each
    # distinct farmer field is flooded at most once and farmers sharing a field
    # resolve to the same memoized Farm object.
    own_cache = not hasattr(state, "_farm_cache")
    if own_cache:
        # When USE_COMPACT_LEAF is on, build the full compact farm cache rather
        # than an empty {} — keeps this standalone encode path on the same leaf
        # implementation as the rest (else it would silently stay on lazy BFS).
        from . import compact_leaf
        from . import virtual_score as _vs

        state._farm_cache = compact_leaf.build_farm_cache(state) if _vs.USE_COMPACT_LEAF else {}
    try:
        counts: dict = {}  # id(farm) -> [mine, theirs]
        for pl in range(state.players):
            slot = 0 if pl == player else 1
            for mp in state.placed_meeples[pl]:
                if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                    continue
                farm = FarmUtil.find_farm_by_coordinate(state, mp.coordinate_with_side)
                if farm is None:
                    continue
                # With a _farm_cache attached, find_farm_by_coordinate returns the
                # SAME Farm object for every farmer on one field, so id() dedups
                # correctly and avoids building a region-key set per farmer.
                counts.setdefault(id(farm), [0, 0])[slot] += 1
    finally:
        if own_cache:
            del state._farm_cache

    contested = 0
    balance = 0
    for mine, theirs in counts.values():
        if mine > 0 and theirs > 0:
            contested += 1
        if mine > theirs:
            balance += 1
        elif theirs > mine:
            balance -= 1
    return contested, balance


def encode_scalars(
    state: "CarcassonneGameState",
    player: int,
    total_tiles: int,
    include_farm: bool = False,
) -> np.ndarray:
    opp = 1 - player
    is_tiles = state.phase == GamePhase.TILES  # D2: enum, not the "tiles" literal
    # D13 fix (2026-05-29): the engine doesn't clear state.next_tile after
    # play_tile — it still holds the just-placed tile through the MEEPLES phase
    # until draw_tile runs. So counting next_tile unconditionally overcounted the
    # deck by 1 on every MEEPLES-phase encode (~half of all evals), and `progress`
    # jumped by 1/total at each TILES->MEEPLES transition. Only count next_tile as
    # a future tile during the TILES phase. (Matches rule_based_player intent.)
    tiles_remaining = len(state.deck) + (1 if (is_tiles and state.next_tile is not None) else 0)
    progress = 1.0 - (tiles_remaining / max(total_tiles, 1))
    base = [
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
    ]
    if not include_farm:
        return np.array(base, dtype=np.float32)
    contested, balance = farm_control_scalars(state, player)
    base.append(contested / FARM_SCALAR_NORM)
    base.append(balance / FARM_SCALAR_NORM)
    return np.array(base, dtype=np.float32)
