cd /home/doctor/projects/carcassone || exit 9
# remote_launch_laptop.sh — piped to the laptop with `ssh laptop-wsl 'bash -s' < this`.
# NEVER run inline as `ssh laptop-wsl 'cd ... && ...'`: Claude Code strips the `cd` in transit
# (CLAUDE.md, memory feedback_remote_ssh_pipe_script_mandatory). Hence `cd` on line 1 here.
#
# Detaches the census under a memory-capped user scope so an overrun OOM-kills INSIDE the
# scope instead of ballooning vmmem and tearing down the whole WSL VM (the laptop is ~11.9 GB).
# systemd --user linger is enabled on this box, so the scope survives this ssh disconnect.
#
# Measured, not guessed: at W=16 the census's whole worker set peaked at ~0.93 GB RSS
# (~56 MB/worker, 17 processes) with ~10.9 GB still available, i.e. MemoryMax=8G is a pure
# safety net here, not a binding constraint.
set -uo pipefail
W="${WTC_LAUNCH_W:-16}"
MEMMAX="${WTC_MEMMAX:-8G}"

if pgrep -f 'launch_full_census\.sh' >/dev/null 2>&1; then
  echo "ALREADY RUNNING on laptop - not stacking a second launcher"; exit 0
fi

export WTC_LAUNCH_W="$W" WTC_LAUNCH_BOX=laptop
export WTC_LAUNCH_NOTE="manual full census at 530368de on the post-F-c wheel; MemoryMax=$MEMMAX scope"
mkdir -p measurement/window_truncation_20260813/logs
nohup systemd-run --user --scope -p MemoryMax="$MEMMAX" \
      nice -n 19 bash measurement/window_truncation_20260813/launch_full_census.sh \
  >measurement/window_truncation_20260813/logs/scope_laptop.log 2>&1 </dev/null &
disown
echo "launched laptop census W=$W under a MemoryMax=$MEMMAX scope (pid $!)"
