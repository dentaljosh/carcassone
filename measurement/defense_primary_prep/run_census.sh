#!/usr/bin/env bash
# DEFENSE-PRIMARY census runner. Path-stable: does its own `cd`, absolute python.
#
#   run_census.sh classify        [extra args...]
#   run_census.sh counterfactual  [extra args...]
#
# Worktree discipline: PYTHONPATH points at THIS tree (the venv is editable-
# installed against the main tree); the census records the resolved
# `carcassonne_ai.__file__` in its manifest so the reader never has to guess.
set -euo pipefail

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=/home/doctor/projects/carcassone/.venv/bin/python
STAGE="$1"; shift

cd "$WT"
export PYTHONPATH="$WT/src:$WT/engine:$WT/scripts"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

exec nice -n 19 "$PY" "$WT/measurement/defense_primary_prep/census_new_plies.py" \
    --stage "$STAGE" "$@"
