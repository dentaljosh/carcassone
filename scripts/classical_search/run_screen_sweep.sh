#!/bin/bash
# Phase 1.1 PUCT-priors SCREEN sweep launcher (robust, resumable, two-box).
# Runs on BOTH boxes with the same cell list, work-stealing via --shared-claim into
# a shared out-dir. role=primary (local) aggregates each cell + writes results.csv;
# role=helper (laptop) just contributes games. Both gate on the shared per-cell
# result count so they stay in sync. Resumable: cached results are skipped.
#
# Usage: run_screen_sweep.sh <primary|helper> <workers> <out_root>
set -u
ROLE="${1:?role primary|helper}"; WORKERS="${2:?workers}"; OUT_ROOT="${3:?out_root}"
ROUND="${4:-1}"                     # 1 = original c×τ grid; 2 = selector/τ8/finer-c
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
N=100; CHAMP=6400; K=2
# cell = "c tau quant select"
if [ "$ROUND" = 3 ]; then
  # CYTHON candidate @ equal-time 2750 sims (float-Cython, bit-exact). Focused best-region
  # re-screen: locate the Cython optimum in c, test the untested `visits` selector + softer tau.
  CAND=2750
  CELLS=("1.0 5 float Q" "1.5 5 float Q" "2.5 5 float Q" "1.5 5 float visits" "1.5 8 float Q")
  BAND_BASE=9020000000
  PROG=$REPO/measurement/classical_search/SCREEN_PROGRESS_R3.tsv
elif [ "$ROUND" = 2 ]; then
  CAND=800
  CELLS=("1.5 5 float visits" "2.5 5 float visits" "1.5 8 float Q" "2.5 8 float Q" "2.0 5 float Q")
  BAND_BASE=9010000000
  PROG=$REPO/measurement/classical_search/SCREEN_PROGRESS_R2.tsv
else
  CAND=800
  CELLS=("0.5 2 float Q" "0.5 5 float Q" "1.0 2 float Q" "1.0 5 float Q" "1.5 2 float Q" "1.5 5 float Q" "2.5 2 float Q" "2.5 5 float Q")
  BAND_BASE=9000000000
  PROG=$REPO/measurement/classical_search/SCREEN_PROGRESS.tsv
fi

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd $REPO || exit 1
HOST=$(hostname)

count_results() { ls "$1"/seed*_a*.json 2>/dev/null | grep -vc summary; }
clean_stale_claims() {   # drop .claim files with no result; arg2=min-age-minutes (empty=all)
  local d="$1" age="${2:-}"; local args=(-name "seed*.claim")
  [ -n "$age" ] && args+=(-mmin "+$age")
  find "$d" "${args[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}

if [ "$ROLE" = primary ]; then
  echo -e "cell\tc\ttau\tn\tW\tD\tL\telo\tsigma\tpaired_z\tsecs" > "$PROG"
fi

i=0
for cell in "${CELLS[@]}"; do
  read -r c tau quant select <<< "$cell"
  band=$((BAND_BASE + i*1000000))
  sub="c${c}_tau${tau}_${quant}_${select}_s${CAND}_k${K}"
  dir="$OUT_ROOT/$sub"
  mkdir -p "$dir"
  t0=$(date +%s)
  # primary force-cleans ALL orphan claims at cell start (killed-run recovery)
  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[$ROLE $HOST] cell $i=$sub start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 80 ]; do
    $PY "$HARNESS" --c-puct "$c" --tau-p "$tau" --leaf-quantize "$quant" --final-select "$select" \
      --cand-sims $CAND --champ-sims $CHAMP --exact-k $K --n $N --paired \
      --workers "$WORKERS" --shared-claim --claim-host "$ROLE-$HOST" --claim-stale-secs 300 \
      --no-results-csv --seed-start $band --out-root "$OUT_ROOT" --out-subdir "$sub" \
      > /tmp/sweep_${ROLE}_${sub}.log 2>&1
    clean_stale_claims "$dir" 4
    iter=$((iter+1))
    [ "$(count_results "$dir")" -lt "$N" ] && sleep 5
  done
  if [ "$ROLE" = primary ]; then
    # aggregate (all cached -> summary.json + results.csv row + printed block)
    $PY "$HARNESS" --c-puct "$c" --tau-p "$tau" --leaf-quantize "$quant" --final-select "$select" \
      --cand-sims $CAND --champ-sims $CHAMP --exact-k $K --n $N --paired \
      --seed-start $band --out-root "$OUT_ROOT" --out-subdir "$sub" > /tmp/agg_${sub}.log 2>&1
    secs=$(( $(date +%s) - t0 ))
    $PY - "$dir/summary.json" "$sub" "$c" "$tau" "$secs" >> "$PROG" 2>/tmp/parse_${sub}.log <<'PYEOF'
import json,sys
p,sub,c,tau,secs=sys.argv[1:6]
s=json.load(open(p))
print(f"{sub}\t{c}\t{tau}\t{s['n']}\t{s['W']}\t{s['D']}\t{s['L']}\t{s['elo']:.1f}\t{s['elo_sig_1sigma']:.1f}\t{s.get('paired_z',float('nan')):.2f}\t{secs}")
PYEOF
    echo "[primary] cell $sub DONE in ${secs}s -> $(tail -1 "$PROG")"
  fi
  i=$((i+1))
done
if [ "$ROLE" = primary ]; then
  echo "=== SCREEN COMPLETE ==="
  cat "$PROG"
fi
