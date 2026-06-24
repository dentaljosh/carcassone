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
V_CONTEST = 4.0                         # min value of an open feature to count a contest
EPS = 1e-9

MOTIFS = ("block", "avoid_feeding", "farm_claim", "farm_denial", "contest")


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


def opp_completion_equity(state, decomp, opp):
    """Sum over OPEN cities where `opp` holds majority/tie:  value * P(close).
    The opponent's pending-completion value on the board. Cities only."""
    city_counts, _, _ = _feature_owners(state, decomp)
    total = 0.0
    for root in decomp.city_root_coords:
        if decomp.city_root_finished[root]:
            continue
        open_n = decomp.city_root_open_n[root]
        if open_n > NEAR_OPEN_N:
            continue
        winners = _winners(city_counts.get(root, [0, 0]))
        if opp in winners:
            total += _city_value(decomp, root, state.board) * pclose(open_n)
    return total


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
    """TILES-phase motifs: block (deny opp completion equity), avoid_feeding."""
    # opponent's pending completion equity in the CURRENT position
    opp_eq_pre = opp_completion_equity(st, decomp, opp)
    # per-action: opponent's completion equity AFTER my tile placement
    per_action = {}
    for a in legal_actions:
        post_state, post_decomp = _apply(game, board, a)
        per_action[a] = opp_completion_equity(post_state, post_decomp, opp)
    if not per_action:
        return
    vals = per_action.values()
    lo, hi = min(vals), max(vals)
    spread = hi - lo

    # BLOCK: opp already has a near-complete owned city (>= V_BLOCK at stake) AND the
    # placement choice is CONSEQUENTIAL (>= BLOCK_SPREAD swing in opp completion
    # equity). satisfying = STRICT arg-min (the genuine denials). Equity proxy --
    # low fidelity, since my tile rarely interacts with the opp's feature.
    if opp_eq_pre >= V_BLOCK and spread >= BLOCK_SPREAD:
        sat = {a for a, v in per_action.items() if v <= lo + EPS}
        if len(sat) < len(per_action):   # a real choice exists
            out["block"] = MotifLabel(
                opportunity=True, satisfying=sat, best_magnitude=spread,
                detail={"opp_eq_pre": round(opp_eq_pre, 2), "lo": round(lo, 2),
                        "hi": round(hi, 2), "spread": round(spread, 2)},
            )

    # AVOID_FEEDING: a CONSEQUENTIAL feeding move exists (some actions hand the opp
    # >= FEED_SPREAD more pending equity than others). satisfying = strict arg-min
    # (didn't feed). Equity proxy -- low fidelity.
    if spread >= FEED_SPREAD:
        sat = {a for a, v in per_action.items() if v <= lo + EPS}
        if len(sat) < len(per_action):
            out["avoid_feeding"] = MotifLabel(
                opportunity=True, satisfying=sat, best_magnitude=spread,
                detail={"lo": round(lo, 2), "hi": round(hi, 2), "spread": round(spread, 2)},
            )


def _label_meeples(game, board, st, mover, opp, decomp, legal_actions, out):
    """MEEPLES-phase motifs (structural ownership flips): farm_claim, farm_denial,
    contest. Apply each candidate meeple action, re-decompose, compare ownership by
    root (roots are stable across a meeple placement; farms never auto-complete)."""
    pre_city, pre_road, pre_farm = _feature_owners(st, decomp)

    claim_sat, denial_sat, contest_sat = set(), set(), set()
    claim_mag = denial_mag = contest_mag = 0.0
    claim_fin = denial_fin = 0   # # finished adjacent cities of the best farm (outcome-sanity)
    claim_adj = denial_adj = 0   # # adjacent city components

    for a in legal_actions:
        post_state, post_decomp = _apply(game, board, a)
        post_city, post_road, post_farm = _feature_owners(post_state, post_decomp)

        # ---- FARMS (roots stable; farmers survive turn-end) ----
        for root in post_decomp.farm_root_keys:
            post_w = _winners(post_farm.get(root, [0, 0]))
            if mover not in post_w:
                continue
            pre_w = _winners(pre_farm.get(root, [0, 0]))
            if mover in pre_w:
                continue  # already owned -> not a new claim/denial
            vproj = _farm_value_proj(post_decomp, root)
            fin = post_decomp.farm_root_finished_cities.get(root, 0)
            adj = len(post_decomp.farm_root_adj_city_roots.get(root, ()))
            if pre_w == [opp]:
                # I moved an opp-sole farm to a tie (or take) -> DENIAL
                if vproj >= V_FARM_PROJ:
                    denial_sat.add(a)
                    if vproj > denial_mag:
                        denial_mag, denial_fin, denial_adj = vproj, fin, adj
            else:
                # previously unowned (or mine) -> CLAIM of a high-value field
                if vproj >= V_FARM_PROJ and post_w == [mover]:
                    claim_sat.add(a)
                    if vproj > claim_mag:
                        claim_mag, claim_fin, claim_adj = vproj, fin, adj

        # ---- CONTEST open city/road (surviving features) ----
        for root in post_decomp.city_root_coords:
            if post_decomp.city_root_finished.get(root, False):
                continue
            post_w = _winners(post_city.get(root, [0, 0]))
            pre_w = _winners(pre_city.get(root, [0, 0]))
            if pre_w == [opp] and mover in post_w:
                val = _city_value(post_decomp, root, post_state.board)
                if val >= V_CONTEST:
                    contest_sat.add(a)
                    contest_mag = max(contest_mag, val)

    if claim_sat:
        out["farm_claim"] = MotifLabel(True, claim_sat, claim_mag,
                                       {"finished_adj": claim_fin, "adj_n": claim_adj})
    if denial_sat:
        out["farm_denial"] = MotifLabel(True, denial_sat, denial_mag,
                                        {"finished_adj": denial_fin, "adj_n": denial_adj})
    if contest_sat:
        out["contest"] = MotifLabel(True, contest_sat, contest_mag)


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
