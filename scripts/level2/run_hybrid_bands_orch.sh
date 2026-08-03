#!/usr/bin/env bash
# L2 hybrid-handoff bands through the carc-orch SHM GPU orchestrator (orch-ON,
# high W). Mirrors scripts/eval_orch.sh: export iter8 -> TorchScript (parity-gated),
# launch carc-orch --transport shm, run the band client(s) with --shm-eval-server,
# trap-clean the server + /dev/shm on exit. Workers are CPU-only; iter8 net
# forwards are batched on the shared GPU server. The v2.7 leaf + heur@N search
# still run on the worker (CPU) -> CY_REPR=1 (worker-CPU encode win) is set.
#
# Phase 1 (default PH=1): hybrid:{2,3,5,8}:3200 + sanity hybrid:5:800 vs iter8.
# Phase 2 (PH=2, set KS): hybrid:K:3200 vs heur@3200 for each K in KS.
# All bands share the fresh band b340 (seed-start 3.40e9) -> shared decks.
#
# Usage:
#   SHARE=/mnt/c/carc-shared OW=28 N=200 bash scripts/level2/run_hybrid_bands_orch.sh --shared-claim
#   SHARE=/mnt/carc-shared OW=24 N=200 PH=2 KS="5 8" bash scripts/level2/run_hybrid_bands_orch.sh --shared-claim
set -euo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-python}
SHARE=${SHARE:?set SHARE=<share mount path>}
OW=${OW:-28}                 # orch workers (CPU clients) = SHM ring slots
N=${N:-200}
PH=${PH:-1}                  # 1 = vs iter8 (Phase1) ; 2 = vs heur@3200 (Phase2)
KS=${KS:-}                   # Phase2: K values, e.g. "5 8"
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
EXTRA="${1:-}"               # e.g. --shared-claim

CKPT="$SHARE/flywheel_residual_attempt2/ckpt/iter8.pt"
OUT="$SHARE/level2_hybrid"
SEED=3400000000
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS="/tmp/carc_hybrid_${HOST}.ts.pt"
SHMN="hybridorch${HOST}"
LOG="/tmp/carc_hybridsrv_${HOST}.log"

export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export CARCASSONNE_USE_FLAT_LEAF=1
export CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_CY_REPR=1
export CARCASSONNE_V25_RESIDUAL_SCALE=0.25

cd "$REPO"
NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CKPT")"
echo "[hybrid-orch] n_scalar=$NS  exporting iter8 -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CKPT" --out "$TS" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed" >&2; exit 1; }

pkill -f "carc-orch.*$SHMN" 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
echo "[hybrid-orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB watchdog=30s)"
nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG" 2>&1 &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; pkill -f "carc-orch.*'"$SHMN"'" 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT

for _ in $(seq 1 120); do
  grep -q "forwarder-" "$LOG" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "$LOG" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG" 2>/dev/null || { echo "FATAL: server failed to start" >&2; tail -12 "$LOG" >&2; exit 1; }
echo "[hybrid-orch] server ready; running bands via SHM '$SHMN' at W=$OW"

run() {  # $1=agent_a  $2=subdir  $3=agent_b  $4=n(optional, default $N)
  local nn="${4:-$N}"
  echo "=== $1 vs $3  (n=$nn, band b340, orch W=$OW) ==="
  nice -n 19 "$PY" -u scripts/level2/eval_hybrid_handoff.py \
    --agent-a "$1" --agent-b "$3" --ckpt "$CKPT" \
    --n "$nn" --paired --seed-start "$SEED" --workers "$OW" \
    --shm-eval-server "$SHMN" \
    --out-root "$OUT" --out-subdir "$2" $EXTRA
}

if [ "$PH" = "1" ]; then
  run "hybrid:2:3200" "hybridK2h3200__vs__iter8_b340_n${N}" "iter8"
  run "hybrid:3:3200" "hybridK3h3200__vs__iter8_b340_n${N}" "iter8"
  run "hybrid:5:3200" "hybridK5h3200__vs__iter8_b340_n${N}" "iter8"
  run "hybrid:8:3200" "hybridK8h3200__vs__iter8_b340_n${N}" "iter8"
  run "hybrid:5:800"  "hybridK5h800__vs__iter8_b340_n${N}"  "iter8"
else
  : "${KS:?set KS=\"5 8\" for Phase 2}"
  TOPUP="${TOPUP:-400}"
  for K in $KS; do
    # (a) reproduce/strengthen the vs-iter8 result by topping up to n=TOPUP in
    #     the SAME dir (resumes from the cached n=200; the _n200 label is just a name).
    if [ "$TOPUP" -gt "$N" ]; then
      run "hybrid:${K}:3200" "hybridK${K}h3200__vs__iter8_b340_n${N}" "iter8" "$TOPUP"
    fi
    # (b) champion check vs the deepest heuristic.
    run "hybrid:${K}:3200" "hybridK${K}h3200__vs__heur3200_b340_n${N}" "heur@3200" "$N"
  done
fi
echo "[hybrid-orch] all bands done"
