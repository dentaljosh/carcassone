"""Validation tests for the clairvoyance-gap root-determinization wrapper
(measurement-first spec V2/V3 + the non-peek contract).

These pin the correctness of `NeuralMCTS._reshuffled_root` (the fair_chance root
determinizer the gap experiment's non-clairvoyant arm runs K times per move).
No checkpoint needed — a uniform stub evaluator drives the search.

  V3  sampler — every determinization is a PERMUTATION of the remaining multiset
      and keeps the revealed `next_tile`; the caller's board is never mutated
      (the agent cannot peek at / corrupt the true future order).
  V2  degenerate — with <=1 unseen tile there is no hidden order, so the
      determinized root is byte-identical to the original (and so is its search).
  K-distinctness — successive determinizations are DIFFERENT worlds (rng advances
      across clear()), so K>1 actually samples K distinct futures.
"""
from __future__ import annotations

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS


def _uniform_evaluator(board):
    a = board.action_size if hasattr(board, "action_size") else None
    # action_size lives on the Game in this codebase; fall back to the mask length
    n = len(Game().get_valid_moves(board))
    return np.full(n, 1.0 / n, dtype=np.float32), 0.0


def _mcts(game, **kw):
    return NeuralMCTS(game=game, evaluator=_uniform_evaluator, simulations=8,
                      seed=0, fair_chance=True, **kw)


def _multiset(board):
    return sorted(t.description for t in board.state.deck)


def test_v3_determinization_is_permutation_and_nonmutating():
    """V3: deck contents preserved (multiset), next_tile fixed, ORIGINAL untouched."""
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    orig_order = [t.description for t in board.state.deck]
    orig_multiset = sorted(orig_order)
    orig_next = board.state.next_tile.description
    assert len(orig_order) > 5  # a real bag to shuffle

    m = _mcts(game)
    saw_reorder = False
    for _ in range(20):
        r = m._reshuffled_root(board)
        # multiset preserved
        assert _multiset(r) == orig_multiset
        # revealed current tile untouched
        assert r.state.next_tile.description == orig_next
        # the caller's board is NEVER mutated (no peek / no corruption of true order)
        assert [t.description for t in board.state.deck] == orig_order
        if [t.description for t in r.state.deck] != orig_order:
            saw_reorder = True
    # with a 60+ tile bag, at least one of 20 shuffles must reorder it
    assert saw_reorder, "determinizer never changed the deck order"


def test_v2_degenerate_last_tile_is_noop():
    """V2: with <=1 unseen tile the determinized root == original (no hidden order)."""
    game = Game(enable_legal_moves_cache=True)
    m = _mcts(game)
    for keep in (0, 1):
        board = game.get_init_board()
        board.state.deck = board.state.deck[:keep]
        board._str_repr_cache = None
        before = [t.description for t in board.state.deck]
        r = m._reshuffled_root(board)
        after = [t.description for t in r.state.deck]
        assert after == before, f"len={keep} deck reordered (no hidden info to shuffle)"
        # the public state key is identical → search would be identical
        assert game.string_representation(r) == game.string_representation(board)


def test_k_determinizations_are_distinct_worlds():
    """K-distinctness: successive determinizations differ (rng advances), so a
    K-vote actually samples K distinct futures rather than re-using one."""
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    m = _mcts(game)
    orders = set()
    for _ in range(12):
        r = m._reshuffled_root(board)
        orders.add(tuple(t.description for t in r.state.deck))
    # 12 shuffles of a 60+ tile bag → essentially all distinct; require >= 2
    assert len(orders) >= 2, "all K determinizations identical — not distinct worlds"


def test_v2_full_search_degenerate_equivalence():
    """V2 (search-level): at the last unseen tile, a fair_chance search and a
    clairvoyant search choose the same root action (no future order to exploit)."""
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    board.state.deck = board.state.deck[:1]
    board._str_repr_cache = None

    clair = NeuralMCTS(game=Game(enable_legal_moves_cache=True),
                       evaluator=_uniform_evaluator, simulations=16, seed=7,
                       fair_chance=False)
    fair = NeuralMCTS(game=Game(enable_legal_moves_cache=True),
                      evaluator=_uniform_evaluator, simulations=16, seed=7,
                      fair_chance=True)
    vc = clair.search(board)
    vf = fair.search(board)
    a_clair = max(vc, key=lambda a: (vc[a], -a))
    a_fair = max(vf, key=lambda a: (vf[a], -a))
    assert a_clair == a_fair
