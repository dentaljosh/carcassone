#!/bin/bash
# menu_chain_watchdog.sh — cron-armed on-disk watchdog for the lever-menu chain
# (scripts/classical_search/menu_chain.sh, measurement/lever_menu_20260810/).
#
# WHY: menu_chain.sh runs detached as a single long-lived pid but nothing restarts it if the
# box reboots — this box has a documented dirty-reboot history (memory
# reference_local_box_dirty_reboots: 3 in 28h on 2026-08-04). Block E is the LAST block,
# runs unattended overnight (~9.6h GPU net-arm). If the box drops at 02:00 the campaign
# silently stops with no verdict and no notice.
#
# WHY CRON, NOT A DAEMON LOOP OR systemd --user: a bare `while true; sleep N` script is
# itself just a process — it dies in the exact reboot it exists to survive. A
# `systemd-run --user` scope dies with the last ssh session on this fleet's laptop sibling
# (memory reference_laptop_cluster_access). cron is owned by the system service and restarts
# automatically after any reboot, so THIS script is a single TICK, re-invoked by cron every
# 10 minutes — no long-lived watchdog process of its own to lose.
#
# EACH TICK:
#   1. DONE_E present            -> campaign complete. No-op, exit 0.
#   2. chain alive (pgrep)       -> healthy. Log "chain alive, no action", exit 0.
#   3. chain dead, but eval_fair_puct workers are still live for the in-flight block
#                                 -> ANOMALY (chain shell gone, workers orphaned-but-running).
#                                    Log loudly, DO NOT relaunch — a stacked launcher would
#                                    double the worker pools, which is the expensive failure
#                                    mode here (see menu_chain.sh's own "DELIBERATELY NOT
#                                    KILLED" comment re: orphaned spawn workers). Exit 0.
#   4. chain dead, no workers, DONE_E absent
#                                 -> RESTART. Relaunch menu_chain.sh exactly as documented in
#                                    its own header, append a loud, timestamped line to
#                                    chain.log recording the restart + reason, exit 0.
#
# flock (fd 9, non-blocking) wraps the whole tick body so two overlapping cron ticks (or a
# manual run racing a cron tick) can never both decide to relaunch.
#
# Arm via cron (every 10 min, survives reboot because cron itself does):
#   (crontab -l 2>/dev/null; \
#    echo "*/10 * * * * /home/doctor/projects/carcassone/scripts/classical_search/menu_chain_watchdog.sh") \
#     | crontab -
#
# Never touches governance/PRODUCTION.yaml. Never kills anything (same discipline as
# menu_chain.sh itself — killing an mp main orphans its spawn workers without reaping them).
set -u

REPO=/home/doctor/projects/carcassone
DIR="$REPO/measurement/lever_menu_20260810"
LOGS="$DIR/logs"
LOCK="$LOGS/watchdog.lock"
LOG="$LOGS/watchdog.log"
CHAINLOG="$LOGS/chain.log"

mkdir -p "$LOGS"

say() { echo "$(date '+%F %T') $*" >>"$LOG"; }

exec 9>"$LOCK"
if ! flock -n 9; then
  say "tick SKIPPED - lock held by another tick"
  exit 0
fi

if [ -f "$DIR/DONE_E" ]; then
  say "DONE_E present - campaign complete, watchdog no-op"
  exit 0
fi

# pgrep -f matches on the full command line, which would include THIS script's own argv if
# its name collided with the pattern. "menu_chain_watchdog.sh" does not contain the literal
# substring "menu_chain.sh" (the "_watchdog" break saves it), but exclude our own pid/ppid
# anyway so the guard holds even if this file is ever renamed.
chain_alive() {
  local p
  for p in $(pgrep -f 'menu_chain\.sh' 2>/dev/null); do
    [ "$p" = "$$" ] || [ "$p" = "$PPID" ] || return 0
  done
  return 1
}

if chain_alive; then
  say "chain alive, no action"
  exit 0
fi

workers=$(pgrep -cf eval_fair_puct 2>/dev/null || echo 0)
if [ "${workers:-0}" -gt 0 ]; then
  say "ANOMALY: menu_chain.sh is NOT running but $workers eval_fair_puct worker(s) are still live for the in-flight block - NOT relaunching (a stacked launcher would double the worker pools). Investigate by hand."
  exit 0
fi

say "RESTART: menu_chain.sh not running, DONE_E absent, no live eval_fair_puct workers - relaunching"
# Exact original invocation, per menu_chain.sh's own header comment:
#   setsid nohup nice -n 19 bash scripts/classical_search/menu_chain.sh \
#     > measurement/lever_menu_20260810/logs/chain.log 2>&1 < /dev/null &
setsid nohup nice -n 19 bash "$REPO/scripts/classical_search/menu_chain.sh" \
  >>"$CHAINLOG" 2>&1 </dev/null &
newpid=$!
disown
say "RESTART: relaunched menu_chain.sh, new pid $newpid"
