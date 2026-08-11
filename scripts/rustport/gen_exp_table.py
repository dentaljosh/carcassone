#!/usr/bin/env python3
"""Generate ``carc-core/src/compat/exp_data.rs`` from ARM optimized-routines ``exp_data.c``.

Provenance
----------
Source of record: https://github.com/ARM-software/optimized-routines
    ``math/exp_data.c``   (``const struct exp_data __exp_data``)
    ``math/math_config.h`` (``EXP_TABLE_BITS 7``, ``EXP_POLY_ORDER 5``, ``EXP_POLY_WIDE`` unset)

This is the implementation glibc adopted for ``exp()`` in 2.27
(``sysdeps/ieee754/dbl-64/e_exp.c`` + ``e_exp_data.c`` are verbatim copies) and the
same lineage bionic carries. We take the ``N == 128 && EXP_POLY_ORDER == 5 &&
!EXP_POLY_WIDE`` variant, which is the configuration both use.

The generated file is CHECKED IN — this script is provenance + a drift guard, not a
build step (spec: "No Python-invoking build.rs").

Usage
-----
    python3 scripts/rustport/gen_exp_table.py --src /path/to/exp_data.c \
        [--out rust/carc/carc-core/src/compat/exp_data.rs] [--check]

If ``--src`` is omitted the file is downloaded from GitHub (``master``).
``--check`` verifies the checked-in file still matches instead of rewriting it.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
import urllib.request

UPSTREAM = (
    "https://raw.githubusercontent.com/ARM-software/optimized-routines/"
    "master/math/exp_data.c"
)
DEFAULT_OUT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "rust/carc/carc-core/src/compat/exp_data.rs"
)

HEX_D = re.compile(r"0x[0-9a-fA-F]+")


def _slice_between(text: str, start_pat: str, end_pat: str) -> str:
    i = text.index(start_pat) + len(start_pat)
    j = text.index(end_pat, i)
    return text[i:j]


def extract(src: str) -> dict:
    """Pull the N==128 / POLY_ORDER==5 / !POLY_WIDE constants out of exp_data.c."""
    # ---- negln2hiN / negln2loN: the "#elif N == 128" arm of the ln2 block ------
    ln2_block = _slice_between(src, ".negln2hiN", "// Used for rounding")
    # the arms are ordered N==64, N==128, N==256, N==512 -> take the 2nd pair
    lines = [l.strip() for l in ln2_block.splitlines()]
    pairs = []
    cur = {}
    for l in lines:
        if l.startswith("-0x") or l.startswith("0x"):
            cur.setdefault("hi", l.rstrip(","))
            if "lo" not in cur and cur["hi"] != l.rstrip(","):
                pass
        if l.startswith(".negln2loN"):
            cur["lo"] = l.split("=", 1)[1].strip().rstrip(",")
            pairs.append(cur)
            cur = {}
        elif l.startswith(".negln2hiN"):
            cur = {"hi": l.split("=", 1)[1].strip().rstrip(",")}
    # first entry of `pairs` is the fall-through for the leading `.negln2hiN =`
    # line consumed by _slice_between; re-parse robustly instead:
    pairs = []
    for m in re.finditer(
        r"#(?:if|elif) N == (\d+)\s*\n\.negln2hiN = ([^,]+),\s*\n\.negln2loN = ([^,]+),",
        src,
    ):
        pairs.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
    # the very first arm is `#if N == 64` written without a preceding `#elif`
    m0 = re.search(
        r"#if N == 64\s*\n\.negln2hiN = ([^,]+),\s*\n\.negln2loN = ([^,]+),", src
    )
    if m0:
        pairs.insert(0, (64, m0.group(1).strip(), m0.group(2).strip()))
    negln2 = {n: (hi, lo) for n, hi, lo in pairs}
    if 128 not in negln2:
        raise SystemExit("could not locate the N==128 negln2 arm")

    # ---- poly: the `N == 128 && EXP_POLY_ORDER == 5 && !EXP_POLY_WIDE` arm -----
    poly_block = _slice_between(
        src,
        "#elif N == 128 && EXP_POLY_ORDER == 5 && !EXP_POLY_WIDE",
        "#elif N == 128 && EXP_POLY_ORDER == 5 && EXP_POLY_WIDE",
    )
    poly = [
        l.strip().rstrip(",")
        for l in poly_block.splitlines()
        if l.strip().startswith("0x") or l.strip().startswith("-0x")
    ]
    if len(poly) != 4:
        raise SystemExit(f"expected 4 poly coefficients, got {len(poly)}: {poly}")

    # ---- tab: the `#elif N == 128` arm inside `.tab = { ... }` ----------------
    tab_all = _slice_between(src, ".tab = {", "\n},")
    tab_block = _slice_between(tab_all, "#elif N == 128\n", "#elif N == 256")
    words = HEX_D.findall(tab_block)
    if len(words) != 256:
        raise SystemExit(f"expected 256 tab words for N=128, got {len(words)}")

    return {
        "negln2hiN": negln2[128][0],
        "negln2loN": negln2[128][1],
        "poly": poly,
        "tab": words,
        "sha256": hashlib.sha256(src.encode()).hexdigest(),
    }


def c_hex_double_to_rust(lit: str) -> str:
    """C hex-float literal -> a Rust f64 expression.

    Rust has no hex-float literals, so we emit ``f64::from_bits(0x...)`` computed
    here with Python's exact ``float.fromhex``.
    """
    neg = lit.startswith("-")
    body = lit[1:] if neg else lit
    v = float.fromhex(body)
    if neg:
        v = -v
    import struct

    bits = struct.unpack("<Q", struct.pack("<d", v))[0]
    return f"f64::from_bits(0x{bits:016x}) /* {lit} = {v!r} */"


def render(d: dict) -> str:
    out = []
    out.append("// @generated by scripts/rustport/gen_exp_table.py — DO NOT EDIT BY HAND.")
    out.append("//")
    out.append("// Source: ARM optimized-routines math/exp_data.c")
    out.append("//   https://github.com/ARM-software/optimized-routines")
    out.append("//   SPDX-License-Identifier: MIT OR Apache-2.0 WITH LLVM-exception")
    out.append("//   Copyright (c) 2018, Arm Limited.")
    out.append(f"// sha256(exp_data.c) = {d['sha256']}")
    out.append("//")
    out.append("// Configuration: EXP_TABLE_BITS = 7 (N = 128), EXP_POLY_ORDER = 5,")
    out.append("// EXP_POLY_WIDE unset — the arm glibc >= 2.27 and bionic both build.")
    out.append("")
    out.append("#![allow(clippy::unreadable_literal)]")
    out.append("")
    out.append("/// `EXP_TABLE_BITS`")
    out.append("pub const EXP_TABLE_BITS: u32 = 7;")
    out.append("/// `N = 1 << EXP_TABLE_BITS`")
    out.append("pub const N: u64 = 1 << EXP_TABLE_BITS;")
    out.append("")
    out.append("/// `.invln2N = 0x1.71547652b82fep0 * N` (N = 128; the scaling is exact)")
    out.append(
        "pub const INV_LN2_N: f64 = " + c_hex_double_to_rust("0x1.71547652b82fep7") + ";"
    )
    out.append("/// `.negln2hiN` (N = 128 arm)")
    out.append("pub const NEG_LN2_HI_N: f64 = " + c_hex_double_to_rust(d["negln2hiN"]) + ";")
    out.append("/// `.negln2loN` (N = 128 arm)")
    out.append("pub const NEG_LN2_LO_N: f64 = " + c_hex_double_to_rust(d["negln2loN"]) + ";")
    out.append("/// `.shift = 0x1.8p52` (EXP_USE_TOINT_NARROW == 0)")
    out.append("pub const SHIFT: f64 = " + c_hex_double_to_rust("0x1.8p52") + ";")
    out.append("")
    for i, name in enumerate(["C2", "C3", "C4", "C5"]):
        out.append(f"/// `__exp_data.poly[{i}]`")
        out.append(f"pub const {name}: f64 = " + c_hex_double_to_rust(d["poly"][i]) + ";")
    out.append("")
    out.append("/// `__exp_data.tab` — `tab[2*k] = asuint64(T[k])`, `tab[2*k+1] = asuint64(H[k]) - (k << 52)/N`.")
    out.append("pub static TAB: [u64; 256] = [")
    for i in range(0, 256, 2):
        out.append(f"    {d['tab'][i]}, {d['tab'][i + 1]},")
    out.append("];")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=pathlib.Path, default=None)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.src is not None:
        src = a.src.read_text()
    else:
        with urllib.request.urlopen(UPSTREAM, timeout=60) as fh:
            src = fh.read().decode()

    text = render(extract(src))
    if a.check:
        have = a.out.read_text() if a.out.exists() else ""
        if have != text:
            print(f"DRIFT: {a.out} does not match the generator output", file=sys.stderr)
            return 1
        print(f"OK: {a.out} matches")
        return 0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
