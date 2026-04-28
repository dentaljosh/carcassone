"""Compare two trained warm-start checkpoints by running each through
the tournament script and reporting wins-per-hour-of-generation.

Usage:
  python scripts/compare_warmstart_smoke.py \
      --heuristic-ckpt checkpoints/warmstart_heuristic_smoke.best.pt \
      --mcts-ckpt checkpoints/warmstart_mcts_smoke.best.pt \
      --n 50 \
      --heuristic-gen-time-min 1 \
      --mcts-gen-time-min 55

Reports per-strategy win count and "wins per hour of generation cost". The
strategy with higher wins/hour is the recommended pick for the production
warm-start run.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_tournament(checkpoint: Path, n: int, seed_start: int = 10000) -> dict:
    """Run the tournament script and parse its summary."""
    cmd = [
        sys.executable, "-u", str(REPO_ROOT / "scripts" / "eval_warmstart_smoke.py"),
        "--checkpoint", str(checkpoint),
        "--n", str(n),
        "--seed-start", str(seed_start),
    ]
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = result.stdout
    print(out)
    m = re.search(r"vs random:\s+(\d+)/(\d+)\s+wins\s+\(([\d.]+)%\)", out)
    if not m:
        raise RuntimeError(f"could not parse tournament output:\n{out}")
    wins = int(m.group(1))
    n_games = int(m.group(2))
    win_rate = float(m.group(3)) / 100.0
    diff_m = re.search(r"avg score diff \(net - random\):\s+([+\-]?[\d.]+)", out)
    avg_diff = float(diff_m.group(1)) if diff_m else 0.0
    return {
        "checkpoint": str(checkpoint),
        "wins": wins,
        "n_games": n_games,
        "win_rate": win_rate,
        "avg_score_diff": avg_diff,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="compare_warmstart_smoke")
    p.add_argument("--heuristic-ckpt", type=Path, default=REPO_ROOT / "checkpoints" / "warmstart_heuristic_smoke.best.pt")
    p.add_argument("--mcts-ckpt", type=Path, default=REPO_ROOT / "checkpoints" / "warmstart_mcts_smoke.best.pt")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed-start", type=int, default=10000)
    p.add_argument("--heuristic-gen-time-min", type=float, required=True,
                   help="Wall-clock minutes spent generating the heuristic dataset")
    p.add_argument("--mcts-gen-time-min", type=float, required=True,
                   help="Wall-clock minutes spent generating the MCTS dataset")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "warmstart" / "smoke_comparison.json")
    args = p.parse_args(argv)

    if not args.heuristic_ckpt.exists():
        raise SystemExit(f"missing checkpoint: {args.heuristic_ckpt}")
    if not args.mcts_ckpt.exists():
        raise SystemExit(f"missing checkpoint: {args.mcts_ckpt}")

    print("=" * 60)
    print("Heuristic-trained network tournament vs random")
    print("=" * 60)
    h_result = run_tournament(args.heuristic_ckpt, args.n, args.seed_start)

    print("=" * 60)
    print("MCTS-trained network tournament vs random")
    print("=" * 60)
    m_result = run_tournament(args.mcts_ckpt, args.n, args.seed_start)

    h_wins_per_hour = h_result["wins"] / max(args.heuristic_gen_time_min / 60.0, 1e-9)
    m_wins_per_hour = m_result["wins"] / max(args.mcts_gen_time_min / 60.0, 1e-9)

    print()
    print("=" * 60)
    print("SMOKE COMPARISON SUMMARY")
    print("=" * 60)
    print(f"Heuristic: {h_result['wins']}/{h_result['n_games']} wins ({h_result['win_rate']:.1%}); "
          f"gen_time={args.heuristic_gen_time_min:.1f} min; "
          f"wins/hour={h_wins_per_hour:.1f}; "
          f"avg_diff={h_result['avg_score_diff']:+.1f}")
    print(f"MCTS:      {m_result['wins']}/{m_result['n_games']} wins ({m_result['win_rate']:.1%}); "
          f"gen_time={args.mcts_gen_time_min:.1f} min; "
          f"wins/hour={m_wins_per_hour:.1f}; "
          f"avg_diff={m_result['avg_score_diff']:+.1f}")
    print()
    if h_wins_per_hour > m_wins_per_hour:
        recommendation = "HEURISTIC"
        ratio = h_wins_per_hour / max(m_wins_per_hour, 1e-9)
        print(f"  -> {recommendation} wins by {ratio:.1f}x in wins-per-hour")
        print(f"  -> For the production run, scale heuristic to 500K positions (~{args.heuristic_gen_time_min * 100:.0f} min)")
    else:
        recommendation = "MCTS"
        ratio = m_wins_per_hour / max(h_wins_per_hour, 1e-9)
        print(f"  -> {recommendation} wins by {ratio:.1f}x in wins-per-hour")
        print(f"  -> For the production run, scale MCTS to 50K positions (~{args.mcts_gen_time_min * 10:.0f} min)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "heuristic": {**h_result, "gen_time_min": args.heuristic_gen_time_min, "wins_per_hour": h_wins_per_hour},
        "mcts": {**m_result, "gen_time_min": args.mcts_gen_time_min, "wins_per_hour": m_wins_per_hour},
        "recommendation": recommendation,
    }
    with args.out.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
