#!/usr/bin/env python3
"""Claim the curve-shape/phase bands in governance/BAND_REGISTRY.csv via csv.writer.

8 fields: band_seed_start,label,tier,status,claimed_date,decision_influenced,
evidence_or_claim,notes  -- never hand-edit (the file carries quoted commas and
doubled-quote escapes).
"""
import csv
from pathlib import Path

REG = Path("/home/doctor/projects/carcassone/governance/BAND_REGISTRY.csv")

ROWS = [
    (
        110000000000,
        "CURVE-SHAPE CURVATURE PROBE (Part A / S0): 4 cells n=400 deck-paired FAIR PIMC "
        "k8x1376, fixed_v1+R9, rust, vs the curve125 champion. Cells: C0_identity "
        "(production literal, the wiring gate) / C1_flattop (rho=0.4) / C2_broadlow "
        "(gamma=0.8, d=16) / C3_hoard (rho=1.2). ALL CELLS SAME BAND (within-band "
        "deck-matched contrast is the robust class).",
        "dev",
        "claimed",
        "2026-08-09",
        "pending",
        "measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part A",
        "Funded 2026-08-09. Doubles as Part B's S0 if Part B is ever funded. "
        "Reading is pre-registered A1-A4; A1 (all three off-production cells within "
        "+/-25 elo) => do NOT fund the 3.9-box-day sweep.",
    ),
    (
        115000000000,
        "MEEPLE-CURVE PHASE (beta) DOSE LADDER (Part C): 5 cells beta in "
        "{-0.6,-0.3,0.0,+0.3,+0.6}, n=200 deck-paired FAIR PIMC k8x1376, fixed_v1+R9, "
        "rust, vs the curve125 champion; curve multiplied by "
        "f(k;beta)=clip(1+beta*(k-35)/35,0,2) renormalized to E[f]=1. beta=0 is the "
        "identity/wiring cell. ALL CELLS SAME BAND -- the primary statistic is the "
        "FITTED WITHIN-DECK SLOPE across the ladder, not any single cell.",
        "dev",
        "claimed",
        "2026-08-09",
        "pending",
        "measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part C",
        "Funded 2026-08-09. The E[f]=1 renormalization is the ONLY thing licensing this "
        "retry of the 2026-06-22 v28_meeple_recovery_t0 kill (that cell confounded phase "
        "with a mean-magnitude cut). A negative slope RECONFIRMS v28 and closes the axis.",
    ),
]


def main() -> int:
    existing = set()
    with REG.open(newline="") as f:
        for row in csv.reader(f):
            if row and row[0].strip().isdigit():
                existing.add(int(row[0]))
    new = [r for r in ROWS if r[0] not in existing]
    if not new:
        print("[bands] all rows already present, nothing appended")
        return 0
    with REG.open("a", newline="") as f:
        w = csv.writer(f)
        for r in new:
            w.writerow(r)
    print(f"[bands] appended {len(new)} row(s): {[r[0] for r in new]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
