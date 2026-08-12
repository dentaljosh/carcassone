#!/bin/bash
# TARGETED-DENIAL DOSE SCREEN — per-box cell launcher (block D1 of the 2026-08-12 chain).
# Pre-registration: measurement/denial_screen_20260811/PREREG_DRAFT.md.
# Chain + runbook:  scripts/classical_search/denial_simsplit_chain.sh,
#                   measurement/night_chain_20260812/RUNBOOK.md
#
# WHY THIS EXISTS AND capscurve_resweep_launcher.sh IS NOT REUSED VERBATIM. The prereg
# names that launcher as the instrument, and this script IS it structurally — same harness
# (eval_puct_priors.py, the 2750 ablation class), same env canon, same clock-skew guard,
# same resume loop, same primary/helper roles. What it cannot do is take a cell whose knob
# values are chosen at launch time: capscurve validates every cell id against a hardcoded
# CELLS_ALL and demands a pre-committed cell JSON file per id. The denial doses are NOT
# known until Joshua reads the offline calibration, so the cells are generated at launch
# (by scripts/classical_search/chain_capability_probe.py) into a TSV that both boxes read
# off the share. Everything else is the capscurve launcher's behaviour, deliberately.
#
# ⚠️ NEVER EXPORT CARCASSONNE_DENIAL_* HERE. The env resolves DEFAULT_CONFIG, which is the
#    OPPONENT's leaf as well as the candidate's base. An exported dose would move BOTH
#    arms and the cell would measure nothing while looking perfect. The dose is injected on
#    the CANDIDATE SIDE ONLY, in-process, via --cand-leaf-json (c5_leaf_override semantics:
#    replace-fields on DEFAULT_CONFIG, candidate only, champion side always DEFAULT_CONFIG).
#
# ⚠️ The candidate leaf hash in the TSV is CHECKED at read time by menu_block_summary.py
#    (--expect-cand-leaf-hash). A cell whose manifest hash is the champion's is a
#    silently-default-off arm, which is the failure mode this whole chain is built around.
#
# This script NEVER promotes anything, never writes results.csv (--no-results-csv always),
# never claims a band (the chain does that, once, before game 1) and never touches
# governance/PRODUCTION.yaml.
#
# Usage:
#   nice -n 19 bash scripts/classical_search/denial_cell_launcher.sh <WORKERS|auto> <local|laptop> \
#        --cells-file <tsv> --n <games> --band <seed-start> [--out-root DIR] [--dry-run]
set -u
WORKERS="${1:?usage: denial_cell_launcher.sh <WORKERS|auto> <local|laptop> --cells-file F --n N --band B}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

REPO="${DN_REPO:-/home/doctor/projects/carcassone}"
PY="${DN_PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py

CELLS_FILE=""; N=""; BAND=""; DRYRUN=0; MAXITER=60
SIMS=2750; K=2; CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits
PROFILE=fixed_v1; BACKEND=rust

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared; W_AUTO=30 ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared;   W_AUTO=22 ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
[ "$WORKERS" = auto ] && WORKERS=$W_AUTO
OUT_ROOT="${DN_OUT_ROOT:-$SHARE/night_chain_20260812}"

while [ $# -gt 0 ]; do
  case "$1" in
    --cells-file) CELLS_FILE="${2:?}"; shift 2 ;;
    --n)          N="${2:?}"; shift 2 ;;
    --band)       BAND="${2:?}"; shift 2 ;;
    --out-root)   OUT_ROOT="${2:?}"; shift 2 ;;
    --sims)       SIMS="${2:?}"; shift 2 ;;
    --exact-k)    K="${2:?}"; shift 2 ;;
    --max-iter)   MAXITER="${2:?}"; shift 2 ;;
    --dry-run)    DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
[ -n "$CELLS_FILE" ] || { echo "--cells-file is required"; exit 1; }
[ -n "$N" ]          || { echo "--n is required"; exit 1; }
[ -n "$BAND" ]       || { echo "--band is required"; exit 1; }
[ -f "$CELLS_FILE" ] || { echo "cells file '$CELLS_FILE' not found"; exit 1; }

# ---- canonical leaf env: the INTACT v2.9.2 curve125 champion (hash a36d2e15a3b3d71d).
# Identical to capscurve_resweep_launcher.sh / menu_fair_cell.sh. Do not "tidy".
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# ⚠️ OPENBLAS too — the C5 curve ladder's "x1.75 hang" was OpenBLAS thread oversubscription.
export OPENBLAS_NUM_THREADS=1
# ⚠️ R9 is env-latched at IMPORT (base_deck derives the farm data; the Rust registry latches
# a OnceLock), so it MUST be exported before the harness process starts. --rules-profile
# cannot apply it and only stamps whether we did (manifest rules_profile.r9_env_ok).
export CARCASSONNE_FIX_R9=1
cd "$REPO" || exit 1
HOST=$(hostname); ts() { date +%F_%T; }
tag_log="[denial $ROLE $HOST]"

count_records() { find "$1" -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l; }
# Claims-without-records ONLY, and only older than $2 minutes: a .claim NAMES its owning
# host, so a live sibling box's fresh claim is not stranded (2026-07-30 teacher-h2h).
clean_stale_claims() {
  local d="$1" age="${2:-}"; local a=(-maxdepth 1 -name 'seed*.claim')
  [ -n "$age" ] && a+=(-mmin "+$age")
  find "$d" "${a[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}

if [ "$DRYRUN" = 1 ]; then
  while IFS=$'\t' read -r cell cjson chash; do
    [ -n "${cell:-}" ] || continue
    exp="denial_${cell#d1_denial_}_${PROFILE}_vs_puctchamp${SIMS}_k${K}_n${N}"
    echo "[dry-run] cell $cell (cand_leaf_hash $chash) ->"
    echo "[dry-run]   nice -n 19 $PY -u $HARNESS --candidate puct --opponent puct" \
         "--c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT" \
         "--cand-sims $SIMS --exact-k $K --n $N --paired --backend $BACKEND" \
         "--rules-profile $PROFILE --cand-leaf-json '$cjson' --exp-id $exp" \
         "--seed-start $BAND --out-root $OUT_ROOT --out-subdir $cell --workers $WORKERS" \
         "--shared-claim --claim-host denial-$ROLE-$HOST --claim-stale-secs 300 --no-results-csv"
  done < "$CELLS_FILE"
  exit 0
fi

# ---- CLOCK-SKEW GUARD. claim.py:is_stale() compares the SHARE's mtime clock against this
# client's time.time(); a drifted client sees every sibling claim as stale and STEALS it,
# silently halving two-box throughput with no error. Refuse to start instead.
mkdir -p "$OUT_ROOT"
probe="$OUT_ROOT/.clock_probe_$$"
: > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") )); rm -f "$probe"; askew=${skew#-}
  if [ "$askew" -gt 60 ]; then
    echo "$tag_log $(ts) FATAL: clock skew vs the share = ${skew}s (>60s). Fix with:"
    echo "  sudo -n date -s @\$(ssh <share-host> date +%s)"
    exit 3
  fi
  echo "$tag_log $(ts) clock-skew guard OK (${skew}s)"
else
  echo "$tag_log $(ts) WARNING: could not write a clock probe to $OUT_ROOT - skew unchecked"
fi

echo "$tag_log $(ts) START cells_file=$CELLS_FILE n=$N band=$BAND W=$WORKERS sims=$SIMS out_root=$OUT_ROOT"
while IFS=$'\t' read -r cell cjson chash; do
  [ -n "${cell:-}" ] || continue
  dir="$OUT_ROOT/$cell"
  exp="denial_${cell#d1_denial_}_${PROFILE}_vs_puctchamp${SIMS}_k${K}_n${N}"
  mkdir -p "$dir"
  # The cell's own knob spec, written beside its records so the dir is self-describing
  # (the results-discipline rule: never require dirname archaeology to interpret a cell).
  printf '%s\n' "$cjson" > "$dir/cand_leaf.json.txt"
  printf '%s\n' "$chash" > "$dir/expected_cand_leaf_hash.txt"

  args=(--candidate puct --opponent puct
        --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
        --cand-sims "$SIMS" --exact-k "$K" --n "$N" --paired --backend "$BACKEND"
        --rules-profile "$PROFILE" --cand-leaf-json "$cjson" --exp-id "$exp"
        --seed-start "$BAND" --out-root "$OUT_ROOT" --out-subdir "$cell"
        --no-results-csv)

  echo "$tag_log $(ts) cell $cell start ($(count_records "$dir")/$N cached) hash=$chash"
  clean_stale_claims "$dir" 10
  t0=$(date +%s); iter=0
  while [ "$(count_records "$dir")" -lt "$N" ] && [ "$iter" -lt "$MAXITER" ]; do
    nice -n 19 $PY -u "$HARNESS" "${args[@]}" --workers "$WORKERS" \
        --shared-claim --claim-host "denial-$ROLE-$HOST" --claim-stale-secs 300 \
        >> "$dir/${ROLE}_harness.log" 2>&1
    # ⚠️ CAPTURE rc ON ITS OWN LINE. `echo "$(ts) rc=$?"` evaluates ts() FIRST, so $? is
    # ts's status (always 0) and a harness failure reads as a clean run.
    rc=$?
    iter=$((iter+1))
    echo "$tag_log $(ts) cell $cell pass $iter rc=$rc records=$(count_records "$dir")/$N"
    clean_stale_claims "$dir" 4
    [ "$(count_records "$dir")" -lt "$N" ] && sleep 15
  done
  got=$(count_records "$dir"); secs=$(( $(date +%s) - t0 ))
  # The PRIMARY aggregates: a 0-game --summary-only pass rebuilds summary.json from the
  # records on disk (both boxes' games) without playing anything or touching results.csv.
  if [ "$ROLE" = primary ] && [ "$got" -gt 0 ]; then
    nice -n 19 $PY -u "$HARNESS" "${args[@]}" --summary-only \
        >> "$dir/aggregate.log" 2>&1
    arc=$?
    echo "$tag_log $(ts) cell $cell aggregate rc=$arc"
  fi
  echo "$tag_log $(ts) cell $cell END records=$got/$N in ${secs}s after $iter pass(es)"
  [ "$got" -lt "$N" ] && echo "$tag_log $(ts) cell $cell INCOMPLETE ($got/$N) - the 90% VOID rule applies at read time"
done < "$CELLS_FILE"
echo "$tag_log $(ts) ALL CELLS PROCESSED"
exit 0
