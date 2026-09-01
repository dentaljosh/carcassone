#!/usr/bin/env bash
# Selftests for the DEFENSE-PRIMARY census + accrual check. Path-stable.
set -euo pipefail
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=/home/doctor/projects/carcassone/.venv/bin/python
cd "$WT"
export PYTHONPATH="$WT/src:$WT/engine:$WT/scripts"
export OMP_NUM_THREADS=1
exec nice -n 19 "$PY" -m pytest "$WT/measurement/defense_primary_prep/test_defense_primary.py" "$@"
