#!/usr/bin/env bash
# Continuation of the overlap probe: the subagent's driver died (orphaning the
# farm-only train), so this waits for farm's per_group dump, then runs bag-only
# (if not already done), then the overlap analysis. Idempotent.
set -uo pipefail
cd /home/doctor/projects/carcassone
PY=/home/doctor/projects/carcassone/.venv/bin/python
GATE=measurement/feature_planes_gate
FARM=$GATE/probe_farm/V4_listwise/per_group.npz
BAG=$GATE/probe_bag/V4_listwise/per_group.npz
COMMON="--dataset /home/doctor/carc_step1_gate/dataset_both --variant V4_listwise --epochs 30 --patience 6 --dump-per-group"

echo "=== [$(date +%H:%M:%S)] waiting for farm-only dump ($FARM) ==="
while [ ! -f "$FARM" ]; do sleep 30; done
echo "=== [$(date +%H:%M:%S)] farm dump present ==="

if [ ! -f "$BAG" ]; then
  echo "=== [$(date +%H:%M:%S)] BAG-ONLY (--drop-farm) ==="
  nice -n 19 $PY scripts/feature_planes_gate/step1_train.py $COMMON --drop-farm \
    --out $GATE/probe_bag > $GATE/probe_bag.log 2>&1 || { echo "[BAG FAILED]"; exit 1; }
else
  echo "=== bag dump already present, skipping ==="
fi

echo "=== [$(date +%H:%M:%S)] ANALYZE ==="
$PY scripts/feature_planes_gate/analyze_overlap.py
echo "=== OVERLAP PROBE FINISH DONE [$(date +%H:%M:%S)] ==="
