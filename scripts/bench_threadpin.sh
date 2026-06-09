#!/bin/bash
# A/B: does pinning BLAS/torch thread pools to 1/worker help self-play throughput?
# Workers currently spawn ~32 threads each (torch intra-op=16 + interop=32 + OMP/MKL pools);
# at W=16 that's ~512 threads over 32 CPUs. The forwards run on GPU so most are idle, but
# scheduler + per-call dispatch overhead may cost throughput. Test env-only pinning (no code
# change): OMP/MKL/OPENBLAS/NUMEXPR_NUM_THREADS=1. Fixed seed -> default vs pinned play the
# SAME games, so the delta is clean (no game-length variance). npz -> local /tmp.
#
# Usage: WLIST="16 24" G=32 bash scripts/bench_threadpin.sh
set -u
REPO=/home/doctor/projects/carcassone; PY=$REPO/.venv/bin/python
WARM=/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt
OUTDIR=/mnt/c/carc-shared/wsweep_thermal
WLIST="${WLIST:-16 24}"; G="${G:-32}"; SEED="${SEED:-2000000}"
BASEENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=threadpin"
PIN="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1"
cd "$REPO" || { echo FATAL; exit 1; }
[ -f "$WARM" ] || { echo "FATAL no warm"; exit 1; }
mkdir -p "$OUTDIR"
SUM=$OUTDIR/threadpin.csv
echo "w,mode,games,positions,wall_s,pos_per_s" > "$SUM"

run() {  # $1=W $2=mode $3=extra-env
  local W=$1 mode=$2 extra="$3"
  local TMP=/tmp/threadpin_${mode}_w${W}; rm -rf "$TMP"; mkdir -p "$TMP"
  echo "### W=$W $mode @ $(date +%H:%M:%S)"
  local OUT
  OUT=$(nice -n 19 env $BASEENV $extra $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims 200 --leaf-eval v2_5 --value-blend 0.0 \
    --value-target score_diff --workers "$W" --batch-size 8 \
    --checkpoint "$WARM" --anchor-fraction 0.3 --anchor-checkpoint "$WARM" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  local line pos wall pps
  line=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1)
  pos=$(echo "$line" | grep -oE '^[0-9]+'); wall=$(echo "$line" | grep -oE '[0-9.]+s' | tr -d s)
  rm -rf "$TMP"
  if [ -n "$pos" ] && [ -n "$wall" ]; then
    pps=$(awk "BEGIN{printf \"%.2f\", $pos/$wall}")
    echo "$W,$mode,$G,$pos,$wall,$pps" >> "$SUM"
    echo "    -> $pps pos/s"
  else
    echo "$W,$mode,$G,NA,NA,NA" >> "$SUM"; echo "    FAILED"; printf '%s\n' "$OUT" | tail -3
  fi
}

for W in $WLIST; do
  run "$W" default ""
  run "$W" pinned "$PIN"
done
echo "=== THREADPIN DONE @ $(date +%H:%M:%S) ==="
column -s, -t "$SUM"
# delta per W
awk -F, 'NR>1 && $6!="NA"{v[$1","$2]=$6} END{print "--- delta (pinned vs default) ---"; for(k in v){split(k,a,","); if(a[2]=="pinned"){d=v[a[1]",pinned"]; b=v[a[1]",default"]; if(b>0) printf "W=%s: %.2f -> %.2f pos/s (%+.1f%%)\n", a[1], b, d, 100*(d/b-1)}}}' "$SUM"
