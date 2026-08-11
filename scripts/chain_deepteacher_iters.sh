#!/usr/bin/env bash
# Chain watcher: extend the deepteacher flywheel to iter 12 (Joshua, 2026-06-12, pre-Shabbos).
#
# The RUNNING orchestrator (run_residual_flywheel_v2.sh, iters 3..6 + sealed confirm) has its
# range baked in and must not be edited in place. This watcher waits for it to exit, then
# relaunches the same script with START=<last selection row + 1> ITERS=12, repeating until
# selection.csv has row 12 AND a sealed verdict exists. Crash-resilient: every relaunch
# re-derives START from selection.csv; gen/eval phases resume from shared-claim caches.
#
# Sealed-band handling: _run_eval skips a dir that already holds >=N games, so run-1's sealed
# output (band 1700000000, written after iter6) would be silently REUSED by a later run's
# sealed confirm. Before any relaunch that follows a completed sealed verdict, the old
# sealed dirs + SEALED_VERDICT.txt are archived, and chained runs get a FRESH held-out band
# SEALED_SEED=1800000000 (verified unused by any prior eval).
#
# Launch (detached): nohup bash scripts/chain_deepteacher_iters.sh > /tmp/deepteacher_chain.log 2>&1 & disown
set -uo pipefail

REPO=/home/doctor/projects/carcassone
OUT=/mnt/c/carc-shared/deepteacher
TARGET=12
WATCH_PID=${WATCH_PID:-553974}          # the currently-running iters-3..6 orchestrator
RELAUNCH_CAP=6                           # max chained launches before aborting loudly
CHAIN_SEALED_SEED=1800000000             # fresh held-out band for the extended run's verdict

# Env replicated from /proc/553974/environ (everything else was script default):
CHAIN_ENV=(FLYWHEEL_TAG=deepteacher
           ITER0_CKPT=/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt
           SIMS=800)

ts() { date '+%F %T'; }
last_iter() { tail -1 "$OUT/selection.csv" 2>/dev/null | cut -d, -f1; }

echo "[$(ts)] chain watcher up: waiting on pid $WATCH_PID (iters 3..6), then extending to iter $TARGET"

if kill -0 "$WATCH_PID" 2>/dev/null; then
  tail --pid="$WATCH_PID" -f /dev/null
  echo "[$(ts)] orchestrator pid $WATCH_PID exited"
else
  echo "[$(ts)] pid $WATCH_PID already gone — proceeding to state check"
fi

launches=0
while true; do
  last=$(last_iter)
  if [ -z "$last" ]; then
    echo "[$(ts)] FATAL: $OUT/selection.csv missing/empty — not launching anything" >&2
    exit 1
  fi
  if [ "$last" -ge "$TARGET" ] && [ -f "$OUT/SEALED_VERDICT.txt" ]; then
    echo "[$(ts)] DONE: selection.csv at iter $last and sealed verdict present. Chain complete."
    exit 0
  fi
  launches=$((launches+1))
  if [ "$launches" -gt "$RELAUNCH_CAP" ]; then
    echo "[$(ts)] FATAL: relaunch cap ($RELAUNCH_CAP) hit at iter $last — something is crashing repeatedly; stopping" >&2
    exit 1
  fi

  # Archive a completed sealed verdict (run-1's, or any finished intermediate) so the next
  # run's sealed confirm starts from empty dirs instead of resuming stale games.
  if [ -f "$OUT/SEALED_VERDICT.txt" ]; then
    tag="thru_iter${last}_$(date +%s)"
    mv "$OUT/SEALED_VERDICT.txt" "$OUT/SEALED_VERDICT_${tag}.txt"
    [ -d "$OUT/odo/sealed_champ" ] && mv "$OUT/odo/sealed_champ" "$OUT/odo/sealed_champ_${tag}"
    [ -d "$OUT/odo/sealed_iter0" ] && mv "$OUT/odo/sealed_iter0" "$OUT/odo/sealed_iter0_${tag}"
    echo "[$(ts)] archived sealed verdict + dirs as *_${tag}"
  fi

  startit=$((last+1))
  runlog=/tmp/flywheel_deepteacher_chain_start${startit}.log
  echo "[$(ts)] launch #$launches: START=$startit ITERS=$TARGET SEALED_SEED=$CHAIN_SEALED_SEED (log: $runlog)"
  cd "$REPO" || { echo "[$(ts)] FATAL: cd $REPO failed" >&2; exit 1; }
  env "${CHAIN_ENV[@]}" START="$startit" ITERS="$TARGET" SEALED_SEED="$CHAIN_SEALED_SEED" \
    nohup nice -n 19 bash scripts/run_residual_flywheel_v2.sh > "$runlog" 2>&1 &
  runpid=$!
  disown "$runpid" 2>/dev/null || true
  echo "[$(ts)] chained orchestrator pid=$runpid — waiting for exit"
  tail --pid="$runpid" -f /dev/null
  echo "[$(ts)] chained orchestrator pid=$runpid exited (selection now at iter $(last_iter))"
done
