#!/usr/bin/env bash
# microgates driver. Usage: run.sh <stage> [profile] [workers] [budget_s]
# One profile per process (R9 is import-latched). See PREREG.md §6.
set -euo pipefail
WT=/home/doctor/projects/carcassone/.claude/worktrees/agent-a7e4274d1451a32d9
D="$WT/measurement/microgates_20260828"
export PYTHONPATH="$WT/src:$WT/engine:$WT/scripts"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STAGE="${1:?stage}"
PROF="${2:-fixed_v1}"
W="${3:-8}"
BUDGET="${4:-0}"
exec nice -n 19 /home/doctor/projects/carcassone/.venv/bin/python "$D/microgates.py" \
    --stage "$STAGE" --out "$D/out" --profile "$PROF" \
    --workers "$W" --budget-s "$BUDGET" --json "$D/MICROGATES.json"
