#!/usr/bin/env python3
"""G-BITEXACT — the Stage-2 Phase-A gate.

Prove the RUST `tier1-greedy` continuation (`carc_rs.tier1_leg`,
`carc_core::tier1`) reproduces the banked PYTHON judge's per-leg values
**bit-identically** on the adjudicated Stage-1b corpus, before any cost number
is quoted.

Design: `measurement/tiearb2_stage2_20260817/PHASE_A.md` §3.

The sample is **committed before it is drawn** and its expected counts are
CONSTANTS, never `len(whatever_was_found)` — a truncated run must FAIL the gate,
not satisfy it trivially:

    rng = random.Random(20260817)
    for chunk in 1, 2, 3, 4:          # ascending
        for leg in 1, 2, 3, 4:        # ascending
            sel = rng.sample(sorted(rids_in(chunk, leg)), 15)

    => n_legs = 240, n_playouts = 240 * 32 * 2 = 15360

Comparison currency is the raw f64 BIT PATTERN (`struct.pack('<d', x)`), the
same `_f64_bits` discipline `run_tiletie.check_crn_cross_leg` uses — never `==`
after a cast.

Reporting is COUNTS ONLY plus two sha256 digests. A digest is not a value and is
not invertible, so no adjudicated per-leg value leaves this script.

Usage:
    .venv/bin/python scripts/tiletie/verify_tier1_rust.py [--workers 30]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import struct
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

RECORDS_ROOT = Path("/mnt/c/carc-shared/tiearb2_20260816/main")
POSITIONS_ROOT = REPO / "measurement" / "tiearb2_20260816"
OUT_PATH = REPO / "measurement" / "tiearb2_stage2_20260817" / "BITEXACT.json"

# --- the COMMITTED constants (PHASE_A.md §3) --------------------------------
SAMPLE_SEED = 20260817
CHUNKS = (1, 2, 3, 4)
LEGS = (1, 2, 3, 4)
PER_CELL = 15
N_LEGS_EXPECTED = len(CHUNKS) * len(LEGS) * PER_CELL          # 240
M_EXPECTED = 32
N_PLAYOUTS_EXPECTED = N_LEGS_EXPECTED * M_EXPECTED * 2        # 15360
WORLD_SEED_SALT = "tiletie-v1"
MAX_PLIES = 400
# The banked judge memoized the legal mask per record (`Game._legal_cache`).
# Reproducing it — collisions and all — is required for bit-identity.
LEGAL_MASK_CACHE = True


def _f64_bits(x) -> int:
    """Raw f64 bit pattern — the rustport gate's own comparison currency."""
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def records_dir(chunk: int, leg: int) -> Path:
    return RECORDS_ROOT / f"chunk{chunk}" / "tier1-greedy" / "walled" / f"leg{leg}" / "records"


def positions_path(chunk: int, leg: int) -> Path:
    return POSITIONS_ROOT / f"positions_chunk{chunk}" / f"positions_walled_leg{leg}.jsonl"


def rids_in(chunk: int, leg: int) -> list:
    return sorted(p.stem for p in records_dir(chunk, leg).glob("*.json"))


def draw_sample() -> dict:
    """The committed draw. Ascending chunk, then ascending leg, ONE rng."""
    rng = random.Random(SAMPLE_SEED)
    out = {}
    for chunk in CHUNKS:
        for leg in LEGS:
            pool = sorted(rids_in(chunk, leg))
            out[(chunk, leg)] = rng.sample(pool, PER_CELL)
    return out


# --------------------------------------------------------------------------- #
# worker                                                                       #
# --------------------------------------------------------------------------- #
def _one(job: tuple) -> dict:
    """Reproduce ONE banked leg in rust and compare, bit for bit."""
    import carc_rs
    from oracle_score_pilot import playout_seed, world_seed

    chunk, leg, rid = job
    rec = json.loads((records_dir(chunk, leg) / f"{rid}.json").read_text())
    pos = None
    for line in positions_path(chunk, leg).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o["rid"] == rid:
            pos = o
            break
    if pos is None:
        return {"rid": rid, "chunk": chunk, "leg": leg, "error": "position_row_not_found"}

    # The rust run uses the record's OWN seeds, read off the record — never
    # recomputed-and-assumed.
    ws = [int(x) for x in rec["world_seeds"]]
    ps = [int(x) for x in rec["playout_seeds"]]

    # ...and a SEPARATE witness that the derivation still reproduces them.
    seed_witness = (
        ws == [world_seed(rid, j, WORLD_SEED_SALT) for j in range(len(ws))]
        and ps == [playout_seed(rid, j, WORLD_SEED_SALT) for j in range(len(ps))]
    )

    t0 = time.time()
    # `legal_mask_cache=True` reproduces `game_wrapper.Game._legal_cache`, the
    # per-record legal-mask memo the banked judge ran with — INCLUDING its key
    # collisions, which moved 57 of these 15,360 values. See
    # BITEXACT_DIVERGENCE.json and `carc_core::tier1`'s module docs. Grading the
    # gate against the honest-mask port instead would be grading a different
    # player than the one that produced the (BURNED, unregenerable) corpus.
    va, vb, pa, pb, cache_stats = carc_rs.tier1_leg(
        str(int(pos["deck_seed"])),
        [int(a) for a in pos["actions"]],
        int(pos["ply"]),
        int(pos["pick_a"]),
        int(pos["pick_b"]),
        int(pos["root_player"]),
        ws,
        ps,
        MAX_PLIES,
        LEGAL_MASK_CACHE,
    )
    elapsed = time.time() - t0

    py_va, py_vb = rec["values_a"], rec["values_b"]
    py_pa, py_pb = rec["playout_plies_a"], rec["playout_plies_b"]

    n_cmp = 0
    n_val_ok = 0
    n_plies_ok = 0
    first_mismatch = None
    for tag, r_v, p_v, r_p, p_p in (("a", va, py_va, pa, py_pa), ("b", vb, py_vb, pb, py_pb)):
        for j in range(min(len(r_v), len(p_v))):
            n_cmp += 1
            ok_v = _f64_bits(r_v[j]) == _f64_bits(p_v[j])
            ok_p = int(r_p[j]) == int(p_p[j])
            n_val_ok += int(ok_v)
            n_plies_ok += int(ok_p)
            if (not ok_v or not ok_p) and first_mismatch is None:
                first_mismatch = {
                    "arm": tag, "world": j,
                    "value_ok": bool(ok_v), "plies_ok": bool(ok_p),
                    "ply": int(pos["ply"]), "root_player": int(pos["root_player"]),
                }

    # Canonical bytes for the digest: rid-sorted outside, then values_a then
    # values_b, each as its little-endian f64.
    blob_r = b"".join(struct.pack("<d", float(x)) for x in list(va) + list(vb))
    blob_p = b"".join(struct.pack("<d", float(x)) for x in list(py_va) + list(py_vb))

    return {
        "rid": rid, "chunk": chunk, "leg": leg,
        "m": len(va), "n_compared": n_cmp,
        "n_value_bit_identical": n_val_ok,
        "n_plies_identical": n_plies_ok,
        "seed_witness_ok": bool(seed_witness),
        "first_mismatch": first_mismatch,
        "elapsed_secs": elapsed,
        "cache_hits": int(cache_stats[0]), "cache_misses": int(cache_stats[1]),
        "blob_r": blob_r, "blob_p": blob_p,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=30)
    args = ap.parse_args()

    import carc_rs

    sample = draw_sample()
    rids_sorted = sorted(r for v in sample.values() for r in v)
    jobs = [(c, l, r) for (c, l), rs in sorted(sample.items()) for r in rs]

    print(f"[G-BITEXACT] {len(jobs)} legs (expected {N_LEGS_EXPECTED}), "
          f"{N_PLAYOUTS_EXPECTED} playouts expected, workers={args.workers}", flush=True)
    t0 = time.time()
    if args.workers <= 1:
        results = [_one(j) for j in jobs]
    else:
        import multiprocessing as mp
        with mp.Pool(args.workers) as pool:
            results = pool.map(_one, jobs, chunksize=1)
    wall = time.time() - t0

    errors = [r for r in results if r.get("error")]
    good = [r for r in results if not r.get("error")]

    n_cmp = sum(r["n_compared"] for r in good)
    n_val_ok = sum(r["n_value_bit_identical"] for r in good)
    n_plies_ok = sum(r["n_plies_identical"] for r in good)
    n_seed_ok = sum(1 for r in good if r["seed_witness_ok"])

    by_rid = {r["rid"]: r for r in good}
    h_r, h_p = hashlib.sha256(), hashlib.sha256()
    for rid in rids_sorted:
        r = by_rid.get(rid)
        if r is None:
            continue
        h_r.update(r["blob_r"])
        h_p.update(r["blob_p"])

    cells = {f"chunk{c}_leg{l}": {
        "n_legs": sum(1 for r in good if r["chunk"] == c and r["leg"] == l),
        "n_playouts": sum(r["n_compared"] for r in good if r["chunk"] == c and r["leg"] == l),
        "n_value_bit_identical": sum(r["n_value_bit_identical"]
                                     for r in good if r["chunk"] == c and r["leg"] == l),
        "n_plies_identical": sum(r["n_plies_identical"]
                                 for r in good if r["chunk"] == c and r["leg"] == l),
    } for c in CHUNKS for l in LEGS}

    mism = [r["first_mismatch"] | {"rid": r["rid"], "chunk": r["chunk"], "leg": r["leg"]}
            for r in good if r["first_mismatch"]]

    try:
        git_rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                          # pragma: no cover
        git_rev = None

    passed = (
        len(errors) == 0
        and len(good) == N_LEGS_EXPECTED
        and n_cmp == N_PLAYOUTS_EXPECTED
        and n_val_ok == N_PLAYOUTS_EXPECTED
        and n_plies_ok == N_PLAYOUTS_EXPECTED
        and n_seed_ok == N_LEGS_EXPECTED
        and h_r.hexdigest() == h_p.hexdigest()
    )

    out = {
        "gate": "G-BITEXACT",
        "design": "measurement/tiearb2_stage2_20260817/PHASE_A.md#3",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pass": bool(passed),
        # --- committed constants, graded against, never against len(found) ---
        "n_legs_expected": N_LEGS_EXPECTED,
        "n_legs_found": len(good),
        "n_playouts_expected": N_PLAYOUTS_EXPECTED,
        "n_playouts_compared": n_cmp,
        "n_value_bit_identical": n_val_ok,
        "n_value_mismatch": n_cmp - n_val_ok,
        "n_plies_identical": n_plies_ok,
        "n_plies_mismatch": n_cmp - n_plies_ok,
        "n_seed_witness_ok": n_seed_ok,
        "sha256_values_rust": h_r.hexdigest(),
        "sha256_values_python": h_p.hexdigest(),
        "digests_equal": h_r.hexdigest() == h_p.hexdigest(),
        "sample_seed": SAMPLE_SEED,
        "sample_per_cell": PER_CELL,
        "m_expected": M_EXPECTED,
        "max_plies": MAX_PLIES,
        "legal_mask_cache": LEGAL_MASK_CACHE,
        "legal_mask_cache_note": (
            "Reproduces game_wrapper.Game._legal_cache, the per-record legal-mask "
            "memo the banked judge ran with, INCLUDING its string_representation "
            "key collisions (a 180-degree-symmetric tile's rotation signature is "
            "rotation-blind while its farm slots are not). Without it the port "
            "computes the honest mask and misses 57/15360 banked values; see "
            "BITEXACT_DIVERGENCE.json."),
        "cache_hits_total": sum(r.get("cache_hits", 0) for r in good),
        "cache_misses_total": sum(r.get("cache_misses", 0) for r in good),
        "world_seed_salt": WORLD_SEED_SALT,
        "rids": rids_sorted,
        "per_cell": cells,
        "mismatches": mism,
        "errors": [{k: v for k, v in e.items() if k != "blob_r"} for e in errors],
        "carc_rs_version": carc_rs.__version__,
        "carc_rs_file": carc_rs.__file__,
        "git_rev": git_rev,
        "workers": args.workers,
        "wall_secs": wall,
        "records_root": str(RECORDS_ROOT),
        "note": ("Counts only. The two sha256 digests are over the little-endian f64 "
                 "bytes of (values_a + values_b) concatenated in sorted-rid order; a "
                 "digest is not a value and is not invertible, so no adjudicated "
                 "per-leg value leaves this gate."),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("rids", "per_cell")},
                     indent=2))
    print(f"[G-BITEXACT] {'PASS' if passed else 'FAIL'} -> {OUT_PATH}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    raise SystemExit(main())
