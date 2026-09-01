#!/usr/bin/env bash
# DEFENSE-PRIMARY accrual check — call this at EVERY E4 pull.
# Path-stable (does its own `cd`, absolute python). Exit: 0 FIRED / 1 not yet / 3 error.
set -uo pipefail
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=/home/doctor/projects/carcassone/.venv/bin/python
cd "$WT"
export PYTHONPATH="$WT/src:$WT/engine:$WT/scripts"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
nice -n 19 "$PY" "$WT/measurement/defense_primary_prep/accrual_check.py" "$@"
exit $?
