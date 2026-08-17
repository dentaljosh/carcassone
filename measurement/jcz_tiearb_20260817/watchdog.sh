#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — ON-DISK WATCHDOG. The crash-vs-hang discriminator.
#
#   watchdog.sh <CHAIN_PID> [real|smoke]
#
# WHY THIS EXISTS (mirrors measurement/jcz_match_20260809/run_watchdog.sh). This
# box has a dirty-reboot history: a crash takes the chain, every python worker
# and every JVM with it and leaves NO error anywhere — the run simply stops.
# Without an on-disk heartbeat the only evidence afterwards is "the jsonl is
# short", which cannot distinguish a crash from a hang from a chain that exited
# cleanly. With it, a CRASH is a timestamp gap and a HANG is a live pid with a
# frozen record count.
#
# The session heartbeat is NOT a substitute: it dies with the session (that cost
# ~5 h on an orphaned claim on 2026-07-28).
#
# ⚠️ IT RESTARTS NOTHING AND ANNOUNCES NOTHING. House rule: a watchdog restarts a
# DEAD chain and never announces a finished one. This one does not even restart —
# it only writes the ledger. The completion signal the orchestrating session
# watches for is the DONE_/FAILED_ markers written by run_cell.sh, not this log.
#
# It exits on its own once the chain pid is gone (two consecutive misses, so a
# poll that lands between the two cells is not called death), so it never
# outlives the run it watches.
# =============================================================================
set -uo pipefail
. "$(dirname "$0")/WORKERS.conf"

CHAIN_PID="${1:?usage: watchdog.sh <CHAIN_PID> [real|smoke]}"
MODE="${2:-real}"

LOG="$RUN_DIR/logs/watchdog.log"
mkdir -p "$RUN_DIR/logs"

case "$MODE" in
  real)  A_OUT="$RUN_DIR/${CELL_A}.jsonl";       B_OUT="$RUN_DIR/${CELL_B}.jsonl"
         TARGET="$N_GAMES" ;;
  smoke) A_OUT="$RUN_DIR/smoke_${CELL_A}.jsonl"; B_OUT="$RUN_DIR/smoke_${CELL_B}.jsonl"
         TARGET=$(( ${SMOKE_DECKS:-4} * 2 )) ;;
  *) echo "FATAL: mode must be real|smoke, got '$MODE'" >&2; exit 2 ;;
esac

n_of() { if [ -f "$1" ]; then wc -l < "$1" | tr -d ' '; else echo 0; fi; }

echo "[$(date -Is)] watchdog armed mode=$MODE chain_pid=$CHAIN_PID target=$TARGET/cell" >> "$LOG"
echo "[$(date -Is)]   A=$A_OUT" >> "$LOG"
echo "[$(date -Is)]   B=$B_OUT" >> "$LOG"

misses=0
while true; do
    na=$(n_of "$A_OUT")
    nb=$(n_of "$B_OUT")
    # `pgrep`/`kill -0` exit nonzero with no match, which is EXPECTED, not an error.
    if kill -0 "$CHAIN_PID" 2>/dev/null; then alive=yes; else alive=no; fi
    pys=$(pgrep -cf "jcz_match/match.py" 2>/dev/null || true)
    jvms=$(pgrep -cf "$JCZ_AI_CLASS" 2>/dev/null || true)
    load=$(cut -d' ' -f1-3 /proc/loadavg)
    free_g=$(free -g | awk '/^Mem:/{print $7}')
    echo "[$(date -Is)] chain=$CHAIN_PID alive=$alive A=$na/$TARGET B=$nb/$TARGET" \
         "match_py=${pys:-0} jvms=${jvms:-0} load=[$load] free_g=${free_g:-?}" >> "$LOG"

    if [ "$alive" = "no" ]; then
        misses=$((misses + 1))
        if [ "$misses" -ge 2 ]; then
            echo "[$(date -Is)] CHAIN GONE at A=$na/$TARGET B=$nb/$TARGET —" \
                 "crash or clean exit. Read DONE_*/FAILED_* to tell which;" \
                 "resume is idempotent (run_cell.sh skips a DONE cell, match.py --resume" \
                 "skips recorded games). WATCHDOG EXITING — it restarts nothing." >> "$LOG"
            exit 0
        fi
    else
        misses=0
    fi
    sleep 60
done
