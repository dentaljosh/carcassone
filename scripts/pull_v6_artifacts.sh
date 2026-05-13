#!/bin/bash
# Pull v6 cloud-run artifacts from the rented box to local repo.
# Usage:
#   scripts/pull_v6_artifacts.sh <instance_id>
#
# Pulls (rsync):
#   - data/selfplay/v6_cloud/   → local data/selfplay/v6_cloud/
#   - checkpoints/selfplay_v6/  → local checkpoints/selfplay_v6/
#   - /tmp/phase4_v6.log        → local data/selfplay/v6_cloud/cloud.log
#
# Does NOT destroy the box — destruction is a manual final step after
# you've sanity-checked the local artifacts.
#
# Re-runnable: rsync skips unchanged files, so mid-run pulls are safe
# and fast (only new iter dirs + new checkpoint files transferred).

set -eo pipefail

INSTANCE_ID="${1:?Usage: $0 <instance_id>}"
REPO_ROOT="${REPO_ROOT:-/home/doctor/projects/carcassone}"
SSH_KEY="${VAST_SSH_KEY:-$HOME/.ssh/vast}"

# Re-read host/port from vast every time (never cache — they shift).
read -r HOST PORT < <(vastai show instance "$INSTANCE_ID" --raw | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d['ssh_host'], d['ssh_port'])
")

echo "=== pull v6 artifacts from instance $INSTANCE_ID ($HOST:$PORT) ==="
echo

SSH_OPTS=(-i "$SSH_KEY" -p "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
# scp uses -P for port (ssh uses -p); separate array to avoid the conflict.
SCP_OPTS=(-i "$SSH_KEY" -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
RSYNC_OPTS=(-avz --partial --progress -e "ssh ${SSH_OPTS[*]}")

mkdir -p "$REPO_ROOT/data/selfplay" "$REPO_ROOT/checkpoints"

echo "--- data/selfplay/v6_cloud/ ---"
rsync "${RSYNC_OPTS[@]}" \
    "root@$HOST:/workspace/carcassone/data/selfplay/v6_cloud/" \
    "$REPO_ROOT/data/selfplay/v6_cloud/"

echo
echo "--- checkpoints/selfplay_v6/ ---"
rsync "${RSYNC_OPTS[@]}" \
    "root@$HOST:/workspace/carcassone/checkpoints/selfplay_v6/" \
    "$REPO_ROOT/checkpoints/selfplay_v6/"

echo
echo "--- /tmp/phase4_v6.log → cloud.log ---"
scp "${SCP_OPTS[@]}" \
    "root@$HOST:/tmp/phase4_v6.log" \
    "$REPO_ROOT/data/selfplay/v6_cloud/cloud.log"

echo
echo "=== sanity check ==="
n_iter_dirs=$(ls -d "$REPO_ROOT"/data/selfplay/v6_cloud/iter_* 2>/dev/null | wc -l)
n_ckpts=$(ls "$REPO_ROOT"/checkpoints/selfplay_v6/iter_*.pt 2>/dev/null | wc -l)
anchor_log="$REPO_ROOT/data/selfplay/v6_cloud/anchor_gate_log.json"
echo "  iter dirs pulled: $n_iter_dirs"
echo "  checkpoints pulled: $n_ckpts"
if [ -f "$anchor_log" ]; then
    n_anchor=$(python3 -c "import json; print(len(json.load(open('$anchor_log'))))")
    echo "  anchor-gate entries: $n_anchor"
fi
echo
echo "=== DONE ==="
echo "Next: review locally, then destroy box manually:"
echo "  echo y | vastai destroy instance $INSTANCE_ID"
