#!/usr/bin/env python3
"""Stage 0 of the de-objectified flat leaf (DEOBJECTIFY_LEAF_PLAN_2026-06-09).

MEASURE the leaf-OFF per-leaf cost breakdown so we know where the flat-leaf
rewrite should invest. The production leaf (`virtual_score_v2`, compact OFF) is:

    base  = virtual_score(state, p)         # copy.deepcopy + count_final_scores
    bonus = _closure_anticipation_bonus(state, p) for p in (player, opp)

We split the per-leaf wallclock across three buckets:
  (a) copy.deepcopy(state)            -- the per-leaf snapshot
  (b) count_final_scores(snapshot)    -- end-of-game scoring flood-fills
  (c) _closure_anticipation_bonus x2  -- the v2.7 closure/farm-growth passes

Method: DIRECT repeatable timing (min-of-reps, robust to a busy box) of three
production-faithful measurements, NOT cProfile (whose per-call overhead inflates
deepcopy's many tiny recursive calls relative to the few large count_final_scores
calls). cProfile is run separately at the end, only for the WITHIN-bucket detail
(which flood-fill -- farm vs city vs road -- dominates count_final_scores), to
prioritise Stage 1/2.

  t_dc   = copy.deepcopy(state)                                  -> bucket (a)
  t_base = virtual_score(state, p)  (deepcopy + count_final)     -> (b) = t_base - t_dc
  t_bon  = the two _closure_anticipation_bonus passes, on a WARM cache
           (warmed by an untimed virtual_score, exactly as production shares it)
                                                                 -> bucket (c)

Read-only; run with nice -n 19. NOT a throughput bench (that needs a quiet box).

Usage:
  PYTHONPATH=.../src:.../engine nice -n 19 python scripts/stage0_leaf_breakdown.py --n 40 --reps 5
"""
from __future__ import annotations

import argparse
import copy
import cProfile
import os
import pstats
import random
import sys
import time
from pathlib import Path

# Production v2.7 leaf knobs MUST be set before importing virtual_score_v2
# (DEFAULT_CONFIG is built from these at import). Default to production here so
# the script is correct however it is launched.
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

import carcassonne_ai  # noqa: E402
import wingedsheep  # noqa: E402
from carcassonne_ai import virtual_score as _vs  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score import virtual_score  # noqa: E402
from carcassonne_ai.virtual_score_v2 import (  # noqa: E402
    DEFAULT_CONFIG,
    _closure_anticipation_bonus,
    virtual_score_v2,
)


def collect(n_games: int, snap_every: int, seed: int):
    g = Game()
    states = []
    for gi in range(n_games):
        random.seed(seed + gi)
        b = g.get_init_board()
        p = 0
        while g.get_game_ended(b, 0) == 0.0 and p < 400:
            legal = np.flatnonzero(g.get_valid_moves(b))
            if legal.size == 0:
                break
            b, _ = g.get_next_state(b, int(random.choice(legal.tolist())))
            p += 1
            if p % snap_every == 0 and g.get_game_ended(b, 0) == 0.0:
                states.append(b.state)
        states.append(b.state)
    return [s for s in states if s.players == 2]


def _min_reps(fn, reps: int) -> float:
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def time_deepcopy(states, reps: int) -> float:
    def run():
        for s in states:
            copy.deepcopy(s)
    return _min_reps(run, reps)


def time_base(states, reps: int) -> float:
    """virtual_score = deepcopy + count_final_scores (production caches on)."""
    def run():
        for s in states:
            virtual_score(s, 0)
    return _min_reps(run, reps)


def time_bonus_warm(states, reps: int) -> float:
    """The two closure-bonus passes on a WARM shared cache, exactly as the
    production leaf shares it: an UNTIMED virtual_score (with the same fc/cc
    dicts attached to the live state) warms the farm/city caches via
    count_final_scores; only the two bonus passes are timed."""
    best = float("inf")
    for _ in range(reps):
        # warm all caches first (untimed)
        warmed = []
        for s in states:
            fc = {}
            cc = {}
            s._farm_cache = fc
            s._city_cache = cc
            virtual_score(s, 0, farm_cache=fc, city_cache=cc)  # populates fc/cc
            warmed.append(s)
        t = time.perf_counter()
        for s in warmed:
            _closure_anticipation_bonus(s, 0, DEFAULT_CONFIG)
            _closure_anticipation_bonus(s, 1, DEFAULT_CONFIG)
        best = min(best, time.perf_counter() - t)
        for s in warmed:
            try:
                del s._farm_cache
                del s._city_cache
            except AttributeError:
                pass
    return best


def time_full(states, reps: int) -> float:
    def run():
        for s in states:
            virtual_score_v2(s, 0, DEFAULT_CONFIG)
    return _min_reps(run, reps)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="games to play for state collection")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--seed", type=int, default=777)
    a = ap.parse_args()

    # Guard: production config (compact OFF, caches ON) and worktree imports.
    assert _vs.USE_COMPACT_LEAF is False, "expected compact OFF for the leaf-OFF baseline"
    assert "/carc-leafdev/" in carcassonne_ai.__file__, f"not worktree carcassonne_ai: {carcassonne_ai.__file__}"
    assert "/carc-leafdev/" in wingedsheep.__file__, f"not worktree wingedsheep: {wingedsheep.__file__}"
    print(f"carcassonne_ai: {carcassonne_ai.__file__}")
    print(f"wingedsheep   : {wingedsheep.__file__}")
    print(f"USE_FARM_CACHE={_vs.USE_FARM_CACHE} USE_CITY_CACHE={_vs.USE_CITY_CACHE} "
          f"USE_COMPACT_LEAF={_vs.USE_COMPACT_LEAF}")
    print(f"closure_p={DEFAULT_CONFIG.closure_p} cap={DEFAULT_CONFIG.bonus_cap}")

    states = collect(a.n, 5, a.seed)
    nleaf = len(states)  # we measure per "leaf eval" = one virtual_score_v2 call
    print(f"\n{len(states)} two-player states, reps={a.reps} (min-of-reps)\n")

    # warm code paths
    time_full(states[:3], 1)

    t_dc = time_deepcopy(states, a.reps)
    t_base = time_base(states, a.reps)
    t_bon = time_bonus_warm(states, a.reps)
    t_full = time_full(states, a.reps)

    t_cfs = max(t_base - t_dc, 0.0)  # count_final_scores ~= base - deepcopy
    # full = base + bonus(x2) + small overhead (cache build/teardown, capping)
    t_overhead = max(t_full - t_base - t_bon, 0.0)

    def line(name, t):
        print(f"  {name:<34} {t * 1e3 / nleaf:8.4f} ms/leaf   ({t:7.3f}s tot   {100 * t / t_full:5.1f}% of full)")

    print("=== per-leaf wallclock breakdown (compact OFF = production) ===")
    line("(a) copy.deepcopy", t_dc)
    line("(b) count_final_scores", t_cfs)
    line("(c) closure bonus x2 (warm)", t_bon)
    line("    overhead (cache/cap/round)", t_overhead)
    print("    " + "-" * 60)
    line("    FULL virtual_score_v2", t_full)

    print("\n=== interpretation ===")
    deobj_target = t_dc + t_cfs  # deepcopy + count_final_scores = Stage 2's lever
    print(f"  deepcopy + count_final_scores (Stage 2 lever) = {100 * deobj_target / t_full:.1f}% of full")
    print(f"  closure bonus (Stage 3 lever)                 = {100 * t_bon / t_full:.1f}% of full")
    if deobj_target / t_full < 0.4:
        print("  -> Stage-2 lever is SMALL (<40%): the flat-base-score win is capped; reconsider scope.")
    else:
        print("  -> Stage-2 lever is the big chunk: flat base score (no deepcopy) is worth building.")

    # cProfile: WITHIN-bucket detail only -- which flood-fill dominates
    # count_final_scores (farm find_farm vs city _compute_city vs road) + how the
    # closure passes split. Sorted by tottime (self time). cProfile inflates
    # deepcopy's tiny recursive calls, so DO NOT read cross-bucket fractions from
    # here -- use the direct timing above for that.
    print("\n=== cProfile (full virtual_score_v2, by self-time) -- within-bucket detail ===")
    pr = cProfile.Profile()
    pr.enable()
    for s in states:
        virtual_score_v2(s, 0, DEFAULT_CONFIG)
        virtual_score_v2(s, 1, DEFAULT_CONFIG)
    pr.disable()
    st = pstats.Stats(pr, stream=sys.stdout)
    st.sort_stats("tottime")
    st.print_stats(22)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
