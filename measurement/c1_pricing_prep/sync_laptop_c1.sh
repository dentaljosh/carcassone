cd /home/doctor/projects/carcassone
# Offline git bundle sync — the remotes cannot reach github, so the branch travels
# on the share as a bundle (auto-memory: reference_offline_git_bundle_sync).
# ⚠️ Runs ON THE LAPTOP; the share is /mnt/carc-shared there, /mnt/c/carc-shared locally.
# Piped as: ssh laptop-wsl 'bash -s' < sync_laptop_c1.sh
set -e
BUNDLE=/mnt/carc-shared/c1_pricing.bundle
WT=/home/doctor/carc-c1price
BR="${BR:-c1-pricing-freeze}"

git -C /home/doctor/projects/carcassone fetch "$BUNDLE" "$BR:refs/heads/$BR" --force
echo "=== fetched:"
git -C /home/doctor/projects/carcassone log --oneline -1 "$BR"

# A dedicated worktree: never `git checkout` the laptop's shared tree out from
# under anything (auto-memory: feedback_worktree_isolation_live_tree).
if [ -d "$WT" ]; then
  git -C "$WT" fetch "$BUNDLE" "$BR:refs/heads/tmp-c1price" --force
  git -C "$WT" reset --hard tmp-c1price
else
  git -C /home/doctor/projects/carcassone worktree add "$WT" "$BR"
fi
echo "=== worktree at:"
git -C "$WT" log --oneline -1
echo "=== PINNED_SRC_REV gate:"
/home/doctor/projects/carcassone/.venv/bin/python -c \
  "import json;p=json.load(open('$WT/measurement/c1_pricing_prep/PINNED_SRC_REV.json'));print('pinned',p['pinned_src_rev'])"
git -C "$WT" rev-parse HEAD
echo "=== the UNMODIFIED runner is present:"
ls -l "$WT/measurement/e4_continuation_20260828/continue_plies.py"
echo "=== frozen target set + preflight:"
ls "$WT/measurement/c1_pricing_prep/" | head -30
echo "=== archives present:"
ls "$WT/measurement/e4_games/" | wc -l
echo "=== venv resolves into the worktree?"
PYTHONPATH="$WT/src:$WT/engine:$WT/scripts" \
  /home/doctor/projects/carcassone/.venv/bin/python -c \
  "import carcassonne_ai, carc_rs; print(carcassonne_ai.__file__)"
