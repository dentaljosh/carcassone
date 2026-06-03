#!/bin/bash
# Per-box self-play throughput sweep — re-derives the stale pre-Phase-0 worker/mode bench
# on CURRENT code. Runs the REAL run_selfplay_iter.py at production knobs and records
# positions/s + games/min for each (mode, W). Tests the orchestrator-GIL question:
# orch-off vs orchestrator(1 shard) vs shards=2/3. Writes CSV to $SHARE/wsweep/<tag>.csv.
#
# Usage: bash sweep_selfplay.sh <tag>   where tag in {5800x,xeon,laptop}
# blend=0.5 (representative of mid/late Stage B), anchor-fraction 0.3 (prod VRAM), G games.
set -u
TAG="${1:?need tag: 5800x|xeon|laptop}"
G="${G:-24}"
case "$TAG" in
  5800x)  REPO=/home/doctor/projects/carcassone; SHARE=/mnt/c/carc-shared
          CONFIGS="off:14 off:16 off:20 orch:20 orch:28 sh2:20" ;;
  xeon)   REPO=/home/doctor/projects/carcassone; SHARE=/mnt/carc-shared
          CONFIGS="off:10 off:14 orch:16 orch:24 sh2:16 sh2:24 sh3:24" ;;
  laptop) REPO=/home/pop/carcassone; SHARE=/mnt/carc-shared
          CONFIGS="off:14 off:18 off:22 orch:24 orch:32 sh2:22" ;;
  *) echo "bad tag $TAG"; exit 1 ;;
esac
CONFIGS="${CONFIGS_OVERRIDE:-$CONFIGS}"   # let a caller test one config fast
cd "$REPO" || { echo "FATAL no repo $REPO"; exit 1; }
mountpoint -q "$SHARE" 2>/dev/null || [ -d "$SHARE/pathb_loop" ] || { echo "FATAL share $SHARE not ready"; exit 1; }
WARM=$SHARE/pathb_loop/ckpt/iter_11.pt
[ -f "$WARM" ] || { echo "FATAL no warm $WARM"; exit 1; }
OUTCSV=$SHARE/wsweep/${TAG}.csv
mkdir -p "$SHARE/wsweep"
echo "tag,mode,workers,games,positions,wall_s,pos_per_s,games_per_min" > "$OUTCSV"
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=wsweep_${TAG}"
PY=.venv/bin/python
i=0
for cfg in $CONFIGS; do
  mode="${cfg%%:*}"; W="${cfg##*:}"
  case "$mode" in
    off) ORCH="" ;;
    orch) ORCH="--orchestrator" ;;
    sh2) ORCH="--orchestrator --orch-shards 2" ;;
    sh3) ORCH="--orchestrator --orch-shards 3" ;;
  esac
  i=$((i+1)); SEED=$((1000000 + i*100000))
  TMP=$SHARE/wsweep/tmp_${TAG}_${mode}_${W}
  rm -rf "$TMP"; mkdir -p "$TMP"
  echo "### [$TAG] $mode W=$W (seed=$SEED) @ $(date +%H:%M:%S)"
  OUT=$(nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims 200 --leaf-eval v2_5 --value-blend 0.5 \
    --value-target score_diff --workers "$W" $ORCH --batch-size 8 \
    --checkpoint "$WARM" --anchor-fraction 0.3 --anchor-checkpoint "$WARM" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  line=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1)
  pos=$(echo "$line" | grep -oE '^[0-9]+')
  wall=$(echo "$line" | grep -oE '[0-9.]+s' | tr -d 's')
  if [ -n "$pos" ] && [ -n "$wall" ]; then
    pps=$(awk "BEGIN{printf \"%.2f\", $pos/$wall}")
    gpm=$(awk "BEGIN{printf \"%.2f\", $G/($wall/60)}")
    echo "$TAG,$mode,$W,$G,$pos,$wall,$pps,$gpm" >> "$OUTCSV"
    echo "    -> $pos pos / ${wall}s = $pps pos/s, $gpm games/min"
  else
    echo "$TAG,$mode,$W,$G,NA,NA,NA,NA" >> "$OUTCSV"
    echo "    -> FAILED (no throughput line); tail:"; printf '%s\n' "$OUT" | tail -3
  fi
  rm -rf "$TMP"
done
echo "=== [$TAG] SWEEP DONE @ $(date +%H:%M:%S) ==="
cat "$OUTCSV"
