"""Hermetic tests for scripts/measurement_infra/analyze_oracle_price.py.

Synthetic records in tmp_path; no cluster data, no network, sub-second.
"""
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "measurement_infra" / "analyze_oracle_price.py"

_spec = importlib.util.spec_from_file_location("analyze_oracle_price", SCRIPT)
aop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aop)


def _make_run(tmp_path, rows, failed=0):
    """rows = [(root_id, delta), ...]"""
    rec_dir = tmp_path / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)
    for i, (root, delta) in enumerate(rows):
        (rec_dir / f"r{i:03d}.json").write_text(json.dumps(
            {"rid": f"{root}_s{i}", "root_id": root, "delta": delta,
             "ok": True, "crn_verified": True}))
    for j in range(failed):
        (rec_dir / f"f{j:03d}.json").write_text(json.dumps(
            {"rid": f"bad{j}", "root_id": "bad", "delta": None,
             "ok": False, "crn_verified": False}))
    return tmp_path


def test_no_clustering_matches_naive(tmp_path):
    """One record per root => the sandwich reduces to the naive se * sqrt(G/(G-1))."""
    vals = [1.0, 2.0, -1.0, 4.0, 0.5, -2.5]
    _make_run(tmp_path, [(f"root{i}", v) for i, v in enumerate(vals)])
    d = np.array(vals)
    out = aop.cluster_robust_se(d, np.array([f"root{i}" for i in range(len(vals))]))
    n = len(vals)
    naive = d.std(ddof=1) / math.sqrt(n)
    # sandwich uses the ddof=0 sum of squares with a G/(G-1) correction; with G==n those
    # two corrections cancel exactly.
    assert out == pytest.approx(naive, rel=1e-12)


def test_clustering_inflates_when_roots_correlate(tmp_path):
    """Perfectly correlated pairs within a root => se larger than naive (deff > 1)."""
    rows = [("a", 3.0), ("a", 3.0), ("b", -3.0), ("b", -3.0), ("c", 1.0), ("d", -1.0)]
    d = np.array([v for _, v in rows])
    g = np.array([r for r, _ in rows])
    cr = aop.cluster_robust_se(d, g)
    naive = d.std(ddof=1) / math.sqrt(d.size)
    assert cr > naive


def test_end_to_end_json_and_out_file(tmp_path):
    rows = [("a", 1.0), ("a", 3.0), ("b", -1.0), ("c", 2.0), ("d", 0.0), ("e", 5.0)]
    _make_run(tmp_path, rows, failed=2)
    out_path = tmp_path / "o.json"
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--run-dir", str(tmp_path),
         "--out", str(out_path), "--boot-reps", "500", "--reference-mean", "2.0"],
        capture_output=True, text=True, check=True)
    got = json.loads(res.stdout)
    assert json.loads(out_path.read_text()) == got

    assert got["n_positions"] == 6
    assert got["n_roots"] == 5
    assert got["n_failed"] == 2
    # crn_verified_all is over the COMPLETED (ok) records only; failed ones are excluded
    assert got["crn_verified_all"] is True
    assert got["mean_delta_pts"] == pytest.approx(10.0 / 6)
    # root-collapsed: means 2.0, -1.0, 2.0, 0.0, 5.0
    assert got["root_collapsed_mean"] == pytest.approx(1.6)
    assert got["design_effect"] == pytest.approx(
        got["cluster_robust_se"] ** 2 / got["naive_se"] ** 2)
    assert got["price_ratio"] == pytest.approx(got["mean_delta_pts"] / 2.0)
    assert got["bootstrap_ci95_lo"] < got["mean_delta_pts"] < got["bootstrap_ci95_hi"]
    assert got["bootstrap_seed"] == 20260809


def test_deterministic(tmp_path):
    rows = [("a", 1.0), ("a", 3.0), ("b", -1.0), ("c", 2.0), ("d", 0.0), ("e", 5.0)]
    _make_run(tmp_path, rows)
    cmd = [sys.executable, str(SCRIPT), "--run-dir", str(tmp_path), "--boot-reps", "300"]
    a = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    b = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    assert a == b
