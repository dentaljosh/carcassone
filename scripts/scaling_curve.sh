#!/bin/bash
# Test-time compute scaling sweep for iter_01 (the +87 global-best net).
#   Curve A: net sims swept, heuristic FIXED at 200   -> does strength rise with search?
#   Curve B: net FIXED at 200, heuristic sims swept    -> does it beat a deeper-searching ref?
#   #1 probe: value-at-play-time blend at the 200/200 cell.
# Single box (arg $1=host tag, default this host). cheapest-cells-first so the curve
# fills in fast. n=100 paired, nice -19, detached-friendly. shared-claim ON so other
# boxes can hot-join the same OUTROOT.
set -u
REPO=${REPO:-/home/doctor/projects/carcassone}
PY=${PY:-$REPO/.venv/bin/python}
CKPT=${CKPT:-/mnt/c/carc-shared/stage_b/ckpt/iter_01.pt}
OUTROOT=${OUTROOT:-/mnt/c/carc-shared/scaling_curve}
N=${N:-100}
W=${W:-14}
CPUCT=3.0
HOST=${1:-$(hostname)}
BASEENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"
LOG=${LOG:-/tmp/curve.log}
cd "$REPO" || { echo "no repo"; exit 1; }
[ -f "$CKPT" ] || { echo "FATAL no ckpt $CKPT"; exit 1; }

# cell = net_sims:heur_sims:blend  (cheapest total-sims first; value probes are cheap 200/200)
CELLS="
50:200:0
100:200:0
200:200:0
200:200:0.25
200:200:0.5
400:200:0
200:400:0
800:200:0
200:800:0
"

run_cell() {
  local ns=$1 hs=$2 bl=$3
  local sub="curve/s${ns}_h${hs}_b${bl/./}"
  local blendenv="CARCASSONNE_V25_VALUE_BLEND=$bl"
  echo "=== CELL net=$ns heur=$hs blend=$bl  ($(date +%H:%M:%S)) ===" >> "$LOG"
  nice -n 19 env $BASEENV $blendenv $PY -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$CKPT" --n "$N" --sims "$ns" --heur-sims "$hs" --c-puct "$CPUCT" \
    --workers "$W" --out-root "$OUTROOT" --out-subdir "$sub" \
    --seed-start 1000000000 --paired --shared-claim --claim-host "$HOST" >> "$LOG" 2>&1
  # authoritative pooled summary over all json (sees other boxes too)
  nice -n 19 env $BASEENV $blendenv $PY -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$CKPT" --n "$N" --sims "$ns" --heur-sims "$hs" \
    --out-root "$OUTROOT" --out-subdir "$sub" --seed-start 1000000000 --paired \
    --summary-only 2>>"$LOG" | grep -E 'ELO|wr|win' >> "$LOG"
  echo "--- cell done $(date +%H:%M:%S) ---" >> "$LOG"
}

echo "######## SCALING CURVE start $(date) on $HOST  ckpt=$CKPT N=$N ########" >> "$LOG"
for cell in $CELLS; do
  [ -z "$cell" ] && continue
  IFS=: read -r ns hs bl <<< "$cell"
  run_cell "$ns" "$hs" "$bl"
done
echo "######## SCALING CURVE DONE $(date) ########" >> "$LOG"
