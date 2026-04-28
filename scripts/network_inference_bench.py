"""Profile network inference latency at different batch sizes.

Phase 4 NN-MCTS will call the network at each leaf — at s=200 sims/move and
~165 moves/game and 100 games/iteration, that's 3.3M network calls per
iteration. Per-call latency × call count must fit in iteration budget.

Two regimes matter:
  - Naive per-position calls (batch=1): determines worst-case latency.
  - Batched calls (e.g. virtual-loss MCTS collects 256 leaves): determines
    sustainable throughput with batching.

If batch=1 is fast enough we can skip virtual-loss; if batched throughput is
≥100x batch=1 throughput, virtual-loss is essential for Phase 4.

Usage:
  python scripts/network_inference_bench.py
  python scripts/network_inference_bench.py --filters 96 --blocks 6
"""
from __future__ import annotations

import argparse
import sys
import time

import torch

from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.network import CarcassonneNet


def bench_batch(net: CarcassonneNet, device: torch.device, batch_size: int, iters: int = 200) -> tuple[float, float]:
    """Returns (mean ms per batch, mean μs per item)."""
    board = torch.randn(batch_size, N_CHANNELS, 25, 25, device=device)
    scalars = torch.randn(batch_size, N_SCALAR_FEATURES, device=device)
    # Warmup
    net.train(False)
    with torch.no_grad():
        for _ in range(5):
            net(board, scalars)
    if device.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(iters):
            net(board, scalars)
    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    ms_per_batch = (elapsed / iters) * 1000
    us_per_item = ms_per_batch * 1000 / batch_size
    return ms_per_batch, us_per_item


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="network_inference_bench")
    p.add_argument("--filters", type=int, default=96)
    p.add_argument("--blocks", type=int, default=6)
    p.add_argument("--iters", type=int, default=200)
    args = p.parse_args(argv)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(0)
    net = CarcassonneNet(n_filters=args.filters, n_blocks=args.blocks).to(device)

    print(f"Net: {args.blocks} ResBlocks x {args.filters} filters, "
          f"{net.param_count():,} params, device={device}")
    print()
    print(f"  {'batch':>6s}  {'ms/batch':>10s}  {'us/item':>10s}  {'items/sec':>12s}")
    print(f"  {'-'*6}  {'-'*10}  {'-'*10}  {'-'*12}")

    for batch in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
        try:
            ms, us = bench_batch(net, device, batch, iters=args.iters)
        except torch.cuda.OutOfMemoryError:
            print(f"  {batch:>6d}  {'OOM':>10s}")
            break
        items_per_sec = 1_000_000 / max(us, 1e-6)
        print(f"  {batch:>6d}  {ms:>10.2f}  {us:>10.1f}  {items_per_sec:>12.0f}")

    print()
    print("Phase 4 implications:")
    print("  - 100 games/iter × 165 moves × 200 sims = 3.3M network calls/iter.")
    print("  - At naive batch=1 throughput, divide 3.3M by items/sec for sec/iter.")
    print("  - At batched batch=256 throughput, virtual-loss MCTS yields 100-300x speedup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
