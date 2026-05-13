"""Rule-based fixed-policy player for Carcassonne. Tier-1 baseline.

The point: measure how strong an explicit rules-only player is, so we can
tell whether the network learned anything beyond what fast rules capture.
If `RuleBasedPlayer` beats `warmstart_canonical` at ≥45% wr, the network
hasn't moved much past rule-following — strong evidence the v6 ceiling is
recipe-bound, not capacity-bound.

Current implementation is INTENTIONALLY PARTIAL. Rules in this revision:

  1. Forced-move shortcut — single legal action, take it.
  2. Endgame meeple deployment — in MEEPLES phase, if tiles-left ≤ meeples
     in hand, prefer placing a meeple over passing. Avoids wasting the
     economy.
  3. Avoid early farmers — in MEEPLES phase, when tiles-left > 60% of
     original deck, never claim a FARMER. Farmers lock a meeple for the
     rest of the game; too early is usually wasted commitment.

Future rules (see BACKLOG.md "Rule-based player"):
  - Road quick-close, city quick-close
  - Cloister-EV (>=6 adjacent placements + >=4 tiles left → claim)
  - Empty-farm-with-N-cities late-game threshold
  - Contested-city abandon
  - Don't-extend-dominant-farm

A `choose_action(game, board, valid_mask) -> int` is the interface.
Compatible with the existing game loop (see scripts/eval_warmstart_smoke.py
for the reference pattern).
"""
from __future__ import annotations

import random

import numpy as np

from .action_space import (
    meeple_farmer_base,
    meeple_normal_base,
    meeple_pass_index,
)
from .game_wrapper import Board, Game


class RuleBasedPlayer:
    """Deterministic-policy player driven by explicit Carcassonne rules.

    Args:
        seed: RNG seed for tie-breaking among equally-ranked actions.
    """

    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)

    def choose_action(self, game: Game, board: Board, valid_mask: np.ndarray) -> int:
        legal = np.flatnonzero(valid_mask)
        if len(legal) == 0:
            raise RuntimeError("no legal moves — game should have ended")

        # Rule 1: forced move.
        if len(legal) == 1:
            return int(legal[0])

        phase = board.state.phase.value  # "TILES" or "MEEPLES"

        if phase == "MEEPLES":
            return self._choose_meeple(game, board, legal)
        else:
            return self._choose_tile(game, board, legal)

    # --- meeple phase ----------------------------------------------------

    def _choose_meeple(self, game: Game, board: Board, legal: np.ndarray) -> int:
        """In MEEPLES phase the choices are: pass, NORMAL on a side, FARMER on a corner."""
        W = game.window_size
        normal_base = meeple_normal_base(W)
        farmer_base = meeple_farmer_base(W)
        pass_idx = meeple_pass_index(W)

        # Classify legal options.
        normal_options = [a for a in legal if normal_base <= a < farmer_base]
        farmer_options = [a for a in legal if farmer_base <= a < pass_idx]
        can_pass = pass_idx in legal

        cur = board.state.current_player
        meeples_in_hand = self._meeples_in_hand(board, cur)
        tiles_left = self._tiles_remaining(board)

        # Rule 3: avoid early farmers. ~60% of original deck remaining → no farms.
        early_phase = tiles_left > 0.6 * board.total_tiles
        if early_phase:
            farmer_options = []

        # Rule 2: endgame meeple deployment. If tiles_left ≤ meeples in hand,
        # do NOT pass — every unplaced meeple is wasted points.
        force_place = tiles_left <= meeples_in_hand

        # Priority order: NORMAL placement > FARMER (when allowed) > pass.
        # Within each tier, random tiebreak. (Future: rank by feature EV.)
        if force_place and normal_options:
            return int(self._rng.choice(normal_options))
        if normal_options:
            # Default behavior: take NORMAL meeple when it's an option.
            # Conservative but reasonable; future rule: score by feature-EV.
            return int(self._rng.choice(normal_options))
        if farmer_options:
            return int(self._rng.choice(farmer_options))
        if can_pass:
            return pass_idx
        # Shouldn't reach: every meeple-phase legal must be in one of the buckets.
        return int(self._rng.choice(legal))

    # --- tile phase ------------------------------------------------------

    def _choose_tile(self, game: Game, board: Board, legal: np.ndarray) -> int:
        """In TILES phase the choice is WHERE + WHAT ORIENTATION to place the next tile.

        Current implementation: random among legal placements. Future rules:
            - Prefer placements that complete a city / road we own this turn
            - Prefer placements that DENY opponent completion
            - Prefer placements that connect to existing meeple regions
            - Cloister placements only when EV ≥ threshold
        """
        return int(self._rng.choice(legal))

    # --- state queries ---------------------------------------------------

    @staticmethod
    def _meeples_in_hand(board: Board, player: int) -> int:
        """How many meeples player still has off the board (NORMAL + FARMER combined).

        engine's state.meeples[player] is the count of NORMAL meeples available;
        FARMER meeples come from a separate pool but for Phase 1-5 scope we treat
        them as the same resource (no big-meeple distinction). See game_wrapper.py
        for the supplementary-rule guard.
        """
        # state.meeples is the canonical 'in-hand' count of normal meeples.
        s = board.state
        return int(s.meeples[player])

    @staticmethod
    def _tiles_remaining(board: Board) -> int:
        """Tiles still in the deck (excluding the one currently being placed)."""
        return len(board.state.deck)
