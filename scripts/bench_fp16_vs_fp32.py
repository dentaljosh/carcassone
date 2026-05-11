"""Quick fp16 vs fp32 sanity bench for the trained network.

Two checks on a fixed checkpoint:

1. **Numerical agreement** — N random mid-game positions, run fp32 + fp16
   forward passes, report L1 distance between priors and abs delta in
   value. fp16 should agree to within ~1e-3 (fp32 mantissa is 23 bits,
   fp16 is 10 bits → expect ~3 decimal digits of agreement).

2. **Wallclock** — same N positions, time each precision over a warm
   loop. Report mean per-call latency + speedup ratio.

Pass `--n` to set position count (default 50). Doesn't need MCTS so it's
cheap (~30s on local 5060 Ti).
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.evaluators import make_single_evaluator
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet


def _load_net(ckpt_path: Path, device: torch.device) -> CarcassonneNet:
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net


def _gen_mid_game_boards(g: Game, n: int, seed: int = 0):
    """Generate N mid-game boards via random play. Each board is ~30 plies in,
    so the encoder is exercised on something resembling the actual mid-game
    distribution rather than the empty starting board."""
    boards = []
    rng = random.Random(seed)
    for i in range(n):
        random.seed(seed + i)  # engine deck shuffle uses global random
        board = g.get_init_board()
        target_plies = 25 + rng.randint(0, 20)
        for _ in range(target_plies):
            mask = g.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            action = int(rng.choice(legal.tolist()))
            board, _ = g.get_next_state(board, action)
            if g.get_game_ended(board, 0) != 0.0:
                break
        boards.append(board)
    return boards


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--n", type=int, default=50,
                   help="Number of mid-game positions to test.")
    p.add_argument("--repeats", type=int, default=3,
                   help="Bench timing repeats; reports min over repeats.")
    args = p.parse_args(argv)

    if not torch.cuda.is_available():
        print("WARNING: no CUDA — fp16 autocast is a no-op on CPU. "
              "Bench is still informative for numerics but not timing.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}, checkpoint: {args.checkpoint}")

    net = _load_net(args.checkpoint, device)
    g = Game(enable_legal_moves_cache=True)

    print(f"generating {args.n} mid-game boards…")
    boards = _gen_mid_game_boards(g, args.n)
    print(f"  done; {len(boards)} boards")

    fn_fp32 = make_single_evaluator(net, device, g, use_fp16=False)
    fn_fp16 = make_single_evaluator(net, device, g, use_fp16=True)

    # warm both paths so JIT / cuBLAS heuristics settle
    for _ in range(3):
        fn_fp32(boards[0])
        fn_fp16(boards[0])

    # numerical agreement
    print("\n=== numerical agreement ===")
    max_l1 = 0.0
    max_val_diff = 0.0
    argmax_disagreements = 0
    for b in boards:
        p_fp32, v_fp32 = fn_fp32(b)
        p_fp16, v_fp16 = fn_fp16(b)
        l1 = float(np.abs(p_fp32 - p_fp16).sum())
        val_diff = abs(v_fp32 - v_fp16)
        max_l1 = max(max_l1, l1)
        max_val_diff = max(max_val_diff, val_diff)
        if int(p_fp32.argmax()) != int(p_fp16.argmax()):
            argmax_disagreements += 1
    print(f"  max prior L1 distance: {max_l1:.5f}  (over {args.n} positions)")
    print(f"  max value abs diff:    {max_val_diff:.5f}")
    print(f"  argmax disagreements:  {argmax_disagreements}/{args.n}")
    pass_str = (
        "PASS" if (max_l1 < 0.05 and max_val_diff < 0.05 and argmax_disagreements == 0)
        else "REVIEW"
    )
    print(f"  verdict: {pass_str}")

    # timing
    print("\n=== wallclock (lower = better) ===")
    def time_fn(fn, label):
        best = float("inf")
        for r in range(args.repeats):
            torch.cuda.synchronize() if device.type == "cuda" else None
            t0 = time.perf_counter()
            for b in boards:
                fn(b)
            torch.cuda.synchronize() if device.type == "cuda" else None
            elapsed = time.perf_counter() - t0
            best = min(best, elapsed)
        per_call_us = best / args.n * 1e6
        print(f"  {label}: {best*1000:.1f} ms total ({per_call_us:.1f} µs/call)")
        return best
    t_fp32 = time_fn(fn_fp32, "fp32")
    t_fp16 = time_fn(fn_fp16, "fp16")
    speedup = t_fp32 / t_fp16
    print(f"  speedup: {speedup:.2f}× (fp32 / fp16)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
