"""CoreML / ANE net-forward backend contracts — runnable WITHOUT macOS.

The CoreML *runtime* only exists on Darwin, so the on-device fidelity gate is
``scripts/m5_bench/verify_coreml_evaluator.py`` (>=60 real positions, run on the Air).
What CAN be pinned on the CI box is everything between the encoder and the runtime:
shapes, tensor naming, output resolution, the mask semantics, the backend switch, and
the manifest stamp. Those are the parts a human would get wrong; the runtime is the
part Apple gets wrong. This file covers the first set by injecting a mock model that
satisfies the ONLY contract ``make_coreml_policy_evaluator`` requires of it —
``.predict(dict) -> dict``.

The load-bearing test is `test_coreml_evaluator_matches_torch_policy_only`: the mock is
backed by the SAME torch net the reference evaluator uses, so any disagreement is a bug
in this module's encode/feed/mask/softmax pipeline rather than in the accelerator. On
the Air the same comparison runs with a real .mlpackage on the other side, and the only
new term is fp16.

Leaf env pinned to the production v2.9 Bmild_cap8 substrate BEFORE importing
carcassonne_ai (mirrors tests/test_c_cheap_scaffold.py)."""
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

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from carcassonne_ai import champion_factory
from carcassonne_ai.coreml_evaluator import (
    BOARD_INPUT,
    DEFAULT_NET_BACKEND,
    NET_BACKENDS,
    POLICY_OUTPUT,
    SCALARS_INPUT,
    assert_coreml_rep,
    make_coreml_policy_evaluator,
    masked_softmax_np,
    resolve_net_backend,
)
from carcassonne_ai.evaluators import make_single_evaluator_policy_only
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.heuristic_prior_mcts import (
    HeuristicPriorConfig,
    make_fair_net_prior_batch_evaluator,
    make_fair_net_prior_evaluator,
)
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.sighted_planes import N_BAG, N_FARM_PLANES
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

MILD_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
V28 = dc.replace(DEFAULT_CONFIG, meeple_k=2.0)
BMILD_CAP8 = dc.replace(V28, v29_meeple_curve=MILD_CURVE, bonus_cap=8.0,
                        opp_bonus_cap=8.0)

SIGHTED_CH = 78 + N_FARM_PLANES        # 81 — the CL-067 iter_03 rep
SIGHTED_SCALARS = 10 + N_BAG           # 42


def _cfg():
    return HeuristicPriorConfig(leaf_cfg=BMILD_CAP8, c_puct=1.5, tau_p=5.0)


def _sighted_net(seed=0):
    torch.manual_seed(seed)
    net = CarcassonneNet(n_input_channels=SIGHTED_CH,
                         n_scalar_features=SIGHTED_SCALARS,
                         value_global_pool=True)
    net.eval()
    return net


def _midgame_boards(n=4, plies=40):
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


class FakeMLModel:
    """Mock CoreML model backed by a real torch net.

    Stands in for the .mlpackage: same I/O names, same shapes, same numbers (fp32 —
    the accelerator's fp16 is exactly the term this mock CANNOT model, which is why
    the Air still has to run verify_coreml_evaluator.py). It also ASSERTS the feed it
    is handed, so a wrong dtype/shape/name fails here rather than as a confusing
    CoreML error 400 lines into a real run.
    """

    def __init__(self, net, *, out_name=POLICY_OUTPUT, extra_outputs=False):
        self.net = net
        self.out_name = out_name
        self.extra_outputs = extra_outputs
        self.n_calls = 0
        self.last_feed = None
        self.carc_compute_units = "CPU_AND_NE"
        self.carc_path = "/fake/cl067.mlpackage"
        self.carc_input_shapes = {
            BOARD_INPUT: [1, SIGHTED_CH, 25, 25],
            SCALARS_INPUT: [1, SIGHTED_SCALARS],
        }

    def predict(self, feed):
        assert set(feed) == {BOARD_INPUT, SCALARS_INPUT}, sorted(feed)
        b, s = feed[BOARD_INPUT], feed[SCALARS_INPUT]
        assert b.dtype == np.float32 and s.dtype == np.float32
        assert b.shape == (1, SIGHTED_CH, 25, 25), b.shape
        assert s.shape == (1, SIGHTED_SCALARS), s.shape
        assert b.flags["C_CONTIGUOUS"] and s.flags["C_CONTIGUOUS"]
        self.n_calls += 1
        self.last_feed = feed
        with torch.no_grad():
            logits = self.net.forward_policy_only(
                torch.from_numpy(b), torch.from_numpy(s))
        out = {self.out_name: logits.numpy()}
        if self.extra_outputs:
            out["value"] = np.zeros((1, 1), dtype=np.float32)
        return out


# --------------------------------------------------------------------------- #
# 1. masked_softmax_np == network.policy_softmax_with_mask (the wire contract)  #
# --------------------------------------------------------------------------- #
def test_masked_softmax_matches_torch():
    """Same algorithm as torch's masked softmax, to a few ULP, with EXACT ordering.

    Not bit-identical by design (float64 accumulation of the normaliser, for
    cross-machine reproducibility — see masked_softmax_np). What must hold exactly is
    everything MCTS actually consumes: illegal actions get literally zero, the
    distribution normalises, and the argmax / top-5 ORDER is unchanged.
    """
    rng = np.random.default_rng(0)
    n_actions = 2511
    worst = 0.0
    for _ in range(200):
        logits = (rng.normal(size=n_actions) * 3).astype(np.float32)
        mask = rng.random(n_actions) < 0.05
        mask[0] = True                       # never an all-illegal row
        got = masked_softmax_np(logits, mask)
        ref = CarcassonneNet.policy_softmax_with_mask(
            None, torch.from_numpy(logits)[None],
            torch.from_numpy(mask)[None])[0].numpy()

        assert got.shape == (n_actions,) and got.dtype == np.float32
        assert float(got[~mask].sum()) == 0.0, "illegal action got nonzero prior"
        assert abs(float(got.sum()) - 1.0) < 1e-5
        assert int(got.argmax()) == int(ref.argmax())
        assert (np.argsort(-got)[:5] == np.argsort(-ref)[:5]).all()
        worst = max(worst, float(np.abs(got - ref).max()))
    # Measured 2.4e-7 over 500 rows; 1e-6 is the documented tolerance.
    assert worst < 1e-6, f"max abs diff vs torch {worst:.3e}"


def test_masked_softmax_rejects_shape_mismatch():
    """A model exported at the wrong action size must fail loudly, not broadcast."""
    with pytest.raises(ValueError, match="does not match the game"):
        masked_softmax_np(np.zeros(10, np.float32), np.ones(11, bool))


# --------------------------------------------------------------------------- #
# 2. The evaluator reproduces the torch policy-only evaluator, end to end.      #
# --------------------------------------------------------------------------- #
def test_coreml_evaluator_matches_torch_policy_only():
    """THE contract test: same net behind both backends => same priors.

    Covers encode -> feed naming/shape/dtype -> output resolution -> mask -> softmax.
    Anything the CoreML path does differently from the torch path shows up here.
    """
    net = _sighted_net()
    sighted = Game(sighted=True, enable_legal_moves_cache=True)
    boards = _midgame_boards()
    assert len(boards) >= 3, "need >=3 mid-game boards"

    ref_ev = make_single_evaluator_policy_only(net, torch.device("cpu"), sighted)
    model = FakeMLModel(net)
    cml_ev = make_coreml_policy_evaluator(model, sighted)

    assert cml_ev.policy_only is True
    assert cml_ev.backend == "coreml"
    assert cml_ev.mask_applied == "host_numpy_float32"
    assert cml_ev.compute_units == "CPU_AND_NE"

    multi_legal = 0
    for _game, board in boards:
        p_ref, v_ref = ref_ev(board)
        p_cml, v_cml = cml_ev(board)

        assert p_cml.shape == p_ref.shape and p_cml.dtype == np.float32
        assert v_cml == 0.0 == v_ref, "policy-only sentinel must stay 0.0"
        mask = sighted.get_valid_moves(board)
        assert float(p_cml[~mask.astype(bool)].sum()) == 0.0
        assert abs(float(p_cml.sum()) - 1.0) < 1e-5
        assert np.abs(p_cml - p_ref).max() < 1e-6
        assert int(p_cml.argmax()) == int(p_ref.argmax())
        k = min(5, int(mask.sum()))
        assert (np.argsort(-p_cml)[:k] == np.argsort(-p_ref)[:k]).all()
        if int(mask.sum()) > 5:
            multi_legal += 1

    assert multi_legal >= 1, "no board with >5 legal moves — top-5 test was vacuous"
    assert model.n_calls == len(boards)
    assert cml_ev.counters["n_predict"] == len(boards)


def test_output_name_resolution():
    """A single unnamed output resolves; two ambiguous outputs must RAISE.

    coremltools does not always preserve the traced output name, so guessing is
    required — but guessing between two candidates would silently feed MCTS the value
    head as if it were the policy.
    """
    net = _sighted_net()
    sighted = Game(sighted=True, enable_legal_moves_cache=True)
    _game, board = _midgame_boards(n=1)[0]

    renamed = make_coreml_policy_evaluator(FakeMLModel(net, out_name="var_42"), sighted)
    assert renamed(board)[0].shape[0] > 0          # sole output -> resolved

    ambiguous = make_coreml_policy_evaluator(
        FakeMLModel(net, out_name="var_42", extra_outputs=True), sighted)
    with pytest.raises(KeyError, match="cannot tell which is the policy"):
        ambiguous(board)

    explicit = make_coreml_policy_evaluator(
        FakeMLModel(net, out_name="var_42", extra_outputs=True), sighted,
        logits_output="var_42")
    assert explicit(board)[0].shape[0] > 0

    wrong = make_coreml_policy_evaluator(FakeMLModel(net), sighted,
                                         logits_output="nope")
    with pytest.raises(KeyError, match="no output"):
        wrong(board)


def test_assert_coreml_rep_catches_rep_mismatch():
    """The torch path validates channels off net.parameters; CoreML has none, so the
    declared input shape is the guard. A 78ch model fed an 81ch encode produces
    plausible garbage, which is the worst possible failure for a measurement cell."""
    model = FakeMLModel(_sighted_net())
    good = {"sighted": True, "n_input_channels": SIGHTED_CH,
            "n_scalar_features": SIGHTED_SCALARS}
    assert_coreml_rep(model, good)              # no raise

    with pytest.raises(ValueError, match="board channels"):
        assert_coreml_rep(model, {**good, "n_input_channels": 78})
    with pytest.raises(ValueError, match="scalar features"):
        assert_coreml_rep(model, {**good, "n_scalar_features": 10})

    model.carc_input_shapes = {}                # unknowable -> tolerated, not fatal
    assert_coreml_rep(model, {**good, "n_input_channels": 78})


# --------------------------------------------------------------------------- #
# 3. The backend switch.                                                        #
# --------------------------------------------------------------------------- #
def test_resolve_net_backend():
    assert resolve_net_backend(None) == DEFAULT_NET_BACKEND == "torch"
    assert set(NET_BACKENDS) == {"torch", "coreml"}
    for name in NET_BACKENDS:
        assert resolve_net_backend(name) == name
    # A typo must NOT quietly fall back to torch — that is how a cell reports the r
    # ratio of a device it never ran on.
    for bad in ("coreML", "ane", "ANE", "cuda", ""):
        with pytest.raises(ValueError, match="net_backend must be one of"):
            resolve_net_backend(bad)
    # champion_factory is the public seam and must re-export the same objects.
    assert champion_factory.resolve_net_backend is resolve_net_backend
    assert champion_factory.NET_BACKENDS == NET_BACKENDS


def test_fair_net_prior_coreml_backend_matches_torch_backend():
    """The full fair-net-prior evaluator on both backends: priors agree, and the VALUE
    is BYTE-IDENTICAL because the backend cannot reach it (the value is the frozen
    champion v2.9 leaf, computed in-process by the same Cython float leaf)."""
    net = _sighted_net()
    boards = _midgame_boards()
    assert len(boards) >= 3

    torch_ev = make_fair_net_prior_evaluator(_cfg(), net=net)
    model = FakeMLModel(net)
    cml_ev = make_fair_net_prior_evaluator(
        _cfg(), coreml_model=model, net_backend="coreml")

    assert torch_ev.net_backend == "torch"
    assert cml_ev.net_backend == "coreml"
    assert cml_ev.priors_source == "net_policy_head"
    assert cml_ev.value_source == "frozen_champion_v29_leaf"
    assert "CoreML" in cml_ev.value_transport and "CPU_AND_NE" in cml_ev.value_transport
    assert cml_ev.rep["n_input_channels"] == SIGHTED_CH
    assert cml_ev.coreml.counters["n_predict"] == 0

    for _game, board in boards:
        p_t, v_t = torch_ev(board)
        p_c, v_c = cml_ev(board)
        assert v_c == v_t, "the backend must not touch the frozen leaf value"
        assert np.abs(p_c - p_t).max() < 1e-6
        assert int(p_c.argmax()) == int(p_t.argmax())
    assert cml_ev.coreml.counters["n_predict"] == len(boards)


def test_coreml_backend_guards():
    """Every way to ask for the ANE path wrongly must raise, not degrade silently."""
    net = _sighted_net()
    model = FakeMLModel(net)

    # A model supplied but the backend left at torch: the run would measure CUDA/CPU
    # while its manifest implied the ANE.
    with pytest.raises(ValueError, match="net_backend='coreml' to use it"):
        make_fair_net_prior_evaluator(_cfg(), net=net, coreml_model=model)

    # Backend selected but no model.
    with pytest.raises(ValueError, match="needs a `coreml_model`"):
        make_fair_net_prior_evaluator(_cfg(), net=net, net_backend="coreml")

    # No transport at all.
    with pytest.raises(ValueError, match="needs a CPU `net`"):
        make_fair_net_prior_evaluator(_cfg())

    # Batching is refused: the artifact is fixed batch-1, so a "batch" evaluator would
    # buy no transport win while batch_size>1 still engages virtual loss.
    with pytest.raises(ValueError, match="does not support a batch evaluator"):
        make_fair_net_prior_batch_evaluator(
            _cfg(), coreml_model=model, net_backend="coreml")
    with pytest.raises(ValueError, match="does not support a batch evaluator"):
        make_fair_net_prior_batch_evaluator(_cfg(), net=net, coreml_model=model)


def test_default_torch_path_unchanged():
    """Nothing added here may perturb the default. The net-prior evaluator built the
    old way must still produce priors byte-identical to the torch policy-only
    evaluator it delegates to."""
    net = _sighted_net()
    sighted = Game(sighted=True, enable_legal_moves_cache=True)
    ref_ev = make_single_evaluator_policy_only(net, torch.device("cpu"), sighted)
    ev = make_fair_net_prior_evaluator(_cfg(), net=net)
    for _game, board in _midgame_boards(n=3):
        assert np.array_equal(ev(board)[0], ref_ev(board)[0])


# --------------------------------------------------------------------------- #
# 4. champion_factory wiring + the manifest stamp.                              #
# --------------------------------------------------------------------------- #
def test_factory_stamps_manifest_only_when_backend_is_set():
    """The exact_budget / parallel_workers convention: unset == no key at all, so a
    candidate built the old way keeps a byte-identical manifest and no hash drifts."""
    net = _sighted_net()
    game = Game(enable_legal_moves_cache=True)

    plain = champion_factory.build_fair_netprior_candidate(
        game, cfg=_cfg(), net=net, sims=8, k_dets=1, seed=0)
    assert plain.net_backend == "torch"
    assert not hasattr(plain, "manifest"), "unset net_backend must stamp nothing"
    assert plain.netprior_evaluator.priors_source == "net_policy_head"

    stamped = champion_factory.build_fair_netprior_candidate(
        game, cfg=_cfg(), coreml_model=FakeMLModel(net), net_backend="coreml",
        sims=8, k_dets=1, seed=0)
    assert stamped.net_backend == "coreml"
    block = stamped.manifest["net_backend"]
    assert block["backend"] == "coreml"
    assert block["default"] == "torch"
    assert block["compute_units"] == "CPU_AND_NE"
    assert block["model_path"] == "/fake/cl067.mlpackage"
    # The stamp must WARN that this is not behaviour-identical (unlike k-parallel):
    # fp16 perturbs the priors, so the agent's strength claim is its own.
    assert "NOT behaviour-identical" in block["note"]

    # An explicit "torch" is still a deliberate choice and is therefore recorded.
    explicit = champion_factory.build_fair_netprior_candidate(
        game, cfg=_cfg(), net=net, net_backend="torch", sims=8, k_dets=1, seed=0)
    assert explicit.manifest["net_backend"]["backend"] == "torch"


def test_factory_block_shape_matches_house_style():
    """net_backend_manifest_block carries the same keys the sibling blocks do, so a
    manifest reader does not need a special case."""
    block = champion_factory.net_backend_manifest_block(
        "coreml", model_path="/x.mlpackage", model_sha256="deadbeef",
        compute_units="CPU_AND_NE")
    for key in ("backend", "default", "source", "scope", "note", "mask",
                "model_path", "model_sha256", "compute_units"):
        assert key in block, key
    assert block["source"] == "kwarg"
    assert block["model_sha256"] == "deadbeef"
