"""cProfile a single self-play game at production-realistic settings.

Goal: find the hot lines in `src/carcassonne_ai/mcts.py` (selection,
expansion, backup, virtual-loss accounting) so we know what to optimize.

The orchestrator N-sweep on 2026-05-13 proved workers (CPU-bound MCTS
tree work) are the binding constraint, not the GPU dispatcher. This
script answers "which functions in workers are eating wallclock?"

Usage:
    python -u scripts/profile_mcts.py \\
        --checkpoint checkpoints/warmstart_canonical.pt \\
        --sims 200 --batch-size 8 --seed 42

Outputs:
    /tmp/mcts_profile.prof          (binary pstats; load with snakeviz)
    /tmp/mcts_profile_top.txt       (top 40 by tottime + cumtime)
"""
from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

# Make `src/carcassonne_ai/...` importable when run as a script.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402

from carcassonne_ai.evaluators import (  # noqa: E402
    make_batch_evaluator,
    make_single_evaluator,
    make_v25_batch_value_wrapper,
    make_v25_value_wrapper,
)
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.selfplay import play_one_selfplay_game  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(prog="profile_mcts")
    p.add_argument("--checkpoint", type=Path,
                   default=Path("checkpoints/warmstart_canonical.pt"))
    p.add_argument("--sims", type=int, default=200,
                   help="MCTS sims per move (production: 200).")
    p.add_argument("--batch-size", type=int, default=8,
                   help="NeuralMCTS batch size (production: 8).")
    p.add_argument("--virtual-loss", type=float, default=1.0)
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--dirichlet-alpha", type=float, default=0.3)
    p.add_argument("--dirichlet-eps", type=float, default=0.25)
    p.add_argument("--temp-threshold", type=int, default=15)
    p.add_argument(
        "--leaf-eval", choices=["nn", "v2_5"], default="nn",
        help="Leaf value source. 'nn' = network value head. 'v2_5' = the "
             "virtual_score_v2 heuristic leaf (production self-play) — wraps "
             "the evaluator so the profile includes virtual_score_v2 cost.",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path("/tmp/mcts_profile.prof"))
    p.add_argument("--top", type=Path, default=Path("/tmp/mcts_profile_top.txt"))
    p.add_argument(
        "--no-profile", action="store_true",
        help="Skip cProfile (wallclock-only mode). Use for A/B-ing an "
             "optimization against baseline without profiler overhead."
    )
    args = p.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}  checkpoint={args.checkpoint}", flush=True)
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)

    game = Game(enable_legal_moves_cache=True)
    evaluator = make_single_evaluator(net, device, game)
    batch_evaluator = make_batch_evaluator(net, device, game) if args.batch_size > 1 else None

    # v2.5 leaf: replace the NN value with virtual_score_v2 so the profile
    # reflects production self-play (matches run_selfplay_iter --leaf-eval v2_5).
    if args.leaf_eval == "v2_5":
        evaluator = make_v25_value_wrapper(evaluator)
        if batch_evaluator is not None:
            batch_evaluator = make_v25_batch_value_wrapper(batch_evaluator)

    print(
        f"sims={args.sims} batch_size={args.batch_size} "
        f"virtual_loss={args.virtual_loss} leaf_eval={args.leaf_eval} "
        f"seed={args.seed}",
        flush=True,
    )

    pr = None if args.no_profile else cProfile.Profile()
    t0 = time.perf_counter()
    if pr is not None:
        pr.enable()
    ds = play_one_selfplay_game(
        game=game,
        evaluator=evaluator,
        sims=args.sims,
        c_puct=args.c_puct,
        dirichlet_alpha=args.dirichlet_alpha,
        dirichlet_eps=args.dirichlet_eps,
        temp_threshold=args.temp_threshold,
        seed=args.seed,
        batch_size=args.batch_size,
        batch_evaluator=batch_evaluator,
        virtual_loss=args.virtual_loss,
    )
    if pr is not None:
        pr.disable()
    dt = time.perf_counter() - t0

    n_plies = len(ds)
    print(
        f"played 1 game: {n_plies} plies in {dt:.1f}s "
        f"({dt / max(n_plies, 1):.3f}s/ply)",
        flush=True,
    )

    if pr is None:
        print("(no-profile mode: wallclock only, no .prof dump)", flush=True)
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pr.dump_stats(str(args.out))
    print(f"raw profile: {args.out}", flush=True)

    # Top-N summaries: tottime (self-time only) is what tells you where to
    # optimize; cumtime is what tells you which call sites drive that.
    buf = io.StringIO()
    buf.write(
        f"=== mcts profile (1 self-play game, sims={args.sims}, "
        f"batch_size={args.batch_size}) ===\n"
        f"wallclock: {dt:.2f}s   plies: {n_plies}   "
        f"s/ply: {dt / max(n_plies, 1):.3f}\n\n"
    )
    st = pstats.Stats(pr, stream=buf)
    st.strip_dirs()

    buf.write("--- TOP 40 by TOTTIME (self-time; where the CPU actually is) ---\n")
    st.sort_stats("tottime").print_stats(40)

    buf.write("\n--- TOP 40 by CUMTIME (cumulative; which call sites drive cost) ---\n")
    st.sort_stats("cumulative").print_stats(40)

    args.top.write_text(buf.getvalue())
    print(f"top-40 summary: {args.top}", flush=True)
    print("\n=== HEAD OF SUMMARY ===")
    print(buf.getvalue()[:3500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
