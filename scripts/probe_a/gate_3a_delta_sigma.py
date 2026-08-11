#!/usr/bin/env python3
"""PROBE A — §3A gate: proper PAIRED sigma for Delta_indep, from the saved
per-group regret vectors. Delta_indep = gain(both) - gain(best_single) is a
DIFFERENCE of two gains measured on the SAME test groups, so its sigma is the
SD of the per-group difference (correlated, not independent). This reads
<out>/per_group_regret.npz (leaf_reg + best_reg per regime) and reports the
bootstrap + analytic paired sigma of Delta_indep in pp-of-gain units.

  .venv/bin/python scripts/probe_a/gate_3a_delta_sigma.py --out /home/doctor/carc_probe_a/gate_3a
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np


def gain_pp(leaf_reg, best_reg):
    base = leaf_reg.mean()
    return 100.0 * (base - best_reg.mean()) / (base + 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/home/doctor/carc_probe_a/gate_3a")
    ap.add_argument("--boot", type=int, default=5000)
    args = ap.parse_args()
    outd = Path(args.out)
    z = np.load(outd / "per_group_regret.npz")
    summ = json.loads((outd / "summary.json").read_text())

    regimes = ["none", "farm-only", "bag-only", "both"]
    leafr = {r: z[f"{r}_leaf_reg"] for r in regimes}
    bestr = {r: z[f"{r}_best_reg"] for r in regimes}
    n = len(leafr["both"])
    gains = {r: gain_pp(leafr[r], bestr[r]) for r in regimes}
    g_farm, g_bag = gains["farm-only"], gains["bag-only"]
    single = "farm-only" if g_farm >= g_bag else "bag-only"
    delta = gains["both"] - gains[single]

    # analytic paired sigma: per-group gain reduction relative to a COMMON base
    # (leaf-alone regret). Use the shared leaf-alone regret (identical across
    # regimes since leaf_q is the same) as the base; Delta per group =
    # 100 * ( (leaf - both_net) - (leaf - single_net) ) / base
    #      = 100 * (single_net - both_net) / base.
    base = leafr["both"].mean()   # leaf-alone base (same for all regimes)
    per_group_delta = 100.0 * (bestr[single] - bestr["both"]) / (base + 1e-12)
    sd = float(per_group_delta.std(ddof=1))
    se = sd / np.sqrt(n)

    # bootstrap over groups (paired resample).
    rng = np.random.default_rng(0)
    boots = np.empty(args.boot)
    idx = np.arange(n)
    for b in range(args.boot):
        s = rng.choice(idx, n, replace=True)
        gb = gain_pp(leafr["both"][s], bestr["both"][s])
        gs = gain_pp(leafr[single][s], bestr[single][s])
        boots[b] = gb - gs
    boot_sd = float(boots.std(ddof=1))
    ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))

    print(f"[Delta_indep paired sigma]  n_groups={n}")
    print(f"  gains: none={gains['none']:+.2f}  farm-only={g_farm:+.2f}  "
          f"bag-only={g_bag:+.2f}  both={gains['both']:+.2f}")
    print(f"  best single = {single} ({gains[single]:+.2f}pp)")
    print(f"  Delta_indep = both - best_single = {delta:+.2f}pp")
    print(f"  analytic paired SE(Delta_indep) = {se:.2f}pp")
    print(f"  bootstrap SD(Delta_indep)       = {boot_sd:.2f}pp  95% CI [{ci[0]:+.2f},{ci[1]:+.2f}]pp")
    z_score = delta / (boot_sd + 1e-12)
    print(f"  Delta_indep z (vs bootstrap sd) = {z_score:+.2f}")
    verdict = "SEPARATED" if delta >= 3.0 else "REDUNDANT"
    print(f"  3pp threshold => {verdict}  (CI {'excludes' if ci[0] > 3.0 else 'includes'} +3pp)")

    (outd / "delta_sigma.json").write_text(json.dumps({
        "n_groups": n, "gains_pp": gains, "best_single": single,
        "delta_indep_pp": delta, "analytic_se_pp": se, "bootstrap_sd_pp": boot_sd,
        "bootstrap_ci95_pp": ci, "delta_z": z_score, "verdict": verdict,
    }, indent=2, default=float))
    print(f"-> {outd}/delta_sigma.json")


if __name__ == "__main__":
    main()
