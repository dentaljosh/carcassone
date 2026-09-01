#!/usr/bin/env bash
# E-1b ARMED-CONTINUATION driver — one box, W concurrent chunks, sentinel on the share.
#
# Usage (LOCAL, the funded shape):
#   BOX=local W=32 SHARE=/mnt/c/carc-shared ./run_e1b.sh            # the CELL
#   BOX=local W=4  SHARE=/mnt/c/carc-shared MODE=smoke ./run_e1b.sh # the SMOKE
#
# ⚠️ THE SHARE MOUNT SPELLING DIFFERS BY BOX: /mnt/c/carc-shared locally,
# /mnt/carc-shared inside an ssh to the laptop. Pass it in; never hardcode.
#
# It consumes `units_$BOX_<profile>.txt` (or `smokeunits_...` in MODE=smoke)
# written by plan_units.py and splits each into CHUNK-unit pieces. One runner
# process per chunk amortises the import cost while staying fine-grained enough
# to balance W workers, and R9's import latch is respected because a chunk never
# mixes rules profiles. Units are individually atomic on disk, so re-running
# this script RESUMES.
#
# ⛔ MODE=smoke writes to a SEPARATE `out_SMOKE_*` directory with its OWN
# manifest, and is adjudicated from those emitted documents by
# `adjudicate_e1b.py --smoke`, which exits NONZERO on an empty cell.
set -u

REPO="${REPO:?set REPO to the worktree root}"
DIR="$REPO/measurement/e1b_armed_continuation_20260901"
BOX="${BOX:?set BOX}"
W="${W:?set W}"
SHARE="${SHARE:?set SHARE}"
PY="${PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
MODE="${MODE:-cell}"

MEM_CAP_GB="${MEM_CAP_GB:-6}"
# 1800 s CPU, inherited from E-1a's D-1: the cap is an RLIMIT_CPU cap and
# DRAM-contention stalls are charged to process CPU time, so a 600 s cap would
# fire on legitimately slow, contention-hit arms and bias WHICH plies get
# priced. 1800 is a runaway guard, not a budget.
ARM_CAP_S="${ARM_CAP_S:-1800}"
THREADS="${THREADS:-1}"
CHUNK="${CHUNK:-4}"
SUFFIX="${SUFFIX:-}"

if [ "$MODE" = "smoke" ]; then
  STAMP="${STAMP:-$(date +%Y%m%d_%H%M%S)}"
  OUTDIR="$DIR/out_SMOKE_${BOX}_${STAMP}"
  UNITGLOB="$DIR/smokeunits_${BOX}_*.txt"
  MANIFEST="$OUTDIR/manifest.json"
  TAG="SMOKE_${BOX}_${STAMP}"
else
  OUTDIR="$DIR/out_$BOX$SUFFIX"
  UNITGLOB="$DIR/units_${BOX}${SUFFIX}_*.txt"
  MANIFEST="$OUTDIR/manifest.json"
  TAG="CELL_${BOX}${SUFFIX}"
fi
LOGDIR="$DIR/logs"
WORKDIR="$DIR/chunks_${TAG}"
mkdir -p "$OUTDIR" "$LOGDIR" "$WORKDIR"

export PYTHONPATH="$REPO/src:$REPO/engine:$REPO/scripts"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

DRIVER_LOG="$SHARE/e1b_${TAG}_driver.log"
say() { echo "[$(date -Is)] $*" | tee -a "$DRIVER_LOG"; }
DIE() { say "⛔ $*"; exit 1; }

# Freeze-latch sentinel (auto-memory: reference_freeze_latch_hook). Present for
# the lifetime of the run; removed on clean exit. A STALE one must only be
# cleaned after confirming the run is actually dead.
LIVE="$DIR/RUN_LIVE_${TAG}.json"
cat > "$LIVE" <<EOF
{"box": "$BOX", "mode": "$MODE", "started_at": "$(date -Is)", "W": $W,
 "chunk": $CHUNK, "arm_cap_s": $ARM_CAP_S, "driver_log": "$DRIVER_LOG",
 "outdir": "$OUTDIR", "repo": "$REPO",
 "what": "E-1b — the 91 banked E-1a plies re-priced under the S1-armed (dose 0.25, mask 31, scope=opp) continuation, both seats, at E-1a's pinned k8x1376 budget"}
EOF
trap 'rm -f "$LIVE"' EXIT

# --- 1. the manifest + the DOSE-GATED NEGATIVE CONTROL, before any unit ------
# ⭐ Emitted FIRST so every chunk can assert agreement against it, and so the
# adjudicator reads config from a document rather than from a dirname (IS-D1).
if [ ! -f "$MANIFEST" ]; then
  say "emitting manifest + negative control -> $MANIFEST"
  nice -n 19 "$PY" "$DIR/continue_armed.py" \
      --targets "$DIR/targets_continuation.jsonl" \
      --baseline "$DIR/CRN_BASELINE.json" \
      --manifest "$MANIFEST" --emit-manifest --threads "$THREADS" \
      >> "$LOGDIR/manifest_${TAG}.log" 2>&1 \
    || DIE "manifest/negative-control FAILED (see $LOGDIR/manifest_${TAG}.log)"
fi

# --- 2. fan out --------------------------------------------------------------
rm -f "$WORKDIR"/chunk_*
NUNITS=0
for UF in $UNITGLOB; do
  [ -e "$UF" ] || continue
  # the FULL profile name, not the last underscore field: `fixed_v1` must not
  # collapse to `v1` or two profiles could share a chunk prefix.
  PROF="$(basename "$UF" .txt \
          | sed "s/^smokeunits_${BOX}${SUFFIX}_//; s/^units_${BOX}${SUFFIX}_//")"
  NUNITS=$((NUNITS + $(wc -l < "$UF")))
  split -l "$CHUNK" -d -a 4 "$UF" "$WORKDIR/chunk_${PROF}_"
done
[ "$NUNITS" -gt 0 ] || DIE "no unit files matched $UNITGLOB — run plan_units.py first"
NCHUNK=$(ls "$WORKDIR"/chunk_* 2>/dev/null | wc -l)
say "START $TAG W=$W units=$NUNITS chunks=$NCHUNK chunk=$CHUNK \
mem_cap=${MEM_CAP_GB}G arm_cap=${ARM_CAP_S}s threads=$THREADS outdir=$OUTDIR"

i=0
for C in "$WORKDIR"/chunk_*; do
  i=$((i+1))
  LOG="$LOGDIR/${TAG}_$(printf '%04d' "$i").log"
  nice -n 19 "$PY" "$DIR/continue_armed.py" \
      --targets "$DIR/targets_continuation.jsonl" \
      --baseline "$DIR/CRN_BASELINE.json" \
      --manifest "$MANIFEST" \
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
say "ALL CHUNKS DONE $TAG units_on_disk=$NDONE / expected $NUNITS"

# --- 3. adjudicate -----------------------------------------------------------
if [ "$MODE" = "smoke" ]; then
  # ⛔ THE SMOKE IS ADJUDICATED FROM ITS OWN EMITTED MANIFEST, and exits nonzero
  # on an EMPTY cell — the launch-blocking defect class.
  # ⛔ NO `| tee` HERE. A pipeline's exit status is the LAST command's, so
  # `... | tee f || DIE` would swallow the nonzero exit the smoke exists to
  # produce; the adjudicator writes the artifact itself via --out.
  "$PY" "$DIR/adjudicate_e1b.py" --smoke --units "$OUTDIR" \
      --manifest "$MANIFEST" --out "$OUTDIR/SMOKE_VALIDATION.json" \
    || DIE "SMOKE FAILED — do not launch the cell"
  say "✅ SMOKE PASS ($OUTDIR/SMOKE_VALIDATION.json)"
else
  "$PY" - "$OUTDIR" "$OUTDIR/DONE_$TAG.json" "$NUNITS" <<'PYEOF'
import json, sys, glob, collections
outdir, sentinel, expected = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = [json.load(open(f)) for f in glob.glob(outdir + "/unit_*.json")]
pair = collections.Counter(r["pair"]["status"] for r in rows)
arms = collections.Counter(a.get("status") for r in rows
                           for a in (r.get("arms") or {}).values())
jr = collections.Counter()
for r in rows:
    for a in (r.get("arms") or {}).values():
        for k in ("total", "own_mover", "boosted"):
            jr[k] += int(((a.get("jr_expansions") or {}).get(k)) or 0)
json.dump({"units_on_disk": len(rows), "expected_for_this_box": expected,
           "pair_status": dict(pair), "arm_status": dict(arms),
           "jr_expansions_totals": dict(jr),
           "n_plies": len({(r["game"], r["ply"]) for r in rows}),
           "strata": dict(collections.Counter(r["stratum"] for r in rows))},
          open(sentinel, "w"), indent=1)
PYEOF
  say "SENTINEL $OUTDIR/DONE_$TAG.json"
  cp "$OUTDIR/DONE_$TAG.json" "$SHARE/e1b_DONE_$TAG.json" 2>/dev/null || true
  say "READOUT: $PY $DIR/adjudicate_e1b.py --units $OUTDIR --manifest $MANIFEST --out $DIR/E1B.json"
fi
