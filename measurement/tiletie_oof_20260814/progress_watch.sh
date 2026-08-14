#!/usr/bin/env bash
# Monitor feed: emits one line per chunk completion, plus a loud line on death.
M=/home/doctor/projects/carcassone/.claude/worktrees/agent-a1badefaaed4b6d69/measurement/tiletie_oof_20260814
last=""
while true; do
  if [ -f "$M/DONE_MAIN" ]; then
    echo "MAIN READ DONE -- all chunks complete"
    exit 0
  fi
  cur=$(ls "$M"/DONE_CHUNK* 2>/dev/null | wc -l)
  n=$(ls /mnt/c/carc-shared/tiletie_oof_20260814/chunk*/tier1-greedy/*/leg*/records/*.json 2>/dev/null | wc -l)
  if [ "$cur" != "$last" ]; then
    echo "chunk progress: $cur/4 chunks done, $n/1033 leg records"
    last=$cur
  fi
  alive=0
  pgrep -f "tiletie_oof_20260814/run_main.sh" > /dev/null 2>&1 && alive=1
  pgrep -f "tiletie_oof_20260814/watchdog.sh" > /dev/null 2>&1 && alive=1
  if [ "$alive" -eq 0 ]; then
    echo "MAIN READ DIED and the watchdog is gone -- $cur/4 chunks, $n/1033 records"
    tail -6 "$M/logs/main_driver.log" 2>/dev/null
    exit 1
  fi
  sleep 60
done
