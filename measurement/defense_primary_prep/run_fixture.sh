#!/usr/bin/env bash
# Regenerate the pytest fixtures from the real emitters. Path-stable.
set -euo pipefail
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=/home/doctor/projects/carcassone/.venv/bin/python
cd "$WT"
export PYTHONPATH="$WT/src:$WT/engine:$WT/scripts"
export OMP_NUM_THREADS=1
exec nice -n 19 "$PY" "$WT/measurement/defense_primary_prep/make_fixture.py" "$@"
