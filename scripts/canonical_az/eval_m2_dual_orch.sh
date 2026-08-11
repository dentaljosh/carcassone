#!/usr/bin/env bash
# M2 per-iter health check: sighted CANDIDATE vs a FIXED blind REFERENCE net,
# through TWO carc-orch SHM orchestrators (one per net; the two contexts share
# the one GPU). Mirrors scripts/step2_pens/eval_step2_orch.sh's dual-server
# pattern. Cand is 81ch sighted; ref is 78ch blind (default RoD-v2 iter_02,
# ~h3200_v2.9 tier — see reference_rodv2_iter2_eval_anchor). Each net plays its
# OWN rep (fair-info game); the channel-configurable orch (--n-ch/--n-scalar)
# carries both.
#
#   CAND=<sighted iter ckpt> \
#   REF=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
#   OW=28 SIMS=200 N=200 FPU=0.6 OUT=<out dir> \
#   bash scripts/canonical_az/eval_m2_dual_orch.sh [--paired --shared-claim ...]
#
# MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
set -uo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
PY="${PY:-$REPO/.venv/bin/python}"
CAND="${CAND:?set CAND=<sighted candidate .pt>}"
# Default REF: RoD-v2 iter_02 (blind 78ch, ~h3200_v2.9 parity, the standard fast
# anchor). It DISCRIMINATES a fresh sighted net (~greedy/weak-MCTS -> ~wr0.36)
# without saturating, and has headroom both ways as the cand trains up.
REF="${REF:-/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt}"
N="${N:-200}"; SIMS="${SIMS:-200}"; CPUCT="${CPUCT:-3.0}"; FPU="${FPU:-0.6}"
HOST="${HOST:-$(hostname)}"
# dual-server: two contexts contend for one GPU -> per-server W below single-ctx.
# local ~28, laptop 16 (8GB 4070m, two nets resident). Override OW=.
_OWD=28; [ "$HOST" = "laptop" ] && _OWD=16; [ "$HOST" = "xeon" ] && _OWD=12
OW="${OW:-$_OWD}"; FWD="${ORCH_FWD:-4}"; MB="${ORCH_MAX_BATCH:-16}"
OUT="${OUT:?set OUT=<output dir>}"
SEED_START="${SEED_START:-1906220000}"
SRV="$REPO/rust/carc-orch/run_server.sh"
cd "$REPO" || { echo "FATAL: cannot cd $REPO" >&2; exit 1; }
export PYTHONPATH="$REPO/src"
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export CARCASSONNE_V29_MEEPLE_CURVE="${CARCASSONNE_V29_MEEPLE_CURVE:--8,-4,-1,0,2,3,4,5}"
[ -f "$CAND" ] || { echo "FATAL: CAND missing $CAND" >&2; exit 1; }
[ -f "$REF" ]  || { echo "FATAL: REF missing $REF"  >&2; exit 1; }

peek() { "$PY" -c "import torch,sys; c=torch.load(sys.argv[1],map_location='cpu',weights_only=False); print(int(c.get('n_input_channels',78)), int(c.get('n_scalar_features',10)))" "$1"; }
read -r NCH_C NS_C < <(peek "$CAND")
read -r NCH_R NS_R < <(peek "$REF")
TS_C="/tmp/carc_m2evC_${HOST}.ts.pt"; TS_R="/tmp/carc_m2evR_${HOST}.ts.pt"
SHMN_C="m2evC${HOST}"; SHMN_R="m2evR${HOST}"
LOG_C="/tmp/carc_m2srvC_${HOST}.log"; LOG_R="/tmp/carc_m2srvR_${HOST}.log"
echo "[m2-eval-orch] CAND=$(basename "$CAND") ($NCH_C/$NS_C)  REF=$(basename "$REF") ($NCH_R/$NS_R)  export -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CAND" --out "$TS_C" --device cuda \
  || { echo "FATAL: export CAND failed" >&2; exit 1; }
"$PY" scripts/export_torchscript.py --checkpoint "$REF" --out "$TS_R" --device cuda \
  || { echo "FATAL: export REF failed" >&2; exit 1; }

pkill -f "[c]arc-orch.*--shm-name $SHMN_C" 2>/dev/null || true
pkill -f "[c]arc-orch.*--shm-name $SHMN_R" 2>/dev/null || true
sleep 1
rm -f "/dev/shm/carc_$SHMN_C" /dev/shm/sem.carc_"${SHMN_C}"_* \
      "/dev/shm/carc_$SHMN_R" /dev/shm/sem.carc_"${SHMN_R}"_* 2>/dev/null || true

echo "[m2-eval-orch] start CAND server (W=$OW n_ch=$NCH_C n_scalar=$NS_C) shm=$SHMN_C"
nice -n 19 "$SRV" --model "$TS_C" --transport shm --shm-name "$SHMN_C" --workers "$OW" \
  --n-ch "$NCH_C" --n-scalar "$NS_C" --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 \
  --forwarders "$FWD" --watchdog-secs 30 > "$LOG_C" 2>&1 &
SRV_C_PID=$!
echo "[m2-eval-orch] start REF server (W=$OW n_ch=$NCH_R n_scalar=$NS_R) shm=$SHMN_R"
nice -n 19 "$SRV" --model "$TS_R" --transport shm --shm-name "$SHMN_R" --workers "$OW" \
  --n-ch "$NCH_R" --n-scalar "$NS_R" --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 \
  --forwarders "$FWD" --watchdog-secs 30 > "$LOG_R" 2>&1 &
SRV_R_PID=$!
trap 'kill $SRV_C_PID $SRV_R_PID 2>/dev/null || true; rm -f "/dev/shm/carc_'"$SHMN_C"'" /dev/shm/sem.carc_'"$SHMN_C"'_* "/dev/shm/carc_'"$SHMN_R"'" /dev/shm/sem.carc_'"$SHMN_R"'_*' EXIT

for _ in $(seq 1 120); do grep -q "forwarder-" "$LOG_C" 2>/dev/null && break; kill -0 "$SRV_C_PID" 2>/dev/null || { echo "FATAL: CAND server died" >&2; tail -15 "$LOG_C" >&2; exit 1; }; sleep 0.5; done
grep -q "forwarder-" "$LOG_C" 2>/dev/null || { echo "FATAL: CAND server no-start" >&2; tail -12 "$LOG_C" >&2; exit 1; }
for _ in $(seq 1 120); do grep -q "forwarder-" "$LOG_R" 2>/dev/null && break; kill -0 "$SRV_R_PID" 2>/dev/null || { echo "FATAL: REF server died" >&2; tail -15 "$LOG_R" >&2; exit 1; }; sleep 0.5; done
grep -q "forwarder-" "$LOG_R" 2>/dev/null || { echo "FATAL: REF server no-start" >&2; tail -12 "$LOG_R" >&2; exit 1; }
echo "[m2-eval-orch] both servers up; launching net-vs-net (W=$OW sims=$SIMS n=$N fpu=$FPU)"

# shellcheck disable=SC2086
nice -n 19 "$PY" -u scripts/canonical_az/eval_m2_net_vs_net.py \
  --cand-ckpt "$CAND" --ref-ckpt "$REF" \
  --shm-eval-server-cand "$SHMN_C" --shm-eval-server-ref "$SHMN_R" \
  --n "$N" --sims "$SIMS" --c-puct "$CPUCT" --fpu "$FPU" --workers "$OW" \
  --seed-start "$SEED_START" --out-root "$OUT" "$@"
