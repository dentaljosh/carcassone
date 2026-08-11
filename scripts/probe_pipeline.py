#!/usr/bin/env python3
"""Probe v4: does a double-buffer pipeline (async pinned H2D/D2H, 2 streams per
worker) raise throughput over the server's current blocking path?

The carc-orch forwarder currently does, per batch on one stream: blocking H2D
(to_device) -> forward -> blocking D2H (.cpu()). The proposed restructure makes
H2D/D2H async (pinned + non_blocking) and double-buffers across 2 streams so
batch N+1's H2D/compute overlaps batch N's D2H/finalize. This probe tests whether
that actually helps on THIS net BEFORE the ~1-2hr parity-risky Rust rewrite (same
cheap-first pattern that de-risked the streams gambit).

Compares aggregate ex/s (4 worker threads, batch 16) for:
  block    : 1 stream/worker, blocking H2D + forward + blocking D2H, sync per batch
             (mirrors the current 1.33x server)
  pipeline : 2 streams/worker, pinned async H2D + forward + async D2H, finalize the
             PREVIOUS batch while enqueuing the current one (the proposed change)
ratio = pipeline/block. >~1.2 => the Rust restructure is worth building.
~1.0 => the GPU/overlap is already saturated; skip it (FWD=8 + cuDNN already neutral).
"""
import subprocess
import sys
import threading
import time

import torch

TS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/carc_iter8.ts.pt"
DEV = "cuda"
N = 4
BATCH = 16
N_SCALAR = 12
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


def worker_block(idx, barrier, counts):
    m = mods[idx]
    s = torch.cuda.Stream()
    obs = torch.zeros(BATCH, 78, 25, 25)
    scl = torch.zeros(BATCH, N_SCALAR)
    msk = torch.ones(BATCH, 2511, dtype=torch.bool)
    with torch.no_grad():
        for _ in range(10):
            with torch.cuda.stream(s):
                m(obs.to(DEV), scl.to(DEV), msk.to(DEV))
    s.synchronize()
    c = 0
    barrier.wait()
    deadline = time.perf_counter() + DURATION
    with torch.no_grad():
        while time.perf_counter() < deadline:
            with torch.cuda.stream(s):
                o = obs.to(DEV)
                cc = scl.to(DEV)
                k = msk.to(DEV)
                pri, val = m(o, cc, k)
                pri.cpu()
                val.cpu()
            s.synchronize()
            c += 1
    s.synchronize()
    counts[idx] = c


def worker_pipeline(idx, barrier, counts):
    m = mods[idx]
    streams = [torch.cuda.Stream(), torch.cuda.Stream()]
    # 2 slots of pinned host inputs/outputs + persistent GPU inputs
    pin_obs = [torch.zeros(BATCH, 78, 25, 25).pin_memory() for _ in range(2)]
    pin_scl = [torch.zeros(BATCH, N_SCALAR).pin_memory() for _ in range(2)]
    pin_msk = [torch.ones(BATCH, 2511, dtype=torch.bool).pin_memory() for _ in range(2)]
    gpu_obs = [torch.zeros(BATCH, 78, 25, 25, device=DEV) for _ in range(2)]
    gpu_scl = [torch.zeros(BATCH, N_SCALAR, device=DEV) for _ in range(2)]
    gpu_msk = [torch.ones(BATCH, 2511, dtype=torch.bool, device=DEV) for _ in range(2)]
    pin_pri = [torch.zeros(BATCH, 2511).pin_memory() for _ in range(2)]
    pin_val = [torch.zeros(BATCH).pin_memory() for _ in range(2)]

    def enqueue(slot):
        with torch.cuda.stream(streams[slot]):
            gpu_obs[slot].copy_(pin_obs[slot], non_blocking=True)
            gpu_scl[slot].copy_(pin_scl[slot], non_blocking=True)
            gpu_msk[slot].copy_(pin_msk[slot], non_blocking=True)
            pri, val = m(gpu_obs[slot], gpu_scl[slot], gpu_msk[slot])
            pin_pri[slot].copy_(pri, non_blocking=True)
            pin_val[slot].copy_(val, non_blocking=True)

    with torch.no_grad():
        for _ in range(10):
            enqueue(0)
            streams[0].synchronize()
    c = 0
    prev = None
    barrier.wait()
    deadline = time.perf_counter() + DURATION
    with torch.no_grad():
        while time.perf_counter() < deadline:
            cur = c % 2
            enqueue(cur)
            if prev is not None:
                streams[prev].synchronize()  # finalize previous batch's D2H
                _ = pin_pri[prev][0, 0].item() if False else None  # results are ready in pin_pri[prev]
            prev = cur
            c += 1
    if prev is not None:
        streams[prev].synchronize()
    counts[idx] = c


def run(worker):
    counts = [0] * N
    barrier = threading.Barrier(N + 1)
    stop_evt = threading.Event()
    pout = []
    psampler = threading.Thread(target=sample_power, args=(stop_evt, pout))
    psampler.start()
    threads = [threading.Thread(target=worker, args=(i, barrier, counts)) for i in range(N)]
    for t in threads:
        t.start()
    barrier.wait()
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    stop_evt.set()
    psampler.join()
    ex_s = sum(counts) * BATCH / wall
    pmean = (pout + [float("nan")])[0]
    return ex_s, pmean


print(f"module={TS} batch={BATCH} N={N}  device={torch.cuda.get_device_name(0)}")
b_ex, b_pw = run(worker_block)
p_ex, p_pw = run(worker_pipeline)
print(f"{'block':>10}: {b_ex:>8.0f} ex/s  {b_pw:>6.1f}W")
print(f"{'pipeline':>10}: {p_ex:>8.0f} ex/s  {p_pw:>6.1f}W")
print(f"{'ratio':>10}: {p_ex / b_ex:>8.2f}x  ({'WORTH the Rust rewrite' if p_ex/b_ex > 1.2 else 'NOT worth it — skip'})")
