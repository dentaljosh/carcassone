#!/usr/bin/env bash
# Detached watchdog: polls a cloud retrain (process named PROC_PATTERN), and
# when it exits (success OR crash), pulls artifacts + destroys the instance.
# Designed to survive SSH disconnects per the CLAUDE.md SSH-resilience rule —
# launch with nohup + disown locally and let it run for the length of the
# cloud job.
#
# Usage:
#   nohup scripts/cloud_retrain_watchdog.sh \
#     <instance_id> <ssh_port> <ssh_host> <run_name> [proc_pattern] \
#     > /tmp/<run_name>_watchdog.log 2>&1 & disown
#
# Default proc_pattern is "run_phase4_smoke". Override to e.g. "run_selfplay_iter"
# if you ran the inner script directly.
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <instance_id> <ssh_port> <ssh_host> <run_name> [proc_pattern]" >&2
  exit 2
fi

INSTANCE_ID="$1"
SSH_PORT="$2"
SSH_HOST="$3"
RUN_NAME="$4"
PROC_PATTERN="${5:-run_phase4_smoke}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PULL_SCRIPT="$REPO_ROOT/scripts/cloud_pull_destroy.sh"
SSH_OPTS=(-i ~/.ssh/vast -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)

echo "watchdog started at $(date)"
echo "  instance=$INSTANCE_ID host=$SSH_HOST:$SSH_PORT run_name=$RUN_NAME"
echo "  watching for '$PROC_PATTERN' to exit"

while true; do
  status=$(ssh "${SSH_OPTS[@]}" -p "$SSH_PORT" "root@$SSH_HOST" \
    "pgrep -f \"$PROC_PATTERN\" >/dev/null && echo R || echo D" 2>/dev/null || echo "SSH_FAIL")
  ts=$(date '+%H:%M:%S')

  # Heartbeat: try to count generated game files (best-effort)
  count=$(ssh "${SSH_OPTS[@]}" -p "$SSH_PORT" "root@$SSH_HOST" \
    "ls /workspace/carcassone/data/selfplay/$RUN_NAME/iter_00/ 2>/dev/null | wc -l" 2>&1 \
    | tail -1)
  echo "$ts: status=$status games_done=$count"

  if [ "$status" = "D" ]; then
    echo "$ts: RETRAIN_DONE_OR_DEAD — pulling artifacts + destroying"
    ssh "${SSH_OPTS[@]}" -p "$SSH_PORT" "root@$SSH_HOST" \
      "tail -50 /tmp/${RUN_NAME}.log" || true
    "$PULL_SCRIPT" "$INSTANCE_ID" "$SSH_PORT" "$SSH_HOST" "$RUN_NAME"
    echo "$ts: === watchdog done ==="
    exit 0
  fi
  sleep 900  # 15-min heartbeat — small enough to catch finishes quickly,
             # big enough not to spam SSH or fight stop-hook intervals.
done
