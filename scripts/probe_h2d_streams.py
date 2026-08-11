#!/usr/bin/env python3
"""Probe v3: does the per-forward H2D/D2H copy serialize the CUDA streams?

The live server hit only ~67W GPU board power (default-stream level) despite 4
distinct stream handles — i.e. the streams are NOT overlapping in-server, even
though probe_cuda_streams_mt.py showed own-stream reaching ~100W. The difference:
the MT probe kept inputs/outputs GPU-resident; the real server does a per-forward
H2D (host obs/scalars/mask -> GPU) + D2H (priors/values -> host) every forward,
from PAGEABLE memory. A synchronous pageable copy can serialize across streams
(pageable cudaMemcpy syncs broadly), defeating the overlap.

This isolates that. 4 threads, each own stream + module copy, batch 16, three
per-forward modes:
  resident : no transfer (the MT-probe condition)            -> expect ~100W
  pageable : H2D in + D2H out from PAGEABLE host tensors      -> if ~67W, that's the bug
  pinned   : H2D in + D2H out via PINNED host tensors         -> if ~100W, pinning is the fix
If pageable collapses to the server's ~67W and pinned recovers ~100W, the Rust
fix is a cudaHostAlloc pinned-staging shim (tch has no pin_memory). If pinned does
NOT recover, the serializer is elsewhere (allocator lock / D2H sync) and pinning
won't help — stop before building the shim.
"""
import subprocess
import sys
import threading
import time

import torch

TS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/carc_iter8.ts.pt"
DEV = "cuda"
N_SCALAR = 12
BATCH = 16
N = 4
DURATION = 5.0
SYNC_EVERY = 8

torch.cuda.init()
torch.backends.cudnn.benchmark = True
mods = [torch.jit.load(TS, map_location=DEV).eval() for _ in range(N)]


def sample_power(stop_evt, out):
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


def worker(idx, mode, start_barrier, counts):
    m = mods[idx]
    s = torch.cuda.Stream()
    # GPU-resident inputs (used directly in 'resident' mode)
    obs_g = torch.zeros(BATCH, 78, 25, 25, device=DEV)
    scl_g = torch.zeros(BATCH, N_SCALAR, device=DEV)
    msk_g = torch.ones(BATCH, 2511, dtype=torch.bool, device=DEV)
    # host staging buffers; 'nb' uses pinned so non_blocking is truly async
    nb = mode == "nb"
    obs_h = torch.zeros(BATCH, 78, 25, 25, pin_memory=nb)
    scl_h = torch.zeros(BATCH, N_SCALAR, pin_memory=nb)
    msk_h = torch.ones(BATCH, 2511, dtype=torch.bool, pin_memory=nb)

    def one():
        if mode == "resident":
            m(obs_g, scl_g, msk_g)
            return
        if mode == "block":
            # EXACTLY the server's path: blocking .to(device) H2D + blocking .cpu() D2H
            o = obs_h.to(DEV)
            c = scl_h.to(DEV)
            k = msk_h.to(DEV)
            pri, val = m(o, c, k)
            pri.cpu()
            val.cpu()
        else:  # nb: pinned source + non_blocking transfers
            o = obs_h.to(DEV, non_blocking=True)
            c = scl_h.to(DEV, non_blocking=True)
            k = msk_h.to(DEV, non_blocking=True)
            pri, val = m(o, c, k)
            pri.to("cpu", non_blocking=True)
            val.to("cpu", non_blocking=True)

    with torch.no_grad():
        for _ in range(10):  # warmup
            with torch.cuda.stream(s):
                one()
    s.synchronize()
    c = 0
    start_barrier.wait()
    deadline = time.perf_counter() + DURATION
    with torch.no_grad():
        while time.perf_counter() < deadline:
            with torch.cuda.stream(s):
                one()
            c += 1
            if c % SYNC_EVERY == 0:
                s.synchronize()
    s.synchronize()
    counts[idx] = c


def run(mode):
    counts = [0] * N
    start_barrier = threading.Barrier(N + 1)
    stop_evt = threading.Event()
    pout = []
    psampler = threading.Thread(target=sample_power, args=(stop_evt, pout))
    psampler.start()
    threads = [threading.Thread(target=worker, args=(i, mode, start_barrier, counts))
               for i in range(N)]
    for t in threads:
        t.start()
    start_barrier.wait()
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    stop_evt.set()
    psampler.join()
    ex_s = sum(counts) * BATCH / wall
    pmean, pmax = (pout + [float("nan"), float("nan")])[:2]
    return ex_s, pmean, pmax


print(f"module={TS} batch={BATCH} N={N} streams  device={torch.cuda.get_device_name(0)}")
print(f"{'mode':>10} {'ex/s':>10} {'meanW':>8} {'maxW':>8}")
for mode in ("resident", "block", "nb"):
    ex_s, pw, pmax = run(mode)
    print(f"{mode:>10} {ex_s:>10.0f} {pw:>8.1f} {pmax:>8.1f}")
