"""Auxiliary-target extraction for Path B (KataGo-style aux heads).

Step 1 linchpin (see docs/PATH_B.md): compute, at a game's terminal state, the
per-feature OWNERSHIP labels a neural-net auxiliary head will learn to predict —
who controls each open city / road / farm / monastery when the game ends.

Correctness gate. The extractor is a *recording replica* of the engine's own
`PointsCollector.count_final_scores` end-of-game walk: it mirrors the exact
meeple-pop -> find-feature -> majority-winner -> remove-meeples sequence (the
same dedup-by-mutation the engine relies on for features contested across
players). Because it replicates that walk, the points it attributes per feature
sum to the engine's end-of-game point additions *by construction*. The farm walk
is the riskiest part (long-range flood-fill); `scripts/validate_aux_targets.py`
asserts the reconciliation across many games — including farm-heavy endgames —
before any training consumes these labels. A wrong label teaches the aux head
garbage, so that gate is non-negotiable.

The extractor never mutates the caller's state (it works on a deepcopy).

NOTE: ownership here is the *end-of-game* scoring of meeples still on the board
at termination (open features + farms). Features completed mid-game were already
scored and their meeples removed during play, so they are not in these records —
that is intentional: the residual uncertainty a value head most needs help with
is exactly open-feature and farm control (farms never score until the end).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np


# Ownership aux-target planes: one per feature type the head predicts.
# (Monasteries are single-cell / single-owner and rare — folded out for v1.)
OWNERSHIP_TERRAINS: tuple[str, ...] = ("city", "road", "farm")
OWNERSHIP_PLANES = len(OWNERSHIP_TERRAINS)
_OWNERSHIP_TYPE_IDX = {t: i for i, t in enumerate(OWNERSHIP_TERRAINS)}


@dataclass(frozen=True)
class FeatureOwnership:
    """One end-of-game-scored feature.

    terrain:  "city" | "road" | "farm" | "monastery".
    coords:   sorted unique (row, col) board cells the feature occupies — for
              spatial projection onto the board window in Step 2/3.
    finished: feature complete at game end (monastery: 9 tiles around it; farms
              are never "finished" so always False).
    winners:  controlling player indices by meeple majority. Never empty (only
              scored features become records); [p] = sole owner; [p, q] = tie
              (the vendored engine awards full points to all tied players).
    points:   points awarded to EACH winner.
    """

    terrain: str
    coords: tuple[tuple[int, int], ...]
    finished: bool
    winners: tuple[int, ...]
    points: int


def extract_terminal_ownership(state) -> list[FeatureOwnership]:
    """Recording replica of `PointsCollector.count_final_scores`.

    Runs on a deepcopy of `state` (does not mutate the caller). `state` must be a
    terminal state with meeples still placed — i.e. the engine's terminal
    `count_final_scores` has NOT yet consumed them. In self-play that means
    snapshotting before the terminal scoring, or stubbing `count_final_scores`
    during play (see the validator).

    Reconciliation invariant (asserted by validate_aux_targets.py): for each
    player p,
        state.scores[p]  +  sum(r.points for r in result if p in r.winners)
        ==  count_final_scores(deepcopy(state)).scores[p]
    where state.scores[p] holds the mid-game points accumulated before end-game.
    """
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    from wingedsheep.carcassonne.utils.city_util import CityUtil
    from wingedsheep.carcassonne.utils.farm_util import FarmUtil
    from wingedsheep.carcassonne.utils.meeple_util import MeepleUtil
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector
    from wingedsheep.carcassonne.utils.road_util import RoadUtil

    gs = copy.deepcopy(state)
    records: list[FeatureOwnership] = []

    for player in range(gs.players):
        # The engine pops from a per-player set while remove_meeples() mutates
        # the shared placed_meeples list; the membership guard below skips a
        # meeple already consumed by a feature scored on an earlier pass (same
        # contested-/duplicate-feature handling as audit_virtual_score_farmers).
        for mp in list(gs.placed_meeples[player]):
            if mp not in gs.placed_meeples[player]:
                continue
            cws = mp.coordinate_with_side
            tile = gs.board[cws.coordinate.row][cws.coordinate.column]
            if tile is None:
                continue
            terrain = tile.get_type(cws.side)

            if terrain == TerrainType.CITY:
                city = CityUtil.find_city(game_state=gs, city_position=cws)
                meeples = CityUtil.find_meeples(game_state=gs, city=city)
                winners = PointsCollector.get_winning_players(
                    PointsCollector.get_meeple_counts_per_player(meeples)
                )
                if winners:
                    pts = PointsCollector.count_city_points(game_state=gs, city=city)
                    records.append(
                        FeatureOwnership(
                            "city",
                            _coords(city.city_positions),
                            bool(city.finished),
                            tuple(winners),
                            int(pts),
                        )
                    )
                MeepleUtil.remove_meeples(game_state=gs, meeples=meeples)
                continue

            if terrain == TerrainType.ROAD:
                road = RoadUtil.find_road(game_state=gs, road_position=cws)
                meeples = RoadUtil.find_meeples(game_state=gs, road=road)
                winners = PointsCollector.get_winning_players(
                    PointsCollector.get_meeple_counts_per_player(meeples)
                )
                if winners:
                    pts = PointsCollector.count_road_points(game_state=gs, road=road)
                    records.append(
                        FeatureOwnership(
                            "road",
                            _coords(road.road_positions),
                            bool(road.finished),
                            tuple(winners),
                            int(pts),
                        )
                    )
                MeepleUtil.remove_meeples(game_state=gs, meeples=meeples)
                continue

            if terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                pts = PointsCollector.chapel_or_flowers_points(
                    game_state=gs, coordinate=cws.coordinate
                )
                records.append(
                    FeatureOwnership(
                        "monastery",
                        ((cws.coordinate.row, cws.coordinate.column),),
                        pts == 9,
                        (player,),
                        int(pts),
                    )
                )
                meeples_per_player = [[] for _ in range(gs.players)]
                meeples_per_player[player].append(mp)
                MeepleUtil.remove_meeples(game_state=gs, meeples=meeples_per_player)
                continue

            if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                farm = FarmUtil.find_farm_by_coordinate(game_state=gs, position=cws)
                meeples = FarmUtil.find_meeples(game_state=gs, farm=farm)
                winners = PointsCollector.get_winning_players(
                    PointsCollector.get_meeple_counts_per_player(meeples)
                )
                if winners:
                    pts = PointsCollector.count_farm_points(game_state=gs, farm=farm)
                    records.append(
                        FeatureOwnership(
                            "farm",
                            _farm_coords(farm),
                            False,
                            tuple(winners),
                            int(pts),
                        )
                    )
                MeepleUtil.remove_meeples(game_state=gs, meeples=meeples)
                continue

    return records


def scores_from_records(records: list[FeatureOwnership], n_players: int) -> list[int]:
    """Sum the end-of-game points each player earns from the features it owns."""
    scores = [0] * n_players
    for r in records:
        for w in r.winners:
            scores[w] += r.points
    return scores


def ownership_planes(records, offset, player: int, window_size: int) -> np.ndarray:
    """Project per-feature ownership records onto a (OWNERSHIP_PLANES, W, W) tensor.

    One plane per feature type (city/road/farm). Each cell is, from `player`'s
    point of view: +1 if `player` solely/majority-owns the feature covering that
    cell, -1 if the opponent does, 0 if neutral (no owner, a tie, or unplaced).
    Aligns spatially with `encode_board`/`get_canonical_form`, which centre the
    same `offset` window and flip perspective by sign only (no spatial mirror).

    `records` are FeatureOwnership from `extract_terminal_ownership`. `offset` is
    the WindowOffset used to encode the position (board.offset). Cells touched by
    two same-type features with opposite owners net to 0 (sign of the sum).
    """
    W = window_size
    opp = 1 - player
    acc = np.zeros((OWNERSHIP_PLANES, W, W), dtype=np.float32)
    for r in records:
        ti = _OWNERSHIP_TYPE_IDX.get(r.terrain)
        if ti is None:
            continue
        contrib = (1.0 if player in r.winners else 0.0) - (
            1.0 if opp in r.winners else 0.0
        )
        if contrib == 0.0:
            continue
        for (row, col) in r.coords:
            wr = row - offset.origin_row
            wc = col - offset.origin_col
            if 0 <= wr < W and 0 <= wc < W:
                acc[ti, wr, wc] += contrib
    return np.sign(acc).astype(np.float32)


def _coords(positions) -> tuple[tuple[int, int], ...]:
    """Unique (row, col) cells from a list of CoordinateWithSide, sorted."""
    cells = {(p.coordinate.row, p.coordinate.column) for p in positions}
    return tuple(sorted(cells))


def _farm_coords(farm) -> tuple[tuple[int, int], ...]:
    """Unique (row, col) cells a farm region touches, sorted."""
    cells = {
        (fcc.coordinate.row, fcc.coordinate.column)
        for fcc in farm.farmer_connections_with_coordinate
    }
    return tuple(sorted(cells))
