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
export MEM_CAP_GB=2
export TIME_CAP_S=1800
export THREADS=1
D=$REPO/measurement/e4_ply_pricing_20260827
chmod +x "$D/run_pricing.sh"
mkdir -p "$D/logs"
# setsid + nohup: the harness's background flag is NOT enough — a Mac-sleep SIGHUP
# or a WSL VM teardown kills a tty-attached job.
setsid nohup "$D/run_pricing.sh" "$D/shards_laptop.txt" \
    > "$D/logs/driver_laptop.out" 2>&1 < /dev/null &
disown
sleep 3
echo "LAUNCHED laptop pgid=$!"
ps -eo pid,etime,args | grep -c "[p]rice_plies.py" || true
