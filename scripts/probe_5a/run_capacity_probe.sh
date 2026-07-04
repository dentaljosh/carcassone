#!/usr/bin/env bash
# CAPACITY-SCALING PROBE — does model capacity move the Q-label sibling-ranking
# ceiling toward the leaf? The pre-registered disambiguator for "would 10x scale
# help" (read-out doc + FIXED thresholds: measurement/capacity_probe/CAPACITY_PROBE.md
# — written BEFORE results).
#
# Design (fixed): the CL-037/§5A sighted dump dataset_both (81ch/25W/44 scalars)
# + the 10-col tempo block appended = n_scalar 54, NO drop flags (the all_three
# config — richest input, gives capacity its best shot). oracle_q absolute,
# V4_listwise — the exact run_arm_retrains.sh all_three invocation, only
# --trunk-filters/--trunk-blocks vary:
#   (64,4)  = the 386K baseline (pipeline validation + same-config replicate)
#   (128,6) ~ 2M params
#   (256,8) ~ 8-10M params
# x seeds {0,1} = 6 runs, ascending size (smallest validates the pipeline first).
#
# STRICTLY SEQUENTIAL / SOLO (the §5A concurrency-4 OOM lesson — one training at
# a time = page cache + 1 proc). GPU assumed FREE when this runs.
# Resumable: a run is skipped iff its ranknet_best.pt already exists.
#
# Usage (detached — Mac-sleep/WSL-teardown kills tty-attached jobs):
#   mkdir -p measurement/capacity_probe
#   setsid nohup bash scripts/probe_5a/run_capacity_probe.sh \
#     > measurement/capacity_probe/launcher.log 2>&1 & disown
set -uo pipefail   # NOT -e: one run failing must not abort the rest
cd /home/doctor/projects/carcassone

TEMPO="${1:-/home/doctor/carc_step1_gate/tempo_5a/tempo_resid.npz}"
OUTROOT="${2:-measurement/capacity_probe}"
VARIANT=V4_listwise
DS=/home/doctor/carc_step1_gate/dataset_both
PY=.venv/bin/python
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # GPU-frag guard (§4A lesson)
# Same args run_arm_retrains.sh used for its all_three arm (NO drop flags),
# + --trunk-filters/--trunk-blocks per size below.
COMMON="--dataset $DS --tempo-npz $TEMPO --variant $VARIANT --groups-per-batch 8 --save-model"
mkdir -p "$OUTROOT"

# ascending size — smallest validates the pipeline first
SIZES=("64 4" "128 6" "256 8")
SEEDS=(0 1)

echo "[eta] 6 sequential GPU runs (3 sizes x 2 seeds, ascending): f64 ~15-70min/run"
echo "[eta] (2026-07-01 arms-run wallclocks), f128 slower, f256 possibly 2-4h/run"
echo "[eta] -> total possibly 6-12h. First loss lines expected within ~10-20min."

run_one () {  # filters blocks seed
  local f=$1 b=$2 seed=$3
  local out="$OUTROOT/f${f}b${b}_s${seed}"
  local ckpt="$out/$VARIANT/ranknet_best.pt"
  local log="$OUTROOT/f${f}b${b}_s${seed}.log"
  if [ -f "$ckpt" ]; then
    echo "=== SKIP f${f}b${b} s$seed (exists: $ckpt) ==="
    return 0
  fi
  echo "=== SIZE f${f}b${b} seed $seed $(date +%F_%H:%M:%S) -> $log ==="
  # shellcheck disable=SC2086
  nice -n 19 $PY scripts/feature_planes_gate/step1_train.py $COMMON \
    --trunk-filters "$f" --trunk-blocks "$b" \
    --seed "$seed" --out "$out" > "$log" 2>&1
  local rc=$?
  if [ -f "$ckpt" ]; then
    echo "    OK f${f}b${b} s$seed (rc=$rc) -> $ckpt"
  else
    echo "    FAIL f${f}b${b} s$seed (rc=$rc) — no ranknet_best.pt; see $log"
  fi
}

# NOTE: do NOT drop page cache between runs — every run reads the SAME 32GB obs
# memmap; keeping it cached across runs is the speedup, not a leak.
for sz in "${SIZES[@]}"; do
  read -r F B <<< "$sz"
  for seed in "${SEEDS[@]}"; do
    run_one "$F" "$B" "$seed"
  done
done

echo "=== all capacity-probe trainings done -> $OUTROOT ==="
echo "score:  .venv/bin/python scripts/canonical_az/solver_score.py --max-k 2 \\"
echo "          \$(for d in $OUTROOT/f*b*_s*/$VARIANT/ranknet_best.pt; do echo --arm-ckpt \$d; done) \\"
echo "          --workers 12 --out measurement/capacity_probe/solver_score_capacity.json"
