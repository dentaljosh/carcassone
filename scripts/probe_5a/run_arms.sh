#!/usr/bin/env bash
# Probe §5A — Stage 2: the 4-arm CL-037 head at h6400, tempo as a 3rd input axis.
# Runs ONLY after gate_zero.py returns PASS/PARTIAL. All arms share the SAME
# architecture width (n_scalar = 44 base+bag + n_tempo), differing only by which
# input blocks are zeroed — a clean ablation. V4_listwise (matches CL-037/§3A).
#
# Usage: bash run_arms.sh [tempo_npz] [out_root] [variant]
set -uo pipefail   # NOT -e: one arm failing must not abort the other three
cd /home/doctor/projects/carcassone

TEMPO="${1:-/home/doctor/carc_step1_gate/tempo_5a/tempo.npz}"
OUT="${2:-measurement/probe_5a/arms}"
VARIANT="${3:-V4_listwise}"
DS=/home/doctor/carc_step1_gate/dataset_both
PY=.venv/bin/python
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # GPU-frag guard (§4A lesson)
COMMON="--dataset $DS --tempo-npz $TEMPO --variant $VARIANT --groups-per-batch 8"

run () {  # name, extra-flags
  echo "=== ARM: $1 $(date +%H:%M:%S) ==="
  nice -n 19 $PY scripts/feature_planes_gate/step1_train.py $COMMON \
    --out "$OUT/$1" $2 2>&1 | grep -E "regret|beats_leaf|tempo|drop|split|GATE|Error|Traceback" | tail -6
  # NOTE: do NOT drop page cache between arms — all 4 arms read the SAME 32GB obs
  # memmap; keeping it cached across arms is the speedup, not a leak.
}

run none        "--drop-farm --drop-bag --drop-tempo"   # blind control (reproduce +1.9%)
run both        "--drop-tempo"                          # h6400 positive control (reproduce -20.5%)
run tempo_only  "--drop-farm --drop-bag"                # tempo alone (novel-axis standalone)
run all_three   ""                                      # farm+bag+tempo (the binding arm)

echo "=== all 4 arms done -> $OUT ; read with verdict_5a.py ==="
