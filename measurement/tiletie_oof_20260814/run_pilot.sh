#!/usr/bin/env bash
# DESIGN §6 cost pilot -- 20 dev positions, EXCLUDED from the main read.
# Reads ONLY wall/elapsed/integrity. No value, no mean, no sd.
set -euo pipefail
W=/home/doctor/projects/carcassone/.claude/worktrees/agent-a1badefaaed4b6d69
cd "$W"
M=$W/measurement/tiletie_oof_20260814
PY=/home/doctor/projects/carcassone/.venv/bin/python
export CARC_SRC_ROOT=/home/doctor/projects/carcassone/src   # main tree: has the cy .so
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

nice -n 19 "$PY" scripts/tiletie/run_tiletie.py \
  --positions-dir "$M/positions_pilot" \
  --judges tier1-greedy \
  --workers 20 \
  --out-root /mnt/c/carc-shared/tiletie_oof_20260814/pilot \
  --logs-dir "$M/logs" \
  --gate-out "$M/GATE_BACKEND_RECHECK_pilot.json" \
  --manifest-out "$M/RUN_MANIFEST_pilot.json" \
  --yes
rc=$?
echo "pilot rc=$rc"
touch "$M/DONE_PILOT"
exit $rc
