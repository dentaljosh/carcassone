#!/usr/bin/env bash
# iter04 (NEURAL, via carc-orch SHM GPU orchestrator) vs {heur_v2_7@200, greedy}, n=200
# paired, v2.7 leaf. Mirrors eval_orch.sh's orch block but drives eval_hybrid_handoff
# (agent-vs-agent, supports the `greedy` agent). One server, two client runs, trap-clean.
#   CKPT=.../iter_04.pt OW=28 N=200 SHARE=/mnt/c/carc-shared bash run_orch_matchups.sh
set -euo pipefail
REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python3"
CKPT="${CKPT:?set CKPT}"; OW="${OW:-28}"; N="${N:-200}"; SHARE="${SHARE:?set SHARE}"
FWD="${ORCH_FWD:-4}"; MB="${ORCH_MAX_BATCH:-16}"; HOST="$(hostname)"
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_orchm_${HOST}.ts.pt"; SHMN="orchm${HOST}"
OUT="$SHARE/value_search_games"
# v2.7 production leaf (matches heur_v2_7@200; iter04 net-value is an inert residual on it).
LEAFENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_RESIDUAL_SCALE=0.25"

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[orchm] n_scalar=$NS  export $(basename "$CKPT") -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[orchm] start carc-orch (W=$OW fwd=$FWD max_batch=$MB)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "/tmp/carc_orchmsrv_${HOST}.log" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT
for _ in $(seq 1 80); do
  grep -q "forwarder-" "/tmp/carc_orchmsrv_${HOST}.log" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "/tmp/carc_orchmsrv_${HOST}.log" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "/tmp/carc_orchmsrv_${HOST}.log" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "/tmp/carc_orchmsrv_${HOST}.log" >&2; exit 1; }
echo "[orchm] server ready; running matchups via SHM '$SHMN' (OW=$OW)"

run_match () {  # $1=agent-b  $2=out-subdir  $3=seed-start
  echo "### MATCH iter04 vs $1 ($(date +%H:%M:%S))"
  # shellcheck disable=SC2086
  env $LEAFENV nice -n 19 "$PY" -u scripts/level2/eval_hybrid_handoff.py \
    --agent-a iter8 --agent-b "$1" --ckpt "$CKPT" --n "$N" --paired --device cpu \
    --workers "$OW" --shm-eval-server "$SHMN" --out-root "$OUT" --out-subdir "$2" \
    --seed-start "$3" 2>&1 | tail -10
}
run_match "heur@200" "mA_iter04_vs_heur2_7_200" 5400000000
run_match "greedy"   "mB_iter04_vs_greedy"      5500000000
echo "### ORCH MATCHUPS DONE ($(date +%H:%M:%S))"
