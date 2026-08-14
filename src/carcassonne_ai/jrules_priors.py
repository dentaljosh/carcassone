"""J-RULES AS POLICY PRIORS — surface B, the PYTHON REFERENCE MIRROR.

``measurement/jrules_priors_20260814/DESIGN.md`` is the design of record.

THE PRODUCTION PATH IS RUST (``carc_core::leaf::jrules_prior`` consumed by
``carc_core::search`` under ``SearchConfig.jrules_prior_dose != 0``). This
module is the independent re-derivation the parity gate compares against
(``carc_rs.MirrorState.jrules_prior_probe`` vs :func:`jrules_prior_term` here,
bit-for-bit): it exists so the Rust implementation is never the only rendering
of the encoding. It is NOT wired into the Python search — a
``HeuristicPriorConfig`` bound for ``backend="python"`` with a nonzero
``jrules_prior_dose`` raises, fail-loud (``heuristic_prior_mcts``), because a
silently prior-free candidate would read as "the strategy is worth nothing"
instead of "it never ran".

What this surface is (and is not):

* At node expansion, each legal child's Δleaf gets ``dose * T(child)`` added
  BEFORE the prior softmax — a multiplicative, renormalized boost of
  ``exp(dose·T/tau_p)`` on that child's prior. The leaf VALUES the search backs
  up are untouched on every path, and no ``LeafConfig`` field or leaf hash
  moves. ⚠️ A moved-leaf-hash wiring gate therefore CANNOT prove this term
  live; the gate is the RESOLVED ``jrules_prior_dose`` in the manifest.
* The rules run in the bot's ORIGINAL forms, which the static leaf surface
  (``flat_leaf.flat_jrules_term``) could not express: the "he must already be
  there" join predicates (J1 / J2-steal / J6-road-join), J2's deck-counted
  APPROACH/planning clause, J5's before/after throwaway dump, J8's
  margin-at-the-decision-node and still-enterable-farm gates. Each rule is
  evaluated for the MOVER only — a prior is neither backed up nor negated, so
  the antisymmetry contract that forced the static form's deviations does not
  bind here.
* The clock (k, late_frac, bag farm fraction, reserves, margin) is read ONCE
  from the decision node and reused for every candidate child — the bot's own
  fair-information rule (``joshua_bot.Clock``).

Constants are frozen copies of ``joshua_bot.PRESETS["current"]`` — pinned by
``tests/test_jrules_priors.py::test_constants_match_joshua_bot`` — plus the
``_JR_*`` block this module shares with the static bundle via ``flat_leaf``.
Reductions are ``math.fsum`` over push-ordered lists, mirroring the Rust
``compat::fsum`` discipline (both are exact, so iteration order can never
reach the value).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .flat_leaf import (  # the shared static-bundle substrate
    JR_J1,
    JR_J2,
    JR_J5,
    JR_J6,
    JR_J8,
    JR_ALL,
    _JR_J1_JOIN_BONUS,
    _JR_J1_LATE_EXTRA,
    _JR_J1_MIN_CITY_TILES,
    _JR_J1_MIN_OPEN_EDGES,
    _JR_J2_LOW_FARM_PENALTY,
    _JR_J2_MIN_FARM_VALUE,
    _JR_J2_STEAL_W,
    _JR_J6_ANCHOR_BONUS,
    _JR_J6_ANCHOR_CITY_MIN,
    _JR_J6_ANCHOR_ROAD_MIN,
    _JR_J6_ROAD_ANCHOR_ALLOWANCE,
    _JR_J6_ROAD_CLAIM_PENALTY,
    _JR_J6_ROAD_JOIN_BONUS,
    _JR_J6_ROAD_JOIN_MIN_LEN,
    _JR_J6_ROAD_SKEPTIC_MAX_LEN,
    _JR_J8_MAX_CITY_MEEPLES,
    _JR_J8_MAX_FARM_MEEPLES,
    _JR_J8_OVERCOMMIT_BONUS,
    _JR_J8_PIVOTAL_SWING,
    _JR_J8_VALUE_NORM,
    _jr_counts,
    _jr_farm_potential,
    _jr_late_frac,
    _jr_unclaimed_value,
    _jr_urgency,
    _k_remaining,
    decompose,
    flat_base_score,
)

__all__ = [
    "JrPriorClock",
    "jr_prior_clock",
    "jrules_prior_term",
    "bag_farm_fraction",
    "JP_J2_APPROACH_W",
    "JP_J2_PLAN_HORIZON",
    "JP_J2_REACH_THRESHOLD",
    "JP_J2_ENTRY_CELLS_CAP",
    "JP_J5_THROWAWAY_GAIN",
    "JP_J5_WEIGHT",
]

# --- the FROZEN `current`-preset parameters only this surface expresses ------
# (mirrors rust/carc/carc-core/src/leaf/jrules_prior.rs constant-for-constant;
# pinned against joshua_bot.JoshuaParams by the test suite)
JP_J2_APPROACH_W = 0.15
JP_J2_PLAN_HORIZON = 3
JP_J2_REACH_THRESHOLD = 0.50
JP_J2_ENTRY_CELLS_CAP = 3
JP_J5_THROWAWAY_GAIN = 1.0
JP_J5_WEIGHT = 0.5


def bag_farm_fraction(state) -> float:
    """``joshua_bot.bag_farm_fraction``: fraction of the UNDRAWN deck carrying a
    field segment. ``next_tile`` deliberately excluded, as the bot excludes it.
    Order-free (a count over the multiset)."""
    deck = state.deck
    n = len(deck)
    if n == 0:
        return 0.0
    ok = 0
    for tile in deck:
        if tile.farms:
            ok += 1
    return ok / n


@dataclass(frozen=True)
class JrPriorClock:
    """``joshua_bot.Clock`` — the decision node's clock + bag, read ONCE per
    expansion from the PARENT and reused for every candidate child."""

    k: int
    late_frac: float
    bag_farm_frac: float
    urg: float
    opp_reserve: int
    parent_base: float
    abs_margin: float
    parent_unclaimed: float


def jr_prior_clock(parent_state, mover: int, decomp=None) -> JrPriorClock:
    """Build the clock from the decision node (``decomp`` must be the PARENT's
    decomposition when supplied; ``None`` decomposes here)."""
    if decomp is None:
        decomp = decompose(parent_state)
    opp = 1 - mover
    k = _k_remaining(parent_state)
    city_counts, road_counts, _farm_counts, cloister_owned = _jr_counts(parent_state, decomp)
    parent_base = float(flat_base_score(parent_state, mover, decomp))
    parent_unclaimed = _jr_unclaimed_value(
        parent_state, decomp, city_counts, road_counts, cloister_owned)
    return JrPriorClock(
        k=k,
        late_frac=_jr_late_frac(k),
        bag_farm_frac=bag_farm_fraction(parent_state),
        urg=_jr_urgency(parent_state.meeples[opp]),
        opp_reserve=parent_state.meeples[opp],
        parent_base=parent_base,
        abs_margin=abs(parent_base),
        parent_unclaimed=parent_unclaimed,
    )


def _jp_farm_entry_cells(state, decomp, root) -> int:
    """``joshua_bot.Position.farm_entry_cells`` — distinct EMPTY board cells
    orthogonally adjacent to the field."""
    board = state.board
    h = len(board)
    w = len(board[0]) if h else 0
    cells = {(r, c) for (r, c, _fc) in decomp.farm_root_keys.get(root, ())}
    entries = set()
    for (r, c) in cells:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and board[nr][nc] is None:
                entries.add((nr, nc))
    return len(entries)


def _jp_j2_reach(state, decomp, root, clock: JrPriorClock) -> float:
    """``joshua_bot.j2_reach`` — the deck-counted "can I still get in" model.
    ``1 - (1 - per_turn) ** h``; permissive by construction."""
    my_turns = clock.k // 2
    if my_turns < 1:
        return 0.0
    cells = _jp_farm_entry_cells(state, decomp, root)
    if cells == 0:
        return 0.0
    h = min(JP_J2_PLAN_HORIZON, my_turns)
    if h < 1:
        return 0.0
    cap = max(JP_J2_ENTRY_CELLS_CAP, 1)
    per_turn = clock.bag_farm_frac * min(cells, cap) / cap
    if per_turn > 1.0:
        per_turn = 1.0
    return 1.0 - (1.0 - per_turn) ** h


def _jp_j1(decomp, city_counts, me: int, clock: JrPriorClock) -> float:
    """The bot's ORIGINAL ``j1_majority_steal`` — a JOIN into HIS large open
    city (``cnt[me] >= 1 AND cnt[opp] >= 1 AND cnt[me] >= cnt[opp]``; the
    predicate the static surface had to drop)."""
    opp = 1 - me
    contribs: list = []
    bonus = _JR_J1_JOIN_BONUS * (1.0 + _JR_J1_LATE_EXTRA * clock.late_frac) * clock.urg
    for root, cnt in city_counts.items():
        if decomp.city_root_finished[root]:
            continue
        if cnt[me] < 1 or cnt[opp] < 1:
            continue                               # not a JOIN into his city
        if cnt[me] < cnt[opp]:
            continue                               # not a tie/majority
        if len(decomp.city_root_coords[root]) < _JR_J1_MIN_CITY_TILES:
            continue
        if decomp.city_root_open_n[root] < _JR_J1_MIN_OPEN_EDGES:
            continue
        contribs.append(bonus)
    return math.fsum(contribs)


def _jp_j2(state, decomp, farm_counts, me: int, clock: JrPriorClock) -> float:
    """The bot's ORIGINAL ``j2_farm_attack``, all three pieces: REALIZED steal
    (restored ``his >= 1``), the SURRENDER charge, and the APPROACH loop (J2a,
    the planning clause the static surface disclosed as inexpressible)."""
    opp = 1 - me
    contribs: list = []
    for root, cnt in farm_counts.items():
        pot = _jr_farm_potential(decomp, root, clock.k)
        value = 3.0 * decomp.farm_root_finished_cities.get(root, 0) + pot
        mine, his = cnt[me], cnt[opp]
        if mine >= 1 and his >= 1 and mine >= his:
            if value >= _JR_J2_MIN_FARM_VALUE:
                contribs.append(_JR_J2_STEAL_W * pot * clock.urg)
        if mine >= 1 and value < _JR_J2_MIN_FARM_VALUE:
            contribs.append(-_JR_J2_LOW_FARM_PENALTY * mine)
    for root, cnt in farm_counts.items():
        if cnt[me] >= 1 or cnt[opp] < 1:
            continue
        value = (3.0 * decomp.farm_root_finished_cities.get(root, 0)
                 + _jr_farm_potential(decomp, root, clock.k))
        if value < _JR_J2_MIN_FARM_VALUE:
            continue
        reach = _jp_j2_reach(state, decomp, root, clock)
        if reach < JP_J2_REACH_THRESHOLD:
            continue
        contribs.append(JP_J2_APPROACH_W * value * reach * clock.urg)
    return math.fsum(contribs)


def _jp_j5(state, decomp, city_counts, road_counts, cloister_owned,
           clock: JrPriorClock, child_base: float) -> float:
    """The bot's ORIGINAL before/after ``j5_dump`` — needs the parent
    ("before"), which only this surface has."""
    if clock.opp_reserve <= 0:
        return 0.0
    if child_base - clock.parent_base > JP_J5_THROWAWAY_GAIN:
        return 0.0                                 # not a throwaway: take the points
    fed = _jr_unclaimed_value(state, decomp, city_counts, road_counts,
                              cloister_owned) - clock.parent_unclaimed
    if fed <= 0.0:
        return 0.0
    return -JP_J5_WEIGHT * fed * clock.urg


def _jp_j6(decomp, city_counts, road_counts, me: int, clock: JrPriorClock) -> float:
    """The bot's ORIGINAL ``j6_anchor_and_roads``: anchors + road skepticism +
    the road JOIN with its restored ``cnt[opp] >= 1``."""
    opp = 1 - me
    contribs: list = []
    has_city_anchor = False
    for root, cnt in city_counts.items():
        if decomp.city_root_finished[root] or cnt[me] <= cnt[opp]:
            continue
        if len(decomp.city_root_coords[root]) >= _JR_J6_ANCHOR_CITY_MIN:
            has_city_anchor = True
            break
    has_road_anchor = False
    n_short_solo = 0
    for root, cnt in road_counts.items():
        if decomp.road_root_finished[root]:
            continue
        length = len(decomp.road_root_coords[root])
        if (cnt[me] >= 1 and cnt[opp] >= 1 and cnt[me] >= cnt[opp]
                and length >= _JR_J6_ROAD_JOIN_MIN_LEN):
            contribs.append(_JR_J6_ROAD_JOIN_BONUS * clock.urg)      # (b) JOIN
        if cnt[me] > cnt[opp]:
            if length >= _JR_J6_ANCHOR_ROAD_MIN:
                has_road_anchor = True
            if cnt[opp] == 0 and length <= _JR_J6_ROAD_SKEPTIC_MAX_LEN:
                n_short_solo += 1
    contribs.append(
        _JR_J6_ANCHOR_BONUS * (int(has_city_anchor) + int(has_road_anchor)))  # (a)
    excess = n_short_solo - _JR_J6_ROAD_ANCHOR_ALLOWANCE
    if excess < 0:
        excess = 0
    contribs.append(-_JR_J6_ROAD_CLAIM_PENALTY * excess)                      # (c)
    return math.fsum(contribs)


def _jp_j8(state, decomp, city_counts, farm_counts, me: int,
           clock: JrPriorClock) -> float:
    """The bot's ORIGINAL ``j8_overcommit`` — margin at the DECISION NODE,
    still-enterable-farm gate (both restored vs the static surface)."""
    opp = 1 - me
    contribs: list = []
    for root, cnt in city_counts.items():
        if decomp.city_root_finished[root]:
            continue
        if decomp.city_root_open_n[root] < 1:
            continue                               # he can no longer get in
        value = float(decomp.city_root_delta[root])
        swing = 2.0 * value
        if swing < _JR_J8_PIVOTAL_SWING or swing < clock.abs_margin:
            continue
        if cnt[me] - cnt[opp] < 2 or cnt[me] > _JR_J8_MAX_CITY_MEEPLES:
            continue
        v = value / _JR_J8_VALUE_NORM
        if v > 1.0:
            v = 1.0
        contribs.append(_JR_J8_OVERCOMMIT_BONUS * v * clock.urg)
    for root, cnt in farm_counts.items():
        if _jp_farm_entry_cells(state, decomp, root) < 1:
            continue                               # no longer enterable
        value = (3.0 * decomp.farm_root_finished_cities.get(root, 0)
                 + _jr_farm_potential(decomp, root, clock.k))
        swing = 2.0 * value
        if swing < _JR_J8_PIVOTAL_SWING or swing < clock.abs_margin:
            continue
        if cnt[me] - cnt[opp] < 2 or cnt[me] > _JR_J8_MAX_FARM_MEEPLES:
            continue
        v = value / _JR_J8_VALUE_NORM
        if v > 1.0:
            v = 1.0
        contribs.append(_JR_J8_OVERCOMMIT_BONUS * v * clock.urg)
    return math.fsum(contribs)


def jrules_prior_term(child_state, mover: int, decomp, mask: int,
                      clock: JrPriorClock, child_base: float) -> float:
    """The J-rules PRIOR term for one candidate child — mover's own side only,
    original predicates, clock from the decision node. The search adds
    ``dose * T`` to the child's Δleaf BEFORE the prior softmax; nothing the
    search backs up moves.

    ``decomp`` is the CHILD afterstate's decomposition; ``child_base`` is
    ``flat_base_score(child_state, mover)``. Mask bits are the static bundle's
    ``JR_J1 .. JR_J8`` (default ``JR_ALL`` == 31); J2's APPROACH clause rides
    inside ``JR_J2``, as it does in the bot. Parts are pushed in the fixed
    order J1, J2, J5, J6, J8 and fsum-reduced."""
    city_counts, road_counts, farm_counts, cloister_owned = _jr_counts(child_state, decomp)
    parts: list = []
    if mask & JR_J1:
        parts.append(_jp_j1(decomp, city_counts, mover, clock))
    if mask & JR_J2:
        parts.append(_jp_j2(child_state, decomp, farm_counts, mover, clock))
    if mask & JR_J5:
        parts.append(_jp_j5(child_state, decomp, city_counts, road_counts,
                            cloister_owned, clock, child_base))
    if mask & JR_J6:
        parts.append(_jp_j6(decomp, city_counts, road_counts, mover, clock))
    if mask & JR_J8:
        parts.append(_jp_j8(child_state, decomp, city_counts, farm_counts,
                            mover, clock))
    return math.fsum(parts)


# Explicit re-export so callers never need flat_leaf for the mask arithmetic.
JR_PRIOR_MASK_ALL = JR_ALL
_ = (JR_J1, JR_J2, JR_J5, JR_J6, JR_J8)  # keep the imports load-bearing
