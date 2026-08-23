#!/usr/bin/env python3
"""D3-WITNESS step 2 — raw-f64 bit-pattern diff, local re-score vs laptop records.

DEVIATIONS §D3.5 / drafter 751bdd12. BAR: n_mismatch == 0 across all rids.
Any single value mismatch => FAIL, owner-level escalation, nothing further runs.

CANONICALISATION follows the `gate_oracle_pilot_backend` canon() discipline: every
float is compared by its RAW f64 BIT PATTERN (struct '<d' -> uint64), not by ==.
This is the same currency G-BITEXACT uses, and it is strictly stronger than
equality: it separates +0.0/-0.0 and refuses to call two NaNs equal by accident.
Ints/bools/strings/None compare by value. Containers recurse structurally, so a
length or ordering difference is a mismatch, not a silent zip-truncation.

EXCLUSIONS — only these, and each justified:
  elapsed_secs        time-valued; differs by construction between boxes
  host, started_utc,
  workers,
  carc_rs_binary_sha,
  carc_rs_path        box-identity metadata (D3.2 rules the last two BOX-LOCAL
                      and never comparable across hosts)
Everything else — including every one of the 128 values_a / values_b / world_seeds
/ playout_seeds / afterstate hashes / per_world_delta entries and every derived
statistic (mean_a, mean_b, delta, within_var, within_se, unpaired_var,
crn_var_reduction) — MUST be bit-identical.

Writes ONLY under d3_witness/.
"""
from __future__ import annotations
import glob
import json
import math
import os
import platform
import struct
import subprocess
import sys
from pathlib import Path

CAMPAIGN = Path("/home/doctor/projects/carcassone/measurement/tiearb_widening_20260817")
D3 = CAMPAIGN / "d3_witness"
SHARE_CHUNKS = Path("/mnt/c/carc-shared/tiearb_widening_20260817/chunks/s1")  # allow-path
LAPTOP_CHUNKS = (6, 7, 8)

EXCLUDE = {"elapsed_secs", "host", "started_utc", "workers",
           "carc_rs_binary_sha", "carc_rs_path"}


def f64_bits(x: float) -> int:
    """Raw IEEE-754 f64 bit pattern. NOT equality — this is the gate's currency."""
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def canon(o):
    """Structural canonicalisation; floats -> ('f64', raw bits)."""
    if isinstance(o, bool):
        return ("bool", o)
    if isinstance(o, float):
        return ("f64", f64_bits(o))
    if isinstance(o, int):
        return ("int", o)
    if isinstance(o, str):
        return ("str", o)
    if o is None:
        return ("null", None)
    if isinstance(o, list):
        return ("list", len(o), tuple(canon(v) for v in o))
    if isinstance(o, dict):
        return ("dict", tuple(sorted((k, canon(v)) for k, v in o.items()
                                     if k not in EXCLUDE)))
    return ("other", repr(o))


def compare(a, b, path=""):
    """-> (n_compared, [mismatch paths]). Leaf-counted, so counts are meaningful."""
    ca, cb = canon(a), canon(b)
    if isinstance(a, dict) and isinstance(b, dict):
        n, bad = 0, []
        for k in sorted((set(a) | set(b)) - EXCLUDE):
            if k not in a or k not in b:
                bad.append(f"{path}{k}<present-in-one-only>")
                n += 1
                continue
            dn, db = compare(a[k], b[k], f"{path}{k}.")
            n += dn
            bad += db
        return n, bad
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return 1, [f"{path}<len {len(a)} vs {len(b)}>"]
        n, bad = 0, []
        for i, (x, y) in enumerate(zip(a, b)):
            dn, db = compare(x, y, f"{path}{i}.")
            n += dn
            bad += db
        return n, bad
    return 1, ([] if ca == cb else [path.rstrip(".")])


def laptop_record(rid: str):
    for k in LAPTOP_CHUNKS:
        hits = glob.glob(str(SHARE_CHUNKS / f"chunk{k}/clair-puct/walled/leg*/records/{rid}.json"))
        if hits:
            return Path(sorted(hits)[0])
    return None


def local_record(rid: str):
    hits = glob.glob(str(D3 / f"out/**/records/{rid}.json"), recursive=True)
    return Path(sorted(hits)[0]) if hits else None


def stack_local() -> dict:
    try:
        import numpy
        npv = numpy.__version__
    except Exception:
        npv = None
    try:
        glibc = platform.libc_ver()[1]
    except Exception:
        glibc = None
    return {"python": platform.python_version(), "numpy": npv, "glibc": glibc,
            "machine": platform.machine(), "node": platform.node()}


def stack_laptop() -> dict:
    code = ("import platform;"
            "\nimport json"
            "\ntry:\n import numpy; n=numpy.__version__\nexcept Exception: n=None"
            "\nprint(json.dumps({'python':platform.python_version(),'numpy':n,"
            "'glibc':platform.libc_ver()[1],'machine':platform.machine(),"
            "'node':platform.node()}))")
    try:
        out = subprocess.run(
            ["ssh", "laptop-wsl",
             "/home/doctor/projects/carcassone/.venv/bin/python -c " + json.dumps(code)],
            capture_output=True, text=True, timeout=120)
        return json.loads(out.stdout.strip().splitlines()[-1])
    except Exception as e:  # recorded, never fatal — the witness is the diff
        return {"error": f"{type(e).__name__}: {e}"}


def main() -> int:
    sel = json.loads((D3 / "SELECTION.json").read_text())
    rids = sel["rids"]

    per_rid, n_cmp_tot, n_mis_tot = [], 0, 0
    dig_local, dig_lap = [], []
    for rid in rids:
        lp, lo = laptop_record(rid), local_record(rid)
        if lp is None or lo is None:
            per_rid.append({"rid": rid, "status": "MISSING_RECORD",
                            "laptop": str(lp), "local": str(lo),
                            "n_compared": 0, "n_mismatch": 1})
            n_mis_tot += 1
            continue
        A, B = json.loads(lo.read_text()), json.loads(lp.read_text())
        n, bad = compare(A, B)
        n_cmp_tot += n
        n_mis_tot += len(bad)
        dig_local.append(json.dumps(canon(A), sort_keys=True, default=str))
        dig_lap.append(json.dumps(canon(B), sort_keys=True, default=str))
        per_rid.append({"rid": rid, "status": "OK" if not bad else "MISMATCH",
                        "n_compared": n, "n_mismatch": len(bad),
                        "mismatch_fields": bad[:20]})

    import hashlib
    sha_l = hashlib.sha256("\n".join(dig_local).encode()).hexdigest()
    sha_p = hashlib.sha256("\n".join(dig_lap).encode()).hexdigest()

    rep = {
        "gate": "D3-WITNESS",
        "spec": "DEVIATIONS §D3.5 as amended by drafter 751bdd12",
        "bar": "n_mismatch == 0 across all rids; 100% bit-identical, NOT within-tolerance",
        "n_rids": len(rids),
        "rids": rids,
        "selection_rule": sel["selection_rule"],
        "n_values_compared": n_cmp_tot,
        "n_bit_identical": n_cmp_tot - n_mis_tot,
        "n_mismatch": n_mis_tot,
        "sha256_local": sha_l,
        "sha256_laptop": sha_p,
        "digests_equal": sha_l == sha_p,
        "pass": n_mis_tot == 0,
        "excluded_keys": sorted(EXCLUDE),
        "canonicalisation": ("every float compared as its RAW f64 BIT PATTERN "
                             "(struct '<d' -> uint64), the currency G-BITEXACT uses; "
                             "containers compared structurally so a length or ordering "
                             "difference is a mismatch"),
        "stack_local": stack_local(),
        "stack_laptop": stack_laptop(),
        "per_rid": per_rid,
        "note": ("Counts and digests only. A digest is not a value and is not "
                 "invertible, so no adjudicated per-leg value leaves this gate. "
                 "No arb, no ora, no delta."),
    }
    (D3 / "D3_WITNESS.json").write_text(json.dumps(rep, indent=1) + "\n")

    print(f"[d3-witness] rids={len(rids)} values_compared={n_cmp_tot} "
          f"bit_identical={n_cmp_tot - n_mis_tot} mismatch={n_mis_tot}")
    print(f"[d3-witness] sha256_local ={sha_l}")
    print(f"[d3-witness] sha256_laptop={sha_p}  digests_equal={sha_l == sha_p}")
    for r in per_rid:
        if r["status"] != "OK":
            print(f"[d3-witness]   *** {r['rid']}: {r['status']} "
                  f"n_mismatch={r['n_mismatch']} {r.get('mismatch_fields')}")
    print(f"[d3-witness] {'PASS' if rep['pass'] else '***** FAIL *****'}")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
