"""Phase 1.1 correctness + smoke: PUCT-with-heuristic-priors.

Proves the variant (src/carcassonne_ai/heuristic_prior_mcts.py):
  * plays only LEGAL moves and reaches a terminal (full games);
  * is DETERMINISTIC given a seed + fixed deck;
  * the evaluator's priors are a valid distribution over LEGAL actions (sum 1,
    non-negative, zero off-legal);
  * EXPAND-ALL: one search populates a prior for EVERY legal child and spreads
    visits across >1 child;
  * VALUE POV/sign matches the champion HeuristicMCTS leaf exactly (int quantize);
  * the float leaf reproduction is within ±1 of the production int leaf;
  * the existing HeuristicMCTS path still imports and runs (untouched).

Leaf env is set to the production v2.9 Bmild_cap8 substrate BEFORE importing
carcassonne_ai; the tests also pass an EXPLICIT Bmild_cap8 LeafConfig so they do
not depend on the DEFAULT_CONFIG env resolution.
"""
from __future__ import annotations

import os

os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import dataclasses as dc
import math
import random

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.heuristic_prior_mcts import (
    HeuristicPriorAgent,
    HeuristicPriorConfig,
    leaf_score_float,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

MILD_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
# Frozen v2.9 classical substrate (governance/LEAF_SUBSTRATES.yaml v2_9_bmild_cap8).
V28 = dc.replace(DEFAULT_CONFIG, meeple_k=2.0)
BMILD_CAP8 = dc.replace(V28, v29_meeple_curve=MILD_CURVE, bonus_cap=8.0, opp_bonus_cap=8.0)


def _new_game():
    return Game(enable_legal_moves_cache=True)


def _play_random(game, board, rng, n):
    """Advance up to n random-legal plies (stops at terminal)."""
    for _ in range(n):
        if game.get_game_ended(board, 0) != 0.0:
            break
        legal = np.flatnonzero(game.get_valid_moves(board))
        board, _ = game.get_next_state(board, int(rng.choice(legal)))
    return board


def _midgame_boards(n=4, plies=60):
    boards = []
    for s in range(n):
        game = _new_game()
        # get_init_board() shuffles the deck via the GLOBAL random module
        # (carcassonne_game_state.py). np.random.default_rng below only seeds MOVE
        # selection, not the deck — so leave the global RNG unseeded and the deck
        # order (hence the search's visit spread / transposition aliasing) is
        # nondeterministic across processes, making test_expand_all_children_at_once
        # FLAKY. Seed it per-s (reproducible) like the sibling deterministic test.
        random.seed(2_000_000 + s)
        board = game.get_init_board()
        rng = np.random.default_rng(1000 + s)
        board = _play_random(game, board, rng, plies)
        if game.get_game_ended(board, 0) == 0.0:
            boards.append((game, board))
    return boards


# --------------------------------------------------------------------------- #
def test_priors_valid_distribution_over_legal():
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, tau_p=5.0, leaf_quantize="float")
    for game, board in _midgame_boards():
        ev = make_heuristic_prior_evaluator(game, cfg)
        priors, value = ev(board)
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        assert priors.shape == mask.shape
        assert np.all(priors >= 0.0)
        assert np.all(np.isfinite(priors))
        # zero probability off the legal set
        illegal = np.setdiff1d(np.arange(priors.shape[0]), legal)
        assert np.allclose(priors[illegal], 0.0)
        # a valid distribution over legal actions
        assert priors[legal].sum() == pytest.approx(1.0, abs=1e-6)
        assert -1.0 <= value <= 1.0


def test_value_pov_matches_champion_leaf():
    """int-quantized evaluator value == HeuristicMCTS._rollout leaf value exactly
    (same int leaf, same tanh norm, same mover POV) — verifies the sign/POV wiring."""
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, leaf_quantize="int", value_norm=15.0)
    for game, board in _midgame_boards():
        ev = make_heuristic_prior_evaluator(game, cfg)
        _, value = ev(board)
        champ = HeuristicMCTS(
            game=_new_game(), simulations=1, seed=0,
            heur_leaf="v2_7", leaf_cfg=BMILD_CAP8, value_norm=15.0,
        )
        champ_value = champ._rollout(board)
        assert value == pytest.approx(champ_value, abs=1e-9)


def test_float_leaf_within_one_of_production_int():
    """leaf_score_float rounds to within ±1 of the production int leaf (the known
    Cython/pure-Python reorder tolerance)."""
    for game, board in _midgame_boards(n=6, plies=70):
        p = board.state.current_player
        f = leaf_score_float(board.state, p, BMILD_CAP8)
        prod = virtual_score_v2(board.state, p, BMILD_CAP8)
        assert abs(int(round(f)) - prod) <= 1


def test_expand_all_children_at_once():
    """One search sets a prior for EVERY legal root child and spreads visits."""
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0)
    game, board = _midgame_boards(n=1, plies=50)[0]
    n_legal = int(game.get_valid_moves(board).sum())
    agent = HeuristicPriorAgent(game, cfg, simulations=n_legal + 40, seed=7)
    agent.mcts.search(board)
    root = agent.mcts._nodes[game.string_representation(board)]
    # priors computed for ALL legal actions (expand-all, not one-per-sim)
    assert len(root.priors) == n_legal
    assert set(root.valid_actions) == set(np.flatnonzero(game.get_valid_moves(board)).tolist())
    # visits spread across more than one child
    visited = [a for a, c in agent.mcts._deduped_children(root) if c.N > 0]
    assert len(visited) >= 2


def test_plays_full_legal_game_and_terminates():
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8)
    game = _new_game()
    board = game.get_init_board()
    agent = HeuristicPriorAgent(game, cfg, simulations=20, seed=3)
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        mask = game.get_valid_moves(board)
        a = agent.move(board)
        assert mask[a], f"agent returned illegal action {a}"
        board, _ = game.get_next_state(board, a)
        moves += 1
        assert moves < 500, "game did not terminate"
    assert moves > 50  # a real base+farmers game is ~150-170 decisions


def _selfplay_move_sequence(seed, sims):
    import random

    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0)
    game = _new_game()
    # Seed the global RNG BEFORE get_init_board — the engine shuffles the deck via
    # the `random` module (the production harnesses do this too), so a fixed seed
    # fixes the deck. The agent itself is deterministic given (deck, seed).
    random.seed(9_000_000)
    board = game.get_init_board()
    # one agent per seat, both deterministic under `seed`
    a0 = HeuristicPriorAgent(game, cfg, simulations=sims, seed=seed)
    a1 = HeuristicPriorAgent(_new_game(), cfg, simulations=sims, seed=seed + 1)
    seq = []
    while game.get_game_ended(board, 0) == 0.0:
        agent = a0 if board.state.current_player == 0 else a1
        act = agent.move(board)
        seq.append(act)
        board, _ = game.get_next_state(board, act)
    return seq


def test_deterministic_given_seed():
    s1 = _selfplay_move_sequence(seed=42, sims=24)
    s2 = _selfplay_move_sequence(seed=42, sims=24)
    assert s1 == s2 and len(s1) > 50


def test_final_select_visits_vs_q_both_run():
    """Both selectors produce a legal move; they are allowed to differ."""
    game, board = _midgame_boards(n=1, plies=40)[0]
    mask = game.get_valid_moves(board)
    for sel in ("Q", "visits"):
        cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, final_select=sel)
        agent = HeuristicPriorAgent(_new_game(), cfg, simulations=30, seed=11)
        a = agent.best_action(board)
        assert mask[a]


def test_existing_heuristic_mcts_untouched():
    """HeuristicMCTS still imports + runs deterministically (this module only ADDs)."""
    game, board = _midgame_boards(n=1, plies=30)[0]
    m1 = HeuristicMCTS(game=_new_game(), simulations=40, seed=5, heur_leaf="v2_7", leaf_cfg=BMILD_CAP8)
    m2 = HeuristicMCTS(game=_new_game(), simulations=40, seed=5, heur_leaf="v2_7", leaf_cfg=BMILD_CAP8)
    assert m1.best_action(board) == m2.best_action(board)


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
