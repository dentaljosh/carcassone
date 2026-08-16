#!/usr/bin/env python3
"""The DESIGN §5.4 STRATIFIED SYMMETRIC HALF-SPLIT for
measurement/tiearb2_20260816/ (Stage 1b).

Reads the FRESH corpus's `ARMS.json` and assigns every **root** (`root_id`, the
cluster unit — so no game straddles the split) to slice `S1` or `S2`.

  * roots are stratified into **18 cells**
    `phase_bucket (early/mid/late) × arm-count bucket ({2},{3},{4,5}) ×
     champ_is_arm0 (champ_arm_index == 0 ? T : F)`;
  * a root's cell is the **modal** cell over its own positions, ties broken by
    the **lexicographically smallest `rid`** in the tie;
  * within each cell the roots are **sorted**, shuffled with
    `random.Random(20260816)` and assigned **alternately** S1/S2, so every cell
    is balanced to **±1 root** by construction.

⚠️ This script is a *carve*, not a measurement: it reads only selection metadata
(`root_id`, `phase_bucket`, `arms`, `champ_arm_index`) and never opens an oracle
record, a value, or any statistic. It is the instrument DESIGN §5.4 names as the
fix for Stage 1's plain unstratified `mine_oracle_sep.make_split` carve.

Outputs `measurement/tiearb2_20260816/SPLIT.json`. `--verify` re-derives the
split from the same inputs and asserts byte-identity with what is on disk (the
reproducibility witness for `G-SPLIT`).

Usage:
    python3 scripts/tiletie/split_tiearb2.py                    # write SPLIT.json
    python3 scripts/tiletie/split_tiearb2.py --verify           # reproducibility
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

SCHEMA = "carcassonne-tiearb2-split/v1"
DESIGN_DOC = "measurement/tiearb2_20260816/DESIGN.md"
READ_RULE = "measurement/tiearb2_20260816/READ_RULE.md"

SPLIT_SEED = 20260816          # DESIGN §5.4 — committed with the design
SLICES = ("S1", "S2")

PHASES = ("early", "mid", "late")
ARM_BUCKETS = ("2", "3", "4-5")
CHAMP0 = ("T", "F")

#: the 18 cells, in a FIXED order — emitted in full (zeros included) so the
#: `G-SPLIT` balance witness is complete rather than "the cells we happened to
#: populate".
ALL_CELLS = tuple(f"{p}|{a}|{c}" for p in PHASES for a in ARM_BUCKETS for c in CHAMP0)
assert len(ALL_CELLS) == 18


# --------------------------------------------------------------------------- #
# cells                                                                        #
# --------------------------------------------------------------------------- #
def arm_count_bucket(n_arms: int) -> str:
    """{2} / {3} / {4,5} — DESIGN §5.4. `build_positions.py --cap-j 4` caps the
    tie set at 4 candidates + the reference arm, so 5 is the maximum."""
    if n_arms < 2:
        raise ValueError(f"a tie set with {n_arms} arms is not a tie")
    if n_arms == 2:
        return "2"
    if n_arms == 3:
        return "3"
    return "4-5"


def position_cell(meta: dict) -> str:
    """The stratification cell of ONE position."""
    phase = meta.get("phase_bucket")
    if phase not in PHASES:
        raise ValueError(f"unknown phase_bucket {phase!r}; expected one of {PHASES}")
    armb = arm_count_bucket(len(meta["arms"]))
    champ0 = "T" if meta.get("champ_arm_index") == 0 else "F"
    return f"{phase}|{armb}|{champ0}"


def modal_cell(rid_cells) -> str:
    """The MODAL cell over a root's own positions.

    `rid_cells` is an iterable of `(rid, cell)`. Ties are broken by the
    **lexicographically smallest rid** in the tie: among the cells that share the
    maximal count, the winner is the one holding the smallest rid. That is a
    total order (rids are unique within a root), so the tie-break is
    deterministic and independent of iteration order.
    """
    counts = defaultdict(int)
    min_rid = {}
    for rid, cell in rid_cells:
        counts[cell] += 1
        if cell not in min_rid or rid < min_rid[cell]:
            min_rid[cell] = rid
    if not counts:
        raise ValueError("a root with no positions cannot be assigned a cell")
    top = max(counts.values())
    tied = sorted(c for c, n in counts.items() if n == top)
    return min(tied, key=lambda c: min_rid[c])


def root_cells(arms: dict) -> tuple:
    """{root_id: cell}, {root_id: [rid, ...]} — the cluster unit is `root_id`."""
    by_root = defaultdict(list)
    for rid in sorted(arms):
        meta = arms[rid]
        by_root[meta["root_id"]].append((rid, position_cell(meta)))
    cell_of = {root: modal_cell(pairs) for root, pairs in by_root.items()}
    rids_of = {root: [rid for rid, _c in pairs] for root, pairs in by_root.items()}
    return cell_of, rids_of


# --------------------------------------------------------------------------- #
# the carve                                                                    #
# --------------------------------------------------------------------------- #
def assign_slices(cell_of: dict, seed: int = SPLIT_SEED) -> tuple:
    """Alternate S1/S2 within each cell over a seeded shuffle of the SORTED roots.

    A fresh `random.Random(seed)` is constructed **per cell** (DESIGN §5.4's
    literal wording), so the carve is a pure function of (roots, seed) and does
    not depend on the order the cells are visited.
    """
    by_cell = defaultdict(list)
    for root, cell in cell_of.items():
        by_cell[cell].append(root)
    s1, s2, cell_roots = [], [], {}
    for cell in ALL_CELLS:
        roots = sorted(by_cell.get(cell, []))
        random.Random(seed).shuffle(roots)
        cell_roots[cell] = roots
        for i, root in enumerate(roots):
            (s1 if i % 2 == 0 else s2).append(root)
    unknown = sorted(set(by_cell) - set(ALL_CELLS))
    if unknown:                                     # pragma: no cover - defensive
        raise ValueError(f"cell(s) outside the committed 18: {unknown}")
    return sorted(s1), sorted(s2), cell_roots


def build_split(arms: dict, seed: int = SPLIT_SEED, arms_path=None) -> dict:
    cell_of, rids_of = root_cells(arms)
    s1, s2, cell_roots = assign_slices(cell_of, seed)
    s1set, s2set = set(s1), set(s2)

    cells = {}
    balance_ok = True
    for cell in ALL_CELLS:
        roots = cell_roots.get(cell, [])
        n1 = sum(1 for r in roots if r in s1set)
        n2 = sum(1 for r in roots if r in s2set)
        p1 = sum(len(rids_of[r]) for r in roots if r in s1set)
        p2 = sum(len(rids_of[r]) for r in roots if r in s2set)
        if abs(n1 - n2) > 1:                        # pragma: no cover - defensive
            balance_ok = False
        cells[cell] = {"n_roots": len(roots), "n_S1_roots": n1, "n_S2_roots": n2,
                       "n_S1_positions": p1, "n_S2_positions": p2,
                       "balanced": abs(n1 - n2) <= 1}

    n_pos_1 = sum(len(rids_of[r]) for r in s1)
    n_pos_2 = sum(len(rids_of[r]) for r in s2)
    return {
        "schema": SCHEMA,
        "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE,
        "design_ref": "DESIGN §5.4 — the stratified symmetric half-split; "
                      "clustering on root_id, so no game straddles the split.",
        "seed": seed,
        "arms_json": str(arms_path) if arms_path else None,
        "strata": {"phase_bucket": list(PHASES), "arm_count_bucket": list(ARM_BUCKETS),
                   "champ_is_arm0": list(CHAMP0), "n_cells": len(ALL_CELLS)},
        "cell_key_format": "phase_bucket|arm_count_bucket|champ_is_arm0",
        "root_cell_rule": "the MODAL cell over the root's own positions; ties broken "
                          "by the lexicographically smallest rid in the tie.",
        "shuffle_rule": "within each cell: sort roots, shuffle with a FRESH "
                        f"random.Random({seed}), then assign alternately S1/S2 "
                        "(so every cell is balanced to ±1 root by construction).",
        "n_positions": len(arms),
        "n_roots": len(cell_of),
        "n_S1_roots": len(s1), "n_S2_roots": len(s2),
        "n_S1_positions": n_pos_1, "n_S2_positions": n_pos_2,
        "cells": cells,
        "balance_ok": bool(balance_ok),
        "S1_roots": s1,
        "S2_roots": s2,
        "governance": "Selection metadata only. No oracle record, value or statistic "
                      "is read by this script, on any branch.",
    }


# --------------------------------------------------------------------------- #
# I/O                                                                          #
# --------------------------------------------------------------------------- #
def canonical(split: dict) -> str:
    """The byte-comparable form: sorted keys, volatile fields dropped."""
    d = {k: v for k, v in split.items() if k not in ("generated_utc", "arms_json")}
    return json.dumps(d, indent=1, sort_keys=True)


def load_arms(path) -> dict:
    return json.loads(Path(path).read_text())


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms",
                    default=str(REPO / "measurement/tiearb2_20260816/corpus/"
                                       "positions/ARMS.json"),
                    help="the FRESH corpus's ARMS.json (build_positions.py output)")
    ap.add_argument("--out",
                    default=str(REPO / "measurement/tiearb2_20260816/SPLIT.json"))
    ap.add_argument("--seed", type=int, default=SPLIT_SEED)
    ap.add_argument("--verify", action="store_true",
                    help="re-derive the split and assert byte-identity with --out")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    arms_path = Path(a.arms)
    if not arms_path.is_file():
        raise SystemExit(f"REFUSING: ARMS.json not found: {arms_path}")
    split = build_split(load_arms(arms_path), seed=a.seed, arms_path=arms_path)
    out = Path(a.out)

    if a.verify:
        if not out.is_file():
            raise SystemExit(f"REFUSING: --verify but {out} does not exist")
        on_disk = json.loads(out.read_text())
        if canonical(on_disk) != canonical(split):
            raise SystemExit(
                f"REFUSING: G-SPLIT reproducibility FAILED — re-deriving the split "
                f"from {arms_path} at seed {a.seed} does not reproduce {out}.")
        print(f"[split_tiearb2] VERIFY OK — {out} is byte-identical to a fresh "
              f"derivation at seed {a.seed} "
              f"({split['n_roots']} roots, {split['n_positions']} positions, "
              f"balance_ok={split['balance_ok']}).")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(split, indent=1, sort_keys=True) + "\n")
    print(f"[split_tiearb2] {split['n_roots']} roots / {split['n_positions']} positions "
          f"-> S1 {split['n_S1_roots']} roots / {split['n_S1_positions']} positions · "
          f"S2 {split['n_S2_roots']} roots / {split['n_S2_positions']} positions")
    print(f"[split_tiearb2] 18-cell balance_ok = {split['balance_ok']}")
    for cell in ALL_CELLS:
        c = split["cells"][cell]
        print(f"    {cell:>16}  roots {c['n_roots']:>4}  "
              f"S1 {c['n_S1_roots']:>4}/{c['n_S1_positions']:>4}  "
              f"S2 {c['n_S2_roots']:>4}/{c['n_S2_positions']:>4}  "
              f"{'ok' if c['balanced'] else '**OFF-BALANCE**'}")
    print(f"[wrote] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
