#!/usr/bin/env python3
"""ITEM 6 (JCZ S3 cut) — build the S3 stratum and its matched control.

Pre-registration: measurement/jcz_mining_20260809/MINING_PREREG.md §3.3-3.4
names `merge_exposure_differs` as a covariate recorded but "explicitly NOT
tested by this design ... needs its own stratum and its own n ... The
covariate is recorded so a future cut is a query, not a re-run." This IS that
query: it is a small BUILD (fresh stratum + fresh matched control), not a
re-analysis of the banked STRATA.json / A / B / C strata.

DOES NOT MODIFY `scripts/measurement_infra/oracle_score_pilot.py` and does not
touch `governance/PRODUCTION.yaml`. Plays zero games. Mints no claim, no band.

MATCHING DISCIPLINE — mirrors `mine_disagreements.py` byte-for-byte, does not
invent a new scheme:
  - S3 TARGET predicate: `merge_exposure_differs == true` (STRAT_A/STRAT_B/POOL
    membership is IGNORED here — S3 is its own axis, orthogonal to the A/B/C
    partition, exactly as PREREG §3.4 describes it).
  - CONTROL predicate: `merge_exposure_differs == false`.
  - Deterministic sampling order: `order_key` = sha256-derived hash of
    `(deck_seed, champ_seat, ply)`, NEVER Python `hash()` — same function the
    A/B/C assign() step uses.
  - `jcz_seat` balanced to within +/-1 via `_pick_balanced` (>=1 position per
    game, same helper A/B use).
  - CONTROL match: `match_control()` UNCHANGED — nearest-neighbour on
    `our_leaf_gap`, WITHOUT replacement, EXACT on `MATCH_KEY = (ply_class,
    phase_bucket)` (the 2026-08-09 amendment that phase-matches the control so
    a late-deck-heavy target stratum cannot silently draw a mid-game control).
  - `phase_bucket` computed at the SAME `k_late=14` STRATA.json already
    confirmed (the pre-registered widening ladder did not fire on the full
    corpus run, so 14 stays canonical here too).
  - One scored position per game WITHIN THIS BUILD (S3 target games and
    control games are disjoint from each other via the shared `claimed` set
    threaded through `_pick_balanced` -> `match_control`). This build does NOT
    inherit the A/B/C run's claimed-games set: S3 is a fresh, orthogonal cut
    over the same CANDIDATES.jsonl pool, exactly as the prereg frames it
    ("its own stratum and its own n").

Usage:
    python3 scripts/jcz_mining/build_s3_stratum.py \\
        --candidates measurement/jcz_mining_20260809/mining/CANDIDATES.jsonl \\
        --out-dir    measurement/lever_menu_20260810/item6_s3 \\
        --k-late 14 --n-target 50
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "jcz_mining"))

import mine_disagreements as MD  # noqa: E402  (pure-stdlib module, no engine import)

SCHEMA = "carcassonne-lever-menu-item6-s3/v1"
PREREG = "measurement/jcz_mining_20260809/MINING_PREREG.md"
PLAN = "docs/LEVER_MENU_PLAN_20260810.md#4.6"
STRAT_S3, STRAT_S3_CONTROL = "ITEM6_S3", "ITEM6_S3_CONTROL"


def build(candidates: Path, out_dir: Path, *, k_late: int, n_target: int) -> dict:
    rows = MD.load_candidates(candidates)
    for r in rows:
        # Same field, same function, same k_late as the confirmed A/B/C STRATA.json
        # (the pre-registered widening ladder did not fire; 14 stays canonical).
        r["phase_bucket"] = MD.phase_bucket(r, k_late)

    s3_pool = [r for r in rows if bool(r.get("merge_exposure_differs"))]
    ctrl_pool = [r for r in rows if not bool(r.get("merge_exposure_differs"))]
    s3_pool.sort(key=MD.order_key)

    claimed: set = set()
    s3_rows = MD._pick_balanced(s3_pool, claimed, n_target)  # noqa: SLF001 (house fn, reused not re-implemented)
    for r in s3_rows:
        r["stratum"] = STRAT_S3

    ctrl_rows = MD.match_control(s3_rows, ctrl_pool, claimed)
    for r in ctrl_rows:
        r["stratum"] = STRAT_S3_CONTROL
        claimed.add(r["root_id"])

    def _profile(rs):
        return MD._profile(rs)  # noqa: SLF001

    strata = {
        "schema": SCHEMA,
        "prereg": PREREG,
        "plan": PLAN,
        "candidates": str(candidates),
        "k_late": int(k_late),
        "n_target": int(n_target),
        "s3_predicate": "merge_exposure_differs == true",
        "control_predicate": "merge_exposure_differs == false",
        "match_key": list(MD.MATCH_KEY),
        "match_nearest_on": "our_leaf_gap",
        "n_s3_pool_candidates": len(s3_pool),
        "n_s3_pool_distinct_games": len({r["root_id"] for r in s3_pool}),
        "n_control_pool_candidates": len(ctrl_pool),
        "n_control_pool_distinct_games": len({r["root_id"] for r in ctrl_pool}),
        "s3": _profile(s3_rows),
        "control": _profile(ctrl_rows),
        "control_match": {
            "n_targets": len(s3_rows),
            "n_matched": len(ctrl_rows),
            "truncated": bool(len(ctrl_rows) < len(s3_rows)),
            "truncated_by": int(len(s3_rows) - len(ctrl_rows)),
            "mean_gap_diff": MD._mean(r["match_gap_diff"] for r in ctrl_rows),  # noqa: SLF001
            "mean_gap_targets": MD._mean(r["our_leaf_gap"] for r in s3_rows),  # noqa: SLF001
            "mean_gap_control": MD._mean(r["our_leaf_gap"] for r in ctrl_rows),  # noqa: SLF001
        },
        "sizing_note": (
            f"n_target={n_target} per stratum. PREREG §4 gate is n>=25 scored or the "
            "stratum is INCONCLUSIVE BY CONSTRUCTION; its own re-open bar was n=74 for "
            "80% power at +1.4 pts/ply. n=50 sits BETWEEN the gate and the powered bar."
        ),
        "governance": "measurement only; governance/PRODUCTION.yaml untouched; "
                      "exploratory by construction; band 1.08e11 stays retired from "
                      "confirmatory use, this reuse does not un-retire it.",
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "STRATA_S3.json").write_text(json.dumps(strata, indent=2, sort_keys=False))

    s3_path = out_dir / "S3_stratum.jsonl"
    with s3_path.open("w") as fh:
        for r in sorted(s3_rows, key=lambda r: (str(r["root_id"]), str(r["rid"]))):
            fh.write(json.dumps(r) + "\n")

    ctrl_path = out_dir / "S3_control.jsonl"
    with ctrl_path.open("w") as fh:
        for r in sorted(ctrl_rows, key=lambda r: (str(r["root_id"]), str(r["rid"]))):
            fh.write(json.dumps(r) + "\n")

    print(f"[build_s3_stratum] pool: S3-eligible {len(s3_pool)} candidates / "
          f"{strata['n_s3_pool_distinct_games']} games; control-eligible "
          f"{len(ctrl_pool)} candidates / {strata['n_control_pool_distinct_games']} games")
    print(f"[build_s3_stratum] S3 n={len(s3_rows)} games={strata['s3']['n_distinct_games']} "
          f"{sorted(strata['s3']['by_ply_class_x_phase'].items())}")
    print(f"[build_s3_stratum] CONTROL n={len(ctrl_rows)} "
          f"games={strata['control']['n_distinct_games']} "
          f"{sorted(strata['control']['by_ply_class_x_phase'].items())}")
    print(f"[build_s3_stratum] mean our_leaf_gap: S3 "
          f"{strata['control_match']['mean_gap_targets']} vs control "
          f"{strata['control_match']['mean_gap_control']} "
          f"(mean matched diff {strata['control_match']['mean_gap_diff']})")
    print(f"[build_s3_stratum] wrote {s3_path}\n[build_s3_stratum] wrote {ctrl_path}\n"
          f"[build_s3_stratum] wrote {out_dir / 'STRATA_S3.json'}")
    return strata


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--candidates",
                    default=str(REPO / "measurement/jcz_mining_20260809/mining/CANDIDATES.jsonl"))
    ap.add_argument("--out-dir",
                    default=str(REPO / "measurement/lever_menu_20260810/item6_s3"))
    ap.add_argument("--k-late", type=int, default=14)
    ap.add_argument("--n-target", type=int, default=50)
    args = ap.parse_args(argv)
    build(Path(args.candidates), Path(args.out_dir),
          k_late=args.k_late, n_target=args.n_target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
