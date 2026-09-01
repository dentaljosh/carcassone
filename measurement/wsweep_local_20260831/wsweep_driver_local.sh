#!/usr/bin/env bash
# wsweep_driver_local.sh — post-flattening W re-sweep, LOCAL half, ARB-ON-BOTH-SIDES cell shape.
#
# ADAPTED FROM measurement/wsweep_laptop_20260831/wsweep_driver.sh (the merged laptop
# driver, which is NOT edited). The four adaptations, all recorded here:
#   1. SHARE   /mnt/carc-shared          -> /mnt/c/carc-shared     (local mount path)
#   2. LOGDIR  $SHARE/wsweep_laptop_...  -> $SHARE/wsweep_local_20260831
#   3. NAME    SMOKE_WSWEEP_W$W          -> SMOKE_WSWEEPLOC_W$W
#      ⚠️ MANDATORY, not cosmetic: both boxes mount the SAME share, the laptop half
#      already wrote SMOKE_WSWEEP_W{18,22,26,28,30}, and this driver `rm -rf`s its own
#      out-dir at the top of each point. Reusing the laptop's names would have DELETED
#      the laptop half's raw records at the shared W=30 point.
#   4. seed base 167999999000 -> 168999998000 (disjoint throwaway range; caller-supplied)
# Everything else — workload knobs, census gate, sampler, estimators — is byte-identical.
#
# Workload = the H2H's exact shape:
#   eval_fair_puct, k16x1376 = 22016 BOTH sides, tie arbiter ARMED BOTH SIDES with the
#   deployed dict (B=64, J=4, argmax, salt tiearb2-deploy-v1, eps 0.0, phase_gate all),
#   --cand-fpu-reduction 0.2, fixed_v1 + CARCASSONNE_FIX_R9=1, rust backend, exact-k 2,
#   --paired.
#
# ⭐ IDENTITY-GATED: EVERY W point plays the SAME n games from the SAME throwaway deck
#    set. Per-game wall time varies ~40% deck-to-deck/seat-to-seat, so disjoint seed
#    ranges per point would swamp the 5%-of-peak settle threshold with deck noise.
#    Games are bit-identical at any W, so this costs nothing and makes the ladder a
#    deck-PAIRED contrast.
#
# THROWAWAY SEEDS ONLY (168999998000+). SMOKE_ out-subdir prefix keeps every cell out
# of adjudication. --no-results-csv. W IS THROUGHPUT-ONLY — nothing here is a claim.
#
# usage: wsweep_driver_local.sh <phase-tag> <N_GAMES> <SEED_BASE> <W> [<W> ...]
set -uo pipefail
cd /home/doctor/projects/carcassone

PHASE="$1"; N="$2"; SEED="$3"; shift 3

PY=/home/doctor/projects/carcassone/.venv/bin/python
REPO=/home/doctor/projects/carcassone
SHARE=/mnt/c/carc-shared
OUTROOT="$SHARE/fpu_ladder"
LOGDIR="$SHARE/wsweep_local_20260831"
mkdir -p "$LOGDIR"

export CARCASSONNE_FIX_R9=1
export PYTHONUNBUFFERED=1

STAMP() { echo "[wsweep-local $(date -u +%FT%TZ)] $*"; }

STAMP "phase=$PHASE n=$N seed=$SEED points=$* rev=$(git rev-parse --short HEAD)"

for W in "$@"; do
  NAME="SMOKE_WSWEEPLOC_W${W}"
  OUT="$OUTROOT/$NAME"

  # ---- exclusive-tenant check (throughput bench!) --------------------------
  STAMP "--- point W=$W n=$N seed=$SEED ---"
  STAMP "loadavg BEFORE: $(cat /proc/loadavg)"
  STAMP "census (FULL ARGS):"
  ps -eo pid,etime,pcpu,args --sort=-pcpu | grep -E 'python|carc' | grep -v grep | head -6 | sed 's/^/    /'
  BUSY=$(ps -eo pcpu,args --sort=-pcpu | grep -E 'python|carc' | grep -v grep | awk '$1>50' | wc -l)
  if [ "$BUSY" -gt 0 ]; then
    STAMP "!!! NOT AN EXCLUSIVE TENANT ($BUSY busy procs) — ABORTING point W=$W"
    continue
  fi

  rm -rf "$OUT"; mkdir -p "$OUT"

  # ---- background resource sampler ----------------------------------------
  SAMP="$LOGDIR/${PHASE}_W${W}_samples.tsv"
  : > "$SAMP"
  ( while true; do
      printf '%s\t%s\t%s\t%s\n' "$(date +%s)" "$(cut -d' ' -f1-3 /proc/loadavg)" \
             "$(free -m | awk '/^Mem:/{print $3"/"$2"MB used, avail "$7}')" \
             "$(ps -eo stat,args | grep eval_fair_puct | grep -v grep | grep -c '^R')" >> "$SAMP"
      sleep 20
    done ) &
  SAMP_PID=$!

  T0=$(date +%s)
  nice -n 19 "$PY" "$REPO/scripts/classical_search/eval_fair_puct.py" \
    --backend rust --info fair \
    --k-dets 16 --sims 1376 --opp-k-dets 16 --opp-sims 1376 \
    --exact-k 2 \
    --opponent fair-champion \
    --n "$N" --paired --seed-start "$SEED" \
    --workers "$W" --out-root "$OUTROOT" --out-subdir "$NAME" \
    --rules-profile fixed_v1 \
    --cand-fpu-reduction 0.2 \
    --cand-tiearb-enabled --cand-tiearb-b 64 --cand-tiearb-j 4 \
    --cand-tiearb-mode argmax --cand-tiearb-salt tiearb2-deploy-v1 \
    --cand-tiearb-eps 0.0 --cand-tiearb-phase-gate all \
    --opp-tiearb-enabled --opp-tiearb-b 64 --opp-tiearb-j 4 \
    --opp-tiearb-mode argmax --opp-tiearb-salt tiearb2-deploy-v1 \
    --opp-tiearb-eps 0.0 --opp-tiearb-phase-gate all \
    --no-results-csv \
    > "$LOGDIR/${PHASE}_W${W}.log" 2>&1
  RC=$?
  T1=$(date +%s)

  kill "$SAMP_PID" 2>/dev/null || true

  NG=$(ls "$OUT"/seed*.json 2>/dev/null | wc -l)
  STAMP "point W=$W rc=$RC wall=$((T1-T0))s games=$NG"
  STAMP "loadavg AFTER: $(cat /proc/loadavg)"
  printf '{"phase":"%s","W":%d,"n":%d,"seed":%s,"rc":%d,"t0":%d,"t1":%d,"wall_s":%d,"games":%d}\n' \
      "$PHASE" "$W" "$N" "$SEED" "$RC" "$T0" "$T1" "$((T1-T0))" "$NG" \
      >> "$LOGDIR/points.jsonl"
done

STAMP "PHASE $PHASE DONE"
touch "$LOGDIR/DONE_${PHASE}"
