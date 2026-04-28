"""Phase 3 acceptance report — consolidate Tournament 1 + 2 results.

Reads per-game JSON from data/tournament/eval_phase3/ (Tournament 2) and
optionally the streamed stdout of Tournament 1 (which doesn't checkpoint
to disk). Prints win rates against the Phase 3 acceptance criteria:

  Tournament 1 (network-only vs random):       ≥ 90 wins / 100
  Tournament 2 (NeuralMCTS s=50 vs vanilla):   > 55 wins / 100

Usage:
  python scripts/summarize_phase3.py
  python scripts/summarize_phase3.py --t2-dir data/tournament/eval_phase3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _format_pass_fail(wins: int, n: int, threshold: float, note: str) -> str:
    pct = wins / max(n, 1)
    status = "PASS" if pct >= threshold else "FAIL"
    return (
        f"{status}  {wins}/{n} ({pct:.1%})  threshold ≥{threshold:.0%}  ({note})"
    )


def summarize_t2(t2_dir: Path) -> dict:
    files = sorted(t2_dir.glob("n*_v*_seed*.json"))
    if not files:
        return {"n": 0, "wins": 0, "draws": 0, "losses": 0, "avg_diff": 0.0, "avg_elapsed": 0.0}
    rows = []
    for f in files:
        try:
            with f.open() as fh:
                rows.append(json.load(fh))
        except Exception as exc:
            print(f"  [warn] {f.name}: {exc}", file=sys.stderr)
    n = len(rows)
    wins = sum(1 for r in rows if r.get("won_by_neural"))
    draws = sum(1 for r in rows if r.get("drew"))
    losses = n - wins - draws
    avg_diff = sum(r.get("diff", 0) for r in rows) / max(n, 1)
    avg_elapsed = sum(r.get("elapsed_s", 0.0) for r in rows) / max(n, 1)
    avg_moves = sum(r.get("moves", 0) for r in rows) / max(n, 1)
    return {
        "n": n,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "avg_diff": avg_diff,
        "avg_elapsed": avg_elapsed,
        "avg_moves": avg_moves,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="summarize_phase3")
    p.add_argument(
        "--t2-dir",
        type=Path,
        default=REPO_ROOT / "data" / "tournament" / "eval_phase3",
    )
    p.add_argument(
        "--t1-summary",
        type=str,
        default=None,
        help="Optional: paste-in 'wins/N' string for Tournament 1 (e.g. '92/100')",
    )
    args = p.parse_args(argv)

    print("Phase 3 acceptance report")
    print("=" * 60)

    if args.t1_summary:
        try:
            wins, n = (int(x) for x in args.t1_summary.split("/"))
        except ValueError:
            print(f"  [warn] couldn't parse --t1-summary {args.t1_summary!r}; want 'W/N'")
            wins, n = 0, 0
        line = _format_pass_fail(wins, n, threshold=0.90, note="net argmax vs random, no MCTS")
        print(f"\nTournament 1: {line}")
    else:
        print("\nTournament 1: (rerun with --t1-summary W/N to include)")
        print("  scripts/eval_warmstart_smoke.py prints W/N to stdout but does not")
        print("  checkpoint per-game results, so we read from manual paste-in.")

    print()
    t2 = summarize_t2(args.t2_dir)
    if t2["n"] == 0:
        print(f"Tournament 2: no per-game JSON in {args.t2_dir}")
    else:
        line = _format_pass_fail(
            t2["wins"], t2["n"], threshold=0.55,
            note=f"NeuralMCTS(s=50) vs vanilla MCTS(s=100), avg diff {t2['avg_diff']:+.1f}, "
            f"avg elapsed {t2['avg_elapsed']:.1f}s/game, avg moves {t2['avg_moves']:.0f}",
        )
        print(f"Tournament 2: {line}")
        print(f"  draws: {t2['draws']}, losses: {t2['losses']}")

    print()
    print("Acceptance: BOTH tournaments must pass to advance to Phase 4 with the")
    print("current warmstart. If T1 fails: more data / more epochs / bigger net.")
    print("If T2 fails: c_puct sweep or more neural sims.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
