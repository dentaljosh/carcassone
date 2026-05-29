"""Network-evaluator factories for NeuralMCTS callers.

Two flavors:

- `make_single_evaluator`: `Callable[[Board], (priors[A], value)]` — one GPU
  forward per board. Use with `NeuralMCTS(batch_size=1, ...)` (the default
  serial path) and pass as `evaluator=...`.

- `make_batch_evaluator`: `Callable[[list[Board]], (priors[B,A], values[B])]`
  — one GPU forward per K boards. Use with `NeuralMCTS(batch_size=K, ...)`
  and pass as `batch_evaluator=...` to enable the virtual-loss / batched-eval
  path.

Both canonicalize each board from its own `current_player`'s perspective —
this matches NeuralMCTS's expectation that `(priors, value)` come back from
the board's player-to-move POV. The mask is applied via
`net.policy_softmax_with_mask` so invalid actions get zero probability.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import torch

from .game_wrapper import Board, Game
from .network import CarcassonneNet


def _autocast_ctx(device: torch.device, use_fp16: bool):
    """Return an autocast context manager that's a no-op on CPU or when
    fp16 is disabled. fp16 cuts forward latency ~1.5-2× on RTX 30/40/Blackwell
    by routing the matmuls through Tensor Cores. Master weights stay fp32
    (we only autocast at inference; no training implications)."""
    if not use_fp16 or device.type != "cuda":
        return torch.amp.autocast(device_type="cpu", enabled=False)
    return torch.amp.autocast(device_type="cuda", dtype=torch.float16)


def make_single_evaluator(
    net: CarcassonneNet,
    device: torch.device,
    game: Game,
    use_fp16: bool = False,
) -> Callable[[Board], tuple[np.ndarray, float]]:
    """Single-board GPU evaluator. Returns (priors[A], value)."""
    def evaluator(board: Board) -> tuple[np.ndarray, float]:
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
        with torch.no_grad(), _autocast_ctx(device, use_fp16):
            logits, value = net(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(device)
            probs = net.policy_softmax_with_mask(logits, mask_t)
        # Cast back to fp32 before crossing the GPU→CPU boundary so downstream
        # NumPy code doesn't get fp16 surprises (some ops, e.g. masking, behave
        # differently on fp16 arrays).
        return probs[0].float().cpu().numpy(), float(value.item())
    return evaluator


def make_single_evaluator_policy_only(
    net: CarcassonneNet,
    device: torch.device,
    game: Game,
    use_fp16: bool = False,
) -> Callable[[Board], tuple[np.ndarray, float]]:
    """Single-board evaluator that skips the network's value head — returns
    (priors[A], 0.0). Use when the caller will override the value (e.g.
    composed with the v2.5 leaf wrapper, or any leaf eval that doesn't
    trust the NN value head). Saves ~5-10% of forward-pass time.

    Interface matches `make_single_evaluator` so this is a drop-in for any
    place that expects a (priors, value) callable. The returned value is
    a constant 0.0 sentinel — downstream code that uses it without
    overriding will get a degenerate eval, which is the correct surfacing
    of "you asked for policy-only; the value is not real."""
    def evaluator(board: Board) -> tuple[np.ndarray, float]:
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
        with torch.no_grad(), _autocast_ctx(device, use_fp16):
            logits = net.forward_policy_only(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(device)
            probs = net.policy_softmax_with_mask(logits, mask_t)
        return probs[0].float().cpu().numpy(), 0.0
    return evaluator


def make_batch_evaluator_policy_only(
    net: CarcassonneNet,
    device: torch.device,
    game: Game,
    use_fp16: bool = False,
) -> Callable[[list[Board]], tuple[np.ndarray, np.ndarray]]:
    """Batched evaluator that skips the network's value head. Returns
    (priors[B,A], zeros[B]). See `make_single_evaluator_policy_only`."""
    def batch_evaluator(
        boards: list[Board],
    ) -> tuple[np.ndarray, np.ndarray]:
        if not boards:
            return (
                np.empty((0,), dtype=np.float32),
                np.empty((0,), dtype=np.float32),
            )
        obs_list = []
        scalars_list = []
        masks_list = []
        for b in boards:
            obs, scalars = game.get_canonical_form(b, b.state.current_player)
            obs_list.append(obs)
            scalars_list.append(scalars)
            masks_list.append(game.get_valid_moves(b))
        obs_t = torch.from_numpy(np.stack(obs_list)).float().to(device)
        scalars_t = torch.from_numpy(np.stack(scalars_list)).float().to(device)
        masks_t = torch.from_numpy(np.stack(masks_list).copy()).bool().to(device)
        with torch.no_grad(), _autocast_ctx(device, use_fp16):
            logits = net.forward_policy_only(obs_t, scalars_t)
            probs = net.policy_softmax_with_mask(logits, masks_t)
        values = np.zeros(len(boards), dtype=np.float32)
        return probs.float().cpu().numpy(), values
    return batch_evaluator


def make_v25_value_wrapper(
    base_evaluator: Callable[[Board], tuple[np.ndarray, float]],
    cfg=None,
) -> Callable[[Board], tuple[np.ndarray, float]]:
    """Wrap a single-board evaluator: keep its priors, replace its value with
    the v2.5 leaf. The wrapped evaluator has the same NeuralMCTS interface;
    the only change is the leaf value source.

    `cfg` is an optional `virtual_score_v2.LeafConfig` — when None, the
    env-var-built DEFAULT_CONFIG is used. Pass an explicit config to A/B two
    leaf variants in one process.

    Leaf value: `tanh(virtual_score_v2(state, current_player) / 15)`. When
    `cfg.value_blend` (λ) > 0, the network value head is blended in (Option 2,
    2026-05-17): `leaf = (1-λ)·tanh(vs2/15) + λ·v_nn`. Both terms are
    tanh-bounded [-1,1], same current-player POV. λ>0 requires the base
    evaluator to return a real value head output — see the orchestrator's
    policy_only flag.

    Compatible with both local and remote evaluators since it only consumes
    the (priors, value) output shape."""
    import math

    from . import virtual_score as _vs
    from .virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

    eff_cfg = cfg if cfg is not None else DEFAULT_CONFIG
    blend = eff_cfg.value_blend

    def wrapped(board: Board) -> tuple[np.ndarray, float]:
        st = board.state
        # Share one farm/city flood-fill memo across BOTH the policy-encode
        # (base_evaluator -> get_canonical_form, which with farm input scalars on
        # floods farmer fields) and the v2.7 leaf value below. The leaf value
        # would flood those same fields anyway, so sharing makes the farm-scalar
        # floods ~free. virtual_score_v2 reuses an attached cache rather than
        # creating its own. Gated on the memo toggles so the bench/gate OFF
        # baseline (USE_*_CACHE=False) still runs legacy per-call flood-fills.
        own_farm = _vs.USE_FARM_CACHE and not hasattr(st, "_farm_cache")
        own_city = _vs.USE_CITY_CACHE and not hasattr(st, "_city_cache")
        if own_farm:
            st._farm_cache = {}
        if own_city:
            st._city_cache = {}
        try:
            priors, v_nn = base_evaluator(board)
            h = math.tanh(virtual_score_v2(st, st.current_player, eff_cfg) / 15.0)
        finally:
            if own_farm:
                try:
                    del st._farm_cache
                except AttributeError:
                    pass
            if own_city:
                try:
                    del st._city_cache
                except AttributeError:
                    pass
        if blend > 0.0:
            return priors, (1.0 - blend) * h + blend * float(v_nn)
        return priors, h

    return wrapped


def make_v25_batch_value_wrapper(
    base_batch_evaluator: Callable[[list[Board]], tuple[np.ndarray, np.ndarray]],
    cfg=None,
) -> Callable[[list[Board]], tuple[np.ndarray, np.ndarray]]:
    """Same as `make_v25_value_wrapper` but for the K-board batched evaluator.
    Priors come from the batched NN call; values are recomputed per-board from
    `virtual_score_v2`, optionally blended with the network value head when
    `cfg.value_blend` > 0. `cfg` is an optional `LeafConfig` (None → DEFAULT_CONFIG)."""
    import math

    from . import virtual_score as _vs
    from .virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

    eff_cfg = cfg if cfg is not None else DEFAULT_CONFIG
    blend = eff_cfg.value_blend

    def wrapped_batch(boards: list[Board]) -> tuple[np.ndarray, np.ndarray]:
        if not boards:
            priors, values_nn = base_batch_evaluator(boards)
            return priors, values_nn
        # Per-board farm/city memo, attached BEFORE the batched encode and held
        # through the per-board leaf-value loop, so each board's farm-input-scalar
        # floods (done during base_batch_evaluator's encode) are reused by its
        # virtual_score_v2 below — making the farm scalars ~free. See the
        # single-board wrapper for the rationale + toggle gating.
        owned = []
        for b in boards:
            st = b.state
            of = _vs.USE_FARM_CACHE and not hasattr(st, "_farm_cache")
            oc = _vs.USE_CITY_CACHE and not hasattr(st, "_city_cache")
            if of:
                st._farm_cache = {}
            if oc:
                st._city_cache = {}
            owned.append((st, of, oc))
        try:
            priors, values_nn = base_batch_evaluator(boards)
            h = np.array(
                [
                    math.tanh(virtual_score_v2(b.state, b.state.current_player, eff_cfg) / 15.0)
                    for b in boards
                ],
                dtype=np.float32,
            )
        finally:
            for st, of, oc in owned:
                if of:
                    try:
                        del st._farm_cache
                    except AttributeError:
                        pass
                if oc:
                    try:
                        del st._city_cache
                    except AttributeError:
                        pass
        if blend > 0.0:
            return priors, (1.0 - blend) * h + blend * values_nn.astype(np.float32)
        return priors, h

    return wrapped_batch


def make_batch_evaluator(
    net: CarcassonneNet,
    device: torch.device,
    game: Game,
    use_fp16: bool = False,
) -> Callable[[list[Board]], tuple[np.ndarray, np.ndarray]]:
    """K-board batched GPU evaluator. Stacks K canonical encodings into one
    forward pass; returns (priors[B,A], values[B])."""
    def batch_evaluator(
        boards: list[Board],
    ) -> tuple[np.ndarray, np.ndarray]:
        if not boards:
            return (
                np.empty((0,), dtype=np.float32),
                np.empty((0,), dtype=np.float32),
            )
        obs_list = []
        scalars_list = []
        masks_list = []
        for b in boards:
            obs, scalars = game.get_canonical_form(b, b.state.current_player)
            obs_list.append(obs)
            scalars_list.append(scalars)
            masks_list.append(game.get_valid_moves(b))
        obs_t = torch.from_numpy(np.stack(obs_list)).float().to(device)
        scalars_t = torch.from_numpy(np.stack(scalars_list)).float().to(device)
        masks_t = torch.from_numpy(np.stack(masks_list).copy()).bool().to(device)
        with torch.no_grad(), _autocast_ctx(device, use_fp16):
            logits, values = net(obs_t, scalars_t)
            probs = net.policy_softmax_with_mask(logits, masks_t)
        return probs.float().cpu().numpy(), values.float().cpu().numpy()
    return batch_evaluator
