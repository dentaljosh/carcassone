#!/usr/bin/env python3
"""Leaf residual-mining — the PRE-REGISTERED feature dictionary.

This module computes, for one root board, the fixed dictionary of cheap
board-derived features that the residual

    resid = V_deep(root)  -  V_leaf(root)

is regressed against.  Every feature here is FIXED IN ADVANCE by
``measurement/leaf_residual_mining_20260721/PREREG.md`` (§3) — this module and
that document must agree name-for-name; the harness asserts the name set.

COST TIER (does the feature fit inside a leaf that runs millions of times?)
The calibration is C7's, measured: the Cython leaf is ~27.5 us/call and 27.4% of a
search (CYTHON_LEAF_REPORT.md); C7 Term R's ONE EXTRA pass over both players'
placed meeples cost 1.204x median per leaf — OVER the pre-registered <=1.10 cost
gate — while Term F's farmer-only pass cost ~1.01-1.02x.  So "one more meeple
pass" is NOT free; REUSING an existing pass is.
  A  = FREE.  Accumulable inside a pass the champion leaf ALREADY makes — the
       ``flat_closure_bonus`` loop over ``state.placed_meeples[p]`` (run for BOTH
       players, already doing terrain lookups, root lookups, ``open_n``,
       ``city_root_delta`` and ``_surrounding_count``), the ``_final_scores``
       meeple pass, or a direct read of ``decompose``/``state`` scalars.
       ROAD meeples currently fall through that loop's if/elif chain unused —
       a road accumulator there is ~free.
  B  = CHEAP-ISH but a real add: needs a NEW scan (e.g. the deck).  Must pass
       C7's Stage-0 <=1.10x per-leaf cost gate before it can ship.
  C  = NOT LEAF-VIABLE.  Needs legal-move generation or a fresh board traversal.
       Recorded as a DIAGNOSTIC only: a C-tier hit cannot become a leaf term.

PRIOR ART (why the prior probability of a hit is low — see PREREG.md §7):
  * CL-034 — a learned comparator over ~50 handcrafted ``decompose`` scalars BEAT
    the leaf OFFLINE (sibling-regret -41%) and WASHED OUT under search.
  * CL-036 — a typed feature-GNN on the POST-SEARCH residual was INERT.
  * CL-055 (C7) — "the leaf's remaining headroom is NOT in cheap adjacent terms."
  * V27_FAILURE_TAXONOMY — ~67% of the leaf's disagreements with stronger
    references are structural/horizon, i.e. NOT leaf-addressable.
Every candidate below is either (a) never isolated before, or (b) included as an
explicit confirmatory re-read of a killed family in a DIFFERENT functional form,
labelled as such.  No candidate re-proposes a dead term at its dead dose.

Sign convention: every ``*_diff`` feature is MOVER-POV (player minus opponent),
matching the leaf's own convention, so a positive feature means "good for the
player to move".
"""
from __future__ import annotations

import hashlib
import math

from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

from carcassonne_ai import flat_leaf

# --------------------------------------------------------------------------- #
# The pre-registered dictionary.  (name, tier, one-line hypothesis)            #
# --------------------------------------------------------------------------- #
CONTROLS = (
    "v_leaf",            # the existing leaf value, tanh-squashed  (partialled out)
    "v_leaf_sq",         # its square (curvature of the transform)
    "tiles_remaining",   # game stage
    "corpus_champ125",   # corpus indicator (two generating leaves)
)

CANDIDATES = (
    # name                       tier  hypothesis / prior-art status
    ("pending_diff",             "A", "unbanked (would-score-at-end) point differential; with running_diff this tests the leaf's 1:1 banked-vs-pending weighting. NEW (P1-L2 'score as if ended now is structurally biased' was never directly tested)"),
    ("running_diff",             "A", "banked score differential; the paired half of the 1:1 weighting test. NEW"),
    ("pending_share",            "A", "share of the leaf's edge that is unbanked (risk concentration, scale-free). NEW"),
    ("bonus_overflow_self",      "A", "closure bonus lost to the cap=8 truncation, SELF. Cap LEVEL is dead (C5 cap5/cap12 flat, v2.10 cap6 null) — this tests the TRUNCATION, a different object"),
    ("bonus_overflow_opp",       "A", "closure bonus lost to the opp cap=8 truncation. Same distinction; note opp-cap moves were the worst C5 cells (oppcap4 -59.6, oppcap12 -66.8)"),
    ("road_anticip_diff",        "A", "road closure anticipation. The leaf's bonus covers cities/cloisters/farm-growth and gives roads ZERO. NEVER ISOLATED (review P1-L6; C7 Term R bundled roads into a harmful liquidity term). road_root_open_n already exists in the Decomp"),
    ("open_city_liability_diff", "A", "raw at-risk value of MY meepled open cities minus opp's (sum of city_root_delta, unweighted). = BACKLOG 2026-05-16 item #2 'penalize large open cities' — the one lit-review term NEVER IMPLEMENTED, NEVER RUN"),
    ("hopeless_city_diff",       "A", "meepled unfinished cities with open_n>=4, where closure_p truncates to exactly 0. NEW (the schedule's right tail)"),
    ("city_exposure_diff",       "A", "sum(city_root_delta * open_n) over meepled unfinished cities — tests the SHAPE of closure_p. Adjacent to C5 pclose080/pclose120 (both sub-gate), but those RESCALED the schedule; this probes a linear-in-open_n mis-shape"),
    ("stuck_meeple_diff",        "A", "meeples on components that can never close (unfinished, open_n==0 — the D16 guard drops them silently). Adjacent to C7 Term R (HARMFUL) but the opposite object: R credited RETURNABLE meeples, this counts PERMANENTLY STRANDED ones"),
    ("barren_farm_diff",         "A", "farm components with zero adjacent cities of any kind (a farmer that can never be worth anything). NEW — distinct from Term F (dead), which priced CONTESTED-field majority flips"),
    ("cloister_far_diff",        "A", "cloisters needing >=4 more tiles, where closure_p gives exactly 0. NEW (the schedule's right tail, cloister branch)"),
    ("open_frontier",            "A", "len(state.open_positions) — how fluid/volatile the board still is. NEW"),
    ("frontier_x_leaf",          "A", "volatility discount: the leaf's edge is worth less on a fluid board. NEW"),
    ("leaf_x_tiles",             "A", "stage-conditioned leaf scaling = review item M6 'phase-conditioned leaf weights', NEVER IMPLEMENTED. CL-061 already read this channel as sub-threshold for the VALUE TRANSFORM (~0.02 nats); a null here is confirmatory"),
    ("free_meeples_sum",         "A", "self+opp free-meeple TOTAL — the curve prices only the DIFFERENCE, so a level effect is unpriced. NEW (distinct from the curve SCALE axis that C5 already peaked)"),
    ("deck_city_share",          "B", "share of remaining tiles carrying >=1 city edge. ⚠ ADJACENT TO A 3x-KILLED FAMILY (deck-aware closure: 2026-05-17 tile_counting_closure + closure_continuous_slack null, v2.8 v28_completion null, v2.10/C5 bag_close null x2). Included in a DIFFERENT functional form — a global continuous scalar, not a per-feature hard gate — and a hit here would NOT resurrect bag_close; it would name a stage-scalar term. A null is the 4th confirmation"),
    ("n_legal",                  "C", "DIAGNOSTIC ONLY (needs move generation -> not leaf-viable): mover mobility at the root"),
)

NEG_CONTROL = "neg_control"      # deterministic pseudo-random; MUST land in the null band
POS_REF = "pos_ref_c5_curve"     # curve125-minus-curve100 leaf delta == the CL-051 change (+66.8 elo).
#                                  Yardstick only: it is ALREADY in the champion leaf, so it is
#                                  reported for scale and EXCLUDED from the multiple-comparisons family.

CANDIDATE_NAMES = tuple(n for n, _t, _h in CANDIDATES)
TIER = {n: t for n, t, _h in CANDIDATES}
ALL_FEATURES = CANDIDATE_NAMES + (NEG_CONTROL, POS_REF)

# The CL-051 predecessor curve (v2.9 base, "curve100") — champion is 1.25x this.
CURVE100 = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)


def _road_points_if_closed(coords) -> int:
    """Points a road component would score if it completed == #distinct tiles
    (== flat_leaf._road_points(coords, finished=True))."""
    return len(coords)


def _neg_control(root_id: str) -> float:
    """Deterministic uniform(-1,1) from the root id. Pure noise by construction."""
    h = hashlib.blake2b(root_id.encode(), digest_size=8).digest()
    return (int.from_bytes(h, "big") / float(1 << 64)) * 2.0 - 1.0


def root_features(state, player: int, cfg, root_id: str, n_legal: int,
                  corpus_champ125: int) -> dict:
    """Compute the full pre-registered dictionary for one root board.

    `player` = state.current_player (the mover); `cfg` = the champion LeafConfig
    (curve125 / cap8).  `n_legal` is passed in (the harness already has it from
    the root expansion) because generating it is Tier-C work.
    """
    opp = 1 - player
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0
    decomp = flat_leaf.decompose(state)
    closure_p = cfg.closure_p
    curve = cfg.v29_meeple_curve

    # ---------- the leaf's own pieces (all Tier A: the leaf computes these) --- #
    final = flat_leaf._final_scores(state, decomp)
    running_diff = float(int(state.scores[player]) - int(state.scores[opp]))
    pending_diff = float(final[player] - final[opp])
    base = running_diff + pending_diff                       # == flat_base_score

    bonus_self_raw = float(flat_leaf.flat_closure_bonus(state, player, decomp, cfg, None))
    bonus_opp_raw = float(flat_leaf.flat_closure_bonus(state, opp, decomp, cfg, None))
    cap = float(cfg.bonus_cap)
    opp_cap = float(cfg.opp_bonus_cap)

    free_self = int(state.meeples[player])
    free_opp = int(state.meeples[opp])

    # the CL-051 yardstick: what the curve125 change added to the leaf score
    if curve is not None:
        d125 = (flat_leaf._flat_curve_lookup(curve, free_self)
                - flat_leaf._flat_curve_lookup(curve, free_opp))
        d100 = (flat_leaf._flat_curve_lookup(CURVE100, free_self)
                - flat_leaf._flat_curve_lookup(CURVE100, free_opp))
        pos_ref = float(d125 - d100)
    else:
        pos_ref = 0.0

    # ---------- partition the players' meeples by feature kind (Tier B) ------- #
    # Same discrimination as flat_closure_bonus, but for BOTH players and also
    # collecting ROADS (which the leaf's bonus ignores entirely).
    knight_roots = {player: set(), opp: set()}
    road_roots = {player: set(), opp: set()}
    farm_roots = {player: set(), opp: set()}
    cloisters = {player: [], opp: []}
    for p in (player, opp):
        for mp in state.placed_meeples[p]:
            cws = mp.coordinate_with_side
            r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
            tile = board[r][c]
            if tile is None:
                continue
            terrain = tile.get_type(side)
            if terrain == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    knight_roots[p].add(root)
            elif terrain == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is not None:
                    road_roots[p].add(root)
            elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                cloisters[p].append((r, c))
            elif mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                root = decomp.farm_anypos_root.get((r, c, side))
                if root is not None:
                    farm_roots[p].add(root)

    def _road_anticip(p: int) -> float:
        tot = 0.0
        for root in road_roots[p]:
            if decomp.road_root_finished[root]:
                continue
            open_n = decomp.road_root_open_n[root]
            if open_n <= 0:
                continue
            pr = closure_p.get(open_n, 0.0)
            if pr > 0:
                tot += pr * _road_points_if_closed(decomp.road_root_coords[root])
        return tot

    def _hopeless_city(p: int) -> float:
        tot = 0.0
        for root in knight_roots[p]:
            if decomp.city_root_finished[root]:
                continue
            if decomp.city_root_open_n[root] >= 4:
                tot += float(decomp.city_root_delta[root])
        return tot

    def _open_city_liability(p: int) -> float:
        """BACKLOG 2026-05-16 #2: the raw at-risk value sitting in my open cities."""
        tot = 0.0
        for root in knight_roots[p]:
            if decomp.city_root_finished[root]:
                continue
            if decomp.city_root_open_n[root] > 0:
                tot += float(decomp.city_root_delta[root])
        return tot

    def _stuck(p: int) -> float:
        n = 0
        for root in knight_roots[p]:
            if (not decomp.city_root_finished[root]) and decomp.city_root_open_n[root] == 0:
                n += 1
        for root in road_roots[p]:
            if (not decomp.road_root_finished[root]) and decomp.road_root_open_n[root] == 0:
                n += 1
        return float(n)

    def _barren_farm(p: int) -> float:
        n = 0
        for root in farm_roots[p]:
            if not decomp.farm_root_adj_city_roots[root]:
                n += 1
        return float(n)

    def _city_exposure(p: int) -> float:
        tot = 0.0
        for root in knight_roots[p]:
            if decomp.city_root_finished[root]:
                continue
            open_n = decomp.city_root_open_n[root]
            if open_n > 0:
                tot += float(decomp.city_root_delta[root]) * float(open_n)
        return tot

    def _cloister_far(p: int) -> float:
        n = 0
        for (r, c) in cloisters[p]:
            needed = 8 - flat_leaf._surrounding_count(state, r, c, H, W)
            if needed >= 4:
                n += 1
        return float(n)

    bag = flat_leaf._bag_stats(state)          # (n, ge1, ge2, ge3, ge4)
    deck_city_share = (bag[1] / bag[0]) if bag[0] > 0 else 0.0

    frontier = float(len(state.open_positions))
    v_leaf = math.tanh(
        flat_leaf.flat_virtual_score_v2_float(state, player, cfg, False) / 15.0)

    denom = abs(running_diff) + abs(pending_diff) + 1.0
    feats = {
        "pending_diff": pending_diff,
        "running_diff": running_diff,
        "pending_share": pending_diff / denom,
        "bonus_overflow_self": max(0.0, bonus_self_raw - cap),
        "bonus_overflow_opp": max(0.0, bonus_opp_raw - opp_cap),
        "road_anticip_diff": _road_anticip(player) - _road_anticip(opp),
        "open_city_liability_diff": _open_city_liability(player) - _open_city_liability(opp),
        "hopeless_city_diff": _hopeless_city(player) - _hopeless_city(opp),
        "stuck_meeple_diff": _stuck(player) - _stuck(opp),
        "barren_farm_diff": _barren_farm(player) - _barren_farm(opp),
        "open_frontier": frontier,
        "frontier_x_leaf": frontier * v_leaf,
        "leaf_x_tiles": v_leaf * float(bag[0]),
        "city_exposure_diff": _city_exposure(player) - _city_exposure(opp),
        "cloister_far_diff": _cloister_far(player) - _cloister_far(opp),
        "free_meeples_sum": float(free_self + free_opp),
        "deck_city_share": float(deck_city_share),
        "n_legal": float(n_legal),
        NEG_CONTROL: _neg_control(root_id),
        POS_REF: pos_ref,
    }
    assert set(feats) == set(ALL_FEATURES), (
        f"feature set drift: {set(feats) ^ set(ALL_FEATURES)}")

    aux = {
        "v_leaf": v_leaf,
        "leaf_raw": float(flat_leaf.flat_virtual_score_v2_float(state, player, cfg, False)),
        "base_score": base,
        "bonus_self_raw": bonus_self_raw,
        "bonus_opp_raw": bonus_opp_raw,
        "free_self": float(free_self),
        "free_opp": float(free_opp),
        "tiles_remaining": float(bag[0]),
        "corpus_champ125": float(corpus_champ125),
    }
    return feats, aux
