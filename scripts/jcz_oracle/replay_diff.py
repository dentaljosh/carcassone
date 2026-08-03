#!/usr/bin/env python3
"""F9 / D1 — the JCloisterZone runtime replay oracle.

Feeds a recorded game — ``(deck_seed, actions)``, the lossless archive format of
``scripts/measurement_infra/root_replay.py`` — to BOTH engines in lockstep and
diffs, per ply:

  * the **legal-move set** (tile placements: position x rotation; meeple slots,
    canonicalised to JCZ's ``(feature, location)`` granularity),
  * the **running scores**,
  * the **feature partition** — every Field / City / Road as its set of
    (tile, half-edge or edge) atoms.

Our deck order is handed to JCZ verbatim via ``ForcedDrawTilePack``, so no RNG
matching happens anywhere: the two engines see the same tiles in the same order
by construction.

## Expected divergence is CLASSIFIED, not failed on

The 2026-08-02 rules audit names five places our engine knowingly departs from
retail/JCZ. A harness that aborted on the first one would be useless, so each is
given a class and counted; anything OUTSIDE the classified set is a REAL
divergence and exits non-zero.

| class | what it is | disappears under |
|---|---|---|
| ``START_TILE_PLY`` | our first tile is a *player move* at ``starting_position``; JCZ (and retail) pre-place a fixed D tile | ``fixed_v1`` (A4 retail start) |
| ``START_TILE_MEEPLE`` | …and that player may put a meeple on it, which JCZ has no ply to express | ``fixed_v1`` |
| ``WALL_LEGALITY`` | JCZ offers a placement we don't: our board is a 35x35 grid with the start tile 6 rows from the top edge, JCZ's is unbounded | never fully — see below |
| ``WINDOW_OVERFLOW`` | a placement our 25x25 *action space* cannot encode (a representation cap, not a rules cap) | never — see below |
| ``UNPLACEABLE_TURN_LOSS`` | our TILES-phase Pass discards the tile **and hands over the turn**; retail/JCZ redraw with the same player | ``fixed_v1`` (A3 redraw) |
| ``SCORE_TIMING`` | a running-score mismatch that reconciles by the terminal state — the RF-D-1 cloister scan drift defers ~9.6% of completions to the endgame pass | ``fixed_v1`` (A2 fixed scan) |
| ``FARM_ATOM_SET`` / ``FARM_PARTITION`` | R9: ``city_top_straight_road`` claims two field half-edges lying on its own city edge, so ``find_farm`` walks a field straight through a city and merges two strips | ``CARCASSONNE_FIX_R9=1`` |
| ``R9_MEEPLE_FALLOUT`` / ``MEEPLE_DEPLOY_UNMIRRORED`` | the same surplus half-edges arriving through the meeple legal-set: our farmer slot's token set is not one JCZ offers | ``CARCASSONNE_FIX_R9=1`` |
| ``SEAT_DESYNC`` | downstream bookkeeping: once a turn is lost or gained the two engines disagree about *who* is to move, so per-seat scores stop being comparable | ``fixed_v1`` |
| ``DESYNC_FALLOUT`` | any later difference downstream of a CONTAMINATING event (see below) — one cause, not N findings | — |
| ``SCORE_FINAL_EXPLAINED`` | a terminal-score gap in a game that carries a score-moving class above. A gap with NO classified cause is ``SCORE_FINAL``, which is REAL and exits 1 — that is the assertion which catches the next rules bug | — |

**What ``fixed_v1`` + R9 still cannot match** (documented, not fixed):

* ``WALL_LEGALITY`` — ``fixed_v1`` moves the start tile to row 18 of the 35x35
  grid (``centered18``), which buys 18 rows of headroom instead of 6 and makes the
  wall unreachable in practice, but the board is still **bounded** where JCZ's is
  not. A game that pushed 18 tiles in one direction would still diverge. The
  class therefore shrinks toward zero rather than being closed by construction.
* ``WINDOW_OVERFLOW`` — the 25x25 action window is a *representation* cap (spec
  §A1 keeps it a separate decision, J4) and is untouched by any rules profile. A
  placement outside it is unencodable, i.e. our recorded games can never contain
  one; it can only appear as a legal move JCZ offers and we cannot express.
* **Garden semantics** — the 8 "flowers" tiles' geometry is certified (spike Q2),
  but JCZ scores gardens via its own ``GardenCapability`` while we score them as
  cloisters. Gardens are kept OFF in the JCZ setup so the comparison is like for
  like; garden *semantics* stay outside the oracle's reach.
* **Monastery/Field ownership and tie-breaks** are not diffed at feature level —
  only the partitions and the scores are.

## ⚠️ A recorded action sequence is RULES-RELATIVE — pick the right ``--policy``

``--policy record`` replays the archived action ints and is sound **only for the
profile they were recorded under** (``walled``). Under ``fixed_v1`` the same ints
decode to a different, generally illegal game, because the retail start tile, the
redraw rule and the recentred grid all move the action space and the turn parity
(``game_wrapper`` says so at ``DRAW_RULE_*``); the harness refuses such a record with
``RECORD_ILLEGAL`` rather than playing it and blaming JCZ.

``--policy seeded`` therefore keeps the **deck** — the thing the oracle needs held
constant — and generates its own deterministic legal trajectory. That is how any
non-``walled`` profile must be driven.

## Usage

    # the engine of record, against its own archive
    scripts/jcz_oracle/replay_diff.py --games measurement/champ_action_logs/champ_games.jsonl \\
        --limit 20 --profile walled --policy record --out /tmp/walled.json

    # the clean profile: expect ZERO divergences and exact final scores
    scripts/jcz_oracle/replay_diff.py --games measurement/champ_action_logs/champ_games.jsonl \\
        --limit 20 --profile fixed_v1 --policy seeded --r9 --fail-on-real --out /tmp/fixed.json

``--r9`` re-execs with ``CARCASSONNE_FIX_R9=1`` if it is not already set, because
``base_deck`` latches the flag at **import** time (there is no per-``Game`` seam).

Validated 2026-08-03 over 7 legs / 128 games with zero unclassified divergences —
see ``measurement/jcz_oracle_20260803/VALIDATION_REPORT.md``.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --------------------------------------------------------------------------- #
# R9 is latched at base_deck IMPORT time -> the re-exec must happen before any  #
# engine import. Keep this above the wingedsheep imports.                      #
# --------------------------------------------------------------------------- #
if "--r9" in sys.argv and os.environ.get("CARCASSONNE_FIX_R9", "").lower() not in (
        "1", "true", "yes", "on"):
    os.environ["CARCASSONNE_FIX_R9"] = "1"
    os.execv(sys.executable, [sys.executable, str(_HERE)] + sys.argv[1:])

from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction  # noqa: E402
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.objects.terrain_type import TerrainType  # noqa: E402
from wingedsheep.carcassonne.tile_sets.base_deck import R9_FIELD_ON_CITY_EDGE_FIX  # noqa: E402
from wingedsheep.carcassonne.utils.city_util import CityUtil  # noqa: E402
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402
from wingedsheep.carcassonne.utils.road_util import RoadUtil  # noqa: E402

from carcassonne_ai import action_space as A  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

sys.path.insert(0, str(_HERE.parent))
from jcz_driver import (  # noqa: E402
    JczEngine, JczError, free_meeple_id, is_over, meeple_options, scores,
    tile_options, wants_confirm,
)
from tile_map import (  # noqa: E402
    HALF_EDGE_TO_JCZ, SIDE_TO_JCZ, jcz_location_for, jcz_rotation_quarters,
    jcz_rotation_str, load_tile_mapping, parse_location, to_jcz_position,
)

# --------------------------------------------------------------------------- #
# divergence taxonomy                                                           #
# --------------------------------------------------------------------------- #
CLASSIFIED = {
    "START_TILE_PLY",         # A4 — our start tile is a player move
    "START_TILE_MEEPLE",      # A4 — …and can carry a meeple JCZ cannot express
    "DESYNC_FALLOUT",         # any later diff downstream of a CONTAMINATING event
    "R9_MEEPLE_FALLOUT",      # a meeple-option diff that is only the R9 half-edges
    "MEEPLE_DEPLOY_UNMIRRORED",  # our deploy had no JCZ option (R9 token mismatch)
    "WALL_LEGALITY",          # A1 — JCZ offers a placement our bounded grid does not
    "WINDOW_OVERFLOW",        # J4 — outside the 25x25 action window (representation)
    "UNPLACEABLE_TURN_LOSS",  # A3 — our Pass discards AND passes the turn
    "UNPLACEABLE_REDRAW",     # A3 — the retail redraw, aligned with JCZ (informational)
    "SCORE_TIMING",           # A2 — cloister scan drift; reconciles by terminal
    "SEAT_DESYNC",            # bookkeeping fallout of the three above
    "FARM_ATOM_SET",          # R9 — a field half-edge on a city edge
    "FARM_PARTITION",         # R9 — the resulting merge through a city
    "SCORE_FINAL_EXPLAINED",  # a final gap WITH a classified cause (below)
}
REAL = {
    "LEGALITY_OURS_EXTRA",    # we allow a placement JCZ refuses  <- rules bug
    "MEEPLE_LEGALITY",        # canonicalised meeple option sets differ
    "CITY_PARTITION",
    "ROAD_PARTITION",
    "SCORE_FINAL",            # terminal scores disagree with NO classified cause
    "MEEPLE_SLOT_UNMAPPED",   # our slot resolves to no JCZ feature -> mapping gap
    "JCZ_REJECT",             # JCZ refused a move we recorded as legal
    "RECORD_ILLEGAL",         # the record is not a legal game under this profile
    "HARNESS_ERROR",
}
#: CONTAMINATING events — after one of these the two boards are no longer the same
#: game (a meeple exists on one side only, or the turn order has slipped), so every
#: later meeple-legality or score difference is that one event's shadow rather than
#: an independent finding. Recorded as ``DESYNC_FALLOUT``, with the cause carried on
#: the per-game ``contaminated_by`` field. Flagged EXPLICITLY at the site where the
#: two states actually part company — never inferred from the counter, because a
#: legal-set difference alone does NOT desync anything (both engines keep playing
#: our move).
CONTAMINATING = {"START_TILE_MEEPLE", "UNPLACEABLE_TURN_LOSS", "SEAT_DESYNC",
                 "MEEPLE_DEPLOY_UNMIRRORED"}

#: Classified events that move points by construction. A final-score gap in a game
#: carrying one of these is expected; a gap in a game carrying none is a finding.
#: ``WALL_LEGALITY`` is deliberately NOT here: it only ever *adds* options on JCZ's
#: side, and our player picks from OUR set, so the boards stay identical.
SCORE_MOVING = {
    "START_TILE_MEEPLE", "DESYNC_FALLOUT", "UNPLACEABLE_TURN_LOSS",
    "SEAT_DESYNC", "FARM_ATOM_SET", "FARM_PARTITION", "R9_MEEPLE_FALLOUT",
    "MEEPLE_DEPLOY_UNMIRRORED",
}


# --------------------------------------------------------------------------- #
# our-side extraction                                                           #
# --------------------------------------------------------------------------- #
def our_feature_partition(state, origin) -> dict[str, set[frozenset]]:
    """Our board as JCZ-comparable atom sets, one per feature.

    Atoms are ``(x, y, token)`` in JCZ's coordinate and label vocabulary:
    ``token`` is an edge letter (N/E/S/W) for a City or Road and a half-edge
    (NL/NR/…) for a Field — exactly what ``parse_location`` yields from JCZ's own
    ``features[].places``. Comparing SETS OF ATOM SETS makes the diff independent
    of feature identity, ordering and naming on both sides.
    """
    r0, c0 = origin
    out = {"City": set(), "Road": set(), "Field": set()}

    for coord in state.placed_coords:
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        for side in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT):
            terrain = tile.get_type(side)
            pos = CoordinateWithSide(coordinate=coord, side=side)
            if terrain == TerrainType.CITY:
                feat = CityUtil.find_city(state, pos)
                positions = feat.city_positions
                key = "City"
            elif terrain == TerrainType.ROAD:
                feat = RoadUtil.find_road(state, pos)
                positions = feat.road_positions
                key = "Road"
            else:
                continue
            atoms = frozenset(
                (p.coordinate.column - c0, p.coordinate.row - r0, SIDE_TO_JCZ[p.side])
                for p in positions if p.side in SIDE_TO_JCZ
            )
            out[key].add(atoms)

    seen: set[int] = set()
    for farm in FarmUtil.find_all_farms(state).values():
        if id(farm) in seen:
            continue
        seen.add(id(farm))
        atoms = frozenset(
            (n.coordinate.column - c0, n.coordinate.row - r0, HALF_EDGE_TO_JCZ[fs])
            for n in farm.farmer_connections_with_coordinate
            for fs in n.farmer_connection.tile_connections
        )
        if atoms:
            out["Field"].add(atoms)
    return out


def jcz_feature_partition(state: dict) -> dict[str, set[frozenset]]:
    out = {"City": set(), "Road": set(), "Field": set()}
    for f in state.get("features") or []:
        kind = f.get("type")
        if kind not in out:
            continue
        atoms = frozenset(
            (int(x), int(y), tok)
            for x, y, loc in f.get("places", [])
            for tok in parse_location(loc)
        )
        if atoms:
            out[kind].add(atoms)
    return out


def our_tile_options(game, board, tile_map) -> tuple[str | None, set[tuple[int, int, int]], int]:
    """Our legal tile placements as ``(jcz_id, {(x, y, degrees)}, n_overflow)``."""
    state = board.state
    tile = state.next_tile
    if tile is None:
        return None, set(), 0
    jcz_id, rot_cw90 = tile_map[tile.description]
    off, W = board.offset, game.window_size
    valid = game.get_valid_moves(board)
    opts: set[tuple[int, int, int]] = set()
    for idx in range(A.tile_action_count(W)):
        if not valid[idx]:
            continue
        cell, rot = divmod(idx, A.N_ROTATIONS)
        wr, wc = divmod(cell, W)
        coord = off.to_engine(wr, wc)
        opts.add((coord.column - game.start_col, coord.row - game.start_row,
                  jcz_rotation_quarters(rot, rot_cw90) * 90))
    return jcz_id, opts, 0


def our_meeple_options(game, board) -> tuple[set[tuple[str, frozenset]], list[Side]]:
    """Our legal meeple slots, canonicalised to JCZ ``(feature, tokens)`` keys.

    Our action space is FINER than JCZ's — a city spanning two edges is two of our
    slots and one of JCZ's option, a 3-corner field is three slots and one option —
    so the canonical key is what the two sides can actually be compared on. The
    raw slot list is returned alongside for the mapping table.
    """
    state = board.state
    coord = state.last_tile_action.coordinate if state.last_tile_action else None
    if coord is None:
        return set(), []
    tile = state.board[coord.row][coord.column]
    valid = game.get_valid_moves(board)
    W = game.window_size
    nb, fb = A.meeple_normal_base(W), A.meeple_farmer_base(W)
    keys: set[tuple[str, frozenset]] = set()
    unmapped: list[Side] = []
    for base, sides in ((nb, A.NORMAL_SIDES), (fb, A.FARMER_SIDES)):
        for i, side in enumerate(sides):
            if not valid[base + i]:
                continue
            got = jcz_location_for(tile, side)
            if got is None:
                unmapped.append(side)
            else:
                keys.add(got)
    return keys, unmapped


def jcz_meeple_keys(state: dict) -> set[tuple[str, frozenset]]:
    return {(o["feature"], parse_location(o["location"])) for o in meeple_options(state)}


# --------------------------------------------------------------------------- #
# one game                                                                      #
# --------------------------------------------------------------------------- #
class Divergences:
    def __init__(self):
        self.counts: Counter = Counter()
        self.samples: dict[str, list] = {}

    def add(self, cls: str, ply: int, detail) -> None:
        self.counts[cls] += 1
        self.samples.setdefault(cls, [])
        if len(self.samples[cls]) < 3:
            self.samples[cls].append({"ply": ply, "detail": detail})

    def real(self) -> Counter:
        return Counter({k: v for k, v in self.counts.items() if k in REAL})


def _seeded_actions(game, board, deck_seed: int):
    """A deterministic legal trajectory from the same deck — the ``seeded`` policy.

    ⚠️ Needed because a recorded ``(deck_seed, actions)`` pair is **rules-relative**:
    under ``fixed_v1`` the same action ints decode to a different (and generally
    illegal) game, since the retail start tile, the redraw rule and the recentred
    grid all shift the action space and the turn order (``game_wrapper`` documents
    this at ``DRAW_RULE_*``). Replaying a walled recording under fixed rules would
    measure our own mis-replay, not the two engines' rules.

    So the fixed-rules leg keeps the DECK (the thing the oracle actually needs held
    constant) and generates its own legal moves. Uniform over the legal set, from a
    dedicated ``random.Random`` — the engine consumes the *global* stream only in
    the deck shuffle, so this cannot perturb the deck (``root_replay`` contract).
    """
    rng = random.Random(int(deck_seed) ^ 0x5EEDED)
    while game.get_game_ended(board, 0) == 0:
        valid = game.get_valid_moves(board)
        idx = [i for i in range(len(valid)) if valid[i]]
        if not idx:
            break
        a = rng.choice(idx)
        yield a
        board, _ = game.get_next_state(board, a)


def replay_one(rec, *, profile: str, policy: str = "record", jar=None, tiles=None) -> dict:
    """Replay one recorded game through both engines. Returns a result dict."""
    tile_map = load_tile_mapping()
    div = Divergences()

    fixed_start = profile != "walled"
    kw = {"enable_legal_moves_cache": False}
    if profile == "walled":
        pass
    elif profile == "fixed_v1":
        kw.update(fixed_start_tile=True, start_row=18, start_col=15,
                  cloister_scan_fix=True, draw_rule="redraw")
    else:
        raise ValueError(f"unknown profile {profile!r}")

    if policy == "seeded":
        random.seed(int(rec.deck_seed))
        _g = Game(**kw)
        actions = list(_seeded_actions(_g, _g.get_init_board(), rec.deck_seed))
    elif policy == "record":
        actions = [int(a) for a in rec.actions]
    else:
        raise ValueError(f"unknown policy {policy!r}")

    random.seed(int(rec.deck_seed))
    game = Game(**kw)
    board = game.get_init_board()
    state = board.state
    origin = (game.start_row, game.start_col)

    # --- the forced deck ---------------------------------------------------- #
    if fixed_start:
        start_desc, start_rot = "city_top_straight_road", 0
        upcoming = ([state.next_tile] if state.next_tile else []) + list(state.deck)
    else:
        # walled: our player 0 PLACES the first drawn tile; JCZ pre-places it, so
        # the tile and the rotation our recording chose become JCZ's `start`.
        first = state.next_tile
        _, rot0 = divmod(int(actions[0]), A.N_ROTATIONS)
        start_desc, start_rot = first.description, rot0
        upcoming = list(state.deck)
        div.add("START_TILE_PLY", 0, {"tile": start_desc, "our_rotation": rot0})

    start_jcz_id, start_rot_cw90 = tile_map[start_desc]
    start_jcz_deg = jcz_rotation_quarters(start_rot, start_rot_cw90) * 90
    draw_order = [tile_map[t.description][0] for t in upcoming]

    result = {
        "game_id": rec.game_id, "deck_seed": rec.deck_seed, "profile": profile,
        "policy": policy,
        "r9": bool(R9_FIELD_ON_CITY_EDGE_FIX), "n_plies": len(actions),
        "plies_compared": 0, "seat_offset": None, "seat_desync": False,
        "our_final": None, "jcz_final": None, "final_agree": None,
        "counts": {}, "samples": {}, "error": None,
    }

    eng = JczEngine(jar=jar, tiles=tiles)
    try:
        jst = eng.setup(draw_order, start_jcz_id, start_jcz_deg)

        running_mismatch_plies: list[int] = []
        seat_offset: int | None = None
        r9_on = bool(R9_FIELD_ON_CITY_EDGE_FIX)
        desync: list[str] = []          # [0] = the first contaminating cause

        def contaminate(reason: str) -> None:
            if not desync:
                desync.append(reason)
                result["contaminated_by"] = reason

        for ply, raw in enumerate(actions):
            a = int(raw)
            st = board.state
            phase = st.phase
            # A recorded action sequence is RULES-RELATIVE. Playing a walled
            # recording under another profile silently produces an illegal game
            # (our StateUpdater does not re-check legality), which would then read
            # as a JCZ rules divergence. Refuse instead.
            if not game.get_valid_moves(board)[a]:
                div.add("RECORD_ILLEGAL", ply,
                        {"action": a, "phase": str(phase),
                         "hint": "recorded under a different rules profile?"})
                break
            decoded = game._decode_for(st, board.offset, a)

            # ---------------- TILES phase ---------------------------------- #
            if phase == GamePhase.TILES:
                # JCZ may still owe an action/confirm from the previous tile (it
                # skips its ActionPhase when no meeple is placeable, and always
                # ends a turn with a Confirm). Our recording has no ply for
                # either, so drain JCZ to its own TilePhase first.
                jst = _drain_to_tile_phase(eng, jst)
                if isinstance(decoded, PassAction):
                    if not st.redraw_unplaceable:
                        contaminate("UNPLACEABLE_TURN_LOSS")
                    div.add("UNPLACEABLE_REDRAW" if st.redraw_unplaceable
                            else "UNPLACEABLE_TURN_LOSS", ply,
                            {"tile": st.next_tile.description if st.next_tile else None})
                    board, _ = game.get_next_state(board, a)
                    continue

                is_start_ply = (not fixed_start) and ply == 0
                if not is_start_ply:
                    if is_over(jst):
                        div.add("HARNESS_ERROR", ply, "JCZ ended early")
                        break
                    j_tile, j_opts = tile_options(jst)
                    our_id, our_opts, _ = our_tile_options(game, board, tile_map)
                    if j_tile != our_id:
                        div.add("HARNESS_ERROR", ply,
                                {"deck_desync": True, "ours": our_id, "jcz": j_tile})
                        break
                    if our_opts != j_opts:
                        extra, missing = our_opts - j_opts, j_opts - our_opts
                        if extra:
                            div.add("LEGALITY_OURS_EXTRA", ply,
                                    {"tile": our_id, "extra": sorted(extra)[:8]})
                        if missing:
                            div.add("WALL_LEGALITY", ply,
                                    {"tile": our_id, "jcz_only": sorted(missing)[:8],
                                     "n": len(missing)})
                    # seat check
                    j_player = (jst.get("action") or {}).get("player")
                    if j_player is not None:
                        off = (int(j_player) - int(st.current_player)) % 2
                        if seat_offset is None:
                            seat_offset = off
                            result["seat_offset"] = off
                        elif off != seat_offset:
                            result["seat_desync"] = True
                            div.add("SEAT_DESYNC", ply,
                                    {"ours": st.current_player, "jcz": j_player})
                            contaminate("SEAT_DESYNC")
                            seat_offset = off

                    rot_cw90 = tile_map[st.next_tile.description][1]
                    try:
                        jst = eng.place_tile(
                            tile_map[st.next_tile.description][0],
                            jcz_rotation_str(decoded.tile_rotations, rot_cw90),
                            to_jcz_position(decoded.coordinate, *origin))
                    except JczError as e:
                        div.add("JCZ_REJECT", ply, str(e)[:300])
                        break
                    result["plies_compared"] += 1

                board, _ = game.get_next_state(board, a)

                if not is_start_ply:
                    _diff_partitions(div, ply, board.state, origin, jst)
                    _diff_scores(div, ply, board.state, jst, seat_offset,
                                 running_mismatch_plies)
                continue

            # ---------------- MEEPLES phase -------------------------------- #
            if phase == GamePhase.MEEPLES:
                is_start_meeple = (not fixed_start) and ply <= 1 and board.tile_count == 1
                if is_start_meeple:
                    if isinstance(decoded, MeepleAction):
                        div.add("START_TILE_MEEPLE", ply,
                                {"side": str(decoded.coordinate_with_side.side)})
                        contaminate("START_TILE_MEEPLE")
                    board, _ = game.get_next_state(board, a)
                    continue

                our_keys, unmapped = our_meeple_options(game, board)
                if unmapped:
                    div.add("MEEPLE_SLOT_UNMAPPED", ply,
                            {"legal_slots_with_no_jcz_feature": [str(s) for s in unmapped]})
                j_keys = jcz_meeple_keys(jst)
                if our_keys != j_keys:
                    div.add(_meeple_class(our_keys - j_keys, j_keys - our_keys,
                                          (desync[0] if desync else None), r9_on), ply, {
                                "ours_only": sorted((f, sorted(t)) for f, t in our_keys - j_keys),
                                "jcz_only": sorted((f, sorted(t)) for f, t in j_keys - our_keys)})

                if isinstance(decoded, PassAction):
                    if not wants_confirm(jst) and (jst.get("action") or {}).get("canPass"):
                        jst = eng.pass_()
                else:
                    want = jcz_location_for(
                        board.state.board[decoded.coordinate_with_side.coordinate.row]
                                        [decoded.coordinate_with_side.coordinate.column],
                        decoded.coordinate_with_side.side)
                    opt = None
                    for o in meeple_options(jst):
                        if want and (o["feature"], parse_location(o["location"])) == want:
                            opt = o
                            break
                    if opt is None:
                        # We spent a follower JCZ did not. From here the supplies —
                        # and therefore the legal sets — differ for the rest of the
                        # game, so this is where the two states actually part company.
                        cls = ("DESYNC_FALLOUT" if desync
                               else "MEEPLE_DEPLOY_UNMIRRORED" if (not r9_on and want
                                                                   and want[0] == "Field")
                               else "MEEPLE_SLOT_UNMAPPED")
                        div.add(cls, ply, {
                            "side": str(decoded.coordinate_with_side.side),
                            "wanted": [want[0], sorted(want[1])] if want else None,
                            "jcz_offered": [[o["feature"], o["location"]]
                                            for o in meeple_options(jst)]})
                        contaminate(cls if cls != "DESYNC_FALLOUT" else desync[0])
                        if not wants_confirm(jst) and (jst.get("action") or {}).get("canPass"):
                            jst = eng.pass_()
                    else:
                        mid = free_meeple_id(
                            jst, int((jst.get("action") or {}).get("player", 0)))
                        if mid is None:
                            div.add("HARNESS_ERROR", ply, "JCZ has no free follower")
                            break
                        try:
                            jst = eng.deploy_meeple(opt, mid)
                        except JczError as e:
                            div.add("JCZ_REJECT", ply, str(e)[:300])
                            break
                if wants_confirm(jst):
                    jst = eng.commit()
                result["plies_compared"] += 1

                board, _ = game.get_next_state(board, a)
                _diff_partitions(div, ply, board.state, origin, jst)
                _diff_scores(div, ply, board.state, jst, seat_offset,
                             running_mismatch_plies)
                continue

            div.add("HARNESS_ERROR", ply, f"unexpected phase {phase}")
            break

        # --- terminal ------------------------------------------------------ #
        while wants_confirm(jst) and not is_over(jst):
            jst = eng.commit()
        our_final = list(board.state.scores)
        jcz_final = scores(jst)
        if seat_offset:
            jcz_final = [jcz_final[(i + seat_offset) % len(jcz_final)]
                         for i in range(len(jcz_final))]
        result["our_final"], result["jcz_final"] = our_final, jcz_final
        result["jcz_over"] = is_over(jst)
        agree = our_final == jcz_final
        result["final_agree"] = agree

        # A score gap is only a FINDING when nothing classified could have caused
        # it. Every class in SCORE_MOVING is a known rules difference that changes
        # points by construction, so a game carrying one gets the explained class;
        # a game carrying none and still disagreeing is a REAL divergence.
        causes = sorted(SCORE_MOVING & set(div.counts))
        result["score_gap_causes"] = causes
        final_cls = "SCORE_FINAL_EXPLAINED" if causes else "SCORE_FINAL"
        if not agree:
            div.add(final_cls, -1, {"ours": our_final, "jcz": jcz_final,
                                    "classified_causes": causes})
        # A running mismatch that reconciles by the terminal is the A2 cloister
        # timing class; one that does not is part of the final gap.
        n_running = div.counts.pop("SCORE_RUNNING", 0)
        if n_running:
            dest = "SCORE_TIMING" if agree else final_cls
            div.counts[dest] += n_running
            div.samples.setdefault(dest, []).extend(
                div.samples.pop("SCORE_RUNNING", [])[:3])
    except Exception as e:  # noqa: BLE001 — a harness fault must be a CLASS, not a crash
        result["error"] = f"{type(e).__name__}: {e}"
        div.add("HARNESS_ERROR", -1, result["error"])
    finally:
        eng.close()

    result["counts"] = dict(div.counts)
    result["samples"] = div.samples
    result["real"] = dict(div.real())
    return result


def _meeple_class(ours_only, jcz_only, contaminated: str | None, r9_on: bool) -> str:
    """Which class a meeple-option difference belongs to.

    Order matters. A game that has already desynced explains everything after it.
    Failing that, a difference confined to ``Field`` keys while R9 is OFF is the R9
    data bug arriving through the meeple legal-set (the surplus half-edges change
    the region's token set, so our key simply is not one JCZ offers) — the same
    single cause as ``FARM_ATOM_SET``, not a second finding. Anything else is real.
    """
    if contaminated:
        return "DESYNC_FALLOUT"
    keys = set(ours_only) | set(jcz_only)
    if not r9_on and keys and all(f == "Field" for f, _ in keys):
        return "R9_MEEPLE_FALLOUT"
    return "MEEPLE_LEGALITY"


def _drain_to_tile_phase(eng: JczEngine, jst: dict) -> dict:
    """Advance JCZ to its next TilePhase by answering everything our record has no
    ply for: the end-of-turn ``Confirm``, and an ActionPhase our engine skipped
    (JCZ always offers one; our engine only enters MEEPLES when a slot exists)."""
    for _ in range(8):
        if is_over(jst) or tile_options(jst)[0] is not None:
            return jst
        if wants_confirm(jst):
            jst = eng.commit()
            continue
        if (jst.get("action") or {}).get("canPass"):
            jst = eng.pass_()
            continue
        return jst
    return jst


def _diff_partitions(div: Divergences, ply: int, state, origin, jst: dict) -> None:
    ours = our_feature_partition(state, origin)
    theirs = jcz_feature_partition(jst)

    for kind, cls in (("City", "CITY_PARTITION"), ("Road", "ROAD_PARTITION")):
        if ours[kind] != theirs[kind]:
            div.add(cls, ply, {"ours_only": _brief(ours[kind] - theirs[kind]),
                               "jcz_only": _brief(theirs[kind] - ours[kind])})

    our_atoms = {a for r in ours["Field"] for a in r}
    jcz_atoms = {a for r in theirs["Field"] for a in r}
    if our_atoms != jcz_atoms:
        div.add("FARM_ATOM_SET", ply, {
            "ours_only": sorted(our_atoms - jcz_atoms)[:8],
            "jcz_only": sorted(jcz_atoms - our_atoms)[:8]})
    common = our_atoms & jcz_atoms
    if _induced(ours["Field"], common) != _induced(theirs["Field"], common):
        div.add("FARM_PARTITION", ply, {
            "ours_only": _brief(_induced(ours["Field"], common)
                                - _induced(theirs["Field"], common)),
            "jcz_only": _brief(_induced(theirs["Field"], common)
                               - _induced(ours["Field"], common))})


def _induced(regions: set[frozenset], atoms: set) -> set[frozenset]:
    """The partition ``regions`` induces on ``atoms`` (drops atoms absent on one
    side, so a DATA difference does not also masquerade as a TRAVERSAL one)."""
    out = set()
    for r in regions:
        keep = frozenset(r & atoms)
        if keep:
            out.add(keep)
    return out


def _brief(regions, k: int = 3):
    return [sorted(r)[:6] for r in sorted(regions, key=lambda r: sorted(r))[:k]]


def _diff_scores(div, ply, state, jst, seat_offset, mismatch_plies) -> None:
    ours = list(state.scores)
    theirs = scores(jst)
    if seat_offset:
        theirs = [theirs[(i + seat_offset) % len(theirs)] for i in range(len(theirs))]
    if ours != theirs:
        div.add("SCORE_RUNNING", ply, {"ours": ours, "jcz": theirs})
        mismatch_plies.append(ply)


# --------------------------------------------------------------------------- #
# corpora                                                                       #
# --------------------------------------------------------------------------- #
class _Rec:
    __slots__ = ("game_id", "deck_seed", "actions")

    def __init__(self, game_id, deck_seed, actions):
        self.game_id, self.deck_seed, self.actions = game_id, deck_seed, actions


def load_corpus(path: Path) -> list[_Rec]:
    """Accepts both archive shapes: the ``root_replay`` jsonl and an E4 game json."""
    p = Path(path)
    if p.is_dir():
        out = []
        for f in sorted(p.glob("*.json")):
            out.extend(load_corpus(f))
        return out
    if p.suffix == ".jsonl":
        recs = []
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            recs.append(_Rec(o.get("game_id", o.get("deck_seed")),
                             int(o.get("deck_seed", o.get("seed"))),
                             [int(a) for a in o["actions"]]))
        return recs
    o = json.loads(p.read_text())
    return [_Rec(o.get("finished_at", p.stem), int(o["deck_seed"]),
                 [int(a) for a in o["actions"]])]


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", action="append", required=True,
                    help="games jsonl, an E4 game json, or a directory of them (repeatable)")
    ap.add_argument("--limit", type=int, default=0, help="max games per source (0 = all)")
    ap.add_argument("--profile", default="walled", choices=("walled", "fixed_v1"))
    ap.add_argument("--policy", default="record", choices=("record", "seeded"),
                    help="'record' replays the archived action ints (only valid for "
                         "the profile they were recorded under — walled); 'seeded' "
                         "keeps the DECK and plays its own deterministic legal "
                         "trajectory, which is the only sound way to drive a "
                         "different rules profile")
    ap.add_argument("--r9", action="store_true",
                    help="run with CARCASSONNE_FIX_R9=1 (re-execs; latched at import)")
    ap.add_argument("--jar", default=None)
    ap.add_argument("--tiles", default=None)
    ap.add_argument("--out", default=None, help="write the per-game JSON artifact here")
    ap.add_argument("--fail-on-real", action="store_true",
                    help="exit 1 if any UNCLASSIFIED divergence occurs (CI mode)")
    args = ap.parse_args(argv)

    recs: list[_Rec] = []
    for src in args.games:
        got = load_corpus(Path(src))
        recs.extend(got[: args.limit] if args.limit else got)

    print(f"# profile={args.profile}  policy={args.policy}  "
          f"R9={R9_FIELD_ON_CITY_EDGE_FIX}  games={len(recs)}",
          flush=True)

    results, totals, real_total = [], Counter(), Counter()
    agree = compared = 0
    for i, rec in enumerate(recs):
        r = replay_one(rec, profile=args.profile, policy=args.policy,
                       jar=args.jar, tiles=args.tiles)
        results.append(r)
        totals.update(r["counts"])
        real_total.update(r["real"])
        if not r["seat_desync"] and not r["error"]:
            compared += 1
            agree += bool(r["final_agree"])
        flag = "OK " if not r["real"] else "REAL"
        print(f"[{i+1}/{len(recs)}] {flag} seed={rec.deck_seed} "
              f"final={r['our_final']} vs {r['jcz_final']} "
              f"agree={r['final_agree']} classes={sorted(r['counts'])}", flush=True)

    print("\n=== per-class totals ===")
    for cls, n in sorted(totals.items(), key=lambda kv: -kv[1]):
        tag = "REAL" if cls in REAL else "expected"
        print(f"  {cls:<24} {n:>7}   [{tag}]")
    print(f"\nterminal-score agreement: {agree}/{compared} seat-synced games "
          f"({len(recs)} replayed)")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({
            "profile": args.profile, "policy": args.policy,
            "r9": bool(R9_FIELD_ON_CITY_EDGE_FIX),
            "n_games": len(recs), "totals": dict(totals), "real": dict(real_total),
            "score_agreement": {"agree": agree, "compared": compared},
            "games": results,
        }, indent=1))
        print(f"wrote {args.out}")

    if args.fail_on_real and real_total:
        print(f"\nFAIL: unclassified divergences {dict(real_total)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
