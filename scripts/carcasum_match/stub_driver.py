#!/usr/bin/env python3
"""TEST DOUBLE — NOT Carcasum. Read this before trusting anything it says.

``match.py`` was developed and must be tested against a real ``carcasum_driver``
that does not exist yet (PROTOCOL.md predates the C++ side by design — see
``match.py``'s module docstring). This script fakes that binary well enough to
exercise the PROTOCOL PLUMBING: message framing, the coordinate/rotation/meeple
forward-and-inverse maps, timeouts, and void classification. It is backed by OUR
OWN engine playing **both** seats — the "external" (champion) seat's moves are
still genuinely decided by whatever sits on the other end of the wire (real
``match.py``, with a real or audit-mode champion), relayed through this file's
own internal mirror board; the "opponent" seat is decided locally by a cheap
seeded policy, standing in for Carcasum's own ``MCTSPlayer``.

⚠️ **THIS PROVES NOTHING ABOUT CARCASUM.** It is not derived from Carcasum's
source, does not run Carcasum's search, and — because it reuses ``match.py``'s
OWN forward-map functions (``our_tile_carcasum_options``, ``forward_tile_action``,
``rotate_labels``, ``carcasum_node_key``) to build its Carcasum-shaped replies,
rather than an independent implementation — it cannot catch a bug that exists in
those functions: both ends of the wire would silently agree on the wrong
mapping. What it DOES prove: the request/reply/void-classification MACHINERY
round-trips cleanly when both sides are talking about the same game, which is
what a plumbing smoke test needs. The moment the real ``carcasum_driver``
exists, point ``--binary`` at it instead — nothing else in ``match.py`` changes,
and that is the actual rules-agreement test.

## Play-mode shape

Reads ``new_game`` off stdin (a 71-int ``deck`` of Carcasum tile TYPES, decoded
back to our tile kinds via ``TILE_MAPPING.tsv`` — picking one representative
kind per type when the garden-variant collapse makes it ambiguous, since the
two are geometrically identical); replies ``ready``; then drives its own
``Game``/``Board`` (``fixed_v1`` profile) with ``apply_action_inplace`` (no
deepcopy — needed so the ``score_detail`` instrumentation below, which patches
``state.scores`` to a subclass, keeps its type across every ply; a `deepcopy`
path would silently downgrade it back to a plain ``list`` on ply 2, see
``carcassonne_game_state.__deepcopy__``). Emits ``req_tile``/``req_meeple`` for
the external seat (blocking on stdin for the reply), decides the opponent
seat's moves itself (seeded random over the legal mask), and emits
``ev_move``/``ev_discard``/``game_over`` exactly as PROTOCOL.md describes.

## ``score_detail`` — how the stub gets it genuinely right, not just plausible

Real per-terrain ``score_detail`` isn't free even for the stub: our engine only
keeps a flat ``state.scores`` total (the same gap ``match.py``'s docstring
documents on the PRODUCTION side). Since this file OWNS its own game start to
finish, it can afford something ``match.py`` deliberately does not do
(``engine/`` instrumentation was ruled out of scope there): monkeypatch
``PointsCollector``'s four point-counting hooks (``count_city_points`` /
``count_road_points`` / ``chapel_or_flowers_points`` / ``count_farm_points``)
to tag which terrain is "current", and wrap ``state.scores`` in a list
subclass whose ``__setitem__`` mirrors each delta into a parallel per-terrain
dict while that tag is set. Each hook is called exactly once per feature,
immediately before that SAME method's winners loop does
``game_state.scores[w] += points`` for every tied winner (synchronous,
single-threaded, no other scoring code interleaves) — so the tag is correct by
construction, mid-game AND at the final ``count_final_scores`` sweep (which
goes through the identical four hooks). This is contained entirely to this
disposable test file; nothing here is written back to ``engine/``.

Usage (never run standalone for real matches — only as a `match.py --binary`
target):

    scripts/carcasum_match/stub_driver.py --dump-tiles
    scripts/carcasum_match/stub_driver.py            # play mode, speaks stdin/stdout
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

os.environ.setdefault("CARCASSONNE_FIX_R9", "1")  # the ONLY rules-clean config (match.py docstring)
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

for _p in (str(REPO / "src"), str(REPO / "engine"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import match as M  # noqa: E402  sibling module — reuse the forward maps, not re-derive them

CARCASUM_BOARD_SIZE = M.CARCASUM_BOARD_SIZE
CARCASUM_OFFSET = M.CARCASUM_OFFSET


# --------------------------------------------------------------------------- #
# canonical node numbering — shared by --dump-tiles and live req_meeple/ev_move #
# --------------------------------------------------------------------------- #
def _tile_nodes_for(tile) -> list[dict]:
    """One node per City group / Road connection / Field region / chapel, in
    Carcasum's own label vocabulary, TILE-LOCAL (as if orientation 0). `tile`
    must already be in Carcasum-base orientation (`base_tiles[kind].turn(rot_cw90)`).
    ONE canonical numbering, reused (rotated) by both --dump-tiles and every
    live request for the same tile kind, so the two never disagree."""
    TM = M._tile_map_mod()
    nodes: list[dict] = []
    i = 0
    for group in (tile.city or ()):
        labels = sorted(TM.SIDE_TO_JCZ[s] for s in group if s in TM.SIDE_TO_JCZ)
        nodes.append({"i": i, "terrain": "city", "labels": labels})
        i += 1
    for conn in (tile.road or ()):
        ends = {s for s in (conn.a, conn.b) if s in TM.SIDE_TO_JCZ}
        nodes.append({"i": i, "terrain": "road", "labels": sorted(TM.SIDE_TO_JCZ[s] for s in ends)})
        i += 1
    for fc in (tile.farms or ()):
        labels = sorted(TM.HALF_EDGE_TO_JCZ[fs] for fs in fc.tile_connections)
        nodes.append({"i": i, "terrain": "field", "labels": labels})
        i += 1
    if getattr(tile, "chapel", False):
        nodes.append({"i": i, "terrain": "cloister", "labels": ["CLOISTER"]})
        i += 1
    return nodes


def _type_to_kind_and_rot(tile_map: dict) -> dict[int, tuple[str, int]]:
    """carcasum_tile_type -> (one representative our_kind, rot_cw90). Later TSV
    rows win on a collision (the garden-variant collapse) — deterministic given
    stable dict iteration order; which sibling is picked never matters, they
    are geometrically identical (that's why Carcasum collapsed them)."""
    out: dict[int, tuple[str, int]] = {}
    for kind, (_cid, ctype, rot) in tile_map.items():
        out[ctype] = (kind, rot)
    return out


def dump_tiles_response() -> dict:
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts, base_tiles

    tile_map = M.load_carcasum_tile_mapping()
    type_to_kind = _type_to_kind_and_rot(tile_map)
    start_type = tile_map[M.START_TILE_DESC][1]
    _terrain_letter = {TerrainType.CITY: "C", TerrainType.ROAD: "R"}  # default field otherwise
    tiles = []
    for ctype in sorted(type_to_kind):
        kind, rot = type_to_kind[ctype]
        cid = tile_map[kind][0]
        base = base_tiles[kind].turn(rot)
        deck_count = sum(base_tile_counts[k] for k, (c, t, _r) in tile_map.items() if t == ctype)
        # PROTOCOL.md §4: [left, up, right, down] = W, N, E, S.
        edges = [_terrain_letter.get(base.get_type(s), "F")
                for s in (Side.LEFT, Side.TOP, Side.RIGHT, Side.BOTTOM)]
        tiles.append({
            "tile_type": ctype, "id": cid, "deck_count": deck_count,
            "edges": edges, "has_position": ctype == start_type,
            "nodes": _tile_nodes_for(base),
        })
    return {"t": "tiles", "revision": "stub-v1", "count": len(tiles), "tiles": tiles}


# --------------------------------------------------------------------------- #
# score_detail instrumentation (stub-only; see module docstring)                #
# --------------------------------------------------------------------------- #
_CUR_TERRAIN: list[str | None] = [None]


class _TaggedScores(list):
    """`state.scores`, wrapped once (right after `get_init_board`) so every
    `scores[w] += points` mirrors its delta into `detail` while a terrain tag
    is set. `apply_action_inplace` never deepcopies `state`, so this identity
    (and therefore the tag-consuming `__setitem__`) survives the whole game."""

    detail: dict[str, list[int]]

    def __setitem__(self, i, v):
        delta = v - self[i]
        list.__setitem__(self, i, v)
        t = _CUR_TERRAIN[0]
        if t is not None:
            self.detail[t][i] += delta


def _instrument_scoring(state, n_players: int) -> dict[str, list[int]]:
    """Patch PointsCollector's four hooks + wrap `state.scores`. Returns the
    live `detail` dict, updated in place for the rest of the game."""
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    detail = {"field": [0] * n_players, "city": [0] * n_players,
              "road": [0] * n_players, "cloister": [0] * n_players}
    ts = _TaggedScores(state.scores)
    ts.detail = detail
    state.scores = ts

    # count_city_points / count_road_points / chapel_or_flowers_points are
    # @staticmethod; count_farm_points is @classmethod — wrap each in its own
    # matching kind rather than assuming one convention for all four.
    _orig_city = PointsCollector.count_city_points
    _orig_road = PointsCollector.count_road_points
    _orig_chapel = PointsCollector.chapel_or_flowers_points
    _orig_farm = PointsCollector.count_farm_points.__func__

    def _tag_static(name, fn):
        def wrapped(*a, **kw):
            _CUR_TERRAIN[0] = name
            return fn(*a, **kw)
        return staticmethod(wrapped)

    def _tag_class(name, fn):
        def wrapped(cls, *a, **kw):
            _CUR_TERRAIN[0] = name
            return fn(cls, *a, **kw)
        return classmethod(wrapped)

    PointsCollector.count_city_points = _tag_static("city", _orig_city)
    PointsCollector.count_road_points = _tag_static("road", _orig_road)
    PointsCollector.chapel_or_flowers_points = _tag_static("cloister", _orig_chapel)
    PointsCollector.count_farm_points = _tag_class("field", _orig_farm)
    return detail


# --------------------------------------------------------------------------- #
# I/O                                                                          #
# --------------------------------------------------------------------------- #
def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _recv() -> dict:
    line = sys.stdin.readline()
    if not line.strip():
        raise EOFError("stdin closed")
    return json.loads(line)


# --------------------------------------------------------------------------- #
# play mode                                                                    #
# --------------------------------------------------------------------------- #
def run_play_mode() -> None:
    from carcassonne_ai import action_space as A
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    prof = rules_profile.activate(M.PROFILE)
    if not prof.as_manifest()["r9_env_ok"]:
        raise RuntimeError("CARCASSONNE_FIX_R9 must be on for the stub too")

    tile_map = M.load_carcasum_tile_mapping()
    type_to_kind = _type_to_kind_and_rot(tile_map)

    req = _recv()
    if req.get("t") != "new_game":
        _send({"t": "fault", "why": "internal", "detail": {"expected": "new_game", "got": req}})
        return
    external_seat = int(req["external_seat"])
    opp_seat = 1 - external_seat
    deck_types = list(req["deck"])
    if len(deck_types) != M.CARCASUM_DECK_LEN:
        _send({"t": "fault", "why": "deck_desync",
               "detail": {"expected_len": M.CARCASUM_DECK_LEN, "got_len": len(deck_types)}})
        return
    kinds = []
    for ctype in deck_types:
        got = type_to_kind.get(int(ctype))
        if got is None:
            _send({"t": "fault", "why": "deck_desync", "detail": {"unknown_tile_type": ctype}})
            return
        kinds.append(got[0])

    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    st = board.state
    st.next_tile = base_tiles[kinds[0]]
    st.deck = [base_tiles[k] for k in kinds[1:]]
    n_players = len(st.scores)
    detail = _instrument_scoring(st, n_players)

    rng = random.Random(int(req.get("seed", 0)))
    start_desc = st.board[game.start_row][game.start_col].description
    _c_id, start_type, _rot0 = tile_map[start_desc]
    _send({"t": "ready", "start_tile_type": start_type, "start_xy": [CARCASUM_OFFSET, CARCASUM_OFFSET],
          "board_size": CARCASUM_BOARD_SIZE, "deck_len": M.CARCASUM_DECK_LEN,
          "players": ["external", "stub-random"], "revision": "stub-v1", "patches": []})

    origin = (game.start_row, game.start_col)
    ply = 0
    prev_scores = list(st.scores)

    def apply(a: int) -> None:
        nonlocal board, st
        board, _ = game.apply_action_inplace(board, int(a))
        st = board.state

    def event_for(player: int, before_phase, tile_a: int, meeple_a: int | None,
                  discarded_delta: int) -> dict:
        cur = list(st.scores)
        return {"t": "ev_move", "ply": ply, "player": player,
               "tile_type": tile_map[_placed_desc(st)][1],
               "x": _cx(st)[0], "y": _cx(st)[1], "o": _co(st, tile_map),
               "meeple": meeple_a, "scores": cur,
               "score_detail": {k: list(v) for k, v in detail.items()},
               "meeples_left": list(st.meeples), "discarded": len(st.set_aside_tiles),
               "tiles_left": len(st.deck) + (1 if st.next_tile is not None else 0),
               "ms": 0, "playouts": 0}

    def _placed_desc(state) -> str:
        c = state.last_tile_action.coordinate
        return state.board[c.row][c.column].description

    def _cx(state) -> tuple[int, int]:
        TM = M._tile_map_mod()
        c = state.last_tile_action.coordinate
        jp = TM.to_jcz_position(c, *origin)
        return jp[0] + CARCASUM_OFFSET, jp[1] + CARCASUM_OFFSET

    def _co(state, tmap) -> int:
        TM = M._tile_map_mod()
        _cid, _ctype, rot_cw90 = tmap[_placed_desc(state)]
        return TM.jcz_rotation_quarters(state.last_tile_action.tile_rotations, rot_cw90)

    while game.get_game_ended(board, 0) == 0:
        seat = int(st.current_player)
        phase = st.phase
        valid = game.get_valid_moves(board)

        if phase == GamePhase.TILES:
            pass_idx = A.tile_pass_index(game.window_size)
            legal = [i for i, v in enumerate(valid) if v]
            if legal == [pass_idx]:
                discarded_type = tile_map[st.next_tile.description][1] if st.next_tile is not None else None
                apply(pass_idx)
                _send({"t": "ev_discard", "ply": ply, "player": seat,
                      "tile_type": discarded_type,
                      "discarded": len(st.set_aside_tiles),
                      "tiles_left": len(st.deck) + (1 if st.next_tile is not None else 0)})
                ply += 1
                continue

            if seat == external_seat:
                _c_id, c_type, _rot = tile_map[st.next_tile.description]
                _, placements = M.our_tile_carcasum_options(game, board, tile_map, origin)
                _send({"t": "req_tile", "ply": ply, "player": seat, "tile_type": c_type,
                      "placements": sorted(list(p) for p in placements)})
                reply = _recv()
                if reply.get("t") == "quit":
                    return
                a, offered = M.invert_tile_move(game, board, tile_map, x=reply.get("x"),
                                                y=reply.get("y"), o=reply.get("o"),
                                                tile_type=c_type, origin=origin)
                if a is None:
                    _send({"t": "fault", "why": "invalid_move",
                          "detail": {"reply": reply, "offered": offered}})
                    return
            else:
                legal_now = [i for i in legal]
                a = rng.choice(legal_now)

            meeple_a = None
            apply(a)
            if st.phase == GamePhase.MEEPLES:
                mvalid = game.get_valid_moves(board)
                mlegal = [i for i, v in enumerate(mvalid) if v]
                pass_m = A.meeple_pass_index(game.window_size)
                real_options = [i for i in mlegal if i != pass_m]
                if seat == external_seat:
                    if real_options:
                        nodes = _live_meeple_nodes(game, board, tile_map)
                        _send({"t": "req_meeple", "ply": ply, "player": seat,
                              "tile_type": tile_map[_placed_desc(st)][1],
                              "placed": list(_cx(st)) + [_co(st, tile_map)], "nodes": nodes})
                        reply = _recv()
                        if reply.get("t") == "quit":
                            return
                        node_i = reply.get("i")
                        if node_i is None:
                            m_a = pass_m
                        else:
                            m_a, offered = M.invert_meeple_move(
                                game, board, {tile_map[_placed_desc(st)][1]: _canonical_nodes(tile_map, _placed_desc(st))},
                                tile_type=tile_map[_placed_desc(st)][1], o=_co(st, tile_map), node_index=node_i)
                            if m_a is None:
                                _send({"t": "fault", "why": "invalid_move",
                                      "detail": {"reply": reply, "offered": offered}})
                                return
                        apply(m_a)
                        meeple_a = None if m_a == pass_m else int(node_i)
                    else:
                        apply(pass_m)
                        meeple_a = None
                else:
                    if real_options:
                        m_a = rng.choice(real_options)
                    else:
                        m_a = pass_m
                    # Decode-before-apply: `_node_index_for_our_action` needs
                    # the PRE-apply board (still MEEPLES phase, still holding
                    # `last_tile_action`) to know which slot `m_a` means.
                    if m_a != pass_m:
                        nodes_all = _canonical_nodes(tile_map, _placed_desc(st))
                        meeple_a = _node_index_for_our_action(game, board, tile_map, m_a, nodes_all)
                    else:
                        meeple_a = None
                    apply(m_a)

            _send(event_for(seat, phase, a, meeple_a, 0))
            ply += 1
            continue

        _send({"t": "fault", "why": "internal", "detail": {"unexpected_phase": str(phase)}})
        return

    history = [{"tile_index": i, "tile_type": None, "x": None, "y": None, "o": None, "meeple": None}
              for i in range(len(st.deck))]
    _send({"t": "game_over", "scores": list(st.scores),
          "score_detail": {k: list(v) for k, v in detail.items()},
          "plies": ply, "discarded": len(st.set_aside_tiles), "history": history})
    try:
        tail = _recv()
        if tail.get("t") != "quit":
            pass
    except EOFError:
        pass


def _canonical_nodes(tile_map, our_desc: str) -> list[dict]:
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    _c_id, _ctype, rot_cw90 = tile_map[our_desc]
    base = base_tiles[our_desc].turn(rot_cw90)
    return _tile_nodes_for(base)


def _live_meeple_nodes(game, board, tile_map) -> list[dict]:
    """Board-absolute node list for req_meeple: rotate the canonical tile-local
    nodes to the placed orientation, keep only those matching a slot legal on
    OUR board right now (reuses `carcasum_node_key` / `jcz_location_for`)."""
    from carcassonne_ai import action_space as A

    TM = M._tile_map_mod()
    st = board.state
    coord = st.last_tile_action.coordinate
    tile = st.board[coord.row][coord.column]
    our_desc = tile.description
    _c_id, _ctype, rot_cw90 = tile_map[our_desc]
    o = TM.jcz_rotation_quarters(st.last_tile_action.tile_rotations, rot_cw90)
    canon = _canonical_nodes(tile_map, our_desc)

    valid = game.get_valid_moves(board)
    W = game.window_size
    legal_keys = set()
    for base, sides in ((A.meeple_normal_base(W), A.NORMAL_SIDES),
                        (A.meeple_farmer_base(W), A.FARMER_SIDES)):
        for i, side in enumerate(sides):
            if not valid[base + i]:
                continue
            got = TM.jcz_location_for(tile, side)
            if got is not None:
                legal_keys.add(got)

    out = []
    for n in canon:
        labels_abs = M.rotate_labels(n["labels"], o)
        key = M.carcasum_node_key(n["terrain"], labels_abs)
        if key in legal_keys:
            out.append({"i": n["i"], "terrain": n["terrain"], "labels": sorted(labels_abs)})
    return out


def _node_index_for_our_action(game, board, tile_map, action_idx: int, canon_nodes: list[dict]) -> int | None:
    """The stub's OWN opponent-seat meeple choice -> the node index it must
    report in ev_move, using the SAME canonical numbering `--dump-tiles` uses."""
    TM = M._tile_map_mod()
    st = board.state
    coord = st.last_tile_action.coordinate
    tile = st.board[coord.row][coord.column]
    our_desc = tile.description
    _c_id, _ctype, rot_cw90 = tile_map[our_desc]
    o = TM.jcz_rotation_quarters(st.last_tile_action.tile_rotations, rot_cw90)
    decoded = game._decode_for(st, board.offset, action_idx)
    cws = decoded.coordinate_with_side
    want = TM.jcz_location_for(tile, cws.side)
    if want is None:
        return None
    for n in canon_nodes:
        labels_abs = M.rotate_labels(n["labels"], o)
        if M.carcasum_node_key(n["terrain"], labels_abs) == want:
            return n["i"]
    return None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--dump-tiles" in argv:
        print(json.dumps(dump_tiles_response()), flush=True)
        return 0
    try:
        run_play_mode()
    except (EOFError, BrokenPipeError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
