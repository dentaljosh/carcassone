#!/usr/bin/env bash
# Per-box repo sync wrapper — cd-PROOF (git -C + abs paths) + SYNCHRONOUS + clear OK/FAIL.
# Deployed to /home/doctor/sync.sh on each remote box (laptop, xeon). Reason it exists:
# `*-wsl` ssh lands in $HOME (not the repo) and the harness strips `cd`, so inline
# `ssh box "cd repo && git fetch …"` silently runs git in $HOME and fails; and backgrounding
# a `&&` chain masks the failure (trailing echo prints anyway). This wrapper sidesteps both:
# call `ssh <box>-wsl /home/doctor/sync.sh` and READ its single SYNCED/SYNC_FAILED line.
set -uo pipefail
REPO=${REPO:-/home/doctor/projects/carcassone}
BRANCH=${BRANCH:-stage-b-wiring}
# remote boxes mount the share at /mnt/carc-shared; fall back to the 5800x-local path.
for b in /mnt/carc-shared/code_sync/carc_${BRANCH}.bundle /mnt/c/carc-shared/code_sync/carc_${BRANCH}.bundle; do
  [ -f "$b" ] && { BUNDLE="$b"; break; }
done
[ -n "${BUNDLE:-}" ] || { echo "SYNC_FAILED bundle-missing"; exit 1; }
git -C "$REPO" fetch "$BUNDLE" "$BRANCH" >/dev/null 2>&1 || { echo "SYNC_FAILED git-fetch"; exit 1; }
git -C "$REPO" reset --hard FETCH_HEAD >/dev/null 2>&1 || { echo "SYNC_FAILED git-reset"; exit 1; }
echo "SYNCED $(git -C "$REPO" rev-parse --short HEAD)"
