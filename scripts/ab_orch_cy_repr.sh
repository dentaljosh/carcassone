#!/usr/bin/env bash
# 5800x carc-orch game-count A/B: CARCASSONNE_USE_CY_REPR off vs on (2026-06-17).
# Tests whether the Cython board-encoder converts to throughput in the ORCH
# regime (per-worker-CPU-bound = the orchestrator's stated limit) — the one place
# the orch-off W14 A/B (NULL, GPU-dispatch-bound) said it might. Same seeds =>
# bit-identical games => fair fixed-work A/B; only the worker-side encode differs.
#   Env: W=28 SIMS=800 WINDOW=600
set -uo pipefail
R=/home/doctor/projects/carcassone; cd "$R"
CKPT="${CKPT:-/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt}"
TS="${TS:-rust/carc-orch/iter8.ts.pt}"
W="${W:-28}"; SIMS="${SIMS:-800}"; WINDOW="${WINDOW:-600}"
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1"
SP="--iter 0 --games 9000 --sims $SIMS --leaf-eval v2_5 --value-blend 0 --residual-scale 0.25 --value-target residual --batch-size 8 --checkpoint $CKPT --seed-start 5000000"
RESULT=/tmp/ab_orch_cyrepr_result.txt; : > "$RESULT"
ngames(){ find "$1" -name '*.npz' 2>/dev/null | wc -l; }
cleanup(){
  pkill -9 -f "[r]un_selfplay_iter" 2>/dev/null||true
  pkill -9 -f "[c]arc-orch" 2>/dev/null||true
  pkill -9 -f "[m]ultiprocessing.spawn" 2>/dev/null||true
  rm -f /dev/shm/carc_* /dev/shm/sem.carc_* 2>/dev/null||true
  sleep 3
  for _ in $(seq 1 20); do awk '{exit !($1<3)}' /proc/loadavg && break; sleep 2; done
}

run_arm(){
  local cy=$1
  local SHMN="cyrepr${cy}"
  local OUT="/tmp/ab_orch_cy${cy}_out"
  local SLOG="/tmp/ab_orch_cy${cy}_srv.log"
  local PLOG="/tmp/ab_orch_cy${cy}_play.log"
  rm -rf "$OUT"; mkdir -p "$OUT"; cleanup
  echo "=== ARM cy=$cy : carc-orch W=$W sims=$SIMS window=${WINDOW}s ==="
  setsid bash -c "rust/carc-orch/run_server.sh --model $TS --transport shm --shm-name $SHMN --workers $W --n-scalar 12 --forwarders 4 --max-batch 16 --watchdog-secs 0" </dev/null >"$SLOG" 2>&1 &
  for i in $(seq 1 150); do grep -q READY "$SLOG" && break; sleep 1; done
  if ! grep -q READY "$SLOG"; then echo "cy=$cy SERVER-FAIL"; tail -5 "$SLOG"; echo "cy=$cy games=0 dt=0 gpm=0 SERVER-FAIL" >> "$RESULT"; return; fi
  local t0=$(date +%s)
  setsid bash -c "env $ENVV CARCASSONNE_USE_CY_REPR=$cy timeout $WINDOW nice -n 19 .venv/bin/python -u scripts/run_selfplay_iter.py $SP --output-root $OUT --workers $W --shm-eval-server $SHMN" </dev/null >"$PLOG" 2>&1 &
  local APID=$!
  while kill -0 "$APID" 2>/dev/null; do sleep 5; done
  local t1; t1=$(date +%s)
  local dt=$((t1-t0))
  local n; n=$(ngames "$OUT")
  local busy; busy=$(grep -oE "fwd_busy=[0-9]+%" "$SLOG"|tail -1)
  local gpm; gpm=$(python3 -c "print(f'{$n/($dt/60.0):.2f}')")
  echo "ARM cy=$cy: games=$n wall=${dt}s ${busy:-?}  -> ${gpm} g/min"
  echo "cy=$cy games=$n dt=$dt gpm=$gpm" >> "$RESULT"
}

echo "=== 5800x carc-orch W$W cy-repr A/B (sims=$SIMS, ${WINDOW}s/arm) $(date +%T) ==="
run_arm 0
run_arm 1
cleanup
echo "=== SUMMARY ==="; cat "$RESULT"
python3 - "$RESULT" <<'PY'
import sys
d={}
for ln in open(sys.argv[1]):
    p=ln.split(); d[p[0].split('=')[1]]={k:v for k,v in (x.split('=') for x in p[1:] if '=' in x)}
if '0' in d and '1' in d and float(d['0'].get('gpm',0))>0:
    o=float(d['0']['gpm']); n=float(d['1']['gpm'])
    print(f"\ncy-repr ON/OFF = {n/o:.3f}x   (off {o} -> on {n} g/min)")
PY
echo "=== A/B DONE $(date +%T) ==="
