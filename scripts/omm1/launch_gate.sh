#!/usr/bin/env bash
# OM-M1 — detached launcher for the kill-gate run (the only compute-buying step).
#
# Detached with setsid because a Mac-sleep SIGHUP or a WSL VM teardown kills any
# tty-attached job (CLAUDE.md); `run_in_background` alone is not enough.
#
# Usage: scripts/omm1/launch_gate.sh [workers] [stride]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$HERE/env.sh"

W="${1:-30}"
STRIDE="${2:-1}"
LOG="$LOGDIR/gate_run.log"

{
  echo "==================================================================="
  echo " OM-M1 REFUTER-LEG KILL-GATE — stage 1 (four legs, B=64)"
  echo " spec       : measurement/omm1_refuter_gate_20260830/PREREG.md"
  echo " started    : $(date -u '+%Y-%m-%dT%H:%M:%SZ')  ($(TZ=America/New_York date '+%H:%M EDT'))"
  echo " ABORT BY   : 2026-08-31T04:15:00Z (00:15 EDT) — the next round claims"
  echo "              the LOCAL box then. If this is still running at that time"
  echo "              it must be killed cleanly:  kill -TERM -<PGID>"
  echo " box        : LOCAL only. The laptop arm of S1 G3 is still live — do"
  echo "              NOT touch the laptop."
  echo " workers    : $W (nice -19)"
  echo " bitexact   : every ${STRIDE} frame row"
  echo " wheel      : $OMM1_WHEEL_SHA256"
  echo "              $OMM1_WHEEL_FILE"
  echo "              SHADOW install ($SP/pyext_rel) — the venv wheel is UNTOUCHED"
  echo " frame      : $OUT/FIRED_PLIES.jsonl"
  echo " out        : $OUT/LEGS"
  echo " DONE signal: $OUT/LEGS/DONE  (written LAST, only on a complete run)"
  echo " ⛔ DO NOT ADJUDICATE HERE. The prereg'd read (§6) happens at the"
  echo "    orchestrator level via scripts/omm1/analyze_gate.py."
  echo "==================================================================="
} > "$LOG"

cd "$WT"
setsid nohup nice -n 19 "$VENV/bin/python" "$HERE/run_gate.py" \
    --frame "$OUT/FIRED_PLIES.jsonl" \
    --out-dir "$OUT/LEGS" \
    --workers "$W" \
    --bitexact-stride "$STRIDE" \
    --b 64 >> "$LOG" 2>&1 < /dev/null &

PGID=$!
echo "launched pid/pgid $PGID; log $LOG"
echo " pid/pgid   : $PGID" >> "$LOG"
