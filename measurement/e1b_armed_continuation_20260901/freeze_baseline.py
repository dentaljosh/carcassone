#!/usr/bin/env python3
"""Freeze the E-1a (2026-08-28) CHAMPION-continuation baseline this round re-prices.

E-1b changes exactly ONE thing about `measurement/e4_continuation_20260828`: the
CONTINUATION POLICY FAMILY. Everything else — the 91 target plies, the M=8 CRN
worlds, the root states, the arm actions, the estimator — is held identical.

That "held identical" is not a promise; it is a CHECKABLE FACT, because every
one of the E-1a run's CRN witness fields is a property of the ROOT and the WORLD
and carries **no continuation-policy term**:

    root_repr_sha · world_deck_sha · world_deck_len · n_drawn_prefix
    n_legal_root  · det_seed_base_at_root · move_idx_at_root

So an E-1b unit MUST reproduce its E-1a sibling's witness bit-for-bit. This file
freezes those 728 witnesses (plus the banked, already-adjudicated per-world
price) so `adjudicate_e1b.py`'s `G-ROOT` gate can assert it, and so the
pre-registered family-paired secondary has a frozen comparator that cannot be
re-derived favourably after the fact.

⚠️ The banked PRICES in here are ALREADY PUBLIC — `CONTINUATION.json` is the
adjudicated verdict of record (PRIMARY NULL, -1.87 +/- 1.88). Freezing them
spends no blindness: what is blind in this round is the ARMED outcome, and none
of it exists yet. See PREREG.md §0.1.

Usage (the E-1a unit dirs, wherever they live):
    python3 freeze_baseline.py --units <dir> [<dir> ...] \\
        --targets <e4_continuation_20260828>/targets_continuation.jsonl \\
        --verdict /mnt/c/carc-shared/e4_continuation_20260828/CONTINUATION.json \\
        --out CRN_BASELINE.json
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

WITNESS_KEYS = ("root_repr_sha", "world_deck_sha", "world_deck_len",
                "n_drawn_prefix", "n_legal_root", "det_seed_base_at_root",
                "move_idx_at_root")


def unit_key(game: str, ply: int, world: int) -> str:
    return f"{game}|{int(ply)}|{int(world)}"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", nargs="+", required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--verdict", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    units, strata = {}, collections.Counter()
    for d in args.units:
        for f in sorted(Path(d).glob("unit_*.json")):
            r = json.loads(f.read_text())
            pair = r.get("pair") or {}
            if pair.get("status") != "OK":
                raise SystemExit(
                    f"{f}: the E-1a run landed 728/728 OK pairs; a non-OK pair "
                    f"here means these are not the banked units ({pair})")
            w = pair["crn_witness"]
            missing = [k for k in WITNESS_KEYS if k not in w]
            if missing:
                raise SystemExit(f"{f}: witness missing {missing}")
            units[unit_key(r["game"], r["ply"], r["world"])] = {
                "stratum": r["stratum"], "actor": int(r["actor"]),
                "profile": r["profile"],
                "witness": {k: w[k] for k in WITNESS_KEYS},
                "margin_owner": pair["margin_owner"],
                "margin_cf": pair["margin_cf"],
                "delta_pts_mover": pair["delta_pts_mover"],
                "followup_agrees_with_archive": r.get(
                    "followup_agrees_with_archive"),
            }
            strata[r["stratum"]] += 1

    targets = [json.loads(l) for l in Path(args.targets).open()]
    want = {(t["game"], int(t["ply"])) for t in targets}
    have = {(k.split("|")[0], int(k.split("|")[1])) for k in units}
    if want != have:
        raise SystemExit(f"target/unit ply mismatch: missing {sorted(want - have)[:5]} "
                         f"stray {sorted(have - want)[:5]}")

    out = {
        "schema": "e1b-crn-baseline/v1",
        "source_run": "measurement/e4_continuation_20260828",
        "source_unit_dirs": [str(Path(d).resolve()) for d in args.units],
        "targets_sha256": sha256_file(Path(args.targets)),
        "witness_keys": list(WITNESS_KEYS),
        "n_units": len(units),
        "n_plies": len(have),
        "units_by_stratum": dict(strata),
        "banked_verdict": (json.loads(Path(args.verdict).read_text())
                           if args.verdict else None),
        "units": units,
    }
    if out["banked_verdict"] is not None:
        out["banked_verdict"].pop("plies", None)
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"wrote {args.out}: {len(units)} units, {len(have)} plies, "
          f"strata {dict(strata)}")


if __name__ == "__main__":
    main()
