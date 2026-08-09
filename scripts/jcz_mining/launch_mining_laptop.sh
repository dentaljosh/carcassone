#!/bin/bash
# JCZ DISAGREEMENT MINING — LOCAL-BOX ORCHESTRATOR for the LAPTOP run.
#
# Runs HERE, on the local box, and drives the laptop from a distance:
#   1. syncs code to the laptop via a git BUNDLE (the laptop cannot reach
#      github -- memory reference_offline_git_bundle_sync). STRATA.json /
#      POSITIONS*.jsonl are committed to git, so the bundle carries the
#      sampling frame WITH the code -- no separate scp needed.
#   2. VERIFIES the laptop's current HEAD is still an ancestor of the bundled
#      commit before fast-forwarding -- refuses loudly on any unexpected
#      divergence, NEVER `reset --hard` over it.
#   3. launches the repo's OWN scripts/jcz_mining/launch_mining.sh --box
#      laptop on the laptop, detached, so the worker-cap / process-gate /
#      memory-scope logic lives in exactly ONE place (this script duplicates
#      none of it).
#
# REMOTE-COMMAND RULE (memory feedback_remote_ssh_pipe_script_mandatory):
# every remote step is `ssh laptop-wsl 'bash -s' < script.sh` with `cd` as the
# FIRST command in that script -- NEVER an inline `ssh host 'cd X && ...'`
# (Claude Code silently strips the inline `cd` in transit). SSH calls are
# never run in parallel here; they execute one after another.
#
# rc=124 FROM THE FINAL (detached-launch) ssh CALL MEANS LAUNCHED, NOT FAILED
# (memory feedback_wsl_ssh_launch_pkill_traps) -- a bounded `timeout` wraps
# that call because a detached remote launch can hold the ssh channel open
# briefly even after the background job is fully detached; treat 124 as
# success and NEVER retry (a retry stacks a second pool on the laptop).
#
# Usage:
#   bash scripts/jcz_mining/launch_mining_laptop.sh [--dry-run]
#       [--workers 22] [--m 32] [--oracle-sims 100]
#
# --workers/--m/--oracle-sims are forwarded verbatim to the laptop's own
# launch_mining.sh --box laptop (which applies its own cap/clamp/gate; this
# script does not re-implement any of that).
set -euo pipefail

LOCAL_REPO=/home/doctor/projects/carcassone
LAPTOP_HOST=laptop-wsl
LAPTOP_REPO=/home/doctor/projects/carcassone      # same absolute path on both boxes
LOCAL_SHARE=/mnt/c/carc-shared                    # local box's mount of the share
LAPTOP_SHARE=/mnt/carc-shared                     # laptop's mount of the SAME share -- DIFFERENT PATH (the standing trap)
SYNC_SUBDIR=jcz_mining_20260809/sync
SSH_LAUNCH_TIMEOUT=30   # bounded wait on the detached-launch ssh call; rc=124 == LAUNCHED

WORKERS=22
M=32
ORACLE_SIMS=100
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)     DRY_RUN=1; shift ;;
    --workers)     WORKERS="${2:?--workers needs a value}"; shift 2 ;;
    --m)           M="${2:?--m needs a value}"; shift 2 ;;
    --oracle-sims) ORACLE_SIMS="${2:?--oracle-sims needs a value}"; shift 2 ;;
    *) echo "[launch_laptop] unknown arg '$1'" >&2; exit 1 ;;
  esac
done

cd "$LOCAL_REPO" || exit 1
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SHA="$(git rev-parse HEAD)"
SHORT_SHA="$(git rev-parse --short HEAD)"
echo "[launch_laptop] local branch=$BRANCH HEAD=$SHA"

BUNDLE_NAME="sync_$(date +%Y%m%dT%H%M%S)_${SHORT_SHA}.bundle"
LOCAL_BUNDLE="$LOCAL_SHARE/$SYNC_SUBDIR/$BUNDLE_NAME"
LAPTOP_BUNDLE="$LAPTOP_SHARE/$SYNC_SUBDIR/$BUNDLE_NAME"
REMOTE_LOG="$LAPTOP_REPO/measurement/jcz_mining_20260809/mining/launch_mining_laptop_remote.log"

echo "[launch_laptop] plan:"
echo "[launch_laptop]   1. git -C $LOCAL_REPO bundle create $LOCAL_BUNDLE $BRANCH"
echo "[launch_laptop]   2. ssh $LAPTOP_HOST 'bash -s' -- $LAPTOP_BUNDLE $BRANCH $SHA < <sync-verify script>"
echo "[launch_laptop]      (verifies laptop HEAD is still an ancestor of $SHA before"
echo "[launch_laptop]       fast-forwarding with 'git merge --ff-only'; REFUSES -- never"
echo "[launch_laptop]       'reset --hard' -- on any divergence)"
echo "[launch_laptop]   3. ssh $LAPTOP_HOST 'bash -s' < <launch script>  (timeout ${SSH_LAUNCH_TIMEOUT}s)"
echo "[launch_laptop]      -> detached: $LAPTOP_REPO/scripts/jcz_mining/launch_mining.sh --box laptop"
echo "[launch_laptop]         --workers $WORKERS --m $M --oracle-sims $ORACLE_SIMS"
echo "[launch_laptop]         (that script owns the process gate, the W=22 provenance"
echo "[launch_laptop]          caveat/calibration print, the STRATA gate, and the"
echo "[launch_laptop]          per-box systemd-run MemoryMax=8G scope -- this script does"
echo "[launch_laptop]          not duplicate any of it)"
echo "[launch_laptop]   check on it after launch:"
echo "[launch_laptop]     ssh $LAPTOP_HOST 'tail -f $REMOTE_LOG'"
echo "[launch_laptop]     ssh $LAPTOP_HOST 'pgrep -fa run_mining.py'"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[launch_laptop] --dry-run: stopping before any bundle/ssh/launch side effect."
  exit 0
fi

SYNC_SCRIPT="$(mktemp)"
LAUNCH_SCRIPT="$(mktemp)"
trap 'rm -f "$SYNC_SCRIPT" "$LAUNCH_SCRIPT"' EXIT

echo "[launch_laptop] === 1. bundling ==="
mkdir -p "$LOCAL_SHARE/$SYNC_SUBDIR"
git bundle create "$LOCAL_BUNDLE" "$BRANCH"
echo "[launch_laptop] bundle written: $LOCAL_BUNDLE"

echo "[launch_laptop] === 2. sync-and-verify on laptop ==="
cat > "$SYNC_SCRIPT" <<'SYNCEOF'
cd /home/doctor/projects/carcassone || exit 1
set -euo pipefail
BUNDLE="$1"
BRANCH="$2"
EXPECT_SHA="$3"
CUR="$(git rev-parse HEAD)"
echo "[laptop-sync] current laptop HEAD=$CUR"
git fetch "$BUNDLE" "$BRANCH"
NEW="$(git rev-parse FETCH_HEAD)"
if [ "$NEW" != "$EXPECT_SHA" ]; then
  echo "[laptop-sync] NOTE: fetched $NEW; local box HEAD was $EXPECT_SHA at bundle time (someone committed meanwhile)." >&2
fi
if ! git merge-base --is-ancestor "$CUR" "$NEW"; then
  echo "[laptop-sync] REFUSING: laptop HEAD $CUR is NOT an ancestor of $NEW -- this would" >&2
  echo "[laptop-sync]   NOT be a fast-forward. NOT touching the tree (never reset --hard" >&2
  echo "[laptop-sync]   over unexpected divergence)." >&2
  exit 1
fi
git merge --ff-only FETCH_HEAD
echo "[laptop-sync] fast-forwarded laptop repo $CUR -> $(git rev-parse HEAD)"
SYNCEOF
ssh "$LAPTOP_HOST" 'bash -s' -- "$LAPTOP_BUNDLE" "$BRANCH" "$SHA" < "$SYNC_SCRIPT"
echo "[launch_laptop] laptop code sync verified"

echo "[launch_laptop] === 3. detached launch on laptop ==="
cat > "$LAUNCH_SCRIPT" <<LAUNCHEOF
cd $LAPTOP_REPO || exit 1
set -euo pipefail
LOG="$REMOTE_LOG"
mkdir -p "\$(dirname "\$LOG")"
setsid nohup "$LAPTOP_REPO/scripts/jcz_mining/launch_mining.sh" --box laptop --workers $WORKERS --m $M --oracle-sims $ORACLE_SIMS > "\$LOG" 2>&1 < /dev/null &
disown
echo "[laptop-launch] launched pid=\$! log=\$LOG"
LAUNCHEOF
set +e
timeout "$SSH_LAUNCH_TIMEOUT" ssh "$LAPTOP_HOST" 'bash -s' < "$LAUNCH_SCRIPT"
rc=$?
set -e
if [ "$rc" -eq 0 ]; then
  echo "[launch_laptop] launch ssh call returned cleanly (rc=0)"
elif [ "$rc" -eq 124 ]; then
  echo "[launch_laptop] launch ssh call timed out at ${SSH_LAUNCH_TIMEOUT}s (rc=124) -- this"
  echo "[launch_laptop]   is EXPECTED for a detached remote launch and is treated as"
  echo "[launch_laptop]   LAUNCHED, not failed. DO NOT RETRY (a retry stacks a second pool"
  echo "[launch_laptop]   on the laptop). Verify with the check-on-it commands below."
else
  echo "[launch_laptop] launch ssh call FAILED rc=$rc -- likely NOT launched (or the" >&2
  echo "[launch_laptop]   remote launch_mining.sh itself refused -- check its gate output" >&2
  echo "[launch_laptop]   via the check-on-it command below)." >&2
  exit "$rc"
fi

echo "[launch_laptop] check on it:"
echo "[launch_laptop]   ssh $LAPTOP_HOST 'tail -f $REMOTE_LOG'"
echo "[launch_laptop]   ssh $LAPTOP_HOST 'pgrep -fa run_mining.py'"
