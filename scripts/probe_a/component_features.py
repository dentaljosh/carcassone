"""PROBE A — the FROZEN per-component feature contract (A1<->A2 boundary).

Single source of truth for the per-component feature matrix that the structured
value head `g_theta` consumes. BOTH the Cython fast emit
(`flat_leaf_cy.component_features_cy`) and the (milestone-2) trainer read THIS
module's column order and semantics. If you change a column here you MUST rebuild
the .so and re-run tests/test_probe_a_feature_emit.py — they are bit-exact-gated.

WHY THIS VECTOR (not the 12-dim gate-zero starter):
------------------------------------------------------
The gate-zero bench (scripts/probe_a/gate_zero_speed.py) used a 12-dim starter
with NO player-relative / meeple-ownership info. That is inadequate: g_theta
cannot reconstruct the heuristic's per-term structure (leaf_v29.decompose_v29)
without knowing, per component, WHO owns the meeples (self vs opponent) and the
per-component quantities the terms consume (shields, cathedral, open_n, closure
delta, farm->finished/incomplete adjacent cities). A thin vector would make
Probe A false-crater for a REPRESENTATIONAL reason, not the mechanism under test.

The design target is: g_theta(component_i), summed over components (+ the meeple
economy pseudo-row), must be able to RECONSTRUCT every additive term of
`leaf_v29.decompose_v29()`:

  base            -> per city/road/farm: points-if-scored gated by self/opp
                     meeple majority. Cols: kind, tiles, shields, cathedral,
                     finished, farm_finished_cities, self/opp meeple weight.
  closure_self    -> per self-meepled INCOMPLETE city near closing:
                     closure_p[open_n]*delta. Cols: finished, open_n, delta,
                     self_meeples>0 (city); plus farm-growth via
                     farm_adj_incomplete_min_open_n / _sum_delta3.
  closure_opp     -> same, opp-meepled. Cols: opp_meeples>0.
  meeple_flat     -> meeple_k*(m_self - m_opp), a BOARD scalar (free meeples).
  v29 curve       -> curve[m_self] - curve[m_opp], a BOARD scalar.
                     => carried by the MEEPLE-ECONOMY pseudo-row (kind=3), whose
                        features are (self_free_meeples, opp_free_meeples). This
                        keeps the aggregate a pure sum over "components" while
                        letting g_theta learn the (nonlinear) curve differential.
  v28_meeple      -> recovery-scaled free-meeple term; needs deck_size -> also on
                     the meeple-economy pseudo-row (k_remaining feature).
  tactical_punish -> Candidate D: self-minus-opp imminent (open_n==1) high-value
                     city threats. Reconstructible from (open_n, delta, owner).
  farm_access     -> Candidate E: contested high-value field pressure.
                     Reconstructible from (farm self/opp weight, farm potential
                     = 3*n_adjacent_cities).

So the vector below carries, per REAL component, the closure/ownership/value
quantities; and one MEEPLE-ECONOMY pseudo-row per board carries the free-meeple
economy + deck context. The head aggregates by SUM (matched to virtual_score's
own aggregation), so v_leaf = sum_i g_theta(feat_i) is a drop-in leaf.

COLUMN LAYOUT (FEAT_DIM = 24)
------------------------------------------------------
All columns are float32. Integer-valued columns are asserted bit-exact against
the Cython emit; the two P(closure) columns (14,15) are floats compared to a
tight tolerance. Kinds: 0=city 1=road 2=farm 3=meeple-economy pseudo-row.

  0  is_city                1.0 for a city component, else 0.0
  1  is_road                1.0 for a road component, else 0.0
  2  is_farm                1.0 for a farm component, else 0.0
  3  is_meeple_econ         1.0 for the board's meeple-economy pseudo-row
  4  n_tiles                distinct tiles in the component (city/road: |coords|;
                            farm: 0; econ: 0). Feeds base points + city delta.
  5  n_shields              shields in a city component (0 for road/farm/econ).
                            Feeds base city points (4/tile+... doubled on shield).
  6  is_cathedral           1.0 if a city component carries a cathedral (inn flag
                            on a city tile). Feeds base (cathedral finished=3/tile,
                            unfinished=0) — a nonlinearity g_theta must see.
  7  finished               1.0 if the component is complete (city/road). Farms
                            are never "finished"; econ=0. Gates partial vs full
                            base credit AND the closure bonus (finished => no
                            closure bonus).
  8  open_n                 city: #distinct empty adjacent cells to close
                            (closure proximity). road/farm/econ: 0. With col 9,
                            reconstructs the closure schedule lookup.
  9  closure_delta          city: score swing if it closes (== decompose's
                            city_root_delta; count_city_points-if-closed minus
                            partial). road/farm/econ: 0. Feeds closure_self/opp
                            and Candidate D (imminent high-value threat).
  10 self_meeple_w          weighted meeple count of the ROOT player on this
                            component (city knights / road / farm farmers; big=2).
                            THE player-relative signal the 12-dim starter lacked.
                            Feeds base majority + closure (self-meepled?) + D/E.
  11 opp_meeple_w           weighted meeple count of the OPPONENT on this
                            component. Feeds base majority + closure_opp + D/E.
  12 farm_finished_cities   farm: #distinct FINISHED adjacent city components
                            (== decompose's farm_root_finished_cities). Feeds
                            base farm points (3 per finished adjacent city).
                            0 for city/road/econ.
  13 farm_potential3        farm: 3 * (#distinct adjacent city components, any
                            state) — the field's max value. Feeds Candidate E
                            (contested high-value field). 0 for city/road/econ.
  14 self_growth_p_sum      farm: Sum over the field's INCOMPLETE adjacent cities
                            of closure_p[city.open_n] (the farm-growth closure
                            schedule, per city, deduped by city root). Multiplied
                            by 3 in the bonus. This is the per-farm growth signal
                            g_theta needs WITHOUT re-walking the city graph.
                            FLOAT column. 0 for city/road/econ.
  15 self_city_close_p      city: closure_p[open_n] if incomplete & open_n in the
                            schedule, else 0.0 (== the P looked up for the city-
                            closure bonus). FLOAT column. Pairs with col 9 (delta)
                            so g_theta sees P*delta directly. 0 for road/farm/econ.
  16 econ_self_free         meeple-econ row: root player's FREE (unplaced) meeples
                            (state.meeples[root]). Feeds meeple_flat / curve /
                            v28_meeple. 0 for real components.
  17 econ_opp_free          meeple-econ row: opponent's free meeples. 0 else.
  18 econ_k_remaining       meeple-econ row: tiles still to draw (len(deck) [+1 in
                            TILES phase]); the recovery normalizer for v28_meeple.
                            0 for real components.
  19 self_is_cloister       1.0 if this is a CITY row that is actually a cloister-
                            carrier? NO — cloisters are not city components. See
                            note: cloister closure is handled via the meeple-econ
                            row's companion? Reserved 0.0 (documented below).
  20 cloister_needed        RESERVED for cloister closure (8 - surrounding). See
                            "CLOISTER HANDLING" below. 0.0 in v1 of the contract.
  21 cloister_self          RESERVED cloister ownership (root player has a meeple
                            on it). 0.0 in v1.
  22 cloister_opp           RESERVED cloister ownership (opp). 0.0 in v1.
  23 bias                   constant 1.0 (lets g_theta learn a per-kind offset;
                            cheap, standard for a per-component head).

CLOISTER HANDLING (columns 19-22 reserved, currently 0):
------------------------------------------------------
Cloisters (chapel/flowers) are NOT part of the city/road/farm union-find (the
Decomp has no cloister components). They contribute to `base` (surrounding-tile
count when meepled) and to the closure bonus (8 - n_surround). For MILESTONE 1
the contract RESERVES columns 19-22 for a future cloister pseudo-row but emits
0.0 there, because (a) the Cython C decomposition does not currently enumerate
cloisters as components (it handles them inline in the scoring pass), and (b)
cloisters are rare in 2p base+farmers and their omission does not change the
speed characterization. This is called out explicitly so milestone 2 knows the
head cannot yet reconstruct the cloister slice of base/closure. Adding a cloister
pseudo-row is a bounded follow-up (enumerate meepled cloister tiles + their
surrounding count) and does not change FEAT_DIM.

This module is a PYTHON REFERENCE (correctness ground truth). It reads straight
off `flat_leaf.decompose()` + `state.placed_meeples` — no extra board passes
beyond what the leaf already does. The Cython emit reproduces it bit-exactly from
the SAME C decomposition the scalar leaf computes (no second decompose).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from carcassonne_ai.flat_leaf import Decomp

FEAT_DIM = 24

# Column indices (keep in lockstep with the docstring and the Cython emit).
C_IS_CITY = 0
C_IS_ROAD = 1
C_IS_FARM = 2
C_IS_ECON = 3
C_N_TILES = 4
C_N_SHIELDS = 5
C_IS_CATHEDRAL = 6
C_FINISHED = 7
C_OPEN_N = 8
C_CLOSURE_DELTA = 9
C_SELF_MEEPLE_W = 10
C_OPP_MEEPLE_W = 11
C_FARM_FIN_CITIES = 12
C_FARM_POTENTIAL3 = 13
C_SELF_GROWTH_P_SUM = 14
C_SELF_CITY_CLOSE_P = 15
C_ECON_SELF_FREE = 16
C_ECON_OPP_FREE = 17
C_ECON_K_REMAINING = 18
C_CLOISTER_IS = 19
C_CLOISTER_NEEDED = 20
C_CLOISTER_SELF = 21
C_CLOISTER_OPP = 22
C_BIAS = 23

_FARMER_TYPES = (MeepleType.FARMER, MeepleType.BIG_FARMER)


def _default_closure_p():
    # Lazy import so the module has no import cycle with virtual_score_v2.
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    return DEFAULT_CONFIG.closure_p


def _k_remaining(state) -> int:
    """Tiles still to draw = deck + the drawn-but-unplaced tile (TILES phase).
    Matches step2_leaf._k_remaining exactly."""
    nt = getattr(state, "next_tile", None)
    extra = 1 if (nt is not None and state.phase == GamePhase.TILES) else 0
    return len(state.deck) + extra


def _meeple_ownership(state, d: "Decomp", root_player: int):
    """One pass over BOTH players' placed meeples -> weighted self/opp counts per
    component root, keyed by kind. Mirrors flat_leaf._final_scores' meeple->root
    routing (city_side_root / road_side_root / farm_pos0_root) and the weighting
    (big meeple = 2). Returns three dicts: city_own[root] = (self_w, opp_w), etc.
    Cloister meeples are ignored here (see CLOISTER HANDLING)."""
    opp = 1 - root_player
    board = state.board
    city_own: dict = {}
    road_own: dict = {}
    farm_own: dict = {}
    for pl in range(state.players):
        is_self = (pl == root_player)
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            tile = board[r][c]
            if tile is None:
                continue
            terr = tile.get_type(side)
            w = 2 if mp.meeple_type in (MeepleType.BIG, MeepleType.BIG_FARMER) else 1
            if terr == TerrainType.CITY:
                root = d.city_side_root.get((r, c, side))
                if root is not None:
                    e = city_own.get(root)
                    if e is None:
                        e = [0, 0]
                        city_own[root] = e
                    e[0 if is_self else 1] += w
            elif terr == TerrainType.ROAD:
                root = d.road_side_root.get((r, c, side))
                if root is not None:
                    e = road_own.get(root)
                    if e is None:
                        e = [0, 0]
                        road_own[root] = e
                    e[0 if is_self else 1] += w
            elif mp.meeple_type in _FARMER_TYPES:
                root = d.farm_pos0_root.get((r, c, side))
                if root is not None:
                    e = farm_own.get(root)
                    if e is None:
                        e = [0, 0]
                        farm_own[root] = e
                    e[0 if is_self else 1] += w
    return city_own, road_own, farm_own


def component_features(
    state: "CarcassonneGameState",
    decomp: "Decomp",
    root_player: int = 0,
    closure_p: dict | None = None,
) -> np.ndarray:
    """Canonical per-component feature matrix (n_comp, FEAT_DIM) float32.

    Row order (STABLE, must match the Cython emit):
      1. cities   in ascending root id
      2. roads    in ascending root id
      3. farms    in ascending root id
      4. one MEEPLE-ECONOMY pseudo-row (always last)

    `root_player` is the POV player whose meeples are "self". `closure_p` defaults
    to DEFAULT_CONFIG.closure_p; pass the leaf cfg's schedule to match a specific
    heuristic config (production v2.9 uses {1:0.5, 2:0.2, 3:0.05}).
    """
    if closure_p is None:
        closure_p = _default_closure_p()
    opp = 1 - root_player
    city_own, road_own, farm_own = _meeple_ownership(state, decomp, root_player)

    rows: list = []

    # ---- cities (ascending root id) ---------------------------------------- #
    for root in sorted(decomp.city_root_coords.keys()):
        coords = decomp.city_root_coords[root]
        n_tiles = float(len(coords))
        # shields + cathedral straight off the board (same tiles the leaf reads).
        shields = 0
        cathedral = 0.0
        for (r, c) in coords:
            tile = state.board[r][c]
            if tile.shield:
                shields += 1
            if tile.inn:
                cathedral = 1.0
        finished = 1.0 if decomp.city_root_finished.get(root, False) else 0.0
        open_n = decomp.city_root_open_n.get(root, 0)
        delta = float(decomp.city_root_delta.get(root, 0))
        sw, ow = city_own.get(root, (0, 0))
        # city-closure P: incomplete + open_n in the schedule.
        close_p = 0.0
        if not decomp.city_root_finished.get(root, False) and open_n > 0:
            close_p = float(closure_p.get(open_n, 0.0))
        row = [0.0] * FEAT_DIM
        row[C_IS_CITY] = 1.0
        row[C_N_TILES] = n_tiles
        row[C_N_SHIELDS] = float(shields)
        row[C_IS_CATHEDRAL] = cathedral
        row[C_FINISHED] = finished
        row[C_OPEN_N] = float(open_n)
        row[C_CLOSURE_DELTA] = delta
        row[C_SELF_MEEPLE_W] = float(sw)
        row[C_OPP_MEEPLE_W] = float(ow)
        row[C_SELF_CITY_CLOSE_P] = close_p
        row[C_BIAS] = 1.0
        rows.append(row)

    # ---- roads (ascending root id) ----------------------------------------- #
    for root in sorted(decomp.road_root_coords.keys()):
        coords = decomp.road_root_coords[root]
        finished = 1.0 if decomp.road_root_finished.get(root, False) else 0.0
        sw, ow = road_own.get(root, (0, 0))
        row = [0.0] * FEAT_DIM
        row[C_IS_ROAD] = 1.0
        row[C_N_TILES] = float(len(coords))
        row[C_FINISHED] = finished
        row[C_SELF_MEEPLE_W] = float(sw)
        row[C_OPP_MEEPLE_W] = float(ow)
        row[C_BIAS] = 1.0
        rows.append(row)

    # ---- farms (ascending root id) ----------------------------------------- #
    for root in sorted(decomp.farm_root_keys.keys()):
        adj_roots = decomp.farm_root_adj_city_roots.get(root, frozenset())
        fin_cities = float(decomp.farm_root_finished_cities.get(root, 0))
        potential3 = 3.0 * float(len(adj_roots))
        # farm-growth closure schedule: sum of closure_p[open_n] over INCOMPLETE
        # adjacent city components (deduped by city root == adj_roots already).
        growth_p_sum = 0.0
        for croot in adj_roots:
            if decomp.city_root_finished.get(croot, False):
                continue
            c_open_n = decomp.city_root_open_n.get(croot, 0)
            if c_open_n <= 0:
                continue
            growth_p_sum += float(closure_p.get(c_open_n, 0.0))
        sw, ow = farm_own.get(root, (0, 0))
        row = [0.0] * FEAT_DIM
        row[C_IS_FARM] = 1.0
        row[C_FARM_FIN_CITIES] = fin_cities
        row[C_FARM_POTENTIAL3] = potential3
        row[C_SELF_GROWTH_P_SUM] = growth_p_sum
        row[C_SELF_MEEPLE_W] = float(sw)
        row[C_OPP_MEEPLE_W] = float(ow)
        row[C_BIAS] = 1.0
        rows.append(row)

    # ---- meeple-economy pseudo-row (always last) --------------------------- #
    econ = [0.0] * FEAT_DIM
    econ[C_IS_ECON] = 1.0
    econ[C_ECON_SELF_FREE] = float(state.meeples[root_player])
    econ[C_ECON_OPP_FREE] = float(state.meeples[opp])
    econ[C_ECON_K_REMAINING] = float(_k_remaining(state))
    econ[C_BIAS] = 1.0
    rows.append(econ)

    return np.asarray(rows, dtype=np.float32)


# Columns compared bit-exactly (integer-valued) vs the two float P columns.
FLOAT_COLS = (C_SELF_GROWTH_P_SUM, C_SELF_CITY_CLOSE_P)
INT_COLS = tuple(i for i in range(FEAT_DIM) if i not in FLOAT_COLS)
