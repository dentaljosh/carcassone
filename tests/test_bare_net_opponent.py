"""`--opponent bare-net`: our BLIND fair champion vs a SIGHTED bare NeuralMCTS.

The whole point of this mode is an ASYMMETRY that must NOT be "fixed" (see the
BLIND vs SIGHTED block in scripts/classical_search/eval_fair_puct.py). These tests
pin the three axes of that asymmetry, because every one of them is a silent-failure
mode -- a symmetrised cell still produces a perfectly plausible number:

  1. LEAF     candidate == frozen curve125 champion (a36d2e15a3b3d71d);
              opponent  == the rod_v2 ANCHOR leaf, curve100 + residual_scale 0.25
              (4bc26f12badbb10b). They MUST differ.
  2. INFO     candidate is blind (fair PIMC root determinization); opponent is
              CLAIRVOYANT (NeuralMCTS fair_chance=False -> descends the TRUE deck).
  3. ENDGAME  candidate keeps the marginalized exact-K tail; opponent is BARE.

Plus a legacy-additivity guard: the h800 / fair-champion / net modes and their
argument validation are untouched.

Import style follows tests/test_pareto_curve_tally.py: an explicit sys.path insert,
NOT importorskip -- a silently-skipped regression test reads as green.
"""
from __future__ import annotations

import pathlib
import random
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))      # endgame_solver
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
import eval_fair_puct as E  # noqa: E402
from c5_leaf_override import _leaf_hash  # noqa: E402

from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

CURVE125_HASH = "a36d2e15a3b3d71d"      # the frozen production champion leaf
ANCHOR_HASH = "4bc26f12badbb10b"        # curve100 + residual_scale 0.25 (rod_v2 anchor)

# The real anchor checkpoint. Present on the cluster boxes, absent on CI -- the
# net-free tests below cover the same contracts with a random net, so a missing
# share degrades coverage of provenance only, never of the asymmetry itself.
ITER02 = pathlib.Path("/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt")


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _random_anchor_net(seed=0):
    """A randomly-initialised net at the RoD-v2 iter_02 representation
    (non-sighted, 78ch / 12 scalars = 10 base + 2 farm scalars)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    torch.manual_seed(seed)
    probe = Game(sighted=False, include_farm_scalars=True)
    n_ch, n_sc = probe.get_input_channels(), probe.get_scalar_feature_size()
    assert (n_ch, n_sc) == (78, 12), f"unexpected rod_v2 rep {n_ch}ch/{n_sc}sc"
    net = CarcassonneNet(n_input_channels=n_ch, n_scalar_features=n_sc,
                         value_global_pool=False)
    net.eval()
    rep = {"sighted": False, "n_input_channels": n_ch, "n_scalar_features": n_sc,
           "include_farm_scalars": True, "value_global_pool": False,
           "iter": None, "provenance": "RANDOM (unit-test net)"}
    return net, rep


def _board_with_a_real_choice(game, max_plies=8):
    """The initial board is a FORCED move (one legal action), and both fair PIMC and
    a spy on the search path short-circuit there. Advance until a genuine choice."""
    import numpy as np
    board = game.get_init_board()
    for _ in range(max_plies):
        legal = np.flatnonzero(game.get_valid_moves(board))
        if legal.size > 1:
            return board
        board, _ = game.get_next_state(board, int(legal[0]))
    raise AssertionError("no branching position within max_plies")


def _cand_cfg():
    """The candidate exactly as main() resolves it for a bare-net cell: production
    search knobs + the auto-injected frozen curve125 leaf."""
    return E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0,
                              E._curve125_leaf_cfg())


# --------------------------------------------------------------------------- #
# 1. LEAF IDENTITY -- the assertion that matters most                          #
# --------------------------------------------------------------------------- #
def test_candidate_leaf_is_the_frozen_curve125_champion():
    cfg = E._curve125_leaf_cfg()
    assert tuple(float(x) for x in cfg.v29_meeple_curve) == E.CURVE125
    assert _leaf_hash(cfg) == CURVE125_HASH


def test_opponent_leaf_is_the_anchor_leaf_not_curve125():
    cfg = E._bare_net_leaf_cfg()
    # curve100 -- the v2.9 Bmild_cap8 base the anchor rows were played on
    assert tuple(float(x) for x in cfg.v29_meeple_curve) == E.CURVE100
    assert cfg.residual_scale == E.BARE_NET_RESIDUAL_SCALE == 0.25
    assert cfg.meeple_k == E.BARE_NET_MEEPLE_K == 2.0
    assert cfg.bonus_cap == 8.0 and cfg.opp_bonus_cap == 8.0     # Bmild_cap8
    assert _leaf_hash(cfg) == ANCHOR_HASH == E.BARE_NET_LEAF_HASH


def test_the_two_sides_get_DIFFERENT_leaves():
    cand = E._curve125_leaf_cfg()
    opp = E._bare_net_leaf_cfg()
    assert _leaf_hash(cand) != _leaf_hash(opp), (
        "candidate and bare-net opponent must NOT share a leaf -- equality means the "
        "curve125 injection leaked onto the anchor")
    assert _leaf_hash(cand) == CURVE125_HASH
    assert _leaf_hash(opp) == ANCHOR_HASH


def test_opponent_leaf_construction_matches_the_anchor_harness_verbatim():
    """`_bare_net_leaf_cfg()` must equal eval_puct_priors._NetPrefix's inline
    dc.replace(DEFAULT_CONFIG, residual_scale=NET_RESIDUAL_SCALE, meeple_k=NET_MEEPLE_K)."""
    import dataclasses as dc
    import eval_puct_priors as P
    assert (E.BARE_NET_SIMS, E.BARE_NET_CPUCT,
            E.BARE_NET_RESIDUAL_SCALE, E.BARE_NET_MEEPLE_K) == \
           (P.NET_SIMS, P.NET_CPUCT, P.NET_RESIDUAL_SCALE, P.NET_MEEPLE_K)
    # the two harnesses share a verbatim _CANON_ENV -> the same DEFAULT_CONFIG value
    assert E._CANON_ENV == P._CANON_ENV
    inline = dc.replace(DEFAULT_CONFIG, residual_scale=P.NET_RESIDUAL_SCALE,
                        meeple_k=P.NET_MEEPLE_K)
    assert E._bare_net_leaf_cfg() == inline


def test_assert_bare_net_leaf_rejects_a_curve125_opponent():
    with pytest.raises(SystemExit) as ei:
        E._assert_bare_net_leaf(E._curve125_leaf_cfg())
    assert "curve100" in str(ei.value)


def test_assert_bare_net_leaf_rejects_identical_sides():
    """The leak guard: same cfg on both sides must hard-fail, not quietly pass."""
    cfg = E._bare_net_leaf_cfg()
    with pytest.raises(SystemExit) as ei:
        E._assert_bare_net_leaf(cfg, cand_cfg=cfg)
    assert "SAME leaf" in str(ei.value)


def test_assert_bare_net_leaf_rejects_a_moved_residual_scale():
    import dataclasses as dc
    with pytest.raises(SystemExit):
        E._assert_bare_net_leaf(dc.replace(E._bare_net_leaf_cfg(), residual_scale=0.5))


def test_default_config_is_still_the_curve100_ruler():
    """The bare-net opponent leaf is derived from DEFAULT_CONFIG, so a moved
    DEFAULT_CONFIG would silently replace the anchor. Same guard the rung has."""
    assert E._assert_rung_is_ruler() == _leaf_hash(DEFAULT_CONFIG)
    assert tuple(float(x) for x in DEFAULT_CONFIG.v29_meeple_curve) == E.CURVE100


# --------------------------------------------------------------------------- #
# 2. CONSTRUCTED AGENTS -- both sides, no games played                         #
# --------------------------------------------------------------------------- #
def test_constructed_sides_carry_the_right_and_different_leaves():
    net, rep = _random_anchor_net()
    cfg = _cand_cfg()
    champ = E._make_champion("fair", cfg, sims=8, k_dets=2, K=2, seed=1,
                             game=Game(enable_legal_moves_cache=True))
    opp = E._make_opponent("bare-net", None, sims=8, k_dets=2, K=2, rung_sims=800,
                           seed=1, opp_leaf_cfg=E._bare_net_leaf_cfg(),
                           net=net, rep=rep)

    cand_leaf = champ._prefix._cfg.resolved_leaf_cfg()
    assert _leaf_hash(cand_leaf) == CURVE125_HASH, _leaf_hash(cand_leaf)
    assert _leaf_hash(opp.leaf_cfg) == ANCHOR_HASH, _leaf_hash(opp.leaf_cfg)
    assert _leaf_hash(cand_leaf) != _leaf_hash(opp.leaf_cfg)
    # the evaluator the candidate's search actually calls must carry the same leaf
    assert _leaf_hash(champ._prefix._evaluator.leaf_cfg) == CURVE125_HASH


def test_opponent_is_clairvoyant_and_pinned_to_the_anchor_knobs():
    net, rep = _random_anchor_net()
    opp = E._make_opponent("bare-net", None, sims=8, k_dets=2, K=2, rung_sims=800,
                           seed=1, opp_leaf_cfg=E._bare_net_leaf_cfg(),
                           net=net, rep=rep)
    assert isinstance(opp, E._BareNetPrefix)
    # CLAIRVOYANT: fair_chance=False means NeuralMCTS.search descends the engine's
    # TRUE pre-shuffled deck (no _reshuffled_root call). This is the handicap our
    # blind candidate is being asked to overcome -- it must not be "fixed".
    assert opp.mcts.fair_chance is False
    assert opp.mcts.fair_isolate is False
    assert opp.mcts.simulations == E.BARE_NET_SIMS == 200
    assert opp.mcts.c_puct == E.BARE_NET_CPUCT == 3.0
    # the encoder width comes from the OPPONENT's own rep
    assert opp.mcts.game.get_input_channels() == rep["n_input_channels"]
    assert opp.mcts.game.get_scalar_feature_size() == rep["n_scalar_features"]


def test_candidate_is_genuinely_blinding():
    """The candidate is the fair PIMC agent and its determinization path really is
    in use: reshuffled_determinization must permute the unseen deck while preserving
    the multiset (i.e. the search sees a plausible world, not the true one)."""
    champ = E._make_champion("fair", _cand_cfg(), sims=8, k_dets=4, K=2, seed=1,
                             game=Game(enable_legal_moves_cache=True))
    agent = champ._prefix
    assert isinstance(agent, FairHeuristicPriorAgent)
    assert agent._k_dets == 4
    # exact_endgame is OFF on the agent: the harness's _MarginalizedHandoff owns the
    # tail so both arms share one implementation.
    assert agent._exact_endgame is False

    # _pimc_move determinizes via FairHeuristicMCTSAgent.reshuffled_determinization
    # (a staticmethod shared by both fair agents) -- exercise that exact call.
    from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    true_deck = [t.description for t in board.state.deck]
    det = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(7))
    det_deck = [t.description for t in det.state.deck]
    assert sorted(det_deck) == sorted(true_deck), "determinization changed the multiset"
    assert det_deck != true_deck, "determinization did not reshuffle the unseen deck"
    assert [t.description for t in board.state.deck] == true_deck, "caller board mutated"


def test_candidate_actually_calls_the_determinization_path_per_move(monkeypatch):
    """Stronger than the shape check above: spy on the determinization staticmethod
    during ONE real fair move and assert it fired once PER WORLD. If the candidate
    ever stopped blinding, this is what would catch it."""
    from carcassonne_ai import fair_agent as FA
    calls = []
    orig = FA.FairHeuristicMCTSAgent.reshuffled_determinization

    def spy(board, rng):
        calls.append(1)
        return orig(board, rng)

    monkeypatch.setattr(FA.FairHeuristicMCTSAgent, "reshuffled_determinization",
                        staticmethod(spy))
    agent = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _cand_cfg(),
                                    sims=4, k_dets=3, seed=1, exact_endgame=False)
    game = Game(enable_legal_moves_cache=True)
    board = _board_with_a_real_choice(game)
    agent.choose_action(board)
    assert len(calls) == 3, f"expected one determinization per world, got {len(calls)}"


def test_opponent_never_reshuffles_the_deck(monkeypatch):
    """The mirror of the test above: the SIGHTED opponent must search the TRUE deck.
    Spy on NeuralMCTS._reshuffled_root across a real (tiny) search -- zero calls."""
    from carcassonne_ai import mcts as M
    calls = []
    orig = M.NeuralMCTS._reshuffled_root
    monkeypatch.setattr(M.NeuralMCTS, "_reshuffled_root",
                        lambda self, b: (calls.append(1), orig(self, b))[1])

    net, rep = _random_anchor_net()
    opp = E._make_opponent("bare-net", None, sims=8, k_dets=2, K=2, rung_sims=800,
                           seed=1, opp_leaf_cfg=E._bare_net_leaf_cfg(),
                           net=net, rep=rep)
    opp.mcts.simulations = 4          # keep the unit test cheap; fair_chance unchanged
    game = Game(enable_legal_moves_cache=True)
    board = _board_with_a_real_choice(game)     # not the forced opening move
    true_deck = [t.description for t in board.state.deck]
    # count evaluator calls so a short-circuited "search" cannot pass vacuously
    evals = []
    inner = opp.mcts.evaluator
    opp.mcts.evaluator = lambda b: (evals.append(1), inner(b))[1]
    opp.move(board)
    assert evals, "the opponent search never ran -- the no-reshuffle check would be vacuous"
    assert calls == [], "sighted opponent reshuffled the deck -- it must be clairvoyant"
    assert [t.description for t in board.state.deck] == true_deck


def test_endgame_tail_is_one_sided():
    """The candidate is wrapped in the marginalized exact-K handoff; the bare-net
    opponent is NOT. (The harness has always supported a one-sided tail -- the h800
    rung is tail-less too -- so no new machinery is involved.)"""
    net, rep = _random_anchor_net()
    champ = E._make_champion("fair", _cand_cfg(), sims=8, k_dets=2, K=2, seed=1,
                             game=Game(enable_legal_moves_cache=True))
    opp = E._make_opponent("bare-net", None, sims=8, k_dets=2, K=2, rung_sims=800,
                           seed=1, opp_leaf_cfg=E._bare_net_leaf_cfg(),
                           net=net, rep=rep)
    assert isinstance(champ, E._MarginalizedHandoff) and champ._K == 2
    assert not isinstance(opp, E._MarginalizedHandoff)
    # ... and the GameResult opponent fields degrade to the h800-style zeros
    assert E._opp_stats(opp) == {"opp_prefix_moves": 0, "opp_exact_moves": 0,
                                 "opp_prefix_secs": 0.0, "opp_solver_secs": 0.0,
                                 "opp_timeouts": 0, "opp_latch_k": None}


@pytest.mark.skipif(not ITER02.is_file(), reason=f"anchor checkpoint {ITER02} not mounted")
def test_real_iter02_checkpoint_resolves_the_rodv2_anchor_rep():
    _net, rep = E._load_net_rep(str(ITER02), device="cpu")
    assert rep["sighted"] is False
    assert (rep["n_input_channels"], rep["n_scalar_features"]) == (78, 12)
    assert rep["include_farm_scalars"] is True


# --------------------------------------------------------------------------- #
# 3. CLI wiring + legacy additivity                                            #
# --------------------------------------------------------------------------- #
def test_bare_net_is_not_a_symmetric_head_to_head():
    """_HEAD_TO_HEAD gates curve125-on-both-sides, the opponent endgame, the
    opponent prefix-timing read-out and the shared-knob framing. bare-net must be
    outside it or the cell silently symmetrises."""
    assert "bare-net" in E.OPPONENT_MODES
    assert "bare-net" not in E._HEAD_TO_HEAD
    assert E._HEAD_TO_HEAD == ("fair-champion", "net")


def _run_main(argv):
    """Run main() expecting an argparse error; return the SystemExit code/message."""
    return E.main(argv)


@pytest.mark.parametrize("argv,needle", [
    (["--opponent", "bare-net", "--smoke"], "requires --opp-net"),
    (["--opponent", "bare-net", "--opp-net", "/x.pt", "--opp-sims", "400"],
     "does not apply to --opponent bare-net"),
    (["--opponent", "bare-net", "--opp-net", "/x.pt", "--opp-k-dets", "8"],
     "does not apply to --opponent bare-net"),
    (["--opponent", "bare-net", "--opp-net", "/x.pt", "--opp-orch-shm-name", "s"],
     "only applies to --opponent net"),
    (["--opponent", "h800", "--opp-net", "/x.pt"],
     "only applies to --opponent net / bare-net"),
])
def test_bare_net_argument_validation(argv, needle, capsys):
    with pytest.raises(SystemExit):
        _run_main(argv)
    assert needle in capsys.readouterr().err


def test_legacy_opponent_modes_still_parse_and_build():
    """Additivity: the h800 rung and the fair-champion head-to-head are unchanged."""
    rung = E._make_opponent("h800", {"c_puct": 1.5, "tau_p": 5.0,
                                     "leaf_quantize": "float",
                                     "final_select": "visits", "value_norm": 15.0},
                            sims=8, k_dets=2, K=2, rung_sims=800, seed=1)
    assert isinstance(rung, E._RungPrefix)
    assert not isinstance(rung, E._MarginalizedHandoff)
    # the ruler never takes a leaf override
    assert _leaf_hash(rung._m.leaf_cfg if hasattr(rung._m, "leaf_cfg")
                      else DEFAULT_CONFIG) == _leaf_hash(DEFAULT_CONFIG)

    h2h = E._make_opponent("fair-champion", {"c_puct": 1.5, "tau_p": 5.0,
                                             "leaf_quantize": "float",
                                             "final_select": "visits",
                                             "value_norm": 15.0},
                           sims=8, k_dets=2, K=2, rung_sims=800, seed=1,
                           opp_leaf_cfg=E._curve125_leaf_cfg())
    assert isinstance(h2h, E._MarginalizedHandoff)      # symmetric tail, unchanged
    assert _leaf_hash(h2h._prefix._cfg.resolved_leaf_cfg()) == CURVE125_HASH


def test_unknown_opponent_still_raises():
    with pytest.raises(ValueError):
        E._make_opponent("nope", {"c_puct": 1.5, "tau_p": 5.0,
                                  "leaf_quantize": "float",
                                  "final_select": "visits", "value_norm": 15.0},
                         sims=8, k_dets=2, K=2, rung_sims=800, seed=1)


def test_summary_uses_the_driver_timing_for_a_bare_opponent():
    """bare-net has no handoff counters, so the opponent ms/move must come from the
    DRIVER-timed rung_secs/rung_moves (which for a tail-less agent IS prefix time),
    not from the zeroed opp_prefix_* fields."""
    rs = [E.GameResult(seed=1, a_seat=0, info="fair", exact_k=2, k_dets=4, sims=344,
                       rung_sims=800, score_p0=80, score_p1=70, diff=10,
                       won_by_champ=True, drew=False, elapsed_s=1.0, moves=70,
                       champ_prefix_moves=30, champ_prefix_secs=3.0,
                       rung_moves=35, rung_secs=7.0, opponent="bare-net"),
          E.GameResult(seed=1, a_seat=1, info="fair", exact_k=2, k_dets=4, sims=344,
                       rung_sims=800, score_p0=70, score_p1=80, diff=10,
                       won_by_champ=True, drew=False, elapsed_s=1.0, moves=70,
                       champ_prefix_moves=30, champ_prefix_secs=3.0,
                       rung_moves=35, rung_secs=7.0, opponent="bare-net")]
    summ = E._summary(rs, "fair", 2, 4, 344, 800, opponent="bare-net",
                      opp_label="SIGHTED bare NeuralMCTS")
    assert summ["opponent"] == "bare-net"
    assert summ["rung_ms_per_move"] == pytest.approx(7.0 / 35 * 1e3)
    assert summ["champ_prefix_ms_per_move"] == pytest.approx(3.0 / 30 * 1e3)
