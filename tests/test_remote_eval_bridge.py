"""Unit tests for the network-distributed eval-server bridge.

The bridge brokers TCP requests onto local mp.Queue-backed ServerHandles,
so this suite stands up a fake "eval server" using plain Queue objects and
a worker thread, then checks the wire path end-to-end via the loopback TCP
listener.
"""
from __future__ import annotations

import dataclasses
import queue
import threading
import time

import numpy as np
import pytest

from carcassonne_ai.eval_server import (
    EvalRequest, EvalResponse, ServerHandles,
)
from carcassonne_ai.remote_eval_bridge import (
    pack_request, pack_response, recv_framed, send_framed,
    start_bridge, stop_bridge, unpack_request, unpack_response,
)
from carcassonne_ai.remote_socket_handles import connect_remote


# -- fake server helpers --------------------------------------------------

def _make_fake_handles(n_slots: int):
    """Return (handles_list, request_q, response_qs). The caller spins a
    fake-server thread that drains request_q and pushes onto response_qs."""
    request_q: queue.Queue = queue.Queue()
    response_qs = [queue.Queue() for _ in range(n_slots)]
    handles = [
        ServerHandles(request_q=request_q, response_q=response_qs[i], worker_id=i)
        for i in range(n_slots)
    ]
    return handles, request_q, response_qs


def _start_fake_server(request_q, response_qs, stop_event):
    """Drain request_q forever, echo back (priors=ones*k, values=arange)
    on the right response_q. Mimics the real eval_server.
    """
    def loop():
        while not stop_event.is_set():
            try:
                req = request_q.get(timeout=0.1)
            except queue.Empty:
                continue
            k = req.obs.shape[0]
            a = req.mask.shape[1]
            resp = EvalResponse(
                request_id=req.request_id,
                priors=np.ones((k, a), dtype=np.float32) * float(req.request_id),
                values=np.arange(k, dtype=np.float32),
            )
            response_qs[req.worker_id].put(resp)
    t = threading.Thread(target=loop, daemon=True, name="fake-eval-server")
    t.start()
    return t


def _make_req(rid: int, k: int = 1, a: int = 10) -> EvalRequest:
    return EvalRequest(
        worker_id=0,
        request_id=rid,
        obs=np.zeros((k, 3, 5, 5), dtype=np.float32),
        scalars=np.zeros((k, 4), dtype=np.float32),
        mask=np.ones((k, a), dtype=bool),
    )


# -- framing tests --------------------------------------------------------

def test_send_recv_roundtrip_request():
    import socket
    a, b = socket.socketpair()
    req = _make_req(rid=42, k=3, a=17)
    send_framed(a, pack_request(req))
    got = unpack_request(recv_framed(b))
    assert got.request_id == 42
    assert got.worker_id == req.worker_id
    assert got.obs.shape == (3, 3, 5, 5)
    assert got.obs.dtype == np.float32
    assert got.mask.shape == (3, 17)
    assert got.mask.dtype == bool
    a.close(); b.close()


def test_send_recv_roundtrip_response():
    import socket
    a, b = socket.socketpair()
    resp = EvalResponse(
        request_id=7,
        priors=np.full((2, 9), 0.5, dtype=np.float32),
        values=np.array([0.1, -0.2], dtype=np.float32),
    )
    send_framed(a, pack_response(resp))
    got = unpack_response(recv_framed(b))
    assert got.request_id == 7
    assert np.array_equal(got.priors, resp.priors)
    assert np.array_equal(got.values, resp.values)
    a.close(); b.close()


def test_pack_unpack_preserves_values_exactly():
    """Wire format must not introduce any float drift — the eval-server
    contract is bit-identical results (modulo batch ordering, which is
    irrelevant on the per-batch path).
    """
    rng = np.random.default_rng(0)
    obs = rng.standard_normal((4, 22, 25, 25)).astype(np.float32)
    scalars = rng.standard_normal((4, 50)).astype(np.float32)
    mask = (rng.standard_normal((4, 10000)) > 0).astype(bool)
    req = EvalRequest(worker_id=3, request_id=12345, obs=obs, scalars=scalars, mask=mask)
    got = unpack_request(pack_request(req))
    assert got.worker_id == 3
    assert got.request_id == 12345
    assert np.array_equal(got.obs, obs)
    assert np.array_equal(got.scalars, scalars)
    assert np.array_equal(got.mask, mask)


# -- end-to-end bridge tests ----------------------------------------------

@pytest.fixture
def fake_bridge():
    """One-shot fixture: fake server + bridge + 4 slots, on a random port."""
    handles, request_q, response_qs = _make_fake_handles(n_slots=4)
    stop_event = threading.Event()
    server_thread = _start_fake_server(request_q, response_qs, stop_event)
    bridge = start_bridge(handles, host="127.0.0.1", port=0)
    yield bridge
    stop_bridge(bridge)
    stop_event.set()
    server_thread.join(timeout=2.0)


def test_single_request_roundtrip(fake_bridge):
    h = connect_remote("127.0.0.1", fake_bridge.port, worker_id=99)
    req = _make_req(rid=1, k=2, a=8)
    h.request_q.put(req)
    resp = h.response_q.get(timeout=5.0)
    assert resp.request_id == 1
    assert resp.priors.shape == (2, 8)
    assert resp.values.shape == (2,)
    h._sock.close()


def test_many_sequential_requests(fake_bridge):
    h = connect_remote("127.0.0.1", fake_bridge.port, worker_id=0)
    for i in range(50):
        req = _make_req(rid=i, k=1, a=5)
        h.request_q.put(req)
        resp = h.response_q.get(timeout=5.0)
        assert resp.request_id == i
        # fake server stamps priors with the request_id
        assert resp.priors[0, 0] == float(i)
    h._sock.close()


def test_concurrent_workers(fake_bridge):
    """Multiple connections in parallel each get their own correct responses."""
    n_workers = 4
    n_per_worker = 20
    results: list[list[int]] = [[] for _ in range(n_workers)]

    def worker(wid: int):
        h = connect_remote("127.0.0.1", fake_bridge.port, worker_id=wid)
        try:
            for i in range(n_per_worker):
                rid = wid * 1000 + i
                h.request_q.put(_make_req(rid=rid, k=1, a=3))
                resp = h.response_q.get(timeout=5.0)
                results[wid].append(resp.request_id)
        finally:
            h._sock.close()

    threads = [
        threading.Thread(target=worker, args=(w,)) for w in range(n_workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)
        assert not t.is_alive()

    for w in range(n_workers):
        expected = [w * 1000 + i for i in range(n_per_worker)]
        assert results[w] == expected, f"worker {w} got out-of-order responses"


def test_slot_exhaustion_rejects(fake_bridge):
    """5th concurrent connection (only 4 slots) is rejected — but the bridge
    accepts the connection at the TCP layer and then drops it, so the client
    sees EOF on its first send/recv, not connect failure."""
    socks = []
    try:
        for w in range(4):
            socks.append(connect_remote("127.0.0.1", fake_bridge.port, worker_id=w))
        # 5th connect succeeds at TCP layer (server.listen backlog absorbs it),
        # then the bridge closes the socket immediately. Verify that the next
        # request fails — that's the observable signal of rejection.
        extra = connect_remote("127.0.0.1", fake_bridge.port, worker_id=99)
        # Closed sockets may not surface the EOF until the first send/recv.
        # Send a tiny request; expect an OSError or empty recv.
        time.sleep(0.2)  # let the bridge close it
        with pytest.raises((OSError, ConnectionError, queue.Empty)):
            extra.request_q.put(_make_req(rid=0))
            extra.response_q.get(timeout=2.0)
        extra._sock.close()
    finally:
        for h in socks:
            try:
                h._sock.close()
            except OSError:
                pass


def test_slot_released_on_disconnect(fake_bridge):
    """After a worker disconnects, its slot returns to the pool."""
    # Fill all 4 slots, drop one, confirm a new one connects fine.
    socks = [
        connect_remote("127.0.0.1", fake_bridge.port, worker_id=w)
        for w in range(4)
    ]
    socks[0]._sock.close()
    time.sleep(0.5)  # let bridge notice the EOF and release the slot
    # 5th connect should now succeed and work end-to-end.
    fresh = connect_remote("127.0.0.1", fake_bridge.port, worker_id=99)
    fresh.request_q.put(_make_req(rid=777, k=1, a=4))
    resp = fresh.response_q.get(timeout=5.0)
    assert resp.request_id == 777
    fresh._sock.close()
    for h in socks[1:]:
        h._sock.close()


def test_worker_id_restamped_to_slot(fake_bridge):
    """Confirm bridge rewrites worker_id from the client's value to the slot's
    local index — otherwise the fake server's `response_qs[req.worker_id]`
    lookup would index out of bounds when the client uses worker_id=999."""
    h = connect_remote("127.0.0.1", fake_bridge.port, worker_id=999)
    req = _make_req(rid=5, k=1, a=4)
    assert req.worker_id == 0  # _make_req default — irrelevant; client may also override
    req = dataclasses.replace(req, worker_id=999)  # force a non-slot id
    h.request_q.put(req)
    resp = h.response_q.get(timeout=5.0)
    assert resp.request_id == 5
    h._sock.close()
