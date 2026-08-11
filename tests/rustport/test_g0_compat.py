"""Fast pytest guard over the G0 compat primitives (rustport phase P0).

The authoritative gates are the ``scripts/rustport/reconcile_*.py`` fuzzers
(10^4 / 10^6 / bit-exact, results in ``measurement/rustport_p0/``). This file is
the *cheap* version that runs in CI-time seconds so a regression in
``carc-core::compat`` is caught before anyone re-runs the big gates.

Skipped entirely when the ``carc_rs`` dev wheel is not built.
"""

from __future__ import annotations

import math
import random
import struct

import numpy as np
import pytest

carc_rs = pytest.importorskip("carc_rs", reason="build the dev wheel: maturin develop")


# --------------------------------------------------------------------------- #
# mt19937
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", [0, 1, -1, 42, 2**31 - 1, 2**63 - 1, 2**64 + 1,
                                  2**128 - 1, 28_000_000_000])
@pytest.mark.parametrize("n", [0, 1, 2, 5, 71, 72, 100])
def test_shuffle_matches_cpython(seed, n):
    want = list(range(n))
    random.seed(seed)
    random.shuffle(want)
    assert carc_rs.shuffle_indices(str(seed), n, "global") == want


def test_global_seed_and_random_instance_agree():
    for seed in (0, 7, 2**70 + 1):
        a = list(range(72))
        random.seed(seed)
        random.shuffle(a)
        b = list(range(72))
        random.Random(seed).shuffle(b)
        assert a == b
        assert carc_rs.shuffle_indices(str(seed), 72, "global") == a
        assert carc_rs.shuffle_indices(str(seed), 72, "random") == b


def test_seed_word_split_matches_cpython():
    for seed in (0, 1, -5, 2**32, 2**32 - 1, 2**64 + 1, 2**200 + 3):
        n = abs(seed)
        bits = n.bit_length()
        keyused = 1 if bits == 0 else (bits - 1) // 32 + 1
        want = [(n >> (32 * i)) & 0xFFFFFFFF for i in range(keyused)]
        assert carc_rs.seed_words(str(seed)) == want


def test_getrandbits_and_randbelow_streams():
    for seed in (0, 99, 2**65):
        r = random.Random(seed)
        ks = [1, 3, 17, 31, 32, 33, 53, 63, 64] * 4
        assert carc_rs.getrandbits_stream(str(seed), ks) == [r.getrandbits(k) for k in ks]
        r = random.Random(seed)
        ns = [2, 3, 5, 71, 72] + list(range(1, 73))
        assert carc_rs.randbelow_stream(str(seed), ns) == [r._randbelow(v) for v in ns]


# --------------------------------------------------------------------------- #
# fsum
# --------------------------------------------------------------------------- #
FSUM_CASES = [
    [],
    [0.0],
    [-0.0],
    [1e100, 1.0, -1e100, 1e-100, 1e100, -1.0, -1e100],
    [0.1] * 10,
    [1e16, 1.0, -1e16],
    [1e-16, 1.0, 1e16],
    [5e-324, 5e-324, 1.0, -1.0],
]


@pytest.mark.parametrize("case", FSUM_CASES)
def test_fsum_bit_equal(case):
    assert struct.pack("<d", carc_rs.fsum(case)) == struct.pack("<d", math.fsum(case))


def test_fsum_random_bit_equal():
    rng = np.random.default_rng(7)
    for _ in range(2000):
        n = int(rng.integers(1, 60))
        v = (rng.choice([-1.0, 1.0], n) * np.power(10.0, rng.uniform(-200, 200, n))).tolist()
        assert struct.pack("<d", carc_rs.fsum(v)) == struct.pack("<d", math.fsum(v))


# --------------------------------------------------------------------------- #
# npsum
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n", [0, 1, 7, 8, 9, 127, 128, 129, 136, 255, 256, 257, 1000, 5000])
def test_np_sum_bit_equal_f64(n):
    rng = np.random.default_rng(n)
    a = np.ascontiguousarray(rng.standard_normal(n))
    assert struct.pack("<d", carc_rs.np_sum_f64(a.tolist())) == struct.pack("<d", a.sum())


@pytest.mark.parametrize("n", [0, 1, 7, 8, 9, 127, 128, 129, 136, 1000])
def test_np_sum_bit_equal_f32(n):
    rng = np.random.default_rng(n + 1)
    a = np.ascontiguousarray(rng.standard_normal(n), dtype=np.float32)
    assert struct.pack("<f", carc_rs.np_sum_f32(a.tolist())) == struct.pack("<f", a.sum())


def test_np_sum_preserves_negative_zero_semantics():
    # numpy's base case seeds from -0.0 and np.sum adds the +0.0 identity.
    a = np.zeros(4) * -1.0
    assert struct.pack("<d", carc_rs.np_sum_f64(a.tolist())) == struct.pack("<d", a.sum())


# --------------------------------------------------------------------------- #
# libm compat -- platform-conditional (see LibmFlavor docs)
# --------------------------------------------------------------------------- #
def _is_glibc_x86_64():
    import platform

    return platform.machine() == "x86_64" and "glibc" in " ".join(platform.libc_ver()).lower()


def test_exp64_fma_matches_np_exp_on_the_production_range():
    """np.exp(z) for z = Delta_leaf/tau - max is the production call site."""
    z = np.ascontiguousarray(np.linspace(-100.0, 0.0, 200_001))
    got = np.frombuffer(carc_rs.exp64_buf(z.tobytes(), True), dtype=np.float64)
    want = np.exp(z)
    n_bad = int((got.view(np.uint64) != want.view(np.uint64)).sum())
    if not _is_glibc_x86_64():
        pytest.skip(f"platform-conditional; {n_bad} mismatches here")
    assert n_bad == 0


def test_glibc_fma_flavor_matches_math_tanh():
    x = np.ascontiguousarray(np.linspace(-22.0, 22.0, 200_001))
    got = np.frombuffer(carc_rs.tanh64_buf(x.tobytes(), "glibc_fma"), dtype=np.float64)
    want = np.array([math.tanh(v) for v in x])
    n_bad = int((got.view(np.uint64) != want.view(np.uint64)).sum())
    if not _is_glibc_x86_64():
        pytest.skip(f"platform-conditional; {n_bad} mismatches here")
    assert n_bad == 0


def test_np_tanh_is_not_math_tanh():
    """Guard rail: numpy's VECTOR tanh is a different function from libm's scalar
    tanh (~20% of arguments differ). The production value site uses math.tanh --
    a future site that reaches for np.tanh needs its own compat function."""
    x = np.ascontiguousarray(np.linspace(-20.0, 20.0, 100_001))
    want = np.array([math.tanh(v) for v in x])
    assert int((np.tanh(x).view(np.uint64) != want.view(np.uint64)).sum()) > 0


def test_libm_flavors_enumerated():
    assert list(carc_rs.libm_flavors()) == ["msun", "msun_fma", "glibc", "glibc_fma"]
