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
from dataclasses import dataclass
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


@dataclass
class LeafConfig:
    """Tunable knobs for the virtual_score_v2 leaf evaluator.

    Passing an explicit LeafConfig to `virtual_score_v2` lets two leaf
    variants coexist in one process — required for a clean same-checkpoint
    leaf-vs-leaf A/B head-to-head (the env-var globals below cannot do this,
    since they are read once at import). When no config is passed,
    `DEFAULT_CONFIG` (built from the CARCASSONNE_V25_* env vars) is used.

    Fields:
      closure_p: {open_positions: P(closure)} schedule for `_close_prob`.
      bonus_cap / opp_bonus_cap: per-player clamp on the anticipation bonus.
      meeple_k: weight on the (meeples_self - meeples_opp) economy term.
      tile_counting_closure: if True, `_close_prob` consults the remaining
        deck — P=0 for features the deck can no longer complete (Step 2 of
        the 2026-05-17 Option-1 plan). Default False = v2.7 behavior.
      closure_continuous_slack: if > 0, the hard tile-counting gate is
        replaced by a continuous deck-aware ramp — P(closure) is scaled by
        `_supply_factor(supply, need, slack)` instead of cliffed to 0 (Step 5
        of the Option-1 plan). Overrides `tile_counting_closure` when set.
        Default 0.0 = off.
      value_blend: if > 0, the leaf wrapper blends the network value head
        into the leaf value — `leaf = (1-λ)·tanh(vs2/15) + λ·v_nn` (Option 2,
        2026-05-17). 0.0 = pure heuristic leaf (v2.7 production). Read by
        `evaluators.make_v25_value_wrapper`, not by `virtual_score_v2` itself.
    """
    closure_p: dict[int, float]
    bonus_cap: float
    opp_bonus_cap: float
    meeple_k: float = 0.0
    tile_counting_closure: bool = False
    closure_continuous_slack: float = 0.0
    value_blend: float = 0.0


def _config_from_env() -> LeafConfig:
    """Build the default LeafConfig from the CARCASSONNE_V25_* env vars.

    Schedule history: v2.5 halved v2's {1:1.0, 2:0.5, 3:0.25} (the v2
    diagnostic showed the bonus was 4-7x the v1 base, saturating tanh).
    v2.6 (ONE_OPEN_ONLY) restricts to 1-open features. v2.7 (DROP_THREE_OPEN,
    the production default) keeps {1, 2} — the 3-open lottery tickets were
    noise. `CARCASSONNE_V25_CAP` default 5.0 is the pre-v2.7 value; the v2.7
    production runs set CAP=12 explicitly.
    """
    if os.environ.get("CARCASSONNE_V25_ONE_OPEN_ONLY") == "1":
        closure_p: dict[int, float] = {1: 1.0}
    elif os.environ.get("CARCASSONNE_V25_DROP_THREE_OPEN") == "1":
        closure_p = {1: 0.5, 2: 0.2}
    else:
        closure_p = {1: 0.5, 2: 0.2, 3: 0.05}
    bonus_cap = float(os.environ.get("CARCASSONNE_V25_CAP", "5.0"))
    return LeafConfig(
        closure_p=closure_p,
        bonus_cap=bonus_cap,
        opp_bonus_cap=float(os.environ.get("CARCASSONNE_V25_OPP_CAP", str(bonus_cap))),
        meeple_k=float(os.environ.get("CARCASSONNE_V25_MEEPLE_K", "0.0")),
        value_blend=float(os.environ.get("CARCASSONNE_V25_VALUE_BLEND", "0.0")),
        tile_counting_closure=(os.environ.get("CARCASSONNE_V25_TILE_COUNTING") == "1"),
        closure_continuous_slack=float(os.environ.get("CARCASSONNE_V25_CLOSURE_SLACK", "0.0")),
    )


DEFAULT_CONFIG: LeafConfig = _config_from_env()

# Back-compat module constants — some tests + diagnose_v2.py import these
# directly. They mirror DEFAULT_CONFIG; new code should pass a LeafConfig.
_CLOSURE_P: dict[int, float] = DEFAULT_CONFIG.closure_p
_BONUS_CAP: float = DEFAULT_CONFIG.bonus_cap
_OPP_BONUS_CAP: float = DEFAULT_CONFIG.opp_bonus_cap
_MEEPLE_K: float = DEFAULT_CONFIG.meeple_k


def _close_prob(open_positions: int, closure_p: dict[int, float] | None = None) -> float:
    """Probability that an incomplete feature closes by game-end given how
    many adjacent positions still need tiles. `closure_p` defaults to the
    env-built DEFAULT_CONFIG schedule."""
    if open_positions <= 0:
        return 1.0  # already closed (defensive — shouldn't be called)
    if closure_p is None:
        closure_p = DEFAULT_CONFIG.closure_p
    return closure_p.get(open_positions, 0.0)


_CARDINAL_SIDES = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)


def _deck_city_supply(state) -> int:
    """Number of tiles still in the deck that carry at least one city edge.

    A tile is rotated freely on placement, so any cardinal city edge means
    the tile *could* be used to extend a city — a deliberately permissive
    (over-counting) proxy for true placeability (true placeability needs an
    adjacency search, too expensive for the leaf eval hot path). Used by the
    Option-1 tile-counting closure gate: a city needing N more tiles cannot
    close if fewer than N city-bearing tiles remain in the deck."""
    n = 0
    for tile in state.deck:
        if any(tile.get_type(s) == TerrainType.CITY for s in _CARDINAL_SIDES):
            n += 1
    return n


def _supply_factor(supply: int, need: int, slack: float) -> float:
    """Continuous deck-aware closure discount (Option-1 step 5, 2026-05-17).

    Where the tile-counting gate is a hard cliff (P→0 only when the deck
    *literally cannot* finish a feature), this scales P(closure) smoothly by
    how plentiful the usable deck supply is. factor=1.0 once supply reaches
    `need * slack` (closure unconstrained by the deck), ramping linearly to
    0.0 as supply→0. `slack` > 1 reflects that not every usable drawn tile
    lands on this feature, so supply must exceed bare `need` severalfold
    before closure is treated as supply-unconstrained."""
    if need <= 0 or slack <= 0.0:
        return 1.0
    f = supply / (need * slack)
    if f >= 1.0:
        return 1.0
    return f if f > 0.0 else 0.0


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


def _closure_anticipation_bonus(state, player: int, cfg: "LeafConfig | None" = None) -> float:
    """Sum of P(closure) × score-delta over all of `player`'s placed meeples
    on incomplete features.

    `cfg` selects the closure-probability schedule (and, for Step 2, the
    tile-counting gate); defaults to DEFAULT_CONFIG.

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
    if cfg is None:
        cfg = DEFAULT_CONFIG
    closure_p = cfg.closure_p
    # Deck-aware closure (Option-1 steps 2 & 5): a feature whose open
    # positions outnumber what the remaining deck can supply is unlikely (or
    # unable) to close by game-end. `gate` = the step-2 hard cliff (P→0 when
    # the deck literally can't finish it); `continuous` = the step-5 smooth
    # ramp, which overrides the gate when on. When both are off (v2.7
    # default) the supply scan is skipped entirely — zero overhead.
    gate = cfg.tile_counting_closure
    slack = cfg.closure_continuous_slack
    continuous = slack > 0.0
    _need_supply = gate or continuous
    deck_size = len(state.deck) if _need_supply else 0
    city_supply = _deck_city_supply(state) if _need_supply else 0
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
            p = _close_prob(open_n, closure_p)
            if continuous:
                p *= _supply_factor(city_supply, open_n, slack)
            elif gate and (deck_size < open_n or city_supply < open_n):
                p = 0.0  # deck can no longer complete this city
            if p > 0:
                delta = _city_closure_delta(state, city)
                bonus += p * delta

        elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
            n_surround = _surrounding_count(state, coord)
            needed = 8 - n_surround
            if needed > 0:
                p = _close_prob(needed, closure_p)
                if continuous:
                    p *= _supply_factor(deck_size, needed, slack)
                elif gate and deck_size < needed:
                    p = 0.0  # not enough tiles left to surround the cloister
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
                    p = _close_prob(open_n, closure_p)
                    if continuous:
                        p *= _supply_factor(city_supply, open_n, slack)
                    elif gate and (deck_size < open_n or city_supply < open_n):
                        p = 0.0  # deck can no longer complete this city
                    if p > 0:
                        bonus += p * 3
        # ROAD: no closure delta (complete and incomplete both score 1pt/tile
        # without inn modifier; with inn, finished=2/tile, unfinished=0).
        # Inn-roads ARE a closure-blind spot but rare in 2p River+Farmers.
        # Skip for v2; add in v3 if road denial shows up in failure modes.

    return bonus  # uncapped — caller decides which cap to apply (self vs opp)


def _capped(bonus: float, cap: float) -> float:
    if bonus > cap:
        return cap
    return bonus


def virtual_score_v2(
    state: "CarcassonneGameState", player: int, cfg: "LeafConfig | None" = None
) -> int:
    """v1 base + closure-anticipation bonus (self) - closure-anticipation
    bonus (opponent), with optional v3 meeple-economy term.

    `cfg` selects the leaf-eval knobs (closure schedule, caps, meeple_k,
    tile-counting). When None, DEFAULT_CONFIG (env-var-built) is used —
    back-compat. Pass an explicit LeafConfig to A/B two leaf variants in
    one process.

    Caps: self bonus capped at `cfg.bonus_cap`, opp bonus at
    `cfg.opp_bonus_cap` (defaults to same; raise opp cap to strengthen the
    denial signal in search).

    v3 meeple term (off when meeple_k=0.0): adds `cfg.meeple_k × (meeples_self
    - meeples_opp)` AFTER caps. `state.meeples[i]` is i's unplaced-meeple
    count (start 7, decrements on placement, returns on closure).
    """
    if state.players != 2:
        raise ValueError(
            f"virtual_score_v2 is implemented for 2-player only; got {state.players}"
        )
    if cfg is None:
        cfg = DEFAULT_CONFIG
    base = virtual_score(state, player)
    opp = 1 - player
    # Compute bonuses on the live (non-mutated) state. virtual_score deepcopies
    # internally so it does not mutate `state`.
    bonus_self = _capped(_closure_anticipation_bonus(state, player, cfg), cfg.bonus_cap)
    bonus_opp = _capped(_closure_anticipation_bonus(state, opp, cfg), cfg.opp_bonus_cap)
    score = base + bonus_self - bonus_opp
    if cfg.meeple_k > 0.0:
        score += cfg.meeple_k * (state.meeples[player] - state.meeples[opp])
    return int(round(score))
