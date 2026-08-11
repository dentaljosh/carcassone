#!/usr/bin/env python3
"""One-shot: append the B512 calibration row to governance/CHECKPOINT_LINEAGE.csv (NOT_CHAMPION)."""
import csv
ROW = [
    "rod_iter_01_b512",
    "/mnt/c/carc-shared/rod_batch512_calibration/ckpt/iter_01_b512.pt",
    "true",
    "9cca3edf92ba74a1629118966682b7c8af71ec3070d99c63f595fd483ad0d1a1",
    "flywheel2_champion_iter8 (0d355002; warm-from iter8)",
    "704c0de (rod_batch512_calibration branch)",
    "true",
    "96x6 n_scalar=12 value_global_pool=False",
    "base",
    "none (E6-clean ruler family; v2.8 leaf = v2.7+meeple_k2)",
    ("batch-512 CALIBRATION sibling of rod_iter_01: SAME 1000 v2.8 self-play games (dataset fp 61a12d76, "
     "REUSED not re-gen), warm-from iter8, train_iter.py --batch-size 512 (HALF the optimizer steps: 12099 "
     "vs B256's 24196) --value-target residual --value-loss-weight 1.5 --epochs 3 --window 10 --seed 0 "
     "--lr 1e-3. ONLY batch size differs from rod_iter_01 (B256)."),
    "self-play band <1e9 (reused rod_v28_continuation iter1 data); eval bands 1.922e9 (vs parent) / 1.923e9 (vs B256)",
    "fingerprint 61a12d76cd65b719 (IDENTICAL to rod_iter_01)",
    "window=10 over the single shared iter1 gen set",
    "MCTS visit distribution (v2.8-guided search)",
    "residual",
    "value_loss_weight=1.5; policy_entropy=1.5393 (no collapse; floor 0.8731); val_pol=0.435 UNDER-FIT (B256 0.270)",
    "ownership head",
    "v2_8 (v2.7 + meeple_k=2.0; flat fast path; residual_scale 0.25 active)",
    "yes (CARCASSONNE_V25_RESIDUAL_SCALE=0.25; value head ON)",
    ("TIES B256 (rod_iter_01) head-to-head net-vs-net same-leaf deck-paired n=400: -1.7 elo / paired z-0.41 "
     "(the val_pol under-fit WASHED OUT under MCTS; root agreement w/ B256 = 0.737). vs FROZEN iter8+v2.8: "
     "+10.4 / paired z1.65 = INCONCLUSIVE (does NOT credibly beat parent; B256 was +53.4 on SAME decks). "
     "Non-transitivity: transitivity predicted -43 but direct is -1.7."),
    "b512_vs_iter8_v28_n400; b512_vs_b256_v28_n400",
    "NOT_CHAMPION",
    ("batch-512 RECIPE-CALIBRATION artifact (2026-06-23). VERDICT: KEEP BATCH 256. B512 ties B256 head-to-head "
     "but FAILS the parent gate (the defining RoD-positive result) + under-trains the policy; 1.31x faster but "
     "half the optimizer steps. NOT a recipe change, NOT promoted; champion stays flywheel2_champion_iter8; "
     "PRODUCTION.yaml unchanged; v2.7 frozen. branch rod_batch512_calibration; "
     "measurement/rod_batch512_calibration/BATCH512_CALIBRATION_REPORT.md."),
]
with open("governance/CHECKPOINT_LINEAGE.csv", "a", newline="") as f:
    csv.writer(f).writerow(ROW)
print("appended rod_iter_01_b512 lineage row")
