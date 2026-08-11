#!/usr/bin/env bash
# Generic carc-orch SHM launcher for eval_hybrid_handoff.py (iter8 / heur@N / hybrid agents,
# each with an optional v2.8 meeple_k leaf via --meeple-k-a/-b). Export ckpt->TorchScript
# (parity-gated), launch carc-orch --transport shm, run the client with --shm-eval-server,
# trap-clean. Pass-through args go after the wrapper's own (--agent-a/-b, --meeple-k-a/-b, --n ...).
#
#   # ANCHOR: iter8+v2.8 vs heur@3200_v2.7
#   CKPT=/mnt/c/carc-shared/.../iter8.pt OW=48 bash scripts/heuristic_v28/v28_handoff_orch.sh \
#       --agent-a iter8 --meeple-k-a 2.0 --agent-b heur@3200 \
#       --n 200 --paired --seed-start 1907220000 --shared-claim --out-root /mnt/c/carc-shared/v28_pilot
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}; [ -x "$PY" ] || PY=python3
CKPT=${CKPT:?set CKPT=<checkpoint .pt>}
OW=${OW:-48}
FWD=${ORCH_FWD:-4}; MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_v28hndf_${HOST}.ts.pt"
SHMN="v28hndf${HOST}"
# eval_hybrid_handoff.py sets the v2.7 leaf env itself at import; we still set FLAT/CY for speed.
LEAFENV="CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1"

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[v28-hndf-orch] n_scalar=$NS  exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[v28-hndf-orch] start carc-orch (W=$OW)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "/tmp/carc_v28hndfsrv_${HOST}.log" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT
for _ in $(seq 1 80); do
  grep -q "forwarder-" "/tmp/carc_v28hndfsrv_${HOST}.log" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "/tmp/carc_v28hndfsrv_${HOST}.log" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "/tmp/carc_v28hndfsrv_${HOST}.log" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "/tmp/carc_v28hndfsrv_${HOST}.log" >&2; exit 1; }
echo "[v28-hndf-orch] server ready; client W=$OW via SHM '$SHMN'"

# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/level2/eval_hybrid_handoff.py \
  --ckpt "$CKPT" --shm-eval-server "$SHMN" --workers "$OW" "$@"
