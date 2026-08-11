#!/usr/bin/env bash
# On-disk watchdog for the n=400 JCZ confirmatory match.
#
# WHY THIS EXISTS. The local box dirty-crashed five times this week (twice on the
# night of 2026-08-08, ~3 h cadence; this run's own box came up 3 minutes before
# launch). A crash takes the driver, every worker and every JVM with it and leaves
# NO error anywhere — the run simply stops. Without an on-disk heartbeat the only
# evidence afterwards is "the jsonl is short", which cannot distinguish a crash
# from a hang from a driver that exited cleanly.
#
# So this appends one line a minute with the record count and the driver's liveness.
# A crash is then a timestamp gap; a hang is a live pid with a frozen count. The
# session heartbeat is NOT a substitute — it dies with the session (this cost ~5 h
# on an orphaned claim on 2026-07-28).
#
# It writes to disk and exits on its own when the driver is gone, so it never
# outlives the run it is watching.
set -u
OUT=/home/doctor/projects/carcassone/measurement/jcz_match_20260809/confirm.jsonl
LOG=/home/doctor/projects/carcassone/measurement/jcz_match_20260809/watchdog.log
TARGET=400

echo "[$(date -Is)] watchdog armed; target=$TARGET out=$OUT" >> "$LOG"
misses=0
while true; do
    n=$(wc -l < "$OUT" 2>/dev/null || echo 0)
    # `pgrep -f` exits 1 with no match, which is EXPECTED, not an error.
    pid=$(pgrep -f "jcz_match/match.py" | head -1 || true)
    jvms=$(pgrep -cf "com.jcloisterzone.ai.AiEngine" || true)
    load=$(cut -d' ' -f1 /proc/loadavg)
    echo "[$(date -Is)] games=$n/$TARGET driver_pid=${pid:-NONE} jvms=${jvms:-0} load=$load" >> "$LOG"

    if [ "$n" -ge "$TARGET" ]; then
        echo "[$(date -Is)] TARGET REACHED ($n) — watchdog exiting" >> "$LOG"
        exit 0
    fi
    if [ -z "${pid:-}" ]; then
        misses=$((misses + 1))
        # Two consecutive misses, so a driver restart between polls is not called death.
        if [ "$misses" -ge 2 ]; then
            echo "[$(date -Is)] DRIVER GONE at $n/$TARGET games — crash or clean exit; resume with --resume" >> "$LOG"
            exit 1
        fi
    else
        misses=0
    fi
    sleep 60
done
