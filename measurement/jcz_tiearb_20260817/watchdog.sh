#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — ON-DISK WATCHDOG, PER BOX. The crash-vs-hang discriminator.
#
#   watchdog.sh <CHAIN_PID> [real|smoke] [n_decks_this_box]
#
# WHY THIS EXISTS (mirrors measurement/jcz_match_20260809/run_watchdog.sh). Both
# boxes have a teardown history: the local box has dirty reboots, and the laptop
# is an 11 GB WSL guest that Windows TEARS DOWN if it balloons past the
# `.wslconfig` cap (`reference_wsl2_host_memory_teardown`) — DESIGN §0.1.4 names
# that as this run's live risk at W=22 with 22 JVMs. Either event takes the
# chain, every python worker and every JVM with it and leaves NO error anywhere:
# the run simply stops. Without an on-disk heartbeat the only evidence afterwards
# is "the jsonl is short", which cannot distinguish a crash from a hang from a
# chain that exited cleanly. With it, a CRASH is a timestamp gap and a HANG is a
# live pid with a frozen record count — and `free_g` on the last few lines tells
# you whether memory was the cause.
#
# The session heartbeat is NOT a substitute: it dies with the session (that cost
# ~5 h on an orphaned claim on 2026-07-28).
#
# ⭐ PER-BOX (DESIGN §0.1). It watches THIS box's shards
# (`<cell>.<hostname>.jsonl`) against THIS box's deck sub-range, and writes
# `logs/watchdog_<host>.log`. `launch.sh` arms one on each box. The logic is
# otherwise unchanged from the single-box version.
#
# ⚠️ IT RESTARTS NOTHING AND ANNOUNCES NOTHING. House rule: a watchdog restarts a
# DEAD chain and never announces a finished one. This one does not even restart —
# it only writes the ledger. The completion signal the orchestrating session
# watches for is the DONE_<cell>_<host> / FAILED_<cell>_<host> markers written by
# run_cell.sh, not this log.
#
# It exits on its own once the chain pid is gone (two consecutive misses, so a
# poll that lands between the two cells is not called death), so it never
# outlives the run it watches.
# =============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"
. "$HERE/_boxenv.sh"

CHAIN_PID="${1:?usage: watchdog.sh <CHAIN_PID> [real|smoke] [n_decks_this_box]}"
MODE="${2:-real}"
N_DECKS_BOX="${3:-$DECKS_BOX_DEFAULT}"

case "$N_DECKS_BOX" in ''|*[!0-9]*) echo "FATAL: n_decks must be numeric, got '$N_DECKS_BOX'" >&2; exit 2 ;; esac

LOG="$RUN_DIR/logs/watchdog_${HOST}.log"
mkdir -p "$RUN_DIR/logs"

case "$MODE" in
  real)  A_OUT="$RUN_DIR/${CELL_A}.${HOST}.jsonl"
         B_OUT="$RUN_DIR/${CELL_B}.${HOST}.jsonl" ;;
  smoke) A_OUT="$RUN_DIR/smoke_${CELL_A}.${HOST}.jsonl"
         B_OUT="$RUN_DIR/smoke_${CELL_B}.${HOST}.jsonl" ;;
  *) echo "FATAL: mode must be real|smoke, got '$MODE'" >&2; exit 2 ;;
esac
# This box's OWN target: its deck sub-range x 2 seatings. NOT the whole cell —
# the other box is playing the rest, and comparing this box's shard against the
# full N_GAMES would read as permanently stalled.
TARGET=$(( N_DECKS_BOX * 2 ))

n_of() { if [ -f "$1" ]; then wc -l < "$1" | tr -d ' '; else echo 0; fi; }

echo "[$(date -Is)] watchdog armed host=$HOST mode=$MODE chain_pid=$CHAIN_PID" \
     "decks_this_box=$N_DECKS_BOX target=$TARGET/cell W=$W_BOX" >> "$LOG"
echo "[$(date -Is)]   A=$A_OUT" >> "$LOG"
echo "[$(date -Is)]   B=$B_OUT" >> "$LOG"
echo "[$(date -Is)]   the OTHER box's shards are NOT visible here — merge_cells.sh joins them" >> "$LOG"

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
    echo "[$(date -Is)] host=$HOST chain=$CHAIN_PID alive=$alive A=$na/$TARGET B=$nb/$TARGET" \
         "match_py=${pys:-0} jvms=${jvms:-0} load=[$load] free_g=${free_g:-?}" >> "$LOG"

    if [ "$alive" = "no" ]; then
        misses=$((misses + 1))
        if [ "$misses" -ge 2 ]; then
            echo "[$(date -Is)] CHAIN GONE on $HOST at A=$na/$TARGET B=$nb/$TARGET —" \
                 "crash or clean exit. Read DONE_*_$HOST / FAILED_*_$HOST to tell which;" \
                 "resume is idempotent (run_cell.sh skips a DONE cell, match.py --resume" \
                 "skips recorded games). ⚠️ A vanished chain on the LAPTOP with free_g" \
                 "trending to 0 on the lines above is the WSL-teardown signature, not a" \
                 "code failure (DESIGN §0.1.4). WATCHDOG EXITING — it restarts nothing." >> "$LOG"
            exit 0
        fi
    else
        misses=0
    fi
    sleep 60
done
