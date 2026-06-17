#!/usr/bin/env python3
"""End-to-end self-play wall-clock A/B for the Cython board-encoder (2026-06-17).

Times the SAME in-process self-play games (production leaf already on) with
board_repr.USE_CY_REPR off vs on, to size the MARGINAL cycle gain on top of the
already-folded Cython leaf. Plain timer (no cProfile distortion). Mirrors
scripts/profile_selfplay_inproc.py's worker setup exactly.

Run with production knobs:
  CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 \
    python scripts/bench_selfplay_cy_repr.py --checkpoint checkpoints/warmstart_canonical.pt \
      --games 4 --sims 200 --batch-size 8
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import torch  # noqa: E402

from carcassonne_ai import board_repr  # noqa: E402
from carcassonne_ai.evaluators import (  # noqa: E402
    make_batch_evaluator_policy_only,
    make_single_evaluator_policy_only,
    make_v25_batch_value_wrapper,
    make_v25_value_wrapper,
)
from carcassonne_ai.features import N_SCALAR_FEATURES  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.selfplay import play_one_selfplay_game  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--games", type=int, default=4)
    p.add_argument("--sims", type=int, default=200)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--c-puct", type=float, default=3.0)
    args = p.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    n_scalar = int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES))
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_scalar_features=n_scalar,
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)

    game = Game(enable_legal_moves_cache=True, include_farm_scalars=(n_scalar == 12))
    ev = make_v25_value_wrapper(
        make_single_evaluator_policy_only(net, device, game, use_fp16=False)
    )
    bev = make_v25_batch_value_wrapper(
        make_batch_evaluator_policy_only(net, device, game, use_fp16=False)
    )

    def run():
        for s in range(args.games):
            play_one_selfplay_game(
                game=game, evaluator=ev, batch_evaluator=bev, sims=args.sims,
                c_puct=args.c_puct, dirichlet_alpha=0.3, dirichlet_eps=0.25,
                temp_threshold=15, seed=1000 + s, batch_size=args.batch_size,
                virtual_loss=1.0, value_target="score_diff",
            )

    def timed(use_cy: bool) -> float:
        board_repr.USE_CY_REPR = use_cy
        board_repr._CY_ENCODE = None  # force re-bind under the new flag
        # warmup (cudnn autotune, tile-repr cache, first-touch) — not timed
        play_one_selfplay_game(
            game=game, evaluator=ev, batch_evaluator=bev, sims=args.sims,
            c_puct=args.c_puct, dirichlet_alpha=0.3, dirichlet_eps=0.25,
            temp_threshold=15, seed=777, batch_size=args.batch_size,
            virtual_loss=1.0, value_target="score_diff",
        )
        if device.type == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        run()
        if device.type == "cuda":
            torch.cuda.synchronize()
        return time.perf_counter() - t0

    print(f"end-to-end A/B: {args.games} games @ sims={args.sims} batch={args.batch_size} "
          f"device={device} (production leaf via env)")
    # Interleave to average out any thermal/clock drift: off, on, off, on.
    off1 = timed(False)
    on1 = timed(True)
    off2 = timed(False)
    on2 = timed(True)
    off = min(off1, off2)
    on = min(on1, on2)
    print(f"  USE_CY_REPR=0 : {off:7.2f} s  ({off/args.games:6.3f} s/game)")
    print(f"  USE_CY_REPR=1 : {on:7.2f} s  ({on/args.games:6.3f} s/game)")
    print(f"  end-to-end speedup: {off/on:.3f}x   (cycle time -{100*(1-on/off):.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
