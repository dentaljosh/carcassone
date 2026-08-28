#!/usr/bin/env python3
"""E4 CONTINUATION PRICING — freeze the target ply set.

Input is the BANKED row set of the completed E4 ply-pricing run
(`/mnt/c/carc-shared/e4_ply_pricing_20260827/rows_*.jsonl`, 290 rows). This
selector reads ONLY those rows' *decision* fields — stratum, ply, K, actor,
phase, the played action, the champion's counterfactual action and the
agreement flag. It reads NO outcome field: `test_continuation.py::
test_selector_reads_no_outcome_field` asserts at code level that this file
mentions none of `winner` / `final_scores` / `scores` / `margin` /
`realized` / `delta_pts_mover` / `price_`, so the set is outcome-blind BY
CONSTRUCTION rather than by discipline.

THE SET:
  * every DIVERGENT ply (`counterfactual_agrees is False`) in the strata
    `invasion`, `defense`, `farm_capture` — the residual the agreement
    gradient leaves unexplained;
  * a decile-matched random sample of `N_CONTROL` DIVERGENT `control` plies —
    the essential baseline. Without it a nonzero invasion-divergence price is
    uninterpretable: it could just be what ANY champion-divergence is worth.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import statistics
from pathlib import Path

# --- pre-registered constants (frozen; see PREREG.md) ----------------------- #
CONTROL_SEED = 20260828
N_CONTROL = 30
MATCH_STRATUM = "invasion"          # the distribution the controls are matched TO
FULL_STRATA = ("invasion", "defense", "farm_capture")

CARRY = ("game", "profile", "stratum", "ply", "k", "phase", "actor",
         "played_action", "n_legal", "n_plies", "ply_frac", "notes",
         "counterfactual_action", "counterfactual_agrees",
         "counterfactual_flags", "execution")


def decile(row) -> int:
    """The ply-fraction decile a ply sits in. 0.9014 -> 9; 1.0 would clamp to 9."""
    return min(9, int(row["ply_frac"] * 10))


def largest_remainder(weights: dict[int, float], total: int) -> dict[int, int]:
    """Apportion `total` over `weights` by largest remainder; ties -> LOWER decile."""
    s = sum(weights.values())
    exact = {d: total * w / s for d, w in weights.items()}
    quota = {d: int(v) for d, v in exact.items()}
    left = total - sum(quota.values())
    order = sorted(exact, key=lambda d: (-(exact[d] - quota[d]), d))
    for d in order[:left]:
        quota[d] += 1
    return quota


def match_controls(pool, target_rows, n, seed):
    """Sample `n` controls whose ply_frac-decile histogram matches `target_rows`.

    1. quota per decile = largest-remainder apportionment of `n` over the target
       set's decile histogram (ties to the lower decile);
    2. per decile in ASCENDING order take `min(quota, available)`, sampled with
       `random.Random(seed)` from that decile's candidates sorted by (game, ply);
    3. any SHORTFALL (a decile the pool cannot fill) is filled from the remaining
       candidates ordered by `|ply_frac - mean target ply_frac|` ascending, then
       (game, ply) — i.e. the fill is pulled toward the target distribution's
       centre rather than taken arbitrarily.

    Deterministic given (pool, target_rows, n, seed).
    """
    hist = collections.Counter(decile(r) for r in target_rows)
    quota = largest_remainder({d: c for d, c in hist.items()}, n)
    by_dec = collections.defaultdict(list)
    for r in pool:
        by_dec[decile(r)].append(r)
    for d in by_dec:
        by_dec[d].sort(key=lambda r: (r["game"], r["ply"]))

    rng = random.Random(seed)
    chosen, shortfall = [], 0
    for d in sorted(quota):
        want = quota[d]
        have = by_dec.get(d, [])
        take = min(want, len(have))
        chosen.extend(rng.sample(have, take) if take < len(have) else list(have))
        shortfall += want - take
    if shortfall:
        mu = statistics.mean(r["ply_frac"] for r in target_rows)
        picked = {(r["game"], r["ply"]) for r in chosen}
        rest = sorted((r for r in pool if (r["game"], r["ply"]) not in picked),
                      key=lambda r: (abs(r["ply_frac"] - mu), r["game"], r["ply"]))
        chosen.extend(rest[:shortfall])
    chosen.sort(key=lambda r: (r["game"], r["ply"]))
    return chosen, quota, shortfall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True,
                    help="glob dir of the banked e4_ply_pricing rows_*.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", required=True)
    args = ap.parse_args()

    src = sorted(Path(args.rows).glob("rows_*.jsonl"))
    if not src:
        raise SystemExit(f"no rows_*.jsonl under {args.rows}")
    banked = []
    for f in src:
        for line in f.open():
            banked.append(json.loads(line))
    if len({(r["game"], r["ply"]) for r in banked}) != len(banked):
        raise SystemExit("banked rows are not unique on (game, ply)")

    div = [r for r in banked if r.get("counterfactual_agrees") is False]
    for r in div:
        if (r.get("counterfactual_flags") or {}).get("forced"):
            raise SystemExit(f"forced ply in the divergent set: {r['game']} {r['ply']}")
        if r.get("counterfactual_action") is None:
            raise SystemExit(f"divergent row with no counterfactual action: {r}")
        if int(r["counterfactual_action"]) == int(r["played_action"]):
            raise SystemExit(f"agreement flag disagrees with the actions: {r}")

    targets = [r for r in div if r["stratum"] in FULL_STRATA]
    pool = [r for r in div if r["stratum"] == "control"]
    match_to = [r for r in div if r["stratum"] == MATCH_STRATUM]
    ctl, quota, shortfall = match_controls(pool, match_to, N_CONTROL, CONTROL_SEED)
    targets.extend(ctl)
    targets.sort(key=lambda r: (r["game"], r["ply"]))

    with open(args.out, "w") as fh:
        for r in targets:
            fh.write(json.dumps({k: r[k] for k in CARRY if k in r}) + "\n")

    def hist(rows):
        return {str(d): c for d, c in
                sorted(collections.Counter(decile(r) for r in rows).items())}

    def block(rows):
        return {"n": len(rows), "n_games": len({r["game"] for r in rows}),
                "mean_ply_frac": round(statistics.mean(r["ply_frac"] for r in rows), 4),
                "mean_remaining_plies": round(
                    statistics.mean(r["n_plies"] - r["ply"] for r in rows), 2),
                "sum_remaining_plies": sum(r["n_plies"] - r["ply"] for r in rows),
                "k_min": min(r["k"] for r in rows), "k_max": max(r["k"] for r in rows),
                "deciles": hist(rows),
                "profiles": dict(collections.Counter(r["profile"] for r in rows)),
                "phases": dict(collections.Counter(r["phase"] for r in rows)),
                "actors": dict(collections.Counter(str(r["actor"]) for r in rows))}

    meta = {
        "built_from": [str(p) for p in src],
        "n_banked_rows": len(banked),
        "n_divergent_total": len(div),
        "constants": {"CONTROL_SEED": CONTROL_SEED, "N_CONTROL": N_CONTROL,
                      "MATCH_STRATUM": MATCH_STRATUM, "FULL_STRATA": list(FULL_STRATA)},
        "control_pool_n": len(pool),
        "control_pool_deciles": hist(pool),
        "control_quota": {str(d): q for d, q in sorted(quota.items())},
        "control_shortfall_filled_by_nearest": shortfall,
        "by_stratum": {s: block([r for r in targets if r["stratum"] == s])
                       for s in sorted({r["stratum"] for r in targets})},
        "total": block(targets),
    }
    Path(args.meta).write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
