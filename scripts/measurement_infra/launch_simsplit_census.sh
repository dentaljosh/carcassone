#!/usr/bin/env bash
# Launcher: sims-split PRE-GATE census, full 898-root run (0 games, no band consumed).
# Prereg: measurement/simsplit_census_20260811/PREREG.md  — review it BEFORE launching.
# Detach-safe (nohup + disown: survives Mac-sleep SIGHUP / tty teardown), nice -n 19.
# ETA: ~3-5 min at W14 on the local 5900XT, rust backend (smoke-measured 2.76 s/root mean).
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # repo root (worktree-safe)

VENV="${VENV:-/home/doctor/projects/carcassone/.venv}"
OUT="measurement/simsplit_census_20260811"
W="${W:-14}"
TAG="${TAG:-main}"
mkdir -p "$OUT"

# PYTHONPATH prefix: run THIS tree's code even when the venv is editable-installed
# against the main tree (worktree-isolation rule).
nohup nice -n 19 env PYTHONPATH="$PWD/src:$PWD/engine" \
    "$VENV/bin/python" -u scripts/measurement_infra/simsplit_census.py \
    --workers "$W" --determinism-every 1 --tag "$TAG" --out-dir "$OUT" \
    >> "$OUT/census_${TAG}.log" 2>&1 &
PID=$!
disown
echo "[simsplit-launcher] pid $PID -> $OUT/census_${TAG}.log (W=$W, tag=$TAG)"
echo "[simsplit-launcher] outputs: $OUT/{rows,summary,manifest}_${TAG}.*"
