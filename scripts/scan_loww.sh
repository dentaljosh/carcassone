#!/bin/bash
# Self-play throughput scaling scan W=1..30 to locate the knee (bandwidth wall vs core limit).
# G scales with W (G=GMULT*W) so every config runs ~constant wall (~4 min) instead of W=1 taking
# an hour. Fixed seed-start. Samples swap+avail every 4s/config so we KNOW which configs swapped
# and whether swap was STABLE (kernel parked cold idle-MCP = clean) or GREW (workers thrash = bad).
#
# Prediction to test: bandwidth-bound -> pos/s scales ~linearly W=1->8 then BENDS toward flat by
# ~14-16 (per-worker pos/s falls). Core-bound -> linear to 16 then cliff. npz -> local /tmp.
#
# Usage: WLIST="1 2 4 8 14 16 18 30" GMULT=2 bash scripts/scan_loww.sh
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
WARM=/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt
OUTDIR=/mnt/c/carc-shared/wsweep_thermal
WLIST="${WLIST:-1 2 4 8 14 16 18 30}"
GMULT="${GMULT:-2}"
SEED="${SEED:-2000000}"
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=scan_loww"
cd "$REPO" || { echo FATAL; exit 1; }
[ -f "$WARM" ] || { echo "FATAL no warm $WARM"; exit 1; }
mkdir -p "$OUTDIR"
SUM=$OUTDIR/scan_loww.csv
echo "w,games,positions,wall_s,pos_per_s,pos_per_s_per_w,scaling_pct,swap_base_MB,swap_max_MB,swap_growth_MB,avail_min_MB,note" > "$SUM"
base_ppsw=""

for W in $WLIST; do
  G=$(( GMULT * W )); [ "$G" -lt 2 ] && G=2
  TMP=/tmp/scan_loww_w${W}; rm -rf "$TMP"; mkdir -p "$TMP"
  SWAPLOG=$OUTDIR/scan_swap_w${W}.csv; : > "$SWAPLOG"
  sb=$(free -m | awk 'NR==3{print $3}')
  echo "### W=$W G=$G seed=$SEED swap_base=${sb}MB @ $(date +%H:%M:%S)"
  ( while true; do free -m | awk -v t="$(date +%H:%M:%S)" 'NR==2{a=$7} NR==3{print t","$3","a}'; sleep 4; done ) > "$SWAPLOG" 2>/dev/null &
  SAMP=$!
  OUT=$(nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims 200 --leaf-eval v2_5 --value-blend 0.0 \
    --value-target score_diff --workers "$W" --batch-size 8 \
    --checkpoint "$WARM" --anchor-fraction 0.3 --anchor-checkpoint "$WARM" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  kill "$SAMP" 2>/dev/null; pkill -P "$SAMP" 2>/dev/null || true
  line=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1)
  pos=$(echo "$line" | grep -oE '^[0-9]+'); wall=$(echo "$line" | grep -oE '[0-9.]+s' | tr -d 's')
  rm -rf "$TMP"
  read smax sgrow amin <<<"$(awk -F, -v b="$sb" 'NF>=3{if($2+0>mx)mx=$2+0; if(am==""||$3+0<am)am=$3+0} END{printf "%d %d %d", mx, mx-b, am}' "$SWAPLOG")"
  if [ -n "$pos" ] && [ -n "$wall" ]; then
    pps=$(awk "BEGIN{printf \"%.2f\", $pos/$wall}")
    ppsw=$(awk "BEGIN{printf \"%.3f\", $pos/$wall/$W}")
    [ -z "$base_ppsw" ] && base_ppsw=$ppsw
    scal=$(awk "BEGIN{printf \"%.0f\", 100*$ppsw/$base_ppsw}")
    note=$(awk "BEGIN{print ($sgrow>1200)?\"SWAP-GREW(suspect)\":(($smax>250)?\"swap-stable(cold-MCP)\":\"clean\")}")
    echo "$W,$G,$pos,$wall,$pps,$ppsw,$scal,$sb,$smax,$sgrow,$amin,$note" >> "$SUM"
    echo "    -> $pps pos/s | per-worker $ppsw ($scal% of W=1) | swap ${sb}->${smax}MB(+$sgrow) | $note"
  else
    echo "$W,$G,NA,NA,NA,NA,NA,$sb,$smax,$sgrow,$amin,FAILED" >> "$SUM"
    echo "    -> FAILED; tail:"; printf '%s\n' "$OUT" | tail -3
  fi
done
echo "=== SCAN DONE @ $(date +%H:%M:%S) ==="
column -s, -t "$SUM"
