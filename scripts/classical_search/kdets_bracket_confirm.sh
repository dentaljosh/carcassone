#!/usr/bin/env bash
# k_dets bracket — CONFIRM (n=400) of the screen's finding: fewer/deeper determinizations
# beat the deployed k8 (screen: k4 delta-vs-k8 +3.21+-1.79/z1.80, monotone axis k4>k8~k16>k32).
# Fresh CRN band 17.0001e9 (disjoint from the screen's 17e9). Config B (curve125 champ vs
# FROZEN curve100 h800 rung). Cells re-run k8 (anchor) + k4 (screen winner) + k2 (bracket the
# optimum below k4). All fixed total 2752, deck-matched -> delta-vs-k8 at z>=2 = adopt-worthy.
#
#   cell     k_dets  sims/det  total
#   k8x344     8       344      2752   <- deployed baseline / anchor (RUN FIRST)
#   k4x688     4       688      2752   <- screen winner
#   k2x1376    2      1376      2752   <- is the optimum even lower than 4?
#
# Usage:  kdets_bracket_confirm.sh <WORKERS> <OUT_ROOT>
#   local:  kdets_bracket_confirm.sh 30 /mnt/c/carc-shared
#   laptop: kdets_bracket_confirm.sh 22 /mnt/carc-shared
set -uo pipefail
cd /home/doctor/projects/carcassone            # line-1 cd (path-stable for ssh bash -s)

W="${1:?worker count}"
OUT_ROOT="${2:?out root (/mnt/c/carc-shared local | /mnt/carc-shared laptop)}"
PY=/home/doctor/projects/carcassone/.venv/bin/python
EVAL=/home/doctor/projects/carcassone/scripts/classical_search/eval_fair_puct.py
BAND=17000100000                                # confirm sub-band (reserved, disjoint from screen 17e9)
N=400
CAND_LEAF='{"v29_meeple_curve": [-10,-5,-1.25,0,2.5,3.75,5,6.25]}'   # curve125 on CHAMPION only (config B)

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export CARCASSONNE_TT_CAP=200000

declare -a KDETS=(8   4    2)
declare -a PERDET=(344 688 1376)

for i in "${!KDETS[@]}"; do
  K="${KDETS[$i]}"; S="${PERDET[$i]}"
  echo "=== kdets-CONFIRM k_dets=$K (sims/det=$S total=$((K*S))) W=$W band=$BAND $(date -u +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$EVAL" \
    --info fair --exact-k 2 --k-dets "$K" --sims "$S" --rung-sims 800 \
    --cand-leaf-json "$CAND_LEAF" \
    --n "$N" --paired --seed-start "$BAND" --workers "$W" \
    --out-root "$OUT_ROOT" --out-subdir "kdets_k${K}x${S}_tot2752_curve125champ_vs_h800_k2_confirm_b17001" \
    --shared-claim --claim-stale-secs 300 --no-results-csv
  echo "=== confirm cell k$K DONE rc=$? $(date -u +%H:%M:%S) ==="
done
echo "=== kdets-CONFIRM ALL CELLS DONE W=$W $(date -u +%H:%M:%S) ==="
