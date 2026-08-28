#!/usr/bin/env bash
# C1 OUTCOME PRICING driver — one box, one BLOCK, W concurrent chunks.
#
# Usage (LOCAL):
#   BOX=local  W=30 SHARE=/mnt/c/carc-shared BLOCK=base ./run_c1.sh
# Usage (LAPTOP, piped over ssh with `cd` on line 1 of the wrapper):
#   BOX=laptop W=22 SHARE=/mnt/carc-shared  BLOCK=base ./run_c1.sh
#
# ⚠️ THE SHARE MOUNT SPELLING DIFFERS BY BOX: /mnt/c/carc-shared locally,
# /mnt/carc-shared inside an ssh to the laptop. Pass it in; never hardcode.
#
# THE ENTRYPOINT IS `../e4_continuation_20260828/continue_plies.py`, UNMODIFIED.
# This instrument changes nothing about how a continuation is played: it changes
# only WHICH TWO ACTIONS occupy the two arm slots (targets_c1.jsonl) and WHICH
# WORLD INDICES are drawn (>= 16, disjoint from every world any prior instrument
# used). See DESIGN.md §2.
set -u

REPO="${REPO:-/home/doctor/projects/carcassone}"
DIR="$REPO/measurement/c1_pricing_prep"
RUNNER="$REPO/measurement/e4_continuation_20260828/continue_plies.py"
BOX="${BOX:?set BOX}"
W="${W:?set W}"
SHARE="${SHARE:?set SHARE}"
BLOCK="${BLOCK:-base}"
PY="${PY:-$REPO/.venv/bin/python}"

MEM_CAP_GB="${MEM_CAP_GB:-4}"
ARM_CAP_S="${ARM_CAP_S:-1800}"     # D-1 precedent, carried (DESIGN.md §2.4)
THREADS="${THREADS:-1}"
CHUNK="${CHUNK:-4}"
SUFFIX="${SUFFIX:-}"
SMOKE="${SMOKE:-0}"

OUTDIR="$DIR/out_$BOX"
LOGDIR="$DIR/logs"
WORKDIR="$DIR/chunks_${BOX}_${BLOCK}${SUFFIX}"
mkdir -p "$OUTDIR" "$LOGDIR" "$WORKDIR"

export PYTHONPATH="$REPO/src:$REPO/engine:$REPO/scripts"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

DRIVER_LOG="$SHARE/c1_pricing_${BOX}_${BLOCK}${SUFFIX}_driver.log"
say() { echo "[$(date -Is)] $*" | tee -a "$DRIVER_LOG"; }

# ---------------------------------------------------------------- gates ----- #
[ -f "$RUNNER" ] || { say "FATAL: runner missing: $RUNNER"; exit 3; }
[ -f "$DIR/targets_c1.jsonl" ] || { say "FATAL: no frozen target set"; exit 3; }

# PINNED_SRC_REV — the cross-box rev gate. Both boxes must be sitting on the
# exact commit the freeze stamped, or a mixed-rev cell is possible.
PIN="$DIR/PINNED_SRC_REV.json"
[ -f "$PIN" ] || { say "FATAL: $PIN missing (stamp it at the freeze)"; exit 3; }
WANT=$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['pinned_src_rev'])" "$PIN")
HAVE=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)
if [ "$WANT" != "any" ] && [ "$WANT" != "$HAVE" ]; then
  say "FATAL: rev gate — pinned $WANT, this box is on $HAVE"; exit 3
fi

# G-LEGAL must have run, and must not have voided a co-primary stratum.
PF="$DIR/LEGAL_PREFLIGHT.json"
[ -f "$PF" ] || { say "FATAL: run preflight_c1.py first (DESIGN.md §5)"; exit 3; }
VOIDED=$("$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));print(','.join(d['VOID_TRIGGERED']) or 'none')" "$PF")
if [ "$VOIDED" != "none" ]; then
  say "FATAL: G-LEGAL VOID_TRIGGERED for $VOIDED — do not launch"; exit 3
fi

# G-HOST — this run is an EXCLUSIVE TENANT of its box (auto-memory:
# feedback_no_agent_compute_beside_eval; the 2026-08-26 quantification: ONE
# niced 1-core DRAM churner inflated a saturated eval ~1.8x/move). Census by
# FULL ARGS, never by comm/-C python: a silent long job is invisible otherwise.
FOREIGN=$(ps -eo args | grep -E '\.venv/bin/python|python3? ' \
          | grep -vE 'continue_plies\.py|grep|ps -eo|run_c1\.sh' | wc -l)
say "G-HOST host=$(hostname) nproc=$(nproc) load=$(cut -d' ' -f1-3 /proc/loadavg) \
foreign_python=$FOREIGN rev=$HAVE"
if [ "$FOREIGN" -gt 0 ] && [ "${ALLOW_TENANTS:-0}" != "1" ]; then
  say "FATAL: $FOREIGN foreign python process(es) on this box. This run must be \
the exclusive tenant. Census them, then re-run with ALLOW_TENANTS=1 only if you \
have confirmed they are idle."
  ps -eo pid,etime,pcpu,args | grep -E '\.venv/bin/python|python3? ' \
    | grep -vE 'grep|ps -eo' | tee -a "$DRIVER_LOG"
  exit 3
fi

# Freeze-latch sentinel (auto-memory: reference_freeze_latch_hook). Present for
# the lifetime of the run; removed on clean exit. A STALE one must only be
# cleaned after confirming the run is actually dead.
LIVE="$DIR/RUN_LIVE_${BOX}_${BLOCK}${SUFFIX}.json"
cat > "$LIVE" <<EOF
{"box": "$BOX", "block": "$BLOCK", "started_at": "$(date -Is)", "W": $W,
 "chunk": $CHUNK, "driver_log": "$DRIVER_LOG", "outdir": "$OUTDIR",
 "pinned_src_rev": "$HAVE",
 "what": "C1 outcome pricing — CRN-paired realized-outcome price of the tier1-rollout re-ranker's picks vs the production champion's"}
EOF
trap 'rm -f "$LIVE"' EXIT

# ---------------------------------------------------------------- work ------ #
rm -f "$WORKDIR"/chunk_*
NUNITS=0
for UF in "$DIR"/units_${BOX}_${BLOCK}${SUFFIX}_*.txt; do
  [ -e "$UF" ] || continue
  PROF="$(basename "$UF" .txt | sed "s/^units_${BOX}_${BLOCK}${SUFFIX}_//")"
  NUNITS=$((NUNITS + $(wc -l < "$UF")))
  split -l "$CHUNK" -d -a 4 "$UF" "$WORKDIR/chunk_${PROF}_"
done
NCHUNK=$(ls "$WORKDIR"/chunk_* 2>/dev/null | wc -l)
[ "$NCHUNK" -gt 0 ] || { say "FATAL: no unit files for box=$BOX block=$BLOCK"; exit 3; }
say "START box=$BOX block=$BLOCK W=$W units=$NUNITS chunks=$NCHUNK chunk=$CHUNK \
mem_cap=${MEM_CAP_GB}G arm_cap=${ARM_CAP_S}s threads=$THREADS outdir=$OUTDIR smoke=$SMOKE"

i=0
for C in "$WORKDIR"/chunk_*; do
  i=$((i+1))
  LOG="$LOGDIR/${BOX}_${BLOCK}${SUFFIX}_$(printf '%04d' "$i").log"
  nice -n 19 "$PY" "$RUNNER" \
      --targets "$DIR/targets_c1.jsonl" \
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
say "ALL CHUNKS DONE box=$BOX block=$BLOCK units_on_disk=$NDONE / expected $NUNITS (cumulative across blocks)"

SENT="$OUTDIR/DONE_${BOX}_${BLOCK}${SUFFIX}.json"
"$PY" - "$OUTDIR" "$SENT" "$NUNITS" "$BLOCK" "$DIR/targets_c1.jsonl" <<'PYEOF'
import json, sys, glob, collections
outdir, sentinel, expected, block, targets = sys.argv[1:6]
tg = {}
for line in open(targets):
    r = json.loads(line)
    tg[(r["game"], int(r["ply"]))] = r
rows = [json.load(open(f)) for f in glob.glob(outdir + "/unit_*.json")]
pair = collections.Counter(r["pair"]["status"] for r in rows)
arms = collections.Counter(a.get("status") for r in rows
                           for a in (r.get("arms") or {}).values())
# The arm-slot remap is asserted on every landed row, not just documented.
bad = [(r["game"], r["ply"]) for r in rows
       if int(r["played_action"]) != int(tg[(r["game"], r["ply"])]["c1_action"])
       or int(r["counterfactual_action"]) != int(tg[(r["game"], r["ply"])]["champ_action"])]
json.dump({"block": block, "units_on_disk": len(rows),
           "expected_this_block": int(expected),
           "pair_status": dict(pair), "arm_status": dict(arms),
           "n_plies": len({(r["game"], r["ply"]) for r in rows}),
           "worlds_seen": sorted({r["world"] for r in rows}),
           "arm_map_violations": bad,
           "strata": dict(collections.Counter(r["stratum"] for r in rows))},
          open(sentinel, "w"), indent=1)
print("ARM_MAP_VIOLATIONS", len(bad))
PYEOF
say "SENTINEL $SENT"
cp "$SENT" "$SHARE/c1_pricing_DONE_${BOX}_${BLOCK}${SUFFIX}.json" 2>/dev/null || true
