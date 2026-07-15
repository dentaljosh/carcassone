#!/usr/bin/env bash
# T3 Optuna S3 — FAIR-TRANSFER decisive deployability test. Everything upstream of S3
# (rung-C, S2) was CLAIRVOYANT (both players see the pre-shuffled deck). Deployable play
# is FAIR (blind PIMC root-determinization). Two candidates fired at rung C (t020
# +36.3/z2.97 AND t27 +34.9/z2.35 — both clairvoyant); S3 asks: does either candidate's
# clairvoyant edge SURVIVE the transfer to fair play, vs the production champion?
#
# The fair harness (eval_fair_puct.py --info fair) plays a CONFIGURED champion (the
# candidate/prefix, set by --c-puct/--tau-p/--value-norm + --cand-leaf-json) vs a FIXED
# rung (HeuristicMCTS @ rung_sims=800, c=3.0, v2.9 Bmild_cap8 DEFAULT_CONFIG leaf). The
# GameResult records diff = champion − rung. There is NO symmetric candidate-vs-champion
# mode, so S3 is a DELTA-OF-DELTAS: run each candidate arm AND a shared champion-baseline
# arm vs the SAME rung on the SAME decks (CRN, same --seed-start), then compare per-deck
# margins (candidate − champ_base).
#
#   t020_cand (candidate): c1.88 / tau5.42 / vnorm13.79 + t020 leaf (hash a995a38d)
#                          curve125 x1.262 = [-12.62,-6.31,-1.5775,0,3.155,4.7325,6.31,7.8875]
#                          closure_p x0.828 = {1:0.414,2:0.1656,3:0.0414}; bcap 8.55; opp 9.79
#   t27_cand  (candidate): c1.51 / tau5.94 / vnorm15.32 + t27 leaf (hash 0e8b4bc8)
#                          curve x1.261 = [-12.61,-6.305,-1.57625,0,3.1525,4.72875,6.305,7.88125]
#                          closure_p = {1:0.4025,2:0.161,3:0.04025}; bcap 8.74; opp 9.91
#   champ_base (baseline): c1.5  / tau5.0  / vnorm15.0  + NO --cand-leaf-json
#                          (candidate side stays DEFAULT_CONFIG = the champion leaf, hash a36d2e15)
#
# The h800 rung side ALWAYS keeps env DEFAULT_CONFIG (the CL-022 ruler must not move) in
# ALL arms, so its leaf is a36d2e15 everywhere and the paired Δ isolates the champion side.
#
# S3 VERDICT (after all arms finish n=400): the CRN margin-of-margins per candidate, read
# with crn_delta_fairnet.py (its "fair-net" arm == a candidate, its "fair" arm == the
# baseline; Δ = per-deck (cand − rung) − (champ − rung) = cand − champ):
#   .venv/bin/python scripts/classical_search/crn_delta_fairnet.py \
#       --fairnet-dir  <SHARE>/classical_search/t3_s3/t020_cand \
#       --baseline-dir <SHARE>/classical_search/t3_s3/champ_base \
#       --out          <SHARE>/classical_search/t3_s3/s3_verdict_t020.json
#   .venv/bin/python scripts/classical_search/crn_delta_fairnet.py \
#       --fairnet-dir  <SHARE>/classical_search/t3_s3/t27_cand \
#       --baseline-dir <SHARE>/classical_search/t3_s3/champ_base \
#       --out          <SHARE>/classical_search/t3_s3/s3_verdict_t27.json
#
# ⚠️ NO-TOUCH: governance/PRODUCTION.yaml is never read or written. --no-results-csv on
#    every arm (eval_fair_puct never writes results.csv anyway; flag kept for intent).
# ⚠️ eval_fair_puct.py has NO --exp-id flag (unlike eval_puct_priors.py) — the exp-ids
#    t3_s3_<arm> are used ONLY for the per-arm log filename; the out-subdir is what keeps
#    the arms' JSONs in disjoint directories.
#
# Usage: t3_s3_launch.sh [--arm {t020_cand,t27_cand,champ_base,all}]
#                        [--share PATH] [--workers N] [--n N] [--out-prefix PREFIX] [--dry-run]
#   --arm        which arm(s) to launch (default all). Each arm is independently launchable
#                (arms run on different boxes / in parallel; all use --shared-claim = resumable).
#   --share      share root (default /mnt/carc-shared = laptop/xeon; local = /mnt/c/carc-shared)
#   --workers    per-arm worker count (default 22)
#   --n          games per arm (default 400 = the production run; use 2 for a smoke)
#   --out-prefix out-subdir prefix (default t3_s3; use e.g. t3_s3_smoke for a throwaway smoke)
#   --dry-run    print the command(s) that WOULD run, launch nothing
set -euo pipefail

ARM="all"
SHARE="/mnt/carc-shared"          # laptop/xeon share; local would be /mnt/c/carc-shared
WORKERS=22
N=400
OUT_PREFIX="t3_s3"
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --arm)        ARM="$2"; shift 2;;
    --share)      SHARE="$2"; shift 2;;
    --workers)    WORKERS="$2"; shift 2;;
    --n)          N="$2"; shift 2;;
    --out-prefix) OUT_PREFIX="$2"; shift 2;;
    --dry-run)    DRY=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
case "$ARM" in t020_cand|t27_cand|champ_base|all) ;;
  *) echo "--arm must be one of: t020_cand t27_cand champ_base all" >&2; exit 2;; esac

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"

# --- §5(e) curve125 champion leaf env (VERBATIM from optuna_knob_sweep.py lines 61-70) ---
# This resolves DEFAULT_CONFIG (the champion/baseline leaf AND the h800 rung leaf) to the
# curve125 hash a36d2e15, and makes --cand-leaf-json resolve each candidate leaf as a
# replace-fields overlay on it. OPENBLAS_NUM_THREADS=1 is REQUIRED — a prior fair run hung
# from OpenBLAS thread oversubscription under --shared-claim multi-worker (see
# C5_CURVE125_PROPOSAL.md; eval_fair_puct._CANON_ENV documents the same root-cause).
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8
export CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE="-10,-5,-1.25,0,2.5,3.75,5,6.25"
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
# Env parity with the S2 launcher. NOTE: eval_fair_puct.py does NOT read
# CARCASSONNE_GAME_WALL_SECS (only eval_puct_priors.py does) — it is INERT for the fair
# harness (fair games are bounded instead by the solver node budget, EXACT_BUDGET, which
# falls back to the fair prefix on BudgetExceeded). Kept for env symmetry with S2.
export CARCASSONNE_GAME_WALL_SECS=7200

# Candidate leaf overrides — replace-fields on DEFAULT_CONFIG.
CAND_LEAF_T020='{"v29_meeple_curve": [-12.62, -6.31, -1.5775, 0.0, 3.155, 4.7325, 6.31, 7.8875], "closure_p": {"1": 0.414, "2": 0.1656, "3": 0.0414}, "bonus_cap": 8.55, "opp_bonus_cap": 9.79}'
CAND_LEAF_T27='{"v29_meeple_curve": [-12.61, -6.305, -1.57625, 0.0, 3.1525, 4.72875, 6.305, 7.88125], "closure_p": {"1": 0.4025, "2": 0.161, "3": 0.04025}, "bonus_cap": 8.74, "opp_bonus_cap": 9.91}'

# Build arm $1's argv into the global ARGS array (bash array so the space-containing
# --cand-leaf-json JSON stays ONE argument — the S2 template's pattern; an echo/$()
# build would word-split the JSON and silently corrupt the candidate leaf).
# common args (all arms): fair PIMC, k4x688~2752 total, K=2 marginalized endgame handoff,
# fixed h800 rung, n paired on the S3 band 2.02e10 (fresh/disjoint from prior bands).
build_args() {   # $1 = arm name ; sets global ARGS
  local arm="$1" sub="$OUT_PREFIX/$1" host="t3-s3-$1"
  ARGS=(
    --info fair
    --k-dets 4 --sims 688 --exact-k 2 --rung-sims 800
    --n "$N" --paired --seed-start 20200000000
    --leaf-quantize float --final-select visits
    --out-root "$SHARE/classical_search" --out-subdir "$sub"
    --no-results-csv
    --shared-claim --claim-host "$host" --claim-stale-secs 9000
    --workers "$WORKERS"
  )
  case "$arm" in
    t020_cand)
      ARGS+=( --c-puct 1.88 --tau-p 5.42 --value-norm 13.79
              --cand-leaf-json "$CAND_LEAF_T020" ) ;;   # leaf a995a38d
    t27_cand)
      ARGS+=( --c-puct 1.51 --tau-p 5.94 --value-norm 15.32
              --cand-leaf-json "$CAND_LEAF_T27" ) ;;    # leaf 0e8b4bc8
    champ_base)
      ARGS+=( --c-puct 1.5 --tau-p 5.0 --value-norm 15.0 ) ;;  # DEFAULT_CONFIG a36d2e15
  esac
}

launch_arm() {   # $1 = arm name ; exp-id (= t3_s3_<arm>) used only for the log name
  local arm="$1" expid="t3_s3_$1" logname
  build_args "$arm"
  mkdir -p "$REPO/measurement/classical_search"
  logname="$REPO/measurement/classical_search/${expid}.log"
  if [ "$DRY" = "1" ]; then
    echo "[t3-s3] DRY-RUN arm $arm ($expid) — command:"
    printf '%q ' nice -n 19 "$PY" "$HARNESS" "${ARGS[@]}"; echo
    return 0
  fi
  echo "[t3-s3] arm=$arm share=$SHARE workers=$WORKERS n=$N out=$SHARE/classical_search/$OUT_PREFIX/$arm  log=$logname"
  cd "$REPO"
  nice -n 19 setsid "$PY" "$HARNESS" "${ARGS[@]}" </dev/null > "$logname" 2>&1 &
  echo "[t3-s3] launched arm $arm pid $! ; log $logname"
}

echo "[t3-s3] band=2.02e10  n=$N paired  fair k4x688 K=2 vs h800  arm(s)=$ARM"
case "$ARM" in
  all) launch_arm t020_cand; launch_arm t27_cand; launch_arm champ_base ;;
  *)   launch_arm "$ARM" ;;
esac
