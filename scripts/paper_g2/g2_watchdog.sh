#!/usr/bin/env bash
# ON-DISK watchdog for the detached G2 training chain.
#
# The session heartbeat dies with the session (memory
# feedback_hourly_heartbeat_for_background_runs cost ~5h on 2026-07-28), and this
# box has a dirty-reboot history (memory reference_local_box_dirty_reboots). This
# watchdog is the second layer: it re-launches the chain if it is not running and
# not finished, and appends a heartbeat line either way. run_g2_chain.sh is
# idempotent (--resume + skip-if-final.pt), so a spurious relaunch costs nothing.
#
# Arm it from cron (or just leave it running under setsid):
#   setsid nohup .../g2_watchdog.sh > /dev/null 2>&1 < /dev/null &
set -uo pipefail
WT="${G2_TREE:-/home/doctor/projects/carcassone/.claude/worktrees/agent-a1860cb7f9dc6f899}"
OUT=/mnt/c/carc-shared/paper_g2_20260803
HB="$OUT/watchdog.log"
INTERVAL="${G2_WATCHDOG_INTERVAL:-900}"

mkdir -p "$OUT"
while true; do
  ts="$(date -Is)"
  if [ -f "$OUT/tf_large/final.pt" ]; then
    echo "$ts COMPLETE (tf_large/final.pt present) — watchdog exiting" >> "$HB"
    exit 0
  fi
  if pgrep -f "paper_g2/train_g2.py" > /dev/null; then
    prog=$(for a in resnet_scratch tf_match tf_large; do
             n=$(ls "$OUT/$a"/epoch_*.pt 2>/dev/null | wc -l); echo -n "$a=$n "; done)
    echo "$ts RUNNING  $prog" >> "$HB"
  else
    echo "$ts NOT RUNNING and not complete — relaunching chain" >> "$HB"
    setsid nohup "$WT/scripts/paper_g2/run_g2_chain.sh" \
      >> "$OUT/chain.log" 2>&1 < /dev/null &
  fi
  sleep "$INTERVAL"   # allow-sleep (watchdog daemon, not a session poll)
done
