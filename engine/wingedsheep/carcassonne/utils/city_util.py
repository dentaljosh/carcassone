from typing import Set

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.city import City
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.tile import Tile


class CityUtil:

    @classmethod
    def find_city(cls, game_state: CarcassonneGameState, city_position: CoordinateWithSide) -> City:
        # Patched (vendored fork, 2026-05-29): lazy memo of the city flood-fill on
        # the v2.7 leaf hot path. find_cities/count_farm_points re-run find_city
        # per farmer connection AND per city side, and count_final_scores re-runs
        # it per city meeple — ~31% of leaf cost, heavily redundant on the same
        # city. If the caller attaches a `_city_cache` dict to the state, memoize
        # the (positions, finished) flood-fill result under EVERY city_position in
        # the component, then RETURN A FRESH City object each call. Returning a
        # fresh wrapper (sharing the read-only positions set) is HARMLESS for
        # dedup: as of 2026-06-02 count_farm_points dedups adjacent cities by
        # frozenset(city_positions) and City itself has value __eq__/__hash__
        # (objects/city.py), so identity no longer matters — fresh vs reused both
        # collapse correctly. (Pre-2026-06-02 the fresh object was load-bearing
        # because dedup keyed on City identity; that coupling is gone.) Verified
        # by scripts/reconcile_farm_index.py (value equivalence) + tests. Safe to
        # cache: find_city is a symmetric BFS to closure (start-independent, unlike
        # the old find_farm), so the component is a function of the board, and the
        # board topology is frozen for a leaf eval (count_final_scores mutates
        # scores/meeples, never tile.city). CoordinateWithSide is value-hashable,
        # so one cache is valid across a state and its (Tile-sharing) deepcopy.
        cache = getattr(game_state, "_city_cache", None)
        if cache is not None:
            hit = cache.get(city_position)
            if hit is not None:
                positions, finished = hit
                return City(city_positions=positions, finished=finished)
            positions, finished = cls._compute_city(game_state, city_position)
            entry = (positions, finished)
            for pos in positions:
                cache.setdefault(pos, entry)
            return City(city_positions=positions, finished=finished)

        positions, finished = cls._compute_city(game_state, city_position)
        return City(city_positions=positions, finished=finished)

    @classmethod
    def _compute_city(cls, game_state: CarcassonneGameState, city_position: CoordinateWithSide):
        """The city flood-fill, factored out of find_city so the memo wraps it.
        Returns (city_positions set, finished bool) — identical to the prior
        in-line computation."""
        cities: Set[CoordinateWithSide] = set(cls.cities_for_position(game_state, city_position))
        open_edges: Set[CoordinateWithSide] = set(map(lambda x: cls.opposite_edge(x), cities))
        explored: Set[CoordinateWithSide] = cities.union(open_edges)
        while len(open_edges) > 0:
            open_edge: CoordinateWithSide = open_edges.pop()
            new_cities = cls.cities_for_position(game_state, open_edge)
            cities = cities.union(new_cities)
            new_open_edges = set(map(lambda x: cls.opposite_edge(x), new_cities))
            explored = explored.union(new_cities)
            new_open_edge: CoordinateWithSide
            for new_open_edge in new_open_edges:
                if new_open_edge not in explored:
                    open_edges.add(new_open_edge)
                    explored.add(new_open_edge)

        finished: bool = len(explored) == len(cities)
        return cities, finished

    @classmethod
    def opposite_edge(cls, city_position: CoordinateWithSide):
        if city_position.side == Side.TOP:
            return CoordinateWithSide(Coordinate(city_position.coordinate.row - 1, city_position.coordinate.column),
                                      Side.BOTTOM)
        elif city_position.side == Side.RIGHT:
            return CoordinateWithSide(Coordinate(city_position.coordinate.row, city_position.coordinate.column + 1),
                                      Side.LEFT)
        elif city_position.side == Side.BOTTOM:
            return CoordinateWithSide(Coordinate(city_position.coordinate.row + 1, city_position.coordinate.column),
                                      Side.TOP)
        elif city_position.side == Side.LEFT:
            return CoordinateWithSide(Coordinate(city_position.coordinate.row, city_position.coordinate.column - 1),
                                      Side.RIGHT)

    @classmethod
    def cities_for_position(cls, game_state: CarcassonneGameState, city_position: CoordinateWithSide):
        tile: Tile = game_state.board[city_position.coordinate.row][city_position.coordinate.column]
        cities = []
        if tile is None:
            return cities
        for city_group in tile.city:
            if city_position.side in city_group:
                city_group_side: Side
                for city_group_side in city_group:
                    city_position: CoordinateWithSide = CoordinateWithSide(city_position.coordinate, city_group_side)
                    cities.append(city_position)
        return cities

    @classmethod
    def city_contains_meeples(cls, game_state: CarcassonneGameState, city: City):
        for city_position in city.city_positions:
            for i in range(game_state.players):
                if city_position in list(map(lambda x: x.coordinate_with_side, game_state.placed_meeples[i])):
                    return True
        return False

    @classmethod
    def find_meeples(cls, game_state: CarcassonneGameState, city: City) -> [[MeeplePosition]]:
        meeples: [[MeeplePosition]] = []

        for i in range(game_state.players):
            meeples.append([])

        for city_position in city.city_positions:
            for i in range(game_state.players):
                meeple_position: MeeplePosition
                for meeple_position in game_state.placed_meeples[i]:
                    if city_position == meeple_position.coordinate_with_side:
                        meeples[i].append(meeple_position)

        return meeples

    @classmethod
    def find_cities(cls, game_state: CarcassonneGameState, coordinate: Coordinate, sides: [Side] = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)):
        cities: Set[City] = set()

        tile: Tile = game_state.board[coordinate.row][coordinate.column]

        if tile is None:
            return cities

        side: Side
        for side in sides:
            if tile.get_type(side) == TerrainType.CITY:
                city: City = cls.find_city(game_state=game_state,
                                            city_position=CoordinateWithSide(coordinate=coordinate, side=side))
                cities.add(city)

        return list(cities)
