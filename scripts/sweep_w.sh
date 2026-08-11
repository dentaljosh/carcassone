#!/bin/bash
# REAL W sweep (2026-06-03) — resolves the W axis that the coarse sweep left fuzzy.
# Mode is SETTLED (orch-off wins ~2x on all boxes), so this is orch-off only and spends
# all resolution on W. KEY METHODOLOGY FIX: every W config on a box runs the SAME fixed
# seed-set (same G games), so wall-clock differences are PURE parallelism efficiency, not
# game-length variance — that confound is what blurred the 3-4% gaps at G=24.
# Per-box grids bracket each likely peak ABOVE and BELOW (the bracket rule). G=40, blend=0.5.
#
# Usage: bash sweep_w.sh <tag>   tag in {5800x,xeon,laptop}
set -u
TAG="${1:?need tag}"
G="${G:-40}"
SEED="${SEED:-2000000}"   # SAME for all configs on this box -> identical games -> pure W signal
case "$TAG" in
  5800x)  REPO=/home/doctor/projects/carcassone; SHARE=/mnt/c/carc-shared; WS="10 12 14 16 18" ;;
  xeon)   REPO=/home/doctor/projects/carcassone; SHARE=/mnt/carc-shared;   WS="8 10 12 14 16" ;;
  laptop) REPO=/home/pop/carcassone;             SHARE=/mnt/carc-shared;   WS="12 14 16 18 20 22" ;;
  *) echo "bad tag $TAG"; exit 1 ;;
esac
cd "$REPO" || { echo "FATAL no repo $REPO"; exit 1; }
[ -d "$SHARE/pathb_loop" ] || { echo "FATAL share $SHARE not ready"; exit 1; }
WARM=$SHARE/pathb_loop/ckpt/iter_11.pt
OUTCSV=$SHARE/wsweep2/${TAG}.csv
mkdir -p "$SHARE/wsweep2"
echo "tag,mode,workers,games,positions,wall_s,pos_per_s,games_per_min,seed" > "$OUTCSV"
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=wsweep"
PY=.venv/bin/python
for W in $WS; do
  TMP=$SHARE/wsweep2/tmp_${TAG}_w${W}
  rm -rf "$TMP"; mkdir -p "$TMP"
  echo "### [$TAG] orch-off W=$W seed=$SEED (same games every W) @ $(date +%H:%M:%S)"
  OUT=$(nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims 200 --leaf-eval v2_5 --value-blend 0.5 \
    --value-target score_diff --workers "$W" --batch-size 8 \
    --checkpoint "$WARM" --anchor-fraction 0.3 --anchor-checkpoint "$WARM" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  line=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1)
  pos=$(echo "$line" | grep -oE '^[0-9]+'); wall=$(echo "$line" | grep -oE '[0-9.]+s' | tr -d 's')
  if [ -n "$pos" ] && [ -n "$wall" ]; then
    pps=$(awk "BEGIN{printf \"%.2f\", $pos/$wall}")
    gpm=$(awk "BEGIN{printf \"%.2f\", $G/($wall/60)}")
    echo "$TAG,off,$W,$G,$pos,$wall,$pps,$gpm,$SEED" >> "$OUTCSV"
    echo "    -> $pos pos / ${wall}s = $pps pos/s, $gpm games/min"
  else
    echo "$TAG,off,$W,$G,NA,NA,NA,NA,$SEED" >> "$OUTCSV"
    echo "    -> FAILED; tail:"; printf '%s\n' "$OUT" | tail -3
  fi
  rm -rf "$TMP"
done
echo "=== [$TAG] W-SWEEP DONE @ $(date +%H:%M:%S) ==="
cat "$OUTCSV"
