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
#                   '/mnt/c/carc-shared/mycell/seed*_a*.json'  (eval cells)
#                   '/mnt/c/carc-shared/mycell/seed_*.npz'     (gen cells)
#                   The record EXTENSION is taken from this glob (see REC_EXT below) —
#                   the orphan-claim guard pairs <seed>.claim with <seed>.$REC_EXT.
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

# pgrep -f matches THIS script's own argv (PAT is in it) — a naive check reports
# "workers alive" forever and never relaunches (found live 2026-07-28). Exclude
# ourselves and our process group ancestors by pid.
workers_alive() {
  local p
  for p in $(pgrep -f "$PAT" 2>/dev/null); do
    [ "$p" = "$$" ] || [ "$p" = "$PPID" ] || return 0
  done
  return 1
}

count_records() { ls $GLOB 2>/dev/null | wc -l; }

# --- BEGIN testable helpers (tests/test_run_watchdog.py extracts this block) ---
CELL_DIR="$(dirname "$GLOB")"   # dirname is a string op — glob chars in the basename are fine

# The record extension is DERIVED FROM THE GLOB, never hardcoded.
#
# BUG FIXED 2026-07-30 (audit F14): this used to hardcode ".json", which was correct for the
# eval harness it was built against on 2026-07-28 but INVERTS the guard's contract on a *gen*
# cell armed with 'seed_*.npz' — no .json ever exists beside a .npz, so EVERY claim reads
# record-less and the guard deletes ALL of them, including the claims of games already banked.
# (The share-side rodv3 copy, /mnt/c/carc-shared/rodv3_turn1/cells/rodv3_watchdog.sh, had
# already been patched by hand for exactly this; this folds the fix back upstream.)
REC_EXT="${GLOB##*.}"
if [ "$REC_EXT" = "$GLOB" ] || [ -z "$REC_EXT" ] || case "$REC_EXT" in *[!A-Za-z0-9]*) true;; *) false;; esac; then
  echo "records glob must end in a plain .<ext> (e.g. .json or .npz); got: $GLOB" >&2
  exit 2
fi

clear_orphan_claims() {
  # a claim whose record exists is history; a claim with no record blocks resume forever
  local c rec
  for c in "$CELL_DIR"/*.claim; do
    [ -e "$c" ] || break
    rec="${c%.claim}.$REC_EXT"
    if [ ! -f "$rec" ]; then rm -f "$c" && say "cleared orphan claim: $c"; fi
  done
  return 0
}
# --- END testable helpers ---

say "watchdog armed: glob=$GLOB n=$N record_ext=.$REC_EXT pattern=$PAT relaunch=${RELAUNCH[*]}"
while :; do
  sleep "$POLL"
  got="$(count_records)"
  if [ "$got" -ge "$N" ]; then say "DONE: $got/$N records"; exit 0; fi
  if workers_alive; then
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
