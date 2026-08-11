import copy

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.actions.action import Action
from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.utils.points_collector import PointsCollector
from wingedsheep.carcassonne.utils.river_rotation_util import RiverRotationUtil


class StateUpdater:

    @staticmethod
    def next_player(game_state: CarcassonneGameState) -> CarcassonneGameState:
        game_state.phase = GamePhase.TILES
        game_state.current_player = game_state.current_player + 1
        if game_state.current_player >= game_state.players:
            game_state.current_player = 0
        return game_state

    @staticmethod
    def play_tile(game_state: CarcassonneGameState, tile_action: TileAction) -> CarcassonneGameState:
        game_state.board[tile_action.coordinate.row][tile_action.coordinate.column] = tile_action.tile
        game_state.phase = GamePhase.MEEPLES
        game_state.last_river_rotation = RiverRotationUtil.get_river_rotation(game_state=game_state,
                                                                              tile=tile_action.tile)
        game_state.last_tile_action = tile_action

        # Patched (vendored fork): maintain open_positions for fast legal-move
        # queries. Remove the just-placed coordinate; add its 4 empty neighbors.
        # See carcassonne_game_state.open_positions and TilePositionFinder.
        from wingedsheep.carcassonne.objects.coordinate import Coordinate
        r, c = tile_action.coordinate.row, tile_action.coordinate.column
        game_state.open_positions.discard(tile_action.coordinate)
        n_rows = len(game_state.board)
        n_cols = len(game_state.board[0])
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < n_rows and 0 <= nc < n_cols and game_state.board[nr][nc] is None:
                game_state.open_positions.add(Coordinate(row=nr, column=nc))
        # Patched (vendored fork, 2026-05-13): track placed coords for fast
        # string_representation iteration. Tiles never get unplaced; pure add.
        game_state.placed_coords.add(tile_action.coordinate)
        return game_state

    @staticmethod
    def play_meeple(game_state: CarcassonneGameState, meeple_action: MeepleAction) -> CarcassonneGameState:
        if not meeple_action.remove:
            game_state.placed_meeples[game_state.current_player].append(
                MeeplePosition(meeple_type=meeple_action.meeple_type,
                               coordinate_with_side=meeple_action.coordinate_with_side))
        else:
            game_state.placed_meeples[game_state.current_player].remove(
                MeeplePosition(meeple_type=meeple_action.meeple_type,
                               coordinate_with_side=meeple_action.coordinate_with_side))

        if meeple_action.meeple_type == MeepleType.NORMAL or meeple_action.meeple_type == MeepleType.FARMER:
            game_state.meeples[game_state.current_player] += 1 if meeple_action.remove else -1
        elif meeple_action.meeple_type == MeepleType.ABBOT:
            if meeple_action.remove:
                points = PointsCollector.chapel_or_flowers_points(game_state=game_state,
                                                                  coordinate=meeple_action.coordinate_with_side.coordinate)
                game_state.scores[game_state.current_player] += points
            game_state.abbots[game_state.current_player] += 1 if meeple_action.remove else -1
        elif meeple_action.meeple_type == MeepleType.BIG or meeple_action.meeple_type == MeepleType.BIG_FARMER:
            game_state.big_meeples[game_state.current_player] += 1 if meeple_action.remove else -1

        return game_state

    @staticmethod
    def draw_tile(game_state: CarcassonneGameState) -> CarcassonneGameState:
        if len(game_state.deck) == 0:
            game_state.next_tile = None
        else:
            game_state.next_tile = game_state.deck.pop(0)
        return game_state

    @staticmethod
    def remove_meeples_and_update_score(game_state: CarcassonneGameState) -> CarcassonneGameState:
        if game_state.last_tile_action is not None and game_state.last_tile_action.tile is not None:
            PointsCollector.remove_meeples_and_collect_points(game_state=game_state,
                                                              coordinate=game_state.last_tile_action.coordinate)
        return game_state

    @classmethod
    def apply_action(cls, game_state: CarcassonneGameState, action: Action) -> CarcassonneGameState:
        new_game_state: CarcassonneGameState = copy.deepcopy(game_state)
        cls._apply_action_to(new_game_state, game_state.phase, action)
        return new_game_state

    @classmethod
    def apply_action_inplace(cls, game_state: CarcassonneGameState, action: Action) -> CarcassonneGameState:
        """Mutate game_state in place. Caller MUST own the state; the original
        is destroyed. Use only when the resulting state is the only thing the
        caller needs (e.g., MCTS rollouts where the trajectory is discarded
        after value extraction). Skips the deepcopy that dominates state-copy
        cost in mid-game (board has 80+ Tile references with FarmerConnections).

        Patched (vendored fork) for Phase 2/4 speed. See DECISIONS.md.
        """
        cls._apply_action_to(game_state, game_state.phase, action)
        return game_state

    @classmethod
    def _apply_action_to(cls, target: CarcassonneGameState, original_phase, action: Action) -> None:
        """Shared body of apply_action / apply_action_inplace. Mutates `target`.

        Patched (vendored fork, 2026-04-28): a tile-phase PassAction (no legal
        placement for the current tile) used to fall through to MEEPLES with a
        STALE last_tile_action, so the next decision could place a meeple on a
        previous turn's tile. Now: tile-phase pass discards the unplaceable
        tile, draws the next one, clears last_tile_action, and hands off to the
        next player. There is no meeple decision because no tile was played.
        Caught by external review 2026-04-28; regression test in
        tests/test_engine_adjacency.py::test_tile_phase_pass_does_not_leak_meeples.

        ⚠️ F9/A3 (2026-08-03), `state.redraw_unplaceable`: the `next_player`
        call above is the RULES DIVERGENCE (audit RF-D-2,
        docs/RULES_FIDELITY_AUDIT_20260802.md clause P4). The retail rule is
        *"In the rare circumstances where a drawn tile cannot be placed, the
        player returns the tile to the box and draws another tile"* — the tile
        is REMOVED FROM THE GAME and the SAME player continues their turn.
        Default stays False (the engine of record); `Game(draw_rule="redraw")`
        opts in. The two pre-registered sub-decisions the flag resolves:

        **(1) Recursion.** The redrawn tile may itself be unplaceable, and the
        rule re-applies per draw. We realize the loop as a SEQUENCE of forced
        `PassAction`s -- one set-aside + one draw per action, phase left at
        TILES with the drawer still to move -- rather than as a `while` loop
        inside this handler. Behaviourally identical (the redrawn-and-still-
        unplaceable state has `PassAction` as its only legal move, so no agent
        decision is invented), and it buys two things a loop cannot: each draw
        stays a SEPARATE chance event that the marginalized exact solver can
        price (sub-decision 2), and the diff here is the removal of one call.
        TERMINATION is structural, not a guard: the bag strictly shrinks by one
        tile per Pass because a set-aside tile is removed from the game rather
        than returned to it. Deck exhausted mid-redraw resolves exactly as the
        normal path does -- `draw_tile` leaves `next_tile = None`,
        `is_terminated()` becomes True and `count_final_scores` fires from this
        same block (audit E7).

        **(2) The bag / the exact solver's histogram.** A set-aside tile is
        removed PERMANENTLY: not returned to the bag, not reshuffled, never
        redrawn, and absent from every later determinization and chance node.
        Nothing extra is needed to keep the bag a correct multiset of genuinely
        unseen tiles -- `state.deck` IS the bag in both engines (there is no
        separate histogram anywhere in the hot path) and `draw_tile`'s
        `deck.pop(0)` already removes it. What the flag DOES owe the bag is two
        consequences, both gated on it and both implemented outside this file:
          * `Board.total_tiles` is decremented per set-aside
            (`game_wrapper.Game.get_next_state` / `apply_action_inplace`), so
            the two live definitions of "tiles left" -- `len(deck) + has_next`
            (fair_agent's latch band) and `total_tiles - tile_count` (the
            window audit, clip_trace, `features.progress`) -- stay equal;
          * the marginalized solver re-marginalizes the replacement draw
            (`scripts/level2/endgame_solver._Solver`, `fair/solver.rs`),
            because the solver's TT key is the SORTED (multiset) bag, so
            letting the value depend on which tile happened to sit at the front
            of the deck would poison the table. (That unsoundness is latent on
            the flag-OFF discard path too; it is NOT fixed here, because
            flag-off must stay byte-identical.)

        `set_aside_tiles` is appended under BOTH rules -- pure telemetry, read
        by no scorer/repr/mask/leaf -- so the manifest counter prices both
        profiles. Only `redraw_unplaceable` makes it behavioural.
        `action_util.py` is correct and untouched: it emits the Pass only when
        there is genuinely no legal placement, so the must-place-if-possible
        rule is already honoured under both draw rules.
        """
        if isinstance(action, TileAction):
            cls.play_tile(game_state=target, tile_action=action)
            target.phase = GamePhase.MEEPLES
        elif isinstance(action, MeepleAction):
            cls.play_meeple(game_state=target, meeple_action=action)
        elif isinstance(action, PassAction):
            if original_phase == GamePhase.TILES:
                # Tile-phase pass: no placement happened, no meeple to choose.
                # Discard the unplaceable tile, clear last_tile_action so the
                # next player's meeple-time inspection (if they place) can't
                # leak through to a previous turn's tile, draw a new
                # next_tile, and hand off directly to the next player. Phase
                # stays at TILES — the new player owes a tile decision next.
                target.last_tile_action = None
                if target.next_tile is not None:
                    target.set_aside_tiles.append(target.next_tile)
                cls.draw_tile(game_state=target)
                if not target.redraw_unplaceable:
                    cls.next_player(game_state=target)
                if target.is_terminated():
                    PointsCollector.count_final_scores(game_state=target)
                return
            elif original_phase == GamePhase.MEEPLES:
                pass

        if original_phase == GamePhase.MEEPLES:
            cls.remove_meeples_and_update_score(game_state=target)
            cls.draw_tile(game_state=target)
            cls.next_player(game_state=target)

        if target.is_terminated():
            PointsCollector.count_final_scores(game_state=target)
