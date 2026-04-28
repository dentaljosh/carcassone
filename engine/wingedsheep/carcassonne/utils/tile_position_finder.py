from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.playing_position import PlayingPosition
from wingedsheep.carcassonne.objects.tile import Tile
from wingedsheep.carcassonne.utils.tile_fitter import TileFitter


class TilePositionFinder:

    @staticmethod
    def possible_playing_positions(game_state: CarcassonneGameState, tile_to_play: Tile) -> [PlayingPosition]:
        if game_state.empty_board():
            return [PlayingPosition(coordinate=game_state.starting_position, turns=0)]

        playing_positions = []

        # Patched (vendored fork): iterate only the precomputed open_positions
        # set (cells empty AND adjacent to a placed tile) instead of scanning
        # the full 35x35 grid. Maintained incrementally by StateUpdater.play_tile.
        # Reduces get_possible_actions from ~50ms to a few ms in mid-game.
        candidates = sorted(
            game_state.open_positions,
            key=lambda c: (c.row, c.column),
        )

        for coord in candidates:
            row_index, column_index = coord.row, coord.column
            for tile_turns in range(0, 4):
                top = game_state.get_tile(row_index - 1, column_index)
                bottom = game_state.get_tile(row_index + 1, column_index)
                left = game_state.get_tile(row_index, column_index - 1)
                right = game_state.get_tile(row_index, column_index + 1)

                if TileFitter.fits(tile_to_play.turn(tile_turns), top=top, bottom=bottom,
                                   left=left, right=right, game_state=game_state):
                    playing_positions.append(
                        PlayingPosition(coordinate=Coordinate(row=row_index, column=column_index),
                                        turns=tile_turns))

        return playing_positions
