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
# (`<cell>.<hostname>.<BAND_TAG>.jsonl`) against THIS box's deck sub-range, and
# writes `logs/watchdog_<host>_<BAND_TAG>.log`. `launch.sh` arms one on each box.
# The logic is otherwise unchanged from the single-box version.
#
# ⛔ IT ALSO SAMPLES THE TOTAL COMMIT FREEZE, ONCE PER HEARTBEAT — and LOGS ONLY.
# `git rev-parse HEAD` is compared against the band-claim-time sha in FREEZE_HEAD
# and a `!!! FREEZE VIOLATION` block is written if they ever differ (FREEZE.md;
# the voided 2026-08-17 run died on exactly this). IT KILLS NOTHING. By the time
# the watchdog can see a moved HEAD, records under the new rev may already exist:
# killing the leg does not un-write them and takes the other, still-clean cell
# down as collateral. The right response is a HUMAN decision made with this log in
# hand — "stop committing and finish", or "abandon before the second cell is
# spent". The watchdog's job is to make that decision POSSIBLE, loudly, while the
# run is still salvageable; `run_cell.sh` is the layer that actually refuses.
#
# ⚠️ IT RESTARTS NOTHING AND ANNOUNCES NOTHING. House rule: a watchdog restarts a
# DEAD chain and never announces a finished one. This one does not even restart —
# it only writes the ledger. The completion signal the orchestrating session
# watches for is the DONE_<cell>_<host>_<BAND_TAG> /
# FAILED_<cell>_<host>_<BAND_TAG> markers written by run_cell.sh, not this log.
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

LOG="$RUN_DIR/logs/watchdog_${HOST}_${BAND_TAG}.log"
mkdir -p "$RUN_DIR/logs"

case "$MODE" in
  real)  A_OUT="$RUN_DIR/${CELL_A}.${HOST}.${BAND_TAG}.jsonl"
         B_OUT="$RUN_DIR/${CELL_B}.${HOST}.${BAND_TAG}.jsonl" ;;
  smoke) A_OUT="$RUN_DIR/smoke_${CELL_A}.${HOST}.${BAND_TAG}.jsonl"
         B_OUT="$RUN_DIR/smoke_${CELL_B}.${HOST}.${BAND_TAG}.jsonl" ;;
  *) echo "FATAL: mode must be real|smoke, got '$MODE'" >&2; exit 2 ;;
esac
# This box's OWN target: its deck sub-range x 2 seatings. NOT the whole cell —
# the other box is playing the rest, and comparing this box's shard against the
# full N_GAMES would read as permanently stalled.
TARGET=$(( N_DECKS_BOX * 2 ))

n_of() { if [ -f "$1" ]; then wc -l < "$1" | tr -d ' '; else echo 0; fi; }

# ---- the freeze witness, resolved ONCE at arm time (it never legitimately
# ---- changes mid-run: FREEZE.md's whole point is that HEAD does not move).
FREEZE_SHA="$(freeze_head || true)"
FREEZE_ANNOUNCED=0

echo "[$(date -Is)] watchdog armed host=$HOST mode=$MODE chain_pid=$CHAIN_PID" \
     "decks_this_box=$N_DECKS_BOX target=$TARGET/cell W=$W_BOX band_tag=$BAND_TAG" >> "$LOG"
echo "[$(date -Is)]   A=$A_OUT" >> "$LOG"
echo "[$(date -Is)]   B=$B_OUT" >> "$LOG"
echo "[$(date -Is)]   the OTHER box's shards are NOT visible here — merge_cells.sh joins them" >> "$LOG"
if [ -n "$FREEZE_SHA" ]; then
  echo "[$(date -Is)]   TOTAL COMMIT FREEZE armed: FREEZE_HEAD=$FREEZE_SHA (FREEZE.md)." \
       "This watchdog LOGS a violation; it kills nothing." >> "$LOG"
else
  echo "[$(date -Is)]   !!! NO FREEZE_HEAD witness found ($FREEZE_HEAD_FILE or" \
       "$SHARE_RUN/FREEZE_HEAD) — the freeze CANNOT be sampled on this box." \
       "run_cell.sh refuses to start a real cell without it, so if cells are" \
       "running here, find out why this file is missing." >> "$LOG"
fi

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
    head_now=$(git -C "$REPO_LOCAL" rev-parse HEAD 2>/dev/null || echo "unreadable")
    if [ -n "$FREEZE_SHA" ] && [ "$head_now" != "$FREEZE_SHA" ]; then frz=VIOLATED; else frz=ok; fi
    echo "[$(date -Is)] host=$HOST chain=$CHAIN_PID alive=$alive A=$na/$TARGET B=$nb/$TARGET" \
         "match_py=${pys:-0} jvms=${jvms:-0} load=[$load] free_g=${free_g:-?}" \
         "head=${head_now:0:12} freeze=$frz" >> "$LOG"

    # =========================================================================
    # ⛔ THE FREEZE SAMPLE. LOUD, EVERY HEARTBEAT, AND IT KILLS NOTHING.
    # A commit — ANY commit, docs and README typos included — moves HEAD, and
    # match.py stamps `our_git_rev` PER RECORD at record-write time, so every
    # record written from this moment on lands under a second revision.
    # G-TOOL conjunct 2 voids a mixed-rev cell. See FREEZE.md, DISCLOSURE §3.
    # The banner repeats on EVERY heartbeat once tripped: this is the one thing
    # in the log that must not scroll away unnoticed.
    # =========================================================================
    if [ "$frz" = "VIOLATED" ]; then
        if [ "$FREEZE_ANNOUNCED" -eq 0 ]; then
            FREEZE_ANNOUNCED=1
            {
              echo "[$(date -Is)] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
              echo "[$(date -Is)] !!! FREEZE VIOLATION — FIRST OBSERVED NOW."
              echo "[$(date -Is)] !!!   FREEZE_HEAD $FREEZE_SHA  (band-claim time)"
              echo "[$(date -Is)] !!!   HEAD now    $head_now"
              echo "[$(date -Is)] !!!   at A=$na/$TARGET B=$nb/$TARGET on $HOST"
              echo "[$(date -Is)] !!! A COMMIT LANDED WHILE CELLS ARE LIVE. Every record"
              echo "[$(date -Is)] !!! written from here on stamps our_git_rev=$head_now, and"
              echo "[$(date -Is)] !!! G-TOOL conjunct 2 VOIDS a mixed-rev cell. That is exactly"
              echo "[$(date -Is)] !!! how the 2026-08-17 run was lost (DISCLOSURE.md §3)."
              echo "[$(date -Is)] !!!"
              echo "[$(date -Is)] !!! THIS WATCHDOG HAS KILLED NOTHING — deliberately. Decide:"
              echo "[$(date -Is)] !!!   (a) STOP COMMITTING IMMEDIATELY. Do NOT revert, do NOT"
              echo "[$(date -Is)] !!!       reset — a second HEAD move adds a THIRD rev. Let the"
              echo "[$(date -Is)] !!!       run finish and DISCLOSE the mixed-rev window, or"
              echo "[$(date -Is)] !!!   (b) abandon now, before the second cell is spent."
              echo "[$(date -Is)] !!! Either way the disposition is a HUMAN call, made blind to"
              echo "[$(date -Is)] !!! the statistics. Do not amend G-TOOL to fit the accident."
              echo "[$(date -Is)] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            } >> "$LOG"
        else
            echo "[$(date -Is)] !!! FREEZE VIOLATION STILL ACTIVE (expected $FREEZE_SHA, HEAD $head_now)" >> "$LOG"
        fi
    fi

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
