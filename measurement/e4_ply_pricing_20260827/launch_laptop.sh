cd /home/doctor/carc-e4pp
# ⚠️ Piped over ssh as `ssh laptop-wsl 'bash -s' < this_file` with `cd` on LINE 1 —
# the inline `ssh host 'cd X && ...'` form gets the cd STRIPPED in transit
# (auto-memory: feedback_remote_ssh_pipe_script_mandatory, "not optional").
# ⚠️ Share is /mnt/carc-shared on the laptop, /mnt/c/carc-shared locally.
set -u
export REPO=/home/doctor/carc-e4pp
export BOX=laptop
export W=22
export SHARE=/mnt/carc-shared
export PY=/home/doctor/projects/carcassone/.venv/bin/python
export MEM_CAP_GB=4
export TIME_CAP_S=1800
export THREADS=1
D=$REPO/measurement/e4_ply_pricing_20260827
chmod +x "$D/run_pricing.sh"
mkdir -p "$D/logs"
# ⚠️ WSL VM TEARDOWN IS A *WINDOWS* OOM, not a Linux one: the guest page cache
# balloons vmmem past the .wslconfig cap and the whole VM is torn down (auto-memory:
# reference_wsl2_host_memory_teardown). This box has ~11.7 GB, and W=22 shards each
# holding a Game + a rust mirror + a champion, some of them forking a capped solve
# child, is exactly the shape that balloons it. So the driver runs inside a
# --user scope with a hard MemoryMax: pressure is then contained (and, at worst,
# OOM-kills shards) INSIDE the guest instead of taking the VM with it.
# `systemd-run --user` scopes die with the last ssh session unless linger is on —
# it was enabled on this box 2026-08-09.
# setsid + nohup as well: the harness's background flag is NOT enough — a Mac-sleep
# SIGHUP or a WSL VM teardown kills a tty-attached job.
setsid nohup systemd-run --user --scope -p MemoryMax=9G \
    --unit "e4-ply-pricing-$(date +%s)" \
    "$D/run_pricing.sh" "$D/shards_laptop.txt" \
    > "$D/logs/driver_laptop.out" 2>&1 < /dev/null &
disown
sleep 8
echo "LAUNCHED laptop; price_plies procs: $(pgrep -fc '[p]rice_plies.py' || echo 0)"
free -m | head -2
