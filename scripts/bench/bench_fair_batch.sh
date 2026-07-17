#!/usr/bin/env bash
# bench_fair_batch.sh — ms/move vs batch_size for the fair NET-PRIOR agent, over the
# PRODUCTION transport (carc-orch SHM + sighted TorchScript net on the GPU).
#
# Full lifecycle: peek the ckpt rep -> parity-gated TorchScript export -> launch
# carc-orch at the ckpt's OWN dims -> run the bench client -> ALWAYS tear the server
# + its SHM segments down (EXIT trap).
#
# ⚠️ n-ch/n-scalar are peeked from the checkpoint, never assumed: carc-orch defaults to
# 78ch/12sc and a sighted (81/42) net on those defaults SILENTLY corrupts every forward
# (garbage priors, no crash) — the stage-2 trap documented in fair_net_vs_net_orch.sh.
#
# Usage:
#   scripts/bench/bench_fair_batch.sh [CKPT] [BATCH_SIZES] [MOVES]
set -euo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
SRV="$REPO/rust/carc-orch/run_server.sh"

CKPT="${1:-/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_03.pt}"
BATCH_SIZES="${2:-1,8,16,32}"
MOVES="${3:-3}"
SIMS="${SIMS:-688}"
KDETS="${KDETS:-4}"

SHMN="benchfairbatch$$"
TS="/tmp/carc_benchfairbatch_$$.ts.pt"
LOG="/tmp/carc_srv_benchfairbatch_$$.log"
OUT="${OUT:-$REPO/measurement/distill_flywheel_20260715/BATCH_LATENCY_BENCH.json}"

[ -f "$CKPT" ] || { echo "FATAL: no checkpoint at $CKPT" >&2; exit 1; }

# --- peek the rep from the checkpoint itself (never assume the dims) ---
read -r NC NS SG < <("$PY" - "$CKPT" <<'EOF'
import sys, torch
ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
print(int(ck.get("n_input_channels", 78)), int(ck.get("n_scalar_features", 10)),
      "sighted" if ck.get("sighted", False) else "non-sighted")
EOF
)
echo "[bench-fair-batch] ckpt $(basename "$CKPT"): ${NC}ch/${NS}sc ($SG)"

# --- parity-gated TorchScript export (bakes the masked softmax; aborts on mismatch) ---
echo "[bench-fair-batch] exporting -> TorchScript (parity-gated)"
"$PY" "$REPO/scripts/export_torchscript.py" --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

# --- server config (parametrized so a driver can sweep MAX_BATCH / concurrency) ---
SRV_WORKERS="${SRV_WORKERS:-4}"          # SHM slots (>= client concurrency)
SRV_MAXBATCH="${SRV_MAXBATCH:-256}"      # server-side aggregate batch cap across jobs
SRV_FORWARDERS="${SRV_FORWARDERS:-2}"

# --- clean any stale segments for THIS name, then launch ---
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[bench-fair-batch] start carc-orch shm=$SHMN n_ch=$NC n_scalar=$NS workers=$SRV_WORKERS max_batch=$SRV_MAXBATCH fwd=$SRV_FORWARDERS"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$SRV_WORKERS" \
  --n-ch "$NC" --n-scalar "$NS" --device cuda --max-batch "$SRV_MAXBATCH" \
  --batch-timeout-ms 2.0 --forwarders "$SRV_FORWARDERS" --watchdog-secs 30 > "$LOG" 2>&1 &
SRV_PID=$!

# ALWAYS tear down: the server is a daemon (mmap is std::mem::forget'd) with no
# shutdown protocol — kill it and unlink its segments + named semaphores.
# shellcheck disable=SC2064
trap 'kill $SRV_PID 2>/dev/null || true; pkill -9 -f "carc-orch.*--shm-name '"$SHMN"'" 2>/dev/null || true; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_* "'"$TS"'" 2>/dev/null || true' EXIT

# --- readiness gate (80 x 0.5s), fail fast if the server died ---
for _ in $(seq 1 80); do
  grep -q "forwarder-" "$LOG" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "$LOG" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "$LOG" >&2; exit 1; }
echo "[bench-fair-batch] server READY (shm=$SHMN)"

# --- client: the champion leaf env (curve125). CUDA hidden — the server owns the GPU.
# shellcheck disable=SC1091
source "$REPO/scripts/distill_flywheel/champ_env.sh"
export CUDA_VISIBLE_DEVICES=""

# EXTRA_ARGS lets a caller reuse this whole lifecycle for a different client mode
# (e.g. EXTRA_ARGS=--rtt-probe for the round-trip-vs-k probe).
# shellcheck disable=SC2086
nice -n 19 "$PY" "$REPO/scripts/bench/bench_fair_batch.py" \
  --orch-shm-name "$SHMN" --batch-sizes "$BATCH_SIZES" --moves "$MOVES" \
  --sims "$SIMS" --k-dets "$KDETS" --champion --out "$OUT" ${EXTRA_ARGS:-}

echo "[bench-fair-batch] done -> $OUT"
