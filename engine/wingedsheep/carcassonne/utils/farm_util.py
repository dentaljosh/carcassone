from typing import Set, Optional

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_farmer_side import CoordinateWithFarmerSide
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.farm import Farm
from wingedsheep.carcassonne.objects.farmer_connection import FarmerConnection
from wingedsheep.carcassonne.objects.farmer_connection_with_coordinate import FarmerConnectionWithCoordinate
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.tile import Tile
from wingedsheep.carcassonne.utils.side_modification_util import SideModificationUtil


class FarmUtil:

    @classmethod
    def find_farm_by_coordinate(cls, game_state: CarcassonneGameState, position: CoordinateWithSide):
        tile: Tile = game_state.get_tile(position.coordinate.row, position.coordinate.column)

        farmer_connection: FarmerConnection
        for farmer_connection in tile.farms:
            if position.side in farmer_connection.farmer_positions:
                return cls.find_farm(game_state, FarmerConnectionWithCoordinate(farmer_connection, position.coordinate))

    @classmethod
    def find_farm(cls, game_state: CarcassonneGameState, farmer_connection_with_coordinate: FarmerConnectionWithCoordinate) -> Farm:
        # Patched (vendored fork): complete, start-independent connected-component
        # search over farmer connections.
        #
        # The original traversal kept a single `to_ignore` edge-set seeded
        # asymmetrically from the start node and marked edges ignored as it
        # popped them (in set/hash order), so an edge could be pruned before the
        # branch behind it was explored. The region it returned therefore
        # depended on the start coordinate AND on hash order: from some farmer
        # meeples it under-collected the connection set, so `find_meeples` missed
        # meeples and `count_farm_points` missed adjacent finished cities. Worse,
        # via `count_final_scores` this made two same-player farmers on one field
        # score either once or twice depending on pop order — a ~2.2% rate of
        # nondeterministic, sometimes-doubled farm scores that also tainted
        # `virtual_score` / the v2.7 leaf. See DECISIONS.md 2026-05-29.
        #
        # This rewrite visits each connection node exactly once (keyed by
        # coordinate + connection identity) and explores every tile_connection of
        # every visited node, so the component is maximal and identical for any
        # start node. Being start-independent, find_farm is now also safely
        # cacheable (was previously called out as un-cacheable) — see BACKLOG.
        start = farmer_connection_with_coordinate
        component: dict = {cls._farm_node_key(start): start}
        stack: [FarmerConnectionWithCoordinate] = [start]
        while stack:
            node: FarmerConnectionWithCoordinate = stack.pop()
            for farmer_side in node.farmer_connection.tile_connections:
                neighbor_edge: CoordinateWithFarmerSide = cls.opposite_edge(
                    CoordinateWithFarmerSide(node.coordinate, farmer_side)
                )
                neighbor: Optional[FarmerConnectionWithCoordinate] = cls.farm_for_position(game_state, neighbor_edge)
                if neighbor is None:
                    continue
                key = cls._farm_node_key(neighbor)
                if key not in component:
                    component[key] = neighbor
                    stack.append(neighbor)

        return Farm(set(component.values()))

    @staticmethod
    def _farm_node_key(fcc: FarmerConnectionWithCoordinate):
        # A farmer connection is uniquely identified by its tile coordinate plus
        # the identity of the FarmerConnection object (a single tile may host
        # several disjoint field connections). farm_for_position returns wrappers
        # around the persistent tile.farms objects, so id() is stable for the
        # game-state lifetime that find_farm runs in.
        return (fcc.coordinate.row, fcc.coordinate.column, id(fcc.farmer_connection))

    @classmethod
    def opposite_edge(cls, coordinate_with_farmer_side: CoordinateWithFarmerSide) -> CoordinateWithFarmerSide:
        if coordinate_with_farmer_side.farmer_side.get_side() == Side.TOP:
            return CoordinateWithFarmerSide(
                Coordinate(coordinate_with_farmer_side.coordinate.row - 1,
                           coordinate_with_farmer_side.coordinate.column),
                SideModificationUtil.opposite_farmer_side(coordinate_with_farmer_side.farmer_side)
            )
        elif coordinate_with_farmer_side.farmer_side.get_side() == Side.RIGHT:
            return CoordinateWithFarmerSide(
                Coordinate(coordinate_with_farmer_side.coordinate.row,
                           coordinate_with_farmer_side.coordinate.column + 1),
                SideModificationUtil.opposite_farmer_side(coordinate_with_farmer_side.farmer_side)
            )
        elif coordinate_with_farmer_side.farmer_side.get_side() == Side.BOTTOM:
            return CoordinateWithFarmerSide(
                Coordinate(coordinate_with_farmer_side.coordinate.row + 1,
                           coordinate_with_farmer_side.coordinate.column),
                SideModificationUtil.opposite_farmer_side(coordinate_with_farmer_side.farmer_side)
            )
        elif coordinate_with_farmer_side.farmer_side.get_side() == Side.LEFT:
            return CoordinateWithFarmerSide(
                Coordinate(coordinate_with_farmer_side.coordinate.row,
                           coordinate_with_farmer_side.coordinate.column - 1),
                SideModificationUtil.opposite_farmer_side(coordinate_with_farmer_side.farmer_side)
            )

    @classmethod
    def farm_for_position(cls, game_state: CarcassonneGameState, coordinate_with_farmer_side: CoordinateWithFarmerSide) -> Optional[FarmerConnectionWithCoordinate]:
        tile: Tile = game_state.board[coordinate_with_farmer_side.coordinate.row][coordinate_with_farmer_side.coordinate.column]

        if tile is None:
            return None

        farmer_connection: FarmerConnection
        for farmer_connection in tile.farms:
            if coordinate_with_farmer_side.farmer_side in farmer_connection.tile_connections:
                return FarmerConnectionWithCoordinate(farmer_connection, coordinate_with_farmer_side.coordinate)

        return None

    @classmethod
    def has_meeples(cls, game_state: CarcassonneGameState, farm: Farm) -> bool:
        for meeples in cls.find_meeples(game_state, farm):
            if len(meeples) > 0:
                return True
        return False

    @classmethod
    def find_meeples(cls, game_state: CarcassonneGameState, farm: Farm) -> [[MeeplePosition]]:
        meeples: [[MeeplePosition]] = [[] for _ in range(game_state.players)]

        farmer_connection_with_coordinate: FarmerConnectionWithCoordinate
        for farmer_connection_with_coordinate in farm.farmer_connections_with_coordinate:
            farmer_position: CoordinateWithSide = CoordinateWithSide(farmer_connection_with_coordinate.coordinate, farmer_connection_with_coordinate.farmer_connection.farmer_positions[0])
            for player in range(game_state.players):
                meeple_position: MeeplePosition
                for meeple_position in game_state.placed_meeples[player]:
                    if farmer_position == meeple_position.coordinate_with_side:
                        meeples[player].append(meeple_position)

        return meeples
