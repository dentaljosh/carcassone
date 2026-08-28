#!/usr/bin/env python3
"""Freeze the K histogram of the target set. Computes NO prices.

Run AFTER `build_targets.py` and BEFORE the blind commit — the pricing-mode cut in
`MODE_CUT.json` is pre-registered against this histogram.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    rows = [json.loads(l) for l in (HERE / "targets.jsonl").open()]
    k_all = Counter(r["k"] for r in rows)
    by_stratum = {s: Counter(r["k"] for r in rows if r["stratum"] == s)
                  for s in sorted({r["stratum"] for r in rows})}
    cuts = {str(c): {"n": sum(v for k, v in k_all.items() if k <= c),
                     "pct": round(100 * sum(v for k, v in k_all.items() if k <= c)
                                  / len(rows), 2),
                     "by_stratum": {s: sum(v for k, v in c2.items() if k <= c)
                                    for s, c2 in by_stratum.items()}}
            for c in (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 20)}
    out = {
        "n_rows": len(rows),
        "n_games": len({r["game"] for r in rows}),
        "by_stratum": {s: sum(c.values()) for s, c in by_stratum.items()},
        "by_profile": dict(Counter(r["profile"] for r in rows)),
        "k_definition": "len(state.deck) + (1 if state.next_tile is not None else 0)"
                        "  — the exact solver's convention",
        "k_min": min(k_all), "k_max": max(k_all),
        "k_histogram": dict(sorted(k_all.items())),
        "k_histogram_by_stratum": {s: dict(sorted(c.items()))
                                   for s, c in by_stratum.items()},
        "cumulative_at_cut": cuts,
    }
    (HERE / "k_histogram.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("k_histogram", "k_histogram_by_stratum")}, indent=1))


if __name__ == "__main__":
    main()
