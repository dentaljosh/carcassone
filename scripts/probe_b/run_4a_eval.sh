#!/bin/bash
# PROBE B §4A — offline eval driver (docs/PROBE_B_FAIR_INFO_SPEC.md §4A).
#
# For a fair-retargeted dataset AND a clair-retargeted dataset (same obs/scalars/
# leaf/split, ONLY oracle_q differs), run the CL-037 gate trainer UNCHANGED:
#   - full mode (farm+bag) : α-sweep + net-alone Kendall-τ  → H-4A-inert signal
#   - --drop-farm (bag-only) + --drop-bag (farm-only)       → H-4A-bag ablation deltas
# so fair-vs-clair is a pure TARGET swap at matched depth D. Offline, no games.
#
# Usage: bash run_4a_eval.sh <fair_ds_dir> <clair_ds_dir> <out_root> [epochs] [variant]
set -u
cd /home/doctor/projects/carcassone || exit 1
PY=/home/doctor/projects/carcassone/.venv/bin/python
TRAIN=scripts/feature_planes_gate/step1_train.py
FAIR_DS="${1:?fair dataset dir}"
CLAIR_DS="${2:?clair dataset dir}"
OUT="${3:?out root}"
EPOCHS="${4:-30}"
VARIANT="${5:-V4_listwise}"
mkdir -p "$OUT"
echo "[4a-eval] fair=$FAIR_DS clair=$CLAIR_DS out=$OUT ep=$EPOCHS variant=$VARIANT $(date +%H:%M:%S)"

run_arm () {  # kind ds
  local kind="$1" ds="$2"
  echo "=== $kind : full (farm+bag) — α-sweep + τ (H-4A-inert) $(date +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$TRAIN" --dataset "$ds" --variant "$VARIANT" --epochs "$EPOCHS" \
    --out "$OUT/${kind}_both" || echo "[$kind both FAILED]"
  echo "=== $kind : bag-only (drop farm planes) — H-4A-bag $(date +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$TRAIN" --dataset "$ds" --variant "$VARIANT" --epochs "$EPOCHS" \
    --drop-farm --out "$OUT/${kind}_bag_only" || echo "[$kind bag-only FAILED]"
  echo "=== $kind : farm-only (drop bag scalars) — H-4A-bag $(date +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$TRAIN" --dataset "$ds" --variant "$VARIANT" --epochs "$EPOCHS" \
    --drop-bag --out "$OUT/${kind}_farm_only" || echo "[$kind farm-only FAILED]"
}

run_arm fair  "$FAIR_DS"
run_arm clair "$CLAIR_DS"
echo "=== 4A EVAL DONE $(date +%H:%M:%S) ==="
