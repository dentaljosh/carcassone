#!/usr/bin/env bash
# M2 sighted self-play generation through the carc-orch SHM GPU orchestrator
# (PER-BOX; run one instance per box, --shared-claim to pool into one iter).
# Mirrors gen_flywheel.sh's orch block, but for the SIGHTED (81ch/42-scalar) net
# with the M2 knobs: --leaf-eval nn (the net's VALUE head drives the leaf),
# score_diff_wide target, FPU installed. Requires the channel-configurable orch
# (carc-orch --n-ch/--n-scalar; rebuilt 2026-07-03).
#
#   REPO=/home/doctor/projects/carcassone HOST=5800x \
#   WARM=<sighted ckpt> ITER=0 OUT=<buffer root> \
#   GAMES=400 SIMS=200 FPU=0.6 OW=28 \
#   bash scripts/canonical_az/gen_m2_orch.sh [--shared-claim ...extra run_selfplay flags]
#
# MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
set -uo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
HOST="${HOST:-$(hostname)}"
WARM="${WARM:?set WARM=<sighted checkpoint .pt>}"
OUT="${OUT:?set OUT=<self-play buffer root>}"
ITER="${ITER:-0}"
GAMES="${GAMES:-400}"; SIMS="${SIMS:-200}"; CPUCT="${CPUCT:-3.0}"; FPU="${FPU:-0.6}"
VALUE_TARGET="${VALUE_TARGET:-score_diff_wide}"
SEED_START="${SEED_START:-0}"
# per-box orch worker default: local 5800x 28 / laptop 8 (8GB 4070m RAM ceiling;
# gen_flywheel _OWD). xeon 18. Override with OW=.
_OWD=28; [ "$HOST" = "laptop" ] && _OWD=8; [ "$HOST" = "xeon" ] && _OWD=18
OW="${OW:-$_OWD}"; FWD="${ORCH_FWD:-4}"; MB="${ORCH_MAX_BATCH:-16}"
PY="$REPO/.venv/bin/python"
SRV="$REPO/rust/carc-orch/run_server.sh"
cd "$REPO" || { echo "FATAL: cannot cd $REPO" >&2; exit 1; }
export PYTHONPATH="$REPO/src"
# Production leaf substrate (the v2.9 curve makes the leaf == h_v2.9; affects the
# worker's leaf math only, not the net forward). CY_REPR: Cython featurizer.
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export CARCASSONNE_V29_MEEPLE_CURVE="${CARCASSONNE_V29_MEEPLE_CURVE:--8,-4,-1,0,2,3,4,5}"
[ -f "$WARM" ] || { echo "FATAL: WARM missing $WARM" >&2; exit 1; }
mkdir -p "$OUT"

# peek (n_ch, n_scalar) so the server layout matches the net exactly.
read -r NCH NS < <("$PY" -c "import torch,sys; c=torch.load(sys.argv[1],map_location='cpu',weights_only=False); print(int(c.get('n_input_channels',78)), int(c.get('n_scalar_features',10)))" "$WARM")
TS="/tmp/carc_m2gen_${HOST}.ts.pt"; SHMN="m2gen${HOST}"
echo "[m2-gen-orch] $HOST: warm=$(basename "$WARM") n_ch=$NCH n_scalar=$NS  export -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$WARM" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed — refusing orch gen" >&2; exit 1; }

pkill -f "[c]arc-orch.*--shm-name $SHMN" 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[m2-gen-orch] start carc-orch (W=$OW n_ch=$NCH n_scalar=$NS fwd=$FWD max_batch=$MB)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" \
  --n-ch "$NCH" --n-scalar "$NS" --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 \
  --forwarders "$FWD" --watchdog-secs 30 > "/tmp/carc_m2gensrv_${HOST}.log" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill -f "[c]arc-orch.*--shm-name '"$SHMN"'" 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT
for _ in $(seq 1 120); do grep -q "forwarder-" "/tmp/carc_m2gensrv_${HOST}.log" 2>/dev/null && break; kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "/tmp/carc_m2gensrv_${HOST}.log" >&2; exit 1; }; sleep 0.5; done
grep -q "forwarder-" "/tmp/carc_m2gensrv_${HOST}.log" 2>/dev/null \
  || { echo "FATAL: carc-orch server failed to start" >&2; tail -12 "/tmp/carc_m2gensrv_${HOST}.log" >&2; exit 1; }
echo "[m2-gen-orch] server ready; self-play W=$OW via SHM '$SHMN'"

# shellcheck disable=SC2086
nice -n 19 "$PY" -u scripts/run_selfplay_iter.py \
  --checkpoint "$WARM" --iter "$ITER" --games "$GAMES" \
  --sims "$SIMS" --c-puct "$CPUCT" --fpu "$FPU" \
  --value-target "$VALUE_TARGET" --leaf-eval nn \
  --workers "$OW" --shm-eval-server "$SHMN" \
  --seed-start "$SEED_START" --output-root "$OUT" "$@"
echo "[m2-gen-orch] $HOST FINISHED @ $(date)"
