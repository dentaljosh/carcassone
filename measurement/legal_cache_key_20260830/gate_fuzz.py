#!/usr/bin/env python3
"""Fuzz gate for the `game_wrapper.Game._legal_cache` injective-key fix.

WHAT IS BEING GATED. `Game.get_valid_moves` memoizes the legal mask under
`Game.string_representation(board)`. Until 2026-08-30 that key's per-tile
component was `(4 outer edges, shield, chapel, flowers)`, which is NOT
injective for a 180-degree-rotationally-symmetric tile: the two rotations
present the same outer edges but DIFFERENT farm slots, so the second sibling
to ask was served the first sibling's mask — offering a farmer corner that is
illegal there and withholding the one that is legal.

WHY THE WALK BRANCHES. A straight-line self-play walk can never exhibit the
defect: it visits one board per ply, so no two live boards ever share a key.
The defect needs the shape every affected tool actually has — ONE `Game`
whose memo spans SIBLING afterstates (`chain_census.chain_values`,
`meeple_tie_census._process_game`, the EV-loss grader, `run_census`). So at
every TILES ply this gate expands EVERY legal tile child and reads that
child's meeple-phase mask through the memoized `Game`, comparing against a
second, cache-DISABLED `Game` on the very same `Board` object (one apply, two
masks — the honest mask is by construction the same computation with no memo
in front of it).

GATES (all four must hold, `--mode fixed`):
  G-MASK      every meeple-phase mask read through the memo == the
              cache-disabled mask. Zero mismatches.
  G-COVER     every 180-symmetric tile in the deck appeared at every one of
              its 4 rotations among the expanded children, and both banked
              witnesses (`city_left_right`, `straight_road`) are present.
  G-WITNESS   `--mode legacy` (the historical key, `CARCASSONNE_FIX_LEGAL_
              CACHE_KEY=0`) REPRODUCES mismatches, and both witness tiles are
              among the colliding tiles. A fix that "passes" because the fuzz
              cannot reach the bug proves nothing; this is the teeth check.
  G-CACHE     the memo still memoizes — hit rate is reported per mode so the
              key growth cannot silently disable memoization.

The R9 farm-data latch is import-time, so `--mode` x R9 is run as four
separate processes by `run_gate.sh`.

Usage:
  gate_fuzz.py --mode fixed|legacy --games N --seed-start S --workers W --out F
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter

import numpy as np

WITNESS_TILES = ("city_left_right", "straight_road")


def symmetric_tiles() -> dict:
    """Every deck tile whose 4 outer edges are invariant under a 180-degree
    turn — exactly the tiles whose rotation the OLD key could not see."""
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    def edges(t):
        return tuple(t.get_type(s).value
                     for s in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT))

    out = {}
    for name, tile in base_tiles.items():
        r0, r2 = tile.turn(0), tile.turn(2)
        if edges(r0) == edges(r2):
            out[name] = {"edges": list(edges(r0))}
    return out


def _one_game(task: dict) -> dict:
    """Branching walk over one game. Returns counters, mismatches, coverage."""
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    from carcassonne_ai.game_wrapper import Game, WindowOverflowError

    seed = int(task["seed"])
    ctr = Counter()
    mismatches = []
    cover = Counter()

    random.seed(seed)
    g_cache = Game(enable_legal_moves_cache=True)
    g_fresh = Game(enable_legal_moves_cache=False)
    board = g_cache.get_init_board()
    rng = random.Random(seed ^ 0xA5A5A5)

    def compare(b, ctx):
        """Cached-first (production order), then the honest mask on the SAME
        Board. Any difference is the memo answering for a different board."""
        try:
            m_cached = g_cache.get_valid_moves(b)
            m_fresh = g_fresh.get_valid_moves(b)
        except WindowOverflowError:
            ctr["window_overflow"] += 1
            return
        ctr["compared"] += 1
        if not np.array_equal(m_cached, m_fresh):
            ctr["mismatch"] += 1
            c = sorted(int(i) for i in np.flatnonzero(m_cached))
            f = sorted(int(i) for i in np.flatnonzero(m_fresh))
            if len(mismatches) < 40:
                mismatches.append({
                    **ctx,
                    "cached_minus_fresh": sorted(set(c) - set(f)),
                    "fresh_minus_cached": sorted(set(f) - set(c)),
                })

    ply = 0
    while g_cache.get_game_ended(board, 0) == 0.0 and ply < 400:
        st = board.state
        if st.phase == GamePhase.MEEPLES:
            ctr["meeple_plies"] += 1
            compare(board, {"seed": seed, "ply": ply, "kind": "on_walk"})
            try:
                legal = np.flatnonzero(g_cache.get_valid_moves(board))
            except WindowOverflowError:
                break
        else:
            ctr["tile_plies"] += 1
            try:
                legal = np.flatnonzero(g_cache.get_valid_moves(board))
            except WindowOverflowError:
                break
            # Expand EVERY tile sibling and read its meeple-phase mask through
            # the shared memo. This is the shape that exposes the collision.
            for a in legal:
                child, _ = g_cache.get_next_state(board, int(a))
                lta = child.state.last_tile_action
                if lta is None:
                    continue
                desc = lta.tile.description
                rot = int(getattr(lta, "tile_rotations", -1))
                cover[(desc, rot)] += 1
                if child.state.phase == GamePhase.MEEPLES:
                    ctr["children_meeple"] += 1
                    compare(child, {"seed": seed, "ply": ply, "kind": "sibling",
                                    "action": int(a), "tile": desc, "rotation": rot,
                                    "row": lta.coordinate.row,
                                    "col": lta.coordinate.column})
        if len(legal) == 0:
            break
        board, _ = g_cache.get_next_state(board, int(rng.choice(legal)))
        ply += 1

    stats = g_cache.cache_stats()
    return {
        "seed": seed,
        "counters": dict(ctr),
        "mismatches": mismatches,
        "coverage": {f"{d}|{r}": n for (d, r), n in cover.items()},
        "cache": {"hits": stats["hits"], "misses": stats["misses"],
                  "size": stats["size"]},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("fixed", "legacy"), required=True)
    ap.add_argument("--games", type=int, default=300)
    ap.add_argument("--seed-start", type=int, default=880000000)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import carcassonne_ai.game_wrapper as gw
    from carcassonne_ai.rules_profile import r9_env_on

    want = a.mode == "fixed"
    if gw._FIX_LEGAL_CACHE_KEY is not want:
        print(f"FATAL: mode={a.mode} but _FIX_LEGAL_CACHE_KEY="
              f"{gw._FIX_LEGAL_CACHE_KEY}; set CARCASSONNE_FIX_LEGAL_CACHE_KEY "
              f"in the ENVIRONMENT (it is import-latched).", file=sys.stderr)
        return 2

    sym = symmetric_tiles()
    tasks = [{"seed": a.seed_start + i} for i in range(a.games)]
    t0 = time.time()

    ctr = Counter()
    cover = Counter()
    mismatches = []
    cache_tot = Counter()
    first_game_cache = None

    if a.workers > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(a.workers) as pool:
            results = pool.imap(_one_game, tasks, chunksize=2)
            results = list(results)
    else:
        results = [_one_game(t) for t in tasks]

    for i, res in enumerate(results):
        ctr.update(res["counters"])
        for k, n in res["coverage"].items():
            cover[k] += n
        mismatches.extend(res["mismatches"][: max(0, 60 - len(mismatches))])
        cache_tot.update(res["cache"])
        if i == 0:
            first_game_cache = res["cache"]

    # --- G-COVER ---------------------------------------------------------
    missing = []
    for name in sym:
        for rot in range(4):
            if cover.get(f"{name}|{rot}", 0) == 0:
                missing.append(f"{name}|{rot}")
    witness_covered = {
        w: sum(cover.get(f"{w}|{r}", 0) for r in range(4)) for w in WITNESS_TILES
    }
    g_cover = (not missing) and all(v > 0 for v in witness_covered.values())

    # --- G-MASK / G-WITNESS ---------------------------------------------
    n_mismatch = int(ctr.get("mismatch", 0))
    colliding_tiles = sorted({m.get("tile") for m in mismatches if m.get("tile")})
    if a.mode == "fixed":
        gate = {"G-MASK": n_mismatch == 0, "G-COVER": g_cover}
    else:
        gate = {
            "G-WITNESS-fires": n_mismatch > 0,
            "G-WITNESS-tiles": all(w in colliding_tiles for w in WITNESS_TILES),
            "G-COVER": g_cover,
        }

    total = cache_tot["hits"] + cache_tot["misses"]
    out = {
        "mode": a.mode,
        "fix_legal_cache_key": gw._FIX_LEGAL_CACHE_KEY,
        "r9": r9_env_on(),
        "env": {k: os.environ.get(k) for k in
                ("CARCASSONNE_FIX_LEGAL_CACHE_KEY", "CARCASSONNE_FIX_R9")},
        "games": a.games,
        "seed_start": a.seed_start,
        "secs": round(time.time() - t0, 1),
        "counters": dict(ctr),
        "symmetric_tiles": sym,
        "coverage_missing": missing,
        "witness_tile_placements": witness_covered,
        "n_mismatch": n_mismatch,
        "colliding_tiles": colliding_tiles,
        "mismatch_examples": mismatches[:12],
        "cache": {
            "hits": cache_tot["hits"], "misses": cache_tot["misses"],
            "entries": cache_tot["size"],
            "hit_rate": (cache_tot["hits"] / total) if total else 0.0,
            "first_game": first_game_cache,
        },
        "gates": gate,
        "PASS": all(gate.values()),
    }
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in
                      ("mode", "r9", "games", "secs", "n_mismatch",
                       "colliding_tiles", "coverage_missing", "gates", "PASS")},
                     indent=1))
    print(f"[cache] hit_rate={out['cache']['hit_rate']:.4f} "
          f"hits={out['cache']['hits']} misses={out['cache']['misses']}")
    return 0 if out["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
