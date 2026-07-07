"""Client-side shared-memory ServerHandles for the carc-orch `--transport shm`
server. Zero-copy: the worker writes obs/scalars/mask straight into its slot in
the /dev/shm mmap (one memcpy, no np.save), posts a POSIX semaphore, and waits
on its response semaphore — replacing the ~24ms TCP+np.save round-trip.

Drop-in for remote_socket_handles.SocketServerHandles: exposes the same
`request_q.put(EvalRequest)` / `response_q.get(timeout=...)` API, so the existing
make_remote_*_evaluator factories work unchanged.

LAYOUT must stay byte-identical to rust/carc-orch/src/shm.rs (mod layout).

CHANNELS/SCALARS ARE RUNTIME-CONFIGURABLE (2026-07-03, M2 sighted rep): the
obs/scalar region sizes and all offsets are computed from ``(n_ch, n_scalar)``
via ``_Layout`` — NOT module constants. The server is told the same two numbers
(``--n-ch``/``--n-scalar``); ``connect_shm`` receives them here. Both sides
compute an identical layout, so blind 78ch/12-scalar nets keep their exact prior
layout (``_Layout(78, 12)`` == the old N_CH=78/N_SCALAR_MAX=12 constants) and
sighted 81ch/42-scalar nets get their own exact-fit layout. MAX_K/HW/A are fixed
(locked rule set).
"""
from __future__ import annotations

import ctypes
import dataclasses
import mmap
import os
import queue
import time
from typing import Any

import numpy as np

from .eval_server import EvalResponse

# --- fixed layout constants (must match shm.rs::layout) ---
MAX_K = 8
HW = 25
A = 2511
HDR = 64
N_CH_CAP = 128
N_SCALAR_CAP = 128


class _Layout:
    """Runtime slot layout for a given (n_ch, n_scalar). Mirrors
    rust/carc-orch/src/shm.rs::layout::Layout byte-for-byte."""

    __slots__ = ("n_ch", "n_scalar", "obs_per", "off_obs", "off_scl",
                 "off_msk", "off_pri", "off_val", "slot_size")

    def __init__(self, n_ch: int, n_scalar: int):
        if not (1 <= n_ch <= N_CH_CAP):
            raise ValueError(f"n_ch={n_ch} out of range 1..{N_CH_CAP}")
        if not (1 <= n_scalar <= N_SCALAR_CAP):
            raise ValueError(f"n_scalar={n_scalar} out of range 1..{N_SCALAR_CAP}")
        self.n_ch = n_ch
        self.n_scalar = n_scalar
        self.obs_per = n_ch * HW * HW
        self.off_obs = HDR
        self.off_scl = self.off_obs + MAX_K * self.obs_per * 4
        self.off_msk = self.off_scl + MAX_K * n_scalar * 4
        self.off_pri = self.off_msk + MAX_K * A
        self.off_val = self.off_pri + MAX_K * A * 4
        self.slot_size = self.off_val + MAX_K * 4


_ETIMEDOUT = 110
_EINTR = 4


class _timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


_libc = ctypes.CDLL("libc.so.6", use_errno=True)
_libc.sem_open.restype = ctypes.c_void_p
_libc.sem_open.argtypes = [ctypes.c_char_p, ctypes.c_int]
_libc.sem_post.argtypes = [ctypes.c_void_p]
_libc.sem_post.restype = ctypes.c_int
_libc.sem_wait.argtypes = [ctypes.c_void_p]
_libc.sem_wait.restype = ctypes.c_int
_libc.sem_timedwait.argtypes = [ctypes.c_void_p, ctypes.POINTER(_timespec)]
_libc.sem_timedwait.restype = ctypes.c_int


def _open_sem(name: bytes, deadline: float) -> int:
    """Attach to an existing named semaphore, retrying until deadline (the
    server creates them; a worker may start a hair earlier)."""
    while True:
        sem = _libc.sem_open(name, 0)
        if sem:  # non-NULL pointer
            return sem
        if time.monotonic() >= deadline:
            raise ConnectionError(f"sem_open {name!r} failed: {os.strerror(ctypes.get_errno())}")
        time.sleep(0.05)


class _ShmConn:
    def __init__(self, shm_name: str, worker_id: int, n_scalar: int,
                 n_ch: int = 78, connect_timeout_s: float = 30.0):
        self.worker_id = worker_id
        self.n_scalar = n_scalar
        self.n_ch = n_ch
        lay = _Layout(n_ch, n_scalar)
        self.lay = lay
        path = f"/dev/shm/carc_{shm_name}"
        deadline = time.monotonic() + connect_timeout_s
        while not os.path.exists(path):
            if time.monotonic() >= deadline:
                raise ConnectionError(f"shm {path} never appeared")
            time.sleep(0.05)
        fd = os.open(path, os.O_RDWR)
        size = os.fstat(fd).st_size
        # The server sized the file at n_workers*slot_size for the SAME
        # (n_ch, n_scalar). If our layout disagrees, base offsets would land in
        # the wrong slot -> silent corruption. Fail loud instead.
        if size % lay.slot_size != 0 or size < (worker_id + 1) * lay.slot_size:
            raise ConnectionError(
                f"shm {path} size {size} incompatible with _Layout(n_ch={n_ch}, "
                f"n_scalar={n_scalar}) slot_size={lay.slot_size} (server/client "
                f"n_ch/n_scalar mismatch?)")
        self.mm = mmap.mmap(fd, size)
        os.close(fd)
        base = worker_id * lay.slot_size
        # Pre-build writable numpy views into the slot (no per-call alloc).
        self.hdr = np.ndarray((8,), np.uint64, buffer=self.mm, offset=base)
        # obs packed CONTIGUOUS at width obs_per (=n_ch*HW*HW); server reads
        # k*obs_per contiguous floats. (Same contiguous-pack pattern as scalars.)
        self.obs_v = np.ndarray((MAX_K, lay.obs_per), np.float32, buffer=self.mm, offset=base + lay.off_obs)
        # scalars packed CONTIGUOUS at width n_scalar (server reads k*n_scalar).
        self.scl_flat = np.ndarray((MAX_K * n_scalar,), np.float32, buffer=self.mm, offset=base + lay.off_scl)
        self.msk_v = np.ndarray((MAX_K, A), np.uint8, buffer=self.mm, offset=base + lay.off_msk)
        self.pri_v = np.ndarray((MAX_K, A), np.float32, buffer=self.mm, offset=base + lay.off_pri)
        self.val_v = np.ndarray((MAX_K,), np.float32, buffer=self.mm, offset=base + lay.off_val)
        self.req_sem = _open_sem(f"/carc_{shm_name}_req_{worker_id}".encode(), deadline)
        self.resp_sem = _open_sem(f"/carc_{shm_name}_resp_{worker_id}".encode(), deadline)
        self._seq = 0

    def put(self, req) -> None:
        k = int(req.obs.shape[0])
        if k > MAX_K:
            raise ValueError(f"k={k} exceeds MAX_K={MAX_K}")
        ns = self.n_scalar
        self.obs_v[:k] = req.obs.reshape(k, self.lay.obs_per)
        self.scl_flat[: k * ns] = req.scalars.reshape(k * ns)
        self.msk_v[:k] = req.mask.reshape(k, A).astype(np.uint8, copy=False)
        self._seq += 1
        self.hdr[0] = self._seq          # req_seq
        self.hdr[1] = k                  # k
        self.hdr[3] = int(req.request_id)
        if _libc.sem_post(self.req_sem) != 0:
            raise ConnectionError("sem_post(req) failed")

    def get(self, timeout: float | None = None):
        if timeout is None:
            timeout = 75.0
        ts = _timespec()
        dl = time.time() + timeout
        ts.tv_sec = int(dl)
        ts.tv_nsec = int((dl - int(dl)) * 1e9)
        while True:
            r = _libc.sem_timedwait(self.resp_sem, ctypes.byref(ts))
            if r == 0:
                break
            err = ctypes.get_errno()
            if err == _EINTR:
                continue
            if err == _ETIMEDOUT:
                raise queue.Empty(f"shm eval-server timeout after {timeout}s")
            raise ConnectionError(f"sem_timedwait failed: {os.strerror(err)}")
        k = int(self.hdr[1])
        priors = self.pri_v[:k].copy()
        values = self.val_v[:k].copy()
        rid = int(self.hdr[3])
        return EvalResponse(request_id=rid, priors=priors, values=values)


@dataclasses.dataclass
class ShmServerHandles:
    """Drop-in for eval_server.ServerHandles / SocketServerHandles."""
    request_q: Any
    response_q: Any
    worker_id: int
    _conn: Any = dataclasses.field(repr=False, default=None)


def connect_shm(shm_name: str, worker_id: int, n_scalar: int,
                n_ch: int = 78, connect_timeout_s: float = 30.0) -> ShmServerHandles:
    # NOTE (2026-07-06 fix): n_ch was added to _ShmConn's signature (before
    # connect_timeout_s) during the M2 sighted-net work, but this wrapper kept
    # forwarding 4 positionals — so 3-arg callers got n_ch=30.0 (the timeout!)
    # and 4-arg callers' n_ch only worked by landing in the timeout slot and
    # being re-forwarded. Signature now mirrors _ShmConn exactly.
    conn = _ShmConn(shm_name, worker_id, n_scalar, n_ch, connect_timeout_s)
    return ShmServerHandles(request_q=conn, response_q=conn, worker_id=worker_id, _conn=conn)
