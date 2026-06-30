#!/usr/bin/env bash
# Overlap probe: re-run farm-only and bag-only ablations with --dump-per-group.
# Sequential (single GPU, latency-bound net → no parallel gain, avoids contention).
set -euo pipefail
cd /home/doctor/projects/carcassone
PY=/home/doctor/projects/carcassone/.venv/bin/python
DS=/home/doctor/carc_step1_gate/dataset_both
COMMON="--dataset $DS --variant V4_listwise --epochs 30 --patience 6 --dump-per-group"

echo "=== [$(date)] FARM-ONLY (--drop-bag) ==="
nice -n 19 $PY scripts/feature_planes_gate/step1_train.py $COMMON --drop-bag \
    --out measurement/feature_planes_gate/probe_farm \
    > measurement/feature_planes_gate/probe_farm.log 2>&1

echo "=== [$(date)] BAG-ONLY (--drop-farm) ==="
nice -n 19 $PY scripts/feature_planes_gate/step1_train.py $COMMON --drop-farm \
    --out measurement/feature_planes_gate/probe_bag \
    > measurement/feature_planes_gate/probe_bag.log 2>&1

echo "=== [$(date)] BOTH PROBES DONE ==="
