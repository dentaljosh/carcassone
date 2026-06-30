#!/usr/bin/env bash
# Step-2 PeNS candidate-vs-RoD2 SCREEN through TWO carc-orch SHM GPU orchestrators
# (one per POLICY net; the two contexts share the one GPU). Net-on-CPU was the
# ~half-the-flywheel-iter blocker (~32 min/iter, ~24s/game @ sims100); the net
# forwards are ~85% of eval cost, so GPU-batching BOTH nets is the win (mirrors
# the orch verdict: W28 on one shared context, 1.33x over orch-off).
#
# Mirrors gen_step2_orch.sh + v28_net_vs_net_orch.sh: export each ckpt -> TorchScript
# (parity-gated), launch carc-orch --transport shm per side with UNIQUE per-agent
# shm-names, run eval_step2.py --shm-eval-server-cand/-ref, trap-clean BOTH servers +
# /dev/shm on exit. The orch serves PRIORS only; the VALUES stay in-worker on CPU
# (candidate = v2.9/scalar-MLP wean — UNCHANGED, incl. parent-threading + POV flip;
# reference = v2.9 leaf via make_v25_value_wrapper). The orch value is discarded.
#
#   CAND_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
#   REF_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
#   SCALAR=/home/doctor/carc_step2_pens/warmstart/warmstart.pt \
#   OW=28 SIMS=200 N=120 BLEND=0.2 DROPOUT=0.0 \
#   OUT=/mnt/c/carc-shared/step2_pens/eval/iter02 \
#   bash scripts/step2_pens/eval_step2_orch.sh
#
# MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3

CAND_CKPT=${CAND_CKPT:-/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt}  # candidate base POLICY net
REF_CKPT=${REF_CKPT:-/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt}    # reference (RoD2 iter_02)
SCALAR=${SCALAR:?set SCALAR=<warmstart.pt ScalarMLP for the candidate value wean>}
# OW = workers PER SERVER (two contexts on one GPU). Orch-optimal is local OW=28 on a
# SINGLE shared context (reference_carc_orch_verdict, 1.33x over orch-off). With TWO
# servers sharing the one GPU, OW=28 each runs 28 client workers, each holding one
# handle per server. RE-BENCH is the gold standard: the 89-feature path is a code-era
# change (feedback_worker_count_by_bottleneck) and two contexts contend on one GPU, so
# the W28-single-context verdict is a starting point, not a measured optimum here.
OW=${OW:-28}
SIMS=${SIMS:-200}
N=${N:-120}
BLEND=${BLEND:-0.2}
DROPOUT=${DROPOUT:-0.0}
SEED_START=${SEED_START:-5715000000}
OUT=${OUT:?set OUT=<output dir for per-game json + summary>}
FWD=${ORCH_FWD:-4}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"

# UNIQUE per-agent shm-names + TS paths + logs (cand vs ref; host-scoped so two boxes
# don't collide on the share).
TS_C="/tmp/carc_step2evC_${HOST}.ts.pt"
TS_R="/tmp/carc_step2evR_${HOST}.ts.pt"
SHMN_C="step2evC${HOST}"
SHMN_R="step2evR${HOST}"
LOG_C="/tmp/carc_srvStep2evC_${HOST}.log"
LOG_R="/tmp/carc_srvStep2evR_${HOST}.log"

# v2.9 bmild_cap8 leaf env (matches gen_step2_orch.sh / build_dataset's GUARD env; the
# orch net forward is leaf-independent but we keep the env consistent for the worker's
# value path — candidate wean + reference v2.9 leaf both ride this substrate).
LEAFENV="CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0 CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0"

cd "$REPO"

# --- export + n_scalar peek, per side (parity-gated; abort on fail) ---
NS_C="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$CAND_CKPT")"
NS_R="$("$PY" -c "import torch,sys; print(int(torch.load(sys.argv[1],map_location='cpu',weights_only=False).get('n_scalar_features',10)))" "$REF_CKPT")"
echo "[step2-eval-orch] CAND=$(basename "$CAND_CKPT") n_scalar=$NS_C  |  REF=$(basename "$REF_CKPT") n_scalar=$NS_R  exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CAND_CKPT" --out "$TS_C" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed for CANDIDATE" >&2; exit 1; }
"$PY" scripts/export_torchscript.py --checkpoint "$REF_CKPT" --out "$TS_R" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed for REFERENCE" >&2; exit 1; }

# --- clean stale carc-orch for THESE shm-names ONLY (do NOT global-pkill carc-orch:
#     that was BUG-2 — it kills a sibling box's / gen's orchestrator). $SRV_PID-scoped
#     kills + unique per-agent shm-names below. ---
rm -f "/dev/shm/carc_$SHMN_C" /dev/shm/sem.carc_"${SHMN_C}"_* \
      "/dev/shm/carc_$SHMN_R" /dev/shm/sem.carc_"${SHMN_R}"_* 2>/dev/null || true

# --- launch BOTH servers (W=OW each; two contexts on one GPU) ---
echo "[step2-eval-orch] start carc-orch CAND (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_C"
nice -n 19 "$SRV" --model "$TS_C" --transport shm --shm-name "$SHMN_C" --workers "$OW" --n-scalar "$NS_C" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG_C" 2>&1 &
SRV_C_PID=$!
echo "[step2-eval-orch] start carc-orch REF (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_R"
nice -n 19 "$SRV" --model "$TS_R" --transport shm --shm-name "$SHMN_R" --workers "$OW" --n-scalar "$NS_R" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG_R" 2>&1 &
SRV_R_PID=$!
# trap-clean BOTH servers (SRV_PID-scoped, NOT a global pkill) + their /dev/shm.
trap 'kill $SRV_C_PID $SRV_R_PID 2>/dev/null || true; rm -f "/dev/shm/carc_'"$SHMN_C"'" /dev/shm/sem.carc_'"$SHMN_C"'_* "/dev/shm/carc_'"$SHMN_R"'" /dev/shm/sem.carc_'"$SHMN_R"'_*' EXIT

# --- wait for "forwarder-" in BOTH logs (80 x 0.5s each); FATAL if either fails ---
for _ in $(seq 1 80); do
  grep -q "forwarder-" "$LOG_C" 2>/dev/null && break
  kill -0 "$SRV_C_PID" 2>/dev/null || { echo "FATAL: carc-orch CAND died early" >&2; tail -15 "$LOG_C" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG_C" 2>/dev/null \
  || { echo "FATAL: carc-orch CAND failed to start" >&2; tail -12 "$LOG_C" >&2; exit 1; }
for _ in $(seq 1 80); do
  grep -q "forwarder-" "$LOG_R" 2>/dev/null && break
  kill -0 "$SRV_R_PID" 2>/dev/null || { echo "FATAL: carc-orch REF died early" >&2; tail -15 "$LOG_R" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG_R" 2>/dev/null \
  || { echo "FATAL: carc-orch REF failed to start" >&2; tail -12 "$LOG_R" >&2; exit 1; }
echo "[step2-eval-orch] both servers up; launching eval_step2 (W=$OW sims=$SIMS n=$N blend=$BLEND dropout=$DROPOUT)"

# --- run the client ---
# shellcheck disable=SC2086
env $LEAFENV nice -n 19 "$PY" -u scripts/step2_pens/eval_step2.py \
  --ckpt "$CAND_CKPT" --scalar-ckpt "$SCALAR" --ref-ckpt "$REF_CKPT" \
  --shm-eval-server-cand "$SHMN_C" --shm-eval-server-ref "$SHMN_R" \
  --blend "$BLEND" --dropout "$DROPOUT" --n "$N" --sims "$SIMS" --workers "$OW" \
  --seed-start "$SEED_START" --out "$OUT" \
  "$@"
