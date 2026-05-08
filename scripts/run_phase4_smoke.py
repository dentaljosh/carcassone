"""Phase 4 outer loop: orchestrates self-play → train → head-to-head per iter.

Resumable across iterations: re-running with the same `--output-root` skips
any iter whose self-play games, checkpoint, and ELO entry are already on
disk. Per-game checkpointing lives inside each step.

Detached run (recommended):
  nohup python -u scripts/run_phase4_smoke.py \\
      --iters 5 --games 25 --sims 25 --eval-sims 50 --eval-games 10 \\
      --workers 7 --output-root data/selfplay/smoke_v1 \\
      > /tmp/phase4_smoke.log 2>&1 & disown
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SELFPLAY_CKPT_ROOT = REPO_ROOT / "checkpoints" / "selfplay"
WARMSTART_CANONICAL = REPO_ROOT / "checkpoints" / "warmstart_canonical.pt"
WARMSTART_DATA = REPO_ROOT / "data" / "warmstart" / "heuristic_tau05"
SCRIPTS = REPO_ROOT / "scripts"


def _checkpoint_path(iter_idx: int) -> Path:
    return SELFPLAY_CKPT_ROOT / f"iter_{iter_idx:02d}.pt"


def _warm_from_for(iter_idx: int) -> Path:
    """At iter 0 the warm-start is the canonical Phase-3 checkpoint;
    afterwards it's the previous iteration's saved checkpoint."""
    if iter_idx == 0:
        return WARMSTART_CANONICAL
    return _checkpoint_path(iter_idx - 1)


def _mix_fraction_for(iter_idx: int, schedule: list[float]) -> float:
    """Index into the schedule by iter; clamp to the last value if iter is
    past the schedule's end."""
    if iter_idx < len(schedule):
        return schedule[iter_idx]
    return schedule[-1]


def _run_subcommand(name: str, cmd: list[str]) -> None:
    """Run a subcommand inheriting stdout/stderr; raise on non-zero exit."""
    print(f"\n=== {name} ===")
    print("  " + " ".join(str(c) for c in cmd))
    sys.stdout.flush()
    rc = subprocess.call(cmd)
    if rc != 0:
        raise RuntimeError(f"{name} failed with exit code {rc}")


def _elo_log_has_iter(output_root: Path, iter_idx: int) -> bool:
    log_path = output_root / "elo_log.json"
    if not log_path.exists():
        return False
    with log_path.open() as fh:
        entries = json.load(fh)
    return any(e["iter"] == iter_idx for e in entries)


def _selfplay_iter_complete(output_root: Path, iter_idx: int, target_games: int) -> bool:
    iter_dir = output_root / f"iter_{iter_idx:02d}"
    if not iter_dir.exists():
        return False
    return len(list(iter_dir.glob("seed_*.npz"))) >= target_games


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run_phase4_smoke")
    p.add_argument("--iters", type=int, required=True,
                   help="Number of iterations to run (the outer loop budget).")
    p.add_argument("--games", type=int, default=25,
                   help="Self-play games per iter.")
    p.add_argument("--sims", type=int, default=25,
                   help="NeuralMCTS sims per move during self-play.")
    p.add_argument("--eval-sims", type=int, default=50,
                   help="NeuralMCTS sims per move during head-to-head.")
    p.add_argument("--eval-games", type=int, default=10,
                   help="Games per head-to-head match.")
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--dirichlet-alpha", type=float, default=0.3)
    p.add_argument("--dirichlet-eps", type=float, default=0.25)
    p.add_argument("--temp-threshold", type=int, default=15)
    p.add_argument("--window", type=int, default=10,
                   help="Replay-buffer window: last K iters' games.")
    p.add_argument(
        "--warmstart-mix-schedule",
        type=str,
        default="1.0,0.7,0.4,0.0",
        help="Comma-separated list. Element i is the warmstart-mix fraction "
             "at iter i. Clamps to the last value at higher iters. "
             "Default: 1.0 → 0.7 → 0.4 → 0.0...",
    )
    p.add_argument("--epochs", type=int, default=3,
                   help="Training epochs per iter.")
    p.add_argument("--workers", type=int, default=7,
                   help="Pool workers for self-play (default 7 — leaves SMT "
                        "headroom for other workloads on the 5800X). "
                        "Eval/head-to-head uses --eval-workers.")
    p.add_argument("--eval-workers", type=int, default=4,
                   help="Pool workers for head-to-head (CUDA caps to 4 "
                        "unless --no-cuda-cap is set).")
    p.add_argument(
        "--no-cuda-cap", action="store_true",
        help="Lift the 4-worker CUDA cap on both self-play and head-to-head. "
             "Pass through to the underlying scripts.",
    )
    p.add_argument("--output-root", type=Path, required=True,
                   help="Root for self-play data + ELO log.")
    args = p.parse_args(argv)

    args.output_root.mkdir(parents=True, exist_ok=True)
    SELFPLAY_CKPT_ROOT.mkdir(parents=True, exist_ok=True)

    schedule = [float(x) for x in args.warmstart_mix_schedule.split(",")]
    print(
        f"Phase 4 smoke: iters={args.iters}, games/iter={args.games}, "
        f"sims={args.sims}, eval_sims={args.eval_sims}, "
        f"eval_games={args.eval_games}, workers={args.workers}, "
        f"output_root={args.output_root}"
    )
    print(f"  warmstart-mix schedule: {schedule}")
    print(f"  warm-from at iter 0: {WARMSTART_CANONICAL}")
    sys.stdout.flush()

    overall_t0 = time.perf_counter()
    for iter_idx in range(args.iters):
        iter_t0 = time.perf_counter()
        warm_from = _warm_from_for(iter_idx)
        if not warm_from.exists():
            print(f"\nERROR: warm-from checkpoint missing: {warm_from}",
                  file=sys.stderr)
            return 1

        # Step 1: self-play (skip if already done)
        if _selfplay_iter_complete(args.output_root, iter_idx, args.games):
            print(f"\n[iter {iter_idx}] self-play already complete — skipping")
        else:
            _run_subcommand(
                f"iter {iter_idx}: self-play",
                [
                    sys.executable, "-u", str(SCRIPTS / "run_selfplay_iter.py"),
                    "--checkpoint", str(warm_from),
                    "--output-root", str(args.output_root),
                    "--iter", str(iter_idx),
                    "--games", str(args.games),
                    "--sims", str(args.sims),
                    "--c-puct", str(args.c_puct),
                    "--dirichlet-alpha", str(args.dirichlet_alpha),
                    "--dirichlet-eps", str(args.dirichlet_eps),
                    "--temp-threshold", str(args.temp_threshold),
                    "--workers", str(args.workers),
                    *(["--no-cuda-cap"] if args.no_cuda_cap else []),
                ],
            )

        # Step 2: train
        ckpt_out = _checkpoint_path(iter_idx)
        if ckpt_out.exists():
            print(f"\n[iter {iter_idx}] checkpoint exists — skipping training: {ckpt_out}")
        else:
            mix = _mix_fraction_for(iter_idx, schedule)
            _run_subcommand(
                f"iter {iter_idx}: train (warmstart_mix={mix:.2f})",
                [
                    sys.executable, "-u", str(SCRIPTS / "train_iter.py"),
                    "--output-root", str(args.output_root),
                    "--warmstart-root", str(WARMSTART_DATA),
                    "--iter", str(iter_idx),
                    "--window", str(args.window),
                    "--warmstart-mix-fraction", str(mix),
                    "--warm-from", str(warm_from),
                    "--output", str(ckpt_out),
                    "--epochs", str(args.epochs),
                ],
            )

        # Step 3: head-to-head vs prev iter (skip iter 0; nothing to compare to)
        if iter_idx == 0:
            print(f"\n[iter {iter_idx}] no prior iter — skipping head-to-head")
        elif _elo_log_has_iter(args.output_root, iter_idx):
            print(f"\n[iter {iter_idx}] ELO log entry exists — skipping head-to-head")
        else:
            _run_subcommand(
                f"iter {iter_idx}: head-to-head vs iter {iter_idx - 1}",
                [
                    sys.executable, "-u", str(SCRIPTS / "eval_iter_head_to_head.py"),
                    "--new-checkpoint", str(ckpt_out),
                    "--old-checkpoint", str(_checkpoint_path(iter_idx - 1)),
                    "--output-root", str(args.output_root),
                    "--iter", str(iter_idx),
                    "--vs-iter", str(iter_idx - 1),
                    "--games", str(args.eval_games),
                    "--sims", str(args.eval_sims),
                    "--c-puct", str(args.c_puct),
                    "--workers", str(args.eval_workers),
                    *(["--no-cuda-cap"] if args.no_cuda_cap else []),
                ],
            )

        iter_elapsed = time.perf_counter() - iter_t0
        print(f"\n[iter {iter_idx}] complete in {iter_elapsed/60:.1f} min")
        sys.stdout.flush()

    overall = time.perf_counter() - overall_t0
    print(f"\n=== Phase 4 smoke done: {args.iters} iters in {overall/60:.1f} min ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
