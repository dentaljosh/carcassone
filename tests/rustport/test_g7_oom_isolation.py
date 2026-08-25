"""G7/exact_solver — per-job memory AND time isolation (2026-08-23 / 08-24).

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

2026-08-24 addition — the per-job TIME cap (`--job-time-cap-secs`, owner-
authorized "2hr cutoff"). Same contract as the memory cap, and the same trap:
a cutoff must be a RECORDED `TIME_SKIPPED` row (resume-compatible, fail-loud,
never a mismatch), never the legacy `EXCEPTION` mismatch that 9ca3ce44 had to
fix for `MemoryError`. The time tests below are deliberately REAL-SHAPE (the
EP-D3 lesson): they drive the real `run_job_capped`/`run_job`/`_time_row`/
`merge`/`rebuild_from_rows` against real row dicts, not plain-attribute mocks,
so a row that would not survive the actual writer/reader round-trip fails here.
"""
from __future__ import annotations

import importlib.util
import json
import signal
import sys
import time
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "rustport" / "reconcile_exact_solver.py"

TINY_CAP = 64 * 1024 * 1024  # 64 MiB — small enough to trip fast, big enough
                              # that Python's own startup/import footprint
                              # inside the forked child does not itself trip it

ROOMY_CAP = 8 * 1024 * 1024 * 1024  # 8 GiB — a memory cap that will NOT trip,
                                    # for the time-cap tests: they must prove
                                    # the TIME classifier fires, and a child
                                    # that OOMs first would prove nothing
TINY_TIME_CAP = 1                   # seconds. RLIMIT_CPU has 1s granularity,
                                    # so this is the floor; each time-cap test
                                    # below costs ~1-2s of one core


def _burn_cpu() -> None:
    """Spin on integer arithmetic — CPU-bound, allocation-free enough not to
    trip a memory cap. Never returns; the kernel's CPU cap ends it."""
    x = 0
    while True:
        x = (x + 1) % 1_000_003


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
# 3b. regression for the 2026-08-24 misclassification incident: a MemoryError
#     raised DEEP inside the dispatched job function (not at run_job's own
#     top level, and not via a wrapper-level mock of run_job itself) must
#     propagate OUT of the real run_job, not get swallowed by its own
#     exception firewall into an EXCEPTION mismatch. Job
#     corpus:l23:l23_positions:3200000129 hit exactly this: the MemoryError
#     fired inside `job_corpus` -> `check_position` -> `_timed_py_solve` ->
#     `endgame_solver._value_ab` (recursing) -> `_key` ->
#     `game_wrapper.string_representation`, and surfaced through run_job's
#     `except Exception` as a fabricated correctness mismatch instead of
#     OOM_SKIPPED. These tests exercise the REAL `run_job` — only the leaf
#     job-kind function (`job_corpus`) is faked, several real call frames
#     below where run_job's own firewall lives, and the OOM fires from a
#     nested inner() call rather than a bare top-level raise.
# --------------------------------------------------------------------------

def test_run_job_propagates_memoryerror_not_a_mismatch(g7, monkeypatch):
    """The exact chokepoint: run_job's own try/except must re-raise a
    MemoryError from the dispatched job function rather than convert it into
    an `EXCEPTION` mismatch row."""
    def fake_job_corpus(job):
        def inner():
            raise MemoryError()
        inner()
        return {}  # pragma: no cover

    monkeypatch.setattr(g7, "job_corpus", fake_job_corpus)
    job = {"kind": "corpus", "leg": "l23", "tag": "corpus:l23:fake:1"}
    with pytest.raises(MemoryError):
        g7.run_job(job)


def test_job_over_cap_memoryerror_from_real_check_path_is_oom_skipped(g7, monkeypatch):
    """End-to-end: drive the REAL `run_job` (not monkeypatched — only
    `job_corpus`, the leaf, is faked) through `run_job_capped` and confirm the
    result lands as OOM_SKIPPED with zero mismatches and zero checks, which is
    what the incident row should have been."""
    def fake_job_corpus(job):
        def inner():
            raise MemoryError()
        inner()
        return {}  # pragma: no cover

    monkeypatch.setattr(g7, "job_corpus", fake_job_corpus)
    job = {"kind": "corpus", "leg": "l23", "tag": "corpus:l23:fake:1"}
    out = g7.run_job_capped(job, TINY_CAP)
    assert out["status"] == "OOM_SKIPPED"
    assert out["mismatches"] == []
    assert out["checks"] == 0
    assert out["oom_skipped"] == 1
    assert out["leg"] == "l23"


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
    row = g7._oom_row({"kind": "fake", "leg": "golden", "tag": "t"},
                      TINY_CAP, -9)
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps(row) + "\n")

    keys = g7.recorded_job_keys(rows)
    assert row["job_key"] in keys


# ==========================================================================
# 6. the per-job TIME cap (`--job-time-cap-secs`, 2026-08-24).
#
#    Same three obligations as the memory cap, each one covered below:
#      (a) a job over the cap is RECORDED, as a distinct `TIME_SKIPPED` row
#      (b) it is NEVER a mismatch and never an OOM  — the 9ca3ce44 trap
#      (c) `--resume` skips it and the summary counts it separately
# ==========================================================================

def test_job_over_time_cap_is_time_skipped(g7, monkeypatch):
    """(a) The shipped mechanism: the child burns its RLIMIT_CPU budget and
    the kernel terminates it with SIGXCPU. The parent must read that exit
    signature as TIME, not as the "died without a payload => OOM" default."""
    monkeypatch.setattr(g7, "run_job", lambda job: _burn_cpu())

    out = g7.run_job_capped(_job("slow"), ROOMY_CAP, TINY_TIME_CAP)

    assert out["status"] == "TIME_SKIPPED"
    assert out["time_cap_secs"] == TINY_TIME_CAP
    assert out["kill_reason"] == "rlimit_cpu"
    assert out["exitcode"] == -int(signal.SIGXCPU)
    assert out["time_skipped"] == 1
    assert out["time_job_keys"] == [out["job_key"]]
    assert out["job_key"].startswith("UNKEYABLE:")
    assert out["leg"] == "golden"
    # measured, not inferred: the child really did spend its CPU budget
    assert out["child_cpu_s"] >= TINY_TIME_CAP


def test_time_capped_job_is_not_a_mismatch_and_not_an_oom(g7, monkeypatch):
    """(b) The 9ca3ce44 trap, restated for the time cap: a cutoff is a
    resource limitation. It must credit no checks, fabricate no mismatch, and
    not be miscounted against the memory cap."""
    monkeypatch.setattr(g7, "run_job", lambda job: _burn_cpu())

    out = g7.run_job_capped(_job("slow"), ROOMY_CAP, TINY_TIME_CAP)

    assert out["mismatches"] == []
    assert out["checks"] == 0
    assert out["positions"] == 0
    assert out["oom_skipped"] == 0
    assert out.get("status") != "OOM_SKIPPED"


def test_time_cap_alone_still_isolates_with_no_memory_cap(g7, monkeypatch):
    """`--job-mem-cap-gb 0 --job-time-cap-secs N` must still fork a child: a
    time cap cannot be enforced inline without killing the pool worker that
    owns the job, so "no memory cap" must not mean "no isolation"."""
    monkeypatch.setattr(g7, "run_job", lambda job: _burn_cpu())

    out = g7.run_job_capped(_job("slow"), 0, TINY_TIME_CAP)

    assert out["status"] == "TIME_SKIPPED"
    assert out["exitcode"] == -int(signal.SIGXCPU)


def test_both_caps_off_is_still_an_inline_passthrough(g7, monkeypatch):
    """...and the converse: with BOTH caps off the wrapper is still the
    pre-2026-08-23 inline passthrough (the debugger / unit-test path)."""
    calls = []

    def fake(job):
        calls.append(job)
        return {"leg": job["leg"], "checks": 1, "skipped": 0, "positions": 1,
                "mismatches": [], "cells": {}, "job_key": "x"}

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job(), 0, 0)
    assert calls == [_job()]
    assert out["checks"] == 1


def test_job_under_the_time_cap_reports_normally(g7, monkeypatch):
    """A fast job must pass through untouched when a time cap is armed —
    the cap must not stamp a status on healthy work."""
    def fake(job):
        return {"leg": job["leg"], "checks": 3, "skipped": 0, "positions": 1,
                "mismatches": [], "cells": {"c": 3}, "job_key": "ok-job"}

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job(), ROOMY_CAP, 600)
    assert out == {"leg": "golden", "checks": 3, "skipped": 0, "positions": 1,
                   "mismatches": [], "cells": {"c": 3}, "job_key": "ok-job"}
    assert out.get("status") is None


def test_wall_backstop_kills_a_child_that_burns_no_cpu(g7, monkeypatch):
    """RLIMIT_CPU is blind to a child that is over its deadline without
    burning CPU (blocked on I/O, thrashing swap). The parent's wall backstop
    must catch it and record the SAME TIME_SKIPPED row, tagged `wall`."""
    monkeypatch.setattr(g7, "WALL_GRACE_S", 1)
    monkeypatch.setattr(g7, "run_job", lambda job: time.sleep(120))

    t0 = time.time()
    out = g7.run_job_capped(_job("blocked"), ROOMY_CAP, TINY_TIME_CAP)
    elapsed = time.time() - t0

    assert out["status"] == "TIME_SKIPPED"
    assert out["kill_reason"] == "wall"
    assert out["exitcode"] == -int(signal.SIGKILL)  # the parent killed it
    assert out["time_skipped"] == 1
    assert out["mismatches"] == []
    # it really was the wall and not the CPU cap: the child never computed
    assert out["child_cpu_s"] < TINY_TIME_CAP
    assert elapsed < 60  # the parent did not wait for the 120s sleep


# --------------------------------------------------------------------------
# 6b. REAL-SHAPE (EP-D3): drive the real `run_job` — only the leaf job-kind
#     function is faked — so the classification is proved through every real
#     frame between the cutoff and the row, exactly as the 9ca3ce44 tests do
#     for MemoryError. A wrapper-level mock of `run_job` would not exercise
#     `run_job`'s own broad `except Exception`, which is where the equivalent
#     misclassification bug lived.
# --------------------------------------------------------------------------

def test_real_run_job_over_time_cap_is_time_skipped_not_a_mismatch(g7, monkeypatch):
    def fake_job_corpus(job):
        def inner():
            _burn_cpu()
        inner()
        return {}  # pragma: no cover

    monkeypatch.setattr(g7, "job_corpus", fake_job_corpus)
    job = {"kind": "corpus", "leg": "l23", "tag": "corpus:l23:fake:1"}

    out = g7.run_job_capped(job, ROOMY_CAP, TINY_TIME_CAP)

    assert out["status"] == "TIME_SKIPPED"
    assert out["mismatches"] == []      # NOT the legacy EXCEPTION row
    assert out["checks"] == 0
    assert out["time_skipped"] == 1
    assert out["oom_skipped"] == 0
    assert out["leg"] == "l23"


def test_job_time_cap_exceeded_derives_from_baseexception(g7):
    """The structural guarantee: `_JobTimeCapExceeded` cannot be caught by a
    broad `except Exception` anywhere in the solver call tree, so the
    9ca3ce44 misclassification is impossible by construction rather than by
    remembering a re-raise clause at every layer."""
    assert issubclass(g7._JobTimeCapExceeded, BaseException)
    assert not issubclass(g7._JobTimeCapExceeded, Exception)


def test_real_run_job_propagates_the_timeout_exception(g7, monkeypatch):
    """The typed in-child path, at run_job's own chokepoint: a
    `_JobTimeCapExceeded` raised deep inside the dispatched job function must
    come back OUT of the real `run_job`, never be converted into an
    `EXCEPTION` mismatch row."""
    def fake_job_corpus(job):
        def inner():
            raise g7._JobTimeCapExceeded()
        inner()
        return {}  # pragma: no cover

    monkeypatch.setattr(g7, "job_corpus", fake_job_corpus)
    job = {"kind": "corpus", "leg": "l23", "tag": "corpus:l23:fake:1"}
    with pytest.raises(g7._JobTimeCapExceeded):
        g7.run_job(job)


def test_in_child_timeout_exception_lands_as_time_skipped(g7, monkeypatch):
    """...and end-to-end through the isolation wrapper: the child's
    `("TIMEOUT", None)` report must be classified TIME, never folded into the
    OOM row that catches every other payload-less child."""
    def fake(job):
        raise g7._JobTimeCapExceeded()

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job("typed"), ROOMY_CAP, 600)

    assert out["status"] == "TIME_SKIPPED"
    assert out["kill_reason"] == "in_child"
    assert out["mismatches"] == []
    assert out["oom_skipped"] == 0


def test_a_genuine_crash_under_a_time_cap_is_still_a_mismatch(g7, monkeypatch):
    """The inverse guard: arming a time cap must not start swallowing real
    bugs. A plain exception is still a mismatch, not a TIME_SKIPPED."""
    def fake(job):
        raise ValueError("a real bug, not a resource limit")

    monkeypatch.setattr(g7, "run_job", fake)
    out = g7.run_job_capped(_job("bug"), ROOMY_CAP, 600)

    assert out.get("status") not in ("TIME_SKIPPED", "OOM_SKIPPED")
    assert out["time_skipped"] == 0
    assert out["mismatches"] and out["mismatches"][0]["field"] == "EXCEPTION"


# --------------------------------------------------------------------------
# 6c. (c) resume + summary: a TIME_SKIPPED row must be replan-proof and must
#     be counted in its OWN bucket, separate from OOMs and from mismatches.
# --------------------------------------------------------------------------

def test_resume_recognises_a_time_skipped_row_as_recorded(g7, tmp_path):
    row = g7._time_row({"kind": "fake", "leg": "l23", "tag": "t"},
                       7200, -int(signal.SIGXCPU), "rlimit_cpu", 7201.4, 7200.2)
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps(row) + "\n")

    keys = g7.recorded_job_keys(rows)
    assert row["job_key"] in keys


def test_summary_counts_time_skipped_separately(g7, tmp_path, capsys):
    """REAL-SHAPE aggregation: write the three row kinds this gate can emit
    into a real rows file and rebuild the verdict through the real
    `rebuild_from_rows`/`merge`. The time cutoff must land in `time_skipped`,
    leave `oom_skipped` and `n_mismatches` alone, and NOT flip the verdict —
    a resource cutoff is a documented hole in coverage, not a finding."""
    good = g7.blank()
    good.update({"leg": "l23", "job_key": "corpus:l23:src:1", "checks": 4,
                 "positions": 2, "cells": {"k3:marginalized": 4}})
    oomed = g7._oom_row({"kind": "fake", "leg": "l23", "tag": "oom"},
                        26 * 1024 ** 3, -9)
    timed = g7._time_row({"kind": "fake", "leg": "l23", "tag": "slow"},
                         7200, -int(signal.SIGXCPU), "rlimit_cpu", 7201.4, 7200.2)

    rows = tmp_path / "G7_exact_solver_t_rows.jsonl"
    rows.write_text("".join(json.dumps(r, sort_keys=True, default=str) + "\n"
                            for r in (good, oomed, timed)))

    rc = g7.rebuild_from_rows(rows, types.SimpleNamespace(max_mismatch_report=200))
    payload = json.loads((tmp_path / "G7_exact_solver_t_partial.json").read_text())

    assert payload["time_skipped"] == 1
    assert payload["time_job_keys"] == [timed["job_key"]]
    assert payload["oom_skipped"] == 1          # not double-counted as an OOM
    assert payload["n_mismatches"] == 0         # and never a mismatch
    assert payload["checks"] == 4
    assert payload["per_leg"]["l23"]["time_skipped"] == 1
    assert payload["per_leg"]["l23"]["oom_skipped"] == 1
    # a cutoff does NOT flip the verdict
    assert payload["verdict"] == "PASS"
    assert rc == 0
    # ...and it is fail-LOUD on stdout, not only in the JSON
    assert "TIME_SKIPPED" in capsys.readouterr().out


def test_announce_skip_names_which_cap_fired(g7, capsys):
    """An operator tailing a multi-hour log must be able to tell the two caps
    apart without opening the JSON."""
    g7._announce_skip(g7._time_row({"kind": "fake", "leg": "l23", "tag": "t"},
                                   7200, -int(signal.SIGXCPU), "rlimit_cpu",
                                   7201.4, 7200.2))
    g7._announce_skip(g7._oom_row({"kind": "fake", "leg": "l23", "tag": "t"},
                                  26 * 1024 ** 3, -9))
    text = capsys.readouterr().out
    assert "TIME_SKIPPED" in text and "7200s" in text and "rlimit_cpu" in text
    assert "OOM_SKIPPED" in text


# --------------------------------------------------------------------------
# 6d. the pool survives a time-capped job exactly as it survives an OOM one
# --------------------------------------------------------------------------

def test_pool_survives_one_time_capped_job_among_several(g7, monkeypatch):
    def fake(job):
        if job["tag"] == "the-slow-one":
            _burn_cpu()
        return {"leg": job["leg"], "checks": 1, "skipped": 0, "positions": 1,
                "mismatches": [], "cells": {}, "job_key": job["tag"]}

    monkeypatch.setattr(g7, "run_job", fake)

    jobs = [_job(f"good-{i}") for i in range(3)] + [_job("the-slow-one")] + \
        [_job(f"good-{i}") for i in range(3, 6)]

    import functools
    worker_fn = functools.partial(g7.run_job_capped, cap_bytes=ROOMY_CAP,
                                  time_cap_secs=TINY_TIME_CAP)
    with g7.NestablePool(3) as pool:
        results = list(pool.imap_unordered(worker_fn, jobs, chunksize=1))

    assert len(results) == len(jobs)  # every job produced a row — none lost
    statuses = [r.get("status") for r in results]
    assert statuses.count("TIME_SKIPPED") == 1
    assert statuses.count("OOM_SKIPPED") == 0
    good = [r for r in results if r.get("status") is None]
    assert len(good) == 6
    assert all(r["checks"] == 1 for r in good)
