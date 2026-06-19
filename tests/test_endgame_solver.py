"""Tests for the L2-3 exact endgame solver (scripts/level2/endgame_solver.py).

Validates the GROUND-TRUTH solver against an independent brute-force reference
and the pre-registered V2/V9 checks. Positions are DETERMINISTIC: the deck is
shuffled by the global `random` module at get_init_board, so we `random.seed(S)`
first — this is also the suite's provenance mechanism (seed+ply -> exact board).
"""
import os
import random
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "level2"))

from carcassonne_ai.flat_leaf import flat_base_score
from carcassonne_ai.game_wrapper import Game
from wingedsheep.carcassonne.objects.game_phase import GamePhase
import endgame_solver as S


def _k(b):
    return len(b.state.deck) + (1 if b.state.next_tile is not None else 0)


def endgame_position(seed: int, k_target: int):
    """Deterministic Board at the first TILES-phase ply with k_target tiles left."""
    random.seed(seed)                      # seeds the engine deck shuffle
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    mover_rng = random.Random(seed ^ 0x5151)
    while game.get_game_ended(b, 0) == 0.0:
        if b.state.phase == GamePhase.TILES and _k(b) == k_target:
            return game, b
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(mover_rng.choice(legal)))
    raise RuntimeError(f"never reached k={k_target}")


def _brute_clair(game, b):
    """Independent reference: pure minimax over the real deck, no TT/pruning."""
    if b.state.next_tile is None:
        return float(flat_base_score(b.state, 0))
    mover = b.state.current_player
    vals = [_brute_clair(game, game.get_next_state(b, int(a))[0])
            for a in np.flatnonzero(game.get_valid_moves(b))]
    return max(vals) if mover == 0 else min(vals)


def _brute_root(game, b):
    cv = {int(a): _brute_clair(game, game.get_next_state(b, int(a))[0])
          for a in np.flatnonzero(game.get_valid_moves(b))}
    mover = b.state.current_player
    vstar = max(cv.values()) if mover == 0 else min(cv.values())
    return vstar, {a for a, v in cv.items() if v == vstar}, cv


@pytest.mark.parametrize("seed,k", [(1, 2), (7, 2), (11, 2)])
def test_vbrute_clairvoyant_matches_reference(seed, k):
    """V-brute: TT-solver clairvoyant == independent brute-force (V*, optset, all child values)."""
    game, b = endgame_position(seed, k)
    vb, ob, cvb = _brute_root(game, b)
    r = S.solve(game, b, "clairvoyant", budget=5_000_000)
    assert r.value == vb
    assert set(r.optimal_actions) == ob
    for a in cvb:
        assert abs(r.child_values[a] - cvb[a]) < 1e-9, (a, r.child_values[a], cvb[a])


@pytest.mark.parametrize("seed", [1, 7, 11])
def test_v2_last_tile_clair_equals_marg(seed):
    """V2: at K=1 there is no hidden future -> clairvoyant == marginalized exactly."""
    game, b = endgame_position(seed, 1)
    rc = S.solve(game, b, "clairvoyant")
    rm = S.solve(game, b, "marginalized")
    assert abs(rc.value - rm.value) < 1e-9
    assert set(rc.optimal_actions) == set(rm.optimal_actions)
    for a in rc.child_values:
        assert abs(rc.child_values[a] - rm.child_values[a]) < 1e-9


@pytest.mark.parametrize("seed,k", [(1, 2), (7, 2)])
def test_v9_value_realized_by_optimal_play(seed, k):
    """V9: playing solver-optimal moves for BOTH sides from the root reaches a
    terminal whose real score-diff == V* (the solver's value is achievable)."""
    game, b = endgame_position(seed, k)
    root = S.solve(game, b, "clairvoyant", budget=5_000_000)
    cur = b
    guard = 0
    while cur.state.next_tile is not None:
        guard += 1
        assert guard < 40
        r = S.solve(game, cur, "clairvoyant", budget=5_000_000)
        a = r.optimal_actions[0]
        cur, _ = game.get_next_state(cur, int(a))
    final = float(flat_base_score(cur.state, 0))
    assert abs(final - root.value) < 1e-9, (final, root.value)


def test_regret_nonnegative_and_optimal_zero():
    """regret_of >= 0 for every legal action, and == 0 exactly for optimal ones."""
    game, b = endgame_position(1, 2)
    r = S.solve(game, b, "clairvoyant", budget=5_000_000)
    for a in r.child_values:
        reg = S.regret_of(r, a)
        assert reg >= -1e-9
        if a in r.optimal_actions:
            assert abs(reg) < 1e-9
