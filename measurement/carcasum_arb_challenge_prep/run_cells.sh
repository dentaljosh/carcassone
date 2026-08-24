#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- CARCASUM ARBITER-TRANSFER CHALLENGE LAUNCHER.
#
# TWO ARMS, launched CONCURRENTLY (DESIGN.md SS6: thermal/drift control, zero
# extra wall-clock cost -- W_PER_ARM=7 each, running in the SAME calendar
# window, rather than sequential-full-W14). ARM-OFF = production champion, no
# tie-arbiter. ARM-ON = the SAME champion + governance/PRODUCTION.yaml's root
# tie-arbiter (B=64 J=4 argmax salt=tiearb2-deploy-v1 eps=0.0). Both vs the
# SAME Carcasum MCTSPlayer<PortionUtility,RandomPlayout>@5000ms/turn config,
# on the SAME shared 200(+50 topup)-deck band (within-pair CRN).
#
# Each arm runs in CHUNKS (WORKERS.conf::CHUNK_GAMES, default 40) via repeated
# --limit/--resume calls to match.py, with a VOID-RATE CIRCUIT BREAKER checked
# after every chunk: an arm whose cumulative void rate reaches
# WORKERS.conf::VOID_RATE_ABORT_PCT (10%) stops launching further chunks for
# THAT arm (marked FAILED_VOID_RATE_<arm>) without killing the other arm. This
# is DISTINCT from READ_RULE.md SS3.1's 1% FINAL read-out bar -- this is an
# early stop-wasting-compute breaker during the run itself.
#
#   run_cells.sh [--dry-run] [--topup]
#
# ⛔ THIS FILE IS TRACKED AT MODE 644, DELIBERATELY NOT EXECUTABLE. `chmod +x`
# is the ORCHESTRATOR's own launch act, performed only after BLIND_COMMIT
# (WORKERS.conf) is a real sha and BAND_CLAIMED (this directory) exists --
# never by this build. NOT LAUNCHED as of this commit.
#
# PRECONDITIONS, IN ORDER, ENFORCED BY THIS SCRIPT:
#   0. WORKERS.conf's BLIND_COMMIT is a real sha, not the placeholder PENDING.
#   1. BAND_CLAIMED (a file in this directory) exists -- the ORCHESTRATOR drops
#      it AFTER appending DESIGN.md SS4's row to governance/BAND_REGISTRY.csv,
#      and only after RE-VERIFYING the registry AND a live-run process census.
#      This script never claims a band itself.
#   2. The carcasum_driver binary exists at $CARCASUM_DRIVER (or the default).
#   3. --dry-run is EXEMPT from 0-2: it starts nothing and spends no blindness.
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
TOPUP=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --topup) TOPUP=1 ;;
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
  if [ ! -f "$DIR/$BAND_SENTINEL" ]; then
    log "!!! FATAL: $DIR/$BAND_SENTINEL is missing."
    log "!!! The ORCHESTRATOR drops it AFTER appending DESIGN.md SS4's row to"
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
           "why": ("Carcasum arbiter-transfer challenge freeze-latch sentinel: a "
                   "MAIN-TREE commit while either arm is live risks two revisions "
                   "in one run. Cleared on the launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

# --------------------------------------------------------------------------- #
# argv builder. ARM-OFF passes NO --champ-tiearb-* flags at all (disarmed by   #
# default). ARM-ON passes the six flags at PRODUCTION.yaml's deployed shape.  #
# --champ-tiearb-threads does NOT exist (WORKERS.conf note) -- not passed.    #
# --------------------------------------------------------------------------- #
arm_argv() {
  # $1=arm(off|on) $2=decks $3=workers $4=out_path $5=limit
  local arm="$1" decks="$2" workers="$3" out_path="$4" limit="$5"
  ARGV=(nice -n "$NICE" "$PY" -u "$HARNESS"
        --decks "$decks" --champ-seat both --workers "$workers"
        --opp-kind "$OPP_KIND" --opp-budget-ms "$OPP_BUDGET_MS"
        --seed-base "$SHARED_DECK_SEED_START"
        --binary "$BINARY"
        --out "$out_path" --resume --limit "$limit")
  if [ "$arm" = "on" ]; then
    ARGV+=(--champ-tiearb-enabled
           --champ-tiearb-b "$TIEARB_B" --champ-tiearb-j "$TIEARB_J"
           --champ-tiearb-mode "$TIEARB_MODE" --champ-tiearb-salt "$TIEARB_SALT"
           --champ-tiearb-eps "$TIEARB_EPS")
  fi
}

print_dry_run() {
  local arm="$1" decks="$2" workers="$3" out_path="$4"
  arm_argv "$arm" "$decks" "$workers" "$out_path" "$CHUNK_GAMES"
  printf '[dry-run] ARM-%s (decks=%s, workers=%s, seed_start=%s):' \
    "${arm^^}" "$decks" "$workers" "$SHARED_DECK_SEED_START"
  printf ' %q' "${ARGV[@]}"
  printf '\n'
}

# --------------------------------------------------------------------------- #
# void-rate readout -- fraction of archived records with a non-null `void`.   #
# Prints a bare float (e.g. 0.025) to stdout; 0 on a missing/empty archive.   #
# --------------------------------------------------------------------------- #
void_rate() {
  local out_path="$1"
  if [ ! -s "$out_path" ]; then echo "0"; return; fi
  "$PY" -c "
import json
n = v = 0
with open('$out_path') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        n += 1
        if r.get('void'):
            v += 1
print(v / n if n else 0)
"
}

n_lines() {
  local out_path="$1"
  [ -f "$out_path" ] && wc -l < "$out_path" || echo 0
}

# --------------------------------------------------------------------------- #
# run ONE arm, chunked, with the void-rate circuit breaker. Runs to           #
# completion (called inside a backgrounded subshell by main() for            #
# concurrency -- see the `&`/`wait` pair below).                             #
# --------------------------------------------------------------------------- #
run_arm() {
  local arm="$1" decks="$2" workers="$3" out_path="$4" log_path="$5" abort_secs="$6" total_games="$7"
  local name="arm_$arm"
  local done_sentinel="$DIR/DONE_$name"
  local failed_sentinel="$DIR/FAILED_$name"
  local void_sentinel="$DIR/FAILED_VOID_RATE_$name"

  if [ -f "$done_sentinel" ]; then
    log "$name already DONE -- skipping"
    return 0
  fi
  rm -f "$failed_sentinel" "$void_sentinel"
  mkdir -p "$(dirname "$out_path")"

  local n_done
  n_done="$(n_lines "$out_path")"
  while [ "$n_done" -lt "$total_games" ]; do
    arm_argv "$arm" "$decks" "$workers" "$out_path" "$CHUNK_GAMES"
    log "$name: chunk toward $total_games games (currently $n_done) -> $out_path"

    set +e
    timeout --preserve-status "${abort_secs}s" "${ARGV[@]}" >> "$log_path" 2>&1
    local rc=$?
    set -e

    if [ "$rc" -eq 124 ]; then
      log "!!! $name TIMED OUT at ${abort_secs}s (this chunk). Stopping this arm; "
      log "!!! partial archive kept, resumable. FAIL-CLOSED (not silently continued)."
      touch "$failed_sentinel"
      return 1
    fi
    if [ "$rc" -ne 0 ]; then
      log "!!! $name FAILED, rc=$rc (see $log_path). FAIL-CLOSED."
      touch "$failed_sentinel"
      return 1
    fi

    local new_n_done
    new_n_done="$(n_lines "$out_path")"
    if [ "$new_n_done" -eq "$n_done" ]; then
      log "!!! $name: chunk produced 0 new games (rc=0, no progress). FAIL-CLOSED "
      log "!!! (a stalled --resume loop is a launcher/harness defect, not silently retried)."
      touch "$failed_sentinel"
      return 1
    fi
    n_done="$new_n_done"

    local vr
    vr="$(void_rate "$out_path")"
    log "$name: $n_done/$total_games games, void_rate=$vr"
    if "$PY" -c "exit(0 if float('$vr') * 100 >= $VOID_RATE_ABORT_PCT else 1)"; then
      log "!!! $name: void rate $vr >= ${VOID_RATE_ABORT_PCT}% -- ABORTING further "
      log "!!! chunks for this arm (the OTHER arm is not affected). Archive kept."
      touch "$void_sentinel"
      return 1
    fi
  done

  touch "$done_sentinel"
  log "$name DONE ($n_done/$total_games games)"
  return 0
}

main() {
  local decks="$N_DECKS_PRIMARY" abort_secs="$ARM_ABORT_SECS_PRIMARY"
  local off_total off_out on_out log_off log_on
  if [ "$TOPUP" -eq 1 ]; then
    decks=$((N_DECKS_PRIMARY + N_DECKS_TOPUP))
    abort_secs="$ARM_ABORT_SECS_TOPUP"
    log "TOPUP mode: extending both arms' decks from $N_DECKS_PRIMARY to $decks "
    log "(seeds $SHARED_DECK_SEED_START..$SHARED_DECK_SEED_END_TOPUP) -- already-DONE"
    log "primary cells are skipped by --resume; only the reserved topup seeds are new."
  fi
  off_total=$((decks * 2))   # x2 seats

  off_out="$OUT/$ARM_OFF_NAME/games.jsonl"
  on_out="$OUT/$ARM_ON_NAME/games.jsonl"
  mkdir -p "$LOGS"
  log_off="$LOGS/${ARM_OFF_NAME}.log"
  log_on="$LOGS/${ARM_ON_NAME}.log"

  if [ "$DRY" -eq 1 ]; then
    log "DRY RUN -- no games start, no guards enforced beyond argv construction"
    print_dry_run "off" "$decks" "$W_PER_ARM" "$off_out"
    print_dry_run "on"  "$decks" "$W_PER_ARM" "$on_out"
    log "sequencing: CONCURRENT (DESIGN.md SS6) -- both arms launch simultaneously,"
    log "  W_PER_ARM=$W_PER_ARM each (of W_LAPTOP_TOTAL=$W_LAPTOP_TOTAL), same wall-clock"
    log "  total as sequential-full-W -- only the drift/thermal protection differs."
    log "void-rate circuit breaker: ${VOID_RATE_ABORT_PCT}% cumulative, checked every"
    log "  $CHUNK_GAMES games, per arm independently."
    log "wall-clock projection: DESIGN.md SS7 (~4.0h primary, ~5.0h with topup)"
    return 0
  fi

  require_blind_and_band
  mkdir -p "$OUT"
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "carcasum arbiter-transfer challenge (concurrent dual-arm, $([ "$TOPUP" -eq 1 ] && echo topup || echo primary))"

  # --- CONCURRENT LAUNCH (DESIGN.md SS6): both arms as backgrounded subshells,  #
  # each running its own chunk loop independently, `wait`ed together.           #
  local off_rc=0 on_rc=0
  ( run_arm "off" "$decks" "$W_PER_ARM" "$off_out" "$log_off" "$abort_secs" "$off_total" ) &
  local off_pid=$!
  ( run_arm "on"  "$decks" "$W_PER_ARM" "$on_out"  "$log_on"  "$abort_secs" "$off_total" ) &
  local on_pid=$!

  wait "$off_pid" || off_rc=$?
  wait "$on_pid" || on_rc=$?

  run_live_clear
  log "ARM-OFF exit=$off_rc  ARM-ON exit=$on_rc"
  if [ "$off_rc" -ne 0 ] || [ "$on_rc" -ne 0 ]; then
    log "!!! at least one arm did not reach DONE -- see FAILED_arm_* / "
    log "!!! FAILED_VOID_RATE_arm_* sentinels in $DIR. The other arm's own archive"
    log "!!! (if it completed) is still valid and kept."
    exit 1
  fi
  log "DONE -- both arms complete; RUN_LIVE cleared"
}

main "$@"
