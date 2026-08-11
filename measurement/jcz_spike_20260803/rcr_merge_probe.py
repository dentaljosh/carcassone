#!/usr/bin/env python3
"""Empirical probe for the ONE tile-data divergence the JCZ diff found.

`city_top_straight_road` (JCZ `BA/RCr`, 4 copies) declares its NORTH field region
as tile_connections = {TLL, TLT, TRT, TRR}. TLT and TRT are the two halves of the
NORTH edge -- which on this tile is a CITY. JCZ declares the same region as
{WR, EL} only. Every other one of our 32 kinds agrees with JCZ exactly.

`FarmUtil.find_farm` crosses a `tile_connection` unconditionally (there is no
grass/city gate anywhere on the traversal), so the surplus TLT/TRT should make the
under-city field strip of one RCr merge with the under-city field strip of a second
RCr placed city-to-city against it -- a farm merge THROUGH a city, which is
geometrically impossible.

This probe builds that two-tile board directly and asks find_farm.

Usage: .venv/bin/python measurement/jcz_spike_20260803/rcr_merge_probe.py
"""
import copy
import sys

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
from wingedsheep.carcassonne.utils.farm_util import FarmUtil


def probe():
    rcr = base_tiles["city_top_straight_road"]          # city N, road W-E
    rcr180 = rcr.turn(2)                                # city S, road W-E

    state = CarcassonneGameState()
    R, C = 10, 10
    # (R,C) holds the upright RCr  -> its city is on its N edge.
    # (R-1,C) holds the 180-rotated RCr -> its city is on its S edge.
    # The two cities meet across the shared border: a legal placement.
    state.board[R][C] = rcr
    state.board[R - 1][C] = rcr180

    lower_north = CoordinateWithSide(Coordinate(R, C), Side.TOP_LEFT)
    upper_south = CoordinateWithSide(Coordinate(R - 1, C), Side.BOTTOM_LEFT)

    farm_lo = FarmUtil.find_farm_by_coordinate(state, lower_north)
    farm_hi = FarmUtil.find_farm_by_coordinate(state, upper_south)

    lo_cells = sorted((n.coordinate.row - R, n.coordinate.column - C)
                      for n in farm_lo.farmer_connections_with_coordinate)
    hi_cells = sorted((n.coordinate.row - R, n.coordinate.column - C)
                      for n in farm_hi.farmer_connections_with_coordinate)

    merged = len(farm_lo.farmer_connections_with_coordinate) > 1

    print("two RCr tiles, cities joined across the shared N/S border")
    print("  lower tile (0,0) north field  -> region cells (row-offset, col-offset):", lo_cells)
    print("  upper tile (-1,0) south field -> region cells:", hi_cells)
    print()
    if merged:
        print("  RESULT: MERGED  ***  the two under-city field strips are ONE farm.")
        print("          They are separated by a completed-or-not city; canonical rules")
        print("          (and JCZ's tile data) keep them as two distinct fields.")
    else:
        print("  RESULT: separate (no divergence observed).")

    # control: does the same probe on the JCZ-correct data keep them apart?
    print()
    print("control -- same board with the surplus TLT/TRT removed from the north field:")
    fixed = copy.deepcopy(rcr)
    north = [f for f in fixed.farms if f.city_sides][0]
    from wingedsheep.carcassonne.objects.farmer_side import FarmerSide
    north.tile_connections = [s for s in north.tile_connections
                              if s not in (FarmerSide.TLT, FarmerSide.TRT)]
    state2 = CarcassonneGameState()
    state2.board[R][C] = fixed
    state2.board[R - 1][C] = fixed.turn(2)
    farm2 = FarmUtil.find_farm_by_coordinate(state2, lower_north)
    print("  region cells:", sorted((n.coordinate.row - R, n.coordinate.column - C)
                                    for n in farm2.farmer_connections_with_coordinate))
    print("  -> separate" if len(farm2.farmer_connections_with_coordinate) == 1
          else "  -> still merged (something else is going on)")
    return 0 if not merged else 2


if __name__ == "__main__":
    sys.exit(probe())
