"""AlphaZero-style Game wrapper around the wingedsheep Carcassonne engine.

Mirrors alpha-zero-general's Game.py method names so a Coach/Arena port is
trivial later, but does NOT inherit from it (its API assumes 2D board arrays).

Scope (locked for Phases 1-5): 2 players, BASE + THE_RIVER tile sets,
FARMERS supplementary rule. No Inns & Cathedrals, no Abbots, no Big meeples.

Window size is configurable via Game(window_size=...). Default is 25 based on
Phase 0 random-game measurements, but can be changed at construction time
without code changes if Phase 4 reveals 25 is wrong.
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import dataclass, field
from multiprocessing import Pool

import numpy as np

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
from wingedsheep.carcassonne.utils.action_util import ActionUtil
from wingedsheep.carcassonne.utils.state_updater import StateUpdater

from .action_space import (
    DEFAULT_WINDOW_SIZE,
    WindowOffset,
    WindowOverflowError,
    action_size,
    decode,
    encode,
)
from .board_repr import (
    N_CHANNELS,
    board_overflows_window,
    canonical_swap,
    compute_window_offset,
    encode_board,
)
from .eta import measure_one, print_banner
from .features import N_SCALAR_FEATURES, encode_scalars


SCORE_NORM_SCALE = 15.0  # see DECISIONS.md (validated against 1000 random games)


@dataclass
class Board:
    """Container for engine state plus the cached window offset.

    Mutating helpers return new Board instances; the underlying engine state
    is deep-copied to keep MCTS rollouts independent.
    """

    state: CarcassonneGameState
    total_tiles: int
    offset: WindowOffset
    # Memoized string_representation result. None = not yet computed.
    # Boards are created fresh per Game.get_next_state (apply_action returns
    # a NEW Board around a deepcopied state), so this cache is auto-invalidated
    # by replacement — no manual invalidation needed. apply_action_inplace
    # mutates state but does NOT create a new Board; callers MUST not call
    # string_representation on an inplace-mutated Board (rollout-only contract).
    _str_repr_cache: str | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_state(cls, state: CarcassonneGameState, total_tiles: int, window_size: int) -> "Board":
        return cls(
            state=state,
            total_tiles=total_tiles,
            offset=compute_window_offset(state, window_size),
        )


class Game:
    """AlphaZero-style Carcassonne game interface."""

    def __init__(
        self,
        players: int = 2,
        tile_sets: tuple[TileSet, ...] = (TileSet.BASE, TileSet.THE_RIVER),
        supplementary_rules: tuple[SupplementaryRule, ...] = (SupplementaryRule.FARMERS,),
        window_size: int = DEFAULT_WINDOW_SIZE,
        enable_legal_moves_cache: bool = False,
    ):
        if players != 2:
            raise NotImplementedError("Phase 1 wrapper is 2-player only")
        # Reject out-of-scope configurations at construction time so the
        # action-space encoder doesn't surprise the caller mid-game with a
        # ValueError on an ABBOT/BIG MeepleAction. (External review pass 4,
        # 2026-04-28.)
        if TileSet.INNS_AND_CATHEDRALS in tile_sets:
            raise NotImplementedError(
                "INNS_AND_CATHEDRALS is out of scope for Phase 1-5; "
                "the action-space encoder doesn't handle BIG/BIG_FARMER meeples."
            )
        if SupplementaryRule.ABBOTS in supplementary_rules:
            raise NotImplementedError(
                "ABBOTS supplementary rule is out of scope for Phase 1-5; "
                "the action-space encoder doesn't handle ABBOT meeples."
            )
        self.players = players
        self.tile_sets = tuple(tile_sets)
        self.supplementary_rules = tuple(supplementary_rules)
        self.window_size = int(window_size)
        # Legal-moves cache. Off by default; MCTS turns it on per search and
        # calls clear_caches() between root moves. See DECISIONS.md
        # ("Phase 4 prerequisite: get_valid_moves performance strategy").
        self._legal_cache: dict[str, np.ndarray] | None = (
            {} if enable_legal_moves_cache else None
        )
        self._legal_cache_hits = 0
        self._legal_cache_misses = 0

    def clear_caches(self) -> None:
        """Reset all per-search caches. Call between MCTS root moves."""
        if self._legal_cache is not None:
            self._legal_cache.clear()
        self._legal_cache_hits = 0
        self._legal_cache_misses = 0

    def cache_stats(self) -> dict:
        """Returns hits/misses/size for the legal-moves cache."""
        size = len(self._legal_cache) if self._legal_cache is not None else 0
        total = self._legal_cache_hits + self._legal_cache_misses
        hit_rate = self._legal_cache_hits / total if total else 0.0
        return {
            "enabled": self._legal_cache is not None,
            "hits": self._legal_cache_hits,
            "misses": self._legal_cache_misses,
            "hit_rate": hit_rate,
            "size": size,
        }

    # --- Construction ----------------------------------------------------

    def get_init_board(self) -> Board:
        state = CarcassonneGameState(
            players=self.players,
            tile_sets=list(self.tile_sets),
            supplementary_rules=list(self.supplementary_rules),
        )
        # +1 for the first tile already drawn into next_tile.
        total_tiles = len(state.deck) + 1
        return Board.from_state(state, total_tiles, self.window_size)

    def get_board_shape(self) -> tuple[int, int, int]:
        return (N_CHANNELS, self.window_size, self.window_size)

    def get_action_size(self) -> int:
        return action_size(self.window_size)

    def get_scalar_feature_size(self) -> int:
        return N_SCALAR_FEATURES

    # --- Transitions -----------------------------------------------------

    def get_next_state(self, board: Board, action_idx: int) -> tuple[Board, int]:
        """Apply `action_idx` to `board`. Return (new_board, next_player).

        Safe — input board is unmodified. Use for tree expansion in MCTS.
        For rollouts where the trajectory is discarded, prefer
        apply_action_inplace (3-5x faster mid-game).
        """
        state = board.state
        action = self._decode_for(state, board.offset, action_idx)
        new_state = StateUpdater.apply_action(game_state=state, action=action)
        new_board = Board.from_state(new_state, board.total_tiles, self.window_size)
        return new_board, new_state.current_player

    def apply_action_inplace(self, board: Board, action_idx: int) -> tuple[Board, int]:
        """Apply `action_idx` to `board` IN PLACE. Returns (board, next_player).

        WARNING: mutates `board.state` directly. Caller must not retain the
        prior state. Use only in MCTS rollouts and other discard-the-trajectory
        contexts. Saves the deepcopy that dominates mid-game state-copy cost.
        """
        state = board.state
        action = self._decode_for(state, board.offset, action_idx)
        StateUpdater.apply_action_inplace(game_state=state, action=action)
        # offset depends on placed tiles; recompute since state mutated.
        board.offset = compute_window_offset(state, self.window_size)
        # Invalidate the memoized string_representation since state changed.
        # Required for rollouts and warmstart 2-ply lookahead that mutate a
        # Board in place and then re-query get_valid_moves / string_representation.
        board._str_repr_cache = None
        return board, state.current_player

    def _decode_for(self, state, offset, action_idx: int):
        return decode(
            action_idx,
            off=offset,
            phase=state.phase.value,
            next_tile=state.next_tile,
            last_tile_coord=(
                state.last_tile_action.coordinate if state.last_tile_action is not None else None
            ),
        )

    def get_valid_moves(self, board: Board) -> np.ndarray:
        """Return a length-action_size bool mask of legal action indices.

        Built from the engine's own enumerator: encode each emitted Action
        and flip the corresponding bit. Off-phase indices are guaranteed
        zero because our `encode()` only ever produces same-phase indices.

        If the engine has legal placements but ALL of them fall outside the
        centered window (window-overflow), this method raises
        WindowOverflowError so the caller can drop the game from training
        rather than silently see "no legal moves" (the engine's natural
        no-legal-moves signal is a single PassAction, which the mask still
        accepts). (External review pass 4, 2026-04-28.)

        If the legal-moves cache is enabled (constructor flag), checks for
        and writes to it. Returns the cached mask directly without copying
        — callers must NOT mutate the result.
        """
        if self._legal_cache is not None:
            key = self.string_representation(board)
            cached = self._legal_cache.get(key)
            if cached is not None:
                self._legal_cache_hits += 1
                return cached
            self._legal_cache_misses += 1

        mask = np.zeros(self.get_action_size(), dtype=bool)
        n_total = 0
        n_overflow = 0
        for action in ActionUtil.get_possible_actions(board.state):
            n_total += 1
            try:
                idx = encode(action, board.offset, board.state.phase.value)
            except WindowOverflowError:
                n_overflow += 1
                continue
            mask[idx] = True

        # If every legal action is outside the window, surface a clear signal
        # so the caller can drop the game (rather than seeing an empty mask
        # and confusing it with a genuine no-legal-moves terminal).
        if n_total > 0 and n_overflow == n_total:
            raise WindowOverflowError(
                f"All {n_total} legal actions fall outside the {board.offset.size}x"
                f"{board.offset.size} window centered at "
                f"({board.offset.origin_row}, {board.offset.origin_col}). "
                f"Caller should drop this game from training."
            )

        if self._legal_cache is not None:
            mask.flags.writeable = False  # protect cached masks from mutation
            self._legal_cache[key] = mask
        return mask

    # --- Termination / value ---------------------------------------------

    def get_game_ended(self, board: Board, player: int) -> float:
        """0.0 if game ongoing; otherwise normalized score differential.

        Result is from `player`'s perspective: positive = player won (more pts).
        Final value is tanh((score_player - score_opp) / SCORE_NORM_SCALE).
        Exact tie returns a tiny epsilon so callers can distinguish "ended in
        draw" from "still going" — anything in (-1e-4, 1e-4) means draw.
        """
        if not board.state.is_terminated():
            return 0.0
        opp = 1 - player
        diff = board.state.scores[player] - board.state.scores[opp]
        v = math.tanh(diff / SCORE_NORM_SCALE)
        return v if v != 0.0 else 1e-6

    # --- Canonical form / encoding --------------------------------------

    def get_canonical_form(self, board: Board, player: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (board_tensor, scalar_features) from `player`'s perspective.

        Window coordinates are NOT mirrored — only the mine/opp channels
        and player-relative scalar features are perspective-flipped.

        encode_board already reads `player` and writes mine/opp accordingly,
        so no extra canonical_swap is needed here. (A prior version
        double-swapped when player != current_player, silently reversing the
        intended perspective for the one caller that requested non-current
        player. Caught by external review 2026-04-28.)
        """
        arr = encode_board(board.state, player, board.offset)
        scalars = encode_scalars(board.state, player, board.total_tiles)
        return arr, scalars

    encode_observation = get_canonical_form

    # --- Hashing ---------------------------------------------------------

    def string_representation(self, board: Board) -> str:
        """Stable string for MCTS transposition tables.

        Two distinct game positions yield distinct strings; identical
        positions yield identical strings. Returned as a string (not int)
        so it serializes consistently across processes.

        Implementation note: SPARSE — only emits entries for placed tiles
        (~80 mid/late-game) instead of walking the full 35x35 board (1225
        cells, mostly None) and `repr()`ing the dense nested tuple. The
        dense version was ~166ms in late game, dominating get_valid_moves
        and making the legal-moves cache net-negative. Sparse should be
        ~5-10x faster.

        Memoized on the Board (see Board._str_repr_cache). NeuralMCTS keys
        nodes by this string and calls it many times against the same
        root Board within one search; the cache turns ~22K calls/game
        into ~150 cache misses (one per unique state visited).
        """
        cached = board._str_repr_cache
        if cached is not None:
            return cached
        s = board.state
        # Iterate placed_coords (~80 cells) instead of walking the full 35x35
        # grid (1225 cells, mostly None). Sort for determinism — placed_coords
        # is a set. Patched 2026-05-13.
        placed = []
        for coord in sorted(s.placed_coords, key=lambda c: (c.row, c.column)):
            t = s.board[coord.row][coord.column]
            if t is None:
                continue  # defensive; shouldn't happen since the set tracks placements
            placed.append((coord.row, coord.column, t.description, _tile_rotation_signature(t)))
        meeples = tuple(
            tuple(
                (mp.meeple_type.value, mp.coordinate_with_side.coordinate.row,
                 mp.coordinate_with_side.coordinate.column, mp.coordinate_with_side.side.value)
                for mp in s.placed_meeples[p]
            )
            for p in range(self.players)
        )
        last_tile_coord = (
            (s.last_tile_action.coordinate.row, s.last_tile_action.coordinate.column)
            if s.last_tile_action is not None
            else None
        )
        result = repr(
            (
                tuple(placed),
                meeples,
                tuple(s.scores),
                tuple(s.meeples),
                s.current_player,
                s.phase.value,
                len(s.deck),
                s.next_tile.description if s.next_tile is not None else None,
                last_tile_coord,
            )
        )
        board._str_repr_cache = result
        return result


def _tile_rotation_signature(tile) -> tuple:
    """Capture tile orientation + scoring-relevant properties.

    `description` alone is rotation-blind — two `tile.turn(...)` results
    with the same description but different orientations would otherwise
    collide. The 4 outer edges uniquely encode rotation.

    Defense-in-depth: also pin shield/chapel/flowers. The vendored engine
    has had at least one description-collision bug (city_diagonal_top_left_road
    vs city_diagonal_top_left_shield_road shared the same description string;
    fixed in our fork). Shields change scoring (+1 per city tile), so a state
    key that doesn't distinguish them would cause MCTS transpositions to
    merge positions with different value functions.

    Cached on the Tile instance: Tiles are canonically-shared immutable refs
    (base_tiles dict + Tile.turn() builds a fresh Tile per rotation), so the
    signature for any given Tile reference is stable for the lifetime of the
    process.
    """
    cached = tile._rot_sig_cache
    if cached is not None:
        return cached
    from wingedsheep.carcassonne.objects.side import Side
    edges = (
        tile.get_type(Side.TOP).value,
        tile.get_type(Side.RIGHT).value,
        tile.get_type(Side.BOTTOM).value,
        tile.get_type(Side.LEFT).value,
    )
    sig = (edges, bool(tile.shield), bool(tile.chapel), bool(tile.flowers))
    tile._rot_sig_cache = sig
    return sig


# --- CLI entry point ---------------------------------------------------------

@dataclass
class _GameOutcome:
    completed: bool
    rule_violation: bool
    mask_violation: bool
    had_overflow: bool
    score_sum: int
    error: str | None = None


def _play_one_random_game(args: tuple[int, int]) -> _GameOutcome:
    """Run a single random self-play game. Module-level so it pickles for Pool."""
    seed, window_size = args
    game = Game(window_size=window_size)
    random.seed(seed)
    board = game.get_init_board()
    had_overflow = False
    try:
        while game.get_game_ended(board, 0) == 0.0:
            if board_overflows_window(board.state, board.offset):
                had_overflow = True
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                return _GameOutcome(False, True, False, had_overflow, 0,
                                    error=f"seed {seed}: empty legal-move mask")
            idx = int(random.choice(legal))
            if not mask[idx]:
                return _GameOutcome(False, False, True, had_overflow, 0,
                                    error=f"seed {seed}: chose idx {idx} not in mask")
            board, _ = game.get_next_state(board, idx)
    except Exception as exc:
        return _GameOutcome(False, True, False, had_overflow, 0,
                            error=f"seed {seed}: {type(exc).__name__}: {exc}")
    return _GameOutcome(
        completed=True,
        rule_violation=False,
        mask_violation=False,
        had_overflow=had_overflow,
        score_sum=int(sum(board.state.scores)),
    )


def _self_play_random(
    n_games: int,
    seed: int = 0,
    window_size: int = DEFAULT_WINDOW_SIZE,
    workers: int | None = None,
) -> dict:
    """Run n_games of random-vs-random through the wrapper. Verify integrity.

    Parallelized via multiprocessing.Pool. Worker count defaults to
    `os.cpu_count()` (full SMT fan-out — see DECISIONS.md and
    scripts/bench_workers.py for why this beats physical-core cap on this
    workload).
    """
    if workers is None:
        workers = min(os.cpu_count() or 1, n_games)
    args_list = [(seed + i, window_size) for i in range(n_games)]

    # Skip the ETA banner for tiny runs (test fuzz reuses this helper)
    if n_games >= 16:
        per_item = measure_one(_play_one_random_game, args_list[0])
        print_banner(
            label=f"random self-play (window={window_size})",
            n_items=n_games,
            workers=workers,
            measured_per_item_seconds=per_item,
        )

    if workers <= 1 or n_games <= 1:
        outcomes = [_play_one_random_game(a) for a in args_list]
    else:
        with Pool(processes=workers) as pool:
            outcomes = pool.map(_play_one_random_game, args_list)

    rule_violations = sum(1 for o in outcomes if o.rule_violation)
    mask_violations = sum(1 for o in outcomes if o.mask_violation)
    completed = sum(1 for o in outcomes if o.completed)
    overflow_games = sum(1 for o in outcomes if o.had_overflow)
    score_sums = [o.score_sum for o in outcomes if o.completed]

    for o in outcomes:
        if o.error:
            print(f"  {o.error}", file=sys.stderr)

    return {
        "n_games": n_games,
        "completed": completed,
        "rule_violations": rule_violations,
        "mask_violations": mask_violations,
        "overflow_games": overflow_games,
        "overflow_rate": overflow_games / max(n_games, 1),
        "mean_score_sum": (sum(score_sums) / len(score_sums)) if score_sums else 0.0,
        "workers": workers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="carcassonne_ai.game_wrapper")
    parser.add_argument("--self-play-random", action="store_true",
                        help="Run random-vs-random games through the wrapper")
    parser.add_argument("--n", type=int, default=100, help="Number of games")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE)
    parser.add_argument("--workers", type=int, default=None,
                        help="Pool size (default: os.cpu_count())")
    args = parser.parse_args(argv)
    if not args.self_play_random:
        parser.error("nothing to do; pass --self-play-random")

    print(f"Running {args.n} random-vs-random games (window={args.window_size}, workers={args.workers or 'auto'})...")
    summary = _self_play_random(
        args.n, seed=args.seed, window_size=args.window_size, workers=args.workers
    )
    for k, v in summary.items():
        print(f"  {k}: {v}")
    if summary["rule_violations"] > 0 or summary["mask_violations"] > 0:
        print("FAIL: rule or mask violations detected", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
