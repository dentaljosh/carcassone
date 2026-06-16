#!/usr/bin/env bash
# Run eval_net_vs_heuristic.py through the carc-orch SHM GPU orchestrator
# (orch-ON eval). Mirrors gen_flywheel.sh's orch block: export ckpt -> TorchScript
# (parity-gated), launch carc-orch --transport shm, run the eval client with
# --shm-eval-server, then trap-clean the server + /dev/shm on exit.
#
# REQUIRES eval_net_vs_heuristic.py to support --shm-eval-server (orch client).
# Extra eval flags pass through after the wrapper's own:
#
#   CKPT=/mnt/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt OW=10 \
#   SIMS=800 HEUR_SIMS=800 bash scripts/eval_orch.sh \
#       --n 400 --heur-leaf v2_7 --paired \
#       --out-root /mnt/carc-shared/eval_wsweep --out-subdir orch_w10
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
CKPT=${CKPT:?set CKPT=<checkpoint .pt>}
OW=${OW:-10}                               # orch workers (CPU clients)
SIMS=${SIMS:-800}
HEUR_SIMS=${HEUR_SIMS:-$SIMS}
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_eval_${HOST}.ts.pt"
SHMN="evalorch${HOST}"
# Production v2.7 leaf env (matches gen_flywheel / flywheel-eval ENVV).
LEAFENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_V25_RESIDUAL_SCALE=${CARCASSONNE_V25_RESIDUAL_SCALE:-0.25}"

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[eval-orch] n_scalar=$NS  exporting $(basename "$CKPT") -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed — refusing orch eval" >&2; exit 1; }

pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[eval-orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB watchdog=30s)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "/tmp/carc_evalsrv_${HOST}.log" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT

for _ in $(seq 1 80); do
  grep -q "forwarder-" "/tmp/carc_evalsrv_${HOST}.log" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "/tmp/carc_evalsrv_${HOST}.log" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "/tmp/carc_evalsrv_${HOST}.log" 2>/dev/null \
  || { echo "FATAL: carc-orch server failed to start" >&2; tail -12 "/tmp/carc_evalsrv_${HOST}.log" >&2; exit 1; }
echo "[eval-orch] server ready ($(grep -c 'CUDA stream=' "/tmp/carc_evalsrv_${HOST}.log") streams); eval W=$OW via SHM '$SHMN'"

# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/eval_net_vs_heuristic.py \
  --checkpoint "$CKPT" --sims "$SIMS" --heur-sims "$HEUR_SIMS" \
  --workers "$OW" --shm-eval-server "$SHMN" "$@"
