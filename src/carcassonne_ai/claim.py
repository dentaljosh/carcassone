"""Work-stealing claim primitive.

A caller claims a unit of work by exclusively creating a `.claim` file before
doing the work. The O_CREAT|O_EXCL create is the SOLE arbiter — across
processes, and across machines on a shared filesystem (CIFS/NFS), exactly one
caller can create the file. The permanent "done" marker is whatever the caller
writes atomically (rename-into-place); the `.claim` is only a best-effort lock.

Used by both `scripts/run_selfplay_iter.py` (claims a `seed_NNNNNN.claim` next
to each future `.npz`) and `scripts/eval_iter_head_to_head.py` (claims a
`.claim` next to each per-game JSON).
"""
from __future__ import annotations

import errno
import os
import sys
import time
from pathlib import Path


def claim_body(host: str) -> bytes:
    """`host:pid:unix_ts` — informational (identifies the claim's owner for
    debugging). Staleness is judged from the file's mtime, not this ts."""
    return f"{host}:{os.getpid()}:{int(time.time())}".encode()


def is_stale(claim_path: Path, stale_secs: int) -> bool:
    """True if the claim looks abandoned (re-claimable), judged by the claim
    file's mtime — its creation time, since a claim file is written once and
    never touched again.

    mtime, not the embedded timestamp, is deliberate: it stays correct across
    the brief window between the O_EXCL create and the body write. A
    just-created, not-yet-written claim is young -> NOT stale -> a sibling
    mid-claim is never stolen from. A vanished claim counts as stale (the work
    is free again); a transient stat() error counts as NOT stale, so a healthy
    claim survives a filesystem hiccup."""
    try:
        mtime = claim_path.stat().st_mtime
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return (time.time() - mtime) > stale_secs


def _fd_write(fd: int, host: str) -> None:
    try:
        os.write(fd, claim_body(host))
    finally:
        os.close(fd)


def try_claim(claim_path: Path, host: str, stale_secs: int) -> bool:
    """Claim a unit of work for this caller. Returns True iff claimed.

    Fast path: an O_CREAT|O_EXCL create — across processes, and across machines
    on a shared filesystem, exactly one caller can create the file. This path
    is exactly-once.

    Slow path: a claim already exists; recover it only if it is stale (its
    owner died). The recovering caller `os.rename`s the stale claim aside
    rather than unlinking it — among callers racing on the *same* claim file
    only one rename succeeds (the rest get FileNotFoundError) — then re-creates
    the claim via the same O_EXCL race so it competes fairly with fresh-path
    claimers.

    Stale-recovery is NOT exactly-once. A caller whose staleness check predates
    an earlier winner's re-created claim can rename that fresh claim aside and
    win too, so concurrent recovery yields between 1 and N winners (N = racers)
    — bounded, never an unbounded cascade. This is accepted, not fixed
    (REVIEW_LOG.md D15 / DECISIONS.md 2026-05-19): the duplicate is harmless —
    crash-recovery only, a bounded number of replayed units, and the atomic
    final-write (temp file then rename) is the real correctness layer so a
    replay overwrites identically. A concurrency redesign risks losing a
    claim, which is worse."""
    try:
        fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        fd = None
    except OSError as e:
        if e.errno == errno.EEXIST:
            fd = None
        else:
            return False  # transient FS error — skip this work, try another
    if fd is not None:
        try:
            _fd_write(fd, host)
        except OSError:
            # Body write or close failed (e.g. a CIFS flush EIO). The claim
            # file exists but we don't trust the mount — skip the work rather
            # than crash the run; the claim goes stale and is recovered later.
            return False
        return True

    # A claim already exists. Re-claim only if it looks abandoned.
    if not is_stale(claim_path, stale_secs):
        return False
    # Atomically take ownership of the recovery: rename the stale claim aside.
    # Only one racer can rename a given source file; the rest fail here.
    staged = claim_path.with_name(
        f".{claim_path.name}.recovering.{os.getpid()}.{time.monotonic_ns()}"
    )
    try:
        os.rename(claim_path, staged)
    except OSError:
        return False  # another caller is already recovering this claim
    try:
        os.unlink(staged)  # discard the dead owner's claim
    except OSError as e:
        # The staged file is inert — call-site globs don't match the
        # `.*.recovering.*` name — so leaving it only wastes an inode. Log so
        # an operator can sweep leftovers later rather than swallowing silently.
        sys.stderr.write(f"[claim] could not unlink staged {staged}: {e}\n")
    # The work is free again — re-create via O_EXCL, competing fairly with any
    # fresh-path claimer (so still exactly one winner).
    try:
        fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError:
        return False  # a fresh-path caller beat us to the re-created claim
    try:
        _fd_write(fd, host)
    except OSError:
        return False  # body write/close failed (FS hiccup) — skip the work
    return True
