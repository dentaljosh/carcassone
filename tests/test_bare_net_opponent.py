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
    # the two harnesses share a verbatim _CANON_ENV -> the same DEFAULT_CONFIG value.
    #
    # ⚠️ This stays a VERBATIM equality even though eval_fair_puct now supports running
    # the anchor's net on the GPU. Putting the net on the GPU did NOT require relaxing
    # `CUDA_VISIBLE_DEVICES: ""`: the GPU path is the carc-orch SHM orchestrator, where
    # a SEPARATE Rust server process owns the only net and this process stays CPU-only,
    # shipping (obs, scalars, mask) over shared memory. So the leaf env AND the CUDA
    # masking are both untouched, and this assertion keeps its full strength. If someone
    # ever adds a per-worker net-on-CUDA fallback, THAT is the change that would need
    # this to become a leaf-keys-only comparison — do not pre-weaken it for a path that
    # does not exist.
    assert E._CANON_ENV == P._CANON_ENV
    assert E._CANON_ENV["CUDA_VISIBLE_DEVICES"] == ""
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
    # --opp-orch-shm-name is now VALID for bare-net (the GPU transport); it stays
    # rejected for the two NET-FREE opponents, where a server would have nothing to
    # serve. See test_orch_shm_name_is_accepted_for_bare_net below for the positive case.
    (["--opponent", "h800", "--opp-orch-shm-name", "s"],
     "only applies to a net opponent"),
    (["--opponent", "fair-champion", "--opp-orch-shm-name", "s"],
     "only applies to a net opponent"),
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


# --------------------------------------------------------------------------- #
# 4. GPU TRANSPORT (--opp-orch-shm-name) — the net on the GPU, not per-worker   #
#    CPU. carc-orch owns the only net; this process stays CPU-only and ships    #
#    (obs, scalars, mask) over shared memory.                                   #
#                                                                               #
# The load-bearing claim is that this is a TRANSPORT change and nothing else:   #
# same weights, same leaf, same sims/c_puct, same clairvoyance, same bare tail. #
# The loopback test below proves the WIRING is identity-preserving exactly (an  #
# in-process "server" running the same CPU net must reproduce the CPU agent's   #
# move bit-for-bit); the CUDA test proves the real path lands on the GPU. What  #
# neither can prove is float equality between CPU and GPU — that is measured,   #
# not asserted: scripts/classical_search/bare_net_gpu_divergence.py.            #
# --------------------------------------------------------------------------- #
import os          # noqa: E402
import shutil      # noqa: E402
import subprocess  # noqa: E402

ORCH_BIN = REPO / "rust" / "carc-orch" / "target" / "release" / "carc-orch"


def _cuda_present() -> bool:
    """Is there a usable GPU on this box?

    ⚠️ NOT `torch.cuda.is_available()`: importing eval_fair_puct sets
    CUDA_VISIBLE_DEVICES="" process-wide (its _CANON_ENV), so torch would report
    False on a box that has a perfectly good GPU and the CUDA test would SKIP
    SILENTLY — the exact "a skipped test reads as green" failure this file's header
    warns about. Ask the driver instead, out of band."""
    if not shutil.which("nvidia-smi"):
        return False
    try:
        out = subprocess.check_output(["nvidia-smi", "-L"], text=True, timeout=30)
    except Exception:
        return False
    return "GPU 0" in out


class _LoopbackHandles:
    """A `ServerHandles`-shaped stand-in that answers each request IN-PROCESS from the
    same CPU net, doing exactly what the carc-orch server does to the arrays (net
    forward + masked softmax — see scripts/export_torchscript.py::_ScriptedEvaluator).

    Because it runs the SAME weights on the SAME device with the SAME ops, its answers
    are bit-identical to `evaluators.make_single_evaluator`'s. So any difference between
    a CPU-transport agent and a loopback-transport agent can only come from the WIRING,
    which is what this isolates: no GPU, no subprocess, no float noise."""

    def __init__(self, net, game):
        import queue as _queue
        from carcassonne_ai.eval_server import EvalResponse
        self.worker_id = 0
        self.response_q = _queue.Queue()
        self.n_requests = 0
        outer = self

        class _RequestQ:
            def put(self, req):
                import torch
                outer.n_requests += 1
                with torch.no_grad():
                    logits, value = net(torch.from_numpy(req.obs).float(),
                                        torch.from_numpy(req.scalars).float())
                    priors = net.policy_softmax_with_mask(
                        logits, torch.from_numpy(req.mask.copy()).bool())
                outer.response_q.put(EvalResponse(
                    request_id=req.request_id,
                    priors=priors.numpy(),
                    values=value.reshape(-1).numpy()))

        self.request_q = _RequestQ()


def test_orch_shm_name_is_accepted_for_bare_net(capsys):
    """The POSITIVE case for the flag the validation table now rejects only for the
    net-free opponents: bare-net + --opp-orch-shm-name must get PAST validation.
    (It then dies loading the bogus checkpoint, which is the point — the failure is
    the missing file, not the flag.)"""
    with pytest.raises((FileNotFoundError, OSError)):
        E.main(["--opponent", "bare-net", "--opp-net", "/x.pt",
                "--opp-orch-shm-name", "s", "--smoke"])
    err = capsys.readouterr().err
    assert "only applies" not in err, err


def test_make_bare_net_opponent_requires_exactly_one_transport():
    """net XOR handles. Neither = nothing to evaluate with; BOTH = an ambiguous
    agent where the reader cannot tell which forward actually ran."""
    net, rep = _random_anchor_net()
    with pytest.raises(ValueError, match="EXACTLY ONE"):
        E._make_bare_net_opponent(None, rep, seed=1)
    with pytest.raises(ValueError, match="EXACTLY ONE"):
        E._make_bare_net_opponent(net, rep, seed=1,
                                  handles=_LoopbackHandles(net, Game()))
    # ...and the rep is still mandatory on the orch path (slot dims come from it)
    with pytest.raises(ValueError, match="rep"):
        E._make_bare_net_opponent(None, None, seed=1,
                                  handles=_LoopbackHandles(net, Game()))


def test_orch_transport_preserves_every_pinned_anchor_knob():
    """The three asymmetry axes + the pinned play knobs must be IDENTICAL on the orch
    path. A transport change that quietly re-shaped the agent would still produce a
    plausible number."""
    net, rep = _random_anchor_net()
    h = _LoopbackHandles(net, Game())
    opp = E._make_bare_net_opponent(None, rep, seed=1,
                                    leaf_cfg=E._bare_net_leaf_cfg(), handles=h)
    assert isinstance(opp, E._BareNetPrefix)
    assert not isinstance(opp, E._MarginalizedHandoff)      # still BARE
    assert opp.mcts.fair_chance is False                    # still CLAIRVOYANT
    assert opp.mcts.fair_isolate is False
    assert opp.mcts.simulations == E.BARE_NET_SIMS == 200
    assert opp.mcts.c_puct == E.BARE_NET_CPUCT == 3.0
    assert _leaf_hash(opp.leaf_cfg) == ANCHOR_HASH          # still the ANCHOR leaf
    # the encoder still comes from the OPPONENT's own rep
    assert opp.mcts.game.get_input_channels() == rep["n_input_channels"]
    assert opp.mcts.game.get_scalar_feature_size() == rep["n_scalar_features"]


def test_orch_transport_reproduces_the_cpu_agents_move_exactly():
    """THE wiring proof. Same weights, same seed, same board — one agent evaluating
    through the local factory, one through the remote (handles) factory whose 'server'
    is the same CPU net. The chosen action must match EXACTLY, and the remote path must
    actually have been used (n_requests > 0, so a silent local fallback cannot pass).

    This is what makes the GPU number interpretable: it isolates the transport wiring
    from the CPU-vs-GPU float question, which is measured separately by
    scripts/classical_search/bare_net_gpu_divergence.py."""
    net, rep = _random_anchor_net(seed=3)
    leaf = E._bare_net_leaf_cfg()
    cpu = E._make_bare_net_opponent(net, rep, seed=5, leaf_cfg=leaf)
    h = _LoopbackHandles(net, Game())
    orch = E._make_bare_net_opponent(None, rep, seed=5, leaf_cfg=leaf, handles=h)
    cpu.mcts.simulations = orch.mcts.simulations = 24       # keep the unit test cheap

    game = Game(enable_legal_moves_cache=True)
    board = _board_with_a_real_choice(game)
    true_deck = [t.description for t in board.state.deck]
    a_cpu = cpu.move(board)
    a_orch = orch.move(board)
    assert h.n_requests > 0, "the remote evaluator was never called — silent fallback"
    assert a_cpu == a_orch, (
        f"orch transport changed the move ({a_cpu} -> {a_orch}) with IDENTICAL "
        "arithmetic; that is a wiring bug, not float noise")
    # and it is still clairvoyant + non-mutating
    assert [t.description for t in board.state.deck] == true_deck


def test_worker_init_wires_the_bare_net_orch_handles(monkeypatch):
    """`_worker_init` must take the SHM path when --opp-orch-shm-name is set (and size
    the slots from the OPPONENT's own rep, not a hardcoded 78/12), and must NOT load a
    per-worker CPU net in that case."""
    _net, rep = _random_anchor_net()
    seen = {}

    def fake_connect(name, wid, n_scalar, n_ch):
        seen.update(name=name, wid=wid, n_scalar=n_scalar, n_ch=n_ch)
        return "HANDLES"

    import carcassonne_ai.shm_eval_handles as SH
    monkeypatch.setattr(SH, "connect_shm", fake_connect)
    monkeypatch.setattr(E, "_load_net_rep",
                        lambda *a, **k: pytest.fail("orch path must not load a CPU net"))

    class _Q:
        def get(self):
            return 7

    E._W.clear()
    E._worker_init("fair", {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
                            "final_select": "visits", "value_norm": 15.0},
                   sims=8, k_dets=2, exact_k=2, rung_sims=800, shared_claim=False,
                   claim_host="h", claim_stale=1, opponent="bare-net",
                   opp_net_ckpt="/x.pt", opp_rep=rep, opp_orch_shm_name="s",
                   id_q=_Q())
    assert E._W["opp_handles"] == "HANDLES"
    assert E._W["opp_net"] is None
    assert seen == {"name": "s", "wid": 7,
                    "n_scalar": rep["n_scalar_features"],
                    "n_ch": rep["n_input_channels"]}
    E._W.clear()


@pytest.mark.skipif(not _cuda_present(),
                    reason="no GPU on this box (nvidia-smi -L found none)")
@pytest.mark.skipif(not ORCH_BIN.is_file(),
                    reason=f"carc-orch not built at {ORCH_BIN} "
                           "(cargo build --release --manifest-path rust/carc-orch/Cargo.toml)")
def test_carc_orch_really_serves_the_bare_net_opponent_from_the_GPU(tmp_path):
    """END-TO-END on the real path: export a random anchor-rep net, launch carc-orch on
    CUDA, and drive a bare-net opponent through it.

    Proves the thing a mock cannot: the net is ON THE GPU (nvidia-smi memory delta) and
    a silent CPU fallback did not happen. Slow (~30-60s: TorchScript export + parity
    gate + server warmup)."""
    import torch
    import bare_net_gpu_divergence as D          # server lifecycle helpers
    from carcassonne_ai.shm_eval_handles import connect_shm

    from carcassonne_ai.network import DEFAULT_BLOCKS, DEFAULT_FILTERS

    net, rep = _random_anchor_net(seed=11)      # built at the module defaults
    ckpt = tmp_path / "anchor_rand.pt"
    torch.save({"model_state": net.state_dict(),
                "n_filters": DEFAULT_FILTERS, "n_blocks": DEFAULT_BLOCKS,
                "n_input_channels": rep["n_input_channels"],
                "n_scalar_features": rep["n_scalar_features"],
                "sighted": rep["sighted"],
                "value_global_pool": rep["value_global_pool"]}, ckpt)

    shm = f"bntest{os.getpid()}"
    before = D._gpu_mem_mib()
    proc, log = D._start_server(str(ckpt), rep, shm, workers=1, max_batch=8)
    try:
        after = D._gpu_mem_mib()
        assert before is not None and after is not None, "nvidia-smi gave no reading"
        assert after - before > 0, (
            f"carc-orch allocated NO GPU memory ({before} -> {after} MiB) — it is "
            "almost certainly running on the CPU. A silent CPU fallback is the worst "
            "outcome here: it still 'works', at 1/Nx the speed and different floats.")
        assert "cuda" in log.read_text().lower() or after - before > 0

        handles = connect_shm(shm, 0, int(rep["n_scalar_features"]),
                              int(rep["n_input_channels"]))
        opp = E._make_bare_net_opponent(None, rep, seed=1,
                                        leaf_cfg=E._bare_net_leaf_cfg(), handles=handles)
        opp.mcts.simulations = 16                 # wiring proof, not a strength check
        assert opp.mcts.fair_chance is False
        assert _leaf_hash(opp.leaf_cfg) == ANCHOR_HASH

        game = Game(enable_legal_moves_cache=True)
        board = _board_with_a_real_choice(game)
        act = opp.move(board)
        assert game.get_valid_moves(board)[act], "GPU-served opponent returned an illegal action"
    finally:
        proc.send_signal(__import__("signal").SIGTERM)
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        for f in [pathlib.Path(f"/dev/shm/carc_{shm}"),
                  *pathlib.Path("/dev/shm").glob(f"sem.carc_{shm}_*")]:
            try:
                os.remove(f)
            except OSError:
                pass
