cd /home/doctor/projects/carcassone
# Offline git bundle sync — the remotes cannot reach github, so the branch travels
# on the share as a bundle (auto-memory: reference_offline_git_bundle_sync).
# ⚠️ Runs ON THE LAPTOP; the share is /mnt/carc-shared there, /mnt/c/carc-shared locally.
set -e
BUNDLE=/mnt/carc-shared/e4_continuation_20260828.bundle
WT=/home/doctor/carc-e4cont
BR=e4-continuation-freeze

git -C /home/doctor/projects/carcassone fetch "$BUNDLE" "$BR:refs/heads/$BR" --force
echo "=== fetched:"
git -C /home/doctor/projects/carcassone log --oneline -1 "$BR"

# A dedicated worktree: never `git checkout` the laptop's shared tree out from
# under anything (auto-memory: feedback_worktree_isolation_live_tree).
if [ -d "$WT" ]; then
  git -C "$WT" fetch "$BUNDLE" "$BR:refs/heads/tmp-e4cont" --force
  git -C "$WT" reset --hard tmp-e4cont
else
  git -C /home/doctor/projects/carcassone worktree add "$WT" "$BR"
fi
echo "=== worktree at:"
git -C "$WT" log --oneline -1
ls "$WT/measurement/e4_continuation_20260828/" | head -20
echo "=== archives present:"
ls "$WT/measurement/e4_games/" | wc -l
echo "=== venv resolves into the worktree?"
PYTHONPATH="$WT/src:$WT/engine:$WT/scripts" \
  /home/doctor/projects/carcassone/.venv/bin/python -c \
  "import carcassonne_ai, carc_rs; print(carcassonne_ai.__file__)"
