"""Path B Step 6.1a — in-process profile of the per-game self-play hot path.

cProfile-ing run_selfplay_iter.py directly is useless: it always spawns a 'spawn'
Pool (run_selfplay_iter.py:732), so the parent profile only sees the main /
orchestrator process — the per-game worker hot path (tree ops, get_next_state
deepcopy, leaf eval) runs in subprocesses cProfile can't see. This harness runs
the SAME per-game work IN-PROCESS (no Pool) by calling play_one_selfplay_game
directly, so cProfile captures the real cost breakdown.

Mirrors run_selfplay_iter's non-orchestrator worker with --leaf-eval v2_5 (the
production leaf): policy-only NN forward (value head skipped since value_blend==0)
+ the v2.7 virtual_score leaf wrapper.

Usage (after a warm checkpoint exists):
  python scripts/profile_selfplay_inproc.py \
      --checkpoint checkpoints/pathb_smoke/warm_aux015.pt \
      --games 3 --sims 200 --batch-size 8 --out /tmp/sp.prof
"""
from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import torch  # noqa: E402

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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="profile_selfplay_inproc")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--games", type=int, default=3)
    p.add_argument("--sims", type=int, default=200)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--c-puct", type=float, default=3.0)
    p.add_argument("--out", type=Path, default=Path("/tmp/sp.prof"))
    p.add_argument("--top", type=int, default=30)
    args = p.parse_args(argv)

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
    # v2_5 leaf + value_blend==0 -> policy-only NN forward (matches the production worker).
    ev = make_v25_value_wrapper(
        make_single_evaluator_policy_only(net, device, game, use_fp16=False)
    )
    bev = None
    if args.batch_size > 1:
        bev = make_v25_batch_value_wrapper(
            make_batch_evaluator_policy_only(net, device, game, use_fp16=False)
        )

    print(
        f"profiling {args.games} games @ sims={args.sims}, batch={args.batch_size}, "
        f"scalars={n_scalar}, device={device}"
    )

    def run():
        for s in range(args.games):
            play_one_selfplay_game(
                game=game,
                evaluator=ev,
                batch_evaluator=bev,
                sims=args.sims,
                c_puct=args.c_puct,
                dirichlet_alpha=0.3,
                dirichlet_eps=0.25,
                temp_threshold=15,
                seed=1000 + s,
                batch_size=args.batch_size,
                virtual_loss=1.0,
                value_target="score_diff",
            )

    pr = cProfile.Profile()
    pr.enable()
    run()
    pr.disable()
    pr.dump_stats(str(args.out))

    print(f"\n=== top {args.top} by CUMULATIVE time ===")
    pstats.Stats(pr).sort_stats("cumulative").print_stats(args.top)
    print(f"\n=== top {args.top} by TOTAL (self) time ===")
    pstats.Stats(pr).sort_stats("tottime").print_stats(args.top)
    print(f"\nprofile written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
