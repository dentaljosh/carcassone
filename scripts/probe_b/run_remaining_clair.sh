#!/bin/bash
# Re-run ONLY the 2 clair arms lost to the cross-obs OOM (clair_both survived).
# Both use the SAME clair obs → no fair+clair cache accumulation → fits (~34G peak).
set -u
cd /home/doctor/projects/carcassone || exit 1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/doctor/projects/carcassone/.venv/bin/python
TRAIN=scripts/feature_planes_gate/step1_train.py
DS=/home/doctor/carc_probe_b/ds_clair_full
OUT=measurement/probe_b_4a/eval_full
# belt-and-suspenders: drop any lingering page cache (no-op without sudo; box is fresh anyway)
sync; sudo -n sh -c 'echo 1 > /proc/sys/vm/drop_caches' 2>/dev/null || true
for spec in bag_only:--drop-farm farm_only:--drop-bag; do
  name=${spec%%:*}; flag=${spec##*:}
  echo "=== clair $name $(date +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$TRAIN" --dataset "$DS" --variant V4_listwise --epochs 30 \
    --groups-per-batch 8 "$flag" --out "$OUT/clair_$name" || echo "[clair $name FAILED]"
  sync; sudo -n sh -c 'echo 1 > /proc/sys/vm/drop_caches' 2>/dev/null || true
done
echo "=== REMAINING CLAIR DONE $(date +%H:%M:%S) ==="
