"""Rule-based fixed-policy player for Carcassonne. Tier-1 baseline.

The point: measure how strong an explicit rules-only player is, so we can
tell whether the network learned anything beyond what fast rules capture.
If `RuleBasedPlayer` beats `warmstart_canonical` at ≥45% wr, the network
hasn't moved much past rule-following — strong evidence the v6 ceiling is
recipe-bound, not capacity-bound.

Rules in this revision:

  1. Forced-move shortcut — single legal action, take it.
  2. Endgame meeple deployment — in MEEPLES phase, if tiles-left ≤ meeples
     in hand, never PASS. Every unplaced meeple is wasted points.
  3. Avoid early farmers — in MEEPLES phase, when tiles-left > 60% of
     original deck, never claim a FARMER. Farmers lock a meeple for the
     rest of the game; too early is usually wasted commitment.
  4. Tile placement — pick the legal placement that maximizes 1-ply
     virtual_score (my final-score-diff if game ended after the placement).
     Random tiebreak. This is the same heuristic used by warmstart's
     `_heuristic_policy`, without the softmax temperature.
  5. Meeple placement — among remaining MEEPLE options after rules 2/3
     prune, pick the one with the best 1-ply virtual_score. Random
     tiebreak. Subsumes both NORMAL placement scoring and FARMER scoring
     (the engine's end-of-game farmer-counting logic is folded into
     virtual_score, so we don't need a separate adjacent-cities heuristic).

A `choose_action(game, board, valid_mask) -> int` is the interface.
Compatible with the existing game loop (see scripts/eval_warmstart_smoke.py
for the reference pattern).
"""
from __future__ import annotations

import copy
import random

import numpy as np

from wingedsheep.carcassonne.utils.state_updater import StateUpdater

from .action_space import (
    decode,
    meeple_farmer_base,
    meeple_pass_index,
)
from .game_wrapper import Board, Game
from .virtual_score import virtual_score_inplace


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
        """In MEEPLES phase the choices are: pass, NORMAL on a side, FARMER on a corner.

        Apply Rules 2 (force-place near endgame) and 3 (no early farmers) as
        hard filters, then Rule 5 (best 1-ply virtual_score) over what's left.
        """
        W = game.window_size
        farmer_base = meeple_farmer_base(W)
        pass_idx = meeple_pass_index(W)

        cur = board.state.current_player
        meeples_in_hand = self._meeples_in_hand(board, cur)
        tiles_left = self._tiles_remaining(board)

        candidates = list(int(a) for a in legal)

        # Rule 3: avoid early farmers. ~60% of original deck remaining → no farms.
        early_phase = tiles_left > 0.6 * board.total_tiles
        if early_phase:
            non_farmer = [a for a in candidates if not (farmer_base <= a < pass_idx)]
            if non_farmer:
                candidates = non_farmer

        # Rule 2: endgame meeple deployment. If tiles_left ≤ meeples in hand,
        # do NOT pass — every unplaced meeple is wasted points.
        force_place = tiles_left <= meeples_in_hand
        if force_place:
            non_pass = [a for a in candidates if a != pass_idx]
            if non_pass:
                candidates = non_pass

        if not candidates:
            candidates = [int(a) for a in legal]

        return self._best_by_virtual_score(board, np.array(candidates, dtype=np.int64))

    # --- tile phase ------------------------------------------------------

    def _choose_tile(self, game: Game, board: Board, legal: np.ndarray) -> int:
        """Rule 4: pick the tile placement that maximizes my 1-ply virtual_score.

        Random tiebreak across actions tied for the best score. This is
        equivalent to warmstart's `_heuristic_policy` collapsed to argmax
        (no softmax temperature).
        """
        return self._best_by_virtual_score(board, legal)

    # --- shared helper ---------------------------------------------------

    def _best_by_virtual_score(self, board: Board, legal: np.ndarray) -> int:
        """Score each legal action via 1-ply virtual_score from the current
        player's perspective. Return the action with the highest score; ties
        broken uniformly at random.

        Mutates nothing — each candidate is evaluated on a deepcopy of the
        engine state, then discarded (cf. `_heuristic_policy` in warmstart).
        """
        if len(legal) == 1:
            return int(legal[0])

        player = board.state.current_player
        phase = board.state.phase.value
        next_tile = board.state.next_tile
        last_tile_coord = (
            board.state.last_tile_action.coordinate
            if board.state.last_tile_action is not None
            else None
        )

        scores = np.empty(len(legal), dtype=np.int64)
        for i, action_idx in enumerate(legal):
            action = decode(
                int(action_idx),
                off=board.offset,
                phase=phase,
                next_tile=next_tile,
                last_tile_coord=last_tile_coord,
            )
            scratch = copy.deepcopy(board.state)
            StateUpdater.apply_action_inplace(game_state=scratch, action=action)
            scores[i] = virtual_score_inplace(scratch, player)

        best = scores.max()
        best_local = np.flatnonzero(scores == best)
        choice = int(self._rng.choice(best_local.tolist()))
        return int(legal[choice])

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
