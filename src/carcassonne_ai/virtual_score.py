"""Virtual-score heuristic — Ameneyro et al. 2020 §III.B equivalent.

Estimates a position's expected final score differential WITHOUT playing
games to completion. Used as the value-head training target for Phase 3
warm-start, and (later) as a leaf evaluator in Phase 2 reduced-rollout MCTS.

Approach: leverage the engine's own end-of-game scoring (`count_final_scores`)
on a deepcopy of the state. The engine already knows how to count
unfinished cities/roads/cloisters/farms — we just don't want it to mutate
the live game state.

This is a faithful approximation: the engine's `count_final_scores` IS
exactly what would happen if the game ended right now and all unfinished
features were resolved per Carcassonne end-of-game rules. That's a
reasonable estimate of "expected final score differential" for warm-start
labeling — better than random rollouts, and orders of magnitude faster.

Usage:
    diff = virtual_score(state, player=0)  # raw int score differential
    target = math.tanh(diff / 15)           # value-head training target
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from wingedsheep.carcassonne.utils.points_collector import PointsCollector

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState


def virtual_score(state: "CarcassonneGameState", player: int) -> int:
    """Estimate the final score differential `score[player] - score[opp]`
    by running the engine's end-of-game scoring on a copy of the state.

    Returns a raw integer (not normalized). Apply `tanh(diff / 15)` at the
    call site if you want a value-head training target.

    Mutates nothing — operates on a deep copy.
    """
    if state.players != 2:
        raise ValueError(
            f"virtual_score is implemented for 2-player only; got {state.players}"
        )

    snapshot = copy.deepcopy(state)
    PointsCollector.count_final_scores(game_state=snapshot)
    opp = 1 - player
    return int(snapshot.scores[player]) - int(snapshot.scores[opp])
