#!/usr/bin/env bash
# LOCAL launch. ⚠️ Share is /mnt/c/carc-shared locally (/mnt/carc-shared on the laptop).
# W=30 is OWNER-DIRECTED (2026-08-27, "local w30"); it is throughput-only —
# every unit is deterministic in (deck_seed, ply, world, arm), so results are
# bit-identical at any W.
set -u
REPO="${REPO:-/home/doctor/projects/carcassone/.claude/worktrees/agent-a93ae8ea54b24c9b6}"
export REPO
export BOX=local
export W="${W:-30}"
export SHARE=/mnt/c/carc-shared
export PY=/home/doctor/projects/carcassone/.venv/bin/python
export MEM_CAP_GB="${MEM_CAP_GB:-6}"
export ARM_CAP_S="${ARM_CAP_S:-1800}"
export THREADS="${THREADS:-1}"
export CHUNK="${CHUNK:-4}"
export SUFFIX="${SUFFIX:-}"
D="$REPO/measurement/e4_continuation_20260828"
chmod +x "$D/run_continuation.sh"
mkdir -p "$D/logs"
# setsid + nohup: the harness's background flag is NOT enough — a Mac-sleep
# SIGHUP or a WSL VM teardown both kill a tty-attached child.
setsid nohup "$D/run_continuation.sh" \
    > "$D/logs/driver_local${SUFFIX}.out" 2>&1 < /dev/null &
disown
echo "LAUNCHED local W=$W suffix='${SUFFIX}' arm_cap=${ARM_CAP_S}s chunk=$CHUNK"
