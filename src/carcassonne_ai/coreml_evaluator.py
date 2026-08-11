"""CoreML / Apple-Neural-Engine backend for the policy-only net forward.

WHY THIS EXISTS — the reopen condition of the CL-067 equal-wall-clock gate
(``measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md`` §6):

> REOPEN the distilled-net line for deploy when the target device's measured
> ``r = forward_ms / search_ms_per_sim`` is <= ~1.5.

The desktop CUDA batch-1 path measures r ~ 3.0 and the gate fired branch C (WASH).
The ONLY forward path measured below the bar is Apple's ANE: **0.42 ms batch-1 fp16,
r ~ 0.73**, projecting **+11 to +15 elo at equal wall clock**. That projection was
assembled from two *separately* measured numbers (M5 search s/move and ANE forward ms)
and the gate says so explicitly — the honest next test is ONE cell on the M5 with a
real agent whose forwards go through the ANE. This module is the forward path that
cell needs; it plays no other role and changes nothing by default.

WHAT IT IS: a drop-in replacement for
``evaluators.make_single_evaluator_policy_only`` — same *return contract*
(``(priors[A], 0.0)``, the 0.0 being the policy-only sentinel the caller MUST
override), same masked-softmax semantics, same per-call work — but the forward is a
``coremltools`` ``MLModel.predict`` on ``CPU_AND_NE`` instead of a torch forward.
It is consumed by ``heuristic_prior_mcts.make_fair_net_prior_evaluator``, which pairs
these net priors with the FROZEN champion v2.9 leaf value.

--------------------------------------------------------------------------------
DESIGN DECISION 1 — the mask is applied on the HOST, in float32, NOT baked into the
CoreML graph.
--------------------------------------------------------------------------------
The exported ``.mlpackage`` emits raw policy LOGITS. The ``masked_fill(-inf) ->
softmax`` that ``network.policy_softmax_with_mask`` performs is reproduced here in
numpy float32 (``masked_softmax_np``). Four reasons, in order of weight:

1. **fp16 faithfulness.** The ANE computes in fp16. A ``-inf`` sentinel inside an
   fp16 graph is a hazard: fp16 ``-inf`` is representable but accelerator softmax
   kernels routinely clamp/flush non-finite inputs and subtract a max computed in
   reduced precision, so two near-tied LEGAL logits could come back with a different
   ordering than torch produced from the same weights. Keeping the graph mask-free
   means the ONLY fp16 effect is the rounding of the logits themselves — which is
   exactly the quantity ``verify_coreml_evaluator.py`` measures and reports. Bake the
   mask in and that error budget becomes uninterpretable: you can no longer tell a
   bad forward from a bad softmax.
2. **Op coverage / on-NPU residency.** ``ane_coverage_probe.py`` exists because CoreML
   op placement is fragile — one unsupported op splits the graph and the "100% on-NPU"
   result evaporates along with the 0.42 ms. A mask input would add a third (dynamic,
   boolean-ish) input plus ``select``/``fill`` ops to an otherwise pure conv+FC graph
   that is already *measured* 100% on-NPU. That is a gratuitous risk to the one
   property the whole cell depends on.
3. **Transport.** Baking it in ships 2511 extra floats INTO the model every call, on
   top of the 2511 that come out. The host-side mask is a numpy view of an array the
   caller already has (``game.get_valid_moves``) and costs no transfer at all.
4. **Semantics preserved by construction.** Given identical float32 logits,
   ``masked_softmax_np`` performs the same three steps as ``F.softmax`` on
   ``masked_fill(-inf)`` — subtract the row max, exponentiate, normalise — so this is
   the same algorithm, not an approximation of it. It is not bit-identical (the
   reduction order differs; see ``masked_softmax_np``), and the measured gap is 2.4e-7
   max-abs with 100% argmax/top-5 agreement. ``tests/test_coreml_evaluator.py`` pins
   both facts against torch.

--------------------------------------------------------------------------------
DESIGN DECISION 2 — the model is injected, not loaded, by the evaluator factory.
--------------------------------------------------------------------------------
``make_coreml_policy_evaluator`` takes an already-constructed model OBJECT and only
ever calls ``.predict(dict) -> dict`` on it. The coremltools import lives in
``load_coreml_model``. That split is what lets the contract tests run on Linux (no
CoreML runtime exists off macOS) against a mocked model, so the masking/shape/argmax
contract is covered by CI on the box that actually has CI.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np

from .game_wrapper import Board, Game

# Default tensor names. `export_cl067_coreml.py` writes exactly these; they are also
# what `bench_ane_forward.py` has always used, so an .mlpackage produced by either
# tool loads here without argument fiddling.
BOARD_INPUT = "board"
SCALARS_INPUT = "scalars"
POLICY_OUTPUT = "policy_logits"

# The compute unit the reopen condition was measured on. CPU_AND_NE deliberately
# EXCLUDES the GPU: with ALL, CoreML is free to place the graph on the GPU, which is
# a different (and on the M5, slower for batch-1) device than the 0.42 ms measurement.
DEFAULT_COMPUTE_UNITS = "CPU_AND_NE"

# The net-forward backends a fair-net-prior agent can be built on. Canonical here
# (this module has no dependency beyond game_wrapper); re-exported by
# `champion_factory` so harnesses have one public seam to import from.
NET_BACKENDS = ("torch", "coreml")
DEFAULT_NET_BACKEND = "torch"


def resolve_net_backend(net_backend: str | None) -> str:
    """None -> "torch". Anything else must be a known backend, or RAISE.

    None is the pre-feature behaviour and is what every existing caller passes
    implicitly, so the default path is byte-identical. A typo ("coreML", "ane") must
    NOT fall back to torch: a cell that believes it measured the Neural Engine but
    quietly ran a torch forward would report the r ratio of the wrong device, which is
    precisely the mistake the equal-wall-clock gate was built to prevent.
    """
    if net_backend is None:
        return DEFAULT_NET_BACKEND
    if net_backend not in NET_BACKENDS:
        raise ValueError(
            f"net_backend must be one of {NET_BACKENDS} (or None == "
            f"{DEFAULT_NET_BACKEND!r}); got {net_backend!r}")
    return net_backend


def masked_softmax_np(logits: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """float32 numpy twin of ``network.policy_softmax_with_mask`` for ONE row.

    Mirrors ``F.softmax(logits.masked_fill(~mask, -inf), dim=-1)`` step for step:
    illegal actions go to ``-inf`` BEFORE the softmax (not zeroed after it, which is a
    different distribution unless you renormalise, and is the classic way to get priors
    that are subtly wrong on positions with many illegal moves).

    Degenerate rows are NOT special-cased: an all-illegal mask yields ``nan``, exactly
    as torch does, because silently returning uniform-over-illegal would hand MCTS a
    legal-looking prior over moves it cannot play. Callers never see this in practice —
    NeuralMCTS only evaluates non-terminal boards, which have >= 1 legal action.

    NOT bit-identical to torch, and deliberately so. Same three steps, but the
    normalising sum is accumulated in float64 before the float32 divide, where torch
    reduces in float32 with a vectorised (SIMD-width-dependent) order. Two consequences,
    both wanted:

    * our result is reproducible across numpy builds and machines, which a float32
      reduction is not — and this evaluator's whole job is to produce a number that a
      later reader can reproduce;
    * the residual disagreement with torch is a few ULP. MEASURED over 500 random
      2511-wide rows at ~5% legal: max abs diff **2.4e-7**, bit-identical 0/500,
      **argmax and top-5 agreement 100%**.

    That 2.4e-7 is ~4 orders of magnitude below the fp16 forward error the ANE itself
    introduces, so it is never the term that decides anything — but it IS why
    ``verify_coreml_evaluator.py`` reports argmax/top-5 agreement alongside max-abs
    rather than demanding equality.
    """
    logits = np.asarray(logits, dtype=np.float32).reshape(-1)
    mask = np.asarray(valid_mask).reshape(-1).astype(bool)
    if logits.shape != mask.shape:
        raise ValueError(
            f"masked_softmax_np: logits {logits.shape} vs mask {mask.shape} — the "
            "CoreML model's action space does not match the game's. Re-export the "
            "model from the checkpoint of record.")
    with np.errstate(invalid="ignore"):
        z = np.where(mask, logits, np.float32(-np.inf))
        z = z - z.max()
        e = np.exp(z, dtype=np.float32)
        return (e / e.sum(dtype=np.float64)).astype(np.float32)


def load_coreml_model(path, *, compute_units: str = DEFAULT_COMPUTE_UNITS):
    """Load a compiled ``.mlpackage``. macOS only — importing coremltools works
    anywhere, but ``predict`` is a Darwin-only code path.

    ``compute_units`` is bound at LOAD time and is part of the measurement: a model
    loaded ALL is not the model the 0.42 ms / r=0.73 row describes. The resolved unit
    is stamped on the returned object as ``carc_compute_units`` so the harness manifest
    records what actually ran rather than what was asked for.
    """
    import coremltools as ct  # noqa: PLC0415 — optional, macOS-only dependency

    try:
        unit = getattr(ct.ComputeUnit, compute_units)
    except AttributeError as exc:
        raise ValueError(
            f"load_coreml_model: unknown compute_units {compute_units!r}; "
            f"expected one of {[u.name for u in ct.ComputeUnit]}") from exc

    model = ct.models.MLModel(str(path), compute_units=unit)
    model.carc_compute_units = compute_units
    model.carc_path = str(path)
    model.carc_input_shapes = _spec_input_shapes(model)
    return model


def _spec_input_shapes(model) -> dict:
    """Best-effort ``{input_name: [dims]}`` off the protobuf spec.

    Used to fail loud on a rep mismatch (an 81ch model fed a 78ch encode produces
    plausible-looking garbage rather than an error). Best-effort because the spec
    layout differs across coremltools majors and a missing shape must not block a
    run that is otherwise correct — the caller treats ``{}`` as "cannot check".
    """
    try:
        shapes = {}
        for inp in model.get_spec().description.input:
            dims = list(getattr(inp.type, "multiArrayType").shape)
            if dims:
                shapes[inp.name] = [int(d) for d in dims]
        return shapes
    except Exception:  # noqa: BLE001 — provenance nicety, never load-blocking
        return {}


def assert_coreml_rep(model, rep: dict) -> None:
    """Fail loud when the model's input shape contradicts the resolved encode rep.

    The torch path gets this for free from ``_validate_fair_net_prior_dims`` reading
    ``net.stem[0].in_channels``. A CoreML model has no parameters to introspect, so we
    read the declared input shape instead. Silence (``{}``) is tolerated; a CONTRADICTION
    is not.
    """
    shapes = getattr(model, "carc_input_shapes", None) or {}
    board = shapes.get(BOARD_INPUT)
    scalars = shapes.get(SCALARS_INPUT)
    want_ch = int(rep["n_input_channels"])
    want_sc = int(rep["n_scalar_features"])
    if board is not None and len(board) == 4 and int(board[1]) != want_ch:
        raise ValueError(
            f"CoreML model expects {board[1]} board channels but the resolved rep is "
            f"{want_ch}ch (sighted={rep['sighted']}). The .mlpackage was exported from a "
            "different-rep checkpoint; re-export from the checkpoint of record.")
    if scalars is not None and len(scalars) == 2 and int(scalars[1]) != want_sc:
        raise ValueError(
            f"CoreML model expects {scalars[1]} scalar features but the resolved rep is "
            f"{want_sc}. The .mlpackage was exported from a different-rep checkpoint.")


def _resolve_output_name(out: dict, wanted: str | None) -> str:
    """Pick the logits key out of a predict() result, once, then cache it upstream.

    coremltools preserves the traced output name when it can, but a renamed or
    positionally-named output ("var_123") is common enough that hard-coding one name
    turns a working model into a KeyError. Preference order: the caller's explicit
    name -> the documented POLICY_OUTPUT -> the sole output -> fail with the actual
    keys in the message.
    """
    if wanted is not None:
        if wanted not in out:
            raise KeyError(
                f"CoreML model has no output {wanted!r}; it returned {sorted(out)}")
        return wanted
    if POLICY_OUTPUT in out:
        return POLICY_OUTPUT
    if len(out) == 1:
        return next(iter(out))
    raise KeyError(
        f"CoreML model returned {sorted(out)} — cannot tell which is the policy "
        f"logits. Pass logits_output= explicitly, or re-export with "
        f"export_cl067_coreml.py (which names it {POLICY_OUTPUT!r}).")


def make_coreml_policy_evaluator(
    model: Any,
    game: Game,
    *,
    board_input: str = BOARD_INPUT,
    scalars_input: str = SCALARS_INPUT,
    logits_output: str | None = None,
) -> Callable[[Board], tuple[np.ndarray, float]]:
    """CoreML/ANE twin of ``evaluators.make_single_evaluator_policy_only``.

    Returns ``Callable[[Board], (priors[A], 0.0)]`` — the SAME contract, so it drops
    into any slot that takes the torch policy-only evaluator. The 0.0 is the
    policy-only sentinel: the value head is not exported and is never computed, and the
    caller (``make_fair_net_prior_evaluator``) overrides it with the frozen v2.9 leaf.

    ``model`` is duck-typed on ``.predict(dict) -> dict`` and nothing else, which is
    what makes the contract testable without a CoreML runtime.

    The torch factory's ``device`` / ``use_fp16`` arguments have NO analogue here and
    are deliberately absent rather than accepted-and-ignored: for CoreML both are baked
    into the artifact at CONVERT time (``compute_precision``) and at LOAD time
    (``compute_units``), so a runtime knob would be a lie. Precision/placement
    provenance travels on the model object and is surfaced as evaluator attributes.
    """
    # Resolved on the FIRST predict, then cached — including when the caller named the
    # output explicitly, so a wrong name fails with the model's actual keys in the
    # message instead of a bare KeyError.
    out_name: str | None = None
    counters = {"n_predict": 0}

    def evaluator(board: Board) -> tuple[np.ndarray, float]:
        nonlocal out_name
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        feed = {
            board_input: np.ascontiguousarray(obs[None], dtype=np.float32),
            scalars_input: np.ascontiguousarray(scalars[None], dtype=np.float32),
        }
        out = model.predict(feed)
        if out_name is None:
            out_name = _resolve_output_name(out, logits_output)
        counters["n_predict"] += 1
        # The mask is fetched AFTER the forward for the same reason the torch path
        # does it there: predict() is the long pole, and the legal-move cache lookup
        # is free. Order has no semantic effect.
        mask = game.get_valid_moves(board)
        return masked_softmax_np(np.asarray(out[out_name]), mask), 0.0

    evaluator.policy_only = True          # value head NOT exported (sentinel 0.0)
    evaluator.backend = "coreml"
    evaluator.counters = counters
    evaluator.compute_units = getattr(model, "carc_compute_units", None)
    evaluator.model_path = getattr(model, "carc_path", None)
    evaluator.mask_applied = "host_numpy_float32"   # see DESIGN DECISION 1
    return evaluator
