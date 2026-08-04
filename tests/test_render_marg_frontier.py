"""Pin the MARG_FRONTIER table renderer (scripts/rustport/render_marg_frontier.py).

Contracts under test:
  * `status=="EXCEPTION"` rows (stale-wheel artifacts) are dropped, and the drop
    is announced on stderr.
  * a repeated (cell, pos) keeps the LAST occurrence.
  * the min/med/p90/max + rss + nodes math on a hand-computed small case.
  * a group with zero ok rows renders em-dashes for the stats columns.
"""

import json
import os
import subprocess
import sys

import pytest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "rustport", "render_marg_frontier.py"
)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "rustport"))
from render_marg_frontier import clean_rows, load_rows, p90, render_table  # noqa: E402


def _row(k, pos, status, wall_ms=None, rss=None, nodes=None, cell=None):
    r = {
        "cell": cell or f"rust_marginalized_k{k}",
        "engine": "rust",
        "k": k,
        "mode": "marginalized",
        "pos": pos,
        "status": status,
    }
    if status == "ok":
        r.update({"wall_ms": wall_ms, "rss_peak_mb": rss, "nodes": nodes})
    if status == "EXCEPTION":
        r["error"] = "AttributeError: 'builtins.MirrorState' object has no attribute 'solve_endgame'"
    return r


# K4: five ok (1..5 s), one timeout, plus a stale duplicate of p1 that must lose
# to the later real p1 row. K5: two ok. K6: one timeout only (zero-ok group).
ROWS = [
    _row(4, "p1", "EXCEPTION"),
    _row(5, "px", "EXCEPTION"),
    _row(4, "p1", "ok", wall_ms=99_000.0, rss=9999.0, nodes=999_999),  # stale dup, dropped
    _row(4, "p1", "ok", wall_ms=1_000.0, rss=100.0, nodes=10),
    _row(4, "p2", "ok", wall_ms=2_000.0, rss=200.0, nodes=20),
    _row(4, "p3", "ok", wall_ms=3_000.0, rss=300.0, nodes=30),
    _row(4, "p4", "ok", wall_ms=4_000.0, rss=400.0, nodes=40),
    _row(4, "p5", "ok", wall_ms=5_000.0, rss=500.0, nodes=50),
    _row(4, "p6", "timeout"),
    _row(5, "q1", "ok", wall_ms=10_000.0, rss=50.0, nodes=1_000_000),
    _row(5, "q2", "ok", wall_ms=20_000.0, rss=70.0, nodes=1_500_000),
    _row(6, "r1", "timeout", cell="rust_marginalized_k6_probe"),
]

# Hand-computed expectations.
#   K4 ok walls (s), sorted: [1, 2, 3, 4, 5] -> min 1, med 3, max 5
#     p90 index = ceil(0.9*5) - 1 = 5 - 1 = 4 -> 5
#     rss sorted [100,200,300,400,500] -> med 300, max 500; nodes med 30
#   K5 ok walls: [10, 20] -> min 10, med 15, max 20
#     p90 index = ceil(0.9*2) - 1 = 2 - 1 = 1 -> 20
#     rss [50,70] -> med 60, max 70; nodes med (1e6+1.5e6)/2 = 1,250,000
EXPECTED_K4 = "| marg K4 | 5/6 | 1 | 1 / 3 / 5 / 5 | 300 / 500 | 30 |"
EXPECTED_K5 = "| marg K5 | 2/2 | 0 | 10 / 15 / 20 / 20 | 60 / 70 | 1,250,000 |"
EXPECTED_K6 = "| marg K6 | 0/1 | 1 | — | — | — |"


@pytest.fixture
def rows_file(tmp_path):
    path = tmp_path / "BENCH_unit_rows.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for r in ROWS:
            fh.write(json.dumps(r) + "\n")
    return str(path)


def test_p90_index_rule():
    """p90 = sorted[ceil(0.9*n)-1], clamped into range."""
    assert p90([1, 2, 3, 4, 5]) == 5  # ceil(4.5)-1 = 4
    assert p90([10, 20]) == 20  # ceil(1.8)-1 = 1
    assert p90([7]) == 7
    assert p90(list(range(1, 11))) == 9  # ceil(9)-1 = 8 -> value 9


def test_exceptions_dropped_and_dedupe_keeps_last(rows_file):
    raw = load_rows(rows_file)
    assert len(raw) == len(ROWS)

    rows, n_exception, n_deduped = clean_rows(raw)
    assert n_exception == 2
    assert n_deduped == 1
    assert not any(r["status"] == "EXCEPTION" for r in rows)
    assert len(rows) == len(ROWS) - 2 - 1

    p1 = [r for r in rows if r["pos"] == "p1"]
    assert len(p1) == 1
    assert p1[0]["wall_ms"] == 1_000.0  # the LAST occurrence, not the stale 99 s one


def test_table_math(rows_file):
    rows, _, _ = clean_rows(load_rows(rows_file))
    lines = render_table(rows).splitlines()

    assert lines[0].startswith("| cell | ok / n | timeouts | ok wall s (min/med/p90/max)")
    assert lines[1] == "|---|---|---|---|---|---|"
    assert lines[2:] == [EXPECTED_K4, EXPECTED_K5, EXPECTED_K6]


def test_zero_ok_group_renders_em_dashes(rows_file):
    rows, _, _ = clean_rows(load_rows(rows_file))
    k6 = [ln for ln in render_table(rows).splitlines() if ln.startswith("| marg K6 ")]
    assert k6 == [EXPECTED_K6]
    assert k6[0].count("—") == 3


def test_cli_end_to_end(rows_file):
    proc = subprocess.run(
        [sys.executable, SCRIPT, rows_file], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert "dropped 2 EXCEPTION rows (stale wheel)" in proc.stderr
    assert "deduped 1" in proc.stderr
    assert EXPECTED_K4 in proc.stdout
    assert EXPECTED_K5 in proc.stdout
    assert EXPECTED_K6 in proc.stdout
    # single file -> no per-file heading
    assert "###" not in proc.stdout


def test_cli_multi_file_headings(rows_file, tmp_path):
    second = tmp_path / "BENCH_other_rows.jsonl"
    with open(second, "w", encoding="utf-8") as fh:
        for r in ROWS[-3:]:
            fh.write(json.dumps(r) + "\n")
    proc = subprocess.run(
        [sys.executable, SCRIPT, rows_file, str(second)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "### BENCH_unit_rows.jsonl" in proc.stdout
    assert "### BENCH_other_rows.jsonl" in proc.stdout


def test_cli_unreadable_file_exits_1(tmp_path):
    proc = subprocess.run(
        [sys.executable, SCRIPT, str(tmp_path / "nope.jsonl")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "cannot read" in proc.stderr
