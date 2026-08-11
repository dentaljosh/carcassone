#!/usr/bin/env python3
"""Render the per-leg oracle artifacts as the markdown tables in VALIDATION_REPORT.md.

Kept as a script rather than hand-typed numbers so the report can never drift from
the artifacts it cites (the house "point, don't copy" rule).

    scripts/jcz_oracle/summarize.py measurement/jcz_oracle_20260803
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_diff import REAL  # noqa: E402


def main(argv) -> int:
    d = Path(argv[1] if len(argv) > 1 else "measurement/jcz_oracle_20260803")
    legs = []
    for p in sorted(d.glob("*.json")):
        o = json.loads(p.read_text())
        legs.append((p.stem, o))

    classes = sorted({c for _, o in legs for c in o["totals"]},
                     key=lambda c: (c in REAL, c))

    print("| divergence class | " + " | ".join(n.split("_", 1)[0] for n, _ in legs) + " |")
    print("|---|" + "---|" * len(legs))
    for c in classes:
        tag = " **(REAL)**" if c in REAL else ""
        cells = " | ".join(str(o["totals"].get(c, 0)) for _, o in legs)
        print(f"| `{c}`{tag} | {cells} |")

    print()
    print("| leg | profile | policy | R9 | games | terminal scores agree | unclassified |")
    print("|---|---|---|---|---|---|---|")
    for n, o in legs:
        sa = o["score_agreement"]
        print(f"| {n} | {o['profile']} | {o.get('policy','record')} | "
              f"{'on' if o['r9'] else 'off'} | {o['n_games']} | "
              f"**{sa['agree']}/{sa['compared']}** | {o['real'] or 'none'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
