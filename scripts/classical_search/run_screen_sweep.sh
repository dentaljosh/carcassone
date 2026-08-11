#!/bin/bash
# Phase 1.1 PUCT-priors SCREEN sweep launcher (robust, resumable, two-box).
# Runs on BOTH boxes with the same cell list, work-stealing via --shared-claim into
# a shared out-dir. role=primary (local) aggregates each cell + writes results.csv;
# role=helper (laptop) just contributes games. Both gate on the shared per-cell
# result count so they stay in sync. Resumable: cached results are skipped.
#
# Usage: run_screen_sweep.sh <primary|helper> <workers> <out_root>
set -u

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

ROLE="${1:?role primary|helper}"; WORKERS="${2:?workers}"; OUT_ROOT="${3:?out_root}"
ROUND="${4:-1}"                     # 1 = original c×τ grid; 2 = selector/τ8/finer-c
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
N=100; CHAMP=6400; K=2
# cell = "c tau quant select [sims]"  (sims optional; defaults to $CAND)
if [ "$ROUND" = 6 ]; then
  # CONFIRM (pre-registered, PLAN.md): single cell, n=400, FRESH band 9.4e9, K=2.
  # c* via CONF_C (default 1.5 = interior/robust choice). CONF_N/CONF_K/CONF_BAND override
  # for the K=4 n=200 follow-up. Gate: paired-elo >= +35 (2sigma) -> PROPOSE champion flip.
  N=${CONF_N:-400}
  CAND=2750
  K=${CONF_K:-2}
  CC=${CONF_C:-1.5}
  CELLS=("$CC 5 float visits 2750")
  BAND_BASE=${CONF_BAND:-9400000000}
  PROG=$REPO/measurement/classical_search/CONFIRM_PROGRESS.tsv
elif [ "$ROUND" = 7 ]; then
  # TAU BRACKET (robustness, gates NOTHING): tau in {3,8} at c1.5/2750/visits, n=100,
  # band 9.031e9 (= round-5's c1.5 band) so BOTH cells share decks with the existing
  # tau=5/2750 cell (+168.4) -> clean 3-point CRN tau curve at the deployable sims.
  # The only axis fixed from 800-sims data + never re-checked at 2750.
  N=100
  CAND=2750
  K=2
  CELLS=("1.5 3 float visits 2750" "1.5 8 float visits 2750")
  BAND_BASE=9031000000
  PROG=$REPO/measurement/classical_search/TAU_BRACKET_PROGRESS.tsv
elif [ "$ROUND" = 5 ]; then
  # Fable-guided: fix tau=5, selector=visits, quant=float. Sweep c at the DEPLOYABLE 2750
  # sims (visits), + a Q cross-check at 2750, + the matching visits@800 cells for the free
  # "does more sims help" read (paired same-band). Pick c* by neighbor-smoothing, not argmax.
  CAND=2750
  CELLS=("1.0 5 float visits 800" "1.5 5 float visits 800" "2.5 5 float visits 800" \
         "1.0 5 float visits 2750" "1.5 5 float visits 2750" "2.5 5 float visits 2750" \
         "1.5 5 float Q 2750")
  BAND_BASE=9030000000    # SAME band as round-4 so visits@800 c1.0 (=+135) is reused + paired
  PROG=$REPO/measurement/classical_search/SCREEN_PROGRESS_R5.tsv
elif [ "$ROUND" = 4 ]; then
  # BROADEN at CYTHON 800 sims (bit-exact to round-1's pure-Python 800, so directly comparable
  # to round-1's +107 landscape; Cython makes 800-sim games faster). Untested axes only
  # (round-1 already covered c×τ @ 800): the `visits` selector, higher tau (8,12), int-quant,
  # finer/higher c. Winner(s) get pumped to 2750 (equal-time) + confirmed.
  CAND=800
  CELLS=("1.0 5 float visits" "1.5 5 float visits" "2.5 5 float visits" \
         "1.5 8 float Q" "2.5 8 float Q" "1.5 12 float Q" \
         "2.0 5 float Q" "3.0 5 float Q" "1.5 5 int Q")
  BAND_BASE=9030000000
  PROG=$REPO/measurement/classical_search/SCREEN_PROGRESS_R4.tsv
elif [ "$ROUND" = 3 ]; then
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
  read -r c tau quant select sims <<< "$cell"
  sims="${sims:-$CAND}"
  if [ "$ROUND" = 5 ]; then
    # per-c band so same-c cells (800 vs 2750, visits vs Q) share decks -> paired reads,
    # and c1.0/1.5 visits@800 reuse round-4's cached same-band results.
    case "$c" in 1.0) ci=0;; 1.5) ci=1;; 2.5) ci=2;; *) ci=$i;; esac
    band=$((BAND_BASE + ci*1000000))
  elif [ "$ROUND" = 7 ]; then
    band=$BAND_BASE          # both tau cells share the c1.5 band -> CRN-paired with tau=5
  else
    band=$((BAND_BASE + i*1000000))
  fi
  sub="c${c}_tau${tau}_${quant}_${select}_s${sims}_k${K}"
  dir="$OUT_ROOT/$sub"
  mkdir -p "$dir"
  t0=$(date +%s)
  # primary force-cleans ALL orphan claims at cell start (killed-run recovery)
  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[$ROLE $HOST] cell $i=$sub start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 80 ]; do
    $PY "$HARNESS" --c-puct "$c" --tau-p "$tau" --leaf-quantize "$quant" --final-select "$select" \
      --cand-sims $sims --champ-sims $CHAMP --exact-k $K --n $N --paired \
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
      --cand-sims $sims --champ-sims $CHAMP --exact-k $K --n $N --paired \
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
