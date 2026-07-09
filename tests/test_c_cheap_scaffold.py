"""C-cheap scaffold contracts (deck-aware value in the fair PIMC loop).

Proves the four build invariants from C_CHEAP_SPEC §7 + the task brief:

  1. BIT-EXACT-OFF (priors): make_heuristic_prior_evaluator_with_net_value produces
     priors BYTE-IDENTICAL to make_heuristic_prior_evaluator — only the value differs
     (swapped to the learned deck-aware net value).
  2. FairHeuristicPriorAgent with net=None/evaluator=None is the SAME heuristic-value
     evaluator as before (default bit-exact), and an explicit net/evaluator override
     is honored; a net-valued fair agent plays a full legal game.
  3. ENCODE PARITY: the sighted (81ch/42-scalar) obs the eval-time net value is fed
     is byte-identical to the sighted obs gen_fair_selfplay records at train time
     (both = Game(sighted=True).get_canonical_form(board, mover)).
  4. GEN: play_fair_game_to_dataset emits a valid value-only GameDataset with the
     right shapes and the mover-POV score_diff_wide value target; it round-trips npz.

Leaf env pinned to the production v2.9 Bmild_cap8 substrate BEFORE importing
carcassonne_ai (mirrors test_heuristic_prior_mcts.py)."""
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
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import dataclasses as dc
import random
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent, FairHeuristicPriorAgent
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.heuristic_prior_mcts import (
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
    make_heuristic_prior_evaluator_with_net_value,
)
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.sighted_planes import N_BAG, N_FARM_PLANES
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "canonical_az"))
import gen_fair_selfplay as gfs  # noqa: E402

MILD_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
V28 = dc.replace(DEFAULT_CONFIG, meeple_k=2.0)
BMILD_CAP8 = dc.replace(V28, v29_meeple_curve=MILD_CURVE, bonus_cap=8.0, opp_bonus_cap=8.0)

SIGHTED_CH = 78 + N_FARM_PLANES        # 81
SIGHTED_SCALARS = 10 + N_BAG           # 42


def _cfg():
    return HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0)


def _random_sighted_net(seed=0, value_global_pool=True):
    torch.manual_seed(seed)
    net = CarcassonneNet(
        n_input_channels=SIGHTED_CH, n_scalar_features=SIGHTED_SCALARS,
        value_global_pool=value_global_pool,
    )
    net.eval()
    return net


def _midgame_boards(n=4, plies=55):
    """(game, board) mid-game snapshots on a blind Game (seeded, reproducible)."""
    out = []
    for s in range(n):
        game = Game(enable_legal_moves_cache=True)
        random.seed(3_000_000 + s)
        board = game.get_init_board()
        rng = np.random.default_rng(500 + s)
        for _ in range(plies):
            if game.get_game_ended(board, 0) != 0.0:
                break
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        if game.get_game_ended(board, 0) == 0.0:
            out.append((game, board))
    return out


# --------------------------------------------------------------------------- #
# 1. BIT-EXACT-OFF (priors): net-value evaluator keeps priors, swaps value.
# --------------------------------------------------------------------------- #
def test_net_value_evaluator_priors_identical_value_differs():
    net = _random_sighted_net()
    boards = _midgame_boards()
    assert boards, "no mid-game boards produced"
    value_diffs = 0
    for game, board in boards:
        heur_ev = make_heuristic_prior_evaluator(game, _cfg())
        net_ev = make_heuristic_prior_evaluator_with_net_value(game, _cfg(), net)
        p_h, v_h = heur_ev(board)
        p_n, v_n = net_ev(board)
        # PRIORS byte-identical (the whole point — only the value line changed).
        assert np.array_equal(p_h, p_n), "net-value evaluator perturbed the priors"
        # priors are still a valid distribution over legal moves.
        assert p_n.dtype == np.float32
        assert abs(float(p_n.sum()) - 1.0) < 1e-5
        # VALUE is the net value in [-1, 1], generally != the heuristic value.
        assert -1.0 <= v_n <= 1.0
        if abs(v_n - v_h) > 1e-6:
            value_diffs += 1
    assert value_diffs >= 1, "net value never differed from the heuristic value"


def test_net_value_evaluator_provenance_and_dim_guard():
    game = Game(enable_legal_moves_cache=True)
    net = _random_sighted_net()
    ev = make_heuristic_prior_evaluator_with_net_value(game, _cfg(), net)
    assert ev.net is net
    assert ev.sighted_game.sighted is True
    assert ev.leaf_name.endswith("_netvalue")
    assert callable(ev.root_logits)
    # a blind (78ch/10-scalar) net must be rejected loudly, not silently mis-fed.
    blind_net = CarcassonneNet()  # 78ch / 10-scalar default
    with pytest.raises(ValueError):
        make_heuristic_prior_evaluator_with_net_value(game, _cfg(), blind_net)


# --------------------------------------------------------------------------- #
# 2. FairHeuristicPriorAgent default is bit-exact; net/evaluator overrides work.
# --------------------------------------------------------------------------- #
def test_fair_agent_default_evaluator_is_heuristic():
    game = Game(enable_legal_moves_cache=True)
    agent = FairHeuristicPriorAgent(game, _cfg(), sims=16, k_dets=2, seed=1)
    ref = make_heuristic_prior_evaluator(game, _cfg())
    for _, board in _midgame_boards(n=2):
        p_a, v_a = agent._evaluator(board)
        p_r, v_r = ref(board)
        assert np.array_equal(p_a, p_r)
        assert v_a == v_r   # default value is the heuristic leaf value, unchanged
    assert agent._net is None


def test_fair_agent_net_override_builds_net_value_evaluator():
    game = Game(enable_legal_moves_cache=True)
    net = _random_sighted_net()
    agent = FairHeuristicPriorAgent(game, _cfg(), sims=16, k_dets=2, seed=1, net=net)
    assert agent._evaluator.net is net
    # priors match the heuristic evaluator; value is the net value.
    heur = make_heuristic_prior_evaluator(game, _cfg())
    _, board = _midgame_boards(n=1)[0]
    p_a, v_a = agent._evaluator(board)
    p_h, v_h = heur(board)
    assert np.array_equal(p_a, p_h)
    assert -1.0 <= v_a <= 1.0


def test_fair_agent_explicit_evaluator_override_used():
    game = Game(enable_legal_moves_cache=True)
    sentinel = make_heuristic_prior_evaluator(game, _cfg())
    agent = FairHeuristicPriorAgent(game, _cfg(), sims=8, k_dets=1, seed=1, evaluator=sentinel)
    assert agent._evaluator is sentinel


def test_net_valued_fair_agent_plays_full_legal_game():
    """End-to-end plumbing: a net-valued fair agent (random net) plays a legal game."""
    game = Game(enable_legal_moves_cache=True)
    net = _random_sighted_net()
    random.seed(7_000_001)
    board = game.get_init_board()
    agent = FairHeuristicPriorAgent(game, _cfg(), sims=8, k_dets=2, seed=3,
                                    net=net, exact_endgame=False)
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < 40:
        mask = game.get_valid_moves(board)
        act = agent.move(board)
        assert mask[act], f"net-valued fair agent returned illegal action {act}"
        board, _ = game.get_next_state(board, act)
        plies += 1
    assert plies > 0
    assert agent.heur_moves > 0


# --------------------------------------------------------------------------- #
# 3. ENCODE PARITY: eval-time obs == train-time obs (both sighted mover-POV).
# --------------------------------------------------------------------------- #
def test_sighted_encode_parity_eval_vs_train():
    game = Game(enable_legal_moves_cache=True)
    net = _random_sighted_net()
    ev = make_heuristic_prior_evaluator_with_net_value(game, _cfg(), net)
    fresh_encoder = Game(sighted=True)   # the encoder gen_fair_selfplay uses
    for _, board in _midgame_boards(n=3):
        mover = board.state.current_player
        eval_obs, eval_scl = ev.sighted_game.get_canonical_form(board, mover)
        train_obs, train_scl = fresh_encoder.get_canonical_form(board, mover)
        assert eval_obs.shape == (SIGHTED_CH, game.window_size, game.window_size)
        assert eval_scl.shape == (SIGHTED_SCALARS,)
        assert np.array_equal(eval_obs, train_obs)
        assert np.array_equal(eval_scl, train_scl)


# --------------------------------------------------------------------------- #
# 4. GEN: net-free fair self-play emits a valid value-only GameDataset.
# --------------------------------------------------------------------------- #
def test_gen_fair_selfplay_dataset_shapes_and_target(tmp_path):
    ds, info = gfs.play_fair_game_to_dataset(
        seed=1234, k_dets=2, sims=8, exact_endgame=False)
    assert ds is not None, f"gen produced no dataset: {info}"
    assert info["terminated"] is True
    N = len(ds)
    A = Game().get_action_size()
    W = 25
    assert N == info["plies"] == ds.boards.shape[0]
    assert ds.boards.shape == (N, SIGHTED_CH, W, W)
    assert ds.boards.dtype == np.float32
    assert ds.scalars.shape == (N, SIGHTED_SCALARS)
    assert ds.values.shape == (N,)
    assert ds.policies.shape == (N, A)
    assert ds.valid_masks.shape == (N, A)
    # value-only rows: aux_mask all False, dummy policy/mask.
    assert ds.aux_mask.dtype == bool and not ds.aux_mask.any()
    assert not ds.policies.any()
    assert not ds.valid_masks.any()
    # value target = mover-POV score_diff_wide of the FINAL score.
    assert np.all(np.abs(ds.values) <= 1.0)
    z_p0 = float(np.tanh((info["score_p0"] - info["score_p1"]) / 40.0))
    assert abs(abs(ds.values[0]) - abs(z_p0)) < 1e-6

    # npz round-trips through the existing loader.
    from carcassonne_ai.warmstart import GameDataset
    p = tmp_path / "seed_000000001234.npz"
    ds.save(p)
    ds2 = GameDataset.load(p)
    assert ds2.boards.shape == ds.boards.shape
    assert np.array_equal(ds2.values, ds.values)
    assert not ds2.aux_mask.any()


def test_gen_fair_selfplay_determinism():
    """Same seed -> identical value labels (deterministic net-free fair self-play)."""
    ds_a, _ = gfs.play_fair_game_to_dataset(seed=99, k_dets=2, sims=8, exact_endgame=False)
    ds_b, _ = gfs.play_fair_game_to_dataset(seed=99, k_dets=2, sims=8, exact_endgame=False)
    assert ds_a is not None and ds_b is not None
    assert np.array_equal(ds_a.values, ds_b.values)
    assert np.array_equal(ds_a.boards, ds_b.boards)
