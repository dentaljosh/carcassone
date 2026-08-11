#!/bin/bash
# W-parallel game-count A/B for the Cython board-encoder (2026-06-17).
# Orch-off self-play at production W on the 5800x, CY_REPR off vs on, SAME seeds
# (bit-exact => identical games => fair fixed-work A/B). Samples loadavg + GPU
# power mid-run so a null result can be attributed (CPU-bound vs GPU-dispatch-bound).
set -u
REPO=/home/doctor/projects/carcassone
cd "$REPO" || exit 1
CKPT=checkpoints/warmstart_canonical.pt
W=${W:-14}; SIMS=${SIMS:-200}; GAMES=${GAMES:-42}; BS=${BS:-8}
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 \
       CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1
RESULT=/tmp/ab_cy_repr_result.txt
: > "$RESULT"

run_arm () {
  local cy=$1 tag=$2 out=$3
  rm -rf "$out"; mkdir -p "$out"
  echo "=== ARM $tag (CARCASSONNE_USE_CY_REPR=$cy)  W=$W sims=$SIMS games=$GAMES bs=$BS ==="
  # background sampler: load + GPU power every 15s
  ( while true; do
      echo "$(date +%T) load1=$(cut -d' ' -f1 /proc/loadavg) gpuW=$(nvidia-smi --query-gpu=power.draw,utilization.gpu --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')"
      sleep 15
    done ) > "$out/sample.txt" 2>/dev/null &
  local samp=$!
  local t0=$(date +%s)
  CARCASSONNE_USE_CY_REPR=$cy nice -n 19 python -u scripts/run_selfplay_iter.py \
     --checkpoint "$CKPT" --output-root "$out" --iter 0 --seed-start 500 \
     --games "$GAMES" --sims "$SIMS" --batch-size "$BS" --workers "$W" \
     --leaf-eval v2_5 > "$out/log.txt" 2>&1
  local rc=$?; local t1=$(date +%s); local dt=$((t1-t0))
  kill "$samp" 2>/dev/null
  local n=$(find "$out" -name '*.npz' 2>/dev/null | wc -l)
  local gpm=$(python3 -c "print(f'{$n/(($dt)/60.0):.2f}')" 2>/dev/null)
  local midload=$(sed -n '3p;4p' "$out/sample.txt" 2>/dev/null | tr '\n' ' ')
  echo "ARM $tag: rc=$rc wall=${dt}s games=$n  -> ${gpm} g/min   mid-run: ${midload}"
  echo "$tag dt=$dt games=$n gpm=$gpm" >> "$RESULT"
}

run_arm 0 OFF /tmp/ab_selfplay_off
run_arm 1 ON  /tmp/ab_selfplay_on

echo "=== SUMMARY ==="
cat "$RESULT"
python3 - "$RESULT" <<'PY'
import sys
d={}
for ln in open(sys.argv[1]):
    p=ln.split(); tag=p[0]
    d[tag]={k:v for k,v in (x.split('=') for x in p[1:])}
if 'OFF' in d and 'ON' in d:
    off=float(d['OFF']['gpm']); on=float(d['ON']['gpm'])
    if off>0:
        print(f"\nspeedup ON/OFF = {on/off:.3f}x   (off {off} -> on {on} g/min)")
PY
