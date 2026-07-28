#!/usr/bin/env bash
# run_watchdog.sh — on-disk, session-independent watchdog for detached --shared-claim runs.
#
# WHY THIS EXISTS (2026-07-28): Claude-session heartbeats die with the session — twice now
# an overnight run stalled for ~5-6h because the watcher lived inside the harness process.
# The failure shape both times: one worker dies holding a .claim, every other worker exits
# because no UNCLAIMED work remains, and the 300s stale-claim reclaim never fires because
# nobody is left to fire it. This script lives on the box: it clears record-less claims and
# re-execs the driver until the cell is full or the retry budget is spent.
#
# Usage:
#   run_watchdog.sh <records_glob> <expected_n> <worker_pattern> <log> -- <relaunch_cmd...>
#
#   records_glob    quoted glob matching COMPLETED record files, e.g.
#                   '/mnt/c/carc-shared/mycell/seed*_a*.json'
#   expected_n      record count at which the cell is DONE (watchdog exits 0)
#   worker_pattern  pgrep -f pattern identifying live workers for this run
#   log             watchdog's own log file
#   relaunch_cmd    command to (re)launch the driver; run detached via setsid, so the
#                   driver must itself be resume-safe (--shared-claim / --resume)
#
# Launch the watchdog itself detached:
#   setsid scripts/measurement_infra/run_watchdog.sh '<glob>' 400 'eval_fair_puct' \
#       /path/wd.log -- bash scripts/classical_search/foo_screen.sh 16 /mnt/c/carc-shared 74e9 200 \
#       </dev/null >/dev/null 2>&1 &
#
# It does NOT launch the first driver instance — arm it alongside an already-launched run.
# Poll cadence 300s; relaunch budget 5 (then it gives up loudly in the log and exits 1).
set -uo pipefail

GLOB="${1:?records glob}"; N="${2:?expected record count}"
PAT="${3:?worker pgrep pattern}"; LOG="${4:?watchdog log path}"
[ "${5:-}" = "--" ] || { echo "5th arg must be --" >&2; exit 2; }
shift 5
RELAUNCH=("$@"); [ "${#RELAUNCH[@]}" -gt 0 ] || { echo "no relaunch cmd" >&2; exit 2; }

POLL=300
MAX_RELAUNCH=5
relaunches=0

say() { echo "$(date '+%F %T') $*" >>"$LOG"; }

count_records() { ls $GLOB 2>/dev/null | wc -l; }

CELL_DIR="$(dirname "$GLOB")"   # dirname is a string op — glob chars in the basename are fine

clear_orphan_claims() {
  # a claim whose record exists is history; a claim with no record blocks resume forever
  local c j
  for c in "$CELL_DIR"/*.claim; do
    [ -e "$c" ] || break
    j="${c%.claim}.json"
    if [ ! -f "$j" ]; then rm -f "$c" && say "cleared orphan claim: $c"; fi
  done
  return 0
}

say "watchdog armed: glob=$GLOB n=$N pattern=$PAT relaunch=${RELAUNCH[*]}"
while :; do
  sleep "$POLL"
  got="$(count_records)"
  if [ "$got" -ge "$N" ]; then say "DONE: $got/$N records"; exit 0; fi
  if pgrep -f "$PAT" >/dev/null 2>&1; then
    say "healthy: $got/$N records, workers alive"
    continue
  fi
  # no workers, cell short — the stall shape
  if [ "$relaunches" -ge "$MAX_RELAUNCH" ]; then
    say "GIVING UP: $got/$N after $relaunches relaunches — investigate by hand"
    exit 1
  fi
  clear_orphan_claims
  relaunches=$((relaunches+1))
  say "STALL at $got/$N, no workers — relaunch #$relaunches: ${RELAUNCH[*]}"
  setsid "${RELAUNCH[@]}" </dev/null >>"$LOG" 2>&1 &
done
