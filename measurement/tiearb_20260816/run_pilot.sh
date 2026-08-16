#!/usr/bin/env bash
# DESIGN §5 cost pilot -- the OOF run's own 20 DEV rids, EXCLUDED from every read.
#
# Reads ONLY wall/elapsed/integrity and the G-REPRO bit-reproduction count.
# It does NOT read values_a, values_b, per_world_delta, mean_a, mean_b, delta,
# any sd, or any statistic derived from them.
#
# Runs in the MAIN TREE (the box was censused idle and reserved).
set -euo pipefail
W=/home/doctor/projects/carcassone
cd "$W"
M=$W/measurement/tiearb_20260816
PY=/home/doctor/projects/carcassone/.venv/bin/python
export CARC_SRC_ROOT=/home/doctor/projects/carcassone/src
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

mkdir -p "$M/logs"

nice -n 19 "$PY" scripts/tiletie/run_tiletie.py \
  --positions-dir "$M/positions_pilot" \
  --judges tier1-greedy \
  --workers 20 \
  --out-root /mnt/c/carc-shared/tiearb_20260816/pilot \
  --logs-dir "$M/logs" \
  --gate-out "$M/GATE_BACKEND_RECHECK_pilot.json" \
  --manifest-out "$M/RUN_MANIFEST_pilot.json" \
  --yes
rc=$?
echo "pilot rc=$rc"
touch "$M/DONE_PILOT"
exit $rc
