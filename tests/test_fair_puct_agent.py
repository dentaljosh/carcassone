"""Tests for the fair-play PUCT-with-heuristic-priors adapter
(FairHeuristicPriorAgent in src/carcassonne_ai/fair_agent.py).

Mirrors tests/test_fair_agent.py's contract, for the 2026-07-06 champion
(HeuristicPriorAgent core) instead of HeuristicMCTS:
  (a) determinism given a fixed seed;
  (b) the reshuffle touches ONLY the deck (caller board + next_tile byte-identical);
  (c) constructs + plays a FULL legal determinized game to termination;
  (d) the marginalized exact handoff fires at K<=exact_max_k (and only there),
      with exact_max_k configurable (2 and 4);
  (e) exact_endgame=False -> pure PIMC to the end (no solver).

Regression for the pre-existing FairHeuristicMCTSAgent + all other fair agents
lives in tests/test_fair_agent.py (unchanged by this build).

Env: the production v2.9 Bmild_cap8 leaf + Cython flags are set BEFORE importing
carcassonne_ai (DEFAULT_CONFIG reads them at import) so the agent exercises the
production leaf; determinism/legality do not depend on it, but this matches the
champion. Positions are deterministic via random.seed (engine deck shuffle).
"""
import os

for _k, _v in {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
}.items():
    os.environ.setdefault(_k, _v)

import pickle
import random
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "level2"))

from carcassonne_ai.fair_agent import FairHeuristicPriorAgent, k_remaining
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
from wingedsheep.carcassonne.objects.game_phase import GamePhase


# --------------------------------------------------------------------------- #
# Deterministic position builders (the test_fair_agent convention)             #
# --------------------------------------------------------------------------- #
def _k(b):
    return len(b.state.deck) + (1 if b.state.next_tile is not None else 0)


def endgame_position(seed: int, k_target: int):
    """Deterministic Board at the first TILES-phase ply with k_target tiles left."""
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    mover_rng = random.Random(seed ^ 0x5151)
    while game.get_game_ended(b, 0) == 0.0:
        if b.state.phase == GamePhase.TILES and _k(b) == k_target:
            return game, b
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(mover_rng.choice(legal)))
    raise RuntimeError(f"never reached k={k_target}")


def midgame_position(seed: int, plies: int):
    """Deterministic mid-game Board after `plies` random moves (big unseen deck)."""
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    mover_rng = random.Random(seed ^ 0xA5A5)
    for _ in range(plies):
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(mover_rng.choice(legal)))
    assert game.get_game_ended(b, 0) == 0.0
    return game, b


def _champ_cfg():
    return HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                               final_select="visits")


# --------------------------------------------------------------------------- #
# (a) determinism given seed                                                   #
# --------------------------------------------------------------------------- #
def test_puct_deterministic_given_seed():
    game, board = midgame_position(3, 20)
    moves = []
    for _ in range(2):   # two FRESH agents, same seed -> identical pick
        agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True),
                                        _champ_cfg(), sims=24, k_dets=2, seed=123,
                                        exact_endgame=False)
        moves.append(agent.choose_action(board))
    assert moves[0] == moves[1]
    mask = game.get_valid_moves(board)
    assert mask[moves[0]], "fair agent returned an illegal action"


def test_puct_seed_derivation_is_move_indexed():
    a1 = FairHeuristicPriorAgent(Game(), _champ_cfg(), seed=7)
    a2 = FairHeuristicPriorAgent(Game(), _champ_cfg(), seed=7)
    assert a1.det_seed_base(5) == a2.det_seed_base(5)
    assert a1.det_search_seed(5, 3) == a2.det_search_seed(5, 3)
    assert a1.det_search_seed(5, 3) != a1.det_search_seed(5, 4)
    assert a1.det_seed_base(0) != a1.det_seed_base(1)


# --------------------------------------------------------------------------- #
# (b) reshuffle touches ONLY the deck; caller board never mutated              #
# --------------------------------------------------------------------------- #
def test_puct_choose_action_never_mutates_caller_board():
    game, board = midgame_position(9, 16)
    pre = pickle.dumps(board.state)
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True),
                                    _champ_cfg(), sims=16, k_dets=2, seed=42,
                                    exact_endgame=False)
    a = agent.choose_action(board)
    assert game.get_valid_moves(board)[a]
    assert pickle.dumps(board.state) == pre, \
        "choose_action mutated the caller's board state (deck order/next_tile?)"


# --------------------------------------------------------------------------- #
# (c) constructs + plays a FULL legal determinized game to termination         #
# --------------------------------------------------------------------------- #
def test_puct_plays_full_legal_determinized_game():
    """Two fair PUCT agents (one per seat) play a full game to termination. Every
    move is legal, the game ends, and the fair marginalized endgame fires (both
    seats latch at their own K<=2 TILES turns)."""
    random.seed(2024)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    cfg = _champ_cfg()
    a0 = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                 sims=8, k_dets=2, seed=1, exact_endgame=True,
                                 exact_max_k=2)
    a1 = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                 sims=8, k_dets=2, seed=2, exact_endgame=True,
                                 exact_max_k=2)
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        agent = a0 if board.state.current_player == 0 else a1
        act = agent.choose_action(board)
        assert game.get_valid_moves(board)[act], f"illegal action {act}"
        board, _ = game.get_next_state(board, act)
        moves += 1
        assert moves < 400, "game did not terminate"
    assert game.get_game_ended(board, 0) != 0.0
    assert (a0.exact_moves + a1.exact_moves) > 0, "fair marginalized endgame never fired"
    assert (a0.heur_moves + a1.heur_moves) > 0, "fair PIMC prefix never ran"
    assert a0.n_timeouts == 0 and a1.n_timeouts == 0, "unexpected K<=2 solver timeout"


# --------------------------------------------------------------------------- #
# (d) the marginalized exact handoff fires at K<=exact_max_k (and only there)  #
# --------------------------------------------------------------------------- #
def test_puct_marginalized_handoff_fires_at_k2_and_latches():
    game, board = endgame_position(1, 2)
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _champ_cfg(),
                                    sims=8, k_dets=2, seed=5, exact_endgame=True,
                                    exact_max_k=2)
    move = agent.choose_action(board)
    assert game.get_valid_moves(board)[move]
    assert agent.exact_moves == 1 and agent.heur_moves == 0
    assert agent.latch_k == 2 and agent.n_timeouts == 0
    assert agent.solver_nodes > 0
    # latched: the SAME turn's meeple decision (and everything after) is solved too.
    nb, _ = game.get_next_state(board, move)
    if game.get_game_ended(nb, 0) == 0.0:
        agent.choose_action(nb)
        assert agent.exact_moves == 2 and agent.heur_moves == 0


def test_puct_no_solver_above_exact_max_k():
    """Above the K band the fair agent must use PIMC search (a clairvoyant K=3-4
    solve would be cheating; marginalized is intractable)."""
    game, board = endgame_position(1, 6)
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _champ_cfg(),
                                    sims=8, k_dets=1, seed=5, exact_endgame=True,
                                    exact_max_k=2)
    a = agent.choose_action(board)
    assert game.get_valid_moves(board)[a]
    assert agent.exact_moves == 0 and agent.heur_moves == 1
    assert agent.latch_k is None


def test_puct_exact_max_k_configurable_latches_at_k4():
    """exact_max_k=4 latches the marginalized solver at k_remaining=4 (the A2 grid
    sweeps this; K>=3 is the RAM regime but a single small solve here is fine)."""
    game, board = endgame_position(3, 4)
    assert k_remaining(board.state) == 4
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _champ_cfg(),
                                    sims=8, k_dets=1, seed=9, exact_endgame=True,
                                    exact_max_k=4, exact_budget=5_000_000)
    a = agent.choose_action(board)
    assert game.get_valid_moves(board)[a]
    assert agent.latch_k == 4
    # either solved (exact_moves) or budget-exceeded fallback (n_timeouts) — never PIMC-unlatch
    assert agent.exact_moves + agent.n_timeouts == 1
    assert agent.heur_moves == agent.n_timeouts  # PIMC ran iff the solve timed out


# --------------------------------------------------------------------------- #
# (e) exact_endgame=False -> pure PIMC to the end (no solver)                  #
# --------------------------------------------------------------------------- #
def test_puct_exact_endgame_flag_gates_the_handoff():
    game, board = endgame_position(1, 2)
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _champ_cfg(),
                                    sims=8, k_dets=1, seed=5, exact_endgame=False)
    a = agent.choose_action(board)
    assert game.get_valid_moves(board)[a]
    assert agent.exact_moves == 0 and agent.heur_moves == 1
    assert agent.latch_k is None


def test_puct_k_dets_validation():
    with pytest.raises(ValueError):
        FairHeuristicPriorAgent(Game(), _champ_cfg(), k_dets=0)
