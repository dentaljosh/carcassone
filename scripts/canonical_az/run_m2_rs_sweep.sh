#!/usr/bin/env bash
# M2 read-out Leg 2a — the pre-registered rs-sweep (M2_PLAN.md "Read-out protocol").
# 6 cells: iters {00,02,04} x rs {0.25,0.5}, n=200 sims=200 fpu=0.6, paired,
# vs the FIXED RoD-v2 iter_02 anchor, dual-orch W48 local. rs=0 cells are the
# in-loop evals (same seeds: SEED_START 1906220000 -> deck-comparable).
# Resumable: a cell with an existing result.json is skipped.
# Detach:  setsid nohup nice -n 19 bash scripts/canonical_az/run_m2_rs_sweep.sh \
#            > /mnt/c/carc-shared/m2_sighted/logs/rs_sweep.log 2>&1 < /dev/null & disown
set -u
cd "$(dirname "$0")/../.." || exit 1

SHARE="${SHARE:-/mnt/c/carc-shared/m2_sighted}"
OUT="$SHARE/eval"
REF="${REF:-/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt}"
OW="${OW:-48}"
ITERS_LIST="${ITERS_LIST:-00 02 04}"
RS_LIST="${RS_LIST:-0.25 0.5}"

for it in $ITERS_LIST; do
  CKPT="$SHARE/ckpt/iter_${it}.pt"
  [ -f "$CKPT" ] || { echo "[rs-sweep] SKIP iter_$it — ckpt missing"; continue; }
  for rs in $RS_LIST; do
    # rs tag matches eval_m2_net_vs_net.py's out-dir convention (_rs025 / _rs05)
    tag=$(echo "$rs" | sed 's/^0\.//;s/\.//g'); tag="_rs0${tag}"
    D="$OUT/m2nvn_iter_${it}_vs_iter_02_s200_fpu06${tag}"
    if [ -f "$D/result.json" ]; then echo "[rs-sweep] cell iter_$it rs=$rs done — skip"; continue; fi
    echo "=== [rs-sweep] cell iter_$it rs=$rs @ $(date +%H:%M:%S) ==="
    CAND="$CKPT" REF="$REF" HOST="${HOST:-5800x}" OW="$OW" SIMS=200 N=200 FPU=0.6 OUT="$OUT" \
      bash scripts/canonical_az/eval_m2_dual_orch.sh --paired --residual-scale "$rs" \
      || { echo "[rs-sweep] cell iter_$it rs=$rs FAILED @ $(date +%H:%M:%S) — continuing"; }
  done
done

echo "=== [rs-sweep] all cells attempted @ $(date +%H:%M:%S) — summary ==="
for it in $ITERS_LIST; do
  for d in "$OUT"/m2nvn_iter_${it}_vs_iter_02_s200_fpu06 "$OUT"/m2nvn_iter_${it}_vs_iter_02_s200_fpu06_rs0*; do
    r="$d/result.json"
    [ -f "$r" ] && python3 -c "
import json,os
d=json.load(open('$r'))
print(f\"{os.path.basename('$d')}: wr={d['winrate']:.3f} elo={d['elo']:+.1f}+-{d['elo_1sig']:.0f} z={d['paired_z']:+.2f}\")"
  done
done
echo "=== [rs-sweep] DONE ==="
