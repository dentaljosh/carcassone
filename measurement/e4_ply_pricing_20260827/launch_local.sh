#!/usr/bin/env bash
# LOCAL launch. ⚠️ Share is /mnt/c/carc-shared locally (/mnt/carc-shared on the laptop).
set -u
REPO="${REPO:-/home/doctor/projects/carcassone/.claude/worktrees/agent-ae2b24ec0bffecafe}"
export REPO
export BOX=local
export W="${W:-14}"
export SHARE=/mnt/c/carc-shared
export PY=/home/doctor/projects/carcassone/.venv/bin/python
export MEM_CAP_GB="${MEM_CAP_GB:-8}"
export TIME_CAP_S="${TIME_CAP_S:-1800}"
export THREADS="${THREADS:-1}"
D="$REPO/measurement/e4_ply_pricing_20260827"
chmod +x "$D/run_pricing.sh"
mkdir -p "$D/logs"
# setsid + nohup: run_in_background alone is NOT enough (Mac-sleep SIGHUP / WSL
# VM teardown both kill a tty-attached child).
setsid nohup "$D/run_pricing.sh" "$D/shards_local.txt" \
    > "$D/logs/driver_local.out" 2>&1 < /dev/null &
disown
echo "LAUNCHED local W=$W"
