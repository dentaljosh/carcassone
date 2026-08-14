#!/usr/bin/env bash
# wtc_census_watchdog.sh — cron-armed on-disk watchdog for the FULL window-truncation census
# (both boxes), modelled on measurement/jrules_on_search_20260813/jrules_d0p25_watchdog.sh.
#
# ⚠️ IT ONLY RESTARTS A DEAD CHAIN. IT NEVER ANNOUNCES A FINISHED ONE.
#    Completion markers (the things to watch for, per box):
#      local  : measurement/window_truncation_20260813/DONE_CENSUS
#      laptop : /mnt/c/carc-shared/window_truncation_20260813/laptop/DONE_CENSUS
#               (published by launch_full_census.sh; the laptop's own copy is in ITS tree)
#    A FAILED_CENSUS / EXIT_* with rc!=0 is the failure counterpart and also stands the
#    watchdog down for that box - a human decides.
#
# ⚠️ COLD-START GUARD: a box is only ever restarted if CHAIN_STARTED_<box> exists IN THIS
#    (local) tree, i.e. the owner has already launched that box once. The watchdog can
#    therefore be armed BEFORE launch without ever cold-starting a run nobody asked for.
#    ⚠️ CHAIN_STARTED_laptop is written HERE, by whoever dispatches the laptop -- the
#    laptop's own launcher writes its copy into the LAPTOP's tree, which this box cannot
#    see. Dispatching the laptop without dropping that marker leaves the laptop unwatched
#    (it fails safe: no marker => no restart, and the log says so on every tick).
#
# Restart is SAFE: RUN_CMD.sh runs every leg with --resume, rows.jsonl is fsync'd per root,
# and a leg with a DONE_LEG_* marker is skipped outright. A restart resumes at root
# granularity; it never redoes finished work and never double-counts (rows are keyed by rid).
#
# ARM (every 10 min; survives reboot because cron does):
#   (crontab -l 2>/dev/null | grep -v wtc_census_watchdog; \
#    echo "*/10 * * * * /home/doctor/projects/carcassone/measurement/window_truncation_20260813/wtc_census_watchdog.sh") \
#     | crontab -
# DISARM at close-out:
#   crontab -l | grep -v wtc_census_watchdog | crontab -
#
# Never touches governance/. Never kills anything. Never adjudicates.
set -u

REPO=/home/doctor/projects/carcassone
DIR="$REPO/measurement/window_truncation_20260813"
LOGS="$DIR/logs"
LOCK="$LOGS/wtc_watchdog.lock"
LOG="$LOGS/wtc_watchdog.log"
SHARE=/mnt/c/carc-shared                                  # allow-path (this watchdog is LOCAL-only)
PUB_LAPTOP="$SHARE/window_truncation_20260813/laptop"
STOP="$DIR/STOP"
LAPTOP_HOST=laptop-wsl

mkdir -p "$LOGS"
say() { echo "$(date '+%F %T') $*" >>"$LOG"; }

exec 9>"$LOCK"
if ! flock -n 9; then say "tick SKIPPED - lock held by another tick"; exit 0; fi

if [ -f "$STOP" ]; then say "STOP present - operator stopped the census, no-op"; exit 0; fi

# ---------------------------------------------------------------- local box ----------------
local_tick() {
  [ -f "$DIR/CHAIN_STARTED_local" ] || { say "local: CHAIN_STARTED_local absent - ARMED but will not cold-start"; return; }
  [ -f "$DIR/DONE_CENSUS" ]   && { say "local: DONE_CENSUS present - complete, standing down (this is NOT an announcement)"; return; }
  [ -f "$DIR/FAILED_CENSUS" ] && { say "local: FAILED_CENSUS present - a human decides, not relaunching"; return; }

  local p alive=0
  for p in $(pgrep -f 'launch_full_census\.sh' 2>/dev/null); do
    [ "$p" = "$$" ] || [ "$p" = "$PPID" ] || alive=1
  done
  if [ "$alive" = "1" ]; then say "local: chain alive, no action"; return; fi

  local orphans
  orphans=$(pgrep -cf 'window_truncation_census\.py' 2>/dev/null || echo 0)
  if [ "${orphans:-0}" -gt 0 ]; then
    say "local: ANOMALY - launcher gone but $orphans window_truncation_census.py worker(s) still live. NOT relaunching (killing an mp main does not reap its spawn workers; a stacked launcher would double the pools). Resolve by EXACT pid."
    return
  fi
  say "local: RESTART - no chain, no workers, no DONE/FAILED/STOP. Relaunching (RUN_CMD --resume picks up at root granularity)."
  WTC_LAUNCH_W="${WTC_W_LOCAL:-24}" WTC_LAUNCH_BOX=local \
  WTC_LAUNCH_NOTE="watchdog restart $(date -Is)" \
    setsid nohup nice -n 19 bash "$DIR/launch_full_census.sh" \
      >>"$LOGS/chain_local.log" 2>&1 </dev/null &
  disown
  say "local: relaunched, new pid $!"
}

# ---------------------------------------------------------------- laptop -------------------
laptop_tick() {
  [ -f "$DIR/CHAIN_STARTED_laptop" ] || { say "laptop: CHAIN_STARTED_laptop absent - ARMED but will not cold-start"; return; }
  [ -f "$PUB_LAPTOP/DONE_CENSUS" ] && { say "laptop: published DONE_CENSUS present - complete, standing down"; return; }
  if [ -f "$PUB_LAPTOP/EXIT_laptop" ] && ! grep -q '^rc=0 ' "$PUB_LAPTOP/EXIT_laptop" 2>/dev/null; then
    say "laptop: published EXIT_laptop is non-zero ($(cat "$PUB_LAPTOP/EXIT_laptop")) - a human decides, not relaunching"; return
  fi

  local alive
  alive=$(timeout 45 ssh -o BatchMode=yes -o ConnectTimeout=15 "$LAPTOP_HOST" \
            "pgrep -cf 'launch_full_census\.sh'" 2>/dev/null | tr -d '\r\n ')
  if [ -z "$alive" ]; then
    say "laptop: UNREACHABLE (ssh failed) - no action this tick (never relaunch blind)"; return
  fi
  if [ "${alive:-0}" -gt 0 ]; then say "laptop: chain alive ($alive proc) - no action"; return; fi

  local workers
  workers=$(timeout 45 ssh -o BatchMode=yes -o ConnectTimeout=15 "$LAPTOP_HOST" \
             "pgrep -cf 'window_truncation_census\.py'" 2>/dev/null | tr -d '\r\n ')
  if [ "${workers:-0}" -gt 0 ]; then
    say "laptop: ANOMALY - launcher gone but $workers census worker(s) live. NOT relaunching."; return
  fi
  say "laptop: RESTART - relaunching via the piped remote script (cd on line 1)"
  timeout 120 ssh -o BatchMode=yes -o ConnectTimeout=15 "$LAPTOP_HOST" \
      "WTC_LAUNCH_W=${WTC_W_LAPTOP:-16} bash -s" < "$DIR/remote_launch_laptop.sh" >>"$LOG" 2>&1 \
    && say "laptop: relaunch dispatched" || say "laptop: relaunch dispatch FAILED"
}

local_tick
laptop_tick
exit 0
