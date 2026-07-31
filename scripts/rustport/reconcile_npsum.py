#!/usr/bin/env python3
"""G0 gate — ``np.sum`` vs ``carc_rs.np_sum_f{32,64}`` (bit-equal, 0 mismatches).

numpy reduces contiguous 1-D float arrays with a *pairwise* summation whose
ORDER is fixed by ``@TYPE@_pairwise_sum`` in ``loops_utils.h.src`` (block
threshold 128, 8-way unrolled base case, recursive split snapped down to a
multiple of 8). Any other order is a different function of the same multiset, so
the leaf's two prior sites (``w /= w.sum()`` on f64 and the f32 prior
round-trip) require this exact order.

Length coverage: every length 1..300 (each block/recursion boundary), then
stride-sampled to 5000 -- with the block boundaries 128/129/136/256/257/... and
their neighbours forced in.

Value families: random normal, log-uniform magnitudes, all-equal, alternating
signs (cancellation), monotone decreasing (the harmonic series -- order matters
most), all -0.0 (the base case seeds from -0.0), and one-huge-plus-many-tiny.

Usage:  .venv/bin/python scripts/rustport/reconcile_npsum.py
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g0_common import require_carc_rs, verdict, write_result  # noqa: E402

FAMILIES = (
    "normal", "logmag", "equal", "alternating", "harmonic", "negzero",
    "huge_plus_tiny", "subnormal", "integers",
)

# Lengths where the pairwise recursion changes shape.
BOUNDARIES = []
for b in (8, 16, 128, 129, 136, 144, 256, 257, 264, 512, 520, 1024, 2048, 4096):
    BOUNDARIES.extend([b - 1, b, b + 1, b + 7, b + 8])


def lengths(max_len: int) -> list[int]:
    ls = set(range(1, 301))
    ls.update(b for b in BOUNDARIES if 1 <= b <= max_len)
    ls.update(range(300, max_len + 1, 17))
    ls.add(max_len)
    return sorted(ls)


def gen(rng: np.random.Generator, family: str, n: int, dtype) -> np.ndarray:
    if family == "normal":
        v = rng.standard_normal(n)
    elif family == "logmag":
        lo, hi = (-30, 30) if dtype == np.float32 else (-280, 280)
        v = rng.choice([-1.0, 1.0], n) * np.power(10.0, rng.uniform(lo, hi, n))
    elif family == "equal":
        v = np.full(n, float(rng.choice([0.1, 1.0 / 3.0, -7.25, 1e-8])))
    elif family == "alternating":
        v = np.power(10.0, rng.uniform(-8, 8, n)) * np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    elif family == "harmonic":
        v = 1.0 / (np.arange(n) + 1.0)
    elif family == "negzero":
        v = np.full(n, -0.0)
        if n > 3:
            v[rng.integers(0, n)] = 0.0
    elif family == "huge_plus_tiny":
        v = rng.standard_normal(n) * (1e-20 if dtype == np.float64 else 1e-10)
        v[rng.integers(0, n)] = 1e16 if dtype == np.float64 else 1e8
    elif family == "subnormal":
        tiny = np.finfo(dtype).tiny
        v = rng.integers(1, 1 << 15, n).astype(np.float64) * float(tiny) * 1e-3
        v *= rng.choice([-1.0, 1.0], n)
    else:  # integers -- exact in both precisions, isolates ORDER from rounding
        v = rng.integers(-1000, 1001, n).astype(np.float64)
    return np.ascontiguousarray(v, dtype=dtype)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-len", type=int, default=5000)
    ap.add_argument("--reps", type=int, default=1,
                    help="independent draws per (length, family, dtype) cell")
    ap.add_argument("--seed", type=int, default=20260731)
    a = ap.parse_args()

    rs = require_carc_rs()
    rng = np.random.default_rng(a.seed)
    ls = lengths(a.max_len)

    mismatches: list[dict] = []
    checked = {"float64": 0, "float32": 0}
    t0 = time.time()

    for dtype, key, fn, packfmt in (
        (np.float64, "float64", rs.np_sum_f64_batch, "<d"),
        (np.float32, "float32", rs.np_sum_f32_batch, "<f"),
    ):
        pack = struct.Struct(packfmt).pack
        # batch by chunks of cells to keep FFI overhead down
        pending_flat: list[float] = []
        pending_off = [0]
        pending_meta: list[tuple] = []

        def flush():
            nonlocal pending_flat, pending_off, pending_meta
            if not pending_meta:
                return
            got = fn(pending_flat, pending_off)
            for (n, fam, want_bits, head), g in zip(pending_meta, got):
                if pack(g) != want_bits:
                    if len(mismatches) < 40:
                        mismatches.append({
                            "dtype": key, "len": n, "family": fam,
                            "np_bits": want_bits.hex(), "rs_bits": pack(g).hex(),
                            "np": struct.unpack(packfmt, want_bits)[0], "rs": g,
                            "input_head": head,
                        })
            pending_flat = []
            pending_off = [0]
            pending_meta = []

        for n in ls:
            for fam in FAMILIES:
                for _ in range(a.reps):
                    arr = gen(rng, fam, n, dtype)
                    want = pack(dtype(arr.sum()))
                    pending_flat.extend(arr.tolist())
                    pending_off.append(len(pending_flat))
                    pending_meta.append((n, fam, want, arr[:8].tolist()))
                    checked[key] += 1
            if len(pending_flat) > 500_000:
                flush()
        flush()

    ok = not mismatches
    path = write_result("npsum", {
        "pass": ok,
        "checks": checked,
        "total_checks": sum(checked.values()),
        "n_lengths": len(ls),
        "max_len": a.max_len,
        "families": list(FAMILIES),
        "boundary_lengths_covered": sorted(set(b for b in BOUNDARIES if b <= a.max_len)),
        "n_mismatches": len(mismatches),
        "mismatches": mismatches,
        "comparison": "struct.pack byte equality vs ndarray.sum()",
        "wall_s": round(time.time() - t0, 1),
        "seed": a.seed,
    })
    return verdict("npsum", ok,
                   f"{sum(checked.values())} reductions "
                   f"({len(ls)} lengths x {len(FAMILIES)} families x f32+f64), "
                   f"{len(mismatches)} bit-mismatches", path)


if __name__ == "__main__":
    raise SystemExit(main())
