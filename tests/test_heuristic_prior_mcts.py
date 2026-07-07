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


# =========================================================================== #
# Variant flags (LCB final-select / tree-reuse / value_norm) — all DEFAULT-OFF #
# =========================================================================== #

# Bit-exact reference move sequences captured from the PRE-CHANGE champion
# (branch rod_v2_flywheel HEAD 71c6ae8, this file's leaf env + BMILD_CAP8, deck
# seeded random.seed(9_000_000), agent seeds 42/43, sims=16). These are the
# LOAD-BEARING pins: with every variant flag at its default (final_select "Q"/
# "visits", value_norm 15, c_lcb 1.0, reuse_tree False) the agent MUST reproduce
# these byte-for-byte. Regenerate ONLY on an intentional leaf/search change.
_REF_Q_SEED42 = [
    1248, 2501, 1348, 2503, 1150, 2501, 1346, 2510, 1352, 2505, 1449, 2502,
    951, 2510, 1550, 2509, 1055, 2510, 949, 2510, 1359, 2510, 1552, 2510,
    1145, 2510, 1360, 2502, 1257, 2510, 1258, 2503, 1050, 2503, 1360, 2502,
    1054, 2509, 1157, 2510, 844, 2506, 840, 2501, 952, 2510, 1365, 2510,
    1056, 2505, 1369, 2510, 852, 2510, 842, 2510, 1057, 2510, 937, 2510,
    951, 2504, 1550, 2510, 1062, 2503, 740, 2510, 1263, 2504, 736, 2510,
    1340, 2510, 1040, 2502, 733, 2510, 1049, 2510, 1336, 2510, 1036, 2510,
    729, 2510, 1133, 2507, 827, 2502, 1654, 2510, 1432, 2510, 823, 2501,
    1264, 2510, 1662, 2510, 1267, 2508, 1755, 2510, 1744, 2501, 1563, 2501,
    744, 2510, 820, 2510, 1265, 2510, 920, 2510, 1428, 2510, 752, 2510,
    1062, 2503, 859, 2510, 856, 2510, 1756, 2506, 1330, 2510, 1234, 2510,
    1429, 2510, 1857, 2510, 1331, 2510, 1855, 2510, 766, 2510, 1273, 2501,
]
_REF_VISITS_SEED42 = [
    1248, 2501, 1348, 2503, 1149, 2504, 1346, 2510, 1340, 2505, 1453, 2502,
    1050, 2510, 1459, 2508, 949, 2510, 1352, 2501, 949, 2507, 1553, 2510,
    952, 2501, 1458, 2510, 848, 2510, 1652, 2501, 748, 2510, 1460, 2502,
    650, 2503, 652, 2506, 953, 2510, 1056, 2510, 745, 2510, 1565, 2510,
    752, 2510, 1565, 2510, 736, 2502, 758, 2510, 954, 2510, 856, 2501,
    834, 2510, 1752, 2510, 830, 2510, 861, 2510, 825, 2502, 821, 2510,
    823, 2510, 1763, 2510, 868, 2510, 872, 2510, 812, 2510, 1861, 2510,
    876, 2510, 1956, 2506, 876, 2510, 938, 2501, 808, 2510, 971, 2510,
    804, 2510, 1062, 2507, 804, 2510, 1036, 2510, 900, 2510, 1171, 2501,
    1056, 2510, 984, 2510, 988, 2510, 1076, 2510, 993, 2510, 1000, 2505,
    999, 2510, 1100, 2510, 1012, 2510, 1065, 2510, 1020, 2510, 1100, 2510,
    1082, 2510, 1109, 2510, 1087, 2510, 1024, 2510, 1031, 2510, 1352, 2510,
]


def _flags_off_sequence(seed, sims, final_select):
    """Self-play move sequence with ALL variant flags EXPLICITLY at their off
    defaults — the construction the reference was captured with."""
    cfg = HeuristicPriorConfig(
        leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0,
        final_select=final_select,
        value_norm=15.0, c_lcb=1.0, reuse_tree=False,   # variant flags OFF
    )
    game = _new_game()
    random.seed(9_000_000)
    board = game.get_init_board()
    a0 = HeuristicPriorAgent(game, cfg, simulations=sims, seed=seed)
    a1 = HeuristicPriorAgent(_new_game(), cfg, simulations=sims, seed=seed + 1)
    seq = []
    while game.get_game_ended(board, 0) == 0.0:
        agent = a0 if board.state.current_player == 0 else a1
        act = agent.move(board)
        seq.append(int(act))
        board, _ = game.get_next_state(board, act)
    return seq


def test_bit_exact_all_flags_off():
    """LOAD-BEARING: with all variant flags off the agent reproduces the pinned
    pre-change champion move sequences byte-for-byte (both the "Q" default and the
    champion-of-record "visits" selector)."""
    assert _flags_off_sequence(42, 16, "Q") == _REF_Q_SEED42
    assert _flags_off_sequence(42, 16, "visits") == _REF_VISITS_SEED42


def test_final_select_lcb_accepted_and_legal():
    """final_select="lcb" validates and produces a legal move."""
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, final_select="lcb", c_lcb=1.0)
    game, board = _midgame_boards(n=1, plies=40)[0]
    mask = game.get_valid_moves(board)
    agent = HeuristicPriorAgent(_new_game(), cfg, simulations=40, seed=11)
    a = agent.best_action(board)
    assert mask[a]


def test_final_select_bad_value_rejected():
    with pytest.raises(ValueError):
        HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, final_select="nope")


def test_lcb_picks_correct_child():
    """Hand-constructed root: LCB penalizes low-visit high-Q children.
    Children (all same player_to_move as root, so no Q flip):
      A: N=100 Q=0.50   B: N=10 Q=0.90   C: N=1 Q=1.00   D: N=0 (excluded)
    ΣN=111, ln(111)=4.7095.  c_lcb=1.0:  LCB_A≈0.283 > LCB_B≈0.214 > LCB_C≈-1.17
      -> A wins (action 11) despite B,C having higher raw Q.
    c_lcb=0.0 reduces to pure Q -> C wins (action 33). N=0 child D never wins."""
    from carcassonne_ai.mcts import _NeuralNode

    game, board = _midgame_boards(n=1, plies=40)[0]
    key = game.string_representation(board)
    ptm = board.state.current_player

    def _install_root(agent):
        root = _NeuralNode(state_key=key, player_to_move=ptm, expanded=True, N=111)
        cA = _NeuralNode(state_key="A", player_to_move=ptm, N=100, W=50.0, expanded=True)
        cB = _NeuralNode(state_key="B", player_to_move=ptm, N=10, W=9.0, expanded=True)
        cC = _NeuralNode(state_key="C", player_to_move=ptm, N=1, W=1.0, expanded=True)
        cD = _NeuralNode(state_key="D", player_to_move=ptm, N=0, W=999.0)  # excluded
        root.children = {11: cA, 22: cB, 33: cC, 44: cD}
        agent.mcts._nodes[key] = root

    a1 = HeuristicPriorAgent(game, HeuristicPriorConfig(leaf_cfg=BMILD_CAP8,
                             final_select="lcb", c_lcb=1.0), simulations=1, seed=0)
    _install_root(a1)
    assert a1._lcb_action(board) == 11  # LCB winner

    a0 = HeuristicPriorAgent(game, HeuristicPriorConfig(leaf_cfg=BMILD_CAP8,
                             final_select="lcb", c_lcb=0.0), simulations=1, seed=0)
    _install_root(a0)
    assert a0._lcb_action(board) == 33  # c_lcb=0 -> pure argmax-Q


def test_value_norm_plumbing_changes_value_not_priors():
    """value_norm is a live knob: it changes the tanh leaf VALUE but not the
    priors; the manifest records it; default stays 15."""
    assert HeuristicPriorConfig(leaf_cfg=BMILD_CAP8).value_norm == 15.0
    cfg8 = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, value_norm=8.0)
    assert cfg8.value_norm == 8.0
    assert cfg8.as_manifest()["value_norm"] == 8.0
    diffs = 0
    for game, board in _midgame_boards():
        ev15 = make_heuristic_prior_evaluator(game, HeuristicPriorConfig(
            leaf_cfg=BMILD_CAP8, value_norm=15.0))
        ev8 = make_heuristic_prior_evaluator(game, HeuristicPriorConfig(
            leaf_cfg=BMILD_CAP8, value_norm=8.0))
        p15, v15 = ev15(board)
        p8, v8 = ev8(board)
        assert np.allclose(p15, p8)  # priors independent of value_norm
        if abs(v15) > 1e-6:
            assert v15 != v8         # different tanh denominator -> different value
            diffs += 1
    assert diffs >= 1


def test_tree_reuse_hits_and_plays_legal_game():
    """reuse_tree=True: a self-play game completes with only legal moves, the tree
    is actually re-used at least once (reuse_hits>=1), the collision tripwire never
    fires (no AssertionError), and the per-move outcome counters account for every
    prefix move."""
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0)
    game = _new_game()
    random.seed(9_000_000)
    board = game.get_init_board()
    a0 = HeuristicPriorAgent(game, cfg, simulations=32, seed=5, reuse_tree=True)
    a1 = HeuristicPriorAgent(_new_game(), cfg, simulations=32, seed=6)  # reuse OFF
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < 60:
        mask = game.get_valid_moves(board)
        agent = a0 if board.state.current_player == 0 else a1
        act = agent.move(board)
        assert mask[act], f"reuse agent returned illegal action {act}"
        board, _ = game.get_next_state(board, act)
        plies += 1
    assert a0.reuse_hits >= 1, "expected at least one tree-reuse hit"
    assert a0.reuse_hits + a0.reuse_fresh + a0.reuse_collide == a0.neural_moves


def test_tree_reuse_reroots_into_own_successor():
    """The first move is a fresh search; the immediate successor board it produces
    is in the retained tree, so the next move re-roots (a hit) — no clear()."""
    game, board = _midgame_boards(n=1, plies=40)[0]
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0)
    agent = HeuristicPriorAgent(game, cfg, simulations=96, seed=7, reuse_tree=True)
    a0 = agent.move(board)
    assert agent.reuse_fresh == 1 and agent.reuse_hits == 0
    board2, _ = game.get_next_state(board, a0)
    parent_key = game.string_representation(board)
    mask2 = game.get_valid_moves(board2)
    a1 = agent.move(board2)
    assert mask2[a1], "reuse move must be legal"
    # the agent's own successor at high sims should be a HIT (unless the chosen
    # placement was a rotation-collision, which would be a counted fallback);
    # accept either but require the counters to be self-consistent + no crash.
    assert agent.reuse_hits + agent.reuse_fresh + agent.reuse_collide == agent.neural_moves
    if agent.reuse_hits == 1:
        # "drop the rest": re-rooting pruned _nodes to board2's subtree, so the
        # PARENT position (board) — not reachable from board2 — is gone.
        assert parent_key not in agent.mcts._nodes


def test_tree_reuse_fallback_on_unsearched_move():
    """(b) When the next board isn't in the retained tree (opponent played an
    unsearched move — here simulated by an unrelated position), the agent falls
    back to a fresh search: no crash, legal move, reuse_fresh increments."""
    (g0, b0), (g1, b1) = _midgame_boards(n=2, plies=40)
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0)
    agent = HeuristicPriorAgent(g0, cfg, simulations=40, seed=3, reuse_tree=True)
    agent.move(b0)
    assert agent.reuse_fresh == 1
    # b1 is from an unrelated deck -> its key cannot be in b0's retained tree.
    mask1 = g0.get_valid_moves(b1)
    m1 = agent.move(b1)
    assert mask1[m1], "fallback move must be legal"
    assert agent.reuse_fresh == 2 and agent.reuse_hits == 0


def test_tree_reuse_collision_guard_falls_back():
    """(a) A retained node that shares the board's transposition key but carries
    DIFFERENT valid_actions (a wrong-rotation sibling, the Phase-0.3 family) is
    REJECTED by the collision guard -> fresh fallback, no wrong-subtree serving,
    no crash."""
    from carcassonne_ai.mcts import _NeuralNode

    game, board = _midgame_boards(n=1, plies=40)[0]
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8)
    agent = HeuristicPriorAgent(game, cfg, simulations=16, seed=0, reuse_tree=True)
    key = game.string_representation(board)
    ptm = board.state.current_player
    fake = _NeuralNode(state_key=key, player_to_move=ptm, expanded=True, N=99)
    real = sorted(map(int, np.flatnonzero(game.get_valid_moves(board))))
    fake.valid_actions = [real[0] + 100000]  # deliberately NOT the board's real mask
    agent.mcts._nodes[key] = fake
    m = agent.move(board)  # must detect the mismatch -> fresh, no AssertionError
    assert agent.reuse_collide == 1 and agent.reuse_hits == 0
    assert game.get_valid_moves(board)[m], "fallback move must be legal"


def test_reuse_tree_default_off_is_champion_move_path():
    """reuse_tree defaults OFF: move() clear()s the tree every move (champion path).
    A reuse-OFF agent never records a reuse hit/fallback."""
    game, board = _midgame_boards(n=1, plies=40)[0]
    cfg = HeuristicPriorConfig(leaf_cfg=BMILD_CAP8)
    assert cfg.reuse_tree is False
    agent = HeuristicPriorAgent(_new_game(), cfg, simulations=20, seed=1)
    assert agent._reuse_tree is False
    agent.move(board)
    assert agent.reuse_hits == 0 and agent.reuse_fresh == 0 and agent.reuse_collide == 0


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
