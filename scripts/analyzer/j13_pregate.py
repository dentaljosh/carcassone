#!/usr/bin/env python3
"""J13 / J5 PRE-GATE — a retrospective "unclaimed-feature buildup" instrument.

WHAT THIS IS. A **descriptive replay instrument** over the banked human-vs-champion
archives in `measurement/e4_games/`. It plays no games, searches nothing, and
promotes nothing. It exists to answer one question cheaply, BEFORE anyone builds a
leaf term:

    the production leaf prices unclaimed features at exactly ZERO for everyone
    (the incomplete-feature credit is owner-gated, so no term reads an ownerless
    structure). Is "build up a feature nobody owns yet, claim it later" actually a
    thing that happens, does it pay, and do the two seats differ in it?

The proposed term is J13 (offence — invest in what you will likely capture) and
J5 (defence — do not feed what the opponent will likely capture), one signed
weight:  V(feature) x (P_self(claim) - P_opp(claim)).

WHAT IT CANNOT DO — read this before quoting any number below.
  * **No causation.** "He built it up and later claimed it" is outcome-conditioned
    selection. The honest reading is a RATE COMPARISON BETWEEN THE TWO SEATS on the
    same boards (they share every deck, every board, every game length), plus base
    rates that BOUND how much value the term could possibly reach.
  * **One human, 26 games, 3 rules epochs.** Epoch is a real axis (the fixed_v1
    flip changed cloister + farm rules); stats are reported per epoch and the
    headline is the fixed_v1 epoch (n=23). Never pool epochs whose signs disagree.
  * **0 games played => no results.csv row, no band claim, no claim id.** House
    precedent: farm-war, adaptive-k census, item-1 farm-norm replay.

--------------------------------------------------------------------------------
THE DEFINITIONS (this module owns them)
--------------------------------------------------------------------------------
`SLOT`  the atom of feature identity. A city/road slot is `(r, c, Side)`; a farm
        slot is `(r, c, farmer_position Side)`; a cloister slot is the tile `(r, c)`.
        Slots never move and never disappear (tiles are never removed), so they
        are stable across the whole replay while union-find ROOT IDS are not.

`FEATURE`  a persistent union-find class over slots. Components only ever grow or
        MERGE, never split, so unioning every component of every intermediate
        board yields exactly the TERMINAL components. That final class is the
        feature's identity, and it is what "traced forward to its fate" means.

`TOUCH`  one (turn, actor, component) pair: the tile the actor just placed
        contributed >=1 slot to that component. One tile can touch several
        components (a road, a city, two fields) => several touches, one ply.

`OWNERS AT DECISION TIME`  the players with meeples on the touched component in
        the state RIGHT AFTER the tile ply and BEFORE the actor's own meeple ply.
        That is the view the placing player actually had. Meeple removal happens at
        the END of the turn, so completing an opponent's city still reads as
        "opponent-owned" here, which is correct.

A touch is classified as exactly one of:
  `buildup`      - nobody owned the component, and the actor did NOT claim it this
                   turn. THE J13 QUANTITY.
  `claim_now`    - nobody owned it and the actor claimed it in the same turn. Not
                   buildup: the leaf already prices an owned feature.
  `own_growth`   - the actor already owned it (alone).
  `feed_claimed` - the OPPONENT already owned it (alone). The blunt J5 quantity.
  `contested`    - both seats had meeples on it.

`FATE` of a feature: `claimers` = every player who ever put a meeple on it, and
        `points_to[p]` = every point it ever paid seat p, during-play completion
        plus terminal (incomplete-feature and farm) scoring. Both are reconciled
        against the true final scores; a game that fails to reconcile is dropped
        loudly, never quietly averaged.

`SHARED CREDIT`  points-per-buildup-touch needs a split rule or a 7-tile city gets
        counted 7 times. Rule: `credit_p(F) = points_to_p(F) * buildup_p(F) /
        n_tiles(F)`, i.e. each buildup touch earns the feature's payout pro-rata by
        the share of the feature's tiles it laid down while the feature was
        ownerless. It conserves total points and never exceeds them.

CAVEAT THAT MATTERS. `buildup_p(F)` counts touches by the CONTEMPORANEOUS claim
state of the component the tile joined, while `F` is the FINAL merged feature. A
field the human built ownerless for 20 turns that later merged into a field the
champion had already claimed is scored under the merged fate. That is the honest
decision-time-investment / terminal-outcome pairing, and it is exactly the
non-stationarity the term itself would have to price.

--------------------------------------------------------------------------------
RUNNING IT
--------------------------------------------------------------------------------
    .venv/bin/python scripts/analyzer/j13_pregate.py \
        --games measurement/e4_games --out measurement/j13_pregate_20260813

The rules profile is resolved FROM EACH ARCHIVE via `ev_loss.resolve_profile_name`
(never assumed). `CARCASSONNE_FIX_R9` is import-latched, so profiles are processed
one PER SUBPROCESS (<=3 here) and merged; the driver never runs more than
`--max-procs` at once.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "human_anchor"))

# MUST precede any `carcassonne_ai` import (leaf knobs are frozen at import).
import env_preamble  # noqa: E402,F401

SCHEMA = "carcassonne-analyzer-j13-pregate/v1"

# Touch kinds, in the order they are reported.
KINDS = ("buildup", "claim_now", "own_growth", "feed_claimed", "contested")
TERRAINS = ("city", "road", "cloister", "farm")
# The terrains a leaf term could plausibly reach with a tile-count value; farms
# are broken out everywhere because EVERY tile touches some field, so pooling
# farms with structures makes "fraction of plies that are buildup" meaningless.
STRUCTURAL = ("city", "road", "cloister")


# --------------------------------------------------------------------------- #
# persistent union-find over slots                                              #
# --------------------------------------------------------------------------- #
class DSU:
    """Union-find over hashable slot keys. Path-halving; union by size."""

    __slots__ = ("parent", "size")

    def __init__(self):
        self.parent: dict = {}
        self.size: dict = {}

    def add(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1
        return x

    def find(self, x):
        p = self.parent
        if x not in p:
            self.add(x)
            return x
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        return ra


# --------------------------------------------------------------------------- #
# one board -> the structural view this instrument needs                        #
# --------------------------------------------------------------------------- #
class View:
    """Everything about one board state, keyed by SLOT and by COMPONENT.

    `comp` ids are namespaced `(terrain, root)` tuples because flat_leaf's city /
    road / farm union-find label spaces are independent and their ints collide.
    Cloisters are singleton components `("cloister", r, c)`.
    """

    __slots__ = ("slot_comp", "comp_slots", "comp_coords", "comp_value",
                 "comp_finished", "comp_owners", "coord_slots", "decomp")

    def __init__(self):
        self.slot_comp: dict = {}
        self.comp_slots: dict = {}
        self.comp_coords: dict = {}
        self.comp_value: dict = {}
        self.comp_finished: dict = {}
        self.comp_owners: dict = {}     # comp -> {player: weighted meeple count}
        self.coord_slots: dict = {}     # (r, c) -> [slot, ...]
        self.decomp = None


def build_view(state) -> View:
    """One decompose pass -> a View. The only expensive call in the walk."""
    from carcassonne_ai.flat_leaf import (
        _city_points, _cloister_points, _meeple_weight, _road_points, decompose,
    )
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    d = decompose(state)
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0
    v = View()
    v.decomp = d

    def _reg(slot, comp, coord):
        v.slot_comp[slot] = comp
        v.comp_slots.setdefault(comp, []).append(slot)
        v.comp_coords.setdefault(comp, set()).add(coord)
        v.coord_slots.setdefault(coord, []).append(slot)

    for (r, c, side), root in d.city_side_root.items():
        _reg(("city", r, c, side), ("city", root), (r, c))
    for (r, c, side), root in d.road_side_root.items():
        _reg(("road", r, c, side), ("road", root), (r, c))
    for (r, c, side), root in d.farm_anypos_root.items():
        _reg(("farm", r, c, side), ("farm", root), (r, c))

    # cloisters: singleton components, one per placed chapel/flowers tile.
    for coord in state.placed_coords:
        r, c = coord.row, coord.column
        tile = board[r][c]
        if tile is None:
            continue
        if tile.get_type(Side.CENTER) in (TerrainType.CHAPEL, TerrainType.FLOWERS):
            _reg(("cloister", r, c), ("cloister", r, c), (r, c))

    # component coords for cities/roads come from the decomp (the slot pass above
    # already visits every one of them, but the decomp's sets are authoritative).
    for root, coords in d.city_root_coords.items():
        v.comp_coords[("city", root)] = set(coords)
    for root, coords in d.road_root_coords.items():
        v.comp_coords[("road", root)] = set(coords)

    # values: what the component would pay its owner if the game ended now.
    for root in d.city_root_coords:
        comp = ("city", root)
        v.comp_finished[comp] = bool(d.city_root_finished[root])
        v.comp_value[comp] = _city_points(d.city_root_coords[root],
                                          d.city_root_finished[root], board)
    for root in d.road_root_coords:
        comp = ("road", root)
        v.comp_finished[comp] = bool(d.road_root_finished[root])
        v.comp_value[comp] = _road_points(d.road_root_coords[root],
                                          d.road_root_finished[root], board)
    for root, nfin in d.farm_root_finished_cities.items():
        comp = ("farm", root)
        v.comp_finished[comp] = False          # a field never "completes"
        v.comp_value[comp] = 3 * int(nfin)
    for comp in list(v.comp_slots):
        if comp[0] == "cloister":
            _t, r, c = comp
            pts = _cloister_points(r, c, board, H, W)
            v.comp_value[comp] = pts
            v.comp_finished[comp] = pts == 9

    # owners: mirrors flat_leaf._final_scores' meeple->component matching exactly
    # (cities/roads by side root, farmers by farm_pos0_root, cloisters by tile).
    for player in range(state.players):
        for mp in state.placed_meeples[player]:
            comp = meeple_comp(state, mp, d)
            if comp is None:
                continue
            w = _meeple_weight(mp.meeple_type)
            v.comp_owners.setdefault(comp, {}).setdefault(player, 0)
            v.comp_owners[comp][player] += w
    _ = MeepleType  # imported for symmetry with flat_leaf; matching is via helper
    return v


def meeple_slot(state, mp):
    """The SLOT a placed meeple sits on, or None if the tile is gone (impossible)."""
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    cws = mp.coordinate_with_side
    r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
    tile = state.board[r][c]
    if tile is None:
        return None
    terrain = tile.get_type(side)
    if terrain == TerrainType.CITY:
        return ("city", r, c, side)
    if terrain == TerrainType.ROAD:
        return ("road", r, c, side)
    if terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
        return ("cloister", r, c)
    if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
        return ("farm", r, c, side)
    return None


def meeple_comp(state, mp, decomp):
    """The COMPONENT a placed meeple sits on, matched the way the engine matches.

    Farmers go through `farm_pos0_root` (== `FarmUtil.find_meeples`), NOT
    `farm_anypos_root`; the two agree on which component, and pos0 is the key the
    scorer uses, so this is the engine-faithful lookup.
    """
    slot = meeple_slot(state, mp)
    if slot is None:
        return None
    kind = slot[0]
    if kind == "cloister":
        return slot
    _k, r, c, side = slot
    if kind == "city":
        root = decomp.city_side_root.get((r, c, side))
    elif kind == "road":
        root = decomp.road_side_root.get((r, c, side))
    else:
        root = decomp.farm_pos0_root.get((r, c, side))
        if root is None:                      # defensive: any-position fallback
            root = decomp.farm_anypos_root.get((r, c, side))
    return None if root is None else (kind, root)


def _winners_of(counts: dict) -> list:
    """Players tied for the max weighted meeple count; [] if the comp is ownerless."""
    if not counts:
        return []
    m = max(counts.values())
    if m <= 0:
        return []
    return sorted(p for p, v in counts.items() if v == m)


# --------------------------------------------------------------------------- #
# the walk                                                                      #
# --------------------------------------------------------------------------- #
def replay_j13(deck_seed: int, actions, *, game_kwargs=None, recorded_scores=None,
               game_id=None, n_players_expected=2) -> dict:
    """Replay one game and emit its J13/J5 record. Deterministic, no search.

    Returns a dict with `touches` (one per (turn, actor, component)), `features`
    (one per persistent feature, with its fate), `integrity`, and per-seat
    aggregates. Raises on an illegal action or a score that does not reconcile.
    """
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    from carcassonne_ai.flat_leaf import _meeple_weight
    from carcassonne_ai.game_wrapper import Game

    actions = [int(a) for a in actions]
    gk = dict(game_kwargs or {})

    # ---- pass 1: true terminal scores (unstubbed) --------------------------- #
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=False, **gk)
    board = game.get_init_board()
    for a in actions:
        board, _ = game.get_next_state(board, a)
    final_scores = [int(x) for x in board.state.scores]

    # ---- pass 2: the walk, terminal scoring stubbed so meeples survive ------ #
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=False, **gk)
    board = game.get_init_board()
    n_players = int(board.state.players)

    puf = DSU()
    seen_slots: set = set()
    touches: list = []
    completions: list = []          # during-play scoring events
    claim_events: list = []         # (anchor_slot, turn, player)
    during_play = [0] * n_players
    turn = 0
    i = 0
    n_tile_plies = [0] * n_players
    n_pass_plies = [0] * n_players

    def _absorb(view: View):
        """Union every component of `view` into the persistent classes."""
        for slots in view.comp_slots.values():
            s0 = slots[0]
            puf.add(s0)
            for s in slots[1:]:
                puf.union(s0, s)

    # The engine scores a completed feature INSIDE the meeple ply
    # (`remove_meeples_and_update_score` -> `remove_meeples_and_collect_points`),
    # so a meeple placed and scored on the SAME turn is invisible to a
    # before/after diff of the turn. Record the removal directly instead: this
    # callback sees the state with the new meeple down and the points not yet
    # taken, which is the only moment the attribution is unambiguous.
    scoring_log: list = []
    orig_cfs = PointsCollector.count_final_scores
    orig_rm = PointsCollector.remove_meeples_and_collect_points

    def _record_removal(cls, game_state, coordinate):
        before_m = _meeple_index(game_state)
        before_s = [int(x) for x in game_state.scores]
        orig_rm(game_state=game_state, coordinate=coordinate)
        after_m = _meeple_index(game_state)
        after_s = [int(x) for x in game_state.scores]
        scoring_log.append({
            "meeples": before_m,
            "removed": [k for k in before_m if k not in after_m],
            "delta": [after_s[p] - before_s[p] for p in range(len(after_s))],
        })

    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
    PointsCollector.remove_meeples_and_collect_points = classmethod(_record_removal)
    try:
        view = build_view(board.state)          # the start tile is already down
        _absorb(view)
        seen_slots |= set(view.slot_comp)
        prev_view = view

        while i < len(actions):
            st = board.state
            actor = int(st.current_player)
            k_rem = len(st.deck)
            coords_before = {(c.row, c.column) for c in st.placed_coords}
            meeples_before = _meeple_index(st)
            scoring_log.clear()

            # --- ply 1 of the turn: the tile ply (or a TILES-phase pass) ------ #
            board, _ = game.get_next_state(board, actions[i])
            i += 1
            st1 = board.state
            coords_after = {(c.row, c.column) for c in st1.placed_coords}
            new_coords = coords_after - coords_before

            if new_coords:
                n_tile_plies[actor] += 1
                view = build_view(st1)
                _absorb(view)
            else:
                n_pass_plies[actor] += 1
                view = prev_view

            # --- the rest of the turn (the meeple ply, if any) ---------------- #
            while i < len(actions):
                if board.state.is_terminated():
                    break
                if int(board.state.current_player) != actor:
                    break
                if board.state.phase == GamePhase.TILES:
                    break
                board, _ = game.get_next_state(board, actions[i])
                i += 1

            st2 = board.state
            # `meeples_mid` = the meeple set at scoring time: the actor's meeple is
            # down and nothing has been taken off yet. Falls back to the end-of-turn
            # set on a turn where no scoring pass ran.
            meeples_mid = (scoring_log[0]["meeples"] if scoring_log
                           else _meeple_index(st2))
            placed_keys = [k for k in meeples_mid if k not in meeples_before]

            # which component did the actor claim this turn (if any)?
            claimed_comp = None
            for k in placed_keys:
                mp = meeples_mid[k]
                comp = meeple_comp(st2, mp, view.decomp)
                if comp is not None:
                    claimed_comp = comp
                    anchor = meeple_slot(st2, mp)
                    if anchor is not None:
                        claim_events.append((anchor, turn, int(k[0])))
                    break

            # --- the touches --------------------------------------------------- #
            if new_coords:
                for coord in sorted(new_coords):
                    comps: dict = {}
                    for slot in view.coord_slots.get(coord, ()):  # slots of the new tile
                        comps.setdefault(view.slot_comp[slot], []).append(slot)
                    # a cloister the new tile FILLS IN but is not part of: the
                    # 3x3 neighbourhood. This is the purest "grow a structure you
                    # do not own" move in the game, so it must be a touch.
                    r0, c0 = coord
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            comp = ("cloister", r0 + dr, c0 + dc)
                            if comp not in view.comp_slots or comp in comps:
                                continue
                            # a cloister already at 9 cannot be grown; counting it
                            # would inflate the buildup base rate with no-ops.
                            if (prev_view is not None
                                    and prev_view.comp_value.get(comp, 0) >= 9):
                                continue
                            comps[comp] = list(view.comp_slots[comp])
                    for comp, slots in comps.items():
                        touches.append(_classify_touch(
                            comp, slots, view, prev_view, seen_slots, actor,
                            claimed_comp, turn, k_rem, n_players))
                seen_slots |= set(view.slot_comp)

            # --- during-play completions (the recorded scoring passes) -------- #
            for entry in scoring_log:
                by_comp: dict = {}
                for k in entry["removed"]:
                    mp = entry["meeples"][k]
                    comp = meeple_comp(st1, mp, view.decomp)
                    if comp is None:
                        continue
                    by_comp.setdefault(comp, {}).setdefault(int(k[0]), 0)
                    by_comp[comp][int(k[0])] += _meeple_weight(mp.meeple_type)
                got = [0] * n_players
                for comp, counts in by_comp.items():
                    winners = _winners_of(counts)
                    pts = int(view.comp_value.get(comp, 0))
                    anchor = view.comp_slots[comp][0]
                    completions.append({
                        "anchor": anchor, "terrain": comp[0], "turn": turn,
                        "points": pts, "winners": winners,
                        "n_tiles": len(view.comp_coords.get(comp, ())),
                    })
                    for w in winners:
                        during_play[w] += pts
                        got[w] += pts
                if got != [int(x) for x in entry["delta"][:n_players]]:
                    raise AssertionError(
                        f"game {game_id} turn {turn}: reconstructed during-play "
                        f"award {got} != engine delta {entry['delta']}. The "
                        "component attribution disagrees with the engine.")

            if new_coords:
                prev_view = view
            turn += 1
            if board.state.is_terminated():
                break

        term_state = board.state
        final_view = build_view(term_state)
        _absorb(final_view)
    finally:
        PointsCollector.count_final_scores = orig_cfs
        PointsCollector.remove_meeples_and_collect_points = orig_rm

    # ---- terminal attribution (mirror of flat_leaf._final_scores) ------------ #
    terminal = [0] * n_players
    terminal_records = []
    for comp, counts in final_view.comp_owners.items():
        winners = _winners_of(counts)
        if not winners:
            continue
        pts = int(final_view.comp_value.get(comp, 0))
        terminal_records.append({
            "anchor": final_view.comp_slots[comp][0], "terrain": comp[0],
            "points": pts, "winners": winners,
            "n_tiles": len(final_view.comp_coords.get(comp, ())),
            "finished": bool(final_view.comp_finished.get(comp, False)),
        })
        for w in winners:
            terminal[w] += pts

    # ---- the feature ledger -------------------------------------------------- #
    features: dict = {}
    for comp, slots in final_view.comp_slots.items():
        fid = puf.find(slots[0])
        rec = features.get(fid)
        if rec is None:
            rec = features[fid] = {
                "terrain": comp[0], "n_tiles": 0, "finished": False,
                "points_to": [0] * n_players, "claimers": set(),
                "first_claim_turn": None, "first_claim_player": None,
                "buildup_by": [0] * n_players, "touches_by": [0] * n_players,
                "value_final": 0,
            }
        rec["n_tiles"] = max(rec["n_tiles"], len(final_view.comp_coords.get(comp, ())))
        rec["finished"] = rec["finished"] or bool(final_view.comp_finished.get(comp, False))
        rec["value_final"] = max(rec["value_final"], int(final_view.comp_value.get(comp, 0)))

    def _fid(anchor):
        return puf.find(anchor)

    for ev in completions:
        rec = features.get(_fid(ev["anchor"]))
        if rec is None:
            continue
        for w in ev["winners"]:
            rec["points_to"][w] += int(ev["points"])
    for ev in terminal_records:
        rec = features.get(_fid(ev["anchor"]))
        if rec is None:
            continue
        for w in ev["winners"]:
            rec["points_to"][w] += int(ev["points"])
    for anchor, t, p in claim_events:
        rec = features.get(_fid(anchor))
        if rec is None:
            continue
        rec["claimers"].add(int(p))
        if rec["first_claim_turn"] is None or t < rec["first_claim_turn"]:
            rec["first_claim_turn"] = int(t)
            rec["first_claim_player"] = int(p)
    for t in touches:
        rec = features.get(_fid(t["anchor"]))
        if rec is None:
            continue
        rec["touches_by"][t["actor"]] += 1
        if t["kind"] == "buildup":
            rec["buildup_by"][t["actor"]] += 1
        t["feature"] = _fid(t["anchor"])

    # ---- integrity ----------------------------------------------------------- #
    reconstructed = [during_play[p] + terminal[p] for p in range(n_players)]
    integrity = {
        "n_plies": len(actions),
        "n_turns": turn,
        "final_scores": final_scores,
        "recorded_scores": list(recorded_scores) if recorded_scores else None,
        "replay_scores_match": (None if not recorded_scores
                                else [int(x) for x in recorded_scores] == final_scores),
        "during_play": during_play,
        "terminal": terminal,
        "reconstructed_scores": reconstructed,
        "attribution_reconciles": reconstructed == final_scores,
        "n_features": len(features),
        "n_touches": len(touches),
    }
    if not integrity["attribution_reconciles"]:
        raise AssertionError(
            f"game {game_id}: per-feature attribution {reconstructed} != final "
            f"scores {final_scores} (during={during_play}, terminal={terminal}). "
            "FAILING LOUD: an unreconciled split silently mis-prices every rate.")
    if n_players != n_players_expected:
        raise AssertionError(f"game {game_id}: {n_players} players, expected "
                             f"{n_players_expected}")

    return {
        "game_id": game_id,
        "deck_seed": int(deck_seed),
        "n_players": n_players,
        "n_tile_plies": n_tile_plies,
        "n_pass_plies": n_pass_plies,
        "integrity": integrity,
        "touches": touches,
        "features": {k: _feature_json(v) for k, v in features.items()},
        "aggregate": aggregate_game(touches, features, n_tile_plies, n_players),
    }


def _feature_json(rec):
    out = dict(rec)
    out["claimers"] = sorted(rec["claimers"])
    return out


def _meeple_index(state) -> dict:
    """(player, type, r, c, side) -> the MeeplePosition object. Keys are unique:
    the engine never allows two meeples on one tile side."""
    out = {}
    for p, ms in enumerate(state.placed_meeples):
        for mp in ms:
            cws = mp.coordinate_with_side
            out[(p, mp.meeple_type.value, cws.coordinate.row,
                 cws.coordinate.column, cws.side.value)] = mp
    return out


def _classify_touch(comp, slots, view, prev_view, seen_slots, actor, claimed_comp,
                    turn, k_rem, n_players) -> dict:
    """One (turn, actor, component) touch record."""
    owners = view.comp_owners.get(comp, {})
    owner_set = {p for p, v in owners.items() if v > 0}
    opp = 1 - actor if n_players == 2 else None

    if not owner_set:
        kind = "claim_now" if comp == claimed_comp else "buildup"
    elif owner_set == {actor}:
        kind = "own_growth"
    elif opp is not None and owner_set == {opp}:
        kind = "feed_claimed"
    else:
        kind = "contested"

    pre_slots = [s for s in view.comp_slots[comp] if s in seen_slots]
    value_after = int(view.comp_value.get(comp, 0))
    value_before = 0
    if prev_view is not None and pre_slots:
        prev_comps = {prev_view.slot_comp[s] for s in pre_slots
                      if s in prev_view.slot_comp}
        value_before = sum(int(prev_view.comp_value.get(pc, 0)) for pc in prev_comps)

    return {
        "turn": int(turn), "actor": int(actor), "kind": kind, "terrain": comp[0],
        "k_remaining": int(k_rem),
        "anchor": slots[0] if slots else view.comp_slots[comp][0],
        "is_creation": not pre_slots,
        "value_before": value_before, "value_after": value_after,
        "value_delta": value_after - value_before,
        "comp_tiles": len(view.comp_coords.get(comp, ())),
        "owners": sorted(owner_set),
    }


# --------------------------------------------------------------------------- #
# per-game aggregation                                                          #
# --------------------------------------------------------------------------- #
def _fate(rec, p, n_players):
    """Fate of a feature relative to seat `p`, by CLAIM and by POINTS."""
    opp = 1 - p if n_players == 2 else None
    cl = set(rec["claimers"])
    if not cl:
        fate_claim = "none"
    elif cl == {p}:
        fate_claim = "self"
    elif opp is not None and cl == {opp}:
        fate_claim = "opp"
    else:
        fate_claim = "both"
    pts = rec["points_to"]
    ps, po = int(pts[p]), int(pts[opp]) if opp is not None else 0
    if ps <= 0 and po <= 0:
        fate_pts = "none"
    elif ps > 0 and po <= 0:
        fate_pts = "self"
    elif po > 0 and ps <= 0:
        fate_pts = "opp"
    else:
        fate_pts = "both"
    return fate_claim, fate_pts


def aggregate_game(touches, features, n_tile_plies, n_players) -> dict:
    """Per-seat scalars for ONE game. The unit of the corpus statistics."""
    per = []
    for p in range(n_players):
        opp = 1 - p if n_players == 2 else None
        row = {
            "tile_plies": int(n_tile_plies[p]),
            "touches": 0,
            "kind_counts": {k: 0 for k in KINDS},
            "kind_counts_structural": {k: 0 for k in KINDS},
            "buildup_by_terrain": {t: 0 for t in TERRAINS},
            "buildup_plies": 0,
            "buildup_plies_structural": 0,
            "unclaimed_value_added": 0,
            "unclaimed_value_added_structural": 0,
            "fed_value_added": 0,          # value added to an ALREADY-opp-owned comp
            "buildup_fate_claim": {"self": 0, "opp": 0, "both": 0, "none": 0},
            "buildup_fate_claim_structural": {"self": 0, "opp": 0, "both": 0, "none": 0},
            "buildup_fate_points": {"self": 0, "opp": 0, "both": 0, "none": 0},
            "fate_by_terrain": {t: {"self": 0, "opp": 0, "both": 0, "none": 0}
                                for t in TERRAINS},
            "credit_self": 0.0,
            "credit_opp": 0.0,
            "credit_self_structural": 0.0,
            "credit_opp_structural": 0.0,
        }
        per.append(row)

    turns_with_buildup = {p: set() for p in range(n_players)}
    turns_with_buildup_s = {p: set() for p in range(n_players)}
    for t in touches:
        p = t["actor"]
        row = per[p]
        row["touches"] += 1
        row["kind_counts"][t["kind"]] += 1
        struct = t["terrain"] in STRUCTURAL
        if struct:
            row["kind_counts_structural"][t["kind"]] += 1
        if t["kind"] == "buildup":
            row["buildup_by_terrain"][t["terrain"]] += 1
            row["unclaimed_value_added"] += int(t["value_delta"])
            turns_with_buildup[p].add(t["turn"])
            if struct:
                row["unclaimed_value_added_structural"] += int(t["value_delta"])
                turns_with_buildup_s[p].add(t["turn"])
            rec = features.get(t.get("feature"))
            if rec is not None:
                fc, fp = _fate(rec, p, n_players)
                row["buildup_fate_claim"][fc] += 1
                row["buildup_fate_points"][fp] += 1
                row["fate_by_terrain"][t["terrain"]][fc] += 1
                if struct:
                    row["buildup_fate_claim_structural"][fc] += 1
        elif t["kind"] == "feed_claimed":
            row["fed_value_added"] += int(t["value_delta"])

    for p in range(n_players):
        per[p]["buildup_plies"] = len(turns_with_buildup[p])
        per[p]["buildup_plies_structural"] = len(turns_with_buildup_s[p])

    # shared credit: points_to_p(F) * buildup_p(F) / n_tiles(F)
    for rec in features.values():
        n_tiles = max(1, int(rec["n_tiles"]))
        for p in range(n_players):
            b = int(rec["buildup_by"][p])
            if b <= 0:
                continue
            share = b / n_tiles
            opp = 1 - p if n_players == 2 else None
            per[p]["credit_self"] += float(rec["points_to"][p]) * share
            if opp is not None:
                per[p]["credit_opp"] += float(rec["points_to"][opp]) * share
            if rec["terrain"] in STRUCTURAL:
                per[p]["credit_self_structural"] += float(rec["points_to"][p]) * share
                if opp is not None:
                    per[p]["credit_opp_structural"] += (
                        float(rec["points_to"][opp]) * share)

    # THE MECHANISM TEST, seat-symmetric and free of the meeple-supply confound:
    # among features exactly ONE player ever claimed, did the player who laid more
    # of its ownerless tiles get it? A rate of 0.5 (excluding ties) means buildup
    # carries NO claim signal at all, which is the strongest single argument
    # against a P(claim)-weighted leaf term.
    race = {"n": 0, "builder_won": 0, "tie": 0, "builder_lost": 0,
            "n_struct": 0, "builder_won_struct": 0, "tie_struct": 0,
            "builder_lost_struct": 0}
    for rec in features.values():
        cl = set(rec["claimers"])
        if len(cl) != 1 or n_players != 2:
            continue
        p = next(iter(cl))
        a, b = int(rec["buildup_by"][p]), int(rec["buildup_by"][1 - p])
        key = "builder_won" if a > b else ("tie" if a == b else "builder_lost")
        race["n"] += 1
        race[key] += 1
        if rec["terrain"] in STRUCTURAL:
            race["n_struct"] += 1
            race[key + "_struct"] += 1

    # base rates over FEATURES (seat-independent)
    feat = {"n": 0, "by_terrain": {t: 0 for t in TERRAINS},
            "ever_claimed": 0, "never_claimed": 0,
            "never_claimed_by_terrain": {t: 0 for t in TERRAINS},
            "points_total": 0,
            "points_through_unclaimed_buildup": 0.0,
            "tiles_before_first_claim": [],
            "value_left_on_never_claimed": 0}
    for fid, rec in features.items():
        feat["n"] += 1
        feat["by_terrain"][rec["terrain"]] += 1
        pts = sum(int(x) for x in rec["points_to"])
        feat["points_total"] += pts
        if rec["claimers"]:
            feat["ever_claimed"] += 1
            b = sum(int(x) for x in rec["buildup_by"])
            n_tiles = max(1, int(rec["n_tiles"]))
            feat["points_through_unclaimed_buildup"] += pts * (b / n_tiles)
            feat["tiles_before_first_claim"].append(int(b))
        else:
            feat["never_claimed"] += 1
            feat["never_claimed_by_terrain"][rec["terrain"]] += 1
            feat["value_left_on_never_claimed"] += int(rec["value_final"])
    return {"per_seat": per, "features": feat, "claim_race": race}


# --------------------------------------------------------------------------- #
# corpus statistics                                                             #
# --------------------------------------------------------------------------- #
def _mean_sem(xs):
    xs = [float(x) for x in xs]
    n = len(xs)
    if n == 0:
        return {"n": 0, "mean": None, "sem": None}
    m = statistics.fmean(xs)
    if n == 1:
        return {"n": 1, "mean": m, "sem": None}
    sd = statistics.stdev(xs)
    return {"n": n, "mean": m, "sd": sd, "sem": sd / math.sqrt(n)}


def _paired(xs, ys):
    """Paired within-game difference xs - ys (same board, same deck, same length).

    This is the ONLY contrast the corpus supports well: the two seats share every
    nuisance variable, so the game-level variance cancels."""
    d = [float(a) - float(b) for a, b in zip(xs, ys)]
    st = _mean_sem(d)
    st["z"] = (None if not st.get("sem") else st["mean"] / st["sem"])
    return st


def _rate(num, den):
    return None if den <= 0 else num / den


def corpus_stats(games, human_seat=0):
    """Aggregate per-game records into the reported statistics."""
    out = {"n_games": len(games)}
    seats = {"human": human_seat, "champion": 1 - human_seat}

    # ---- pooled (all plies in the epoch), and per-game for uncertainty ------- #
    pooled = {}
    pergame = {}
    for label, s in seats.items():
        agg = [g["aggregate"]["per_seat"][s] for g in games]
        tot = {
            "tile_plies": sum(a["tile_plies"] for a in agg),
            "touches": sum(a["touches"] for a in agg),
            "buildup_plies": sum(a["buildup_plies"] for a in agg),
            "buildup_plies_structural": sum(a["buildup_plies_structural"] for a in agg),
            "kind_counts": {k: sum(a["kind_counts"][k] for a in agg) for k in KINDS},
            "kind_counts_structural": {
                k: sum(a["kind_counts_structural"][k] for a in agg) for k in KINDS},
            "buildup_by_terrain": {
                t: sum(a["buildup_by_terrain"][t] for a in agg) for t in TERRAINS},
            "fate_claim": {f: sum(a["buildup_fate_claim"][f] for a in agg)
                           for f in ("self", "opp", "both", "none")},
            "fate_claim_structural": {
                f: sum(a["buildup_fate_claim_structural"][f] for a in agg)
                for f in ("self", "opp", "both", "none")},
            "fate_points": {f: sum(a["buildup_fate_points"][f] for a in agg)
                            for f in ("self", "opp", "both", "none")},
            "fate_by_terrain": {
                t: {f: sum(a["fate_by_terrain"][t][f] for a in agg)
                    for f in ("self", "opp", "both", "none")} for t in TERRAINS},
            "unclaimed_value_added": sum(a["unclaimed_value_added"] for a in agg),
            "unclaimed_value_added_structural":
                sum(a["unclaimed_value_added_structural"] for a in agg),
            "fed_value_added": sum(a["fed_value_added"] for a in agg),
            "credit_self": sum(a["credit_self"] for a in agg),
            "credit_opp": sum(a["credit_opp"] for a in agg),
            "credit_self_structural": sum(a["credit_self_structural"] for a in agg),
            "credit_opp_structural": sum(a["credit_opp_structural"] for a in agg),
        }
        nb = tot["kind_counts"]["buildup"]
        nbs = tot["kind_counts_structural"]["buildup"]
        fc, fcs = tot["fate_claim"], tot["fate_claim_structural"]
        tot["rates"] = {
            "buildup_ply_share": _rate(tot["buildup_plies"], tot["tile_plies"]),
            "buildup_ply_share_structural":
                _rate(tot["buildup_plies_structural"], tot["tile_plies"]),
            "conversion_self": _rate(fc["self"], nb),
            "feed_opp": _rate(fc["opp"], nb),
            "contested_both": _rate(fc["both"], nb),
            "never_claimed": _rate(fc["none"], nb),
            "conversion_self_structural": _rate(fcs["self"], nbs),
            "feed_opp_structural": _rate(fcs["opp"], nbs),
            "never_claimed_structural": _rate(fcs["none"], nbs),
            "points_per_buildup_touch_self": _rate(tot["credit_self"], nb),
            "points_per_buildup_touch_opp": _rate(tot["credit_opp"], nb),
            "net_points_per_buildup_touch":
                None if nb == 0 else (tot["credit_self"] - tot["credit_opp"]) / nb,
            "points_per_buildup_touch_self_structural":
                _rate(tot["credit_self_structural"], nbs),
            "points_per_buildup_touch_opp_structural":
                _rate(tot["credit_opp_structural"], nbs),
            "net_points_per_buildup_touch_structural":
                None if nbs == 0 else
                (tot["credit_self_structural"] - tot["credit_opp_structural"]) / nbs,
            "feed_claimed_share": _rate(tot["kind_counts"]["feed_claimed"],
                                        tot["touches"]),
            "feed_claimed_share_structural":
                _rate(tot["kind_counts_structural"]["feed_claimed"],
                      sum(tot["kind_counts_structural"].values())),
        }
        pooled[label] = tot

        # per-game versions of each headline rate (for SEM and pairing)
        pg = {}
        for key, fn in _PERGAME_METRICS.items():
            pg[key] = [fn(a) for a in agg]
        pergame[label] = pg

    out["pooled"] = pooled
    out["per_game"] = {
        label: {k: _mean_sem([x for x in v if x is not None])
                for k, v in pg.items()}
        for label, pg in pergame.items()
    }
    out["paired_human_minus_champion"] = {}
    for k in _PERGAME_METRICS:
        hs, cs = pergame["human"][k], pergame["champion"][k]
        pairs = [(a, b) for a, b in zip(hs, cs) if a is not None and b is not None]
        if not pairs:
            out["paired_human_minus_champion"][k] = {"n": 0}
            continue
        out["paired_human_minus_champion"][k] = _paired([a for a, _ in pairs],
                                                        [b for _, b in pairs])

    # ---- feature base rates (seat independent) ------------------------------ #
    fr = {"n_features": 0, "by_terrain": {t: 0 for t in TERRAINS},
          "ever_claimed": 0, "never_claimed": 0,
          "never_claimed_by_terrain": {t: 0 for t in TERRAINS},
          "points_total": 0, "points_through_unclaimed_buildup": 0.0,
          "value_left_on_never_claimed": 0}
    tbc = []
    for g in games:
        f = g["aggregate"]["features"]
        fr["n_features"] += f["n"]
        fr["ever_claimed"] += f["ever_claimed"]
        fr["never_claimed"] += f["never_claimed"]
        fr["points_total"] += f["points_total"]
        fr["points_through_unclaimed_buildup"] += f["points_through_unclaimed_buildup"]
        fr["value_left_on_never_claimed"] += f["value_left_on_never_claimed"]
        for t in TERRAINS:
            fr["by_terrain"][t] += f["by_terrain"][t]
            fr["never_claimed_by_terrain"][t] += f["never_claimed_by_terrain"][t]
        tbc.extend(f["tiles_before_first_claim"])
    fr["claim_rate"] = _rate(fr["ever_claimed"], fr["n_features"])
    fr["points_share_through_unclaimed_buildup"] = _rate(
        fr["points_through_unclaimed_buildup"], fr["points_total"])
    if tbc:
        tbc_sorted = sorted(tbc)
        fr["tiles_before_first_claim"] = {
            "n": len(tbc), "mean": statistics.fmean(tbc),
            "median": statistics.median(tbc_sorted),
            "share_zero": sum(1 for x in tbc if x == 0) / len(tbc),
            "share_ge2": sum(1 for x in tbc if x >= 2) / len(tbc),
            "p90": tbc_sorted[min(len(tbc) - 1, int(0.90 * len(tbc)))],
        }
    out["feature_base_rates"] = fr

    race = {k: 0 for k in ("n", "builder_won", "tie", "builder_lost",
                           "n_struct", "builder_won_struct", "tie_struct",
                           "builder_lost_struct")}
    for g in games:
        for k in race:
            race[k] += g["aggregate"]["claim_race"][k]
    dec = race["builder_won"] + race["builder_lost"]
    dec_s = race["builder_won_struct"] + race["builder_lost_struct"]
    race["builder_won_share_decided"] = _rate(race["builder_won"], dec)
    race["builder_won_share_decided_structural"] = _rate(
        race["builder_won_struct"], dec_s)
    race["n_decided"] = dec
    race["n_decided_structural"] = dec_s
    # binomial z against the 0.5 null (no claim signal in buildup)
    for key, w, n in (("z_vs_half", race["builder_won"], dec),
                      ("z_vs_half_structural", race["builder_won_struct"], dec_s)):
        race[key] = (None if n <= 0 else
                     (w - 0.5 * n) / math.sqrt(0.25 * n))
    out["claim_race"] = race
    return out


# per-game metric extractors (each takes ONE seat's per-game aggregate row)
def _m_buildup_share(a):
    return _rate(a["buildup_plies"], a["tile_plies"])


def _m_buildup_share_s(a):
    return _rate(a["buildup_plies_structural"], a["tile_plies"])


def _m_conv(a):
    return _rate(a["buildup_fate_claim"]["self"], a["kind_counts"]["buildup"])


def _m_feed(a):
    return _rate(a["buildup_fate_claim"]["opp"], a["kind_counts"]["buildup"])


def _m_none(a):
    return _rate(a["buildup_fate_claim"]["none"], a["kind_counts"]["buildup"])


def _m_conv_s(a):
    return _rate(a["buildup_fate_claim_structural"]["self"],
                 a["kind_counts_structural"]["buildup"])


def _m_feed_s(a):
    return _rate(a["buildup_fate_claim_structural"]["opp"],
                 a["kind_counts_structural"]["buildup"])


def _m_ppb_self(a):
    return _rate(a["credit_self"], a["kind_counts"]["buildup"])


def _m_ppb_opp(a):
    return _rate(a["credit_opp"], a["kind_counts"]["buildup"])


def _m_ppb_net(a):
    n = a["kind_counts"]["buildup"]
    return None if n == 0 else (a["credit_self"] - a["credit_opp"]) / n


def _m_ppb_net_s(a):
    n = a["kind_counts_structural"]["buildup"]
    return None if n == 0 else (
        a["credit_self_structural"] - a["credit_opp_structural"]) / n


def _m_ppb_self_s(a):
    return _rate(a["credit_self_structural"], a["kind_counts_structural"]["buildup"])


def _m_ppb_opp_s(a):
    return _rate(a["credit_opp_structural"], a["kind_counts_structural"]["buildup"])


def _m_feed_claimed_share(a):
    return _rate(a["kind_counts"]["feed_claimed"], a["touches"])


def _m_unclaimed_value(a):
    return _rate(a["unclaimed_value_added"], a["tile_plies"])


def _m_unclaimed_value_s(a):
    return _rate(a["unclaimed_value_added_structural"], a["tile_plies"])


_PERGAME_METRICS = {
    "buildup_ply_share": _m_buildup_share,
    "buildup_ply_share_structural": _m_buildup_share_s,
    "conversion_self": _m_conv,
    "feed_opp": _m_feed,
    "never_claimed": _m_none,
    "conversion_self_structural": _m_conv_s,
    "feed_opp_structural": _m_feed_s,
    "points_per_buildup_touch_self": _m_ppb_self,
    "points_per_buildup_touch_opp": _m_ppb_opp,
    "net_points_per_buildup_touch": _m_ppb_net,
    "points_per_buildup_touch_self_structural": _m_ppb_self_s,
    "points_per_buildup_touch_opp_structural": _m_ppb_opp_s,
    "net_points_per_buildup_touch_structural": _m_ppb_net_s,
    "feed_claimed_share": _m_feed_claimed_share,
    "unclaimed_value_added_per_ply": _m_unclaimed_value,
    "unclaimed_value_added_per_ply_structural": _m_unclaimed_value_s,
}


# --------------------------------------------------------------------------- #
# driver                                                                        #
# --------------------------------------------------------------------------- #
def resolve_corpus(games_dir):
    """[(path, profile_name, archive_dict)] — profile resolved FROM the archive.

    Imports only `carcassonne_ai.rules_profile` (cheap, no engine, no R9 latch),
    so it is safe to call before `prepare_env`.

    ⚠️ Archives NOT played against the champion are excluded, loudly: since the
    app gained the remote-Carcasum opponent (2026-08-30) this directory can hold
    games the champion never played. `scripts/e4_archives` owns that gate."""
    import sys as _sys

    if str(REPO / "scripts") not in _sys.path:
        _sys.path.insert(0, str(REPO / "scripts"))
    import e4_archives                                  # noqa: PLC0415

    from ev_loss import load_archive, resolve_profile_name
    rows = []
    for p in sorted(Path(games_dir).glob("*.json")):
        arch = load_archive(p)
        why = e4_archives.rejection_reason(arch["provenance"])
        if why is not None:
            _sys.stderr.write(f"[j13_pregate] EXCLUDED {p.name}: {why}\n")
            continue
        prof = resolve_profile_name(arch["provenance"])
        rows.append((str(p), prof, arch))
    return rows


def run_profile(games_dir, profile, out_path):
    """Process every archive of ONE rules profile in THIS process (R9 is latched)."""
    from ev_loss import prepare_env
    env_stamp = prepare_env(profile)                    # must precede the engine import
    from carcassonne_ai import rules_profile
    prof = rules_profile.activate(profile)

    rows = [r for r in resolve_corpus(games_dir) if r[1] == profile]
    games = []
    for path, _p, arch in rows:
        rec = replay_j13(arch["deck_seed"], arch["actions"],
                         game_kwargs=prof.game_kwargs(),
                         recorded_scores=arch["recorded_scores"],
                         game_id=Path(path).stem)
        rec["path"] = path
        rec["profile"] = profile
        rec["human_player"] = int(arch["human_player"])
        rec["finished_at"] = arch["provenance"].get("finished_at")
        rec["champion_id"] = arch["provenance"].get("champion_id")
        # touches/features are large; keep only what the aggregation needs.
        rec.pop("touches", None)
        rec.pop("features", None)
        games.append(rec)
        print(f"[j13] {profile} {Path(path).name}: "
              f"turns={rec['integrity']['n_turns']} "
              f"features={rec['integrity']['n_features']} "
              f"touches={rec['integrity']['n_touches']} "
              f"replay_ok={rec['integrity']['replay_scores_match']} "
              f"recon={rec['integrity']['attribution_reconciles']}", flush=True)
    payload = {"schema": SCHEMA, "profile": profile, "env": env_stamp,
               "game_kwargs": {k: str(v) for k, v in prof.game_kwargs().items()},
               "games": games}
    Path(out_path).write_text(json.dumps(payload, default=str))
    return payload


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--games", default="measurement/e4_games")
    ap.add_argument("--out", default="measurement/j13_pregate_20260813")
    ap.add_argument("--profile", default=None,
                    help="internal: process ONE profile in this process")
    ap.add_argument("--raw-out", default=None, help="internal: per-profile json")
    ap.add_argument("--max-procs", type=int, default=3,
                    help="LOCAL is busy; keep this <= 3")
    args = ap.parse_args()

    if args.profile:
        run_profile(args.games, args.profile, args.raw_out)
        return

    out = Path(args.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    rows = resolve_corpus(args.games)
    by_prof: dict = {}
    for path, prof, _a in rows:
        by_prof.setdefault(prof, []).append(path)
    print(f"[j13] corpus: {len(rows)} archives, profiles="
          f"{ {k: len(v) for k, v in by_prof.items()} }", flush=True)

    # R9 is import-latched => one subprocess per profile.
    procs, raws = [], {}
    for prof in sorted(by_prof):
        raw = out / "raw" / f"{prof}.json"
        raws[prof] = raw
        cmd = [sys.executable, str(Path(__file__).resolve()),
               "--games", str(args.games), "--profile", prof, "--raw-out", str(raw)]
        while len([p for p in procs if p.poll() is None]) >= max(1, args.max_procs):
            procs[0].wait()
            procs.pop(0)
        procs.append(subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parents[2])))
    for p in procs:
        if p.wait() != 0:
            raise SystemExit(f"[j13] subprocess failed with rc={p.returncode}")

    epochs = {}
    all_games = []
    for prof, raw in raws.items():
        payload = json.loads(Path(raw).read_text())
        gs = payload["games"]
        all_games.extend(gs)
        epochs[prof] = {"n_games": len(gs), "stats": corpus_stats(gs)}

    verdict = {
        "schema": SCHEMA,
        "generated": "2026-08-13",
        "corpus": str(args.games),
        "n_archives": len(rows),
        "profiles": {k: len(v) for k, v in by_prof.items()},
        "integrity": {
            "replay_scores_match_all": all(
                g["integrity"]["replay_scores_match"] is True for g in all_games),
            "attribution_reconciles_all": all(
                g["integrity"]["attribution_reconciles"] for g in all_games),
            "n_games": len(all_games),
        },
        "epochs": epochs,
        "pooled_all_epochs": corpus_stats(all_games),
        "caveats": [
            "descriptive only: 0 games played, no results.csv row, no band, no claim id",
            "outcome-conditioned selection: buildup->claim conversion CANNOT be read causally",
            "one human, 26 games, 3 rules epochs; headline is the fixed_v1 epoch (n=23)",
            "buildup is classified by the CONTEMPORANEOUS component's claim state; "
            "fate is the FINAL merged feature",
        ],
    }
    (out / "VERDICT.json").write_text(json.dumps(verdict, indent=1, default=str))
    print(f"[j13] wrote {out/'VERDICT.json'}")
    return verdict


if __name__ == "__main__":
    os.nice(19)
    main()
