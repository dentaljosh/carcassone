# NOTE: the RUNTIME copy lives at /mnt/c/carc-shared/code_sync/gen_flywheel_v29.sh
# (all boxes run it via their CIFS mount). This repo copy is the TRACKED source —
# edit the share copy to deploy, keep this in sync. (No auto-staging yet.)
#!/usr/bin/env bash
# RoD v2 per-box residual-FLYWHEEL self-play, FROZEN v2.9 leaf (Bmild_cap8).
# == gen_flywheel.sh but the heuristic leaf is the frozen v2.9 classical substrate
# (governance/LEAF_SUBSTRATES.yaml v2_9_bmild_cap8): nonlinear meeple liquidity CURVE
# (-8,-4,-1,0,2,3,4,5) REPLACES flat meeple_k, bonus_cap=8, 3-open closure. The net's
# residual head (SCALE·Δ) rides on top of THIS leaf. Self-play SEARCH is guided by
# (v2.9 leaf + SCALE·Δ) using the CURRENT flywheel net; records value_target=residual.
#
# Curve runs on the cython fast leaf (flat_leaf_cy SUPPORTS_V29_CURVE) — this script
# rebuilds the .so on any box whose build lacks curve support, else the pure-Python
# flat curve path (capability-flag fallback) keeps it CORRECT (just slower).
#
# Env: SHARE REPO HOST WARM OUT [SCALE=0.25] [WORKERS=14] [GAMES=400] [SIMS=200] [BRANCH=rod_v2_flywheel]
set -uo pipefail

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

SHARE="${SHARE:?}"; REPO="${REPO:?}"; HOST="${HOST:?}"; WARM="${WARM:?}"; OUT="${OUT:?}"
SCALE="${SCALE:-0.25}"; WORKERS="${WORKERS:-14}"; GAMES="${GAMES:-400}"; SIMS="${SIMS:-200}"
SEED_START="${SEED_START:-0}"
BRANCH="${BRANCH:-rod_v2_flywheel}"
PY="$REPO/.venv/bin/python"
cd "$REPO" || { echo "FATAL: cannot cd $REPO" >&2; exit 1; }
echo "=== gen_flywheel_v29 on $HOST @ $(date): v2.9 leaf (Bmild_cap8) scale=$SCALE warm=$(basename $WARM) W=$WORKERS target=$GAMES seed_start=$SEED_START ==="
# Only REMOTES need the code sync. The local 5800x AUTHORS the bundle; a hard reset
# here clobbers post-launch doc commits. Skip it locally.
if [ "$HOST" != "5800x" ]; then
  git fetch "$SHARE/code_sync/carc_${BRANCH}.bundle" "$BRANCH" && git reset --hard FETCH_HEAD \
    || { echo "FATAL: code sync failed on $HOST — refusing to generate self-play on STALE code" >&2; exit 1; }
fi
echo "  HEAD now: $(git rev-parse --short HEAD) (host=$HOST)"
# Ensure the cython leaf on THIS box implements the v2.9 curve. If not (stale .so /
# fresh remote), rebuild it. On failure the Python wrapper falls back to the
# pure-Python flat curve path (bit-exact, slower) — never a silent v2.8 leaf.
if ! "$PY" -c "import carcassonne_ai.flat_leaf_cy as c; assert getattr(c,'SUPPORTS_V29_CURVE',False)" 2>/dev/null; then
  echo "  [cy] flat_leaf_cy lacks v2.9 curve on $HOST — rebuilding (.so)"
  "$PY" setup_flat_leaf_cy.py build_ext --inplace >/dev/null 2>&1 \
    && echo "  [cy] rebuilt OK ($("$PY" -c 'import carcassonne_ai.flat_leaf_cy as c; print(getattr(c,"SUPPORTS_V29_CURVE",False))'))" \
    || echo "  [cy] rebuild FAILED — using pure-Python flat curve fallback (correct, ~slower)"
fi
[ -f "$WARM" ] || { echo "FATAL: WARM missing $WARM" >&2; exit 1; }
mkdir -p "$OUT"
SP_COMMON="--iter 0 --games $GAMES --sims $SIMS --leaf-eval v2_5 --value-blend 0 \
  --residual-scale $SCALE --value-target residual --batch-size 8 --checkpoint $WARM \
  --anchor-fraction 0 --output-root $OUT --shared-claim --claim-host $HOST --seed-start $SEED_START"

# v2.9 FROZEN leaf env (Bmild_cap8): curve REPLACES flat meeple; cap=8; 3-open (do NOT
# set DROP_THREE_OPEN); meeple_k=2.0 present-but-inert (matches the frozen substrate).
V29_LEAF_ENV="CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 \
CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0 \
CARCASSONNE_USE_FLAT_LEAF=1"

USE_ORCH="${USE_ORCH:-0}"
if { [ "$HOST" = "5800x" ] || [ "$HOST" = "xeon" ] || [ "$HOST" = "laptop" ]; } && [ "$USE_ORCH" = "1" ]; then
  _OWD=28; [ "$HOST" = "xeon" ] && _OWD=18; [ "$HOST" = "laptop" ] && _OWD=8
  OW="${ORCH_WORKERS:-$_OWD}"; FWD="${ORCH_FWD:-4}"; MB="${ORCH_MAX_BATCH:-16}"
  SRV="$REPO/rust/carc-orch/run_server.sh"
  NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$WARM")"
  TS="/tmp/carc_fwgenv29_${HOST}.ts.pt"; SHMN="fwgenv29${HOST}"
  echo "  [orch] n_scalar=$NS  exporting $(basename "$WARM") -> TorchScript (parity-gated)"
  "$PY" scripts/export_torchscript.py --checkpoint "$WARM" --out "$TS" --device cuda \
    || { echo "FATAL: TorchScript export/parity failed — refusing to gen on orch path" >&2; exit 1; }
  pkill carc-orch 2>/dev/null; sleep 1; rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_*
  echo "  [orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB watchdog=30s)"
  nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
    --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
    > "/tmp/carc_srv_v29_${HOST}.log" 2>&1 &
  SRV_PID=$!
  trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT
  for _ in $(seq 1 80); do grep -q "forwarder-" "/tmp/carc_srv_v29_${HOST}.log" 2>/dev/null && break; sleep 0.5; done
  grep -q "forwarder-" "/tmp/carc_srv_v29_${HOST}.log" 2>/dev/null \
    || { echo "FATAL: carc-orch server failed to start" >&2; tail -10 "/tmp/carc_srv_v29_${HOST}.log" >&2; exit 1; }
  echo "  [orch] server ready ($(grep -c 'CUDA stream=' "/tmp/carc_srv_v29_${HOST}.log") streams); self-play W=$OW via SHM '$SHMN'"
  # shellcheck disable=SC2086
  env $V29_LEAF_ENV CARCASSONNE_USE_CY_REPR=1 \
    nice -n 19 "$PY" -u scripts/run_selfplay_iter.py $SP_COMMON --workers "$OW" --shm-eval-server "$SHMN"
else
  # shellcheck disable=SC2086
  env $V29_LEAF_ENV \
    nice -n 19 "$PY" -u scripts/run_selfplay_iter.py $SP_COMMON --workers "$WORKERS"
fi
echo "=== gen_flywheel_v29 on $HOST FINISHED @ $(date) ==="
