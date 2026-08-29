#!/usr/bin/env python3
"""C1 OUTCOME PRICING — the EXACT-SOLVER BONUS LEG. Never a verdict. n is tiny.

At a ply with K <= 4 unseen tiles the rust `carc_core::endgame` marginalized
solver returns the TRUE expectiminimax value of every child of the root in one
call (`child_values`), so BOTH arms of this instrument are priced exactly by a
SINGLE solve, with no judge, no search score and no sampling:

    exact_delta_pts_mover = +-( child_values[c1_action] - child_values[champ_action] )

⚠️⚠️ **THIS IS A DIFFERENT ESTIMAND FROM THE CONTINUATION PRICE, AND A SIGN
DISAGREEMENT IS NOT A BUG.** The continuation price is the value of an arm
*under subsequent production-champion play by both seats*; the exact price is
its value *under optimal play by both seats*. A move can be worth more against
the champion than against a perfect opponent and vice versa. This leg is
therefore reported ALONE, is never pooled with the continuation price, never
voids it, and cannot fire any pre-registered branch (DESIGN.md §4.4).

Pre-registered coverage, measured at freeze time: **4 of the 188 target plies
have K <= 4** (1 `farm_capture`, 1 `invasion`, 2 `defense`, 0 `control`), and 0
have K == 5. That is the whole leg. It exists because judge-free gold at four
positions is worth its ~20 minutes, not because it can settle anything.

The K cut is inherited verbatim from `../e4_ply_pricing_20260827/MODE_CUT.json`
(`k_marginalized_max = 4`, `per_solve_cpu_cap_s = 1800`, sized from the measured
rust ladder by its TAIL: ~290 s at K=4 with a heavy tail, ~10-30x per K).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRICING = REPO / "measurement" / "e4_ply_pricing_20260827"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(PRICING))
ARCHIVES = REPO / "measurement" / "e4_games"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default=str(HERE / "targets_c1.jsonl"))
    ap.add_argument("--mode-cut", default=str(PRICING / "MODE_CUT.json"))
    ap.add_argument("--out", default=str(HERE / "EXACT_LEG.json"))
    ap.add_argument("--budget", type=int, default=4_000_000,
                    # C1-D3: 0 is NOT unlimited — the rust core treats it as a
                    # zero-node budget and returns BudgetExceeded instantly.
                    # 4_000_000 is the pyo3 default the e4 pricing solved K<=5 on.
                    help="node budget passed to solve_endgame (was wrongly 0-as-unlimited, "
                         "the RLIMIT_CPU cap is the real bound)")
    ap.add_argument("--cpu-cap-secs", type=int, default=None)
    ap.add_argument("--mem-cap-gb", type=float, default=8.0)
    args = ap.parse_args()

    cut = json.loads(Path(args.mode_cut).read_text())
    k_max = int(cut["k_marginalized_max"])
    cap_s = args.cpu_cap_secs or int(cut["per_solve_cpu_cap_s"])

    rows = [json.loads(l) for l in Path(args.targets).open()]
    sel = [r for r in rows if int(r["k"]) <= k_max]
    profiles = {r["profile"] for r in sel}
    if len(profiles) > 1:
        raise SystemExit(f"R9 is import-latched: one process per profile, "
                         f"got {sorted(profiles)}")
    if not sel:
        Path(args.out).write_text(json.dumps(
            {"k_marginalized_max": k_max, "n_plies": 0,
             "note": "no target ply is exactly solvable at this cut"}, indent=1))
        return
    profile = profiles.pop()

    from analyzer.ev_loss import prepare_env, resolve_profile_name
    env = prepare_env(profile)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    import price_plies                                       # the frozen solver

    out_rows, t0 = [], time.time()
    for r in sel:
        arc = json.loads((ARCHIVES / r["game"]).read_text())
        resolved = resolve_profile_name(arc)
        if resolved != r["profile"]:
            raise SystemExit(f"profile drift on {r['game']}: {resolved!r} "
                             f"vs {r['profile']!r}")
        res = price_plies.solve_isolated(
            {"mode": "exact_marginalized", "profile": resolved,
             "deck_seed": int(arc["deck_seed"]),
             "actions": [int(x) for x in arc["actions"]],
             "ply": int(r["ply"]), "budget": args.budget},
            args.mem_cap_gb, cap_s)
        rec = {"game": r["game"], "ply": r["ply"], "stratum": r["stratum"],
               "k": r["k"], "actor": int(r["actor"]),
               "c1_action": int(r["c1_action"]),
               "champ_action": int(r["champ_action"]),
               "insample_gap_pts": r["insample_gap_pts"],
               "solve_status": res.get("status")}
        cv = {int(k): v for k, v in (res.get("child_values") or {}).items()}
        if res.get("status") == "OK" and rec["c1_action"] in cv \
                and rec["champ_action"] in cv:
            d = cv[rec["c1_action"]] - cv[rec["champ_action"]]
            rec.update({
                "exact_value_c1": cv[rec["c1_action"]],
                "exact_value_champ": cv[rec["champ_action"]],
                "exact_delta_pts_mover": d if int(r["actor"]) == 0 else -d,
                "root_optimal_actions": res.get("optimal_actions"),
                "c1_is_optimal": rec["c1_action"] in (res.get("optimal_actions") or []),
                "champ_is_optimal": rec["champ_action"] in (res.get("optimal_actions") or []),
                "nodes": res.get("nodes"), "solve_s": res.get("solve_s"),
            })
        else:
            rec["detail"] = {k: res.get(k) for k in
                             ("detail", "kill_reason", "elapsed_s")}
        out_rows.append(rec)

    priced = [r for r in out_rows if "exact_delta_pts_mover" in r]
    Path(args.out).write_text(json.dumps({
        "schema": "carcassonne-c1-outcome-pricing-exact-leg/v1",
        "estimand": "value of the arm under OPTIMAL play by both seats — NOT "
                    "the continuation estimand (production-champion play). "
                    "Reported alone. Never pooled. Cannot fire a branch.",
        "k_marginalized_max": k_max, "per_solve_cpu_cap_s": cap_s,
        "profile": profile, "r9_env": env,
        "n_selected": len(sel), "n_priced": len(priced),
        "n_c1_optimal": sum(1 for r in priced if r.get("c1_is_optimal")),
        "n_champ_optimal": sum(1 for r in priced if r.get("champ_is_optimal")),
        "mean_exact_delta_pts_mover": (
            sum(r["exact_delta_pts_mover"] for r in priced) / len(priced)
            if priced else None),
        "elapsed_s": round(time.time() - t0, 1),
        "rows": out_rows,
    }, indent=1))
    print(json.dumps({"n_selected": len(sel), "n_priced": len(priced)}, indent=1))


if __name__ == "__main__":
    main()
