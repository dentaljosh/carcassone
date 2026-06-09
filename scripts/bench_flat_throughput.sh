#!/bin/bash
# Flat-leaf END-TO-END self-play THROUGHPUT bench: USE_FLAT_LEAF OFF vs ON, at
# production knobs, over a worker-count sweep — the deploy-decision number the
# per-leaf 2.26x micro-bench cannot give (self-play is RAM-bandwidth-bound at high
# W; the at-scale games/min gain is what matters).
#
# Runs the WORKTREE code (the live tree has no flat_leaf) via a PYTHONPATH override
# + the live venv's python. For each W, plays IDENTICAL games (fixed seed) twice:
#   OFF  : engine v2.7 leaf (production today)
#   FLAT : CARCASSONNE_USE_FLAT_LEAF=1 -> virtual_score_v2 redirects to flat_leaf
# so the wall-clock delta is pure leaf cost. npz -> LOCAL /tmp (no CIFS confound).
#
# Success for DEPLOY = FLAT raises games/min meaningfully at production W (>= ~1.5x)
# AND/OR flattens the per-worker erosion curve / raises the saturation-W (the
# bandwidth-wall test). Both runs see the same thermal state (back-to-back, fixed
# seed), so VRM throttle ~cancels in the ratio; FLAT runs second (warmer) -> the
# ratio is conservative.
#
# ⚠️ Run ONLY on a quiet box (the flywheel must not be competing for this box's
# cores/RAM). Cleanest: free the 5800x (kill its self-play worker; xeon+laptop
# continue via --shared-claim), run this, then rejoin.
#
# Usage:
#   WS="16" G=32 bash scripts/bench_flat_throughput.sh                 # quick headline
#   WS="8 12 16 20" G=48 bash scripts/bench_flat_throughput.sh         # saturation curve
set -u

WT="${WT:-/home/doctor/projects/carc-leafdev}"          # override on remotes (overlay dir)
PY="${PY:-/home/doctor/projects/carcassone/.venv/bin/python}"  # override per box (remote venv)
WS="${WS:-16}"
G="${G:-32}"
SEED="${SEED:-2000000}"   # SAME games for OFF and FLAT at each W -> pure leaf signal
SIMS="${SIMS:-200}"
BATCH="${BATCH:-8}"
# A valid checkpoint (any — we measure throughput, not strength). Copied to /tmp so
# the share is not in the hot path. Override CKPT=... if this one is gone.
CKPT_SRC="${CKPT:-/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter4.pt}"
OUTROOT=/tmp/bench_flat_throughput
SUM=$OUTROOT/summary.csv

export PYTHONPATH="$WT/src:$WT/engine"
COMMON_ENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"

cd "$WT" || { echo "FATAL no worktree $WT"; exit 1; }
[ -f "$CKPT_SRC" ] || { echo "FATAL no checkpoint $CKPT_SRC (pass CKPT=...)"; exit 1; }
mkdir -p "$OUTROOT"
CKPT=$OUTROOT/ckpt.pt
cp -f "$CKPT_SRC" "$CKPT" || { echo "FATAL cp checkpoint"; exit 1; }

# sanity: confirm we're importing the WORKTREE code + flat path exists
$PY - <<'PY' || { echo "FATAL worktree import check failed"; exit 1; }
import os, sys
sys.path.insert(0, os.environ["PYTHONPATH"].split(":")[0])
import carcassonne_ai, carcassonne_ai.flat_leaf as fl
want = os.environ["PYTHONPATH"].split(":")[0]
assert carcassonne_ai.__file__.startswith(want), (carcassonne_ai.__file__, want)
assert hasattr(fl, "flat_virtual_score_v2"), "no flat path"
print("worktree import OK:", carcassonne_ai.__file__)
PY

FOREIGN_THRESH="${FOREIGN_THRESH:-40}"  # mean foreign (non-python) %cpu above this => run CONTAMINATED

# Background sentinel: every 3s, sum %cpu of all NON-python procs. The selfplay
# workers are python; VS Code/node, editor indexing, etc. are "foreign". A clean
# box reads ~0-10%; a VS Code restart spiked the node MainThreads to ~80%+. Lets a
# run SELF-FLAG contaminated instead of silently recording a throttled wall-clock
# (the 2026-06-09 mid-sweep VS Code restart that invalidated FLAT W=16).
sample_foreign() {  # $1=outfile ; echoes the sampler's bg pid
  ( while true; do
      ps -eo %cpu,comm --no-headers 2>/dev/null | awk '$2!="python" && ($1+0)>5{s+=$1} END{printf "%.0f\n", s+0}'
      sleep 3
    done ) > "$1" 2>/dev/null &
  echo $!
}

echo "mode,w,games,positions,wall_s,pos_per_s,games_per_min,foreign_cpu" > "$SUM"

run_one() {  # $1=mode(OFF|FLAT) $2=W $3=extra_env
  local mode=$1 W=$2 xenv=$3
  local TMP=$OUTROOT/${mode}_w${W}; rm -rf "$TMP"; mkdir -p "$TMP"
  echo "### $mode  W=$W  G=$G  sims=$SIMS  seed=$SEED  @ $(date +%H:%M:%S)"
  local FCPU=$OUTROOT/foreign_${mode}_w${W}.txt; : > "$FCPU"
  local SPID; SPID=$(sample_foreign "$FCPU")
  local OUT
  OUT=$(nice -n 19 env $COMMON_ENV $xenv $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims "$SIMS" --leaf-eval v2_5 --value-blend 0.0 \
    --value-target score_diff --workers "$W" --batch-size "$BATCH" \
    --checkpoint "$CKPT" --anchor-fraction 0.3 --anchor-checkpoint "$CKPT" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  kill "$SPID" 2>/dev/null; pkill -P "$SPID" 2>/dev/null || true
  local fmean; fmean=$(awk '{s+=$1;n++} END{printf "%.0f",(n?s/n:0)}' "$FCPU" 2>/dev/null); [ -z "$fmean" ] && fmean=0
  local line pos wall
  line=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1)
  pos=$(echo "$line" | grep -oE '^[0-9]+'); wall=$(echo "$line" | grep -oE '[0-9.]+s' | tr -d 's')
  rm -rf "$TMP"
  if [ -z "$pos" ] || [ -z "$wall" ]; then
    echo "  !! could not parse output; last lines:"; printf '%s\n' "$OUT" | tail -5
    echo "$mode,$W,$G,PARSE_FAIL,,,,$fmean" >> "$SUM"; return
  fi
  local pps gpm flag
  pps=$(awk "BEGIN{printf \"%.2f\", $pos/$wall}")
  gpm=$(awk "BEGIN{printf \"%.2f\", $G/($wall/60)}")
  flag=""; awk "BEGIN{exit !($fmean > $FOREIGN_THRESH)}" && flag="  ⚠ CONTAMINATED(foreign_cpu=${fmean}%)"
  echo "  -> $pos pos, ${wall}s, ${pps} pos/s, ${gpm} games/min  [foreign_cpu=${fmean}%]${flag}"
  echo "$mode,$W,$G,$pos,$wall,$pps,$gpm,$fmean" >> "$SUM"
}

# short warmup (few games) so the first timed run isn't on a cold/cool box
# (CPU boost-when-cool would skew the first run). OFF also runs before FLAT at
# each W, so any residual thermal bias makes OFF look faster -> FLAT/OFF ratio is
# conservative (understates flat's gain), the safe direction.
echo "### warmup @ $(date +%H:%M:%S)"
_GSAVE=$G; G=6; run_one WARMUP "$(echo $WS | awk '{print $1}')" "" >/dev/null 2>&1 || true; G=$_GSAVE
sed -i '/^WARMUP,/d' "$SUM" 2>/dev/null || true

for W in $WS; do
  run_one OFF  "$W" ""
  run_one FLAT "$W" "CARCASSONNE_USE_FLAT_LEAF=1"
done

echo
echo "=== summary ($SUM) ==="
column -t -s, "$SUM"
echo
echo "=== FLAT/OFF speedup by W (games/min) — contaminated rows (foreign_cpu>${FOREIGN_THRESH}%) excluded ==="
awk -F, -v th="$FOREIGN_THRESH" 'NR>1 && $1=="OFF"  && ($8+0)<=th {off[$2]=$7}
  NR>1 && $1=="FLAT" && ($8+0)<=th {flat[$2]=$7}
  END{ for(w in off){ if(flat[w]!="" && off[w]+0>0) printf "  W=%-3s  OFF %-8s  FLAT %-8s  %.2fx\n", w, off[w], flat[w], flat[w]/off[w] } }' "$SUM" | sort -t= -k2 -n
