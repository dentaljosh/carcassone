#!/usr/bin/env python3
"""One-shot: append the rod_batch512_calibration result rows to experiments/results.csv."""
import csv
ROWS = [
    # exp_id,date,game,code_rev,n,new_ckpt,new_c,new_cap,new_var,new_sims,old_ckpt,old_c,old_cap,old_var,old_sims,W,L,D,elo,sigma,avg_diff,src_dir,confidence,note
    ["b512_vs_iter8_v28_n400","2026-06-23","base","704c0de","400",
     "iter_01_b512.pt+v2.8","3.0","12","v2_7+meeple_k2","200",
     "iter8.pt+v2.8","3.0","12","v2_7+meeple_k2","200",
     "203","191","6","10.4","17.4","1.87",
     "/mnt/c/carc-shared/rod_b512_calib/nvn_iter_01_b512_mk20_vs_iter8_mk20_s200_rs025","high",
     "batch-512 calibration: B512 (batch 512 = HALF optimizer steps; same data/lr/seed/epochs as B256, "
     "dataset fp 61a12d76 identical) vs FROZEN ITER8_V28_PARENT, same v2.8 leaf, deck-paired band 1.922e9. "
     "paired z=1.65 = INCONCLUSIVE -- does NOT credibly beat parent (B256 was +53.4/z3.51 on the SAME decks). "
     "The policy under-fit (val_pol 0.435 vs 0.270) cost the parent edge. MEASUREMENT ONLY; not promoted; "
     "PRODUCTION.yaml unchanged; v2.7 frozen. branch rod_batch512_calibration"],
    ["b512_vs_b256_v28_n400","2026-06-23","base","704c0de","400",
     "iter_01_b512.pt+v2.8","3.0","12","v2_7+meeple_k2","200",
     "rod_iter_01.pt+v2.8","3.0","12","v2_7+meeple_k2","200",
     "194","196","10","-1.7","17.4","-0.44",
     "/mnt/c/carc-shared/rod_b512_calib/nvn_iter_01_b512_mk20_vs_iter_01_mk20_s200_rs025","high",
     "batch-512 calibration KEY matchup: B512 vs B256 (RoD_iter_01) DIRECT head-to-head, same v2.8 leaf, "
     "fresh band 1.923e9. paired z=-0.41 = TIE (point est -6.9 n200 -> -1.7 n400). The val_pol under-fit "
     "WASHED OUT under MCTS@200; B512 plays 0.737 like B256 (root audit). NON-TRANSITIVITY: transitivity "
     "predicted -43 (from parent margins +10.4/+53.4) but direct is -1.7 (~41 elo gap). VERDICT: KEEP BATCH 256 "
     "(B512 ties head-to-head but FAILS the parent gate + under-trains; 1.31x speedup not worth it). measurement only"],
]
with open("experiments/results.csv", "a", newline="") as f:
    w = csv.writer(f)
    for r in ROWS:
        w.writerow(r)
print(f"appended {len(ROWS)} rows")
