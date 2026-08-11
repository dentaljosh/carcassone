"""Pins the W-sweep driver for the rust exact solver.

The driver never runs a solve in these tests: `plan_commands`, `check_ram`,
`parse_point` and `summarize` are pure, and the dry-run path is exercised
end-to-end with no subprocess.

The load-bearing test is `test_generated_argv_runs_exactly_one_cell`: the whole
sweep is meaningless if a point silently runs `bench_exact_solver.py`'s seven
DEFAULT cells instead of the one cell asked for.  It re-derives the bench's
argparse defaults from the source text (so a default change breaks the test
rather than the sweep) and replays the driver's argv through an equivalent
parser + the bench's own cell-building loop.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPO / "scripts" / "rustport" / "wsweep_exact_solver.py"
BENCH_PATH = REPO / "scripts" / "rustport" / "bench_exact_solver.py"


def _load_driver():
    """Import the driver by path — it is stdlib-only, so this is side-effect free.

    (`bench_exact_solver.py` is NOT imported anywhere in this file: importing it
    pulls in carc_rs and the corpus loaders.  Only its source TEXT is read.)
    """
    spec = importlib.util.spec_from_file_location("wsweep_exact_solver",
                                                  DRIVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W = _load_driver()


def args(**kw):
    ns = argparse.Namespace(k=4, mode="marginalized", w_points=[4, 12, 30],
                            n=20, timeout_s=3600, out="/tmp/sweep",
                            ram_cap_mb=24000, rss_max_mb=1237.0,
                            dry_run=False)
    for key, val in kw.items():
        setattr(ns, key, val)
    return ns


# ---------------------------------------------------------------------------
# (b) RAM guard math
# ---------------------------------------------------------------------------

def test_ram_guard_boundary_accept_and_reject():
    # exactly at the cap is accepted: 10 * 100 * 1.5 == 1500
    v = W.check_ram([10], rss_max_mb=100.0, ram_cap_mb=1500)[0]
    assert v["ok"] and v["need_mb"] == pytest.approx(1500.0)
    # one worker more is not
    v = W.check_ram([11], rss_max_mb=100.0, ram_cap_mb=1500)[0]
    assert not v["ok"] and v["need_mb"] == pytest.approx(1650.0)
    assert W.RAM_HEADROOM == 1.5


def test_ram_guard_aborts_rc3_naming_the_offending_w(capsys):
    with pytest.raises(SystemExit) as exc:
        W.guard_ram(args(w_points=[4, 12, 30], rss_max_mb=1237.0,
                         ram_cap_mb=24000))
    assert exc.value.code == W.RC_RAM == 3
    err = capsys.readouterr().err
    # 12 fits (22266), 30 does not (55665) -> 30 is named
    assert "W=30" in err


def test_ram_guard_passes_when_all_points_fit():
    W.guard_ram(args(w_points=[4, 12], rss_max_mb=1237.0, ram_cap_mb=24000))


# ---------------------------------------------------------------------------
# exactly-one-cell command construction
# ---------------------------------------------------------------------------

def _bench_defaults() -> dict:
    """Pull the four cell-list defaults out of bench_exact_solver.py's source."""
    tree = ast.parse(BENCH_PATH.read_text())
    found: dict = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        flag = node.args[0].value
        if flag not in ("--k-clair", "--k-marg", "--k-marg-probe",
                        "--python-k-clair"):
            continue
        kw = {k.arg: k.value for k in node.keywords}
        assert getattr(kw.get("nargs"), "value", None) == "*", (
            f"{flag} is no longer nargs='*' — the empty-flag suppression trick "
            f"the driver relies on is broken")
        found[flag] = ast.literal_eval(kw["default"])
    return found


def test_bench_cell_defaults_are_what_the_driver_assumes():
    """If these drift, `cell_flags` must be revisited — hence a hard pin."""
    assert _bench_defaults() == {
        "--k-clair": [4, 5, 6],
        "--k-marg": [3, 4],
        "--k-marg-probe": [5],
        "--python-k-clair": [4],
    }


def _replica_parser() -> argparse.ArgumentParser:
    """An argparse equivalent to the bench's cell options (same specs)."""
    d = _bench_defaults()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--k-clair", type=int, nargs="*", default=d["--k-clair"])
    ap.add_argument("--k-marg", type=int, nargs="*", default=d["--k-marg"])
    ap.add_argument("--k-marg-probe", type=int, nargs="*",
                    default=d["--k-marg-probe"])
    ap.add_argument("--python-k-clair", type=int, nargs="*",
                    default=d["--python-k-clair"])
    ap.add_argument("--timeout-s", type=int, default=600)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tag", default=None)
    return ap


def _cells(parsed) -> list[tuple[str, str, bool, int, int]]:
    """The bench's own cell-building loop, transcribed."""
    cells = []
    for k in parsed.k_clair:
        cells.append((f"rust_clairvoyant_ab_k{k}", "clairvoyant", True, k,
                      parsed.n))
    for k in parsed.k_marg:
        cells.append((f"rust_marginalized_k{k}", "marginalized", False, k,
                      parsed.n))
    for k in parsed.k_marg_probe:
        cells.append((f"rust_marginalized_k{k}_probe", "marginalized", False,
                      k, 1))
    for k in parsed.python_k_clair:
        cells.append((f"py_clairvoyant_ab_k{k}", "clairvoyant", True, k,
                      parsed.n))
    return cells


def test_bare_defaults_would_run_seven_cells():
    """Control: without the suppression flags the bench runs the full menu."""
    assert len(_cells(_replica_parser().parse_args([]))) == 7


@pytest.mark.parametrize("mode,k,expect_cell", [
    ("marginalized", 4, "rust_marginalized_k4"),
    ("marginalized", 5, "rust_marginalized_k5"),
    ("clairvoyant", 6, "rust_clairvoyant_ab_k6"),
])
def test_generated_argv_runs_exactly_one_cell(mode, k, expect_cell):
    plans = W.plan_commands(args(k=k, mode=mode, w_points=[7]))
    argv = plans[0]["cmd"]
    # strip interpreter/-u/script; the rest is what the bench parses
    assert argv[0] == sys.executable and argv[1] == "-u"
    assert Path(argv[2]) == BENCH_PATH
    # every suppressible option must be present, else its defaults fire
    for flag in ("--k-clair", "--k-marg", "--k-marg-probe",
                 "--python-k-clair"):
        assert flag in argv, f"{flag} missing -> its default cells would run"
    parsed = _replica_parser().parse_args(argv[3:])
    cells = _cells(parsed)
    assert [c[0] for c in cells] == [expect_cell]
    assert parsed.workers == 7
    assert parsed.n == 20
    assert parsed.timeout_s == 3600
    assert parsed.tag == f"wsweep_k{k}_w7"
    assert parsed.out.endswith("/w7")


def test_plan_paths_match_the_bench_artifact_naming():
    plans = W.plan_commands(args(k=5, w_points=[4, 12], out="/tmp/sweep"))
    assert [p["w"] for p in plans] == [4, 12]
    p = plans[1]
    assert p["point_dir"] == Path("/tmp/sweep/w12")
    # bench writes f"BENCH_{tag}_rows.jsonl" into --out
    assert p["rows_path"] == Path(
        "/tmp/sweep/w12/BENCH_wsweep_k5_w12_rows.jsonl")
    assert p["log_path"] == Path("/tmp/sweep/w12/bench.log")


def test_cell_flags_rejects_unknown_mode():
    with pytest.raises(ValueError):
        W.cell_flags(4, "telepathic")


# ---------------------------------------------------------------------------
# parse_point
# ---------------------------------------------------------------------------

def _write_rows(tmp_path, rows) -> Path:
    path = tmp_path / "BENCH_x_rows.jsonl"
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    return path


def test_parse_point_counts_and_sums(tmp_path):
    rows = [
        {"status": "ok", "wall_ms": 1000.0, "rss_peak_mb": 120.0},
        {"status": "ok", "wall_ms": 2500.5, "rss_peak_mb": 640.5},
        {"status": "timeout", "timeout_s": 3600},
        {"status": "timeout", "timeout_s": 3600},
        {"status": "budget"},
    ]
    got = W.parse_point(_write_rows(tmp_path, rows), timeout_s=3600)
    assert got["n"] == 5
    assert got["n_ok"] == 2
    assert got["n_timeout"] == 2
    assert got["n_other"] == 1 and got["other_statuses"] == ["budget"]
    assert got["ok_wall_ms_sum"] == pytest.approx(3500.5)
    assert got["waste_worker_s"] == 7200
    # max is over OK rows only
    assert got["rss_peak_max_mb"] == pytest.approx(640.5)


def test_parse_point_handles_blank_lines_and_no_ok_rows(tmp_path):
    path = tmp_path / "BENCH_x_rows.jsonl"
    path.write_text(json.dumps({"status": "timeout"}) + "\n\n")
    got = W.parse_point(path, timeout_s=600)
    assert got["n"] == 1 and got["n_ok"] == 0
    assert got["rss_peak_max_mb"] == 0.0
    assert got["waste_worker_s"] == 600


def test_parse_point_raises_on_exception_rows(tmp_path):
    """The stale-wheel signature must abort, never be counted as a datum."""
    rows = [{"status": "ok", "wall_ms": 5.0, "rss_peak_mb": 10.0},
            {"status": "EXCEPTION",
             "error": "AttributeError: 'MirrorState' has no 'solve_endgame'"}]
    with pytest.raises(RuntimeError, match="EXCEPTION"):
        W.parse_point(_write_rows(tmp_path, rows), timeout_s=3600)


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

def _pt(w, n_ok, wall_s, n=20, n_timeout=0, rss=500.0):
    return {"w": w, "n": n, "n_ok": n_ok, "n_timeout": n_timeout,
            "point_wall_s": wall_s, "waste_worker_s": n_timeout * 3600,
            "rss_peak_max_mb": rss}


def test_summarize_picks_smallest_w_within_10_percent_not_the_argmax():
    # throughput: W4 = 20/h, W12 = 40/h, W30 = 41.6/h (peak, but only +4%)
    points = [_pt(4, 20, 3600), _pt(12, 20, 1800), _pt(30, 26, 2250)]
    s = W.summarize(points)
    assert s["peak_w"] == 30
    assert s["recommended_w"] == 12
    assert "RECOMMEND W=12" in s["recommendation"]


def test_summarize_flags_an_endpoint_peak():
    points = [_pt(4, 10, 3600), _pt(12, 20, 3600), _pt(30, 40, 3600)]
    s = W.summarize(points)
    assert s["peak_w"] == 30 and s["recommended_w"] == 30
    assert s["endpoint_peak"] is True
    assert "ladder endpoint" in s["recommendation"]


def test_summarize_interior_peak_has_no_endpoint_note():
    points = [_pt(4, 10, 3600), _pt(12, 40, 3600), _pt(30, 20, 3600)]
    s = W.summarize(points)
    assert s["peak_w"] == 12 and s["recommended_w"] == 12
    assert s["endpoint_peak"] is False
    assert "ladder endpoint" not in s["recommendation"]


def test_summarize_table_shape_and_derived_columns():
    points = [_pt(4, 18, 3600, n_timeout=2, rss=1237.0)]
    s = W.summarize(points)
    header = ("| W | ok/n | timeouts | point wall min | solved/h | "
              "waste worker-h | rss_peak max MB |")
    lines = s["table"].splitlines()
    assert lines[0] == header
    assert lines[2] == "| 4 | 18/20 | 2 | 60.0 | 18.00 | 2.00 | 1237 |"


def test_summarize_survives_a_zero_wall_point():
    s = W.summarize([_pt(4, 0, 0.0)])
    assert s["rows"][0]["solved_per_h"] == 0.0


# ---------------------------------------------------------------------------
# dry run
# ---------------------------------------------------------------------------

def test_dry_run_exits_zero_and_prints_one_command_per_point(capsys, tmp_path):
    rc = W.main(["--k", "4", "--mode", "marginalized",
                 "--w-points", "4", "12", "30",
                 "--ram-cap-mb", "24000", "--rss-max-mb", "100",
                 "--out", str(tmp_path / "sweep"), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("bench_exact_solver.py") == 3
    assert "DRY RUN" in out
    # nothing was created or run
    assert not (tmp_path / "sweep").exists()


def test_dry_run_still_enforces_the_ram_guard(tmp_path):
    with pytest.raises(SystemExit) as exc:
        W.main(["--k", "4", "--w-points", "30", "--ram-cap-mb", "11000",
                "--rss-max-mb", "1237", "--out", str(tmp_path / "s"),
                "--dry-run"])
    assert exc.value.code == W.RC_RAM
