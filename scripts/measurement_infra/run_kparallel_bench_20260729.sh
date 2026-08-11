#!/usr/bin/env bash
# One-shot driver for the 2026-07-29 quiet-window k-parallel latency bench.
# Exists because the harness-launched form died with a session restart mid-run:
# this is exec'd under setsid so the python reparents to init (PPID 1) and
# survives SIGHUP from the Mac->Windows->WSL chain.
set -euo pipefail
REPO=/home/doctor/projects/carcassone
OUT="$REPO/measurement/kparallel_bench_20260729"
mkdir -p "$OUT"
exec "$REPO/.venv/bin/python" -u \
  "$REPO/scripts/measurement_infra/kparallel_latency_bench.py" \
  --out "$OUT" >"$OUT/run.log" 2>&1 </dev/null
