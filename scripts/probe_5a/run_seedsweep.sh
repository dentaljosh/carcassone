#!/usr/bin/env bash
# Probe §5A — seed sweep to defeat the single-seed init-fragility that flipped the
# `both` control +20.5%->0%. 4 configs × N seeds, same harness. Reads mean±std +
# a paired-per-seed Δ_indep (all_three − both54) with aggregate_seedsweep.py.
#
#   both44      natural farm+bag (no tempo append) -> farm/bag magnitude + harness sanity
#   both54      farm+bag, tempo cols zeroed        -> paired baseline (same arch as all_three)
#   tempo_only  tempo, farm/bag zeroed             -> tempo standalone
#   all_three   farm+bag+tempo                     -> the binding arm (paired w/ both54)
set -uo pipefail
cd /home/doctor/projects/carcassone
TEMPO=/home/doctor/carc_step1_gate/tempo_5a/tempo_resid.npz
DS=/home/doctor/carc_step1_gate/dataset_both
OUT=measurement/probe_5a/seedsweep
PY=.venv/bin/python
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
EPOCHS="${EPOCHS:-30}"
SEEDS="${SEEDS:-0 1 2 3}"
CONC="${CONC:-4}"
mkdir -p "$OUT"

run_one () {  # config seed
  local cfg=$1 seed=$2 flags tempo o
  case $cfg in
    both44)     flags=""                       ; tempo="" ;;
    both54)     flags="--drop-tempo"           ; tempo="--tempo-npz $TEMPO" ;;
    tempo_only) flags="--drop-farm --drop-bag" ; tempo="--tempo-npz $TEMPO" ;;
    all_three)  flags=""                       ; tempo="--tempo-npz $TEMPO" ;;
  esac
  o="$OUT/${cfg}_s${seed}"
  nice -n 19 $PY scripts/feature_planes_gate/step1_train.py \
    --dataset "$DS" $tempo --variant V4_listwise --groups-per-batch 8 \
    --epochs "$EPOCHS" --seed "$seed" --out "$o" $flags > "$OUT/${cfg}_s${seed}.log" 2>&1
  echo "[done] $cfg s$seed"
}

running=0
for cfg in both44 both54 tempo_only all_three; do
  for s in $SEEDS; do
    run_one "$cfg" "$s" &
    running=$((running+1))
    if [ "$running" -ge "$CONC" ]; then wait -n; running=$((running-1)); fi
  done
done
wait
echo "=== seed sweep complete -> $OUT ; read with aggregate_seedsweep.py ==="
