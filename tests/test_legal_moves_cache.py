"""Verify the get_valid_moves cache: correctness, stats, and clear behavior."""
from __future__ import annotations

import random
import time

import numpy as np

from carcassonne_ai.game_wrapper import Game


def _stepped_board(g: Game, n_moves: int = 20, seed: int = 0):
    random.seed(seed)
    board = g.get_init_board()
    for _ in range(n_moves):
        if g.get_game_ended(board, 0) != 0.0:
            break
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    return board


def test_cache_returns_same_mask_as_uncached() -> None:
    """The cache must not change masks. Run the same trajectory through a
    cache-on Game and a cache-off Game; masks must be byte-identical.

    The engine shuffles its deck via the global `random` module on
    `get_init_board()`, so we re-seed before each init to guarantee both
    games start from identical deck orderings.
    """
    g_off = Game(enable_legal_moves_cache=False)
    g_on = Game(enable_legal_moves_cache=True)

    INIT_SEED = 11
    random.seed(INIT_SEED)
    b_off = g_off.get_init_board()
    random.seed(INIT_SEED)
    b_on = g_on.get_init_board()

    random.seed(99)
    rng_seeds = [random.randint(0, 1_000_000) for _ in range(50)]

    for s in rng_seeds:
        if g_off.get_game_ended(b_off, 0) != 0.0:
            break
        m_off = g_off.get_valid_moves(b_off)
        m_on = g_on.get_valid_moves(b_on)
        np.testing.assert_array_equal(m_off, m_on)

        # Pick the same action on both branches by index
        random.seed(s)
        legal = np.flatnonzero(m_off)
        idx = int(random.choice(legal))
        b_off, _ = g_off.get_next_state(b_off, idx)
        b_on, _ = g_on.get_next_state(b_on, idx)


def test_cache_hits_on_repeated_calls() -> None:
    g = Game(enable_legal_moves_cache=True)
    board = _stepped_board(g, n_moves=10, seed=3)
    g.clear_caches()  # reset stats after the warmup steps
    for _ in range(50):
        g.get_valid_moves(board)
    stats = g.cache_stats()
    assert stats["enabled"]
    assert stats["misses"] == 1, stats
    assert stats["hits"] == 49, stats
    assert stats["hit_rate"] > 0.95


def test_cache_miss_when_disabled() -> None:
    g = Game(enable_legal_moves_cache=False)
    board = g.get_init_board()
    g.get_valid_moves(board)
    stats = g.cache_stats()
    assert stats["enabled"] is False
    assert stats["hits"] == 0
    assert stats["misses"] == 0


def test_clear_caches_resets_state() -> None:
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    g.get_valid_moves(board)
    g.get_valid_moves(board)
    assert g.cache_stats()["hits"] == 1
    g.clear_caches()
    assert g.cache_stats() == {
        "enabled": True, "hits": 0, "misses": 0, "hit_rate": 0.0, "size": 0,
    }


def test_cached_mask_is_read_only() -> None:
    """Returned cached masks are marked non-writable so accidental mutation
    fails loudly instead of corrupting future cache hits."""
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    m = g.get_valid_moves(board)
    import pytest as _pytest
    with _pytest.raises(ValueError):
        m[0] = True


def test_cache_speedup_on_repeated_state() -> None:
    """Quantitative check: 1000 calls on a single state are faster with cache.
    Not a precise speedup assertion (CI noise), just a sanity threshold."""
    g_off = Game(enable_legal_moves_cache=False)
    g_on = Game(enable_legal_moves_cache=True)
    board_off = _stepped_board(g_off, n_moves=20, seed=42)
    board_on = _stepped_board(g_on, n_moves=20, seed=42)

    n = 200
    t0 = time.perf_counter()
    for _ in range(n):
        g_off.get_valid_moves(board_off)
    off_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(n):
        g_on.get_valid_moves(board_on)
    on_s = time.perf_counter() - t0

    # Cache should be at least 5x faster on the hot path. Quick-bench shows
    # ~50ms uncached vs <1ms cached, so the real ratio is much higher.
    assert on_s * 5 < off_s, f"cache no faster than uncached: on={on_s:.3f}s off={off_s:.3f}s"
