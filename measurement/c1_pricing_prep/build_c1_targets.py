#!/usr/bin/env python3
"""C1 OUTCOME PRICING — freeze the target ply set. OUTCOME-BLIND BY CONSTRUCTION.

Inputs, both already on disk and already adjudicated:

  * `../microgates_20260828/MICROGATES.json` -> `G2.plies` — one record per crux
    ply carrying `rollout_argmax` (the tier1-rollout re-ranker's pick, the argmax
    of mover-signed mean terminal margin over the microgates' M=16 CRN worlds),
    `counterfactual_action` (the banked PRODUCTION CHAMPION's pick), `arm_values`
    and `spread_pts`;
  * `../e4_ply_pricing_20260827/targets.jsonl` — the banked 290 decision rows,
    read ONLY for the decision fields the runner needs (`k`, `phase`, `actor`,
    `n_plies`, `ply_frac`) — never for an outcome.

⚠️ NEITHER INPUT CONTAINS A CONTINUATION OUTCOME FOR THESE ARMS. `arm_values`
are the microgates' own rollout margins; they are the SELECTION statistic (the
thing whose winner's curse this instrument exists to de-bias), never a price.
`selftest_c1.py::test_selector_reads_no_outcome_field` asserts at code level
that this file does not mention any realized-outcome field name.

The output rows are written in `continue_plies.py`'s OWN target schema, with the
arm slots remapped:

      arm_owner  <-  rollout_argmax          (THE C1 PICK)
      arm_cf     <-  counterfactual_action   (THE CHAMPION PICK)

so `delta_pts_mover` emitted by the frozen runner reads, unchanged and
mover-signed, as **C1-pick minus champion-pick**. See READ_RULE.md §1 — that
remap is the single most misreadable thing in this instrument.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# --- frozen constants (DESIGN.md §1.3; asserted by selftest_c1.py) ---------- #
WORLD_BASE = 16                 # microgates owned 0..15; e4_continuation 0..7
M_BASE = {                      # base-pass world COUNT per stratum
    "farm_capture": 32,         # PRIMARY, and the cheapest stratum by 10x
    "invasion": 16,
    "defense": 8,
    "control": 8,
}
EXTENSIONS = [                  # elasticity blocks, in trigger order (DESIGN §6)
    {"block": "E1", "strata": ["farm_capture"], "add": 32},
    {"block": "E2", "strata": ["invasion"], "add": 16},
    {"block": "E3", "strata": ["defense", "control"], "add": 8},
]
PROFILE = "fixed_v1"            # the single rules epoch admitted (DESIGN §1.2)
STRATA = ("farm_capture", "invasion", "defense", "control")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--microgates",
                    default=str(REPO / "measurement" / "microgates_20260828"
                               / "MICROGATES.json"))
    ap.add_argument("--banked",
                    default=str(REPO / "measurement" / "e4_ply_pricing_20260827"
                               / "targets.jsonl"))
    ap.add_argument("--out", default=str(HERE / "targets_c1.jsonl"))
    ap.add_argument("--meta", default=str(HERE / "TARGETS_C1.json"))
    args = ap.parse_args()

    mg = json.loads(Path(args.microgates).read_text())
    plies = mg["G2"]["plies"]
    banked = {}
    for line in Path(args.banked).open():
        r = json.loads(line)
        banked[(r["game"], int(r["ply"]))] = r

    excluded = collections.Counter()
    rows = []
    for p in plies:
        key = (p["game"], int(p["ply"]))
        if p["profile"] != PROFILE:
            excluded[f"profile:{p['profile']}"] += 1
            continue
        if p["stratum"] not in STRATA:
            excluded[f"stratum:{p['stratum']}"] += 1
            continue
        c1, champ = int(p["rollout_argmax"]), int(p["counterfactual_action"])
        if c1 == champ:
            # The two arms would be byte-identical, so the paired price is
            # EXACTLY zero with no compute. Dropped from the run, counted here,
            # and folded back analytically as the policy-level price
            # (DESIGN.md §4.3). This is arithmetic, not a filter.
            excluded["agree:zero_by_construction"] += 1
            continue
        b = banked[key]
        av = p["arm_values"]
        m = M_BASE[p["stratum"]]
        ext = []
        lo = WORLD_BASE + m
        for e in EXTENSIONS:
            if p["stratum"] in e["strata"]:
                ext.append({"block": e["block"], "world_lo": lo,
                            "world_hi": lo + e["add"]})
                lo += e["add"]
        rows.append({
            # --- fields `continue_plies.py` reads (its schema, unchanged) ---
            "game": p["game"],
            "profile": p["profile"],
            "stratum": p["stratum"],
            "ply": int(p["ply"]),
            "k": b["k"],
            "phase": b["phase"],
            "actor": int(b["actor"]),
            "played_action": c1,             # ⚠️ arm_owner slot := THE C1 PICK
            "counterfactual_action": champ,  # ⚠️ arm_cf    slot := CHAMPION PICK
            "n_plies": b["n_plies"],
            "ply_frac": b["ply_frac"],
            # --- C1 fields; the runner ignores them, the adjudicator asserts ---
            "arm_map": {"arm_owner": "c1_rollout_argmax",
                        "arm_cf": "production_champion_pick"},
            "c1_action": c1,
            "champ_action": champ,
            "owner_action": int(p["played_action"]),
            "n_arms_microgate": int(p["n_arms"]),
            "n_worlds_microgate": int(p["n_worlds"]),
            "insample_gap_pts": round(av[str(c1)] - av[str(champ)], 3),
            "spread_pts": p["spread_pts"],
            "n_remaining_plies": int(b["n_plies"]) - int(p["ply"]),
            "m_worlds_base": m,
            "world_lo_base": WORLD_BASE,
            "world_hi_base": WORLD_BASE + m,
            "extension_blocks": ext,
        })

    rows.sort(key=lambda r: (r["stratum"], r["game"], r["ply"]))
    with Path(args.out).open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    def blk(sel, m):
        return sum(r["n_remaining_plies"] for r in sel) * 2 * m

    meta = {
        "schema": "carcassonne-c1-outcome-pricing-targets/v1",
        "built_from": {"microgates": args.microgates, "banked_rows": args.banked},
        "constants": {"WORLD_BASE": WORLD_BASE, "M_BASE": M_BASE,
                      "EXTENSIONS": EXTENSIONS, "PROFILE": PROFILE},
        "n_target_plies": len(rows),
        "n_games": len({r["game"] for r in rows}),
        "excluded": dict(excluded),
        "by_stratum": {},
        "totals": {},
    }
    for s in STRATA:
        sel = [r for r in rows if r["stratum"] == s]
        if not sel:
            continue
        meta["by_stratum"][s] = {
            "n_plies": len(sel),
            "n_games": len({r["game"] for r in sel}),
            "m_worlds_base": M_BASE[s],
            "sum_remaining_plies": sum(r["n_remaining_plies"] for r in sel),
            "mean_remaining_plies": round(
                sum(r["n_remaining_plies"] for r in sel) / len(sel), 1),
            "mean_insample_gap_pts": round(
                sum(r["insample_gap_pts"] for r in sel) / len(sel), 3),
            "n_units_base": len(sel) * M_BASE[s],
            "continuation_plies_base": blk(sel, M_BASE[s]),
            "k_min": min(r["k"] for r in sel),
            "k_median": sorted(r["k"] for r in sel)[len(sel) // 2],
            "n_exact_solvable_k_le_4": sum(1 for r in sel if r["k"] <= 4),
            "n_near_tie_gap_lt_0p5": sum(1 for r in sel
                                         if abs(r["insample_gap_pts"]) < 0.5),
            "extension_continuation_plies": {
                e["block"]: blk(sel, e["add"]) for e in EXTENSIONS
                if s in e["strata"]},
        }
    contested = [r for r in rows if r["stratum"] in ("invasion", "farm_capture")]
    meta["totals"] = {
        "continuation_plies_base": sum(v["continuation_plies_base"]
                                       for v in meta["by_stratum"].values()),
        "n_units_base": sum(v["n_units_base"] for v in meta["by_stratum"].values()),
        "contested_n_plies": len(contested),
        "contested_n_games": len({r["game"] for r in contested}),
        "contested_mean_insample_gap_pts": round(
            sum(r["insample_gap_pts"] for r in contested) / len(contested), 3),
        "all_mean_insample_gap_pts": round(
            sum(r["insample_gap_pts"] for r in rows) / len(rows), 3),
    }
    Path(args.meta).write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
