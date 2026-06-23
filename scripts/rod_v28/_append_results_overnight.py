#!/usr/bin/env python3
"""Append the rod_v28_overnight_flywheel eval rows (binding: n=400 vs RoD_iter_01 + heur ruler)."""
import csv
EV = "/mnt/c/carc-shared/rod_v28_overnight_flywheel/evals"
ROWS = [
    # exp_id,date,game,code_rev,n,new_ckpt,new_c,new_cap,new_var,new_sims,old_ckpt,old_c,old_cap,old_var,old_sims,W,L,D,elo,sigma,avg_diff,src_dir,confidence,note
    ["rod_ov_iter08_vs_rod1_v28_n400", "2026-06-23", "base", "208be38", "400",
     "rod_ov_iter_08.pt+v2.8", "3.0", "12", "v2_7+meeple_k2", "200",
     "rod_iter_01.pt+v2.8", "3.0", "12", "v2_7+meeple_k2", "200",
     "217", "179", "4", "33.1", "17.5", "2.23", f"{EV}/iter08_vs_iter01_n400", "high",
     "overnight-flywheel keep-best: iter_08 (best of the 9-iter chain RoD_iter_02..10) vs RoD_iter_01, "
     "v2.8 leaf, deck-paired net-vs-net, band 1.953e9 n400 (superset of n100 screen 1952e9). "
     "paired_z=+2.00 -> MODEST credible gain over the chain parent (n100 screen was +49/z1.05). "
     "MEASUREMENT ONLY; not promoted; champion stays flywheel2_champion_iter8."],
    ["rod_ov_iter10_vs_rod1_v28_n400", "2026-06-23", "base", "208be38", "400",
     "rod_ov_iter_10.pt+v2.8", "3.0", "12", "v2_7+meeple_k2", "200",
     "rod_iter_01.pt+v2.8", "3.0", "12", "v2_7+meeple_k2", "200",
     "211", "186", "3", "21.7", "17.4", "0.735", f"{EV}/iter10_vs_iter01_n400", "high",
     "overnight-flywheel ENDPOINT iter_10 vs RoD_iter_01, v2.8 leaf, deck-paired, band 1.953e9 n400. "
     "paired_z=+0.69 -> ~TIE (the n100 screen's +77.7/z2.28 was an up-fluctuation; regressed to +21.7). "
     "Chain gain is NON-monotonic: iter_08 peaks, iter_10 endpoint ~back to parent. keep-best=iter_08."],
    ["rod_ov_iter08_vs_heur3200_v28_n200", "2026-06-23", "base", "208be38", "200",
     "rod_ov_iter_08.pt+v2.8", "3.0", "12", "v2_7+meeple_k2", "200",
     "heur@3200+meeple_k2", "3.0", "12", "v2_7+meeple_k2", "3200",
     "104", "95", "1", "15.6", "24.6", "-1.455", f"{EV}/iter08_vs_heur3200_v28", "high",
     "RULER: chain-best iter_08 vs heur@3200_v2.8, deck-paired, band 1.96e9 n200. winrate +15.6/z0.64 "
     "but paired margin -1.46/z-0.83 = TIE (104W/1D/95L). VIRTUALLY IDENTICAL to RoD_iter_01 "
     "(rod_iter01_v28_vs_heur3200_v28_n800: +16.5wr/-0.36 paired = tie). NON-TRANSITIVE: iter_08's +33 "
     "over its lineage parent WASHED OUT vs the external ruler -> reaches PARITY, does NOT exceed. "
     "structural blocker #2 stands (learned must EXCEED heuristic). Not superhuman. MEASUREMENT ONLY."],
]
with open("experiments/results.csv", "a", newline="") as f:
    w = csv.writer(f)
    for r in ROWS:
        w.writerow(r)
print(f"appended {len(ROWS)} rows")
