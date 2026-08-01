"""P1 in-phase investigation: is `PointsCollector.count_final_scores`'s
`set(...).pop()` iteration order outcome-relevant?

WHY THIS EXISTS
---------------
`count_final_scores` snapshots each player's meeples into a **set** and drains it
with `.pop()`:

    meeples_to_remove: Set[MeeplePosition] = set(placed_meeples)
    while len(meeples_to_remove) > 0:
        meeple_position = meeples_to_remove.pop()

`MeeplePosition.__hash__` bottoms out in `hash(<enum member>)`, which CPython
derives from object identity — so the drain order is **not stable across
processes**.  The Rust port cannot reproduce "CPython set order"; it has to pick
*some* deterministic order.  That is only sound if the order is outcome-
irrelevant.  This script measures that, rather than assuming it.

WHAT IS TESTED
--------------
An order-parameterised transcription of `count_final_scores` (`_count_ordered`,
byte-for-byte the same body except the drain is an explicit list) is run over
many random permutations of each player's meeple list, on many positions, and
the resulting `state.scores` are compared.  The engine's own
`count_final_scores` is included as one more "order" so the transcription is
pinned to the original, not just to itself.

Positions come from the real corpora (champ games / E4 archives / golden games)
replayed to a spread of plies -- deliberately including mid-game plies, where
many more meeples are on the board than at the natural terminal, so the sample
stresses multi-meeple fields rather than the sparse endgame.

VERDICT
-------
Exit 0 + `ORDER-IRRELEVANT` -> the port may choose any deterministic order.
Exit 1 + `ESCALATE`         -> a reproducer is written and the port must stop.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")

# ⚠️ BEFORE any carcassonne_ai import (see scripts/rustport/prod_leaf_env.py):
# `root_replay` below pulls in carcassonne_ai, so this module can win the
# DEFAULT_CONFIG freeze race in a full-tree pytest.
import prod_leaf_env  # noqa: E402,F401

from wingedsheep.carcassonne.objects.city import City  # noqa: E402
from wingedsheep.carcassonne.objects.farm import Farm  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_type import MeepleType  # noqa: E402
from wingedsheep.carcassonne.objects.terrain_type import TerrainType  # noqa: E402
from wingedsheep.carcassonne.utils.city_util import CityUtil  # noqa: E402
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402
from wingedsheep.carcassonne.utils.meeple_util import MeepleUtil  # noqa: E402
from wingedsheep.carcassonne.utils.points_collector import PointsCollector  # noqa: E402
from wingedsheep.carcassonne.utils.road_util import RoadUtil  # noqa: E402

from _g0_common import environment  # noqa: E402
from root_replay import replay_actions  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p1"


def write_result(name: str, payload: dict) -> Path:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"P1_{name}.json"
    path.write_text(json.dumps({"gate": f"P1/{name}", "env": environment(), **payload},
                               indent=2, default=str))
    return path


# ---------------------------------------------------------------------------
# The order-parameterised transcription of PointsCollector.count_final_scores.
# Kept structurally line-for-line with engine/wingedsheep/carcassonne/utils/
# points_collector.py::count_final_scores; the ONLY difference is that the
# `set(placed_meeples)` + `.pop()` drain is replaced by an explicit ordering.
# ---------------------------------------------------------------------------
def _count_ordered(game_state, order_fn) -> None:
    cls = PointsCollector
    for player, placed_meeples in enumerate(game_state.placed_meeples):
        # set(...) dedups; order_fn then imposes an explicit drain order.
        pending = order_fn(player, list(set(placed_meeples)))
        for meeple_position in pending:
            tile = game_state.board[meeple_position.coordinate_with_side.coordinate.row][
                meeple_position.coordinate_with_side.coordinate.column
            ]
            terrain_type = tile.get_type(meeple_position.coordinate_with_side.side)

            if terrain_type == TerrainType.CITY:
                city: City = CityUtil.find_city(
                    game_state=game_state,
                    city_position=meeple_position.coordinate_with_side,
                )
                meeples = CityUtil.find_meeples(game_state=game_state, city=city)
                counts = cls.get_meeple_counts_per_player(meeples)
                winning_players = cls.get_winning_players(counts)
                if winning_players:
                    points = cls.count_city_points(game_state=game_state, city=city)
                    for w in winning_players:
                        game_state.scores[w] += points
                MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)
                continue

            if terrain_type == TerrainType.ROAD:
                road = RoadUtil.find_road(
                    game_state=game_state,
                    road_position=meeple_position.coordinate_with_side,
                )
                meeples = RoadUtil.find_meeples(game_state=game_state, road=road)
                counts = cls.get_meeple_counts_per_player(meeples)
                winning_players = cls.get_winning_players(counts)
                if winning_players:
                    points = cls.count_road_points(game_state=game_state, road=road)
                    for w in winning_players:
                        game_state.scores[w] += points
                MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)
                continue

            if terrain_type == TerrainType.CHAPEL or terrain_type == TerrainType.FLOWERS:
                points = cls.chapel_or_flowers_points(
                    game_state=game_state,
                    coordinate=meeple_position.coordinate_with_side.coordinate,
                )
                game_state.scores[player] += points
                meeples_per_player = [[] for _ in range(game_state.players)]
                meeples_per_player[player].append(meeple_position)
                MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples_per_player)
                continue

            if meeple_position.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                farm: Farm = FarmUtil.find_farm_by_coordinate(
                    game_state=game_state, position=meeple_position.coordinate_with_side
                )
                meeples = FarmUtil.find_meeples(game_state=game_state, farm=farm)
                counts = cls.get_meeple_counts_per_player(meeples)
                winning_players = cls.get_winning_players(counts)
                if winning_players:
                    points = cls.count_farm_points(game_state=game_state, farm=farm)
                    for w in winning_players:
                        game_state.scores[w] += points
                MeepleUtil.remove_meeples(game_state=game_state, meeples=meeples)
                continue


def _outcome(state) -> tuple:
    """Everything count_final_scores is allowed to touch: scores, meeple pools,
    and the residual placed_meeples (as a canonical multiset, since the LIST
    order is itself order-of-removal dependent and is compared separately)."""
    residual = tuple(
        tuple(
            sorted(
                (
                    mp.meeple_type.value,
                    mp.coordinate_with_side.coordinate.row,
                    mp.coordinate_with_side.coordinate.column,
                    mp.coordinate_with_side.side.value,
                )
                for mp in state.placed_meeples[p]
            )
        )
        for p in range(state.players)
    )
    return (tuple(state.scores), tuple(state.meeples), residual)


def _residual_list_order(state) -> tuple:
    return tuple(
        tuple(
            (
                mp.meeple_type.value,
                mp.coordinate_with_side.coordinate.row,
                mp.coordinate_with_side.coordinate.column,
                mp.coordinate_with_side.side.value,
            )
            for mp in state.placed_meeples[p]
        )
        for p in range(state.players)
    )


# ---------------------------------------------------------------------------
# Position sampling
# ---------------------------------------------------------------------------
def load_corpus(max_games: int, plies_per_game: int, rng: random.Random) -> list:
    """(label, deck_seed, actions, ply) roots across all three corpora."""
    roots = []

    champ = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
    games = []
    with champ.open() as fh:
        for line in fh:
            if line.strip():
                games.append(json.loads(line))
    rng.shuffle(games)
    for g in games[:max_games]:
        acts, n = g["actions"], len(g["actions"])
        # mid-game plies carry the most meeples; the terminal ply is always kept.
        picks = sorted({n} | {rng.randrange(max(1, n // 3), n) for _ in range(plies_per_game - 1)})
        for ply in picks:
            roots.append(("champ", int(g["deck_seed"]), acts, int(ply)))

    for path in sorted((REPO / "measurement" / "e4_games").glob("*.json")):
        d = json.loads(path.read_text())
        acts, n = d["actions"], len(d["actions"])
        picks = sorted({n} | {rng.randrange(max(1, n // 3), n) for _ in range(plies_per_game - 1)})
        for ply in picks:
            roots.append(("e4", int(d["deck_seed"]), acts, int(ply)))

    fixture = REPO / "tests" / "golden" / "golden_fixture.json"
    if fixture.exists():
        gd = json.loads(fixture.read_text()).get("games", {})
        for seed, acts in gd.items():
            acts = acts["actions"] if isinstance(acts, dict) else acts
            n = len(acts)
            picks = sorted({n} | {rng.randrange(max(1, n // 3), n) for _ in range(plies_per_game - 1)})
            for ply in picks:
                roots.append(("golden", int(seed), acts, int(ply)))

    return roots


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=120)
    ap.add_argument("--plies-per-game", type=int, default=8)
    ap.add_argument("--perms", type=int, default=12, help="random drain orders per position")
    ap.add_argument("--seed", type=int, default=20260731)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    roots = load_corpus(args.games, args.plies_per_game, rng)

    n_positions = 0
    n_comparisons = 0
    n_meeples_seen = 0
    max_meeples = 0
    n_multi = 0  # positions with >= 2 meeples for some player (where order can matter)
    mismatches = []
    list_order_sensitive = 0

    for label, deck_seed, actions, ply in roots:
        try:
            _game, board = replay_actions(deck_seed, actions, ply)
        except Exception as exc:  # replay failure is an environment problem, surface it
            mismatches.append({"kind": "replay_error", "label": label,
                               "deck_seed": deck_seed, "ply": ply, "error": repr(exc)})
            continue
        state = board.state
        nm = sum(len(pm) for pm in state.placed_meeples)
        if nm == 0:
            continue
        n_positions += 1
        n_meeples_seen += nm
        max_meeples = max(max_meeples, nm)
        if any(len(pm) >= 2 for pm in state.placed_meeples):
            n_multi += 1

        # Reference: the ENGINE's own count_final_scores (native set order).
        ref_state = copy.deepcopy(state)
        PointsCollector.count_final_scores(game_state=ref_state)
        ref = _outcome(ref_state)
        ref_list = _residual_list_order(ref_state)

        orders = []
        # deterministic candidate orders the Rust port might plausibly pick
        orders.append(lambda p, ms: sorted(
            ms, key=lambda m: (m.coordinate_with_side.coordinate.row,
                               m.coordinate_with_side.coordinate.column,
                               m.coordinate_with_side.side.value,
                               m.meeple_type.value)))
        orders.append(lambda p, ms: sorted(
            ms, key=lambda m: (-m.coordinate_with_side.coordinate.row,
                               -m.coordinate_with_side.coordinate.column,
                               m.coordinate_with_side.side.value,
                               m.meeple_type.value)))
        # placement (list insertion) order and its reverse
        orders.append(lambda p, ms, st=state: [m for m in st.placed_meeples[p] if m in ms])
        orders.append(lambda p, ms, st=state: [m for m in reversed(st.placed_meeples[p]) if m in ms])
        for _ in range(args.perms):
            perm_rng = random.Random(rng.randrange(1 << 30))

            def _shuffled(p, ms, r=perm_rng):
                out = list(ms)
                r.shuffle(out)
                return out

            orders.append(_shuffled)

        for oi, order_fn in enumerate(orders):
            trial = copy.deepcopy(state)
            _count_ordered(trial, order_fn)
            got = _outcome(trial)
            n_comparisons += 1
            if got != ref:
                mismatches.append({
                    "kind": "outcome",
                    "label": label, "deck_seed": deck_seed, "ply": ply,
                    "order_index": oi,
                    "ref": [list(ref[0]), list(ref[1]), [list(x) for x in ref[2]]],
                    "got": [list(got[0]), list(got[1]), [list(x) for x in got[2]]],
                })
                if len(mismatches) >= 20:
                    break
            if _residual_list_order(trial) != ref_list:
                list_order_sensitive += 1
        if len(mismatches) >= 20:
            break

    ok = not mismatches
    payload = {
        "positions": n_positions,
        "comparisons": n_comparisons,
        "orders_per_position": 4 + args.perms,
        "meeples_seen": n_meeples_seen,
        "max_meeples_on_a_position": max_meeples,
        "positions_with_multi_meeple_player": n_multi,
        "outcome_mismatches": len(mismatches),
        "residual_list_ORDER_differences": list_order_sensitive,
        "verdict": "ORDER-IRRELEVANT" if ok else "ESCALATE",
        "args": vars(args),
        "mismatches": mismatches[:20],
    }
    path = write_result("p1_count_final_scores_order", payload)
    print(
        f"P1/count_final_scores_order: {'ORDER-IRRELEVANT' if ok else 'ESCALATE'}  "
        f"{n_positions} positions x {4 + args.perms} orders = {n_comparisons} comparisons, "
        f"{n_meeples_seen} meeples (max {max_meeples} on one position), "
        f"{len(mismatches)} outcome mismatches, "
        f"{list_order_sensitive} residual-list-order differences"
    )
    print(f"P1/count_final_scores_order: result -> {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
