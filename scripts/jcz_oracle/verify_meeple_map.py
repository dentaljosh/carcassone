#!/usr/bin/env python3
"""F9 / D1 — evidence for the meeple-slot (JCZ ``location``) mapping.

The spike left this as D1's one unverified piece ("no meeple-slot (``location``)
mapping verified — the main remaining unknown"). ``tile_map.jcz_location_for``
proposes the mapping; this script proves it, and it does so **semantically rather
than by label**, which is the part that actually matters.

For every meeple our engine deploys during a replay it:

1. resolves our slot (``Side.TOP`` … ``Side.BOTTOM_RIGHT``) to a JCZ
   ``(feature, location)`` via ``jcz_location_for``;
2. deploys on the JCZ side at exactly that pointer;
3. **re-derives, on BOTH engines independently, the whole feature the meeple
   landed on** — ours via ``CityUtil.find_city`` / ``RoadUtil.find_road`` /
   ``FarmUtil.find_farm_by_coordinate``, JCZ's from the ``features`` array — and
   compares their multi-tile atom sets.

A label that happened to be accepted but pointed at the wrong feature would pass
step 2 and fail step 3, which is why step 3 is the actual verification: it checks
the meeple is standing on the SAME field/city/road on both boards, across every
tile that feature spans, not merely that the string parsed.

Usage::

    scripts/jcz_oracle/verify_meeple_map.py --games measurement/champ_action_logs/champ_games.jsonl \\
        --limit 6 --r9 --out measurement/jcz_oracle_20260803/MEEPLE_MAPPING.tsv
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if "--r9" in sys.argv and os.environ.get("CARCASSONNE_FIX_R9", "").lower() not in (
        "1", "true", "yes", "on"):
    os.environ["CARCASSONNE_FIX_R9"] = "1"
    os.execv(sys.executable, [sys.executable, str(_HERE)] + sys.argv[1:])

from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction  # noqa: E402
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.utils.city_util import CityUtil  # noqa: E402
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402
from wingedsheep.carcassonne.utils.road_util import RoadUtil  # noqa: E402

from carcassonne_ai.game_wrapper import Game  # noqa: E402

sys.path.insert(0, str(_HERE.parent))
from jcz_driver import (  # noqa: E402
    JczEngine, free_meeple_id, is_over, meeple_options, wants_confirm,
)
from replay_diff import _drain_to_tile_phase, _seeded_actions, load_corpus  # noqa: E402
from tile_map import (  # noqa: E402
    HALF_EDGE_TO_JCZ, JCZ_MONASTERY_LOCATION, JCZ_TO_HALF_EDGE, JCZ_TO_SIDE,
    SIDE_TO_JCZ, format_edge_location, format_field_location, jcz_location_for,
    jcz_rotation_str, load_tile_mapping, parse_location, to_jcz_position,
)


def our_feature_atoms(state, coord, side, origin):
    """The atom set of OUR feature under a meeple at ``(coord, side)``."""
    r0, c0 = origin
    if side == Side.CENTER:
        return frozenset({(coord.column - c0, coord.row - r0, "I")})
    pos = CoordinateWithSide(coordinate=coord, side=side)
    if side in SIDE_TO_JCZ:
        tile = state.board[coord.row][coord.column]
        for group in (tile.city or ()):
            if side in group:
                return frozenset(
                    (p.coordinate.column - c0, p.coordinate.row - r0, SIDE_TO_JCZ[p.side])
                    for p in CityUtil.find_city(state, pos).city_positions
                    if p.side in SIDE_TO_JCZ)
        return frozenset(
            (p.coordinate.column - c0, p.coordinate.row - r0, SIDE_TO_JCZ[p.side])
            for p in RoadUtil.find_road(state, pos).road_positions
            if p.side in SIDE_TO_JCZ)
    farm = FarmUtil.find_farm_by_coordinate(state, pos)
    return frozenset(
        (n.coordinate.column - c0, n.coordinate.row - r0, HALF_EDGE_TO_JCZ[fs])
        for n in farm.farmer_connections_with_coordinate
        for fs in n.farmer_connection.tile_connections)


def jcz_feature_atoms(jst, position, location, feature):
    """The atom set of the JCZ feature that contains ``(position, location)``."""
    want = (int(position[0]), int(position[1]))
    if feature == "Monastery":
        return frozenset({(want[0], want[1], "I")})
    toks = parse_location(location)
    for f in jst.get("features") or []:
        if f.get("type") != feature:
            continue
        places = [(int(x), int(y), loc) for x, y, loc in f.get("places", [])]
        if any((x, y) == want and parse_location(loc) & toks for x, y, loc in places):
            return frozenset((x, y, t) for x, y, loc in places for t in parse_location(loc))
    return frozenset()


def run(rec, tile_map, rows, stats, jar=None, tiles=None):
    kw = dict(fixed_start_tile=True, start_row=18, start_col=15,
              cloister_scan_fix=True, draw_rule="redraw")
    random.seed(int(rec.deck_seed))
    _g = Game(**kw)
    actions = list(_seeded_actions(_g, _g.get_init_board(), rec.deck_seed))

    random.seed(int(rec.deck_seed))
    game = Game(**kw)
    board = game.get_init_board()
    origin = (game.start_row, game.start_col)
    upcoming = ([board.state.next_tile] if board.state.next_tile else []) + list(board.state.deck)

    eng = JczEngine(jar=jar, tiles=tiles)
    try:
        jst = eng.setup([tile_map[t.description][0] for t in upcoming],
                        tile_map["city_top_straight_road"][0], 0)
        for a in actions:
            st = board.state
            decoded = game._decode_for(st, board.offset, int(a))
            if st.phase == GamePhase.TILES:
                jst = _drain_to_tile_phase(eng, jst)
                if isinstance(decoded, PassAction):
                    board, _ = game.get_next_state(board, int(a))
                    continue
                rot_cw90 = tile_map[st.next_tile.description][1]
                jst = eng.place_tile(tile_map[st.next_tile.description][0],
                                     jcz_rotation_str(decoded.tile_rotations, rot_cw90),
                                     to_jcz_position(decoded.coordinate, *origin))
                board, _ = game.get_next_state(board, int(a))
                continue

            if isinstance(decoded, MeepleAction):
                coord = decoded.coordinate_with_side.coordinate
                side = decoded.coordinate_with_side.side
                tile = board.state.board[coord.row][coord.column]
                want = jcz_location_for(tile, side)
                opt = next((o for o in meeple_options(jst)
                            if want and (o["feature"], parse_location(o["location"])) == want),
                           None)
                stats["deploys"] += 1
                if opt is None:
                    stats["unmapped"] += 1
                    board, _ = game.get_next_state(board, int(a))
                    if not wants_confirm(jst) and (jst.get("action") or {}).get("canPass"):
                        jst = eng.pass_()
                    if wants_confirm(jst):
                        jst = eng.commit()
                    continue
                mid = free_meeple_id(jst, int((jst.get("action") or {}).get("player", 0)))
                jst = eng.deploy_meeple(opt, mid)
                board, _ = game.get_next_state(board, int(a))

                ours = our_feature_atoms(board.state, coord, side, origin)
                theirs = jcz_feature_atoms(jst, opt["position"], opt["location"],
                                           opt["feature"])
                ok = ours == theirs and bool(ours)
                stats["verified" if ok else "feature_mismatch"] += 1
                rows[(tile.description, tile.turns, side.value,
                      opt["feature"], _canonical_loc(want[1], opt["feature"]))].append(
                    (ok, len(ours)))
                if not ok:
                    stats.setdefault("mismatch_samples", []).append(
                        {"kind": tile.description, "side": side.value,
                         "ours": sorted(ours)[:8], "jcz": sorted(theirs)[:8]})
            else:
                if not wants_confirm(jst) and (jst.get("action") or {}).get("canPass"):
                    jst = eng.pass_()
                board, _ = game.get_next_state(board, int(a))
            if wants_confirm(jst):
                jst = eng.commit()
            if is_over(jst):
                break
    finally:
        eng.close()


def _canonical_loc(tokens, feature):
    """Spell a token set the way JCZ itself would (so the table is greppable
    against a raw protocol log)."""
    if feature == "Monastery":
        return JCZ_MONASTERY_LOCATION
    if feature == "Field":
        return format_field_location(JCZ_TO_HALF_EDGE[t] for t in tokens)
    return format_edge_location(JCZ_TO_SIDE[t] for t in tokens)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", action="append", required=True)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--r9", action="store_true")
    ap.add_argument("--jar", default=None)
    ap.add_argument("--tiles", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    tile_map = load_tile_mapping()
    recs = []
    for src in args.games:
        recs.extend(load_corpus(Path(src))[: args.limit])

    rows: dict = defaultdict(list)
    stats: Counter = Counter()
    for rec in recs:
        run(rec, tile_map, rows, stats, jar=args.jar, tiles=args.tiles)

    hdr = ["our_tile_kind", "our_turns", "our_slot", "jcz_feature", "jcz_location",
           "n_deploys", "n_feature_verified", "max_feature_atoms"]
    lines = ["\t".join(hdr)]
    for key in sorted(rows):
        obs = rows[key]
        lines.append("\t".join(str(v) for v in (
            *key, len(obs), sum(1 for ok, _ in obs if ok), max(n for _, n in obs))))
    text = "\n".join(lines) + "\n"

    by_feature = Counter(k[3] for k in rows)
    print(text)
    print(f"deploys={stats['deploys']}  feature-verified={stats['verified']}  "
          f"feature-MISMATCH={stats['feature_mismatch']}  unmapped={stats['unmapped']}")
    print("distinct (kind,rot,slot) rows per JCZ feature type:", dict(by_feature))
    if stats.get("mismatch_samples"):
        print(json.dumps(stats["mismatch_samples"][:3], indent=1))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"wrote {args.out}")
    return 1 if (stats["feature_mismatch"] or stats["unmapped"]) else 0


if __name__ == "__main__":
    sys.exit(main())
