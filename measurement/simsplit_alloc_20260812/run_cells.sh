#!/bin/bash
# SIMS-SPLIT ALLOCATION A/B driver — prereg: measurement/simsplit_alloc_20260812/PREREG.md
#
# Two cells, ONE shared band (123000000000), CRN, run SEQUENTIALLY so each gets the full
# two-box worker pool:
#   A  a_split_t2752_m1376   cand k8 --sims 2064 --sims-tile 2752 --sims-meeple 1376
#   B  b_uniform_2064        cand k8 --sims 2064 (uniform, NO split)   <- matched-budget control
# Opponent in BOTH = the unmodified champion (--opp-k-dets 8 --opp-sims 1376).
#
# ADJUDICATES NOTHING. No promotion, no PRODUCTION.yaml, no results.csv row, no claim row.
# Writes per-cell extracts and stops; the orchestrating session reads and closes out.
#
# Band was claimed BEFORE this script ran (sentinel measurement/simsplit_alloc_20260812/BAND);
# this script never claims a band, so a restart cannot burn a second one.
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/simsplit_alloc_20260812
LOGS=$DIR/logs
OUT=/mnt/c/carc-shared/simsplit_alloc_20260812      # LOCAL prefix
LOUT=/mnt/carc-shared/simsplit_alloc_20260812       # LAPTOP prefix (same store)
LAPTOP=laptop-wsl
W_LOCAL=${W_LOCAL:-30}
W_LAPTOP=${W_LAPTOP:-22}
N=${N:-800}
BAND=$(head -1 "$DIR/BAND")
SUMMARY=$REPO/scripts/classical_search/menu_block_summary.py

mkdir -p "$LOGS" "$OUT"
ts() { date +%F_%T; }
log() { echo "[alloc $(ts)] $*"; }

case "$BAND" in ''|*[!0-9]*) log "FATAL: bad band '$BAND'"; exit 3 ;; esac

busy_py_local() { ps -eo pcpu,args --no-headers | awk '$1 > 20.0 && /python/' | wc -l; }
count_records() { find "$1" -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l; }
laptop_claims() {
  find "$1" -maxdepth 1 -name 'seed*.claim' -print0 2>/dev/null \
    | xargs -0 -r grep -l -E 'helper|laptop' 2>/dev/null | wc -l
}
laptop_busy() {
  local b
  b=$(timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' 2>/dev/null <<'RQ'
cd /home/doctor/projects/carcassone || exit 1
n=$(ps -eo pcpu,args --no-headers | awk '$1 > 20.0 && /python/' | wc -l)
echo "${n:-0}"
RQ
)
  b=$(printf '%s' "$b" | head -1 | tr -dc '0-9'); echo "${b:-0}"
}

# run_cell <sub> <extra menu_fair_cell args...>
run_cell() {
  local sub="$1"; shift
  if [ -f "$DIR/DONE_$sub" ]; then log "cell $sub already DONE - skipping"; return 0; fi
  log "=== CELL $sub START (n=$N band=$BAND W_local=$W_LOCAL W_laptop=$W_LAPTOP) ==="
  mkdir -p "$OUT/$sub"

  # laptop leg — piped script with cd on line 1; the CALL is backgrounded (a synchronous
  # ssh 'job &' can hang and starve everything launched after it). timeout rc=124 == LAUNCHED.
  cat > "$LOGS/_laptop_$sub.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
mkdir -p $LOUT/$sub
setsid nohup env MENU_OUT_ROOT=$LOUT nice -n 19 bash \\
  scripts/classical_search/menu_fair_cell.sh $W_LAPTOP laptop \\
    --sub $sub --n $N --band $BAND $* \\
  > $LOUT/$sub/laptop.log 2>&1 < /dev/null & disown
echo "laptop $sub launched pid \$!"
EOF
  ( timeout 180 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$LOGS/_laptop_$sub.sh" \
      >> "$LOGS/laptop_launch.log" 2>&1
    echo "[laptop-launch $(date +%F_%T)] $sub ssh rc=$? (124 == launched-and-detached)" \
      >> "$LOGS/laptop_launch.log" ) &

  MENU_OUT_ROOT=$OUT nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W_LOCAL" local \
      --sub "$sub" --n "$N" --band "$BAND" "$@" > "$LOGS/${sub}_local.log" 2>&1 &
  local pid=$!
  log "cell $sub: local launcher pid $pid"

  # two-box verification: workers busy on BOTH boxes AND a laptop-owned claim ON THIS CELL.
  local t0 lw pw lc ok=0
  t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt 1200 ]; do
    lw=$(busy_py_local); pw=$(laptop_busy); lc=$(laptop_claims "$OUT/$sub")
    if [ "$lw" -gt 1 ] && [ "$pw" -gt 1 ] && [ "$lc" -gt 0 ]; then ok=1; break; fi
    sleep 30
  done
  log "cell $sub: two-box check local_busy=$lw laptop_busy=$pw laptop_claims_on_cell=$lc ok=$ok"
  [ "$ok" = 1 ] || log "cell $sub: WARNING two-box verification did not confirm within 1200s (throughput risk, not a validity risk) - continuing"

  wait $pid
  log "cell $sub: local launcher exited rc=$?"
  local got; got=$(count_records "$OUT/$sub")
  log "cell $sub: records $got/$N"
  $PY "$SUMMARY" --dir "$OUT/$sub" --label "${sub}_n${N}_b${BAND}" \
      --expected-rules-profile fixed_v1 --expect-cand-leaf-hash a36d2e15a3b3d71d \
      --out "$DIR/verdicts/${sub}.json" >> "$LOGS/${sub}_local.log" 2>&1
  : > "$DIR/DONE_$sub"
  log "=== CELL $sub COMPLETE -> $DIR/verdicts/${sub}.json ==="
}

log "=== SIMS-SPLIT ALLOCATION A/B START, band $BAND ==="
run_cell a_split_t2752_m1376 --k-dets 8 --sims 2064 --sims-tile 2752 --sims-meeple 1376 --opp-k-dets 8 --opp-sims 1376
run_cell b_uniform_2064      --k-dets 8 --sims 2064                                      --opp-k-dets 8 --opp-sims 1376

# A-B CRN contrast (the PRIMARY statistic). crn_delta_fairnet.py is generic: it joins two
# dirs on (seed,a_seat) and differences the per-deck seat-balanced margins. Its LABELS say
# "fair-net"/"fair" - here they mean cell A / cell B. Read the numbers, not the labels.
$PY "$REPO/scripts/classical_search/crn_delta_fairnet.py" \
    --fairnet-dir "$OUT/a_split_t2752_m1376" --baseline-dir "$OUT/b_uniform_2064" \
    --out "$DIR/verdicts/A_minus_B_contrast.json" > "$LOGS/contrast.log" 2>&1
log "A-B contrast -> $DIR/verdicts/A_minus_B_contrast.json"
log "=== FINISHED. Nothing promoted, PRODUCTION.yaml untouched, no verdict adjudicated. ==="
