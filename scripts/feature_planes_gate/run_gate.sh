#!/bin/bash
# Step-1 representation gate orchestrator — SEQUENTIAL, streamed, RAM-guarded.
# Each mode: stream-dump (W30, obs->ext4) then train (memmap). Separate processes
# so RAM returns to baseline between steps. Datasets on LOCAL ext4 (fast memmap;
# the CIFS share is 9p = slow random reads). Usage: bash run_gate.sh none both ...
set -u
cd /home/doctor/projects/carcassone || exit 1
PY=/home/doctor/projects/carcassone/.venv/bin/python
GATE=measurement/feature_planes_gate
DS=/home/doctor/carc_step1_gate
VARIANT="${VARIANT:-V4_listwise}"
EPOCHS="${EPOCHS:-30}"
W="${W:-30}"
mkdir -p "$GATE" "$DS"
echo "[run_gate] modes='$*' variant=$VARIANT epochs=$EPOCHS W=$W ds=$DS $(date +%H:%M:%S)"
for mode in "$@"; do
  avail=$(free -g | awk '/Mem/{print $7}')
  echo "[guard] mode=$mode avail=${avail}GB $(date +%H:%M:%S)"
  if [ "$avail" -lt 8 ]; then echo "[ABORT] low RAM (${avail}GB)"; exit 1; fi
  rm -rf "$DS/dataset_$mode"
  echo "=== DUMP $mode (W$W, stream->ext4) $(date +%H:%M:%S) ==="
  nice -n 19 "$PY" -u scripts/feature_planes_gate/step1_dump.py \
    --mode "$mode" --workers "$W" --out "$DS/dataset_$mode" \
    || { echo "[DUMP $mode FAILED]"; exit 1; }
  avail=$(free -g | awk '/Mem/{print $7}'); echo "[guard post-dump] avail=${avail}GB"
  echo "=== TRAIN $mode ($VARIANT, ${EPOCHS}ep) $(date +%H:%M:%S) ==="
  nice -n 19 "$PY" -u scripts/feature_planes_gate/step1_train.py \
    --dataset "$DS/dataset_$mode" --variant "$VARIANT" --epochs "$EPOCHS" \
    --out "$GATE/stage_$mode" \
    || echo "[TRAIN $mode FAILED]"
  echo "[mode $mode COMPLETE $(date +%H:%M:%S)]"
done
echo "=== RUN_GATE ALL DONE: '$*' $(date +%H:%M:%S) ==="
