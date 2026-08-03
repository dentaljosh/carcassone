#!/usr/bin/env python3
"""F9 Gate A1-a — read a wall-probe corpus and print the W2-vs-W3 decision inputs.

Input: a `gen_fair_distill` output dir carrying `sentinel/seed_*.json` shards (the
W4 sentinel, default on). Output: per-face event rates with Wilson CIs, the
re-priced event rates for every candidate geometry, near-fatal exposure both ways,
and the A2 cloister numbers under champion play.

    scripts/f9/analyze_wall_probe.py DIR [DIR ...] [--margin 2] [--json OUT.json]

WHAT THE SPEC ASKS THIS TO DECIDE (docs/F9_BUILD_SPEC_20260802.md §A1, Gate A1-a):

  * **zero sentinel events ⇒ W2** (recentre only) is adopted as the F9 fixed-rules
    geometry, and "wall-free under champion play" becomes a MEASURED statement
    about the exact policy the cells run;
  * **any sentinel event ⇒ W3** (runtime board size) is required, and its funding
    gate is a leaf µs/leaf bench BEFORE committing — with the grid sized by the
    MEASURED span, not the theoretical 143.

⚠️ TWO READING RULES, both from the spec.

1. **The probe should be generated on the UNCENSORED grid.** A trajectory played
   at row 6 has already been bent by the wall — its denial count is what the wall
   let it be, not what champion play wanted. Generating at `centered18` (where the
   measured denial rate is 0) and re-pricing row 6 from it is the honest direction.
   The re-pricing is exact for the trajectory OBSERVED; it is not a claim about
   what would have been played on a differently-binding grid.

2. **W2 moves risk, it does not only remove it** (spec T2). Recentring takes
   downward headroom from 28 rows to 16, so it removes a SILENT face (denial) and
   makes a FATAL one (last-row, where the flat and object scorers additionally
   disagree) materially more reachable. So `row_last` / `col_last` / near-fatal
   exposure are reported for every candidate geometry, not only the denial count.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai import wall_sentinel as ws  # noqa: E402

# The geometries the decision is between. (start_row, start_col, rows, cols, label)
CANDIDATES = [
    (6, 15, 35, 35, "engine6 / 35x35  [W1 control — the engine of record]"),
    (18, 15, 35, 35, "centered18 / 35x35  [W2 — recentre only, free, app-shipped]"),
    (22, 22, 45, 45, "centered22 / 45x45  [W3 candidate — 1.65x cells]"),
    (27, 27, 55, 55, "centered27 / 55x55  [W3 candidate — 2.5x cells]"),
    (71, 71, 143, 143, "centered71 / 143x143  [W3 provable — 16.7x cells]"),
]

FACES = [
    ("drops_row_neg", "wall denial, row<0        (silent; the production face)"),
    ("drops_row_over", "wall denial, row>max      (silent)"),
    ("drops_col_neg", "wall denial, col<0        (silent)"),
    ("drops_col_over", "wall denial, col>max      (silent)"),
    ("row_wrap_plies", "negative-row wrap         (silent WRONG READ: board[-1])"),
    ("col_last_plies", "col-34 placement          (FATAL: IndexError, farm path)"),
    ("row_last_plies", "last-row placement        (FATAL: count_final_scores)"),
    ("window_overflow", "WindowOverflowError       (FATAL: 25x25 window, board-size-proof)"),
]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval — correct at k=0, which is the case that matters here
    (a normal-approximation CI on 0/400 is [0,0], which would read as proof)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load(dirs) -> list[dict]:
    recs = []
    for d in dirs:
        sd = Path(d) / "sentinel"
        if not sd.is_dir():
            print(f"  ! {d}: no sentinel/ dir (was the probe run with --no-sentinel?)")
            continue
        for jf in sorted(sd.glob("seed_*.json")):
            try:
                recs.append(json.loads(jf.read_text()))
            except Exception as e:
                print(f"  ! unreadable {jf}: {e}")
    return recs


def main() -> int:
    ap = argparse.ArgumentParser(prog="analyze_wall_probe")
    ap.add_argument("dirs", nargs="+", help="gen_fair_distill output dir(s)")
    ap.add_argument("--margin", type=int, default=ws.NEAR_FATAL_MARGIN,
                    help="rows/cols from a fatal face that count as near-fatal exposure")
    ap.add_argument("--json", type=str, default=None, help="also write the report as json")
    args = ap.parse_args()

    recs = load(args.dirs)
    n = len(recs)
    if n == 0:
        raise SystemExit("no sentinel shards found")
    profiles = sorted({r.get("profile", "?") for r in recs})
    agg = ws.aggregate(recs)

    print(f"F9 A1-a WALL PROBE — {n} champion-play games, profile(s) {profiles}")
    print(f"  DESCRIPTIVE ONLY: throwaway seeds, no band claimed, no elo, no results.csv row.")
    print(f"  aborted {agg['games_aborted']}  |  any sentinel event "
          f"{agg['games_any_event']}/{n}\n")

    print("AS PLAYED — per-face event rates (games with >=1 event; Wilson 95% CI)")
    print(f"  {'face':<58} {'games':>6} {'rate':>8}  {'95% CI':>16}   {'events':>7}")
    for key, label in FACES:
        g = agg.get(f"games_with_{key}", 0)
        lo, hi = wilson(g, n)
        print(f"  {label:<58} {g:>6} {g/n:>7.2%}  [{lo:>6.2%},{hi:>6.2%}]   "
              f"{agg.get(key, 0):>7}")

    print(f"\nSPAN (relative to the start tile, over all {n} games)")
    print(f"  rows [{agg['rel_min_row']:+d}, {agg['rel_max_row']:+d}]   "
          f"cols [{agg['rel_min_col']:+d}, {agg['rel_max_col']:+d}]   "
          f"=> needs {agg['rel_max_row']-agg['rel_min_row']+1} rows x "
          f"{agg['rel_max_col']-agg['rel_min_col']+1} cols")
    print(f"  closest approach: row-0 face {agg['min_dist_row_zero']}   "
          f"last-row face {agg['min_dist_row_last']}   "
          f"last-col face {agg['min_dist_col_last']}  (0 = reached it)")

    print(f"\nRE-PRICED — the SAME {n} trajectories drawn on each candidate grid")
    print("  (exact for the observed play; a grid that binds differently would have")
    print("   produced different play — see the module docstring, reading rule 1)")
    per_geom = {}
    for srow, scol, rows, cols, label in CANDIDATES:
        gp = {"games_any_event": 0, "games_not_fitting": 0}
        for k, _ in FACES:
            gp[k] = 0
            gp[f"games_with_{k}"] = 0
        near_row = near_col = 0
        for r in recs:
            rp = ws.reprice(r.get("rel_coords", []), srow, scol, rows, cols)
            if not rp["fits"]:
                gp["games_not_fitting"] += 1
            if rp["any_event"]:
                gp["games_any_event"] += 1
            for k, _ in FACES:
                if k == "window_overflow":
                    continue
                gp[k] += rp.get(k, 0)
                if rp.get(k, 0):
                    gp[f"games_with_{k}"] += 1
            # near-fatal exposure on THIS grid, from the relative span
            if (rows - 1) - (srow + r.get("rel_max_row", 0)) <= args.margin:
                near_row += 1
            if (cols - 1) - (scol + r.get("rel_max_col", 0)) <= args.margin:
                near_col += 1
        gp["near_fatal_row_games"] = near_row
        gp["near_fatal_col_games"] = near_col
        per_geom[label] = gp
        lo, hi = wilson(gp["games_any_event"], n)
        flag = "CLEAN" if gp["games_any_event"] == 0 else "EVENTS"
        print(f"\n  {label}")
        print(f"    any event: {gp['games_any_event']}/{n} = {gp['games_any_event']/n:.2%} "
              f"[{lo:.2%},{hi:.2%}]   -> {flag}")
        print(f"    denials  row<0 {gp['drops_row_neg']:>6}  row>max {gp['drops_row_over']:>6}  "
              f"col<0 {gp['drops_col_neg']:>6}  col>max {gp['drops_col_over']:>6}")
        print(f"    fatal    col-last {gp['col_last_plies']:>5} ({gp['games_with_col_last_plies']} games)   "
              f"row-last {gp['row_last_plies']:>5} ({gp['games_with_row_last_plies']} games)   "
              f"row-wrap {gp['row_wrap_plies']:>5}")
        print(f"    near-fatal (<={args.margin}): {near_row} games near the last row, "
              f"{near_col} near the last col")
        if gp["games_not_fitting"]:
            print(f"    ⚠️  {gp['games_not_fitting']} games do not FIT this grid at all")

    print("\nA2 — CLOISTER ECONOMY UNDER CHAMPION PLAY (audit R1 re-run at strength)")
    print(f"  cloister completions          {agg['cloister_completions']:>6}  "
          f"({agg['cloister_completions']/n:.3f}/game)")
    print(f"  completion DEFERRALS (missed) {agg['cloister_deferrals']:>6}  "
          f"({agg['cloister_deferrals']/n:.3f}/game, "
          f"{agg['games_with_cloister_deferrals']}/{n} games)")
    print(f"  monks PINNED at terminal      {agg['monk_pins_terminal']:>6}  "
          f"({agg['monk_pins_terminal']/n:.3f}/game, "
          f"{agg['games_with_monk_pins_terminal']}/{n} games)")
    print("  ^ this is what R2 is worth: a permanent -1 on a supply of 7, invisible")
    print("    to every score-based check (the points still arrive at final scoring).")

    print("\nDECISION (spec Gate A1-a)")
    w2 = per_geom[CANDIDATES[1][4]]
    if w2["games_any_event"] == 0 and agg["window_overflow"] == 0:
        print("  W2 is CLEAN on this corpus: zero sentinel events at start row 18.")
        print("  -> the spec's branch is 'W2 adopted as the F9 fixed-rules geometry'.")
        print("  Report the CI as a BOUND, never as 'zero' — and note that W2 is a")
        print("  MITIGATION whose denial rate is policy-dependent, so the claim is")
        print("  about THIS policy, carried in every manifest.")
    else:
        print("  W2 shows sentinel events on this corpus -> W3 is required (spec A1).")
        print("  Funding gate BEFORE committing: a flat_base_score µs/leaf bench at")
        print("  35x35 vs the candidate size on the G2 corpus. Size the grid by the")
        print(f"  MEASURED span above ({agg['rel_max_row']-agg['rel_min_row']+1} x "
              f"{agg['rel_max_col']-agg['rel_min_col']+1}), not the theoretical 143.")
    if agg["window_overflow"]:
        print(f"  ⚠️  {agg['window_overflow']} WindowOverflowError(s): NO board change fixes")
        print("      this — the 25x25 centroid window is a representation cap (J4).")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"n_games": n, "profiles": profiles, "as_played": agg,
             "repriced": per_geom, "near_fatal_margin": args.margin}, indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
