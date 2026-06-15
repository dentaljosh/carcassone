# NOTE: the RUNTIME copy lives at /mnt/c/carc-shared/code_sync/gen_flywheel.sh
# (all boxes run it via their CIFS mount). This repo copy is the TRACKED source —
# edit the share copy to deploy, keep this in sync. (No auto-staging yet.)
#!/usr/bin/env bash
# Per-box residual-FLYWHEEL self-play (Lever 3). Like gen_residual.sh but the
# self-play SEARCH is guided by the residual leaf (v2.7 + SCALE·Δ, value head
# ACTIVE via --residual-scale) using the CURRENT flywheel net, and records
# value_target=residual from that co-adapted search distribution. Shared-claim →
# boxes hot-join the iter's data pool.
#
# Env: SHARE REPO HOST WARM OUT [SCALE=0.25] [WORKERS=14] [GAMES=400] [SIMS=200]
set -uo pipefail
SHARE="${SHARE:?}"; REPO="${REPO:?}"; HOST="${HOST:?}"; WARM="${WARM:?}"; OUT="${OUT:?}"
SCALE="${SCALE:-0.25}"; WORKERS="${WORKERS:-14}"; GAMES="${GAMES:-400}"; SIMS="${SIMS:-200}"
# SEED_START rotates the self-play deck band per flywheel iter (attempt #2: distinct
# decks each iter → no co-adaptation to one fixed 400-deck set). Default 0 = back-compat
# with attempt #1. Self-play namespace stays well below the 1e9 eval floor.
SEED_START="${SEED_START:-0}"
PY="$REPO/.venv/bin/python"
cd "$REPO" || { echo "FATAL: cannot cd $REPO" >&2; exit 1; }
echo "=== gen_flywheel on $HOST @ $(date): residual leaf scale=$SCALE warm=$(basename $WARM) W=$WORKERS target=$GAMES seed_start=$SEED_START ==="
# Only REMOTES need the code sync. The local 5800x AUTHORS the bundle; a hard reset
# here clobbers post-launch doc commits (the 2026-06-08 paperwork-clobber). Skip it locally.
if [ "$HOST" != "5800x" ]; then
  git fetch "$SHARE/code_sync/carc_stage-b-wiring.bundle" stage-b-wiring && git reset --hard FETCH_HEAD \
    || { echo "FATAL: code sync failed on $HOST — refusing to generate self-play on STALE code" >&2; exit 1; }
fi
echo "  HEAD now: $(git rev-parse --short HEAD) (host=$HOST)"
[ -f "$WARM" ] || { echo "FATAL: WARM missing $WARM" >&2; exit 1; }
mkdir -p "$OUT"
SP_COMMON="--iter 0 --games $GAMES --sims $SIMS --leaf-eval v2_5 --value-blend 0 \
  --residual-scale $SCALE --value-target residual --batch-size 8 --checkpoint $WARM \
  --anchor-fraction 0 --output-root $OUT --shared-claim --claim-host $HOST --seed-start $SEED_START"

# USE_ORCH=1 routes the LOCAL box (5800x) through the carc-orch GPU orchestrator
# (per-forwarder CUDA streams → W~28 on one shared context = ~1.33x more games/min
# than orch-off; verdict 2026-06-15, result-IDENTICAL priors — just batched over
# SHM instead of per-worker forward). NOW ALSO ON XEON (A/B 2026-06-15: fwd-rate
# scales W10->W18 = 1.40x, GPU starved at W10; xeon has the binary + matching
# libtorch 2.11/cu128). LAPTOP stays orch-off (no Rust binary copied there).
USE_ORCH="${USE_ORCH:-0}"
if { [ "$HOST" = "5800x" ] || [ "$HOST" = "xeon" ]; } && [ "$USE_ORCH" = "1" ]; then
  # per-box worker default: 5800x VRAM allows W28; xeon (12-thread Turing) -> W18
  _OWD=28; [ "$HOST" = "xeon" ] && _OWD=18
  OW="${ORCH_WORKERS:-$_OWD}"; FWD="${ORCH_FWD:-4}"; MB="${ORCH_MAX_BATCH:-16}"
  SRV="$REPO/rust/carc-orch/run_server.sh"
  NS="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$WARM")"
  TS="/tmp/carc_fwgen_${HOST}.ts.pt"; SHMN="fwgen${HOST}"
  echo "  [orch] n_scalar=$NS  exporting $(basename "$WARM") -> TorchScript (parity-gated)"
  "$PY" scripts/export_torchscript.py --checkpoint "$WARM" --out "$TS" --device cuda \
    || { echo "FATAL: TorchScript export/parity failed — refusing to gen on orch path" >&2; exit 1; }
  pkill carc-orch 2>/dev/null; sleep 1; rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_*
  echo "  [orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB watchdog=30s)"
  nice -n 19 "$SRV" --model "$TS" --transport shm --shm-name "$SHMN" --workers "$OW" --n-scalar "$NS" \
    --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
    > "/tmp/carc_srv_${HOST}.log" 2>&1 &
  SRV_PID=$!
  trap 'kill $SRV_PID 2>/dev/null; pkill carc-orch 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN"'" /dev/shm/sem.carc_'"$SHMN"'_*' EXIT
  for _ in $(seq 1 80); do grep -q "forwarder-" "/tmp/carc_srv_${HOST}.log" 2>/dev/null && break; sleep 0.5; done
  grep -q "forwarder-" "/tmp/carc_srv_${HOST}.log" 2>/dev/null \
    || { echo "FATAL: carc-orch server failed to start" >&2; tail -10 "/tmp/carc_srv_${HOST}.log" >&2; exit 1; }
  echo "  [orch] server ready ($(grep -c 'CUDA stream=' "/tmp/carc_srv_${HOST}.log") streams); self-play W=$OW via SHM '$SHMN'"
  # shellcheck disable=SC2086
  env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 \
    nice -n 19 "$PY" -u scripts/run_selfplay_iter.py $SP_COMMON --workers "$OW" --shm-eval-server "$SHMN"
else
  # shellcheck disable=SC2086
  env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 \
    nice -n 19 "$PY" -u scripts/run_selfplay_iter.py $SP_COMMON --workers "$WORKERS"
fi
echo "=== gen_flywheel on $HOST FINISHED @ $(date) ==="
