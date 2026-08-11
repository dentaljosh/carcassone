#!/usr/bin/env bash
# Pulls retrain artifacts from a vast.ai instance, then destroys it.
# Usage:
#   scripts/cloud_pull_destroy.sh <instance_id> <ssh_port> <ssh_host> <run_name>
# Example:
#   scripts/cloud_pull_destroy.sh 36800338 10338 ssh9.vast.ai v25_retrain
#
# Assumes ~/.ssh/vast is the private key.
# Pulls /workspace/carcassone/checkpoints/<run_name>/ and
#       /workspace/carcassone/data/selfplay/<run_name>/
# back into the local repo. Also grabs /tmp/<run_name>.log into the data dir.
# Idempotent: rsync overwrites; warnings on partial pulls are reported but
# do not fail the script.
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <instance_id> <ssh_port> <ssh_host> <run_name>" >&2
  exit 2
fi

INSTANCE_ID="$1"
SSH_PORT="$2"
SSH_HOST="$3"
RUN_NAME="$4"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_CKPT="$REPO_ROOT/checkpoints/$RUN_NAME"
LOCAL_DATA="$REPO_ROOT/data/selfplay/$RUN_NAME"
mkdir -p "$LOCAL_CKPT" "$LOCAL_DATA"

SSH_OPTS=(-i ~/.ssh/vast -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new)

echo "=== pulling checkpoints from $SSH_HOST:$SSH_PORT ==="
rsync -avz -e "ssh ${SSH_OPTS[*]} -p $SSH_PORT" \
  "root@$SSH_HOST:/workspace/carcassone/checkpoints/$RUN_NAME/" \
  "$LOCAL_CKPT/" || echo "WARN: ckpt rsync had issues"

echo "=== pulling self-play data ==="
rsync -avz -e "ssh ${SSH_OPTS[*]} -p $SSH_PORT" \
  "root@$SSH_HOST:/workspace/carcassone/data/selfplay/$RUN_NAME/" \
  "$LOCAL_DATA/" || echo "WARN: data rsync had issues"

echo "=== pulling log ==="
scp "${SSH_OPTS[@]}" -P "$SSH_PORT" \
  "root@$SSH_HOST:/tmp/${RUN_NAME}.log" \
  "$LOCAL_DATA/cloud.log" || echo "WARN: log scp had issues"

echo "=== destroying instance $INSTANCE_ID ==="
echo "y" | vastai destroy instance "$INSTANCE_ID"
echo "=== BOX DESTROYED ==="
