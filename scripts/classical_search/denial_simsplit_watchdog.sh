#!/bin/bash
# denial_simsplit_watchdog.sh — cron-armed on-disk watchdog for the 2026-08-12 chain
# (scripts/classical_search/denial_simsplit_chain.sh, measurement/night_chain_20260812/).
#
# Same shape and the same reasoning as menu_chain_watchdog.sh, with its OWN lockfile, log,
# sentinels and pgrep pattern so the two watchdogs can never interfere. The older one
# no-ops on its own DONE_E and stays armed; do not remove its crontab entry.
#
# WHY CRON, NOT A DAEMON LOOP OR systemd --user: a `while true; sleep N` script is itself
# just a process — it dies in the exact reboot it exists to survive (this box has a
# documented dirty-reboot history: 3 in 28 h on 2026-08-04, memory
# reference_local_box_dirty_reboots). A `systemd-run --user` scope dies with the last ssh
# session on this fleet's laptop sibling. cron is owned by the system service and comes back
# by itself after a reboot, so THIS script is a single TICK, re-invoked every 10 minutes —
# no long-lived watchdog process of its own to lose.
#
# EACH TICK:
#   0. BLOCKED_* marker present -> the chain fail-STOPPED on purpose. NEVER relaunch: it
#      would re-run straight back into the same wall and, worse, could stack a second
#      launcher on top of games still in flight. Log once per tick, exit 0.
#   1. campaign complete -> no-op. "Complete" is DONE_S1, or DONE_D1 alongside SKIPPED_S1
#      (S1 skipping on its hard gate IS a clean finish, and a watchdog that did not know
#      that would relaunch the chain forever).
#   2. chain alive (pgrep) -> healthy, log and exit.
#   3. chain dead but harness workers still live -> ANOMALY (shell gone, workers orphaned).
#      Log loudly, DO NOT relaunch: a stacked launcher doubles the worker pools, which is
#      the expensive failure mode here. Exit 0.
#   4. chain dead, no workers, not complete -> RESTART, sourcing the chain's persisted
#      PARAMS.env first. ⚠️ The knob values (DENIAL_DOSES / thresholds / the split) have NO
#      defaults anywhere, by design; cron has no environment, so without PARAMS.env there is
#      nothing to restart WITH. Missing file => refuse and say so, never launch a
#      half-parameterized chain.
#
# flock (fd 9, non-blocking) wraps the tick body so two overlapping ticks — or a manual run
# racing a cron tick — can never both decide to relaunch.
#
# Arm via cron (every 10 min, survives reboot because cron itself does):
#   (crontab -l 2>/dev/null; \
#    echo "*/10 * * * * /home/doctor/projects/carcassone/scripts/classical_search/denial_simsplit_watchdog.sh") \
#     | crontab -
#
# Never touches governance/PRODUCTION.yaml. Never kills anything (killing an mp main
# orphans its spawn workers without reaping them).
set -u

REPO=/home/doctor/projects/carcassone
DIR="$REPO/measurement/night_chain_20260812"
LOGS="$DIR/logs"
LOCK="$LOGS/watchdog.lock"
LOG="$LOGS/watchdog.log"
CHAINLOG="$LOGS/chain.log"
CHAIN="$REPO/scripts/classical_search/denial_simsplit_chain.sh"

mkdir -p "$LOGS"
say() { echo "$(date '+%F %T') $*" >>"$LOG"; }

exec 9>"$LOCK"
if ! flock -n 9; then
  say "tick SKIPPED - lock held by another tick"
  exit 0
fi

blockers=$(find "$DIR" -maxdepth 1 -name 'BLOCKED_*' 2>/dev/null | tr '\n' ' ')
if [ -n "${blockers// /}" ]; then
  say "BLOCKED marker present ($blockers) - the chain fail-stopped deliberately. NOT relaunching; a human clears the marker after fixing the cause."
  exit 0
fi

if [ -f "$DIR/DONE_S1" ]; then
  say "DONE_S1 present - campaign complete, watchdog no-op"
  exit 0
fi
if [ -f "$DIR/DONE_D1" ] && [ -f "$DIR/SKIPPED_S1" ]; then
  say "DONE_D1 + SKIPPED_S1 - S1 declined its hard gate, which IS a clean finish. No-op."
  exit 0
fi

# pgrep -f matches the full command line. "denial_simsplit_watchdog.sh" does not contain
# the literal "denial_simsplit_chain.sh" (the _watchdog break saves it), but exclude our own
# pid/ppid anyway so the guard survives a rename.
chain_alive() {
  local p
  for p in $(pgrep -f 'denial_simsplit_chain\.sh' 2>/dev/null); do
    [ "$p" = "$$" ] || [ "$p" = "$PPID" ] || return 0
  done
  return 1
}

if chain_alive; then
  say "chain alive, no action"
  exit 0
fi

# Both harnesses this chain drives. `pgrep -c` prints 0 AND exits 1 on no match, so capture
# then default rather than `|| echo 0` (which would yield a two-line "0").
workers=$(pgrep -cf 'eval_fair_puc[t]|eval_puct_prior[s]' 2>/dev/null)
workers=$(printf '%s' "${workers:-0}" | head -1 | tr -dc '0-9')
if [ "${workers:-0}" -gt 0 ]; then
  say "ANOMALY: the chain is NOT running but $workers harness worker(s) are still live for the in-flight block - NOT relaunching (a stacked launcher would double the worker pools). Investigate by hand."
  exit 0
fi

if [ ! -f "$DIR/PARAMS.env" ]; then
  say "REFUSING to restart: $DIR/PARAMS.env is missing. The knob values (DENIAL_DOSES / DENIAL_SIZE_MIN / DENIAL_OPEN_MAX, and SIMS_TILE/SIMS_MEEPLE) have NO defaults by design and cron has no environment - there is nothing to restart WITH. Relaunch by hand with the parameters, which writes PARAMS.env for subsequent ticks."
  exit 0
fi

say "RESTART: chain not running, campaign not complete, no live harness workers - relaunching with $DIR/PARAMS.env"
# shellcheck disable=SC1091
. "$DIR/PARAMS.env"
export DENIAL_DOSES DENIAL_SIZE_MIN DENIAL_OPEN_MAX
setsid nohup nice -n 19 bash "$CHAIN" >>"$CHAINLOG" 2>&1 </dev/null &
newpid=$!
disown
say "RESTART: relaunched denial_simsplit_chain.sh, new pid $newpid (doses=[${DENIAL_DOSES:-?}] size_min=${DENIAL_SIZE_MIN:-?} open_max=${DENIAL_OPEN_MAX:-?})"
