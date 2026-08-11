#!/usr/bin/env python3
"""One-shot migration: add `game` (river|base) + `code_rev` columns to results.csv.

WHY: the table conflates eras — the same matchup (iter_11@200 vs heur@200) appears
as +181.7 (River+buggy) and +25.2 (base-only bug-fixed) with nothing structural to
tell them apart (only a `baseonly` substring in exp_id). This adds an authoritative
`game` column so era is a filter, not a fragile grep. `code_rev` is 'unknown' for the
existing rows (git hash wasn't recorded pre-instrumentation); the eval harness stamps
it going forward (see carcassonne_ai.run_manifest).

Backfill rule (verified row-by-row 2026-06-04, see git log / DECISIONS):
  base  := exp_id contains 'baseonly'  OR  exp_id starts with 'verdict_'
           (the verdict_* re-sweep + the *baseonly* ladders/stage_b are the post-
            2026-06-02 base-only era; River was dropped 2026-06-02)
  river := everything else (all date<2026-06-02 work, incl diag_iter4 closure)

Idempotent: re-running after migration is a no-op.
"""
import csv
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "experiments" / "results.csv"


def game_for(exp_id: str) -> str:
    e = exp_id.lower()
    if "baseonly" in e or e.startswith("verdict_"):
        return "base"
    return "river"


def main():
    with open(CSV, newline="") as f:
        reader = csv.DictReader(f)
        old_fields = reader.fieldnames
        rows = list(reader)
    if "game" in old_fields:
        print("already migrated (game column present) — no-op")
        return
    # insert game, code_rev right after date
    i = old_fields.index("date") + 1
    new_fields = old_fields[:i] + ["game", "code_rev"] + old_fields[i:]
    for r in rows:
        r["game"] = game_for(r["exp_id"])
        r["code_rev"] = "unknown"
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=new_fields)
        w.writeheader()
        w.writerows(rows)
    nb = sum(1 for r in rows if r["game"] == "base")
    print(f"migrated {len(rows)} rows: {nb} base, {len(rows)-nb} river")
    print("BASE rows (verify):")
    for r in rows:
        if r["game"] == "base":
            print(f"  {r['date']}  {r['exp_id']}")


if __name__ == "__main__":
    main()
