#!/usr/bin/env bash
# tiearb2 STAGE 2 PHASE B — rolling progress view. READ-ONLY, adjudicates nothing.
#
#   watch_cells.sh [interval_secs]
#
# Prints, per cell: records on the share vs the planned 800, the DONE/FAILED
# marker state, and (once summary.json exists) the FIRING RATE only — never
# `paired_z`, never elo. READ_RULE §3 must be checkable before a number is
# opened, so this watcher deliberately cannot show one.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"
INT="${1:-300}"
OUT="$SHARE_LOCAL/$RUN_ID"
PY="$REPO_LOCAL/.venv/bin/python"

while :; do
  echo "=== $(date +%F_%T) ==="
  for SUB in "$CELL_ARB" "$CELL_RND"; do
    n=$(find "$OUT/$SUB" -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l)
    f=$(find "$OUT/$SUB/failed" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
    mark="-"
    [ -f "$HERE/DONE_$SUB" ] && mark="DONE"
    [ -f "$HERE/FAILED_$SUB" ] && mark="FAILED"
    line="$SUB  $n/$N_GAMES records  $f failed  [$mark]"
    if [ -f "$OUT/$SUB/summary.json" ]; then
      line="$line  $("$PY" -c "
import json,sys
d=json.load(open('$OUT/$SUB/summary.json'))
print('phi=%s fired=%s pickchange=%s arms=%s' % (
  round(d.get('tiearb_phi',0),2), d.get('tiearb_fired_plies_total'),
  round(d.get('tiearb_pickchange_rate',0),3), round(d.get('tiearb_mean_arms',0),2)))
" 2>/dev/null)"
    fi
    echo "  $line"
  done
  ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -4
  [ -f "$HERE/DONE_$CELL_ARB" ] && [ -f "$HERE/DONE_$CELL_RND" ] && {
    echo "both cells DONE — stopping the watch"; break; }
  sleep "$INT"
done
