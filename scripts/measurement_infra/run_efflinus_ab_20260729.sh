#!/usr/bin/env bash
# One-shot driver for the 2026-07-29 quiet-window eff_linus WSL-vs-native A/B.
# wsl_vs_native_ab.sh runs ~20 min in the foreground; this wrapper is exec'd under
# setsid so it reparents to init and survives the Mac->Windows->WSL SIGHUP chain
# (and a Claude session restart, which already killed one bench in this batch).
set -euo pipefail
REPO=/home/doctor/projects/carcassone
OUT="$REPO/measurement/eff_linus/run_20260729"
mkdir -p "$OUT"
exec "$REPO/scripts/measurement_infra/wsl_vs_native_ab.sh" \
  --out "$OUT" >"$OUT/driver.log" 2>&1 </dev/null
