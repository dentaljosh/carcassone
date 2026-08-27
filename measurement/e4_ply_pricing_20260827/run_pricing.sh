#!/usr/bin/env bash
# E4 PLY-PRICING driver — one box, W shards, detached, sentinel on the share.
#
# Usage (LOCAL):
#   BOX=local W=14 SHARE=/mnt/c/carc-shared ./run_pricing.sh <shardfile>
# Usage (LAPTOP, piped over ssh with `cd` on line 1 of the wrapper):
#   BOX=laptop W=22 SHARE=/mnt/carc-shared ./run_pricing.sh <shardfile>
#
# ⚠️ THE SHARE MOUNT SPELLING DIFFERS BY BOX: /mnt/c/carc-shared locally,
# /mnt/carc-shared inside an ssh to the laptop. Pass it in; never hardcode.
#
# <shardfile> is a text file, one line per shard: "<profile> <game,game,...>".
set -u

REPO="${REPO:-/home/doctor/projects/carcassone}"
DIR="$REPO/measurement/e4_ply_pricing_20260827"
BOX="${BOX:?set BOX}"
W="${W:?set W}"
SHARE="${SHARE:?set SHARE}"
PY="${PY:-$REPO/.venv/bin/python}"
SHARDFILE="${1:?usage: run_pricing.sh <shardfile>}"

MEM_CAP_GB="${MEM_CAP_GB:-8}"
TIME_CAP_S="${TIME_CAP_S:-1800}"
THREADS="${THREADS:-1}"

OUTDIR="$DIR/out_$BOX"
LOGDIR="$DIR/logs"
mkdir -p "$OUTDIR" "$LOGDIR"

export PYTHONPATH="$REPO/src:$REPO/engine:$REPO/scripts"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

DRIVER_LOG="$SHARE/e4_ply_pricing_${BOX}_driver.log"
say() { echo "[$(date -Is)] $*" | tee -a "$DRIVER_LOG"; }

say "START box=$BOX W=$W shards=$(wc -l < "$SHARDFILE") mem_cap=${MEM_CAP_GB}G time_cap=${TIME_CAP_S}s"

# Freeze-latch sentinel (auto-memory: reference_freeze_latch_hook). Present for the
# lifetime of the run; removed on clean exit. A STALE one must only be cleaned
# after confirming the run is actually dead.
LIVE="$DIR/RUN_LIVE_${BOX}.json"
cat > "$LIVE" <<EOF
{"box": "$BOX", "started_at": "$(date -Is)", "shardfile": "$SHARDFILE",
 "W": $W, "driver_log": "$DRIVER_LOG", "outdir": "$OUTDIR",
 "what": "E4 ply pricing — judge-free exact/realized pricing of the owner exploit plies"}
EOF
trap 'rm -f "$LIVE"' EXIT

i=0
while read -r PROFILE GAMES; do
  [ -z "${PROFILE:-}" ] && continue
  i=$((i+1))
  OUT="$OUTDIR/rows_${BOX}_$(printf '%03d' "$i").jsonl"
  LOG="$LOGDIR/${BOX}_$(printf '%03d' "$i").log"
  SENT="$OUTDIR/DONE_${BOX}_$(printf '%03d' "$i").json"
  nice -n 19 "$PY" "$DIR/price_plies.py" \
      --profile "$PROFILE" \
      --targets "$DIR/targets.jsonl" \
      --mode-cut "$DIR/MODE_CUT.json" \
      --games "$GAMES" \
      --threads "$THREADS" \
      --job-mem-cap-gb "$MEM_CAP_GB" \
      --job-time-cap-secs "$TIME_CAP_S" \
      --out "$OUT" --log "$LOG" --done-sentinel "$SENT" \
      >> "$LOG" 2>&1 &
  # throttle to W concurrent shards
  while [ "$(jobs -rp | wc -l)" -ge "$W" ]; do sleep 5; done
done < "$SHARDFILE"

wait
say "ALL SHARDS DONE box=$BOX"
cat "$OUTDIR"/rows_"$BOX"_*.jsonl > "$OUTDIR/rows_$BOX.jsonl" 2>/dev/null || true
python3 - "$OUTDIR/rows_$BOX.jsonl" "$OUTDIR/DONE_$BOX.json" <<'PYEOF'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
json.dump({"box_rows": len(rows),
           "by_mode": {m: sum(1 for r in rows if r["pricing_mode"] == m)
                       for m in {r["pricing_mode"] for r in rows}},
           "priced": sum(1 for r in rows if r.get("delta_pts_mover") is not None)},
          open(sys.argv[2], "w"), indent=1)
PYEOF
say "SENTINEL $OUTDIR/DONE_$BOX.json"
cp "$OUTDIR/DONE_$BOX.json" "$SHARE/e4_ply_pricing_DONE_$BOX.json" 2>/dev/null || true
