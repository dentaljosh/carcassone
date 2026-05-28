"""Optuna search over eval-time hyperparameters.

Wraps eval_iter_head_to_head.py as a TPE objective. Each trial tests a
suggested (c_puct, leaf_cap, leaf_variant) tuple against a fixed baseline
(c=1.5, cap=12, variant=v2_7), starting at n=100 (screen) and promoting to
n=400 (verify) if elo_delta >= +15. Same checkpoint both sides (iter_B1).

CURRENT STATE — single-box per trial. Each trial runs eval on the 5800X
alone (W=14), no shared-claim. ~20 min per screen trial, ~50 min if promoted.
20 trials → ~7h baseline, more with promotions.

DEFERRED — DUAL-BOX TRIAL DISPATCH for ~2.5× speedup per trial:
  - Add --shared-claim --claim-host 5800x-trial${N} to the 5800X subprocess
  - Also ssh-launch xeon-side eval_iter_head_to_head with matching flags
    (mirror phase3_sequencer.sh::run_job pattern)
  - Wait-loop on trial_dir for n_games JSONs (laptop joining is the same
    pattern via /home/doctor/laptop_cluster_lib.sh::launch_laptop_eval)
  - Cleanup both processes when trial complete
  Trade: more code, but trial wallclock 20m → 8m. Worth doing after we
  confirm the basic study converges sensibly.

DEFERRED — DISTRIBUTED OPTUNA (parallel trials across boxes):
  Easier than dual-box-per-trial. Each box runs its own optuna study worker
  against the shared SQLite (or postgres) DB. TPE works fine concurrently —
  trials inform each other via the DB. But: SQLite over CIFS-over-tailscale
  has known locking issues. Either (a) keep SQLite on 5800X and run all
  workers from 5800X by ssh'ing into each box per trial, or (b) switch to
  postgres backend on 5800X (extra setup but clean). Postpone until we have
  a reason to want > 2x search throughput.

Usage:
    .venv/bin/python scripts/optuna_eval_search.py --n-trials 20

Storage: SQLite at /mnt/c/carc-shared/optuna_runs/study.db.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import optuna

REPO = Path("/home/doctor/projects/carcassone")
OPTUNA_OUT = Path("/mnt/c/carc-shared/optuna_runs")
BASELINE_CKPT = REPO / "checkpoints/v25_retrain_optionB_iter1/iter_00.pt"

# Baseline reference (current production config)
BASELINE_C_PUCT = 1.5
BASELINE_LEAF_CAP = 12.0
BASELINE_LEAF_VARIANT = "v2_7"

# Multi-fidelity tiers — trials start at SCREEN_N games; promising trials
# are re-run with PROMOTE_N games (work-stealing skips cached seeds, so this
# only plays PROMOTE_N - SCREEN_N more games).
SCREEN_N = 100        # 1σ ≈ ±17 elo
PROMOTE_N = 400       # 1σ ≈ ±9 elo
PROMOTE_THRESHOLD = 15.0  # promote if screen elo >= +15 (~1σ above zero at n=100)


def _run_eval(trial_dir: Path, seed_start: int, games: int, c_puct: float,
              leaf_cap: int, leaf_variant: str) -> dict:
    """Run one eval_iter_head_to_head invocation and return its elo_log entry."""
    cmd = [
        str(REPO / ".venv/bin/python"),
        "-u",
        str(REPO / "scripts/eval_iter_head_to_head.py"),
        "--new-checkpoint", str(BASELINE_CKPT),
        "--old-checkpoint", str(BASELINE_CKPT),
        "--output-root", str(trial_dir),
        "--iter", "1", "--vs-iter", "1",
        "--seed-start", str(seed_start),
        "--games", str(games),
        "--sims", "200",
        "--c-puct", str(BASELINE_C_PUCT),  # required, overridden per-side
        "--leaf-eval", "v2_5",
        "--workers", "14",
        "--orchestrator",
        # NEW side gets the suggested config
        "--new-c-puct", str(c_puct),
        "--new-leaf-cap", str(float(leaf_cap)),
        "--new-leaf-variant", leaf_variant,
        # OLD side stays at baseline
        "--old-c-puct", str(BASELINE_C_PUCT),
        "--old-leaf-cap", str(BASELINE_LEAF_CAP),
        "--old-leaf-variant", BASELINE_LEAF_VARIANT,
    ]
    env = {
        **os.environ,
        "CARCASSONNE_V25_DROP_THREE_OPEN": "1",
        "CARCASSONNE_V25_CAP": "12",
    }
    result = subprocess.run(cmd, env=env, cwd=str(REPO))
    if result.returncode != 0:
        raise RuntimeError(f"eval failed (rc={result.returncode})")

    elo_log = trial_dir / "elo_log.json"
    with open(elo_log) as fh:
        entries = json.load(fh)
    return entries[-1]


def objective(trial: optuna.Trial) -> float:
    """One trial = screen at SCREEN_N, promote to PROMOTE_N if promising.
    Returns elo_delta (maximize). 1σ on screen ≈ ±17 elo; 1σ on promotion ≈ ±9."""
    c_puct = trial.suggest_float("c_puct", 1.5, 5.0, step=0.25)
    leaf_cap = trial.suggest_int("leaf_cap", 8, 20)
    leaf_variant = trial.suggest_categorical(
        "leaf_variant", ["v2_7", "tile_counting", "tile_counting_cont"]
    )

    trial_dir = OPTUNA_OUT / f"trial_{trial.number:04d}"
    trial_dir.mkdir(parents=True, exist_ok=True)

    # Unique seed range per trial: avoids cross-trial cache hits.
    # Trial seeds span [seed_start, seed_start + PROMOTE_N) so promotion
    # re-runs against the same start and only fills in the remaining games.
    seed_start = 1_000_000 + trial.number * 1000

    # --- Tier 1: screen at SCREEN_N games ---
    screen = _run_eval(trial_dir, seed_start, SCREEN_N, c_puct, leaf_cap, leaf_variant)
    screen_elo = float(screen["elo_delta"])
    trial.set_user_attr("screen_elo", screen_elo)
    trial.set_user_attr("screen_n", SCREEN_N)

    # --- Tier 2: promote if promising (>= threshold) ---
    if screen_elo >= PROMOTE_THRESHOLD:
        promoted = _run_eval(trial_dir, seed_start, PROMOTE_N, c_puct, leaf_cap, leaf_variant)
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

    # Stash suggested params alongside for later inspection
    trial.set_user_attr("c_puct", c_puct)
    trial.set_user_attr("leaf_cap", leaf_cap)
    trial.set_user_attr("leaf_variant", leaf_variant)

    return elo_delta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=20)
    ap.add_argument(
        "--study-name", default="eval_time_search_v1",
        help="Optuna study identifier in the SQLite DB",
    )
    args = ap.parse_args()

    OPTUNA_OUT.mkdir(parents=True, exist_ok=True)
    storage = f"sqlite:///{OPTUNA_OUT}/study.db"

    study = optuna.create_study(
        study_name=args.study_name,
        storage=storage,
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
        load_if_exists=True,
    )
    study.optimize(objective, n_trials=args.n_trials)

    print(f"\n=== Study complete: {len(study.trials)} trials ===")
    print(f"Best elo_delta: {study.best_value:+.1f}")
    print(f"Best params: {study.best_params}")
    print(f"\nTop 5 trials:")
    sorted_trials = sorted(
        study.trials, key=lambda t: (t.value if t.value is not None else -1e9), reverse=True
    )
    for t in sorted_trials[:5]:
        print(f"  #{t.number}: elo {t.value:+.1f}  params={t.params}")


if __name__ == "__main__":
    main()
