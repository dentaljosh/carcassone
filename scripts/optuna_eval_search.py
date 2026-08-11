"""Optuna search over eval-time hyperparameters.

Wraps eval_iter_head_to_head.py as a TPE objective. Each trial tests a
suggested (c_puct, leaf_cap, leaf_variant) tuple against a fixed baseline
(c=1.5, cap=12, variant=v2_7), starting at n=100 (screen) and promoting to
n=400 (verify) if elo_delta >= +15. Same checkpoint both sides (iter_B1).

DISTRIBUTED PATTERN (2026-05-28):
  Each box runs its own worker process pointed at the SAME shared SQLite
  study DB on /mnt/c/carc-shared/optuna_runs/. Optuna handles trial
  assignment + locking. Each trial pulls one (c_puct, leaf_cap, leaf_variant)
  tuple, runs single-box eval, reports result. Box-level parallelism — 2
  boxes = 2 trials in flight, scales linearly with added workers (laptop
  joins by ssh'ing in another worker pointed at the same DB).

  Box-specific paths are passed via CLI flags (--repo, --baseline-ckpt,
  --output-root, --storage, --workers, --worker-id) so each box uses its
  own filesystem layout while writing to the shared study.

Usage:
    # 5800X worker:
    .venv/bin/python scripts/optuna_eval_search.py \\
        --repo /home/doctor/projects/carcassone \\
        --baseline-ckpt /mnt/c/carc-shared/checkpoints/iter_B1.pt \\
        --output-root /mnt/c/carc-shared/optuna_runs \\
        --storage sqlite:////mnt/c/carc-shared/optuna_runs/study.db \\
        --workers 14 --worker-id 5800x --n-trials 20

    # Xeon worker (via /home/doctor/launch_xeon_optuna.sh which self-heals
    # the CIFS mount first):
    --repo /home/doctor/projects/carcassone \\
        --baseline-ckpt /mnt/carc-shared/checkpoints/iter_B1.pt \\
        --output-root /mnt/carc-shared/optuna_runs \\
        --storage sqlite:////mnt/carc-shared/optuna_runs/study.db \\
        --workers 10 --worker-id xeon --n-trials 20

Each box runs `n_trials` total — n_trials should be the GLOBAL trial budget
divided across boxes (e.g. 20 total = 10 per box on 2 boxes). Optuna's TPE
sampler benefits from trials informing each other via the shared DB.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import zlib
from pathlib import Path

import optuna

# Baseline reference (current production config)
BASELINE_C_PUCT = 1.5
BASELINE_LEAF_CAP = 12.0
BASELINE_LEAF_VARIANT = "v2_7"

# Multi-fidelity tiers — trials start at SCREEN_N games; promising trials
# are re-run with PROMOTE_N games (work-stealing skips cached seeds, so this
# only plays PROMOTE_N - SCREEN_N more games).
SCREEN_N = 100        # 1sigma ~= +/-17 elo
PROMOTE_N = 400       # 1sigma ~= +/-9 elo
PROMOTE_THRESHOLD = 15.0  # promote if screen elo >= +15 (~1sigma above zero at n=100)


def _run_eval(
    repo: Path,
    baseline_ckpt: Path,
    trial_dir: Path,
    seed_start: int,
    games: int,
    c_puct: float,
    leaf_cap: int,
    leaf_variant: str,
    workers: int,
) -> dict:
    """Run one eval_iter_head_to_head invocation and return its elo_log entry."""
    cmd = [
        str(repo / ".venv/bin/python"),
        "-u",
        str(repo / "scripts/eval_iter_head_to_head.py"),
        "--new-checkpoint", str(baseline_ckpt),
        "--old-checkpoint", str(baseline_ckpt),
        "--output-root", str(trial_dir),
        "--iter", "1", "--vs-iter", "1",
        "--seed-start", str(seed_start),
        "--games", str(games),
        "--sims", "200",
        "--c-puct", str(BASELINE_C_PUCT),
        "--leaf-eval", "v2_5",
        "--workers", str(workers),
        "--orchestrator",
        "--new-c-puct", str(c_puct),
        "--new-leaf-cap", str(float(leaf_cap)),
        "--new-leaf-variant", leaf_variant,
        "--old-c-puct", str(BASELINE_C_PUCT),
        "--old-leaf-cap", str(BASELINE_LEAF_CAP),
        "--old-leaf-variant", BASELINE_LEAF_VARIANT,
    ]
    env = {
        **os.environ,
        "CARCASSONNE_V25_DROP_THREE_OPEN": "1",
        "CARCASSONNE_V25_CAP": "12",
    }
    result = subprocess.run(cmd, env=env, cwd=str(repo))
    if result.returncode != 0:
        raise RuntimeError(f"eval failed (rc={result.returncode})")

    elo_log = trial_dir / "elo_log.json"
    with open(elo_log) as fh:
        entries = json.load(fh)
    return entries[-1]


def make_objective(repo: Path, baseline_ckpt: Path, output_root: Path,
                   workers: int, worker_id: str):
    def objective(trial: optuna.Trial) -> float:
        c_puct = trial.suggest_float("c_puct", 1.5, 5.0, step=0.25)
        leaf_cap = trial.suggest_int("leaf_cap", 8, 20)
        leaf_variant = trial.suggest_categorical(
            "leaf_variant", ["v2_7", "tile_counting", "tile_counting_cont"]
        )

        # Per-trial dir tagged with worker_id so concurrent workers don't
        # collide on the same output path (different boxes have different
        # filesystem roots but the shared mount is one folder).
        trial_dir = output_root / f"trial_{trial.number:04d}_{worker_id}"
        trial_dir.mkdir(parents=True, exist_ok=True)

        # Unique seed range per trial (shared across promotion tiers so
        # promote re-uses screen games via the resume cache).
        seed_start = 1_000_000 + trial.number * 1000

        screen = _run_eval(
            repo, baseline_ckpt, trial_dir, seed_start, SCREEN_N,
            c_puct, leaf_cap, leaf_variant, workers,
        )
        screen_elo = float(screen["elo_delta"])
        trial.set_user_attr("worker_id", worker_id)
        trial.set_user_attr("screen_elo", screen_elo)
        trial.set_user_attr("screen_n", SCREEN_N)

        if screen_elo >= PROMOTE_THRESHOLD:
            promoted = _run_eval(
                repo, baseline_ckpt, trial_dir, seed_start, PROMOTE_N,
                c_puct, leaf_cap, leaf_variant, workers,
            )
            elo_delta = float(promoted["elo_delta"])
            trial.set_user_attr("promoted", True)
            trial.set_user_attr("promote_n", PROMOTE_N)
            trial.set_user_attr("wins", int(promoted["wins"]))
            trial.set_user_attr("losses", int(promoted["losses"]))
            trial.set_user_attr("draws", int(promoted["draws"]))
        else:
            elo_delta = screen_elo
            trial.set_user_attr("promoted", False)
            trial.set_user_attr("wins", int(screen["wins"]))
            trial.set_user_attr("losses", int(screen["losses"]))
            trial.set_user_attr("draws", int(screen["draws"]))

        trial.set_user_attr("c_puct", c_puct)
        trial.set_user_attr("leaf_cap", leaf_cap)
        trial.set_user_attr("leaf_variant", leaf_variant)
        return elo_delta
    return objective


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True,
                    help="Path to carcassone repo on this box.")
    ap.add_argument("--baseline-ckpt", type=Path, required=True,
                    help="Path to iter_B1 checkpoint on this box's shared mount.")
    ap.add_argument("--output-root", type=Path, required=True,
                    help="Directory for per-trial output (typically the shared mount's optuna_runs/).")
    ap.add_argument("--storage", required=True,
                    help="Optuna storage URL, e.g. sqlite:////mnt/c/carc-shared/optuna_runs/study.db")
    ap.add_argument("--workers", type=int, required=True,
                    help="Worker count for eval_iter_head_to_head (per-box optimum).")
    ap.add_argument("--worker-id", default=socket.gethostname(),
                    help="Identifier tagged onto trial output dirs to avoid cross-box collisions.")
    ap.add_argument("--n-trials", type=int, default=20,
                    help="Trials this worker should pull from the study (across boxes, sum to global budget).")
    ap.add_argument("--study-name", default="eval_time_search_v1",
                    help="Optuna study identifier in the shared SQLite DB.")
    args = ap.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)

    # Per-worker seed: deterministic but unique per box, so the TPE sampler's
    # prior-sample sequence differs between workers (avoids the seed-collision
    # bug seen 2026-05-28 where 3 trials all sampled the same first-prior point).
    # 5800X stays on seed=42 for back-compat; others derive from worker_id.
    if args.worker_id == "5800x":
        sampler_seed = 42
    else:
        sampler_seed = 42 + (zlib.crc32(args.worker_id.encode()) & 0x7FFFFFFF)
    print(f"  [optuna] worker={args.worker_id}  sampler_seed={sampler_seed}")

    study = optuna.create_study(
        study_name=args.study_name,
        storage=args.storage,
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=sampler_seed),
        load_if_exists=True,
    )
    obj = make_objective(
        args.repo, args.baseline_ckpt, args.output_root,
        args.workers, args.worker_id,
    )
    study.optimize(obj, n_trials=args.n_trials)

    print(f"\n=== Worker {args.worker_id}: {args.n_trials} trials done. Study has {len(study.trials)} trials total ===")
    print(f"Global best elo_delta: {study.best_value:+.1f}")
    print(f"Global best params: {study.best_params}")
    print(f"\nTop 5 trials (global):")
    sorted_trials = sorted(
        study.trials, key=lambda t: (t.value if t.value is not None else -1e9), reverse=True
    )
    for t in sorted_trials[:5]:
        wid = t.user_attrs.get("worker_id", "?")
        print(f"  #{t.number} ({wid}): elo {t.value:+.1f}  params={t.params}")


if __name__ == "__main__":
    main()
