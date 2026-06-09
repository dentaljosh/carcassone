#!/bin/bash
# Worker-count sweep WITH thermal-throttle instrumentation — for the 5900XT (VRM throttling).
#
# For each W: run REAL production-knob self-play (sims=200, v2.7 CPU leaf, orch-off,
# batch=8, anchor 0.3) at a FIXED seed -> every W plays IDENTICAL games, so wall-clock
# differences are pure parallelism efficiency x throttle (no game-length variance).
# Meanwhile a background sampler logs Windows '% Processor Performance' (= effective
# clock / 3.3GHz nominal) every ~6s, so we can SEE whether a higher W wins on parallelism
# but loses it back to VRM throttling (freq decays warmup->steady).
#
# npz output goes to LOCAL /tmp (ext4) NOT the drvfs share, so CIFS/drvfs I/O is not a
# throughput confound. Only the small CSVs land on the share.
#
# Usage: WS="14 24 30" G=64 bash scripts/sweep_w_thermal.sh
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
WARM=/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt
OUTDIR=/mnt/c/carc-shared/wsweep_thermal
WS="${WS:-14 24 30}"
G="${G:-64}"
SEED="${SEED:-2000000}"        # SAME games for every W -> pure W signal
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=wsweep_thermal"
cd "$REPO" || { echo "FATAL no repo"; exit 1; }
[ -f "$WARM" ] || { echo "FATAL no warm $WARM"; exit 1; }
mkdir -p "$OUTDIR"
SUM=$OUTDIR/summary.csv
echo "w,games,positions,wall_s,pos_per_s,games_per_min,freq_n,freq_mean,freq_min,freq_warm,freq_steady,load_mean" > "$SUM"

# background effective-frequency sampler -> $1 ; echoes its bg PID
start_sampler() {
  ( while true; do
      t=$(date +%H:%M:%S)
      p=$(powershell.exe -NoProfile -Command "(Get-Counter '\Processor Information(_Total)\% Processor Performance').CounterSamples.CookedValue" 2>/dev/null | tr -d '\r' | head -1)
      l=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Processor).LoadPercentage" 2>/dev/null | tr -d '\r' | head -1)
      echo "$t,$p,$l"
      sleep 6
    done ) > "$1" 2>/dev/null &
  echo $!
}

for W in $WS; do
  TMP=/tmp/wsweep_thermal_w${W}; rm -rf "$TMP"; mkdir -p "$TMP"
  FREQ=$OUTDIR/freq_w${W}.csv
  : > "$FREQ"
  echo "### W=$W  G=$G  seed=$SEED  @ $(date +%H:%M:%S)"
  SPID=$(start_sampler "$FREQ")
  OUT=$(nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims 200 --leaf-eval v2_5 --value-blend 0.0 \
    --value-target score_diff --workers "$W" --batch-size 8 \
    --checkpoint "$WARM" --anchor-fraction 0.3 --anchor-checkpoint "$WARM" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  kill "$SPID" 2>/dev/null
  pkill -P "$SPID" 2>/dev/null || true
  line=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1)
  pos=$(echo "$line" | grep -oE '^[0-9]+'); wall=$(echo "$line" | grep -oE '[0-9.]+s' | tr -d 's')
  rm -rf "$TMP"
  # freq stats: col2 = perf%, col3 = load% ; warm = first third, steady = last third
  stats=$(awk -F, '$2!="" && $2!="NA" && ($2+0)>0 {a[n]=$2; n++; s+=$2; if(mn==""||$2<mn)mn=$2; if($3!=""){ls+=$3; lc++}}
    END{
      if(n==0){print "0,NA,NA,NA,NA,NA"; exit}
      k=int(n/3); if(k<1)k=1;
      for(i=0;i<k;i++)ws+=a[i];
      for(i=n-k;i<n;i++)ss+=a[i];
      printf "%d,%.1f,%.1f,%.1f,%.1f,%.0f", n, s/n, mn, ws/k, ss/k, (lc?ls/lc:0)
    }' "$FREQ")
  if [ -n "$pos" ] && [ -n "$wall" ]; then
    pps=$(awk "BEGIN{printf \"%.2f\", $pos/$wall}")
    gpm=$(awk "BEGIN{printf \"%.2f\", $G/($wall/60)}")
    echo "$W,$G,$pos,$wall,$pps,$gpm,$stats" >> "$SUM"
    echo "    -> $pps pos/s, $gpm games/min | freq mean/min/warm/steady% = $(echo "$stats" | cut -d, -f2-5)"
  else
    echo "$W,$G,NA,NA,NA,NA,$stats" >> "$SUM"
    echo "    -> FAILED; tail:"; printf '%s\n' "$OUT" | tail -3
  fi
done
echo "=== DONE @ $(date +%H:%M:%S) ==="
column -s, -t "$SUM"
