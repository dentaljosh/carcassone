"""G7/exact_solver — per-job memory isolation (2026-08-23).

`reconcile_exact_solver` was OOM-killed inside its systemd scope TWICE
(workers=3/28G, then workers=2/34G — dmesg showed one worker's Python
marginalized solve at 27.6GB RSS and still growing). The whole-scope cap means
one pathological job kills the entire run and wastes every sibling job's
finished work.

`run_job_capped` isolates each job in its own forked subprocess with its own
`RLIMIT_AS` cap, so a job that blows the cap dies ALONE — the pool worker that
forked it survives — and gets recorded as a distinct `OOM_SKIPPED` row (never
a mismatch, never silent) so `--resume` will not replan it forever.

These tests exercise the isolation wrapper directly against fake, fast,
deterministic "jobs" (monkeypatching the module's `run_job`) rather than
paying for a real multi-gigabyte allocation or a real solver call — the point
under test is the subprocess/pipe/cap plumbing, not the solver.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "rustport" / "reconcile_exact_solver.py"

TINY_CAP = 64 * 1024 * 1024  # 64 MiB — small enough to trip fast, big enough
                              # that Python's own startup/import footprint
                              # inside the forked child does not itself trip it


def _load():
    spec = importlib.util.spec_from_file_location("g7_oom_isolation", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # A real, importable name in sys.modules — required for
    # `test_pool_survives_one_oom_job_among_several` below: Pool.imap_unordered
    # pickles the (func, args) task tuple even under the "fork" start method
    # (it hands tasks to workers over an internal queue), and pickling a
    # function looks it up as `sys.modules[obj.__module__].obj.__qualname__`.
    sys.modules[mod.__name__] = mod
    return mod


@pytest.fixture()
def g7():
    return _load()


def _job(tag: str = "t") -> dict:
    # Deliberately NOT a real "golden"/"corpus"/etc. job — job_key() cannot
    # key it, so it falls to the UNKEYABLE: fallback, which is fine here: the
    # isolation wrapper's contract does not depend on job shape.
    return {"kind": "fake", "leg": "golden", "tag": tag}


# --------------------------------------------------------------------------
# 1. the wrapper is a no-op passthrough when isolation is disabled
# --------------------------------------------------------------------------

def test_zero_cap_disables_isolation_and_calls_run_job_inline(g7, monkeypatch):
    calls = []

    def fake(job):
        calls.append(job)
        return {"leg": job["leg"], "checks": 1, "skipped": 0, "positions": 1,
                "mismatches": [], "cells": {}, "job_key": "x"}

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job(), 0)
    assert calls == [_job()]
    assert out["checks"] == 1


# --------------------------------------------------------------------------
# 2. a job that stays under the cap reports through unchanged
# --------------------------------------------------------------------------

def test_job_under_cap_reports_normally(g7, monkeypatch):
    def fake(job):
        return {"leg": job["leg"], "checks": 3, "skipped": 0, "positions": 1,
                "mismatches": [], "cells": {"c": 3}, "job_key": "ok-job"}

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job(), TINY_CAP)
    assert out == {"leg": "golden", "checks": 3, "skipped": 0, "positions": 1,
                    "mismatches": [], "cells": {"c": 3}, "job_key": "ok-job"}
    assert out.get("status") != "OOM_SKIPPED"


# --------------------------------------------------------------------------
# 3. a job that exceeds the cap is recorded OOM_SKIPPED, not a crash and not
#    a silent nothing
# --------------------------------------------------------------------------

def test_job_over_cap_via_memoryerror_is_oom_skipped(g7, monkeypatch):
    """The clean case: the child's own allocation raises `MemoryError`."""
    def fake(job):
        data = []
        for _ in range(10_000):
            data.append(bytearray(1024 * 1024))  # will not reach 10GB
        return {"never": "reached"}  # pragma: no cover

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job("mem"), TINY_CAP)
    assert out["status"] == "OOM_SKIPPED"
    assert out["cap_bytes"] == TINY_CAP
    assert out["oom_skipped"] == 1
    assert out["oom_job_keys"] == [out["job_key"]]
    assert out["job_key"].startswith("UNKEYABLE:")
    # not a correctness finding: no mismatch, no check credited
    assert out["mismatches"] == []
    assert out["checks"] == 0
    assert out["leg"] == "golden"


def test_job_that_hard_crashes_under_a_cap_is_also_oom_skipped(g7, monkeypatch):
    """The dirty case: the child is killed by a signal before it can report
    anything (e.g. a Rust allocator aborting rather than raising).  From the
    outside this is indistinguishable from — and treated the same as — an
    OOM: something that fails ONLY under isolation, capped or not, is not a
    distinction this gate needs to make (run_job's own firewall already
    reports every recoverable failure as a normal mismatch)."""
    def fake(job):
        import os
        os.abort()

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job("crash"), TINY_CAP)
    assert out["status"] == "OOM_SKIPPED"
    assert out["exitcode"] == -6  # SIGABRT
    assert out["oom_skipped"] == 1


def test_a_genuine_non_memory_crash_is_still_a_mismatch_not_an_oom(g7, monkeypatch):
    """A real bug inside the isolated child (any Python exception other than
    MemoryError) must be reported as the SAME kind of thing run_job's own
    firewall would have produced — a mismatch — not folded into OOM_SKIPPED,
    which would misreport a correctness bug as a resource limitation."""
    def fake(job):
        raise ValueError("a real bug, not a resource limit")

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job("bug"), TINY_CAP)
    assert out.get("status") != "OOM_SKIPPED"
    assert out["oom_skipped"] == 0
    assert out["mismatches"] and out["mismatches"][0]["field"] == "EXCEPTION"
    assert "ValueError" in out["mismatches"][0]["error"]


# --------------------------------------------------------------------------
# 4. the pool survives: one OOM job among several must not stall or kill the
#    others, and every job still gets a row
# --------------------------------------------------------------------------

def test_pool_survives_one_oom_job_among_several(g7, monkeypatch):
    def fake(job):
        if job["tag"] == "the-bad-one":
            data = []
            for _ in range(10_000):
                data.append(bytearray(1024 * 1024))
            return {"never": "reached"}  # pragma: no cover
        return {"leg": job["leg"], "checks": 1, "skipped": 0, "positions": 1,
                "mismatches": [], "cells": {}, "job_key": job["tag"]}

    monkeypatch.setattr(g7, "run_job", fake)

    jobs = [_job(f"good-{i}") for i in range(3)] + [_job("the-bad-one")] + \
        [_job(f"good-{i}") for i in range(3, 6)]

    import functools
    worker_fn = functools.partial(g7.run_job_capped, cap_bytes=TINY_CAP)
    # The production pool, NOT a plain ctx.Pool: run_job_capped forks a
    # per-job child from inside the worker, and a plain Pool's workers are
    # daemons, which are hard-blocked from having children. Regression cover
    # for exactly that: this test failed silently-open (0 OOM_SKIPPED, the
    # bad job completing its full allocation) before NestablePool existed.
    with g7.NestablePool(3) as pool:
        results = list(pool.imap_unordered(worker_fn, jobs, chunksize=1))

    assert len(results) == len(jobs)  # every job produced a row — none lost
    statuses = [r.get("status") for r in results]
    assert statuses.count("OOM_SKIPPED") == 1
    good = [r for r in results if r.get("status") != "OOM_SKIPPED"]
    assert len(good) == 6
    assert all(r["checks"] == 1 for r in good)


# --------------------------------------------------------------------------
# 5. resume: an OOM_SKIPPED row is recognised the same as any other recorded
#    row — it must not be replanned forever
# --------------------------------------------------------------------------

def test_resume_recognises_an_oom_skipped_row_as_recorded(g7, tmp_path):
    import json

    row = g7._oom_row({"kind": "fake", "leg": "golden", "tag": "t"},
                      TINY_CAP, -9)
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps(row) + "\n")

    keys = g7.recorded_job_keys(rows)
    assert row["job_key"] in keys
