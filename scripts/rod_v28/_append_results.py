#!/usr/bin/env python3
"""One-shot: append the RoD v2.8 continuation BINDING rows to experiments/results.csv."""
import csv
ROWS = [
    # exp_id,date,game,code_rev,n,new_ckpt,new_c,new_cap,new_var,new_sims,old_ckpt,old_c,old_cap,old_var,old_sims,W,L,D,elo,sigma,avg_diff,src_dir,confidence,note
    ["rod_iter01_v28_vs_iter8_v28_n400","2026-06-22","base","9e3c0ea","400",
     "rod_iter_01.pt+v2.8","3.0","12","v2_7+meeple_k2","200",
     "iter8.pt+v2.8","3.0","12","v2_7+meeple_k2","200",
     "227","166","7","53.4","17.6","3.675",
     "/mnt/c/carc-shared/v28_rod_probe/nvn_iter_01_mk20_vs_iter8_mk20_s200_rs025","high",
     "RoD v2.8 continuation BINDING: RoD_iter_01 (1000 v2.8 self-play games warm-from iter8) "
     "vs FROZEN ITER8_V28_PARENT, same v2.8 leaf, deck-paired both seats, band 1.922e9. paired z=3.51. "
     "RoD POSITIVE -- first continuation to beat its parent (v2.7 deeper-teacher was a powered null). "
     "Gain is genuine policy reshaping, NOT teacher-imitation. MEASUREMENT ONLY; not promoted; "
     "PRODUCTION.yaml unchanged. branch rod_v28_continuation_probe; see measurement/rod_v28_continuation/"],
    ["rod_iter01_v28_vs_heur3200_v28_n800","2026-06-22","base","9e3c0ea","800",
     "rod_iter_01.pt+v2.8","3.0","12","v2_7+meeple_k2","200",
     "heur@3200+meeple_k2","3.0","12","v2_7+meeple_k2","3200",
     "412","374","14","16.5","12.3","-0.36",
     "/mnt/c/carc-shared/v28_rod_probe/rod_iter01_vs_heur3200_v28","high",
     "RoD v2.8 RULER: RoD_iter_01+v2.8 vs heur@3200_v28, paired band 1.9221e9. TIE -- winrate elo "
     "+16.5/z1.34 but paired score margin -0.36/z-0.47. RoD CLOSED the equal-leaf gap (parent "
     "iter8+v2.8 was -38.4 vs same ruler, row iter8_v28_vs_heur3200_v28_n200) to PARITY; does NOT "
     "exceed deep heuristic search. NOT superhuman (hand-crafted leaf, no human anchor). measurement only"],
]
with open("experiments/results.csv", "a", newline="") as f:
    w = csv.writer(f)
    for r in ROWS:
        w.writerow(r)
print(f"appended {len(ROWS)} rows")
