#!/usr/bin/env bash
# Clean 5900XT single-stream champion reference — the denominator the M5 read-out
# says is "owed" (its local rows were taken under the CL-067 gate at loadavg ~13).
#
# Same bundle, same 60 positions, same budgets and --repeat 3 as the M5 run, and
# the SAME CPython the earlier local rows used: the bundle's Cython .so files are
# built for cpython-313, so the repo venv (3.12) would silently fall back to the
# pure-Python leaf and produce a ~4.5x-inflated, non-comparable number.
set -euo pipefail
M5=/mnt/c/carc-shared/m5_bench_20260728
OUT=/home/doctor/projects/carcassone/measurement/m5_bench_20260728
exec "$M5/.venv/bin/python3.13" "$M5/bench_champion.py" \
  --budgets k1x32,k4x172,k4x344,k4x688 \
  --repeat 3 \
  --tag clean_5900XT_quiet_window_20260729 \
  --out "$OUT/bench_champion_5900XT_CLEAN_20260729.json" \
  >"$OUT/bench_champion_5900XT_CLEAN_20260729.log" 2>&1 </dev/null
