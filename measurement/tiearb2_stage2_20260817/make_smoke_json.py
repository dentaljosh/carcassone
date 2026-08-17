#!/usr/bin/env python
"""tiearb2 STAGE 2 PHASE B — aggregate the two boxes' smoke runs into SMOKE.json.

⚠️ THE SMOKE IS NOT A CELL AND CARRIES NO STRENGTH CLAIM. It reads exactly four
things off a handful of throwaway-band games and computes an ETA from them:

  * per-game wall clock, per cell, per box;
  * the REALIZED `phi` (fired tile plies per game), per cell — DESIGN §3's
    witness and `G-FIRE`'s floor, reported beside the offline prior **22.96**
    with DESIGN §2.1's two runtime-vs-corpus mismatches attached, because the
    offline rate ESTIMATES the runtime rate and does not equal it;
  * `ms_ratio_cand_over_opp`, per cell, against DESIGN §5's advance prediction of
    ≈ **1.1985** and the N4 trigger of **1.20**;
  * the pick-change rate.

⚠️ **THE FIELD-NAME TRAP**, restated wherever the number appears:
`champ_prefix_ms_per_move` **IS THE CANDIDATE SIDE** in `eval_fair_puct`
(the opposite of `eval_puct_priors`, confirmed at live lines 2361/2371/2389).
A read-out that swaps them inverts the cost verdict.

The ETA model is deliberately the dullest one that can be checked by hand:
per box and per cell, throughput = games / wall; the two boxes add; each cell is
800 games; the driver runs the two cells sequentially, so the totals add too.
It is only honest if each box's smoke was at FULL OCCUPANCY (n_games >= W) —
a smoke with fewer games than workers leaves slots idle and UNDER-states
capacity. That condition is checked and stamped, never assumed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PHI_OFFLINE_PRIOR = 22.96
PHI_FUNNEL = {"exact_tie_rate_on_tile_plies": 0.6598, "deduped_scoreable": 0.404}
MS_RATIO_PREDICTED = 1.1985
N4_TRIGGER = 1.20
N4_COST_NEUTRAL = 1.05
CELL_N = 800

MISMATCHES_VERBATIM = [
    "(i) The corpus predicate was evaluated on a REPLAYED board at the champion's "
    "seat. At runtime it is evaluated inside a live search on the candidate's "
    "seat. The board distribution is the same population; the *evaluation "
    "context* is not identical.",
    "(ii) The corpus `champ_picks` came from a FRESH search. CL-070 established "
    "that **reseeding alone flips picks**. => the offline firing rate "
    "**estimates** the runtime rate; it does not equal it.",
]


def read_cell(root: Path, sub: str, host: str) -> dict | None:
    d = root / f"{sub}_{host}"
    s = d / "summary.json"
    m = d / "manifest.json"
    w = d / ".wall_secs"
    if not s.exists():
        return None
    summ = json.loads(s.read_text())
    man = json.loads(m.read_text()) if m.exists() else {}
    wall = int(w.read_text().strip()) if w.exists() else None
    n = int(summ.get("n") or 0)
    champ_ms = summ.get("champ_prefix_ms_per_move")
    rung_ms = summ.get("rung_ms_per_move")
    return {
        "dir": str(d),
        "host": host,
        "n_games": n,
        "wall_secs": wall,
        "secs_per_game": (wall / n) if (wall and n) else None,
        # ⚠️ CANDIDATE / OPPONENT, spelled out so the trap cannot bite a reader.
        "champ_prefix_ms_per_move_IS_THE_CANDIDATE": champ_ms,
        "rung_ms_per_move_IS_THE_OPPONENT": rung_ms,
        "ms_ratio_cand_over_opp": (champ_ms / rung_ms) if (champ_ms and rung_ms) else None,
        "tiearb_phi": summ.get("tiearb_phi"),
        "tiearb_fired_plies_total": summ.get("tiearb_fired_plies_total"),
        "tiearb_tile_plies_total": summ.get("tiearb_tile_plies_total"),
        "tiearb_fire_rate_on_tile_plies": summ.get("tiearb_fire_rate_on_tile_plies"),
        "tiearb_pickchange_rate": summ.get("tiearb_pickchange_rate"),
        "tiearb_mean_arms": summ.get("tiearb_mean_arms"),
        "tiearb_playouts_total": summ.get("tiearb_playouts_total"),
        "tiearb_secs_per_game": summ.get("tiearb_secs_per_game"),
        "tiearb_games": summ.get("tiearb_games"),
        "tiearb_modes": summ.get("tiearb_modes"),
        "resolved_cand_tiearb_top_level": man.get("cand_tiearb"),
        "resolved_cand_tiearb_under_config": (man.get("config") or {}).get("cand_tiearb"),
        "cand_leaf_hash": (man.get("config") or {}).get("cand_leaf_hash"),
        "rust_toolchain": man.get("rust_toolchain"),
        "carc_rs_build": man.get("carc_rs_build"),
        "carc_rs_binary_sha": man.get("carc_rs_binary_sha"),
        "n_failed": summ.get("n_failed"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--share-root", default="/mnt/c/carc-shared/tiearb2_stage2_20260817_SMOKE")
    ap.add_argument("--arb", default="tiearb_ARB_B16J4_deploy11008")
    ap.add_argument("--rnd", default="tiearb_RND_B16J4_deploy11008")
    ap.add_argument("--local-host", default="Doctor")
    ap.add_argument("--laptop-host", default="laptop-wsl")
    ap.add_argument("--w-local", type=int, default=30)
    ap.add_argument("--w-laptop", type=int, default=22)
    ap.add_argument("--band", type=int, required=True)
    ap.add_argument("--out", default="measurement/tiearb2_stage2_20260817/SMOKE.json")
    a = ap.parse_args()

    root = Path(a.share_root)
    cells = {}
    for label, sub in (("ARB", a.arb), ("RND", a.rnd)):
        cells[label] = {
            "local": read_cell(root, sub, a.local_host),
            "laptop": read_cell(root, sub, a.laptop_host),
        }

    W = {"local": a.w_local, "laptop": a.w_laptop}
    eta = {}
    total = 0.0
    complete = True
    for label, per_box in cells.items():
        tput = 0.0
        detail = {}
        for box, c in per_box.items():
            if not c or not c["secs_per_game"]:
                complete = False
                detail[box] = None
                continue
            t = c["n_games"] / c["wall_secs"]
            full = c["n_games"] >= W[box]
            complete &= full
            detail[box] = {
                "games": c["n_games"], "wall_secs": c["wall_secs"],
                "secs_per_game_wallclock": round(c["secs_per_game"], 1),
                "games_per_sec": t,
                "worker_secs_per_game": round(c["wall_secs"] * W[box] / c["n_games"], 1),
                "workers": W[box],
                "full_occupancy": full,
                "note": None if full else
                        "n_games < W: idle slots, so this UNDER-states the box's capacity",
            }
            tput += t
        secs = (CELL_N / tput) if tput else None
        eta[label] = {
            "per_box": detail,
            "combined_games_per_sec": tput or None,
            "cell_n": CELL_N,
            "eta_secs": secs,
            "eta_hours": round(secs / 3600.0, 2) if secs else None,
        }
        if secs:
            total += secs
    eta["BOTH_CELLS"] = {
        "eta_secs": total or None,
        "eta_hours": round(total / 3600.0, 2) if total else None,
        "note": "the driver runs ARB then RND on each box, so the two cells' "
                "wall-clocks ADD; both boxes work each cell concurrently under "
                "--shared-claim.",
        "all_inputs_at_full_occupancy": complete,
    }

    out = {
        "kind": "tiearb2_stage2_phase_b_smoke",
        "⚠️": "NOT A CELL. Throwaway band, no results.csv row, no band claim, no "
              "strength statistic. Its ONLY jobs are the ETA and the first look "
              "at the realized firing rate and cost.",
        "throwaway_band": a.band,
        "cell_band_untouched": 132000000000,
        "production_knobs": {"k_dets": 8, "sims": 1376, "total_sims": 11008,
                             "exact_k": 2, "backend": "rust",
                             "rules_profile": "fixed_v1 + R9",
                             "paired": True,
                             "B": 16, "J": 4, "eps": 0.0,
                             "salt": "tiearb2-deploy-v1",
                             "only_difference_from_the_cell": "the game count"},
        "cells": cells,
        "phi_reference": {
            "offline_prior": PHI_OFFLINE_PRIOR,
            "funnel": PHI_FUNNEL,
            "G_FIRE_floor_per_game": 1.0,
            "design_2_1_mismatches_verbatim": MISMATCHES_VERBATIM,
        },
        "cost_reference": {
            "design_5_predicted_ms_ratio": MS_RATIO_PREDICTED,
            "N4_trigger": N4_TRIGGER,
            "cost_neutral_restored_at_or_below": N4_COST_NEUTRAL,
            "field_name_trap": "champ_prefix_ms_per_move IS THE CANDIDATE SIDE in "
                               "eval_fair_puct (live lines 2361/2371/2389); "
                               "rung_ms_per_move is the opponent. Swapping them "
                               "inverts the cost verdict.",
            "N4_is_a_downgrade_trigger_never_a_branch_input": True,
        },
        "eta_for_the_real_cells": eta,
    }
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out["eta_for_the_real_cells"], indent=2))
    print(f"[SMOKE.json] wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
