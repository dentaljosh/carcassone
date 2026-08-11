#!/usr/bin/env bash
# Residual-role pilot through the carc-orch SHM GPU orchestrator (orch-ON, high W).
# Modeled byte-for-byte on scripts/level2/run_hybrid_bands_orch.sh: export iter8 ->
# TorchScript (parity-gated), launch carc-orch --transport shm, run residual_pilot.py
# with --shm-eval-server, trap-clean server + /dev/shm on exit. Workers are CPU-only;
# iter8 net forwards (priors+value) batch on the shared GPU server; the v2.7 leaf runs
# on the worker CPU. residual_scale is set PER-AGENT in the client (0.25 vs 0.0), so the
# SAME net forward feeds both agents — isolating exactly the value head.
#
# Usage:
#   SHARE=/mnt/c/carc-shared OW=28 N=20  bash scripts/search_policy_mixing/run_residual_orch.sh --shared-claim
#   SHARE=/mnt/c/carc-shared OW=28 N=200 bash scripts/search_policy_mixing/run_residual_orch.sh --shared-claim
set -euo pipefail

REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-python}
SHARE=${SHARE:?set SHARE=<share mount path>}
OW=${OW:-28}
N=${N:-200}
SEED=${SEED:-3600000000}
SCALE_A=${SCALE_A:-0.25}
SCALE_B=${SCALE_B:-0.0}
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
EXTRA="${1:-}"

CKPT="$SHARE/flywheel_residual_attempt2/ckpt/iter8.pt"
OUT="$SHARE/spm_residual"
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_residual_${HOST}.ts.pt"
SHMN="residorch${HOST}"
LOG="/tmp/carc_residsrv_${HOST}.log"

export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export CARCASSONNE_USE_FLAT_LEAF=1
export CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_CY_REPR=1

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[resid-orch] n_scalar=$NS  exporting iter8 -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill -f "carc-orch.*$SHMN" 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[resid-orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB watchdog=30s)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill -f "carc-orch.*'"$SHMN"'" 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT

for _ in $(seq 1 120); do
  grep -q "forwarder-" "$LOG" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "$LOG" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG" 2>/dev/null || { echo "FATAL: server failed to start" >&2; tail -12 "$LOG" >&2; exit 1; }
echo "[resid-orch] server ready; running residual pilot (scale_a=$SCALE_A vs scale_b=$SCALE_B) at W=$OW, n=$N"

nice -n 19 "$PY" -u scripts/search_policy_mixing/residual_pilot.py \
  --scale-a "$SCALE_A" --scale-b "$SCALE_B" --ckpt "$CKPT" \
  --n "$N" --paired --seed-start "$SEED" --workers "$OW" \
  --shm-eval-server "$SHMN" \
  --out-root "$OUT" --out-subdir "resid${SCALE_A}__vs__resid${SCALE_B}_b360_n${N}" $EXTRA
echo "[resid-orch] done"
