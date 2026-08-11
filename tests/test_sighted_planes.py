"""M2 canonical-AZ "sighted" representation: byte-identical-when-off + shape-on.

Contract (measurement-only opt-in):
  * Game(sighted=False) — the production default — MUST produce a featurizer
    output byte-identical to a direct encode_board/encode_scalars (the branch is
    never taken; nothing shifts). This is the guard that turning the flag OFF
    leaves the champion / production path untouched.
  * Game(sighted=True) appends exactly +3 farm-connectivity planes (78 -> 81 ch)
    and +32 bag-histogram scalars, with the first 78 channels / base scalars
    byte-identical to the blind path.
  * The src helpers (carcassonne_ai.sighted_planes) stay byte-identical to the
    original standalone helpers in scripts/feature_planes_gate/step1_planes.py.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pytest

from carcassonne_ai.board_repr import N_CHANNELS, encode_board
from carcassonne_ai.features import encode_scalars
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.sighted_planes import (
    N_BAG,
    N_FARM_PLANES,
    bag_histogram,
    farm_connectivity_planes,
)

REPO = Path(__file__).resolve().parents[1]


def _midgame_boards(seed: int, n_steps: int, window_size: int = 25):
    """Play a random game and yield (board, current_player) snapshots."""
    g = Game(window_size=window_size)
    board = g.get_init_board()
    random.seed(seed)
    out = []
    steps = 0
    while g.get_game_ended(board, 0) == 0.0 and steps < n_steps:
        out.append((board, board.state.current_player))
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = g.get_next_state(board, int(random.choice(legal)))
        steps += 1
    return out


# --------------------------------------------------------------------------- #
# OFF path: byte-identical to the unmodified featurizer.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("include_farm", [False, True])
def test_sighted_off_is_byte_identical(include_farm: bool) -> None:
    g = Game(sighted=False, include_farm_scalars=include_farm)
    base_channels = N_CHANNELS
    base_scalars = 12 if include_farm else 10
    assert g.get_input_channels() == base_channels
    assert g.get_scalar_feature_size() == base_scalars
    assert g.get_board_shape() == (base_channels, g.window_size, g.window_size)

    for board, _ in _midgame_boards(seed=7, n_steps=70):
        for player in (0, 1):
            arr, scalars = g.get_canonical_form(board, player)
            ref_arr = encode_board(board.state, player, board.offset)
            ref_scalars = encode_scalars(
                board.state, player, board.total_tiles, include_farm=include_farm
            )
            assert arr.shape == (base_channels, g.window_size, g.window_size)
            assert scalars.shape == (base_scalars,)
            # byte-identical: sighted=False must not touch the arrays at all.
            assert np.array_equal(arr, ref_arr)
            assert np.array_equal(scalars, ref_scalars)


# --------------------------------------------------------------------------- #
# ON path: +3 planes / +32 scalars, identical prefix.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("include_farm", [False, True])
def test_sighted_on_shapes_and_prefix(include_farm: bool) -> None:
    g = Game(sighted=True, include_farm_scalars=include_farm)
    base_scalars = 12 if include_farm else 10
    exp_ch = N_CHANNELS + N_FARM_PLANES
    exp_scalars = base_scalars + N_BAG
    assert g.get_input_channels() == exp_ch == 81
    assert g.get_scalar_feature_size() == exp_scalars == base_scalars + 32
    assert g.get_board_shape() == (exp_ch, g.window_size, g.window_size)

    for board, _ in _midgame_boards(seed=11, n_steps=70):
        for player in (0, 1):
            arr, scalars = g.get_canonical_form(board, player)
            assert arr.shape == (exp_ch, g.window_size, g.window_size)
            assert scalars.shape == (exp_scalars,)
            # First 78 channels / base scalars are byte-identical to blind path.
            ref_arr = encode_board(board.state, player, board.offset)
            ref_scalars = encode_scalars(
                board.state, player, board.total_tiles, include_farm=include_farm
            )
            assert np.array_equal(arr[:N_CHANNELS], ref_arr)
            assert np.array_equal(scalars[:base_scalars], ref_scalars)
            # Appended block equals the standalone helpers exactly.
            ref_fp = farm_connectivity_planes(
                board.state, player, board.offset, board.offset.size
            )
            ref_bag = bag_histogram(board.state)
            assert np.array_equal(arr[N_CHANNELS:], ref_fp)
            assert np.array_equal(scalars[base_scalars:], ref_bag)


def test_sighted_planes_fire_somewhere() -> None:
    """At least one mid/late-game position must have nonzero farm planes and a
    depleted (non-all-ones) bag — proves the sighted signal is live, not a stub."""
    g = Game(sighted=True)
    saw_farm = False
    saw_depleted_bag = False
    for board, player in _midgame_boards(seed=1940000001, n_steps=110):
        arr, scalars = g.get_canonical_form(board, player)
        if arr[N_CHANNELS:].sum() > 0:
            saw_farm = True
        bag = scalars[10:]
        if 0.0 < bag.sum() < N_BAG:
            saw_depleted_bag = True
        if saw_farm and saw_depleted_bag:
            break
    assert saw_depleted_bag, "bag histogram never depleted across a full game"
    assert saw_farm, "farm-connectivity planes never fired across a full game"


# --------------------------------------------------------------------------- #
# Parity: src helpers == the original standalone scripts helpers.
# --------------------------------------------------------------------------- #
def test_src_helpers_match_scripts_helpers() -> None:
    """carcassonne_ai.sighted_planes must stay byte-identical to the standalone
    scripts/feature_planes_gate/step1_planes.py helpers it was moved from."""
    sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))
    import step1_planes as legacy  # noqa: E402

    assert legacy.BASE_TILE_COUNTS == \
        __import__("carcassonne_ai.sighted_planes", fromlist=["BASE_TILE_COUNTS"]).BASE_TILE_COUNTS
    for board, player in _midgame_boards(seed=1940000001, n_steps=90):
        fp_src = farm_connectivity_planes(
            board.state, player, board.offset, board.offset.size
        )
        fp_legacy = legacy.farm_connectivity_planes(
            board.state, player, board.offset, board.offset.size
        )
        assert np.array_equal(fp_src, fp_legacy)
        assert np.array_equal(bag_histogram(board.state), legacy.bag_histogram(board.state))
