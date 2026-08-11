"""Forward-latency vs batch-size micro-bench — isolate per-launch GPU overhead
from compute.

Why: the laptop regressed hard pop-os(native Linux) -> Win11+WSL2. Hypothesis:
the WSL2 GPU passthrough (CUDA via /dev/dxg / GPU-PV) adds per-kernel-launch
latency, and a 7M net at batch~1 (every MCTS node) is latency-bound, so that tax
dominates. This bench tests it WITHOUT game-logic confound.

Read the output two ways:
  * synced ms/fwd (sync after EACH forward = what MCTS actually pays, since the
    worker blocks on each result). If this is ~FLAT from B=1 to B=64, the forward
    time is dominated by fixed launch+sync overhead, NOT compute -> overhead-bound
    -> the WSL boundary tax. If it scales ~linearly with B, it's compute-bound.
  * synced-vs-queued gap at B=1: queued (sync once over many forwards) lets
    launches pipeline. If synced >> queued, the per-forward round-trip overhead is
    large -> again, launch/sync-bound.
Absolute number is informative even without a native baseline: a 7M net forward
is ~tens of microseconds of compute on a 4070m; a synced B=1 latency of ~1ms means
~95% of it is fixed overhead (launch + boundary crossing + sync), which on WSL2 is
the dxg tax. Content-independent (random inputs).

  python scripts/bench_forward_latency.py --checkpoint <ckpt.pt>
"""
from __future__ import annotations
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import torch

from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.board_repr import N_CHANNELS


def build_net(checkpoint: str, device: torch.device):
    ck = torch.load(checkpoint, map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(
        n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
        n_scalar_features=ns,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    )
    net.load_state_dict(ck["model_state"])
    return net.to(device).eval(), ns


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--batches", default="1,2,4,8,16,32,64")
    args = ap.parse_args()

    device = torch.device(args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu")
    net, ns = build_net(args.checkpoint, device)
    W, C = net.window_size, N_CHANNELS
    cuda = device.type == "cuda"
    name = torch.cuda.get_device_name(0) if cuda else "cpu"
    print(f"device={name} torch={torch.__version__} cuda={torch.version.cuda} "
          f"W={W} C={C} ns={ns} iters={args.iters}")
    batches = [int(x) for x in args.batches.split(",")]

    def timed(B: int, per_forward_sync: bool) -> float:
        b = torch.randn(B, C, W, W, device=device)
        s = torch.randn(B, ns, device=device)
        with torch.no_grad():
            for _ in range(20):
                net(b, s)
            if cuda:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            for _ in range(args.iters):
                net(b, s)
                if per_forward_sync and cuda:
                    torch.cuda.synchronize()
            if cuda:
                torch.cuda.synchronize()
        return (time.perf_counter() - t0) / args.iters

    print(f"{'B':>4} {'synced ms/fwd':>14} {'ms/sample':>11} {'queued ms/fwd':>14}")
    base = None
    for B in batches:
        sdt = timed(B, True)    # per-forward latency (what MCTS pays)
        qdt = timed(B, False)   # pipelined (throughput)
        if base is None:
            base = sdt
        print(f"{B:>4} {sdt * 1000:>14.3f} {sdt * 1000 / B:>11.4f} {qdt * 1000:>14.3f}")
    last = timed(batches[-1], True)
    print(f"\nsynced B={batches[-1]}/B={batches[0]} ratio = {last / base:.2f}  "
          f"(~1 => launch/overhead-bound [WSL-tax signature]; ~{batches[-1]} => compute-bound)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
