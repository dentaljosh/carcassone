#!/usr/bin/env bash
# G-PIN runner (path-stable; does its own `cd`, absolute python).
set -euo pipefail
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=/home/doctor/projects/carcassone/.venv/bin/python
cd "$WT"
export PYTHONPATH="$WT/src:$WT/engine:$WT/scripts"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
exec nice -n 19 "$PY" "$WT/measurement/defense_primary_prep/verify_pin.py" "$@"
