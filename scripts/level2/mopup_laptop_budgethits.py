"""Mop up the laptop's capped budget-hits so a local UNCAPPED pass redoes them.

The laptop runs the K=4 probe with CARCASSONNE_TT_CAP set (so its 11GB can't
OOM). On a "monster" position the cap inflates nodes -> it budget-hits and writes
a `solved:false` result. Those are NOT genuine unsolved positions — local (uncapped)
can solve them. This script finds each `solved:false` json whose claim was made by
the laptop and deletes the json+claim, so a fresh local imap re-claims and solves
them uncapped.

GENUINE budget-hits (claim host == Doctor/Xeon, i.e. unsolved even uncapped at the
1M budget, e.g. greedy_s3500000000) are LEFT ALONE — they're correct selection-bias
data. Ambiguous (`solved:false` with no claim file) are also left (rare).

After this: relaunch local uncapped (the STATUS resume cmd) to solve the purged set.

Usage:
  python scripts/level2/mopup_laptop_budgethits.py /mnt/c/carc-shared/l23_k4_expand_probe [--apply]
  (dry-run by default; --apply actually deletes)
"""
import json
import sys
from pathlib import Path


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: mopup_laptop_budgethits.py <probe_out_dir> [--apply]")
        return 2
    out = Path(argv[0])
    apply = "--apply" in argv
    purge_host = "Laptop"

    laptop_bh, genuine_bh, ambiguous = [], [], []
    for jf in sorted(out.glob("*.json")):
        if jf.name.startswith("_"):
            continue
        try:
            g = json.load(open(jf)).get("gt", {}).get("clairvoyant", {})
        except Exception:
            continue
        if g.get("solved"):
            continue
        # this is a solved:false (budget-hit) result — who produced it?
        cf = jf.with_suffix(".claim")
        host = None
        if cf.exists():
            try:
                host = cf.read_text().split(":")[0].strip()
            except Exception:
                host = None
        if host == purge_host:
            laptop_bh.append((jf, cf))
        elif host in (None,):
            ambiguous.append(jf)
        else:
            genuine_bh.append((jf, host))

    print(f"solved:false breakdown -> laptop={len(laptop_bh)} "
          f"genuine(uncapped, kept)={len(genuine_bh)} ambiguous(no-claim, kept)={len(ambiguous)}")
    for jf, host in genuine_bh:
        print(f"  KEEP genuine [{host}]: {jf.name}")
    for jf in ambiguous:
        print(f"  KEEP ambiguous [no-claim]: {jf.name}")
    for jf, cf in laptop_bh:
        print(f"  {'PURGE' if apply else 'WOULD-PURGE'} laptop: {jf.name}")
        if apply:
            jf.unlink(missing_ok=True)
            cf.unlink(missing_ok=True)

    if laptop_bh and not apply:
        print("\nDry-run. Re-run with --apply to delete, then relaunch local UNCAPPED "
              "(STATUS resume cmd) to solve the purged set.")
    elif apply and laptop_bh:
        print(f"\nPurged {len(laptop_bh)} laptop budget-hits. Now relaunch local uncapped "
              "to re-solve them (fresh imap re-claims the now-missing json).")
    else:
        print("\nNothing to purge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
