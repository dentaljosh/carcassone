"""Verify the per-side / per-corner meeple encoding.

Pre-fix: a NORMAL meeple anywhere on a tile lit a single mine/opp channel.
A meeple on TOP (claiming the top city) was indistinguishable from a meeple
on CENTER (claiming a chapel). The expanded encoding gives one channel per
side (5) for normal meeples and one per corner (4) for farmers.
"""
from __future__ import annotations

import random

import numpy as np
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side

from carcassonne_ai import board_repr as B
from carcassonne_ai.game_wrapper import Game


def _empty_board_with_meeple(side: Side, mt: MeepleType, owner: int):
    """Build a stepped board, then plant ONE synthetic meeple at a fixed
    coord/side so we can check exactly which channel lights up.
    """
    g = Game()
    random.seed(0)
    b = g.get_init_board()
    # Step a few times so a tile exists at the coord we'll plant the meeple on.
    for _ in range(5):
        if g.get_game_ended(b, 0) != 0.0:
            break
        mask = g.get_valid_moves(b)
        legal = np.flatnonzero(mask)
        b, _ = g.get_next_state(b, int(random.choice(legal)))
    # Find a placed-tile coordinate to attach the meeple to.
    placed_coord = None
    for r, row in enumerate(b.state.board):
        for c, t in enumerate(row):
            if t is not None:
                placed_coord = (r, c)
                break
        if placed_coord is not None:
            break
    assert placed_coord is not None
    # Wipe all real meeples to isolate the channel we're testing.
    b.state.placed_meeples = [[], []]
    cws = CoordinateWithSide(
        coordinate=Coordinate(row=placed_coord[0], column=placed_coord[1]),
        side=side,
    )
    b.state.placed_meeples[owner].append(MeeplePosition(meeple_type=mt, coordinate_with_side=cws))
    return g, b, placed_coord


def test_normal_meeple_on_each_side_lights_distinct_channel() -> None:
    seen_offsets = set()
    for i, side in enumerate((Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT, Side.CENTER)):
        g, b, (pr, pc) = _empty_board_with_meeple(side, MeepleType.NORMAL, owner=0)
        arr = B.encode_board(b.state, player=0, off=b.offset)
        wr, wc = pr - b.offset.origin_row, pc - b.offset.origin_col
        # All 5 mine-side channels are at CH_NORMAL_MEEPLE_MINE..+5; only
        # one should be hot at this cell.
        block = arr[B.CH_NORMAL_MEEPLE_MINE:B.CH_NORMAL_MEEPLE_MINE + 5, wr, wc]
        hot = np.flatnonzero(block)
        assert hot.shape == (1,), f"side={side} got block={block}"
        assert hot[0] == i, f"side={side} expected offset {i}, got {hot[0]}"
        seen_offsets.add(int(hot[0]))
    assert seen_offsets == {0, 1, 2, 3, 4}


def test_farmer_on_each_corner_lights_distinct_channel() -> None:
    seen_offsets = set()
    for i, corner in enumerate(
        (Side.TOP_LEFT, Side.TOP_RIGHT, Side.BOTTOM_LEFT, Side.BOTTOM_RIGHT)
    ):
        g, b, (pr, pc) = _empty_board_with_meeple(corner, MeepleType.FARMER, owner=0)
        arr = B.encode_board(b.state, player=0, off=b.offset)
        wr, wc = pr - b.offset.origin_row, pc - b.offset.origin_col
        block = arr[B.CH_FARMER_MEEPLE_MINE:B.CH_FARMER_MEEPLE_MINE + 4, wr, wc]
        hot = np.flatnonzero(block)
        assert hot.shape == (1,), f"corner={corner} got block={block}"
        assert hot[0] == i, f"corner={corner} expected offset {i}, got {hot[0]}"
        seen_offsets.add(int(hot[0]))
    assert seen_offsets == {0, 1, 2, 3}


def test_owner_swap_routes_to_opp_block() -> None:
    """A meeple owned by player 1 (opponent of player 0) must light the OPP
    block — not the MINE block — when encoded from player 0's perspective.
    """
    g, b, (pr, pc) = _empty_board_with_meeple(Side.RIGHT, MeepleType.NORMAL, owner=1)
    arr = B.encode_board(b.state, player=0, off=b.offset)
    wr, wc = pr - b.offset.origin_row, pc - b.offset.origin_col

    mine_block = arr[B.CH_NORMAL_MEEPLE_MINE:B.CH_NORMAL_MEEPLE_MINE + 5, wr, wc]
    opp_block = arr[B.CH_NORMAL_MEEPLE_OPP:B.CH_NORMAL_MEEPLE_OPP + 5, wr, wc]
    assert mine_block.sum() == 0.0
    # RIGHT is offset 1 in (T, R, B, L, CENTER).
    assert opp_block[1] == 1.0
    assert opp_block.sum() == 1.0
