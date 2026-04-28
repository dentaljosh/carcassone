"""ETA banner helpers for long-running scripts.

Goal: never make the user wonder "is it still running?" when a job will take
more than a few seconds. Print the estimate up front, ideally based on a
quick sample-of-N timing.
"""
from __future__ import annotations

import sys
import time
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def fmt_seconds(s: float) -> str:
    if s < 1.0:
        return f"{s * 1000:.0f}ms"
    if s < 60.0:
        return f"{s:.1f}s"
    m, s_rem = divmod(s, 60)
    if m < 60:
        return f"{int(m)}m{int(s_rem):02d}s"
    h, m_rem = divmod(m, 60)
    return f"{int(h)}h{int(m_rem):02d}m"


def print_banner(
    *,
    label: str,
    n_items: int,
    workers: int,
    measured_per_item_seconds: float,
) -> None:
    """Print a one-line ETA estimate before kicking off a parallel job."""
    eta_s = (n_items * measured_per_item_seconds) / max(workers, 1)
    print(
        f"[ETA] {label}: {n_items} items × {measured_per_item_seconds * 1000:.0f}ms/item "
        f"on {workers} workers ≈ {fmt_seconds(eta_s)}",
        file=sys.stderr,
    )


def measure_one(fn: Callable[[T], object], sample_arg: T, warmups: int = 1) -> float:
    """Run fn(sample_arg) once (after `warmups` warmups) and return seconds."""
    for _ in range(warmups):
        fn(sample_arg)
    t0 = time.perf_counter()
    fn(sample_arg)
    return time.perf_counter() - t0
