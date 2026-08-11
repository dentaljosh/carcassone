#!/usr/bin/env python3
"""Probe v2: multi-threaded launchers, default-stream vs own-stream.

probe_cuda_streams.py (single thread) showed pure GPU kernel-overlap is ~1.0x at
batch<=8 and ~1.4x at batch 16. But orch-off's edge is TWO things: (1) GPU stream
concurrency AND (2) many independent host threads keeping the launch queue full.
The single-thread probe only tests (1). This tests both, answering:

  Q1  own-stream vs default-stream at the same thread count -> is the CUDA-stream
      C++ shim worth building, or does the default stream already saturate?
  Q2  does aggregate ex/s scale with launcher (forwarder) count on the DEFAULT
      stream -> if yes, just spawn more forwarders (zero new code, no shim).

Each cell: N threads, each its own module copy + own input tensors, loop forwards
for DURATION s, syncing its stream every SYNC_EVERY forwards (bounds queue depth
so the count reflects COMPLETION, not enqueue, rate). Aggregate ex/s =
sum(forwards)*batch/wall. GPU board power sampled across the run.

CAVEAT: Python threads are GIL-limited; torch releases the GIL around CUDA calls
but not perfectly. A POSITIVE own-stream/scaling result is therefore a LOWER
bound for what GIL-free Rust forwarder threads would achieve; a flat result is
weaker evidence (could be the GIL, not the GPU).
"""
import subprocess
import sys
import threading
import time

import torch

TS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/carc_iter8.ts.pt"
DEV = "cuda"
N_SCALAR = 12
DURATION = 4.0
SYNC_EVERY = 8
MAX_THREADS = 8

torch.cuda.init()
torch.backends.cudnn.benchmark = True
mods = [torch.jit.load(TS, map_location=DEV).eval() for _ in range(MAX_THREADS)]


def sample_power(stop_evt, out):
    """Mean/max GPU board power (W) over the run, via Windows-interop nvidia-smi."""
    vals = []
    while not stop_evt.is_set():
        try:
            r = subprocess.run(
                ["nvidia-smi.exe", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2)
            vals.append(float(r.stdout.strip().split("\n")[0]))
        except Exception:
            pass
        time.sleep(0.25)
    out.append(sum(vals) / len(vals) if vals else float("nan"))
    out.append(max(vals) if vals else float("nan"))


def worker(idx, batch, own_stream, start_barrier, counts):
    m = mods[idx]
    obs = torch.zeros(batch, 78, 25, 25, device=DEV)
    scl = torch.zeros(batch, N_SCALAR, device=DEV)
    msk = torch.ones(batch, 2511, dtype=torch.bool, device=DEV)
    s = torch.cuda.Stream() if own_stream else torch.cuda.default_stream()
    with torch.no_grad():  # warmup
        for _ in range(10):
            if own_stream:
                with torch.cuda.stream(s):
                    m(obs, scl, msk)
            else:
                m(obs, scl, msk)
    s.synchronize()
    c = 0
    start_barrier.wait()
    deadline = time.perf_counter() + DURATION  # self-timed from simultaneous release
    with torch.no_grad():
        while time.perf_counter() < deadline:
            if own_stream:
                with torch.cuda.stream(s):
                    m(obs, scl, msk)
            else:
                m(obs, scl, msk)
            c += 1
            if c % SYNC_EVERY == 0:
                s.synchronize()
    s.synchronize()
    counts[idx] = c


def run(batch, n, own_stream):
    counts = [0] * n
    start_barrier = threading.Barrier(n + 1)
    stop_evt = threading.Event()
    pout = []
    psampler = threading.Thread(target=sample_power, args=(stop_evt, pout))
    psampler.start()
    threads = [threading.Thread(target=worker,
                                args=(i, batch, own_stream, start_barrier,
                                      counts)) for i in range(n)]
    for t in threads:
        t.start()
    # All workers warm up, then block on the barrier; main is the (n+1)th party
    # and releases everyone simultaneously. Each worker self-times DURATION.
    start_barrier.wait()
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    stop_evt.set()
    psampler.join()
    total = sum(counts)
    ex_s = total * batch / wall
    pmean, pmax = (pout + [float("nan"), float("nan")])[:2]
    return ex_s, pmean, pmax


print(f"module={TS}  dur={DURATION}s  device={torch.cuda.get_device_name(0)}")
print(f"{'batch':>6} {'N':>3} {'default ex/s':>13} {'(W)':>6} | {'own-strm ex/s':>14} {'(W)':>6} | {'own/def':>8}")
for batch in (8, 16, 32):
    for n in (2, 4, 8):
        d_ex, d_pw, _ = run(batch, n, False)
        o_ex, o_pw, _ = run(batch, n, True)
        print(f"{batch:>6} {n:>3} {d_ex:>13.0f} {d_pw:>6.1f} | {o_ex:>14.0f} {o_pw:>6.1f} | {o_ex/d_ex:>7.2f}x")
