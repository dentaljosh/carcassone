#!/bin/bash
# C7 Stage-1 leaf-terms SCREEN launcher (pre-reg: measurement/classical_search/
# C7_LEAF_TERMS_DESIGN.md "Stage 1"). Term-F ONLY (3 cells) — Term R was DROPPED at
# Stage-0(b) on the per-leaf cost gate (1.20x > 1.10; F passed at 1.07x). Two-box
# work-stealing per cell via eval_puct_priors.py --shared-claim, the c5_s1_launcher.sh
# house pattern (local=primary aggregates + writes results.csv/progress TSV; laptop=helper
# contributes games into the SAME shared out-dir).
#
# ============================ PRE-FLIGHT (read before launch) ============================
# 1. Process census BOTH boxes first. Net-free classical harness (NO carc-orch; CUDA masked).
# 2. Wall-clock: ~45 min/cell two-box (C5 SCREEN_PROGRESS_R5: 2425-3002 s/cell @ n=100 s2750)
#    -> 3 cells ~= 2.25 h two-box ~= 4.5 box-h. NET-FREE CPU worker rule: W~30 local / W~22 laptop.
# 3. Seed band consumed: 1.80e10 — seeds 18,000,000,000..18,000,000,049 (n=100 paired = 50 decks
#    x 2 seats), ONE band shared by all 3 cells (CRN). VERIFIED FREE 2026-07-13 (design's 1.60e10
#    was NOT free -> collided with the D-1 clair sub-ladder clair_pair_*_vs_h6400 @1.6e10; moved).
#    Downstream reserved: 1.81e10 (re-measure), 1.82e10 (S2 confirm), 1.83e10 (S3 fair), 1.84e10 (combo).
# 4. Laptop must be code-synced FIRST (git bundle) AND its cy .so REBUILT (setup_flat_leaf_cy.py
#    build_ext --inplace) — a stale .so silently drops the C7 terms via SUPPORTS_V29_C7_TERMS
#    (candidate then falls back to ~30x pure-Python). Detach every launch, nice -n 19 (built in).
# 5. Results land in <SHARE>/classical_search/c7_s1_<cell>/ (per-game json + summary.json +
#    manifest.json w/ per-side leaf_cfg+hash); primary appends results.csv rows exp_id
#    c7_<cell>_vs_puctchamp2750_k2 + one line/cell to measurement/classical_search/C7_S1_PROGRESS.tsv.
# 6. CHAMPION side = curve125 (the ADOPTED champion) via env DEFAULT_CONFIG. The candidate side
#    inherits curve125 and adds ONLY v29_farm_flip_k (c7_cells/*.json). ** The champion curve env
#    below is curve125, NOT the c5 launcher's stale curve100. ** Candidate=curve125+flip vs
#    champion=curve125 is the clean isolate-F A/B.
# =========================================================================================
#
# Usage:
#   local  (primary): nice -n 19 bash scripts/classical_search/c7_s1_launcher.sh 30 local
#   laptop (helper):  nice -n 19 bash scripts/classical_search/c7_s1_launcher.sh 22 laptop
# Optional:
#   --cells "flip050 ..."   subset/static split; default = all 3 (R-first priority: flip050 flip025 flip100)
#   --dry-run               print the per-cell harness commands and exit (no compute)
set -u
WORKERS="${1:?usage: c7_s1_launcher.sh <WORKERS> <BOX_TAG local|laptop> [--cells \"id ...\"] [--dry-run]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
CELL_DIR=$REPO/measurement/classical_search/c7_cells
PROG=$REPO/measurement/classical_search/C7_S1_PROGRESS.tsv

# ---- pre-registered S1 knobs (C7_LEAF_TERMS_DESIGN.md "Stage 1") ----
N=100                      # deck-paired: 50 decks x 2 seats
K=2                        # exact-K both sides
BAND=18000000000           # 1.80e10, ONE band for all cells (CRN). 1.60e10 was NOT free (D-1 ladder).
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; SIMS=2750   # champion-sibling A/B knobs

# 3 Term-F dose cells + 3 Term-R dose cells. R RE-ADDED 2026-07-14 (Joshua accepts the 1.2x per-leaf
# cost): screen R at equal sims=2750, read RAW paired elo vs the +35/z1.5 gate (NO cost penalty — cost
# accepted); the in-run ms-ratio will show ~1.2, expected/fine. OFF == champion == 0 by construction.
# Run R alone with: --cells "ret050 ret100 ret200" (band 1.80e10, CRN-shares the champion decks with F).
CELLS_ALL="flip025 flip050 flip100 ret050 ret100 ret200"

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
OUT_ROOT="${C7_OUT_ROOT:-$SHARE/classical_search}"

CELLS="$CELLS_ALL"; DRYRUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --cells)   CELLS="${2:?--cells needs a quoted id list}"; shift 2 ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
for c in $CELLS; do
  case " $CELLS_ALL " in *" $c "*) ;; *) echo "unknown cell id '$c' (valid: $CELLS_ALL)"; exit 1 ;; esac
  [ -f "$CELL_DIR/c7_${c}_vs_puctchamp2750_k2.json" ] || { echo "missing cell json for '$c'"; exit 1; }
done

# production leaf env for the CHAMPION side (harness setdefaults these; explicit per house pattern).
# ** curve125 = the ADOPTED champion (v2_9_2_Bmild_cap8_curve125), NOT curve100. **
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
echo "[c7-s1 $ROLE $HOST $(ts)] start: W=$WORKERS out_root=$OUT_ROOT band=$BAND cells=[$CELLS]"

for c in $CELLS; do
  exp="c7_${c}_vs_puctchamp2750_k2"
  cell_json="$CELL_DIR/$exp.json"
  sub="c7_s1_$c"
  dir="$OUT_ROOT/$sub"
  base_args=(--candidate puct --opponent puct
             --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
             --cand-sims $SIMS --exact-k $K --n $N --paired
             --cand-leaf-json "$cell_json" --exp-id "$exp"
             --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$sub")
  if [ "$DRYRUN" = 1 ]; then
    echo "[dry-run] $exp -> nice -n 19 $PY $HARNESS ${base_args[*]} --workers $WORKERS" \
         "--shared-claim --claim-host c7-$ROLE-$HOST --claim-stale-secs 300 --no-results-csv"
    continue
  fi
  mkdir -p "$dir"
  t0=$(date +%s)

  # resume: a cell with a COMPLETE summary.json is done — but primary re-checks the
  # results.csv row (crash-between-summary-and-row recovery; aggregate replays 0 games).
  if cell_complete "$dir"; then
    if [ "$ROLE" = primary ] && ! grep -q "^$exp," "$REPO/experiments/results.csv"; then
      echo "[c7-s1 $(ts)] $exp complete but results.csv row missing -> re-aggregate"
      nice -n 19 $PY "$HARNESS" "${base_args[@]}" > "/tmp/c7s1_agg_${c}.log" 2>&1
    fi
    tsv_line "$c" cached "$dir/summary.json" 0
    echo "[c7-s1 $ROLE $(ts)] cell $exp CACHED ($(count_results "$dir")/$N) -> skip"
    continue
  fi

  # primary force-cleans ALL orphan claims at cell start (killed-run recovery)
  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[c7-s1 $ROLE $(ts)] cell $exp start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 60 ]; do
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" \
      --workers "$WORKERS" --shared-claim --claim-host "c7-$ROLE-$HOST" --claim-stale-secs 300 \
      --no-results-csv > "/tmp/c7s1_${ROLE}_${c}.log" 2>&1
    clean_stale_claims "$dir" 4
    iter=$((iter+1))
    [ "$(count_results "$dir")" -lt "$N" ] && sleep 5
  done
  secs=$(( $(date +%s) - t0 ))
  if [ "$(count_results "$dir")" -lt "$N" ]; then
    tsv_line "$c" STALLED - "$secs"
    echo "[c7-s1 $ROLE $(ts)] cell $exp STALLED at $(count_results "$dir")/$N -> next cell (NO row written)"
    continue
  fi
  if [ "$ROLE" = primary ]; then
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" > "/tmp/c7s1_agg_${c}.log" 2>&1
    tsv_line "$c" DONE "$dir/summary.json" "$secs"
    echo "[c7-s1 primary $(ts)] cell $exp DONE in ${secs}s -> $(tail -1 "$PROG")"
  else
    tsv_line "$c" helper-done - "$secs"
    echo "[c7-s1 helper $(ts)] cell $exp games reached $N in ${secs}s (primary aggregates)"
  fi
done
echo "[c7-s1 $ROLE $HOST $(ts)] ALL CELLS PROCESSED"
[ "$ROLE" = primary ] && [ "$DRYRUN" = 0 ] && { echo "=== C7 S1 PROGRESS ==="; cat "$PROG"; }
exit 0
