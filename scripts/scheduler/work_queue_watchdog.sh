#!/usr/bin/env bash
# work_queue_watchdog.sh -- cron-armed on-disk watchdog for the measurement work
# queue (scripts/scheduler/work_queue.sh, measurement/scheduler_20260813/).
#
# WHY: work_queue.sh runs detached as a single long-lived pid, and nothing restarts
# it if the box reboots. This box has a documented dirty-reboot history (memory
# reference_local_box_dirty_reboots: 3 in 28 h on 2026-08-04, one at near-idle),
# and the queue's whole value is that it dispatches unattended overnight. If the
# box drops at 02:00 the queue silently stops and the boxes idle until a human
# notices.
#
# WHY CRON, NOT A DAEMON LOOP OR systemd --user: a `while true; sleep N` watchdog
# is itself just a process -- it dies in the exact reboot it exists to survive.
# A `systemd-run --user` scope dies with the last ssh session on this fleet.
# cron is owned by the system service and comes back after any reboot, so THIS
# script is a single TICK, re-invoked every 10 minutes.
#
# EACH TICK:
#   1. STOP file present   -> the operator stopped the queue on purpose. No-op.
#   2. scheduler alive     -> healthy. Log and exit.
#   3. scheduler dead      -> relaunch it detached, exactly as documented in
#                             work_queue.sh's own header, and log loudly.
#
# It NEVER kills anything (killing an mp main orphans its spawn workers without
# reaping them) and it NEVER touches governance/. Restarting the scheduler is
# safe at any moment: work_queue.sh takes an flock, and every dispatched job is
# tracked in state.json, so a fresh scheduler will not double-launch an in-flight
# item -- it sees status DISPATCHED and treats the box as busy.
#
# ARM (every 10 min, survives reboot because cron does):
#   (crontab -l 2>/dev/null | grep -v work_queue_watchdog; \
#    echo "*/10 * * * * /home/doctor/projects/carcassone/scripts/scheduler/work_queue_watchdog.sh") \
#     | crontab -
set -u

REPO=/home/doctor/projects/carcassone
RUN="$REPO/measurement/scheduler_20260813"
LOGS="$RUN/logs"
LOCK="$LOGS/watchdog.lock"
LOG="$LOGS/watchdog.log"
CHAINLOG="$LOGS/chain.log"
STOP="$RUN/STOP"

mkdir -p "$LOGS"

say() { echo "$(date '+%F %T') $*" >>"$LOG"; }

# fd 9, non-blocking: two overlapping ticks (or a manual run racing cron) can
# never both decide to relaunch.
exec 9>"$LOCK"
if ! flock -n 9; then
  say "tick SKIPPED - lock held by another tick"
  exit 0
fi

if [ -f "$STOP" ]; then
  say "STOP file present - operator stopped the queue, watchdog no-op"
  exit 0
fi

# pgrep -f matches full argv, which would include THIS script if the pattern
# collided. "work_queue_watchdog.sh" does contain "work_queue", so match the
# exact chain filename and exclude our own pid/ppid anyway.
chain_alive() {
  local p
  for p in $(pgrep -f 'scheduler/work_queue\.sh' 2>/dev/null); do
    [ "$p" = "$$" ] || [ "$p" = "$PPID" ] || return 0
  done
  return 1
}

if chain_alive; then
  say "work_queue.sh alive, no action"
  exit 0
fi

say "RESTART: work_queue.sh not running and no STOP file - relaunching"
setsid nohup nice -n 19 bash "$REPO/scripts/scheduler/work_queue.sh" \
  >>"$CHAINLOG" 2>&1 </dev/null &
newpid=$!
disown
say "RESTART: relaunched work_queue.sh, new pid $newpid"
