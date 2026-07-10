#!/bin/bash
# C5 Stage-1 leaf-retune SCREEN launcher (pre-reg: measurement/classical_search/
# C5_LEAF_RETUNE_DESIGN.md "Stage 1"). 10 cells SEQUENTIAL, two-box work-stealing
# per cell via eval_puct_priors.py --shared-claim (the run_screen_sweep.sh house
# pattern: local=primary aggregates + writes results.csv/progress TSV, laptop=helper
# just contributes games into the SAME shared out-dir).
#
# ============================ PRE-FLIGHT (read before launch) ============================
# 1. Process census BOTH boxes first (ps -o pid,etime,%cpu,comm -C python --sort=-etime +
#    scripts/cluster_status.py): no other eval/gen may be running — this is a CPU-saturating
#    net-free classical harness (NO carc-orch server needed; CUDA is masked by the harness).
# 2. Wall-clock: ~45 min/cell two-box (SCREEN_PROGRESS_R5 measured 2425-3002 s/cell at
#    n=100 s2750) -> 10 cells ~= 7.5 h two-box wall ~= 15 box-h. Workers follow NET-FREE
#    CPU rules: W~30 local(5900XT) / W~22 laptop (NOT the orch W48/26 counts).
# 3. Seed band consumed: 1.20e10 — seeds 12,000,000,000..12,000,000,049 (n=100 paired =
#    50 decks x 2 seats), ONE band shared by ALL 10 cells (CRN across cells, pre-registered).
#    Bands 1.21e10 (re-measure), 1.22e10 (2x2), 1.24e10 (confirm) stay RESERVED.
# 4. Laptop must be code-synced FIRST (git bundle — memory reference_offline_git_bundle_sync):
#    it needs eval_puct_priors.py @>=this commit, measurement/classical_search/c5_cells/*.json
#    and this launcher. Detach every launch (setsid ... </dev/null &), nice -n 19 (built in).
# 5. Results land in <SHARE>/classical_search/c5_s1_<cell>/ (per-game json + summary.json +
#    manifest.json w/ per-side leaf_cfg+hash); primary appends results.csv rows with the
#    PRE-REGISTERED exp_ids c5_<cell>_vs_puctchamp2750_k2 + one line per cell to
#    measurement/classical_search/C5_S1_PROGRESS.tsv. Champion side stays env DEFAULT_CONFIG.
# =========================================================================================
#
# Usage:
#   local  (primary): nice -n 19 bash scripts/classical_search/c5_s1_launcher.sh 30 local
#   laptop (helper):  nice -n 19 bash scripts/classical_search/c5_s1_launcher.sh 22 laptop
# Optional:
#   --cells "cap5 cap12 ..."   subset/static split (short ids below); default = all 10 in
#                              the design's budget-squeeze priority order
#   --dry-run                  print the per-cell harness commands and exit (no compute)
#
# BOX_TAG: local|primary -> primary role (share /mnt/c/carc-shared);
#          laptop|helper -> helper role (share /mnt/carc-shared).
set -u
WORKERS="${1:?usage: c5_s1_launcher.sh <WORKERS> <BOX_TAG local|laptop> [--cells \"id ...\"] [--dry-run]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
CELL_DIR=$REPO/measurement/classical_search/c5_cells
PROG=$REPO/measurement/classical_search/C5_S1_PROGRESS.tsv

# ---- pre-registered S1 knobs (C5_LEAF_RETUNE_DESIGN.md "Stage 1") ----
N=100                      # deck-paired: 50 decks x 2 seats
K=2                        # exact-K both sides
BAND=12000000000           # 1.20e10, ONE band for all cells (CRN)
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; SIMS=2750   # champion-sibling A/B knobs

# the 10 cells, design's budget-squeeze priority order: caps -> closure_p -> opp_cap
# -> curve -> bag. Short id <cell>; full pre-registered exp_id = c5_<cell>_vs_puctchamp2750_k2;
# leaf json = measurement/classical_search/c5_cells/c5_<cell>_vs_puctchamp2750_k2.json.
CELLS_ALL="cap5 cap12 pclose080 pclose120 oppcap4 oppcap12 curve075 curve125 nocurve_mk2 bagclose"

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
OUT_ROOT="${C5_OUT_ROOT:-$SHARE/classical_search}"

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
  [ -f "$CELL_DIR/c5_${c}_vs_puctchamp2750_k2.json" ] || { echo "missing cell json for '$c'"; exit 1; }
done

# production leaf env for the CHAMPION side (harness setdefaults these too; explicit
# per run_screen_sweep.sh house pattern — Trap 1: env-absent workers silently run cap5)
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0
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
echo "[c5-s1 $ROLE $HOST $(ts)] start: W=$WORKERS out_root=$OUT_ROOT band=$BAND cells=[$CELLS]"

for c in $CELLS; do
  exp="c5_${c}_vs_puctchamp2750_k2"
  cell_json="$CELL_DIR/$exp.json"
  sub="c5_s1_$c"
  dir="$OUT_ROOT/$sub"
  base_args=(--candidate puct --opponent puct
             --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
             --cand-sims $SIMS --exact-k $K --n $N --paired
             --cand-leaf-json "$cell_json" --exp-id "$exp"
             --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$sub")
  if [ "$DRYRUN" = 1 ]; then
    echo "[dry-run] $exp -> nice -n 19 $PY $HARNESS ${base_args[*]} --workers $WORKERS" \
         "--shared-claim --claim-host c5-$ROLE-$HOST --claim-stale-secs 300 --no-results-csv"
    continue
  fi
  mkdir -p "$dir"
  t0=$(date +%s)

  # resume: a cell with a COMPLETE summary.json is done — but primary re-checks the
  # results.csv row (crash-between-summary-and-row recovery; aggregate replays 0 games).
  if cell_complete "$dir"; then
    if [ "$ROLE" = primary ] && ! grep -q "^$exp," "$REPO/experiments/results.csv"; then
      echo "[c5-s1 $(ts)] $exp complete but results.csv row missing -> re-aggregate"
      nice -n 19 $PY "$HARNESS" "${base_args[@]}" > "/tmp/c5s1_agg_${c}.log" 2>&1
    fi
    tsv_line "$c" cached "$dir/summary.json" 0
    echo "[c5-s1 $ROLE $(ts)] cell $exp CACHED ($(count_results "$dir")/$N) -> skip"
    continue
  fi

  # primary force-cleans ALL orphan claims at cell start (killed-run recovery)
  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[c5-s1 $ROLE $(ts)] cell $exp start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 60 ]; do
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" \
      --workers "$WORKERS" --shared-claim --claim-host "c5-$ROLE-$HOST" --claim-stale-secs 300 \
      --no-results-csv > "/tmp/c5s1_${ROLE}_${c}.log" 2>&1
    clean_stale_claims "$dir" 4
    iter=$((iter+1))
    [ "$(count_results "$dir")" -lt "$N" ] && sleep 5
  done
  secs=$(( $(date +%s) - t0 ))
  if [ "$(count_results "$dir")" -lt "$N" ]; then
    tsv_line "$c" STALLED - "$secs"
    echo "[c5-s1 $ROLE $(ts)] cell $exp STALLED at $(count_results "$dir")/$N -> next cell (NO row written)"
    continue
  fi
  if [ "$ROLE" = primary ]; then
    # aggregate: all games cached -> plays nothing; writes summary.json + manifest +
    # the pre-registered results.csv row (exp_id=$exp)
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" > "/tmp/c5s1_agg_${c}.log" 2>&1
    tsv_line "$c" DONE "$dir/summary.json" "$secs"
    echo "[c5-s1 primary $(ts)] cell $exp DONE in ${secs}s -> $(tail -1 "$PROG")"
  else
    tsv_line "$c" helper-done - "$secs"
    echo "[c5-s1 helper $(ts)] cell $exp games reached $N in ${secs}s (primary aggregates)"
  fi
done
echo "[c5-s1 $ROLE $HOST $(ts)] ALL CELLS PROCESSED"
[ "$ROLE" = primary ] && [ "$DRYRUN" = 0 ] && { echo "=== C5 S1 PROGRESS ==="; cat "$PROG"; }
exit 0
