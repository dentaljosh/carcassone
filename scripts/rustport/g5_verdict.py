"""Aggregate the P5 / G5 gate legs into one machine-readable verdict.

G5 has four legs (docs/RUSTPORT_BUILD_SPEC_2026-07-31.md, P5 row):

  1. flag tests      every merged Python flag test reproduced against carc_rs
                     (`tests/rustport/test_p5_flags.py`, plus the carc-core unit
                     tests) — reported, not re-run here.
  2. even shift      `even_shift_property.py` — the EVEN-shift property + the
                     odd-shift negative (the negative lives in the pytest file).
  3. flags-on fuzz   `lockstep_fuzz.py --start-rule retail` (and the row-18 /
                     control combinations).
  4. flags-off       G1-G4 `reconcile_*.py` re-run with NO flag set — the
                     byte-compatibility regression bar.

Every leg writes its own JSON with a `verdict` field; this collects them and
fails loudly if any is missing or not PASS.

Usage:
    .venv/bin/python scripts/rustport/g5_verdict.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
P5 = REPO / "measurement" / "rustport_p5"

LEGS = {
    "leg2_even_shift": [
        ("row6->18, engine rule, n=500", P5 / "G5_even_shift_engine.json"),
        ("row6->18, retail rule, n=500", P5 / "G5_even_shift_retail.json"),
        ("row6->8   (d=+2),  n=150", P5 / "G5_even_shift_drow2.json"),
        ("row6->0   (d=-6),  n=150", P5 / "G5_even_shift_drow-6.json"),
        ("row6->30  (d=+24), n=60 — last-row refusal probe",
         P5 / "G5_even_shift_drow24.json"),
        ("row+12/col+4 (both even), n=150", P5 / "G5_even_shift_dcol4.json"),
    ],
    "leg3_flags_on_fuzz": [
        ("retail @ row 6, n=1000", P5 / "G5_lockstep_fuzz_p5_retail.json"),
        ("engine @ row 6, n=1000 (flags-off control)",
         P5 / "G5_lockstep_fuzz_p5_engine_ctl.json"),
        ("engine @ row 18, n=1000", P5 / "G5_lockstep_fuzz_p5_engine_row18.json"),
        ("retail @ row 18, n=1000", P5 / "G5_lockstep_fuzz_p5_retail_row18.json"),
        ("engine @ row 30, n=120 — last-row refusal probe",
         P5 / "G5_lockstep_fuzz_p5_row30_probe.json"),
    ],
    "leg4_flags_off_regate": [
        ("G1 reconcile_engine --corpus all", P5 / "G5_regate_G1_engine_all.json"),
        ("G2 reconcile_leaf --corpus all --configs all",
         P5 / "G5_regate_G2_leaf_all.json"),
        ("G3 reconcile_search golden+det @344",
         REPO / "measurement" / "rustport_p3" / "G3_search_p5_regate.json"),
        ("G4 reconcile_fair --leg latch @k8x1376",
         REPO / "measurement" / "rustport_p4" / "G4_fair_p5_regate_latch.json"),
        ("G4 reconcile_fair --leg game @k8x1376",
         REPO / "measurement" / "rustport_p4" / "G4_fair_p5_regate_game.json"),
    ],
}

SIZE_KEYS = ("total_positions_compared", "total_values_compared", "values_compared",
             "positions_compared", "total_checks", "n_searches", "total_games",
             "mismatch_count", "n_mismatches", "wallclock_s", "wall_secs",
             "stop_reasons", "engine_error_games", "window_overflow_games",
             "totals", "verdict")


def summarize(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "verdict": "MISSING"}
    d = json.loads(path.read_text())
    out = {"path": str(path.relative_to(REPO))}
    for k in SIZE_KEYS:
        if k in d:
            out[k] = d[k]
    if "flags" in d:
        out["flags"] = d["flags"]
    if "shift" in d:
        out["shift"] = d["shift"]
    return out


def main() -> int:
    legs = {name: [{"leg": label, **summarize(p)} for label, p in items]
            for name, items in LEGS.items()}
    bad = [r for rows in legs.values() for r in rows if r.get("verdict") != "PASS"]
    payload = {
        "gate": "G5/flags",
        "verdict": "PASS" if not bad else "FAIL",
        "phase": "P5",
        "default_semantics": (
            "unchanged — no flag is enabled anywhere; MirrorState.from_seed(seed) "
            "with no kwargs is the byte-compatible walled engine (start_rule "
            "missing => 'engine', start (6, 15))"),
        "leg1_flag_tests": {
            "pytest": "tests/rustport/test_p5_flags.py",
            "cargo": "carc-core game:: unit tests",
            "note": "run by the suite, not aggregated here",
        },
        **legs,
        "failures": bad,
    }
    (P5 / "G5_VERDICT.json").write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({k: v for k, v in payload.items() if k != "failures"},
                     indent=2, default=str))
    print(f"G5: {payload['verdict']}  -> {P5 / 'G5_VERDICT.json'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
