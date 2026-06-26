#!/usr/bin/env bash
# v2.9-leaf net-vs-net via TWO carc-orch SHM orchestrators (one per ckpt; two contexts
# on one GPU). == v28_net_vs_net_orch.sh but LEAFENV = the frozen v2.9 Bmild_cap8 leaf
# (curve replaces flat meeple, cap 8, 3-open). Both nets ride the v2.9 leaf + residual_scale.
# --meeple-k-a/-b 2.0 are inert (curve replaces the flat term). Single-box (local).
#
#   CKPT_A=/abs/A.pt CKPT_B=/abs/B.pt OW=24 SIMS=200 \
#   bash scripts/rod_v2/net_vs_net_v29.sh --n 200 --paired --c-puct 3.0 --residual-scale 0.25 \
#       --meeple-k-a 2.0 --meeple-k-b 2.0 --seed-start <S> --shared-claim --claim-host local \
#       --out-root <dir> --out-subdir <sub>
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3
CKPT_A=${CKPT_A:?set CKPT_A=<side-A .pt>}
CKPT_B=${CKPT_B:?set CKPT_B=<side-B .pt>}
OW=${OW:-24}
SIMS=${SIMS:-200}
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS_A="/tmp/carc_v29nvnA_${HOST}.ts.pt"
TS_B="/tmp/carc_v29nvnB_${HOST}.ts.pt"
SHMN_A="v29nvnA${HOST}"
SHMN_B="v29nvnB${HOST}"
LOG_A="/tmp/carc_srvV29NVNA_${HOST}.log"
LOG_B="/tmp/carc_srvV29NVNB_${HOST}.log"
# v2.9 FROZEN leaf env (Bmild_cap8). DROP_THREE_OPEN=0 -> 3-open.
LEAFENV="CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0 CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0"

cd "$REPO"
NS_A="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT_A")"
NS_B="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT_B")"
echo "[v29-nvn] A=$(basename "$CKPT_A") ns=$NS_A | B=$(basename "$CKPT_B") ns=$NS_B  exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT_A" --out "$TS_A" --device cuda || { echo "FATAL: export A failed" >&2; exit 1; }
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT_B" --out "$TS_B" --device cuda || { echo "FATAL: export B failed" >&2; exit 1; }

pkill -9 -f "[c]arc-orch" 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN_A" /dev/shm/sem.carc_"${SHMN_A}"_* "/dev/shm/carc_$SHMN_B" /dev/shm/sem.carc_"${SHMN_B}"_* 2>/dev/null || true

echo "[v29-nvn] start carc-orch A (W=$OW) shm=$SHMN_A"
nice -n 19 "$SRV" --model "$TS_A" --transport shm --shm-name "$SHMN_A" --workers "$OW" --n-scalar "$NS_A" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 > "$LOG_A" 2>&1 &
SRV_A_PID=$!
echo "[v29-nvn] start carc-orch B (W=$OW) shm=$SHMN_B"
nice -n 19 "$SRV" --model "$TS_B" --transport shm --shm-name "$SHMN_B" --workers "$OW" --n-scalar "$NS_B" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 > "$LOG_B" 2>&1 &
SRV_B_PID=$!
trap 'kill $SRV_A_PID $SRV_B_PID 2>/dev/null; pkill -9 -f "[c]arc-orch" 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN_A"'" /dev/shm/sem.carc_'"$SHMN_A"'_* "/dev/shm/carc_'"$SHMN_B"'" /dev/shm/sem.carc_'"$SHMN_B"'_*' EXIT

for _ in $(seq 1 80); do grep -q "forwarder-" "$LOG_A" 2>/dev/null && break; kill -0 "$SRV_A_PID" 2>/dev/null || { echo "FATAL: orch A died" >&2; tail -15 "$LOG_A" >&2; exit 1; }; sleep 0.5; done
grep -q "forwarder-" "$LOG_A" 2>/dev/null || { echo "FATAL: orch A no start" >&2; tail -12 "$LOG_A" >&2; exit 1; }
for _ in $(seq 1 80); do grep -q "forwarder-" "$LOG_B" 2>/dev/null && break; kill -0 "$SRV_B_PID" 2>/dev/null || { echo "FATAL: orch B died" >&2; tail -15 "$LOG_B" >&2; exit 1; }; sleep 0.5; done
grep -q "forwarder-" "$LOG_B" 2>/dev/null || { echo "FATAL: orch B no start" >&2; tail -12 "$LOG_B" >&2; exit 1; }
echo "[v29-nvn] both servers ready; client W=$OW"

# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/heuristic_v28/v28_net_vs_net_orch.py \
  --checkpoint-a "$CKPT_A" --checkpoint-b "$CKPT_B" \
  --shm-eval-server-a "$SHMN_A" --shm-eval-server-b "$SHMN_B" \
  --sims "$SIMS" --workers "$OW" "$@"
