"""HIGH-PRECISION strategic-trap detectors (narrow successors to the broad ladder).

Optimised for PRECISION, not coverage. Each detector fires only on concrete,
human-recognisable tactical situations and labels the qualifying action(s) by
STRUCTURAL INTERFERENCE, not "play elsewhere". All structural — no outcome/score/
agent/exact leakage.

Motifs:
  MUST_BLOCK_CITY      a placement that physically lands in an opp >=8-pt near-complete
                       city's open completion cell WITHOUT completing it (spoil/extend),
                       and doesn't sacrifice more than it denies.
  MUST_NOT_FEED        a placement that hands the opp an immediate >=8-pt completable city
                       (opp-owned, post open_n<=1) that a safe alternative avoids.
  MUST_PUNISH_WEAK     mover can immediately bank >=8 pts the (weak) opp left exposed:
                       complete own >=8 city, claim a >=9 live farm, or steal a >=8 city.
  HIGH_VALUE_FARM_CLAIM_REFINED  sole-claim a farm with projected >=9 AND >=1 LIVE adjacent
                       city (finished or open_n<=2), excluding already-won states (margin>+20).
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field

from carcassonne_ai.flat_leaf import decompose, _city_points, _winners
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.side import Side

import sys
sys.path.insert(0, os.path.dirname(__file__))
from motifs import _feature_owners, _city_value, _farm_value_proj, k_remaining, phase_of

# ---- frozen thresholds ----------------------------------------------------- #
V_CITY_BLOCK = 8        # opp city must be worth >= this to be block-worthy
V_FEED = 8              # opp gets a completable city worth >= this
V_PUNISH = 8            # exposed swing the mover can bank
V_FARM_REFINED = 9      # refined farm projected value (>= 3 cities)
ALREADY_WON = 20        # pre-move score margin above which we call it already-won
CARD = {Side.TOP: (-1, 0), Side.RIGHT: (0, 1), Side.BOTTOM: (1, 0), Side.LEFT: (0, -1)}

MOTIFS = ("MUST_BLOCK_CITY", "MUST_NOT_FEED", "MUST_PUNISH_WEAK", "HIGH_VALUE_FARM_CLAIM_REFINED")


@dataclass
class StrictLabel:
    opportunity: bool = False
    satisfying: set = field(default_factory=set)
    feeding: set = field(default_factory=set)        # the BAD actions (feed/block-fail), for MUST_NOT_FEED
    magnitude: float = 0.0
    threat: str = ""                                  # human-readable description
    detail: dict = field(default_factory=dict)


# ---- geometry helpers ------------------------------------------------------ #
def _city_open_cells(state, decomp, root):
    board = state.board
    H, W = len(board), len(board[0])
    cells = set()
    for (r, c, side) in decomp.city_root_positions.get(root, ()):
        d = CARD.get(side)
        if d is None:
            continue
        nr, nc = r + d[0], c + d[1]
        if 0 <= nr < H and 0 <= nc < W and board[nr][nc] is None:
            cells.add((nr, nc))
    return cells


def _placed_cells(state):
    return {(co.row, co.column) for co in state.placed_coords}


def _apply(game, board, a):
    nb, _ = game.get_next_state(board, int(a))
    return nb.state, decompose(nb.state)


def _city_owner_value(state, decomp, city_counts):
    """root -> (winners, value, open_n, finished) for every city."""
    out = {}
    for root in decomp.city_root_coords:
        winners = _winners(city_counts.get(root, [0, 0]))
        out[root] = (winners, _city_value(decomp, root, state.board),
                     decomp.city_root_open_n[root], decomp.city_root_finished[root])
    return out


# ---- the detectors --------------------------------------------------------- #
def label_strict(game, board, legal_actions):
    st = board.state
    mover, opp = st.current_player, 1 - st.current_player
    margin = int(st.scores[mover]) - int(st.scores[opp])
    decomp = decompose(st)
    is_tiles = st.phase == GamePhase.TILES
    city_counts, _, farm_counts = _feature_owners(st, decomp)
    out = {m: StrictLabel() for m in MOTIFS}

    if is_tiles:
        _block_and_feed(game, board, st, mover, opp, decomp, city_counts, legal_actions, margin, out)
        _punish_tiles(game, board, st, mover, opp, decomp, city_counts, legal_actions, margin, out)
    else:
        _farm_refined(game, board, st, mover, opp, decomp, farm_counts, legal_actions, margin, out)
        _punish_meeples(game, board, st, mover, opp, decomp, farm_counts, legal_actions, margin, out)
    return out


def _block_and_feed(game, board, st, mover, opp, decomp, city_counts, legal, margin, out):
    pre = _city_owner_value(st, decomp, city_counts)
    # target opp near-complete >=8 cities (open_n==1), opp owns (>= mover), mover not sole owner
    targets = {root: t for root, t in pre.items()
               if not t[3] and t[2] == 1 and t[1] >= V_CITY_BLOCK and opp in t[0] and t[0] != [mover]}
    pre_cells = _placed_cells(st)

    block_sat = set()
    feed_bad, feed_safe = set(), set()
    best_block = 0.0
    best_threat = ""
    feed_val = 0.0
    for a in legal:
        post_state, post_decomp = _apply(game, board, a)
        post_cc, _, _ = _feature_owners(post_state, post_decomp)
        new_cell = (_placed_cells(post_state) - pre_cells)
        new_cell = next(iter(new_cell)) if new_cell else None

        # ---- MUST_BLOCK_CITY: placement lands in a target's open cell, doesn't finish it ----
        for root, (w, val, openn, fin) in targets.items():
            cells = _city_open_cells(st, decomp, root)
            if new_cell in cells:
                # did the target stay UNfinished (spoiled) and bigger?
                edge = next(iter(decomp.city_root_positions[root]))
                post_root = post_decomp.city_side_root.get(edge)
                post_fin = post_decomp.city_root_finished.get(post_root, True) if post_root is not None else True
                post_openn = post_decomp.city_root_open_n.get(post_root, 0) if post_root is not None else 0
                if (not post_fin) and post_openn > openn:
                    # strictly harder to close (not just a 1->1 swap); a real spoil
                    block_sat.add(a)
                    if val > best_block:
                        best_block = val
                        best_threat = (f"opp city ~{val}pts, 1 tile from done at cell {new_cell}; "
                                       f"this placement spoils it (post open_n {openn}->{post_openn})")

        # ---- MUST_NOT_FEED: this placement gives opp a ready >=8 city ----
        post = _city_owner_value(post_state, post_decomp, post_cc)
        opp_ready = max((val for (w, val, openn, fin) in post.values()
                         if (not fin) and openn <= 1 and val >= V_FEED and opp in w and w != [mover]),
                        default=0.0)
        if opp_ready >= V_FEED:
            feed_bad.add(a)
            feed_val = max(feed_val, opp_ready)
        else:
            feed_safe.add(a)

    if block_sat:
        out["MUST_BLOCK_CITY"] = StrictLabel(True, block_sat, magnitude=best_block, threat=best_threat,
                                             detail={"n_targets": len(targets)})
    # feed: a real choice (some feed, some don't) and a meaningful shot
    if feed_bad and feed_safe and feed_val >= V_FEED:
        out["MUST_NOT_FEED"] = StrictLabel(True, feed_safe, feeding=feed_bad, magnitude=feed_val,
                                           threat=f"a legal move hands opp a ~{feed_val:.0f}pt completable city; "
                                                  f"{len(feed_safe)}/{len(legal)} placements avoid it")


def _punish_tiles(game, board, st, mover, opp, decomp, city_counts, legal, margin, out):
    """MUST_PUNISH_WEAK (TILES): mover completes its OWN >=8 city this turn (banks exposed pts)."""
    if margin > ALREADY_WON:
        return
    pre = _city_owner_value(st, decomp, city_counts)
    sat = set()
    best = 0.0
    for a in legal:
        post_state, post_decomp = _apply(game, board, a)
        post_cc, _, _ = _feature_owners(post_state, post_decomp)
        post = _city_owner_value(post_state, post_decomp, post_cc)
        for root, (w, val, openn, fin) in post.items():
            if fin and val >= V_PUNISH and w == [mover]:
                # was it not-yet-finished pre? (a genuine completion this move)
                sat.add(a)
                best = max(best, val)
                break
    if sat:
        cur = out["MUST_PUNISH_WEAK"]
        if best > cur.magnitude:
            out["MUST_PUNISH_WEAK"] = StrictLabel(True, sat, magnitude=best,
                                                  threat=f"mover can COMPLETE its own ~{best:.0f}pt city this turn")


def _live_adj(decomp, root):
    """# adjacent cities that are finished OR near-done (open_n<=2) -- 'finishable'."""
    n = 0
    for cr in decomp.farm_root_adj_city_roots.get(root, ()):
        if decomp.city_root_finished.get(cr, False) or decomp.city_root_open_n.get(cr, 9) <= 2:
            n += 1
    return n


def _farm_refined(game, board, st, mover, opp, decomp, farm_counts, legal, margin, out):
    """HIGH_VALUE_FARM_CLAIM_REFINED + farm flavour of MUST_PUNISH_WEAK."""
    sat = set()
    best = 0.0
    best_threat = ""
    live_best = 0
    for a in legal:
        post_state, post_decomp = _apply(game, board, a)
        _, _, post_farm = _feature_owners(post_state, post_decomp)
        for root in post_decomp.farm_root_keys:
            if _winners(post_farm.get(root, [0, 0])) != [mover]:
                continue
            if mover in _winners(farm_counts.get(root, [0, 0])):
                continue  # already owned
            vproj = _farm_value_proj(post_decomp, root)
            live = _live_adj(post_decomp, root)
            if vproj >= V_FARM_REFINED and live >= 2:   # >=2 finishable cities (live=1 is declined by strong agents)
                sat.add(a)
                if vproj > best:
                    best, live_best = vproj, live
                    best_threat = (f"sole-claim a field touching {vproj//3} cities ({live} live/finishable), "
                                   f"projected ~{vproj}pts")
    if sat and margin <= ALREADY_WON:
        out["HIGH_VALUE_FARM_CLAIM_REFINED"] = StrictLabel(True, sat, magnitude=best, threat=best_threat,
            detail={"live_adj": live_best, "margin_before": margin})


def _punish_meeples(game, board, st, mover, opp, decomp, farm_counts, legal, margin, out):
    """MUST_PUNISH_WEAK (MEEPLES): claim a >=9 live farm the opp left exposed."""
    if margin > ALREADY_WON:
        return
    sat = set()
    best = 0.0
    for a in legal:
        post_state, post_decomp = _apply(game, board, a)
        _, _, post_farm = _feature_owners(post_state, post_decomp)
        for root in post_decomp.farm_root_keys:
            if _winners(post_farm.get(root, [0, 0])) != [mover]:
                continue
            if mover in _winners(farm_counts.get(root, [0, 0])):
                continue
            vproj = _farm_value_proj(post_decomp, root)
            if vproj >= V_PUNISH and _live_adj(post_decomp, root) >= 1:
                sat.add(a)
                best = max(best, vproj)
    if sat:
        cur = out["MUST_PUNISH_WEAK"]
        if best > cur.magnitude:
            out["MUST_PUNISH_WEAK"] = StrictLabel(True, sat, magnitude=best,
                threat=f"mover can CLAIM a ~{best:.0f}pt live field the opp left exposed")


def score_take(labels, chosen):
    res = {}
    for m, lab in labels.items():
        if not lab.opportunity:
            res[m] = None
        elif chosen in lab.satisfying:
            res[m] = "took"
        else:
            res[m] = "missed"
    return res
