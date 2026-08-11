#!/usr/bin/env python3
"""Read-out for the move-agreement-vs-budget probe. PRE-REGISTERED — written and committed
BEFORE any result existed (see measurement/classical_search/MOVE_AGREEMENT_PREREG.md).

THE THREE DISAGREEMENT STATISTICS
---------------------------------
For position i, budget level L, salt s, let a_i(L,s) be the DEPLOYED pick
(`q_argmax_action`). Salts are independent agent-seed lineages; because
`det_seed_base`/`det_search_seed` depend only on (seed, move_idx) and NOT on the sim
budget, a fixed salt draws the SAME determinizations at every level.

  D_paired(L1,L2) = E_i [ mean_s  1{ a_i(L1,s) != a_i(L2,s) } ]
      Same salt => same worlds, same search seeds; ONLY depth varies. Its same-budget
      null is EXACTLY 0 (a salt replayed at its own budget is bit-identical). This is the
      maximum-power test of "does depth change the move at all".

  D_same(L)       = E_i [ mean_{s<s'} 1{ a_i(L,s) != a_i(L,s') } ]
      THE NOISE FLOOR: same budget, independent reseed.

  D_cross(L1,L2)  = E_i [ mean_{s != s'} 1{ a_i(L1,s) != a_i(L2,s') } ]
      Different budget AND different seed — matched to the floor.

  NULL: if the per-position move distributions at L1 and L2 are identical (budget changed
  nothing about what the agent plays), then for independent reseeds
        D_cross_null(L1,L2) = 1 - sqrt( (1-D_same(L1)) * (1-D_same(L2)) )
  (the Cauchy-Schwarz equality case, p == q). The decision-bearing statistic is the EXCESS
        Delta(L1,L2) = D_cross(L1,L2) - D_cross_null(L1,L2)
  CI by POSITION-level bootstrap (positions are the independent unit; salts and levels
  within a position are resampled together).

EXCLUSIONS (pre-registered): roots with `ok != True`; `solver_region` roots (k_remaining
<= exact_max_k are decided by the marginalized exact solver in production, so they are
budget-independent by construction and would inflate agreement); `n_legal < 2`.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


def load(out_dir: str):
    """(positions, levels) — positions[(deck_seed,ply)] = {"meta":…, "picks":{L:{salt:a}}}."""
    pos: dict = defaultdict(lambda: {"meta": None, "picks": defaultdict(dict)})
    levels = None
    n_raw = n_bad = n_excl = 0
    for fp in sorted(Path(out_dir).glob("*.json")):
        if fp.name.startswith("manifest"):
            continue
        try:
            r = json.loads(fp.read_text())
        except Exception:
            continue
        n_raw += 1
        if not r.get("ok"):
            n_bad += 1
            continue
        if r.get("solver_region") or int(r.get("n_legal", 0)) < 2:
            n_excl += 1
            continue
        key = (int(r["deck_seed"]), int(r["ply"]))
        levels = levels or [int(x) for x in r["levels"]]
        pos[key]["meta"] = {k: r.get(k) for k in
                            ("phase_bucket", "game_phase", "h200_top2_q_gap",
                             "blind_top2_q_gap", "n_legal", "k_remaining", "k_dets")}
        for L, a in r["q_pick_by_level"].items():
            pos[key]["picks"][int(L)][int(r["salt"])] = a
    return dict(pos), levels, {"n_records": n_raw, "n_failed": n_bad, "n_excluded": n_excl}


def _per_position_rates(p, levels):
    """Per position: D_paired / D_cross matrices and the D_same vector (None if <2 salts)."""
    picks = p["picks"]
    salts = sorted(set.intersection(*[set(picks[L]) for L in levels])) if levels else []
    if len(salts) < 2:
        return None
    n = len(levels)
    same = np.full(n, np.nan)
    paired = np.full((n, n), np.nan)
    cross = np.full((n, n), np.nan)
    for i, L in enumerate(levels):
        d = [picks[L][s] != picks[L][t]
             for ii, s in enumerate(salts) for t in salts[ii + 1:]]
        same[i] = float(np.mean(d))
    for i, L1 in enumerate(levels):
        for j, L2 in enumerate(levels):
            paired[i, j] = float(np.mean([picks[L1][s] != picks[L2][s] for s in salts]))
            cross[i, j] = float(np.mean([picks[L1][s] != picks[L2][t]
                                         for s in salts for t in salts if s != t]))
    return same, paired, cross


def _pool(mats):
    same = np.nanmean(np.stack([m[0] for m in mats]), axis=0)
    paired = np.nanmean(np.stack([m[1] for m in mats]), axis=0)
    cross = np.nanmean(np.stack([m[2] for m in mats]), axis=0)
    null = 1.0 - np.sqrt(np.clip(np.outer(1 - same, 1 - same), 0, 1))
    return same, paired, cross, cross - null, null


def analyse(mats, levels, k_dets, boot=10000, seed=20260727):
    same, paired, cross, delta, null = _pool(mats)
    rng = np.random.default_rng(seed)
    N = len(mats)
    bs_delta, bs_paired, bs_same = [], [], []
    for _ in range(boot):
        idx = rng.integers(0, N, N)
        s, p, c, d, _n = _pool([mats[i] for i in idx])
        bs_delta.append(d)
        bs_paired.append(p)
        bs_same.append(s)
    bs_delta, bs_paired, bs_same = map(np.array, (bs_delta, bs_paired, bs_same))
    tot = [k_dets * L for L in levels]
    out = {"n_positions": N, "levels_per_world": levels, "total_budgets": tot,
           "n_bootstrap": boot, "pairs": {}, "floor": {}}
    for i, L in enumerate(levels):
        lo, hi = np.percentile(bs_same[:, i], [2.5, 97.5])
        out["floor"][str(tot[i])] = {"D_same": round(float(same[i]), 4),
                                     "ci95": [round(float(lo), 4), round(float(hi), 4)]}
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            dl, dh = np.percentile(bs_delta[:, i, j], [2.5, 97.5])
            pl, ph = np.percentile(bs_paired[:, i, j], [2.5, 97.5])
            sd = float(np.std(bs_delta[:, i, j]))
            out["pairs"][f"{tot[i]}v{tot[j]}"] = {
                "D_paired": round(float(paired[i, j]), 4),
                "D_paired_ci95": [round(float(pl), 4), round(float(ph), 4)],
                "D_cross": round(float(cross[i, j]), 4),
                "D_cross_null": round(float(null[i, j]), 4),
                "Delta": round(float(delta[i, j]), 4),
                "Delta_ci95": [round(float(dl), 4), round(float(dh), 4)],
                "Delta_z": (round(float(delta[i, j]) / sd, 3) if sd > 0 else None),
            }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read out the move-agreement probe")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report", default="")
    ap.add_argument("--stratifier", default="h200_top2_q_gap",
                    choices=["h200_top2_q_gap", "blind_top2_q_gap"],
                    help="PRIMARY is h200_top2_q_gap (pre-registered); median split")
    ap.add_argument("--bootstrap", type=int, default=10000)
    args = ap.parse_args(argv)

    pos, levels, counts = load(args.out_dir)
    print(f"[readout] {counts}  positions={len(pos)}", flush=True)
    if not levels:
        print("[readout] no usable records yet")
        return 1

    keyed, mats = [], []
    for k, p in pos.items():
        m = _per_position_rates(p, levels)
        if m is not None:
            keyed.append((k, p))
            mats.append(m)
    print(f"[readout] positions with >=2 complete salts: {len(mats)}", flush=True)
    if not mats:
        return 1
    k_dets = int(keyed[0][1]["meta"].get("k_dets") or 4)

    report = {"overall": analyse(mats, levels, k_dets, args.bootstrap),
              "record_counts": counts, "stratifier": args.stratifier, "strata": {}}

    # --- STRATUM 1: decision criticality (median split on the stratifier) ---------
    gaps = [p["meta"].get(args.stratifier) for _k, p in keyed]
    have = [g for g in gaps if g is not None]
    if have:
        med = float(np.median(have))
        report["stratifier_median"] = round(med, 6)
        for name, keep in (("narrow_gap", lambda g: g is not None and g <= med),
                           ("wide_gap", lambda g: g is not None and g > med)):
            sub = [m for m, g in zip(mats, gaps) if keep(g)]
            if len(sub) >= 20:
                report["strata"][name] = analyse(sub, levels, k_dets, args.bootstrap)

    # --- STRATUM 2: game phase (fixed k_remaining cuts) --------------------------
    for name in ("early", "mid", "late"):
        sub = [m for m, (_k, p) in zip(mats, keyed) if p["meta"].get("phase_bucket") == name]
        if len(sub) >= 20:
            report["strata"][f"phase_{name}"] = analyse(sub, levels, k_dets, args.bootstrap)

    # --- STRATUM 3: engine phase (tile vs meeple decision) -----------------------
    for name in ("TILES", "MEEPLES"):
        sub = [m for m, (_k, p) in zip(mats, keyed) if p["meta"].get("game_phase") == name]
        if len(sub) >= 20:
            report["strata"][f"gamephase_{name}"] = analyse(sub, levels, k_dets, args.bootstrap)

    txt = json.dumps(report, indent=2)
    if args.report:
        Path(args.report).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
