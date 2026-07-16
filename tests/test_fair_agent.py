"""Tests for the production fair-play mode (src/carcassonne_ai/fair_agent.py).

Covers the contract from the fair-mode build spec:
  (a) determinism given seed;
  (b) the reshuffle touches ONLY the deck (caller board state + next_tile
      byte-identical pre/post; determinization differs only in deck order);
  (c) rigged 1-hidden-tile endgame: fair move == clairvoyant HeuristicMCTS move
      (the identity-permutation property — at deck_len<=1 the unseen-deck
      reshuffle is an identity permutation, so a seed-matched K=1 PIMC search
      IS the clairvoyant search; proven statistically by
      scripts/canonical_az/fairness_decision_probe.py);
  (d) the pooled-Q rule on synthetic root stats (missing-action pooling,
      min-visits floor, tiebreaks, dedup/sign harvest);
  (e) the marginalized exact handoff fires at K<=2 (and only there).

Positions are deterministic: the engine deck is shuffled via the global
`random` module at get_init_board, so `random.seed(S)` first (the same
provenance mechanism as tests/test_endgame_solver.py).
"""
import copy
import os
import pickle
import random
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "level2"))

from carcassonne_ai.fair_agent import (
    FairHeuristicMCTSAgent,
    FairHeuristicPriorAgent,
    k_remaining,
    pool_root_stats,
    pooled_q_argmax,
)
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS, Node
from wingedsheep.carcassonne.objects.game_phase import GamePhase
import endgame_solver as S


# --------------------------------------------------------------------------- #
# Deterministic position builders (the test_endgame_solver convention)         #
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# (a) determinism given seed                                                   #
# --------------------------------------------------------------------------- #
def test_deterministic_given_seed():
    game, board = midgame_position(3, 20)
    moves = []
    for _ in range(2):   # two FRESH agents, same seed -> identical pick
        agent = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                       sims=32, k_dets=2, seed=123,
                                       exact_endgame=False)
        moves.append(agent.choose_action(board))
    assert moves[0] == moves[1]
    mask = game.get_valid_moves(board)
    assert mask[moves[0]], "fair agent returned an illegal action"


def test_seed_derivation_is_move_indexed():
    """Per-move seeds depend on (seed, move_idx) only — stable across replays."""
    a1 = FairHeuristicMCTSAgent(Game(), seed=7)
    a2 = FairHeuristicMCTSAgent(Game(), seed=7)
    assert a1.det_seed_base(5) == a2.det_seed_base(5)
    assert a1.det_search_seed(5, 3) == a2.det_search_seed(5, 3)
    assert a1.det_search_seed(5, 3) != a1.det_search_seed(5, 4)
    assert a1.det_seed_base(0) != a1.det_seed_base(1)


# --------------------------------------------------------------------------- #
# (b) reshuffle touches ONLY the deck; caller board never mutated              #
# --------------------------------------------------------------------------- #
def test_determinization_touches_only_deck_order():
    game, board = midgame_position(5, 12)
    pre_state = pickle.dumps(board.state)
    pre_deck_order = [t.description for t in board.state.deck]
    det = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(0))
    # caller's board byte-identical (state incl. deck order + next_tile)
    assert pickle.dumps(board.state) == pre_state
    assert [t.description for t in board.state.deck] == pre_deck_order
    # determinization: deck MULTISET preserved, next_tile untouched
    assert sorted(t.description for t in det.state.deck) == sorted(pre_deck_order)
    assert det.state.next_tile.description == board.state.next_tile.description
    # everything the transposition key sees (placed tiles, meeples, scores,
    # phase, player, next_tile — deck order is deliberately NOT in the key)
    # is identical: only the unseen deck order may differ.
    assert (game.string_representation(det)
            == game.string_representation(board))
    assert det.state is not board.state, "determinization must be a copy"


def test_determinization_invariant_to_input_deck_order():
    """PIMC deck-sort hardening (fair-handoff audit 2026-07-06, probe C): the
    sampled determinization must be a pure function of the unseen MULTISET + rng,
    NOT the engine's hidden TRUE deck order. Two boards with the same multiset but
    a different unseen-deck order must produce byte-identical reshuffled decks
    under the same rng seed (before the fix they would differ ~19% of the time)."""
    _game, board = midgame_position(5, 12)
    # a genuine permutation of the SAME unseen deck (same multiset, different order)
    permuted = copy.deepcopy(board)
    random.Random(999).shuffle(permuted.state.deck)
    assert ([t.description for t in permuted.state.deck]
            != [t.description for t in board.state.deck]), "need a real permutation to test"
    d0 = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(0))
    d1 = FairHeuristicMCTSAgent.reshuffled_determinization(permuted, random.Random(0))
    assert ([t.description for t in d0.state.deck]
            == [t.description for t in d1.state.deck]), \
        "determinization must not depend on the hidden input deck order (canonical-sort fix)"
    # and the caller's boards are still untouched (sort operates on the copy only)
    assert [t.description for t in permuted.state.deck] != \
           [t.description for t in board.state.deck], "caller boards must be unmutated"


def test_choose_action_never_mutates_caller_board():
    game, board = midgame_position(9, 16)
    pre = pickle.dumps(board.state)
    agent = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                   sims=16, k_dets=2, seed=42,
                                   exact_endgame=False)
    a = agent.choose_action(board)
    assert game.get_valid_moves(board)[a]
    assert pickle.dumps(board.state) == pre, \
        "choose_action mutated the caller's board state (deck order/next_tile?)"


# --------------------------------------------------------------------------- #
# (c) 1-hidden-tile endgame: fair == clairvoyant (identity permutation)        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", [1, 7])
def test_fair_equals_clairvoyant_at_one_hidden_tile(seed):
    """At a K=2 TILES root the unseen deck is a single tile -> the reshuffle is
    an identity permutation. A seed-matched K=1 PIMC pick must therefore equal
    the clairvoyant HeuristicMCTS pick exactly (same tree, same tiebreaks).
    min_pooled_visits=1 so the pooled-Q floor cannot diverge from best_action
    (which has no floor)."""
    game, board = endgame_position(seed, 2)
    assert len(board.state.deck) <= 1, "rig requires <=1 hidden tile"

    agent = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                   sims=64, k_dets=1, seed=seed,
                                   min_pooled_visits=1, exact_endgame=False)
    fair_move = agent.choose_action(board)
    assert agent.heur_moves == 1 and agent.exact_moves == 0  # PIMC path used

    clair = HeuristicMCTS(game=Game(enable_legal_moves_cache=True),
                          simulations=64, c=3.0,
                          seed=agent.det_search_seed(0, 0), heur_leaf="v2_7")
    clair_move = int(clair.best_action(board))
    assert fair_move == clair_move


# --------------------------------------------------------------------------- #
# (d) the pooled-Q rule (synthetic root stats)                                 #
# --------------------------------------------------------------------------- #
def test_pooled_q_missing_action_not_diluted():
    """An action visited in fewer determinizations pools Q over those only —
    higher mean Q wins over higher visit mass."""
    agg_n = {1: 8.0, 3: 4.0}           # 3 was missing from some dets
    agg_w = {1: 4.0, 3: 3.6}           # Q1=0.5, Q3=0.9
    assert pooled_q_argmax(agg_n, agg_w, min_visits=2) == 3


def test_pooled_q_min_visits_floor_blocks_one_visit_noise():
    agg_n = {1: 8.0, 2: 1.0}
    agg_w = {1: 4.0, 2: 1.0}           # Q2=1.0 but N=1: a single-leaf sample
    assert pooled_q_argmax(agg_n, agg_w, min_visits=2) == 1
    assert pooled_q_argmax(agg_n, agg_w, min_visits=1) == 2  # floor off -> Q wins


def test_pooled_q_all_below_floor_falls_back_to_visited():
    agg_n = {5: 1.0, 7: 1.0}
    agg_w = {5: 0.2, 7: 0.9}
    assert pooled_q_argmax(agg_n, agg_w, min_visits=2) == 7


def test_pooled_q_tiebreaks():
    # equal Q -> higher pooled N wins
    assert pooled_q_argmax({4: 10.0, 6: 20.0}, {4: 5.0, 6: 10.0}) == 6
    # equal Q and N -> lowest action index (deterministic)
    assert pooled_q_argmax({9: 10.0, 2: 10.0}, {9: 5.0, 2: 5.0}) == 2


def test_pooled_q_empty_raises():
    with pytest.raises(ValueError):
        pooled_q_argmax({}, {})


def test_pool_root_stats_dedup_and_sign():
    """Harvest dedups transposition aliases (one child object under two
    actions pools ONCE, lowest action kept) and signs W into the root
    player's perspective."""
    root = Node(state_key="r", player_to_move=0)
    child_a = Node(state_key="a", player_to_move=1)   # opponent to move
    child_a.N, child_a.W = 10, 4.0                    # -> signed -4.0
    child_b = Node(state_key="b", player_to_move=0)   # same player
    child_b.N, child_b.W = 3, 1.5                     # -> signed +1.5
    child_c = Node(state_key="c", player_to_move=1)   # unvisited: skipped
    root.children = {5: child_a, 7: child_a, 9: child_b, 1: child_c}
    from collections import defaultdict
    agg_n, agg_w = defaultdict(float), defaultdict(float)
    pool_root_stats(root, agg_n, agg_w)
    assert dict(agg_n) == {5: 10.0, 9: 3.0}   # 7 deduped (alias), 1 skipped (N=0)
    assert dict(agg_w) == {5: -4.0, 9: 1.5}


# --------------------------------------------------------------------------- #
# (e) the marginalized exact handoff fires at K<=2 (and only there)            #
# --------------------------------------------------------------------------- #
def test_marginalized_handoff_fires_at_k2_and_latches():
    game, board = endgame_position(1, 2)
    agent = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                   sims=16, k_dets=2, seed=5,
                                   exact_endgame=True)
    move = agent.choose_action(board)
    assert agent.exact_moves == 1 and agent.heur_moves == 0
    assert agent.latch_k == 2 and agent.n_timeouts == 0
    assert agent.solver_nodes > 0
    # the move IS the deterministic marginalized-optimal pick
    ref = S.solve(game, board, mode="marginalized", budget=5_000_000)
    assert move == min(ref.optimal_actions)
    assert move in ref.optimal_actions
    # latched: the SAME turn's meeple decision (and everything after) is also
    # solved — turn-atomic handoff, never split across sub-agents.
    nb, _ = game.get_next_state(board, move)
    if game.get_game_ended(nb, 0) == 0.0:
        agent.choose_action(nb)
        assert agent.exact_moves == 2 and agent.heur_moves == 0


def test_no_solver_above_k2():
    """Above the K<=2 band the fair agent must use PIMC search — a clairvoyant
    K=3-4 solve would be the cheating path, and marginalized is intractable."""
    game, board = endgame_position(1, 6)
    agent = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                   sims=8, k_dets=1, seed=5,
                                   exact_endgame=True)
    a = agent.choose_action(board)
    assert game.get_valid_moves(board)[a]
    assert agent.exact_moves == 0 and agent.heur_moves == 1
    assert agent.latch_k is None


def test_exact_endgame_flag_gates_the_handoff():
    game, board = endgame_position(1, 2)
    agent = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                   sims=16, k_dets=1, seed=5,
                                   exact_endgame=False)
    a = agent.choose_action(board)
    assert game.get_valid_moves(board)[a]
    assert agent.exact_moves == 0 and agent.heur_moves == 1


def test_k_remaining_matches_l23_convention():
    game, board = endgame_position(1, 2)
    assert k_remaining(board.state) == 2


# --------------------------------------------------------------------------- #
# (f) FairHeuristicPriorAgent.last_pooled_visits — the distillation stash        #
#     (fair-distill addendum Change 2). ADDITIVE: exposing the pooled visit      #
#     distribution must NOT change the pooled-Q played action.                   #
# --------------------------------------------------------------------------- #
def _prior_cfg():
    """Champion fair_deploy knobs (leaf resolves from the session env — irrelevant
    to the no-behavior-change pin, which is about the stash being inert)."""
    return HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, value_norm=15.0,
                                leaf_quantize="float", final_select="visits",
                                leaf_cfg=None)


def test_prior_last_pooled_visits_nonempty_on_normal_move():
    game, board = midgame_position(3, 20)
    assert int(game.get_valid_moves(board).sum()) > 1, "need a non-forced move"
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True),
                                    cfg=_prior_cfg(), sims=16, k_dets=2, seed=11,
                                    exact_endgame=False)
    a = agent.choose_action(board)
    pv = agent.last_pooled_visits
    assert isinstance(pv, dict) and len(pv) > 0, "normal move must stash a pooled dict"
    assert all(v > 0 for v in pv.values()), "pooled visit counts must be positive"
    assert a in pv, "the played (pooled-Q) action must be a pooled root action"
    assert game.get_valid_moves(board)[a], "played action must be legal"


def test_prior_stash_is_no_behavior_change():
    """Reading last_pooled_visits (the additive stash) must not change the played
    action: a seed-matched agent whose stash we never touch returns the SAME move."""
    _game, board = midgame_position(3, 20)
    a1_agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True),
                                       cfg=_prior_cfg(), sims=16, k_dets=2, seed=11,
                                       exact_endgame=False)
    a1 = a1_agent.choose_action(board)
    _read = dict(a1_agent.last_pooled_visits)   # READ + consume the stash
    assert _read  # (used, so the read is not optimized away)
    a2_agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True),
                                       cfg=_prior_cfg(), sims=16, k_dets=2, seed=11,
                                       exact_endgame=False)
    a2 = a2_agent.choose_action(board)          # never read the stash
    assert a1 == a2, "the additive stash perturbed the played action"


def test_prior_exact_endgame_stash_is_value_only():
    """The exact-endgame latch path stashes {} (an empty dict) so the emitter emits
    a value-only row — this is what makes aux_mask MIXED across a game."""
    game, board = endgame_position(1, 2)   # K=2 TILES root -> marginalized latch
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True),
                                    cfg=_prior_cfg(), sims=16, k_dets=1, seed=5,
                                    exact_endgame=True, exact_max_k=2)
    a = agent.choose_action(board)
    assert agent.exact_moves == 1, "K=2 root must take the exact handoff"
    assert agent.last_pooled_visits == {}, "exact-endgame row must stash {} (value-only)"
    assert game.get_valid_moves(board)[a], "played action must be legal"
