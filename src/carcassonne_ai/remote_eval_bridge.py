"""Network-fronted bridge for the eval_server orchestrator pool.

Lets a remote machine submit eval requests over TCP to a local eval_server
that's owned by another process on this host. The bridge pre-claims K
ServerHandles from the pool and binds one to each incoming TCP connection.

Per-conn loop:
    read len-prefixed binary EvalRequest  ->  put on slot.request_q
    get from slot.response_q              ->  write len-prefixed binary EvalResponse

Wire format (no pickle — every arbitrary-code-exec foot-gun avoided):
    Frame:    [4 B big-endian uint32 body_len][body]
    Request:  [8 B worker_id i64][8 B request_id i64]
              [npy blob obs][npy blob scalars][npy blob mask]
    Response: [8 B request_id i64]
              [npy blob priors][npy blob values]
    npy blob: [4 B big-endian uint32 blob_len][blob_bytes from np.save]

`np.save` with `allow_pickle=False` is used for every array — the .npy
header is fully self-describing (shape + dtype) and the load side refuses
to evaluate object dtypes. ~128 B of overhead per array, fine vs the
60-80 KB payloads.

The bridge runs as a daemon thread in the same Python process that owns
the ServerPool — no extra subprocess, no extra GPU memory.
"""
from __future__ import annotations

import dataclasses
import io
import socket
import struct
import sys
import threading
import time
from typing import Any

import numpy as np

from .eval_server import EvalRequest, EvalResponse, ServerHandles


_FRAME_FMT = ">I"
_FRAME_SIZE = struct.calcsize(_FRAME_FMT)
_BLOB_FMT = ">I"
_BLOB_SIZE = struct.calcsize(_BLOB_FMT)
_REQ_HDR_FMT = ">qq"          # worker_id, request_id
_REQ_HDR_SIZE = struct.calcsize(_REQ_HDR_FMT)
_RESP_HDR_FMT = ">q"          # request_id
_RESP_HDR_SIZE = struct.calcsize(_RESP_HDR_FMT)
# 64 MB cap. A single EvalRequest at sims=200, mask~10 K, obs 22x25x25 fp32
# is ~65 KB; even a pathological 1000-board batch stays well under this.
_MAX_FRAME_SIZE = 64 * 1024 * 1024


def _pack_array(arr: np.ndarray) -> bytes:
    bio = io.BytesIO()
    np.save(bio, arr, allow_pickle=False)
    return bio.getvalue()


def _unpack_array(buf: bytes) -> np.ndarray:
    return np.load(io.BytesIO(buf), allow_pickle=False)


def pack_request(req: EvalRequest) -> bytes:
    obs_b = _pack_array(req.obs)
    scl_b = _pack_array(req.scalars)
    msk_b = _pack_array(req.mask)
    return (
        struct.pack(_REQ_HDR_FMT, int(req.worker_id), int(req.request_id))
        + struct.pack(_BLOB_FMT, len(obs_b)) + obs_b
        + struct.pack(_BLOB_FMT, len(scl_b)) + scl_b
        + struct.pack(_BLOB_FMT, len(msk_b)) + msk_b
    )


def unpack_request(buf: bytes) -> EvalRequest:
    offset = 0
    worker_id, request_id = struct.unpack_from(_REQ_HDR_FMT, buf, offset)
    offset += _REQ_HDR_SIZE
    arrays = []
    for _ in range(3):
        (n,) = struct.unpack_from(_BLOB_FMT, buf, offset)
        offset += _BLOB_SIZE
        arrays.append(_unpack_array(buf[offset:offset + n]))
        offset += n
    obs, scalars, mask = arrays
    return EvalRequest(
        worker_id=worker_id, request_id=request_id,
        obs=obs, scalars=scalars, mask=mask,
    )


def pack_response(resp: EvalResponse) -> bytes:
    p_b = _pack_array(resp.priors)
    v_b = _pack_array(resp.values)
    return (
        struct.pack(_RESP_HDR_FMT, int(resp.request_id))
        + struct.pack(_BLOB_FMT, len(p_b)) + p_b
        + struct.pack(_BLOB_FMT, len(v_b)) + v_b
    )


def unpack_response(buf: bytes) -> EvalResponse:
    offset = 0
    (request_id,) = struct.unpack_from(_RESP_HDR_FMT, buf, offset)
    offset += _RESP_HDR_SIZE
    arrays = []
    for _ in range(2):
        (n,) = struct.unpack_from(_BLOB_FMT, buf, offset)
        offset += _BLOB_SIZE
        arrays.append(_unpack_array(buf[offset:offset + n]))
        offset += n
    priors, values = arrays
    return EvalResponse(request_id=request_id, priors=priors, values=values)


def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed during recv")
        buf.extend(chunk)
    return bytes(buf)


def send_framed(sock: socket.socket, body: bytes) -> None:
    if len(body) > _MAX_FRAME_SIZE:
        raise ValueError(
            f"frame body {len(body)} exceeds {_MAX_FRAME_SIZE} byte cap"
        )
    sock.sendall(struct.pack(_FRAME_FMT, len(body)) + body)


def recv_framed(sock: socket.socket) -> bytes:
    header = _recv_exactly(sock, _FRAME_SIZE)
    (length,) = struct.unpack(_FRAME_FMT, header)
    if length == 0:
        raise ConnectionError("zero-length frame")
    if length > _MAX_FRAME_SIZE:
        raise ConnectionError(
            f"incoming frame {length} exceeds {_MAX_FRAME_SIZE} byte cap"
        )
    return _recv_exactly(sock, length)


def _conn_loop(conn: socket.socket, addr, handles: ServerHandles,
               drain_timeout_s: float = 60.0) -> None:
    """Per-connection broker. Synchronous: one request in flight at a time
    (matches the client-side make_remote_batch_evaluator contract).
    """
    pending = False
    try:
        while True:
            req = unpack_request(recv_framed(conn))
            # Re-stamp worker_id to this slot's local index. The remote box
            # uses its own enumeration; the local eval_server needs the index
            # into its own response_qs list.
            req = dataclasses.replace(req, worker_id=handles.worker_id)
            handles.request_q.put(req)
            pending = True
            # Bounded wait (review R2-B2): an untimed get() blocks this broker
            # thread FOREVER if the eval-server crashes mid-batch — no response
            # ever lands, the slot is never released, and once every slot is
            # parked here all remote workers stall with BrokenServerError for the
            # rest of the iter (one 5800X server crash silently kills the Xeon's
            # whole contribution). Time out and let queue.Empty propagate to the
            # except below: the socket closes and the finally drains + frees the
            # slot. Mirrors the finally-drain and the client-side get() timeouts.
            resp = handles.response_q.get(timeout=drain_timeout_s)
            pending = False
            send_framed(conn, pack_response(resp))
    except (ConnectionError, EOFError, OSError) as e:
        sys.stderr.write(
            f"[bridge] conn {addr} closed: {type(e).__name__}: {e}\n"
        )
    except Exception as e:
        sys.stderr.write(
            f"[bridge] conn {addr} crashed: {type(e).__name__}: {e}\n"
        )
    finally:
        # If a request was in flight when the socket died, the eval_server
        # will still push a response onto response_q. Drain it before
        # releasing the slot — otherwise the next connection that lands on
        # this slot would receive the stale prior response.
        if pending:
            try:
                handles.response_q.get(timeout=drain_timeout_s)
                sys.stderr.write(
                    f"[bridge] drained stale response on slot "
                    f"{handles.worker_id} after conn {addr} died\n"
                )
            except Exception as drain_e:
                sys.stderr.write(
                    f"[bridge] WARNING: failed to drain slot "
                    f"{handles.worker_id} after conn {addr} died: "
                    f"{type(drain_e).__name__}: {drain_e}\n"
                )
        try:
            conn.close()
        except OSError:
            pass


@dataclasses.dataclass
class BridgeServer:
    sock: socket.socket
    accept_thread: threading.Thread
    stop_event: threading.Event
    host: str
    port: int


def start_bridge(
    handles_pool: list[ServerHandles],
    host: str = "0.0.0.0",
    port: int = 0,
    accept_poll_s: float = 1.0,
) -> BridgeServer:
    """Start the TCP bridge. Returns a handle for shutdown.

    Accepts up to len(handles_pool) concurrent connections — one slot per
    connection. Additional connections are accepted then closed (RST) until
    a slot frees up. Slots are FIFO from the pool.
    """
    if not handles_pool:
        raise ValueError("handles_pool is empty; nothing to bridge")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(8)
    server_sock.settimeout(accept_poll_s)
    bound_port = server_sock.getsockname()[1]

    available_slots = list(handles_pool)
    slots_lock = threading.Lock()
    stop_event = threading.Event()

    def accept_loop() -> None:
        sys.stderr.write(
            f"[bridge] listening on {host}:{bound_port}, "
            f"{len(handles_pool)} slots\n"
        )
        sys.stderr.flush()
        while not stop_event.is_set():
            try:
                conn, addr = server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with slots_lock:
                if not available_slots:
                    sys.stderr.write(
                        f"[bridge] reject {addr}: all "
                        f"{len(handles_pool)} slots in use\n"
                    )
                    conn.close()
                    continue
                slot = available_slots.pop(0)
            sys.stderr.write(
                f"[bridge] accept {addr} -> slot {slot.worker_id}\n"
            )
            sys.stderr.flush()

            def per_conn(conn=conn, addr=addr, slot=slot):
                try:
                    _conn_loop(conn, addr, slot)
                finally:
                    with slots_lock:
                        available_slots.append(slot)
                    sys.stderr.write(
                        f"[bridge] release {addr}, slot {slot.worker_id} "
                        f"back to pool\n"
                    )
                    sys.stderr.flush()

            t = threading.Thread(
                target=per_conn, daemon=True, name=f"bridge-conn-{addr}"
            )
            t.start()

    accept_thread = threading.Thread(
        target=accept_loop, daemon=True, name="bridge-accept"
    )
    accept_thread.start()
    # Tiny pause so an immediate connect() from the same process sees the
    # listening socket. bind+listen are synchronous, but tests that race
    # connect immediately after start_bridge() benefit.
    time.sleep(0.01)
    return BridgeServer(
        sock=server_sock,
        accept_thread=accept_thread,
        stop_event=stop_event,
        host=host,
        port=bound_port,
    )


def stop_bridge(bridge: BridgeServer, join_timeout_s: float = 2.0) -> None:
    bridge.stop_event.set()
    try:
        bridge.sock.close()
    except OSError:
        pass
    bridge.accept_thread.join(timeout=join_timeout_s)
