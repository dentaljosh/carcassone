#!/usr/bin/env bash
# E4 AUTOPSY — grading backfill for the 9 ungraded archives.
#
# Identical invocation to every prior E4 grading (E4_UPDATE_20260812.md §8): the
# archive's OWN stamped budget (k8x1376 here), `--seed 12345 --calibration-seed 777`,
# `nice -n 19`.  Resumable: an archive whose EV_LOSS_<label>.json already exists is
# skipped, so re-running this after a crash costs nothing.
#
# One process per game, all 9 concurrently.  `resolve_execution(profile="desktop")`
# gives rust_threads=None => ONE rust thread per process, so 9 processes is 9 busy
# cores on a 16C/32T box, not an oversubscription.
set -uo pipefail
cd /home/doctor/projects/carcassone

OUT=measurement/analyzer_evloss_20260805
LOG=measurement/e4_autopsy_20260812/logs
mkdir -p "$LOG"

LABELS=(
  1786045035_338139
  1786074812_935815
  1786076853_2116173857
  1786113542_627623
  1786116818_134510
  1786118143_1621601234
  1786142936_703591
  1786242001_49628
  1786243458_1382293676
)

pids=()
for L in "${LABELS[@]}"; do
  if [[ -f "$OUT/EV_LOSS_$L.json" ]]; then
    echo "[backfill] SKIP $L (already graded)"
    continue
  fi
  nice -n 19 .venv/bin/python scripts/analyzer/ev_loss.py \
      "measurement/e4_games/$L.json" -o "$OUT" \
      --label "$L" --seed 12345 --calibration-seed 777 \
      > "$LOG/evloss_$L.log" 2>&1 &
  pids+=($!)
  echo "[backfill] launched $L pid=${pids[-1]}"
done

rc=0
for p in "${pids[@]}"; do
  wait "$p" || rc=1
done
echo "[backfill] all done rc=$rc"
exit "$rc"
