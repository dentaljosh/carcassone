#!/usr/bin/env bash
# bench_fair_batch_grid.sh — the FULL deliverable: the fair net-prior agent's per-move
# cost across (batch_size) and (server --max-batch), over the PRODUCTION orch transport.
#
# Produces two complementary measurements:
#   A) SINGLE-AGENT latency curve  — isolated ms/move vs batch_size (+ the champion
#      reference). max-batch is irrelevant here: one agent never fills the aggregate
#      batch (it fires <=MAX_K=8 boards/request, serially), so a single --max-batch
#      (256) is used. This is the headline latency-per-move number.
#   B) CONCURRENCY throughput grid — W agents searching AT ONCE, batch_size x
#      --max-batch {16,64}. This is where --max-batch bites: the server aggregates the
#      W workers' concurrent requests up to the cap (the "avg_batch 13-14/16 saturating"
#      axis). Reports per-agent ms/move + aggregate throughput + GPU util/power.
#
# Each server config is a fresh export+launch; ALL are torn down on EXIT (trap).
set -euo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
SRV="$REPO/rust/carc-orch/run_server.sh"

CKPT="${CKPT:-/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_03.pt}"
SIMS="${SIMS:-688}"; KDETS="${KDETS:-4}"
CONC="${CONC:-12}"                 # concurrency for grid B (server workers >= this)
SINGLE_MOVES="${SINGLE_MOVES:-3}"  # positions timed in grid A
CONC_MOVES="${CONC_MOVES:-2}"      # positions each agent times in grid B
MEASURE="${MEASURE:-$REPO/measurement/distill_flywheel_20260715}"
mkdir -p "$MEASURE"

[ -f "$CKPT" ] || { echo "FATAL: no checkpoint at $CKPT" >&2; exit 1; }

SHMN="benchgrid$$"
TS="/tmp/carc_benchgrid_$$.ts.pt"
LOG="/tmp/carc_srv_benchgrid_$$.log"

# --- peek rep + export ONCE (server model is the same across configs) ---
read -r NC NS SG < <("$PY" - "$CKPT" <<'EOF'
import sys, torch
ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
print(int(ck.get("n_input_channels", 78)), int(ck.get("n_scalar_features", 10)),
      "sighted" if ck.get("sighted", False) else "non-sighted")
EOF
)
echo "[grid] ckpt $(basename "$CKPT"): ${NC}ch/${NS}sc ($SG)"
echo "[grid] exporting -> TorchScript (parity-gated)"
"$PY" "$REPO/scripts/export_torchscript.py" --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: export/parity failed" >&2; exit 1; }

SRV_PID=""
_stop_srv() {
  [ -n "$SRV_PID" ] && kill "$SRV_PID" 2>/dev/null || true
  pkill -9 -f "carc-orch.*--shm-name $SHMN" 2>/dev/null || true
  rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
  SRV_PID=""
}
# shellcheck disable=SC2064
trap '_stop_srv; rm -f "'"$TS"'" 2>/dev/null || true' EXIT

_start_srv() {  # $1=workers $2=max_batch $3=forwarders
  _stop_srv
  echo "[grid] start carc-orch workers=$1 max_batch=$2 fwd=$3 (${NC}ch/${NS}sc)"
  nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$1" \
    --n-ch "$NC" --n-scalar "$NS" --device cuda --max-batch "$2" \
    --batch-timeout-ms 2.0 --forwarders "$3" --watchdog-secs 30 > "$LOG" 2>&1 &
  SRV_PID=$!
  for _ in $(seq 1 80); do
    grep -q "forwarder-" "$LOG" 2>/dev/null && break
    kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: server died" >&2; tail -15 "$LOG" >&2; exit 1; }
    sleep 0.5
  done
  grep -q "forwarder-" "$LOG" 2>/dev/null || { echo "FATAL: server not ready" >&2; tail -12 "$LOG" >&2; exit 1; }
  echo "[grid] server READY"
}

# client env: curve125 leaf, CUDA hidden (server owns the GPU)
# shellcheck disable=SC1091
source "$REPO/scripts/distill_flywheel/champ_env.sh"
export CUDA_VISIBLE_DEVICES=""

# === A) single-agent latency curve (max-batch irrelevant; 256) ===
echo "=== [grid] A: single-agent latency curve ==="
_start_srv 4 256 2
nice -n 19 "$PY" "$REPO/scripts/bench/bench_fair_batch.py" \
  --orch-shm-name "$SHMN" --batch-sizes "1,8,16,32" --moves "$SINGLE_MOVES" \
  --sims "$SIMS" --k-dets "$KDETS" --champion \
  --out "$MEASURE/BATCH_LATENCY_SINGLE.json"

# === B) concurrency throughput grid, max_batch in {16,64} ===
for MB in 16 64; do
  echo "=== [grid] B: concurrency=$CONC throughput, max_batch=$MB ==="
  _start_srv "$CONC" "$MB" 4
  nice -n 19 "$PY" "$REPO/scripts/bench/bench_fair_batch.py" \
    --orch-shm-name "$SHMN" --concurrency "$CONC" --batch-sizes "8,16,32" \
    --moves "$CONC_MOVES" --sims "$SIMS" --k-dets "$KDETS" \
    --out "$MEASURE/BATCH_THROUGHPUT_mb${MB}.json"
done

echo "[grid] done -> $MEASURE/BATCH_LATENCY_SINGLE.json + BATCH_THROUGHPUT_mb{16,64}.json"
