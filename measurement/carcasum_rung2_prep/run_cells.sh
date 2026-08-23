#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- CARCASUM RUNG-2 BUDGET LADDER LAUNCHER (AMENDED PRE-LAUNCH).
#
# Four rungs (D0=0.5x, A=2x, B=4x, C=8x the r1-calibrated median), executed
# CHEAPEST-FIRST (D0 -> A -> B -> C), against the SAME champion + Carcasum
# MCTSPlayer config rung 1 used, differing from rung 1 ONLY in the opponent's
# budget encoding (--opp-playouts instead of --opp-budget-ms). D0/A/B/C all
# draw from ONE SHARED 100-deck seed range (the amendment's within-deck slope
# estimator, READ_RULE.md §1.1) -- per-rung separation is by OUTPUT PATH, not
# seed offset. A KILL-ONLY interim futility check runs after D0, A, and B
# (never after C). See DESIGN.md and READ_RULE.md for the full design; this
# file does not reproduce either.
#
#   run_cells.sh [--dry-run] [--rung D0|A|B|C|all]
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
#      and only after RE-VERIFYING the registry AND a live-run process census.
#      This script never claims a band itself.
#   2. The carcasum_driver binary exists at $CARCASUM_DRIVER (or the default).
#   3. --dry-run is EXEMPT from 0-2: it starts nothing and spends no blindness.
#
# Every stage fail-closes: a non-timeout non-zero exit from match.py, or a
# completed-but-empty archive, STOPS the launcher (SIZE-1 EP-D2 lesson). A
# TIMEOUT (DESIGN.md §6's abort-to-partial rule) marks that rung
# ABORTED_PARTIAL and continues. An INTERIM-KILL (READ_RULE.md §5) marks every
# remaining rung SKIPPED_INTERIM_KILL and STOPS CLEANLY (exit 0) -- a planned
# early stop, not a failure.
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
ANALYZER="$REPO/$ADJUDICATOR"
LOGS="$DIR/logs"
OUT="$REPO/$OUT_SUBDIR"
RUNG0_PATH="$REPO/$RUNG0_GAMES_PATH"

DRY=0
RUNG_SEL="all"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --rung) RUNG_SEL="${2:?--rung needs D0|A|B|C|all}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

BINARY="${CARCASUM_DRIVER:-$REPO_LOCAL/vendor/carcasum/build-driver/carcasum_driver}"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[run_cells $(ts) $(hostname)] $*"; }

require_blind_and_band() {
  if [ "$BLIND_COMMIT" = "PENDING" ] || ! [[ "$BLIND_COMMIT" =~ ^[0-9a-f]{8,40}$ ]]; then
    log "!!! FATAL: WORKERS.conf::BLIND_COMMIT is missing or still the PENDING placeholder."
    exit 2
  fi
  if [ ! -f "$DIR/BAND_CLAIMED" ]; then
    log "!!! FATAL: $DIR/BAND_CLAIMED is missing."
    log "!!! The ORCHESTRATOR drops it AFTER appending DESIGN.md §4's row to"
    log "!!! governance/BAND_REGISTRY.csv AND re-verifying no live run holds this band."
    exit 2
  fi
  if [ ! -f "$BINARY" ]; then
    log "!!! FATAL: carcasum_driver not found at $BINARY."
    exit 2
  fi
}

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
# ONE shared argv builder. AMENDMENT: every rung uses the SAME seed range      #
# ($SHARED_DECK_SEED_START, all four) -- only --opp-playouts and --out differ. #
# --------------------------------------------------------------------------- #
rung_argv() {
  local playouts="$1" out_path="$2"
  ARGV=(nice -n "$NICE" "$PY" -u "$HARNESS"
        --decks "$N_DECKS" --champ-seat both --workers "$W_LAPTOP"
        --opp-kind "$OPP_KIND" --opp-playouts "$playouts"
        --seed-base "$SHARED_DECK_SEED_START"
        --binary "$BINARY"
        --out "$out_path" --resume)
}

print_dry_run() {
  local name="$1" playouts="$2" out_path="$3"
  rung_argv "$playouts" "$out_path"
  printf '[dry-run] rung %s (playouts=%s, SHARED seed_start=%s):' "$name" "$playouts" "$SHARED_DECK_SEED_START"
  printf ' %q' "${ARGV[@]}"
  printf '\n'
}

# $1=name $2=playouts $3=out_subdir $4=abort_secs
run_one_rung() {
  local name="$1" playouts="$2" subdir="$3" abort_secs="$4"
  local out_path="$OUT/$subdir/games.jsonl"
  local done_sentinel="$DIR/DONE_$name"
  local abort_sentinel="$DIR/ABORTED_PARTIAL_$name"
  local failed_sentinel="$DIR/FAILED_$name"
  local skip_sentinel="$DIR/SKIPPED_INTERIM_KILL_$name"

  if [ -f "$skip_sentinel" ]; then
    log "rung $name already SKIPPED_INTERIM_KILL -- not re-running"
    return 2   # distinct from 0/1: caller must know this rung did not run
  fi
  if [ -f "$done_sentinel" ]; then
    log "rung $name already DONE -- skipping"
    return 0
  fi
  rm -f "$abort_sentinel" "$failed_sentinel"

  mkdir -p "$LOGS" "$(dirname "$out_path")"
  rung_argv "$playouts" "$out_path"
  log "rung $name (playouts=$playouts, SHARED seed_start=$SHARED_DECK_SEED_START) -> $out_path"
  log "  abort-to-partial bound: ${abort_secs}s (DESIGN.md §6)"

  set +e
  timeout --preserve-status "${abort_secs}s" "${ARGV[@]}" >> "$LOGS/rung_$name.log" 2>&1
  local rc=$?
  set -e

  if [ "$rc" -eq 124 ]; then
    log "rung $name TIMED OUT at ${abort_secs}s -- ABORT-TO-PARTIAL (DESIGN.md §6)."
    touch "$abort_sentinel"
    return 0
  fi
  if [ "$rc" -ne 0 ]; then
    log "!!! rung $name FAILED, rc=$rc (see $LOGS/rung_$name.log). FAIL-CLOSED."
    touch "$failed_sentinel"
    return 1
  fi
  if [ ! -s "$out_path" ]; then
    log "!!! rung $name exited 0 but produced an EMPTY archive at $out_path. FAIL-CLOSED."
    touch "$failed_sentinel"
    return 1
  fi
  local n_lines
  n_lines="$(wc -l < "$out_path")"
  if [ "$n_lines" -lt "$N_GAMES" ]; then
    log "!!! rung $name exited 0 with only $n_lines/$N_GAMES games. FAIL-CLOSED."
    touch "$failed_sentinel"
    return 1
  fi

  touch "$done_sentinel"
  log "rung $name DONE ($n_lines/$N_GAMES games)"
  return 0
}

# --------------------------------------------------------------------------- #
# interim futility check (READ_RULE.md §5) -- runs the analyzer's --interim   #
# mode on rung0 + whatever shared-deck rungs are DONE so far. Exit code        #
# INTERIM_KILL_EXIT_CODE means STOP; anything else (incl. non-zero from a      #
# real analyzer error) is treated as "did not fire, but log it" -- an         #
# analyzer crash must never silently masquerade as a kill OR as a pass.       #
# --------------------------------------------------------------------------- #
run_interim_check() {
  local done_paths=(--rung0 "$RUNG0_PATH")
  [ -f "$DIR/DONE_$RUNG_D0_NAME" ] && done_paths+=(--rungD0 "$OUT/rungD0/games.jsonl" --playouts-d0 "$RUNG_D0_PLAYOUTS")
  [ -f "$DIR/DONE_$RUNG_A_NAME" ]  && done_paths+=(--rungA  "$OUT/rungA/games.jsonl"  --playouts-a  "$RUNG_A_PLAYOUTS")
  [ -f "$DIR/DONE_$RUNG_B_NAME" ]  && done_paths+=(--rungB  "$OUT/rungB/games.jsonl"  --playouts-b  "$RUNG_B_PLAYOUTS")

  log "interim futility check: ${done_paths[*]}"
  set +e
  "$PY" "$ANALYZER" --interim "${done_paths[@]}" 2>&1 | tee -a "$LOGS/interim_checks.log"
  local rc="${PIPESTATUS[0]}"
  set -e

  if [ "$rc" -eq "$INTERIM_KILL_EXIT_CODE" ]; then
    log "INTERIM-K FIRED -- stopping the ladder early (READ_RULE.md §5)."
    return 0   # "fired" — caller checks the sentinel file this function writes
  fi
  if [ "$rc" -ne 0 ]; then
    log "!!! interim check exited rc=$rc (not the kill code) -- treating as"
    log "!!! 'did not fire' per this launcher's fail-safe (never silently kill"
    log "!!! on an analyzer error), but this is logged for review, not ignored."
  fi
  return 1   # "did not fire"
}

mark_remaining_skipped() {
  # $@ = the rung NAME variables (e.g. RUNG_A) still to come
  for var in "$@"; do
    local name_var="${var}_NAME"
    local name="${!name_var}"
    if [ ! -f "$DIR/DONE_$name" ]; then
      touch "$DIR/SKIPPED_INTERIM_KILL_$name"
      log "rung $name marked SKIPPED_INTERIM_KILL"
    fi
  done
}

main() {
  if [ "$DRY" -eq 1 ]; then
    log "DRY RUN -- no games start, no guards enforced beyond argv construction"
    print_dry_run "$RUNG_D0_NAME" "$RUNG_D0_PLAYOUTS" "$OUT/rungD0/games.jsonl"
    print_dry_run "$RUNG_A_NAME"  "$RUNG_A_PLAYOUTS"  "$OUT/rungA/games.jsonl"
    print_dry_run "$RUNG_B_NAME"  "$RUNG_B_PLAYOUTS"  "$OUT/rungB/games.jsonl"
    print_dry_run "$RUNG_C_NAME"  "$RUNG_C_PLAYOUTS"  "$OUT/rungC/games.jsonl"
    log "wall-clock projection: DESIGN.md §6 (~0.65h/1.67h/3.03h/5.76h linear D0/A/B/C, ~12.3h total w/ contention)"
    log "execution order: D0 -> A -> B -> C, cheapest-first, kill-only interim check after D0/A/B"
    return 0
  fi

  require_blind_and_band
  mkdir -p "$LOGS" "$OUT"
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "carcasum rung-2 budget ladder (amended pre-launch: D0/A/B/C shared decks)"

  if [ "$RUNG_SEL" != "all" ]; then
    # single-rung mode: no interim check, no ordering enforcement (diagnostic use)
    case "$RUNG_SEL" in
      D0) run_one_rung "$RUNG_D0_NAME" "$RUNG_D0_PLAYOUTS" rungD0 "$RUNG_D0_ABORT_SECS" || exit 1 ;;
      A)  run_one_rung "$RUNG_A_NAME"  "$RUNG_A_PLAYOUTS"  rungA  "$RUNG_A_ABORT_SECS"  || exit 1 ;;
      B)  run_one_rung "$RUNG_B_NAME"  "$RUNG_B_PLAYOUTS"  rungB  "$RUNG_B_ABORT_SECS"  || exit 1 ;;
      C)  run_one_rung "$RUNG_C_NAME"  "$RUNG_C_PLAYOUTS"  rungC  "$RUNG_C_ABORT_SECS"  || exit 1 ;;
      *) log "!!! FATAL: bad --rung '$RUNG_SEL' (want D0|A|B|C|all)"; exit 2 ;;
    esac
    run_live_clear
    return 0
  fi

  # --rung all: the real cheapest-first ladder, with interim kill checks.
  run_one_rung "$RUNG_D0_NAME" "$RUNG_D0_PLAYOUTS" rungD0 "$RUNG_D0_ABORT_SECS" || { run_live_clear; exit 1; }
  if run_interim_check; then
    mark_remaining_skipped RUNG_A RUNG_B RUNG_C
    run_live_clear
    log "STOPPED after D0 -- INTERIM-K fired. Ladder ends early (planned outcome, exit 0)."
    return 0
  fi

  run_one_rung "$RUNG_A_NAME" "$RUNG_A_PLAYOUTS" rungA "$RUNG_A_ABORT_SECS" || { run_live_clear; exit 1; }
  if run_interim_check; then
    mark_remaining_skipped RUNG_B RUNG_C
    run_live_clear
    log "STOPPED after A -- INTERIM-K fired. Ladder ends early (planned outcome, exit 0)."
    return 0
  fi

  run_one_rung "$RUNG_B_NAME" "$RUNG_B_PLAYOUTS" rungB "$RUNG_B_ABORT_SECS" || { run_live_clear; exit 1; }
  if run_interim_check; then
    mark_remaining_skipped RUNG_C
    run_live_clear
    log "STOPPED after B -- INTERIM-K fired. Ladder ends early (planned outcome, exit 0)."
    return 0
  fi

  run_one_rung "$RUNG_C_NAME" "$RUNG_C_PLAYOUTS" rungC "$RUNG_C_ABORT_SECS" || { run_live_clear; exit 1; }

  local n_done=0
  for n in "$RUNG_D0_NAME" "$RUNG_A_NAME" "$RUNG_B_NAME" "$RUNG_C_NAME"; do
    [ -f "$DIR/DONE_$n" ] && n_done=$((n_done + 1))
  done
  log "ladder run finished: $n_done/4 rungs DONE"
  run_live_clear
  log "DONE -- full ladder complete; RUN_LIVE cleared"
}

main "$@"
