#!/usr/bin/env bash
# T3 Optuna S2 confirm — t020 (the rung-C FIRE candidate) vs the PINNED curve125 champion.
# n=400 on FRESH decks (band 2.01e10, disjoint from the ladder's 2.00e10) to defend against
# the winner's curse: rung-C selected t020 on the SAME CRN decks it climbed, so +36.3/z2.97
# is a selection estimate. S2 re-measures on unseen decks. Gate: +25 elo AND paired_z>=2.
#
# Config is t020's EXACT resolved cfg from its rung manifest (leaf_hash a995a38d):
#   c_puct 1.88 / tau_p 5.42 / value_norm 13.79
#   curve125 x1.262 = [-12.62,-6.31,-1.5775,0,3.155,4.7325,6.31,7.8875]
#   closure_p x0.828 = {1:0.414, 2:0.1656, 3:0.0414} ; bonus_cap 8.55 ; opp_bonus_cap 9.79
# Champion side is PINNED (--opp-pin-champion): c=1.5/tau=5.0/vnorm=15.0 + BASE curve125
# (leaf hash a36d2e15) resolved from CARCASSONNE_V29_MEEPLE_CURVE below. The candidate's
# --cand-leaf-json overrides ONLY the candidate's leaf.
#
# Usage: t3_s2_launch.sh [--share PATH] [--workers N] [--dry-run]
set -euo pipefail

SHARE="/mnt/carc-shared"          # laptop/xeon share; local would be /mnt/c/carc-shared
WORKERS=22
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --share)   SHARE="$2"; shift 2;;
    --workers) WORKERS="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/classical_search/eval_puct_priors.py"

# --- §5(e) curve125 champion leaf env (VERBATIM from optuna_knob_sweep.py lines 61-70) ---
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8
export CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE="-10,-5,-1.25,0,2.5,3.75,5,6.25"
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
# S2 de-risk: explicit 7200s per-game wall (default is 3600; t020's slowest ladder game was 3572s)
export CARCASSONNE_GAME_WALL_SECS=7200

CAND_LEAF_JSON='{"v29_meeple_curve": [-12.62, -6.31, -1.5775, 0.0, 3.155, 4.7325, 6.31, 7.8875], "closure_p": {"1": 0.414, "2": 0.1656, "3": 0.0414}, "bonus_cap": 8.55, "opp_bonus_cap": 9.79}'

ARGS=(
  --candidate puct --opponent puct --opp-pin-champion
  --leaf-quantize float --final-select visits
  --cand-sims 2750 --exact-k 2
  --n 400 --paired
  --seed-start 20100000000
  --out-root "$SHARE/classical_search" --out-subdir t3_optuna_s2/t020
  --exp-id t3_s2_t020 --no-results-csv
  --c-puct 1.88 --tau-p 5.42 --value-norm 13.79
  --cand-leaf-json "$CAND_LEAF_JSON"
  --workers "$WORKERS"
  --shared-claim --claim-host t3-s2-laptop --claim-stale-secs 9000
)

echo "[t3-s2] share=$SHARE workers=$WORKERS wall=${CARCASSONNE_GAME_WALL_SECS}s"
echo "[t3-s2] out=$SHARE/classical_search/t3_optuna_s2/t020  band=2.01e10  n=400 fresh paired"
if [ "$DRY" = "1" ]; then
  echo "[t3-s2] DRY-RUN — command:"; printf '%q ' nice -n 19 "$PY" "$HARNESS" "${ARGS[@]}"; echo
  exit 0
fi

mkdir -p "$REPO/measurement/classical_search"
LOG="$REPO/measurement/classical_search/t3_s2_t020.log"
cd "$REPO"
nice -n 19 setsid "$PY" "$HARNESS" "${ARGS[@]}" </dev/null > "$LOG" 2>&1 &
echo "[t3-s2] launched pid $! ; log $LOG"
