"""Client-side socket-backed ServerHandles for remote eval-server access.

Each worker process opens one long-lived TCP connection to the remote
bridge and wraps it in objects that mimic the `request_q.put()` /
`response_q.get()` API of an mp.Queue. That lets the existing
`make_remote_batch_evaluator` and `make_remote_single_evaluator` work over
the network without any changes.

Synchronous, one-in-flight-per-worker (same contract as the local IPC
path): the evaluator does `put(req); get()` strictly in sequence.
"""
from __future__ import annotations

import dataclasses
import queue
import socket
import time
from typing import Any

from .remote_eval_bridge import (
    pack_request, recv_framed, send_framed, unpack_response,
)


_DEFAULT_CONNECT_TIMEOUT_S = 30.0


class _SocketReqQ:
    """request_q.put(EvalRequest) over a socket."""
    __slots__ = ("_sock",)

    def __init__(self, sock: socket.socket):
        self._sock = sock

    def put(self, req: Any) -> None:
        send_framed(self._sock, pack_request(req))


class _SocketRespQ:
    """response_q.get(timeout=...) over a socket. Raises queue.Empty on
    timeout so callers' existing `except Exception` paths (BrokenServerError
    wrapping in remote_evaluators._wait_for_response) trigger correctly.
    """
    __slots__ = ("_sock",)

    def __init__(self, sock: socket.socket):
        self._sock = sock

    def get(self, timeout: float | None = None) -> Any:
        if timeout is not None:
            self._sock.settimeout(timeout)
        try:
            return unpack_response(recv_framed(self._sock))
        except socket.timeout as e:
            raise queue.Empty(
                f"remote eval-server timeout after {timeout}s"
            ) from e
        finally:
            if timeout is not None:
                self._sock.settimeout(None)


@dataclasses.dataclass
class SocketServerHandles:
    """Drop-in replacement for `eval_server.ServerHandles`. The worker_id
    here is informational only — the bridge re-stamps it to its local slot
    index — but kept for log/debug parity with the local-IPC path."""
    request_q: Any
    response_q: Any
    worker_id: int
    _sock: socket.socket = dataclasses.field(repr=False, default=None)


def connect_remote(
    host: str,
    port: int,
    worker_id: int,
    connect_timeout_s: float = _DEFAULT_CONNECT_TIMEOUT_S,
) -> SocketServerHandles:
    """Open one TCP connection to the remote bridge.

    Retries every ~0.5 s for up to `connect_timeout_s`, so it tolerates the
    common case where the server-side bridge is starting at roughly the
    same moment as the remote workers.
    """
    deadline = time.monotonic() + connect_timeout_s
    last_err: BaseException | None = None
    while True:
        try:
            sock = socket.create_connection((host, port), timeout=10.0)
            sock.settimeout(None)
            # Each request waits synchronously for its response, so Nagle
            # would add a per-RTT delay for no batching benefit on the
            # client side.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return SocketServerHandles(
                request_q=_SocketReqQ(sock),
                response_q=_SocketRespQ(sock),
                worker_id=worker_id,
                _sock=sock,
            )
        except OSError as e:
            last_err = e
            if time.monotonic() >= deadline:
                break
            time.sleep(0.5)
    raise ConnectionError(
        f"could not connect to remote eval-server {host}:{port} in "
        f"{connect_timeout_s}s: {last_err}"
    )
