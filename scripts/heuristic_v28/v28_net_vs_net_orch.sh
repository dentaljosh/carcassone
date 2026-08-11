#!/usr/bin/env bash
# Run the two-checkpoint net-vs-net gate through TWO carc-orch SHM GPU orchestrators
# (one per checkpoint; the two contexts share the one GPU). Mirrors v28_leaf_swap_orch.sh:
# export each ckpt -> TorchScript (parity-gated), launch carc-orch --transport shm per side,
# run v28_net_vs_net_orch.py with --shm-eval-server-a/-b, trap-clean BOTH servers + /dev/shm.
#
#   CKPT_A=/mnt/c/carc-shared/.../iterRoD.pt CKPT_B=/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
#   OW=24 SIMS=200 \
#   bash scripts/heuristic_v28/v28_net_vs_net_orch.sh \
#       --n 400 --paired --c-puct 3.0 --residual-scale 0.25 --meeple-k-a 2.0 --meeple-k-b 2.0 \
#       --out-root /mnt/c/carc-shared/v28_nvn
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3
CKPT_A=${CKPT_A:?set CKPT_A=<side-A checkpoint .pt, the RoD candidate>}
CKPT_B=${CKPT_B:?set CKPT_B=<side-B checkpoint .pt, the iter8 parent>}
OW=${OW:-24}                       # workers PER SERVER (two contexts share one GPU)
SIMS=${SIMS:-200}
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS_A="/tmp/carc_v28nvnA_${HOST}.ts.pt"
TS_B="/tmp/carc_v28nvnB_${HOST}.ts.pt"
SHMN_A="v28nvnA${HOST}"
SHMN_B="v28nvnB${HOST}"
LOG_A="/tmp/carc_srvNVNA_${HOST}.log"
LOG_B="/tmp/carc_srvNVNB_${HOST}.log"
LEAFENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0"

cd "$REPO"

# --- export + n_scalar peek, per side (parity-gated; abort on fail) ---
NS_A="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT_A")"
NS_B="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT_B")"
echo "[v28-nvn-orch] A=$(basename "$CKPT_A") n_scalar=$NS_A  |  B=$(basename "$CKPT_B") n_scalar=$NS_B  exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT_A" --out "$TS_A" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed for A" >&2; exit 1; }
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT_B" --out "$TS_B" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed for B" >&2; exit 1; }

# --- clean any stale carc-orch for THESE shm-names ---
pkill carc-orch 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN_A" /dev/shm/sem.carc_"${SHMN_A}"_* \
      "/dev/shm/carc_$SHMN_B" /dev/shm/sem.carc_"${SHMN_B}"_* 2>/dev/null || true

# --- launch BOTH servers (W=OW each; two contexts on one GPU) ---
echo "[v28-nvn-orch] start carc-orch A (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_A"
nice -n 19 "$SRV" --model "$TS_A" --transport shm --shm-name "$SHMN_A" --workers "$OW" --n-scalar "$NS_A" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG_A" 2>&1 &
SRV_A_PID=$!
echo "[v28-nvn-orch] start carc-orch B (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_B"
nice -n 19 "$SRV" --model "$TS_B" --transport shm --shm-name "$SHMN_B" --workers "$OW" --n-scalar "$NS_B" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG_B" 2>&1 &
SRV_B_PID=$!
trap 'kill $SRV_A_PID $SRV_B_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN_A"'" /dev/shm/sem.carc_'"$SHMN_A"'_* "/dev/shm/carc_'"$SHMN_B"'" /dev/shm/sem.carc_'"$SHMN_B"'_*' EXIT

# --- wait for "forwarder-" in BOTH logs (80 x 0.5s each); FATAL if either fails ---
for _ in $(seq 1 80); do
  grep -q "forwarder-" "$LOG_A" 2>/dev/null && break
  kill -0 "$SRV_A_PID" 2>/dev/null || { echo "FATAL: carc-orch A died early" >&2; tail -15 "$LOG_A" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG_A" 2>/dev/null \
  || { echo "FATAL: carc-orch A failed to start" >&2; tail -12 "$LOG_A" >&2; exit 1; }
for _ in $(seq 1 80); do
  grep -q "forwarder-" "$LOG_B" 2>/dev/null && break
  kill -0 "$SRV_B_PID" 2>/dev/null || { echo "FATAL: carc-orch B died early" >&2; tail -15 "$LOG_B" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG_B" 2>/dev/null \
  || { echo "FATAL: carc-orch B failed to start" >&2; tail -12 "$LOG_B" >&2; exit 1; }
echo "[v28-nvn-orch] both servers ready; client W=$OW via SHM A='$SHMN_A' B='$SHMN_B'"

# --- run the client ---
# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/heuristic_v28/v28_net_vs_net_orch.py \
  --checkpoint-a "$CKPT_A" --checkpoint-b "$CKPT_B" \
  --shm-eval-server-a "$SHMN_A" --shm-eval-server-b "$SHMN_B" \
  --sims "$SIMS" --workers "$OW" "$@"
