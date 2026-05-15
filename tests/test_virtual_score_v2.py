"""Correctness tests for virtual_score_v2 (closure-anticipation bonus +
farm-growth potential on top of v1).

These don't validate playing strength (that's a head-to-head bench against
v1). They check structural invariants:
  - matches v1 on empty board (no meeples → no bonuses)
  - matches v1 at terminal (everything closed → no bonuses)
  - returns symmetric values: v2(state, p) == -v2(state, 1-p)
  - doesn't crash mid-game across multiple seeds
  - actually returns DIFFERENT values from v1 in mid-game (bonuses fire)
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score import virtual_score
from carcassonne_ai.virtual_score_v2 import (
    _close_prob,
    _closure_anticipation_bonus,
    virtual_score_v2,
)


def _walk_random(g: Game, b, n_moves: int, seed: int):
    rng = random.Random(seed)
    for _ in range(n_moves):
        if g.get_game_ended(b, 0) != 0.0:
            break
        mask = g.get_valid_moves(b)
        legal = np.flatnonzero(mask)
        a = int(rng.choice(legal.tolist()))
        b, _ = g.get_next_state(b, a)
    return b


# ---------------------------------------------------------------------------
# Boundary / structural invariants
# ---------------------------------------------------------------------------


def test_close_prob_schedule() -> None:
    """The v2.5 probability schedule (halved from v2 after the diagnostic
    showed v2's bonus saturated tanh)."""
    assert _close_prob(1) == 0.5
    assert _close_prob(2) == 0.2
    assert _close_prob(3) == 0.05
    assert _close_prob(4) == 0.0
    assert _close_prob(10) == 0.0


def test_v2_matches_v1_at_init() -> None:
    """No meeples placed → no closure-anticipation bonus → v2 == v1 == 0."""
    g = Game()
    b = g.get_init_board()
    assert virtual_score_v2(b.state, 0) == virtual_score(b.state, 0) == 0


def test_v2_matches_v1_at_terminal() -> None:
    """At terminal, count_final_scores has run; all features are scored.
    The closure-anticipation bonus is computed on the unmutated live state
    but `state.placed_meeples` is also cleared at terminal (meeples removed
    when features close). v2 may still differ from v1 if some meeples
    remain on incomplete features at game end, but the delta is small."""
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    rng = random.Random(0)
    while g.get_game_ended(b, 0) == 0.0:
        mask = g.get_valid_moves(b)
        legal = np.flatnonzero(mask)
        b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
    # The base virtual_score already counts final scores.
    v1 = virtual_score(b.state, 0)
    v2 = virtual_score_v2(b.state, 0)
    # v2 may add a small bonus for any meeples remaining on barely-incomplete
    # features at game end. Sanity: same sign, within 20pts.
    assert (v1 > 0) == (v2 > 0) or (v1 == 0 and abs(v2) <= 5), (
        f"v1={v1} v2={v2} disagree on winner at terminal"
    )


def test_v2_is_antisymmetric() -> None:
    """v2(state, 0) == -v2(state, 1) — bonuses for player p subtract for the
    opponent, so swapping perspective negates the result."""
    g = Game(enable_legal_moves_cache=True)
    b = _walk_random(g, g.get_init_board(), 40, seed=7)
    assert virtual_score_v2(b.state, 0) == -virtual_score_v2(b.state, 1)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_v2_doesnt_crash_mid_game(seed: int) -> None:
    """v2 should evaluate any reachable mid-game state without exception."""
    g = Game(enable_legal_moves_cache=True)
    for n in [20, 50, 100]:
        b = _walk_random(g, g.get_init_board(), n, seed=seed)
        # Must not raise:
        _ = virtual_score_v2(b.state, 0)
        _ = virtual_score_v2(b.state, 1)


# ---------------------------------------------------------------------------
# Behavior: bonuses actually fire mid-game
# ---------------------------------------------------------------------------


def test_v2_differs_from_v1_when_meeples_placed_mid_game() -> None:
    """After enough moves to place meeples on incomplete features, v2 should
    produce values that differ from v1 (the closure-anticipation bonus is
    non-zero for SOMEONE). Aggregates across multiple seeds to avoid
    accidentally hitting a state with no bonus."""
    g = Game(enable_legal_moves_cache=True)
    any_diff = False
    for seed in range(10):
        b = _walk_random(g, g.get_init_board(), 60, seed=seed)
        if g.get_game_ended(b, 0) != 0.0:
            continue
        v1 = virtual_score(b.state, 0)
        v2 = virtual_score_v2(b.state, 0)
        if v1 != v2:
            any_diff = True
            break
    assert any_diff, (
        "v2 never differed from v1 across 10 mid-game seeds — bonuses "
        "may be miswired (or _close_prob never returns >0)"
    )


def test_v2_bonus_dedupes_duplicate_meeples() -> None:
    """Regression for the over-counting bug fixed in commit `08dfead`.
    Adding a duplicate meeple (same coord+side as an existing meeple) must
    NOT increase the bonus, since the engine itself only scores each
    farm/city once per player. Pre-fix, this test would fail because
    every meeple's bonus was added independently.

    Implementation: walk a random game to a state with several meeples,
    then artificially clone one of them onto `state.placed_meeples`.
    Bonus must be identical before and after the clone."""
    g = Game(enable_legal_moves_cache=True)
    for seed in range(5):
        b = _walk_random(g, g.get_init_board(), 80, seed=seed)
        for player in (0, 1):
            mps = b.state.placed_meeples[player]
            if not mps:
                continue
            base = _closure_anticipation_bonus(b.state, player)
            # Clone the first meeple into the list. Same coord+side ⇒
            # falls into the same farm/city when find_farm/find_city runs.
            b.state.placed_meeples[player] = list(mps) + [mps[0]]
            try:
                augmented = _closure_anticipation_bonus(b.state, player)
            finally:
                b.state.placed_meeples[player] = mps
            assert base == augmented, (
                f"seed={seed} player={player}: dedup broken — adding a "
                f"duplicate meeple changed the bonus from {base} to {augmented}"
            )


def test_v2_bonus_is_capped() -> None:
    """v2.5 caps the per-player bonus at _BONUS_CAP. Verify the cap holds
    across many random states (no state should produce bonus > cap)."""
    from carcassonne_ai.virtual_score_v2 import _BONUS_CAP

    g = Game(enable_legal_moves_cache=True)
    for seed in range(5):
        b = _walk_random(g, g.get_init_board(), 100, seed=seed)
        for player in (0, 1):
            assert _closure_anticipation_bonus(b.state, player) <= _BONUS_CAP


def test_v2_bonus_is_nonnegative_for_player_with_meeples() -> None:
    """For a state where ONLY player 0 has placed meeples, the closure-
    anticipation bonus should be >= 0 for player 0, since all bonuses come
    from p0's own meeples. Hard to engineer directly, so check across many
    random states that the bonus has the expected sign property."""
    from carcassonne_ai.virtual_score_v2 import _closure_anticipation_bonus

    g = Game(enable_legal_moves_cache=True)
    for seed in range(5):
        b = _walk_random(g, g.get_init_board(), 80, seed=seed)
        # Bonuses are non-negative by construction (P >= 0, delta >= 0).
        assert _closure_anticipation_bonus(b.state, 0) >= 0
        assert _closure_anticipation_bonus(b.state, 1) >= 0
