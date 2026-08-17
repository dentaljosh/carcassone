#!/usr/bin/env bash
# watch_main.sh — completion/death watcher for the MAIN SCORING run.
#
# Emits ONE line and exits. Silence is not success: it fires on BOTH the success
# marker AND on both-boxes-dead-without-it, so a crashloop cannot look like
# "still running".
#
# Success  = DONE_LOCAL_SHIFT (local chain finished its clair-puct 1-4 + tier1 #4)
#            AND DONE_tier1-greedy_laptop-side (laptop finished chunks 1-3).
# Death    = neither box has a scoring process and the markers are not both there.
#
# (This box reads the share at /mnt/c/carc-shared; the ssh'd laptop reads it at
#  /mnt/carc-shared. This script only ever counts records on the LOCAL path.)
HERE="$(cd "$(dirname "$0")" && pwd)"
SHARE=/mnt/c/carc-shared/tiearb2_20260816/main
OK_LOCAL="$HERE/DONE_LOCAL_SHIFT"
OK_LAPTOP="$HERE/DONE_tier1-greedy_laptop-side"

while true; do
  recs=$(find "$SHARE" -path '*/records/*.json' 2>/dev/null | wc -l)
  loc=$(pgrep -fc oracle_score_pilot 2>/dev/null || echo 0)
  rem=$(timeout 45 ssh laptop 'pgrep -fc oracle_score_pilot || echo 0' 2>/dev/null | tr -d '\r')
  [ -z "$rem" ] && rem="?"

  if [ -f "$OK_LOCAL" ] && [ -f "$OK_LAPTOP" ]; then
    echo "MAIN-COMPLETE records=$recs both DONE markers present"
    exit 0
  fi

  # both boxes idle and not finished => dead. '?' (ssh failed) is NOT treated as
  # idle: an unreachable laptop must not be mistaken for a finished one.
  if [ "$loc" -le 1 ] && [ "$rem" = "0" ]; then
    echo "MAIN-DIED-BOTH-IDLE records=$recs local=$loc laptop=$rem localDone=$([ -f "$OK_LOCAL" ] && echo Y || echo N) laptopDone=$([ -f "$OK_LAPTOP" ] && echo Y || echo N)"
    exit 1
  fi

  sleep 180  # allow-sleep: the monitor's own poll interval, not a foreground block
done
