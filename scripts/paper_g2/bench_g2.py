#!/usr/bin/env python3
"""G2 pre-flight bench: parameter counts + measured fwd+bwd step time for every
arm, at PRODUCTION knobs (effective batch 256, the real 81x25x25 / 42-scalar
shapes, the real loss terms, gradient accumulation where VRAM forces it).
Feeds the ETA in PREREG.md. Read-only.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

from carcassonne_ai.network import CarcassonneNet          # noqa: E402
from g2_transformer import build as build_tf               # noqa: E402

EFF_B = 256
C, W, S, A = 81, 25, 42, 2511


def bench(name, make_net, device, amp_dtype, micro, iters=8, warmup=3):
    net = make_net().to(device)
    accum = EFF_B // micro
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=1e-4)
    board = torch.randn(micro, C, W, W, device=device)
    scal = torch.randn(micro, S, device=device)
    pol = torch.rand(micro, A, device=device)
    pol = pol / pol.sum(1, keepdim=True)
    val = torch.rand(micro, device=device) * 2 - 1
    torch.cuda.reset_peak_memory_stats()
    for i in range(warmup + iters):
        if i == warmup:
            torch.cuda.synchronize()
            t0 = time.perf_counter()
        opt.zero_grad(set_to_none=True)
        for _ in range(accum):
            with torch.autocast("cuda", dtype=amp_dtype, enabled=amp_dtype is not None):
                logits, v, _o = net.forward_train(board, scal)
                loss = (F.cross_entropy(logits.float(), pol)
                        + 5.0 * F.mse_loss(v.float(), val)) / accum
            loss.backward()
        opt.step()
    torch.cuda.synchronize()
    dt = (time.perf_counter() - t0) / iters
    mem = torch.cuda.max_memory_allocated() / 2**30
    n = sum(p.numel() for p in net.parameters() if p.requires_grad)
    print(f"{name:34s} params={n:>11,} micro={micro:4d} "
          f"step(eff256)={dt*1000:8.1f} ms  peakVRAM={mem:5.2f} GiB  "
          f"-> {dt*1282/60:6.2f} min/epoch")
    del net, opt, board, scal, pol, val
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    return n, dt


def main():
    dev = torch.device("cuda")
    print(f"torch {torch.__version__}  {torch.cuda.get_device_name(0)}  "
          f"(1282 optimizer steps/epoch at eff batch 256)")
    mk_resnet = lambda: CarcassonneNet(  # noqa: E731
        n_input_channels=C, n_scalar_features=S,
        n_filters=96, n_blocks=6, value_global_pool=True)

    print("\n--- fp32 + TF32 matmul ---")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    bench("resnet 6x96  [tf32]", mk_resnet, dev, None, 256)
    bench("tf_match d128L6 [tf32]", lambda: build_tf("tf_match"), dev, None, 256)
    bench("tf_large d384L12 [tf32]", lambda: build_tf("tf_large"), dev, None, 64)

    print("\n--- bf16 autocast ---")
    bench("resnet 6x96  [bf16]", mk_resnet, dev, torch.bfloat16, 256)
    bench("tf_match d128L6 [bf16]", lambda: build_tf("tf_match"), dev, torch.bfloat16, 256)
    bench("tf_large d384L12 [bf16]", lambda: build_tf("tf_large"), dev, torch.bfloat16, 64)
    bench("tf_large d384L12 [bf16]", lambda: build_tf("tf_large"), dev, torch.bfloat16, 128)


if __name__ == "__main__":
    main()
