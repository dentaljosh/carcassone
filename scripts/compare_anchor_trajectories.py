#!/usr/bin/env python3
"""Compare anchor-gate trajectories across recipe versions.

Reads anchor_gate_log.json from one or more runs and prints a side-by-side
ASCII table + a tiny ASCII chart. Useful for the v6 post-mortem (vs v5)
and for any future recipe A/B.

Usage:
    python scripts/compare_anchor_trajectories.py \\
        data/selfplay/v5_cloud/anchor_gate_log.json \\
        data/selfplay/v6_cloud/anchor_gate_log.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_log(p: Path) -> list[dict]:
    return json.loads(p.read_text())


def label_for(p: Path) -> str:
    # Pick the immediate parent dir as the label (e.g. v5_cloud, v6_cloud).
    return p.parent.name


def render(logs: list[tuple[str, list[dict]]]) -> None:
    max_iter = max(max((e["iter"] for e in log), default=-1) for _, log in logs)

    # Header row.
    print()
    print(f"  iter  ", end="")
    for label, _ in logs:
        print(f"{label:>14}", end="")
    print()
    print("  " + "─" * (6 + 14 * len(logs)))

    # By-iter rows.
    for it in range(max_iter + 1):
        print(f"  {it:>4}  ", end="")
        for _, log in logs:
            entry = next((e for e in log if e["iter"] == it), None)
            if entry is None:
                cell = "—"
            else:
                wr = entry["winrate"]
                tag = "PASS" if entry["passed"] else "FAIL"
                cell = f"{wr*100:>4.0f}% {tag}"
            print(f"{cell:>14}", end="")
        print()

    # Summary line.
    print()
    for label, log in logs:
        passes = sum(1 for e in log if e["passed"])
        best = max((e["winrate"] for e in log), default=0)
        first_fail = next((e["iter"] for e in log if not e["passed"]), None)
        ff_str = f"iter {first_fail}" if first_fail is not None else "none"
        print(f"  {label}: {passes}/{len(log)} PASS  best={best*100:.0f}%  first FAIL={ff_str}")

    # Tiny ASCII chart of winrate (just the runs, no v5 anchor line).
    print()
    print("  winrate vs iter (rows = recipe, cols = iter):")
    print("    │ 80% ──────────────────────────────────")
    for label, log in logs:
        wrs = sorted(log, key=lambda e: e["iter"])
        bar = "    │ "
        for entry in wrs:
            wr = entry["winrate"]
            if wr >= 0.70:
                ch = "█"
            elif wr >= 0.55:
                ch = "▓"
            elif wr >= 0.40:
                ch = "▒"
            else:
                ch = "░"
            bar += ch + " "
        print(f"{bar}  {label}")
    print("    │ ░ <40% (FAIL)  ▒ 40-54%  ▓ 55-69%  █ ≥70%")
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    paths = [Path(a) for a in sys.argv[1:]]
    missing = [p for p in paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: {p} not found", file=sys.stderr)
        return 2
    logs = [(label_for(p), load_log(p)) for p in paths]
    render(logs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
