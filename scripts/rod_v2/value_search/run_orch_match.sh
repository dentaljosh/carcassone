#!/usr/bin/env bash
# General single-matchup orchestrator screen: AGENT_A (neural iter8, via carc-orch SHM)
# vs AGENT_B, on the chosen LEAF, n=N paired. Reusable for any "neural vs <opponent>"
# screen on the v2.7 OR v2.9 leaf.
#   CKPT=.../iter_02.pt AGENT_B=heur@3200 LEAF=v2_9 N=200 OW=16 \
#   SUBDIR=rodv2_iter02_vs_h3200_v29 SEED=5700000000 SHARE=/mnt/c/carc-shared \
#   bash run_orch_match.sh
set -euo pipefail
REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python3"
CKPT="${CKPT:?}"; AGENT_A="${AGENT_A:-iter8}"; AGENT_B="${AGENT_B:?}"
LEAF="${LEAF:-v2_7}"; N="${N:-200}"; OW="${OW:-16}"; SHARE="${SHARE:?}"
SUBDIR="${SUBDIR:?}"; SEED="${SEED:-5700000000}"
FWD="${ORCH_FWD:-4}"; MB="${ORCH_MAX_BATCH:-16}"; HOST="$(hostname)"
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_om_${HOST}.ts.pt"; SHMN="om${HOST}"
OUT="$SHARE/value_search_games"

if [ "$LEAF" = "v2_9" ]; then
  LEAFENV="CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0 CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0 CARCASSONNE_V25_RESIDUAL_SCALE=0.25"
  MK=2.0
else
  LEAFENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0 CARCASSONNE_V25_RESIDUAL_SCALE=0.25"
  MK=0.0
fi

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[om] $AGENT_A($(basename "$CKPT")) vs $AGENT_B | leaf=$LEAF mk=$MK n=$N OW=$OW  export TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "/tmp/carc_omsrv_${HOST}.log" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT
for _ in $(seq 1 80); do
  grep -q "forwarder-" "/tmp/carc_omsrv_${HOST}.log" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "/tmp/carc_omsrv_${HOST}.log" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "/tmp/carc_omsrv_${HOST}.log" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "/tmp/carc_omsrv_${HOST}.log" >&2; exit 1; }
echo "[om] server ready; running $AGENT_A vs $AGENT_B ($(date +%H:%M:%S))"
# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/level2/eval_hybrid_handoff.py \
  --agent-a "$AGENT_A" --agent-b "$AGENT_B" --ckpt "$CKPT" --n "$N" --paired --device cpu \
  --workers "$OW" --shm-eval-server "$SHMN" --meeple-k-a "$MK" --meeple-k-b "$MK" \
  --out-root "$OUT" --out-subdir "$SUBDIR" --seed-start "$SEED" 2>&1 | tail -12
echo "### OM DONE ($(date +%H:%M:%S))"
