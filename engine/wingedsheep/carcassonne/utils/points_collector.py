import json
import os
from typing import Set

import numpy as np

# Patched (vendored fork): all debug prints in this file gated by a module-level
# flag so headless training/measurement isn't drowned in noise. Set
# CARCASSONNE_VERBOSE=1 in the environment (or VERBOSE=True at runtime) to
# restore the original chatter.
VERBOSE = bool(int(os.environ.get("CARCASSONNE_VERBOSE", "0")))


def _log(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)


from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.city import City
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.farm import Farm
from wingedsheep.carcassonne.objects.farmer_connection_with_coordinate import FarmerConnectionWithCoordinate
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.road import Road
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.tile import Tile
from wingedsheep.carcassonne.utils.city_util import CityUtil
from wingedsheep.carcassonne.utils.farm_util import FarmUtil
from wingedsheep.carcassonne.utils.meeple_util import MeepleUtil
from wingedsheep.carcassonne.utils.road_util import RoadUtil


class PointsCollector:

    @classmethod
    def remove_meeples_and_collect_points(cls, game_state: CarcassonneGameState, coordinate: Coordinate):

        # Points for finished cities
        cities: [City] = CityUtil.find_cities(game_state=game_state, coordinate=coordinate)
        for city in cities:
            if city.finished:
                meeples: [[MeeplePosition]] = CityUtil.find_meeples(game_state=game_state, city=city)
                meeple_counts_per_player = cls.get_meeple_counts_per_player(meeples)
                _log("City finished. Meeples:", json.dumps(meeple_counts_per_player))
                if sum(meeple_counts_per_player) == 0:
                    continue
                winning_players = cls.get_winning_players(meeple_counts_per_player)
                if winning_players:
                    points = cls.count_city_points(game_state=game_state, city=city)
                    for w in winning_players:
                        _log(points, "points for player", w)
                        game_state.scores[w] += points
                MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)

        # Points for finished roads
        roads: [Road] = RoadUtil.find_roads(game_state=game_state, coordinate=coordinate)
        for road in roads:
            if road.finished:
                meeples: [[MeeplePosition]] = RoadUtil.find_meeples(game_state=game_state, road=road)
                meeple_counts_per_player = cls.get_meeple_counts_per_player(meeples)
                _log("Road finished. Meeples:", json.dumps(meeple_counts_per_player))
                if sum(meeple_counts_per_player) == 0:
                    continue
                winning_players = cls.get_winning_players(meeple_counts_per_player)
                if winning_players:
                    points = cls.count_road_points(game_state=game_state, road=road)
                    for w in winning_players:
                        _log(points, "points for player", w)
                        game_state.scores[w] += points
                MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)

        # Points for finished chapels
        #
        # RF-D-1 ("cloister rebinding", audit 2026-08-02).  Upstream writes both
        # the loop bound and the cell under inspection to the SAME name
        # `coordinate`: the outer `range` is evaluated once from the true
        # placement, but the inner `range` is re-evaluated per outer iteration
        # from the REBOUND value, so scan rows 2 and 3 drift to wherever the last
        # non-empty cell of the previous row was.  ~9.6% of completed cloisters
        # fall outside the drifted window: points are only deferred
        # (count_final_scores still awards 9) but the MONK IS PINNED for the rest
        # of the game, because a completed 3x3 can never be revisited.
        #
        # The fix is the rename — `anchor` is the loop bound, `scan` is the cell.
        # OPT-IN, DEFAULT OFF (`cloister_scan_fix`): the drift is load-bearing for
        # every measurement, checkpoint and gate recorded to date, and the Rust
        # port carries it verbatim (mutation-proven at G1).  With the flag off
        # `anchor` is rebound exactly where upstream rebinds `coordinate`, so the
        # legacy walk is reproduced cell-for-cell.
        fix = getattr(game_state, "cloister_scan_fix", False)
        legacy_visited = cls._legacy_scan_cells(game_state, coordinate) if fix else None
        anchor: Coordinate = coordinate
        for row in range(coordinate.row - 1, coordinate.row + 2):
            for column in range(anchor.column - 1, anchor.column + 2):
                tile: Tile = game_state.get_tile(row, column)

                if tile is None:
                    continue

                scan = Coordinate(row=row, column=column)
                if not fix:
                    anchor = scan          # LEGACY: the rebinding quirk (RF-D-1)
                coordinate_with_side = CoordinateWithSide(coordinate=scan, side=Side.CENTER)
                meeple_of_player = MeepleUtil.position_contains_meeple(game_state=game_state,
                                                                             coordinate_with_side=coordinate_with_side)
                if (tile.chapel or tile.flowers) and meeple_of_player is not None:
                    points = cls.chapel_or_flowers_points(game_state=game_state, coordinate=scan)
                    if points == 9:
                        if legacy_visited is not None and (row, column) not in legacy_visited:
                            # A completion the drifting scan would NOT have seen
                            # this ply — i.e. a monk it would have pinned.
                            game_state.cloister_completions_accelerated = getattr(
                                game_state, "cloister_completions_accelerated", 0) + 1
                        _log("Chapel or flowers finished for player", str(meeple_of_player))
                        _log(points, "points for player", meeple_of_player)
                        game_state.scores[meeple_of_player] += points

                        meeples_per_player = []
                        for _ in range(game_state.players):
                            meeples_per_player.append([])

                        for meeple_position in game_state.placed_meeples[meeple_of_player]:
                            if coordinate_with_side == meeple_position.coordinate_with_side:
                                meeples_per_player[meeple_of_player].append(meeple_position)

                        MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples_per_player)

    @staticmethod
    def _legacy_scan_cells(game_state: CarcassonneGameState, coordinate: Coordinate) -> set:
        """The cells the LEGACY (drifting) cloister scan would visit this ply.

        Pure enumeration — no scoring, no mutation — used only when
        `cloister_scan_fix` is ON, to count the completions the drift would have
        missed (`state.cloister_completions_accelerated`).  Never called on the
        default path, so the flags-off walk is untouched.

        The count is an UPPER bound on monk-pins avoided: the same drift that
        misses a completion can also visit cells outside the true 3x3, so the
        legacy scan occasionally self-heals an earlier miss from a later
        placement (audit RF-D-1, "partial, unreliable self-heal").
        """
        visited = set()
        anchor = coordinate
        for row in range(coordinate.row - 1, coordinate.row + 2):
            for column in range(anchor.column - 1, anchor.column + 2):
                if game_state.get_tile(row, column) is None:
                    continue
                anchor = Coordinate(row=row, column=column)
                visited.add((row, column))
        return visited

    @staticmethod
    def get_winning_players(meeple_counts_per_player: [int]):
        """Return a list of player indices who tie for most meeples on a feature.

        Patched (vendored fork). The original engine returned the single sole
        winner or None — meaning ties awarded zero points to anyone, which
        contradicts official Carcassonne rules ("if tied, all tied players
        score full points"). Now returns a list: empty if no meeples are on
        the feature, [winner] if there's a sole majority, or [w1, w2, ...] on
        a tie. Also coerces the input to ndarray for numpy 2.x compatibility
        (the original `int(winners[0])` call broke on 1-D 1-element arrays).
        """
        arr = np.asarray(meeple_counts_per_player)
        if arr.size == 0 or int(arr.max()) == 0:
            return []
        return [int(i[0]) for i in np.argwhere(arr == arr.max())]

    @staticmethod
    def count_city_points(game_state: CarcassonneGameState, city: City):
        points = 0
        has_cathedral = False

        coordinates: Set[Coordinate] = set()
        position: CoordinateWithSide
        for position in city.city_positions:
            coordinate: Coordinate = position.coordinate
            tile: Tile = game_state.board[coordinate.row][coordinate.column]
            if tile.inn:
                has_cathedral = True
            coordinates.add(coordinate)

        tiles: [Tile] = list(map(lambda x: game_state.board[x.row][x.column], coordinates))

        if not city.finished and has_cathedral:
            return 0

        tile: Tile
        for tile in tiles:
            if tile.shield:
                if has_cathedral:
                    points += 6
                else:
                    points += 4 if city.finished else 2
            else:
                if has_cathedral:
                    points += 3
                else:
                    points += 2 if city.finished else 1

        return points

    @staticmethod
    def count_road_points(game_state: CarcassonneGameState, road: Road):
        points = 0
        has_inn = False

        coordinates: Set[Coordinate] = set()
        position: CoordinateWithSide
        for position in road.road_positions:
            coordinate: Coordinate = position.coordinate
            tile: Tile = game_state.board[coordinate.row][coordinate.column]
            if tile.inn:
                has_inn = True
            coordinates.add(coordinate)

        tiles: [Tile] = list(map(lambda x: game_state.board[x.row][x.column], coordinates))

        if not road.finished and has_inn:
            return 0

        tile: Tile
        for _ in tiles:
            if has_inn:
                points += 2
            else:
                points += 1

        return points

    @staticmethod
    def chapel_or_flowers_points(game_state: CarcassonneGameState, coordinate: Coordinate):
        points = 0
        for row in range(coordinate.row - 1, coordinate.row + 2):
            for column in range(coordinate.column - 1, coordinate.column + 2):
                tile: Tile = game_state.board[row][column]
                if tile is not None:
                    points += 1
        return points

    @classmethod
    def count_final_scores(cls, game_state: CarcassonneGameState):
        for player, placed_meeples in enumerate(game_state.placed_meeples):

            # TODO also remove meeples from meeples_to_remove, when there are multiple

            meeples_to_remove: Set[MeeplePosition] = set(placed_meeples)
            while len(meeples_to_remove) > 0:
                meeple_position: MeeplePosition = meeples_to_remove.pop()

                tile: Tile = game_state.board[meeple_position.coordinate_with_side.coordinate.row][
                    meeple_position.coordinate_with_side.coordinate.column]

                terrrain_type: TerrainType = tile.get_type(meeple_position.coordinate_with_side.side)

                if terrrain_type == TerrainType.CITY:
                    city: City = CityUtil.find_city(game_state=game_state,
                                                          city_position=meeple_position.coordinate_with_side)
                    meeples: [CoordinateWithSide] = CityUtil.find_meeples(game_state=game_state, city=city)
                    meeple_counts_per_player = cls.get_meeple_counts_per_player(meeples)
                    _log("Collecting points for unfinished city. Meeples:", json.dumps(meeple_counts_per_player))
                    winning_players = cls.get_winning_players(meeple_counts_per_player)
                    if winning_players:
                        points = cls.count_city_points(game_state=game_state, city=city)
                        for w in winning_players:
                            _log(points, "points for player", w)
                            game_state.scores[w] += points

                    MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)
                    continue

                if terrrain_type == TerrainType.ROAD:
                    road: [Road] = RoadUtil.find_road(game_state=game_state,
                                                            road_position=meeple_position.coordinate_with_side)
                    meeples: [CoordinateWithSide] = RoadUtil.find_meeples(game_state=game_state, road=road)
                    meeple_counts_per_player = cls.get_meeple_counts_per_player(meeples)
                    _log("Collecting points for unfinished road. Meeples:", json.dumps(meeple_counts_per_player))
                    winning_players = cls.get_winning_players(meeple_counts_per_player)
                    if winning_players:
                        points = cls.count_road_points(game_state=game_state, road=road)
                        for w in winning_players:
                            _log(points, "points for player", w)
                            game_state.scores[w] += points
                    MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)
                    continue

                if terrrain_type == TerrainType.CHAPEL or terrrain_type == TerrainType.FLOWERS:
                    points = cls.chapel_or_flowers_points(game_state=game_state,
                                                           coordinate=meeple_position.coordinate_with_side.coordinate)
                    _log("Collecting points for unfinished chapel or flowers for player", str(player))
                    _log(points, "points for player", player)
                    game_state.scores[player] += points

                    meeples_per_player = []
                    for _ in range(game_state.players):
                        meeples_per_player.append([])
                    meeples_per_player[player].append(meeple_position)

                    MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples_per_player)
                    continue

                if meeple_position.meeple_type == MeepleType.FARMER or meeple_position.meeple_type == MeepleType.BIG_FARMER:
                    farm: Farm = FarmUtil.find_farm_by_coordinate(game_state=game_state, position=meeple_position.coordinate_with_side)
                    meeples: [[MeeplePosition]] = FarmUtil.find_meeples(game_state=game_state, farm=farm)
                    meeple_counts_per_player = cls.get_meeple_counts_per_player(meeples)
                    _log("Collecting points for farm. Meeples:", json.dumps(meeple_counts_per_player))
                    winning_players = cls.get_winning_players(meeple_counts_per_player)
                    if winning_players:
                        points = cls.count_farm_points(game_state=game_state, farm=farm)
                        for w in winning_players:
                            _log(points, "points for player", w)
                            game_state.scores[w] += points
                    MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)
                    continue

                _log("Collecting points for unknown type", terrrain_type)

    @staticmethod
    def get_meeple_counts_per_player(meeples: [[MeeplePosition]]):
        meeple_counts_per_player = list(
            map(
                lambda x:
                sum(list(map(
                    lambda y: 2 if y.meeple_type == MeepleType.BIG or y.meeple_type == MeepleType.BIG_FARMER else 1, x
                ))),
                meeples
            )
        )
        return meeple_counts_per_player

    @classmethod
    def count_farm_points(cls, game_state: CarcassonneGameState, farm: Farm):
        # Dedup touched cities by their POSITION SET, not object identity.
        # `City` had no __eq__/__hash__ (set dedups by id) and find_cities
        # returns fresh City objects per call, so a field touching one finished
        # city from N farmer connections used to score N*3 instead of 3
        # (~17% of farms over-scored — corrupted reward + the v2.7 leaf).
        # Mirrors the correct dedup in virtual_score_v2.py:348.
        counted_city_keys: Set[frozenset] = set()

        points = 0

        farmer_connection_with_coordinate: FarmerConnectionWithCoordinate
        for farmer_connection_with_coordinate in farm.farmer_connections_with_coordinate:
            cities = CityUtil.find_cities(game_state=game_state, coordinate=farmer_connection_with_coordinate.coordinate, sides=farmer_connection_with_coordinate.farmer_connection.city_sides)
            for city in cities:
                city_key = frozenset(city.city_positions)
                if city_key in counted_city_keys:
                    continue
                counted_city_keys.add(city_key)
                if city.finished:
                    points += 3

        return points
