cd /home/doctor/projects/carcassone
# Offline git bundle sync — the remotes cannot reach github, so the branch travels
# on the share as a bundle (auto-memory: reference_offline_git_bundle_sync).
# ⚠️ Runs ON THE LAPTOP; the share is /mnt/carc-shared there, /mnt/c/carc-shared locally.
set -e
BUNDLE=/mnt/carc-shared/e4_ply_pricing_20260827.bundle
WT=/home/doctor/carc-e4pp

git -C /home/doctor/projects/carcassone fetch "$BUNDLE" \
    'e4-ply-pricing-freeze:refs/heads/e4-ply-pricing-freeze' --force
echo "=== fetched:"
git -C /home/doctor/projects/carcassone log --oneline -1 e4-ply-pricing-freeze

# A dedicated worktree: never `git checkout` the laptop's shared tree out from
# under anything (auto-memory: feedback_worktree_isolation_live_tree).
if [ -d "$WT" ]; then
  git -C "$WT" fetch "$BUNDLE" 'e4-ply-pricing-freeze:refs/heads/tmp-e4pp' --force
  git -C "$WT" reset --hard tmp-e4pp
else
  git -C /home/doctor/projects/carcassone worktree add "$WT" e4-ply-pricing-freeze
fi
echo "=== worktree at:"
git -C "$WT" log --oneline -1
ls "$WT/measurement/e4_ply_pricing_20260827/" | head
echo "=== archives present:"
ls "$WT/measurement/e4_games/" | wc -l
