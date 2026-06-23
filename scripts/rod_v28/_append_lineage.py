#!/usr/bin/env python3
"""One-shot: append the RoD_iter_01 row to governance/CHECKPOINT_LINEAGE.csv (NOT_CHAMPION, measurement)."""
import csv
ROW = [
    "rod_iter_01",
    "/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt",
    "true",
    "a8b824df0786284cbc5caf8e49d27ea90fb263bc1016eed27c2fe30e6d2a1f4b",
    "flywheel2_champion_iter8 (0d355002; warm-from iter8)",
    "dbdd4b3 (rod probe branch; net-vs-net harness 9e3c0ea)",
    "true",
    "96x6 n_scalar=12 value_global_pool=False",
    "base",
    "none (E6-clean ruler family; v2.8 leaf = v2.7+meeple_k2)",
    ("RoD v2.8 continuation: 1000 v2.8 self-play games (CARCASSONNE_V25_MEEPLE_K=2.0, leaf v2_5+meeple_k2, "
     "residual_scale 0.25, sims 200) warm-from iter8, then train_iter.py --value-target residual "
     "--value-loss-weight 1.5 --epochs 3 --batch-size 256 --window 10 (scripts/gen_flywheel.sh + "
     "scripts/train_iter.py; PROBE_PLAN.md). v2.7 bit-identical (env-opt-in)."),
    "self-play 6.0001e8; eval bands 1.922e9 (parent matchup) / 1.9221e9 (heur ruler)",
    "unknown@train (rod_v28_continuation/iter1_data .npz not hashed)",
    "window=10 over the single iter1 gen set",
    "MCTS visit distribution (v2.8-guided search)",
    "residual",
    "value_loss_weight=1.5; policy_entropy=1.5429 (no collapse; floor 0.8731)",
    "ownership head",
    "v2_8 (v2.7 + meeple_k=2.0; flat fast path; residual_scale 0.25 active in gen)",
    "yes (CARCASSONNE_V25_RESIDUAL_SCALE=0.25; value head ON)",
    ("BEATS frozen iter8+v2.8 net-vs-net same-leaf deck-paired n=400: +53.4 elo / paired z=3.51 (RoD POSITIVE). "
     "vs heur@3200_v28 n=800: TIE (+16.5 winrate elo / paired margin -0.36/z-0.47) = reached PARITY, NOT exceeded. "
     "Gain is genuine policy reshaping (root-move agreement w/ heur@3200_v28 flat, delta -0.009), NOT teacher-imitation."),
    "rod_iter01_v28_vs_iter8_v28_n400; rod_iter01_v28_vs_heur3200_v28_n800",
    "NOT_CHAMPION",
    ("RoD v2.8 continuation probe checkpoint (2026-06-22). FIRST continuation to BEAT its parent (v2.7 deeper-teacher "
     "+ residual-flywheel were powered nulls) => the v2.7 leaf was a real ceiling; v2.8 unstuck a +53 gain. Reached "
     "PARITY with deep heuristic search at equal leaf, NOT exceeded. NOT superhuman (hand-crafted leaf, no human anchor). "
     "NOT promoted; champion stays flywheel2_champion_iter8; PRODUCTION.yaml unchanged. branch rod_v28_continuation_probe; "
     "measurement/rod_v28_continuation/ROD_V28_CONTINUATION_REPORT.md. Next: dedicated rod_v28_flywheel to test compounding."),
]
with open("governance/CHECKPOINT_LINEAGE.csv", "a", newline="") as f:
    csv.writer(f).writerow(ROW)
print("appended rod_iter_01 lineage row")
