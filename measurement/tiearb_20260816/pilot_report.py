#!/usr/bin/env python3
"""DESIGN §5 COST PILOT report — writes PILOT.json.

⚠️ READS ONLY wall-clock / `elapsed_secs` / `n_ok` / `n_failed` / `crn_verified`,
the world+playout-seed identity witness, and the `G-REPRO` bit-reproduction
COUNT. It does NOT read (and this file never prints) `values_a`, `values_b`,
`per_world_delta`, `mean_a`, `mean_b`, `delta`, any sd, or any statistic derived
from them. `G-REPRO` compares a sha256 of the value lists and emits only the
number of matching legs — never a value.

Mechanical rule (DESIGN §5), evaluated here, no owner call:
  1. n_failed > 0  OR  any crn_verified false  OR  any world/playout-seed
     mismatch vs the pricing record  OR  G-REPRO < 43/43   =>  ABORT.
  2. H = 25,088 * c / (3600 * 30)
       H <= 4.0  => launch all 4 chunks
       H >  4.0  => launch ceil(4 * 4.0 / H) chunks, floor 3
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
M = REPO / "measurement/tiearb_20260816"
PILOT_ROOT = Path("/mnt/c/carc-shared/tiearb_20260816/pilot/tier1-greedy")
OOF_PILOT_ROOT = Path("/mnt/c/carc-shared/tiletie_oof_20260814/pilot/tier1-greedy")
IF_ROOT = Path("/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct")
HOLDOUT_PLAYOUTS = 25088
EXPECT_LEGS = 43
_LEG_RE = re.compile(r"^leg(\d+)$")


def walk(root: Path) -> dict:
    """{(rid, leg): record} over <root>/<profile>/leg<r>/records/*.json."""
    out = {}
    if not root.is_dir():
        raise SystemExit(f"REFUSING: records root missing: {root}")
    for prof in sorted(p for p in root.iterdir() if p.is_dir()):
        for legdir in sorted(p for p in prof.iterdir() if p.is_dir()):
            mm = _LEG_RE.match(legdir.name)
            if not mm:
                continue
            leg = int(mm.group(1))
            rdir = legdir / "records"
            if not rdir.is_dir():
                continue
            for f in sorted(rdir.glob("*.json")):
                rec = json.loads(f.read_text())
                key = (rec["rid"], leg)
                if key in out:
                    raise SystemExit(f"REFUSING: duplicate record {key} under {root}")
                out[key] = rec
    return out


def fingerprint(rec: dict) -> str:
    """sha256 over the value + seed lists. Returns a HASH, never a value."""
    h = hashlib.sha256()
    for k in ("values_a", "values_b", "world_seeds", "playout_seeds"):
        h.update(k.encode())
        h.update(json.dumps(rec[k], separators=(",", ":"), sort_keys=False).encode())
    return h.hexdigest()


def main() -> int:
    new = walk(PILOT_ROOT)
    oof = walk(OOF_PILOT_ROOT)
    ifr = walk(IF_ROOT)

    n = len(new)
    n_ok = sum(1 for r in new.values() if r.get("ok"))
    n_failed = n - n_ok
    n_crn = sum(1 for r in new.values() if r.get("crn_verified") is True)
    n_checksum = sum(1 for r in new.values() if r.get("checksum_ok") is True)

    world_id = playout_id = arm_id = 0
    missing_if = []
    for key, rec in new.items():
        ref = ifr.get(key)
        if ref is None:
            missing_if.append(list(key))
            continue
        if list(rec["world_seeds"]) == list(ref["world_seeds"]):
            world_id += 1
        if list(rec["playout_seeds"]) == list(ref["playout_seeds"]):
            playout_id += 1
        if (rec.get("pick_a"), rec.get("pick_b")) == (ref.get("pick_a"), ref.get("pick_b")):
            arm_id += 1

    repro = 0
    repro_missing = []
    for key, rec in new.items():
        prev = oof.get(key)
        if prev is None:
            repro_missing.append(list(key))
            continue
        if fingerprint(rec) == fingerprint(prev):
            repro += 1

    playouts = sum(len(r["values_a"]) + len(r["values_b"]) for r in new.values())
    sum_elapsed = sum(float(r.get("elapsed_secs") or 0.0) for r in new.values())
    c = sum_elapsed / playouts if playouts else float("nan")
    secs = sorted(float(r.get("elapsed_secs") or 0.0) for r in new.values())
    H = HOLDOUT_PLAYOUTS * c / (3600.0 * 30.0)

    abort_reasons = []
    if n != EXPECT_LEGS:
        abort_reasons.append(f"expected {EXPECT_LEGS} pilot legs, found {n}")
    if n_failed > 0:
        abort_reasons.append(f"n_failed = {n_failed}")
    if n_crn != n:
        abort_reasons.append(f"crn_verified {n_crn}/{n}")
    if world_id != n or playout_id != n:
        abort_reasons.append(f"CRN seed identity vs primary {world_id}/{playout_id} of {n}")
    if arm_id != n:
        abort_reasons.append(f"arm identity vs primary {arm_id}/{n}")
    if repro != EXPECT_LEGS:
        abort_reasons.append(f"G-REPRO {repro}/{EXPECT_LEGS}")
    if missing_if or repro_missing:
        abort_reasons.append(f"missing counterparts if={len(missing_if)} oof={len(repro_missing)}")

    if abort_reasons:
        chunks = 0
        decision = "ABORT — the holdout is NOT launched and stays unburned"
    elif H <= 4.0:
        chunks = 4
        decision = "LAUNCH ALL 4 CHUNKS (full 211-position holdout)"
    else:
        chunks = max(3, math.ceil(4 * 4.0 / H))
        decision = f"LAUNCH FIRST {chunks} CHUNKS (floor 3)"

    out = {
        "schema": "carcassonne-tiearb-pilot/v1",
        "design_doc": "measurement/tiearb_20260816/DESIGN.md",
        "scope": ("DESIGN §5 COST PILOT. Reads ONLY wall/elapsed/integrity and the "
                  "G-REPRO bit-reproduction COUNT. No value, no mean, no sd, no delta "
                  "was read from any record. The 20 pilot positions are DEV and enter "
                  "no read as pilot artefacts."),
        "n_legs_records": n, "playouts": playouts,
        "judge": "tier1-greedy", "backend": "python", "m": 32,
        "world_seed_salt": "tiletie-v1", "workers": 20,
        "integrity": {
            "records": n, "ok": n_ok, "n_failed": n_failed,
            "crn_verified": n_crn, "checksum_ok": n_checksum,
            "world_seed_identical_to_primary": world_id,
            "playout_seed_identical_to_primary": playout_id,
            "arm_identical_to_primary": arm_id,
            "missing_primary_counterpart": missing_if,
            "G_REPRO_bit_identical_to_oof": repro,
            "G_REPRO_expected": EXPECT_LEGS,
            "G_REPRO_missing_counterpart": repro_missing,
            "note": ("G-REPRO compares a sha256 over (values_a, values_b, world_seeds, "
                     "playout_seeds) against the 2026-08-14 OOF pilot records for the "
                     "same rid+leg. Only the COUNT is reported."),
        },
        "cost": {
            "sum_elapsed_secs": round(sum_elapsed, 1),
            "c_tier1_worker_s_per_playout": round(c, 4),
            "median_record_secs": round(secs[len(secs) // 2], 1) if secs else None,
            "max_record_secs": round(secs[-1], 1) if secs else None,
            "oof_pilot_c": 2.1783,
            "realized_over_oof_pilot": round(c / 2.1783, 3),
        },
        "mechanical_rule": {
            "rule_1_abort": ("ABORT: " + "; ".join(abort_reasons)) if abort_reasons
                            else "NOT TRIGGERED (0 failed / 0 crn / 0 seed / G-REPRO clean).",
            "rule_2_launch_shape": (f"H = {HOLDOUT_PLAYOUTS} x c / (3600 x 30) = "
                                    f"{H:.3f} wall-hours at W30."),
            "H_wall_hours_at_W30": round(H, 4),
            "worker_hours": round(HOLDOUT_PLAYOUTS * c / 3600.0, 2),
            "chunks_to_launch": chunks,
            "decision": decision,
        },
    }
    (M / "PILOT.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["integrity"], indent=1))
    print(json.dumps(out["cost"], indent=1))
    print(json.dumps(out["mechanical_rule"], indent=1))
    return 0 if not abort_reasons else 3


if __name__ == "__main__":
    raise SystemExit(main())
