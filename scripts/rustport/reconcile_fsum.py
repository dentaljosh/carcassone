#!/usr/bin/env python3
"""G0 gate — ``math.fsum`` vs ``carc_rs.fsum`` (bit-equal, 0 mismatches).

10^6 random multisets by default. Comparison is on the raw IEEE-754 bits
(``struct.pack``), not ``==``, so a ``-0.0``/``+0.0`` disagreement is a failure.

Input families (mixed, roughly equal shares):
  uniform      : magnitudes drawn log-uniformly over 1e-300 .. 1e300
  narrow       : leaf-like values -- small integers and integer/2 quantities
  cancellation : x, -x pairs plus a small residue (the case naive summation kills)
  catastrophic : the CPython test_math ladder (1e100, 1, -1e100, 1e-100, ...)
  subnormal    : denormals and the smallest positive double
  mixed_scale  : one huge term plus many tiny ones (half-even fixup territory)

Lengths span 1..500 (short lengths oversampled -- the leaf sums ~5-40 terms).

Usage:  .venv/bin/python scripts/rustport/reconcile_fsum.py [--cases 1000000]
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g0_common import require_carc_rs, verdict, write_result  # noqa: E402

PACK = struct.Struct("<d").pack

FAMILIES = ("uniform", "narrow", "cancellation", "catastrophic", "subnormal", "mixed_scale")


def gen_case(rng: np.random.Generator, family: str) -> list[float]:
    # short lengths oversampled: the production leaf reduces ~5-40 terms
    r = rng.random()
    if r < 0.55:
        n = int(rng.integers(1, 41))
    elif r < 0.85:
        n = int(rng.integers(1, 101))
    else:
        n = int(rng.integers(1, 501))

    if family == "uniform":
        expo = rng.uniform(-300, 300, n)
        sign = rng.choice([-1.0, 1.0], n)
        return (sign * np.power(10.0, expo)).tolist()

    if family == "narrow":
        # leaf-like: small ints, halves, and /3 quantities
        base = rng.integers(-60, 61, n).astype(np.float64)
        frac = rng.choice([0.0, 0.5, 0.25, 1.0 / 3.0, 2.0 / 3.0], n)
        return (base + frac).tolist()

    if family == "cancellation":
        half = max(1, n // 2)
        expo = rng.uniform(-40, 40, half)
        v = np.power(10.0, expo) * rng.choice([-1.0, 1.0], half)
        out = np.empty(2 * half + 1)
        out[0::2][:half] = v
        out[1::2][:half] = -v
        out[-1] = float(rng.uniform(-1, 1))
        arr = out.tolist()
        rng.shuffle(arr)
        return arr[:n] if n <= len(arr) else arr

    if family == "catastrophic":
        ladder = [1e100, 1.0, -1e100, 1e-100, 1e100, -1.0, -1e100]
        out = []
        while len(out) < n:
            out.extend(ladder)
        out = out[:n]
        rng.shuffle(out)
        return out

    if family == "subnormal":
        tiny = 5e-324
        mult = rng.integers(1, 1 << 20, n).astype(np.float64)
        sign = rng.choice([-1.0, 1.0], n)
        vals = sign * mult * tiny
        # sprinkle a few normals so the partials array actually grows
        k = max(1, n // 8)
        idx = rng.integers(0, n, k)
        vals[idx] = rng.normal(0, 1, k)
        return vals.tolist()

    # mixed_scale
    out = (rng.normal(0, 1, n) * np.power(10.0, rng.uniform(-16, -8, n))).tolist()
    out[rng.integers(0, n)] = float(rng.choice([1e16, -1e16, 1.0, -1.0]))
    if n > 1:
        out[rng.integers(0, n)] = float(rng.choice([1e-16, -1e-16]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=1_000_000)
    ap.add_argument("--chunk", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=20260731)
    a = ap.parse_args()

    rs = require_carc_rs()
    rng = np.random.default_rng(a.seed)

    mismatches: list[dict] = []
    per_family = {f: 0 for f in FAMILIES}
    total_elems = 0
    done = 0
    t0 = time.time()

    while done < a.cases:
        k = min(a.chunk, a.cases - done)
        flat: list[float] = []
        offsets = [0]
        want: list[bytes] = []
        cases: list[list[float]] = []
        for _ in range(k):
            fam = FAMILIES[int(rng.integers(0, len(FAMILIES)))]
            per_family[fam] += 1
            c = gen_case(rng, fam)
            cases.append(c)
            flat.extend(c)
            offsets.append(len(flat))
            want.append(PACK(math.fsum(c)))
        total_elems += len(flat)
        got = rs.fsum_batch(flat, offsets)
        for i, g in enumerate(got):
            if PACK(g) != want[i]:
                if len(mismatches) < 25:
                    mismatches.append({
                        "case_index": done + i,
                        "len": len(cases[i]),
                        "py_bits": want[i].hex(),
                        "rs_bits": PACK(g).hex(),
                        "py": struct.unpack("<d", want[i])[0],
                        "rs": g,
                        "input_head": cases[i][:16],
                    })
        done += k
        if done % 200_000 == 0:
            el = time.time() - t0
            print(f"  ... {done}/{a.cases} ({el:.0f}s, {len(mismatches)} mismatches)",
                  file=sys.stderr)

    ok = not mismatches
    path = write_result("fsum", {
        "pass": ok,
        "cases": done,
        "total_elements": total_elems,
        "per_family": per_family,
        "n_mismatches": len(mismatches),
        "mismatches": mismatches,
        "comparison": "struct.pack('<d') byte equality",
        "wall_s": round(time.time() - t0, 1),
        "seed": a.seed,
    })
    return verdict("fsum", ok,
                   f"{done} multisets / {total_elems} terms, "
                   f"{len(mismatches)} bit-mismatches", path)


if __name__ == "__main__":
    raise SystemExit(main())
