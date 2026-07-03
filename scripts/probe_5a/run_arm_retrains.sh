#!/usr/bin/env bash
# Probe §5A arm RETRAINS with --save-model — the CL-040 fold-in re-adjudication prep.
# Retrains the 4 CL-040 arms x seeds {0,1,2} so each RankNet is PERSISTED
# (<out>/V4_listwise/ranknet_best.pt) and can be scored NON-CIRCULARLY against the
# exact K<=4 solver via scripts/canonical_az/solver_score.py --arm-ckpt.
#
# STRICTLY SEQUENTIAL / SOLO by design: the 4x4 seedsweep at concurrency-4
# OOM-killed the 41GB WSL VM (PROBE_5A_RESULTS.md — 32GB obs page cache + 4
# training procs). One training at a time = page cache + 1 proc. GPU assumed
# FREE when this runs (do NOT launch while the rs-sweep owns it).
#
# Priority order: tempo_only seeds first, then both, all_three, none — so a
# partial run still answers the headline question (is tempo's +44.7% real
# under the solver ruler?).
#
# Resumable: a run is skipped iff its ranknet_best.pt already exists.
#
# Usage (detached — Mac-sleep/WSL-teardown kills tty-attached jobs):
#   mkdir -p measurement/probe_5a/arms_retrain
#   nohup bash scripts/probe_5a/run_arm_retrains.sh \
#     > measurement/probe_5a/arms_retrain/launcher.log 2>&1 & disown
set -uo pipefail   # NOT -e: one run failing must not abort the rest
cd /home/doctor/projects/carcassone

# tempo_resid.npz = the 10-core gate-zero survivor block — what the CL-040 arms
# actually trained on (n_scalar=54; see measurement/probe_5a_arms.log).
TEMPO="${1:-/home/doctor/carc_step1_gate/tempo_5a/tempo_resid.npz}"
OUTROOT="${2:-measurement/probe_5a/arms_retrain}"
VARIANT=V4_listwise
DS=/home/doctor/carc_step1_gate/dataset_both
PY=.venv/bin/python
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # GPU-frag guard (§4A lesson)
# Same args run_arms.sh used per arm, + --save-model (--seed added per run below).
COMMON="--dataset $DS --tempo-npz $TEMPO --variant $VARIANT --groups-per-batch 8 --save-model"
mkdir -p "$OUTROOT"

declare -A FLAGS=(
  [tempo_only]="--drop-farm --drop-bag"
  [both]="--drop-tempo"
  [all_three]=""
  [none]="--drop-farm --drop-bag --drop-tempo"
)

echo "[eta] 12 sequential runs (4 arms x 3 seeds): inert/early-stop arms ~15m, live tempo arms ~60-75m (2026-07-01 arms-run wallclocks) -> total ~6-9h"

run_one () {  # arm seed
  local arm=$1 seed=$2
  local out="$OUTROOT/${arm}_s${seed}"
  local ckpt="$out/$VARIANT/ranknet_best.pt"
  local log="$OUTROOT/${arm}_s${seed}.log"
  if [ -f "$ckpt" ]; then
    echo "=== SKIP $arm s$seed (exists: $ckpt) ==="
    return 0
  fi
  echo "=== ARM $arm seed $seed $(date +%F_%H:%M:%S) — ETA ~15m if inert/early-stop, ~60-75m if live -> $log ==="
  # shellcheck disable=SC2086
  nice -n 19 $PY scripts/feature_planes_gate/step1_train.py $COMMON \
    --seed "$seed" --out "$out" ${FLAGS[$arm]} > "$log" 2>&1
  local rc=$?
  if [ -f "$ckpt" ]; then
    echo "    OK $arm s$seed (rc=$rc) -> $ckpt"
  else
    echo "    FAIL $arm s$seed (rc=$rc) — no ranknet_best.pt; see $log"
  fi
}

# NOTE: do NOT drop page cache between runs — every run reads the SAME 32GB obs
# memmap; keeping it cached across runs is the speedup, not a leak.
for arm in tempo_only both all_three none; do
  for seed in 0 1 2; do
    run_one "$arm" "$seed"
  done
done

echo "=== all retrains done -> $OUTROOT ==="
echo "score:  .venv/bin/python scripts/canonical_az/solver_score.py --max-k 2 \\"
echo "          \$(for d in $OUTROOT/*_s*/$VARIANT/ranknet_best.pt; do echo --arm-ckpt \$d; done) \\"
echo "          --workers 8 --out measurement/probe_5a/arms_retrain/solver_score_k2.json"
