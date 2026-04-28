"""Verify phase-aware action encode/decode round-trips on real engine actions."""
from __future__ import annotations

import os
import random
from multiprocessing import Pool

import pytest

from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.utils.action_util import ActionUtil

from carcassonne_ai import action_space as A
from carcassonne_ai.game_wrapper import Game


def _actions_equal(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, PassAction):
        return True
    if isinstance(a, TileAction):
        return (
            a.coordinate == b.coordinate
            and a.tile_rotations == b.tile_rotations
            and a.tile.description == b.tile.description
        )
    if isinstance(a, MeepleAction):
        return (
            a.meeple_type == b.meeple_type
            and a.coordinate_with_side == b.coordinate_with_side
        )
    return False


@pytest.mark.parametrize("window_size", [25, 21, 31])
def test_action_size_matches_constants(window_size: int) -> None:
    g = Game(window_size=window_size)
    assert g.get_action_size() == A.action_size(window_size)
    assert A.tile_action_count(window_size) == window_size * window_size * 4
    assert A.action_size(window_size) == window_size * window_size * 4 + 11


def test_pass_indices_are_distinct_and_phase_specific() -> None:
    off = A.WindowOffset(0, 0, 25)
    tile_pass_idx = A.encode(PassAction(), off, "tiles")
    meeple_pass_idx = A.encode(PassAction(), off, "meeples")
    assert tile_pass_idx == A.tile_pass_index(25)
    assert meeple_pass_idx == A.meeple_pass_index(25)
    assert tile_pass_idx != meeple_pass_idx
    assert A.decode(tile_pass_idx, off=off, phase="tiles") == PassAction() or isinstance(
        A.decode(tile_pass_idx, off=off, phase="tiles"), PassAction
    )
    assert isinstance(A.decode(meeple_pass_idx, off=off, phase="meeples"), PassAction)


def test_decoding_off_phase_index_raises() -> None:
    off = A.WindowOffset(0, 0, 25)
    # tile-half index decoded as meeples → error
    with pytest.raises(ValueError):
        A.decode(0, off=off, phase="meeples", last_tile_coord=None)
    # meeple-half index decoded as tiles → error
    with pytest.raises(ValueError):
        A.decode(A.meeple_normal_base(25), off=off, phase="tiles")
    # out of range → error
    with pytest.raises(ValueError):
        A.decode(A.action_size(25), off=off, phase="tiles")


def test_window_overflow_on_encode() -> None:
    """Encoding a TileAction at a coord outside the window raises WindowOverflowError."""
    from wingedsheep.carcassonne.objects.coordinate import Coordinate
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    off = A.WindowOffset(origin_row=0, origin_col=0, size=10)
    bogus = TileAction(
        tile=base_tiles["chapel"], coordinate=Coordinate(row=50, column=50), tile_rotations=0
    )
    with pytest.raises(A.WindowOverflowError):
        A.encode(bogus, off, "tiles")


def _round_trip_one_game(seed: int) -> tuple[int, str | None]:
    """Play one random game; round-trip every legal action through encode/decode.
    Returns (n_actions_checked, error_msg_or_None)."""
    import numpy as np

    g = Game()
    random.seed(seed)
    board = g.get_init_board()
    n = 0
    while g.get_game_ended(board, 0) == 0.0:
        phase = board.state.phase.value
        for action in ActionUtil.get_possible_actions(board.state):
            try:
                idx = A.encode(action, board.offset, phase)
            except A.WindowOverflowError:
                continue
            decoded = A.decode(
                idx,
                off=board.offset,
                phase=phase,
                next_tile=board.state.next_tile,
                last_tile_coord=(
                    board.state.last_tile_action.coordinate
                    if board.state.last_tile_action is not None
                    else None
                ),
            )
            if not _actions_equal(action, decoded):
                return n, f"seed {seed}: mismatch {action!r} vs {decoded!r} (idx={idx}, phase={phase})"
            n += 1
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    return n, None


def test_round_trip_on_real_random_play() -> None:
    """For 30 random games (parallelized), every legal action emitted by the
    engine must round-trip through encode→decode and produce an equivalent
    Action.
    """
    workers = min(os.cpu_count() or 1, 30)
    with Pool(processes=workers) as pool:
        results = pool.map(_round_trip_one_game, range(30))
    total = 0
    for n, err in results:
        assert err is None, err
        total += n
    assert total > 1000, f"expected >1000 round-trips, got {total}"
