"""Client-side shared-memory ServerHandles for the carc-orch `--transport shm`
server. Zero-copy: the worker writes obs/scalars/mask straight into its slot in
the /dev/shm mmap (one memcpy, no np.save), posts a POSIX semaphore, and waits
on its response semaphore — replacing the ~24ms TCP+np.save round-trip.

Drop-in for remote_socket_handles.SocketServerHandles: exposes the same
`request_q.put(EvalRequest)` / `response_q.get(timeout=...)` API, so the existing
make_remote_*_evaluator factories work unchanged.

LAYOUT must stay byte-identical to rust/carc-orch/src/shm.rs (mod layout).
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

# --- layout (must match shm.rs::layout) ---
MAX_K = 8
N_CH = 78
HW = 25
OBS_PER = N_CH * HW * HW           # 48750
A = 2511
N_SCALAR_MAX = 12
HDR = 64
OFF_OBS = HDR
OFF_SCL = OFF_OBS + MAX_K * OBS_PER * 4
OFF_MSK = OFF_SCL + MAX_K * N_SCALAR_MAX * 4
OFF_PRI = OFF_MSK + MAX_K * A
OFF_VAL = OFF_PRI + MAX_K * A * 4
SLOT_SIZE = OFF_VAL + MAX_K * 4

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
                 connect_timeout_s: float = 30.0):
        self.worker_id = worker_id
        self.n_scalar = n_scalar
        path = f"/dev/shm/carc_{shm_name}"
        deadline = time.monotonic() + connect_timeout_s
        while not os.path.exists(path):
            if time.monotonic() >= deadline:
                raise ConnectionError(f"shm {path} never appeared")
            time.sleep(0.05)
        fd = os.open(path, os.O_RDWR)
        size = os.fstat(fd).st_size
        self.mm = mmap.mmap(fd, size)
        os.close(fd)
        base = worker_id * SLOT_SIZE
        # Pre-build writable numpy views into the slot (no per-call alloc).
        self.hdr = np.ndarray((8,), np.uint64, buffer=self.mm, offset=base)
        self.obs_v = np.ndarray((MAX_K, OBS_PER), np.float32, buffer=self.mm, offset=base + OFF_OBS)
        # scalars are packed CONTIGUOUS at width n_scalar (the server reads
        # k*n_scalar contiguous floats), NOT strided at N_SCALAR_MAX.
        self.scl_flat = np.ndarray((MAX_K * N_SCALAR_MAX,), np.float32, buffer=self.mm, offset=base + OFF_SCL)
        self.msk_v = np.ndarray((MAX_K, A), np.uint8, buffer=self.mm, offset=base + OFF_MSK)
        self.pri_v = np.ndarray((MAX_K, A), np.float32, buffer=self.mm, offset=base + OFF_PRI)
        self.val_v = np.ndarray((MAX_K,), np.float32, buffer=self.mm, offset=base + OFF_VAL)
        rn = shm_name.encode()
        self.req_sem = _open_sem(f"/carc_{shm_name}_req_{worker_id}".encode(), deadline)
        self.resp_sem = _open_sem(f"/carc_{shm_name}_resp_{worker_id}".encode(), deadline)
        self._seq = 0

    def put(self, req) -> None:
        k = int(req.obs.shape[0])
        if k > MAX_K:
            raise ValueError(f"k={k} exceeds MAX_K={MAX_K}")
        ns = self.n_scalar
        self.obs_v[:k] = req.obs.reshape(k, OBS_PER)
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
                connect_timeout_s: float = 30.0) -> ShmServerHandles:
    conn = _ShmConn(shm_name, worker_id, n_scalar, connect_timeout_s)
    return ShmServerHandles(request_q=conn, response_q=conn, worker_id=worker_id, _conn=conn)
