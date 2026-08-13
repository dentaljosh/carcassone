#!/usr/bin/env bash
# jrules_d0p25_watchdog.sh — cron-armed on-disk watchdog for the J-rules dose-0.25
# deploy-budget chain (run_deploy_jrules_d0p25.sh, measurement/jrules_on_search_20260813/).
#
# WHY: the chain runs detached as a single long-lived pid and nothing restarts it if the box
# reboots. This box has a documented dirty-reboot history (memory
# reference_local_box_dirty_reboots: 3 in 28 h on 2026-08-04, one at near-idle) and the cell
# is a ~2 h unattended run. If the box drops at 02:00 the cell silently stops.
#
# WHY CRON, NOT A DAEMON LOOP OR systemd --user: a `while true; sleep N` watchdog is itself
# just a process — it dies in the exact reboot it exists to survive. A `systemd-run --user`
# scope dies with the last ssh session on this fleet. cron is owned by the system service and
# comes back after any reboot, so THIS script is a single TICK, re-invoked every 10 minutes.
#
# ⚠️ KNOWN AND DELIBERATE LIMITATION: THIS WATCHDOG ONLY RESTARTS A DEAD CHAIN.
#    IT NEVER ANNOUNCES A FINISHED ONE. The completion signal is the on-disk marker
#    $DIR/DONE_jrules_d0p25_deploy11008 (written by the chain itself), which is also this
#    watchdog's stand-down condition. Arm a completion Monitor separately if a session needs
#    to be told; do not expect a "finished" line in this log — there will never be one.
#
# EACH TICK:
#   0. CHAIN_STARTED absent  -> ⚠️ THE COLD-START GUARD. This watchdog RESTARTS a dead
#                               chain; it must NEVER be the thing that launches the cell in
#                               the first place. The chain writes $DIR/CHAIN_STARTED the
#                               moment the OWNER starts its local leg, so the watchdog can be
#                               armed BEFORE launch (which is when you actually want it
#                               armed) without ever starting a run nobody asked for.
#   1. STOP file present     -> the operator stopped the cell on purpose. No-op.
#   2. DONE_<cell> present   -> cell complete. No-op, stand down.
#   3. chain alive (pgrep)   -> healthy. Log and exit.
#   4. chain dead BUT eval_fair_puct workers still live
#                            -> ANOMALY (chain shell gone, workers orphaned-but-running).
#                               Log loudly, DO NOT relaunch: a stacked launcher would double
#                               the worker pools on a DRAM-bound box, which is the expensive
#                               failure mode here. Killing an mp main does NOT reap its spawn
#                               workers, so a human resolves this by exact pid.
#   5. chain dead, no workers, no DONE, no STOP
#                            -> RESTART, exactly as documented in the chain's own header.
#                               Safe: menu_fair_cell.sh counts seed*.json in the SHARED dir
#                               and resumes rather than restarting, and it sweeps claims that
#                               have no record before re-entering its loop.
#
# flock (fd 9, non-blocking) wraps the tick so two overlapping cron ticks — or a manual run
# racing a cron tick — can never both decide to relaunch.
#
# ARM (every 10 min; survives reboot because cron does):
#   (crontab -l 2>/dev/null | grep -v jrules_d0p25_watchdog; \
#    echo "*/10 * * * * /home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/jrules_d0p25_watchdog.sh") \
#     | crontab -
#
# DISARM at close-out:
#   crontab -l | grep -v jrules_d0p25_watchdog | crontab -
#
# Never touches governance/. Never kills anything. Never adjudicates.
set -u

REPO=/home/doctor/projects/carcassone
DIR="$REPO/measurement/jrules_on_search_20260813"
LOGS="$DIR/logs"
LOCK="$LOGS/watchdog.lock"
LOG="$LOGS/watchdog.log"
CHAINLOG="$LOGS/chain.log"
CHAIN="$DIR/run_deploy_jrules_d0p25.sh"
SUB=jrules_d0p25_deploy11008
STOP="$DIR/STOP"

mkdir -p "$LOGS"
say() { echo "$(date '+%F %T') $*" >>"$LOG"; }

exec 9>"$LOCK"
if ! flock -n 9; then
  say "tick SKIPPED - lock held by another tick"
  exit 0
fi

# ⚠️ COLD-START GUARD — read the header. The owner launches; the watchdog only ever restarts.
if [ ! -f "$DIR/CHAIN_STARTED" ]; then
  say "CHAIN_STARTED absent - the cell has never been launched by the owner. Watchdog is ARMED but will NOT cold-start a run (it restarts a dead chain; it does not begin one)."
  exit 0
fi

if [ -f "$STOP" ]; then
  say "STOP file present - operator stopped the cell, watchdog no-op"
  exit 0
fi

if [ -f "$DIR/DONE_$SUB" ]; then
  say "DONE_$SUB present - cell complete, watchdog standing down (it does NOT announce this)"
  exit 0
fi

if [ -f "$DIR/FAILED_$SUB" ]; then
  say "FAILED_$SUB present - the chain already declared the cell short of the 90% floor. NOT relaunching; a human decides."
  exit 0
fi

# pgrep -f matches the full argv, which would include THIS script if the pattern collided.
# "jrules_d0p25_watchdog.sh" does not contain "run_deploy_jrules_d0p25.sh", but exclude our
# own pid/ppid anyway so the guard survives a rename.
chain_alive() {
  local p
  for p in $(pgrep -f 'run_deploy_jrules_d0p25\.sh' 2>/dev/null); do
    [ "$p" = "$$" ] || [ "$p" = "$PPID" ] || return 0
  done
  return 1
}

if chain_alive; then
  say "chain alive, no action"
  exit 0
fi

# Two counts, because they mean different things and both block a relaunch:
#   ours  = orphaned workers from THIS cell (chain shell gone, spawn workers still running).
#           Killing an mp main does NOT reap its spawn workers, so this is the expected shape
#           of a half-dead chain and a human resolves it by exact pid.
#   any   = eval_fair_puct workers from ANY cell. Relaunching on top of another cell's pool
#           oversubscribes a DRAM-bound box, which is the expensive failure mode here.
ours=$(pgrep -cf 'out-subdir jrules_d0p25_deploy11008' 2>/dev/null || echo 0)
any=$(pgrep -cf eval_fair_puct 2>/dev/null || echo 0)
if [ "${ours:-0}" -gt 0 ] || [ "${any:-0}" -gt 0 ]; then
  say "ANOMALY: run_deploy_jrules_d0p25.sh is NOT running but eval_fair_puct workers are still live (this cell: $ours, any cell: $any) - NOT relaunching (a stacked launcher would double the worker pools on a DRAM-bound box). Investigate by hand; kill by EXACT pid if you kill at all."
  exit 0
fi

say "RESTART: chain not running, no DONE/FAILED/STOP marker, no live eval_fair_puct workers - relaunching (resume, not restart: menu_fair_cell counts records already on the share)"
# The chain's own documented invocation. --no-laptop is NOT passed: the chain re-runs the
# laptop's per-box gates on every dispatch, so a laptop whose wheel is still stale is refused
# again (loudly, non-fatally) rather than joining half-built.
setsid nohup nice -n 19 bash "$CHAIN" >>"$CHAINLOG" 2>&1 </dev/null &
newpid=$!
disown
say "RESTART: relaunched run_deploy_jrules_d0p25.sh, new pid $newpid"
exit 0
