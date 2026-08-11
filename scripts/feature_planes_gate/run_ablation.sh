#!/bin/bash
# Step-1 attribution: farm-only vs bag-only, REUSING dataset_both (no re-dump).
# --drop-bag zeroes the 32 bag scalars -> farm-only; --drop-farm zeroes the 3 farm
# planes -> bag-only. Sequential: the 16GB GPU fits only one train at a time.
# Fire ONLY after the both_shuffled negative control comes back clean.
set -u
cd /home/doctor/projects/carcassone || exit 1
PY=/home/doctor/projects/carcassone/.venv/bin/python
DS=/home/doctor/carc_step1_gate/dataset_both
GATE=measurement/feature_planes_gate
common="--dataset $DS --variant V4_listwise --epochs 30 --patience 6"
echo "[ablation] start $(date +%H:%M:%S)"

echo "=== FARM-ONLY (drop bag scalars) $(date +%H:%M:%S) ==="
nice -n 19 "$PY" -u scripts/feature_planes_gate/step1_train.py $common \
  --drop-bag --out "$GATE/stage_farm_only" || echo "[FARM-ONLY FAILED]"

echo "=== BAG-ONLY (drop farm planes) $(date +%H:%M:%S) ==="
nice -n 19 "$PY" -u scripts/feature_planes_gate/step1_train.py $common \
  --drop-farm --out "$GATE/stage_bag_only" || echo "[BAG-ONLY FAILED]"

echo "=== ABLATION ALL DONE $(date +%H:%M:%S) ==="
