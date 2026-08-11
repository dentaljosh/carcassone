#!/usr/bin/env python3
"""Append the rod_v28_overnight_flywheel TAIL-eval rows to results.csv.

Reads each eval's result.json (verified numbers, no hand-typing) and emits one
row per matchup matching the results.csv schema. MEASUREMENT ONLY — nothing
promoted; records that the extended chain (iters 11-17) + early iters (02/03)
do not beat the keep-best iter_08.
"""
import csv, json, subprocess
from pathlib import Path

EV = Path("/mnt/c/carc-shared/rod_v28_overnight_flywheel/evals")
REV = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()

# (subdir, exp_id, new_ckpt_label, old_ckpt_label, confidence, note)
M = [
    ("iter02_vs_iter01_n100", "rod_ov_iter02_vs_rod1_v28_n100", "rod_ov_iter_02.pt", "rod_iter_01.pt", "screen",
     "tail-eval completeness sweep; iter_02 vs RoD_iter_01, v2.8 leaf, deck-paired n100 SCREEN (coarse, +-35 elo)."),
    ("iter03_vs_iter01_n100", "rod_ov_iter03_vs_rod1_v28_n100", "rod_ov_iter_03.pt", "rod_iter_01.pt", "screen",
     "tail-eval completeness; iter_03 vs RoD_iter_01, n100 SCREEN. ~tied."),
    ("iter11_vs_iter01_n100", "rod_ov_iter11_vs_rod1_v28_n100", "rod_ov_iter_11.pt", "rod_iter_01.pt", "screen",
     "tail iter_11 vs RoD_iter_01 n100 SCREEN: +96 looks strong but INFLATED (regression-to-mean) -- "
     "iter_11 LOSES to keep-best iter_08 head-to-head (-56, see rod_ov_iter11_vs_iter08). non-transitive."),
    ("iter13_vs_iter01_n100", "rod_ov_iter13_vs_rod1_v28_n100", "rod_ov_iter_13.pt", "rod_iter_01.pt", "screen",
     "tail iter_13 vs RoD_iter_01 n100 SCREEN. weakly positive."),
    ("iter15_vs_iter01_n100", "rod_ov_iter15_vs_rod1_v28_n100", "rod_ov_iter_15.pt", "rod_iter_01.pt", "screen",
     "tail iter_15 vs RoD_iter_01 n100 SCREEN (re-tallied to full 100 after a 2-box premature-tally clip). ~tied."),
    ("iter17_vs_iter01_n100", "rod_ov_iter17_vs_rod1_v28_n100", "rod_ov_iter_17.pt", "rod_iter_01.pt", "screen",
     "tail iter_17 vs RoD_iter_01 n100 SCREEN (re-tallied to 100). positive; best tail contender."),
    ("iter11_vs_iter08_n100", "rod_ov_iter11_vs_iter08_v28_n100", "rod_ov_iter_11.pt", "rod_ov_iter_08.pt", "screen",
     "tail-vs-keepbest: iter_11 vs iter_08 n100 SCREEN -> LOSES (-56, paired_z near -2). the chain's "
     "strongest-vs-RoD1 iter is WEAKER than iter_08 h2h."),
    ("iter13_vs_iter08_n100", "rod_ov_iter13_vs_iter08_v28_n100", "rod_ov_iter_13.pt", "rod_ov_iter_08.pt", "screen",
     "tail-vs-keepbest: iter_13 vs iter_08 n100 SCREEN -> TIE (sign-conflicted wash)."),
    ("iter17_vs_iter08_n100", "rod_ov_iter17_vs_iter08_v28_n100", "rod_ov_iter_17.pt", "rod_ov_iter_08.pt", "screen",
     "tail-vs-keepbest: iter_17 vs iter_08 n100 SCREEN -> TIE (best contender; topped up to n=384 below)."),
    ("iter17_vs_iter08_n400", "rod_ov_iter17_vs_iter08_v28_n384", "rod_ov_iter_17.pt", "rod_ov_iter_08.pt", "high",
     "VERDICT (n=384, harness 40min-timeout clipped from 400): best tail contender iter_17 TIES keep-best "
     "iter_08 (+6.3 elo / paired_z -0.16, both |z|<1). The extended chain 11-17 does NOT beat iter_08. "
     "iter_08 stays keep-best (= heur@3200 parity). MEASUREMENT ONLY; nothing promoted."),
]

rows = []
for sub, exp_id, new_lab, old_lab, conf, note in M:
    rj = EV / sub / "result.json"
    d = json.load(open(rj))
    rows.append([
        exp_id, "2026-06-23", "base", REV, str(d["n"]),
        f"{new_lab}+v2.8", "3.0", "12", "v2_7+meeple_k2", "200",
        f"{old_lab}+v2.8", "3.0", "12", "v2_7+meeple_k2", "200",
        str(d["W"]), str(d["L"]), str(d["D"]),
        f'{d["elo"]:.1f}', f'{d["elo_1sig"]:.1f}', f'{d["avg_diff"]:.2f}',
        str((EV / sub).as_posix()), conf, note,
    ])

with open("experiments/results.csv", "a", newline="") as f:
    w = csv.writer(f)
    for r in rows:
        w.writerow(r)
print(f"appended {len(rows)} tail-eval rows (code_rev {REV})")
for r in rows:
    print(f"  {r[0]:42s} n={r[4]:4s} elo={r[18]:>7s} (+-{r[19]}) W/L/D={r[15]}/{r[16]}/{r[17]}")
