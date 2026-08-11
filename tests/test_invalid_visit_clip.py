"""Phase 0.3 regression: the self-play invalid-visit clip was a legal-moves-CACHE
collision between two rotation-instances of the same physical position.

ROOT CAUSE (net-free, deterministic; see measurement/invalid_visit_clip/ROOT_CAUSE.md):
A rotationally-symmetric tile (straight_road) placed at the SAME (row,col) in two
180-equivalent rotations produces EDGE-IDENTICAL boards -> identical
`string_representation` (the transposition/cache key) -> but the engine stores the
tile's `.farms` in a rotated order, so `possible_meeple_actions` picks a different
representative farmer corner (`farmer_positions[0]`). The SAME physical farm thus
encodes to a DIFFERENT meeple action index. The legal cache is keyed by
`string_representation`, so an entry written for instance A is served for instance B
-> B's snapshot mask carries A's farmer indices, differing from what a fresh search
on B visits -> the clip.

FIX (src/carcassonne_ai/selfplay.py): `mcts.clear()` (which calls
`game.clear_caches()`) now runs BEFORE the snapshot mask is taken, so the snapshot
and the search root recompute an identical mask from the same board instance; the
silent clip became a hard assert-with-telemetry.

These tests pin the collision (so the mechanism can't silently change) and prove the
clear-before-snapshot ordering resolves the stale-cache serving. All net-free.
"""
import random

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import Game
from wingedsheep.carcassonne.objects.game_phase import GamePhase


def _replay_lowest_legal(seed: int, plies: int) -> tuple[Game, object]:
    """Deterministically play `plies` moves taking the lowest legal action each
    step (net-free, reproducible). Returns (game, board_at_ply)."""
    random.seed(seed)
    g = Game(enable_legal_moves_cache=False)
    b = g.get_init_board()
    for _ in range(plies):
        legal = np.flatnonzero(g.get_valid_moves(b))
        b, _ = g.get_next_state(b, int(legal[0]))
    return g, b


# The pinned deterministic repro (verified 2026-07-06):
SEED, PLY = 0, 8
ACT_A, ACT_B = 1044, 1046          # same (row,col), rotations 180 apart on straight_road
MASK_A = [2506, 2507, 2510]
MASK_B = [2508, 2509, 2510]


def test_collision_position_is_reproducible():
    """seed 0 reaches the straight_road collision at ply 8 with the pinned actions."""
    g, b = _replay_lowest_legal(SEED, PLY)
    assert b.state.phase == GamePhase.TILES
    assert b.state.next_tile.description == "straight_road"
    mask = g.get_valid_moves(b)
    assert mask[ACT_A] and mask[ACT_B], "both rotation actions must be legal here"


def test_rotation_instances_share_key_but_differ_in_mask():
    """The soundness fact: two children with the SAME string_representation key have
    DIFFERENT fresh legal masks -> the legal cache (keyed by that string) is unsound
    across rotation-instances."""
    g, b = _replay_lowest_legal(SEED, PLY)
    childA, _ = g.get_next_state(b, ACT_A)
    childB, _ = g.get_next_state(b, ACT_B)
    keyA = g.string_representation(childA)
    keyB = g.string_representation(childB)
    assert keyA == keyB, "the two rotation-instances must collide on the cache key"
    maskA = sorted(map(int, np.flatnonzero(g.get_valid_moves(childA))))
    maskB = sorted(map(int, np.flatnonzero(g.get_valid_moves(childB))))
    assert maskA == MASK_A and maskB == MASK_B
    assert maskA != maskB, "same key, different masks == the collision"


def test_stale_cache_serves_wrong_mask_without_clear():
    """The literal corruption path: a cache-enabled Game that wrote instance A's mask
    serves it for instance B (same key) -> B gets A's farmer indices, not its own."""
    g, b = _replay_lowest_legal(SEED, PLY)
    childA, _ = g.get_next_state(b, ACT_A)
    childB, _ = g.get_next_state(b, ACT_B)
    gc = Game(enable_legal_moves_cache=True)
    a_cached = gc.get_valid_moves(childA).copy()           # writes cache under the key
    b_served = gc.get_valid_moves(childB).copy()           # same key -> stale A mask
    b_fresh = Game(enable_legal_moves_cache=False).get_valid_moves(childB)
    assert np.array_equal(b_served, a_cached), "stale-cache serving reproduced"
    assert not np.array_equal(b_served, b_fresh), "served mask is wrong for B"


def test_clear_before_snapshot_resolves_the_stale_serving():
    """The FIX invariant: clearing the cache before the snapshot (what selfplay.py now
    does via mcts.clear() -> game.clear_caches()) makes the snapshot recompute instance
    B's own mask, so it matches what a fresh search root would use."""
    g, b = _replay_lowest_legal(SEED, PLY)
    childA, _ = g.get_next_state(b, ACT_A)
    childB, _ = g.get_next_state(b, ACT_B)
    gc = Game(enable_legal_moves_cache=True)
    gc.get_valid_moves(childA)          # pollute cache with A's mask (the "prior ply")
    gc.clear_caches()                   # <-- the fix: clear before snapshotting B
    snapshot = gc.get_valid_moves(childB).copy()
    root_mask = gc.get_valid_moves(childB)   # the "search root" recompute (cache hit, same instance)
    b_fresh = Game(enable_legal_moves_cache=False).get_valid_moves(childB)
    assert np.array_equal(snapshot, root_mask), "snapshot must equal search-root mask"
    assert np.array_equal(snapshot, b_fresh), "and both must be B's own fresh mask"


def test_clear_caches_actually_empties_legal_cache():
    """Guards the fix's premise: clear_caches() empties the legal-moves cache (so a
    stale cross-ply entry cannot survive into the snapshot)."""
    g, b = _replay_lowest_legal(SEED, PLY)
    gc = Game(enable_legal_moves_cache=True)
    gc.get_valid_moves(b)
    assert gc._legal_cache and len(gc._legal_cache) > 0
    gc.clear_caches()
    assert len(gc._legal_cache) == 0
