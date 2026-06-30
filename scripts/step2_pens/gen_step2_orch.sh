#!/usr/bin/env bash
# Step-2 PeNS weaned-flywheel GEN through ONE carc-orch SHM GPU orchestrator for
# the POLICY net (the production fast path; net-on-CPU was the ~145s/game-at-sims50
# blocker). Exports the base policy ckpt -> TorchScript (parity-gated), launches a
# single carc-orch --transport shm server, runs gen_step2.py --shm-eval-server,
# trap-cleans the server + /dev/shm. The orch serves PRIORS; the VALUE is the
# scalar-MLP wean (computed in-worker on CPU, cheap).
#
#   CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
#   SCALAR=/home/doctor/carc_step2_pens/warmstart/warmstart.pt \
#   OW=24 SIMS=200 \
#   bash scripts/step2_pens/gen_step2_orch.sh \
#       --games 400 --blend 0.5 --dropout 0.1 --iter 0 \
#       --out /mnt/c/carc-shared/step2_pens/gen/iter_00
#
# MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3
CKPT=${CKPT:-/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt}   # base POLICY net
SCALAR=${SCALAR:?set SCALAR=<warmstart.pt ScalarMLP, or pass --random-init in EXTRA>}
OW=${OW:-24}                       # gen workers = orchestrator workers (one context)
SIMS=${SIMS:-200}
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_step2pol_${HOST}.ts.pt"
SHMN="step2pol${HOST}"
LOG="/tmp/carc_srvStep2_${HOST}.log"
# v2.9 bmild_cap8 leaf env (matches build_dataset's GUARD env; the orch net forward
# is leaf-independent but we keep the env consistent for the worker's value path).
LEAFENV="CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0 CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0"

cd "$REPO"

NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[step2-orch] base=$(basename "$CKPT") n_scalar=$NS  exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true

echo "[step2-orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null || true; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT

for _ in $(seq 1 80); do
  grep -q "forwarder-" "$LOG" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "$LOG" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "$LOG" >&2; exit 1; }
echo "[step2-orch] server up; launching gen_step2 (W=$OW sims=$SIMS shm=$SHMN)"

# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/step2_pens/gen_step2.py \
  --checkpoint "$CKPT" --scalar-ckpt "$SCALAR" \
  --shm-eval-server "$SHMN" --workers "$OW" --sims "$SIMS" \
  "$@"
