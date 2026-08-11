#!/usr/bin/env bash
# orch-IN-EVAL throughput sweep (2026-06-17): does carc-orch speed up the EVAL
# gate (net@sims vs heur@sims)? eval = 64% of cycle. orch-off runs N separate net
# CUDA contexts (GPU context-thrash); orch = 1 shared context. Metric = moves/s
# via CARC_BENCH_TP (moves/game identical orch-vs-off -> valid; avoids long-game
# windows). 5800x A/B 2026-06-17: matched W14 orch=4.7 vs off=2.1 = 2.24x.
#   Env: CELLS="off:14 orch:14 orch:24 orch:28"  SIMS=800  DUR=360  CKPT=...
set -uo pipefail
R="${REPO:-/home/doctor/projects/carcassone}"; cd "$R"
CKPT="${CKPT:-/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt}"
TS="${TS:-/tmp/carc_evalab.ts.pt}"
SIMS="${SIMS:-800}"; HSIMS="${HSIMS:-$SIMS}"; DUR="${DUR:-360}"; WARM="${WARM:-120}"
CELLS="${CELLS:-off:14 orch:14 orch:24 orch:28}"
LEAFENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1"
RESULT="${RESULT:-/tmp/ab_orch_eval_result.txt}"; : > "$RESULT"
PY="$R/.venv/bin/python"

kill_all(){
  pkill -9 -f "release/carc-orch" 2>/dev/null
  pkill -9 -f "eval_net_vs_heuristic" 2>/dev/null
  pkill -9 -f "multiprocessing.spawn" 2>/dev/null
  rm -f /dev/shm/carc_* /dev/shm/sem.carc_* 2>/dev/null
  sleep 2
  for _ in $(seq 1 20); do awk '{exit !($1<3)}' /proc/loadavg && break; sleep 2; done
}

parse_mps(){  # $1=log : sum of per-pid moves/s over [WARM, end]
  "$PY" - "$1" "$WARM" <<'PY'
import sys,re
log,warm=sys.argv[1],float(sys.argv[2])
per={}
for ln in open(log,errors='ignore'):
    m=re.search(r'BENCHTP pid=(\d+) t=([\d.]+) moves=(\d+)',ln)
    if m: per.setdefault(m.group(1),[]).append((float(m.group(2)),int(m.group(3))))
tot=0.0
for pid,pts in per.items():
    if len(pts)<2: continue
    base=pts[0][0]
    a=next((p for p in pts if p[0]-base>=warm), pts[0])
    b=pts[-1]
    if b[0]>a[0]: tot+=(b[1]-a[1])/(b[0]-a[0])
print(f"{tot:.2f}")
PY
}

run_cell(){
  local mode=$1 W=$2
  local tag="${mode}${W}"
  local SHMN="evab${tag}" OUT="/tmp/ab_eval_${tag}_out"
  local PLOG="/tmp/ab_eval_${tag}_play.log" SLOG="/tmp/ab_eval_${tag}_srv.log"
  rm -rf "$OUT"; mkdir -p "$OUT"; kill_all
  local EXTRA=""
  if [ "$mode" = "orch" ]; then
    rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null
    setsid bash -c "$R/rust/carc-orch/run_server.sh --model $TS --transport shm --shm-name $SHMN --workers $W --n-scalar 12 --forwarders 4 --max-batch 16 --watchdog-secs 30" </dev/null >"$SLOG" 2>&1 &
    for i in $(seq 1 120); do grep -q "forwarder-" "$SLOG" && break; sleep 1; done
    grep -q "forwarder-" "$SLOG" || { echo "$tag SERVER-FAIL"; tail -5 "$SLOG"; echo "$mode W=$W mps=0 SERVER-FAIL" >>"$RESULT"; return; }
    EXTRA="--shm-eval-server $SHMN"
  fi
  echo "=== CELL $tag : eval W=$W net@$SIMS heur@$HSIMS dur=${DUR}s ==="
  setsid bash -c "env $LEAFENV CARC_BENCH_TP=1 timeout $DUR nice -n 19 $PY -u scripts/eval_net_vs_heuristic.py --checkpoint $CKPT --n 9000 --sims $SIMS --heur-sims $HSIMS --c-puct 3.0 --heur-leaf v2_7 --residual-scale 0.25 --workers $W $EXTRA --out-root $OUT --out-subdir run --seed-start 3000000000" </dev/null >"$PLOG" 2>&1 &
  local APID=$!
  while kill -0 "$APID" 2>/dev/null; do sleep 10; done
  local mps; mps=$(parse_mps "$PLOG")
  local busy=""; [ "$mode" = "orch" ] && busy=$(grep -oE "fwd_busy=[0-9]+%" "$SLOG"|tail -1)
  local npid; npid=$(grep -oE 'pid=[0-9]+' "$PLOG" 2>/dev/null | sort -u | wc -l)
  echo "CELL $tag: moves/s=$mps  workers_seen=$npid  $busy"
  echo "$mode W=$W mps=$mps workers=$npid $busy" >>"$RESULT"
  kill_all
}

echo "=== orch-in-eval sweep ($(hostname)) net@$SIMS heur@$HSIMS ${DUR}s/cell cells=[$CELLS] $(date +%T) ==="
echo "[setup] export TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda 2>&1 | tail -2 || { echo "FATAL: TS export"; exit 1; }
for cell in $CELLS; do run_cell "${cell%%:*}" "${cell##*:}"; done
echo "=== SUMMARY ==="; cat "$RESULT"
"$PY" - "$RESULT" <<'PY'
import sys,re
rows=[]
for ln in open(sys.argv[1]):
    m=re.match(r'(\w+) W=(\d+) mps=([\d.]+)',ln)
    if m: rows.append((m.group(1),int(m.group(2)),float(m.group(3))))
base=next((r for r in rows if r[0]=='off'), None)
print()
for mode,w,mps in rows:
    rel=f"  ({mps/base[2]:.2f}x vs off W{base[1]})" if base and base[2]>0 else ""
    print(f"  {mode:4s} W={w:<3d} {mps:6.2f} moves/s{rel}")
PY
echo "=== EVAL SWEEP DONE $(date +%T) ==="
