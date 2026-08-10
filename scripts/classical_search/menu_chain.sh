#!/bin/bash
# LEVER-MENU SERIAL CHAIN — blocks B -> C -> D -> E of docs/LEVER_MENU_PLAN_20260810.md
# (FUNDED IN FULL 2026-08-10, Joshua: "its all funded").
#
#   B = item 2  farm_growth_off n=1600 DEPLOY confirm      band 1.18e11   ~3.0 h
#   C = item 4  capscurve 4 cells x n=800 (ablation class) band 1.20e11   ~2.2 h
#   D = item 3  CL-060 width residual H2H n=800            band 1.19e11   ~1.5 h
#   E = item 5  CL-072 n->800 extension (GPU, exclusive)   band 94e9      ~9.6 h
#
# WHY SERIAL. Plan section 2: every item's primary statistic is a SIM-budgeted deck-paired
# margin, so co-tenancy is a throughput cost, not a validity cost - and with both boxes
# already saturated by one work-stealing cell, running two evals concurrently and running
# them back-to-back consume the SAME total wall clock. Serial is strictly better: clean
# attribution, one --shared-claim output dir per box at a time (what the launchers assume),
# and no repeat of the crash-cycle stretching seen when a second workload sat beside a live
# eval. Item 5 additionally monopolizes the GPU.
#
# WHAT THIS SCRIPT DOES NOT DO. It adjudicates NOTHING. It never promotes, never edits
# governance/PRODUCTION.yaml, never writes a verdict, and never runs the conditional item-3
# top-up (plan section 6.6: that spend is Joshua's call - the chain only records that the
# pre-registered trigger fired). Reading and close-out belong to the orchestrating session.
#
# FAIL-STOP DISCIPLINE. Every block verifies BOTH boxes are actually working before it is
# allowed to proceed: N>1 busy python workers on each box AND the shared record count
# growing. On any failure the chain writes a BLOCKED_<block> marker and EXITS. It never
# ploughs on - a block that ran on one box, or on a stale laptop revision, is a contaminated
# cell, not a slow one.
#
# ENGINEERED-AROUND TRAPS (each cost real hours; do not "simplify" them away):
#  * `rc=$?` is captured on its OWN line. `echo "$(ts) rc=$?"` evaluates ts() first, so $?
#    becomes ts's status (always 0) and a launcher failure reads as a clean run.
#  * NEVER pkill-by-name from here. This script's own name and its heredocs contain the
#    patterns; `pkill -f X` self-kills when the killer's cmdline contains X. Kill by exact
#    pid only. (Nothing in this chain kills anything - it is stated so nobody adds it.)
#  * The ssh CALL to launch the laptop is itself BACKGROUNDED. A synchronous `ssh host "job &"`
#    can hang and starve every box launched after it; a DOWN box masks the bug entirely.
#  * Laptop reach is ALWAYS `ssh laptop-wsl 'bash -s' < script` with `cd` on line 1. The
#    inline `ssh host 'cd X && ...'` form gets the cd STRIPPED in transit.
#  * The share path DIFFERS BY BOX: /mnt/c/carc-shared here, /mnt/carc-shared on the laptop.
#  * Claims-without-records are cleaned before each resume - but ONLY ones older than the
#    grace age, because a .claim NAMES the host that owns it and a live sibling box's fresh
#    claim is not stranded (the 2026-07-30 teacher-h2h near-miss).
#  * A rev mismatch between the boxes is a CONTAMINATION class, not an inconvenience: the
#    chain refuses to launch a two-box block unless the laptop is at this exact commit.
#
# Resume: every leg is --shared-claim, so re-running this script after a crash resumes from
# the records on disk. Completed blocks are skipped on their DONE markers.
#
# Launch:  setsid nohup nice -n 19 bash scripts/classical_search/menu_chain.sh \
#            > measurement/lever_menu_20260810/logs/chain.log 2>&1 < /dev/null &
set -u

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/lever_menu_20260810
LOGS=$DIR/logs
SHARE=/mnt/c/carc-shared           # LOCAL prefix
LSHARE=/mnt/carc-shared            # LAPTOP prefix (different mount, same store)
OUT=$SHARE/lever_menu_20260810
LOUT=$LSHARE/lever_menu_20260810
LAPTOP=laptop-wsl
W_LOCAL=${W_LOCAL:-14}             # Joshua's cap - he is using the box
W_LAPTOP=${W_LAPTOP:-22}
OW_LOCAL=${OW_LOCAL:-14}           # item 5 orch workers (GPU-blocked, not core-bound)
OW_LAPTOP=${OW_LAPTOP:-12}         # measured-safe on the laptop's ~10 GB (537 MB RSS/worker)

# item 2
B_SUB=b_farmgrowthoff_n1600_b118e9 ; B_N=1600 ; B_BAND=118000000000
B_CELL=$DIR/cells/menu_farmgrowthoff_fixed_v1_vs_fairchamp11008.json
# item 4
C_CELLS="cap5 cap12 curve150 curve175" ; C_N=800 ; C_BAND=120000000000
C_PREFIX=cc800_ ; C_SUFFIX=_n800_b120e9 ; C_ROOT=$SHARE/capscurve_resweep
# item 3
D_SUB=d_width_k4x2752_vs_champ_n800_b119e9 ; D_N=800 ; D_BAND=119000000000
# item 5
E_SUB=n800ext_paired_b94e9 ; E_N=400 ; E_BAND=94000000200
E_ROOT=$SHARE/teacher_h2h_94e9

mkdir -p "$LOGS" "$OUT" "$DIR/verdicts"
ts() { date +%F_%T; }
log() { echo "[chain $(ts)] $*"; }
CUR_PID=""   # the local launcher of the block currently in flight, if any
blocked() {   # $1 = block letter, $2... = reason
  local b="$1"; shift
  log "!!! BLOCK $b BLOCKED: $*"
  {
    echo "$(ts)"; echo "block: $b"; echo "reason: $*"
    # DELIBERATELY NOT KILLED. Killing an mp main does NOT reap its spawn workers - they
    # orphan and become invisible to a pattern kill - and the games already in flight are
    # valid, --shared-claim-checkpointed work. The operator kills by EXACT pid if they want
    # the box back; the chain refuses to guess.
    [ -n "$CUR_PID" ] && echo "local launcher STILL RUNNING as pid $CUR_PID (not killed on purpose: killing an mp main orphans its spawn workers; kill by EXACT pid if you want the box back)"
    echo "resume: re-run this script - every leg is --shared-claim and completed blocks skip on their DONE markers."
  } > "$DIR/BLOCKED_$b"
  log "chain STOPPED. Nothing further launches. Marker: $DIR/BLOCKED_$b"
  exit 10
}

# ---------- census / verification helpers ----------
# Busy python processes. eval_fair_puct/eval_puct_priors fan out through multiprocessing
# SPAWN children, whose cmdline is `python -c from multiprocessing.spawn import spawn_main`
# and therefore does NOT contain the harness name - counting by cmdline would report 1
# worker on a fully saturated box. Count busy python processes instead.
busy_py_local() { ps -eo pcpu,comm --no-headers | awk '$2 ~ /python/ && $1 > 20.0' | wc -l; }
count_records() {   # $1 = a GLOB of record dirs (unquoted at call site)
  find $1 -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l
}
laptop_probe() {    # prints "<busy_py> <rev>"; empty on unreachable
  timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' 2>/dev/null <<'RPROBE'
cd /home/doctor/projects/carcassone || exit 1
b=$(ps -eo pcpu,comm --no-headers | awk '$2 ~ /python/ && $1 > 20.0' | wc -l)
r=$(git -C /home/doctor/projects/carcassone rev-parse HEAD)
echo "$b $r"
RPROBE
}
# CELL-SPECIFIC laptop proof. A generic "is the laptop busy" count is NOT sufficient and this
# is not hypothetical: on 2026-08-10 the laptop was running item 6's oracle scorer at 16
# workers x ~100% CPU, which would have satisfied any busy-python check while contributing
# ZERO games to the cell. A `.claim` file NAMES the host that owns it, so counting the cell's
# claims that carry a helper/laptop host is direct proof the laptop joined THIS cell.
laptop_claims() {   # $1 = record-dir GLOB (unquoted at call site)
  find $1 -maxdepth 1 -name 'seed*.claim' -print0 2>/dev/null \
    | xargs -0 -r grep -l -E 'helper|laptop' 2>/dev/null | wc -l
}
# Wait for the laptop to be free of the block-A oracle instrument before a game block starts.
# Plan section 2: items 1 and 6 are CPU-heavy and go in GAPS, not beside a game eval - purely
# to protect throughput and the ms riders.
wait_laptop_quiet() {
  local dl="${1:-7200}" t0; t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$dl" ]; do
    local busy
    busy=$(timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' 2>/dev/null <<'RQ'
cd /home/doctor/projects/carcassone || exit 1
pgrep -fc 'oracle_score_pilo[t]' 2>/dev/null || echo 0
RQ
)
    busy=${busy:-0}
    if [ "$busy" = "0" ]; then log "laptop is quiet (no oracle_score_pilot) - game block may start"; return 0; fi
    log "laptop still running item 6's oracle scorer ($busy proc) - holding the game block"
    sleep 120
  done
  log "WARNING: laptop did not go quiet within ${dl}s; proceeding anyway (throughput cost only, not a validity cost - plan section 2)"
  return 0
}
launch_laptop() {   # $1 = path to a local script file, piped to the laptop. BACKGROUND the CALL.
  local f="$1"
  ( timeout 180 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$f" \
      >> "$LOGS/laptop_launch.log" 2>&1
    # A detached remote launch makes `timeout` return 124 AFTER the job is already running.
    # 124 means LAUNCHED. Never retry on it - retries stack duplicate worker pools.
    echo "[laptop-launch $(date +%F_%T)] $(basename "$f") ssh rc=$? (124 == launched-and-detached)" \
      >> "$LOGS/laptop_launch.log" ) &
}

# verify_two_box <block> <record-dir-glob> <deadline-workers-s> <deadline-records-s>
# PASS requires, within the deadlines: >1 busy python on LOCAL, >1 busy python on LAPTOP,
# the laptop holding at least one claim ON THIS CELL, and the shared record count strictly
# greater than the baseline taken at entry. All four, or the chain stops.
verify_two_box() {
  local b="$1" glob="$2" dlw="$3" dlr="$4"
  local base; base=$(count_records "$glob")
  local t0; t0=$(date +%s)
  local lw=0 pw=0 lc=0 lrev="" ok_w=0
  log "verify[$b]: baseline records=$base; waiting up to ${dlw}s for workers on BOTH boxes"
  while [ $(( $(date +%s) - t0 )) -lt "$dlw" ]; do
    lw=$(busy_py_local)
    read -r pw lrev <<< "$(laptop_probe)"
    pw=${pw:-0}
    lc=$(laptop_claims "$glob")
    if [ "$lw" -gt 1 ] && [ "$pw" -gt 1 ] && [ "$lc" -gt 0 ]; then ok_w=1; break; fi
    sleep 20
  done
  log "verify[$b]: busy python -> local=$lw laptop=$pw | laptop claims on this cell=$lc (laptop rev=${lrev:-UNREACHABLE})"
  [ "$ok_w" = 1 ] || blocked "$b" "two-box verification failed after ${dlw}s (local busy=$lw need >1; laptop busy=$pw need >1; laptop claims on this cell=$lc need >0). A block that runs on one box only is a throughput loss AND an unverified topology - not proceeding."
  log "verify[$b]: waiting up to ${dlr}s for the record count to grow past $base"
  t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$dlr" ]; do
    local now; now=$(count_records "$glob")
    if [ "$now" -gt "$base" ]; then
      log "verify[$b]: PASS - records $base -> $now, local=$lw laptop=$pw busy workers"
      return 0
    fi
    sleep 30
  done
  blocked "$b" "record count never grew past $base within ${dlr}s (workers were up: local=$lw laptop=$pw) - games are being claimed but not completing"
}

# ---------- pre-flight ----------
log "=== LEVER-MENU CHAIN START ==="
log "plan: docs/LEVER_MENU_PLAN_20260810.md (FUNDED IN FULL 2026-08-10)"
LOCAL_REV=$(git -C "$REPO" rev-parse HEAD)
log "local rev $LOCAL_REV | W_LOCAL=$W_LOCAL W_LAPTOP=$W_LAPTOP OW=$OW_LOCAL/$OW_LAPTOP"
read -r PRE_W PRE_REV <<< "$(laptop_probe)"
[ -n "${PRE_REV:-}" ] || blocked PREFLIGHT "laptop unreachable at chain start (ssh $LAPTOP)"
log "laptop rev $PRE_REV (busy python $PRE_W)"
if [ "$PRE_REV" != "$LOCAL_REV" ]; then
  blocked PREFLIGHT "laptop is at rev $PRE_REV but local is at $LOCAL_REV. Stale remote code is a CONTAMINATION class, not an inconvenience. Bundle-sync the laptop and relaunch: git bundle create $SHARE/sync/menu.bundle <branch> (local) then git fetch $LSHARE/sync/menu.bundle <branch> && git reset --hard FETCH_HEAD (laptop, inside a piped script with cd on line 1)."
fi
[ -f "$DIR/GATE2a_VERDICT.json" ] || blocked PREFLIGHT "item 2's wiring gate (2a) has not been run - $DIR/GATE2a_VERDICT.json is missing. 2a is a HARD BLOCKER (plan section 4.2)."
GV=$($PY -c "import json;print(json.load(open('$DIR/GATE2a_VERDICT.json'))['verdict'])" 2>/dev/null)
log "item-2 wiring gate (2a) verdict: ${GV:-UNREADABLE}"
[ "$GV" = "PASS" ] || blocked PREFLIGHT "wiring gate 2a verdict is '${GV:-UNREADABLE}', not PASS. Item 2 stops and becomes a build task; do NOT fix it and keep the games."

# =====================================================================================
# BLOCK B - item 2: farm_growth_off n=1600 deploy confirm. Band 1.18e11. ~3.0 h two-box.
# =====================================================================================
if [ -f "$DIR/DONE_B" ]; then
  log "BLOCK B already DONE - skipping"
else
  wait_laptop_quiet 10800
  log "--- BLOCK B: item 2 farm_growth_off n=$B_N band=$B_BAND -> $OUT/$B_SUB"
  mkdir -p "$OUT/$B_SUB"
  cat > "$LOGS/_laptop_B.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
mkdir -p $LOUT/$B_SUB
setsid nohup env MENU_OUT_ROOT=$LOUT nice -n 19 bash \\
  scripts/classical_search/menu_fair_cell.sh $W_LAPTOP laptop \\
    --sub $B_SUB --n $B_N --band $B_BAND \\
    --cand-leaf-json $B_CELL --drift \\
    --k-dets 8 --sims 1376 \\
  > $LOUT/$B_SUB/laptop.log 2>&1 < /dev/null & disown
echo "laptop B launched pid \$!"
EOF
  launch_laptop "$LOGS/_laptop_B.sh"
  nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W_LOCAL" local \
      --sub "$B_SUB" --n "$B_N" --band "$B_BAND" \
      --cand-leaf-json "$B_CELL" --drift --k-dets 8 --sims 1376 \
      > "$LOGS/B_local.log" 2>&1 &
  B_PID=$!; CUR_PID=$B_PID
  log "BLOCK B: local launcher pid $B_PID; laptop joiner launch backgrounded"
  verify_two_box B "$OUT/$B_SUB" 900 1800
  wait $B_PID
  B_RC=$?; CUR_PID=""
  log "BLOCK B: local launcher exited rc=$B_RC"
  B_GOT=$(count_records "$OUT/$B_SUB")
  log "BLOCK B: records $B_GOT/$B_N"
  if [ "$B_GOT" -lt $(( B_N * 90 / 100 )) ]; then
    blocked B "only $B_GOT/$B_N records (<90%) - the cell is VOID by the standing rule; not proceeding to C on a contaminated queue"
  fi
  $PY "$REPO/scripts/classical_search/menu_block_summary.py" --dir "$OUT/$B_SUB" \
      --label "item2_farmgrowthoff_n1600_b118e9" --out "$DIR/verdicts/BLOCK_B_item2.json" \
      >> "$LOGS/B_local.log" 2>&1
  : > "$DIR/DONE_B"
  log "BLOCK B COMPLETE -> $DIR/verdicts/BLOCK_B_item2.json"
fi

# =====================================================================================
# BLOCK C - item 4: capscurve 4 cells x n=800, ablation class. Band 1.20e11 SHARED (CRN).
# =====================================================================================
if [ -f "$DIR/DONE_C" ]; then
  log "BLOCK C already DONE - skipping"
else
  wait_laptop_quiet 10800
  log "--- BLOCK C: item 4 capscurve cells [$C_CELLS] n=$C_N band=$C_BAND -> $C_ROOT/${C_PREFIX}*"
  cat > "$LOGS/_laptop_C.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
mkdir -p $LSHARE/capscurve_resweep
setsid nohup env CC_OUT_ROOT=$LSHARE/capscurve_resweep nice -n 19 bash \\
  scripts/classical_search/capscurve_resweep_launcher.sh $W_LAPTOP laptop \\
    --cells "$C_CELLS" --n $C_N --band $C_BAND \\
    --out-sub-prefix $C_PREFIX --exp-suffix $C_SUFFIX \\
  > $LSHARE/capscurve_resweep/laptop_menu_C.log 2>&1 < /dev/null & disown
echo "laptop C launched pid \$!"
EOF
  launch_laptop "$LOGS/_laptop_C.sh"
  nice -n 19 bash "$REPO/scripts/classical_search/capscurve_resweep_launcher.sh" "$W_LOCAL" local \
      --cells "$C_CELLS" --n "$C_N" --band "$C_BAND" \
      --out-sub-prefix "$C_PREFIX" --exp-suffix "$C_SUFFIX" \
      > "$LOGS/C_local.log" 2>&1 &
  C_PID=$!; CUR_PID=$C_PID
  log "BLOCK C: local launcher pid $C_PID; laptop joiner launch backgrounded"
  verify_two_box C "$C_ROOT/${C_PREFIX}*" 900 1800
  wait $C_PID
  C_RC=$?; CUR_PID=""
  log "BLOCK C: local launcher exited rc=$C_RC"
  C_FAIL=0
  for c in $C_CELLS; do
    g=$(count_records "$C_ROOT/${C_PREFIX}$c")
    log "BLOCK C: cell $c records $g/$C_N"
    [ "$g" -lt $(( C_N * 90 / 100 )) ] && C_FAIL=1
    $PY "$REPO/scripts/classical_search/menu_block_summary.py" --dir "$C_ROOT/${C_PREFIX}$c" \
        --label "item4_capscurve_${c}_n800_b120e9" \
        --out "$DIR/verdicts/BLOCK_C_item4_${c}.json" >> "$LOGS/C_local.log" 2>&1
  done
  [ "$C_FAIL" = 1 ] && blocked C "at least one capscurve cell is under 90% completion (VOID by the standing rule)"
  : > "$DIR/DONE_C"
  log "BLOCK C COMPLETE -> $DIR/verdicts/BLOCK_C_item4_*.json"
fi

# =====================================================================================
# BLOCK D - item 3: CL-060 width residual, direct H2H at fixed 11008. Band 1.19e11.
# candidate k4x2752 vs opponent k8x1376. BOTH asymmetry flags are required - --opp-sims
# alone would silently give a k8x2752 opponent (plan section 4.3).
# =====================================================================================
if [ -f "$DIR/DONE_D" ]; then
  log "BLOCK D already DONE - skipping"
else
  wait_laptop_quiet 10800
  log "--- BLOCK D: item 3 width H2H k4x2752 vs k8x1376 n=$D_N band=$D_BAND -> $OUT/$D_SUB"
  mkdir -p "$OUT/$D_SUB"
  cat > "$LOGS/_laptop_D.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
mkdir -p $LOUT/$D_SUB
setsid nohup env MENU_OUT_ROOT=$LOUT nice -n 19 bash \\
  scripts/classical_search/menu_fair_cell.sh $W_LAPTOP laptop \\
    --sub $D_SUB --n $D_N --band $D_BAND \\
    --k-dets 4 --sims 2752 --opp-k-dets 8 --opp-sims 1376 \\
  > $LOUT/$D_SUB/laptop.log 2>&1 < /dev/null & disown
echo "laptop D launched pid \$!"
EOF
  launch_laptop "$LOGS/_laptop_D.sh"
  nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W_LOCAL" local \
      --sub "$D_SUB" --n "$D_N" --band "$D_BAND" \
      --k-dets 4 --sims 2752 --opp-k-dets 8 --opp-sims 1376 \
      > "$LOGS/D_local.log" 2>&1 &
  D_PID=$!; CUR_PID=$D_PID
  log "BLOCK D: local launcher pid $D_PID; laptop joiner launch backgrounded"
  verify_two_box D "$OUT/$D_SUB" 900 1800
  wait $D_PID
  D_RC=$?; CUR_PID=""
  log "BLOCK D: local launcher exited rc=$D_RC"
  D_GOT=$(count_records "$OUT/$D_SUB")
  log "BLOCK D: records $D_GOT/$D_N"
  [ "$D_GOT" -lt $(( D_N * 90 / 100 )) ] && blocked D "only $D_GOT/$D_N records (<90%) - VOID by the standing rule"
  $PY "$REPO/scripts/classical_search/menu_block_summary.py" --dir "$OUT/$D_SUB" \
      --label "item3_width_k4x2752_vs_k8x1376_n800_b119e9" \
      --topup-trigger --out "$DIR/verdicts/BLOCK_D_item3.json" >> "$LOGS/D_local.log" 2>&1
  : > "$DIR/DONE_D"
  log "BLOCK D COMPLETE -> $DIR/verdicts/BLOCK_D_item3.json"
  # D' (the n=1600 top-up at 1.5 <= |z| < 2.0) is PRE-REGISTERED but its SPEND is Joshua's
  # call (plan section 6.6). The chain records that the trigger fired and does NOT run it.
  if $PY -c "import json,sys;d=json.load(open('$DIR/verdicts/BLOCK_D_item3.json'));sys.exit(0 if d.get('topup_triggered') else 1)" 2>/dev/null; then
    log "BLOCK D: the pre-registered item-3 TOP-UP trigger FIRED (1.5 <= |z| < 2.0). NOT running it - the +1.5 h spend is Joshua's call (plan section 6.6). Marker: $DIR/TOPUP_TRIGGERED_D"
    { echo "$(ts)"; echo "item 3 top-up trigger fired: 1.5 <= |margin z| < 2.0 at n=800."; \
      echo "Pre-registered continuation: n=1600 on FRESH decks of band 1.19e11, seeds 119000000400..119000000799."; \
      echo "NOT LAUNCHED - the spend is Joshua's call (plan section 6.6)."; } > "$DIR/TOPUP_TRIGGERED_D"
  fi
fi

# =====================================================================================
# BLOCK E - item 5: CL-072 n->800 extension. Band 94e9, FRESH decks (94000000200..399).
# GPU EXCLUSIVE. Each box serves its OWN net from its OWN GPU through its own carc-orch
# (the topology the n=400 cell already proved: local OW=20 + laptop OW=12).
# =====================================================================================
if [ -f "$DIR/DONE_E" ]; then
  log "BLOCK E already DONE - skipping"
else
  wait_laptop_quiet 10800
  log "--- BLOCK E: item 5 CL-072 extension n=$E_N band=$E_BAND -> $E_ROOT/$E_SUB (GPU exclusive)"
  cat > "$LOGS/_laptop_E.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
setsid nohup env OW=$OW_LAPTOP nice -n 19 bash \\
  scripts/classical_search/menu_item5_ext_laptop.sh \\
  > $LSHARE/teacher_h2h_94e9/logs/ext_laptop_launch.log 2>&1 < /dev/null & disown
echo "laptop E launched pid \$!"
EOF
  launch_laptop "$LOGS/_laptop_E.sh"
  OW=$OW_LOCAL nice -n 19 bash "$REPO/scripts/classical_search/menu_item5_ext_local.sh" \
      > "$LOGS/E_local.log" 2>&1 &
  E_PID=$!; CUR_PID=$E_PID
  log "BLOCK E: local cell pid $E_PID; laptop joiner launch backgrounded"
  # The net arm is ~12x slower than the deploy class (32.9 min/game measured), so the FIRST
  # record can legitimately take over half an hour. Deadlines are sized for that, not for
  # the CPU classes above.
  verify_two_box E "$E_ROOT/$E_SUB" 1200 4800
  wait $E_PID
  E_RC=$?; CUR_PID=""
  log "BLOCK E: local cell exited rc=$E_RC"
  E_GOT=$(count_records "$E_ROOT/$E_SUB")
  log "BLOCK E: extension records $E_GOT/$E_N"
  [ "$E_GOT" -lt $(( E_N * 90 / 100 )) ] && blocked E "only $E_GOT/$E_N extension records (<90%) - VOID by the standing rule"
  $PY "$REPO/scripts/classical_search/menu_block_summary.py" --dir "$E_ROOT/$E_SUB" \
      --label "item5_cl072_ext_n400_b94e9_fresh" --out "$DIR/verdicts/BLOCK_E_item5.json" \
      >> "$LOGS/E_local.log" 2>&1
  : > "$DIR/DONE_E"
  log "BLOCK E COMPLETE -> $DIR/verdicts/BLOCK_E_item5.json"
fi

log "=== LEVER-MENU CHAIN FINISHED (B/C/D/E) ==="
log "Nothing was promoted. governance/PRODUCTION.yaml untouched. No verdict was adjudicated."
log "Per-block extracts: $DIR/verdicts/ - the orchestrating session reads and closes out."
