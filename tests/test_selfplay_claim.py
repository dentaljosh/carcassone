"""Tests for the work-stealing claim primitive in scripts/run_selfplay_iter.py.

`_try_claim` / `_claim_is_stale` / `_claim_path` let multiple self-play workers
— on one box, or across machines on a shared filesystem — atomically claim
game seeds so each game is played exactly once. The O_CREAT|O_EXCL create is
the sole arbiter; these tests exercise it under thread and process contention.
Cross-MACHINE atomicity (over a CIFS mount) is verified separately by a live
two-box test — not here.
"""
from __future__ import annotations

import importlib.util
import multiprocessing as mp
import os
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_selfplay_iter.py"


@pytest.fixture(scope="module")
def rsi():
    """Import run_selfplay_iter.py as a module (it's a script, not a package)."""
    spec = importlib.util.spec_from_file_location("run_selfplay_iter", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_selfplay_iter"] = mod
    spec.loader.exec_module(mod)
    return mod


def _race_threads(target, n):
    """Run `target` (a no-arg callable) on n threads released simultaneously."""
    barrier = threading.Barrier(n)
    results: list = []
    lock = threading.Lock()

    def runner():
        barrier.wait()
        won = target()
        with lock:
            results.append(won)

    threads = [threading.Thread(target=runner) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_claim_path(rsi, tmp_path):
    assert rsi._claim_path(tmp_path, 42).name == "seed_000042.claim"


def test_try_claim_fresh_then_taken(rsi, tmp_path):
    claim = rsi._claim_path(tmp_path, 1)
    assert rsi._try_claim(claim, "boxA", 5400) is True
    assert claim.exists()
    fields = claim.read_bytes().decode().split(":")
    assert len(fields) == 3 and fields[0] == "boxA"
    # The now-fresh claim is refused to a second caller.
    assert rsi._try_claim(claim, "boxB", 5400) is False


def test_claim_is_stale(rsi, tmp_path):
    missing = rsi._claim_path(tmp_path, 2)
    assert rsi._claim_is_stale(missing, 5400) is True       # absent -> free
    rsi._try_claim(missing, "boxA", 5400)
    assert rsi._claim_is_stale(missing, 5400) is False      # just made -> fresh
    old = time.time() - 10_000
    os.utime(missing, (old, old))
    assert rsi._claim_is_stale(missing, 5400) is True       # aged out -> stale


def test_stale_claim_is_reclaimed(rsi, tmp_path):
    claim = rsi._claim_path(tmp_path, 3)
    rsi._try_claim(claim, "deadbox", 5400)
    old = time.time() - 10_000
    os.utime(claim, (old, old))
    assert rsi._try_claim(claim, "livebox", 5400) is True   # stale -> re-claimed
    assert claim.read_bytes().decode().split(":")[0] == "livebox"
    assert rsi._claim_is_stale(claim, 5400) is False        # mtime refreshed


def test_staleness_ignores_claim_content(rsi, tmp_path):
    # Staleness is mtime-based, so claim *content* is irrelevant: a garbled
    # but freshly-written claim is NOT stolen (it may be a sibling mid-write);
    # the same garbled claim, once aged out, IS re-claimable.
    claim = rsi._claim_path(tmp_path, 4)
    claim.write_bytes(b"garbage-not-host-pid-ts")
    assert rsi._try_claim(claim, "boxB", 5400) is False
    old = time.time() - 10_000
    os.utime(claim, (old, old))
    assert rsi._try_claim(claim, "boxB", 5400) is True


def test_32_threads_race_one_winner(rsi, tmp_path):
    claim = rsi._claim_path(tmp_path, 5)
    # stale_secs huge -> no stale-recovery -> a pure O_EXCL create race.
    results = _race_threads(lambda: rsi._try_claim(claim, "box", 99_999), 32)
    assert sum(results) == 1
    assert len(list(tmp_path.glob("seed_*.claim"))) == 1


def test_32_threads_race_for_one_stale_claim(rsi, tmp_path):
    # Many workers all observe the SAME abandoned claim and race to recover it.
    # The fast-path O_EXCL create is exactly-one-winner; stale-recovery is not.
    # A worker whose staleness check predates an earlier winner's re-created
    # claim can rename that fresh claim aside and win too (the accepted D15
    # TOCTOU race — REVIEW_LOG.md D15 / DECISIONS.md 2026-05-19). So the winner
    # count is bounded, not exact: at least 1 (the seed is never lost), at most
    # N (a bounded number of duplicate crash-recovery replays, never corruption
    # — the atomic .npz write is the real correctness layer).
    claim = rsi._claim_path(tmp_path, 6)
    rsi._try_claim(claim, "deadbox", 5400)
    old = time.time() - 10_000
    os.utime(claim, (old, old))
    n = 32
    results = _race_threads(lambda: rsi._try_claim(claim, "box", 5400), n)
    assert 1 <= sum(results) <= n


def test_fork_processes_race_one_winner(rsi, tmp_path):
    # Cross-address-space race: 16 forked processes, separate fd tables.
    claim = rsi._claim_path(tmp_path, 7)
    n = 16
    ctx = mp.get_context("fork")
    q = ctx.Queue()

    def racer():  # closure — fork inherits the target directly, so this is fine
        q.put(rsi._try_claim(claim, "box", 99_999))

    procs = [ctx.Process(target=racer) for _ in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
    results = [q.get() for _ in range(n)]
    assert sum(results) == 1
    assert len(list(tmp_path.glob("seed_*.claim"))) == 1
