#!/usr/bin/env bash
# k_dets marginalization bracket — SCREEN (cheap-first), FAIR ruler.
# Pre-reg: scratchpad/kdets_bracket_prereg.md.  Fresh CRN band 17e9 (verified unused).
# The ONLY live lever on the ~120 fair clairvoyance tax (C-cheap dead CL-049/050; search
# doesn't close it CL-048). CL-046 flagged k_dets as NEVER SWEPT — all fair numbers held k8.
#
# Question: at FIXED total budget (k_dets x sims/det = 2752), does more determinizations
# (width) or deeper per-det search beat the deployed k8?  4 equal-cost cells, CRN-paired
# n=150 (75 decks x 2 seats) on the SAME band => cross-cell delta-vs-k8 is the verdict.
#
#   cell     k_dets  sims/det  total
#   k8x344     8       344      2752   <- DEPLOYED baseline / anchor (RUN FIRST)
#   k4x688     4       688      2752
#   k16x172   16       172      2752
#   k32x86    32        86      2752
#
# CONFIG B (production-faithful, rung frozen): champion = curve125 via --cand-leaf-json;
# the h800 rung stays on curve100 (the FROZEN CL-022 ruler, leaf_hash 4f2a93e7 — it must
# NOT move). So the k8x344 cell reproduces the KNOWN c5_confirm anchor ~+118.7 vs h800
# (curve125-champ vs curve100-rung) = the setup sanity check. The other 3 cells' anchors
# are UNMEASURED (k_dets never swept) -> that's the experiment. Verify k8 first.
#
# Usage:  kdets_bracket_screen.sh <WORKERS> <OUT_ROOT>
#   local:  kdets_bracket_screen.sh 30 /mnt/c/carc-shared
#   laptop: kdets_bracket_screen.sh 22 /mnt/carc-shared
set -uo pipefail
cd /home/doctor/projects/carcassone            # line-1 cd (path-stable for ssh bash -s)

W="${1:?worker count}"
OUT_ROOT="${2:?out root (/mnt/c/carc-shared local | /mnt/carc-shared laptop)}"
PY=/home/doctor/projects/carcassone/.venv/bin/python
EVAL=/home/doctor/projects/carcassone/scripts/classical_search/eval_fair_puct.py
BAND=17000000000
N=150
CAND_LEAF='{"v29_meeple_curve": [-10,-5,-1.25,0,2.5,3.75,5,6.25]}'   # curve125 on CHAMPION only

# ---- production leaf knobs + BLAS pins. NOTE: NO CARCASSONNE_V29_MEEPLE_CURVE export
# ---- (config B keeps the rung on curve100); curve125 goes to the champion via --cand-leaf-json.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export CARCASSONNE_TT_CAP=200000

declare -a KDETS=(8   4   16  32)     # k8 FIRST = anchor reads earliest
declare -a PERDET=(344 688 172 86)

for i in "${!KDETS[@]}"; do
  K="${KDETS[$i]}"; S="${PERDET[$i]}"
  echo "=== kdets-screen k_dets=$K (sims/det=$S total=$((K*S))) W=$W band=$BAND $(date -u +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$EVAL" \
    --info fair --exact-k 2 --k-dets "$K" --sims "$S" --rung-sims 800 \
    --cand-leaf-json "$CAND_LEAF" \
    --n "$N" --paired --seed-start "$BAND" --workers "$W" \
    --out-root "$OUT_ROOT" --out-subdir "kdets_k${K}x${S}_tot2752_curve125champ_vs_h800_k2_b17e9" \
    --shared-claim --claim-stale-secs 300 --no-results-csv
  echo "=== cell k$K DONE rc=$? $(date -u +%H:%M:%S) ==="
done
echo "=== kdets-screen ALL CELLS DONE W=$W $(date -u +%H:%M:%S) ==="
