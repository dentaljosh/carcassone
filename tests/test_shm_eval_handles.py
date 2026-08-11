"""Contract tests for the carc-orch SHM client wait (`_ShmConn.get`).

THE BUG THESE PIN (2026-07-16): `sem_timedwait` takes an absolute **CLOCK_REALTIME**
deadline, but `get(timeout=...)` promises a DURATION. WSL2 resyncs its clock to the
Windows host (and after host sleep/resume), so the wall clock STEPS. A forward step
past the deadline made `sem_timedwait` return ETIMEDOUT *immediately*, and the caller
(`remote_evaluators._wait_for_response`) turned that into

    BrokenServerError: no response from eval_server within 60.0s

against a HEALTHY server that was still batching — whose own watchdog
(jobs-in/no-batches-out) correctly stayed silent. Raising the timeout cannot fix it:
a big enough step lands past any deadline.

The fix enforces the budget on `time.monotonic()` (immune to clock steps) and only
believes an ETIMEDOUT when the monotonic clock agrees the duration really elapsed.

These tests drive a REAL POSIX semaphore (no server needed) via a minimal stand-in
that carries only the fields `get` touches.
"""
from __future__ import annotations

import ctypes
import os
import queue
import threading
import time

import numpy as np
import pytest

from carcassonne_ai import shm_eval_handles as H

_O_CREAT = 0o100  # Linux


@pytest.fixture()
def sem():
    """A fresh, real, unposted named POSIX semaphore."""
    name = f"/carc_test_shmwait_{os.getpid()}_{time.monotonic_ns()}".encode()
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    libc.sem_open.restype = ctypes.c_void_p
    libc.sem_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    libc.sem_unlink.argtypes = [ctypes.c_char_p]
    libc.sem_unlink(name)
    s = libc.sem_open(name, _O_CREAT, 0o600, 0)
    if not s:
        pytest.skip("cannot create a POSIX semaphore here")
    yield s
    libc.sem_unlink(name)


class _Conn:
    """Minimal stand-in exposing exactly what `_ShmConn.get` reads."""

    def __init__(self, sem):
        self.resp_sem = sem
        self.hdr = np.zeros(8, dtype=np.uint64)
        self.pri_v = np.zeros((H.MAX_K, 4), dtype=np.float32)
        self.val_v = np.zeros((H.MAX_K,), dtype=np.float32)
        self.hdr[1] = 1        # k
        self.hdr[3] = 4242     # request_id echoed back by the server


def test_get_returns_posted_response(sem):
    """Fast path: a posted response is returned (and carries the request_id)."""
    conn = _Conn(sem)
    conn.val_v[0] = 0.5
    H._libc.sem_post(sem)
    resp = H._ShmConn.get(conn, timeout=5.0)
    assert resp.request_id == 4242
    assert float(resp.values[0]) == pytest.approx(0.5)


def test_get_real_timeout_still_fires(sem):
    """A genuinely absent response must still time out — and take ~the full budget,
    enforced monotonically (a liveness bound must not become an infinite hang)."""
    conn = _Conn(sem)
    t0 = time.monotonic()
    with pytest.raises(queue.Empty):
        H._ShmConn.get(conn, timeout=0.5)
    assert time.monotonic() - t0 >= 0.45


def test_forward_clock_step_does_not_fake_a_timeout(sem, monkeypatch):
    """THE REGRESSION. A forward wall-clock STEP right after the deadline is computed
    must NOT be reported as an eval-server timeout while the response is on its way.

    Simulated exactly as it happens: the deadline is built from a wall clock that is
    then stepped forward — i.e. `time.time()` reads STALE once, so the absolute
    CLOCK_REALTIME deadline lands in the past and sem_timedwait returns ETIMEDOUT
    instantly. `time.monotonic()` is untouched (clock steps don't affect it).

    Pre-fix this raised queue.Empty immediately -> BrokenServerError on a healthy
    server. Post-fix the wait re-arms and collects the real response.
    """
    conn = _Conn(sem)
    real_time = time.time
    calls = {"n": 0}

    def stale_once():
        calls["n"] += 1
        if calls["n"] == 1:
            return real_time() - 1_000_000.0   # deadline lands 1e6 s in the past
        return real_time()

    monkeypatch.setattr(H.time, "time", stale_once)

    # The server answers a little later, as it would under load.
    def responder():
        time.sleep(0.2)
        conn.val_v[0] = 0.75
        H._libc.sem_post(sem)

    t = threading.Thread(target=responder)
    t.start()
    try:
        resp = H._ShmConn.get(conn, timeout=5.0)
    finally:
        t.join()

    assert calls["n"] >= 2, "expected the wait to re-arm after the spurious ETIMEDOUT"
    assert resp.request_id == 4242
    assert float(resp.values[0]) == pytest.approx(0.75)
