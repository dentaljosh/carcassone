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


# A/B toggles for the 2026-05-29 leaf flood-fill memoization — the lazy
# `_farm_cache` (farm regions, count_final_scores' find_farm) and `_city_cache`
# (city components, find_city via count_final_scores + count_farm_points + the
# closure bonus). True in production; flipped to False by the bench /
# reconciliation gate to measure each speedup and assert value-invariance.
# Reference them as module attributes (`virtual_score.USE_FARM_CACHE` etc.) so a
# runtime flip is seen by virtual_score_v2 too.
USE_FARM_CACHE = True
USE_CITY_CACHE = True

# Compact-leaf toggle (2026-06-09, leaf-rewrite branch). When True, the lazy
# object-graph flood-fills (`FarmUtil.find_farm` / `CityUtil._compute_city`) are
# bypassed: `compact_leaf.build_farm_cache` / `build_city_cache` pre-populate the
# SAME `_farm_cache` / `_city_cache` dicts via a flat union-find, so every engine
# query is a cache hit. Default OFF — must be bit-exact-validated by
# scripts/reconcile_compact_leaf.py before any production use. Reference it as a
# module attribute (`virtual_score.USE_COMPACT_LEAF`) so a runtime flip (the
# gate) is seen here AND by virtual_score_v2.
USE_COMPACT_LEAF = False


def virtual_score(
    state: "CarcassonneGameState",
    player: int,
    farm_cache: dict | None = None,
    city_cache: dict | None = None,
) -> int:
    """Estimate the final score differential `score[player] - score[opp]`
    by running the engine's end-of-game scoring on a copy of the state.

    Returns a raw integer (not normalized). Apply `tanh(diff / 15)` at the
    call site if you want a value-head training target.

    Mutates nothing — operates on a deep copy. For perf-critical inner
    loops where the caller already owns a scratch copy, prefer
    `virtual_score_inplace` to skip the second deepcopy.

    `farm_cache` (2026-05-29 find_farm speedup): a dict attached to the scoring
    snapshot so `count_final_scores` memoizes farm flood-fills (one per distinct
    field instead of one per farmer meeple). A caller that also scores the same
    state elsewhere (e.g. virtual_score_v2's closure bonus) passes its shared
    cache in — valid because a state's deepcopy shares Tile/FarmerConnection
    refs, so id-keyed entries stay correct on the copy. When None and
    USE_FARM_CACHE is on, a fresh cache is used for this call.
    """
    if state.players != 2:
        raise ValueError(
            f"virtual_score is implemented for 2-player only; got {state.players}"
        )

    snapshot = copy.deepcopy(state)
    if farm_cache is not None:
        snapshot._farm_cache = farm_cache
    elif USE_COMPACT_LEAF:
        from . import compact_leaf
        snapshot._farm_cache = compact_leaf.build_farm_cache(snapshot)
    elif USE_FARM_CACHE:
        snapshot._farm_cache = {}
    if city_cache is not None:
        snapshot._city_cache = city_cache
    elif USE_COMPACT_LEAF:
        from . import compact_leaf
        snapshot._city_cache = compact_leaf.build_city_cache(snapshot)
    elif USE_CITY_CACHE:
        snapshot._city_cache = {}
    PointsCollector.count_final_scores(game_state=snapshot)
    opp = 1 - player
    return int(snapshot.scores[player]) - int(snapshot.scores[opp])


def virtual_score_inplace(
    state: "CarcassonneGameState",
    player: int,
    farm_cache: dict | None = None,
    city_cache: dict | None = None,
) -> int:
    """Same return value as `virtual_score`, but MUTATES the input state
    by invoking the engine's `count_final_scores` directly on it. After
    this call the state's `scores` reflect end-of-game resolution and the
    state should not be used for further play.

    Use only when the caller already owns the state (e.g. just deepcopied
    it) and is going to discard it after reading the score. Skips the
    deepcopy that otherwise dominates heuristic-policy lookahead cost.
    """
    if state.players != 2:
        raise ValueError(
            f"virtual_score_inplace is implemented for 2-player only; "
            f"got {state.players}"
        )
    if farm_cache is not None:
        state._farm_cache = farm_cache
    elif USE_COMPACT_LEAF:
        from . import compact_leaf
        state._farm_cache = compact_leaf.build_farm_cache(state)
    elif USE_FARM_CACHE:
        state._farm_cache = {}
    if city_cache is not None:
        state._city_cache = city_cache
    elif USE_COMPACT_LEAF:
        from . import compact_leaf
        state._city_cache = compact_leaf.build_city_cache(state)
    elif USE_CITY_CACHE:
        state._city_cache = {}
    PointsCollector.count_final_scores(game_state=state)
    opp = 1 - player
    return int(state.scores[player]) - int(state.scores[opp])
