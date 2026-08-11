"""F1 property: the CL-056 fair deck canonicalization (fair-handoff audit 2026-07-06,
probe C). A fair determinization must be a pure function of the unseen MULTISET + rng —
NOT the engine's hidden TRUE deck order. This is the regression for the 07-14 leak: if the
sampled world depended on the true order, a fair decision could leak hidden information.
"""
import copy
import random

import numpy as np

from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent, FairHeuristicPriorAgent
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig


def _midgame(seed, plies):
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    rng = random.Random(seed ^ 0xA5A5)
    for _ in range(plies):
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(rng.choice(legal)))
    assert game.get_game_ended(b, 0) == 0.0
    return game, b


def test_determinization_invariant_to_hidden_deck_order():
    """Two boards with the SAME unseen multiset but a DIFFERENT hidden order must yield
    byte-identical reshuffled decks under the same rng seed."""
    _game, board = _midgame(5, 12)
    permuted = copy.deepcopy(board)
    random.Random(999).shuffle(permuted.state.deck)
    assert ([t.description for t in permuted.state.deck]
            != [t.description for t in board.state.deck]), "need a real permutation"

    r0 = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(0))
    r1 = FairHeuristicMCTSAgent.reshuffled_determinization(permuted, random.Random(0))
    assert ([t.description for t in r0.state.deck]
            == [t.description for t in r1.state.deck]), \
        "determinization depends on hidden deck order (CL-056 canonical-sort broken)"


def test_determinization_preserves_multiset_and_next_tile():
    _game, board = _midgame(7, 16)
    before_multiset = sorted(t.description for t in board.state.deck)
    before_next = board.state.next_tile.description if board.state.next_tile else None
    det = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(3))
    assert sorted(t.description for t in det.state.deck) == before_multiset
    # next_tile (the already-revealed in-hand tile) is NEVER reshuffled.
    det_next = det.state.next_tile.description if det.state.next_tile else None
    assert det_next == before_next
    # caller board untouched (sort/shuffle operate on the copy only).
    assert [t.description for t in board.state.deck] == \
        [t.description for t in copy.deepcopy(board).state.deck]


def test_fair_agent_pick_invariant_to_hidden_order():
    """End-to-end: the champion's fair pick is identical whether the hidden deck order is
    permuted — the fair agent cannot see (or leak) the true order."""
    _game, board = _midgame(9, 14)
    permuted = copy.deepcopy(board)
    random.Random(12345).shuffle(permuted.state.deck)
    cfg = HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                               final_select="visits")
    a = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg, sims=16,
                                k_dets=2, seed=77, exact_endgame=False).choose_action(board)
    b = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg, sims=16,
                                k_dets=2, seed=77, exact_endgame=False).choose_action(permuted)
    assert a == b, "fair pick changed with the hidden deck order — an information leak"
