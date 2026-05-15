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
WARMSTART_CANONICAL = REPO_ROOT / "checkpoints" / "warmstart_canonical.pt"
WARMSTART_DATA = REPO_ROOT / "data" / "warmstart" / "heuristic_tau05"
SCRIPTS = REPO_ROOT / "scripts"

# Anchor-gate eval uses --vs-iter 9999 as a sentinel (real iters never
# reach 4 digits in our scope) so the eval_dir naming
# `eval/iter_NN_vs_9999/` doesn't collide with chain head-to-heads.
ANCHOR_VS_ITER_SENTINEL = 9999


def _checkpoint_path(checkpoint_root: Path, iter_idx: int) -> Path:
    return checkpoint_root / f"iter_{iter_idx:02d}.pt"


def _warm_from_for(
    checkpoint_root: Path, iter_idx: int, initial_checkpoint: Path
) -> Path:
    """At iter 0 the warm-start is `initial_checkpoint` (defaults to
    warmstart_canonical.pt for the original Phase-4 recipe; v6+ recipes
    override this to bootstrap from a prior trained checkpoint).
    Afterwards it's the previous iteration's saved checkpoint."""
    if iter_idx == 0:
        return initial_checkpoint
    return _checkpoint_path(checkpoint_root, iter_idx - 1)


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


def _tally_anchor_eval_dir(
    eval_dir: Path, sims: int, n_games: int
) -> tuple[int, int, int] | None:
    """Tally W/D/L from the per-game JSONs eval_iter_head_to_head.py wrote.
    Returns (wins, draws, losses) for the new checkpoint; None if fewer than
    n_games results have landed."""
    pattern = f"s{sims:04d}_seed*_p*.json"
    files = sorted(eval_dir.glob(pattern))
    if len(files) < n_games:
        return None
    wins = draws = losses = 0
    for f in files[:n_games]:
        with f.open() as fh:
            r = json.load(fh)
        if r.get("won_by_new"):
            wins += 1
        elif r.get("drew"):
            draws += 1
        else:
            losses += 1
    return wins, draws, losses


def _append_anchor_gate_log(
    output_root: Path, iter_idx: int, anchor_path: Path,
    wins: int, draws: int, losses: int, threshold: float,
) -> dict:
    log_path = output_root / "anchor_gate_log.json"
    entries: list[dict] = []
    if log_path.exists():
        with log_path.open() as fh:
            entries = json.load(fh)
    n_games = wins + draws + losses
    wr = wins / n_games if n_games else 0.0
    entry = {
        "iter": iter_idx,
        "anchor": str(anchor_path),
        "wins": wins, "draws": draws, "losses": losses,
        "winrate": round(wr, 4),
        "threshold": threshold,
        "passed": wr >= threshold,
    }
    # Replace any stale entry for this iter (e.g. from a prior partial run).
    entries = [e for e in entries if e.get("iter") != iter_idx]
    entries.append(entry)
    entries.sort(key=lambda e: e["iter"])
    with log_path.open("w") as fh:
        json.dump(entries, fh, indent=2)
    return entry


def _anchor_gate_log_has_iter(output_root: Path, iter_idx: int) -> dict | None:
    log_path = output_root / "anchor_gate_log.json"
    if not log_path.exists():
        return None
    with log_path.open() as fh:
        entries = json.load(fh)
    for e in entries:
        if e.get("iter") == iter_idx:
            return e
    return None


def _best_so_far_iter(output_root: Path, before_iter: int) -> int | None:
    """Return the iter index with the highest anchor-gate winrate among
    PASSED entries strictly before `before_iter`. Ties broken in favor of
    the later iter (more training data baked in). None if no prior iter
    has passed yet."""
    log_path = output_root / "anchor_gate_log.json"
    if not log_path.exists():
        return None
    with log_path.open() as fh:
        entries = json.load(fh)
    candidates = [
        e for e in entries
        if e.get("iter", 1_000_000) < before_iter and e.get("passed")
    ]
    if not candidates:
        return None
    # Sort by (winrate desc, iter desc) so the first element is best.
    candidates.sort(key=lambda e: (-e["winrate"], -e["iter"]))
    return candidates[0]["iter"]


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
    p.add_argument("--eval-games", type=int, default=50,
                   help="Games per head-to-head match. Default raised from "
                        "10/20 to 50 (2026-05-10 v2 recipe): single-game "
                        "swings at n=20 are ±35 ELO, at n=50 are ±~22 ELO.")
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--dirichlet-alpha", type=float, default=0.3)
    p.add_argument("--dirichlet-eps", type=float, default=0.25)
    p.add_argument("--temp-threshold", type=int, default=15)
    p.add_argument(
        "--batch-size", type=int, default=1,
        help="NeuralMCTS batch size during self-play. 1 (default) = serial; "
             ">1 enables virtual-loss / batched-eval (~2-4× speedup when "
             "GPU is bottleneck).",
    )
    p.add_argument(
        "--virtual-loss", type=float, default=1.0,
        help="W-penalty for in-flight nodes during batched selection. "
             "Only matters when --batch-size > 1.",
    )
    p.add_argument("--window", type=int, default=30,
                   help="Replay-buffer window: last K iters' games. Default "
                        "raised from 10 to 30 (2026-05-10 v2 recipe): more "
                        "history regularizes against the closed-loop drift "
                        "that crashed the v1 30-iter run.")
    p.add_argument(
        "--warmstart-mix-schedule",
        type=str,
        default="1.0,0.7,0.5,0.5",
        help="Comma-separated list. Element i is the warmstart-mix fraction "
             "at iter i. Clamps to the last value at higher iters. Default "
             "(2026-05-11 v3 recipe): 1.0 → 0.7 → 0.5 → 0.5 floor. v2's "
             "0.3 floor (default 1.0,0.7,0.4,0.3) still regressed -200 ELO "
             "vs warmstart by iter 4; v3 doubles the floor anchor strength.",
    )
    p.add_argument("--epochs", type=int, default=3,
                   help="Training epochs per iter.")
    p.add_argument(
        "--fp16", action="store_true",
        help="Pass --fp16 to selfplay + head-to-head subprocesses. fp16 "
             "autocast at inference (master weights stay fp32). ~1.5-2× "
             "forward speedup on Blackwell/Ada Tensor Cores. No-op on CPU.",
    )
    p.add_argument(
        "--orchestrator", action="store_true",
        help="Pass --orchestrator to selfplay + h2h subprocesses. Single "
             "GPU-side eval server with CPU workers (mp.Queue IPC). Required "
             "at W>=48 — at that fan-out the per-worker torch allocator pool "
             "(~600 MB) blows past 32 GB VRAM. Validated 2026-05-12.",
    )
    p.add_argument(
        "--leaf-eval", choices=["nn", "v2_5"], default="nn",
        help="Leaf-value source for self-play, h2h, AND anchor eval. 'nn' "
             "(default, back-compat) uses each net's value head; 'v2_5' uses "
             "tanh(virtual_score_v2/15) — production at +6.6pp wr vs Tier-1 "
             "(DECISIONS.md 2026-05-14). Applied uniformly to all three "
             "sub-stages so eval comparisons stay apples-to-apples.",
    )
    p.add_argument("--workers", type=int, default=8,
                   help="Pool workers for self-play. Default 8 leaves SMT "
                        "headroom for other workloads on a 5800X; for "
                        "dedicated runs use --workers 16 (empirical optimum, "
                        "measured 2026-05-09).")
    p.add_argument("--eval-workers", type=int, default=8,
                   help="Pool workers for head-to-head. Same guidance as "
                        "--workers; head-to-head loads 2 networks/worker "
                        "(2× GPU memory).")
    p.add_argument("--output-root", type=Path, required=True,
                   help="Root for self-play data + ELO log.")
    p.add_argument(
        "--checkpoint-root", type=Path,
        default=REPO_ROOT / "checkpoints" / "selfplay",
        help="Root for per-iter checkpoints. Default 'checkpoints/selfplay'; "
             "use a different path (e.g. 'checkpoints/selfplay_v2') to keep "
             "v1 and v2 outputs separate.",
    )
    p.add_argument(
        "--anchor-gate", action="store_true",
        help="After each iter's training, run a fixed-anchor eval. If "
             "winrate < --anchor-min-winrate, count a failure; halt the "
             "loop after --anchor-max-fails consecutive failures. Off by "
             "default for backward compat. Cost: ~3 min/iter.",
    )
    p.add_argument(
        "--anchor-checkpoint", type=Path, default=WARMSTART_CANONICAL,
        help="Reference checkpoint for the anchor gate. Default: "
             "warmstart_canonical.pt — the Phase 3 baseline.",
    )
    p.add_argument(
        "--anchor-games", type=int, default=10,
        help="Games per anchor-gate eval (default 10).",
    )
    p.add_argument(
        "--anchor-sims", type=int, default=50,
        help="NeuralMCTS sims per move during anchor-gate eval. Lower than "
             "head-to-head's --eval-sims to keep cost down (default 50).",
    )
    p.add_argument(
        "--anchor-min-winrate", type=float, default=0.4,
        help="Pass threshold (default 0.4 = 40%% wr). Below this counts as "
             "a failure for the consecutive-fails counter.",
    )
    p.add_argument(
        "--anchor-max-fails", type=int, default=3,
        help="Halt the outer loop after this many consecutive anchor-gate "
             "failures (default 3).",
    )
    p.add_argument(
        "--best-so-far-warmstart", action="store_true",
        help="At each iter N>0, use the highest-anchor-winrate PASSED iter "
             "as warm_from instead of iter N-1. Acts as a regression-stop "
             "ratchet: if iter N's anchor wr is below best-so-far, the next "
             "iter restarts from best-so-far's checkpoint with a fresh RNG. "
             "Requires --anchor-gate (else nothing to track). Default OFF "
             "for backward compat with v1/v2 behavior.",
    )
    p.add_argument(
        "--initial-checkpoint", type=Path, default=WARMSTART_CANONICAL,
        help="Initial weights for iter 0 (and the fallback for best-so-far "
             "when no prior anchor-gate has PASSED yet). Default: "
             "warmstart_canonical.pt — the heuristic-warmstart baseline. "
             "For v6+ recipes that bootstrap from a previously-trained "
             "checkpoint (e.g. selfplay_v5/iter_06.pt), override this. "
             "Independent of --anchor-checkpoint, which always measures "
             "absolute progress against a fixed reference.",
    )
    args = p.parse_args(argv)
    if args.best_so_far_warmstart and not args.anchor_gate:
        print(
            "ERROR: --best-so-far-warmstart requires --anchor-gate "
            "(no anchor-gate log → no best-so-far to track).",
            file=sys.stderr,
        )
        return 1

    args.output_root.mkdir(parents=True, exist_ok=True)
    args.checkpoint_root.mkdir(parents=True, exist_ok=True)

    schedule = [float(x) for x in args.warmstart_mix_schedule.split(",")]
    print(
        f"Phase 4 smoke: iters={args.iters}, games/iter={args.games}, "
        f"sims={args.sims}, eval_sims={args.eval_sims}, "
        f"eval_games={args.eval_games}, workers={args.workers}, "
        f"output_root={args.output_root}, checkpoint_root={args.checkpoint_root}"
    )
    print(f"  warmstart-mix schedule: {schedule}")
    print(f"  warm-from at iter 0 (initial-checkpoint): {args.initial_checkpoint}")
    if args.anchor_gate:
        print(
            f"  anchor-gate: ON ({args.anchor_games} games at sims={args.anchor_sims} "
            f"vs {args.anchor_checkpoint.name}, "
            f"min_wr={args.anchor_min_winrate:.2f}, "
            f"halt after {args.anchor_max_fails} consecutive fails)"
        )
    else:
        print("  anchor-gate: OFF")
    print(
        f"  best-so-far warmstart: {'ON' if args.best_so_far_warmstart else 'OFF'}"
    )
    sys.stdout.flush()

    consecutive_anchor_fails = 0
    overall_t0 = time.perf_counter()
    for iter_idx in range(args.iters):
        iter_t0 = time.perf_counter()
        if args.best_so_far_warmstart and iter_idx > 0:
            best_iter = _best_so_far_iter(args.output_root, iter_idx)
            if best_iter is None:
                # No prior iter has PASSED yet — fall back to the configured
                # initial checkpoint (default warmstart_canonical.pt; v6+
                # recipes override via --initial-checkpoint). Iter 0 uses
                # the same; this branch triggers when every prior anchor-gate
                # FAILed.
                warm_from = args.initial_checkpoint
                print(
                    f"\n[iter {iter_idx}] best-so-far: no prior PASS — "
                    f"warm-from {warm_from.name}"
                )
            else:
                warm_from = _checkpoint_path(args.checkpoint_root, best_iter)
                if best_iter != iter_idx - 1:
                    print(
                        f"\n[iter {iter_idx}] best-so-far: rolling back to "
                        f"iter_{best_iter:02d} (highest anchor wr) instead "
                        f"of latest iter_{iter_idx - 1:02d}"
                    )
        else:
            warm_from = _warm_from_for(
                args.checkpoint_root, iter_idx, args.initial_checkpoint
            )
        if not warm_from.exists():
            print(f"\nERROR: warm-from checkpoint missing: {warm_from}",
                  file=sys.stderr)
            return 1

        # Step 1: self-play (skip if already done)
        if _selfplay_iter_complete(args.output_root, iter_idx, args.games):
            print(f"\n[iter {iter_idx}] self-play already complete — skipping")
        else:
            cmd = [
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
                "--batch-size", str(args.batch_size),
                "--virtual-loss", str(args.virtual_loss),
                "--workers", str(args.workers),
            ]
            if args.fp16:
                cmd.append("--fp16")
            if args.orchestrator:
                cmd.append("--orchestrator")
            if args.leaf_eval != "nn":
                cmd.extend(["--leaf-eval", args.leaf_eval])
            _run_subcommand(f"iter {iter_idx}: self-play", cmd)

        # Step 2: train
        ckpt_out = _checkpoint_path(args.checkpoint_root, iter_idx)
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

        # Step 2b: anchor gate (opt-in). Run BEFORE the chain head-to-head so
        # we can halt cleanly without paying the head-to-head cost on a
        # known-bad iter.
        if args.anchor_gate:
            cached_gate = _anchor_gate_log_has_iter(args.output_root, iter_idx)
            if cached_gate is not None:
                gate_entry = cached_gate
                print(
                    f"\n[iter {iter_idx}] anchor-gate cached: "
                    f"{gate_entry['wins']}W/{gate_entry['draws']}D/{gate_entry['losses']}L "
                    f"wr={gate_entry['winrate']:.2f} passed={gate_entry['passed']}"
                )
            else:
                anchor_eval_dir = (
                    args.output_root / "eval"
                    / f"iter_{iter_idx:02d}_vs_{ANCHOR_VS_ITER_SENTINEL:04d}"
                )
                cmd = [
                    sys.executable, "-u", str(SCRIPTS / "eval_iter_head_to_head.py"),
                    "--new-checkpoint", str(ckpt_out),
                    "--old-checkpoint", str(args.anchor_checkpoint),
                    "--output-root", str(args.output_root),
                    "--iter", str(iter_idx),
                    "--vs-iter", str(ANCHOR_VS_ITER_SENTINEL),
                    "--games", str(args.anchor_games),
                    "--sims", str(args.anchor_sims),
                    "--c-puct", str(args.c_puct),
                    "--workers", str(args.eval_workers),
                    "--batch-size", str(args.batch_size),
                    "--virtual-loss", str(args.virtual_loss),
                    "--no-elo-log",
                ]
                if args.fp16:
                    cmd.append("--fp16")
                if args.orchestrator:
                    cmd.append("--orchestrator")
                if args.leaf_eval != "nn":
                    cmd.extend(["--leaf-eval", args.leaf_eval])
                _run_subcommand(
                    f"iter {iter_idx}: anchor-gate vs {args.anchor_checkpoint.name}",
                    cmd,
                )
                tally = _tally_anchor_eval_dir(
                    anchor_eval_dir, args.anchor_sims, args.anchor_games
                )
                if tally is None:
                    print(
                        f"\nERROR: anchor-gate eval dir incomplete: {anchor_eval_dir}",
                        file=sys.stderr,
                    )
                    return 1
                wins, draws, losses = tally
                gate_entry = _append_anchor_gate_log(
                    args.output_root, iter_idx, args.anchor_checkpoint,
                    wins, draws, losses, args.anchor_min_winrate,
                )
                print(
                    f"\n[iter {iter_idx}] anchor-gate: "
                    f"{wins}W/{draws}D/{losses}L  wr={gate_entry['winrate']:.2f}  "
                    f"threshold={args.anchor_min_winrate:.2f}  "
                    f"{'PASS' if gate_entry['passed'] else 'FAIL'}"
                )
            if gate_entry["passed"]:
                consecutive_anchor_fails = 0
            else:
                consecutive_anchor_fails += 1
                if consecutive_anchor_fails >= args.anchor_max_fails:
                    print(
                        f"\nABORT: {consecutive_anchor_fails} consecutive "
                        f"anchor-gate failures (limit {args.anchor_max_fails}). "
                        f"Halting at iter {iter_idx}. Inspect "
                        f"{args.output_root / 'anchor_gate_log.json'} and "
                        "DECISIONS.md before re-launching.",
                        file=sys.stderr,
                    )
                    return 2

        # Step 3: head-to-head vs prev iter (skip iter 0; nothing to compare to)
        if iter_idx == 0:
            print(f"\n[iter {iter_idx}] no prior iter — skipping head-to-head")
        elif _elo_log_has_iter(args.output_root, iter_idx):
            print(f"\n[iter {iter_idx}] ELO log entry exists — skipping head-to-head")
        else:
            cmd = [
                sys.executable, "-u", str(SCRIPTS / "eval_iter_head_to_head.py"),
                "--new-checkpoint", str(ckpt_out),
                "--old-checkpoint", str(_checkpoint_path(args.checkpoint_root, iter_idx - 1)),
                "--output-root", str(args.output_root),
                "--iter", str(iter_idx),
                "--vs-iter", str(iter_idx - 1),
                "--games", str(args.eval_games),
                "--sims", str(args.eval_sims),
                "--c-puct", str(args.c_puct),
                "--workers", str(args.eval_workers),
                "--batch-size", str(args.batch_size),
                "--virtual-loss", str(args.virtual_loss),
            ]
            if args.fp16:
                cmd.append("--fp16")
            if args.orchestrator:
                cmd.append("--orchestrator")
            if args.leaf_eval != "nn":
                cmd.extend(["--leaf-eval", args.leaf_eval])
            _run_subcommand(
                f"iter {iter_idx}: head-to-head vs iter {iter_idx - 1}", cmd
            )

        iter_elapsed = time.perf_counter() - iter_t0
        print(f"\n[iter {iter_idx}] complete in {iter_elapsed/60:.1f} min")
        sys.stdout.flush()

    overall = time.perf_counter() - overall_t0
    print(f"\n=== Phase 4 smoke done: {args.iters} iters in {overall/60:.1f} min ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
