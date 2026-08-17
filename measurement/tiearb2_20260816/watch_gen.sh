#!/usr/bin/env bash
# watch_gen.sh — completion/death watcher for PHASE 1 (self-play generation).
# Emits ONE line and exits: either the target is reached, or BOTH boxes are dead.
# Silence is not success: the death branch is what makes this monitor honest.
# (Local reads the share at /mnt/c/carc-shared; the ssh'd laptop reads it at
#  /mnt/carc-shared — this script only ever counts on the LOCAL path.)
GEN=/mnt/c/carc-shared/tiearb2_20260816/gen/actions
TARGET=850
while true; do
  n=$(ls "$GEN" 2>/dev/null | wc -l)
  loc=$(pgrep -fc gen_fair_distill 2>/dev/null || echo 0)
  rem=$(timeout 30 ssh laptop 'pgrep -fc gen_fair_distill || echo 0' 2>/dev/null | tr -d '\r')
  [ -z "$rem" ] && rem="?"
  if [ "$n" -ge "$TARGET" ]; then
    echo "GEN-COMPLETE shards=$n target=$TARGET"
    exit 0
  fi
  if [ "$loc" -le 1 ] && { [ "$rem" = "0" ] || [ "$rem" = "1" ]; }; then
    echo "GEN-DIED-BOTH-BOXES shards=$n target=$TARGET local=$loc laptop=$rem"
    exit 1
  fi
  sleep 120  # allow-sleep: this is the monitor's own poll interval, not a foreground block
done
