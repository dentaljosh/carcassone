#!/bin/bash
# Test high-W self-play (W=30/32) by first parking the IDLE MCP servers in swap, so the
# HOT workers run entirely in physical RAM. Idle MCP pages are cold -> they sit in swap the
# whole run and never page back in -> harmless. The danger is swapping the WORKERS (thrash),
# so this samples swap every few seconds: swap STABLE near the post-reclaim baseline = good
# (only cold MCP parked); swap GROWING during a run = workers thrashing = back off that W.
#
# Pre-step (ONCE, before any workers exist) reclaims ~RECLAIM bytes from /init.scope (where the
# MCP servers + this session live). memory.reclaim self-selects the coldest pages = idle MCP.
# Needs sudo (cgroup write + swappiness). Reuses the same production knobs as sweep_w_thermal.sh.
#
# Usage: sudo -v; WS="30 32" RECLAIM=8G bash scripts/sweep_w_mcpswap.sh
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
WARM=/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt
OUTDIR=/mnt/c/carc-shared/wsweep_thermal
WS="${WS:-30 32}"
G="${G:-48}"
SEED="${SEED:-2000000}"
RECLAIM="${RECLAIM:-8G}"
SCOPE=/sys/fs/cgroup/init.scope/memory.reclaim
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=wsweep_mcpswap"
cd "$REPO" || { echo "FATAL no repo"; exit 1; }
[ -f "$WARM" ] || { echo "FATAL no warm $WARM"; exit 1; }
mkdir -p "$OUTDIR"
SUM=$OUTDIR/mcpswap_summary.csv
echo "w,games,positions,wall_s,pos_per_s,games_per_min,swap_base_MB,swap_max_MB,swap_growth_MB,avail_min_MB,verdict" > "$SUM"

# sudo gate
sudo -n true 2>/dev/null || { echo "FATAL need sudo (run 'sudo -v' first)"; exit 1; }

echo "### swappiness 60 -> 90 (swap cold anon sooner)"
echo 90 | sudo tee /proc/sys/vm/swappiness >/dev/null

# convert RECLAIM (e.g. 8G) to bytes
rb=$(numfmt --from=iec "$RECLAIM" 2>/dev/null || echo "$RECLAIM")
echo "### pre-reclaim ${RECLAIM} (${rb} bytes) from /init.scope (parks idle MCP in swap; NO workers running yet) @ $(date +%H:%M:%S)"
free -m | awk 'NR==2{print "  before: used="$3" avail="$7}'; free -m | awk 'NR==3{print "  before: swap_used="$3}'
echo "$rb" | sudo tee "$SCOPE" >/dev/null 2>&1 || echo "  (memory.reclaim returned non-zero; partial reclaim still applied)"
sleep 3
free -m | awk 'NR==2{print "  after:  used="$3" avail="$7}'; free -m | awk 'NR==3{print "  after:  swap_used="$3}'
swap_base=$(free -m | awk 'NR==3{print $3}')

for W in $WS; do
  TMP=/tmp/wsweep_mcpswap_w${W}; rm -rf "$TMP"; mkdir -p "$TMP"
  echo "### W=$W  G=$G  seed=$SEED  swap_base=${swap_base}MB  @ $(date +%H:%M:%S)"
  # background swap/avail sampler
  SWAPLOG=$OUTDIR/swap_w${W}.csv; : > "$SWAPLOG"
  ( while true; do free -m | awk -v t="$(date +%H:%M:%S)" 'NR==2{a=$7} NR==3{print t","$3","a}'; sleep 4; done ) > "$SWAPLOG" 2>/dev/null &
  SAMP=$!
  OUT=$(nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims 200 --leaf-eval v2_5 --value-blend 0.0 \
    --value-target score_diff --workers "$W" --batch-size 8 \
    --checkpoint "$WARM" --anchor-fraction 0.3 --anchor-checkpoint "$WARM" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  kill "$SAMP" 2>/dev/null
  line=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1)
  pos=$(echo "$line" | grep -oE '^[0-9]+'); wall=$(echo "$line" | grep -oE '[0-9.]+s' | tr -d 's')
  rm -rf "$TMP"
  read smax sgrow amin <<<"$(awk -F, -v b="$swap_base" '{if($2>mx)mx=$2; if(am==""||$3<am)am=$3} END{printf "%d %d %d", mx, mx-b, am}' "$SWAPLOG")"
  if [ -n "$pos" ] && [ -n "$wall" ]; then
    pps=$(awk "BEGIN{printf \"%.2f\", $pos/$wall}")
    gpm=$(awk "BEGIN{printf \"%.2f\", $G/($wall/60)}")
    verdict=$(awk "BEGIN{print ($sgrow>1200)?\"THRASH(workers swapping)\":\"clean(cold MCP only)\"}")
    echo "$W,$G,$pos,$wall,$pps,$gpm,$swap_base,$smax,$sgrow,$amin,$verdict" >> "$SUM"
    echo "    -> $pps pos/s, $gpm games/min | swap ${swap_base}->${smax}MB (grow ${sgrow}) | $verdict"
  else
    echo "$W,$G,NA,NA,NA,NA,$swap_base,$smax,$sgrow,$amin,FAILED" >> "$SUM"
    echo "    -> FAILED; tail:"; printf '%s\n' "$OUT" | tail -3
  fi
done
echo "=== MCP-SWAP SWEEP DONE @ $(date +%H:%M:%S) ==="
column -s, -t "$SUM"
echo "(restore swappiness with: echo 60 | sudo tee /proc/sys/vm/swappiness)"
