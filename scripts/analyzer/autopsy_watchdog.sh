#!/usr/bin/env bash
# On-box (LAPTOP) watchdog for the E4 autopsy scoring run — armed by
# launch_autopsy_laptop.sh as a 10-min cron tick. Relaunches RUN_CMD.sh if the run
# died without a DONE/FAILED marker (e.g. VM teardown). A python exception writes
# FAILED_AUTOPSY (rc!=0), which STOPS relaunches — only markerless deaths are retried,
# capped at 3 attempts so a systematic crash cannot loop forever.
# The scoring driver resumes from existing ok=true records; ok=false records from a
# crashed attempt are left for manual triage (clearing them mid-loop could mask a
# systematic failure — DESIGN.md §7).
set -u
REPO=/home/doctor/projects/carcassone
AUT="$REPO/measurement/e4_autopsy_20260812"
LOG="$AUT/logs/watchdog.log"
mkdir -p "$AUT/logs"

exec 9>"$AUT/logs/watchdog.lock"
flock -n 9 || exit 0                                   # overlapping tick

[ -f "$AUT/DONE_AUTOPSY" ] && exit 0
[ -f "$AUT/FAILED_AUTOPSY" ] && exit 0
[ -x "$AUT/RUN_CMD.sh" ] || exit 0                     # nothing launched yet
pgrep -f "scripts/analyzer/run_autopsy.py" >/dev/null && exit 0   # alive

n=$(cat "$AUT/logs/relaunch_count" 2>/dev/null || echo 0)
if [ "$n" -ge 3 ]; then
  echo "$(date -Is) relaunch cap (3) hit — manual intervention needed" >> "$LOG"
  exit 0
fi
echo $((n + 1)) > "$AUT/logs/relaunch_count"
echo "$(date -Is) run dead without marker — relaunching (attempt $((n + 1))/3)" >> "$LOG"
nohup systemd-run --user --scope -p MemoryMax=8G bash "$AUT/RUN_CMD.sh" \
  >> "$AUT/logs/scope.log" 2>&1 < /dev/null &
disown
