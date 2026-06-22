#!/usr/bin/env bash
# Run the iter8 leaf-swap gate (v28 meeple_k=2 leaf vs v2.7 leaf, same net) through the
# carc-orch SHM GPU orchestrator. Mirrors scripts/eval_orch.sh: export ckpt -> TorchScript
# (parity-gated), launch carc-orch --transport shm, run v28_leaf_swap_orch.py with
# --shm-eval-server, trap-clean the server + /dev/shm on exit.
#
#   CKPT=/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt OW=14 SIMS=200 \
#   bash scripts/heuristic_v28/v28_leaf_swap_orch.sh \
#       --n 200 --paired --c-puct 3.0 --residual-scale 0.25 --meeple-k 2.0 \
#       --out-root /mnt/c/carc-shared/v28_pilot
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3
CKPT=${CKPT:?set CKPT=<checkpoint .pt>}
OW=${OW:-14}
SIMS=${SIMS:-200}
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_v28leaf_${HOST}.ts.pt"
SHMN="v28leaf${HOST}"
LEAFENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_RESIDUAL_SCALE=0.25"

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[v28-leaf-orch] n_scalar=$NS  exporting $(basename "$CKPT") -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[v28-leaf-orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "/tmp/carc_v28srv_${HOST}.log" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT

for _ in $(seq 1 80); do
  grep -q "forwarder-" "/tmp/carc_v28srv_${HOST}.log" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "/tmp/carc_v28srv_${HOST}.log" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "/tmp/carc_v28srv_${HOST}.log" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "/tmp/carc_v28srv_${HOST}.log" >&2; exit 1; }
echo "[v28-leaf-orch] server ready; client W=$OW via SHM '$SHMN'"

# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/heuristic_v28/v28_leaf_swap_orch.py \
  --checkpoint "$CKPT" --shm-eval-server "$SHMN" --sims "$SIMS" --workers "$OW" "$@"
