#!/usr/bin/env python3
"""PHASE 0.3 — deterministic, NET-FREE reproduction of the invalid-visit clip's
root cause: a legal-moves-CACHE collision between two rotation-instances of the
same physical position.

Mechanism (from the fix comment in selfplay.py):
  A rotationally-symmetric tile (e.g. straight_road) placed at the SAME (row,col)
  in two 180-equivalent rotations yields EDGE-IDENTICAL boards -> identical
  `string_representation` (the transposition key) -> but the engine stores the
  tile's `.farms` in a rotated order, so `possible_meeple_actions` picks a
  different representative farmer corner (`farmer_positions[0]`). The SAME physical
  farm therefore encodes to a DIFFERENT meeple action index. Because the legal
  cache is keyed by `string_representation`, a cache entry written for instance A
  is served for instance B -> B's snapshot mask carries A's farmer indices, which
  differ from the ones a fresh search on B actually visits -> the clip.

This script plays seed 0 with a deterministic "lowest-legal-action" policy and
scans each ply for the collision, then demonstrates the stale-cache serving.
Run: .venv/bin/python scripts/invalid_visit_clip/repro.py
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import random
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402


def find_collision(seed: int, max_plies: int = 80):
    """Play a deterministic line; at each TILES decision look for two legal
    actions whose resulting boards share a string_representation but differ in
    fresh legal mask (the collision). Return the first one found."""
    random.seed(seed)
    g = Game(enable_legal_moves_cache=False)   # NO cache: fresh masks everywhere
    board = g.get_init_board()
    for ply in range(max_plies):
        if g.get_game_ended(board, 0) != 0.0:
            break
        mask = g.get_valid_moves(board)
        legal = list(map(int, np.flatnonzero(mask)))
        if not legal:
            break
        if board.state.phase == GamePhase.TILES and len(legal) >= 2:
            # group children by string_representation key
            by_key = {}
            for a in legal:
                child, _ = g.get_next_state(board, a)
                key = g.string_representation(child)
                fresh = g.get_valid_moves(child)
                by_key.setdefault(key, []).append((a, fresh))
            for key, items in by_key.items():
                if len(items) < 2:
                    continue
                (a0, m0) = items[0]
                for (a1, m1) in items[1:]:
                    if not np.array_equal(m0, m1):
                        return {
                            "ply": ply, "next_tile": board.state.next_tile.description,
                            "actions": (a0, a1),
                            "key_prefix": key[:40],
                            "mask0": sorted(map(int, np.flatnonzero(m0))),
                            "mask1": sorted(map(int, np.flatnonzero(m1))),
                        }
        # advance deterministically (lowest legal action)
        board, _ = g.get_next_state(board, legal[0])
    return None


def demo_stale_cache(seed: int, coll: dict):
    """Reconstruct the collision position and show a cache-ENABLED Game serves
    instance-A's mask for instance-B (the stale-cache bug), while clearing the
    cache first yields each instance's own (differing) mask."""
    random.seed(seed)
    g = Game(enable_legal_moves_cache=False)
    board = g.get_init_board()
    for ply in range(coll["ply"]):
        mask = g.get_valid_moves(board)
        legal = list(map(int, np.flatnonzero(mask)))
        board, _ = g.get_next_state(board, legal[0])
    a0, a1 = coll["actions"]
    childA, _ = g.get_next_state(board, a0)
    childB, _ = g.get_next_state(board, a1)
    keyA = g.string_representation(childA)
    keyB = g.string_representation(childB)
    # cache-enabled Game: write A first, then read B (same key) -> stale A mask
    gc = Game(enable_legal_moves_cache=True)
    maskA_cached = gc.get_valid_moves(childA).copy()     # writes cache under keyA
    maskB_served = gc.get_valid_moves(childB).copy()      # keyB == keyA -> stale A
    # fresh (no-cache) truth for B
    maskB_fresh = Game(enable_legal_moves_cache=False).get_valid_moves(childB).copy()
    return {
        "same_key": keyA == keyB,
        "B_served_equals_A": np.array_equal(maskB_served, maskA_cached),
        "B_served_equals_freshB": np.array_equal(maskB_served, maskB_fresh),
        "A_fresh_neq_B_fresh": not np.array_equal(maskA_cached, maskB_fresh),
        "maskA": sorted(map(int, np.flatnonzero(maskA_cached))),
        "maskB_served": sorted(map(int, np.flatnonzero(maskB_served))),
        "maskB_fresh": sorted(map(int, np.flatnonzero(maskB_fresh))),
    }


if __name__ == "__main__":
    for seed in range(8):
        coll = find_collision(seed)
        if coll:
            print(f"[seed {seed}] COLLISION at ply {coll['ply']} "
                  f"tile={coll['next_tile']} actions={coll['actions']}")
            print(f"   mask0={coll['mask0']}")
            print(f"   mask1={coll['mask1']}")
            demo = demo_stale_cache(seed, coll)
            print(f"   stale-cache demo: same_key={demo['same_key']} "
                  f"B_served==A={demo['B_served_equals_A']} "
                  f"B_served==freshB={demo['B_served_equals_freshB']} "
                  f"A_fresh!=B_fresh={demo['A_fresh_neq_B_fresh']}")
            print(f"   maskA={demo['maskA']} maskB_served={demo['maskB_served']} "
                  f"maskB_fresh={demo['maskB_fresh']}")
            break
    else:
        print("no collision found in seeds 0-7 (unexpected)")
