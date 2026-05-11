"""Generate one iteration's worth of self-play games for Phase 4.

Per-game `.npz` checkpointing under `data/selfplay/<run>/iter_NN/seed_NNNNNN.npz`
— same schema as warmstart, so the streaming dataset / IO machinery is
reused unchanged.

Resumable: rerunning with the same args skips already-cached seeds. To
wipe and start over: `--reset`.

Workers default to 7 to leave SMT headroom for other workloads on the 5800X.

Usage:
  python -u scripts/run_selfplay_iter.py \\
      --checkpoint checkpoints/warmstart_canonical.pt \\
      --output-root data/selfplay/calibration \\
      --iter 0 --games 10 --sims 25 --workers 7

Detached (recommended for long iters):
  nohup python -u scripts/run_selfplay_iter.py [...] \\
      > /tmp/selfplay_iter00.log 2>&1 & disown
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.evaluators import (
    make_batch_evaluator,
    make_single_evaluator,
)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.selfplay import play_one_selfplay_game
from carcassonne_ai.warmstart import GameDataset


REPO_ROOT = Path(__file__).resolve().parent.parent


# Per-worker globals. CUDA can't survive forks, so the Pool uses 'spawn'
# context and each worker re-loads the checkpoint exactly once on init.
_worker_net: CarcassonneNet | None = None
_worker_device: torch.device | None = None
_worker_cfg: dict | None = None


def _worker_init(checkpoint_path: str, cfg: dict) -> None:
    global _worker_net, _worker_device, _worker_cfg
    _worker_device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    ckpt = torch.load(
        checkpoint_path, map_location=_worker_device, weights_only=False
    )
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
    ).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net
    _worker_cfg = cfg


def _seed_for(iter_idx: int, game_idx: int) -> int:
    # Reproducible seeds; iter_idx * 10_000 leaves room for 10K games/iter.
    return iter_idx * 10_000 + game_idx


def _result_path(out_dir: Path, seed: int) -> Path:
    return out_dir / f"seed_{seed:06d}.npz"


def _play_one_pool(args: tuple[int, str]) -> tuple[int, str, int]:
    """Worker entry: skip if cached, else play one self-play game and save."""
    seed, out_dir_str = args
    out_dir = Path(out_dir_str)
    path = _result_path(out_dir, seed)
    if path.exists():
        try:
            ds = GameDataset.load(path)
            return seed, "cached", len(ds)
        except Exception:
            path.unlink(missing_ok=True)

    cfg = _worker_cfg
    assert cfg is not None and _worker_net is not None and _worker_device is not None

    game = Game(enable_legal_moves_cache=True)
    use_fp16 = cfg.get("use_fp16", False)
    evaluator = make_single_evaluator(
        _worker_net, _worker_device, game, use_fp16=use_fp16
    )
    batch_evaluator = None
    if cfg["batch_size"] > 1:
        batch_evaluator = make_batch_evaluator(
            _worker_net, _worker_device, game, use_fp16=use_fp16
        )
    try:
        ds = play_one_selfplay_game(
            game=game,
            evaluator=evaluator,
            sims=cfg["sims"],
            c_puct=cfg["c_puct"],
            dirichlet_alpha=cfg["dirichlet_alpha"],
            dirichlet_eps=cfg["dirichlet_eps"],
            temp_threshold=cfg["temp_threshold"],
            seed=seed,
            batch_size=cfg["batch_size"],
            batch_evaluator=batch_evaluator,
            virtual_loss=cfg["virtual_loss"],
        )
    except Exception as e:
        # Engine edge cases (e.g. farm_util IndexError seen 2026-05-10) shouldn't
        # nuke the whole iter. Log + skip; a missing seed file just means less
        # training data for this iter, not a corrupt buffer.
        import traceback
        sys.stderr.write(
            f"\n[seed {seed}] selfplay FAILED: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}\n"
        )
        sys.stderr.flush()
        return seed, "failed", 0
    ds.save(path)
    return seed, "fresh", len(ds)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run_selfplay_iter")
    p.add_argument("--checkpoint", type=Path, required=True,
                   help="Network checkpoint to use as the self-play opponent.")
    p.add_argument("--output-root", type=Path, required=True,
                   help="Root dir for self-play data; per-iter subdirs created.")
    p.add_argument("--iter", type=int, required=True, dest="iter_idx",
                   help="Iteration index (used in the seed prefix and subdir name).")
    p.add_argument("--games", type=int, default=25,
                   help="Number of self-play games to generate (default 25).")
    p.add_argument("--sims", type=int, default=25,
                   help="NeuralMCTS simulations per move (default 25).")
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--dirichlet-alpha", type=float, default=0.3)
    p.add_argument("--dirichlet-eps", type=float, default=0.25)
    p.add_argument("--temp-threshold", type=int, default=15)
    p.add_argument(
        "--batch-size", type=int, default=1,
        help="NeuralMCTS batch size for virtual-loss / batched-eval mode. "
             "1 (default) = serial. >1 = collect K leaves per batch and "
             "evaluate them in a single GPU forward pass. Typical: 8.",
    )
    p.add_argument(
        "--virtual-loss", type=float, default=1.0,
        help="PUCT W-penalty applied to in-flight nodes during batched "
             "selection. Only matters when --batch-size > 1.",
    )
    p.add_argument(
        "--workers", type=int, default=8,
        help="Pool workers. Default 8 leaves SMT headroom for other "
             "workloads on a 5800X. For dedicated runs, W=16 is the "
             "empirical local optimum (1 worker per SMT thread; saturates "
             "GPU queue without CPU-side preemption — measured 2026-05-09 "
             "on RTX 5060 Ti, ~20%% faster than W=8).",
    )
    p.add_argument(
        "--fp16", action="store_true",
        help="Run network forward passes under torch.amp.autocast(fp16) on "
             "CUDA. Master weights stay fp32 (inference-only autocast). "
             "Typical 1.5-2× speedup on Blackwell/Ada Tensor Cores. "
             "No-op on CPU. Default off for backward compat.",
    )
    p.add_argument("--reset", action="store_true",
                   help="Wipe the iter subdir before starting.")
    p.add_argument("--summary-only", action="store_true",
                   help="Just count what's on disk; do not play.")
    args = p.parse_args(argv)

    iter_dir = args.output_root / f"iter_{args.iter_idx:02d}"

    if args.summary_only:
        if not iter_dir.exists():
            print(f"No data at {iter_dir}")
            return 0
        files = sorted(iter_dir.glob("seed_*.npz"))
        n_pos = 0
        for f in files:
            try:
                ds = GameDataset.load(f)
                n_pos += len(ds)
            except Exception as e:
                print(f"  load failed: {f.name}: {e}")
        print(f"{iter_dir}: {len(files)} games, {n_pos} positions")
        return 0

    if args.reset and iter_dir.exists():
        shutil.rmtree(iter_dir)
        print(f"Wiped {iter_dir}")
    iter_dir.mkdir(parents=True, exist_ok=True)

    seeds = [_seed_for(args.iter_idx, i) for i in range(args.games)]
    pool_args = [(s, str(iter_dir)) for s in seeds]
    already = sum(1 for s in seeds if _result_path(iter_dir, s).exists())
    remaining = args.games - already

    # Auto-cap removed 2026-05-09: empirical bench (W={4,8,12,16,20}) on
    # RTX 5060 Ti showed W=16 actually beats W=4 by ~2× (vs. the old cap
    # logic which forced W≤4 for "GPU thrash safety"). The driver-level
    # GPU queue self-regulates — more workers fill the queue more cleanly,
    # they don't thrash. Cap your workers explicitly via --workers if you
    # need to leave CPU/GPU headroom for other workloads.
    n_workers = min(args.workers, remaining or 1)

    cfg = {
        "sims": args.sims,
        "c_puct": args.c_puct,
        "dirichlet_alpha": args.dirichlet_alpha,
        "dirichlet_eps": args.dirichlet_eps,
        "temp_threshold": args.temp_threshold,
        "batch_size": args.batch_size,
        "virtual_loss": args.virtual_loss,
        "use_fp16": args.fp16,
    }
    print(
        f"selfplay iter={args.iter_idx}: {args.games} games "
        f"(sims={args.sims}, c_puct={args.c_puct}, "
        f"alpha={args.dirichlet_alpha}, eps={args.dirichlet_eps}, "
        f"temp_thresh={args.temp_threshold}, "
        f"batch_size={args.batch_size}, vloss={args.virtual_loss}), "
        f"{n_workers} workers, {already} cached, {remaining} to play, "
        f"out={iter_dir}"
    )
    sys.stdout.flush()

    if remaining == 0:
        print("All games cached; nothing to do.")
        return 0

    t0 = time.perf_counter()
    fresh = 0
    cached = 0
    failed = 0
    n_pos_total = 0
    first_fresh_t: float | None = None
    ctx = mp.get_context("spawn")
    with ctx.Pool(
        processes=n_workers,
        initializer=_worker_init,
        initargs=(str(args.checkpoint), cfg),
    ) as pool:
        for done, (seed, status, n_positions) in enumerate(
            pool.imap_unordered(_play_one_pool, pool_args, chunksize=1), 1
        ):
            n_pos_total += n_positions
            if status == "fresh":
                fresh += 1
                if first_fresh_t is None:
                    first_fresh_t = time.perf_counter()
                    elapsed = first_fresh_t - t0
                    eta_min = (remaining * elapsed / n_workers) / 60.0
                    print(
                        f"  [ETA] first fresh game took {elapsed:.0f}s; "
                        f"~{eta_min:.1f} min for {remaining} fresh"
                    )
                    sys.stdout.flush()
            elif status == "failed":
                failed += 1
            else:
                cached += 1
            if done % max(1, args.games // 10) == 0 or done == args.games:
                print(
                    f"  ... {done}/{args.games} done "
                    f"(fresh={fresh}, cached={cached}, failed={failed})"
                )
                sys.stdout.flush()
    elapsed = time.perf_counter() - t0
    print(
        f"\nDone iter={args.iter_idx}: {fresh} fresh + {cached} cached + "
        f"{failed} failed = {fresh + cached + failed} games attempted, "
        f"{n_pos_total} positions, {elapsed:.1f}s wallclock"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
