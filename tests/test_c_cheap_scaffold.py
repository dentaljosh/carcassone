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
    make_fair_net_prior_evaluator,
    make_heuristic_prior_evaluator,
    make_heuristic_prior_evaluator_with_net_value,
    make_heuristic_prior_evaluator_with_residual_value,
    make_sighted_net_value_fn,
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


# --------------------------------------------------------------------------- #
# 1b. RESIDUAL evaluator: λ=0 is BYTE-IDENTICAL (value AND priors); λ>0 nudges.
# --------------------------------------------------------------------------- #
def test_residual_evaluator_lambda0_byte_identical():
    """C-cheap v2 core invariant: λ=0 residual == the heuristic-value evaluator,
    byte-for-byte (value exactly equal, priors exactly equal) on >=3 midgame boards.
    A random (finite) net proves heur + 0*net == heur and the clip is a no-op."""
    net = _random_sighted_net()
    boards = _midgame_boards(n=4)
    assert len(boards) >= 3, "need >=3 mid-game boards"
    for game, board in boards:
        heur_ev = make_heuristic_prior_evaluator(game, _cfg())
        value_fn, _ = make_sighted_net_value_fn(game, net)
        res_ev = make_heuristic_prior_evaluator_with_residual_value(
            game, _cfg(), value_fn, lam=0.0)
        p_h, v_h = heur_ev(board)
        p_r, v_r = res_ev(board)
        assert np.array_equal(p_h, p_r), "λ=0 residual perturbed the priors"
        assert v_r == v_h, f"λ=0 residual value {v_r!r} != heuristic value {v_h!r}"


def test_residual_evaluator_lambda_nudges_value_only():
    """λ>0 keeps priors byte-identical but shifts the value by λ·net_value; the
    shift equals λ·(net_value) and the result stays in [-1, 1]."""
    net = _random_sighted_net()
    boards = _midgame_boards(n=4)
    nudged = 0
    for game, board in boards:
        heur_ev = make_heuristic_prior_evaluator(game, _cfg())
        value_fn, _ = make_sighted_net_value_fn(game, net)
        res_ev = make_heuristic_prior_evaluator_with_residual_value(
            game, _cfg(), value_fn, lam=0.25)
        p_h, v_h = heur_ev(board)
        p_r, v_r = res_ev(board)
        assert np.array_equal(p_h, p_r), "residual perturbed the priors"
        assert -1.0 <= v_r <= 1.0
        expected = min(1.0, max(-1.0, v_h + 0.25 * value_fn(board)))
        assert abs(v_r - expected) < 1e-6
        if abs(v_r - v_h) > 1e-6:
            nudged += 1
    assert nudged >= 1, "λ=0.25 never moved the value off the heuristic value"


# --------------------------------------------------------------------------- #
# 1c. FAIR-NET-PRIOR evaluator (STAGE-2 flywheel substrate) — the MIRROR of the  #
#     net-value evaluator: net POLICY head -> priors, FROZEN champion leaf -> value.
# --------------------------------------------------------------------------- #
def test_fair_net_prior_evaluator_value_frozen_priors_from_net():
    """make_fair_net_prior_evaluator: VALUE is byte-identical to the frozen champion
    heuristic leaf value (severed value loop), while PRIORS come from the net policy
    head (a valid distribution that generally differs from the heuristic priors)."""
    net = _random_sighted_net()
    # plies=40 -> boards with many legal moves (late boards can be forced/one-hot,
    # where net & heuristic priors trivially coincide).
    boards = _midgame_boards(n=4, plies=40)
    assert len(boards) >= 3, "need >=3 mid-game boards"
    prior_diffs = 0
    multi_legal = 0
    for game, board in boards:
        heur_ev = make_heuristic_prior_evaluator(game, _cfg())
        fairnet_ev = make_fair_net_prior_evaluator(_cfg(), net=net)
        p_h, v_h = heur_ev(board)
        p_fn, v_fn = fairnet_ev(board)
        # VALUE byte-identical: both = tanh(flat_virtual_score_v2_float/value_norm).
        assert v_fn == v_h, f"fair-net value {v_fn!r} != frozen heuristic leaf value {v_h!r}"
        # PRIORS: valid masked distribution over legal, float32, sums to 1.
        assert p_fn.dtype == np.float32
        assert abs(float(p_fn.sum()) - 1.0) < 1e-5
        mask = game.get_valid_moves(board).astype(bool)
        assert float((p_fn * (~mask)).sum()) == 0.0, "net priors put mass off the legal mask"
        if int(mask.sum()) > 1:
            multi_legal += 1
            if not np.array_equal(p_fn, p_h):
                prior_diffs += 1
    assert multi_legal >= 1, "test needs at least one multi-legal board"
    assert prior_diffs >= 1, "net priors never differed from the heuristic priors"


def _random_net_at_rep(sighted, seed=0):
    """A random net whose dims match `Game(sighted=...)` — the two distill candidates
    are sighted (81ch/42) and non-sighted (78ch/10)."""
    probe = Game(sighted=sighted)
    torch.manual_seed(seed)
    net = CarcassonneNet(
        n_input_channels=probe.get_input_channels(),
        n_scalar_features=probe.get_scalar_feature_size(),
        value_global_pool=sighted,
    )
    net.eval()
    return net


@pytest.mark.parametrize("sighted", [True, False])
def test_fair_net_prior_evaluator_rep_switch(sighted):
    """The fair-netprior evaluator drives BOTH candidate reps — sighted (81ch/42) and
    NON-sighted (78ch/10). The frozen leaf VALUE is rep-independent (it reads the
    engine state, not the encode), so only the priors' encode changes."""
    net = _random_net_at_rep(sighted)
    ev = make_fair_net_prior_evaluator(_cfg(), net=net, sighted=sighted)
    expect_ch = 81 if sighted else 78
    expect_sc = 42 if sighted else 10
    assert ev.rep == {"sighted": sighted, "n_input_channels": expect_ch,
                      "n_scalar_features": expect_sc}
    assert ev.sighted is sighted
    assert ev.sighted_game.sighted is sighted

    game, board = _midgame_boards(n=1, plies=40)[0]
    priors, value = ev(board)
    mask = game.get_valid_moves(board).astype(bool)
    assert priors.dtype == np.float32
    assert abs(float(priors.sum()) - 1.0) < 1e-5
    assert float((priors * (~mask)).sum()) == 0.0, "net priors put mass off the legal mask"
    # VALUE is the frozen champion leaf — identical to the heuristic evaluator's value
    # and IDENTICAL ACROSS REPS (the severed value loop never consults the net).
    _, v_heur = make_heuristic_prior_evaluator(game, _cfg())(board)
    assert value == v_heur


def test_fair_net_prior_evaluator_rep_mismatch_fails_loud():
    """A rep/net-dim mismatch must RAISE, never silently mis-encode: feeding a 78ch
    net the 81ch sighted planes (or vice versa) would produce plausible-looking but
    garbage priors, i.e. a quietly weak agent that still passes a smoke test."""
    # non-sighted net + sighted encode
    with pytest.raises(ValueError, match="input channels"):
        make_fair_net_prior_evaluator(_cfg(), net=_random_net_at_rep(False), sighted=True)
    # sighted net + non-sighted encode
    with pytest.raises(ValueError, match="input channels"):
        make_fair_net_prior_evaluator(_cfg(), net=_random_net_at_rep(True), sighted=False)
    # a net whose channels match but whose SCALARS do not (same-ch, different rep)
    torch.manual_seed(0)
    odd = CarcassonneNet(n_input_channels=81, n_scalar_features=10)
    odd.eval()
    with pytest.raises(ValueError, match="scalar features"):
        make_fair_net_prior_evaluator(_cfg(), net=odd, sighted=True)
    # an explicit `sighted` contradicting the supplied encoder must not be guessed
    with pytest.raises(ValueError, match="contradicts"):
        make_fair_net_prior_evaluator(_cfg(), net=_random_net_at_rep(True),
                                      sighted_game=Game(sighted=True), sighted=False)


def test_fair_net_prior_evaluator_defaults_to_sighted():
    """Back-compat: no `sighted` / no `sighted_game` -> the sighted rep (the stage-2
    flywheel callers rely on this default)."""
    ev = make_fair_net_prior_evaluator(_cfg(), net=_random_sighted_net())
    assert ev.sighted_game.sighted is True
    assert ev.rep["n_input_channels"] == 81


def test_fair_net_prior_evaluator_provenance_and_needs_a_source():
    net = _random_sighted_net()
    ev = make_fair_net_prior_evaluator(_cfg(), net=net)
    assert ev.priors_source == "net_policy_head"
    assert ev.value_source == "frozen_champion_v29_leaf"
    assert ev.value_transport == "per-worker CPU net"
    assert ev.sighted_game.sighted is True
    assert ev.net is net
    # neither net nor handles -> loud failure (no silent net-free fallthrough).
    with pytest.raises(ValueError):
        make_fair_net_prior_evaluator(_cfg())


def test_fair_net_prior_agent_plays_full_legal_game():
    """End-to-end: FairHeuristicPriorAgent(evaluator=fair-net-prior) plays a legal
    game — the exact stage-2 gen wiring (net priors steer search, frozen leaf value)."""
    game = Game(enable_legal_moves_cache=True)
    net = _random_sighted_net()
    ev = make_fair_net_prior_evaluator(_cfg(), net=net)
    agent = FairHeuristicPriorAgent(game, _cfg(), sims=8, k_dets=2, seed=3,
                                    evaluator=ev, exact_endgame=False)
    random.seed(7_000_002)
    board = game.get_init_board()
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < 40:
        mask = game.get_valid_moves(board)
        act = agent.move(board)
        assert mask[act], f"fair-net-prior agent returned illegal action {act}"
        # the additive pooled-visit stash still populates (the policy target path).
        assert agent.last_pooled_visits is not None
        board, _ = game.get_next_state(board, act)
        plies += 1
    assert plies > 0 and agent.heur_moves > 0


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


def test_gen_fair_meta_sidecar_stamps_value_target(tmp_path):
    """T4e provenance fix: the per-shard sidecar ALWAYS records `value_target` so a
    shard is self-describing (outcome vs residual) even without the run manifest,
    and the sidecar is EXCLUDED from the training globs."""
    from carcassonne_ai.warmstart import iter_game_dataset_files

    # (a) outcome target: value_target stamped, NO residual diagnostics.
    po = gfs._write_meta_sidecar(tmp_path, 7, "outcome")
    assert po == gfs._meta_path(tmp_path, 7)
    with np.load(po) as m:
        assert str(m["value_target"]) == "outcome"
        assert "z" not in m.files and "leaf_tanh" not in m.files

    # (b) residual target: value_target stamped AND per-ply {z, leaf_tanh}.
    z = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    lt = np.array([0.0, 0.1, -0.1], dtype=np.float32)
    pr = gfs._write_meta_sidecar(tmp_path, 8, "residual", z=z, leaf_tanh=lt)
    with np.load(pr) as m:
        assert str(m["value_target"]) == "residual"
        assert np.array_equal(m["z"], z)
        assert np.array_equal(m["leaf_tanh"], lt)

    # (c) the sidecars are named seed_*.meta.npz and are NOT picked up as training
    # shards (they lack boards/values) — iter_game_dataset_files must skip them.
    assert po.name.endswith(".meta.npz") and pr.name.endswith(".meta.npz")
    (tmp_path / "seed_000000000007.npz").write_bytes(b"")  # a real (empty) shard name
    shards = list(iter_game_dataset_files(tmp_path))
    assert po not in shards and pr not in shards
    assert (tmp_path / "seed_000000000007.npz") in shards
