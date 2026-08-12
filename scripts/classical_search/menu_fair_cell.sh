#!/bin/bash
# LEVER-MENU generic FAIR-PIMC cell launcher (items 2 and 3, and item 2's wiring gate).
# Spec of record: docs/LEVER_MENU_PLAN_20260810.md (FUNDED IN FULL 2026-08-10).
#
# WHY A GENERIC LAUNCHER AND NOT TWO SCRIPTS. Items 2 and 3 are the SAME cell shape — one
# `eval_fair_puct.py --info fair --opponent fair-champion` head-to-head, deck-paired,
# fixed_v1+R9, rust, two-box `--shared-claim` — differing only in (a) which side carries a
# `--cand-leaf-json` knob and (b) the per-arm budget flags. Everything that is easy to get
# wrong (the env canon, the R9 export, the clock-skew guard, claim hygiene, the resume loop)
# is identical, so it lives here once. Structure is lifted from
# curvephase_ladder_launcher.sh (the launcher that ran the 2026-08-10 b0p3 powered confirm)
# with the capscurve launcher's resume loop grafted on.
#
# ⚠️ ASYMMETRIC BUDGETS NEED BOTH FLAGS. `--opp-sims` alone silently leaves the opponent at
#    the CANDIDATE's k_dets. Item 3 (k4x2752 candidate vs k8x1376 champion) passes
#    --opp-k-dets AND --opp-sims. This is called out in the plan §4.3 for a reason.
#
# ⚠️ --drift (=--allow-cand-curve-drift) STAMPS the candidate leaf instead of asserting
#    curve125. It is what lets a knocked-out leaf reach the fair harness at all, and
#    eval_fair_puct permits it ONLY under --info fair --opponent fair-champion AND only
#    when the candidate JSON carries an explicit 8-entry finite curve (_stamp_cand_leaf).
#    That is why the menu's cell JSONs carry curve125 verbatim alongside the knob.
#    The OPPONENT arm is untouched and still passes the unmodified curve125 assert.
#
# This script NEVER promotes anything, never edits governance/PRODUCTION.yaml, and never
# writes a results.csv row (--no-results-csv always). Reading and close-out are the
# orchestrating session's job.
#
# Usage:
#   nice -n 19 bash scripts/classical_search/menu_fair_cell.sh <WORKERS|auto> <local|laptop> \
#        --sub <out-subdir> --n <games> --band <seed-start> [opts]
# Opts:
#   --cand-leaf-json <path>   candidate-side leaf override (item 2; omit for item 3)
#   --drift                   pass --allow-cand-curve-drift (required with a hash-moving knob)
#   --k-dets N --sims N       CANDIDATE budget           (default 8 / 1376 = the deploy champion)
#   --opp-k-dets N --opp-sims N   OPPONENT budget        (default: symmetric with the candidate)
#   --sims-tile N --sims-meeple N  CANDIDATE per-phase sims split (added 2026-08-12 for the
#                             sims-split screen, block S1). PASSED THROUGH ONLY WHEN SET, so
#                             every pre-existing caller is byte-identical to before — and a
#                             harness that does not define the flags fails LOUDLY (unknown
#                             argument) instead of quietly running an unsplit candidate.
#                             The chain probes `eval_fair_puct.py --help` for both flags and
#                             SKIPS its block if they are absent; it never passes them blind.
#   --max-iter N              resume-loop cap (default 60)
#   --dry-run                 print the resolved harness command and exit
set -u
WORKERS="${1:?usage: menu_fair_cell.sh <WORKERS|auto> <local|laptop> --sub S --n N --band B [opts]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

REPO="${MENU_REPO:-/home/doctor/projects/carcassone}"
PY="${MENU_PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
HARNESS=$REPO/scripts/classical_search/eval_fair_puct.py

SUB=""; N=""; BAND=""; CANDJSON=""; DRIFT=0; DRYRUN=0; MAXITER=60
KDETS=8; SIMS=1376; OPPK=""; OPPS=""; K=2; STILE=""; SMEEPLE=""
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; PROFILE=fixed_v1; BACKEND=rust

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared; W_AUTO=14 ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared;   W_AUTO=22 ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
[ "$WORKERS" = auto ] && WORKERS=$W_AUTO

while [ $# -gt 0 ]; do
  case "$1" in
    --sub)            SUB="${2:?}"; shift 2 ;;
    --n)              N="${2:?}"; shift 2 ;;
    --band)           BAND="${2:?}"; shift 2 ;;
    --cand-leaf-json) CANDJSON="${2:?}"; shift 2 ;;
    --drift)          DRIFT=1; shift ;;
    --k-dets)         KDETS="${2:?}"; shift 2 ;;
    --sims)           SIMS="${2:?}"; shift 2 ;;
    --opp-k-dets)     OPPK="${2:?}"; shift 2 ;;
    --opp-sims)       OPPS="${2:?}"; shift 2 ;;
    --sims-tile)      STILE="${2:?}"; shift 2 ;;
    --sims-meeple)    SMEEPLE="${2:?}"; shift 2 ;;
    --exact-k)        K="${2:?}"; shift 2 ;;
    --max-iter)       MAXITER="${2:?}"; shift 2 ;;
    --dry-run)        DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
[ -n "$SUB" ]  || { echo "--sub is required"; exit 1; }
[ -n "$N" ]    || { echo "--n is required"; exit 1; }
[ -n "$BAND" ] || { echo "--band is required"; exit 1; }
[ -z "$CANDJSON" ] || [ -f "$CANDJSON" ] || { echo "missing cand leaf json '$CANDJSON'"; exit 1; }

OUT_ROOT="${MENU_OUT_ROOT:-$SHARE/lever_menu_20260810}"
dir="$OUT_ROOT/$SUB"

# ---- canonical leaf env: the INTACT v2.9.2 curve125 champion (hash a36d2e15a3b3d71d).
# The candidate-side knob is injected IN-PROCESS via --cand-leaf-json; the env must stay the
# champion so DEFAULT_CONFIG (and therefore the opponent arm) cannot move underneath the cell.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# ⚠️ OPENBLAS too — the C5 curve ladder's "x1.75 hang" was OpenBLAS thread oversubscription.
export OPENBLAS_NUM_THREADS=1
# ⚠️ R9 is env-latched at IMPORT (base_deck derives the farm data; the Rust registry latches a
# OnceLock), so it MUST be exported before the harness process starts. --rules-profile cannot
# apply it and only stamps whether we did (manifest rules_profile.r9_env_ok).
export CARCASSONNE_FIX_R9=1
cd "$REPO" || exit 1
HOST=$(hostname); ts() { date +%F_%T; }
tag="[menu-fair $ROLE $HOST]"

args=(--info fair --opponent fair-champion --backend "$BACKEND"
      --k-dets "$KDETS" --sims "$SIMS" --exact-k "$K"
      --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
      --n "$N" --paired --seed-start "$BAND"
      --rules-profile "$PROFILE" --workers "$WORKERS"
      --out-root "$OUT_ROOT" --out-subdir "$SUB"
      --shared-claim --claim-host "menu-$ROLE-$HOST" --claim-stale-secs 900
      --no-results-csv)
[ -n "$OPPK" ]     && args+=(--opp-k-dets "$OPPK")
[ -n "$OPPS" ]     && args+=(--opp-sims "$OPPS")
# Per-phase split: candidate side only, appended ONLY when set (see the header note).
[ -n "$STILE" ]    && args+=(--sims-tile "$STILE")
[ -n "$SMEEPLE" ]  && args+=(--sims-meeple "$SMEEPLE")
[ -n "$CANDJSON" ] && args+=(--cand-leaf-json "$CANDJSON")
[ "$DRIFT" = 1 ]   && args+=(--allow-cand-curve-drift)

if [ "$DRYRUN" = 1 ]; then
  echo "[dry-run] $PY -u $HARNESS ${args[*]}"; exit 0
fi

# ---- CLOCK-SKEW GUARD. claim.py:is_stale() compares the SHARE's mtime clock against this
# client's time.time(); a drifted client sees every sibling claim as stale and STEALS it,
# silently halving two-box throughput with no error. Refuse to start instead.
mkdir -p "$dir"
probe="$OUT_ROOT/.clock_probe_$$"
: > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") )); rm -f "$probe"; askew=${skew#-}
  if [ "$askew" -gt 60 ]; then
    echo "$tag $(ts) FATAL: clock skew vs the share = ${skew}s (>60s). Fix with:"
    echo "  sudo -n date -s @\$(ssh <share-host> date +%s)"
    exit 3
  fi
  echo "$tag $(ts) clock-skew guard OK (${skew}s)"
else
  echo "$tag $(ts) WARNING: could not write a clock probe to $OUT_ROOT - skew unchecked"
fi

count_records() { find "$1" -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l; }
# Claims-without-records only. A .claim NAMES the host that owns it; a live sibling box's
# claim is NOT stranded (2026-07-30 teacher-h2h incident). $2 = min age in minutes, so a
# claim taken seconds ago by the other box is never swept.
clean_stale_claims() {
  local d="$1" age="${2:-}"; local a=(-maxdepth 1 -name 'seed*.claim')
  [ -n "$age" ] && a+=(-mmin "+$age")
  find "$d" "${a[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}

echo "$tag $(ts) START sub=$SUB n=$N band=$BAND W=$WORKERS cand=k${KDETS}x${SIMS} opp=k${OPPK:-$KDETS}x${OPPS:-$SIMS} drift=$DRIFT cand_json=${CANDJSON:-none} split=${STILE:-none}/${SMEEPLE:-none}"
clean_stale_claims "$dir" 10
t0=$(date +%s); iter=0
while [ "$(count_records "$dir")" -lt "$N" ] && [ "$iter" -lt "$MAXITER" ]; do
  nice -n 19 $PY -u "$HARNESS" "${args[@]}"
  # ⚠️ CAPTURE rc ON ITS OWN LINE. `echo "$(ts) rc=$?"` evaluates ts() FIRST, so $? is ts's
  # status (always 0) and a harness failure reads as a clean run. Cost 2 h on 2026-08-09.
  rc=$?
  iter=$((iter+1))
  echo "$tag $(ts) harness pass $iter rc=$rc records=$(count_records "$dir")/$N"
  clean_stale_claims "$dir" 10
  [ "$(count_records "$dir")" -lt "$N" ] && sleep 15
done
secs=$(( $(date +%s) - t0 ))
got=$(count_records "$dir")
echo "$tag $(ts) END sub=$SUB records=$got/$N in ${secs}s after $iter pass(es)"
# >=90% completion or the cell is VOID (the standing rule). Report it; do not judge it.
[ "$got" -lt "$N" ] && echo "$tag $(ts) INCOMPLETE ($got/$N = $(( 100 * got / N ))%) - the 90% VOID rule applies at read time"
exit 0
