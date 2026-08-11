"""Strategic-behavior MOTIF detectors for the pseudo-human ladder benchmark.

READ THIS before trusting any number it produces.

A *position* is a (game, board) at a decision point (TILES or MEEPLES phase),
with `mover = board.state.current_player`, `opp = 1 - mover`.

DESIGN PRINCIPLES
-----------------
1. Detectors are STRUCTURAL. Opportunity + satisfying-action sets are derived from
   the flat_leaf board decomposition (feature components, ownership majority,
   completion distance, farm->city adjacency), NOT from any single agent's value
   function. The v2.7 closure schedule {1:0.5, 2:0.2} is used ONLY as a labeled
   closure-PROBABILITY model. The v2.7 leaf SCORE (virtual_score_v2) is reported as
   a SECONDARY magnitude, never as the opportunity gate -- otherwise "took the
   motif" collapses to "agreed with v2.7", which heuristic agents win by
   construction (they search exactly that leaf).

2. label_position() is AGENT-INDEPENDENT and computed ONCE per position. Agents'
   chosen actions are harvested separately and joined: an agent TOOK a motif iff
   its chosen action is in that motif's `satisfying` set; it MISSED iff the
   opportunity existed and its choice was not satisfying.

3. FIDELITY TIERS (honest, surfaced in the report):
   - structural / credible : farm_claim, farm_denial, contest (ownership flips)
   - equity-proxy / noisier : block (opp completion-equity denial), avoid_feeding
                              -- cities only; the decomposition exposes no road
                              completion-distance, and roads are low value anyway.
   - descriptive only       : meeple liquidity (reported as state stats, not a
                              take-rate motif).
   Pre-endgame conversion (exact-K) is a SEPARATE solver-labeled slice, not here.

RESIDUAL CIRCULARITY (acknowledged): structural motifs (block a near-complete
city, claim a 2-city farm) correlate with what v2.7 values, so heuristic agents
are EXPECTED to score high. The diagnostic question is whether the NEURAL agent
(RoD1) matches that behavior, and whether strong agents punish weak-CREATED
opportunities more than strong-created ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from carcassonne_ai.flat_leaf import (
    decompose,
    _city_points,
    _road_points,
    _meeple_weight,
    _winners,
)
from carcassonne_ai.virtual_score_v2 import virtual_score_v2
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.game_phase import GamePhase

# ---- dev-tunable thresholds (FROZEN after dev-set tuning; see report) -------- #
CLOSURE_P = {0: 1.0, 1: 0.5, 2: 0.2}   # v2.7 schedule, used ONLY as a P(close) model
NEAR_OPEN_N = 2                         # an open city is "near complete" if open_n <= 2
V_BLOCK = 4.0                           # min at-stake opp city value to be a block opportunity
BLOCK_SPREAD = 2.0                      # min (max-min) swing in opp completion-equity across
                                        #   legal actions for a CONSEQUENTIAL block decision
                                        #   (>= ~1 completion's worth). Tile placement rarely
                                        #   touches opp features, so this gate keeps only real
                                        #   choices -- block/feed are LOW-FIDELITY equity proxies.
FEED_SPREAD = 2.0                       # same consequential-swing gate for avoid_feeding
V_FARM_PROJ = 6.0                       # high-value farm = projected >= 6 (touches >= 2 cities)
EPS = 1e-9

# NOTE on contest/denial: in 2-player BASE Carcassonne you CANNOT place a meeple on an
# occupied feature (illegal), so you cannot "steal" a field by placing on it. The ONLY
# legal contest/denial mechanism is a TILES-phase MERGE -- a tile that connects two
# pre-placed farmers into one shared field. So contest_merge is a TILES motif, and there
# is no meeple-phase "steal". (This is a genuine rules constraint, surfaced in the report.)
MOTIFS = ("block", "avoid_feeding", "contest_merge", "farm_claim")


def pclose(open_n: int) -> float:
    if open_n <= 0:
        return 1.0
    return CLOSURE_P.get(open_n, 0.0)


# --------------------------------------------------------------------------- #
#  Ownership: per-feature winners, mirroring flat_leaf._final_scores exactly.
# --------------------------------------------------------------------------- #
def _feature_owners(state, decomp):
    """Return (city_counts, road_counts, farm_counts): root -> [p0_w, p1_w]."""
    board = state.board
    city_counts: dict = {}
    road_counts: dict = {}
    farm_counts: dict = {}
    for player in range(2):
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
            terrain = board[r][c].get_type(side)
            w = _meeple_weight(mp.meeple_type)
            if terrain == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                d = city_counts
            elif terrain == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                d = road_counts
            elif mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                root = decomp.farm_pos0_root.get((r, c, side))
                d = farm_counts
            else:
                continue
            if root is None:
                continue
            cnt = d.get(root)
            if cnt is None:
                cnt = [0, 0]
                d[root] = cnt
            cnt[player] += w
    return city_counts, road_counts, farm_counts


def _city_value(decomp, root, board):
    """At-stake value of a city if it closes (== count_city_points when closed)."""
    if decomp.city_root_finished[root]:
        return _city_points(decomp.city_root_coords[root], True, board)
    return decomp.city_root_delta[root]


def _farm_value_proj(decomp, root):
    """Projected farm value = 3 * (# adjacent city components), optimistic
    (assumes adjacent cities complete). Spec Part A.3 'connected-city count'."""
    return 3 * len(decomp.farm_root_adj_city_roots.get(root, ()))


def _farm_value_real(decomp, root):
    return 3 * decomp.farm_root_finished_cities.get(root, 0)


def _opp_eq(state, decomp, city_counts, opp):
    """Sum over OPEN cities where `opp` holds majority/tie:  value * P(close).
    The opponent's pending-completion value on the board. Cities only."""
    total = 0.0
    for root in decomp.city_root_coords:
        if decomp.city_root_finished[root]:
            continue
        open_n = decomp.city_root_open_n[root]
        if open_n > NEAR_OPEN_N:
            continue
        if opp in _winners(city_counts.get(root, [0, 0])):
            total += _city_value(decomp, root, state.board) * pclose(open_n)
    return total


def opp_completion_equity(state, decomp, opp):
    city_counts, _, _ = _feature_owners(state, decomp)
    return _opp_eq(state, decomp, city_counts, opp)


def _mover_fav_contest(decomp, farm_counts, mover):
    """Max projected value of a mover-FAVORABLE (tie-or-win) CONTESTED farm (both
    players have farmers) with projected value >= V_FARM_PROJ; 0.0 if none. This is
    the only legal steal/denial in 2p base -- created by a tile merging two fields."""
    best = 0.0
    for root, counts in farm_counts.items():
        if counts[0] > 0 and counts[1] > 0 and mover in _winners(counts):
            v = _farm_value_proj(decomp, root)
            if v >= V_FARM_PROJ:
                best = max(best, v)
    return best


# --------------------------------------------------------------------------- #
#  Position snapshot (scores, meeples, phase, k, feature inventory).
# --------------------------------------------------------------------------- #
def k_remaining(board) -> int:
    st = board.state
    return len(st.deck) + (1 if st.next_tile is not None else 0)


def phase_of(k: int) -> str:
    if k <= 6:
        return "endgame"
    if k <= 14:
        return "pre_endgame"
    if k <= 28:
        return "late_mid"
    if k <= 46:
        return "midgame"
    return "opening"


def position_snapshot(game, board) -> dict:
    st = board.state
    mover = st.current_player
    decomp = decompose(st)
    k = k_remaining(board)
    return {
        "to_move": mover,
        "phase_tile": "TILES" if st.phase == GamePhase.TILES else "MEEPLES",
        "k_remaining": k,
        "phase": phase_of(k),
        "scores": list(st.scores),
        "meeples_free": list(st.meeples),
        "meeples_placed": [len(st.placed_meeples[0]), len(st.placed_meeples[1])],
        "score_margin_mover": int(st.scores[mover]) - int(st.scores[1 - mover]),
        "decomp": decomp,
    }


# --------------------------------------------------------------------------- #
#  Core: apply a candidate action safely -> (post_state, post_decomp).
# --------------------------------------------------------------------------- #
def _apply(game, board, a):
    nb, _ = game.get_next_state(board, int(a))
    return nb.state, decompose(nb.state)


# --------------------------------------------------------------------------- #
#  label_position : agent-independent motif labels for ONE position.
# --------------------------------------------------------------------------- #
@dataclass
class MotifLabel:
    opportunity: bool = False
    satisfying: set = field(default_factory=set)   # legal action idxs that satisfy
    best_magnitude: float = 0.0                     # value at stake (structural)
    detail: dict = field(default_factory=dict)


def label_position(game, board, legal_actions, leaf_cfg=None) -> dict:
    """Compute {motif -> MotifLabel} for this position (agent-independent).

    `legal_actions` : iterable of legal action indices at this board.
    `leaf_cfg`       : LeafConfig for the SECONDARY v2.7-equity magnitude (optional).
    """
    st = board.state
    mover, opp = st.current_player, 1 - st.current_player
    is_tiles = st.phase == GamePhase.TILES
    decomp = decompose(st)
    out = {m: MotifLabel() for m in MOTIFS}

    if is_tiles:
        _label_tiles(game, board, st, mover, opp, decomp, legal_actions, out)
    else:
        _label_meeples(game, board, st, mover, opp, decomp, legal_actions, out)
    return out


def _label_tiles(game, board, st, mover, opp, decomp, legal_actions, out):
    """TILES-phase motifs: block, avoid_feeding (equity proxies), contest_merge
    (favorable merge into a contested high-value field). One ownership scan / action."""
    pre_city, _, _ = _feature_owners(st, decomp)
    opp_eq_pre = _opp_eq(st, decomp, pre_city, opp)
    per_eq = {}       # opp completion equity AFTER my placement
    per_contest = {}  # mover-favorable contested-farm value AFTER my placement
    for a in legal_actions:
        ps, pd = _apply(game, board, a)
        cc, _, fc = _feature_owners(ps, pd)
        per_eq[a] = _opp_eq(ps, pd, cc, opp)
        per_contest[a] = _mover_fav_contest(pd, fc, mover)
    if not per_eq:
        return
    lo, hi = min(per_eq.values()), max(per_eq.values())
    spread = hi - lo

    # BLOCK: opp has a near-complete owned city (>= V_BLOCK) AND the placement choice
    # is consequential (>= BLOCK_SPREAD swing). satisfying = strict arg-min (denials).
    if opp_eq_pre >= V_BLOCK and spread >= BLOCK_SPREAD:
        sat = {a for a, v in per_eq.items() if v <= lo + EPS}
        if len(sat) < len(per_eq):
            out["block"] = MotifLabel(True, sat, spread,
                {"opp_eq_pre": round(opp_eq_pre, 2), "lo": round(lo, 2),
                 "hi": round(hi, 2), "spread": round(spread, 2)})

    # AVOID_FEEDING: a consequential feeding move exists. satisfying = strict arg-min.
    if spread >= FEED_SPREAD:
        sat = {a for a, v in per_eq.items() if v <= lo + EPS}
        if len(sat) < len(per_eq):
            out["avoid_feeding"] = MotifLabel(True, sat, spread,
                {"lo": round(lo, 2), "hi": round(hi, 2), "spread": round(spread, 2)})

    # CONTEST_MERGE: some placements give the mover a favorable share of a valuable
    # contested field (the only legal steal/denial), others don't -> a real choice.
    has = {a for a, v in per_contest.items() if v >= V_FARM_PROJ}
    if has and len(has) < len(per_contest):
        out["contest_merge"] = MotifLabel(True, has, max(per_contest.values()),
            {"n_yes": len(has), "n_legal": len(per_contest)})


def _label_meeples(game, board, st, mover, opp, decomp, legal_actions, out):
    """MEEPLES-phase motif: farm_claim (the only legal field motif at meeple time --
    you cannot place on an occupied feature, so no steal/denial here)."""
    pre_city, pre_road, pre_farm = _feature_owners(st, decomp)
    claim_sat = set()
    claim_mag = 0.0
    claim_fin = claim_adj = 0
    for a in legal_actions:
        post_state, post_decomp = _apply(game, board, a)
        _, _, post_farm = _feature_owners(post_state, post_decomp)
        for root in post_decomp.farm_root_keys:
            post_w = _winners(post_farm.get(root, [0, 0]))
            if post_w != [mover]:
                continue
            if mover in _winners(pre_farm.get(root, [0, 0])):
                continue  # already owned
            vproj = _farm_value_proj(post_decomp, root)
            if vproj >= V_FARM_PROJ:
                claim_sat.add(a)
                fin = post_decomp.farm_root_finished_cities.get(root, 0)
                adj = len(post_decomp.farm_root_adj_city_roots.get(root, ()))
                if vproj > claim_mag:
                    claim_mag, claim_fin, claim_adj = vproj, fin, adj
    if claim_sat:
        out["farm_claim"] = MotifLabel(True, claim_sat, claim_mag,
                                       {"finished_adj": claim_fin, "adj_n": claim_adj})


# --------------------------------------------------------------------------- #
#  Scoring an agent's choice against labels.
# --------------------------------------------------------------------------- #
def score_take(labels: dict, chosen_action: int) -> dict:
    """Given {motif->MotifLabel} and an agent's chosen action, return
    {motif -> 'took'|'missed'|None} (None = no opportunity at this position)."""
    res = {}
    for m, lab in labels.items():
        if not lab.opportunity:
            res[m] = None
        elif chosen_action in lab.satisfying:
            res[m] = "took"
        else:
            res[m] = "missed"
    return res
