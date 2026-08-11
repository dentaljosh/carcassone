#!/usr/bin/env bash
# SECONDARY gate — HYBRID_K8 leaf-swap via carc-orch SHM:
#   A = hybrid:8:<HEURSIMS> with the v2.8 (meeple_k=2) leaf (neural value + heur endgame)
#   B = hybrid:8:<HEURSIMS> with the v2.7 leaf
# Same iter8 net / @200 neural / residual 0.25 / c_puct / K=8 handoff / decks / seats; only the
# leaf changes. Reuses scripts/level2/eval_hybrid_handoff.py (--meeple-k-a/-b, added 2026-06-22).
# Run AFTER the primary leaf-swap gate (one carc-orch per box). Measurement only; nothing promoted.
#
#   CKPT=/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt OW=48 HEURSIMS=800 \
#   bash scripts/heuristic_v28/v28_hybrid_leaf_swap_orch.sh \
#       --n 200 --paired --seed-start 1907220000 --shared-claim --out-root /mnt/c/carc-shared/v28_pilot
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}; [ -x "$PY" ] || PY=python3
CKPT=${CKPT:?set CKPT=<checkpoint .pt>}
OW=${OW:-48}
HEURSIMS=${HEURSIMS:-800}
MK=${MK:-2.0}
FWD=${ORCH_FWD:-4}; MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_v28hyb_${HOST}.ts.pt"
SHMN="v28hyb${HOST}"
LEAFENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0"

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[v28-hyb-orch] n_scalar=$NS  exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[v28-hyb-orch] start carc-orch (W=$OW)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "/tmp/carc_v28hybsrv_${HOST}.log" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT
for _ in $(seq 1 80); do
  grep -q "forwarder-" "/tmp/carc_v28hybsrv_${HOST}.log" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "/tmp/carc_v28hybsrv_${HOST}.log" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "/tmp/carc_v28hybsrv_${HOST}.log" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "/tmp/carc_v28hybsrv_${HOST}.log" >&2; exit 1; }
echo "[v28-hyb-orch] server ready; client W=$OW via SHM '$SHMN' (A=hybrid:8:$HEURSIMS meeple_k=$MK, B=v2.7)"

# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/level2/eval_hybrid_handoff.py \
  --agent-a "hybrid:8:$HEURSIMS" --agent-b "hybrid:8:$HEURSIMS" \
  --meeple-k-a "$MK" --meeple-k-b 0.0 \
  --ckpt "$CKPT" --shm-eval-server "$SHMN" --workers "$OW" "$@"
