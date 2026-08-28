#!/usr/bin/env bash
# E4 CONTINUATION-PRICING driver — one box, W concurrent chunks, sentinel on the share.
#
# Usage (LOCAL):
#   BOX=local  W=30 SHARE=/mnt/c/carc-shared ./run_continuation.sh
# Usage (LAPTOP, piped over ssh with `cd` on line 1 of the wrapper):
#   BOX=laptop W=22 SHARE=/mnt/carc-shared  ./run_continuation.sh
#
# ⚠️ THE SHARE MOUNT SPELLING DIFFERS BY BOX: /mnt/c/carc-shared locally,
# /mnt/carc-shared inside an ssh to the laptop. Pass it in; never hardcode.
#
# It consumes `units_$BOX_<profile>.txt` written by plan_boxes.py and splits each
# into CHUNK-unit pieces. One runner process per chunk keeps the import cost
# amortised while staying fine-grained enough to balance W workers, and R9's
# import latch is respected because a chunk never mixes rules profiles.
# Units are individually atomic on disk, so re-running this script RESUMES.
set -u

REPO="${REPO:-/home/doctor/projects/carcassone}"
DIR="$REPO/measurement/e4_continuation_20260828"
BOX="${BOX:?set BOX}"
W="${W:?set W}"
SHARE="${SHARE:?set SHARE}"
PY="${PY:-$REPO/.venv/bin/python}"

MEM_CAP_GB="${MEM_CAP_GB:-4}"
ARM_CAP_S="${ARM_CAP_S:-1800}"
THREADS="${THREADS:-1}"
CHUNK="${CHUNK:-4}"
SUFFIX="${SUFFIX:-}"

OUTDIR="$DIR/out_$BOX"
LOGDIR="$DIR/logs"
WORKDIR="$DIR/chunks_$BOX$SUFFIX"
mkdir -p "$OUTDIR" "$LOGDIR" "$WORKDIR"

export PYTHONPATH="$REPO/src:$REPO/engine:$REPO/scripts"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

DRIVER_LOG="$SHARE/e4_continuation_${BOX}${SUFFIX}_driver.log"
say() { echo "[$(date -Is)] $*" | tee -a "$DRIVER_LOG"; }

# Freeze-latch sentinel (auto-memory: reference_freeze_latch_hook). Present for
# the lifetime of the run; removed on clean exit. A STALE one must only be
# cleaned after confirming the run is actually dead.
LIVE="$DIR/RUN_LIVE_${BOX}${SUFFIX}.json"
cat > "$LIVE" <<EOF
{"box": "$BOX", "started_at": "$(date -Is)", "W": $W, "chunk": $CHUNK,
 "driver_log": "$DRIVER_LOG", "outdir": "$OUTDIR",
 "what": "E4 continuation pricing — CRN-paired game-outcome price of the divergent plies"}
EOF
trap 'rm -f "$LIVE"' EXIT

rm -f "$WORKDIR"/chunk_*
NUNITS=0
for UF in "$DIR"/units_${BOX}${SUFFIX}_*.txt; do
  [ -e "$UF" ] || continue
  PROF="$(basename "$UF" .txt | sed "s/^units_${BOX}${SUFFIX}_//")"
  NUNITS=$((NUNITS + $(wc -l < "$UF")))
  split -l "$CHUNK" -d -a 4 "$UF" "$WORKDIR/chunk_${PROF}_"
done
NCHUNK=$(ls "$WORKDIR"/chunk_* 2>/dev/null | wc -l)
say "START box=$BOX W=$W units=$NUNITS chunks=$NCHUNK chunk=$CHUNK \
mem_cap=${MEM_CAP_GB}G arm_cap=${ARM_CAP_S}s threads=$THREADS outdir=$OUTDIR"

i=0
for C in "$WORKDIR"/chunk_*; do
  i=$((i+1))
  LOG="$LOGDIR/${BOX}${SUFFIX}_$(printf '%04d' "$i").log"
  nice -n 19 "$PY" "$DIR/continue_plies.py" \
      --targets "$DIR/targets_continuation.jsonl" \
      --units "$C" \
      --outdir "$OUTDIR" \
      --threads "$THREADS" \
      --job-mem-cap-gb "$MEM_CAP_GB" \
      --arm-cap-secs "$ARM_CAP_S" \
      --log "$LOG" \
      >> "$LOG" 2>&1 &
  while [ "$(jobs -rp | wc -l)" -ge "$W" ]; do sleep 5; done
done

wait
NDONE=$(ls "$OUTDIR"/unit_*.json 2>/dev/null | wc -l)
say "ALL CHUNKS DONE box=$BOX units_on_disk=$NDONE / expected $NUNITS"

"$PY" - "$OUTDIR" "$OUTDIR/DONE_$BOX$SUFFIX.json" "$NUNITS" <<'PYEOF'
import json, sys, glob, collections
outdir, sentinel, expected = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = [json.load(open(f)) for f in glob.glob(outdir + "/unit_*.json")]
pair = collections.Counter(r["pair"]["status"] for r in rows)
arms = collections.Counter(a.get("status") for r in rows
                           for a in (r.get("arms") or {}).values())
json.dump({"units_on_disk": len(rows), "expected_for_this_box": expected,
           "pair_status": dict(pair), "arm_status": dict(arms),
           "n_plies": len({(r["game"], r["ply"]) for r in rows}),
           "strata": dict(collections.Counter(r["stratum"] for r in rows))},
          open(sentinel, "w"), indent=1)
PYEOF
say "SENTINEL $OUTDIR/DONE_$BOX$SUFFIX.json"
cp "$OUTDIR/DONE_$BOX$SUFFIX.json" "$SHARE/e4_continuation_DONE_$BOX$SUFFIX.json" 2>/dev/null || true
