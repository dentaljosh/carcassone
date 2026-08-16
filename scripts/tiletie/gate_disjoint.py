#!/usr/bin/env python3
"""G-DISJOINT — hard gate: the FRESH tie-arbitration corpus must not touch the
SPENT one on ANY identity.

The tiearb2_20260816 corpus exists because the 2026-08-12 tile-tie corpus
(733 positions / 399 roots) is SPENT: it selected the read rule, so re-using any
of its positions in the confirmatory corpus would re-import the winner's curse
the successor run is built to escape. "Fresh deck-seed band" is the mechanism;
this gate is the PROOF, and it is deliberately over-determined — three
independent identities, any overlap fails the run:

  a. `root_id`   — the GAME. Two plies of the same game are not independent
                   draws, so a shared root contaminates even at distinct plies.
                   Read from `ARMS.json` values' `root_id` on both sides.
  b. `rid`       — the (game, ply) POSITION identity `build_positions.rid_for`
                   assigns. Read from `ARMS.json` KEYS on both sides.
  c. `sha256(checksum)` — the BOARD. `checksum` is
                   `game.string_representation(board)` at the tied root, carried
                   verbatim on every leg jsonl line. This is the strongest layer:
                   it catches the same board reached from a DIFFERENT game or a
                   different ply, which neither (a) nor (b) can see.

The gate REPORTS COUNTS ONLY — never a rid, a root_id, a checksum or a digest.
A gate that printed the overlapping values would leak spent-corpus identities
into the fresh corpus's own audit trail; the count is the whole finding, and the
two rid-list sha256s let a later reader prove which two sets were compared
without either set being reproducible from the report.

Exit codes
    0   all three intersections empty
    1   ANY intersection non-empty (loud banner on stderr)
    2   an input is missing / unreadable (the gate could not be evaluated)

Usage (defaults are the tiearb2 vs 2026-08-12 pairing):
    python scripts/tiletie/gate_disjoint.py
    python scripts/tiletie/gate_disjoint.py --new-dir <dir> --spent-dir <dir> --out <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEFAULT_SPENT_DIR = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
DEFAULT_NEW_DIR = REPO / "measurement/tiearb2_20260816/corpus/positions"
DEFAULT_OUT = REPO / "measurement/tiearb2_20260816/DISJOINTNESS.json"

#: leg1 carries EVERY position exactly once (leg r exists only for positions
#: with >= r+1 arms, and every scoreable position has at least 2), so leg1 is the
#: complete board census of a corpus. Higher legs would duplicate checksums.
SPENT_LEG_GLOB = "positions_*_leg1.jsonl"
NEW_LEG_GLOB = "positions_*_leg1.jsonl"


class GateInputError(RuntimeError):
    """An input the gate needs is missing or malformed (exit 2, not a failure of
    disjointness — the gate simply could not be evaluated)."""


# --------------------------------------------------------------------------- #
# loaders                                                                       #
# --------------------------------------------------------------------------- #
def _load_arms(path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise GateInputError(f"ARMS.json not found: {path}")
    try:
        arms = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise GateInputError(f"{path}: not JSON ({exc})") from exc
    if not isinstance(arms, dict):
        raise GateInputError(f"{path}: expected a rid-keyed object, got "
                             f"{type(arms).__name__}")
    return arms


def load_rids(arms_path) -> set[str]:
    """The corpus's rid set — the KEYS of ARMS.json."""
    return set(_load_arms(arms_path))


def load_root_ids(arms_path) -> set[str]:
    """The corpus's root (game) set — `root_id` off every ARMS.json value."""
    arms = _load_arms(arms_path)
    missing = [k for k, v in arms.items() if "root_id" not in v]
    if missing:
        raise GateInputError(f"{arms_path}: {len(missing)} entr(ies) carry no "
                             f"'root_id' — cannot evaluate layer (a)")
    return {str(v["root_id"]) for v in arms.values()}


def leg_paths(directory, glob_pat) -> list[Path]:
    paths = sorted(Path(directory).glob(glob_pat))
    if not paths:
        raise GateInputError(f"no leg files matching {glob_pat!r} under "
                             f"{directory}")
    return paths


def load_digests(paths) -> tuple[set[str], int]:
    """`sha256(checksum)` over every leg line. Returns (digest set, n_lines).

    A collision between the set size and the line count is NOT an error here
    (the caller reports both); within one corpus leg1 they should be equal."""
    digests: set[str] = set()
    n_lines = 0
    for p in paths:
        p = Path(p)
        if not p.is_file():
            raise GateInputError(f"leg file not found: {p}")
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateInputError(f"{p}:{i}: not JSON ({exc})") from exc
            if "checksum" not in rec:
                raise GateInputError(f"{p}:{i}: no 'checksum' field — cannot "
                                     f"evaluate layer (c)")
            n_lines += 1
            digests.add(hashlib.sha256(str(rec["checksum"]).encode()).hexdigest())
    return digests, n_lines


def sha256_of_ids(ids) -> str:
    """A stable fingerprint of an id SET: sha256 over the sorted ids, one per
    line, trailing newline included. Lets a later reader prove WHICH two sets
    were compared without this report making either set reproducible."""
    return hashlib.sha256(
        "".join(str(i) + "\n" for i in sorted(ids)).encode()).hexdigest()


# --------------------------------------------------------------------------- #
# the gate                                                                      #
# --------------------------------------------------------------------------- #
def run_gate(*, spent_arms, new_arms, spent_legs, new_legs) -> dict:
    """Evaluate the three layers. Returns the report dict (counts only).
    Raises `GateInputError` if an input is missing."""
    spent_rids, new_rids = load_rids(spent_arms), load_rids(new_arms)
    spent_roots, new_roots = load_root_ids(spent_arms), load_root_ids(new_arms)
    spent_dig, spent_lines = load_digests(spent_legs)
    new_dig, new_lines = load_digests(new_legs)

    layers = {
        "a_root_id": {
            "identity": "root_id (the GAME) from ARMS.json values",
            "n_spent": len(spent_roots), "n_new": len(new_roots),
            "n_intersection": len(spent_roots & new_roots),
        },
        "b_rid": {
            "identity": "rid (the (game, ply) POSITION) from ARMS.json keys",
            "n_spent": len(spent_rids), "n_new": len(new_rids),
            "n_intersection": len(spent_rids & new_rids),
        },
        "c_position_digest": {
            "identity": "sha256(checksum) where checksum = "
                        "game.string_representation(board) at the tied root",
            "n_spent": len(spent_dig), "n_new": len(new_dig),
            "n_intersection": len(spent_dig & new_dig),
            "n_spent_leg_lines": spent_lines, "n_new_leg_lines": new_lines,
        },
    }
    n_bad = sum(1 for L in layers.values() if L["n_intersection"])
    report = {
        "gate": "G-DISJOINT",
        "goal": "the fresh tie-arbitration corpus shares NO game, NO position "
                "and NO board with the spent 2026-08-12 corpus",
        "disclosure_policy": "COUNTS ONLY — no rid, root_id, checksum or digest "
                             "value appears in this report by construction",
        "inputs": {
            "spent_arms": str(spent_arms), "new_arms": str(new_arms),
            "spent_legs": [str(p) for p in spent_legs],
            "new_legs": [str(p) for p in new_legs],
        },
        "layers": layers,
        "sha256_spent_rid_list": sha256_of_ids(spent_rids),
        "sha256_new_rid_list": sha256_of_ids(new_rids),
        "n_layers_violated": n_bad,
        "passed": n_bad == 0,
    }
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spent-dir", default=str(DEFAULT_SPENT_DIR))
    ap.add_argument("--new-dir", default=str(DEFAULT_NEW_DIR))
    ap.add_argument("--spent-arms", default=None,
                    help="default: <spent-dir>/ARMS.json")
    ap.add_argument("--new-arms", default=None,
                    help="default: <new-dir>/ARMS.json")
    ap.add_argument("--spent-leg-glob", default=SPENT_LEG_GLOB)
    ap.add_argument("--new-leg-glob", default=NEW_LEG_GLOB)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)

    spent_dir, new_dir = Path(a.spent_dir), Path(a.new_dir)
    spent_arms = Path(a.spent_arms) if a.spent_arms else spent_dir / "ARMS.json"
    new_arms = Path(a.new_arms) if a.new_arms else new_dir / "ARMS.json"

    try:
        report = run_gate(
            spent_arms=spent_arms, new_arms=new_arms,
            spent_legs=leg_paths(spent_dir, a.spent_leg_glob),
            new_legs=leg_paths(new_dir, a.new_leg_glob))
    except GateInputError as exc:
        print(f"\n{'=' * 70}\n[G-DISJOINT] COULD NOT EVALUATE: {exc}\n{'=' * 70}",
              file=sys.stderr)
        return 2

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True))

    for name, L in sorted(report["layers"].items()):
        print(f"[G-DISJOINT] {name:20s} spent={L['n_spent']:6d} "
              f"new={L['n_new']:6d} intersection={L['n_intersection']:6d}")
    print(f"[G-DISJOINT] sha256(spent rid list) = {report['sha256_spent_rid_list']}")
    print(f"[G-DISJOINT] sha256(new   rid list) = {report['sha256_new_rid_list']}")
    if a.out:
        print(f"[G-DISJOINT] -> {a.out}")

    if not report["passed"]:
        bad = sorted(k for k, L in report["layers"].items() if L["n_intersection"])
        print(f"\n{'=' * 70}\n"
              f"[G-DISJOINT] ***** GATE FAILED *****\n"
              f"[G-DISJOINT] {report['n_layers_violated']} of 3 identity layers "
              f"OVERLAP the spent corpus: {', '.join(bad)}\n"
              f"[G-DISJOINT] The fresh corpus is CONTAMINATED — it re-uses "
              f"positions that already selected the read rule.\n"
              f"[G-DISJOINT] DO NOT score it. Rebuild the corpus from a clean "
              f"deck-seed band.\n{'=' * 70}", file=sys.stderr)
        return 1

    print("[G-DISJOINT] PASS — all three intersections are empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
