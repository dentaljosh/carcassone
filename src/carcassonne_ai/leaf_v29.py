"""leaf_v29 — opt-in, individually-ablatable v2.9 evaluator candidates.

Built on top of the FROZEN v2.7 / v2.8 leaf (`virtual_score_v2`). Every term here
is gated by a `LeafConfig.v29_*` field that defaults to neutral, so when none is set
`_v29_active(cfg)` is False, this module is never called, and the leaf is
byte-identical to production v2.8. None of these terms touch `flat_leaf.py`
(the v2.9 configs force the engine/object path, same pattern as the `v28_*` knobs).

Design goals (V29 spec, 2026-06-25):
  - Each candidate is one toggle, ablatable in isolation.
  - `decompose_v29` returns EVERY component separately so an audit can see which
    term moved a decision.
  - Point margin is a diagnostic; winrate is the throne. These terms are judged by
    paired full-game winrate vs h6400_v2.8, not by margin or trap-score.

Candidates (see V29_CANDIDATE_TERMS.md):
  A  v29_util_tanh_t   — win-shaped utility: total -> T*tanh(total/T) (point-scale).
  B  v29_meeple_curve  — nonlinear meeple liquidity: value-by-free-count table,
                         REPLACES the flat meeple_k term.
  D  v29_punish_k      — sparse high-confidence tactical-punish swing (STUB, see note).
  E  v29_farm_access_k — farm access / denial window (STUB, low prior — see code map §5).

Pre-killed (NOT implemented here, do not re-run): deck-aware completion probability
(Candidate C) is a confirmed null (DECISIONS 2026-05-17, re-confirmed 2026-06-22);
the existing `closure_continuous_slack` knob already covers it.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .virtual_score_v2 import LeafConfig


# ---------------------------------------------------------------------------
# Candidate A — win-shaped utility transform
# ---------------------------------------------------------------------------
def _util_transform(score: float, t: float) -> float:
    """T*tanh(score/T): preserves point-scale for |score| << T (≈ identity),
    smoothly caps magnitude at ±T for big leads. Composed downstream with the
    consumer's tanh(./15): HeuristicMCTS value = tanh(T*tanh(diff/T)/15).
    Smaller T = stronger anti-padding / more binary; larger T -> baseline."""
    if t <= 0.0:
        return score
    return t * math.tanh(score / t)


# ---------------------------------------------------------------------------
# Candidate B — nonlinear meeple liquidity curve
# ---------------------------------------------------------------------------
def _curve_lookup(curve, n: int) -> float:
    """Value of holding `n` free meeples, from a table indexed by count.
    Clamps n into [0, len-1] (free-meeple count is 0..7 in base+farmers)."""
    if n < 0:
        n = 0
    elif n >= len(curve):
        n = len(curve) - 1
    return float(curve[n])


def _meeple_curve_term(state, player: int, opp: int, curve) -> float:
    """Symmetric differential of the liquidity curve. REPLACES the flat
    meeple_k*(m_self - m_opp) term (the caller omits the flat term when a curve
    is set). `state.meeples[i]` = free/unplaced meeples (start 7)."""
    return _curve_lookup(curve, state.meeples[player]) - _curve_lookup(curve, state.meeples[opp])


# ---------------------------------------------------------------------------
# Candidate D — sparse high-confidence tactical punish / must-block
# ---------------------------------------------------------------------------
# Thresholds: a feature is a "tactical" target only if it's IMMINENT (open_n==1, the
# high-confidence half of the closure schedule) AND HIGH-VALUE (closure delta >= this).
# Sparse by construction — fires on a handful of positions, not generically.
V_PUNISH = 8.0

# Caveat carried from the code map / strategic-ladder finding: this is a LEAF-state
# term, and "complete my own feature / claim an exposed farm" is already in `base`. The
# only genuinely-additive signal a leaf can carry is that the CAPPED linear closure
# bonus UNDER-weights a single big imminent threat — so D emphasizes exactly those.
# The 2026-06-25 evidence says the real punish gap is in SEARCH/POLICY; we screen D
# anyway (user request) and expect the data to kill it. Examples inspected before the
# aggregate (spec Part B) — see HIGH_PRECISION_EXAMPLES discipline.


def _imminent_high_value(state, p: int) -> float:
    """Σ closure-delta over p's meepled INCOMPLETE cities that are ONE tile from
    closing (open_n==1) AND worth >= V_PUNISH points. The sparse set of completions a
    strong player fights over. Deduped by city content. Cloisters never qualify (a
    1-away cloister is worth only 1pt). Roads have no closure delta in this leaf."""
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    from wingedsheep.carcassonne.utils.city_util import CityUtil
    from .virtual_score_v2 import _city_closure_delta, _open_city_positions

    total = 0.0
    seen: set = set()
    for mp in state.placed_meeples[p]:
        cs = mp.coordinate_with_side
        coord = cs.coordinate
        tile = state.board[coord.row][coord.column]
        if tile is None or tile.get_type(cs.side) != TerrainType.CITY:
            continue
        city = CityUtil.find_city(game_state=state, city_position=cs)
        key = frozenset(city.city_positions)
        if key in seen or city.finished:
            continue
        seen.add(key)
        if _open_city_positions(state, city) != 1:
            continue
        d = _city_closure_delta(state, city)
        if d >= V_PUNISH:
            total += d
    return total


def _punish_signal(state, player: int, opp: int, cfg: "LeafConfig") -> float:
    """Differential of sparse imminent high-value city threats (mine minus theirs).
    Positive => I have more big near-complete cities (press); negative => the opponent
    does (must-block). Multiplied by cfg.v29_punish_k in apply_v29."""
    return _imminent_high_value(state, player) - _imminent_high_value(state, opp)


# ---------------------------------------------------------------------------
# Candidate E — contested high-value farm pressure (low prior)
# ---------------------------------------------------------------------------
V_FARM = 9.0  # a field counts as high-value at >= this potential (3pts per adjacent city)

# Low prior: farm-majority-gate (broad degradation) and opp-denial (no movement) were
# both KILLED in the 2026-06-22 v2.8 program. This is a different angle — directional
# pressure on CONTESTED high-value fields (both players hold farmers, the outcome can
# still flip) — but starts from a very negative base. Screened on user request.


def _contested_field_pressure(state, player: int, opp: int) -> float:
    """For high-value CONTESTED fields (both players have farmers, potential >= V_FARM):
    +potential if `player` leads the field, -potential if behind, 0 if tied. Values
    WINNING the contest for a big field, beyond `base` (which scores the current
    majority as if final). Potential = 3 * distinct adjacent cities (any state)."""
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.utils.city_util import CityUtil
    from wingedsheep.carcassonne.utils.farm_util import FarmUtil

    fields: dict = {}  # field_key -> [count_p0, count_p1, potential]
    for pl in (0, 1):
        for mp in state.placed_meeples[pl]:
            if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                continue
            farm = FarmUtil.find_farm_by_coordinate(game_state=state, position=mp.coordinate_with_side)
            key = frozenset(farm.farmer_connections_with_coordinate)
            ent = fields.get(key)
            if ent is None:
                pot, seen_cities = 0, set()
                for fc in farm.farmer_connections_with_coordinate:
                    for city in CityUtil.find_cities(game_state=state, coordinate=fc.coordinate,
                                                     sides=fc.farmer_connection.city_sides):
                        ck = frozenset(city.city_positions)
                        if ck not in seen_cities:
                            seen_cities.add(ck)
                            pot += 3
                ent = [0, 0, pot]
                fields[key] = ent
            ent[pl] += 2 if mp.meeple_type == MeepleType.BIG_FARMER else 1

    total = 0.0
    for c0, c1, pot in fields.values():
        if pot < V_FARM:
            continue
        cp, co = (c0, c1) if player == 0 else (c1, c0)
        if cp > 0 and co > 0:  # contested
            if cp > co:
                total += pot
            elif co > cp:
                total -= pot
    return total


def _farm_access_signal(state, player: int, opp: int, cfg: "LeafConfig") -> float:
    """Contested-high-value-field pressure, multiplied by cfg.v29_farm_access_k in
    apply_v29."""
    return _contested_field_pressure(state, player, opp)


# ---------------------------------------------------------------------------
# C7 wave-2 — Term R (meeple-return liquidity) + Term F (farm majority-flip)
# ---------------------------------------------------------------------------
# Object-path reference implementations (CityUtil/RoadUtil/FarmUtil + the engine
# base-scoring calls). Bit-exact to flat_leaf.flat_return_term / flat_farm_flip_term
# under fsum (the reconcile + object-vs-flat gates are the arbiter). Pre-registered
# module constants (NOT LeafConfig fields — like V_PUNISH); mirror flat_leaf's.
FLIP_BETA = 0.5
FLIP_RAMP = 2.0


def _dcurve(curve, n: int) -> float:
    """Marginal curve value of recovering ONE meeple at free count `n`:
    ``curve[min(n+1, L-1)] - curve[min(max(n,0), L-1)]`` (0 at n == L-1). ==
    flat_leaf._flat_dcurve / the cy _dcurve_c."""
    L = len(curve)
    hi = n + 1
    if hi > L - 1:
        hi = L - 1
    lo = n
    if lo < 0:
        lo = 0
    if lo > L - 1:
        lo = L - 1
    return float(curve[hi]) - float(curve[lo])


def _return_liquidity(state, player: int, cfg: "LeafConfig") -> float:
    """Term R per-player ``ret(p) = dcurve(free) * ΣP(feature closes)`` (§1). PER
    MEEPLE (no dedup); city/road/cloister meeples on incomplete features credit the
    closure-schedule P; farmers never return (skip). Requires a curve. The caller in
    apply_v29 forms the differential ``ret(player) - ret(opp)``."""
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    from wingedsheep.carcassonne.utils.city_util import CityUtil
    from wingedsheep.carcassonne.utils.road_util import RoadUtil
    from .virtual_score_v2 import (
        _open_city_positions,
        _open_road_positions,
        _surrounding_count,
    )

    curve = cfg.v29_meeple_curve
    if curve is None:
        raise ValueError(
            "v29_meeple_return_k requires v29_meeple_curve (Term R prices the "
            "marginal step of the liquidity curve)"
        )
    closure_p = cfg.closure_p
    plist: list = []
    for mp in state.placed_meeples[player]:
        coord_side = mp.coordinate_with_side
        coord = coord_side.coordinate
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        terrain = tile.get_type(coord_side.side)
        if terrain == TerrainType.CITY:
            city = CityUtil.find_city(game_state=state, city_position=coord_side)
            if city.finished:
                continue
            open_n = _open_city_positions(state, city)
            if open_n <= 0:
                continue
            p = closure_p.get(open_n, 0.0)
            if p > 0:
                plist.append(p)
        elif terrain == TerrainType.ROAD:
            road = RoadUtil.find_road(game_state=state, road_position=coord_side)
            if road.finished:
                continue
            open_n = _open_road_positions(state, road)
            if open_n <= 0:
                continue
            p = closure_p.get(open_n, 0.0)
            if p > 0:
                plist.append(p)
        elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
            n_surround = _surrounding_count(state, coord)
            needed = 8 - n_surround
            if needed <= 0:
                continue
            p = closure_p.get(needed, 0.0)
            if p > 0:
                plist.append(p)
        # FARMER / BIG_FARMER: terrain is not city/road/cloister -> skip (never returns)
    return _dcurve(curve, state.meeples[player]) * math.fsum(plist)


def _farm_flip_term(state, player: int, opp: int, cfg: "LeafConfig") -> float:
    """Term F player-POV antisymmetric fsum of per-contested-field contributions (§2).
    Field membership + weights use the ENGINE base-scoring path (find_farm_by_coordinate
    region + find_meeples pos0 counts + count_farm_points) so it sees exactly what base
    awards. Smooths base's hard sign(margin)·V step by weighted margin + free-meeple
    liquidity; contested fields only."""
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.utils.farm_util import FarmUtil
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    fields: dict = {}  # region key -> (counts[c0,c1], V)
    for pl in (0, 1):
        for mp in state.placed_meeples[pl]:
            if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                continue
            farm = FarmUtil.find_farm_by_coordinate(
                game_state=state, position=mp.coordinate_with_side
            )
            key = frozenset(farm.farmer_connections_with_coordinate)
            if key in fields:
                continue
            meeples = FarmUtil.find_meeples(game_state=state, farm=farm)
            counts = PointsCollector.get_meeple_counts_per_player(meeples)
            V = float(PointsCollector.count_farm_points(game_state=state, farm=farm))
            fields[key] = (counts, V)

    free_d = state.meeples[player] - state.meeples[opp]
    if free_d > 1:
        free_d = 1
    elif free_d < -1:
        free_d = -1
    contribs: list = []
    for counts, V in fields.values():
        w_me = counts[player]
        w_opp = counts[opp]
        if w_me >= 1 and w_opp >= 1:  # contested only
            m = w_me - w_opp
            step = 1.0 if m > 0 else (-1.0 if m < 0 else 0.0)
            m_eff = m + FLIP_BETA * free_d
            ramp = m_eff / FLIP_RAMP
            if ramp > 1.0:
                ramp = 1.0
            elif ramp < -1.0:
                ramp = -1.0
            contribs.append(V * (ramp - step))
    return math.fsum(contribs)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def apply_v29(state, player: int, opp: int, cfg: "LeafConfig", score: float) -> float:
    """Add the active v2.9 terms to the (base + closure ± + flat-meeple-if-no-curve)
    score, then apply the win-shaping transform LAST (on the full total).

    Called from `virtual_score_v2` only when `_v29_active(cfg)`. The caller has
    already omitted the flat meeple_k term iff a curve is set."""
    if cfg.v29_meeple_curve is not None:          # B (replaces flat meeple)
        score += _meeple_curve_term(state, player, opp, cfg.v29_meeple_curve)
    # C7 Term R then Term F — two SEPARATE gated adds in this fixed order (float add
    # is non-associative; matches the flat/cy sites exactly for 3-way bit-exactness).
    if cfg.v29_meeple_return_k != 0.0:            # R (meeple-return liquidity)
        score += cfg.v29_meeple_return_k * (
            _return_liquidity(state, player, cfg) - _return_liquidity(state, opp, cfg)
        )
    if cfg.v29_farm_flip_k != 0.0:                # F (farm majority-flip)
        score += cfg.v29_farm_flip_k * _farm_flip_term(state, player, opp, cfg)
    if cfg.v29_punish_k != 0.0:                   # D (stub)
        score += cfg.v29_punish_k * _punish_signal(state, player, opp, cfg)
    if cfg.v29_farm_access_k != 0.0:              # E (stub)
        score += cfg.v29_farm_access_k * _farm_access_signal(state, player, opp, cfg)
    if cfg.v29_util_tanh_t > 0.0:                 # A (last, on full total)
        score = _util_transform(score, cfg.v29_util_tanh_t)
    return score


def decompose_v29(state, player: int, cfg: "LeafConfig") -> dict:
    """Return every leaf component separately for the v2.9 audit ("which term moved
    the decision"). Recomputes each piece independently — slower than the production
    path, diagnostic-only. Sum of additive components + utility_transform_delta ==
    pre-round total; `total_int` == what `virtual_score_v2(state, player, cfg)` returns.

    Keys:
      base                  v1 end-of-game score differential
      closure_self          capped self closure-anticipation bonus
      closure_opp           capped opp closure-anticipation bonus  (subtracted)
      meeple_flat           v2.8 flat meeple term meeple_k*(m_self-m_opp) (reference)
      meeple_curve_delta    (curve term - meeple_flat) when a curve is set, else 0
      deck_completion_delta 0.0 (Candidate C pre-killed — not a v2.9 term)
      tactical_punish_delta D term (0.0 stub)
      threat_block_delta    alias of the block half of D (0.0 stub; kept for the spec schema)
      farm_access_delta     E term (0.0 stub)
      phase_scaling_delta   0.0 (no phase-scaling candidate active)
      pretransform_total    base+closure_self-closure_opp+meeple+deltas (before A)
      utility_transform_delta  A: T*tanh(pretransform/T) - pretransform (0 if A off)
      total                 pretransform_total + utility_transform_delta (float)
      total_int             int(round(total)) == virtual_score_v2 output
    """
    from .virtual_score import virtual_score
    from .virtual_score_v2 import _closure_anticipation_bonus, _soft_capped

    opp = 1 - player
    base = float(virtual_score(state, player))
    # F6 soft cap: slope 0.0 (default) delegates to the hard clamp -> bit-identical.
    closure_self = _soft_capped(_closure_anticipation_bonus(state, player, cfg),
                                cfg.bonus_cap, getattr(cfg, "soft_cap_slope", 0.0))
    closure_opp = _soft_capped(_closure_anticipation_bonus(state, opp, cfg),
                               cfg.opp_bonus_cap, getattr(cfg, "opp_soft_cap_slope", 0.0))

    # meeple: flat reference always computed; curve delta only when a curve is set.
    m_self, m_opp = state.meeples[player], state.meeples[opp]
    meeple_flat = cfg.meeple_k * (m_self - m_opp) if cfg.meeple_k > 0.0 else 0.0
    if cfg.v29_meeple_curve is not None:
        curve_term = _meeple_curve_term(state, player, opp, cfg.v29_meeple_curve)
        meeple_curve_delta = curve_term - meeple_flat
        meeple_contribution = curve_term
    else:
        meeple_curve_delta = 0.0
        meeple_contribution = meeple_flat

    # v28 recovery-scaled meeple (independent of legacy meeple_k); included so the
    # decomposition total matches virtual_score_v2 for v28-active cfgs too.
    v28_meeple = 0.0
    if cfg.v28_meeple_k != 0.0:
        rf = 1.0
        if cfg.v28_meeple_recovery_t0 > 0:
            rf = min(1.0, len(state.deck) / cfg.v28_meeple_recovery_t0)
        v28_meeple = cfg.v28_meeple_k * (m_self - m_opp) * rf

    # C7 Term R / Term F deltas (added in apply_v29 between the curve and punish
    # blocks — mirror that order here so pretransform matches production).
    meeple_return_delta = cfg.v29_meeple_return_k * (
        _return_liquidity(state, player, cfg) - _return_liquidity(state, opp, cfg)
    ) if cfg.v29_meeple_return_k != 0.0 else 0.0
    farm_flip_delta = cfg.v29_farm_flip_k * _farm_flip_term(state, player, opp, cfg) \
        if cfg.v29_farm_flip_k != 0.0 else 0.0

    tactical_punish_delta = cfg.v29_punish_k * _punish_signal(state, player, opp, cfg) \
        if cfg.v29_punish_k != 0.0 else 0.0
    farm_access_delta = cfg.v29_farm_access_k * _farm_access_signal(state, player, opp, cfg) \
        if cfg.v29_farm_access_k != 0.0 else 0.0

    pretransform = (base + closure_self - closure_opp + meeple_contribution + v28_meeple
                    + meeple_return_delta + farm_flip_delta
                    + tactical_punish_delta + farm_access_delta)
    if cfg.v29_util_tanh_t > 0.0:
        total = _util_transform(pretransform, cfg.v29_util_tanh_t)
    else:
        total = pretransform
    utility_transform_delta = total - pretransform

    return {
        "base": base,
        "closure_self": closure_self,
        "closure_opp": closure_opp,
        "meeple_flat": meeple_flat,
        "meeple_curve_delta": meeple_curve_delta,
        "v28_meeple": v28_meeple,
        "meeple_return_delta": meeple_return_delta,
        "farm_flip_delta": farm_flip_delta,
        "deck_completion_delta": 0.0,
        "tactical_punish_delta": tactical_punish_delta,
        "threat_block_delta": 0.0,
        "farm_access_delta": farm_access_delta,
        "phase_scaling_delta": 0.0,
        "pretransform_total": pretransform,
        "utility_transform_delta": utility_transform_delta,
        "total": total,
        "total_int": int(round(total)),
    }
