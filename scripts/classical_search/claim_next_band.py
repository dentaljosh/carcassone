#!/usr/bin/env python3
"""Claim the NEXT FREE deck band in `governance/BAND_REGISTRY.csv`, at launch time.

Used by `scripts/classical_search/denial_simsplit_chain.sh`: each block claims its own
band **immediately before its own game 1** and never earlier, so a block that never runs
never consumes a band (bands are one-use for confirmatory work -- a band that influenced
a decision retires, CLAUDE.md "CROSS-BAND z's GET ~2x HUMILITY").

Two properties that matter more than they look:

* **Idempotent on resume.** The claimed band is mirrored into a per-block SENTINEL file.
  A re-run (crash resume, watchdog restart) reads the sentinel and re-uses the SAME band
  instead of claiming a second one -- otherwise every restart would burn a band and,
  worse, split one cell's decks across two bands, which is the exact cross-band pooling
  the house forbids.
* **csv.writer, never hand-formatted.** The registry carries quoted commas and doubled
  quotes inside its notes; the 8 fields are
  `band_seed_start,label,tier,status,claimed_date,decision_influenced,evidence_or_claim,notes`.
  (Same discipline as `claim_curveshape_bands.py`.)

`decision_influenced` is written as `pending` at claim time -- the house convention for a
live row (see the 1.10e11 / 1.15e11 rows). Close-out flips it and appends the verdict to
`notes`; `scripts/doc_lint.py` W4 flags live rows on purpose so they cannot be forgotten.

Read-only rehearsal: `--dry-run` prints the row it WOULD append and touches nothing.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
from pathlib import Path

DEFAULT_REGISTRY = Path("/home/doctor/projects/carcassone/governance/BAND_REGISTRY.csv")
STEP = 1_000_000_000


def read_bands(registry: Path) -> set[int]:
    """Every numeric band_seed_start already in the registry (comment rows skipped)."""
    out: set[int] = set()
    with registry.open(newline="") as f:
        for row in csv.reader(f):
            if row and row[0].strip().isdigit():
                out.add(int(row[0].strip()))
    return out


def next_free_band(existing: set[int], floor: int = 0, step: int = STEP) -> int:
    """The lowest `step`-aligned band that is > every existing band and >= `floor`.

    Deliberately NOT "the lowest unused gap": gaps below the high-water mark are
    unregistered-but-used territory (the share census carries probe bands that were
    no-band by design, e.g. the 1.09e11 f9_wall_probe note on the 1.03e11 row), so
    allocating into a gap risks colliding with decks that were actually played.
    """
    hi = max(existing) if existing else 0
    cand = ((max(hi + 1, floor) + step - 1) // step) * step
    while cand in existing:
        cand += step
    return cand


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--notes", required=True)
    ap.add_argument("--evidence", required=True, help="evidence_or_claim column (a doc path)")
    ap.add_argument("--tier", default="claim", choices=("dev", "sealed", "claim", "confirmatory"))
    ap.add_argument("--sentinel", required=True,
                    help="file that memoizes the claimed band for idempotent resume")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--date", default=None, help="claimed_date (default: today)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sent = Path(a.sentinel)
    if sent.exists():
        txt = sent.read_text().strip().splitlines()
        for line in txt:
            if line.strip().isdigit():
                print(line.strip())
                return 0

    reg = Path(a.registry)
    existing = read_bands(reg)
    band = next_free_band(existing)
    row = (band, a.label, a.tier, "claimed",
           a.date or _dt.date.today().isoformat(), "pending", a.evidence, a.notes)

    if a.dry_run:
        print(f"[dry-run] would claim band {band} (registry high-water "
              f"{max(existing) if existing else 0}) and append:")
        print(f"[dry-run]   {row}")
        print(band)
        return 0

    if band in read_bands(reg):                       # paranoia: re-read before append
        raise SystemExit(f"band {band} appeared in the registry between read and write")
    with reg.open("a", newline="") as f:
        csv.writer(f).writerow(row)
    sent.parent.mkdir(parents=True, exist_ok=True)
    sent.write_text(f"{band}\n{a.label}\nclaimed {row[4]}\n")
    print(band)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
