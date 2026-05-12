"""Remote-evaluator factories for orchestrator mode.

Drop-in replacements for `evaluators.make_single_evaluator` and
`evaluators.make_batch_evaluator` with identical call contracts:

- `make_remote_single_evaluator(handles, game)` → `Callable[[Board], (priors[A], value)]`
- `make_remote_batch_evaluator(handles, game)` → `Callable[[list[Board]], (priors[B,A], values[B])]`

Instead of running the forward pass locally, the callable encodes the board
on the worker side, ships (obs, scalars, mask) over IPC to the server, and
blocks until its response arrives.

The server batches across concurrent worker requests, so even when each
individual worker submits a 1-board or 8-board sub-batch, the GPU sees a
larger effective batch (lifts utilization on workloads where the network
is otherwise GPU-starved).
"""
from __future__ import annotations

import itertools
import sys
import time
from typing import Callable

import numpy as np

from .eval_server import EvalRequest, EvalResponse, ServerHandles
from .game_wrapper import Board, Game


# Default: assume worst-case wallclock for one forward (server warmup + queue
# wait + GPU forward) is under 60s. If we wait longer than this, the server is
# almost certainly dead — raise so the worker exits instead of hanging.
_DEFAULT_RESPONSE_TIMEOUT_S = 60.0


class BrokenServerError(RuntimeError):
    """Raised when the eval-server appears to have died (response timeout)."""


def _wait_for_response(
    response_q,
    expected_request_id: int,
    timeout_s: float,
) -> EvalResponse:
    try:
        resp = response_q.get(timeout=timeout_s)
    except Exception as e:
        raise BrokenServerError(
            f"no response from eval_server within {timeout_s}s "
            f"(request_id={expected_request_id}): {type(e).__name__}: {e}"
        ) from e
    if resp.request_id != expected_request_id:
        raise BrokenServerError(
            f"response request_id mismatch: expected {expected_request_id}, "
            f"got {resp.request_id} (workers must read their own queue only)"
        )
    return resp


def make_remote_single_evaluator(
    handles: ServerHandles,
    game: Game,
    timeout_s: float = _DEFAULT_RESPONSE_TIMEOUT_S,
) -> Callable[[Board], tuple[np.ndarray, float]]:
    """Single-board remote evaluator. Wraps the 1-board case in a k=1 batch."""
    counter = itertools.count()

    def evaluator(board: Board) -> tuple[np.ndarray, float]:
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        mask = game.get_valid_moves(board)
        rid = next(counter)
        handles.request_q.put(
            EvalRequest(
                worker_id=handles.worker_id,
                request_id=rid,
                obs=obs[np.newaxis, ...],         # (1, C, H, W)
                scalars=scalars[np.newaxis, ...], # (1, S)
                mask=mask[np.newaxis, ...],       # (1, A)
            )
        )
        resp = _wait_for_response(handles.response_q, rid, timeout_s)
        return resp.priors[0], float(resp.values[0])

    return evaluator


def make_remote_batch_evaluator(
    handles: ServerHandles,
    game: Game,
    timeout_s: float = _DEFAULT_RESPONSE_TIMEOUT_S,
) -> Callable[[list[Board]], tuple[np.ndarray, np.ndarray]]:
    """K-board remote batch evaluator. Matches `make_batch_evaluator` signature."""
    counter = itertools.count()

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
        mask_list = []
        for b in boards:
            obs, scalars = game.get_canonical_form(b, b.state.current_player)
            obs_list.append(obs)
            scalars_list.append(scalars)
            mask_list.append(game.get_valid_moves(b))
        rid = next(counter)
        handles.request_q.put(
            EvalRequest(
                worker_id=handles.worker_id,
                request_id=rid,
                obs=np.stack(obs_list),
                scalars=np.stack(scalars_list),
                mask=np.stack(mask_list),
            )
        )
        resp = _wait_for_response(handles.response_q, rid, timeout_s)
        return resp.priors, resp.values

    return batch_evaluator
