"""Virtual-score v2 — adds closure-proximity bonus + farm-growth potential
on top of the base `virtual_score`.

Diagnosed failure modes of v1 (DECISIONS.md 2026-05-14):
  1. **Closure-event blindness.** v1 gives partial credit for incomplete cities
     (1pt/tile, 1pt/shield) but the same tiles score double when the city
     closes (2pt/tile, 2pt/shield). v1 doesn't anticipate the partial→full
     credit swing → confidently mis-prices positions when a closure is
     imminent. Same for cloisters (1+N → 9 at close).
  2. **Farm composition opacity.** v1's farm scoring counts only cities with
     `city.finished == True`. Incomplete cities adjacent to a farmed area
     contribute 0 to v1, but those cities tend to complete by game-end,
     producing +3pts each. v1 systematically *underestimates* mature farms.

v2 adds an anticipation bonus for each placed meeple, weighted by P(closure)
based on how many adjacent board positions need to be filled. Mirror for the
opponent: their anticipated closures subtract from our v2 value.

Closure-probability heuristic (open_positions → P):
  1 → 1.0   (next tile placed nearby almost certainly closes)
  2 → 0.5
  3 → 0.25
  4+ → 0.0  (too far out; tile supply runs out before closure)

These thresholds are initial guesses. If v2 improves winrate, tune via a
small grid search; if v2 doesn't improve, the failure mode is elsewhere
(probably denial/meeple economy) and we redesign instead of tuning.

API mirrors `virtual_score`:
    diff = virtual_score_v2(state, player=0)
"""
from __future__ import annotations

import copy
import os
from typing import TYPE_CHECKING

from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.utils.city_util import CityUtil
from wingedsheep.carcassonne.utils.farm_util import FarmUtil
from wingedsheep.carcassonne.utils.points_collector import PointsCollector

from .virtual_score import virtual_score

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.objects.city import City


# Closure probability as a function of number of open adjacent positions.
# Hand-picked initial heuristic, see module docstring.
#
# v2.5 (2026-05-14): halved from v2's {1: 1.0, 2: 0.5, 3: 0.25}. v2-diagnostic
# showed v2's bonus magnitude was 4-7x the v1 base, saturating tanh and killing
# the search gradient. v2.5 brings the bonus into the same scale as the base.
_CLOSURE_P: dict[int, float] = {1: 0.5, 2: 0.2, 3: 0.05}

# v2.5 hard cap on the per-player bonus. The bonus is non-negative by
# construction; clamping to [0, BONUS_CAP] prevents chained closure waves
# (multiple farmers + multiple near-complete cities) from saturating the leaf
# value through tanh. Net bonus = bonus_self - bonus_opp is then in
# [-BONUS_CAP, +BONUS_CAP]. With a typical base of ±15-30, leaf value stays
# in tanh's responsive region.
#
# Tunable via CARCASSONNE_V25_CAP env var (read once at module import time)
# for cap-tuning sweeps. Default 5.0 is the validated production value.
_BONUS_CAP: float = float(os.environ.get("CARCASSONNE_V25_CAP", "5.0"))


def _close_prob(open_positions: int) -> float:
    """Probability that an incomplete feature closes by game-end given how
    many adjacent positions still need tiles."""
    if open_positions <= 0:
        return 1.0  # already closed (defensive — shouldn't be called)
    return _CLOSURE_P.get(open_positions, 0.0)


def _neighbor_coord(coord: Coordinate, side: Side) -> Coordinate | None:
    """Coordinate of the tile adjacent to `coord` across `side`. Returns
    None for non-cardinal sides (e.g. farmer corners), which are handled
    differently in scoring."""
    if side == Side.TOP:
        return Coordinate(coord.row - 1, coord.column)
    if side == Side.BOTTOM:
        return Coordinate(coord.row + 1, coord.column)
    if side == Side.LEFT:
        return Coordinate(coord.row, coord.column - 1)
    if side == Side.RIGHT:
        return Coordinate(coord.row, coord.column + 1)
    return None


def _open_city_positions(state, city: "City") -> int:
    """Number of unique adjacent board positions that need a tile (with a
    matching city side) to close this city. Coarse — counts empty neighbors
    of city-side positions, deduplicated."""
    seen: set[tuple[int, int]] = set()
    for pos in city.city_positions:
        neighbor = _neighbor_coord(pos.coordinate, pos.side)
        if neighbor is None:
            continue
        if 0 <= neighbor.row < len(state.board) and 0 <= neighbor.column < len(state.board[0]):
            if state.board[neighbor.row][neighbor.column] is None:
                seen.add((neighbor.row, neighbor.column))
    return len(seen)


def _city_closure_delta(state, city: "City") -> int:
    """Score delta if this incomplete city closed: full credit minus partial
    credit. For a city with T tiles and S shields, partial = T+S, full =
    2T+2S, so delta = T+S. Cathedrals (inns flag) are scored at 3pts/tile
    when finished, 0 when unfinished — different math, handled separately."""
    if city.finished:
        return 0
    has_cathedral = False
    coords: set[tuple[int, int]] = set()
    for pos in city.city_positions:
        c = pos.coordinate
        tile = state.board[c.row][c.column]
        if tile is None:
            continue
        if tile.inn:  # engine reuses .inn as the cathedral flag on city tiles
            has_cathedral = True
        coords.add((c.row, c.column))
    delta = 0
    for r, col in coords:
        tile = state.board[r][col]
        if has_cathedral:
            # incomplete cathedral city = 0pts, complete = 3pts/tile (or 6 with shield).
            # Risk of closure with cathedral is high reward, but our coarse
            # heuristic doesn't distinguish; treat as plain city for delta.
            delta += 6 if tile.shield else 3
        else:
            delta += 2 if tile.shield else 1
    return delta


def _surrounding_count(state, coord: Coordinate) -> int:
    """Number of placed tiles among the 8 cells surrounding `coord`. Same
    metric the engine uses to score a cloister/chapel/flowers."""
    n = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = coord.row + dr, coord.column + dc
            if 0 <= r < len(state.board) and 0 <= c < len(state.board[0]):
                if state.board[r][c] is not None:
                    n += 1
    return n


def _closure_anticipation_bonus(state, player: int) -> int:
    """Sum of P(closure) × score-delta over all of `player`'s placed meeples
    on incomplete features. Integer-rounded for compatibility with v1's
    int return type.

    Dedupes features (cities and farms) across meeples — multiple meeples
    on the same farm/city contribute the bonus exactly once. This both
    fixes a real over-counting bug (the engine itself only scores each
    farm once per player regardless of how many of that player's farmers
    are on it) AND cuts CPU work by skipping repeated find_city /
    find_farm_by_coordinate calls on the same logical feature.
    Identification is by canonical content (frozenset of city positions /
    farmer connections) since the engine returns a fresh City/Farm
    object on each call (no __eq__/__hash__).
    """
    bonus = 0.0
    seen_cities: set[frozenset] = set()
    seen_farms: set[frozenset] = set()
    # Cities counted via farm-growth bonus stay deduped across all the
    # player's farms — same incomplete city adjacent to two farms shouldn't
    # be paid for twice.
    counted_growth_cities: set[frozenset] = set()

    for mp in state.placed_meeples[player]:
        coord_side = mp.coordinate_with_side
        coord = coord_side.coordinate
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        terrain = tile.get_type(coord_side.side)

        if terrain == TerrainType.CITY:
            city = CityUtil.find_city(game_state=state, city_position=coord_side)
            city_key = frozenset(city.city_positions)
            if city_key in seen_cities:
                continue
            seen_cities.add(city_key)
            if city.finished:
                continue
            open_n = _open_city_positions(state, city)
            p = _close_prob(open_n)
            if p > 0:
                delta = _city_closure_delta(state, city)
                bonus += p * delta

        elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
            n_surround = _surrounding_count(state, coord)
            needed = 8 - n_surround
            if needed > 0:
                p = _close_prob(needed)
                if p > 0:
                    # Cloister already scores 1 + n_surround in v1's partial.
                    # If closed, scores 9. Delta = 8 - n_surround.
                    bonus += p * (8 - n_surround)

        elif mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
            # Farm growth: for each incomplete city adjacent to this farm,
            # add 3 × P(closes). Cities that ARE already complete are
            # already counted by v1 — don't double-count.
            farm = FarmUtil.find_farm_by_coordinate(game_state=state, position=coord_side)
            farm_key = frozenset(farm.farmer_connections_with_coordinate)
            if farm_key in seen_farms:
                continue
            seen_farms.add(farm_key)
            for fc in farm.farmer_connections_with_coordinate:
                cities = CityUtil.find_cities(
                    game_state=state,
                    coordinate=fc.coordinate,
                    sides=fc.farmer_connection.city_sides,
                )
                for city in cities:
                    city_key = frozenset(city.city_positions)
                    if city_key in counted_growth_cities:
                        continue
                    counted_growth_cities.add(city_key)
                    if city.finished:
                        continue  # already in v1 farm score
                    open_n = _open_city_positions(state, city)
                    p = _close_prob(open_n)
                    if p > 0:
                        bonus += p * 3
        # ROAD: no closure delta (complete and incomplete both score 1pt/tile
        # without inn modifier; with inn, finished=2/tile, unfinished=0).
        # Inn-roads ARE a closure-blind spot but rare in 2p River+Farmers.
        # Skip for v2; add in v3 if road denial shows up in failure modes.

    if bonus > _BONUS_CAP:
        return _BONUS_CAP
    return bonus


def virtual_score_v2(state: "CarcassonneGameState", player: int) -> int:
    """v1 base + closure-anticipation bonus (self) - closure-anticipation
    bonus (opponent). See module docstring for the failure modes this
    addresses and the closure-probability heuristic."""
    if state.players != 2:
        raise ValueError(
            f"virtual_score_v2 is implemented for 2-player only; got {state.players}"
        )
    base = virtual_score(state, player)
    opp = 1 - player
    # Compute bonuses on the live (non-mutated) state. virtual_score deepcopies
    # internally so it does not mutate `state`.
    bonus_self = _closure_anticipation_bonus(state, player)
    bonus_opp = _closure_anticipation_bonus(state, opp)
    return int(round(base + bonus_self - bonus_opp))
