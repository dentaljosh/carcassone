#!/usr/bin/env bash
# On-disk watchdog for the OOF main read (auto-memory: session heartbeats die with
# the session; overnight detached runs need a watchdog ARMED ON THE BOX).
# Restarts the chain if it is neither DONE nor alive. Idempotent: run_main.sh
# skips DONE chunks and run_tiletie --resume skips existing records/<rid>.json.
set -uo pipefail
M=/home/doctor/projects/carcassone/.claude/worktrees/agent-a1badefaaed4b6d69/measurement/tiletie_oof_20260814
LOG=$M/logs/watchdog.log
MAX_RESTARTS=${MAX_RESTARTS:-6}
n=0
while true; do
  if [ -f "$M/DONE_MAIN" ]; then
    echo "$(date -Is) DONE_MAIN present -- watchdog exiting" >> "$LOG"
    exit 0
  fi
  if ! pgrep -f "tiletie_oof_20260814/run_main.sh" > /dev/null 2>&1 \
     && ! pgrep -f "positions_chunk" > /dev/null 2>&1; then
    if [ "$n" -ge "$MAX_RESTARTS" ]; then
      echo "$(date -Is) chain dead and restart budget ($MAX_RESTARTS) spent -- giving up" >> "$LOG"
      exit 1
    fi
    n=$((n + 1))
    echo "$(date -Is) chain DEAD, restart #$n" >> "$LOG"
    setsid nohup "$M/run_main.sh" >> "$M/logs/main_driver.log" 2>&1 < /dev/null &
  fi
  sleep 120
done
