#!/usr/bin/env bash
# STEP 3 — the offline verdict. One solver pass over the 1,119 exact K<=2
# marginalized h6400_v2.9 sibling roots; four rankers scored on the SAME solves:
#   v29_leaf (harness baseline, curve100) | curve125 (the CHAMPION's leaf)
#   iter_03 (CL-067 warm parent value head, the control) | value_unlock_v1 (this run)
# Metric + bar are PRE-REGISTERED in READOUT.md §3 (committed before this ran).
# MEASUREMENT ONLY. Pure CPU (the harness masks CUDA at import).
set -euo pipefail
REPO=/home/doctor/projects/carcassone
OUT=/home/doctor/projects/carcassone/measurement/value_unlock_20260730
cd "$REPO"
nice -n 19 "$REPO/.venv/bin/python" -u scripts/canonical_az/solver_score.py \
  --max-k 2 --workers "${W:-16}" \
  --leaf-variant 'curve125:{"V29_MEEPLE_CURVE":"-8,-4,-1,0,2.5,3.75,5,6.25"}' \
  --checkpoint /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
  --checkpoint /mnt/c/carc-shared/value_unlock_20260730/ckpt/value_unlock_v1.pt \
  --out "$OUT/solver_score_value_unlock.json"
echo "=== run_ruler DONE rc=$? @ $(date) ==="
