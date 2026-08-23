#!/bin/bash
# b32v64 on-disk watchdog — OBSERVE ONLY, never restarts (auto-restart strands
# claims; the orchestrator handles resume with the claims-without-records sweep).
# Appends one line every 5 min: timestamp, launcher liveness, record counts.
# Usage: setsid nohup ./cell_watchdog.sh <local|laptop-side> <share_run_dir> >> <log> 2>&1 &
ROLE="$1"; SHARE_RUN="$2"
while true; do
  TS=$(date -u +%FT%TZ)
  ALIVE=$(pgrep -c -f "run_cells.sh $ROLE" || true)
  LO=$(find "$SHARE_RUN"/b32v64_B32J4_deploy11008 -name 'seed*.json' 2>/dev/null | wc -l)
  HI=$(find "$SHARE_RUN"/b32v64_B64J4_deploy11008 -name 'seed*.json' 2>/dev/null | wc -l)
  echo "[$TS $ROLE] launcher_procs=$ALIVE B32_records=$LO B64_records=$HI"
  if [ "$ALIVE" -eq 0 ]; then
    echo "[$TS $ROLE] ⚠️ LAUNCHER DEAD — NOT restarting (observe-only); orchestrator must sweep claims-without-records before any resume"
  fi
  sleep 300
done
