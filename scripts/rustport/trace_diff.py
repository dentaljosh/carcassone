"""rustport **P3** — bisect two per-simulation traces to the FIRST divergence.

    .venv/bin/python scripts/rustport/trace_diff.py A_py.jsonl A_rs.jsonl

Both files are JSONL emitted by `trace_search.JsonlTrace` (Python) and
`carc_core::search::trace::JsonlTrace` (Rust), in the same order.  When they are
byte-identical the tool says so and exits 0.  When they are not, it prints:

* the record index and kind where they first differ;
* a field-by-field diff of that record, with floats shown as raw bits AND as
  decimals (so "3 ulp in the prior" reads differently from "wrong action");
* the last few AGREEING records for context — in practice the divergence is
  caused by the expansion just before it, not by the simulation that surfaces it;
* a one-line verdict naming the most likely culprit site (edge choice / prior
  vector / leaf value / backprop arithmetic), because those four map onto four
  different pieces of the port.

Exit codes: 0 identical, 1 diverged, 2 usage/parse error.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def f(bits_hex: str) -> float:
    return struct.unpack("<d", struct.pack("<Q", int(bits_hex, 16)))[0]


def ulps(a: str, b: str) -> int:
    """Signed ULP distance between two bit patterns (monotone ordering)."""
    def key(h: str) -> int:
        u = int(h, 16)
        return u if u < 0x8000000000000000 else -(u & 0x7FFFFFFFFFFFFFFF)
    return key(b) - key(a)


def load(path: Path) -> list[dict]:
    out = []
    with open(path) as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{i + 1}: not JSON ({e})")
    return out


def _fmt_float_list(name: str, a: list[str], b: list[str], out: list[str]) -> None:
    if a == b:
        return
    if len(a) != len(b):
        out.append(f"    {name}: LENGTH {len(a)} vs {len(b)}")
        return
    bad = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    out.append(f"    {name}: {len(bad)}/{len(a)} entries differ")
    for i in bad[:8]:
        out.append(
            f"      [{i}] py={a[i]} ({f(a[i])!r})  rs={b[i]} ({f(b[i])!r})  "
            f"ulps={ulps(a[i], b[i])}")
    if len(bad) > 8:
        out.append(f"      ... {len(bad) - 8} more")


def diff_record(x: dict, y: dict) -> tuple[list[str], str]:
    """Field diff + a culprit guess."""
    out: list[str] = []
    culprit = "unknown"
    if x.get("t") != y.get("t"):
        return [f"    record KIND differs: {x.get('t')!r} vs {y.get('t')!r}"], "record ordering"

    if x["t"] == "exp":
        for k in ("node", "p", "term"):
            if x[k] != y[k]:
                out.append(f"    {k}: py={x[k]!r} rs={y[k]!r}")
                culprit = "node identity / engine state" if k == "node" else "node metadata"
        if x["va"] != y["va"]:
            only_py = sorted(set(x["va"]) - set(y["va"]))
            only_rs = sorted(set(y["va"]) - set(x["va"]))
            out.append(f"    va: {len(x['va'])} vs {len(y['va'])} actions; "
                       f"py-only={only_py[:12]} rs-only={only_rs[:12]}")
            culprit = "legal-move enumeration / mask cache"
        for k in ("tv", "lv"):
            if x[k] != y[k]:
                out.append(f"    {k}: py={x[k]} ({f(x[k])!r}) rs={y[k]} ({f(y[k])!r}) "
                           f"ulps={ulps(x[k], y[k])}")
                culprit = ("terminal value (tanh(diff/SCORE_NORM_SCALE))" if k == "tv"
                           else "leaf value (tanh(leaf/value_norm)) or the f32 root round-trip")
        if x["pr"] != y["pr"]:
            _fmt_float_list("pr", x["pr"], y["pr"], out)
            culprit = ("prior vector: np.exp flavour / np.sum pairwise order / "
                       "float32 round-trip")
    else:
        if x["i"] != y["i"]:
            out.append(f"    sim index: py={x['i']} rs={y['i']}")
            culprit = "record ordering"
        if x["acts"] != y["acts"]:
            n = min(len(x["acts"]), len(y["acts"]))
            k = next((j for j in range(n) if x["acts"][j] != y["acts"][j]), n)
            out.append(f"    acts: diverge at depth {k}: "
                       f"py={x['acts'][k:k + 3]} rs={y['acts'][k:k + 3]}")
            out.append(f"      py path={x['path'][:k + 2]}")
            out.append(f"      rs path={y['path'][:k + 2]}")
            culprit = "PUCT edge choice (Q/U arithmetic, tie-break, alias skip, FPU)"
        elif x["path"] != y["path"]:
            k = next(j for j in range(min(len(x["path"]), len(y["path"])))
                     if x["path"][j] != y["path"][j])
            out.append(f"    path: same actions but different node at depth {k}: "
                       f"py={x['path'][k]} rs={y['path'][k]}")
            culprit = "transposition keying (string_representation bytes)"
        if x["lv"] != y["lv"]:
            out.append(f"    lv: py={x['lv']} ({f(x['lv'])!r}) rs={y['lv']} ({f(y['lv'])!r}) "
                       f"ulps={ulps(x['lv'], y['lv'])}")
            culprit = "leaf value backed up"
        if x["nw"] != y["nw"]:
            for j, (a, b) in enumerate(zip(x["nw"], y["nw"])):
                if a == b:
                    continue
                out.append(f"    nw[{j}] ({x['path'][j]}): py=(N={a[0]}, W={a[1]}) "
                           f"rs=(N={b[0]}, W={b[1]}) ulps={ulps(a[1], b[1])}")
                if culprit == "unknown":
                    culprit = ("backprop arithmetic (W += +/-leaf_value) or POV sign"
                               if a[0] == b[0] else "visit accounting")
    if not out:
        out.append("    (records compare equal field-by-field but not byte-for-byte "
                   "— check key order / formatting)")
    return out, culprit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("python_trace", type=Path)
    ap.add_argument("rust_trace", type=Path)
    ap.add_argument("--context", type=int, default=3,
                    help="agreeing records to show before the divergence")
    a = ap.parse_args(argv)

    for p in (a.python_trace, a.rust_trace):
        if not p.exists():
            print(f"missing trace: {p}", file=sys.stderr)
            return 2

    py, rs = load(a.python_trace), load(a.rust_trace)
    n = min(len(py), len(rs))
    first = next((i for i in range(n) if py[i] != rs[i]), None)

    if first is None and len(py) == len(rs):
        print(f"IDENTICAL — {len(py)} records "
              f"({sum(1 for r in py if r['t'] == 'sim')} sims, "
              f"{sum(1 for r in py if r['t'] == 'exp')} expansions)")
        return 0

    if first is None:
        longer, name = (py, "python") if len(py) > len(rs) else (rs, "rust")
        print(f"DIVERGED — the first {n} records agree, but {name} emitted "
              f"{len(longer) - n} extra record(s); next is {longer[n]!r}")
        return 1

    print(f"DIVERGED at record {first} of {n} "
          f"(py has {len(py)}, rs has {len(rs)})")
    lo = max(0, first - a.context)
    for i in range(lo, first):
        r = py[i]
        tag = (f"sim {r['i']} depth={len(r['acts'])}" if r["t"] == "sim"
               else f"exp {r['node']} |va|={len(r['va'])}")
        print(f"  ok  [{i}] {tag}")
    print(f"  >>  [{first}] {py[first]['t']}")
    lines, culprit = diff_record(py[first], rs[first])
    for line in lines:
        print(line)
    sims_before = sum(1 for r in py[:first] if r["t"] == "sim")
    print(f"\n  first divergent simulation index: {sims_before}")
    print(f"  LIKELY CULPRIT: {culprit}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
