#!/usr/bin/env python3
"""ARBCOST addendum — per-GAME capture aggregation and the early-gate loss bound.

Combines the phase x B capture table (component i) with the phase-resolved fire
rates (component iii) into pts/GAME, with root-bootstrap CIs computed INSIDE the
replicate (phase means resampled, phi_p fixed).

Banked inputs only. Emits: CAPTURE_PER_GAME.json
"""
from __future__ import annotations

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOOT_REPS = 2000
BOOT_SEED = 20260819
PHASES = ["early", "mid", "late"]
B_LADDER = [1, 2, 4, 8, 16, 32, 64]


def main():
    cost = json.load(open(os.path.join(HERE, "COST_MODEL.json")))
    cens = cost["census"]
    kphi = cost["phi_calibration"]["K_PHI"]
    phi = {p: cens["by_phase"][p]["fired_plies_per_game_phi"] * kphi for p in PHASES}

    rows = [json.loads(l) for l in open(os.path.join(
        REPO, "measurement/tiearb_widening_20260817/shared_run_r4/verdicts/"
              "per_position_s1.jsonl"))]
    roots = sorted({r["root_id"] for r in rows})
    pos = {rt: i for i, rt in enumerate(roots)}
    g = len(roots)
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, g, size=(BOOT_REPS, g))

    def phase_reps(key, ph):
        s = np.zeros(g)
        c = np.zeros(g)
        vals = []
        for r in rows:
            if r["phase_bucket"] != ph:
                continue
            v = r.get(key)
            if v is None:
                continue
            i = pos[r["root_id"]]
            s[i] += float(v)
            c[i] += 1.0
            vals.append(float(v))
        tot = c[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out = s[idx].sum(axis=1) / tot
        return out, (sum(vals) / len(vals) if vals else None), len(vals)

    def ci(vec, value):
        srt = np.sort(vec[np.isfinite(vec)])
        n = srt.size
        return {"value": value,
                "ci95": [float(srt[int(0.025 * n)]),
                         float(srt[min(n - 1, int(0.975 * n))])],
                "se": float(srt.std(ddof=1)),
                "z": (value / float(srt.std(ddof=1))) if srt.std(ddof=1) else None}

    out = {
        "artifact": "CAPTURE_PER_GAME",
        "prereg": "measurement/arb_costopt_prep/PREREG.md",
        "generated_by": "measurement/arb_costopt_prep/capture_per_game.py",
        "phi_fired_plies_per_game": phi,
        "phi_total": sum(phi.values()),
        "phi_source": ("census phase SHARES x the 22.96 fired-tile-plies/game of "
                       "record (COST_MODEL.json::phi_calibration)"),
        "judge_label": ("IN-FAMILY judge-priced (clair-puct oracle / tier1-greedy "
                        "arbiter). Absolute pts/game are FAMILY-RELATIVE; the "
                        "phase CONTRAST is the robust part. F4 rider applies."),
        "per_game": {}, "early_gate": {}, "b16_early": {},
    }

    for b in B_LADDER:
        key = f"arb_j4_E64_B{b}"
        tot_rep = np.zeros(BOOT_REPS)
        tot_val = 0.0
        per_phase = {}
        for p in PHASES:
            rep, val, n = phase_reps(key, p)
            per_phase[p] = {"pts_per_tied_ply": val,
                            "pts_per_game": val * phi[p], "n": n}
            tot_rep += rep * phi[p]
            tot_val += val * phi[p]
        out["per_game"][f"B{b}"] = {
            "total_pts_per_game": ci(tot_rep, tot_val),
            "by_phase": per_phase,
            "midlate_only_pts_per_game": ci(
                sum(phase_reps(key, p)[0] * phi[p] for p in ("mid", "late")),
                sum(phase_reps(key, p)[1] * phi[p] for p in ("mid", "late"))),
        }

    # --- early-gate loss: the EARLY-bucket capture that is forgone -----------
    for b in (16, 32, 64):
        key = f"arb_j4_E64_B{b}"
        rep, val, n = phase_reps(key, "early")
        s = ci(rep * phi["early"], val * phi["early"])
        out["early_gate"][f"B{b}"] = {
            "forgone_early_capture_pts_per_game": s,
            "loss_bound_upper_ci95_pts_per_game": s["ci95"][1],
            "n_early_positions": n,
            "reading": ("point estimate NEGATIVE means gating early off is a "
                        "GAIN in the point estimate; the DECISION-RELEVANT number "
                        "is the upper CI limit -- the most capture the banked "
                        "evidence allows the early bucket to be worth."),
        }

    # --- B=16-early: the paired within-position B64 - B16 difference ---------
    for r in rows:
        r["d_64_16_j4"] = r["arb_j4_E64_B64"] - r["arb_j4_E64_B16"]
        r["d_64_32_j4"] = r["arb_j4_E64_B64"] - r["arb_j4_E64_B32"]
    for name, key in (("B64_minus_B16", "d_64_16_j4"),
                      ("B64_minus_B32", "d_64_32_j4")):
        cell = {}
        for p in PHASES:
            rep, val, n = phase_reps(key, p)
            cell[p] = {"pts_per_tied_ply": ci(rep, val),
                       "pts_per_game": ci(rep * phi[p], val * phi[p]), "n": n}
        out["b16_early"][name] = cell
    out["b16_early"]["note"] = (
        "within-position PAIRED difference on identical CRN worlds -- the robust "
        "contrast class. 'B=16 early' forgoes early[B64_minus_B16].")

    dst = os.path.join(HERE, "CAPTURE_PER_GAME.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote", dst)


if __name__ == "__main__":
    main()
