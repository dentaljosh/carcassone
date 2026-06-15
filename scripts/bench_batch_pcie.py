"""Isolate the batching question with NO networking confound: does a bigger
GPU batch amortize the per-forward PCIe + kernel-launch cost enough to matter?

Measures end-to-end examples/sec (CPU obs -> H2D -> forward -> priors/values D2H,
the full PCIe round-trip) at increasing batch sizes on the production net. This
is what an orchestrator is trying to exploit: fewer, larger PCIe hits.

- If ex/s climbs steeply 8 -> 112 -> 512, batching IS the lever (PCIe/launch
  fixed cost amortizes) and a ZERO-COPY transport could make an orchestrator win.
- If ex/s is ~flat, each forward is already PCIe/launch-bound at batch-8 and no
  amount of orchestrator batching can beat local forwards (which pay no transport).
"""
from __future__ import annotations

import time
import numpy as np
import torch

from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.network import CarcassonneNet

CKPT = "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt"
device = torch.device("cuda")
ckpt = torch.load(CKPT, map_location=device, weights_only=False)
n_scalar = int(ckpt.get("n_scalar_features", 10))
net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"],
                     n_scalar_features=n_scalar).to(device).eval()
net.load_state_dict(ckpt["model_state"])
with torch.no_grad():
    A = net(torch.zeros(1, N_CHANNELS, 25, 25, device=device),
            torch.zeros(1, n_scalar, device=device))[0].shape[1]

rng = np.random.default_rng(0)

def bench(bs, iters=200):
    # fresh CPU tensors each iter (realistic: obs is built on the worker/CPU,
    # then must cross PCIe). Includes H2D, forward, masked softmax, D2H.
    obs_h = torch.from_numpy(rng.standard_normal((bs, N_CHANNELS, 25, 25), dtype=np.float32))
    scl_h = torch.from_numpy(rng.standard_normal((bs, n_scalar), dtype=np.float32))
    msk_h = torch.ones((bs, A), dtype=torch.bool)
    # warm
    for _ in range(10):
        with torch.no_grad():
            o = obs_h.to(device, non_blocking=True); s = scl_h.to(device, non_blocking=True)
            m = msk_h.to(device, non_blocking=True)
            lg, v = net(o, s)
            p = torch.softmax(lg.masked_fill(~m, float("-inf")), dim=-1)
            _ = p.cpu().numpy(); _ = v.cpu().numpy()
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(iters):
        with torch.no_grad():
            o = obs_h.to(device, non_blocking=True); s = scl_h.to(device, non_blocking=True)
            m = msk_h.to(device, non_blocking=True)
            lg, v = net(o, s)
            p = torch.softmax(lg.masked_fill(~m, float("-inf")), dim=-1)
            pr = p.cpu().numpy(); vv = v.cpu().numpy()
    torch.cuda.synchronize()
    dt = time.perf_counter() - t
    ms = dt / iters * 1000
    exps = bs * iters / dt
    return ms, exps

print(f"net: {ckpt['n_filters']}f x {ckpt['n_blocks']}b, A={A}, device={device}")
print(f"{'batch':>6} {'ms/fwd':>8} {'ex/s':>9} {'ex/s vs b8':>11}")
base = None
for bs in [8, 16, 32, 64, 112, 224, 512, 1024]:
    ms, exps = bench(bs)
    if base is None:
        base = exps
    print(f"{bs:>6} {ms:>8.2f} {exps:>9.0f} {exps/base:>10.2f}x")
print("\nReading: if ex/s at 512 >> ex/s at 8, batching amortizes PCIe/launch -> "
      "a zero-copy orchestrator could win. If ~flat, no orchestrator beats local forwards.")
