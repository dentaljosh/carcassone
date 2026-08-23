#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- CARCASUM RUNG-2 BUDGET LADDER LAUNCHER.
#
# Three rungs (2x/4x/8x the r1-calibrated median playout budget), deck-paired,
# n=100 decks/rung, against the SAME champion + Carcasum MCTSPlayer config rung
# 1 used, differing from rung 1 ONLY in the opponent's budget encoding
# (--opp-playouts instead of --opp-budget-ms). See DESIGN.md and READ_RULE.md
# for the full design and the read-out branches; this file does not reproduce
# either.
#
#   run_cells.sh [--dry-run] [--rung A|B|C|all]
#
# ⛔ THIS FILE IS TRACKED AT MODE 644, DELIBERATELY NOT EXECUTABLE. `chmod +x`
# is the ORCHESTRATOR's own launch act, performed only after BLIND_COMMIT
# (WORKERS.conf) is a real 8+ hex-char sha and BAND_CLAIMED (this directory)
# exists -- never by this build. NOT LAUNCHED as of this commit.
#
# PRECONDITIONS, IN ORDER, ENFORCED BY THIS SCRIPT:
#   0. WORKERS.conf's BLIND_COMMIT is a real sha, not the placeholder PENDING.
#   1. BAND_CLAIMED (a file in this directory) exists -- the ORCHESTRATOR drops
#      it AFTER appending the DESIGN.md §4 row to governance/BAND_REGISTRY.csv,
#      and only after RE-VERIFYING the registry AND a live-run process census
#      (DESIGN.md §4's own warning). This script never claims a band itself.
#   2. --dry-run is EXEMPT from 0-1: it starts nothing and spends no blindness.
#
# Every stage fail-closes: a non-timeout non-zero exit from match.py, or a
# completed-but-empty archive, STOPS the launcher (the remaining rungs do NOT
# run silently past a real failure -- SIZE-1 EP-D2 lesson). A TIMEOUT
# (DESIGN.md §6's abort-to-partial rule) is the one exception: it marks that
# rung ABORTED_PARTIAL and the launcher continues to the next rung, because an
# abort-to-partial is a planned outcome, not a fault.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached
# jobs -- launch as:
#   setsid nohup ./run_cells.sh </dev/null >/dev/null 2>&1 & disown
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=WORKERS.conf
. "$DIR/WORKERS.conf"

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/carcasum_match/match.py"
LOGS="$DIR/logs"
OUT="$REPO/$OUT_SUBDIR"

DRY=0
RUNG_SEL="all"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --rung) RUNG_SEL="${2:?--rung needs A|B|C|all}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[run_cells $(ts) $(hostname)] $*"; }

# --------------------------------------------------------------------------- #
# hard refuse-to-run guard -- BLIND_COMMIT + BAND_CLAIMED, both real.         #
# --dry-run is exempt: it spends no blindness and claims no band.            #
# --------------------------------------------------------------------------- #
require_blind_and_band() {
  if [ "$BLIND_COMMIT" = "PENDING" ] || ! [[ "$BLIND_COMMIT" =~ ^[0-9a-f]{8,40}$ ]]; then
    log "!!! FATAL: WORKERS.conf::BLIND_COMMIT is missing or still the PENDING placeholder."
    log "!!! It must be stamped with the real freeze commit sha before any real launch."
    exit 2
  fi
  if [ ! -f "$DIR/BAND_CLAIMED" ]; then
    log "!!! FATAL: $DIR/BAND_CLAIMED is missing."
    log "!!! The ORCHESTRATOR drops it AFTER appending DESIGN.md §4's row to"
    log "!!! governance/BAND_REGISTRY.csv AND re-verifying no live run holds this band."
    log "!!! This script never claims a band; it only checks that someone else already did."
    exit 2
  fi
  if [ ! -f "$BINARY" ]; then
    log "!!! FATAL: carcasum_driver not found at $BINARY."
    log "!!! Set CARCASUM_DRIVER, or build it at the default path (DESIGN.md §8)."
    exit 2
  fi
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel -- refuses a MAIN-TREE commit while any #
# rung is live. Dropped at real-cell launch, cleared on ANY exit via trap.    #
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("Carcasum rung-2 budget ladder freeze-latch sentinel: a "
                   "MAIN-TREE commit while any rung is live risks two revisions "
                   "in one run. Cleared on the launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

# --------------------------------------------------------------------------- #
# ONE shared argv builder -- every rung's invocation differs from the others  #
# in EXACTLY --opp-playouts, --seed-base, and --out (bookkeeping). Nothing    #
# else. (DESIGN.md §0 / §2's "single experimental variable" property made    #
# structural, not clerical -- same discipline as track_d2_prep/run_cells.sh.) #
# --------------------------------------------------------------------------- #
#: Resolved ONCE in main(), never inline -- ${CARCASUM_DRIVER:-...} default is a
#: DISPLAY convenience for --dry-run only; a REAL launch additionally requires the
#: file to actually exist (checked in require_blind_and_band(), not here).
BINARY="${CARCASUM_DRIVER:-$REPO_LOCAL/vendor/carcasum/build-driver/carcasum_driver}"

rung_argv() {
  local playouts="$1" seed_start="$2" out_path="$3" claim_host="$4"
  ARGV=(nice -n "$NICE" "$PY" -u "$HARNESS"
        --decks "$N_DECKS" --champ-seat both --workers "$W_LAPTOP"
        --opp-kind "$OPP_KIND" --opp-playouts "$playouts"
        --seed-base "$seed_start"
        --binary "$BINARY"
        --out "$out_path" --resume)
  # ⚠️ claim_host is accepted for log-line identification only -- match.py's
  # CLI has no --claim-host flag (unlike the shared-claim eval harnesses); it
  # is stamped into this script's OWN log line, not passed through to argv.
  : "$claim_host"
}

print_dry_run() {
  local name="$1" playouts="$2" seed_start="$3" out_path="$4"
  rung_argv "$playouts" "$seed_start" "$out_path" "rung2-$name"
  printf '[dry-run] rung %s (playouts=%s, seed_start=%s):' "$name" "$playouts" "$seed_start"
  printf ' %q' "${ARGV[@]}"
  printf '\n'
}

# $1=name $2=playouts $3=seed_start $4=out_subdir $5=abort_secs
run_one_rung() {
  local name="$1" playouts="$2" seed_start="$3" subdir="$4" abort_secs="$5"
  local out_path="$OUT/$subdir/games.jsonl"
  local done_sentinel="$DIR/DONE_$name"
  local abort_sentinel="$DIR/ABORTED_PARTIAL_$name"
  local failed_sentinel="$DIR/FAILED_$name"

  if [ -f "$done_sentinel" ]; then
    log "rung $name already DONE -- skipping"
    return 0
  fi
  rm -f "$abort_sentinel" "$failed_sentinel"

  mkdir -p "$LOGS" "$(dirname "$out_path")"
  rung_argv "$playouts" "$seed_start" "$out_path" "rung2-$name"
  log "rung $name (playouts=$playouts, seed_start=$seed_start) -> $out_path"
  log "  abort-to-partial bound: ${abort_secs}s (DESIGN.md §6)"

  set +e
  timeout --preserve-status "${abort_secs}s" "${ARGV[@]}" >> "$LOGS/rung_$name.log" 2>&1
  local rc=$?
  set -e

  if [ "$rc" -eq 124 ]; then
    log "rung $name TIMED OUT at ${abort_secs}s -- ABORT-TO-PARTIAL (DESIGN.md §6)."
    log "  partial games are kept (resumable archive); this rung stays NOT-DONE."
    touch "$abort_sentinel"
    return 0    # planned outcome -- launcher continues to the next rung
  fi
  if [ "$rc" -ne 0 ]; then
    log "!!! rung $name FAILED, rc=$rc (see $LOGS/rung_$name.log)."
    log "!!! FAIL-CLOSED: this is NOT a timeout, so the launcher STOPS here."
    log "!!! (SIZE-1 EP-D2 lesson: a real failure never falls through silently.)"
    touch "$failed_sentinel"
    return 1
  fi
  if [ ! -s "$out_path" ]; then
    log "!!! rung $name exited 0 but produced an EMPTY archive at $out_path."
    log "!!! FAIL-CLOSED: treating a silent no-op as a failure, not a completion."
    touch "$failed_sentinel"
    return 1
  fi

  local n_lines
  n_lines="$(wc -l < "$out_path")"
  if [ "$n_lines" -lt "$N_GAMES" ]; then
    log "!!! rung $name exited 0 with only $n_lines/$N_GAMES games -- FAIL-CLOSED."
    log "!!! (a clean exit that did not reach the target count is a defect, not a partial.)"
    touch "$failed_sentinel"
    return 1
  fi

  touch "$done_sentinel"
  log "rung $name DONE ($n_lines/$N_GAMES games)"
  return 0
}

main() {
  if [ "$DRY" -eq 1 ]; then
    log "DRY RUN -- no games start, no guards enforced beyond argv construction"
    print_dry_run "$RUNG_A_NAME" "$RUNG_A_PLAYOUTS" "$RUNG_A_SEED_START" "$OUT/rungA/games.jsonl"
    print_dry_run "$RUNG_B_NAME" "$RUNG_B_PLAYOUTS" "$RUNG_B_SEED_START" "$OUT/rungB/games.jsonl"
    print_dry_run "$RUNG_C_NAME" "$RUNG_C_PLAYOUTS" "$RUNG_C_SEED_START" "$OUT/rungC/games.jsonl"
    log "wall-clock projection: DESIGN.md §6 (~1.67h / 3.03h / 5.76h linear, ~11.6h total w/ contention)"
    return 0
  fi

  require_blind_and_band
  mkdir -p "$LOGS" "$OUT"
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "carcasum rung-2 budget ladder"

  local ran_any=0
  if [ "$RUNG_SEL" = "all" ] || [ "$RUNG_SEL" = "A" ]; then
    run_one_rung "$RUNG_A_NAME" "$RUNG_A_PLAYOUTS" "$RUNG_A_SEED_START" rungA "$RUNG_A_ABORT_SECS" || { run_live_clear; exit 1; }
    ran_any=1
  fi
  if [ "$RUNG_SEL" = "all" ] || [ "$RUNG_SEL" = "B" ]; then
    run_one_rung "$RUNG_B_NAME" "$RUNG_B_PLAYOUTS" "$RUNG_B_SEED_START" rungB "$RUNG_B_ABORT_SECS" || { run_live_clear; exit 1; }
    ran_any=1
  fi
  if [ "$RUNG_SEL" = "all" ] || [ "$RUNG_SEL" = "C" ]; then
    run_one_rung "$RUNG_C_NAME" "$RUNG_C_PLAYOUTS" "$RUNG_C_SEED_START" rungC "$RUNG_C_ABORT_SECS" || { run_live_clear; exit 1; }
    ran_any=1
  fi
  [ "$ran_any" -eq 1 ] || { log "!!! FATAL: --rung selected nothing (want A|B|C|all)"; exit 2; }

  local n_done=0
  for n in "$RUNG_A_NAME" "$RUNG_B_NAME" "$RUNG_C_NAME"; do
    [ -f "$DIR/DONE_$n" ] && n_done=$((n_done + 1))
  done
  log "ladder run finished this invocation: $n_done/3 rungs DONE"
  if [ "$n_done" -ge 2 ]; then
    run_live_clear
    log "DONE -- >=2 rungs complete (DESIGN.md §6 minimum for the fit); RUN_LIVE cleared"
  else
    log "fewer than 2 rungs complete -- RUN_LIVE stays until re-run recovers more, or the"
    log "orchestrator accepts the ladder as U-UNREADABLE per READ_RULE.md §3.1"
  fi
}

main "$@"
