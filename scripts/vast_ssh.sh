#!/bin/bash
# Look up a vast.ai instance's CURRENT ssh_host/ssh_port and connect.
# Avoids the "I cached ssh8 but vast.ai shifted us to ssh6" pain point from
# the 2026-05-12 bootstrap. Always re-reads vastai show instance --raw, so
# port/host shifts under your feet are handled.
#
# Usage:
#   scripts/vast_ssh.sh <instance_id>                       # interactive shell
#   scripts/vast_ssh.sh <instance_id> <remote_command>      # run command + exit
#   scripts/vast_ssh.sh <instance_id> -- scp /local root@%%:/remote   # scp form
#
# %% is a placeholder for the dynamically-resolved `root@<host>:<port>` string.
# Useful for scp where you want the resolved address inline.
#
# Env knobs:
#   VAST_SSH_KEY=~/.ssh/vast    private key (default)
#   VAST_SSH_OPTS=...           extra ssh args
set -eo pipefail

INSTANCE_ID="${1:?Usage: $0 <instance_id> [command...]}"
shift || true

KEY="${VAST_SSH_KEY:-$HOME/.ssh/vast}"
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${VAST_SSH_OPTS:-}"

# Re-read host/port from vastai EVERY time. Never cache.
HOST_PORT=$(vastai show instance "$INSTANCE_ID" --raw 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
host = d.get('ssh_host')
port = d.get('ssh_port')
status = d.get('actual_status')
if not host or not port:
    print(f'ERROR: instance not ready (actual_status={status}, ports={list(d.get(\"ports\",{}).keys())})', file=sys.stderr)
    sys.exit(1)
print(f'{host} {port}')
")

HOST=$(echo "$HOST_PORT" | awk '{print $1}')
PORT=$(echo "$HOST_PORT" | awk '{print $2}')

if [ -z "$HOST" ] || [ -z "$PORT" ]; then
    echo "ERROR: failed to resolve ssh_host/ssh_port for instance $INSTANCE_ID" >&2
    exit 1
fi

# If first remaining arg is --, treat the rest as a literal command with %%
# placeholder for the resolved root@host:port string.
if [ "${1:-}" = "--" ]; then
    shift
    cmd_template="$*"
    cmd_resolved="${cmd_template//%%/root@${HOST}:${PORT}}"
    eval "$cmd_resolved"
    exit $?
fi

if [ $# -eq 0 ]; then
    # Interactive shell
    exec ssh -i "$KEY" $OPTS -p "$PORT" "root@$HOST"
else
    # Run command and exit
    exec ssh -i "$KEY" $OPTS -p "$PORT" "root@$HOST" "$@"
fi
