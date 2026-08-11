#!/usr/bin/env python3
"""G0 gate — CPython MT19937 vs ``carc_rs`` (0 mismatches, full stop).

What is checked, element for element:

  1. ``random.seed(s); random.shuffle(list(range(n)))``  == ``carc_rs.shuffle_indices(s, n, "global")``
  2. ``random.Random(s).shuffle(list(range(n)))``        == ``carc_rs.shuffle_indices(s, n, "random")``
  3. the two Python forms agree with each other (proves the SeedMode split is a
     no-op rather than assuming it)
  4. ``random_seed()``'s little-endian 32-bit word split
  5. raw ``getrandbits(32)`` streams
  6. ``getrandbits(k)`` for k in 0..64
  7. ``Random._randbelow(n)`` sequences (the rejection loop)

Seed coverage: 0, small ints, 2^31-1, 2^32, 2^63-1, 2^64, and > 2^64 (CPython
uses the FULL absolute value, so big seeds are passed to Rust as decimal strings
rather than hashed down), plus negatives (CPython takes ``abs``).

n coverage: 0..100, the exact deck lengths {71, 72}, and every determinization
k_remaining in 1..72.

Usage:  .venv/bin/python scripts/rustport/reconcile_mt19937.py [--pairs 10000]
"""

from __future__ import annotations

import argparse
import random
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _g0_common import require_carc_rs, verdict, write_result  # noqa: E402

DECK_LENGTHS = [71, 72]


def seed_pool(rng: random.Random, k: int) -> list[int]:
    """Seeds spanning every magnitude class CPython's random_seed() branches on."""
    fixed = [
        0, 1, -1, 2, 7, 42, 12345, 65535, 65536,
        2**31 - 1, 2**31, 2**32 - 1, 2**32, 2**32 + 1,
        2**63 - 1, 2**63, 2**64 - 1, 2**64, 2**64 + 1,
        -(2**63), -(2**64) - 12345,
        2**70 + 12345,
        2**128 - 1,
        2**191 + 7,
        2**256 + 2**33 + 1,
        28_000_000_000,          # the champ_games deck-seed band
        28_000_000_449,
        60_000_000_000, 76_000_000_000, 88_000_000_000,   # the claim bands
    ]
    out = list(fixed)
    while len(out) < k:
        cls = rng.randrange(5)
        if cls == 0:
            out.append(rng.randrange(0, 1 << 16))
        elif cls == 1:
            out.append(rng.randrange(0, 1 << 32))
        elif cls == 2:
            out.append(rng.randrange(0, 1 << 63))
        elif cls == 3:
            out.append(rng.randrange(1 << 64, 1 << 96))
        else:
            out.append(-rng.randrange(0, 1 << 40))
    return out[:k]


def n_pool(rng: random.Random, k: int) -> list[int]:
    out = list(range(0, 101)) + DECK_LENGTHS + list(range(1, 73))
    while len(out) < k:
        out.append(rng.randrange(0, 400))
    return out[:k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=10_000,
                    help="number of (seed, n) shuffle reproductions (default 1e4)")
    ap.add_argument("--bitstream-cases", type=int, default=400)
    a = ap.parse_args()

    rs = require_carc_rs()
    rng = random.Random(0xC0FFEE)

    seeds = seed_pool(rng, a.pairs)
    ns = n_pool(rng, a.pairs)
    rng.shuffle(ns)

    mismatches: list[dict] = []
    checked = {"shuffle_global": 0, "shuffle_random": 0, "modes_agree": 0}

    for i in range(a.pairs):
        s = seeds[i % len(seeds)] if i < len(seeds) else rng.choice(seeds)
        n = ns[i % len(ns)]
        sd = str(s)

        random.seed(s)
        want_global = list(range(n))
        random.shuffle(want_global)
        got_global = rs.shuffle_indices(sd, n, "global")
        checked["shuffle_global"] += 1
        if got_global != want_global:
            mismatches.append({"kind": "shuffle_global", "seed": sd, "n": n,
                               "py": want_global[:12], "rs": got_global[:12]})

        want_rand = list(range(n))
        random.Random(s).shuffle(want_rand)
        got_rand = rs.shuffle_indices(sd, n, "random")
        checked["shuffle_random"] += 1
        if got_rand != want_rand:
            mismatches.append({"kind": "shuffle_random", "seed": sd, "n": n,
                               "py": want_rand[:12], "rs": got_rand[:12]})

        checked["modes_agree"] += 1
        if want_global != want_rand:
            mismatches.append({"kind": "python_modes_disagree", "seed": sd, "n": n})

        if len(mismatches) > 50:
            break

    # ---- seed word split -----------------------------------------------------
    checked["seed_words"] = 0
    for s in seeds[:2000]:
        n_abs = abs(s)
        bits = n_abs.bit_length()
        keyused = 1 if bits == 0 else (bits - 1) // 32 + 1
        want = [(n_abs >> (32 * i)) & 0xFFFFFFFF for i in range(keyused)]
        got = rs.seed_words(str(s))
        checked["seed_words"] += 1
        if got != want:
            mismatches.append({"kind": "seed_words", "seed": str(s),
                               "py": want, "rs": got})

    # ---- raw genrand_uint32 / getrandbits / _randbelow streams ---------------
    checked["genrand"] = checked["getrandbits"] = checked["randbelow"] = 0
    for s in seeds[: a.bitstream_cases]:
        sd = str(s)
        r = random.Random(s)
        want = [r.getrandbits(32) for _ in range(64)]
        got = rs.genrand_uint32_stream(sd, 64)
        checked["genrand"] += 1
        if got != want:
            mismatches.append({"kind": "genrand", "seed": sd,
                               "py": want[:8], "rs": got[:8]})

        ks = [rng.randrange(0, 65) for _ in range(64)]
        r = random.Random(s)
        want = [r.getrandbits(k) if k else 0 for k in ks]
        got = rs.getrandbits_stream(sd, ks)
        checked["getrandbits"] += 1
        if got != want:
            bad = next(j for j in range(len(ks)) if got[j] != want[j])
            mismatches.append({"kind": "getrandbits", "seed": sd, "k": ks[bad],
                               "py": want[bad], "rs": got[bad]})

        # _randbelow: deck lengths + determinization k_remaining + random n
        nsq = DECK_LENGTHS + list(range(1, 73)) + [rng.randrange(1, 1 << 40) for _ in range(16)]
        r = random.Random(s)
        want = [r._randbelow(v) for v in nsq]
        got = rs.randbelow_stream(sd, nsq)
        checked["randbelow"] += 1
        if got != want:
            bad = next(j for j in range(len(nsq)) if got[j] != want[j])
            mismatches.append({"kind": "randbelow", "seed": sd, "n": nsq[bad],
                               "py": want[bad], "rs": got[bad]})

    ok = not mismatches
    total = sum(checked.values())
    path = write_result("mt19937", {
        "pass": ok,
        "checks": checked,
        "total_checks": total,
        "n_mismatches": len(mismatches),
        "mismatches": mismatches[:50],
        "coverage": {
            "n_values": sorted(set(ns)),
            "deck_lengths": DECK_LENGTHS,
            "n_seeds": len(set(seeds)),
            "max_seed_bits": max(abs(s).bit_length() for s in seeds),
            "seeds_over_2_64": sum(1 for s in seeds if abs(s) >= 2**64),
        },
    })
    return verdict(
        "mt19937", ok,
        f"{total} checks over {len(set(seeds))} seeds "
        f"(max {max(abs(s).bit_length() for s in seeds)} bits, "
        f"{sum(1 for s in seeds if abs(s) >= 2**64)} >= 2^64), "
        f"{len(mismatches)} mismatches",
        path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
