#!/usr/bin/env python3
"""Probe: does the iter8 net's forward overlap across CUDA streams on THIS GPU?

The load-bearing question for the carc-orch CUDA-streams gambit. orch-off wins
self-play because W worker processes (each its own CUDA context = its own stream)
overlap their batch-~8 forwards on the GPU for free. The central orchestrator runs
every forward on the *default* stream -> kernels serialize. To beat orch-off the
orchestrator must give each forwarder its own non-default stream so kernels
overlap. tch 0.24 has NO stream API, so doing this in Rust means a C++ FFI shim.
Before paying for that, measure the OVERLAP CEILING here in Python (where stream
control is one line).

Method, compute-only (sync once at the end) to isolate GPU overlap from D2H:
  serial : M forwards on the default stream (mods[0])
  streams: M forwards round-robin across N independent streams, each its own
           module copy, launched back-to-back with NO inter-forward sync
ratio = streams_fps / serial_fps.
  >~1.3  => real overlap; the Rust shim is worth building.
  ~1.0   => kernels don't overlap (launch-bound / GPU already saturated) => gambit dead.
"""
import sys
import time

import torch

TS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/carc_iter8.ts.pt"
DEV = "cuda"
M = int(sys.argv[2]) if len(sys.argv) > 2 else 500       # forwards per measurement
MAX_STREAMS = 4
N_SCALAR = 12

torch.cuda.init()
torch.backends.cudnn.benchmark = True
mods = [torch.jit.load(TS, map_location=DEV).eval() for _ in range(MAX_STREAMS)]
streams = [torch.cuda.Stream() for _ in range(MAX_STREAMS)]


def make_inputs(batch):
    obs = torch.zeros(batch, 78, 25, 25, device=DEV)
    scl = torch.zeros(batch, N_SCALAR, device=DEV)
    msk = torch.ones(batch, 2511, dtype=torch.bool, device=DEV)
    return obs, scl, msk


def serial(inputs, iters):
    m = mods[0]
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(iters):
            m(*inputs)
    torch.cuda.synchronize()
    return time.perf_counter() - t0


def multistream(inputs, iters, n):
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        for i in range(iters):
            s = streams[i % n]
            mm = mods[i % n]
            with torch.cuda.stream(s):
                mm(*inputs)
    torch.cuda.synchronize()
    return time.perf_counter() - t0


print(f"module={TS}  M={M} forwards/measurement  device={torch.cuda.get_device_name(0)}")
print(f"{'batch':>6} {'serial_fwd/s':>13} {'N':>3} {'stream_fwd/s':>13} {'ratio':>7} {'verdict':>11}")
for batch in (1, 4, 8, 16):
    inputs = make_inputs(batch)
    # warmup every module at this batch (cuDNN autotune)
    with torch.no_grad():
        for m in mods:
            for _ in range(15):
                m(*inputs)
    torch.cuda.synchronize()
    t_s = serial(inputs, M)
    fps_s = M / t_s
    for n in (2, 3, 4):
        t_m = multistream(inputs, M, n)
        fps_m = M / t_m
        ratio = fps_m / fps_s
        verdict = "OVERLAP" if ratio > 1.15 else "flat"
        print(f"{batch:>6} {fps_s:>13.0f} {n:>3} {fps_m:>13.0f} {ratio:>6.2f}x {verdict:>11}")
