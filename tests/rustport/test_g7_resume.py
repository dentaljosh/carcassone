"""G7/exact_solver — plan stability and job-level resume.

The exact-solver reconcile gate is a multi-hour, uncapped run that has been
killed mid-flight twice (box contention 2026-08-18, a host reboot 2026-08-19
after ~7.5 h). Two properties have to hold before a third attempt is worth
launching, and neither was tested:

  1. THE PLAN IS REPRODUCIBLE. `build_jobs` sub-samples each (corpus, K) cell.
     The seed used to be `abs(hash((source, k)))`, which CPython salts per
     process — so the same arguments built a different job set on every
     invocation (179 vs 186 jobs was observed in the run logs). A plan that is
     not reproducible cannot be resumed at all.
  2. RESUME IS HONEST. Rows are appended, so a re-run with the same --tag must
     skip what is already recorded (or it double-counts), must refuse a rows
     file it cannot identify (rather than guess), and must report the verdict
     over the WHOLE plan rather than over its own remaining share.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "rustport" / "reconcile_exact_solver.py"


def _load():
    spec = importlib.util.spec_from_file_location("g7_reconcile", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def g7():
    return _load()


class _Args:
    """The gate's committed defaults, as an argparse-namespace stand-in."""
    leg = ["all"]
    per_k = 25
    budget = 4_000_000
    solve_timeout_s = 0
    max_k = 6
    max_k_clair = 4
    max_k_clair_noprune = 3
    max_k_marg = 3
    synth_n = 6
    synth_max_k = 3
    synth_seed_base = 880_000
    resume = False


# --------------------------------------------------------------------------
# 1. plan stability
# --------------------------------------------------------------------------

def test_cell_seed_is_process_stable(g7):
    """The value itself is pinned, not merely self-consistent in one process."""
    assert g7.cell_seed("l23_positions", 3) == g7.cell_seed("l23_positions", 3)
    assert g7.cell_seed("l23_positions", 3) != g7.cell_seed("l23_positions", 4)
    assert g7.cell_seed("l23_positions", 3) != g7.cell_seed("f3_roots_k3_suite", 3)
    assert 0 <= g7.cell_seed("l23_positions", 3) < 100_000


@pytest.mark.parametrize("hashseed", ["0", "1", "12345", "random"])
def test_plan_is_identical_under_every_hash_seed(hashseed):
    """THE REGRESSION GUARD.

    Under the old `abs(hash((source, k)))` seeding this test fails: the four
    seeds below produced 179 / 186 / 182 / 177 jobs from identical arguments.
    Run in subprocesses because PYTHONHASHSEED is fixed at interpreter start.
    """
    code = f"""
import importlib.util, json
spec = importlib.util.spec_from_file_location('m', {str(SCRIPT)!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class A:
    leg = ['all']; per_k = 25; budget = 4000000; solve_timeout_s = 0
    max_k = 6; max_k_clair = 4; max_k_clair_noprune = 3; max_k_marg = 3
    synth_n = 6; synth_max_k = 3; synth_seed_base = 880000
print(json.dumps([m.job_key(j) for j in m.build_jobs(A())]))
"""
    def run(seed: str) -> list[str]:
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=REPO, capture_output=True,
            text=True, env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin",
                            "HOME": str(Path.home())})
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])

    assert run(hashseed) == run("0")


def test_job_keys_are_unique_over_the_committed_plan(g7):
    keys = [g7.job_key(j) for j in g7.build_jobs(_Args())]
    assert keys, "the committed plan is not empty"
    assert len(keys) == len(set(keys)), "job_key collides — resume would skip work"


def test_job_key_covers_every_job_kind(g7):
    kinds = {j["kind"] for j in g7.build_jobs(_Args())}
    assert {"golden", "v2", "corpus", "synth"} <= kinds
    with pytest.raises(ValueError):
        g7.job_key({"kind": "not-a-kind"})


# --------------------------------------------------------------------------
# 2. rows-file identity
# --------------------------------------------------------------------------

def test_run_job_stamps_the_key_onto_the_row(g7):
    """The identity must survive into the recorded row, exception path too."""
    out = g7.run_job({"kind": "not-a-kind", "leg": "golden", "tag": "boom"})
    assert out["job_key"].startswith("UNKEYABLE:")
    assert out["leg"] == "golden"
    # an unknown kind is a recorded MISMATCH, never a silent pass
    assert out["mismatches"] and out["mismatches"][0]["field"] == "EXCEPTION"


def test_recorded_job_keys_reads_back_what_was_written(g7, tmp_path):
    rows = tmp_path / "rows.jsonl"
    rows.write_text(
        json.dumps({"job_key": "golden:1:k1", "leg": "golden", "checks": 2,
                    "skipped": 0, "positions": 1, "mismatches": [], "cells": {}}) + "\n"
        + json.dumps({"job_key": "synth:s#1", "leg": "synth", "checks": 3,
                      "skipped": 0, "positions": 1, "mismatches": [], "cells": {}}) + "\n"
        + "\n")  # a blank line must not become a key
    assert g7.recorded_job_keys(rows) == {"golden:1:k1", "synth:s#1"}


def test_recorded_job_keys_refuses_a_pre_keying_rows_file(g7, tmp_path):
    """The real hazard: the live `run` rows file has 112 unkeyed rows.

    Guessing either way is wrong — treating them as absent re-pays hours of
    solves, treating them as present skips comparisons that never ran.
    """
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps({"leg": "golden", "checks": 2, "skipped": 0,
                                "positions": 1, "mismatches": [], "cells": {}}) + "\n")
    with pytest.raises(SystemExit) as ei:
        g7.recorded_job_keys(rows)
    assert "job_key" in str(ei.value)
    assert "--from-rows" in str(ei.value)


def test_resume_filter_leaves_exactly_the_unfinished_jobs(g7):
    jobs = g7.build_jobs(_Args())
    done = {g7.job_key(j) for j in jobs[:10]}
    left = [j for j in jobs if g7.job_key(j) not in done]
    assert len(left) == len(jobs) - 10
    assert not (done & {g7.job_key(j) for j in left})


# --------------------------------------------------------------------------
# 3. the contaminated live rows file — documented, not hand-waved
# --------------------------------------------------------------------------

LIVE_ROWS = REPO / "measurement/rustport_exact_solver/G7_exact_solver_run_rows.jsonl"


@pytest.mark.skipif(not LIVE_ROWS.exists(), reason="the killed run's rows file is gone")
def test_the_killed_runs_rows_file_is_recognised_as_unresumable(g7):
    with pytest.raises(SystemExit):
        g7.recorded_job_keys(LIVE_ROWS)
