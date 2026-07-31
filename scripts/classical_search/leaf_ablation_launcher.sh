#!/bin/bash
# LEAF-COMPONENT KNOCKOUT ABLATION launcher — the first systematic SUBTRACTIVE ablation of
# the production champion leaf v2.9.2 (Bmild_cap8_curve125, fingerprint a36d2e15).
# Pre-registration: measurement/leaf_ablation_20260730/PREREG.md (COMMITTED before game 1).
#
# Structure lifted verbatim from scripts/classical_search/c7_s1_launcher.sh (the house
# two-box work-stealing pattern): local=primary (aggregates + writes results.csv/progress
# TSV), laptop=helper (contributes games into the SAME shared out-dir via --shared-claim).
#
# ============================ PRE-FLIGHT (read before launch) ============================
# 1. Process census BOTH boxes first. Net-free classical harness (NO carc-orch; CUDA masked).
# 2. Seed band consumed: 9.60e10 — seeds 96,000,000,000..96,000,000,199 (n=400 paired = 200
#    decks x 2 seats), ONE band shared by ALL cells (CRN: every cell plays the SAME 200 decks
#    against the SAME intact-champion opponent). VERIFIED FREE 2026-07-30 against BOTH
#    governance/BAND_REGISTRY.csv and the share-wide manifest seed_start census.
# 3. CHAMPION side = the INTACT champion leaf (env DEFAULT_CONFIG = v2.9.2 curve125 cap8,
#    hash a36d2e15a3b3d71d — runtime-verified 2026-07-30). CANDIDATE side = champion leaf
#    with exactly ONE component knocked out (cells/*.json). SIGN CONVENTION: elo is
#    candidate-minus-champion, so a NEGATIVE elo means the knocked-out component is WORTH
#    that much. The component's value == -elo.
# 4. ALL SIX CELLS STAY ON THE CYTHON FLOAT FAST PATH (verified 2026-07-30: every cell passes
#    _assert_cy_float_path AND is bit-exact cy==pure-python on 360 mid-game states). No leaf
#    source change was needed and none was made — every knockout is an EXISTING LeafConfig
#    field. capoff needs SUPPORTS_F6_SOFT_CAP; both boxes verified True.
# 5. Laptop must be code-synced FIRST (git bundle). No cy rebuild needed (no .pyx change).
# 6. Results land in <SHARE>/leaf_ablation/abl_<cell>/ (per-game json + summary.json +
#    manifest.json w/ per-side leaf_cfg+hash); primary appends results.csv rows exp_id
#    abl_<cell>_vs_puctchamp2750_k2 + one line/cell to
#    measurement/leaf_ablation_20260730/ABL_PROGRESS.tsv.
# =========================================================================================
#
# Usage:
#   local  (primary): nice -n 19 bash scripts/classical_search/leaf_ablation_launcher.sh 16 local
#   laptop (helper):  nice -n 19 bash scripts/classical_search/leaf_ablation_launcher.sh 16 laptop
# Optional:
#   --cells "meepleoff ..."  subset/static split; default = all 6 in PRIORITY order
#   --n 400                  override game count (smoke only)
#   --band 96000000000       override seed band (smoke only)
#   --out-sub-prefix abl_    out-subdir prefix (smoke uses a distinct prefix)
#   --dry-run                print the per-cell harness commands and exit (no compute)
set -u
WORKERS="${1:?usage: leaf_ablation_launcher.sh <WORKERS> <BOX_TAG local|laptop> [opts]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
CELL_DIR=$REPO/measurement/leaf_ablation_20260730/cells
PROG=$REPO/measurement/leaf_ablation_20260730/ABL_PROGRESS.tsv

# ---- pre-registered knobs (PREREG.md "Cell configuration") ----
N=400                      # deck-paired: 200 decks x 2 seats
K=2                        # exact-K both sides (C7 convention)
BAND=96000000000           # 9.60e10, ONE band for all cells (CRN). Verified free 2026-07-30.
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; SIMS=2750   # champion-sibling A/B knobs (C5/C7)

# PRIORITY ORDER (PREREG.md "Priority"). Cells run left-to-right; n=400 completes per-cell
# rather than spreading thin, so a partial night yields whole verdicts, not partial ones.
CELLS_ALL="meepleoff oppanticoff anticoff selfanticoff capoff meepleflat"

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
OUT_ROOT="${ABL_OUT_ROOT:-$SHARE/leaf_ablation}"

CELLS="$CELLS_ALL"; DRYRUN=0; SUBPREFIX=abl_
while [ $# -gt 0 ]; do
  case "$1" in
    --cells)   CELLS="${2:?--cells needs a quoted id list}"; shift 2 ;;
    --n)       N="${2:?--n needs a count}"; shift 2 ;;
    --band)    BAND="${2:?--band needs a seed}"; shift 2 ;;
    --out-sub-prefix) SUBPREFIX="${2:?}"; shift 2 ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
for c in $CELLS; do
  case " $CELLS_ALL " in *" $c "*) ;; *) echo "unknown cell id '$c' (valid: $CELLS_ALL)"; exit 1 ;; esac
  [ -f "$CELL_DIR/abl_${c}_vs_puctchamp2750_k2.json" ] || { echo "missing cell json for '$c'"; exit 1; }
done

# production leaf env for the CHAMPION (opponent) side — the INTACT v2.9.2 champion.
# ** curve125 = the ADOPTED champion (v2_9_2_Bmild_cap8_curve125). Hash a36d2e15a3b3d71d. **
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd $REPO || exit 1
HOST=$(hostname)
ts() { date +%F_%T; }

count_results() { ls "$1"/seed*_a*.json 2>/dev/null | grep -vc summary; }
clean_stale_claims() {   # drop .claim files with no result; arg2=min-age-minutes (empty=all)
  local d="$1" age="${2:-}"; local args=(-name "seed*.claim")
  [ -n "$age" ] && args+=(-mmin "+$age")
  find "$d" "${args[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}
cell_complete() {  # $1 = cell dir -> rc 0 iff summary.json exists with n >= N
  [ -f "$1/summary.json" ] || return 1
  $PY -c "import json,sys;s=json.load(open(sys.argv[1]));sys.exit(0 if s.get('n',0)>=int(sys.argv[2]) else 1)" \
      "$1/summary.json" "$N" 2>/dev/null
}
tsv_line() {  # $1=cell $2=status $3=summary.json(or -) $4=secs -> appends one PROG line
  if [ "$3" != "-" ] && [ -f "$3" ]; then
    $PY - "$1" "$2" "$3" "$4" >> "$PROG" <<'PYEOF'
import json, sys, time
cell, status, path, secs = sys.argv[1:5]
s = json.load(open(path))
ms = s.get("cand_prefix_ms_per_move", 0.0) / max(1e-9, s.get("champ_prefix_ms_per_move", 1.0))
pz = s.get("paired_z"); pz = float("nan") if pz is None else pz
print(f"{cell}\t{status}\t{s['n']}\t{s['W']}\t{s['D']}\t{s['L']}\t{s['elo']:.1f}\t"
      f"{s['elo_sig_1sigma']:.1f}\t{pz:.2f}\t{ms:.2f}\t{secs}\t{time.strftime('%F_%T')}")
PYEOF
  else
    printf "%s\t%s\t-\t-\t-\t-\t-\t-\t-\t-\t%s\t%s\n" "$1" "$2" "$4" "$(ts)" >> "$PROG"
  fi
}

[ "$DRYRUN" = 0 ] && { [ -f "$PROG" ] || echo -e "cell\tstatus\tn\tW\tD\tL\telo\tsigma\tpaired_z\tms_ratio\tsecs\ttimestamp" > "$PROG"; }
echo "[abl $ROLE $HOST $(ts)] start: W=$WORKERS out_root=$OUT_ROOT band=$BAND n=$N cells=[$CELLS]"

for c in $CELLS; do
  exp="abl_${c}_vs_puctchamp2750_k2"
  cell_json="$CELL_DIR/$exp.json"
  sub="${SUBPREFIX}$c"
  dir="$OUT_ROOT/$sub"
  base_args=(--candidate puct --opponent puct
             --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
             --cand-sims $SIMS --exact-k $K --n $N --paired
             --cand-leaf-json "$cell_json" --exp-id "$exp"
             --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$sub")
  if [ "$DRYRUN" = 1 ]; then
    echo "[dry-run] $exp -> nice -n 19 $PY $HARNESS ${base_args[*]} --workers $WORKERS" \
         "--shared-claim --claim-host abl-$ROLE-$HOST --claim-stale-secs 300 --no-results-csv"
    continue
  fi
  mkdir -p "$dir"
  t0=$(date +%s)

  # resume: a cell with a COMPLETE summary.json is done — but primary re-checks the
  # results.csv row (crash-between-summary-and-row recovery; aggregate replays 0 games).
  if cell_complete "$dir"; then
    if [ "$ROLE" = primary ] && ! grep -q "^$exp," "$REPO/experiments/results.csv"; then
      echo "[abl $(ts)] $exp complete but results.csv row missing -> re-aggregate"
      nice -n 19 $PY "$HARNESS" "${base_args[@]}" > "/tmp/abl_agg_${c}.log" 2>&1
    fi
    tsv_line "$c" cached "$dir/summary.json" 0
    echo "[abl $ROLE $(ts)] cell $exp CACHED ($(count_results "$dir")/$N) -> skip"
    continue
  fi

  # primary force-cleans ALL orphan claims at cell start (killed-run recovery)
  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[abl $ROLE $(ts)] cell $exp start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 60 ]; do
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" \
      --workers "$WORKERS" --shared-claim --claim-host "abl-$ROLE-$HOST" --claim-stale-secs 300 \
      --no-results-csv > "/tmp/abl_${ROLE}_${c}.log" 2>&1
    clean_stale_claims "$dir" 4
    iter=$((iter+1))
    [ "$(count_results "$dir")" -lt "$N" ] && sleep 5
  done
  secs=$(( $(date +%s) - t0 ))
  if [ "$(count_results "$dir")" -lt "$N" ]; then
    tsv_line "$c" STALLED - "$secs"
    echo "[abl $ROLE $(ts)] cell $exp STALLED at $(count_results "$dir")/$N -> next cell (NO row written)"
    continue
  fi
  if [ "$ROLE" = primary ]; then
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" > "/tmp/abl_agg_${c}.log" 2>&1
    tsv_line "$c" DONE "$dir/summary.json" "$secs"
    echo "[abl primary $(ts)] cell $exp DONE in ${secs}s -> $(tail -1 "$PROG")"
  else
    tsv_line "$c" helper-done - "$secs"
    echo "[abl helper $(ts)] cell $exp games reached $N in ${secs}s (primary aggregates)"
  fi
done
echo "[abl $ROLE $HOST $(ts)] ALL CELLS PROCESSED"
[ "$ROLE" = primary ] && [ "$DRYRUN" = 0 ] && { echo "=== LEAF ABLATION PROGRESS ==="; cat "$PROG"; }
exit 0
