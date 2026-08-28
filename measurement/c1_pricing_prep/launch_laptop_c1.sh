cd /home/doctor/carc-c1price
# ⚠️ Piped over ssh as `ssh laptop-wsl 'bash -s' < this_file` with `cd` on LINE 1 —
# the inline `ssh host 'cd X && ...'` form gets the cd STRIPPED in transit
# (auto-memory: feedback_remote_ssh_pipe_script_mandatory, "not optional").
# ⚠️ Share is /mnt/carc-shared on the laptop, /mnt/c/carc-shared locally.
set -u
export REPO=/home/doctor/carc-c1price
export BOX=laptop
export W="${W:-22}"
export BLOCK="${BLOCK:-base}"
export SHARE=/mnt/carc-shared
export PY=/home/doctor/projects/carcassone/.venv/bin/python
export MEM_CAP_GB="${MEM_CAP_GB:-3}"
export ARM_CAP_S="${ARM_CAP_S:-1800}"
export THREADS="${THREADS:-1}"
export CHUNK="${CHUNK:-4}"
export SUFFIX="${SUFFIX:-}"
export SMOKE="${SMOKE:-0}"
export ALLOW_TENANTS="${ALLOW_TENANTS:-0}"
D=$REPO/measurement/c1_pricing_prep
chmod +x "$D/run_c1.sh"
mkdir -p "$D/logs"
# ⚠️ WSL VM TEARDOWN IS A *WINDOWS* OOM, not a Linux one: the guest page cache
# balloons vmmem past the .wslconfig cap and the whole VM is torn down
# (auto-memory: reference_wsl2_host_memory_teardown). This box has ~11.7 GB and
# W=22 continuation workers each hold a Game + a rust mirror + a champion, and
# each forks a capped arm child on top — exactly the shape that balloons it. So
# the driver runs inside a --user scope with a hard MemoryMax: pressure is then
# contained (and at worst OOM-kills a single arm, which is recorded as a skip)
# INSIDE the guest instead of taking the VM with it. `systemd-run --user` scopes
# die with the last ssh session unless linger is on — enabled on this box
# 2026-08-09.
# setsid + nohup as well: the harness's background flag is NOT enough.
setsid nohup systemd-run --user --scope -p MemoryMax=9G \
    --unit "c1-pricing-${BLOCK}-$(date +%s)" \
    "$D/run_c1.sh" \
    > "$D/logs/driver_laptop_${BLOCK}${SUFFIX}.out" 2>&1 < /dev/null &
disown
sleep 10
echo "LAUNCHED laptop W=$W block=$BLOCK suffix='${SUFFIX}'; continue_plies procs: $(pgrep -fc '[c]ontinue_plies.py' || echo 0)"
tail -5 "$D/logs/driver_laptop_${BLOCK}${SUFFIX}.out" 2>/dev/null || true
free -m | head -2
