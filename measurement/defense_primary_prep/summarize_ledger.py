#!/usr/bin/env python3
"""Read-only summary of the NEW-PLIES ledger. Computes NO prices.

Prints the accrual cut every way the PREREG declares a stratifier: corpus,
budget epoch, stratum. Used by the report and by the accrual check's `--verbose`.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def budget_epoch(row: dict) -> str:
    """champion_11k | champion_22k | carcasum_A_5000ms | carcasum_B_p103500.

    ⭐ The champion corpus is NOT one epoch. E-1a/E-1b's plies were played by an
    on-device champion at k8x1376 = 11008 — the SAME budget the counterfactual is
    pinned to. The 2026-09-01 pull's champion games were played at k16x1376 =
    22016, so their divergence has a BUDGET component E-1a's did not (PREREG
    §7.3). The epoch is read from the archive's own stamps, never a date.
    """
    era = row.get("archive_era") or {}
    if row["corpus"] != "champion_game":
        return "carcasum_B_p103500" if row["corpus"] == "carcasum_p103500" \
            else "carcasum_A_5000ms"
    k = era.get("played_k_dets_effective") or era.get("k_dets_effective")
    s = era.get("played_sims_effective") or era.get("sims_effective")
    if k and s:
        return f"champion_{int(k) * int(s) // 1000}k"
    return "champion_unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(HERE / "NEW_PLIES.jsonl"))
    args = ap.parse_args()
    rows = [json.loads(l) for l in Path(args.ledger).open() if l.strip()]
    div = [r for r in rows if r.get("divergent")]

    print(f"ledger rows {len(rows)}  divergent {len(div)}  games {len({r['game'] for r in rows})}")
    print("\n-- censused (all candidates) --")
    for k, n in sorted(Counter((r["corpus"], r["stratum"]) for r in rows).items()):
        print(f"  {k[0]:18s} {k[1]:13s} {n}")
    print("\n-- DIVERGENT --")
    for k, n in sorted(Counter((r["corpus"], r["stratum"]) for r in div).items()):
        print(f"  {k[0]:18s} {k[1]:13s} {n}")
    print("\n-- DEFENSE accrual by budget epoch --")
    d = [r for r in div if r["stratum"] == "defense"]
    for k, n in sorted(Counter(budget_epoch(r) for r in d).items()):
        print(f"  {k:22s} {n}")
    print(f"  TOTAL {len(d)}   game clusters {len({r['game'] for r in d})}")
    print("\n-- archive era stamps (per game) --")
    seen = {}
    for r in rows:
        seen.setdefault(r["game"], (r["corpus"], budget_epoch(r), r["archive_era"]))
    for g, (c, e, era) in sorted(seen.items()):
        print(f"  {g:30s} {c:18s} {e:22s} "
              f"sims={era.get('sims_effective')} k={era.get('k_dets_effective')} "
              f"played_sims={era.get('played_sims_effective')} "
              f"played_k={era.get('played_k_dets_effective')} "
              f"arb={era.get('tiearb_enabled')}/{era.get('tiearb_b')} "
              f"note={era.get('budget_note')}")


if __name__ == "__main__":
    main()
