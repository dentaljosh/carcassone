import random
from typing import Optional

from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.rotation import Rotation
from wingedsheep.carcassonne.objects.tile import Tile
from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts, base_tiles
from wingedsheep.carcassonne.tile_sets.inns_and_cathedrals_deck import inns_and_cathedrals_tiles, \
    inns_and_cathedrals_tile_counts
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.the_river_deck import the_river_tiles, the_river_tile_counts
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet


class CarcassonneGameState:

    def __init__(
            self,
            tile_sets: [TileSet] = (TileSet.BASE, TileSet.THE_RIVER, TileSet.INNS_AND_CATHEDRALS),
            supplementary_rules: [SupplementaryRule] = (SupplementaryRule.FARMERS, SupplementaryRule.ABBOTS),
            players: int = 2,
            board_size: (int, int) = (35, 35),
            starting_position: Coordinate = Coordinate(6, 15)
    ):
        self.deck = self.initialize_deck(tile_sets=tile_sets)
        self.supplementary_rules: [SupplementaryRule] = supplementary_rules
        self.board: [[Tile]] = [[None for column in range(board_size[1])] for row in range(board_size[0])]
        self.starting_position: Coordinate = starting_position
        self.next_tile = self.deck.pop(0)
        self.players = players
        self.meeples = [7 for _ in range(players)]
        self.abbots = [1 if SupplementaryRule.ABBOTS in supplementary_rules else 0 for _ in range(players)]
        self.big_meeples = [1 if TileSet.INNS_AND_CATHEDRALS in tile_sets else 0 for _ in range(players)]
        self.placed_meeples = [[] for _ in range(players)]
        self.scores: [int] = [0 for _ in range(players)]
        self.current_player = 0
        self.phase = GamePhase.TILES
        self.last_tile_action: Optional[TileAction] = None
        self.last_river_rotation: Rotation = Rotation.NONE
        # Patched (vendored fork): track empty cells adjacent to placed tiles
        # so TilePositionFinder doesn't need to scan the entire 35x35 grid on
        # every legal-move query. Maintained by StateUpdater.play_tile.
        # Set of Coordinate objects.
        self.open_positions: set = set()
        # Patched (vendored fork, 2026-05-13): track placed-tile coordinates
        # so string_representation can iterate ~80 coords instead of walking
        # the full 1225-cell board. Maintained by StateUpdater.play_tile.
        self.placed_coords: set = set()
        # Patched (vendored fork, F9/A3): the unplaceable-tile DRAW RULE.
        #   False (DEFAULT, the walled engine of record) -- a TILES-phase
        #     PassAction discards the tile, draws the next one AND hands the
        #     turn to the opponent: the drawer loses their whole placement.
        #   True  -- the retail rule: reveal, set the tile aside (it leaves the
        #     game), draw again, SAME player continues.  Opt-in only, via
        #     `Game(draw_rule="redraw")`.
        # Set on the state rather than passed to StateUpdater because every
        # transition helper is a staticmethod over the state alone; the flag
        # therefore rides deepcopy/clone into every MCTS node and PIMC world.
        self.redraw_unplaceable: bool = False
        # Tiles that left the game without being placed, in removal order.
        # Written under BOTH draw rules (it is pure telemetry -- no scorer,
        # repr, mask or leaf reads it), so the C-lite event counter can price
        # the flag-off discard rate too.  Only `redraw_unplaceable` makes it
        # BEHAVIOURAL (turn retention, the total_tiles decrement and the
        # solver's re-marginalization all key off it).
        self.set_aside_tiles: list = []

    def __deepcopy__(self, memo):
        # Patched (vendored fork, 2026-05-13): bypass the default recursive
        # deepcopy. cProfile of one self-play game at sims=50 batch=8 showed
        # `copy.deepcopy` accounted for 75% of wallclock (200/267s) — every
        # MCTS get_next_state step deepcopies the full state, which by default
        # recursively walks every Tile (with FarmerConnections), every
        # MeeplePosition, every Coordinate, etc.
        #
        # State analysis (see DECISIONS.md): everything reachable from state
        # is either (a) mutated by reassignment, (b) a list/set we copy
        # one level deep, or (c) an immutable value object (Tile, TileAction,
        # Coordinate, MeeplePosition, enum members) safe to share by reference.
        # In particular Tile.turn() returns a NEW Tile and no codepath
        # mutates Tile / TileAction / MeeplePosition fields after construction.
        new = CarcassonneGameState.__new__(CarcassonneGameState)
        memo[id(self)] = new

        # Immutable refs — share.
        new.supplementary_rules = self.supplementary_rules
        new.starting_position = self.starting_position
        new.players = self.players
        new.phase = self.phase
        new.last_river_rotation = self.last_river_rotation
        new.current_player = self.current_player
        new.last_tile_action = self.last_tile_action
        new.next_tile = self.next_tile
        new.redraw_unplaceable = self.redraw_unplaceable

        # Lists/sets of immutable refs — shallow copy the container only.
        new.deck = self.deck[:]
        new.scores = self.scores[:]
        new.meeples = self.meeples[:]
        new.abbots = self.abbots[:]
        new.big_meeples = self.big_meeples[:]
        new.placed_meeples = [pl[:] for pl in self.placed_meeples]
        new.open_positions = set(self.open_positions)
        new.placed_coords = set(self.placed_coords)
        new.set_aside_tiles = self.set_aside_tiles[:]

        # 2D board: refs are immutable Tile / None; shallow per row.
        new.board = [row[:] for row in self.board]

        return new

    def get_tile(self, row: int, column: int):
        if row < 0 or column < 0:
            return None
        elif row >= len(self.board) or column >= len(self.board[0]):
            return None
        else:
            return self.board[row][column]

    def empty_board(self):
        for row in self.board:
            for column in row:
                if column is not None:
                    return False
        return True

    def is_terminated(self) -> bool:
        return self.next_tile is None

    def initialize_deck(self, tile_sets: [TileSet]):
        deck: [Tile] = []

        # The river
        if TileSet.THE_RIVER in tile_sets:
            deck.append(the_river_tiles["river_start"])

            new_tiles = []
            for card_name, count in the_river_tile_counts.items():
                if card_name == "river_start":
                    continue
                if card_name == "river_end":
                    continue

                for i in range(count):
                    new_tiles.append(the_river_tiles[card_name])

            random.shuffle(new_tiles)
            for tile in new_tiles:
                deck.append(tile)

            deck.append(the_river_tiles["river_end"])

        new_tiles = []

        if TileSet.BASE in tile_sets:
            for card_name, count in base_tile_counts.items():
                for i in range(count):
                    new_tiles.append(base_tiles[card_name])

        if TileSet.INNS_AND_CATHEDRALS in tile_sets:
            for card_name, count in inns_and_cathedrals_tile_counts.items():
                for i in range(count):
                    new_tiles.append(inns_and_cathedrals_tiles[card_name])

        random.shuffle(new_tiles)
        for tile in new_tiles:
            deck.append(tile)

        return deck
