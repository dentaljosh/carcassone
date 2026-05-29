"""Profile the v2.7 leaf hot path (find_farm) POST engine-fix (2026-05-29).

Path B Step 2 / find_farm-speedup prerequisite: before building a batch farm
decomposition we must confirm, with data, that `find_farm` is still the dominant
leaf cost after the complete-CC rewrite, and quantify how much of it is REDUNDANT
(the same farm region recomputed multiple times within one leaf eval). "Measure,
don't extrapolate" (CLAUDE.md).

What it does:
  1. Random-plays a few games, snapshotting board states across game depth (farm
     regions grow late, so depth matters for representativeness).
  2. cProfiles a loop of `virtual_score_v2(state, player)` over those states.
  3. Separately instruments `FarmUtil.find_farm` to count calls per leaf eval and
     how many land on an already-seen region (the dedup headroom).

Usage:  python scripts/profile_leaf_farm.py --games 6 --snap-every 8 --repeats 3
"""
from __future__ import annotations

import argparse
import cProfile
import copy
import io
import pstats
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2  # noqa: E402
from wingedsheep.carcassonne.utils.farm_util import FarmUtil  # noqa: E402


def collect_states(games: int, snap_every: int, seed_start: int, max_plies: int = 400):
    """Random-legal play; snapshot a deepcopy of the state every `snap_every`
    plies (only mid-game, non-terminal states — that's what MCTS leaves are)."""
    game = Game()
    states = []
    for g in range(games):
        random.seed(seed_start + g)
        board = game.get_init_board()
        plies = 0
        while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            action = int(random.choice(legal.tolist()))
            board, _ = game.get_next_state(board, action)
            plies += 1
            if plies % snap_every == 0 and game.get_game_ended(board, 0) == 0.0:
                states.append(copy.deepcopy(board.state))
    return states


def region_key(farm) -> frozenset:
    """Canonical identity of a farm region: the set of (row, col, connection-id)
    nodes. Start-independent after the 2026-05-29 fix, so two find_farm calls on
    the same field produce the same key."""
    return frozenset(
        (fcc.coordinate.row, fcc.coordinate.column, id(fcc.farmer_connection))
        for fcc in farm.farmer_connections_with_coordinate
    )


def instrument_redundancy(states):
    """Wrap find_farm to count, per virtual_score_v2 leaf eval, total calls and
    how many hit an already-computed region (the within-pass dedup headroom)."""
    orig_find_farm = FarmUtil.find_farm.__func__  # unwrap classmethod

    stats = {"calls": 0, "redundant": 0}
    per_leaf_calls = []
    per_leaf_redundant = []
    seen_this_leaf: set = set()

    def wrapped(cls, game_state, fcc):
        farm = orig_find_farm(cls, game_state, fcc)
        stats["calls"] += 1
        k = region_key(farm)
        if k in seen_this_leaf:
            stats["redundant"] += 1
        else:
            seen_this_leaf.add(k)
        return farm

    FarmUtil.find_farm = classmethod(wrapped)
    try:
        for st in states:
            seen_this_leaf.clear()
            c0, r0 = stats["calls"], stats["redundant"]
            virtual_score_v2(st, 0, DEFAULT_CONFIG)
            per_leaf_calls.append(stats["calls"] - c0)
            per_leaf_redundant.append(stats["redundant"] - r0)
    finally:
        FarmUtil.find_farm = classmethod(orig_find_farm)
    return stats, per_leaf_calls, per_leaf_redundant


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--snap-every", type=int, default=8)
    ap.add_argument("--repeats", type=int, default=3, help="profile loop passes over the states")
    ap.add_argument("--seed-start", type=int, default=10000)
    args = ap.parse_args(argv)

    print(f"collecting states: {args.games} games, snap every {args.snap_every} plies ...")
    states = collect_states(args.games, args.snap_every, args.seed_start)
    print(f"collected {len(states)} mid-game states")
    if not states:
        print("no states collected"); return 1

    # --- cProfile the leaf eval -------------------------------------------
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(args.repeats):
        for st in states:
            virtual_score_v2(st, 0, DEFAULT_CONFIG)
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("tottime")
    ps.print_stats(25)
    print("\n===== cProfile (top 25 by tottime) =====")
    print(s.getvalue())

    # Pull out the lines we care about for a compact summary.
    s2 = io.StringIO()
    pstats.Stats(pr, stream=s2).sort_stats("cumulative").print_stats(
        "find_farm|count_final_scores|deepcopy|count_farm_points|find_cities|virtual_score"
    )
    print("\n===== cumulative time for hot functions =====")
    print(s2.getvalue())

    # --- redundancy instrumentation ---------------------------------------
    stats, per_leaf_calls, per_leaf_redundant = instrument_redundancy(states)
    n = len(per_leaf_calls)
    tot = stats["calls"]
    red = stats["redundant"]
    print("\n===== find_farm redundancy (one pass over the states) =====")
    print(f"total find_farm calls:        {tot}")
    print(f"redundant (same region):      {red}  ({100*red/max(tot,1):.1f}%)")
    print(f"mean find_farm calls / leaf:  {np.mean(per_leaf_calls):.2f}")
    print(f"max  find_farm calls / leaf:  {max(per_leaf_calls)}")
    print(f"mean redundant / leaf:        {np.mean(per_leaf_redundant):.2f}")
    dist = Counter(per_leaf_calls)
    print(f"calls/leaf distribution:      {dict(sorted(dist.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
