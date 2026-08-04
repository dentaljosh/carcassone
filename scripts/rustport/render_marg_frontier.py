#!/usr/bin/env python3
"""Render the MARG_FRONTIER.md verdict tables from bench row files.

Input: one or more `BENCH_*_rows.jsonl` paths (positional). Each line is a JSON
object emitted by `bench_exact_solver.py` with at least:
    cell, engine, k, mode, pos, status ("ok" | "timeout" | "EXCEPTION")
and, on `status=="ok"` rows: wall_ms, rss_peak_mb, nodes.

Behaviour (see measurement/rust_solver_bench_20260803/MARG_FRONTIER.md):
  * `status=="EXCEPTION"` rows are stale-wheel artifacts -> dropped (noted on stderr).
  * duplicate (cell, pos) among the survivors -> keep the LAST occurrence
    (the relaunch appended the real row after the stale one).
  * group by (mode, k); one markdown row per group.

stdlib only, python 3.12.
"""

from __future__ import annotations

import json
import math
import statistics
import sys

HEADER = (
    "| cell | ok / n | timeouts | ok wall s (min/med/p90/max) "
    "| rss_peak MB (med/max) | nodes med |"
)
SEPARATOR = "|---|---|---|---|---|---|"
DASH = "—"  # em dash


def p90(sorted_values: list[float]) -> float:
    """Value at index ceil(0.9 * n) - 1 of an already-sorted list."""
    idx = math.ceil(0.9 * len(sorted_values)) - 1
    idx = max(0, min(idx, len(sorted_values) - 1))
    return sorted_values[idx]


def load_rows(path: str) -> list[dict]:
    """Read a jsonl file into a list of dicts. Blank lines are skipped."""
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def clean_rows(rows: list[dict]) -> tuple[list[dict], int, int]:
    """Drop EXCEPTION rows, then dedupe (cell,pos) keeping the LAST occurrence.

    Returns (rows, n_exception_dropped, n_deduped).
    """
    kept = [r for r in rows if r.get("status") != "EXCEPTION"]
    n_exception = len(rows) - len(kept)

    by_key: dict[tuple, dict] = {}
    for r in kept:
        by_key[(r.get("cell"), r.get("pos"))] = r  # last write wins
    n_deduped = len(kept) - len(by_key)
    return list(by_key.values()), n_exception, n_deduped


def render_table(rows: list[dict]) -> str:
    """Render the markdown table for already-cleaned rows.

    `rows` must have had EXCEPTION rows dropped and (cell,pos) deduped; use
    `clean_rows` for that. Groups by (mode, k), sorted.
    """
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r.get("mode"), r.get("k")), []).append(r)

    lines = [HEADER, SEPARATOR]
    for (mode, k), grp in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        n = len(grp)
        ok = [r for r in grp if r.get("status") == "ok"]
        timeouts = sum(1 for r in grp if r.get("status") == "timeout")
        label = f"marg K{k}" if mode == "marginalized" else f"{mode} K{k}"

        if not ok:
            lines.append(f"| {label} | 0/{n} | {timeouts} | {DASH} | {DASH} | {DASH} |")
            continue

        walls = sorted(r["wall_ms"] / 1000.0 for r in ok)
        rss = sorted(float(r["rss_peak_mb"]) for r in ok)
        nodes_med = int(statistics.median(sorted(int(r["nodes"]) for r in ok)))

        lines.append(
            f"| {label} | {len(ok)}/{n} | {timeouts} "
            f"| {walls[0]:.0f} / {statistics.median(walls):.0f} / {p90(walls):.0f} / {walls[-1]:.0f} "
            f"| {statistics.median(rss):.0f} / {rss[-1]:.0f} "
            f"| {nodes_med:,} |"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    paths = argv[1:]
    if not paths:
        print(
            f"usage: {argv[0]} BENCH_x_rows.jsonl [BENCH_y_rows.jsonl ...]",
            file=sys.stderr,
        )
        return 1

    multi = len(paths) > 1
    for i, path in enumerate(paths):
        try:
            raw = load_rows(path)
        except OSError as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as exc:
            print(f"error: malformed json in {path}: {exc}", file=sys.stderr)
            return 1

        rows, n_exception, n_deduped = clean_rows(raw)
        if n_exception:
            print(f"dropped {n_exception} EXCEPTION rows (stale wheel)", file=sys.stderr)
        if n_deduped:
            print(f"deduped {n_deduped} repeated (cell,pos) rows (kept last)", file=sys.stderr)

        if multi:
            if i:
                print()
            print(f"### {path.rsplit('/', 1)[-1]}")
            print()
        print(render_table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
